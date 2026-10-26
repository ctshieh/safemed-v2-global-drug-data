"""Publish an independently verified signed reference download; never approve clinical use.

The App signing contract authenticates bytes and producer declarations only.
This release remains a prerelease while medical/rights/runtime acceptance is pending.
No candidate cleanup, mutable latest alias, App configuration, or activation occurs here.
"""
import argparse
import gzip
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from monthly_release import api, download, eligible, sha, check_workflow_alignment

SIGNED_PREFIX = 'signed-drug-reference-'
MARKETS = {'TW', 'CA', 'FR', 'US', 'JP', 'KR', 'AU'}


def require(value, message):
    if not value:
        raise ValueError(message)


def allowed_asset(name):
    return name in {'snapshot.sqlite3.gz', 'ledger-checkpoint.sqlite3.gz',
                   'BUILD_MEASUREMENTS.json', 'MONTHLY_VERIFICATION.json',
                   'MONTHLY_SUCCESS.json'} or bool(re.fullmatch(r'sources\.tar\.gz\.part-\d+', name))


def validate_remote(release, marker):
    require(eligible(release), 'Not a complete managed candidate release')
    assets = {a['name']: a for a in release['assets']}
    require(len(assets) == len(release['assets']), 'Duplicate assets')
    require(all(allowed_asset(n) for n in assets), 'Unexpected source asset')
    require(set(marker['assets']) == set(assets) - {'MONTHLY_SUCCESS.json'}, 'Marker asset set mismatch')
    require(any(n.startswith('sources.tar.gz.part-') for n in assets), 'Source archive absent')
    for name, declared in marker['assets'].items():
        actual = assets[name]
        require(actual['state'] == 'uploaded' and actual['size'] == declared['bytes'] and
                actual.get('digest') == 'sha256:' + declared['sha256'], 'Source asset digest mismatch: ' + name)
    v = marker['verification']
    require(v['technical_build_status'] == 'PASS' and v['seven_market_product_reconciliation'] == 'PASS' and
            v['gzip_full_roundtrip'] == 'PASS' and v['stable_id_and_source_history'] == 'PASS' and
            v['integrity_check'] == 'ok' and v['foreign_key_violations'] == 0, 'Source verification failed')
    require(set(v['market_product_counts']) == MARKETS and all(v['market_product_counts'].values()), 'Incomplete markets')


def prepare(repo, tag, root):
    match = re.fullmatch(r'global-drug-candidate-(\d{4}-\d{2})-run-(\d+)-(\d+)', tag)
    require(match is not None, 'Only an immutable managed candidate tag is accepted')
    root.mkdir(parents=True, exist_ok=False)
    release = api(f'repos/{repo}/releases/tags/{tag}')
    require(eligible(release), 'Candidate not published successfully')
    marker_path = download(repo, tag, 'MONTHLY_SUCCESS.json', root)
    marker_asset = next(a for a in release['assets'] if a['name'] == marker_path.name)
    require(marker_asset.get('digest') == 'sha256:' + sha(marker_path) and
            marker_asset['size'] == marker_path.stat().st_size, 'Marker digest mismatch')
    marker = json.loads(marker_path.read_text())
    validate_remote(release, marker)
    run = api(f'repos/{repo}/actions/runs/{match[2]}')
    require(run['conclusion'] == 'success' and run['status'] == 'completed' and
            run['head_sha'] == marker['commit'] and str(run['run_attempt']) == match[3] and
            run['path'] == '.github/workflows/monthly-public-reference.yml' and
            run['head_repository']['full_name'] == repo and marker['run_id'] == match[2] and
            marker['month'] == match[1], 'Build provenance mismatch')
    for name, info in marker['assets'].items():
        path = download(repo, tag, name, root)
        require(sha(path) == info['sha256'] and path.stat().st_size == info['bytes'], 'Downloaded source mismatch: ' + name)
    v = marker['verification']
    require(json.loads((root / 'MONTHLY_VERIFICATION.json').read_text()) == v, 'Verification report mismatch')
    db = root / 'snapshot.sqlite3'
    with gzip.open(root / 'snapshot.sqlite3.gz', 'rb') as src, db.open('xb') as dst:
        count = 0
        while chunk := src.read(1048576):
            count += len(chunk)
            require(count <= v['sqlite_bytes'], 'Decompression exceeds declared bytes')
            dst.write(chunk)
    require(db.stat().st_size == v['sqlite_bytes'] and sha(db) == v['sqlite_sha256'], 'SQLite roundtrip mismatch')
    c = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    require([r[0] for r in c.execute('PRAGMA integrity_check')] == ['ok'] and
            not c.execute('PRAGMA foreign_key_check').fetchall(), 'SQLite integrity failure')
    require(len(c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()) == 29,
            'Table count mismatch')
    require(dict(c.execute('SELECT jurisdiction,count(*) FROM drug_product_identity GROUP BY jurisdiction')) ==
            v['market_product_counts'], 'Market counts mismatch')
    require(c.execute('SELECT count(*) FROM rules').fetchone()[0] == 0 and
            c.execute("SELECT count(*) FROM product_composition WHERE composition_status='VERIFIED_COMPLETE'").fetchone()[0] == 0,
            'Unexpected clinical activation')
    rows = c.execute('SELECT * FROM package_manifest').fetchall()
    require(len(rows) == 1, 'Expected one package manifest')
    p = dict(rows[0])
    c.close()
    require(p['data_version'] == f'candidate-{match[2]}-{match[3]}', 'SQLite build version provenance mismatch')
    signed_tag = (SIGNED_PREFIX + match[1] + '-run-' + match[2] + '-' + match[3] +
                  '-sign-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
    payload = root / 'snapshot.sqlite3.gz'
    require(payload.stat().st_size == v['gzip_bytes'] and sha(payload) == v['gzip_sha256'], 'Payload mismatch')
    require(p['requires_entitlement'] in (0, 1), 'Invalid entitlement declaration')
    manifest = {
        'schema_version': p['schema_version'], 'package_major_version': int(p['package_major_version']),
        'product_line': p['product_line'], 'license_tier': p['license_tier'],
        'requires_entitlement': bool(p['requires_entitlement']),
        'compatible_app_major_versions': json.loads(p['compatible_app_major_versions']),
        'version': p['data_version'], 'created_at': p['created_at'],
        'package_url': f'https://github.com/{repo}/releases/download/{signed_tag}/snapshot.sqlite3.gz',
        'package_format': p['package_format'], 'gzip_bytes': v['gzip_bytes'], 'sqlite_bytes': v['sqlite_bytes'],
        'gzip_sha256': v['gzip_sha256'], 'sqlite_sha256': v['sqlite_sha256'], 'sha256': None,
        'signature_algorithm': 'ED25519_SAFEMED_SORTED_JSON_V1',
        'signature_key_id': os.environ['SAFEMED_DATA_PACKAGE_SIGNING_KEY_ID'], 'signature': ''}
    (root / 'manifest-input.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    receipt = {'format': 'safemed-signed-monthly-reference-v1', 'signed_tag': signed_tag,
        'source_tag': tag, 'source_run': run['html_url'], 'source_commit': marker['commit'],
        'source_run_attempt': int(match[3]), 'source_month': match[1],
        'package_version': p['data_version'], 'verification': v, 'signing_key_id': manifest['signature_key_id'],
        'public_key_base64': os.environ['SAFEMED_DATA_PACKAGE_ED25519_PUBLIC_KEY_B64'],
        'clinical_review': v['clinical_review'], 'source_rights': v['source_rights'],
        'runtime_accepted': False, 'activated': False, 'iPhone_performance_tested': False,
        'formal_app_shipping_approved': False,
        'transport_note': 'GitHub asset download redirects; existing App no-redirect policy must be resolved by App owner.',
        'source_archive_assets_preserved': True,
        'no_private_key_in_assets': True}
    (root / 'PREPARED.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': 'PASS_FULL_DOWNLOAD_AND_SQLITE_VERIFICATION', 'signed_tag': signed_tag}))


def publish(repo, root, commit, signer):
    check_workflow_alignment(repo, commit)
    receipt = json.loads((root / 'PREPARED.json').read_text())
    tag = receipt['signed_tag']
    # Reverify the signed manifest with the pinned public key; no secret is needed here.
    canonical = root / 'canonical-payload.json'
    subprocess.run([signer, 'verify', str(root / 'manifest.json'), str(canonical), receipt['public_key_base64']], check=True)
    m = json.loads((root / 'manifest.json').read_text())
    v = receipt['verification']
    require(m['gzip_sha256'] == sha(root / 'snapshot.sqlite3.gz') == v['gzip_sha256'] and
            m['gzip_bytes'] == (root / 'snapshot.sqlite3.gz').stat().st_size == v['gzip_bytes'] and
            m['sqlite_sha256'] == v['sqlite_sha256'] and m['sqlite_bytes'] == v['sqlite_bytes'] and
            m['package_url'] == f'https://github.com/{repo}/releases/download/{tag}/snapshot.sqlite3.gz', 'Manifest payload binding mismatch')
    receipt.update(signature_verified=True, manifest_sha256=sha(root / 'manifest.json'),
        canonical_payload_sha256=sha(canonical), publisher_commit=commit,
        publisher_run_id=os.environ['GITHUB_RUN_ID'], publisher_run_attempt=os.environ['GITHUB_RUN_ATTEMPT'])
    evidence = root / 'SIGNED_RELEASE.json'
    evidence.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    # Upload independent copies, including original sources, so candidate retention cannot break this download.
    files = [p for p in root.iterdir() if allowed_asset(p.name)] + [root / 'manifest.json', canonical, evidence]
    release = api(f'repos/{repo}/releases', 'POST', {'tag_name': tag, 'target_commitish': commit,
        'name': f'Signed seven-market reference {receipt["source_month"]}', 'draft': True, 'prerelease': True,
        'body': 'safemed-signed-monthly-reference-v1\nEd25519-authenticated monthly reference download. '
                'Medical and redistribution review remain PENDING/UNKNOWN; not App shipping or clinical acceptance. '
                'Independent source archives and original failed/successful build provenance are retained. '
                'No App activation, TestFlight upload, or prior release deletion.'})
    for path in sorted(files):
        subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', repo], check=True)
    remote = api(f'repos/{repo}/releases/{release["id"]}')
    by_name = {a['name']: a for a in remote['assets']}
    require(set(by_name) == {p.name for p in files}, 'Uploaded asset set mismatch')
    for path in files:
        a = by_name[path.name]
        require(a['state'] == 'uploaded' and a['size'] == path.stat().st_size and
                a.get('digest') == 'sha256:' + sha(path), 'Uploaded asset digest mismatch')
    api(f'repos/{repo}/releases/{release["id"]}', 'PATCH', {'draft': False})
    print(json.dumps({'status': 'PASS_SIGNED_REFERENCE_PUBLISHED', 'url': remote['html_url'],
        'manifest_sha256': receipt['manifest_sha256'], 'clinical_review': receipt['clinical_review'],
        'source_rights': receipt['source_rights'], 'formal_app_shipping_approved': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'publish'])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-tag')
    parser.add_argument('--commit')
    parser.add_argument('--signer')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.repo, args.source_tag, args.root)
    else:
        publish(args.repo, args.root, args.commit, args.signer)
