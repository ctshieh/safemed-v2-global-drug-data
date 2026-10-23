"""Regression tests for irreversible month-retention decisions and source gates."""
import copy, json, tempfile, unittest
from pathlib import Path
from monthly_release import eligible, plan, MARKER, PREFIX
from collect_additional_markets import sha
from build_jp_native import cells

def release(month, **overrides):
    value={'tag_name':PREFIX+month,'draft':False,'prerelease':True,'body':MARKER+'\nCandidate only',
        'assets':[{'name':n,'state':'uploaded'} for n in ['MONTHLY_SUCCESS.json','snapshot.sqlite3.gz','ledger-checkpoint.sqlite3.gz']]}
    value.update(overrides); return value

class Retention(unittest.TestCase):
    def test_november_keeps_october_november(self):
        rows=[release(m) for m in ['2026-08','2026-09','2026-10','2026-11']]
        result=plan(rows,PREFIX+'2026-11',True)
        self.assertEqual(result['keep'],[PREFIX+'2026-11',PREFIX+'2026-10'])
        self.assertEqual(set(result['delete']),{PREFIX+'2026-08',PREFIX+'2026-09'})
    def test_december_deletes_october(self):
        rows=[release(m) for m in ['2026-10','2026-11','2026-12']]
        self.assertEqual(plan(rows,PREFIX+'2026-12',True)['delete'],[PREFIX+'2026-10'])
    def test_failure_never_deletes(self):
        rows=[release(m) for m in ['2026-08','2026-09','2026-10']]
        self.assertEqual(plan(rows,PREFIX+'2026-11',False)['delete'],[])
    def test_first_and_second_month_never_delete(self):
        for months in [['2026-10'],['2026-10','2026-11']]:
            self.assertEqual(plan([release(m) for m in months],PREFIX+months[-1],True)['delete'],[])
    def test_unmanaged_release_untouched(self):
        rows=[release('2026-09',body='another project'),release('2026-08',prerelease=False),
              release('2026-10'),release('2026-11'),release('2026-07',tag_name='v1.0.0')]
        self.assertEqual(plan(rows,PREFIX+'2026-11',True)['delete'],[])
    def test_incomplete_upload_or_draft_never_success(self):
        value=release('2026-11'); value['assets'].pop()
        self.assertFalse(eligible(value)); self.assertFalse(eligible(release('2026-11',draft=True)))
        with self.assertRaises(ValueError):plan([release('2026-09'),release('2026-10'),value],PREFIX+'2026-11',True)
    def test_year_rollover(self):
        rows=[release(m) for m in ['2026-11','2026-12','2027-01']]
        self.assertEqual(plan(rows,PREFIX+'2027-01',True)['delete'],[PREFIX+'2026-11'])
    def test_stale_run_refuses_cleanup(self):
        rows=[release(m) for m in ['2026-09','2026-10','2026-11']]
        with self.assertRaises(ValueError):plan(rows,PREFIX+'2026-09',True)
    def test_retry_keeps_previous_month_and_only_newest_same_month(self):
        old=release('2026-11',tag_name=PREFIX+'2026-11-run-100-1')
        new=release('2026-11',tag_name=PREFIX+'2026-11-run-101-1')
        rows=[release('2026-10'),old,new]
        result=plan(rows,new['tag_name'],True)
        self.assertEqual(result['keep'],[new['tag_name'],PREFIX+'2026-10'])
        self.assertEqual(result['delete'],[old['tag_name']])
    def test_retry_failed_leaves_both_working_months(self):
        rows=[release('2026-10'),release('2026-11',tag_name=PREFIX+'2026-11-run-100-1')]
        self.assertEqual(plan(rows,PREFIX+'2026-11-run-101-1',False)['delete'],[])
    def test_invalid_month_not_managed(self):
        self.assertFalse(eligible(release('2026-13')))
        self.assertFalse(eligible(release('2026-10-extra')))

class Sources(unittest.TestCase):
    def test_jp_original_cell_duplicate_address_rejected(self):
        with self.assertRaises(ValueError):cells({'cells':[{'attributes':{'r':'A1'},'value':'one'},{'attributes':{'r':'A2'},'value':'two'}]})
    def test_whole_download_hash_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'original';p.write_bytes(b'original');first=sha(p)
            p.write_bytes(b'changed');self.assertNotEqual(first,sha(p))

if __name__=='__main__':unittest.main()
