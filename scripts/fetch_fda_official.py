#!/usr/bin/env python3
"""Bounded public FDA-only downloads; no credentials or billable services."""
import argparse,datetime,hashlib,json,traceback,urllib.request,urllib.parse
from pathlib import Path
ALLOWED={'api.fda.gov','download.open.fda.gov','open.fda.gov','www.fda.gov'}
def fetch(url,target,limit):
 if urllib.parse.urlparse(url).scheme!='https' or urllib.parse.urlparse(url).hostname not in ALLOWED:raise ValueError('Not an allowed official HTTPS source')
 if target.exists():raise ValueError('Retained destination exists; do not overwrite')
 target.parent.mkdir(parents=True,exist_ok=True);e={'url':url,'utc_started':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SafeMed-public-source-intake/1.0'}),timeout=45) as r:
   if urllib.parse.urlparse(r.url).hostname not in ALLOWED:raise ValueError('Redirect outside official FDA hosts')
   e.update(http_status=r.status,final_url=r.url,headers=dict(r.headers.items()));h=hashlib.sha256();n=0
   if r.status!=200:raise ValueError('Non200')
   with target.open('xb') as out:
    while True:
     b=r.read(1024*1024)
     if not b:break
     n+=len(b)
     if n>limit:raise ValueError('Download byte bound exceeded')
     h.update(b);out.write(b)
   e.update(status='DOWNLOADED',bytes=n,sha256=h.hexdigest(),path=str(target.resolve()))
 except Exception as error:e.update(status='FAILED_RETAINED',error=repr(error),traceback=traceback.format_exc())
 e['utc_finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();target.with_name(target.name+'.download.json').write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n');print(json.dumps(e,ensure_ascii=False),flush=True)
 if e['status']!='DOWNLOADED':raise RuntimeError('Download failed; evidence retained')
 return e
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--output',required=True,type=Path);p.add_argument('--max-bytes',type=int,default=512*1024*1024);a=p.parse_args();fetch(a.url,a.output,a.max_bytes)
