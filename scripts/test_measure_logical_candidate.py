import gzip,importlib.util,sqlite3,sys,tempfile,unittest
from pathlib import Path
from measure_logical_candidate import measure,LIMITS
from produce_contract_snapshot import C
sys.path.insert(0,str(C));spec=importlib.util.spec_from_file_location('fixture',C/'test_contract.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
class Measurements(unittest.TestCase):
 def test_fixture_is_not_production(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'fixture.sqlite3';fixture.fixture(p);gp=Path(str(p)+'.gz');gp.write_bytes(gzip.compress(p.read_bytes(),mtime=0));r=measure(p,gp,True)
   self.assertTrue(r['schema']['exact_required_tables']);self.assertEqual(r['contract_validation']['status'],'PASS');self.assertTrue(r['gzip']['matches_logical_sqlite']);self.assertEqual(r['logical_sqlite']['sqlite_bytes'],p.stat().st_size);self.assertFalse(r['runtime_consumer_compatible']);self.assertTrue(r['fixture_markers']);self.assertEqual(measure(p)['contract_validation']['status'],'FAIL')
 def test_oversize_cell_detected_without_approving(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'fixture.sqlite3';fixture.fixture(p)
   with sqlite3.connect(p) as c:c.execute('update drugs set display_name=?',('x'*(LIMITS['cell_bytes']+1),))
   r=measure(p,test_only=True);self.assertIn('drugs:cell_bytes',r['budget_violations']);self.assertFalse(r['budget_compatible'])
 def test_missing_table_and_bad_json(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'fixture.sqlite3';fixture.fixture(p)
   with sqlite3.connect(p) as c:c.execute('drop table drug_aliases');c.execute("update package_contract set required_capabilities_json='[NaN]'")
   r=measure(p,test_only=True);self.assertFalse(r['schema']['exact_required_tables']);self.assertTrue(r['json_errors']);self.assertEqual(r['contract_validation']['status'],'FAIL')
 def test_corruption_and_wrong_gzip(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'fixture.sqlite3';fixture.fixture(p);gp=Path(str(p)+'.gz');gp.write_bytes(gzip.compress(b'wrong SQLite',mtime=0))
   self.assertFalse(measure(p,gp,True)['gzip']['matches_logical_sqlite'])
   p.write_bytes(b'not a database')
   with self.assertRaises(sqlite3.DatabaseError):measure(p)
if __name__=='__main__':unittest.main()
