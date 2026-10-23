"""Collect all aliases for the standalone Foundation producer reference."""
import argparse, json, sqlite3
from pathlib import Path
from build_seven_market_candidate import products

def collect(base, config, output):
    c = sqlite3.connect(base.resolve().as_uri()+'?mode=ro', uri=True)
    names = {r[0] for r in c.execute('SELECT alias FROM drug_aliases')}; c.close()
    for entry in json.loads(config.read_text())['countries']:
        for row in products(entry):
            names.update(json.loads(row['aliases_json']))
            names.add(row['display_name'] or ('NDC ' if entry['market']=='US' else entry['market']+' ')+row['native_id'])
    output.write_text(json.dumps([{'input': x} for x in sorted(names)], ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();collect(a.base,a.config,a.output)
