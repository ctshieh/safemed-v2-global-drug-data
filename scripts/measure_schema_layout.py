#!/usr/bin/env python3
"""Independent exact frozen SQLite layout comparison; no gate size override."""
import argparse,hashlib,json,sqlite3,re
from contextlib import closing
from pathlib import Path
from produce_contract_snapshot import gate,C

def indexes(c,table):
 q='"'+table.replace('"','""')+'"';result=[]
 for row in c.execute('pragma index_list('+q+')'):
  name=row[1];x=[list(r) for r in c.execute('pragma index_xinfo("'+name.replace('"','""')+'")')]
  result.append({'name':name,'unique':row[2],'origin':row[3],'partial':row[4],'xinfo':x})
 return sorted(result,key=lambda x:x['name'])
def inspect(path,physical_layout='frozen'):
 if physical_layout not in {'frozen','compact-source-v1'}:raise ValueError('Unsupported physical layout')
 results={}
 with closing(sqlite3.connect(':memory:')) as gold,closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as actual:
  schema=gate.SCHEMA
  if physical_layout=='compact-source-v1':
   # Only the already-declared storage optimization for these three exact
   # composite-key tables. Columns, types, PK/unique/FK constraints and every
   # other index must still match. This is not formal runtime acceptance.
   for table in ['drug_source_links','ingredient_sources','id_ledger']:
    schema,n=re.subn(r'(CREATE TABLE '+table+r'\s*\(.*?\));',r'\1 WITHOUT ROWID;',schema,flags=re.S)
    if n!=1:raise ValueError('Frozen storage declaration changed '+table)
  gold.executescript(schema)
  for t in gate.CONTRACT['required_tables']:
   row={};q='"'+t+'"'
   for p in ['table_info','foreign_key_list']:
    e=[list(x) for x in gold.execute('pragma '+p+'('+q+')')];a=[list(x) for x in actual.execute('pragma '+p+'('+q+')')];row[p]={'match':e==a,'expected':e,'actual':a}
   e=indexes(gold,t);a=indexes(actual,t);row['indexes']={'match':e==a,'expected':e,'actual':a}
   results[t]=row
  ident=indexes(actual,'drug_product_identity')
  exact_identity=any(i['unique']==1 and i['partial']==0 and [(x[2],x[4],x[3]) for x in i['xinfo'] if x[5]==1]==[('jurisdiction','BINARY',0),('identifier_namespace','BINARY',0),('local_product_id','BINARY',0)] for i in ident)
 return {'status':'PASS' if exact_identity and all(x[p]['match'] for x in results.values() for p in ['table_info','foreign_key_list','indexes']) else 'FAIL','physical_layout':physical_layout,'schema_layout':results,'exact_full_unique_binary_identity_index':exact_identity,'contract_schema_sha256':hashlib.sha256((C/'schema.sql').read_bytes()).hexdigest(),'sqlite_bytes':Path(path).stat().st_size,'formal_gate_pass':False,'scope':'Exact required table column/FK/index PRAGMA comparison for the explicitly selected physical layout, independent of whole-file/row size gates. Not a substitute for formal contract or native consumer acceptance.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sqlite',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--physical-layout',choices=['frozen','compact-source-v1'],default='frozen');a=p.parse_args();r=inspect(a.sqlite,a.physical_layout);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':r['status'],'schema_layout_tables':len(r['schema_layout']),'identity_index':r['exact_full_unique_binary_identity_index']}));raise SystemExit(0 if r['status']=='PASS' else 1)
