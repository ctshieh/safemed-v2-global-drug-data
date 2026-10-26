import copy
import unittest
from resolve_monthly_signing_source import resolve


class AutomaticSource(unittest.TestCase):
    def setUp(self):
        self.event = {'workflow_run': {'id': 123, 'run_attempt': 2, 'conclusion': 'success',
            'status': 'completed', 'head_branch': 'main', 'head_repository': {'full_name': 'owner/repo'},
            'path': '.github/workflows/monthly-public-reference.yml'}}
        self.release = {'tag_name': 'global-drug-candidate-2026-10-run-123-2', 'draft': False,
            'prerelease': True, 'body': 'safemed-seven-market-monthly-candidate-v1\nCandidate',
            'assets': [{'name': n, 'state': 'uploaded'} for n in
                ['MONTHLY_SUCCESS.json','snapshot.sqlite3.gz','ledger-checkpoint.sqlite3.gz']]}

    def test_automatic_exact_source(self):
        self.assertEqual(resolve('owner/repo',self.event,'',[self.release]),self.release['tag_name'])

    def test_no_new_candidate_is_a_cadence_skip(self):
        self.assertIsNone(resolve('owner/repo',self.event,'',[]))
        old = copy.deepcopy(self.release); old['tag_name'] = 'global-drug-candidate-2026-10-run-122-2'
        self.assertIsNone(resolve('owner/repo',self.event,'',[old]))

    def test_failed_foreign_or_wrong_workflow_is_rejected(self):
        for field, value in [('conclusion','failure'),('head_branch','feature'),
            ('head_repository',{'full_name':'foreign/repo'}),('path','.github/workflows/other.yml'),
            ('run_attempt',True)]:
            event = copy.deepcopy(self.event); event['workflow_run'][field] = value
            with self.assertRaises(ValueError): resolve('owner/repo',event,'',[self.release])

    def test_draft_or_wrong_attempt_never_selected(self):
        for field, value in [('draft',True),('tag_name','global-drug-candidate-2026-10-run-123-1')]:
            release = copy.deepcopy(self.release); release[field] = value
            self.assertIsNone(resolve('owner/repo',self.event,'',[release]))

    def test_ambiguous_month_rejected(self):
        other = copy.deepcopy(self.release); other['tag_name'] = 'global-drug-candidate-2026-11-run-123-2'
        with self.assertRaises(ValueError): resolve('owner/repo',self.event,'',[self.release,other])

    def test_manual_requires_exact_tag(self):
        self.assertEqual(resolve('owner/repo',{},self.release['tag_name']),self.release['tag_name'])
        for tag in ['latest','global-drug-candidate-2026-10','../bad\nSOURCE_TAG=bad']:
            with self.assertRaises(ValueError): resolve('owner/repo',{},tag)


if __name__ == '__main__': unittest.main()
