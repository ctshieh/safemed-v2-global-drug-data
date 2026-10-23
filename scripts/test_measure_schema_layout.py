import sqlite3,tempfile,unittest,re
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
 def test_declared_physical_layout_still_rejects_unrelated_changes(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'compact.sqlite3';schema=gate.SCHEMA
   for table in ['drug_source_links','ingredient_sources','id_ledger']:
    schema=re.sub(r'(CREATE TABLE '+table+r'\s*\(.*?\));',r'\1 WITHOUT ROWID;',schema,flags=re.S)
   with sqlite3.connect(p) as c:c.executescript(schema)
   self.assertEqual(inspect(p)['status'],'FAIL')
   self.assertEqual(inspect(p,'compact-source-v1')['status'],'PASS')
   with sqlite3.connect(p) as c:c.execute('drop index idx_drug_aliases_normalized')
   self.assertEqual(inspect(p,'compact-source-v1')['status'],'FAIL')
 def test_missing_nonunique_index(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'test.sqlite3'
   with sqlite3.connect(p) as c:c.executescript(gate.SCHEMA);c.execute('drop index idx_drug_aliases_normalized')
   self.assertEqual(inspect(p)['status'],'FAIL')
if __name__=='__main__':unittest.main()
