#!/usr/bin/env python3
"""Synthetic isolated comparator negatives; never part of a source package."""
import io,json,unittest,zipfile
from reconcile_original_source_rows import compare_rows,expected_rows
class RowReconciliationTests(unittest.TestCase):
    def test_equal_count_mutations_are_detected_with_complete_evidence(self):
        original=[(1,'ID-1','record:source/row/1','{"原文":"Ａ，鹽類"}'),(2,'ID-2','record:source/row/2','{"v":null}')]
        for field in range(4):
            with self.subTest(field=field):
                changed=list(original);r=list(changed[0]);r[field]=str(r[field])+' changed';changed[0]=tuple(r)
                failures=[];n,bad=compare_rows(iter(original),iter(changed),failures.append,'TEST_ONLY','test_rows')
                self.assertEqual((n,bad),(2,1));self.assertEqual(tuple(failures[0]['expected']),original[0]);self.assertEqual(tuple(failures[0]['actual']),changed[0])
    def test_missing_extra_and_reordered_rows(self):
        for actual in [[(1,'x')],[(1,'x'),(2,'y'),(3,'z')],[(2,'y'),(1,'x')]]:
            failures=[];_,bad=compare_rows([(1,'x'),(2,'y')],actual,failures.append,'TEST_ONLY','test_rows');self.assertGreater(bad,0)
    def test_tfda_zip_and_literal_fields(self):
        raw='許可證字號,成分名稱,含量\r\nID-001,"甲,乙",０１\r\n'.encode('utf-8-sig')
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('data.csv',raw)
        a=list(expected_rows('TW','TEST_ONLY',{},b.getvalue()))
        self.assertEqual(a[0][:3],(1,'ID-001','record:TEST_ONLY/csv-data-row/1'))
        self.assertEqual(json.loads(a[0][3]),{'許可證字號':'ID-001','成分名稱':'甲,乙','含量':'０１'})
    def test_canada_zero_order_and_native_string(self):
        rows=list(expected_rows('CA-EMA','TEST_ONLY',{'key':'ca-dpd-products','native_id_field':'drug_code','jurisdiction':'CA'},b'[{"drug_code":123,"name":"A"}]'))
        self.assertEqual(rows[0][:4],(0,'CA','123','record:TEST_ONLY/native/123/row/0'))
    def test_france_positional_empty_fields(self):
        rows=list(expected_rows('FR','TEST_ONLY',{},b'123\tA\t\t\r\n'))
        self.assertEqual(json.loads(rows[0][-1]),['123','A','',''])
    def test_korea_native_trim_does_not_change_raw(self):
        raw='표준코드,한글상품명\r\n 00123 ,甲\r\n'.encode('utf-8-sig')
        rows=list(expected_rows('KR','TEST_ONLY',{},raw))
        self.assertEqual(rows[0][1],'00123');self.assertEqual(json.loads(rows[0][-1])['columns'][0],' 00123 ')
    def test_empty_mismatch_stream_is_not_evidence_of_medical_review(self):
        failures=[];self.assertEqual(compare_rows([],[],failures.append,'TEST_ONLY','test_rows'),(0,0))
if __name__=='__main__':unittest.main()
