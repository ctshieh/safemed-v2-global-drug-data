"""Regression tests for irreversible month-retention decisions and source gates."""
import copy, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from monthly_release import eligible, plan, legacy_artifact_plan, completed_month, check_workflow_alignment, MARKER, PREFIX
from collect_additional_markets import sha, kr_dictionary
from build_jp_native import cells

def release(month, **overrides):
    value={'tag_name':PREFIX+month,'draft':False,'prerelease':True,'body':MARKER+'\nCandidate only',
        'assets':[{'name':n,'state':'uploaded'} for n in ['MONTHLY_SUCCESS.json','snapshot.sqlite3.gz','ledger-checkpoint.sqlite3.gz']]}
    value.update(overrides); return value

class Retention(unittest.TestCase):
    def test_release_preflight_requires_same_workflow_bytes(self):
        one=[{'path':'.github/workflows/monthly.yml','type':'file','sha':'a'}]
        two=[{'path':'.github/workflows/monthly.yml','type':'file','sha':'b'}]
        with patch('monthly_release.api',side_effect=[one,one]):
            self.assertEqual(check_workflow_alignment('owner/repo','commit')['status'],'PASS_WORKFLOW_ALIGNMENT')
        with patch('monthly_release.api',side_effect=[one,two]):
            with self.assertRaisesRegex(ValueError,'Re-run latest main'):check_workflow_alignment('owner/repo','old')
    def test_cadence_only_skips_a_complete_candidate_in_same_month(self):
        rows=[release('2026-10'),release('2026-11',draft=True)]
        self.assertTrue(completed_month(rows,'2026-10'))
        self.assertFalse(completed_month(rows,'2026-11'))
        self.assertFalse(completed_month(rows,'2026-12'))
        self.assertFalse(completed_month([{'tag_name':'PUBLIC-REFERENCE-MANIFEST'}],'2026-10'))
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
    def test_legacy_payload_cleanup_respects_two_month_cutoff(self):
        def artifact(n,date):return {'name':n,'created_at':date,'expired':False}
        old=artifact('LOGICAL-RUNTIME-CANDIDATE','2026-10-18T01:17:00Z')
        nov=artifact('LOGICAL-RUNTIME-CANDIDATE','2026-11-18T01:17:00Z')
        evidence=artifact('BUILD-EVIDENCE-100-1','2026-09-18T01:17:00Z')
        failed=artifact('FAILED-LOGICAL-CANDIDATE-100-1','2026-09-18T01:17:00Z')
        unrelated=artifact('OTHER-PROJECT','2026-09-18T01:17:00Z')
        self.assertEqual(legacy_artifact_plan([old,nov,evidence,failed,unrelated],'2026-11'),[old])
    def test_legacy_artifact_month_uses_taipei_boundary(self):
        a={'name':'PUBLIC-REFERENCE-UNREVIEWED-100-1','created_at':'2026-10-31T16:00:00Z','expired':False}
        self.assertEqual(legacy_artifact_plan([a],'2026-11'),[])

class Sources(unittest.TestCase):
    def test_dictionary_portal_update_is_not_inferred_data_edition(self):
        page="출처표시 (제 1유형) fn_fileDataDown('15067461', 'detail', 'attach','1', 'history')".encode()
        response={'status':True,'atchFileId':'FILE_123','fileDetailSn':'1',
            'fileDataRegistVO':{'orginlFileNm':'dictionary 2025.10.csv'},
            'dataSetFileDetailInfo':{'updtDt':'2026-01-20'}}
        raw='일반명코드,일반명,함량,단위,제형,투여\n123,ORIGINAL,1,mg,FORM,ROUTE\n'.encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch('collect_additional_markets.download',side_effect=[page,json.dumps(response).encode()]),patch('collect_additional_markets.retrieve',return_value=(raw,{'sha256':'a'*64,'retrieved_at':'2026-10-23T00:00:00+00:00'})):
                kr_dictionary(root)
            receipt=json.loads((root/'DICTIONARY_DOWNLOAD.json').read_text())
            self.assertIsNone(receipt['publisher_date'])
            self.assertEqual(receipt['portal_updated_at'],'2026-01-20')
            self.assertEqual(receipt['original_file_name'],'dictionary 2025.10.csv')
            self.assertEqual(receipt['rows'],1)
    def test_jp_original_cell_duplicate_address_rejected(self):
        with self.assertRaises(ValueError):cells({'cells':[{'attributes':{'r':'A1'},'value':'one'},{'attributes':{'r':'A2'},'value':'two'}]})
    def test_whole_download_hash_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'original';p.write_bytes(b'original');first=sha(p)
            p.write_bytes(b'changed');self.assertNotEqual(first,sha(p))

if __name__=='__main__':unittest.main()
