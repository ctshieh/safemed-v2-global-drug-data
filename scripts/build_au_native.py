"""PBS source-native projection, retaining all records and exact native concept links."""
import collections,datetime,hashlib,json,sqlite3,argparse
from pathlib import Path
ROOT=None
def js(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def textsha(s):return hashlib.sha256(s.encode()).hexdigest()
def one(values):
    s={x for x in values if x is not None and x!=''}
    return next(iter(s)) if len(s)==1 else None
def main(root):
    global ROOT
    ROOT=root
    out=ROOT/'AU_PBS_SOURCE_NATIVE.sqlite3';assert not out.exists()
    c=sqlite3.connect(out);c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA synchronous=FULL')
    c.executescript('''
      CREATE TABLE sources(source_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL,raw_path TEXT NOT NULL,raw_sha256 TEXT NOT NULL);
      CREATE TABLE raw_rows(source_id TEXT NOT NULL REFERENCES sources,record_index INTEGER NOT NULL,source_locator TEXT NOT NULL UNIQUE,row_sha256 TEXT NOT NULL,original_json TEXT NOT NULL,PRIMARY KEY(source_id,record_index));
      CREATE TABLE products_export(native_id TEXT PRIMARY KEY,display_name TEXT,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT NOT NULL,components_json TEXT NOT NULL,source_refs_json TEXT NOT NULL,original_json TEXT NOT NULL);
      CREATE TABLE item_product_map(li_item_id TEXT PRIMARY KEY,native_id TEXT NOT NULL REFERENCES products_export,source_locator TEXT NOT NULL);
    ''')
    sources={};datasets={};refs={};metas={}
    for endpoint,folder in [('schedules','schedules'),('items','items'),('amt-items','amt-items'),('organisations','organisations')]:
        p=ROOT/folder/'response.json';r=json.loads((p.parent/'RECEIPT.json').read_text());assert r['http_status']==200 and sha(p)==r['sha256'];d=json.loads(p.read_bytes());meta=d['_meta'];rows=d['data'];assert len(rows)==meta['total_records']==meta['count'];assert meta['page']==1
        assert meta['info']['messages'] and any(m['type']=='copyright' for m in meta['info']['messages'])
        sid='au-pbs-'+endpoint+'-sha256-'+r['sha256'];sources[endpoint]=sid;datasets[endpoint]=rows;metas[endpoint]=meta
        metadata={'source_id':sid,'source_url':r['request_url'],'url':r['request_url'],'publisher':'Department of Health / Pharmaceutical Benefits Scheme (PBS)','jurisdiction':'AU','retrieved_at':r['retrieved_at'],'raw_sha256':r['sha256'],'version_label':'PBS selected schedule '+str(json.loads((ROOT/'SELECTED_SCHEDULE.json').read_text())['schedule_code'])+'; response-sha256:'+r['sha256'],'license_url':'https://www.health.gov.au/using-our-websites/copyright','license':'Exact response copyright retained; user-provided HPP correspondence supports conditional commercial redistribution and machine-readable conversion; third-party and other narrow scopes separately tracked','copyright_messages':meta['info']['messages'],'rights_review':'PENDING_FORMAL_GATE_WITH_AFFIRMATIVE_CONDITIONAL_CORRESPONDENCE','source_scope':'Published PBS schedule subsidy/product reference; not all Australian medicines or TGA approval/complete composition/DDI','record_count':len(rows),'api_meta':meta}
        c.execute('INSERT INTO sources VALUES(?,?,?,?)',(sid,js(metadata),str(p.resolve()),r['sha256']))
        erefs=[]
        for idx,row in enumerate(rows):
            raw=js(row);digest=textsha(raw);loc=f'record:{sid}/data/{idx}/parsed-json-sha256/{digest}'
            c.execute('INSERT INTO raw_rows VALUES(?,?,?,?,?)',(sid,idx,loc,digest,raw));erefs.append({'source_id':sid,'locator':loc})
        refs[endpoint]=erefs
    now=datetime.datetime.now(datetime.timezone.utc).date().isoformat();published=[x for x in datasets['schedules'] if x['effective_date']<=now and x['publication_status']=='PUBLISHED'];latest=max(published,key=lambda x:(x['effective_date'],x['revision_number']));assert latest==json.loads((ROOT/'SELECTED_SCHEDULE.json').read_text())
    groups=collections.defaultdict(list);amt=collections.defaultdict(list);orgs={x['organisation_id']:i for i,x in enumerate(datasets['organisations'])}
    for i,row in enumerate(datasets['amt-items']):
        assert row['schedule_code']==latest['schedule_code'];amt[row['li_item_id']].append((i,row))
    missing_tpp=0;native_kinds=collections.Counter();item_map={}
    for i,row in enumerate(datasets['items']):
        assert row['schedule_code']==latest['schedule_code']
        tpp=[(n,x) for n,x in amt[row['li_item_id']] if x['concept_type_code']=='TPP'];codes={(x['amt_code'],x['non_amt_code']) for n,x in tpp};assert len(codes)<=1
        if tpp:
            amt_code,other=next(iter(codes));native=('AMT_TPP/'+amt_code) if amt_code else ('PBS_NON_AMT_TPP/'+str(other));assert amt_code or other
        else:native='PBS_ITEM/'+row['li_item_id'];missing_tpp+=1
        groups[native].append((i,row));item_map[row['li_item_id']]=native;native_kinds[native.split('/')[0]]+=1
    assert len(item_map)==len(datasets['items'])
    comp_count=aliases_count=conflicts=0
    for native,entries in sorted(groups.items()):
        names=set();all_refs={};comp_refs=collections.defaultdict(dict);rows=[];concepts=[];org_rows=[]
        for i,row in entries:
            rows.append(row);ref=refs['items'][i];all_refs[(ref['source_id'],ref['locator'])]=ref
            for f in ['brand_name','drug_name','li_drug_name','schedule_form','pbs_code']:
                if row.get(f) and row[f].strip():names.add(row[f])
            if row.get('drug_name') and row['drug_name'].strip():comp_refs[row['drug_name']][(ref['source_id'],ref['locator'])]=ref
            for j,x in amt[row['li_item_id']]:
                concepts.append(x);ar=refs['amt-items'][j];all_refs[(ar['source_id'],ar['locator'])]=ar
                if x['concept_type_code']=='TPP':
                    for f in ['preferred_term','pbs_preferred_term']:
                        if x.get(f) and x[f].strip():names.add(x[f])
            if row['organisation_id'] in orgs:
                j=orgs[row['organisation_id']];org_rows.append(datasets['organisations'][j]);ar=refs['organisations'][j];all_refs[(ar['source_id'],ar['locator'])]=ar
        preferred=one(x['preferred_term'] for x in concepts if x['concept_type_code']=='TPP')
        display=preferred or one(x['brand_name'] for x in rows) or ('PBS '+native)
        names.add(display)
        components=[]
        for order,(name,rr) in enumerate(sorted(comp_refs.items())):
            rlist=[v for k,v in sorted(rr.items())];components.append({'source_order':order,'name_as_listed':name,'strength_text':None,'role':'UNKNOWN','mapping_status':'UNMAPPED','source_ref':rlist[0],'source_refs':rlist,'assertion_kind':'PBS_DRUG_NAME_ORIGINAL_UNSPLIT_NOT_VERIFIED_COMPOSITION'})
        generic=one(x['drug_name'] for x in rows);form=one(x['li_form'] for x in rows);route=one(x['manner_of_administration'] for x in rows)
        conflict={f:sorted({str(x[f]) for x in rows if x.get(f) is not None}) for f in ['drug_name','brand_name','li_form','manner_of_administration'] if len({x.get(f) for x in rows if x.get(f) is not None})>1};conflicts+=bool(conflict)
        original={'identifier_namespace':'PBS_SOURCE_PRODUCT_REFERENCE','identity_kind':native.split('/')[0],'items':rows,'amt_concepts':concepts,'organisations':org_rows,'all_field_conflicts':conflict,'composition_status':'CONFLICT' if conflict else 'UNKNOWN','review_status':'PENDING','complete_ingredient_list':False,'ingredient_specific_strengths_extracted':False,'medical_text_rewritten':False,'dedupe_policy':'Merge only exact publisher TPP concept identity; all PBS item/program records and concept links retained; no same-name chemical inference','manufacturer_field':None,'manufacturer_reason':'Organisation/sponsor and manufacturer code remain source assertions; not inferred as physical manufacturing entity'}
        all_refs=[v for k,v in sorted(all_refs.items())]
        c.execute('INSERT INTO products_export VALUES(?,?,?,?,?,?,?,?,?,?)',(native,display,generic,None,form,route,js(sorted(names)),js(components),js(all_refs),js(original)));comp_count+=len(components);aliases_count+=len(names)
    for i,row in enumerate(datasets['items']):c.execute('INSERT INTO item_product_map VALUES(?,?,?)',(row['li_item_id'],item_map[row['li_item_id']],refs['items'][i]['locator']))
    c.commit();integrity=c.execute('PRAGMA integrity_check').fetchall();fk=c.execute('PRAGMA foreign_key_check').fetchall();assert integrity==[('ok',)] and not fk
    count=c.execute('SELECT COUNT(*) FROM products_export').fetchone()[0];raw_count=c.execute('SELECT COUNT(*) FROM raw_rows').fetchone()[0];c.close()
    report={'status':'SOURCE_NATIVE_ENGINEERING_COMPLETE_NOT_CLINICAL_OR_RUNTIME_ACCEPTANCE','namespace':'PBS_SOURCE_PRODUCT_REFERENCE','schedule':latest,'sqlite_path':str(out.resolve()),'sqlite_bytes':out.stat().st_size,'sqlite_sha256':sha(out),'raw_records':raw_count,'endpoint_counts':{k:len(v) for k,v in datasets.items()},'deduplicated_products':count,'item_rows_merged_into_existing_tpp_identity':len(datasets['items'])-count,'items_without_tpp_retained_as_separate_item_identity':missing_tpp,'aliases':aliases_count,'unsplit_generic_assertions':comp_count,'products_with_original_field_conflicts':conflicts,'integrity_check':integrity,'foreign_key_violations':fk,'original_body_sha256_by_endpoint':{k:s.rsplit('-sha256-',1)[1] for k,s in sources.items()},'original_row_hash_method':'SHA256 compact sorted UTF8 parsed JSON perrecord; exact complete HTTP response bytes separately preserved and hashed','original_records_removed':0,'clinical_rules':0,'verified_complete_products':0,'formal_rights_or_manifest_changed':False,'remaining':['Not all Australian medicines; PBS subsidy/product scope only','No complete independently verified composition or clinical interaction rules','Current official license/correspondence conditions retained; no blanket TGA/thirdparty grant','Global integration and iPhone acceptance pending']}
    (ROOT/'INTAKE_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root)
