#!/usr/bin/env python3
"""Offline openFDA intake: full raw assertions, immutable snapshot, no inferred mappings."""
import argparse,hashlib,json
from pathlib import Path
def build(source,output,retrieved_at):
    from produce_contract_snapshot import gate,verify_contract
    verify_contract()
    if not gate.stamp(retrieved_at): raise ValueError('Timezone-aware retrieval timestamp required')
    raw=source.read_bytes()
    if len(raw)>25*1024*1024: raise ValueError('Input exceeds bounded intake limit')
    payload=gate.parse(raw,dict,'openFDA raw')
    records=payload.get('results')
    if not isinstance(records,list) or not records: raise ValueError('Missing results')
    checksum=hashlib.sha256(raw).hexdigest(); sid='openfda-label-sha256-'+checksum
    dest=output/sid
    if dest.exists(): raise ValueError('Immutable source snapshot already exists')
    seen=set(); candidates=[]
    for record in records:
        identity=record.get('id') if isinstance(record,dict) else None
        if not gate.nonempty(identity) or identity in seen: raise ValueError('Missing/duplicate label record ID')
        seen.add(identity)
        # Label document ID is not a market product ID. Preserve assertions without merging.
        candidates.append({'source_record_id':identity,'source_record_version':record.get('version'),
            'source_locator':'record:'+identity,'jurisdiction':'US','product_identity':None,
            'raw_label_assertions':record,'parsed_ingredient_rows':[],
            'composition_status':'UNKNOWN','mapping_review':'PENDING',
            'composition_review':'PENDING','runtime_active':False})
    result={'format':'safemed-contract-1.0.0-source-candidate','source_snapshot_id':sid,
        'raw_sha256':checksum,'retrieved_at':retrieved_at,'source_type':'OFFICIAL_LABEL',
        'source_url':'https://open.fda.gov/apis/drug/label/',
        'commercial_rights_review':'PENDING','redistribution_rights_review':'PENDING',
        'release_eligible':False,'coverage':'BOUNDED_INPUT_NOT_GLOBAL_COVERAGE',
        'records':candidates}
    dest.mkdir(parents=True)
    (dest/'original.json').write_bytes(raw)
    (dest/'candidate.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True); p.add_argument('--retrieved-at',required=True)
    a=p.parse_args(); result=build(a.input,a.output_dir,a.retrieved_at)
    print(json.dumps({'source_snapshot_id':result['source_snapshot_id'],'records':len(result['records']),'release_eligible':False}))
