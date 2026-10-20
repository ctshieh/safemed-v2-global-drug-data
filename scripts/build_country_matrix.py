#!/usr/bin/env python3
"""Every contract jurisdiction gets an explicit coverage disposition, never inferred EU rows."""
import argparse,json
from pathlib import Path

def build(manifest,contract):
    result=[]
    for country in contract['iso_3166_1_alpha2']:
        sources=[s for s in manifest['sources'] if s.get('jurisdiction')==country]
        result.append({'country':country,'status':'ACQUIRED_REFERENCE_ONLY' if sources else 'NOT_ACQUIRED','source_snapshots':len(sources),'source_rows':sum(s['row_count'] for s in sources),'source_ids':[s['source_snapshot_id'] for s in sources],'runtime_approved_products':0,'active_clinical_rules':0,'gap': 'Mapping/composition/rights approval pending' if sources else manifest.get('excluded',{}).get(country,'No verified official export acquired in this build')})
    return {'format':'safemed-country-source-matrix-v1','countries':result,'regional_sources':[s for s in manifest['sources'] if not s.get('jurisdiction')],'regional_note':'EMA procedures kept separate; no inferred national market registrations','commercial_vendor_credentials':'NOT_PROVIDED; no licensed feeds accessed'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle-dir',required=True,type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=build(json.loads((a.bundle_dir/'manifest.json').read_text()),json.loads((root/'contracts/global-drug-data/1.0.0/contract.json').read_text()))
    (a.bundle_dir/'COUNTRY_SOURCE_MATRIX.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
