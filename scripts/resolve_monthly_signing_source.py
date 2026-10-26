"""Resolve only the completed source run, never an unrelated latest release."""
import argparse
import json
import os
from pathlib import Path
from monthly_release import PATTERN, eligible, releases, api


def resolve(repo, event, manual_tag, rows=None):
    run = event.get('workflow_run')
    if run is None:
        m = PATTERN.fullmatch(manual_tag)
        if not m or m[2] is None:
            raise ValueError('Manual signing requires an exact immutable source run tag')
        return manual_tag
    if (run.get('conclusion') != 'success' or run.get('status') != 'completed' or
        run.get('head_branch') != 'main' or run.get('head_repository', {}).get('full_name') != repo or
        run.get('path') != '.github/workflows/monthly-public-reference.yml'):
        raise ValueError('Refuse signing from a failed, foreign, branch, or unrelated workflow run')
    run_id, attempt = run.get('id'), run.get('run_attempt')
    if type(run_id) is not int or run_id <= 0 or type(attempt) is not int or attempt <= 0:
        raise ValueError('Invalid run identity')
    if rows is None:
        rows = [r for page in releases(repo) for r in page]
    matching = []
    for r in rows:
        m = PATTERN.fullmatch(r.get('tag_name', ''))
        if eligible(r) and m[2] == str(run_id) and m[3] == str(attempt):
            matching.append(r['tag_name'])
    if len(matching) > 1:
        raise ValueError('Ambiguous source releases for the completed run')
    # A successful scheduled cadence check may skip the build because this month
    # is already complete. Never substitute another run's package in that case.
    return matching[0] if matching else None


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True)
    p.add_argument('--event', type=Path, required=True)
    p.add_argument('--manual-tag', default='')
    args = p.parse_args()
    event = json.loads(args.event.read_text())
    if 'workflow_run' in event:
        trigger = event['workflow_run']
        run_id = trigger.get('id')
        if type(run_id) is not int or run_id <= 0:
            raise ValueError('Invalid triggering run')
        current = api(f'repos/{args.repo}/actions/runs/{run_id}')
        if any(current.get(k) != trigger.get(k) for k in ['id','head_sha','run_attempt']):
            raise ValueError('Trigger and current source run identity differ')
        event['workflow_run'] = current
    tag = resolve(args.repo, event, args.manual_tag)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write('ready=' + ('true' if tag else 'false') + '\nsource_tag=' + (tag or '') + '\n')
    if tag:
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write('SOURCE_TAG=' + tag + '\n')
    print(json.dumps({'status': 'READY_FOR_SIGNING' if tag else 'NO_NEW_SOURCE_RELEASE', 'source_tag': tag}))
