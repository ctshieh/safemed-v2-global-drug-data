"""Read the public PBS API using its publisher-provided public collection header."""
import argparse, datetime, hashlib, json, time, urllib.request, urllib.error
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--public-key-file',type=Path);p.add_argument('--delay',type=float,default=0);a=p.parse_args()
    assert a.url.startswith('https://data-api.health.gov.au/pbs/api/v3/')
    assert not a.out.exists(), 'Never overwrite source evidence'
    a.out.mkdir(parents=True)
    if a.delay:time.sleep(a.delay)
    headers={'Accept':'application/json','User-Agent':'SafeMed-official-source-ingest/1.0'}
    if a.public_key_file:headers['subscription-key']=a.public_key_file.read_text().strip()
    receipt={'request_url':a.url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'request_header_names':sorted(headers),'account_login_used':False,'user_password_used':False,
        'public_key_source':'Official HPP public Postman collection, anonymously visible subscription-key variable' if a.public_key_file else None,
        'public_key_fingerprint':hashlib.sha256(headers['subscription-key'].encode()).hexdigest() if a.public_key_file else None}
    try:
        try:response=urllib.request.urlopen(urllib.request.Request(a.url,headers=headers),timeout=45)
        except urllib.error.HTTPError as e:response=e
        with response:
            receipt.update(http_status=response.status,final_url=response.url,response_headers={k:v for k,v in response.headers.items() if k.lower() not in {'set-cookie'}})
            h=hashlib.sha256();n=0
            with (a.out/'response.json').open('xb') as f:
                for b in iter(lambda:response.read(1048576),b''):
                    n+=len(b);assert n<=1024**3,'Source exceeds bounded1GiB cap';h.update(b);f.write(b)
            receipt.update(bytes=n,sha256=h.hexdigest())
        body=json.loads((a.out/'response.json').read_bytes());receipt['top_level_keys']=list(body)
        receipt['api_meta']=body.get('_meta');receipt['copyright_messages']=(body.get('_meta') or {}).get('info',{}).get('messages',[])
        receipt['returned_rows']=len(body.get('data',[])) if isinstance(body.get('data'),list) else None
        receipt['error_body']=body if receipt['http_status']!=200 else None
        receipt['status']='SOURCE_RESPONSE_SAVED' if receipt['http_status']==200 else 'HTTP_FAILURE_RESPONSE_SAVED'
    except Exception as e:receipt.update(status='FETCH_FAILURE_RETAINED',error=repr(e))
    (a.out/'RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in {'api_meta','copyright_messages','response_headers'}},ensure_ascii=False),flush=True)
    raise SystemExit(0 if receipt.get('http_status')==200 else 1)
if __name__=='__main__':main()
