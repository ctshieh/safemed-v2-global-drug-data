#!/usr/bin/env python3
"""Reproducible source-native MHLW price-list intermediate. Not a medical runtime package."""
import argparse,collections,hashlib,json,re,shutil,sqlite3,sys,traceback
from pathlib import Path
NAMESPACE='JP_MHLW_NHI_PRICE_LIST_CODE'
# Each fresh source is revalidated against its downloaded XLSX hash, original headers and row counts.
SCHEMA='''
PRAGMA foreign_keys=ON;
PRAGMA user_version=10000;
CREATE TABLE sources(source_id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL, original_file TEXT NOT NULL, original_sha256 TEXT NOT NULL, original_bytes INTEGER NOT NULL);
CREATE TABLE source_rows(source_id TEXT NOT NULL REFERENCES sources(source_id), source_order INTEGER NOT NULL, source_locator TEXT NOT NULL, raw_json TEXT NOT NULL, raw_json_sha256 TEXT NOT NULL, native_id_as_listed TEXT, row_classification TEXT NOT NULL, PRIMARY KEY(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE products(product_key TEXT PRIMARY KEY,native_id TEXT NOT NULL UNIQUE, jurisdiction TEXT NOT NULL,identifier_namespace TEXT NOT NULL,identity_kind TEXT NOT NULL,display_name TEXT NOT NULL,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,specification_as_listed TEXT,category_as_listed TEXT,composition_status TEXT NOT NULL,review_status TEXT NOT NULL,reviewer_kind TEXT NOT NULL,conflicts_json TEXT NOT NULL);
CREATE TABLE product_rows(product_key TEXT NOT NULL REFERENCES products(product_key),source_id TEXT NOT NULL,source_order INTEGER NOT NULL,source_locator TEXT NOT NULL,projection_json TEXT NOT NULL,projection_sha256 TEXT NOT NULL,PRIMARY KEY(product_key,source_id,source_order),FOREIGN KEY(source_id,source_order) REFERENCES source_rows(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE product_values(product_key TEXT NOT NULL REFERENCES products(product_key),field_name TEXT NOT NULL,value_text TEXT NOT NULL,value_key TEXT NOT NULL,PRIMARY KEY(product_key,field_name,value_key)) WITHOUT ROWID;
CREATE TABLE value_sources(product_key TEXT NOT NULL,field_name TEXT NOT NULL,value_key TEXT NOT NULL,source_id TEXT NOT NULL,source_order INTEGER NOT NULL,source_locator TEXT NOT NULL,source_column TEXT NOT NULL,PRIMARY KEY(product_key,field_name,value_key,source_id,source_order),FOREIGN KEY(product_key,field_name,value_key) REFERENCES product_values(product_key,field_name,value_key),FOREIGN KEY(source_id,source_order) REFERENCES source_rows(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE aliases(alias_id TEXT PRIMARY KEY,product_key TEXT NOT NULL REFERENCES products(product_key),alias TEXT NOT NULL,language TEXT NOT NULL,alias_type TEXT NOT NULL,UNIQUE(product_key,alias,language));
CREATE TABLE alias_sources(alias_id TEXT NOT NULL REFERENCES aliases(alias_id),source_id TEXT NOT NULL,source_order INTEGER NOT NULL,source_locator TEXT NOT NULL,PRIMARY KEY(alias_id,source_id,source_order),FOREIGN KEY(source_id,source_order) REFERENCES source_rows(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE components(component_id TEXT PRIMARY KEY,product_key TEXT NOT NULL REFERENCES products(product_key),source_order INTEGER NOT NULL,name_as_listed TEXT NOT NULL,strength_text TEXT,strength_value REAL,strength_unit TEXT,basis_text TEXT,role TEXT NOT NULL CHECK(role='UNKNOWN'),mapping_status TEXT NOT NULL CHECK(mapping_status='UNMAPPED'),canonical_ingredient_id TEXT,statement_kind TEXT NOT NULL,UNIQUE(product_key,source_order));
CREATE TABLE component_sources(component_id TEXT NOT NULL REFERENCES components(component_id),source_id TEXT NOT NULL,source_order INTEGER NOT NULL,source_locator TEXT NOT NULL,source_column TEXT NOT NULL,PRIMARY KEY(component_id,source_id,source_order),FOREIGN KEY(source_id,source_order) REFERENCES source_rows(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE dedupe_map(source_id TEXT NOT NULL,source_order INTEGER NOT NULL,product_key TEXT,component_id TEXT,action TEXT NOT NULL,reason TEXT NOT NULL,PRIMARY KEY(source_id,source_order),FOREIGN KEY(source_id,source_order) REFERENCES source_rows(source_id,source_order)) WITHOUT ROWID;
CREATE TABLE products_export(native_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT NOT NULL,components_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,original_json TEXT NOT NULL);
CREATE INDEX idx_jp_product_rows_source ON product_rows(source_id,source_order);
CREATE INDEX idx_jp_components_product ON components(product_key,source_order);
CREATE INDEX idx_jp_aliases_product ON aliases(product_key);
'''
def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def key(kind,*p):return 'jp-'+kind+':'+digest(js(p))
def insert(c,t,**r):
 names=list(r);c.execute('INSERT INTO '+t+' ('+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')',[r[n] for n in names])
def cells(raw):
 result={}
 for cell in raw['cells']:
  address=cell['attributes']['r'];m=re.fullmatch(r'([A-Z]+)[0-9]+',address)
  if not m or m[1] in result:raise ValueError('Invalid/repeated original cell address '+address)
  value=cell.get('value')
  if value is not None and not isinstance(value,str):raise ValueError('Unexpected cell display value type')
  result[m[1]]=value
 return result

def build(source,output):
 if output.exists():raise ValueError('Refuse overwrite '+str(output))
 output.mkdir(parents=True);state={'status':'RUNNING','events':[]}
 def progress(name,**data):
  state['events'].append({'phase':name,**data});(output/'BUILD_PROGRESS.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');print(js(state['events'][-1]),flush=True)
 try:
  source_db=source/'JP_UNREVIEWED_candidate.sqlite3'
  if not source_db.is_file():raise ValueError('Missing fresh official JP intake')
  src=sqlite3.connect('file:'+str(source_db.resolve())+'?mode=ro',uri=True);src.row_factory=sqlite3.Row
  original=[(r['source_snapshot_id'],json.loads(r['metadata_json'])) for r in src.execute('SELECT * FROM candidate_sources')]
  if len(original)!=5:raise ValueError('Require exactly five retained MHLW snapshots')
  def section(sid):
   m=re.search(r'[-_]0([1-5])\.xlsx-sha256-',sid)
   if not m:raise ValueError('Unrecognized original section '+sid)
   return int(m[1])
  original.sort(key=lambda r:section(r[0]));archive=output/'raw-sources';archive.mkdir();pins={};metadata={};headers={};records=[];counts=collections.Counter();per_source={}
  for file in ['source-page.html','license-evidence.html','ATTRIBUTION.txt','intake-report.json']:
   f=source/file
   if not f.is_file():raise ValueError('Required source evidence missing '+file)
   shutil.copyfile(f,archive/file);pins[file]={'sha256':sha(f),'bytes':f.stat().st_size}
  db=output/'JP_NATIVE_INTERMEDIATE.sqlite3';c=sqlite3.connect(db);c.executescript(SCHEMA);c.execute('BEGIN');c.execute('PRAGMA defer_foreign_keys=ON')
  for sid,m in original:
   sect=section(sid);folder=source/sid;xlsx=list(folder.glob('*.xlsx'))
   if len(xlsx)!=1:raise ValueError('Original workbook missing/ambiguous '+sid)
   xlsx=xlsx[0];actual=sha(xlsx)
   if actual!=m['raw_sha256'] or actual!=sid.split('-sha256-')[1]:raise ValueError('Original XLSX hash mismatch '+sid)
   dst=archive/sid;dst.mkdir();shutil.copyfile(xlsx,dst/xlsx.name);shutil.copyfile(folder/'source.json',dst/'source.json');pins[sid]={'file':'raw-sources/'+sid+'/'+xlsx.name,'sha256':actual,'bytes':xlsx.stat().st_size,'source_metadata_sha256':sha(folder/'source.json')};metadata[sid]=m
   insert(c,'sources',source_id=sid,metadata_json=js(m),original_file=pins[sid]['file'],original_sha256=actual,original_bytes=xlsx.stat().st_size)
   n=0;header_count=0
   for row in src.execute('SELECT * FROM candidate_rows WHERE source_snapshot_id=? ORDER BY source_order',(sid,)):
    n+=1;raw=json.loads(row['raw_json']);v=cells(raw);order=row['source_order'];code=v.get('A' if sect==5 else 'B')
    if order==1:
     expected={'A':'薬価基準収載医薬品コード','B':'成分名','C':'品名'} if sect==5 else {'A':'区分','B':'薬価基準収載医薬品コード','C':'成分名','D':'規格','H':'品名','I':'メーカー名'}
     if any(v.get(k)!=value for k,value in expected.items()):raise ValueError('Official header/schema mismatch '+sid)
     headers[sid]=v;classification='HEADER';counts['header_rows']+=1;header_count+=1
    else:
     if not code or not re.fullmatch('[0-9]{7}[A-Z][0-9]{4}',code):raise ValueError('Invalid native price-list code at '+row['source_locator'])
     if row['native_reference']!=code:raise ValueError('Native reference disagrees with original cell')
     name=v.get('C' if sect==5 else 'H');ingredient=v.get('B' if sect==5 else 'C')
     if not name or not name.strip():raise ValueError('Missing official product name at '+row['source_locator'])
     classification='DATA';counts['data_rows']+=1
     projection={'native_id':code,'name_as_listed':name,'ingredient_statement_as_listed':ingredient,'manufacturer_as_listed':v.get('I') if sect!=5 else None,'specification_as_listed':v.get('D') if sect!=5 else None,'category_as_listed':v.get('A') if sect!=5 else None,'source_section':sect,'all_cell_values':v}
     records.append({'source_id':sid,'source_order':order,'source_locator':row['source_locator'],'projection':projection})
    insert(c,'source_rows',source_id=sid,source_order=order,source_locator=row['source_locator'],raw_json=row['raw_json'],raw_json_sha256=digest(row['raw_json']),native_id_as_listed=code,row_classification=classification)
    counts['original_raw_rows']+=1
   if n!=m['row_count'] or header_count!=1:raise ValueError('Incomplete source rows/header '+sid)
   per_source[sid]={'raw_rows':n,'headers':header_count,'data_rows':n-header_count,'source_section':sect}
  progress('all_five_original_sources_verified',original_rows=counts['original_raw_rows'],headers=counts['header_rows'],data_rows=counts['data_rows'])
  grouped=collections.defaultdict(list)
  for r in records:grouped[r['projection']['native_id']].append(r)
  conflict_products=[];missing_manufacturer=0;component_ref_count=0;component_count=0;identity_merge=0
  for code,rs in sorted(grouped.items()):
   rs.sort(key=lambda r:(r['projection']['source_section'],r['source_order'],r['source_id']));pid=key('product',NAMESPACE,code)
   fields={'display_name':'name_as_listed','generic_name':'ingredient_statement_as_listed','manufacturer':'manufacturer_as_listed','specification':'specification_as_listed','category':'category_as_listed'}
   values={k:sorted({r['projection'][f] for r in rs if r['projection'][f] is not None and r['projection'][f].strip()}) for k,f in fields.items()}
   conflicts={k:v for k,v in values.items() if len(v)>1};conflict_products.append(code) if conflicts else None
   def first(f):return next((r['projection'][f] for r in rs if r['projection'][f] is not None and r['projection'][f].strip()),None)
   display=first('name_as_listed');generic=first('ingredient_statement_as_listed');manufacturer=first('manufacturer_as_listed');specification=first('specification_as_listed');category=first('category_as_listed')
   if manufacturer is None:missing_manufacturer+=1
   insert(c,'products',product_key=pid,native_id=code,jurisdiction='JP',identifier_namespace=NAMESPACE,identity_kind='PRICE_LIST_ENTRY_NOT_MARKETING_AUTHORIZATION',display_name=display,generic_name=generic,manufacturer=manufacturer,dosage_form=None,route=None,specification_as_listed=specification,category_as_listed=category,composition_status='UNKNOWN',review_status='PENDING',reviewer_kind='AUTOMATED',conflicts_json=js(conflicts))
   comps={};all_refs=[];assertions=[]
   for i,r in enumerate(rs):
    sid=r['source_id'];order=r['source_order'];loc=r['source_locator'];p=r['projection'];sect=p['source_section'];source_ref={'source_id':sid,'locator':loc};all_refs.append(source_ref)
    insert(c,'product_rows',product_key=pid,source_id=sid,source_order=order,source_locator=loc,projection_json=js(p),projection_sha256=digest(js(p)))
    name=p['name_as_listed'];aid=key('alias',NAMESPACE,code,name,'ja');c.execute('INSERT OR IGNORE INTO aliases VALUES (?,?,?,?,?)',(aid,pid,name,'ja','MHLW_PRODUCT_NAME_AS_LISTED'));insert(c,'alias_sources',alias_id=aid,source_id=sid,source_order=order,source_locator=loc)
    columns={'display_name':'C' if sect==5 else 'H','generic_name':'B' if sect==5 else 'C','manufacturer':'I','specification':'D','category':'A'}
    for label,field in fields.items():
     value=p[field]
     if value is None or not value.strip():continue
     vid=key('value',label,value);c.execute('INSERT OR IGNORE INTO product_values VALUES (?,?,?,?)',(pid,label,value,vid));insert(c,'value_sources',product_key=pid,field_name=label,value_key=vid,source_id=sid,source_order=order,source_locator=loc,source_column=columns[label])
    ingredient=p['ingredient_statement_as_listed'];cid=None
    if ingredient is None or not ingredient.strip():counts['ingredient_statement_missing_rows']+=1
    elif ingredient.strip() in ['略','（略）','(略)','省略']:
     counts['explicit_omitted_statement_rows']+=1
    else:
     cid=key('component',NAMESPACE,code,ingredient)
     if cid not in comps:
      seq=len(comps);comps[cid]={'source_order':seq,'name_as_listed':ingredient,'strength_text':None,'role':'UNKNOWN','mapping_status':'UNMAPPED','source_ref':source_ref,'source_refs':[]};insert(c,'components',component_id=cid,product_key=pid,source_order=seq,name_as_listed=ingredient,strength_text=None,strength_value=None,strength_unit=None,basis_text=None,role='UNKNOWN',mapping_status='UNMAPPED',canonical_ingredient_id=None,statement_kind='OFFICIAL_INGREDIENT_NAME_FIELD_UNSPLIT_NOT_COMPLETE_LABEL');component_count+=1
     comps[cid]['source_refs'].append(source_ref);insert(c,'component_sources',component_id=cid,source_id=sid,source_order=order,source_locator=loc,source_column='B' if sect==5 else 'C');component_ref_count+=1
    action='FIRST_NATIVE_CODE_ASSERTION' if i==0 else 'MERGED_SAME_NATIVE_CODE_RETAINED_ASSERTIONS';identity_merge+=(i>0)
    insert(c,'dedupe_map',source_id=sid,source_order=order,product_key=pid,component_id=cid,action=action,reason='Official same price-list native code only; all original fields/locators retained. No cross-code or chemical-name equivalence.')
    assertions.append({'source_ref':source_ref,'source_order':order,'source_section':sect,'fields':p,'raw_row_sha256':c.execute('SELECT raw_json_sha256 FROM source_rows WHERE source_id=? AND source_order=?',(sid,order)).fetchone()[0]})
   components=list(comps.values());original={'identity_kind':'PRICE_LIST_ENTRY_NOT_MARKETING_AUTHORIZATION','all_original_assertions':assertions,'conflicts':conflicts,'missing':{'manufacturer':manufacturer is None,'standalone_dosage_form':True,'explicit_administration_route':True,'ingredient_specific_dose':True,'complete_composition':True},'specification_as_listed':values['specification'],'category_as_listed':values['category'],'field_semantics':{'generic_name':'Original 成分名 string only; unsplit possibly abbreviated/aggregate statement, not verified INN/global canonical ingredient','specification':'Original 規格 is product price-list specification, not ingredient-specific strength/dose','manufacturer':'Original メーカー名, absent for some unified-name price entries; not inferred','dosage_form_and_route':'NULL because no explicit standalone source fields; not guessed from name/code/category'},'clinical_completeness':'UNKNOWN','clinical_rules':0,'source_original_bytes_in_archive':True}
   insert(c,'products_export',native_id=code,display_name=display,generic_name=generic,manufacturer=manufacturer,dosage_form=None,route=None,aliases_json=js(values['display_name']),components_json=js(components),source_refs_json=js(all_refs),original_json=js(original))
  # Headers remain first-class raw evidence and explicit dedupe exclusions, never product rows.
  for row in c.execute("SELECT source_id,source_order FROM source_rows WHERE row_classification='HEADER'").fetchall():insert(c,'dedupe_map',source_id=row[0],source_order=row[1],product_key=None,component_id=None,action='HEADER_NOT_PRODUCT',reason='Original official column header retained intact')
  c.commit();integrity=c.execute('PRAGMA integrity_check').fetchone()[0];fk=c.execute('PRAGMA foreign_key_check').fetchall()
  if integrity!='ok' or fk:raise ValueError('SQLite integrity/FK failure')
  table_counts={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t, in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
  missing_raw_mapping=c.execute('SELECT COUNT(*) FROM source_rows s LEFT JOIN dedupe_map d USING(source_id,source_order) WHERE d.source_id IS NULL').fetchone()[0]
  if missing_raw_mapping:raise ValueError('Raw rows not mapped or explicitly classified')
  c.close();progress('source_native_intermediate_complete',products=len(grouped),components=component_count,source_refs=component_ref_count)
  summary={'status':'PASS_SOURCE_NATIVE_INTERMEDIATE_NOT_RUNTIME_OR_CLINICAL_APPROVAL','country':'JP','identifier_namespace':NAMESPACE,'identity_kind':'MHLW_PRICE_LIST_ENTRY_NOT_PMDA_MARKETING_AUTHORIZATION','source_reference_database':str(source_db.resolve()),'source_reference_sha256':sha(source_db),'source_files':pins,'headers':headers,'per_source_counts':per_source,'counts':dict(counts)|{'independent_native_price_entries':len(grouped),'merged_duplicate_identity_source_rows':identity_merge,'exact_same_code_component_statements':component_count,'component_source_assertion_rows':component_ref_count,'merged_component_assertion_refs':component_ref_count-component_count,'conflicting_product_ids':len(conflict_products),'missing_manufacturer_products':missing_manufacturer,'excluded_product_rows':0,'unknown_composition_products':len(grouped),'unknown_standalone_dosage_form_products':len(grouped),'unknown_route_products':len(grouped)},'conflict_product_ids':conflict_products,'dedupe_policy':'Group only identical official12-character price code. Same native code exact display and ingredient statement dedupe into one projection, all source assertions/headers/OOXML/raw workbook bytes remain. Null absent fields are not conflicting nonempty values. No same-name cross-country/code merges or chemical inference.','composition_policy':'One unsplit official 成分名 statement per exact product-code+string. Never split dot separators, expand compound ingredients, infer salts or ingredient dose, call it COMPLETE, or claim PMDA labels. Generic_name export means original 成分名 only.','tables':table_counts,'exports':'products_export contains required parent interchange fields; components_json has source_ref plus all source_refs; original_json preserves all original source-cell assertions, conflict/missing semantics and raw-row hashes. Original OOXML detail remains source_rows.raw_json and byte-exact workbooks.','clinical_rules':0,'review':'AUTOMATED/PENDING; no licence/clinical approval','integrity_check':integrity,'foreign_key_violations':len(fk),'database_sha256':sha(db),'database_bytes':db.stat().st_size,'builder_sha256':sha(Path(__file__)),'python':sys.version,'sqlite':sqlite3.sqlite_version,'rebuild_argv':['python3',str(Path(__file__).resolve()),'--source',str(source.resolve()),'--output','<new-empty-output-directory>'],'source_pages':['https://www.mhlw.go.jp/topics/2026/04/tp20260401-01.html','https://shinryohoshu.mhlw.go.jp/shinryohoshu/faq/'],'limitations':['Price code is a reimbursement entry; unified-name entries may cover more than one marketed manufacturer/brand. Do not claim all approved Japanese medicines.','Original five price/generic-info sections only; not PMDA package inserts or complete composition.','No full market coverage, regulatory approval, canonical mapping, clinical rule or licence approval implied.']}
  (output/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');state['status']='BUILD_COMPLETE';(output/'BUILD_PROGRESS.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');(output/'SHA256SUMS.json').write_text(json.dumps({str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'},ensure_ascii=False,indent=2)+'\n');print(js({'status':summary['status'],'database':str(db),'counts':summary['counts'],'sha256':summary['database_sha256']}),flush=True)
  return summary
 except Exception as exc:
  state['status']='FAIL_RETAINED';state['error']=repr(exc);state['traceback']=traceback.format_exc();(output/'BUILD_FAILURE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n');raise
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.source,a.output)
