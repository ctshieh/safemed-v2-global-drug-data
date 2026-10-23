import pathlib,sqlite3,csv,io,json,hashlib,collections,argparse
D=None;OLD=None;RAW=None
def js(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(source,output):
 global D,OLD,RAW
 D=output;OLD=source;RAW=D/'downloads/HIRA_ingredient_dictionary.csv'
 db=D/'SUPPLEMENT.sqlite3'
 if db.exists():raise ValueError('immutable output exists')
 download=json.loads((D/'downloads/DICTIONARY_DOWNLOAD.json').read_text());assert sha(RAW)==download['sha256'];sid='kr-hira-ingredient-dictionary-sha256-'+download['sha256'];old=sqlite3.connect(OLD.resolve().as_uri()+'?mode=ro',uri=True);c=sqlite3.connect(db);c.execute('pragma foreign_keys=ON');c.executescript('''
 CREATE TABLE sources(source_id TEXT PRIMARY KEY,source_url TEXT,source_sha256 TEXT,metadata_json TEXT);
 CREATE TABLE dictionary_rows(source_order INTEGER PRIMARY KEY,general_code TEXT NOT NULL,name_as_listed TEXT NOT NULL,source_locator TEXT UNIQUE NOT NULL,raw_json TEXT NOT NULL,row_sha256 TEXT NOT NULL,original_record_sha256 TEXT NOT NULL);
 CREATE INDEX idx_dictionary_code ON dictionary_rows(general_code);
 CREATE TABLE code_match_evidence(native_id TEXT,general_code TEXT,original_source_id TEXT,original_source_order INTEGER,original_locator TEXT,original_row_sha256 TEXT,PRIMARY KEY(native_id,general_code,original_source_id,original_source_order));
 CREATE TABLE products_export(native_id TEXT PRIMARY KEY,display_name TEXT,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT,components_json TEXT,source_refs_json TEXT,original_json TEXT);
 ''');metadata={**download,'publisher':'Health Insurance Review and Assessment Service HIRA','licence_declared':'Korea Open Government License Type1 attribution','review_status':'PENDING','temporal_scope':'Official dictionary with fresh product-code assertions; publisher dates preserved in source metadata; historical raw evidence only','clinical_rules':0};c.execute('insert into sources values (?,?,?,?)',(sid,download['source_url'],download['sha256'],js(metadata)))
 lines=RAW.read_bytes().splitlines(keepends=True);rows=list(csv.DictReader(io.StringIO(RAW.read_bytes().decode(download['encoding']))));assert len(lines)==len(rows)+1==download['rows']+1
 bycode=collections.defaultdict(list)
 for n,obj in enumerate(rows,1):
  parsed=dict(zip(rows[0],next(csv.reader(io.StringIO(lines[n].decode(download['encoding']))))))
  assert parsed==obj
  code=obj['일반명코드'].strip();name=obj['일반명'];assert code and name.strip();serial=js(obj);loc=f'record:{sid}/csv/row/{n+1}';rowhash=hashlib.sha256(serial.encode()).hexdigest();c.execute('insert into dictionary_rows values (?,?,?,?,?,?,?)',(n,code,name,loc,serial,rowhash,hashlib.sha256(lines[n]).hexdigest()));bycode[code].append((n,obj,loc,rowhash))
 matches=collections.defaultdict(set);firstproof={}
 for native,code,s,order,locator,rowhash in old.execute("select a.native_id,a.code,a.source_id,a.source_order,r.source_locator,r.row_sha256 from code_assertions a join raw_rows r on r.source_id=a.source_id and r.source_order=a.source_order where a.code_type='일반명코드(성분명코드)'"):
  if code not in bycode:continue
  matches[native].add(code);c.execute('insert into code_match_evidence values (?,?,?,?,?,?)',(native,code,s,order,locator,rowhash));firstproof.setdefault((native,code),{'source_id':s,'locator':locator,'row_sha256':rowhash})
 total=0;previous_missing=0;multiconstituent=0
 for native,codes in sorted(matches.items()):
  original=old.execute('select * from products_export where native_id=?',(native,)).fetchone();assert original
  components=[];refs=[]
  for code in sorted(codes):
   for n,obj,loc,rhash in bycode[code]:
    source_ref={'source_id':sid,'locator':loc};components.append({'source_order':n,'name_as_listed':obj['일반명'],'strength_text':js({'amount_as_listed':obj['함량'],'unit_as_listed':obj['단위']}),'role':'UNKNOWN','mapping_status':'UNMAPPED','source_ref':source_ref,'assertion_kind':'OFFICIAL_DICTIONARY_ORIGINAL_ROW','original_assertion':{'general_code':code,'dosage_form_as_listed':obj['제형'],'route_as_listed':obj['투여'],'raw_original_fields':obj,'row_sha256':rhash,'matched_product_code_evidence':firstproof[(native,code)]}});refs.append(source_ref)
  was_missing=old.execute('select count(*) from raw_components where native_id=?',(native,)).fetchone()[0]==0;previous_missing+=was_missing;total+=len(components);multiconstituent+=any(len(bycode[k])>2 for k in codes)
  info={'merge_policy':'merge_same_identity','identifier_namespace':'MFDS_ITEM_CODE','jurisdiction':'KR','supplement_only':True,'dedupe_policy':'Exact product code_assertions.general_code = official dictionary일반명코드; no name matching, no inferred codes, no chemical equivalence. Keep all raw dictionary rows, including third+ constituents.','matched_codes':sorted(codes),'new_original_rows':len(components),'previously_missing_all_assertions':was_missing,'temporal_mismatch':'Dictionary and product mapping may have different publisher dates, recorded in original metadata; not complete reviewed composition.','composition_status':'UNKNOWN','review_status':'PENDING','clinical_rules':0,'original_v1_retained':str(OLD),'code_match_evidence_table':'Every matching originalCSVcode assertion+rowhash/locator retained in code_match_evidence; main v1 preserves full original rows.'}
  c.execute('insert into products_export values (?,?,?,?,?,?,?,?,?,?)',(*original[:6],original[6],js(components),js(refs),js(info)))
 c.commit();integrity=c.execute('pragma integrity_check').fetchone()[0];fk=c.execute('pragma foreign_key_check').fetchall();assert integrity=='ok' and not fk;assert matches
 report={'status':'PASS_SOURCE_NATIVE_SUPPLEMENT_PENDING_RIGHTS_CLINICAL','merge_policy':'merge_same_identity','identifier_namespace':'MFDS_ITEM_CODE','country':'KR','new_products':0,'matched_existing_product_exports':len(matches),'new_dictionary_assertion_rows_exported':total,'dictionary_raw_rows':len(rows),'dictionary_unique_codes':len(bycode),'products_previously_no_assertion_newly_supported':previous_missing,'still_no_any_assertion':old.execute('select count(*) from products where native_id not in (select distinct native_id from raw_components)').fetchone()[0]-previous_missing,'all_products_still_UNKNOWN_PENDING':old.execute('select count(*) from products').fetchone()[0],'products_linked_to_codes_with_more_than_two_original_rows':multiconstituent,'exact_code_match_evidence_rows':c.execute('select count(*) from code_match_evidence').fetchone()[0],'integrity':integrity,'foreign_keys':fk,'source_id':sid,'source_url':download['source_url'],'source_sha256':download['sha256'],'original_v1_sqlite_sha256':sha(OLD),'sqlite_bytes':db.stat().st_size,'sqlite_sha256':None,'clinical_rules':0,'rights_status':'PENDING','clinical_review':'PENDING','runtime_accepted':False,'rebuild_command':'python3 '+str(pathlib.Path(__file__).resolve()),'scope':'Official bulk exists without ServiceKey, no API bypass. Historical raw constituent statements, exact official code mapping only. No completeness/active/current claims.'};c.close();old.close();report['sqlite_sha256']=sha(db);(D/'SUPPLEMENT_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();run(a.source,a.output)
