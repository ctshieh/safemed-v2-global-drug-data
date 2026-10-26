"""Fail-closed provenance checks, using synthetic data only."""
import copy
import unittest
from signed_monthly_release import allowed_asset, validate_remote


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


if __name__ == '__main__': unittest.main()
