"""Fail-closed provenance checks, using synthetic data only."""
import copy
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from signed_monthly_release import allowed_asset, validate_remote, prepare


class SignedSourceGate(unittest.TestCase):
    def setUp(self):
        self.names = ['snapshot.sqlite3.gz', 'ledger-checkpoint.sqlite3.gz',
                      'BUILD_MEASUREMENTS.json', 'MONTHLY_VERIFICATION.json', 'sources.tar.gz.part-00']
        self.marker = {'assets': {n: {'bytes': 3, 'sha256': 'a'*64} for n in self.names}, 'verification': {
            'technical_build_status': 'PASS', 'seven_market_product_reconciliation': 'PASS',
            'gzip_full_roundtrip': 'PASS', 'stable_id_and_source_history': 'PASS',
            'integrity_check': 'ok', 'foreign_key_violations': 0,
            'market_product_counts': {m: 1 for m in ['TW','CA','FR','US','JP','KR','AU']}}}
        self.release = {'tag_name': 'global-drug-candidate-2026-10-run-10-1', 'draft': False,
            'prerelease': True, 'body': 'safemed-seven-market-monthly-candidate-v1\nCandidate',
            'assets': [{'name': n, 'state': 'uploaded', 'size': 3, 'digest': 'sha256:'+'a'*64}
                       for n in self.names + ['MONTHLY_SUCCESS.json']]}

    def test_complete_source(self):
        validate_remote(self.release, self.marker)

    def test_bad_remote_assets(self):
        for field, value in [('digest', 'sha256:'+'b'*64), ('size', 4), ('state', 'new')]:
            r = copy.deepcopy(self.release); r['assets'][0][field] = value
            with self.assertRaises(ValueError): validate_remote(r, self.marker)

    def test_incomplete_or_failed_source(self):
        for field, value in [('draft', True), ('prerelease', False), ('body', 'unmanaged')]:
            r = copy.deepcopy(self.release); r[field] = value
            with self.assertRaises(ValueError): validate_remote(r, self.marker)
        for field, value in [('technical_build_status', 'FAIL'), ('foreign_key_violations', 1),
                             ('market_product_counts', {'TW': 1})]:
            m = copy.deepcopy(self.marker); m['verification'][field] = value
            with self.assertRaises(ValueError): validate_remote(self.release, m)

    def test_no_secret_or_path_upload(self):
        for name in ['private.key', '.env', '../snapshot.sqlite3.gz', 'sources.tar.gz.part-00/secret',
                     'manifest-input.json', 'snapshot.sqlite3']:
            self.assertFalse(allowed_asset(name))
        r = copy.deepcopy(self.release); r['assets'].append({'name': 'private.key'})
        with self.assertRaises(ValueError): validate_remote(r, self.marker)


class ReferenceLogicIntegrity(unittest.TestCase):
    def test_only_import_and_access_adapters_differ_from_app_reference(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/'signing/Reference/DataPackageSignatureVerifier.swift').read_text()
        text=text.replace('#if canImport(CryptoKit)\nimport CryptoKit\n#else\nimport Crypto\n#endif\n','import CryptoKit\n')
        text=re.sub(r'(?m)^(\s*)public ',r'\1',text)
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),
            'f42ea61536a7c522b6a9191b0a7a3dde628ef7faab88e213951634b4b7a88152')


class FullPrepareBoundary(unittest.TestCase):
    def test_actual_gzip_sqlite_metadata_binding_and_unchanged_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp); source = top/'source'; source.mkdir()
            db = source/'snapshot.sqlite3'
            c = sqlite3.connect(db)
            c.executescript('''CREATE TABLE drug_product_identity(jurisdiction TEXT);
CREATE TABLE rules(rule_id TEXT);
CREATE TABLE product_composition(composition_status TEXT);
CREATE TABLE package_manifest(schema_version TEXT,package_major_version TEXT,product_line TEXT,
license_tier TEXT,requires_entitlement INTEGER,compatible_app_major_versions TEXT,data_version TEXT,
created_at TEXT,package_format TEXT);''')
            for n in range(25): c.execute(f'CREATE TABLE padding_{n}(id INTEGER)')
            markets = ['TW','CA','FR','US','JP','KR','AU']
            c.executemany('INSERT INTO drug_product_identity VALUES (?)', [(m,) for m in markets])
            c.execute('INSERT INTO package_manifest VALUES (?,?,?,?,?,?,?,?,?)',
                ('safemed-mobile-safety-v2.1','2','safemed_pro','professional',1,'[2]',
                 'candidate-10-1','2026-10-26T00:00:00Z','sqlite3+gzip'))
            c.commit(); c.close()
            payload = source/'snapshot.sqlite3.gz'; payload.write_bytes(gzip.compress(db.read_bytes()))
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            v = {'technical_build_status':'PASS','seven_market_product_reconciliation':'PASS',
                 'gzip_full_roundtrip':'PASS','stable_id_and_source_history':'PASS','integrity_check':'ok',
                 'foreign_key_violations':0,'market_product_counts':{m:1 for m in markets},
                 'gzip_bytes':payload.stat().st_size,'gzip_sha256':digest(payload),
                 'sqlite_bytes':db.stat().st_size,'sqlite_sha256':digest(db),
                 'clinical_review':'PENDING','source_rights':'PENDING'}
            (source/'MONTHLY_VERIFICATION.json').write_text(json.dumps(v))
            for n in ['BUILD_MEASUREMENTS.json','ledger-checkpoint.sqlite3.gz','sources.tar.gz.part-00']:
                (source/n).write_bytes(b'SYNTHETIC_TEST_ONLY')
            files = [p for p in source.iterdir() if p.name != 'snapshot.sqlite3']
            marker = {'assets': {p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in files},
                      'verification':v,'commit':'test-commit','run_id':'10','month':'2026-10'}
            (source/'MONTHLY_SUCCESS.json').write_text(json.dumps(marker))
            release = {'tag_name':'global-drug-candidate-2026-10-run-10-1','draft':False,
                'prerelease':True,'body':'safemed-seven-market-monthly-candidate-v1\nSynthetic fixture',
                'assets':[{'name':p.name,'state':'uploaded','size':p.stat().st_size,
                           'digest':'sha256:'+digest(p)} for p in source.iterdir() if allowed_asset(p.name)]}
            run = {'conclusion':'success','status':'completed','head_sha':'test-commit','run_attempt':1,
                   'path':'.github/workflows/monthly-public-reference.yml',
                   'head_repository':{'full_name':'owner/repo'},'html_url':'https://example.invalid/run/10'}
            def fake_download(repo, tag, name, root):
                shutil.copyfile(source/name, root/name); return root/name
            env = {'GITHUB_RUN_ID':'20','GITHUB_RUN_ATTEMPT':'1',
                   'SAFEMED_DATA_PACKAGE_SIGNING_KEY_ID':'TEST_ONLY',
                   'SAFEMED_DATA_PACKAGE_ED25519_PUBLIC_KEY_B64':'TEST_ONLY'}
            with patch.dict(os.environ,env), patch('signed_monthly_release.api',side_effect=[release,run]), \
                 patch('signed_monthly_release.download',side_effect=fake_download):
                root = top/'prepared'; prepare('owner/repo',release['tag_name'],root)
            result = json.loads((root/'manifest-input.json').read_text())
            self.assertEqual(result['version'],'candidate-10-1')
            self.assertEqual(result['gzip_sha256'],v['gzip_sha256'])
            self.assertEqual(result['sqlite_bytes'],v['sqlite_bytes'])
            self.assertIs(result['requires_entitlement'],True)
            self.assertIsNone(result['sha256'])
            self.assertIn('-sign-20-1/snapshot.sqlite3.gz',result['package_url'])
            receipt = json.loads((root/'PREPARED.json').read_text())
            self.assertEqual(receipt['source_rights'],'PENDING')
            self.assertFalse(receipt['formal_app_shipping_approved'])
            self.assertEqual(digest(root/'snapshot.sqlite3'),v['sqlite_sha256'])
            # Even with matching remote/marker digests, forged decompressed lengths fail closed.
            v['sqlite_bytes'] -= 1
            (source/'MONTHLY_VERIFICATION.json').write_text(json.dumps(v))
            marker['assets']['MONTHLY_VERIFICATION.json'] = {
                'sha256':digest(source/'MONTHLY_VERIFICATION.json'),
                'bytes':(source/'MONTHLY_VERIFICATION.json').stat().st_size}
            (source/'MONTHLY_SUCCESS.json').write_text(json.dumps(marker))
            for a in release['assets']:
                p = source/a['name']; a.update(size=p.stat().st_size,digest='sha256:'+digest(p))
            with patch.dict(os.environ,env), patch('signed_monthly_release.api',side_effect=[release,run]), \
                 patch('signed_monthly_release.download',side_effect=fake_download):
                with self.assertRaisesRegex(ValueError,'Decompression exceeds declared bytes'):
                    prepare('owner/repo',release['tag_name'],top/'bad-length')


if __name__ == '__main__': unittest.main()
