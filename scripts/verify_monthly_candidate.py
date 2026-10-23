"""Verify transport, all markets, immutable identity history; emit a small checkpoint."""
import argparse, gzip, hashlib, json, shutil, sqlite3
from pathlib import Path
from build_seven_market_candidate import products, stable

MARKETS = {'TW','CA','FR','US','JP','KR','AU'}

def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def verify(root, config, previous=None):
    db=root/'snapshot.sqlite3'; payload=root/'snapshot.sqlite3.gz'
    m=json.loads((root/'BUILD_MEASUREMENTS.json').read_text())
    if sha(db)!=m['sqlite_sha256'] or sha(payload)!=m['gzip_sha256']:
        raise ValueError('Payload SHA mismatch')
    h=hashlib.sha256(); size=0
    with gzip.open(payload,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b);size+=len(b)
    if size!=db.stat().st_size or h.hexdigest()!=m['sqlite_sha256']:
        raise ValueError('Full gzip roundtrip mismatch')
    c=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row
    if [r[0] for r in c.execute('PRAGMA integrity_check')]!=['ok'] or c.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Integrity/FK failure')
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    counts=dict(c.execute('SELECT jurisdiction,count(*) FROM drug_product_identity GROUP BY jurisdiction'))
    if len(tables)!=29 or set(counts)!=MARKETS or not all(counts.values()):
        raise ValueError('Incomplete seven-market package')
    for entry in json.loads(config.read_text())['countries']:
        expected={stable('drug',entry['market'],entry['namespace'],r['native_id']) for r in products(entry)}
        actual={r[0] for r in c.execute('SELECT drug_id FROM drug_product_identity WHERE jurisdiction=?',(entry['market'],))}
        if expected!=actual:raise ValueError('Product reconciliation failed '+entry['market'])
    if c.execute("SELECT count(*) FROM drugs d LEFT JOIN id_ledger l ON l.entity_kind='DRUG' AND l.stable_id=d.drug_id AND l.lifecycle='ACTIVE' WHERE l.stable_id IS NULL").fetchone()[0]:
        raise ValueError('Active product without active ledger ID')
    if c.execute('SELECT count(*) FROM rules').fetchone()[0] or c.execute("SELECT count(*) FROM product_composition WHERE composition_status='VERIFIED_COMPLETE'").fetchone()[0]:
        raise ValueError('Unreviewed candidate cannot invent clinical acceptance')
    if previous:
        old=sqlite3.connect(previous.resolve().as_uri()+'?mode=ro',uri=True);old.row_factory=sqlite3.Row
        for r in old.execute('SELECT * FROM id_ledger'):
            now=c.execute('SELECT * FROM id_ledger WHERE entity_kind=? AND stable_id=?',(r['entity_kind'],r['stable_id'])).fetchone()
            if not now or now['compact_int_id']!=r['compact_int_id'] or (r['lifecycle']=='RETIRED' and now['lifecycle']!='RETIRED'):
                raise ValueError('ID history reset/reassignment/resurrection')
        for r in old.execute('SELECT * FROM source_registry'):
            now=c.execute('SELECT * FROM source_registry WHERE source_id=?',(r['source_id'],)).fetchone()
            if not now or dict(now)!=dict(r):raise ValueError('Immutable source history changed')
        old.close()
    checkpoint=root/'ledger-checkpoint.sqlite3'
    if checkpoint.exists():raise ValueError('Refuse overwrite checkpoint')
    out=sqlite3.connect(checkpoint)
    for table in ['package_manifest','package_contract','source_registry','source_rights','id_ledger']:
        out.execute(c.execute('SELECT sql FROM sqlite_master WHERE type=\'table\' AND name=?',(table,)).fetchone()[0])
        fields=[r[1] for r in c.execute('PRAGMA table_info('+table+')')]
        out.executemany('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in fields)+')',c.execute('SELECT * FROM '+table))
    out.commit()
    if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or out.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Checkpoint failure')
    out.close(); c.close()
    with checkpoint.open('rb') as src,(root/'ledger-checkpoint.sqlite3.gz').open('xb') as dest,gzip.GzipFile(fileobj=dest,mode='wb',filename='',mtime=0) as gz:
        shutil.copyfileobj(src,gz,1048576)
    report={'technical_build_status':'PASS','seven_market_product_reconciliation':'PASS',
        'integrity_check':'ok','foreign_key_violations':0,'gzip_full_roundtrip':'PASS',
        'stable_id_and_source_history':'PASS','market_product_counts':counts,
        'sqlite_bytes':db.stat().st_size,'sqlite_sha256':m['sqlite_sha256'],
        'gzip_bytes':payload.stat().st_size,'gzip_sha256':m['gzip_sha256'],
        'ledger_checkpoint_sha256':sha(checkpoint),
        'ledger_checkpoint_gzip_sha256':sha(root/'ledger-checkpoint.sqlite3.gz'),
        'clinical_review':'PENDING','source_rights':'PENDING','runtime_accepted':False,
        'signed':False,'activated':False,'iPhone_performance_tested':False,
        'limitations':'Source-native reference candidate only. US catalogue discrepancy, KR source gaps, JP price-list and AU PBS scope remain explicit in source intake reports. No formal App manifest is produced.'}
    (root/'MONTHLY_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--previous',type=Path)
    a=p.parse_args();print(json.dumps(verify(a.root,a.config,a.previous),ensure_ascii=False))
