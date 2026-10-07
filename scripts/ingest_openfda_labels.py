#!/usr/bin/env python3
"""Create an auditable US identity candidate; never an activated app package."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ENDPOINT = 'https://api.fda.gov/drug/label.json?limit=100'

def build(raw):
    payload = json.loads(raw)
    rows = payload.get('results')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Missing or empty label results')
    records = []
    seen = set()
    for row in rows:
        identity = row.get('id')
        version = row.get('version')
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError('Missing or duplicate label ID')
        seen.add(identity)
        # Preserve source assertions verbatim; label prose is not parsed into
        # verified active ingredients or interaction rules.
        records.append({'source_record_id': identity,
                        'source_record_version': version,
                        'jurisdiction': 'US', 'status': 'CANDIDATE',
                        'identity_assertions': row.get('openfda', {}),
                        'ingredient_review_status': 'UNREVIEWED',
                        'active_ingredients': [], 'safety_rules': []})
    return {'format': 'safemed-global-source-candidate-v1',
            'source_id': 'us_fda_openfda_drug_label_api',
            'source_url': ENDPOINT,
            'source_metadata': payload.get('meta', {}),
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'jurisdiction': 'US', 'coverage': 'BOUNDED_SAMPLE_NOT_FULL_SNAPSHOT',
            'release_eligible': False, 'redistribution_review': 'PENDING',
            'records': records}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Offline original JSON snapshot')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.input:
        raw = args.input.read_bytes()
    else:
        with urlopen(ENDPOINT, timeout=60) as response:
            raw = response.read(25 * 1024 * 1024 + 1)
    if len(raw) > 25 * 1024 * 1024:
        raise ValueError('Snapshot exceeds 25 MiB limit')
    candidate = build(raw)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'openfda-labels-original.json').write_bytes(raw)
    (args.output_dir / 'candidate.json').write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"US label candidates: {len(candidate['records'])}; release_eligible=false")

if __name__ == '__main__':
    main()
