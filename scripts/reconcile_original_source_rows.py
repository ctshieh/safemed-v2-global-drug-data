#!/usr/bin/env python3
"""Reparse pinned official originals and compare every candidate row, without medical promotion.

Parser code is shared with intake; this is an independent execution/comparison, not an
independently authored parser. JSON text comparison is exact to the adapter serialization.
Every mismatch is retained in JSONL, including complete expected/actual tuples.
"""
import argparse, hashlib, itertools, json, re, sqlite3, traceback
from pathlib import Path
from ingest_tfda_open_data import decode
from ingest_international_open_data import parse as json_rows
from ingest_france_public_data import parse as french_rows
from ingest_japan_korea_public_data import xlsx_rows, csv_rows

GROUPS={'TW':('TW_UNREVIEWED_candidate.sqlite3',5),'CA-EMA':('INTERNATIONAL_UNREVIEWED_candidate.sqlite3',3),'FR':('FR_UNREVIEWED_candidate.sqlite3',3),'JP':('JP_UNREVIEWED_candidate.sqlite3',5),'KR':('KR_UNREVIEWED_candidate.sqlite3',1)}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def js(obj,compact=False):return json.dumps(obj,ensure_ascii=False,**({'separators':(',',':')} if compact else {}))
def compare_rows(expected,actual,write,source,table):
    count=bad=0
    for pos,(want,got) in enumerate(itertools.zip_longest(expected,actual),1):
        count+=1
        if want is not None:want=tuple(want)
        if got is not None:got=tuple(got)
        if want!=got:
            bad+=1;write({'source_snapshot_id':source,'table':table,'comparison_position':pos,'expected':want,'actual':got})
    return count,bad

def expected_rows(group,sid,meta,raw):
    if group=='TW':
        _,header,reader=decode(raw)
        for n,values in enumerate(reader,1):
            if len(values)!=len(header):raise ValueError('TFDA original field count mismatch')
            row=dict(zip(header,values));yield n,row['許可證字號'],f'record:{sid}/csv-data-row/{n}',js(row,True)
    elif group=='CA-EMA':
        rows,_=json_rows(raw,meta)
        for n,row in enumerate(rows):
            native=str(row[meta['native_id_field']]);yield n,meta['jurisdiction'],native,f'record:{sid}/native/{native}/row/{n}',js(row,True)
    elif group=='FR':
        rows,_=french_rows(raw)
        for n,row in enumerate(rows,1):yield n,row[0],f'record:{sid}/cis/{row[0]}/row/{n}',js(row)
    elif group=='JP':
        rows=xlsx_rows(raw);columns={}
        for sheet,r,cells in rows:
            for cell in cells:
                if cell['value']=='薬価基準収載医薬品コード':columns[sheet]=re.sub(r'[0-9]+$','',cell['attributes']['r'])
        for n,(sheet,r,cells) in enumerate(rows,1):
            code=next((c['value'] for c in cells if re.sub(r'[0-9]+$','',c['attributes'].get('r',''))==columns.get(sheet)),None)
            native=code if isinstance(code,str) and re.fullmatch(r'[0-9A-Z]{12}',code) else None
            yield n,native,f'record:{sid}/{sheet}/row/{r}',js({'sheet':sheet,'row':r,'cells':cells})
    elif group=='KR':
        rows,_=csv_rows(raw);idx=rows[0].index('표준코드')
        for n,row in enumerate(rows[1:],1):yield n,row[idx].strip(),f'record:{sid}/csv/row/{n+1}',js({'header':rows[0],'columns':row})
    else:raise ValueError('Undeclared group')

def original(group,folder,meta):
    if group=='TW':
        raw=(folder/'original-download.bin').read_bytes()
        if sha(raw)!=meta['download_sha256']:raise ValueError('Transport hash mismatch')
        content,_,_=decode(raw)
        if content!=(folder/'original.csv').read_bytes():raise ValueError('ZIP transport vs original.csv differs')
        if sha(content)!=meta['csv_sha256']:raise ValueError('CSV hash mismatch')
        return raw,meta['csv_sha256']
    choices=[p for p in folder.iterdir() if p.name!='source.json' and p.is_file()]
    matching=[p for p in choices if sha(p.read_bytes())==meta['raw_sha256']]
    if len(matching)!=1:raise ValueError('Expected exactly one pinned original file')
    return matching[0].read_bytes(),meta['raw_sha256']

def run(inputs,catalog,output):
    if output.exists():raise ValueError('Refuse overwriting retained evidence directory')
    output.mkdir(parents=True)
    pinned=json.loads(catalog.read_text())['sources'];pins={s['source_snapshot_id']:s for s in pinned}
    results=[];seen=set();errors=0
    with (output/'mismatches.jsonl').open('w') as failures:
        def mismatch(obj):
            nonlocal errors
            errors+=1;failures.write(js(obj)+'\n');failures.flush()
        for group,(name,expected_count) in GROUPS.items():
            path=inputs/group/name
            try:
                with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as c:
                    sources=c.execute('SELECT source_snapshot_id,metadata_json FROM candidate_sources ORDER BY source_snapshot_id').fetchall()
                    if len(sources)!=expected_count:raise ValueError('Unexpected source count')
                    for sid,text in sources:
                        before=errors;report={'group':group,'source_snapshot_id':sid};results.append(report)
                        try:
                            if sid in seen or sid not in pins:raise ValueError('Duplicate or unpinned source; fixtures prohibited')
                            seen.add(sid);meta=json.loads(text);pin={k:v for k,v in pins[sid].items() if k!='archive_group'}
                            if meta!=pin or pins[sid]['archive_group']!=group:raise ValueError('Pinned metadata differs')
                            if meta.get('runtime_active') is not False or meta.get('release_eligible') is not False:raise ValueError('Reference source gate changed')
                            if meta.get('publisher') is None or not (meta.get('source_url') or meta.get('url','')).startswith('https://'):raise ValueError('Missing official provenance')
                            folder=inputs/group/sid
                            if json.loads((folder/'source.json').read_text())!=meta:raise ValueError('Retained source metadata differs')
                            raw,digest=original(group,folder,meta)
                            if not sid.endswith('-sha256-'+digest):raise ValueError('Snapshot ID not derived from original')
                            table='candidate_source_rows' if group in ('TW','CA-EMA') else 'candidate_rows'
                            fields={'TW':'row_number,local_product_id,source_locator,raw_assertions_json','CA-EMA':'source_order,jurisdiction,native_record_id,source_locator,raw_assertions_json','FR':'source_order,native_cis_reference,source_locator,raw_columns_json','JP':'source_order,native_reference,source_locator,raw_json','KR':'source_order,native_reference,source_locator,raw_json'}[group]
                            order=fields.split(',')[0]
                            actual=c.execute(f'SELECT {fields} FROM {table} WHERE source_snapshot_id=? ORDER BY {order}',(sid,))
                            n,bad=compare_rows(expected_rows(group,sid,meta,raw),actual,mismatch,sid,table)
                            report.update(original_sha256=digest,compared_rows=n,mismatching_rows=bad)
                            if n!=meta['row_count']:mismatch({'source_snapshot_id':sid,'error':'Source metadata row count differs','expected':meta['row_count'],'actual':n})
                            # Also verify every retained ingredient projection against reparsed originals.
                            if group=='TW' or group=='CA-EMA':
                                if group=='TW':
                                    def ingredients():
                                        for row in expected_rows(group,sid,meta,raw):
                                            n,native,_,text=row;obj=json.loads(text)
                                            if sid.startswith('tfda-43-'):yield f'{sid}/row/{n}',n,native,obj.get('成分名稱',''),obj.get('成分代碼',''),'UNKNOWN','UNMAPPED',None,text
                                    fields2='component_id,source_order,local_product_id,name_as_listed,local_ingredient_code,role,mapping_status,ingredient_id,raw_assertions_json'
                                else:
                                    def ingredients():
                                        for row in expected_rows(group,sid,meta,raw):
                                            n,_,native,_,text=row;obj=json.loads(text)
                                            if meta['key']=='ca-dpd-active-ingredients':yield f'{sid}/row/{n}',n,native,obj.get('ingredient_name',''),'ACTIVE','UNMAPPED',None,text
                                    fields2='component_id,source_order,native_product_reference,name_as_listed,role,mapping_status,ingredient_id,raw_assertions_json'
                                n2,b2=compare_rows(ingredients(),c.execute(f'SELECT {fields2} FROM candidate_ingredient_rows WHERE source_snapshot_id=? ORDER BY source_order',(sid,)),mismatch,sid,'candidate_ingredient_rows')
                                report.update(compared_ingredient_rows=n2,mismatching_ingredient_rows=b2)
                        except Exception as e:mismatch({'source_snapshot_id':sid,'error':str(e),'traceback':traceback.format_exc()})
                        report['status']='PASS' if errors==before else 'FAIL'
                        print(js(report),flush=True)
                    # Orphan rows must not hide behind the source registry selection.
                    for table, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'candidate_%rows'"):
                        for row in c.execute(f'SELECT * FROM {table} WHERE source_snapshot_id IS NULL OR source_snapshot_id NOT IN (SELECT source_snapshot_id FROM candidate_sources)'):
                            mismatch({'group':group,'table':table,'error':'Unregistered source row','actual':row})
            except Exception as e:mismatch({'group':group,'error':str(e),'traceback':traceback.format_exc()})
        if seen!=set(pins):mismatch({'error':'Source set differs from pinned catalog','missing':sorted(set(pins)-seen),'unexpected':sorted(seen-set(pins))})
    result={'status':'PASS' if not errors else 'FAIL','method':'Original bytes reparsed with pinned intake adapter functions; exact row tuples and exact serialized JSON compared, including OOXML cell XML/formulas/types. Not an independent parser implementation.','catalog_sha256':sha(catalog.read_bytes()),'source_count':len(results),'source_rows_compared':sum(r.get('compared_rows',0) for r in results),'ingredient_rows_compared':sum(r.get('compared_ingredient_rows',0) for r in results),'mismatch_records':errors,'sources':results,'clinical_approval':False,'runtime_approved':False,'inputs':str(inputs.resolve()),'mismatches':'mismatches.jsonl','tool_and_parser_sha256':{p.name:sha(p.read_bytes()) for p in [Path(__file__),*(Path(__file__).parent/n for n in ['ingest_tfda_open_data.py','ingest_international_open_data.py','ingest_france_public_data.py','ingest_japan_korea_public_data.py'])]}}
    (output/'RECONCILIATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    result=run(a.inputs,a.catalog,a.output_dir);print(js(result));raise SystemExit(0 if result['status']=='PASS' else 1)
