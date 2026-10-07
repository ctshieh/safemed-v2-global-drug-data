#!/usr/bin/env python3
"""Whole official Canada/EMA JSON intake; no clinical activation or cross-market name merging."""
import argparse,datetime as dt,hashlib,json,shutil,sqlite3,tempfile
from pathlib import Path
from ingest_tfda_open_data import download
CANADA_PAGE='https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe'
CANADA_LICENSE='https://open.canada.ca/en/open-government-licence-canada/'
EMA_PAGE='https://www.ema.europa.eu/en/scientific-guidelines/download-website-data-json-data-format'
EMA_LICENSE='https://www.ema.europa.eu/en/about-us/about-website/legal-notice'
SOURCES=[
 {'key':'ca-dpd-products','url':'https://health-products.canada.ca/api/drug/drugproduct/?lang=en&type=json','publisher':'Health Canada','name':'Drug Product Database products','jurisdiction':'CA','native_id_field':'drug_code','page':CANADA_PAGE,'license_url':CANADA_LICENSE,'license':'Open Government Licence–Canada','attribution':'Source: Health Canada Drug Product Database. Contains information licensed under the Open Government Licence – Canada.','scope':'All returned DPD drugproduct records; includes non-human/historical entries; not proof of current marketed human medicines'},
 {'key':'ca-dpd-active-ingredients','url':'https://health-products.canada.ca/api/drug/activeingredient/?lang=en&type=json','publisher':'Health Canada','name':'Drug Product Database active ingredients','jurisdiction':'CA','native_id_field':'drug_code','page':CANADA_PAGE,'license_url':CANADA_LICENSE,'license':'Open Government Licence–Canada','attribution':'Source: Health Canada Drug Product Database. Contains information licensed under the Open Government Licence – Canada.','scope':'All returned activeingredient assertions; no canonical equivalence or human composition review'},
 {'key':'ema-central-medicines','url':'https://www.ema.europa.eu/en/documents/report/medicines-output-medicines_json-report_en.json','publisher':'European Medicines Agency','name':'EMA centralised procedure medicines metadata','jurisdiction':None,'native_id_field':'ema_product_number','page':EMA_PAGE,'license_url':EMA_LICENSE,'license':'EMA copyright notice: attributed commercial/non-commercial reuse; excludes third-party content','attribution':'Source: European Medicines Agency, centralised procedure medicines JSON. Metadata preserved and indexed; EMA does not endorse this application.','scope':'EU centralised procedure medicine metadata; not all Member State products; includes withdrawn/refused/veterinary entries; member-state identity unresolved'}
]
def parse(raw,source):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('Duplicate JSON field')
            result[k]=v
        return result
    data=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if source['key'].startswith('ema-'):
        if not isinstance(data,dict) or not isinstance(data.get('meta'),dict):raise ValueError('EMA metadata missing')
        records=data.get('data');meta=data['meta']
        if not isinstance(records,list) or meta.get('total_records')!=len(records):raise ValueError('EMA total does not match retained rows')
    else:
        records=data;meta={}
    if not isinstance(records,list) or not records or not all(isinstance(x,dict) for x in records):raise ValueError('Expected nonempty record array')
    if any(source['native_id_field'] not in row for row in records):raise ValueError('Missing native record identifier')
    return records,meta

def build(output,input_dir=None,retrieved_at=None):
    if output.exists():raise ValueError('Refuse overwriting immutable candidate intake')
    retrieved_at=retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat()
    if dt.datetime.fromisoformat(retrieved_at.replace('Z','+00:00')).tzinfo is None:raise ValueError('Timezone required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        root=Path(td)/'intake';root.mkdir();reports=[]
        with sqlite3.connect(root/'INTERNATIONAL_UNREVIEWED_candidate.sqlite3') as c:
            c.executescript("""
CREATE TABLE candidate_sources(source_snapshot_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL);
CREATE TABLE candidate_source_rows(source_snapshot_id TEXT,source_order INTEGER,jurisdiction TEXT,native_record_id TEXT,source_locator TEXT,raw_assertions_json TEXT,PRIMARY KEY(source_snapshot_id,source_order));
CREATE TABLE candidate_ingredient_rows(component_id TEXT PRIMARY KEY,source_snapshot_id TEXT,source_order INTEGER,native_product_reference TEXT,name_as_listed TEXT,role TEXT,mapping_status TEXT CHECK(mapping_status='UNMAPPED'),ingredient_id TEXT CHECK(ingredient_id IS NULL),raw_assertions_json TEXT);
""")
            for source in SOURCES:
                raw=(input_dir/(source['key']+'.json')).read_bytes() if input_dir else download(source['url'])
                digest=hashlib.sha256(raw).hexdigest();sid=source['key']+'-sha256-'+digest
                rows,meta=parse(raw,source);folder=root/sid;folder.mkdir()
                (folder/'original.json').write_bytes(raw)
                for order,row in enumerate(rows):
                    native=str(row[source['native_id_field']]);serialized=json.dumps(row,ensure_ascii=False,separators=(',',':'))
                    # Source record references are not the market-product identity triple.
                    c.execute('INSERT INTO candidate_source_rows VALUES (?,?,?,?,?,?)',(sid,order,source['jurisdiction'],native,f'record:{sid}/native/{native}/row/{order}',serialized))
                    if source['key']=='ca-dpd-active-ingredients':
                        c.execute('INSERT INTO candidate_ingredient_rows VALUES (?,?,?,?,?,?,?,?,?)',(f'{sid}/row/{order}',sid,order,native,row.get('ingredient_name',''),'ACTIVE','UNMAPPED',None,serialized))
                report={**source,'source_snapshot_id':sid,'raw_sha256':digest,'version_label':'content-sha256:'+digest,'retrieved_at':retrieved_at,'row_count':len(rows),'source_metadata':meta,'rights_status':'OPEN_REUSE_DECLARED_FORMAL_REVIEW_PENDING','clinical_review':'PENDING','release_eligible':False,'runtime_active':False,'linked_document_content_downloaded':False,'transformations':'JSON row indexing only; all original bytes/fields retained; no active rules or verified mappings'}
                reports.append(report)
                c.execute('INSERT INTO candidate_sources VALUES (?,?)',(sid,json.dumps(report,ensure_ascii=False)))
                (folder/'source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps({'source':source['key'],'rows':len(rows),'sha256':digest},ensure_ascii=False),flush=True)
            if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity')
            result={'format':'safemed-international-source-candidate-v1','sources':reports,'retained_source_rows':c.execute('select count(*) from candidate_source_rows').fetchone()[0],'retained_active_ingredient_rows':c.execute('select count(*) from candidate_ingredient_rows').fetchone()[0],'runtime_active_rules':0,'verified_complete_products':0,'release_eligible':False,'limitations':'Candidate database only. Not runtime schema. EMA is regional metadata, no country inferred. No medical decisions or canonical name-based merging.'}
        (root/'intake-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (root/'ATTRIBUTION.txt').write_text('\n'.join(x['attribution']+' '+x['page']+' Licence: '+x['license_url'] for x in reports)+'\n本 App 僅提供參考並建議諮詢藥師或醫師，不作醫療決策。\n')
        shutil.move(str(root),output)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--input-dir',type=Path);p.add_argument('--retrieved-at')
    a=p.parse_args();build(a.output_dir,a.input_dir,a.retrieved_at)
