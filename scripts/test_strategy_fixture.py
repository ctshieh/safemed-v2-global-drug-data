import json,sqlite3,tempfile,unittest
from pathlib import Path
from build_strategy_fixture import create,gate
class StrategyFixture(unittest.TestCase):
 def test_unknown_variants_preserve_third_row_and_reject_false_complete(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'fixture';r=create(root);db=root/'TEST_ONLY_snapshot.sqlite3'
   with sqlite3.connect(db) as c:
    self.assertEqual(c.execute('select count(*) from rules').fetchone()[0],0)
    self.assertEqual(c.execute("select count(*) from product_ingredient_rows where drug_id='A'").fetchone()[0],3)
    self.assertEqual({r[0] for r in c.execute('select composition_status from product_composition')},{'UNKNOWN','PARTIAL','CONFLICT'})
    self.assertEqual(c.execute('select count(*) from drug_ingredients').fetchone()[0],0)
    c.execute("update drugs set data_completeness='COMPLETE' where drug_id='A'")
   with self.assertRaisesRegex(gate.ContractError,'incomplete composition'):gate.validate(db,test_only=True)
 def test_fixture_never_passes_production_gate(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'fixture';create(root)
   with self.assertRaises(gate.ContractError):gate.validate(root/'TEST_ONLY_snapshot.sqlite3',test_only=False)
if __name__=='__main__':unittest.main()
