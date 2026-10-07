#!/usr/bin/env python3
"""Full TFDA open CSV intake. Candidate only; preserve all assertions and original bytes."""
import argparse,csv,datetime as dt,hashlib,io,json,shutil,sqlite3,tempfile,time,zipfile
from pathlib import Path
from urllib.request import urlopen
SOURCES=[(36,9122,'全部藥品許可證資料集'),(43,9121,'藥品詳細處方成分資料集'),(39,9117,'藥品仿單或外盒資料集'),(41,9119,'藥品藥理治療分類ATC碼資料集'),(40,9118,'藥品藥理治療分類AHFS/DI碼資料集')]
LIMIT=128*1024*1024
LICENSE='https://data.gov.tw/license'
def sha(b): return hashlib.sha256(b).hexdigest()
def decode(raw):
    if raw.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            files=z.infolist()
            if len(files)!=1 or not files[0].filename.endswith('.csv') or files[0].file_size>LIMIT:
                raise ValueError('Expected one bounded CSV member')
            content=z.read(files[0])
    else: content=raw
    if len(content)>LIMIT: raise ValueError('CSV exceeds limit')
    text=content.decode('utf-8-sig')
    reader=csv.reader(io.StringIO(text,newline=''),strict=True)
    header=next(reader,None)
    if not header or len(header)!=len(set(header)) or '許可證字號' not in header:
        raise ValueError('Missing/duplicate headers or product ID')
    return content,header,reader

def store(c,key,raw,root,retrieved_at):
    export,catalog,name=key
    content,header,reader=decode(raw)
    sid=f'tfda-{export}-sha256-'+sha(content)
    folder=root/sid;folder.mkdir(exist_ok=False)
    (folder/'original-download.bin').write_bytes(raw)
    (folder/'original.csv').write_bytes(content)
    count=0;missing=0
    for number,values in enumerate(reader,1):
        if len(values)!=len(header): raise ValueError(f'{export} row {number}: field count mismatch')
        row=dict(zip(header,values));license_id=row['許可證字號']
        missing+=not bool(license_id.strip())
        c.execute('INSERT INTO candidate_source_rows VALUES (?,?,?,?,?)',(sid,number,license_id,f'record:{sid}/csv-data-row/{number}',json.dumps(row,ensure_ascii=False,separators=(',',':'))))
        if export==43:
            c.execute('INSERT INTO candidate_ingredient_rows VALUES (?,?,?,?,?,?,?,?,?,?)',(f'{sid}/row/{number}',sid,number,license_id,row.get('成分名稱',''),row.get('成分代碼',''),'UNKNOWN','UNMAPPED',None,json.dumps(row,ensure_ascii=False,separators=(',',':'))))
        count+=1
    if not count: raise ValueError('Empty dataset')
    info={'source_snapshot_id':sid,'dataset_name':name,'publisher':'衛生福利部食品藥物管理署',
        'jurisdiction':'TW','dataset_page':f'https://data.gov.tw/dataset/{catalog}',
        'source_url':f'https://data.fda.gov.tw/data/opendata/export/{export}/csv',
        'license':'政府資料開放授權條款-第1版','license_evidence_url':f'https://data.gov.tw/dataset/{catalog}',
        'license_url':LICENSE,'rights_status':'OPEN_LICENSE_DECLARED_FORMAL_REVIEW_PENDING',
        'attribution':f'資料來源：衛生福利部食品藥物管理署－{name}。依政府資料開放授權條款第1版整理，並非機關背書。',
        'retrieved_at':retrieved_at,'version_label':'content-sha256:'+sha(content),
        'csv_sha256':sha(content),'download_sha256':sha(raw),'row_count':count,
        'missing_product_identifier_rows':missing,'columns':header,
        'clinical_review':'PENDING','release_eligible':False,'runtime_active':False,
        'coverage':'ALL_ROWS_IN_THIS_OFFICIAL_EXPORT_NOT_PROOF_OF_ALL_MARKET_OR_COMPLETE_COMPOSITION',
        'changes':'ZIP decompressed and CSV indexed; all row fields preserved; no medical rules generated'}
    (folder/'source.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    c.execute('INSERT INTO candidate_sources VALUES (?,?)',(sid,json.dumps(info,ensure_ascii=False)))
    return info

def download(url):
    for attempt in range(3):
        try:
            with urlopen(url,timeout=60) as response:
                raw=response.read(LIMIT+1)
            if len(raw)>LIMIT: raise ValueError('Download exceeds limit')
            return raw
        except (OSError,TimeoutError):
            if attempt==2: raise
            time.sleep(2**attempt)

def build(output,input_dir=None,retrieved_at=None):
    if output.exists(): raise ValueError('Refuse overwriting immutable intake')
    retrieved_at=retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat()
    if dt.datetime.fromisoformat(retrieved_at.replace('Z','+00:00')).tzinfo is None:
        raise ValueError('Timezone required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        root=Path(td)/'intake';root.mkdir()
        with sqlite3.connect(root/'TW_UNREVIEWED_candidate.sqlite3') as c:
            c.executescript("""
CREATE TABLE candidate_sources(source_snapshot_id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL);
CREATE TABLE candidate_source_rows(source_snapshot_id TEXT,row_number INTEGER,local_product_id TEXT,source_locator TEXT,raw_assertions_json TEXT,PRIMARY KEY(source_snapshot_id,row_number));
CREATE TABLE candidate_ingredient_rows(component_id TEXT PRIMARY KEY,source_snapshot_id TEXT,source_order INTEGER,local_product_id TEXT,name_as_listed TEXT,local_ingredient_code TEXT,role TEXT CHECK(role='UNKNOWN'),mapping_status TEXT CHECK(mapping_status='UNMAPPED'),ingredient_id TEXT CHECK(ingredient_id IS NULL),raw_assertions_json TEXT);
""")
            sources=[]
            for key in SOURCES:
                raw=(input_dir/f'{key[0]}.bin').read_bytes() if input_dir else download(f'https://data.fda.gov.tw/data/opendata/export/{key[0]}/csv')
                info=store(c,key,raw,root,retrieved_at);sources.append(info)
                print(json.dumps({'dataset':info['dataset_name'],'rows':info['row_count'],'csv_sha256':info['csv_sha256']},ensure_ascii=False))
            assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
            report={'format':'safemed-TW-public-source-candidate-v1','sources':sources,
                'candidate_source_rows':c.execute('select count(*) from candidate_source_rows').fetchone()[0],
                'ingredient_rows_retained':c.execute('select count(*) from candidate_ingredient_rows').fetchone()[0],
                'verified_complete_products':0,'runtime_active_rules':0,'release_eligible':False,
                'limitations':'Candidate archive only, not contract 1.0.0 runtime snapshot. Roles/mappings UNKNOWN/UNMAPPED pending human review. Linked PDF/image contents not downloaded or assumed licensed by link metadata.'}
        (root/'intake-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        (root/'ATTRIBUTION.txt').write_text('\n'.join(s['attribution']+' '+s['dataset_page']+' 授權：'+LICENSE for s in sources)+'\n本 App 僅提供參考，建議諮詢藥師或醫師，不作醫療決策。\n')
        shutil.move(str(root),output)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--input-dir',type=Path);p.add_argument('--retrieved-at')
    a=p.parse_args();build(a.output_dir,a.input_dir,a.retrieved_at)
