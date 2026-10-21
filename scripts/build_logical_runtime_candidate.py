#!/usr/bin/env python3
"""Build an isolated real-source logical snapshot; never sign, activate, or approve it."""
import argparse, collections, datetime, gzip, hashlib, importlib.util, json, os, shutil, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'contracts/global-drug-data/1.0.0'
def js(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def stable(kind,*parts): return kind+':'+hashlib.sha256(js(parts).encode()).hexdigest()
def normalized(s): return ' '.join(s.casefold().split())
def insert(c,table,**r):
 keys=sorted(r);c.execute('INSERT INTO '+table+' ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[r[k] for k in keys])
def rows(c,table):
 for r in c.execute('SELECT * FROM '+table+' ORDER BY source_snapshot_id,'+('row_number' if table=='candidate_source_rows' and 'row_number' in [x[1] for x in c.execute('pragma table_info('+table+')')] else 'source_order')):yield dict(r)
def source_key(s):return s.split('-sha256-')[0]
def source_aliases(market,display_name,fields):
 # Language comes only from the publisher's declared field, never Unicode/glyph guessing.
 if market=='TW':
  aliases={(fields[k],language,kind) for k,language,kind in [('chinese_name','zh-Hant','OFFICIAL_CHINESE_PRODUCT_NAME'),('english_name','en','OFFICIAL_ENGLISH_PRODUCT_NAME')] if fields.get(k) and fields[k].strip()}
  if not any(a[0]==display_name for a in aliases):raise ValueError('TW display name lacks declared source-field evidence')
  return aliases
 return {(display_name,{'CA':'en','FR':'fr'}[market],'OFFICIAL_PRODUCT_NAME')}

def json_nodes(v):
 if isinstance(v,dict): return 1+sum(1+json_nodes(x) for x in v.values())
 if isinstance(v,list): return 1+sum(json_nodes(x) for x in v)
 return 1
def measure(c,tables):
 result={};whole_nodes=0
 for table in tables:
  q=c.execute('SELECT * FROM '+table);names=[x[0] for x in q.description]
  n=total=cellmax=rowmax=nodes=cellnodes=0
  for r in q:
   n+=1;rb=0
   for name,v in zip(names,r):
    if isinstance(v,(str,bytes)):
     size=len(v.encode() if isinstance(v,str) else v);total+=size;rb+=size;cellmax=max(cellmax,size)
     if isinstance(v,str) and (name.endswith('_json') or name in ['source_snapshots']):
      x=json_nodes(json.loads(v)); nodes+=x;cellnodes=max(cellnodes,x)
   rowmax=max(rowmax,rb)
  result[table]={'rows':n,'text_blob_bytes':total,'max_cell_bytes':cellmax,'max_row_text_blob_bytes':rowmax,'json_nodes':nodes,'max_cell_json_nodes':cellnodes}
  whole_nodes+=nodes
 return result,whole_nodes

def resolve_created_at(value=None):
 if value is None and 'SOURCE_DATE_EPOCH' in os.environ:
  value=datetime.datetime.fromtimestamp(int(os.environ['SOURCE_DATE_EPOCH']),datetime.timezone.utc).isoformat()
 if value is None:value=datetime.datetime.now(datetime.timezone.utc).isoformat()
 parsed=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
 if parsed.tzinfo is None or parsed.utcoffset() is None:raise ValueError('created_at requires explicit timezone')
 return value

def build(inputs,output,version='candidate-20261021-full-tw-ca-fr-v1',previous=None,created_at=None):
 if output.exists():raise ValueError('Refuse overwrite '+str(output))
 output.mkdir(parents=True)
 frozen=json.loads((CONTRACT/'SHA256SUMS.json').read_text())['sha256']
 for name,digest in frozen.items():
  if sha(CONTRACT/name)!=digest:raise ValueError('Frozen contract hash mismatch '+name)
 contract=json.loads((CONTRACT/'contract.json').read_text()); tables=contract['required_tables']
 source_cons={};sources={};input_hashes={}
 for f in sorted(inputs.rglob('*.sqlite3')):
  c=sqlite3.connect('file:'+str(f.resolve())+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
  if not c.execute("select 1 from sqlite_master where name='candidate_sources'").fetchone():continue
  input_hashes[str(f.resolve())]=sha(f)
  for sid,m in c.execute('select * from candidate_sources'):
   if sid in sources:raise ValueError('Duplicate snapshot '+sid)
   sources[sid]=json.loads(m);source_cons[sid]=c
 if len(sources)!=17:raise ValueError('Require all seventeen input source inventories')
 db=output/'snapshot.sqlite3';c=sqlite3.connect(db)
 c.executescript((CONTRACT/'schema.sql').read_text());c.execute('PRAGMA journal_mode=DELETE');c.execute('PRAGMA synchronous=FULL')
 old_registry={};old_ledger={};next_ingredient=0;release_sequence=1
 if previous:
  with sqlite3.connect('file:'+str(previous.resolve())+'?mode=ro',uri=True) as old:
   old.row_factory=sqlite3.Row
   old_registry={r['source_id']:dict(r) for r in old.execute('SELECT * FROM source_registry')}
   old_ledger={(r['entity_kind'],r['stable_id']):dict(r) for r in old.execute('SELECT * FROM id_ledger')}
   next_ingredient=max([r['compact_int_id'] or 0 for r in old_ledger.values() if r['entity_kind']=='INGREDIENT']+[0])
   release_sequence=old.execute('SELECT release_sequence FROM package_contract').fetchone()[0]+1
 created=resolve_created_at(created_at);markets=['CA','FR','TW'];coverage={m:{d:{'status':'NONE','scope':'No clinical evaluation is supported by this unreviewed candidate.','limitations':'UNKNOWN composition, unverified identity normalization, no active rules; absence of findings does not imply no risk.'} for d in contract['coverage_domains']} for m in ['GLOBAL']+markets}
 snaps=[]
 for sid,m in sorted(sources.items()):
  checksum=m.get('csv_sha256') or m.get('raw_sha256');ver=m['version_label'];snaps.append({'source_id':sid,'version_label':ver,'checksum':checksum})
  if sid in old_registry:
   insert(c,'source_registry',**old_registry[sid])
  else: insert(c,'source_registry',source_id=sid,source_name=m.get('dataset_name') or m.get('source_name') or m.get('name') or source_key(sid),source_url=m.get('source_url') or m['url'],version_label=ver,license_note=m.get('license','')+'; AI audit pending; isolated engineering candidate only.',source_type='OFFICIAL_REGULATOR',retrieved_at=m['retrieved_at'],checksum=checksum)
  insert(c,'source_rights',source_id=sid,commercial_use_allowed=0,mobile_redistribution_allowed=0,license_evidence_url=m.get('license_evidence_url') or m.get('license_url'),attribution_text=m.get('attribution') or 'Source: '+m.get('publisher','official publisher')+'; '+source_key(sid),review_status='PENDING',review_reference=None,reviewed_at=None)
 insert(c,'package_manifest',package_id=version,schema_version='safemed-mobile-safety-v2.1',package_major_version='2',product_line='safemed_pro',license_tier='professional',requires_entitlement=1,compatible_app_major_versions='[2]',data_version=version,rules_version='NONE-0',created_at=created,package_format='sqlite3+gzip',source_snapshots=js(snaps),quality_gate_result='CANDIDATE_ONLY',locked_regression_result='NOT_RUN')
 insert(c,'package_contract',package_id=version,contract_version='1.0.0',core_namespace='safemed-global-core-v1',core_version=version,release_sequence=release_sequence,snapshot_kind='COMPOSED_SNAPSHOT',market_codes_json=js(markets),required_capabilities_json=js(contract['required_capabilities']),coverage_json=js(coverage))
 bykey={source_key(s):s for s in sources};products={};stats=collections.Counter();excluded=collections.Counter();used=set();ingredient_ids={};raw_entity_occurrences=collections.Counter()
 def product(market,ns,native,name,sid,loc,**fields):
  if not native or not name or not name.strip():excluded[market+':missing identity or name']+=1;return None
  did=stable('drug',market,ns,str(native));used.add(sid)
  if did not in products:
   products[did]={'market':market,'ns':ns,'native':str(native),'name':name,'sid':sid,'fields':fields,'links':set(),'aliases':set(),'medical':set(),'component_count':0,'raw_orders':0}
  p=products[did];p['aliases'].update(source_aliases(market,name,fields));p['links'].add((sid,'IDENTITY',loc))
  # Preserve all distinct original medical assertions where product identities have several official rows.
  if fields.get('original_medical_text'):p['medical'].add(js(fields['original_medical_text']))
  stats[market+':product_source_rows']+=1
  return did
 # TW product rows can repeat a license for different factories. Group only exact native license identity, retain all locators and distinct medical assertions.
 sid=bykey['tfda-36']
 for r in rows(source_cons[sid],'candidate_source_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_assertions_json']);product('TW','TFDA_LICENSE',r['local_product_id'],x.get('中文品名') or x.get('英文品名'),sid,r['source_locator'],chinese_name=x.get('中文品名'),english_name=x.get('英文品名'),dosage_form=x.get('劑型'),original_medical_text={k:x.get(k,'') for k in ['適應症','用法用量','主成分略述']})
 sid=bykey['ca-dpd-products']
 for r in rows(source_cons[sid],'candidate_source_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_assertions_json']);product('CA','HEALTH_CANADA_DPD_DRUG_CODE',r['native_record_id'],x.get('brand_name'),sid,r['source_locator'],english_name=x.get('brand_name'),original_medical_text={k:x.get(k,'') for k in ['class_name','drug_identification_number','descriptor','number_of_ais']})
 sid=bykey['fr-bdpm-CIS_bdpm.txt']
 for r in rows(source_cons[sid],'candidate_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_columns_json']);product('FR','BDPM_CIS',x[0],x[1],sid,r['source_locator'],dosage_form=x[2],route=x[3],original_medical_text={'authorization_status':x[4],'marketing_status':x[6]})
 # Insert drug/identity before raw component foreign keys. Metadata source_ids is finalized after component links.
 for did,p in sorted(products.items()):
  f=p['fields'];sid=p['sid'];insert(c,'drugs',drug_id=did,display_name=p['name'],generic_name='',chinese_name=f.get('chinese_name'),english_name=f.get('english_name'),tfda_license_no=p['native'] if p['market']=='TW' else None,dosage_form=f.get('dosage_form'),route=f.get('route'),source=sid,source_version=sources[sid]['version_label'],evidence_quality='OFFICIAL',data_completeness='UNKNOWN',is_combination=-1,active_ingredient_count=0)
  insert(c,'drug_product_identity',drug_id=did,jurisdiction=p['market'],identifier_namespace=p['ns'],local_product_id=p['native'],market_status='UNKNOWN',prescription_status='UNKNOWN')
  insert(c,'drug_compact_index',drug_id=did,ingredient_int_ids_json='[]',class_int_ids_json='[]')
  if old_ledger.get(('DRUG',did),{}).get('lifecycle')=='RETIRED':raise ValueError('Refuse resurrect retired drug '+did)
  insert(c,'id_ledger',entity_kind='DRUG',stable_id=did,compact_int_id=None,lifecycle='ACTIVE')
 def component(market,ns,native,sid,loc,order,name,code=None,strength=None,unit=None,basis=None,role='UNKNOWN',extra=None):
  nonlocal next_ingredient
  did=stable('drug',market,ns,str(native));stats[market+':ingredient_source_rows']+=1
  if did not in products:excluded[market+':orphan ingredient rows retained in raw archive']+=1;return
  if not name or not name.strip():excluded[market+':empty ingredient name retained in raw archive']+=1;return
  p=products[did];seq=p['raw_orders'];p['raw_orders']+=1;p['component_count']+=1;p['links'].add((sid,'COMPOSITION',loc));used.add(sid)
  # Canonical evidence entities remain source scoped. Code+exact original spelling only; without native ingredient code, each source row is isolated.
  raw_key=(source_key(sid),str(native),name,strength,unit,basis,role)
  occurrence=raw_entity_occurrences[raw_key];raw_entity_occurrences[raw_key]+=1
  ikey=(source_key(sid),str(code),name) if code else (*raw_key,occurrence)
  iid=stable('ingredient',*ikey)
  if iid not in ingredient_ids:
   prior=old_ledger.get(('INGREDIENT',iid))
   if prior and prior['lifecycle']=='RETIRED':raise ValueError('Refuse resurrect retired ingredient ID '+iid)
   if prior:number=prior['compact_int_id']
   else:
    next_ingredient+=1;number=next_ingredient
   ingredient_ids[iid]=number
   insert(c,'ingredients',ingredient_id=iid,ingredient_int_id=number,canonical_name=name,normalized_name=normalized(name),source=sid,source_version=sources[sid]['version_label'],evidence_quality='OFFICIAL')
   insert(c,'id_ledger',entity_kind='INGREDIENT',stable_id=iid,compact_int_id=number,lifecycle='ACTIVE')
  c.execute('INSERT OR IGNORE INTO ingredient_sources VALUES (?,?,?)',(iid,sid,loc))
  insert(c,'product_ingredient_rows',component_id=stable('component',source_key(sid),loc),drug_id=did,source_order=seq,ingredient_id=None,name_as_listed=name,role=role,strength_text=strength,strength_value=None,strength_unit=unit,basis_text=basis,mapping_status='UNMAPPED',source_id=sid,source_locator=loc)
  stats[market+':retained_ingredient_rows']+=1
 sid=bykey['tfda-43']
 for r in rows(source_cons[sid],'candidate_source_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_assertions_json']);component('TW','TFDA_LICENSE',r['local_product_id'],sid,r['source_locator'],r['row_number'],x.get('成分名稱'),code=x.get('成分代碼'),strength=js({k:x.get(k,'') for k in ['含量描述','含量','含量單位']}),unit=x.get('含量單位'),basis=x.get('處方標示'))
 sid=bykey['ca-dpd-active-ingredients']
 for r in rows(source_cons[sid],'candidate_source_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_assertions_json']);component('CA','HEALTH_CANADA_DPD_DRUG_CODE',r['native_record_id'],sid,r['source_locator'],r['source_order'],x.get('ingredient_name'),strength=x.get('strength'),unit=x.get('strength_unit'),basis=js({k:x.get(k,'') for k in ['dosage_unit','dosage_value']}),role='ACTIVE')
 sid=bykey['fr-bdpm-CIS_COMPO_bdpm.txt']
 for r in rows(source_cons[sid],'candidate_rows'):
  if r['source_snapshot_id']!=sid:continue
  x=json.loads(r['raw_columns_json']);component('FR','BDPM_CIS',x[0],sid,r['source_locator'],r['source_order'],x[3],code=x[2],strength=x[4],basis=js({'reference_dosage':x[5],'element':x[1],'source_role_code':x[6],'source_link_number':x[7] if len(x)>7 else ''}))
 # Product locators retain the original source row number; source_order is deterministic sequence per product.
 for did,p in sorted(products.items()):
  ids=sorted({s for s,_,_ in p['links']});metadata={'safemed_product_identity':{'contract_version':'safemed-product-identity-v1','jurisdiction':p['market'],'identifier_namespace':p['ns'],'local_product_id':p['native'],'source_ids':ids},'original_medical_assertions':[json.loads(x) for x in sorted(p['medical'])],'automated_candidate':True,'identity_source_rows':len([1 for _,purpose,_ in p['links'] if purpose=='IDENTITY'])}
  c.execute('UPDATE drugs SET metadata_json=? WHERE drug_id=?',(js(metadata),did))
  insert(c,'product_composition',drug_id=did,composition_status='UNKNOWN',expected_active_row_count=None,review_status='PENDING',reviewer_kind='AUTOMATED',review_reference='AI_ENGINEERING_ONLY:'+version,reviewed_at=created,completeness_note='All acquired matching raw rows retained; source coverage and roles/completeness are not clinically approved. No canonical product mappings. Zero verified ingredients does not mean none present.')
  for sid,purpose,loc in sorted(p['links']):insert(c,'drug_source_links',drug_id=did,source_id=sid,purpose=purpose,source_locator=loc)
  for alias,language,kind in sorted(p['aliases']):insert(c,'drug_aliases',alias_id=stable('alias',did,alias,language),drug_id=did,alias=alias,normalized_alias=normalized(alias),alias_type=kind,language=language,source=p['sid'],source_version=sources[p['sid']]['version_label'],confidence=1)
 for key,r in sorted(old_ledger.items()):
  if not c.execute('SELECT 1 FROM id_ledger WHERE entity_kind=? AND stable_id=?',key).fetchone():
   r['lifecycle']='RETIRED';insert(c,'id_ledger',**r)
 c.commit()
 integrity=c.execute('PRAGMA integrity_check').fetchall();fk=c.execute('PRAGMA foreign_key_check').fetchall()
 measurements,nodes=measure(c,tables);totalrows=sum(v['rows'] for v in measurements.values());totalbytes=sum(v['text_blob_bytes'] for v in measurements.values())
 plans={q:[list(x) for x in c.execute('EXPLAIN QUERY PLAN '+q,('example',))] for q in ['SELECT * FROM product_ingredient_rows WHERE drug_id=?','SELECT * FROM drug_aliases WHERE normalized_alias=?']}
 index_sizes=[dict(zip(['name','bytes'],r)) for r in c.execute('SELECT name,sum(pgsize) FROM dbstat GROUP BY name ORDER BY name')]
 c.close()
 with db.open('rb') as src,(output/'snapshot.sqlite3.gz').open('wb') as dest:
  with gzip.GzipFile(fileobj=dest,mode='wb',mtime=0,filename='',compresslevel=6) as z:shutil.copyfileobj(src,z,1024*1024)
 spec=importlib.util.spec_from_file_location('frozen_gate',CONTRACT/'validate_contract.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 try:gate.validate(db);gate_result={'status':'UNEXPECTED_PASS'}
 except Exception as e:gate_result={'status':'EXPECTED_REJECTION','error':str(e),'call':'frozen validate(snapshot.sqlite3), no test_only or overrides'}
 caps={'sqlite_bytes':db.stat().st_size<=33554432,'whole_rows':totalrows<=250000,'whole_text_blob_bytes':totalbytes<=134217728,'whole_json_nodes':nodes<=1000000,'per_table_full_query_rows':all(v['rows']<=30000 for v in measurements.values()),'per_table_full_query_bytes':all(v['text_blob_bytes']<=16777216 for v in measurements.values()),'per_table_full_query_json_nodes':all(v['json_nodes']<=200000 for v in measurements.values()),'max_cell':all(v['max_cell_bytes']<=65536 for v in measurements.values()),'max_row':all(v['max_row_text_blob_bytes']<=262144 for v in measurements.values()),'max_cell_json_nodes':all(v['max_cell_json_nodes']<=4096 for v in measurements.values())}
 report={'version':version,'status':'ISOLATED_UNREVIEWED_LOGICAL_CANDIDATE','runtime_compatible':False,'signed':False,'published':False,'activated':False,'clinical_rules':0,'verified_complete_products':0,'quality_gate':'CANDIDATE_ONLY','integrity_check':integrity,'foreign_key_violations':fk,'frozen_gate':gate_result,'app_cap_checks':caps,'additional_rejection_reasons':['source_rights=PENDING; commercial/mobile permission not asserted','Initial ledger proposal not human-confirmed','Not signed; no trusted App key','No App native acceptance performed'],'no_test_sources':all(not any(x in source_key(s).lower() for x in ['test','seed','fixture']) for s in sources)}
 coverage_report={'markets':{m:{'products':sum(p['market']==m for p in products.values()),'composition':'UNKNOWN','coverage':'NONE','active_rules':0} for m in markets},'source_rows':dict(stats),'excluded_rows':dict(excluded),'included_snapshot_ids':sorted(used),'excluded_snapshots':{s:('JP price-list field definitions require dedicated transformation; no necessary source content truncated' if s.startswith('jp-') else 'KR package-code mapping lacks explicit ingredient name field; retained source archive' if s.startswith('kr-') else 'EMA regional procedure identity is not a two-letter market product authorization; no invented jurisdiction' if s.startswith('ema-') else 'Auxiliary label links/classification/package reference source retained in full source archive, not ingredient/composition inference') for s in sorted(set(sources)-used)},'scope':'All eligible identity rows from acquired TW TFDA36, CA DPD products and FR CIS, all matched acquired ingredient rows. Archived/nonhuman/source-category records remain unfiltered; market/prescription status UNKNOWN. Not all worldwide medicines.','canonical_policy':'Source-native code + exact original name scoped per feed; code-free CA ingredient records are separate source-row entities. Never cross-market or chemical-name equivalence; all product mappings UNMAPPED.','alias_language_policy':'TW Chinese-name field => zh-Hant; English-name field => en. Identical text in both fields is retained as two source-declared language rows, not guessed or resolved. CA English endpoint brand names => en; FR original names => fr. Alias IDs include language; clinical stable IDs are unchanged.','dual_language_exact_text_aliases':sum(len({a for a,lang,kind in p['aliases'] if lang=='en'} & {a for a,lang,kind in p['aliases'] if lang=='zh-Hant'}) for p in products.values()),'source_native_ingredient_codes':'Preserved in complete official source archives and auditable source locators; not represented as plain native-code fields for UNMAPPED runtime rows. Do not claim full native-code projection.','source_order_policy':'Rows in immutable source order; per-product contiguous source_order. Original row retained verbatim in source_locator.','original_archive_required':'All original downloads and full positional/raw JSON evidence remain outside runtime; no original medical text is summarized to fit cap.'}
 measured={'sqlite_bytes':db.stat().st_size,'sqlite_sha256':sha(db),'gzip_bytes':(output/'snapshot.sqlite3.gz').stat().st_size,'gzip_sha256':sha(output/'snapshot.sqlite3.gz'),'tables':measurements,'whole_rows':totalrows,'whole_text_blob_bytes':totalbytes,'whole_json_nodes':nodes,'index_page_sizes':index_sizes,'explain_query_plans':plans,'input_sqlite_sha256':input_hashes,'frozen_contract_sha256':frozen,'builder_sha256':sha(Path(__file__)),'created_at':created,'rebuild_argv':['python3','scripts/build_logical_runtime_candidate.py','--inputs',str(inputs.resolve()),'--output','<new isolated directory>','--version',version,'--created-at',created]+(['--previous',str(previous.resolve())] if previous else []),'rebuild_command':'Use rebuild_argv with preserved input snapshots, previous ledger, and explicit --created-at; outputs refuse overwrite.'}
 ledger={'status':'PROPOSAL_ONLY_NOT_HUMAN_CONFIRMED','namespace':'safemed-global-core-v1','release_sequence':release_sequence,'drug_ids':len(products),'ingredient_ids':len(ingredient_ids),'stable_id_algorithm':'SHA256 compact sorted UTF8 JSON tuple; source feed names exclude snapshot checksum to preserve native identity across source snapshots','ingredients':'Code+exact-name when source provides code, otherwise native product ID+exact raw name/strength/unit/basis/role+duplicate occurrence; no chemical equivalence claimed. Future releases must retain IDs/tombstones; no regeneration/reset authorized.','full_proposal':'id_ledger table inside snapshot.sqlite3','previous_snapshot':str(previous) if previous else None,'human_confirmation':False,'clinical_review':False}
 for name,value in [('BUILD_MEASUREMENTS.json',measured),('VALIDATION_REPORT.json',report),('COVERAGE_AND_EXCLUSIONS.json',coverage_report),('LEDGER_REVIEW.json',ledger),('candidate-envelope.json',{'status':'UNSIGNED_NOT_PUBLISHED_NOT_ACCEPTED','package_format':'sqlite3+gzip','logical_sqlite_bytes':measured['sqlite_bytes'],'logical_sqlite_sha256':measured['sqlite_sha256'],'gzip_bytes':measured['gzip_bytes'],'gzip_sha256':measured['gzip_sha256'],'not_a_runtime_download_manifest':True})]: (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 (output/'SHA256SUMS.json').write_text(json.dumps({p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},indent=2)+'\n')
 print(json.dumps({'output':str(output),'products':len(products),'ingredients':len(ingredient_ids),'rows':totalrows,'sqlite_bytes':measured['sqlite_bytes'],'gzip_bytes':measured['gzip_bytes'],'runtime_compatible':False,'gate':gate_result},ensure_ascii=False,indent=2),flush=True)
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--previous',type=Path);p.add_argument('--created-at',help='Deterministic timezone-aware ISO timestamp; otherwise SOURCE_DATE_EPOCH, otherwise current UTC');p.add_argument('--version',default='candidate-20261021-full-tw-ca-fr-v1');a=p.parse_args();build(a.inputs,a.output,a.version,a.previous,a.created_at)
