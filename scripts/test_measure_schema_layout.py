import sqlite3,tempfile,unittest
from pathlib import Path
from measure_schema_layout import inspect
from produce_contract_snapshot import gate
class Layout(unittest.TestCase):
 def test_exact_and_altered_layout(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'test.sqlite3'
   with sqlite3.connect(p) as c:c.executescript(gate.SCHEMA)
   self.assertEqual(inspect(p)['status'],'PASS')
   with sqlite3.connect(p) as c:c.execute('alter table drugs add column unsolicited TEXT')
   self.assertEqual(inspect(p)['status'],'FAIL')
 def test_missing_nonunique_index(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'test.sqlite3'
   with sqlite3.connect(p) as c:c.executescript(gate.SCHEMA);c.execute('drop index idx_drug_aliases_normalized')
   self.assertEqual(inspect(p)['status'],'FAIL')
if __name__=='__main__':unittest.main()
