#!/usr/bin/env python3
"""Lossless offline legacy archive. Never an App snapshot or runtime input."""
import argparse,hashlib,json,sqlite3
from pathlib import Path
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def archive(source,output):
    if output.exists(): raise ValueError('Refuse overwriting immutable candidate')
    checksum=digest(source)
    source_id='legacy-sqlite-sha256-'+checksum
    output.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as old,sqlite3.connect(output) as dest:
        if old.execute('pragma integrity_check').fetchone()[0]!='ok': raise ValueError('Corrupt source')
        old.backup(dest)
        dest.execute('CREATE TABLE candidate_archive_metadata (source_snapshot_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, release_eligible INTEGER NOT NULL CHECK(release_eligible=0), review_status TEXT NOT NULL, limitations TEXT NOT NULL)')
        dest.execute('INSERT INTO candidate_archive_metadata VALUES (?,?,0,?,?)',(source_id,checksum,'PENDING','All legacy assertions preserved verbatim; COMPLETE and old review statuses are not contract approval; missing raw label rows cannot be reconstructed'))
        counts={t:dest.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in ['drugs','ingredients','drug_ingredients','rules','source_registry']}
    if digest(source)!=checksum: raise ValueError('Source changed during archive')
    report={'source_snapshot_id':source_id,'source_sha256':checksum,'counts':counts,'release_eligible':False,'runtime_active':False,'new_contract_approved_rows':0,'candidate_archive_sha256':digest(output)}
    output.with_suffix('.audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--source',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(archive(a.source,a.output),indent=2))
