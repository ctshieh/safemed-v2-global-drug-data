#!/usr/bin/env python3
"""Independently unpack and verify reference bytes; explicitly reject runtime suitability."""
import argparse, collections, hashlib, json, sqlite3, tarfile, tempfile
from pathlib import Path, PurePosixPath
from audit_source_duplicates import audit
from build_public_reference_bundle import LABELS, COUNTS, sha

def verify(root):
    checksum=json.loads((root/'archive-sha256.json').read_text())
    archive=root/'PUBLIC-REFERENCE-UNREVIEWED.tar.gz'
    if checksum['file']!=archive.name or checksum['bytes']!=archive.stat().st_size or checksum['sha256']!=sha(archive):
        raise ValueError('Archive checksum/size mismatch')
    with tempfile.TemporaryDirectory() as td:
        base=Path(td)
        with tarfile.open(archive,'r:gz') as t:
            names=set()
            for m in t.getmembers():
                path=PurePosixPath(m.name)
                if path.is_absolute() or '..' in path.parts or m.name in names or not (m.isfile() or m.isdir()):
                    raise ValueError('Unsafe or duplicate archive member')
                names.add(m.name)
            t.extractall(base,filter='data')
        manifest=json.loads((base/'manifest.json').read_text())
        if manifest['source_count']!=17 or manifest['runtime_active'] is not False or manifest['release_eligible'] is not False:
            raise ValueError('Reference-only gates changed')
        expected={x['path']:x for x in manifest['source_files']}
        actual={p.relative_to(base).as_posix():p for p in (base/'sources').rglob('*') if p.is_file()}
        if set(expected)!=set(actual):raise ValueError('Missing or undeclared source file')
        for name,p in actual.items():
            if p.stat().st_size!=expected[name]['bytes'] or sha(p)!=expected[name]['sha256']:
                raise ValueError('Source file checksum mismatch: '+name)
        paths=[];countries=collections.Counter();source_ids=set()
        for group,name in LABELS.items():
            db=base/'sources'/group/name;paths.append(db)
            with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as c:
                if c.execute('pragma integrity_check').fetchone()[0]!='ok' or c.execute('pragma foreign_key_check').fetchall():
                    raise ValueError('SQLite integrity/foreign key failure')
                sources=c.execute('select source_snapshot_id,metadata_json from candidate_sources').fetchall()
                if len(sources)!=COUNTS[group]:raise ValueError('Missing source')
                for sid,text in sources:
                    meta=json.loads(text)
                    if sid in source_ids or meta['row_count']<=0 or meta.get('runtime_active') is not False or meta.get('release_eligible') is not False:
                        raise ValueError('Duplicate/empty/activated source')
                    declared=next(x for x in manifest['sources'] if x['source_snapshot_id']==sid)
                    if {k:v for k,v in declared.items() if k!='archive_group'}!=meta:raise ValueError('Source metadata mismatch')
                    source_ids.add(sid);countries[meta.get('jurisdiction') or 'EMA_REGION']+=meta['row_count']
        if source_ids!={x['source_snapshot_id'] for x in manifest['sources']}:raise ValueError('Manifest provenance mismatch')
        report=audit(paths,base/'independent-audit')
        if report['skipped'] or report['total_input_rows']!=manifest['retained_source_rows'] or not all(x['original_source_checksum_verified'] for x in report['sources']):
            raise ValueError('Original source/row audit failed')
        result={'status':'PASS','archive_sha256':checksum['sha256'],'source_count':len(source_ids),'source_rows_by_jurisdiction':dict(countries),'retained_source_rows':report['total_input_rows'],'runtime_consumer_compatible':False,'runtime_rejection_reason':'Reference databases are not contract 1.0.0 COMPOSED_SNAPSHOT; no rights approvals or reviewed mappings fabricated','test_fixture_policy':'Only 17 declared official snapshots accepted; fixture databases rejected by source identity/count/checksum audit','clinical_rules_active':0}
    (root/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle-dir',required=True,type=Path)
    print(json.dumps(verify(p.parse_args().bundle_dir),ensure_ascii=False,indent=2))
