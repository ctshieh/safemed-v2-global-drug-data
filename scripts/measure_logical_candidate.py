#!/usr/bin/env python3
"""Read-only logical SQLite measurements; never grants activation/rights approval."""
import argparse,gzip,hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path
from produce_contract_snapshot import gate
LIMITS={'sqlite_bytes':33554432,'package_rows':250000,'query_rows':30000,'query_text_blob_bytes':16777216,'cell_bytes':65536,'row_text_blob_bytes':262144,'package_text_blob_bytes':134217728,'query_json_nodes':200000,'package_json_nodes':1000000,'cell_json_nodes':4096,'columns':128}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def nodes(value):
 count=0; stack=[value]
 while stack:
  x=stack.pop();count+=1
  if isinstance(x,dict):stack.extend(x.values());count+=len(x)
  elif isinstance(x,list):stack.extend(x)
 return count
def measure(path,gzip_path=None,test_only=False):
 path=Path(path); tables={};violations=[];fixture_markers=[];json_errors=[];total_nodes=0
 with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
  c.execute('pragma query_only=ON')
  integrity=[x[0] for x in c.execute('pragma integrity_check')];fk=[list(x) for x in c.execute('pragma foreign_key_check')]
  actual={x[0] for x in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")};required=set(gate.CONTRACT['required_tables'])
  for table in sorted(actual):
   q='"'+table.replace('"','""')+'"';cols=[x[1] for x in c.execute('pragma table_info('+q+')')]
   stat={'rows':0,'text_bytes':0,'blob_bytes':0,'max_cell_bytes':0,'max_row_text_blob_bytes':0,'max_json_nodes':0,'json_nodes':0,'columns':len(cols)}
   # Measure large cells inside SQLite before retrieving values; fetch only bounded
   # cells for JSON/fixture inspection. Oversized cells remain exact in byte totals.
   expr=['case when typeof("'+x.replace('"','""')+'") in (\'text\',\'blob\') then length(cast("'+x.replace('"','""')+'" as blob)) else 0 end' for x in cols]
   for lengths in c.execute('select '+','.join(expr)+' from '+q):
    stat['rows']+=1;stat['max_cell_bytes']=max(stat['max_cell_bytes'],max(lengths,default=0));stat['max_row_text_blob_bytes']=max(stat['max_row_text_blob_bytes'],sum(lengths))
   for col in cols:
    qc='"'+col.replace('"','""')+'"'
    for kind,n in c.execute('select typeof('+qc+'),sum(length(cast('+qc+' as blob))) from '+q+' where typeof('+qc+") in ('text','blob') group by typeof("+qc+')'):
     stat[kind+'_bytes']+=n or 0
    for (value,) in c.execute('select '+qc+' from '+q+' where typeof('+qc+")='text' and length(cast("+qc+' as blob)) <= ?', (LIMITS['cell_bytes'],)):
     if any(marker in value.upper() for marker in ('TEST_FIXTURE','TEST_ONLY','TEST-ONLY','SEED_ONLY')) and len(fixture_markers)<30:fixture_markers.append({'table':table,'column':col})
     if col.endswith('_json') or col in ('source_snapshots','compatible_app_major_versions'):
      try:
       def reject(x):raise ValueError('Nonfinite JSON')
       n=nodes(json.loads(value,parse_constant=reject));stat['max_json_nodes']=max(stat['max_json_nodes'],n);stat['json_nodes']+=n
      except (ValueError,RecursionError) as e:
       if len(json_errors)<30:json_errors.append({'table':table,'column':col,'error':str(e)})
   tables[table]=stat
   for key,limit in [('rows','query_rows'),('max_cell_bytes','cell_bytes'),('max_row_text_blob_bytes','row_text_blob_bytes'),('max_json_nodes','cell_json_nodes'),('columns','columns'),('json_nodes','query_json_nodes')]:
    if stat[key]>LIMITS[limit]:violations.append(table+':'+limit)
   if stat['text_bytes']+stat['blob_bytes']>LIMITS['query_text_blob_bytes']:violations.append(table+':query_text_blob_bytes')
  try:contract={'status':'PASS','result':gate.validate(path,test_only=test_only)}
  except Exception as e:contract={'status':'FAIL','error':type(e).__name__+': '+str(e)}
  indexes=[{'name':x[0],'table':x[1],'sql':x[2]} for x in c.execute("select name,tbl_name,sql from sqlite_master where type='index'")]
  try:index_sizes=[dict(zip(('name','bytes','pages'),x)) for x in c.execute('select name,sum(pgsize),count(*) from dbstat group by name')]
  except sqlite3.DatabaseError:index_sizes=None
  plans={}
  for table,column in [('drugs','drug_id'),('drug_product_identity','drug_id'),('ingredient_sources','ingredient_id'),('id_ledger','stable_id')]:
   if table in actual:
    try:plans[table]=[list(x) for x in c.execute('explain query plan select * from '+table+' where '+column+'=?',('candidate-measurement',))]
    except sqlite3.DatabaseError:pass
  user_version=c.execute('pragma user_version').fetchone()[0]
 required_stats=[s for t,s in tables.items() if t in required];rows=sum(s['rows'] for s in required_stats);textblob=sum(s['text_bytes']+s['blob_bytes'] for s in required_stats);total_nodes=sum(s['json_nodes'] for s in required_stats)
 for key,value in [('sqlite_bytes',path.stat().st_size),('package_rows',rows),('package_text_blob_bytes',textblob),('package_json_nodes',total_nodes)]:
  if value>LIMITS[key]:violations.append(key)
 compressed=None
 if gzip_path:
  gp=Path(gzip_path);h=hashlib.sha256();n=0
  with gzip.open(gp,'rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):
    h.update(b);n+=len(b)
    if n>path.stat().st_size:break
  compressed={'file':str(gp.resolve()),'gzip_bytes':gp.stat().st_size,'gzip_sha256':sha(gp),'expanded_bytes':n,'matches_logical_sqlite':n==path.stat().st_size and h.hexdigest()==sha(path)}
 schema_ok=actual==required and user_version==20100
 return {'logical_sqlite':{'file':str(path.resolve()),'sqlite_bytes':path.stat().st_size,'sqlite_sha256':sha(path)},'gzip':compressed,'schema':{'exact_required_tables':schema_ok,'missing':sorted(required-actual),'unexpected':sorted(actual-required),'user_version':user_version},'integrity':integrity,'foreign_key_violations':fk,'contract_validation':contract,'tables':tables,'required_table_rows':rows,'required_table_text_blob_bytes':textblob,'required_table_json_nodes':total_nodes,'json_errors':json_errors,'fixture_markers':fixture_markers,'test_only':test_only,'indexes':indexes,'page_sizes':index_sizes,'example_query_plans':plans,'measurement_limits':['Per-table query budget is a conservative SELECT * table estimate, not a proof of all native query paths','JSON node counts are structural estimates; native consumer remains authoritative','JSON/fixture inspection skips cells over 64KiB; exact SQL byte measurements still detect them','Frozen Python gate provides full schema/clinical checks; successful gate does not supply absent rights or signatures'],'formal_app_limits':LIMITS,'budget_violations':violations,'budget_compatible':not violations,'runtime_consumer_compatible':False,'runtime_reason':'Measurements are not native signed-envelope/activation acceptance; current formal limits unchanged; unsigned candidate never auto-approved','release_eligible':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sqlite',type=Path,required=True);p.add_argument('--gzip',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--test-only',action='store_true');a=p.parse_args();r=measure(a.sqlite,a.gzip,a.test_only);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'output':str(a.output),'sqlite_bytes':r['logical_sqlite']['sqlite_bytes'],'rows':r['required_table_rows'],'runtime_consumer_compatible':False}))
