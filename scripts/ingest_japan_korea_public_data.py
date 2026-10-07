#!/usr/bin/env python3
"""Lossless JP/KR official candidate intake. AU records rights blockers only."""
import os,argparse,csv,datetime as dt,hashlib,io,json,re,shutil,sqlite3,tempfile,urllib.parse,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from ingest_tfda_open_data import download
JP_PAGE=os.environ.get('MHLW_PRICE_LIST_PAGE') or 'https://www.mhlw.go.jp/topics/2026/04/tp20260401-01.html'
JP_LICENSE='https://www.mhlw.go.jp/chosakuken/index.html'
KR_PAGE='https://www.data.go.kr/data/15067462/fileData.do'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def plain(node):
    # Include rich text runs, exclude phonetic annotations from resolved display text.
    if node is None:return None
    return ''.join(x.text or '' for x in list(node.findall('s:t',NS))+list(node.findall('s:r/s:t',NS)))
def xlsx_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(x.file_size for x in z.infolist())>256*1024*1024:raise ValueError('Expanded workbook too large')
        strings=[plain(x) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
        rows=[]
        for sheet in sorted(x for x in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',x)):
            for row in ET.fromstring(z.read(sheet)).findall('s:sheetData/s:row',NS):
                cells=[]
                for c in row.findall('s:c',NS):
                    v=c.findtext('s:v',namespaces=NS);value=strings[int(v)] if c.get('t')=='s' else plain(c.find('s:is',NS)) if c.get('t')=='inlineStr' else v
                    cells.append({'attributes':dict(c.attrib),'value':value,'cached_raw_value':v,'formula':c.findtext('s:f',namespaces=NS),'original_cell_xml':ET.tostring(c,encoding='unicode')})
                rows.append((sheet,row.get('r'),cells))
        if not rows:raise ValueError('Empty workbook')
        if not any(any(c['value']=='薬価基準収載医薬品コード' for c in row[2]) for row in rows):raise ValueError('Unexpected Japan workbook')
        return rows

def csv_rows(raw):
    for encoding in ['utf-8-sig','cp949']:
        try:rows=list(csv.reader(io.StringIO(raw.decode(encoding),newline='')));break
        except UnicodeDecodeError:continue
    else:raise ValueError('Unknown CSV encoding')
    if not rows or '표준코드' not in rows[0] or '한글상품명' not in rows[0]:raise ValueError('Expected HIRA standard code CSV')
    if len(rows)<2 or any(len(x)!=len(rows[0]) for x in rows[1:]):raise ValueError('CSV row width mismatch')
    return rows,encoding

def build(country,output):
    if output.exists():raise ValueError('Refuse overwriting source archive')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        root=Path(tmp)/'intake';root.mkdir();reports=[]
        with sqlite3.connect(root/(country+'_UNREVIEWED_candidate.sqlite3')) as db:
            db.executescript('CREATE TABLE candidate_sources(source_snapshot_id TEXT PRIMARY KEY,metadata_json TEXT);CREATE TABLE candidate_rows(source_snapshot_id TEXT,source_order INTEGER,native_reference TEXT,source_locator TEXT,raw_json TEXT,PRIMARY KEY(source_snapshot_id,source_order));')
            if country=='JP':
                if not os.environ.get('MHLW_PRICE_LIST_PAGE') and dt.datetime.now(dt.timezone.utc).year != 2026:raise ValueError('Confirm current MHLW source page via MHLW_PRICE_LIST_PAGE before a new-year build')
                if not JP_PAGE.startswith('https://www.mhlw.go.jp/'):raise ValueError('Japan source must be official MHLW')
                page=download(JP_PAGE);html=page.decode('shift_jis');(root/'source-page.html').write_bytes(page)
                license_raw=download(JP_LICENSE);(root/'license-evidence.html').write_bytes(license_raw)
                if b'PDL1.0' not in license_raw:raise ValueError('Japan license changed')
                links=list(dict.fromkeys(re.findall(r'href="([^"]+\.xlsx)"',html)))[:5]
                if len(links)!=5:raise ValueError('Expected current five MHLW Excel sections')
                for link in links:
                    url=urllib.parse.urljoin(JP_PAGE,link);raw=download(url);rows=xlsx_rows(raw)
                    normalized=[];data_count=0;code_columns={}
                    for sheet,r,cells in rows:
                        for cell in cells:
                            if cell["value"]=="薬価基準収載医薬品コード":code_columns[sheet]=re.sub(r"[0-9]+$","",cell["attributes"]["r"])
                    for sheet,r,cells in rows:
                        code=next((c['value'] for c in cells if re.sub(r'[0-9]+$','',c['attributes'].get('r',''))==code_columns.get(sheet)),None)
                        is_data=isinstance(code,str) and bool(re.fullmatch(r'[0-9A-Z]{12}',code))
                        data_count+=is_data;normalized.append((code if is_data else None,f'{sheet}/row/{r}',{'sheet':sheet,'row':r,'cells':cells}))
                    if data_count==0:raise ValueError('No Japanese drug records')
                    reports.append(store(db,root,country,Path(link).name,url,raw,normalized,{'publisher':'厚生労働省 / MHLW','source_page':JP_PAGE,'license':'Public Data License 1.0 (PDL1.0), site-specific exclusions apply','license_url':JP_LICENSE,'rights_status':'OPEN_LICENSE_DECLARED_FORMAL_REVIEW_PENDING','drug_record_rows':data_count,'scope':'Five current published price-list sections, including overlapping generic-status section. Row counts are not unique drug counts. Some multi-ingredient names omitted by publisher; no full ingredient/DDI coverage.','publication_date':'See original source-page.html per-section date; not inferred from retrieval','encoding':'Original OOXML with resolved display strings; original cell XML/formula/type/style retained'}))
            elif country=='KR':
                page=download(KR_PAGE);html=page.decode('utf-8');(root/'source-page.html').write_bytes(page)
                if '출처표시 (제 1유형)' not in html:raise ValueError('Korean reuse declaration changed')
                match=re.search(r"fn_fileDataDown\('15067462', '([^']+)', '([^']*)','([^']+)', '([^']+)'\)",html)
                if not match:raise ValueError('No official public file download button')
                detail,atch,sn,hist=match.groups()
                query=urllib.parse.urlencode({'publicDataPk':'15067462','publicDataDetailPk':detail,'atchFileId':atch,'fileDetailSn':sn,'publicDataTyCode':'PR0051'})
                response=download('https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?'+query);(root/'download-response.json').write_bytes(response);j=json.loads(response)
                (root/'license-evidence.html').write_bytes(download('https://www.kogl.or.kr/info/licenseType1.do'))
                if j.get('status') is not True or not re.fullmatch(r'FILE_[0-9]+',j.get('atchFileId','')):raise ValueError('Official file unavailable')
                url='https://www.data.go.kr/cmm/cmm/fileDownload.do?'+urllib.parse.urlencode({'atchFileId':j['atchFileId'],'fileDetailSn':j['fileDetailSn'],'insertDataPrcus':'N'})
                raw=download(url);rows,encoding=csv_rows(raw);idx=rows[0].index('표준코드')
                normalized=[(row[idx].strip(),f'csv/row/{n+2}',{'header':rows[0],'columns':row}) for n,row in enumerate(rows[1:])]
                reports.append(store(db,root,country,'HIRA_standard_codes.csv',url,raw,normalized,{'publisher':'Health Insurance Review and Assessment Service (HIRA)','source_page':KR_PAGE,'license':'Korea Open Government License Type 1 / attribution','license_url':'https://www.kogl.or.kr/info/licenseType1.do','dataset_license_declaration_url':KR_PAGE,'original_file_name':j['fileDataRegistVO'].get('orginlFileNm'),'rights_status':'OPEN_LICENSE_DECLARED_FORMAL_REVIEW_PENDING','publication_date':j['dataSetFileDetailInfo'].get('updtDt'),'scope':'Full downloaded standard-code mapping CSV including withdrawn products; not current reimbursement status or complete ingredient/DDI database. File row count may differ from portal metadata.','encoding':encoding,'source_description':j['dataSetFileDetailInfo'].get('publicDataDc')}))
            else:raise ValueError('Unknown country')
            if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
        result={'sources':reports,'retained_source_rows':sum(x['row_count'] for x in reports),'runtime_active_rules':0,'release_eligible':False}
        (root/'intake-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (root/'ATTRIBUTION.txt').write_text('\n'.join('Source: '+x['publisher']+'; '+x['source_page']+'; '+x['license']+'; '+x['license_url']+'; retrieved '+x['retrieved_at']+'; original data preserved and indexed by SafeMed (加工・索引化：SafeMed), no publisher endorsement.' for x in reports)+'\n本 App 僅提供參考並建議用戶諮詢藥師和醫師，不作醫療決策。\n')
        shutil.move(str(root),output)
    return result

def store(db,root,country,name,url,raw,rows,extra):
    digest=hashlib.sha256(raw).hexdigest();sid=country.lower()+'-'+name+'-sha256-'+digest;folder=root/sid;folder.mkdir();(folder/name).write_bytes(raw)
    report={'source_snapshot_id':sid,'source_url':url,'jurisdiction':country,'raw_sha256':digest,'version_label':'content-sha256:'+digest,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'row_count':len(rows),'composition_status':'UNKNOWN','mapping_status':'UNMAPPED','clinical_review':'PENDING','runtime_active':False,'release_eligible':False,**extra}
    for n,(ref,locator,row) in enumerate(rows,1):db.execute('INSERT INTO candidate_rows VALUES (?,?,?,?,?)',(sid,n,ref,'record:'+sid+'/'+locator,json.dumps(row,ensure_ascii=False)))
    db.execute('INSERT INTO candidate_sources VALUES (?,?)',(sid,json.dumps(report,ensure_ascii=False)));(folder/'source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'country':country,'file':name,'rows':len(rows),'sha256':digest}),flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--country',choices=['JP','KR'],required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();build(a.country,a.output_dir)
