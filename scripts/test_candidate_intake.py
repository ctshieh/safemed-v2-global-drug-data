#!/usr/bin/env python3
import json,sqlite3,tempfile,unittest
from pathlib import Path
from ingest_contract_candidate import build
from archive_legacy_candidate import archive
class IntakeTests(unittest.TestCase):
    def test_raw_retention_immutable_versions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'input.json'
            record={'id':'label-document','version':'1','active_ingredient':['unmapped prose','third assertion'],'inactive_ingredient':['unknown role'], 'openfda':{'brand_name':['Same Brand'],'product_ndc':['123-456']}}
            source.write_text(json.dumps({'results':[record]}))
            first=build(source,root/'out','2026-10-07T00:00:00Z')
            self.assertEqual(first['records'][0]['raw_label_assertions'],record)
            self.assertIsNone(first['records'][0]['product_identity'])
            self.assertFalse(first['release_eligible'])
            with self.assertRaises(ValueError): build(source,root/'out','2026-10-07T00:00:00Z')
            record['version']='2'; source.write_text(json.dumps({'results':[record]}))
            second=build(source,root/'out','2026-10-07T00:00:00Z')
            self.assertNotEqual(first['source_snapshot_id'],second['source_snapshot_id'])
            with self.assertRaises(ValueError): build(source,root/'other','2026-10-07')
    def test_legacy_verbatim_no_upgrade(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root/'old.sqlite3'
            with sqlite3.connect(source) as c:
                for table in ['drugs','ingredients','drug_ingredients','rules','source_registry']:
                    c.execute('CREATE TABLE '+table+' (raw TEXT)'); c.execute('INSERT INTO '+table+' VALUES (?)',('COMPLETE unknown third original',))
            result=archive(source,root/'candidate.sqlite3')
            self.assertEqual(result['new_contract_approved_rows'],0)
            with sqlite3.connect(root/'candidate.sqlite3') as c:
                self.assertEqual(c.execute('SELECT raw FROM drugs').fetchone()[0],'COMPLETE unknown third original')
            with self.assertRaises(ValueError): archive(source,root/'candidate.sqlite3')
if __name__=='__main__': unittest.main()
