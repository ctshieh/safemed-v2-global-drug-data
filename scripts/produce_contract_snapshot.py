#!/usr/bin/env python3
"""Build one unsigned snapshot from explicit reviewed table rows; no medical inference."""
import argparse, gzip, hashlib, importlib.util, json, sqlite3, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/'contracts/global-drug-data/1.0.0'
spec=importlib.util.spec_from_file_location('gate',C/'validate_contract.py')
gate=importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
def verify_contract():
    for name,digest in json.loads((C/'SHA256SUMS.json').read_text())['sha256'].items():
        if hashlib.sha256((C/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Contract hash mismatch: '+name)
def build(payload,output,previous=None,test_only=False,initial_ledger_confirmed=False):
    verify_contract()
    if previous is None and not (test_only or initial_ledger_confirmed):
        raise ValueError('Initial ledger requires explicit human confirmation')
    if output.exists() or Path(str(output)+'.gz').exists():
        raise ValueError('Refuse overwriting snapshot')
    if set(payload)!=set(gate.CONTRACT['required_tables']):
        raise ValueError('Exactly all 29 table arrays required')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as td:
        temp=Path(td)/'snapshot.sqlite3'
        with sqlite3.connect(temp) as c:
            c.executescript(gate.SCHEMA)
            c.execute('PRAGMA foreign_keys=OFF')
            for table in gate.CONTRACT['required_tables']:
                columns={x[1] for x in c.execute('PRAGMA table_info("'+table+'")')}
                if not isinstance(payload[table],list): raise ValueError('Table must be array')
                # Input row order is preserved; identical reviewed input yields identical bytes.
                for row in payload[table]:
                    if not isinstance(row,dict) or not row or not set(row)<=columns:
                        raise ValueError('Unknown or empty row fields: '+table)
                    names=sorted(row)
                    c.execute('INSERT INTO "'+table+'" ('+','.join('"'+n+'"' for n in names)+') VALUES ('+','.join('?' for _ in names)+')',[row[n] for n in names])
        result=gate.validate(temp,previous=previous,test_only=test_only)
        raw=temp.read_bytes(); zipped=gzip.compress(raw,mtime=0)
        report={'status':'PASS','unsigned':True,'test_only':test_only,'release_eligible':False,'sqlite_sha256':hashlib.sha256(raw).hexdigest(),'gzip_sha256':hashlib.sha256(zipped).hexdigest(),'sqlite_bytes':len(raw),'gzip_bytes':len(zipped),'validation':result}
        output.write_bytes(raw); Path(str(output)+'.gz').write_bytes(zipped)
        output.with_suffix('.gate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    p.add_argument('--previous',type=Path); p.add_argument('--test-only',action='store_true')
    p.add_argument('--initial-ledger-confirmed',action='store_true',help='Human confirmation of initial stable IDs; never medical/rights approval')
    a=p.parse_args(); print(json.dumps(build(gate.parse(a.input.read_text(),dict,"producer input"),a.output,a.previous,a.test_only,a.initial_ledger_confirmed),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
