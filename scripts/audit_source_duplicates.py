#!/usr/bin/env python3
"""Read-only full-row duplicate and literal cross-market name audit. Never merges records."""
import argparse,collections,hashlib,itertools,json,re,sqlite3,unicodedata
from pathlib import Path

def canon(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canon(value).encode()).hexdigest()
def norm(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split()) if isinstance(value,str) else ''

def extract(sid,meta,row,native,jp_headers):
    country=meta.get('jurisdiction') or ('EMA_REGION' if sid.startswith('ema-') else 'UNRESOLVED')
    names=[];projection=row;family='UNRESOLVED';kind='REFERENCE'
    if country=='TW':
        family='TW_LICENSE';kind='PRODUCT' if sid.startswith('tfda-36-') else 'CHILD_REFERENCE'
        names=[('PRODUCT_NAME',row.get(k,'')) for k in ['中文品名','英文品名']]+[('INGREDIENT_TEXT',row.get('成分名稱',''))]
    elif country=='CA':
        family='CA_DPD_DRUG_CODE';kind='PRODUCT' if 'products-sha256' in sid else 'CHILD_REFERENCE'
        names=[('PRODUCT_NAME',row.get('brand_name','')),('INGREDIENT_TEXT',row.get('ingredient_name',''))]
    elif country=='EMA_REGION':
        family='EMA_PROCEDURE_NUMBER';kind='PROCEDURE'
        names=[('PRODUCT_NAME',row.get('name_of_medicine','')),('INGREDIENT_TEXT',row.get('active_substance',''))]
    elif country=='FR':
        family='FR_CIS';kind='PRODUCT' if meta['source_name']=='CIS_bdpm.txt' else 'CHILD_REFERENCE'
        if meta['source_name']=='CIS_bdpm.txt':names=[('PRODUCT_NAME',row[1])]
        elif meta['source_name']=='CIS_COMPO_bdpm.txt':names=[('INGREDIENT_TEXT',row[3])]
    elif country=='KR':
        family='KR_STANDARD_CODE';kind='PACKAGE_REFERENCE';projection=row['columns'];obj=dict(zip(row['header'],row['columns']));names=[('PRODUCT_NAME',obj.get('한글상품명',''))]
    elif country=='JP':
        family='JP_PRICE_LIST_CODE';kind='PRICE_LIST_REFERENCE'
        cells={re.sub(r'[0-9]+$','',c['attributes']['r']):c for c in row['cells']}
        hkey=(sid,row['sheet'])
        if not native:
            jp_headers[hkey]={col:c['value'] for col,c in cells.items()};return None
        headers=jp_headers[hkey]
        names=[('PRODUCT_NAME',c['value']) for col,c in cells.items() if headers.get(col)=='品名']+ [('INGREDIENT_TEXT',c['value']) for col,c in cells.items() if str(headers.get(col,'')).startswith('成分名')]
        projection={col:{'value':c['value'],'formula':c['formula']} for col,c in cells.items()}
    return country,family,kind,projection,names

def audit(paths,output):
    if output.exists():raise ValueError('Refuse overwriting audit')
    output.mkdir(parents=True);reports=[];headers={};skipped=[]
    with sqlite3.connect(output/'duplicate-audit.sqlite3') as out:
        out.executescript('CREATE TABLE records(source TEXT,row_order INTEGER,market TEXT,family TEXT,kind TEXT,native TEXT,locator TEXT,content_hash TEXT,PRIMARY KEY(source,row_order));CREATE TABLE names(kind TEXT,normalized TEXT,original TEXT,market TEXT,source TEXT,row_order INTEGER,native TEXT,locator TEXT);')
        for path in paths:
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as src:
                if src.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('Input SQLite integrity failed')
                tables={r[0] for r in src.execute("select name from sqlite_master where type='table'")}
                if 'candidate_sources' not in tables:skipped.append({'file':str(path),'reason':'Not an official candidate intake; legacy/fixtures must be audited separately'});continue
                table='candidate_source_rows' if 'candidate_source_rows' in tables else 'candidate_rows'
                cols=[r[1] for r in src.execute('pragma table_info('+table+')')]
                order=next(x for x in ['row_number','source_order'] if x in cols)
                rawfield=next(x for x in ['raw_assertions_json','raw_columns_json','raw_json'] if x in cols)
                nativefield=next(x for x in ['local_product_id','native_record_id','native_cis_reference','native_reference'] if x in cols)
                for sid,text in src.execute('select source_snapshot_id,metadata_json from candidate_sources order by source_snapshot_id'):
                    meta=json.loads(text);n=0;header_n=0
                    expected=meta.get('csv_sha256') or meta.get('raw_sha256');original_verified=False
                    if expected:
                        folder=path.parent/sid
                        candidates=[f for f in folder.iterdir() if f.name!='source.json' and (f.name=='original.csv' if meta.get('csv_sha256') else True)]
                        original_verified=any(hashlib.sha256(f.read_bytes()).hexdigest()==expected for f in candidates)
                        if not original_verified:raise ValueError('Original source byte checksum mismatch')
                    for row_order,native,locator,raw in src.execute(f'select {order},{nativefield},source_locator,{rawfield} from {table} where source_snapshot_id=? order by {order}',(sid,)):
                        n+=1;row=json.loads(raw);result=extract(sid,meta,row,native,headers)
                        if result is None:header_n+=1;continue
                        market,family,kind,projection,names=result
                        out.execute('insert into records values (?,?,?,?,?,?,?,?)',(sid,row_order,market,family,kind,native.strip() if native else '',locator,digest(projection)))
                        for name_kind,name in names:
                            normalized=norm(name)
                            if normalized:out.execute('insert into names values (?,?,?,?,?,?,?,?)',(name_kind,normalized,name,market,sid,row_order,native,locator))
                    if n!=meta['row_count']:raise ValueError('Row count does not match intake report')
                    details={}
                    if sid.startswith('tfda-36-'):
                        groups=collections.defaultdict(list)
                        for ref,raw in src.execute(f'select {nativefield},{rawfield} from {table} where source_snapshot_id=?',(sid,)):
                            groups[ref].append(json.loads(raw))
                        varying=collections.Counter();samples=[]
                        for ref,rows in groups.items():
                            if len(rows)<2:continue
                            fields=[k for k in rows[0] if len({canon(x[k]) for x in rows})>1];varying.update(fields)
                            if len(samples)<10:samples.append({'native_reference':ref,'row_count':len(rows),'varying_fields':fields})
                        details={'distinct_license_references':len(groups),'same_license_varying_field_group_counts':dict(varying),'same_license_examples':samples,'interpretation':'Repeated license rows retain manufacturing-site/process variants; do not count rows as distinct products or delete manufacturing assertions'}
                    reports.append({'source_snapshot_id':sid,'market':meta.get('jurisdiction') or 'EMA_REGION','input_path':str(path),'input_rows':n,'excluded_header_rows':header_n,'audited_record_rows':n-header_n,'source_metadata':meta,'original_source_checksum_verified':original_verified,**details})
                    print('Scanned',sid.split('-sha256-')[0],n,flush=True)
        out.executescript('CREATE INDEX records_source_hash ON records(source,content_hash);CREATE INDEX records_native ON records(source,native);CREATE INDEX names_match ON names(kind,normalized,market);')
        for report in reports:
            sid=report['source_snapshot_id'];where='source=?'
            d=out.execute('select count(*),coalesce(sum(n-1),0) from (select count(*) n from records where source=? group by content_hash having count(*)>1)',(sid,)).fetchone()
            repeated=out.execute("select count(*),coalesce(sum(n-1),0),coalesce(sum(variants>1),0) from (select count(*) n,count(distinct content_hash) variants from records where source=? and native!='' group by native having count(*)>1)",(sid,)).fetchone()
            report.update(exact_content_duplicate_groups=d[0],exact_content_extra_rows=d[1],repeated_native_reference_groups=repeated[0],repeated_native_extra_rows=repeated[1],repeated_native_with_different_content_groups=repeated[2],missing_native_reference_rows=out.execute("select count(*) from records where source=? and native=''",(sid,)).fetchone()[0])
        out.executescript("CREATE VIEW exact_duplicate_members AS SELECT r.* FROM records r JOIN (SELECT source,content_hash FROM records GROUP BY source,content_hash HAVING count(*)>1) g USING(source,content_hash);CREATE VIEW repeated_native_members AS SELECT r.* FROM records r JOIN (SELECT source,native FROM records WHERE native!='' GROUP BY source,native HAVING count(*)>1) g USING(source,native);CREATE VIEW source_content_groups AS SELECT source,content_hash,min(row_order) representative_row_order,count(*) occurrence_count FROM records GROUP BY source,content_hash;CREATE VIEW cross_market_name_members AS SELECT n.* FROM names n JOIN (SELECT kind,normalized FROM names GROUP BY kind,normalized HAVING count(distinct market)>1) g USING(kind,normalized);")
        markets=[x[0] for x in out.execute('select distinct market from records order by market')];pairs=[]
        for left,right in itertools.combinations(markets,2):
            counts={}
            for kind in ['PRODUCT_NAME','INGREDIENT_TEXT']:
                counts[kind]=out.execute('select count(*) from (select normalized from names where market=? and kind=? intersect select normalized from names where market=? and kind=?)',(left,kind,right,kind)).fetchone()[0]
            pairs.append({'left':left,'right':right,**counts,'meaning':'Literal normalized text overlap only; NOT proven same product or canonical ingredient'})
        jp=[]
        for a,b in itertools.combinations([r['source_snapshot_id'] for r in reports if r['market']=='JP'],2):
            n=out.execute("select count(*) from (select native from records where source=? and native!='' intersect select native from records where source=? and native!='')",(a,b)).fetchone()[0]
            if n:jp.append({'left':a,'right':b,'shared_price_list_codes':n})
        groups=out.execute('select kind,count(*) from (select kind,normalized from names group by kind,normalized having count(distinct market)>1) group by kind').fetchall()
        result={'format':'safemed-duplicate-audit-v1','sources':reports,'total_input_rows':sum(r['input_rows'] for r in reports),'total_audited_record_rows':sum(r['audited_record_rows'] for r in reports),'exact_content_extra_rows_total':sum(r['exact_content_extra_rows'] for r in reports),'cross_market_literal_groups':dict(groups),'cross_market_pairs':pairs,'japan_cross_file_overlaps':jp,'japan_unique_price_list_codes':out.execute("select count(distinct native) from records where market='JP' and native!=''").fetchone()[0],'skipped':skipped,'limitations':['No deletions, merges, canonical IDs or clinical approvals','Cross-market matching uses NFKC, casefold and collapsed whitespace only; no fuzzy matches, translations, salt equivalence, dosage/route equivalence or composition inference','Repeated native parent references for ingredient/classification/package rows are expected relationships, not automatically duplicates','Japan content comparison excludes Excel coordinates and styles; retains resolved cell values and formulas','Same-market multiple snapshots are kept separate, not counted as duplicate ingestion','US bounded label sample raw assertions unavailable to this audit; AU has no ingested drug records','Legacy package and engineering fixtures are excluded from official-country statistics','Zero literal matches between languages is not proof of zero overlap; Japanese/Korean translation and verified canonical mapping remain pending']}
        (output/'duplicate-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        lines=['# 各市場候選資料重複稽核','',f"檢查 {result['total_input_rows']:,} 原始列；不刪除或合併任何來源資料。",'','| 來源 | 資料列 | 同內容額外列 | 重複來源鍵群組 | 同鍵不同內容群組 |','| --- | ---: | ---: | ---: | ---: |']
        for r in reports:lines.append(f"| {r['source_snapshot_id'].split('-sha256-')[0]} | {r['audited_record_rows']:,} | {r['exact_content_extra_rows']:,} | {r['repeated_native_reference_groups']:,} | {r['repeated_native_with_different_content_groups']:,} |")
        lines+=['',f"日本共有 {result['japan_unique_price_list_codes']:,} 不同藥價清單代碼；跨檔重疊詳見 JSON。",'', '跨市場同名只列為人工核對線索，不是同一市場商品的證明。成分名稱相同不表示包裝、劑量、途徑或完整組成相同。','', '完整逐列來源定位保存於 duplicate-audit.sqlite3 的 exact_duplicate_members、repeated_native_members、cross_market_name_members views。','', '限制：美國100筆標示樣本原文未提供此稽核、澳洲尚無藥品列；不宣稱已查完全世界。舊包／fixture另查，不混入官方清單統計。']
        (output/'DUPLICATE_REPORT.md').write_text('\n'.join(lines)+'\n')
        if out.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('Audit integrity failed')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,action='append',required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();audit(a.input,a.output_dir)
