import json,sqlite3,tempfile,unittest
from pathlib import Path
from audit_source_duplicates import audit,norm
class DuplicateAuditTests(unittest.TestCase):
    def test_record_duplicates_and_native_conflicts_are_separate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'source.sqlite3'
            with sqlite3.connect(p) as c:
                c.executescript('CREATE TABLE candidate_sources(source_snapshot_id TEXT,metadata_json TEXT);CREATE TABLE candidate_source_rows(source_snapshot_id TEXT,source_order INTEGER,native_record_id TEXT,source_locator TEXT,raw_assertions_json TEXT);')
                for market,rows in [('CA',[{'brand_name':'ＦＯＯ','drug_code':'0001','strength':'5'},{'drug_code':'0001','strength':'5','brand_name':'ＦＯＯ'},{'drug_code':'0001','brand_name':'ＦＯＯ','strength':'10'}]),('EMA_REGION',[{'name_of_medicine':'foo','ema_product_number':'0001'}])]:
                    sid='ca-dpd-products-sha256-test' if market=='CA' else 'ema-central-medicines-sha256-test'
                    c.execute('insert into candidate_sources values (?,?)',(sid,json.dumps({'jurisdiction':market if market=='CA' else None,'row_count':len(rows)})))
                    for n,r in enumerate(rows):c.execute('insert into candidate_source_rows values (?,?,?,?,?)',(sid,n,'0001',f'record:{sid}/{n}',json.dumps(r)))
            before=p.read_bytes();result=audit([p],root/'audit');self.assertEqual(p.read_bytes(),before)
            ca=next(x for x in result['sources'] if x['market']=='CA');self.assertEqual(ca['exact_content_extra_rows'],1);self.assertEqual(ca['repeated_native_with_different_content_groups'],1)
            self.assertEqual(result['cross_market_pairs'][0]['PRODUCT_NAME'],1)
            with sqlite3.connect(root/'audit'/'duplicate-audit.sqlite3') as c:
                self.assertEqual(c.execute('select count(*) from exact_duplicate_members').fetchone()[0],2)
                self.assertEqual(c.execute('select count(*) from cross_market_name_members').fetchone()[0],4)
            with self.assertRaises(ValueError):audit([p],root/'audit')
    def test_normalization_preserves_strength_salt_and_dosage_punctuation(self):
        self.assertEqual(norm(' Ａ  B '),'a b');self.assertNotEqual(norm('drug 5mg'),norm('drug 10mg'));self.assertNotEqual(norm('chloride'),norm('hydrochloride'));self.assertNotEqual(norm('a-b'),norm('ab'))
if __name__=='__main__':unittest.main()
