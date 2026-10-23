"""Producer-only integration fixture: build, reconcile, checkpoint and tamper gate.

This tiny synthetic fixture is never a medicine payload or App QA result.
"""
import argparse, hashlib, json, sqlite3, tempfile, unittest
from pathlib import Path
from contextlib import redirect_stdout
import io
from build_seven_market_candidate import main, stable, sha, js, insert
from verify_monthly_candidate import verify

class SevenMarketProducer(unittest.TestCase):
    def fixture(self, root):
        base=root/'base.sqlite3';c=sqlite3.connect(base)
        c.executescript((Path(__file__).resolve().parents[1]/'contracts/global-drug-data/1.0.0/schema.sql').read_text())
        insert(c,'package_manifest',dict(package_id='TEST_ONLY',schema_version='safemed-mobile-safety-v2.1',
            package_major_version='2',product_line='safemed_pro',license_tier='professional',requires_entitlement=1,
            compatible_app_major_versions='[2]',data_version='TEST_ONLY',rules_version='NONE-0',
            created_at='2026-10-23T00:00:00+00:00',package_format='sqlite3+gzip',source_snapshots='[]',
            quality_gate_result='CANDIDATE_ONLY',locked_regression_result='NOT_RUN'))
        insert(c,'package_contract',dict(package_id='TEST_ONLY',contract_version='1.0.0',
            core_namespace='safemed-global-core-v1',core_version='TEST_ONLY',release_sequence=6,
            snapshot_kind='COMPOSED_SNAPSHOT',market_codes_json='["CA","FR","TW"]',
            required_capabilities_json='[]',coverage_json='{"GLOBAL":{}}'))
        source='TEST_ONLY_BASE'
        insert(c,'source_registry',dict(source_id=source,source_name='TEST_ONLY',source_url='https://example.invalid',
            version_label='TEST_ONLY',license_note='TEST_ONLY',source_type='OFFICIAL_REGULATOR',
            retrieved_at='2026-10-23T00:00:00+00:00',checksum='a'*64))
        insert(c,'source_rights',dict(source_id=source,commercial_use_allowed=0,mobile_redistribution_allowed=0,
            attribution_text='TEST_ONLY',review_status='PENDING'))
        for market in ['TW','CA','FR']:
            did=stable('drug',market,'TEST_ONLY','123')
            insert(c,'drugs',dict(drug_id=did,display_name=market,generic_name='',source=source,
                source_version='TEST_ONLY',evidence_quality='OFFICIAL',data_completeness='UNKNOWN',
                is_combination=-1,active_ingredient_count=0,metadata_json=js({'safemed_product_identity':{},'original_medical_assertions':['TEST_ONLY exact retained archive']})))
            insert(c,'drug_product_identity',dict(drug_id=did,jurisdiction=market,identifier_namespace='TEST_ONLY',
                local_product_id='123',market_status='UNKNOWN',prescription_status='UNKNOWN'))
            insert(c,'id_ledger',dict(entity_kind='DRUG',stable_id=did,compact_int_id=None,lifecycle='ACTIVE'))
        for market,native,life in [('KR','123','ACTIVE'),('US','old-retired','RETIRED'),('US','withdrawn','ACTIVE')]:
            insert(c,'id_ledger',dict(entity_kind='DRUG',stable_id=stable('drug',market,'TEST_ONLY',native),compact_int_id=None,lifecycle=life))
        c.commit();c.close(); entries=[];norm=[]
        for market in ['US','JP','KR','AU']:
            path=root/(market+'.sqlite3');d=sqlite3.connect(path);sid='TEST_ONLY_'+market
            d.executescript('CREATE TABLE sources(source_id TEXT PRIMARY KEY,metadata_json TEXT);CREATE TABLE products_export(native_id TEXT,display_name TEXT,generic_name TEXT,manufacturer TEXT,dosage_form TEXT,route TEXT,aliases_json TEXT,components_json TEXT,source_refs_json TEXT,original_json TEXT);')
            meta={'raw_sha256':'b'*64,'source_url':'https://example.invalid/'+market,'retrieved_at':'2026-10-23T00:00:00+00:00','version_label':'TEST_ONLY'}
            d.execute('INSERT INTO sources VALUES (?,?)',(sid,js(meta)))
            rr={'source_id':sid,'locator':'TEST_ONLY/row/1'};name=market+' TEST';norm.append({'input':name,'normalized_utf8_hex':(market.lower()+'test').encode().hex()})
            component={'name_as_listed':'TEST_ONLY unsplit','role':'UNKNOWN','source_ref':rr}
            d.execute('INSERT INTO products_export VALUES (?,?,?,?,?,?,?,?,?,?)',('123',name,'',None,None,None,js([name]),js([component]),js([rr]),'{}'))
            d.commit();d.close();entries.append({'market':market,'namespace':'TEST_ONLY','language':'en','path':str(path),'sha256':sha(path)})
        config=root/'INPUTS.json';config.write_text(js({'countries':entries}));ref=root/'normalization.json';ref.write_text(js(norm))
        return base,config,ref

    def test_complete_roundtrip_checkpoint_and_tamper(self):
        with tempfile.TemporaryDirectory() as temp,redirect_stdout(io.StringIO()):
            root=Path(temp);base,config,ref=self.fixture(root);out=root/'candidate'
            main(argparse.Namespace(base=base,inputs=config,reference=ref,output=out,version='TEST_ONLY',created_at='2026-10-23T00:00:00+00:00'))
            result=verify(out,config,base)
            self.assertEqual(result['technical_build_status'],'PASS')
            self.assertEqual(result['market_product_counts'],{m:1 for m in ['TW','CA','FR','US','JP','KR','AU']})
            self.assertFalse(result['runtime_accepted'])
            checkpoint=sqlite3.connect(out/'ledger-checkpoint.sqlite3')
            self.assertEqual(checkpoint.execute('SELECT count(*) FROM id_ledger').fetchone()[0],9)
            self.assertEqual(checkpoint.execute("SELECT count(*) FROM id_ledger WHERE lifecycle='RETIRED'").fetchone()[0],2)
            checkpoint.close()
            with (out/'snapshot.sqlite3.gz').open('ab') as f:f.write(b'tampered')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):verify(out,config,base)

if __name__=='__main__':unittest.main()
