#!/usr/bin/env python3
"""Synthetic UNKNOWN/PARTIAL/CONFLICT transport fixture. Never production data."""
import argparse, gzip, hashlib, importlib.util, json, sqlite3, sys
from pathlib import Path
from produce_contract_snapshot import C, gate, build
sys.path.insert(0,str(C))
spec=importlib.util.spec_from_file_location('synthetic_fixture',C/'test_contract.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
def create(output):
    if output.exists():raise ValueError('Refuse overwriting fixture output')
    output.mkdir(parents=True)
    seed=output/'TEST_ONLY_source.sqlite3';fixture.fixture(seed)
    with sqlite3.connect(seed) as c:
        c.execute('PRAGMA foreign_keys=ON')
        for t in ['ingredient_pair_rules','rule_evidence','rule_sources','rule_applicability','rules']:c.execute('DELETE FROM '+t)
        c.execute("DELETE FROM id_ledger WHERE entity_kind='RULE'")
        c.execute('DELETE FROM drug_ingredients')
        c.execute("UPDATE product_ingredient_rows SET role='UNKNOWN',ingredient_id=NULL,mapping_status='UNMAPPED',mapping_source_id=NULL,mapping_source_locator=NULL,mapping_review_reference=NULL,mapping_reviewed_at=NULL")
        c.execute("UPDATE drugs SET data_completeness='UNKNOWN',active_ingredient_count=0,is_combination=-1")
        c.execute("UPDATE drug_compact_index SET ingredient_int_ids_json='[]'")
        c.execute("UPDATE product_composition SET composition_status='UNKNOWN',expected_active_row_count=NULL,review_status='PENDING',reviewer_kind='AUTOMATED',review_reference=NULL,reviewed_at=NULL,completeness_note='TEST ONLY original synthetic rows retained; no complete composition or clinical conclusion'")
        c.execute("UPDATE product_composition SET composition_status='PARTIAL' WHERE drug_id='B'")
        c.execute("UPDATE product_composition SET composition_status='CONFLICT' WHERE drug_id='C'")
        pc=json.loads(c.execute('SELECT coverage_json FROM package_contract').fetchone()[0])
        for market in pc:
            for domain in pc[market]:pc[market][domain]['status']='NONE'
        c.execute('UPDATE package_contract SET coverage_json=?',(json.dumps(pc,ensure_ascii=False,separators=(',',':')),))
        c.commit();c.row_factory=sqlite3.Row
        payload={t:[dict(row) for row in c.execute('SELECT * FROM "'+t+'"')] for t in gate.CONTRACT['required_tables']}
    report=build(payload,output/'TEST_ONLY_snapshot.sqlite3',test_only=True)
    data=output/'TEST_ONLY_reviewed_rows.json';data.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    report['fixture_only']=True;report['not_real_medical_data']=True
    (output/'FIXTURE_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    (output/'SHA256SUMS.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()},indent=2)+'\n')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    print(json.dumps(create(p.parse_args().output_dir),indent=2))
