#!/usr/bin/env python3
"""Independently compare normalized TW/CA/FR candidate fields to original intake JSON.
No builder imports. Original-to-intake byte/row reconciliation is a separate required
proof. Native code is not a standalone runtime column: audit code-derived entity ID
and exact source locator, preserving the original code in the external source archive.
"""
import argparse,collections,hashlib,json,sqlite3,sys
from pathlib import Path

def j(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def entity_id(kind,*parts):return kind+':'+hashlib.sha256(j(parts).encode('utf-8')).hexdigest()
def ro(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def component_fields(market,x):
 if market=='TW':return x.get('成分名稱'),x.get('成分代碼'),j({k:x.get(k,'') for k in ['含量描述','含量','含量單位']}),x.get('含量單位'),x.get('處方標示'),'UNKNOWN'
 if market=='CA':return x.get('ingredient_name'),None,x.get('strength'),x.get('strength_unit'),j({k:x.get(k,'') for k in ['dosage_unit','dosage_value']}),'ACTIVE'
 if market=='FR':return x[3],x[2],x[4],None,j({'reference_dosage':x[5],'element':x[1],'source_role_code':x[6],'source_link_number':x[7] if len(x)>7 else ''}),'UNKNOWN'
 raise ValueError('Unexpected market')
def run(inputs,candidate,out):
 if out.exists():raise ValueError('Refuse overwriting immutable reconciliation evidence')
 out.mkdir(parents=True);(out/'audit-script.py').write_bytes(Path(__file__).read_bytes());stage=sqlite3.connect(out/'comparison-staging.sqlite3');stage.row_factory=sqlite3.Row
 stage.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;')
 stage.executescript('''CREATE TABLE products(market TEXT,native TEXT,namespace TEXT,sid TEXT,display TEXT,chinese TEXT,english TEXT,form TEXT,route TEXT,seen INTEGER DEFAULT 0,PRIMARY KEY(market,native));
CREATE TABLE medical(market TEXT,native TEXT,text TEXT,PRIMARY KEY(market,native,text));
CREATE TABLE aliases(market TEXT,native TEXT,alias TEXT,language TEXT,kind TEXT,PRIMARY KEY(market,native,alias,language));
CREATE TABLE links(market TEXT,native TEXT,sid TEXT,purpose TEXT,locator TEXT,PRIMARY KEY(market,native,sid,purpose,locator));
CREATE TABLE components(sid TEXT,locator TEXT,market TEXT,native TEXT,namespace TEXT,seq INTEGER,name TEXT,strength TEXT,unit TEXT,basis TEXT,role TEXT,code TEXT,iid TEXT,seen INTEGER DEFAULT 0,PRIMARY KEY(sid,locator));
CREATE TABLE entities(iid TEXT PRIMARY KEY,name TEXT,normalized TEXT);
CREATE TABLE entity_sources(iid TEXT,sid TEXT,locator TEXT,PRIMARY KEY(iid,sid,locator));''')
 srcs={};cons={};input_db_hashes={}
 for group,name in [('TW','TW_UNREVIEWED_candidate.sqlite3'),('CA-EMA','INTERNATIONAL_UNREVIEWED_candidate.sqlite3'),('FR','FR_UNREVIEWED_candidate.sqlite3')]:
  p=inputs/group/name;c=ro(p);cons[group]=c
  for sid,m in c.execute('select source_snapshot_id,metadata_json from candidate_sources'):srcs[sid]=json.loads(m)
 bykey={sid.split('-sha256-')[0]:sid for sid in srcs};stats=collections.Counter();exclusions=[];seqs=collections.Counter();occurrences=collections.Counter()
 specs=[('TW','TFDA_LICENSE','TW','tfda-36','candidate_source_rows','row_number'),('CA','HEALTH_CANADA_DPD_DRUG_CODE','CA-EMA','ca-dpd-products','candidate_source_rows','source_order'),('FR','BDPM_CIS','FR','fr-bdpm-CIS_bdpm.txt','candidate_rows','source_order')]
 for market,ns,group,key,table,order in specs:
  sid=bykey[key]
  for r in cons[group].execute(f'select * from {table} where source_snapshot_id=? order by {order}',(sid,)):
   x=json.loads(r['raw_columns_json'] if market=='FR' else r['raw_assertions_json'])
   if market=='TW':native=r['local_product_id'];name=x.get('中文品名') or x.get('英文品名');cn=x.get('中文品名');en=x.get('英文品名');form=x.get('劑型');route=None;med={k:x.get(k,'') for k in ['適應症','用法用量','主成分略述']}
   elif market=='CA':native=r['native_record_id'];name=x.get('brand_name');cn=None;en=name;form=route=None;med={k:x.get(k,'') for k in ['class_name','drug_identification_number','descriptor','number_of_ais']}
   else:native=x[0];name=x[1];cn=en=None;form=x[2];route=x[3];med={'authorization_status':x[4],'marketing_status':x[6]}
   if not native or not name or not name.strip():exclusions.append({'kind':'PRODUCT','market':market,'source_id':sid,'source_locator':r['source_locator'],'native_product_id':native,'reason':'Missing native identifier or nonblank product name'});continue
   stage.execute('insert or ignore into products(market,native,namespace,sid,display,chinese,english,form,route) values(?,?,?,?,?,?,?,?,?)',(market,str(native),ns,sid,name,cn,en,form,route))
   stage.execute('insert or ignore into medical values(?,?,?)',(market,str(native),j(med)))
   aliases=[(cn,'zh-Hant','OFFICIAL_CHINESE_PRODUCT_NAME'),(en,'en','OFFICIAL_ENGLISH_PRODUCT_NAME')] if market=='TW' else [(name,'en' if market=='CA' else 'fr','OFFICIAL_PRODUCT_NAME')]
   for alias,language,kind in aliases:
    if alias and alias.strip():stage.execute('insert or ignore into aliases values(?,?,?,?,?)',(market,str(native),alias,language,kind))
   stage.execute('insert or ignore into links values(?,?,?,?,?)',(market,str(native),sid,'IDENTITY',r['source_locator']));stats[market+':source_identity_rows']+=1
  print('Prepared product originals',market,flush=True)
 specs=[('TW','TFDA_LICENSE','TW','tfda-43','candidate_source_rows','row_number','local_product_id'),('CA','HEALTH_CANADA_DPD_DRUG_CODE','CA-EMA','ca-dpd-active-ingredients','candidate_source_rows','source_order','native_record_id'),('FR','BDPM_CIS','FR','fr-bdpm-CIS_COMPO_bdpm.txt','candidate_rows','source_order','native_cis_reference')]
 for market,ns,group,key,table,order,nativefield in specs:
  sid=bykey[key]
  for r in cons[group].execute(f'select * from {table} where source_snapshot_id=? order by {order}',(sid,)):
   x=json.loads(r['raw_columns_json'] if market=='FR' else r['raw_assertions_json']);native=str(r[nativefield]);loc=r['source_locator'];name,code,strength,unit,basis,role=component_fields(market,x);stats[market+':source_component_rows']+=1
   reason=None
   if not stage.execute('select 1 from products where market=? and native=?',(market,native)).fetchone():reason='No selected matching native product identity; original retained in source archive'
   elif not name or not name.strip():reason='Empty ingredient name: runtime name_as_listed is nonempty; original retained without inventing a name'
   if reason:
    exclusions.append({'kind':'INGREDIENT','market':market,'source_id':sid,'source_locator':loc,'source_order':r[order],'native_product_id':native,'ingredient_code':code,'original_name':name,'original_row':x,'reason':reason});continue
   seq=seqs[(market,native)];seqs[(market,native)]+=1
   # Independently reproduce the explicitly documented source-native entity identity.
   rawkey=(key,native,name,strength,unit,basis,role);occurrence=occurrences[rawkey];occurrences[rawkey]+=1
   iid=entity_id('ingredient',*((key,str(code),name) if code else (*rawkey,occurrence)))
   stage.execute('insert into components(sid,locator,market,native,namespace,seq,name,strength,unit,basis,role,code,iid) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,loc,market,native,ns,seq,name,strength,unit,basis,role,code,iid))
   stage.execute('insert or ignore into entities values(?,?,?)',(iid,name,' '.join(name.casefold().split())))
   stage.execute('insert or ignore into entity_sources values(?,?,?)',(iid,sid,loc))
   stage.execute('insert or ignore into links values(?,?,?,?,?)',(market,native,sid,'COMPOSITION',loc));stats[market+':expected_runtime_component_rows']+=1
  print('Prepared component originals',market,flush=True)
 stage.commit();mismatches=0;checked=collections.Counter();mismatch_kinds=collections.Counter()
 with (out/'mismatches.jsonl').open('w') as f:
  def fail(kind,expected,actual,**where):
   nonlocal mismatches
   mismatches+=1;mismatch_kinds[kind]+=1;f.write(j({'kind':kind,'expected':expected,'actual':actual,**where})+'\n')
  c=ro(candidate)
  stage.execute('create table actual_aliases(drug_id text,alias text,language text,kind text)')
  stage.executemany('insert into actual_aliases values(?,?,?,?)',c.execute('select drug_id,alias,language,alias_type from drug_aliases'))
  stage.execute('create index actual_alias_product on actual_aliases(drug_id)')
  for r in c.execute('''select p.*,i.jurisdiction,i.identifier_namespace,i.local_product_id from product_ingredient_rows p left join drug_product_identity i using(drug_id)'''):
   e=stage.execute('select * from components where sid=? and locator=?',(r['source_id'],r['source_locator'])).fetchone();checked['runtime_component_rows']+=1
   if e is None:fail('Unexpected runtime component',None,dict(r));continue
   if e['seen']:fail('Duplicate source component',dict(e),dict(r))
   stage.execute('update components set seen=seen+1 where sid=? and locator=?',(e['sid'],e['locator']))
   pairs={'source_order':'seq','name_as_listed':'name','strength_text':'strength','strength_unit':'unit','basis_text':'basis','role':'role','jurisdiction':'market','identifier_namespace':'namespace','local_product_id':'native'}
   for actual,expected in pairs.items():
    if r[actual]!=e[expected]:fail('Component field differs',e[expected],r[actual],source_id=e['sid'],source_locator=e['locator'],field=actual)
   for actual,expected in [('mapping_status','UNMAPPED'),('ingredient_id',None),('strength_value',None)]:
    if r[actual]!=expected:fail('Unexpected clinical mapping/value',expected,r[actual],source_id=e['sid'],source_locator=e['locator'],field=actual)
  for e in stage.execute('select * from components where seen!=1'):fail('Source component multiset mismatch',dict(e),None)
  print('Compared component rows',checked['runtime_component_rows'],flush=True)
  for r in c.execute('select * from ingredients'):
   checked['source_scoped_ingredient_entities']+=1;e=stage.execute('select * from entities where iid=?',(r['ingredient_id'],)).fetchone()
   if not e:fail('Unexpected source-scoped ingredient entity',None,dict(r));continue
   if (r['canonical_name'],r['normalized_name'])!=(e['name'],e['normalized']):fail('Source-scoped ingredient name differs',dict(e),dict(r))
  expected_entities=stage.execute('select count(*) from entities').fetchone()[0]
  if checked['source_scoped_ingredient_entities']!=expected_entities:fail('Ingredient entity count differs',expected_entities,checked['source_scoped_ingredient_entities'])
  # Actual evidence multiset is compared through an independent temporary table.
  stage.execute('create table actual_entity_sources(iid text,sid text,locator text)')
  stage.executemany('insert into actual_entity_sources values(?,?,?)',c.execute('select ingredient_id,source_id,source_locator from ingredient_sources'))
  for sql,kind in [('select * from entity_sources except select * from actual_entity_sources','Missing ingredient direct evidence'),('select * from actual_entity_sources except select * from entity_sources','Unexpected ingredient direct evidence')]:
   for r in stage.execute(sql):fail(kind,None,list(r))
  for r in c.execute('select d.*,i.jurisdiction,i.identifier_namespace,i.local_product_id from drugs d left join drug_product_identity i using(drug_id)'):
   checked['runtime_products']+=1;market,native=r['jurisdiction'],r['local_product_id'];e=stage.execute('select * from products where market=? and native=?',(market,native)).fetchone()
   if e is None:fail('Unexpected product native identity',None,dict(r));continue
   if e['seen']:fail('Duplicate product native identity',dict(e),r['drug_id'])
   stage.execute('update products set seen=seen+1 where market=? and native=?',(market,native))
   for actual,expected in {'identifier_namespace':'namespace','display_name':'display','chinese_name':'chinese','english_name':'english','dosage_form':'form','route':'route','source':'sid'}.items():
    if r[actual]!=e[expected]:fail('Product field differs',e[expected],r[actual],market=market,native=native,field=actual)
   if r['source_version']!=srcs[e['sid']]['version_label']:fail('Product source version differs',srcs[e['sid']]['version_label'],r['source_version'],market=market,native=native)
   if r['generic_name']!='' or r['data_completeness']!='UNKNOWN':fail('Unreviewed generic/completeness changed',['','UNKNOWN'],[r['generic_name'],r['data_completeness']],market=market,native=native)
   meta=json.loads(r['metadata_json']);actualmed=sorted(j(x) for x in meta.get('original_medical_assertions',[]));expectedmed=sorted(x[0] for x in stage.execute('select text from medical where market=? and native=?',(market,native)))
   if actualmed!=expectedmed:fail('Original medical assertion set differs',expectedmed,actualmed,market=market,native=native)
   expectedaliases=sorted(tuple(x) for x in stage.execute('select alias,language,kind from aliases where market=? and native=?',(market,native)));actualaliases=sorted(tuple(x) for x in stage.execute('select alias,language,kind from actual_aliases where drug_id=?',(r['drug_id'],)))
   if market=='TW' and len({a for a,lang,kind in expectedaliases if lang=='en'} & {a for a,lang,kind in expectedaliases if lang=='zh-Hant'}):checked['tw_products_with_same_literal_both_declared_languages']+=1
   checked['runtime_alias_rows_compared']+=len(actualaliases)
   if actualaliases!=expectedaliases:fail('Original product names/aliases differ',sorted(expectedaliases),sorted(actualaliases),market=market,native=native)
   expectedlinks=sorted(tuple(x) for x in stage.execute('select sid,purpose,locator from links where market=? and native=?',(market,native)));actuallinks=sorted(tuple(x) for x in c.execute('select source_id,purpose,source_locator from drug_source_links where drug_id=?',(r['drug_id'],)))
   if expectedlinks!=actuallinks:fail('Product source link multiset differs',expectedlinks,actuallinks,market=market,native=native)
   if sorted(meta.get('safemed_product_identity',{}).get('source_ids',[]))!=sorted({x[0] for x in expectedlinks}):fail('Metadata source IDs differ',sorted({x[0] for x in expectedlinks}),meta,market=market,native=native)
  for e in stage.execute('select * from products where seen!=1'):fail('Source product identity multiset mismatch',dict(e),None)
 stage.commit()
 (out/'EXCLUSIONS.json').write_text(json.dumps({'excluded_count':len(exclusions),'records':exclusions,'original_rows_retained_in_source_archive':True},ensure_ascii=False,indent=2)+'\n')
 result={'status':'PASS' if mismatches==0 else 'FAIL','checks':dict(checked),'original_counts':dict(stats),'mismatch_records':mismatches,'mismatch_kind_counts':dict(mismatch_kinds),'candidate_sha256':hashlib.file_digest(open(candidate,'rb'),'sha256').hexdigest(),'excluded_rows':len(exclusions),'excluded_empty_name_rows':sum('Empty ingredient name' in x['reason'] for x in exclusions),'methods':['Independently decode original source JSON/tab-column positions without importing builder','Exact component fields, namespace/native identity, per-product ordering, locator and original-row multiset; explicit source exclusions','All product primary/translated names and complete aliases, source versions, metadata original medical assertion sets, exact source links','Native ingredient codes checked via documented source-scoped entity ID derivation and direct evidence sets; product mappings remain UNMAPPED'],'limitations':['Original native ingredient code is retained in external source archive, not standalone plain runtime column; entity ID is not chemical equivalence or clinical mapping','Product medical assertions compare distinct complete assertion objects, matching candidate set semantics; original multiplicity remains explicit in source links','No independent reparse of original downloads in this tool: use separate original-source reconciliation PASS','No claim of clinical correctness, complete composition, commercial readiness, or official product endorsement'],'candidate_path':str(candidate.resolve()),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'clinical_approval':False}
 (out/'LOGICAL_RECONCILIATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(j(result),flush=True);return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();r=run(a.inputs,a.candidate,a.output_dir);sys.exit(0 if r['status']=='PASS' else 1)
