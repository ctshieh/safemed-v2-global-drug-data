"""Fresh public US/PBS retrieval and source-native JP/KR/AU transforms.

No user account, private API key, App build, signature or clinical approval.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from ingest_tfda_open_data import download
from fetch_fda_official import fetch
from build_us_ndc_intermediate import run as build_us
from build_jp_native import build as build_jp
from build_kr_native import build as build_kr
from build_kr_supplement import run as build_supplement
from build_au_native import main as build_au

SCRIPTS = Path(__file__).resolve().parent
POSTMAN = 'https://www.postman.com/_api/collection/33098837-829fc4a1-741d-4807-b524-a492afe522bb'
PBS = 'https://data-api.health.gov.au/pbs/api/v3/'

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def retrieve(url, path):
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    body = download(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(body)
    receipt = {'source_url': url, 'retrieved_at': started, 'sha256': sha(path),
               'bytes': len(body), 'http_status': 200}
    save(path.with_suffix('.receipt.json'), receipt)
    return body, receipt

def kr_dictionary(root):
    page_url = 'https://www.data.go.kr/data/15067461/fileData.do'
    page = download(page_url)
    (root / 'source-page.html').write_bytes(page)
    html = page.decode('utf-8')
    if '출처표시 (제 1유형)' not in html:
        raise ValueError('KR dictionary reuse declaration changed')
    match = re.search(r"fn_fileDataDown\('15067461', '([^']+)', '([^']*)','([^']+)', '([^']+)'\)", html)
    if not match:
        raise ValueError('No current public dictionary download button')
    detail, atch, sn, _ = match.groups()
    q = urllib.parse.urlencode({'publicDataPk': '15067461', 'publicDataDetailPk': detail,
        'atchFileId': atch, 'fileDetailSn': sn, 'publicDataTyCode': 'PR0051'})
    raw = download('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?' + q)
    (root / 'download-response.json').write_bytes(raw)
    obj = json.loads(raw)
    if obj.get('status') is not True or not re.fullmatch(r'FILE_[0-9]+', obj.get('atchFileId', '')):
        raise ValueError('Official KR dictionary unavailable')
    url = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?' + urllib.parse.urlencode({
        'atchFileId': obj['atchFileId'], 'fileDetailSn': obj['fileDetailSn'], 'insertDataPrcus': 'N'})
    raw, receipt = retrieve(url, root / 'HIRA_ingredient_dictionary.csv')
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            rows = list(csv.DictReader(io.StringIO(raw.decode(encoding), newline='')))
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('Unknown dictionary encoding')
    required = {'일반명코드', '일반명', '함량', '단위', '제형', '투여'}
    if not rows or not required <= rows[0].keys():
        raise ValueError('Dictionary schema changed')
    receipt.update(source_page=page_url, encoding=encoding, rows=len(rows),
        portal_updated_at=obj['dataSetFileDetailInfo'].get('updtDt'),
        original_file_name=obj.get('fileDataRegistVO',{}).get('orginlFileNm'),
        publisher_date=None, rights_status='PENDING', clinical_review='PENDING')
    save(root / 'DICTIONARY_DOWNLOAD.json', receipt)

def pbs(root):
    root.mkdir(parents=True)
    # The collection is explicitly published by HPP and anonymously readable.
    # Never persist or print its shared header value, or use a private user key.
    req = urllib.request.Request(POSTMAN, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as response:
        collection = json.loads(response.read(8 * 1024 * 1024))
    keys = set()
    def scan(obj):
        if isinstance(obj, dict):
            if obj.get('key') == 'subscription-key':
                value = obj.get('value')
                if isinstance(value, str) and value and not value.startswith('{{'):
                    keys.add(value)
            for value in obj.values(): scan(value)
        elif isinstance(obj, list):
            for value in obj: scan(value)
    scan(collection)
    if len(keys) != 1:
        raise ValueError('Official public PBS header absent or ambiguous; no private-key fallback')
    key = next(iter(keys))
    save(root / 'PUBLIC_HEADER_SOURCE.json', {'url': POSTMAN,
        'public_header_fingerprint': hashlib.sha256(key.encode()).hexdigest(),
        'user_credentials_used': False, 'value_stored': False})
    with tempfile.TemporaryDirectory(prefix='pbs-public-header-') as temp:
        keyfile = Path(temp) / 'public-header'
        keyfile.write_text(key)
        keyfile.chmod(0o600)
        def get(endpoint, query):
            subprocess.run([sys.executable, str(SCRIPTS / 'fetch_pbs_response.py'),
                '--url', PBS + endpoint + '?' + urllib.parse.urlencode(query),
                '--out', str(root / endpoint), '--public-key-file', str(keyfile)], check=True)
            body = json.loads((root / endpoint / 'response.json').read_bytes())
            meta = body['_meta']
            if not (meta['count'] == meta['total_records'] == len(body['data']) and meta['page'] == 1):
                raise ValueError('Incomplete/paginated PBS response; never publish a partial package')
            return body['data']
        schedules = get('schedules', {'limit': 100})
        now = dt.datetime.now(dt.timezone.utc).date().isoformat()
        valid = [s for s in schedules if s['publication_status'] == 'PUBLISHED' and s['effective_date'] <= now]
        if not valid: raise ValueError('No effective published PBS schedule')
        latest = max(valid, key=lambda s: (s['effective_date'], s['revision_number']))
        save(root / 'SELECTED_SCHEDULE.json', latest)
        for endpoint in ('items', 'amt-items', 'organisations'):
            time.sleep(21)  # Published shared-key limit: one call per 20 seconds.
            get(endpoint, {'schedule_code': latest['schedule_code'], 'limit': 100000})
    build_au(root)

def main(inputs, intermediate):
    if intermediate.exists(): raise ValueError('Refuse overwrite')
    intermediate.mkdir(parents=True)
    us = inputs / 'US'; us.mkdir()
    fetch('https://api.fda.gov/download.json', us / 'download.json', 8 * 1024 * 1024)
    catalogue = json.loads((us / 'download.json').read_bytes())
    ndc = catalogue['results']['drug']['ndc']
    save(us / 'NDC_PARTITIONS.json', {'catalogue_meta': catalogue['meta'], 'ndc': ndc})
    if not ndc['partitions'] or sum(p['records'] for p in ndc['partitions']) != ndc['total_records']:
        raise ValueError('Invalid FDA catalogue')
    for part in ndc['partitions']:
        fetch(part['file'], us / 'raw' / Path(urllib.parse.urlparse(part['file']).path).name, 512 * 1024 * 1024)
    # Keep the known catalogue/bulk discrepancy explicit in the candidate report;
    # no source completeness, clinical or runtime acceptance is asserted.
    build_us(us, intermediate / 'US', retain_unreconciled=True)
    build_jp(inputs / 'JP', intermediate / 'JP')
    kr = intermediate / 'KR'; (kr / 'raw').mkdir(parents=True)
    retrieve('https://www.khidi.or.kr/fileDownload?fileDownType=C&fileId=1&paramMenuId=MENU01869&titleId=523332',
        kr / 'raw' / 'khidi-reimbursement-xlsx.bin')
    build_kr(inputs / 'KR', kr)
    sup = intermediate / 'KR-supplement'; (sup / 'downloads').mkdir(parents=True)
    kr_dictionary(sup / 'downloads')
    build_supplement(kr / 'KR_SOURCE_NATIVE.sqlite3', sup)
    pbs(inputs / 'AU')
    entries = []
    for market, path, ns, lang in [
        ('US', intermediate/'US/US_NDC_source_native.sqlite3', 'FDA_PRODUCT_NDC', 'en'),
        ('JP', intermediate/'JP/JP_NATIVE_INTERMEDIATE.sqlite3', 'JP_MHLW_NHI_PRICE_LIST_CODE', 'ja'),
        ('KR', kr/'KR_SOURCE_NATIVE.sqlite3', 'MFDS_ITEM_CODE', 'ko'),
        ('AU', inputs/'AU/AU_PBS_SOURCE_NATIVE.sqlite3', 'PBS_SOURCE_PRODUCT_REFERENCE', 'en')]:
        entry = {'market': market, 'path': str(path.resolve()), 'sha256': sha(path), 'namespace': ns, 'language': lang}
        if market == 'KR':
            sp = sup / 'SUPPLEMENT.sqlite3'
            entry['supplement'] = {'path': str(sp.resolve()), 'sha256': sha(sp)}
        entries.append(entry)
    save(intermediate / 'GLOBAL_INPUTS.json', {'countries': entries,
        'source_scope': 'Seven-market acquired source-native references; UNKNOWN/PENDING. Not worldwide completeness or clinical approval.'})

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--intermediate', type=Path, required=True); a = p.parse_args()
    main(a.inputs, a.intermediate)
