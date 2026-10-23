"""Add independently sourced countries to a fresh TW/CA/FR base; never activate or sign."""
import argparse,datetime,gzip,hashlib,json,shutil,sqlite3,time,traceback
from pathlib import Path

def js(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def stable(kind,*parts):return kind+':'+hashlib.sha256(js(parts).encode()).hexdigest()
def ro(p):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro&immutable=1',uri=True);c.row_factory=sqlite3.Row;return c
def insert(c,t,r):
 keys=list(r);c.execute('INSERT INTO '+t+' ('+','.join(keys)+') VALUES ('+','.join('?' for k in keys)+')',[r[k] for k in keys])
def refs(row):
 rs=row.get('source_refs') or ([row['source_ref']] if row.get('source_ref') else [])
 return sorted({(x['source_id'],x.get('locator') or x.get('source_locator')) for x in rs})
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def source_metadata(c):
 name='sources' if c.execute("SELECT 1 FROM sqlite_master WHERE name='sources'").fetchone() else 'source_registry'
 for r in c.execute('SELECT * FROM '+name):
  d=json.loads(r['metadata_json']);sid=r['source_id'];digest=d.get('raw_sha256') or d.get('original_json_sha256') or d.get('sha256') or d.get('source_sha256')
  if not digest:
   digest=r['raw_sha256'] if 'raw_sha256' in r.keys() else r['source_sha256']
  yield sid,d,digest
def products(entry):
 c=ro(entry['path']);sup=ro(entry['supplement']['path']) if entry.get('supplement') else None
 table='products_export' if c.execute("SELECT 1 FROM sqlite_master WHERE name='products_export'").fetchone() else 'products'
 for r in c.execute('SELECT * FROM '+table+' ORDER BY native_id'):
  row=dict(r)
  if sup:
   s=sup.execute('SELECT * FROM products_export WHERE native_id=?',(row['native_id'],)).fetchone()
   if s:
    s=dict(s);row['aliases_json']=js(sorted(set(json.loads(row['aliases_json'])+json.loads(s['aliases_json']))));row['components_json']=js(json.loads(row['components_json'])+json.loads(s['components_json']));row['source_refs_json']=js(json.loads(row['source_refs_json'])+json.loads(s['source_refs_json']));row['original_json']=js({'base':json.loads(row['original_json']),'supplement':json.loads(s['original_json']),'supplement_merge':'Exact official item/general ingredient codes; historical source assertions, not current clinical approval'})
  yield row
 c.close()
 if sup:sup.close()
def main(a):
 start=time.monotonic();out=a.output.resolve();assert not out.exists();out.mkdir(parents=True);events=[]
 def event(phase,**kw):
  e={'phase':phase,'seconds':round(time.monotonic()-start,3),**kw};events.append(e);print(js(e),flush=True);write(out/'PROGRESS.json',{'status':'RUNNING','events':events})
 try:
  config=json.loads(a.inputs.read_text());base_sha=sha(a.base)
  ref_bytes=a.reference.read_bytes();norm={x['input']:bytes.fromhex(x['normalized_utf8_hex']).decode() for x in json.loads(ref_bytes)}
  for e in config['countries']:
   assert sha(e['path'])==e['sha256'],e['market']
   if e.get('supplement'):assert sha(e['supplement']['path'])==e['supplement']['sha256']
  db=out/'snapshot.sqlite3';shutil.copyfile(a.base,db);assert db.stat().st_ino!=a.base.stat().st_ino;c=sqlite3.connect(db);c.row_factory=sqlite3.Row
  c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA cache_size=-32768');c.execute('PRAGMA temp_store=FILE');c.execute('PRAGMA synchronous=FULL');assert c.execute('PRAGMA user_version').fetchone()[0]==20100
  before={x[0]:c.execute('SELECT count(*) FROM '+x[0]).fetchone()[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")};sequence=c.execute('SELECT release_sequence FROM package_contract').fetchone()[0]
  for alias in c.execute('SELECT alias_id,alias FROM drug_aliases').fetchall():
   value=norm[alias['alias']]
   if not value:
    assert alias['alias']=='.','Unreviewed empty normalized alias'
    c.execute('DELETE FROM drug_aliases WHERE alias_id=?',(alias['alias_id'],))
   else:c.execute('UPDATE drug_aliases SET normalized_alias=? WHERE alias_id=?',(value,alias['alias_id']))
  for product in c.execute('SELECT drug_id,metadata_json FROM drugs').fetchall():
   metadata=json.loads(product['metadata_json'])
   for field in ['original_medical_assertions','automated_candidate','identity_source_rows']:metadata.pop(field,None)
   c.execute('UPDATE drugs SET metadata_json=? WHERE drug_id=?',(js(metadata),product['drug_id']))
  c.commit()
  event('base_and_inputs_verified',base_bytes=db.stat().st_size)
  archive=out/'source-archive';archive.mkdir();source_observations={};old_sources={x['source_id']:dict(x) for x in c.execute('SELECT * FROM source_registry')};c.execute('BEGIN');c.execute('PRAGMA defer_foreign_keys=ON')
  for entry in config['countries']:
   paths=[entry]+([entry['supplement']] if entry.get('supplement') else [])
   for inp in paths:
    ic=ro(inp['path'])
    for sid,m,digest in source_metadata(ic):
     assert len(digest)==64;source_observations[sid]=dict(m)
     override=config.get('source_metadata_overrides',{}).get(sid)
     if override:
      assert sha(override['evidence_path'])==override['evidence_sha256'] and override['response_sha256']==digest
      proof=json.loads(Path(override['evidence_path']).read_text());assert any(x.get('sha256')==digest and x.get('retrieved_at')==override['retrieved_at'] and x.get('http_status')==200 for x in proof)
      m=dict(m);m['retrieved_at']=override['retrieved_at'];source_observations[sid]['verified_retrieval_timestamp_override']=override
     old=c.execute('SELECT * FROM source_registry WHERE source_id=?',(sid,)).fetchone()
     if old:assert old['checksum']==digest, 'Immutable source snapshot collision '+sid
     else:
      url=m.get('source_url') or m.get('url') or m.get('directory_url');assert url and url.startswith('https://')
      ver=m.get('version_label') or ('content-sha256:'+digest)
      retrieved=m.get('retrieved_at');assert retrieved and datetime.datetime.fromisoformat(retrieved.replace('Z','+00:00')).tzinfo is not None,'Missing evidenced timezone-aware retrieval time: '+sid
      insert(c,'source_registry',{'source_id':sid,'source_name':m.get('publisher') or m.get('source_name') or sid.split('-sha256-')[0],'source_url':url,'version_label':ver,'license_note':m.get('license') or 'Official source; applicable copyright/attribution and third-party exclusions retained. Source review pending.','source_type':'OFFICIAL_REGULATOR','retrieved_at':retrieved,'checksum':digest})
      insert(c,'source_rights',{'source_id':sid,'commercial_use_allowed':0,'mobile_redistribution_allowed':0,'license_evidence_url':m.get('license_url') or m.get('source_page') or url,'attribution_text':'Source: '+(m.get('publisher') or sid)+'; '+url+'; source text retained, SQLite projection and deduplication identified in accompanying attribution.','review_status':'PENDING','review_reference':None,'reviewed_at':None})
    ic.close()
  source_versions={x['source_id']:x['version_label'] for x in c.execute('SELECT source_id,version_label FROM source_registry')};counts={};empty=[];fallback=[];row_map=archive/'NEW_PRODUCT_PROJECTION.jsonl.gz'
  with row_map.open('wb') as dest,gzip.GzipFile(filename='',fileobj=dest,mode='wb',mtime=0,compresslevel=6) as gz:
   for entry in config['countries']:
    market,ns,lang=entry['market'],entry['namespace'],entry['language'];n=aliases=components=links=conflicts=0
    for row in products(entry):
     native=row['native_id'];did=stable('drug',market,ns,native);assert not c.execute('SELECT 1 FROM drugs WHERE drug_id=?',(did,)).fetchone()
     names=json.loads(row['aliases_json']);display=row['display_name']
     if not display:
      display=('NDC ' if market=='US' else market+' ')+native;fallback.append({'drug_id':did,'market':market,'native_id':native,'display':display,'reason':'Conflicting/missing original display; explicit identifier fallback, not an invented medicine name'})
     names=sorted(set(names+[display]));rs=refs({'source_refs':json.loads(row['source_refs_json'])});assert rs and all(loc and sid in source_versions for sid,loc in rs)
     comp=json.loads(row['components_json']);all_sources={sid for sid,loc in rs}
     for x in comp:
      rr=refs(x);assert rr;all_sources.update(sid for sid,loc in rr);assert all(sid in source_versions for sid,loc in rr)
     primary_sid=next((sid for sid,loc in rs if (sid.startswith('au-pbs-items-sha256-') if market=='AU' else True)),rs[0][0])
     mirror_sources=all_sources-{sid for sid in all_sources if market=='AU' and sid.startswith('au-pbs-organisations-sha256-')}
     metadata={'safemed_product_identity':{'contract_version':'safemed-product-identity-v1','jurisdiction':market,'identifier_namespace':ns,'local_product_id':native,'source_ids':sorted(mirror_sources)}}
     original=json.loads(row['original_json']);status=row.get('composition_status') or original.get('composition_status') or 'UNKNOWN';assert status in {'UNKNOWN','CONFLICT','PARTIAL'}
     if status=='CONFLICT':conflicts+=1
     insert(c,'drugs',{'drug_id':did,'display_name':display,'generic_name':row['generic_name'] or '', 'english_name':display if market in {'US','AU'} and row['display_name'] else None,'dosage_form':row['dosage_form'],'route':row['route'],'source':primary_sid,'source_version':source_versions[primary_sid],'evidence_quality':'OFFICIAL','data_completeness':'PARTIAL' if status=='PARTIAL' else 'UNKNOWN','is_combination':-1,'active_ingredient_count':0,'metadata_json':js(metadata)})
     insert(c,'drug_product_identity',{'drug_id':did,'jurisdiction':market,'identifier_namespace':ns,'local_product_id':native,'market_status':'UNKNOWN','prescription_status':'UNKNOWN'})
     insert(c,'drug_compact_index',{'drug_id':did,'ingredient_int_ids_json':'[]','class_int_ids_json':'[]'})
     prior=c.execute("SELECT lifecycle FROM id_ledger WHERE entity_kind='DRUG' AND stable_id=?",(did,)).fetchone()
     if prior:assert prior[0]=='ACTIVE','Retired ID reappeared; explicit review required'
     else:insert(c,'id_ledger',{'entity_kind':'DRUG','stable_id':did,'compact_int_id':None,'lifecycle':'ACTIVE'})
     insert(c,'product_composition',{'drug_id':did,'composition_status':status,'expected_active_row_count':None,'review_status':'PENDING','reviewer_kind':'AUTOMATED','review_reference':'AI_ENGINEERING_ONLY:'+a.version,'reviewed_at':a.created_at,'completeness_note':'Original source assertions retained; composition, canonical mappings and current clinical coverage are not approved.'})
     def source_purpose(sid):
      if market=='KR' and not sid.startswith('kr-HIRA_standard_codes.csv-sha256-'):return 'COMPOSITION'
      if market=='AU' and sid.startswith('au-pbs-organisations-sha256-'):return 'LABEL'
      return 'IDENTITY'
     pairs={(sid,source_purpose(sid),loc) for sid,loc in rs};component_map=[]
     for order,x in enumerate(comp):
      name=x['name_as_listed'];assert name and name.strip();rr=refs(x);sid,loc=rr[0];role=x.get('role') or 'UNKNOWN';assert role in {'ACTIVE','EXCIPIENT','UNKNOWN'}
      strength,unit=x.get('strength_text'),x.get('strength_unit');strength_policy='Export scalar values retained'
      if market=='KR' and x.get('assertion_kind')=='OFFICIAL_DICTIONARY_ORIGINAL_ROW':
       fields=x['original_assertion']['raw_original_fields'];strength=fields['함량'];unit=fields['단위'];assert isinstance(strength,str) and isinstance(unit,str)
       strength_policy='Official original CSV 함량 -> strength_text and 단위 -> strength_unit, exact strings including blank units; no JSON wrapper or dose inference'
      cid=stable('component','source-native-projection-v1',did,order,name,strength,unit,rr)
      insert(c,'product_ingredient_rows',{'component_id':cid,'drug_id':did,'source_order':order,'ingredient_id':None,'name_as_listed':name,'role':role,'strength_text':strength,'strength_unit':unit,'basis_text':x.get('basis_text'),'mapping_status':'UNMAPPED','source_id':sid,'source_locator':loc})
      pairs.update((sid,'COMPOSITION',loc) for sid,loc in rr);component_map.append({'source_input_order':order,'component_id':cid,'all_source_refs':rr,'runtime_strength_text':strength,'runtime_strength_unit':unit,'strength_projection':strength_policy});components+=1
     for sid,purpose,loc in sorted(pairs):insert(c,'drug_source_links',{'drug_id':did,'source_id':sid,'purpose':purpose,'source_locator':loc});links+=1
     alias_map=[]
     for name in names:
      assert name in norm,'Missing actual Swift normalization: '+repr(name);key=norm[name];aid=stable('alias',did,name,lang)
      if not key:
       empty.append({'drug_id':did,'alias_id':aid,'market':market,'native_id':native,'alias':name,'reason':'Exact actual Swift key is empty; raw name archived, source product and other names retained'});continue
      alias_sid=primary_sid
      if market=='AU' and not any(name==x.get(f) for x in original.get('items',[]) for f in ['brand_name','drug_name','li_drug_name','schedule_form','pbs_code']):
       if any(name==x.get(f) for x in original.get('amt_concepts',[]) for f in ['preferred_term','pbs_preferred_term']):alias_sid=next(s for s in all_sources if s.startswith('au-pbs-amt-items-sha256-'))
      insert(c,'drug_aliases',{'alias_id':aid,'drug_id':did,'alias':name,'normalized_alias':key,'alias_type':'SOURCE_IDENTIFIER_FALLBACK' if not row['display_name'] and name==display else 'ORIGINAL_SOURCE_VALUE','language':lang,'source':alias_sid,'source_version':source_versions[alias_sid],'confidence':1.0});aliases+=1;alias_map.append({'alias_id':aid,'alias':name,'normalized_alias':key})
     assert any(x['alias']==display for x in alias_map),'Display alias must remain usable'
     gz.write((js({'drug_id':did,'market':market,'namespace':ns,'original_export':row,'runtime_display':display,'alias_projection':alias_map,'component_projection':component_map,'typed_original_json_retained':True})+'\n').encode());n+=1
     if n%25000==0:event('country_rows_in_progress',market=market,products=n)
    counts[market]={'products':n,'aliases':aliases,'component_assertions':components,'source_links':links,'composition_conflict_products':conflicts};event('country_added',market=market,**counts[market])
  write(archive/'EMPTY_ALIAS_EXCEPTIONS.json',{'policy':'Explicit archive of empty exact Swift keys only; full input names retained in projection archive; no product removed','rows':empty});write(archive/'DISPLAY_IDENTIFIER_FALLBACKS.json',fallback);write(archive/'SOURCE_METADATA_OBSERVATIONS.json',source_observations)
  snaps=[{'source_id':x['source_id'],'version_label':x['version_label'],'checksum':x['checksum']} for x in c.execute('SELECT * FROM source_registry ORDER BY source_id')];contract=dict(c.execute('SELECT * FROM package_contract').fetchone());coverage=json.loads(contract['coverage_json']);markets=sorted(set(json.loads(contract['market_codes_json']))|set(counts))
  template=coverage['GLOBAL']
  for market in markets:
   if market not in coverage:coverage[market]=template
  c.execute('UPDATE package_manifest SET package_id=?,data_version=?,created_at=?,source_snapshots=?',(a.version,a.version,a.created_at,js(snaps)))
  c.execute('UPDATE package_contract SET package_id=?,core_version=?,release_sequence=?,market_codes_json=?,coverage_json=?',(a.version,a.version,sequence,js(markets),js(coverage)));c.execute("UPDATE id_ledger SET lifecycle='RETIRED' WHERE entity_kind='DRUG' AND stable_id NOT IN (SELECT drug_id FROM drugs)");c.commit();event('new_rows_committed')
  integrity=[x[0] for x in c.execute('PRAGMA integrity_check')];fk=[list(x) for x in c.execute('PRAGMA foreign_key_check')];assert integrity==['ok'] and not fk
  totals={x[0]:c.execute('SELECT count(*) FROM '+x[0]).fetchone()[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")};assert totals['drugs']==before['drugs']+sum(x['products'] for x in counts.values());assert totals['ingredients']==before['ingredients'];assert c.execute('SELECT count(*) FROM rules').fetchone()[0]==0
  market_counts=[dict(x) for x in c.execute('SELECT jurisdiction,count(*) AS products FROM drug_product_identity GROUP BY jurisdiction ORDER BY jurisdiction')];c.close();event('integrity_fk_counts_passed',sqlite_bytes=db.stat().st_size,products=totals['drugs'])
  payload=out/'snapshot.sqlite3.gz'
  with db.open('rb') as src,payload.open('wb') as dest,gzip.GzipFile(fileobj=dest,filename='',mode='wb',mtime=0,compresslevel=6) as g:shutil.copyfileobj(src,g,1048576)
  assert sha(a.base)==base_sha
  result={'status':'UNSIGNED_SEVEN_MARKET_ENGINEERING_CANDIDATE','version':a.version,'release_sequence':sequence,'sqlite_bytes':db.stat().st_size,'sqlite_sha256':sha(db),'gzip_bytes':payload.stat().st_size,'gzip_sha256':sha(payload),'market_products':market_counts,'new_country_rows':counts,'tables':totals,'whole_rows':sum(totals.values()),'integrity_check':integrity,'foreign_key_violations':fk,'base_original_unchanged':True,'old_ids_or_compact_ids_reassigned':False,'new_canonical_ingredient_mappings':0,'clinical_rules':0,'verified_complete_products':0,'runtime_accepted':False,'signed':False,'published':False,'activated':False,'App_modified':False,'empty_alias_exceptions':len(empty),'identifier_display_fallbacks':len(fallback),'original_input_configuration':config,'reference_path':str(a.reference.resolve()),'reference_sha256':hashlib.sha256(ref_bytes).hexdigest(),'producer_host_only_not_iOS_measurements':True,'host_build_seconds':time.monotonic()-start}
  write(out/'BUILD_MEASUREMENTS.json',result);write(out/'candidate-envelope.json',{k:result[k] for k in ['status','version','release_sequence','sqlite_bytes','sqlite_sha256','gzip_bytes','gzip_sha256','runtime_accepted','signed','published','activated']});shutil.copyfile(__file__,out/'BUILD_SCRIPT.py');shutil.copyfile(a.inputs,out/'INPUTS.json');write(out/'REBUILD.json',{'builder_sha256':sha(__file__),'created_at':a.created_at,'argv':__import__('sys').argv,'refuses_overwrite':True});write(out/'SHA256SUMS.json',{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='PROGRESS.json'});event('build_complete',sqlite_bytes=result['sqlite_bytes'],gzip_bytes=result['gzip_bytes']);write(out/'PROGRESS.json',{'status':'BUILD_COMPLETE_AWAITING_INDEPENDENT_VALIDATION','events':events})
 except BaseException as e:
  write(out/'BUILD_FAILURE.json',{'status':'FAIL_RETAINED','error':repr(e),'traceback':traceback.format_exc(),'events':events});raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',required=True);p.add_argument('--created-at',required=True);main(p.parse_args())
