#!/usr/bin/env python3
"""Rebuild source-native KR item projection; never infer composition from product names."""
import pathlib,sqlite3,csv,io,json,hashlib,collections,zipfile,xml.etree.ElementTree as E,shutil,re,datetime,argparse
OUT=None;RAW=None;OLD=None
def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def digest(b):return hashlib.sha256(b).hexdigest()
def ref(s,n):return {'source_id':s,'locator':n}
def parsed_xlsx(p):
 ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 def plain(n):return ''.join(x.text or '' for x in list(n.findall('s:t',ns))+list(n.findall('s:r/s:t',ns)))
 with zipfile.ZipFile(p) as z:
  if sum(x.file_size for x in z.infolist())>128*1024**2:raise ValueError('expanded XLSX over bound')
  ss=[plain(x) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
  for row in E.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('s:sheetData/s:row',ns):
   obj={};orig=[]
   for cell in row.findall('s:c',ns):
    val=cell.findtext('s:v',namespaces=ns);val=ss[int(val)] if cell.get('t')=='s' and val is not None else plain(cell.find('s:is',ns)) if cell.get('t')=='inlineStr' else val
    obj[re.sub(r'\d+$','',cell.get('r'))]=val
    orig.append({'coordinate':cell.get('r'),'type':cell.get('t'),'value':val,'formula':cell.findtext('s:f',namespaces=ns)})
   yield int(row.get('r')),obj,orig

def build(source,output):
 global OUT,RAW,OLD
 OUT=output;RAW=OUT/'raw';OLD=source;RAW.mkdir(parents=True,exist_ok=True)
 db=OUT/'KR_SOURCE_NATIVE.sqlite3'
 if db.exists():raise ValueError('Refuse overwriting retained intermediate')
 original=next(OLD.rglob('HIRA_standard_codes.csv'));raw=original.read_bytes();sha=digest(raw)
 archived=RAW/'HIRA_standard_codes.csv'
 if not archived.exists():shutil.copyfile(original,archived)
 meta=json.loads(original.with_name('source.json').read_text());assert sha==meta['raw_sha256'];sid=meta['source_snapshot_id'];xp=RAW/'khidi-reimbursement-xlsx.bin';xsha=digest(xp.read_bytes());xid='kr-hira-reimbursement-20260101-sha256-'+xsha
 con=sqlite3.connect(db);con.execute('pragma foreign_keys=ON');con.executescript('''
 CREATE TABLE sources(source_id TEXT PRIMARY KEY,source_url TEXT NOT NULL,source_sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL);
 CREATE TABLE raw_rows(source_id TEXT NOT NULL REFERENCES sources(source_id),source_order INTEGER NOT NULL,source_locator TEXT NOT NULL,row_sha256 TEXT NOT NULL,raw_json TEXT NOT NULL,PRIMARY KEY(source_id,source_order));
 CREATE TABLE products(native_id TEXT PRIMARY KEY,identifier_namespace TEXT NOT NULL,display_name TEXT NOT NULL,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,composition_status TEXT CHECK(composition_status='UNKNOWN'),review_status TEXT CHECK(review_status='PENDING'));
 CREATE TABLE product_source_rows(native_id TEXT REFERENCES products(native_id),source_id TEXT,source_order INTEGER,FOREIGN KEY(source_id,source_order) REFERENCES raw_rows(source_id,source_order),PRIMARY KEY(native_id,source_id,source_order));
 CREATE TABLE package_codes(standard_code TEXT PRIMARY KEY,native_id TEXT REFERENCES products(native_id),representative_code TEXT,product_code TEXT,general_ingredient_code TEXT,source_id TEXT,source_order INTEGER,FOREIGN KEY(source_id,source_order) REFERENCES raw_rows(source_id,source_order));
 CREATE TABLE aliases(native_id TEXT REFERENCES products(native_id),alias TEXT,alias_type TEXT,language TEXT CHECK(language='ko'),PRIMARY KEY(native_id,alias,alias_type));
 CREATE TABLE code_assertions(native_id TEXT REFERENCES products(native_id),code_type TEXT,code TEXT,source_id TEXT,source_order INTEGER,FOREIGN KEY(source_id,source_order) REFERENCES raw_rows(source_id,source_order),PRIMARY KEY(native_id,code_type,code,source_id,source_order));
 CREATE TABLE raw_components(native_id TEXT REFERENCES products(native_id),source_order INTEGER,name_as_listed TEXT NOT NULL,strength_text TEXT,role TEXT,mapping_status TEXT CHECK(mapping_status='UNMAPPED'),source_id TEXT,source_locator TEXT,raw_assertion_json TEXT,PRIMARY KEY(native_id,source_id,source_locator));
 CREATE TABLE products_export(native_id TEXT PRIMARY KEY,display_name TEXT,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT,components_json TEXT,source_refs_json TEXT,original_json TEXT);
 CREATE TABLE exclusions(reason TEXT,source_id TEXT,source_order INTEGER,details_json TEXT);
 ''')
 con.execute('insert into sources values (?,?,?,?)',(sid,meta['source_url'],sha,js(meta)))
 xm={'source_url':'https://www.khidi.or.kr/fileDownload?fileDownType=C&fileId=1&paramMenuId=MENU01869&titleId=523332','source_page':'https://www.khidi.or.kr/board/view?linkId=48938997&menuId=MENU01869','publisher':'HIRA, official copy hosted by Korea Health Industry Development Institute','publisher_date':'2026-01-01','retrieved_at':json.loads(xp.with_suffix('.receipt.json').read_text())['retrieved_at'],'sha256':xsha,'scope':'21770 reimbursed records at2026-01-01, not all KR products/current composition','rights_status':'PENDING','clinical_review':'PENDING'}
 con.execute('insert into sources values (?,?,?,?)',(xid,xm['source_url'],xsha,js(xm)))
 groups=collections.defaultdict(list);codeitems=collections.defaultdict(set);codes=collections.Counter();excluded=0
 rows=list(csv.DictReader(io.StringIO(raw.decode(meta.get('encoding','cp949')),newline='')))
 for n,obj in enumerate(rows,1):
  native=obj['품목기준코드'].strip();standard=obj['표준코드'].strip();loc=f'record:{sid}/csv/row/{n+1}';serial=js(obj)
  con.execute('insert into raw_rows values (?,?,?,?,?)',(sid,n,loc,digest(serial.encode()),serial))
  if not re.fullmatch(r'[0-9]{9}',native) or not re.fullmatch(r'[0-9]{13}',standard):
   con.execute('insert into exclusions values (?,?,?,?)',('invalid official ID',sid,n,serial));excluded+=1;continue
  codes[standard]+=1;groups[native].append((n,obj,loc));pc=obj['제품코드(개정후)'].strip()
  if pc:codeitems[pc].add(native)
 assert rows and not any(v>1 for v in codes.values())
 for native,rr in sorted(groups.items()):
  values=lambda field:sorted({obj[field] for _,obj,_ in rr if obj[field].strip()})
  one=lambda field:values(field)[0] if len(values(field))==1 else None
  name=rr[0][1]['한글상품명'];con.execute('insert into products values (?,?,?,?,?,?,?,?,?)',(native,'MFDS_ITEM_CODE',name,None,one('업체명'),one('제형구분'),None,'UNKNOWN','PENDING'))
  for alias in values('한글상품명'):con.execute('insert into aliases values (?,?,?,?)',(native,alias,'OFFICIAL_PRODUCT_NAME','ko'))
  for n,obj,loc in rr:
   con.execute('insert into product_source_rows values (?,?,?)',(native,sid,n));con.execute('insert into package_codes values (?,?,?,?,?,?,?)',(obj['표준코드'].strip(),native,obj['대표코드'].strip(),obj['제품코드(개정후)'].strip() or None,obj['일반명코드(성분명코드)'].strip() or None,sid,n))
   for field in ['대표코드','제품코드(개정후)','일반명코드(성분명코드)','국제표준코드(ATC코드)']:
    if obj[field].strip():con.execute('insert into code_assertions values (?,?,?,?,?)',(native,field,obj[field].strip(),sid,n))
 # Join by exact official reimbursement product code only. If that code names more
 # than one MFDS item, quarantine; never join on name, substrings or inferred codes.
 workbook=list(parsed_xlsx(xp));assert workbook[0][1].get('F')=='주성분명' and workbook[0][1].get('G')=='제품코드'
 matched=0;unmatched=0;ambiguous=0;routes=collections.defaultdict(set);xrefs=collections.defaultdict(list);seen_assertions=collections.Counter()
 for n,obj,orig in workbook[1:]:
  serial=js({'resolved_columns':obj,'cells':orig});loc=f'record:{xid}/xlsx/sheet1/row/{n}';con.execute('insert into raw_rows values (?,?,?,?,?)',(xid,n,loc,digest(serial.encode()),serial));pc=(obj.get('G') or '').strip();nativeids=codeitems.get(pc,set())
  if len(nativeids)!=1:
   reason='ambiguous_product_code_to_multiple_item_ids' if len(nativeids)>1 else 'xlsx_product_code_not_in_august_standard_mapping';con.execute('insert into exclusions values (?,?,?,?)',(reason,xid,n,js({'product_code':pc,'item_ids':sorted(nativeids)})));ambiguous+=len(nativeids)>1;unmatched+=not nativeids;continue
  native=next(iter(nativeids));name=obj.get('F')
  if not name or not name.strip():con.execute('insert into exclusions values (?,?,?,?)',('missing_explicit_ingredient_text',xid,n,serial));continue
  # F is the complete official主成分 assertion; preserve multiple constituent text
  # intact. It is not asserted to be one chemical ingredient or complete current composition.
  assertion={'official_ingredient_count':obj.get('E'),'general_ingredient_code':obj.get('D'),'source_product_code':pc,'full_name_strength_as_listed':name,'status':'RAW_COMPOSITION_TEXT_UNSPLIT','temporal_mismatch':'2026-01 reimbursement vs2026-08 standard mapping','raw_source_row':n}
  con.execute('insert into raw_components values (?,?,?,?,?,?,?,?,?)',(native,n,name,None,'UNKNOWN','UNMAPPED',xid,loc,js(assertion)));con.execute('insert into product_source_rows values (?,?,?)',(native,xid,n));matched+=1;xrefs[native].append(ref(xid,loc))
  if obj.get('B'):routes[native].add(obj['B'])
  seen_assertions[obj.get('E')]+=1
 for native,rr in sorted(groups.items()):
  p=con.execute('select display_name,generic_name,manufacturer,dosage_form from products where native_id=?',(native,)).fetchone();route=next(iter(routes[native])) if len(routes[native])==1 else None
  con.execute('update products set route=? where native_id=?',(route,native));aa=[x[0] for x in con.execute('select alias from aliases where native_id=? order by alias',(native,))]
  cc=[{'source_order':r[0],'name_as_listed':r[1],'strength_text':r[2],'role':r[3],'mapping_status':r[4],'source_ref':ref(r[5],r[6]),'assertion_kind':'RAW_COMPOSITION_TEXT_UNSPLIT','original_assertion':json.loads(r[7])} for r in con.execute('select source_order,name_as_listed,strength_text,role,mapping_status,source_id,source_locator,raw_assertion_json from raw_components where native_id=? order by source_order',(native,))]
  refs=[ref(sid,loc) for _,_,loc in rr]+xrefs[native];vals={k:sorted({o[k] for _,o,_ in rr}) for k in rows[0]};conf={k:v for k,v in vals.items() if len(v)>1}
  original={'identifier_namespace':'MFDS_ITEM_CODE','jurisdiction':'KR','composition_status':'UNKNOWN','review_status':'PENDING','clinical_rules':0,'raw_standard_rows':len(rr),'source_native_values':vals,'conflicting_values':conf,'missing_fields':['generic_ingredient_identity','verified_current_composition','canonical_mapping'],'provenance':'All raw_rows contain exact parsed original cells/columns, original rowSHA and locator; fullCSV/XLSX archived','dedupe_policy':'Only exact official MFDS item code groups pack rows; all pack/representative/insurance codes and name variants preserved. No same-name merge or cross-market equivalence.'}
  con.execute('insert into products_export values (?,?,?,?,?,?,?,?,?,?)',(native,*p,route,js(aa),js(cc),js(refs),js(original)))
 con.commit();assert con.execute('pragma integrity_check').fetchone()[0]=='ok';assert not con.execute('pragma foreign_key_check').fetchall()
 counts={t:con.execute('select count(*) from '+t).fetchone()[0] for t in ['sources','raw_rows','products','package_codes','aliases','raw_components','code_assertions','exclusions','products_export']};assert counts['products']==len(groups) and counts['package_codes']+excluded==len(rows)
 report={'status':'SOURCE_NATIVE_INTERMEDIATE_COMPLETE_UNREVIEWED','counts':counts,'csv_rows':len(rows),'unique_item_products':len(groups),'unique_standard_package_codes':len(codes),'pack_rows_grouped_to_items':len(rows)-len(groups),'duplicate_standard_codes':sum(v>1 for v in codes.values()),'input_headers':list(rows[0]),'xlsx_source_rows':len(workbook)-1,'xlsx_exact_product_code_matched_rows':matched,'xlsx_unmatched_rows':unmatched,'xlsx_ambiguous_rows':ambiguous,'reported_ingredient_count_distribution_for_matched_assertions':dict(seen_assertions),'products_with_raw_composition_assertions':con.execute('select count(distinct native_id) from raw_components').fetchone()[0],'product_name_variation_groups':con.execute('select count(*) from (select native_id from aliases group by native_id having count(*)>1)').fetchone()[0],'input_sha256':{'standardCSV':sha,'reimbursementXLSX':xsha},'rights_status':'PENDING','clinical_rules':0,'clinical_review':'PENDING','runtime_approved':False,'source_scope':'Fresh HIRA standard mapping (publisher date in source metadata) plus historical Jan2026 HIRA reimbursement copy; historical and herbal products retained, status UNKNOWN. Not current all-market ingredient coverage.','dedupe':'Exact MFDS item code only; package rows+codes preserved; ambiguous insurance code links excluded','ingredient_policy':'Full official主成分名 cell stored unsplit; if multiingredient, all text preserved but no inferred split or canonical equivalence. Zero assertion rows means UNKNOWN, not no ingredients.','api_gap':'Official15021027 ingredient API requires ServiceKey; no-key request returned401. API key not supplied or bypassed. Public XLSX partly fills source evidence gap.','rebuild_command':'python3 '+str(pathlib.Path(__file__).resolve()),'schema_export':'products_export(native_id,display_name,generic_name,manufacturer,dosage_form,route,aliases_json,components_json,source_refs_json,original_json)'}
 con.close();report['sqlite_bytes']=db.stat().st_size;report['sqlite_sha256']=digest(db.read_bytes());(OUT/'BUILD_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();build(a.source,a.output)
