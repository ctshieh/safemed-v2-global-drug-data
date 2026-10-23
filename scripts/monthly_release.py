"""Publish unsigned engineering candidates and retain exactly two successful months.

Only this producer's strictly named, verified releases are eligible for deletion.
A new release must be fully uploaded and hash-verified remotely before cleanup.
"""
import argparse, datetime as dt, gzip, hashlib, json, os
from pathlib import Path
import re, shutil, subprocess, tempfile
from zoneinfo import ZoneInfo

PREFIX='global-drug-candidate-'
MARKER='safemed-seven-market-monthly-candidate-v1'
PATTERN=re.compile(r'^global-drug-candidate-(\d{4}-(?:0[1-9]|1[0-2]))(?:-run-(\d+)-(\d+))?$')

def gh(*args):
    return subprocess.check_output(['gh',*args],text=True).strip()

def api(path,method='GET',body=None):
    args=['api',path,'--method',method]
    if body is not None:
        args+=['--input','-']
        raw=subprocess.check_output(['gh',*args],input=json.dumps(body),text=True)
    else:raw=gh(*args)
    return json.loads(raw) if raw else None

def releases(repo):
    return json.loads(gh('api',f'repos/{repo}/releases','--paginate','--slurp'))

def eligible(release):
    return (bool(PATTERN.fullmatch(release.get('tag_name',''))) and
        not release.get('draft',True) and release.get('prerelease') is True and
        release.get('body','').startswith(MARKER+'\n') and
        {'MONTHLY_SUCCESS.json','snapshot.sqlite3.gz','ledger-checkpoint.sqlite3.gz'} <=
        {a['name'] for a in release.get('assets',[]) if a.get('state')=='uploaded'})

def plan(rows,current_tag,new_verified=False):
    """Pure planner: failure, unknown tags and incomplete releases can never delete."""
    if not new_verified:return {'keep':[],'delete':[],'reason':'New package not verified; no deletion'}
    current=next((r for r in rows if r.get('tag_name')==current_tag and eligible(r)),None)
    if current is None:raise ValueError('Current successful release absent')
    valid=ordered(rows)
    keep=[];months=set()
    for r in valid:
        month=PATTERN.fullmatch(r['tag_name'])[1]
        if month not in months and len(months)<2:keep.append(r);months.add(month)
    if current not in keep:raise ValueError('Refuse cleanup from a stale month')
    return {'keep':[r['tag_name'] for r in keep],'delete':[r['tag_name'] for r in valid if r not in keep]}

def ordered(rows):
    def key(r):
        m=PATTERN.fullmatch(r['tag_name']);return (m[1],int(m[2] or 0),int(m[3] or 0))
    return sorted((r for r in rows if eligible(r)),key=key,reverse=True)

def legacy_artifact_plan(artifacts, oldest_kept_month):
    """Select only legacy package payloads; never diagnostic or failed evidence.

    Caller must additionally verify the producing workflow and success status.
    """
    result=[]
    for artifact in artifacts:
        name=artifact.get('name','')
        managed=(name=='LOGICAL-RUNTIME-CANDIDATE' or
            re.fullmatch(r'PUBLIC-REFERENCE-UNREVIEWED-\d+-\d+',name))
        if not managed or artifact.get('expired',True):continue
        created=dt.datetime.fromisoformat(artifact['created_at'].replace('Z','+00:00'))
        if created.tzinfo is None:raise ValueError('Artifact date lacks timezone')
        month=created.astimezone(ZoneInfo('Asia/Taipei')).strftime('%Y-%m')
        if month<oldest_kept_month:result.append(artifact)
    return result

def cleanup_legacy(repo, kept):
    cutoff=min(PATTERN.fullmatch(tag)[1] for tag in kept)
    pages=json.loads(gh('api',f'repos/{repo}/actions/artifacts','--paginate','--slurp'))
    artifacts=[a for page in pages for a in page['artifacts']]
    candidates=legacy_artifact_plan(artifacts,cutoff)
    workflow=api(f'repos/{repo}/actions/workflows/monthly-public-reference.yml')['id']
    deleted=[]
    for artifact in candidates:
        run=api(f'repos/{repo}/actions/runs/{artifact["workflow_run"]["id"]}')
        if run['workflow_id']!=workflow or run['conclusion']!='success':continue
        api(f'repos/{repo}/actions/artifacts/{artifact["id"]}','DELETE')
        deleted.append({'id':artifact['id'],'name':artifact['name'],'created_at':artifact['created_at']})
    return deleted

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def download(repo,tag,name,directory):
    subprocess.run(['gh','release','download',tag,'--repo',repo,'--pattern',name,
        '--dir',str(directory)],check=True)
    return directory/name

def previous(repo,output):
    rows=[r for page in releases(repo) for r in page]
    valid=ordered(rows)
    if not valid:raise ValueError('No durable monthly checkpoint; use explicit legacy bootstrap, never reset')
    output.mkdir(parents=True,exist_ok=False)
    tag=valid[0]['tag_name']
    marker=json.loads(download(repo,tag,'MONTHLY_SUCCESS.json',output).read_text())
    payload=download(repo,tag,'ledger-checkpoint.sqlite3.gz',output)
    if sha(payload)!=marker['assets']['ledger-checkpoint.sqlite3.gz']['sha256']:
        raise ValueError('Remote checkpoint compressed SHA mismatch')
    with gzip.open(payload,'rb') as src,(output/'checkpoint.sqlite3').open('xb') as dest:
        shutil.copyfileobj(src,dest,1048576)
    if sha(output/'checkpoint.sqlite3')!=marker['verification']['ledger_checkpoint_sha256']:
        raise ValueError('Remote checkpoint SQLite SHA mismatch')
    print(output/'checkpoint.sqlite3')

def publish(repo,root,month,commit):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month):raise ValueError('Invalid month')
    tag=PREFIX+month+'-run-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    verification=json.loads((root/'MONTHLY_VERIFICATION.json').read_text())
    if verification.get('technical_build_status')!='PASS':raise ValueError('Not a validated build')
    rows=[r for page in releases(repo) for r in page]
    if any(r['tag_name']==tag for r in rows):
        raise ValueError('This immutable run release exists; preserve it. Re-run with a new run attempt; never overwrite success')
    # Only whitelisted deliverables and source archives are public. No local
    # correspondence, credentials, workflow state, App, or signed manifest.
    files=[root/'snapshot.sqlite3.gz',root/'ledger-checkpoint.sqlite3.gz',
        root/'MONTHLY_VERIFICATION.json',root/'BUILD_MEASUREMENTS.json']
    files+=sorted(root.glob('sources.tar.gz.part-*'))
    if not any(p.name.startswith('sources.tar.gz.part-') for p in files):raise ValueError('Full source archive missing')
    marker={'format':MARKER,'month':month,'commit':commit,'run_id':os.environ.get('GITHUB_RUN_ID'),
        'verification':verification,'assets':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in files},
        'not_a_formal_app_manifest':True,'unsigned_candidate_only':True}
    success=root/'MONTHLY_SUCCESS.json';success.write_text(json.dumps(marker,ensure_ascii=False,indent=2)+'\n');files.append(success)
    release=api(f'repos/{repo}/releases','POST',{'tag_name':tag,'target_commitish':commit,
        'name':f'Seven-market unreviewed candidate {month}','draft':True,'prerelease':True,
        'body':MARKER+'\nUnsigned engineering candidate; not App/clinical approval. Original copyright, source scope, transformations and gaps are in the source archive. Retention: latest two successful months.'})
    for f in files:
        subprocess.run(['gh','release','upload',tag,str(f),'--repo',repo],check=True)
    remote=api(f'repos/{repo}/releases/{release["id"]}')
    byname={a['name']:a for a in remote['assets']}
    # GitHub's server-side asset digest plus bytes proves remote content before
    # publishing the completion marker or deleting any older release.
    for f in files:
        asset=byname.get(f.name)
        if not asset or asset['state']!='uploaded' or asset['size']!=f.stat().st_size or asset.get('digest')!='sha256:'+sha(f):
            raise ValueError('Remote upload digest/size verification failed: '+f.name)
    api(f'repos/{repo}/releases/{release["id"]}','PATCH',{'draft':False})
    rows=[r for page in releases(repo) for r in page]
    retention=plan(rows,tag,new_verified=True)
    for oldtag in retention['delete']:
        old=next(r for r in rows if r['tag_name']==oldtag)
        # Re-read immediately; never delete changed/unmanaged releases.
        fresh=api(f'repos/{repo}/releases/{old["id"]}')
        if not eligible(fresh) or fresh['tag_name']!=oldtag:raise ValueError('Cleanup identity changed')
        subprocess.run(['gh','release','delete',oldtag,'--repo',repo,'--yes','--cleanup-tag'],check=True)
    retention['legacy_payload_artifacts_deleted']=cleanup_legacy(repo,retention['keep'])
    (root/'RETENTION_RESULT.json').write_text(json.dumps(retention,indent=2)+'\n')
    print(json.dumps({'url':f'https://github.com/{repo}/releases/tag/{tag}',**retention}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['previous','publish','has-monthly'])
    p.add_argument('--repo',required=True);p.add_argument('--root',type=Path)
    p.add_argument('--month');p.add_argument('--commit');a=p.parse_args()
    if a.mode=='previous':previous(a.repo,a.root)
    elif a.mode=='has-monthly':print('true' if any(eligible(r) for page in releases(a.repo) for r in page) else 'false')
    else:publish(a.repo,a.root,a.month or dt.datetime.now(ZoneInfo('Asia/Taipei')).strftime('%Y-%m'),a.commit)
