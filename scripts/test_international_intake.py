#!/usr/bin/env python3
import json,sqlite3,tempfile,unittest
from pathlib import Path
from ingest_international_open_data import SOURCES,parse,build
class IntakeTests(unittest.TestCase):
    def test_retains_third_and_unmapped_duplicates_no_eu_country(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);input_dir=root/'input';input_dir.mkdir()
            payloads=[[{'drug_code':1,'brand_name':'Same','drug_identification_number':'00000001'}],[{'drug_code':1,'ingredient_name':x,'strength':'unparsed'} for x in ['A','B','Third','Third']],{'meta':{'total_records':1,'timestamp':'2026-10-08T00:00:00Z'},'data':[{'ema_product_number':'TEST/1','name_of_medicine':'Same','active_substance':'unmapped prose'}]}]
            for source,p in zip(SOURCES,payloads):(input_dir/(source['key']+'.json')).write_text(json.dumps(p))
            report=build(root/'out',input_dir,'2026-10-08T00:00:00Z')
            self.assertEqual(report['retained_source_rows'],6);self.assertEqual(report['retained_active_ingredient_rows'],4)
            self.assertFalse(report['release_eligible']);self.assertIsNone(report['sources'][2]['jurisdiction'])
            with sqlite3.connect(root/'out/INTERNATIONAL_UNREVIEWED_candidate.sqlite3') as c:
                self.assertEqual(c.execute("select count(*) from candidate_ingredient_rows where name_as_listed='Third' and ingredient_id is null").fetchone()[0],2)
            with self.assertRaises(ValueError):build(root/'out',input_dir)
    def test_total_and_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):parse(b'{"meta":{"total_records":2},"data":[{"ema_product_number":"X"}]}',SOURCES[2])
        with self.assertRaises(ValueError):parse(b'[{"drug_code":1,"drug_code":2}]',SOURCES[0])
if __name__=='__main__':unittest.main()
