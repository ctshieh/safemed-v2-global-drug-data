import unittest
from ingest_france_public_data import parse
class FranceIntakeTests(unittest.TestCase):
    def test_positional_fields_no_first_row_or_duplicate_loss(self):
        rows,encoding=parse('12345678\télément\t\n12345678\tThird\t\n12345678\tThird\t\n'.encode('cp1252'))
        self.assertEqual(len(rows),3);self.assertEqual(rows[0][1],'élément');self.assertEqual(rows[0][-1],'');self.assertEqual(rows[1],rows[2])
    def test_html_not_drug_data(self):
        with self.assertRaises(ValueError):parse(b'<html>error</html>')
if __name__=='__main__':unittest.main()
