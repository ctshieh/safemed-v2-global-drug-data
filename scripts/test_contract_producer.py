#!/usr/bin/env python3
"""Offline synthetic producer checks. No real drug or clinical claim."""
import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
from produce_contract_snapshot import build,C,gate
spec=importlib.util.spec_from_file_location('fixture',C/'test_contract.py'); fixture=importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0,str(C)); spec.loader.exec_module(fixture)
class ProducerTests(unittest.TestCase):
    def test_build_roundtrip_and_rejections(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); base=root/'base'; fixture.fixture(base)
            with sqlite3.connect(base) as c:
                c.row_factory=sqlite3.Row
                data={t:[dict(row) for row in c.execute('SELECT * FROM "'+t+'"')] for t in gate.CONTRACT['required_tables']}
            a=build(data,root/'a',test_only=True); b=build(data,root/'b',test_only=True)
            self.assertEqual(a['sqlite_sha256'],b['sqlite_sha256']); self.assertEqual(a['gzip_sha256'],b['gzip_sha256'])
            with self.assertRaises(ValueError): build(data,root/'a',test_only=True)
            with self.assertRaises(ValueError): build(data,root/'initial')
            with self.assertRaises(gate.ContractError): build(data,root/'production',initial_ledger_confirmed=True)
            data['package_contract'][0]['required_capabilities_json']='["unknown"]'
            with self.assertRaises(gate.ContractError): build(data,root/'unknown',test_only=True)
            self.assertFalse((root/'unknown').exists())
if __name__=='__main__': unittest.main()
