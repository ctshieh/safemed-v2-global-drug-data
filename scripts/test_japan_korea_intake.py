import io,unittest,zipfile
from ingest_japan_korea_public_data import csv_rows,xlsx_rows
class IntakeTests(unittest.TestCase):
    def test_csv_codes_duplicates_and_multiline_retained(self):
        raw='한글상품명,표준코드,비고\r\n商品,00123 ,"first\nsecond"\r\n商品,00123 ,third\r\n'.encode('utf-8')
        rows,encoding=csv_rows(raw)
        self.assertEqual(len(rows),3);self.assertEqual(rows[1][1],'00123 ');self.assertEqual(rows[1][2],'first\nsecond');self.assertEqual(rows[2][2],'third')
    def test_csv_rejects_html_and_incomplete_rows(self):
        for raw in [b'<html>error</html>','한글상품명,표준코드\nfoo\n'.encode()]:
            with self.assertRaises(ValueError):csv_rows(raw)
    def test_xlsx_rich_strings_phonetic_and_formula_preserved(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('xl/sharedStrings.xml','<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>薬価基準収載医薬品コード</t></si><si><r><t>001</t></r><r><t>ABC</t></r><rPh sb="0" eb="1"><t>PHONETIC</t></rPh></si></sst>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2" t="s" s="42"><v>1</v></c><c r="C2"><f>1+2</f><v>3</v></c></row></sheetData></worksheet>')
        rows=xlsx_rows(b.getvalue());self.assertEqual(rows[1][2][0]['value'],'001ABC');self.assertEqual(rows[1][2][0]['attributes']['s'],'42');self.assertEqual(rows[1][2][1]['formula'],'1+2');self.assertEqual(rows[1][2][1]['cached_raw_value'],'3')
if __name__=='__main__':unittest.main()
