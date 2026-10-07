#!/usr/bin/env python3
"""France BDPM full original tab-file intake; no guessed semantic mapping or activated rules."""
import argparse,datetime as dt,hashlib,json,shutil,sqlite3,tempfile
from pathlib import Path
from ingest_tfda_open_data import download
BASE='https://base-donnees-publique.medicaments.gouv.fr'
FILES=['CIS_bdpm.txt','CIS_COMPO_bdpm.txt','CIS_CIP_bdpm.txt']
def parse(raw):
    try:text=raw.decode('utf-8-sig');encoding='utf-8-sig'
    except UnicodeDecodeError:text=raw.decode('cp1252');encoding='cp1252'
    rows=[line.split('\t') for line in text.splitlines()]
    if not rows or any(len(row)<2 or not row[0].isdigit() for row in rows):raise ValueError('Expected BDPM tab rows with native CIS reference')
    return rows,encoding

def build(output,input_dir=None):
    if output.exists():raise ValueError('Refuse overwriting immutable source archive')
    output.parent.mkdir(parents=True,exist_ok=True);reports=[]
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        root=Path(td)/'intake';root.mkdir()
        page=download(BASE+'/telechargement') if not input_dir else b'TEST ONLY offline intake'
        (root/'download-page-evidence.html').write_bytes(page)
        with sqlite3.connect(root/'FR_UNREVIEWED_candidate.sqlite3') as c:
            c.executescript('CREATE TABLE candidate_sources(source_snapshot_id TEXT PRIMARY KEY,metadata_json TEXT);CREATE TABLE candidate_rows(source_snapshot_id TEXT,source_order INTEGER,native_cis_reference TEXT,source_locator TEXT,raw_columns_json TEXT,PRIMARY KEY(source_snapshot_id,source_order));')
            for name in FILES:
                url=BASE+'/download/file/'+name
                raw=(input_dir/name).read_bytes() if input_dir else download(url)
                rows,encoding=parse(raw);digest=hashlib.sha256(raw).hexdigest();sid='fr-bdpm-'+name+'-sha256-'+digest
                folder=root/sid;folder.mkdir();(folder/name).write_bytes(raw)
                for n,row in enumerate(rows,1):
                    c.execute('INSERT INTO candidate_rows VALUES (?,?,?,?,?)',(sid,n,row[0],f'record:{sid}/cis/{row[0]}/row/{n}',json.dumps(row,ensure_ascii=False)))
                report={'source_snapshot_id':sid,'source_name':name,'publisher':'ANSM / France Base de données publique des médicaments','jurisdiction':'FR','source_url':url,'source_page':BASE+'/telechargement','license_url':BASE+'/docs/telechargement/licence_bdpm.pdf','license':'Licence Ouverte / Open Licence','rights_status':'OPEN_LICENSE_DECLARED_FORMAL_REVIEW_PENDING','raw_sha256':digest,'version_label':'content-sha256:'+digest,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'encoding':encoding,'row_count':len(rows),'date_evidence':'Per-file official update dates preserved verbatim in download-page-evidence.html; retrieval time is not publication date','clinical_review':'PENDING','composition_status':'UNKNOWN','mapping_status':'UNMAPPED','runtime_active':False,'release_eligible':False,'scope':'All rows in the named official BDPM download; not all historical French drugs or a DDI database','changes':'Original bytes and positional tab fields retained; no inferred ACTIVE role, canonical IDs, completeness or medical rules'}
                reports.append(report);c.execute('INSERT INTO candidate_sources VALUES (?,?)',(sid,json.dumps(report,ensure_ascii=False)))
                (folder/'source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'source':name,'rows':len(rows),'sha256':digest}),flush=True)
            if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity')
        result={'sources':reports,'retained_source_rows':sum(x['row_count'] for x in reports),'runtime_active_rules':0,'release_eligible':False}
        (root/'intake-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (root/'ATTRIBUTION.txt').write_text('Source: Base de données publique des médicaments (ANSM/HAS/UNCAM), '+BASE+'. Official per-file update dates are preserved in download-page-evidence.html. Original data preserved and indexed; no official endorsement. Licence Ouverte: '+BASE+'/docs/telechargement/licence_bdpm.pdf\n本 App 僅提供參考並建議諮詢藥師或醫師，不作醫療決策。\n')
        shutil.move(str(root),output)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--input-dir',type=Path)
    a=p.parse_args();build(a.output_dir,a.input_dir)
