#!/usr/bin/env python3
"""Public CI artifact contains audit metadata only while redistribution rights are pending."""
import argparse,json
from pathlib import Path
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=False)
    items=[]
    for path in sorted(a.input_dir.glob('*/candidate.json')):
        c=json.loads(path.read_text())
        items.append({k:c[k] for k in ['source_snapshot_id','source_url','raw_sha256','retrieved_at','source_type','commercial_rights_review','redistribution_rights_review','release_eligible','coverage']})
        items[-1].update(record_count=len(c['records']),clinical_review='PENDING',raw_assertions_distributed=False)
    if not items: raise ValueError('No candidate snapshots')
    (a.output_dir/'source-intake-audit.json').write_text(json.dumps({'sources':items,'runtime_active':False,'limitations':'Metadata only. Full raw labels are not distributed while rights remain pending.'},indent=2)+'\n')
