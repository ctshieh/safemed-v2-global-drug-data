#!/usr/bin/env python3
"""Synthetic-only producer and contract tests. Contains no real drugs or clinical recommendations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from validate_contract import CONTRACT, SCHEMA, ROOT, validate, ContractError

DATE='2026-10-07T00:00:00Z'
SID='TEST-source-snapshot-v1'
def js(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def put(c,table,**values):
    names=','.join(values)
    marks=','.join('?' for _ in values)
    c.execute(f'INSERT INTO {table} ({names}) VALUES ({marks})',list(values.values()))
def fixture(path):
    with sqlite3.connect(path) as c:
        c.executescript(SCHEMA)
        put(c,'source_registry',source_id=SID,source_name='TEST ONLY invented labels',source_url='https://example.invalid/synthetic/labels',version_label='TEST-v1',license_note='Synthetic fixture only. No clinical use.',source_type='TEST_FIXTURE',retrieved_at=DATE,checksum='a'*64)
        put(c,'source_rights',source_id=SID,commercial_use_allowed=1,mobile_redistribution_allowed=1,license_evidence_url='https://example.invalid/synthetic/rights',attribution_text='TEST ONLY synthetic fixture',review_status='APPROVED',review_reference='TEST-NOT-A-HUMAN-APPROVAL',reviewed_at=DATE)
        put(c,'package_manifest',package_id='TEST-global-composition',schema_version=CONTRACT['schema_version'],package_major_version='2',product_line='safemed_pro',license_tier='testing',requires_entitlement=0,compatible_app_major_versions='[2]',data_version='TEST-1',rules_version='TEST-1',created_at=DATE,package_format='sqlite3+gzip',source_snapshots=js([{'source_id':SID,'version_label':'TEST-v1','checksum':'a'*64}]),quality_gate_result='PASS',locked_regression_result='PASS')
        coverage={market:{d:{'status':'PARTIAL' if market=='GLOBAL' and d in CONTRACT['coverage_domains'][:5] else 'NONE','scope':'Synthetic test scope only','limitations':'No real drug, no medical assurance'} for d in CONTRACT['coverage_domains']} for market in ['GLOBAL','TW','US']}
        put(c,'package_contract',package_id='TEST-global-composition',contract_version='1.0.0',core_namespace=CONTRACT['core_namespace'],core_version='TEST-1',release_sequence=1,snapshot_kind='COMPOSED_SNAPSHOT',market_codes_json='["TW","US"]',required_capabilities_json=js(CONTRACT['required_capabilities']),coverage_json=js(coverage))
        for n in range(1,6):
            iid=f'ING-{n}'
            put(c,'ingredients',ingredient_id=iid,ingredient_int_id=n,canonical_name=f'TEST Ingredient {n}',normalized_name=f'test ingredient {n}',source=SID,source_version='TEST-v1',evidence_quality='TEST_FIXTURE')
            put(c,'ingredient_sources',ingredient_id=iid,source_id=SID,source_locator=f'record:canonical/{iid}')
            put(c,'id_ledger',entity_kind='INGREDIENT',stable_id=iid,compact_int_id=n,lifecycle='ACTIVE')
        # A's third ingredient is shared with SINGLE and B, and interacts with C's second.
        products=[('A','TW',[1,2,3]),('SINGLE','TW',[3]),('B','TW',[4,3]),('C','US',[1,5]),('SAME-NAME-US','US',[4])]
        for did,country,ids in products:
            name='TEST Same Brand' if did in ['A','SAME-NAME-US'] else f'TEST Product {did}'
            identity={'contract_version':'safemed-product-identity-v1','jurisdiction':country,'identifier_namespace':'TEST-LABEL-ID','local_product_id':did,'source_ids':[SID]}
            put(c,'drugs',drug_id=did,display_name=name,generic_name=name,source=SID,source_version='TEST-v1',evidence_quality='TEST_FIXTURE',data_completeness='COMPLETE',is_combination=int(len(ids)>1),active_ingredient_count=len(ids),metadata_json=js({'safemed_product_identity':identity}))
            put(c,'drug_product_identity',drug_id=did,jurisdiction=country,identifier_namespace='TEST-LABEL-ID',local_product_id=did,market_status='ACTIVE',prescription_status='RX')
            for purpose in ['IDENTITY','COMPOSITION']:
                put(c,'drug_source_links',drug_id=did,source_id=SID,purpose=purpose,source_locator=f'record:products/{did}/{purpose.lower()}')
            put(c,'product_composition',drug_id=did,composition_status='VERIFIED_COMPLETE',expected_active_row_count=len(ids),review_status='APPROVED',reviewer_kind='TEST_FIXTURE',review_reference='TEST-NOT-A-HUMAN-APPROVAL',reviewed_at=DATE,completeness_note='TEST ONLY full synthetic rows, not clinical approval')
            for order,n in enumerate(ids):
                put(c,'product_ingredient_rows',component_id=f'{did}-{order}',drug_id=did,source_order=order,ingredient_id=f'ING-{n}',name_as_listed=f'TEST Ingredient {n}',role='ACTIVE',strength_text='10 mg',strength_value=10,strength_unit='mg',basis_text='per synthetic tablet',mapping_status='VERIFIED',source_id=SID,source_locator=f'record:products/{did}/row/{order}',mapping_source_id=SID,mapping_source_locator=f'record:canonical/ING-{n}',mapping_review_reference='TEST-MAPPING-NOT-HUMAN',mapping_reviewed_at=DATE)
                put(c,'drug_ingredients',drug_id=did,ingredient_id=f'ING-{n}',ingredient_int_id=n,ingredient_name_as_listed=f'TEST Ingredient {n}',strength_text='10 mg',strength_value=10,strength_unit='mg',role='ACTIVE',source=SID,source_version='TEST-v1',confidence=1)
            put(c,'drug_compact_index',drug_id=did,ingredient_int_ids_json=js(sorted(ids)),class_int_ids_json='[]')
            put(c,'id_ledger',entity_kind='DRUG',stable_id=did,compact_int_id=None,lifecycle='ACTIVE')
        put(c,'rules',rule_id='TEST-PAIR',rule_int_id=1,rule_code='TEST_THIRD_COMPONENT_PAIR',rule_type='INGREDIENT_PAIR',severity='ORANGE',minimum_status='ORANGE',title='TEST ONLY third component pair',mechanism='Synthetic fixture relation',clinical_concern='No clinical claim',patient_plain_text='TEST ONLY no clinical recommendation',action_text='Do not use this test data clinically',evidence_quality='TEST_FIXTURE',review_status='APPROVED_FOR_V2',source_ids_json=js([SID]),created_at=DATE,updated_at=DATE)
        put(c,'rule_sources',rule_id='TEST-PAIR',source_id=SID,evidence_note='TEST ONLY invented relation')
        put(c,'rule_evidence',rule_id='TEST-PAIR',source_id=SID,source_locator='record:rules/TEST-PAIR',evidence_type='TEST_FIXTURE')
        put(c,'rule_applicability',rule_id='TEST-PAIR',jurisdiction_scope='GLOBAL',reviewer_kind='TEST_FIXTURE',review_reference='TEST-NOT-HUMAN',reviewed_at=DATE)
        put(c,'ingredient_pair_rules',rule_id='TEST-PAIR',left_ingredient_id='ING-3',right_ingredient_id='ING-5',pair_key='3:5')
        put(c,'id_ledger',entity_kind='RULE',stable_id='TEST-PAIR',compact_int_id=1,lifecycle='ACTIVE')
        # Reserved ID must survive every next snapshot even with no current entity.
        put(c,'id_ledger',entity_kind='INGREDIENT',stable_id='ING-retired',compact_int_id=100,lifecycle='RETIRED')

def change(path,fn):
    with sqlite3.connect(path) as c:
        fn(c)

def sql(statement,params=()):
    return lambda c:c.execute(statement,params)

def partial(c):
    c.execute("UPDATE product_ingredient_rows SET ingredient_id=NULL,mapping_status='UNMAPPED',mapping_review_reference=NULL,mapping_reviewed_at=NULL,mapping_source_id=NULL,mapping_source_locator=NULL WHERE component_id='A-2'")
    c.execute("DELETE FROM drug_ingredients WHERE drug_id='A' AND ingredient_id='ING-3'")
    c.execute("UPDATE drug_compact_index SET ingredient_int_ids_json='[1,2]' WHERE drug_id='A'")
    c.execute("UPDATE drugs SET active_ingredient_count=2,data_completeness='PARTIAL' WHERE drug_id='A'")
    c.execute("UPDATE product_composition SET composition_status='PARTIAL',review_status='PENDING',reviewer_kind='UNREVIEWED',review_reference=NULL,reviewed_at=NULL,completeness_note='Third active row unresolved; retained verbatim' WHERE drug_id='A'")

def count_looks_complete(c):
    c.execute("DELETE FROM product_ingredient_rows WHERE component_id='A-2'")
    c.execute("DELETE FROM drug_ingredients WHERE drug_id='A' AND ingredient_id='ING-3'")
    c.execute("UPDATE drug_compact_index SET ingredient_int_ids_json='[1,2]' WHERE drug_id='A'")
    c.execute("UPDATE drugs SET active_ingredient_count=2 WHERE drug_id='A'")
    c.execute("UPDATE product_composition SET expected_active_row_count=2,composition_status='PARTIAL',review_status='PENDING' WHERE drug_id='A'")

def coverage_claim(c):
    value=json.loads(c.execute('SELECT coverage_json FROM package_contract').fetchone()[0]); value['GLOBAL']['dose']['status']='REVIEWED_SCOPE'
    c.execute('UPDATE package_contract SET coverage_json=?',(js(value),))

def repeated(c):
    old=dict(zip([r[1] for r in c.execute('PRAGMA table_info(product_ingredient_rows)')],c.execute("SELECT * FROM product_ingredient_rows WHERE component_id='A-2'").fetchone()))
    old.update(component_id='A-3',source_order=3,strength_text='5 mg',strength_value=5,source_locator='record:products/A/row/3')
    put(c,'product_ingredient_rows',**old)
    c.execute("UPDATE product_composition SET expected_active_row_count=4 WHERE drug_id='A'")
    c.execute("UPDATE drug_ingredients SET strength_text='10 mg | 5 mg',strength_value=NULL,strength_unit=NULL WHERE drug_id='A' AND ingredient_id='ING-3'")

def excipient(c):
    put(c,'product_ingredient_rows',component_id='A-excipient',drug_id='A',source_order=10,ingredient_id='ING-5',name_as_listed='TEST excipient',role='EXCIPIENT',mapping_status='UNVERIFIED',source_id=SID,source_locator='record:products/A/excipient')

def add_class(c,with_proof):
    put(c,'classes',class_id='CLASS-X',class_int_id=1,class_name='TEST Class X',class_type='TEST',description='Synthetic class')
    put(c,'id_ledger',entity_kind='CLASS',stable_id='CLASS-X',compact_int_id=1,lifecycle='ACTIVE')
    put(c,'drug_class_memberships',drug_id='A',class_id='CLASS-X',source=SID,source_version='TEST-v1',evidence_quality='TEST_FIXTURE',mapping_method='TEST',review_status='APPROVED_FOR_V2')
    c.execute("UPDATE drug_compact_index SET class_int_ids_json='[1]' WHERE drug_id='A'")
    if with_proof:
        put(c,'class_membership_evidence',drug_id='A',class_id='CLASS-X',source_id=SID,source_locator='record:products/A/class/X',reviewer_kind='TEST_FIXTURE',review_reference='TEST-NOT-HUMAN',reviewed_at=DATE)

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    cases=[]
    def record(name,fn):
        try:
            detail=fn(); cases.append({'name':name,'status':'PASS','detail':detail})
        except Exception as e:
            cases.append({'name':name,'status':'FAIL','detail':f'{type(e).__name__}: {e}'})
    with tempfile.TemporaryDirectory(prefix='safemed-contract-') as tmp:
        base=Path(tmp)/'base.sqlite3'; fixture(base)
        record('synthetic_composed_snapshot_accept',lambda:validate(base,test_only=True))
        def variant(name,mutate,expected_error=None,accept=False,previous=False):
            path=Path(tmp)/(name+'.sqlite3'); shutil.copyfile(base,path); change(path,mutate)
            try:
                result=validate(path,test_only=True,previous=base if previous else None)
            except ContractError as e:
                if not accept and (expected_error is None or expected_error in str(e)): return str(e)
                raise
            if not accept: raise AssertionError('invalid package accepted')
            return result
        variants=[
            ('partial_unmapped_third_retained',partial,None,True),
            ('unmapped_third_false_complete',lambda c:(partial(c),c.execute("UPDATE drugs SET data_completeness='COMPLETE' WHERE drug_id='A'")),'incomplete composition',False),
            ('count_matches_but_full_review_absent',count_looks_complete,'incomplete composition',False),
            ('third_raw_row_deleted_expected_count',lambda c:(c.execute("DELETE FROM product_ingredient_rows WHERE component_id='A-2'"),c.execute("DELETE FROM drug_ingredients WHERE drug_id='A' AND ingredient_id='ING-3'"),c.execute("UPDATE drug_compact_index SET ingredient_int_ids_json='[1,2]' WHERE drug_id='A'"),c.execute("UPDATE drugs SET active_ingredient_count=2 WHERE drug_id='A'")),'expected active',False),
            ('unknown_role_false_complete',sql("UPDATE product_ingredient_rows SET role='UNKNOWN' WHERE component_id='A-2'"),'projection',False),
            ('unverified_mapping_false_complete',sql("UPDATE product_ingredient_rows SET mapping_status='UNVERIFIED' WHERE component_id='A-2'"),'projection',False),
            ('source_locator_missing',sql("UPDATE product_ingredient_rows SET source_locator=NULL WHERE component_id='A-2'"),'direct evidence',False),
            ('mapping_source_missing',sql("UPDATE product_ingredient_rows SET mapping_source_id=NULL,mapping_source_locator=NULL WHERE component_id='A-2'"),'direct evidence',False),
            ('composition_identity_source_missing',sql("DELETE FROM drug_source_links WHERE drug_id='A' AND purpose='COMPOSITION'"),'full product',False),
            ('official_portal_cannot_supply_rule_evidence',sql("UPDATE source_registry SET source_type='SOURCE_PORTAL'"),'unqualified source',False),
            ('commercial_rights_denied',sql("UPDATE source_rights SET commercial_use_allowed=0"),'rights not approved',False),
            ('mobile_redistribution_denied',sql("UPDATE source_rights SET mobile_redistribution_allowed=0"),'rights not approved',False),
            ('source_snapshot_checksum_changed',sql("UPDATE source_registry SET checksum=?",('b'*64,)),'inventory',False),
            ('schema_unknown',sql("UPDATE package_manifest SET schema_version='safemed-mobile-safety-v999'"),'unsupported',False),
            ('legacy_relabel_without_new_user_version',sql('PRAGMA user_version=2'),'unsupported',False),
            ('unknown_required_capability',sql("UPDATE package_contract SET required_capabilities_json='[\"invented-capability\"]'"),'capability',False),
            ('coverage_unsupported_dose_claim',coverage_claim,'unsupported coverage',False),
            ('coverage_missing',sql("UPDATE package_contract SET coverage_json='{}'"),'coverage',False),
            ('identity_country_unsupported',sql("UPDATE drug_product_identity SET jurisdiction='ZZ' WHERE drug_id='A'"),'full supported',False),
            ('identity_metadata_disagrees',sql("UPDATE drugs SET metadata_json='{}' WHERE drug_id='A'"),'mirror',False),
            ('canonical_compact_stale',sql("UPDATE drug_compact_index SET ingredient_int_ids_json='[1,2]' WHERE drug_id='A'"),'projection',False),
            ('canonical_wrong_id',sql("UPDATE drug_ingredients SET ingredient_int_id=4 WHERE drug_id='A' AND ingredient_id='ING-3'"),'projection',False),
            ('excipient_not_in_active_checks',excipient,None,True),
            ('repeated_canonical_preserves_raw_rows',repeated,None,True),
            ('class_mapping_requires_direct_review',lambda c:add_class(c,False),'class mapping evidence',False),
            ('class_mapping_reviewed',lambda c:add_class(c,True),None,True),
            ('rule_direct_evidence_missing',sql('DELETE FROM rule_evidence'),'citations',False),
            ('rule_join_missing',sql('DELETE FROM rule_sources'),'foreign key',False),
            ('conditional_active_rule_rejected',sql("UPDATE rule_applicability SET required_context_json='{\"renal\":true}'"),'future capability',False),
            ('market_specific_active_rule_rejected',sql("UPDATE rule_applicability SET jurisdiction_scope='MARKET_SPECIFIC',market_codes_json='[\"TW\"]'"),'future capability',False),
            ('legacy_active_rule_label_rejected',sql("UPDATE rules SET review_status='ACTIVE'"),'invalid review status',False),
            ('legacy_MVP_rule_label_rejected',sql("UPDATE rules SET review_status='APPROVED_FOR_MVP'"),'invalid review status',False),
            ('candidate_rule_kept_inactive',sql("UPDATE rules SET review_status='CANDIDATE_ONLY'"),None,True),
            ('unreviewed_rule_cannot_activate',sql("UPDATE rule_applicability SET reviewer_kind='AUTOMATED'"),'human review',False),
            ('minimum_status_cannot_weaken_rule',sql("UPDATE rules SET minimum_status='GREEN'"),'severity/status',False),
            ('pair_key_wrong',sql("UPDATE ingredient_pair_rules SET pair_key='1:5'"),'pair key',False),
            ('pair_index_missing',sql('DELETE FROM ingredient_pair_rules'),'runtime index',False),
            ('ledger_projection_changed',sql("UPDATE id_ledger SET compact_int_id=9 WHERE stable_id='ING-3'"),'projection',False),
            ('null_review_cannot_claim_complete',lambda c:(c.execute('PRAGMA ignore_check_constraints=ON'),c.execute("UPDATE product_composition SET review_reference=NULL WHERE drug_id='A'")),'human review',False),
            ('partial_identity_null_rejected_even_constraints_off',lambda c:(c.execute('PRAGMA ignore_check_constraints=ON'),c.execute("UPDATE drug_product_identity SET identifier_namespace=NULL WHERE drug_id='A'")),'full supported',False),
            ('mapping_review_null_rejected_even_constraints_off',lambda c:(c.execute('PRAGMA ignore_check_constraints=ON'),c.execute("UPDATE product_ingredient_rows SET mapping_review_reference=NULL WHERE component_id='A-2'")),'mapping review',False),
            ('ingredient_without_source',sql("DELETE FROM ingredient_sources WHERE ingredient_id='ING-3'"),'ingredient evidence',False),
            ('json_duplicate_capability',sql("UPDATE package_contract SET required_capabilities_json='[\"composition-v1\",\"composition-v1\"]'"),'duplicate',False),
            ('required_table_missing',sql('DROP TABLE class_membership_evidence'),'missing table',False),
            ('raw_strength_infinity',sql("UPDATE product_ingredient_rows SET strength_value=? WHERE component_id='A-2'",(float('inf'),)),'strength unit/value',False),
            ('source_homepage_not_direct_evidence',sql("UPDATE rule_evidence SET source_locator='https://example.invalid/'"),'direct record',False),
            ('missing_rule_scope',sql('DELETE FROM rule_applicability'),'explicit scope',False),
            ('timezone_missing',sql("UPDATE package_manifest SET created_at='2026-10-07'"),'date',False),
        ]
        for name,mutate,expected,accept in variants:
            record(name,lambda n=name,m=mutate,e=expected,a=accept:variant(n,m,e,a))
        def rejected_production():
            path=Path(tmp)/'production-rejection.sqlite3'; shutil.copyfile(base,path)
            change(path,sql("UPDATE package_manifest SET license_tier='professional'"))
            try:validate(path)
            except ContractError as e:
                assert 'test' in str(e).lower(); return str(e)
            raise AssertionError('test fixture accepted as production')
        record('test_fixture_rejected_without_flag',rejected_production)
        for name,mutate,expected in [
            ('update_sequence_increases',sql('UPDATE package_contract SET release_sequence=2'),None),
            ('update_sequence_replay',sql('UPDATE package_contract SET release_sequence=1'),'sequence'),
            ('tombstone_removed',lambda c:(c.execute('UPDATE package_contract SET release_sequence=2'),c.execute("DELETE FROM id_ledger WHERE stable_id='ING-retired'")),'tombstone'),
            ('product_identity_reused',lambda c:(c.execute('UPDATE package_contract SET release_sequence=2'),c.execute("UPDATE drug_product_identity SET local_product_id='OTHER' WHERE drug_id='A'"),c.execute("UPDATE drugs SET metadata_json=json_set(metadata_json,'$.safemed_product_identity.local_product_id','OTHER') WHERE drug_id='A'")),'stable product identity'),
            ('tombstone_reassigned',lambda c:(c.execute('UPDATE package_contract SET release_sequence=2'),c.execute("UPDATE id_ledger SET compact_int_id=101 WHERE stable_id='ING-retired'")),'stable ID'),
        ]:
            record(name,lambda n=name,m=mutate,e=expected:variant(n,m,e,e is None,previous=True))
        def full_composition_matching():
            with sqlite3.connect(base) as c:
                active=lambda did:{r[0] for r in c.execute("SELECT ingredient_id FROM product_ingredient_rows WHERE drug_id=? AND role='ACTIVE' AND mapping_status='VERIFIED'",(did,))}
                assert active('A') & active('SINGLE') == {'ING-3'}
                assert active('A') & active('B') == {'ING-3'}
                pairs={tuple(sorted((a,b))) for a in active('A') for b in active('C') if a!=b}
                matching={r[0] for r in c.execute('SELECT rule_id,left_ingredient_id,right_ingredient_id FROM ingredient_pair_rules') if tuple(sorted(r[1:])) in pairs}
                assert matching=={'TEST-PAIR'}
                # Regression contrast: first-only matching would miss both third-component outcomes.
                assert {'ING-1'} & active('SINGLE') == set()
                assert tuple(sorted(('ING-3','ING-5'))) not in {tuple(sorted(('ING-1',b))) for b in active('C')}
                return 'A third vs SINGLE, A third vs B second duplicate; A third vs C second pair found'
        record('third_component_compound_single_and_compound_pair',full_composition_matching)
        def same_brand_distinct():
            with sqlite3.connect(base) as c:
                rs=c.execute("SELECT d.drug_id,i.jurisdiction FROM drugs d JOIN drug_product_identity i USING(drug_id) WHERE display_name='TEST Same Brand'").fetchall()
                assert set(rs)=={('A','TW'),('SAME-NAME-US','US')}; return rs
        record('same_brand_different_markets_not_merged',same_brand_distinct)
        for name,statement in [
            ('sql_null_composition_review_rejected',"UPDATE product_composition SET review_reference=NULL WHERE drug_id='A'"),
            ('sql_null_mapping_review_rejected',"UPDATE product_ingredient_rows SET mapping_review_reference=NULL WHERE component_id='A-2'"),
            ('sql_partial_identity_null_rejected',"UPDATE drug_product_identity SET identifier_namespace=NULL WHERE drug_id='A'"),
            ('sql_role_invalid_rejected',"UPDATE product_ingredient_rows SET role='invented' WHERE component_id='A-2'"),
            ('sql_compact_zero_rejected',"UPDATE ingredients SET ingredient_int_id=0 WHERE ingredient_id='ING-3'"),
        ]:
            def ddl_reject(statement=statement):
                path=Path(tmp)/'sql-negative.sqlite3'; shutil.copyfile(base,path)
                try:change(path,sql(statement))
                except sqlite3.IntegrityError as e:return str(e)
                raise AssertionError('SQL constraint accepted invalid value')
            record(name,ddl_reject)
        shutil.copyfile(base,output/'TEST_ONLY_global_compound.sqlite3')
    report={'status':'PASS' if all(x['status']=='PASS' for x in cases) else 'FAIL','test_only':True,'clinical_validation':'NOT_PERFORMED','cases':cases,'passed':sum(x['status']=='PASS' for x in cases),'failed':sum(x['status']=='FAIL' for x in cases),'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'schema.sql',ROOT/'contract.json',ROOT/'validate_contract.py',ROOT/'test_contract.py']}}
    (output/'contract-test-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f"{report['status']}: {report['passed']} passed, {report['failed']} failed")
    for x in cases:
        if x['status']=='FAIL': print(x['name'],x['detail'])
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    raise SystemExit(run(parser.parse_args().output))
