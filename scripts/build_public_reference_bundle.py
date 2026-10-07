#!/usr/bin/env python3
"""Build a lossless official reference candidate bundle; never a clinical runtime release."""
import argparse, datetime as dt, hashlib, json, os, sqlite3, tarfile
from pathlib import Path
from audit_source_duplicates import audit

LABELS = {'TW': 'TW_UNREVIEWED_candidate.sqlite3', 'CA-EMA': 'INTERNATIONAL_UNREVIEWED_candidate.sqlite3', 'FR': 'FR_UNREVIEWED_candidate.sqlite3', 'JP': 'JP_UNREVIEWED_candidate.sqlite3', 'KR': 'KR_UNREVIEWED_candidate.sqlite3'}
COUNTS = {'TW': 5, 'CA-EMA': 3, 'FR': 3, 'JP': 5, 'KR': 1}
DISCLAIMER = '本 App 僅提供參考，建議用戶諮詢藥師與醫師，不作醫療決策。'

def scheduled_due(interval, date):
    if interval not in (1, 2): raise ValueError('Interval must be 1 or 2 months')
    return (date.year * 12 + date.month - (2026 * 12 + 10)) % interval == 0

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def build(inputs, output, previous=None):
    if set(inputs) != set(LABELS): raise ValueError('Require exactly TW, CA-EMA, FR, JP, KR; AU and US are excluded')
    if output.exists(): raise ValueError('Refuse overwriting candidate bundle')
    output.mkdir(parents=True)
    sources=[]; files=[]; attrs=[]; databases=[]
    for label, name in LABELS.items():
        folder=inputs[label]; database=folder/name; databases.append(database)
        with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as c:
            rows=c.execute('select source_snapshot_id,metadata_json from candidate_sources order by source_snapshot_id').fetchall()
            if len(rows)!=COUNTS[label]: raise ValueError('Unexpected source count: '+label)
            for sid, text in rows:
                meta=json.loads(text)
                if meta.get('jurisdiction') not in ('TW','CA','FR','JP','KR',None): raise ValueError('Unapproved jurisdiction')
                if meta.get('jurisdiction') is None and not sid.startswith('ema-'): raise ValueError('Unexpected regional source')
                if 'DECLARED' not in meta.get('rights_status',''): raise ValueError('No declared open reuse evidence')
                if meta.get('runtime_active') is not False or meta.get('release_eligible') is not False: raise ValueError('Candidate gate changed')
                sources.append({'archive_group':label, **meta})
        attrs.append((folder/'ATTRIBUTION.txt').read_text())
        for f in sorted(folder.rglob('*')):
            if f.is_symlink(): raise ValueError('Refuse symlinks')
            if f.is_file(): files.append({'path':'sources/'+label+'/'+f.relative_to(folder).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)})
    result=audit(databases, output/'duplicate-audit')
    if result['skipped'] or len(result['sources'])!=17 or not all(x['original_source_checksum_verified'] for x in result['sources']): raise ValueError('Incomplete full-row audit')
    def fingerprints(items): return {x['source_snapshot_id'].split('-sha256-')[0]:x.get('csv_sha256') or x['raw_sha256'] for x in items}
    current=fingerprints(sources); old=fingerprints(json.loads(previous.read_text())['sources']) if previous else None
    changes={'baseline_available':old is not None,'added_source_keys':sorted(set(current)-set(old or {})),'removed_source_keys':sorted(set(old or {})-set(current)),'changed_source_keys':sorted(k for k in current if old is not None and k in old and current[k]!=old[k]),'unchanged_source_keys':sorted(k for k in current if old is not None and current[k]==old[k]),'note':'Content checksums, not inferred clinical changes. Date-labelled Japanese files may appear as added/removed keys.'}
    manifest={'format':'safemed-public-reference-candidate-bundle-v1','source_collection_mode':os.environ.get('SOURCE_COLLECTION_MODE','PROVIDED_LOCAL_ARCHIVES'),'built_at':dt.datetime.now(dt.timezone.utc).isoformat(),'git_sha':os.environ.get('GITHUB_SHA'),'actions_run_id':os.environ.get('GITHUB_RUN_ID'),'included_markets':['TW','CA','FR','JP','KR'],'regional_scope':['EMA centralised procedures only; not all EU medicines'],'source_count':17,'retained_source_rows':result['total_input_rows'],'audited_nonheader_rows':result['total_audited_record_rows'],'sources':sources,'source_files':files,'changes':changes,'excluded':{'AU':'PBS commercial scope awaits written clarification; TGA restrictions unresolved','US':'Legacy US/raw label rights and review unresolved; no US data in this new bundle'},'runtime_active':False,'runtime_active_rules':0,'verified_complete_products':0,'release_eligible':False,'signed':False,'clinical_review':'PENDING','disclaimer':DISCLAIMER,'limitations':['Full rows from these 17 source exports only, not complete global medicine or interaction coverage','Independent source SQLite databases; this is not the 29-table App runtime schema','No name-based cross-market merges, deduplication deletions, salt equivalence or inferred clinical rules','Source licences permit declared reuse subject to conditions; formal rights/content review is still pending','Retrieval time is not publisher update date; original publisher date evidence is retained']}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (output/'APP_SOURCE_CATALOG.json').write_text(json.dumps({'disclaimer':DISCLAIMER,'runtime_active':False,'sources':sources,'excluded':manifest['excluded']},ensure_ascii=False,indent=2)+'\n')
    (output/'ATTRIBUTION.txt').write_text('\n'.join(attrs)+'\n'+DISCLAIMER+'\n')
    (output/'README.txt').write_text('SafeMed official public reference candidate bundle.\nCandidate only; unsigned, not an App runtime package or formal Release.\nOriginal source bytes, all source rows and per-source SQLite archives are retained in sources/.\nApp-readable source catalogue, licence URLs and retrieval dates: APP_SOURCE_CATALOG.json.\nFull-row checksum and duplicate checks: duplicate-audit/. No rows merged or removed.\nAU and US are excluded. '+DISCLAIMER+'\n')
    archive=output/'PUBLIC-REFERENCE-UNREVIEWED.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=6) as t:
        for label in LABELS: t.add(inputs[label],arcname='sources/'+label,recursive=True)
        for name in ['manifest.json','APP_SOURCE_CATALOG.json','ATTRIBUTION.txt','README.txt','duplicate-audit']: t.add(output/name,arcname=name,recursive=True)
    (output/'archive-sha256.json').write_text(json.dumps({'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive)},indent=2)+'\n')
    print(json.dumps({'source_count':17,'retained_source_rows':manifest['retained_source_rows'],'archive_bytes':archive.stat().st_size,'release_eligible':False}),flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-root',type=Path);p.add_argument('--output-dir',type=Path);p.add_argument('--previous',type=Path);p.add_argument('--check-schedule',action='store_true');p.add_argument('--interval',type=int,default=1);a=p.parse_args()
    if a.check_schedule: print('true' if scheduled_due(a.interval,dt.datetime.now(dt.timezone.utc).date()) else 'false')
    else:
        if not a.input_root or not a.output_dir:p.error('input-root and output-dir required')
        build({k:a.input_root/k for k in LABELS},a.output_dir,a.previous)
