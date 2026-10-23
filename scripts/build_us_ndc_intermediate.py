#!/usr/bin/env python3
"""Rebuild a US NDC source-native intermediate from retained full FDA bulk bytes.
Not contract1.0 runtime; no canonical equivalence, listing approval, or clinical claims.
"""
import argparse,collections,datetime,hashlib,json,re,sqlite3,traceback,zipfile
from pathlib import Path

def js(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(x):return hashlib.sha256(js(x).encode()).hexdigest()
def strict_pairs(items):
 d={}
 for k,v in items:
  if k in d:raise ValueError('Duplicate original JSON field '+k)
  d[k]=v
 return d

def run(root,output,retain_unreconciled=False):
 if output.exists():raise ValueError('Immutable output exists')
 output.mkdir(parents=True);partitions=json.loads((root/'NDC_PARTITIONS.json').read_text());cat=partitions['ndc'];manifest=[]
 db=sqlite3.connect(output/'US_NDC_source_native.sqlite3');db.execute('pragma foreign_keys=on');db.executescript('''
CREATE TABLE source_registry(source_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL);
CREATE TABLE source_records(source_id TEXT NOT NULL,record_index INTEGER NOT NULL,locator TEXT PRIMARY KEY,native_id TEXT,record_sha256 TEXT NOT NULL,original_json TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES source_registry(source_id));
CREATE INDEX source_records_native ON source_records(native_id);
CREATE TABLE products(native_id TEXT PRIMARY KEY,display_name TEXT,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT NOT NULL,components_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,original_json TEXT NOT NULL,jurisdiction TEXT NOT NULL,identifier_namespace TEXT NOT NULL,labeler_name TEXT,product_type TEXT,marketing_category TEXT,composition_status TEXT NOT NULL,review_status TEXT NOT NULL);
CREATE TABLE components(native_id TEXT NOT NULL,source_order INTEGER NOT NULL,name_as_listed TEXT,strength_text TEXT,role TEXT NOT NULL,mapping_status TEXT NOT NULL,source_refs_json TEXT NOT NULL,original_json TEXT NOT NULL,PRIMARY KEY(native_id,source_order),FOREIGN KEY(native_id) REFERENCES products(native_id));
CREATE TABLE packages(native_id TEXT NOT NULL,package_ndc TEXT,source_order INTEGER NOT NULL,source_refs_json TEXT NOT NULL,original_json TEXT NOT NULL,PRIMARY KEY(native_id,source_order),FOREIGN KEY(native_id) REFERENCES products(native_id));
CREATE TABLE exclusions(source_id TEXT,record_index INTEGER,reason TEXT,original_json TEXT);
''');total=0;catalogue_issues=[];stats=collections.Counter();typecounts=collections.Counter();maxingredients=0
 for partition in cat['partitions']:
  zipname=Path(partition['file']).name;p=root/'raw'/zipname;download=json.loads(p.with_name(p.name+'.download.json').read_text());assert sha(p)==download['sha256']
  with zipfile.ZipFile(p) as z:
   files=z.infolist()
   if len(files)!=1 or Path(files[0].filename).name!=files[0].filename or not files[0].filename.endswith('.json') or files[0].file_size>1024**3:raise ValueError('Unexpected or excessive ZIP members')
   info=files[0];raw=z.read(info);rawsha=hashlib.sha256(raw).hexdigest();member=output/info.filename;member.write_bytes(raw)
  sourceid='us-openfda-ndc-sha256-'+rawsha
  payload=json.loads(raw,object_pairs_hook=strict_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')));records=payload['results']
  if not isinstance(records,list) or not records:raise ValueError('Empty partition')
  if payload.get('meta',{}).get('results',{}).get('total')!=len(records):raise ValueError('Bulk self-declared total does not equal actual records')
  if len(records)!=partition['records']:
   issue={'kind':'OFFICIAL_CATALOGUE_VS_BULK_COUNT_MISMATCH','catalogue_records':partition['records'],'bulk_meta_records':payload['meta']['results']['total'],'actual_records':len(records),'catalogue_export_date':cat['export_date'],'bulk_last_updated':payload['meta'].get('last_updated'),'url':partition['file']};catalogue_issues.append(issue)
   if not retain_unreconciled:raise ValueError('Empty/incomplete partition or upstream catalogue discrepancy: '+js(issue))
  metadata={'source_id':sourceid,'publisher':'U.S. Food and Drug Administration / openFDA NDC Directory','jurisdiction':'US','url':partition['file'],'directory_url':'https://open.fda.gov/apis/drug/ndc/','download_catalogue_url':'https://api.fda.gov/download.json','export_date':cat['export_date'],'retrieved_at':download['utc_finished'],'transport_sha256':download['sha256'],'original_json_sha256':rawsha,'original_json_member':info.filename,'record_count':len(records),'api_meta':payload.get('meta'),'download_meta':download,'license_url':'https://open.fda.gov/license/','terms_url':'https://open.fda.gov/terms/','license':'CC0 1.0 default; stated exclusions/third-party rights apply','rights_review':'AUTOMATED_OFFICIAL_TERMS_EVIDENCE_NOT_CLINICAL_APPROVAL','composition_status':'UNKNOWN','clinical_review':'PENDING','clinical_rules_active':0,'coverage':'Entire named bulk NDC export, not all US drugs, approval records, labels or interactions'}
  db.execute('insert into source_registry values(?,?)',(sourceid,js(metadata)));manifest.append(metadata)
  for index,record in enumerate(records):
   rawtext=js(record);recordsha=hashlib.sha256(rawtext.encode()).hexdigest();native=record.get('product_ndc');loc=f'record:{sourceid}/file/{info.filename}/index/{index}/record-sha256/{recordsha}'
   db.execute('insert into source_records values(?,?,?,?,?,?)',(sourceid,index,loc,native if isinstance(native,str) else None,recordsha,rawtext));total+=1
   if not isinstance(native,str) or len(native)>200 or not re.fullmatch(r'[0-9]+-[0-9]+',native):db.execute('insert into exclusions values(?,?,?,?)',(sourceid,index,'INVALID_NATIVE_PRODUCT_NDC_NO_ID_FABRICATED',rawtext));stats['excluded_invalid_native_id']+=1
  print('Retained original partition records',len(records),flush=True);del records,payload,raw
 if total!=cat['total_records'] and not retain_unreconciled:raise ValueError('Catalogue full total differs')
 native_ids=[r[0] for r in db.execute('select distinct native_id from source_records where native_id is not null order by native_id')]
 for native in native_ids:
  if len(native)>200 or not re.fullmatch(r'[0-9]+-[0-9]+',native):continue
  originalrows=list(db.execute('select source_id,record_index,locator,record_sha256,original_json from source_records where native_id=? order by source_id,record_index',(native,)))
  variants={};refs=[]
  for sid,index,loc,h,rawtext in originalrows:
   ref={'source_id':sid,'source_locator':loc,'record_sha256':h,'record_index':index}
   refs.append(ref);variants.setdefault(h,{'row':json.loads(rawtext),'refs':[]})['refs'].append(ref)
  values=list(variants.values());objects=[v['row'] for v in values];stats['exact_duplicate_source_record_projections_removed']+=len(originalrows)-len(values)
  if len(values)>1:stats['native_ids_with_distinct_source_variants']+=1
  def consistent(field):
   v=[r.get(field) for r in objects];return v[0] if all(js(x)==js(v[0]) for x in v) else None
  aliases=[]
  for r in objects:
   for field in ['brand_name','brand_name_base','generic_name']:
    value=r.get(field)
    if isinstance(value,str) and value.strip() and value not in aliases:aliases.append(value)
   for field in ['brand_name','generic_name']:
    for value in r.get('openfda',{}).get(field,[]):
     if isinstance(value,str) and value.strip() and value not in aliases:aliases.append(value)
  display=consistent('brand_name') or consistent('generic_name')
  if not isinstance(display,str) or not display.strip():stats['products_without_unambiguous_display_name']+=1
  # Only duplicate full ingredient-list projections are collapsed. Within-source duplicate
  # ingredient positions (including third-plus entries) are always retained.
  ingredientlists={};packagelists={}
  for v in values:
   row=v['row'];active=row.get('active_ingredients',[])
   if not isinstance(active,list):raise ValueError('Active ingredient array invalid')
   key=digest(active);g=ingredientlists.setdefault(key,{'values':active,'refs':[]});g['refs'].extend(v['refs'])
   packages=row.get('packaging',[])
   if not isinstance(packages,list):raise ValueError('Packaging array invalid')
   key=digest(packages);g=packagelists.setdefault(key,{'values':packages,'refs':[]});g['refs'].extend(v['refs'])
  components=[];packages=[]
  for group in ingredientlists.values():
   for original_order,obj in enumerate(group['values']):
    if not isinstance(obj,dict):raise ValueError('Ingredient not object')
    comp={'source_order':len(components),'original_source_order':original_order,'name_as_listed':obj.get('name'),'strength_text':obj.get('strength'),'role':'ACTIVE','mapping_status':'UNMAPPED','source_refs':[{**ref,'original_ingredient_order':original_order} for ref in group['refs']],'original_json':obj};components.append(comp)
  for group in packagelists.values():
   for original_order,obj in enumerate(group['values']):packages.append({'package_ndc':obj.get('package_ndc'),'source_order':len(packages),'source_refs':[{**ref,'original_package_order':original_order} for ref in group['refs']],'original_json':obj})
  maxingredients=max(maxingredients,len(components));typecounts[consistent('product_type') or 'CONFLICT_OR_UNKNOWN']+=1
  orig=objects[0] if len(objects)==1 else {'retained_source_variants':objects,'identity_assertion_conflict':True}
  status='UNKNOWN' if len(values)==1 else 'CONFLICT'
  db.execute('insert into products values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(native,display,consistent('generic_name'),None,consistent('dosage_form'),js(consistent('route')) if consistent('route') is not None else None,js(aliases),js(components),js(refs),js(orig),'US','FDA_PRODUCT_NDC',consistent('labeler_name'),consistent('product_type'),consistent('marketing_category'),status,'PENDING'))
  for comp in components:
   db.execute('insert into components values(?,?,?,?,?,?,?,?)',(native,comp['source_order'],comp['name_as_listed'],comp['strength_text'],'ACTIVE','UNMAPPED',js(comp['source_refs']),js(comp['original_json'])))
  for pkg in packages:db.execute('insert into packages values(?,?,?,?,?)',(native,pkg['package_ndc'],pkg['source_order'],js(pkg['source_refs']),js(pkg['original_json'])))
  stats['products']+=1;stats['components']+=len(components);stats['packages']+=len(packages);stats['original_records']+=len(originalrows)
  if len(components)==0:stats['products_without_active_ingredient_rows']+=1
  if len(components)>=3:stats['products_with_third_plus_ingredients']+=1
 db.commit()
 if db.execute('pragma integrity_check').fetchone()[0]!='ok' or db.execute('pragma foreign_key_check').fetchall():raise ValueError('Integrity/FK failure')
 # Consumers may stream SQLite products or a deterministic one-record-per-native-ID JSONL.
 with (output/'products.jsonl').open('w') as f:
  cur=db.execute('select * from products order by native_id');fields=[x[0] for x in cur.description]
  for row in cur:f.write(js(dict(zip(fields,row)))+'\n')
 db.close()
 result={'status':'RETAINED_SOURCE_NATIVE_CANDIDATE_CATALOGUE_RECONCILIATION_PENDING' if catalogue_issues else 'PASS_SOURCE_NATIVE_INTERMEDIATE_NOT_APP_RUNTIME','release_eligible':False,'external_completeness_gate':'FAIL_UPSTREAM_CATALOGUE_MISMATCH' if catalogue_issues else 'PASS_NAMED_BULK_CATALOGUE_COUNTS','catalogue_issues':catalogue_issues,'sources':manifest,'counts':dict(stats),'catalogue_declared_total':cat['total_records'],'retained_original_records':total,'max_ingredient_rows_per_product':maxingredients,'product_types':dict(typecounts),'output_database':str((output/'US_NDC_source_native.sqlite3').resolve()),'database_sha256':sha(output/'US_NDC_source_native.sqlite3'),'products_jsonl_sha256':sha(output/'products.jsonl'),'composition_status':'UNKNOWN_OR_CONFLICT','clinical_review':'PENDING','clinical_rules_active':0,'fda_approval_claimed':False,'canonical_mapping_claimed':False,'manufacturer_field_policy':'NULL: labeler_name is retained separately, not falsely asserted to be manufacturer','route_field_policy':'Exact source route array encoded as JSON string; no guessing/splitting','dedup_policy':'Same product_ndc only; identical whole source records and repeated identical ingredient/package-list projections merge with all original locators retained. No name-based cross-market identity merging; repeated positions within each source ingredient array remain.','limitations':['Full named NDC export only, not all US medicines or full labels/interaction evidence','NDC listing/assignment does not mean FDA approval, verification, current marketing or reimbursement eligibility','All original source records/fields/packaging retained; runtime integration/signature and clinical review not performed'],'builder_sha256':sha(__file__)}
 (output/'INTAKE_REPORT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(output/'INTERMEDIATE_SCHEMA.sql').write_text('\n'.join(r[0]+';' for r in sqlite3.connect(output/'US_NDC_source_native.sqlite3').execute("select sql from sqlite_master where sql is not null order by type,name"))+'\n')
 print(js(result),flush=True);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--retain-catalogue-mismatch-candidate',action='store_true');a=p.parse_args()
 try:run(a.root,a.output,a.retain_catalogue_mismatch_candidate)
 except Exception as e:
  if a.output.exists():(a.output/'BUILD_FAILURE.json').write_text(json.dumps({'error':repr(e),'traceback':traceback.format_exc()},indent=2)+'\n')
  raise
