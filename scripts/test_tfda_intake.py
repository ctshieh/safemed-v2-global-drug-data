#!/usr/bin/env python3
import io,sqlite3,tempfile,unittest,zipfile
from pathlib import Path
from ingest_tfda_open_data import decode,store
class IntakeTests(unittest.TestCase):
    def test_duplicate_unknown_and_third_rows_preserved(self):
        raw=('許可證字號,成分名稱,成分代碼,含量描述\nTW-A,Alpha,1,10 mg\nTW-A,Beta,2,20 mg\nTW-A,Unknown third,,\nTW-A,Unknown third,,\n').encode()
        with tempfile.TemporaryDirectory() as td,sqlite3.connect(':memory:') as c:
            c.execute('create table candidate_sources(a,b)');c.execute('create table candidate_source_rows(a,b,c,d,e)');c.execute('create table candidate_ingredient_rows(a,b,c,d,e,f,g,h,i,j)')
            result=store(c,(43,9121,'TEST ONLY'),raw,Path(td),'2026-10-08T00:00:00Z')
            self.assertEqual(result['row_count'],4)
            self.assertEqual(c.execute('select count(*) from candidate_ingredient_rows where g="UNKNOWN" and h="UNMAPPED" and i is null').fetchone()[0],4)
            with self.assertRaises(FileExistsError): store(c,(43,9121,'TEST ONLY'),raw,Path(td),'2026-10-08T00:00:00Z')
    def test_wrong_header_and_multi_member_zip_rejected(self):
        with self.assertRaises(ValueError): decode(b'a,a\n1,2\n')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z: z.writestr('a.csv','x');z.writestr('b.csv','x')
        with self.assertRaises(ValueError): decode(stream.getvalue())
if __name__=='__main__': unittest.main()
