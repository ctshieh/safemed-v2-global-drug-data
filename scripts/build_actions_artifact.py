#!/usr/bin/env python3
"""Reproducible TEST ONLY composed package and source disclosure for Actions."""
import argparse,hashlib,json,sqlite3,subprocess,sys
from pathlib import Path
from produce_contract_snapshot import ROOT,C,build,verify_contract,gate

def run(output):
    verify_contract()
    if output.exists(): raise ValueError('Output must be a new immutable build directory')
    output.mkdir(parents=True)
    subprocess.run([sys.executable,str(C/'test_contract.py'),'--output',str(output/'regression')],check=True)
    with sqlite3.connect(output/'regression/TEST_ONLY_global_compound.sqlite3') as c:
        c.row_factory=sqlite3.Row
        payload={t:[dict(x) for x in c.execute('SELECT * FROM "'+t+'"')] for t in gate.CONTRACT['required_tables']}
    (output/'TEST_ONLY_reviewed_rows.json').write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    a=build(payload,output/'TEST_ONLY_composed.sqlite3',test_only=True)
    b=build(payload,output/'reproducibility/TEST_ONLY_composed.sqlite3',test_only=True)
    if (a['sqlite_sha256'],a['gzip_sha256'])!=(b['sqlite_sha256'],b['gzip_sha256']):
        raise ValueError('Reproducibility gate failed')
    disclosures=[]
    rights={x['source_id']:x for x in payload['source_rights']}
    for source in payload['source_registry']:
        disclosures.append({**source,'rights':rights[source['source_id']],
            'status':'TEST_ONLY_NOT_CLINICAL_EVIDENCE','clinical_review':'NOT_PERFORMED'})
    provenance={'format':'safemed-build-provenance-v1','test_only':True,'release_eligible':False,
        'purpose':'Engineering contract tests only; not a global clinical drug database',
        'contract_version':'1.0.0','schema_version':gate.CONTRACT['schema_version'],
        'reproducible_sqlite_and_gzip':True,'gates':a,'sources':disclosures}
    (output/'sources-and-build.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
    (output/'README.txt').write_text('TEST ONLY. Synthetic ingredients/products/rules. No human medical review. Unsigned. Not for App deployment.\nApp provides reference information and recommends consulting a pharmacist or physician; it does not make medical decisions.\n')
    print(json.dumps(provenance,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
