#!/usr/bin/env python3
"""SafeMed contract gate; stdlib only. Fixture permission is explicit and never production approval."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT / 'contract.json').read_text())
SCHEMA = (ROOT / 'schema.sql').read_text()

class ContractError(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise ContractError(message)

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def stamp(value):
    try:
        return nonempty(value) and dt.datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except (ValueError, TypeError):
        return False

def https(value):
    try:
        u = urlparse(value)
        return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password
    except (ValueError, TypeError):
        return False

def parse(value, kind, label):
    def pairs(items):
        result = {}
        for key, val in items:
            require(key not in result, f'{label}: duplicate JSON key {key}')
            result[key] = val
        return result
    try:
        result = json.loads(value, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        require(isinstance(result, kind), f'{label}: wrong JSON type')
        return result
    except (ValueError, TypeError) as e:
        raise ContractError(f'{label}: invalid JSON ({e})') from e

def unique_list(value, kind, label):
    result = parse(value, list, label)
    require(all(type(x) is kind for x in result), f'{label}: invalid element type')
    require(len(set(result)) == len(result), f'{label}: duplicate entries')
    return result

def connect(path):
    p = Path(path).resolve()
    require(p.is_file(), 'database missing')
    require(p.stat().st_size <= 512 * 1024 * 1024, 'database exceeds contract size limit')
    con = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    return con

def rows(con, table):
    return [dict(row) for row in con.execute(f'SELECT * FROM "{table}"')]

def table_map(con, table, key):
    return {row[key]: row for row in rows(con, table)}

def verified_reviewer(kind, reference, date, test_only, label):
    allowed = ['PHARMACIST', 'PHYSICIAN'] + (['TEST_FIXTURE'] if test_only else [])
    require(kind in allowed and nonempty(reference) and stamp(date), f'{label}: human review/evidence missing')

def validate(path, *, test_only=False, previous=None):
    with connect(path) as con:
        try:
            return validate_connection(con, test_only=test_only, previous=previous)
        except sqlite3.Error as e:
            raise ContractError(f'SQLite: {e}') from e

def validate_connection(con, *, test_only=False, previous=None):
    require(con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'database integrity failed')
    require(not con.execute('PRAGMA foreign_key_check').fetchall(), 'foreign key check failed')
    require(con.execute('PRAGMA user_version').fetchone()[0] == CONTRACT['sqlite_user_version'], 'user_version unsupported')
    layout = sqlite3.connect(':memory:')
    layout.executescript(SCHEMA)
    actual_tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in CONTRACT['required_tables']:
        require(table in actual_tables, f'missing table {table}')
        expected = [tuple(r) for r in layout.execute(f'PRAGMA table_info("{table}")')]
        actual = [tuple(r) for r in con.execute(f'PRAGMA table_info("{table}")')]
        require(actual[:len(expected)] == expected, f'{table}: required field layout mismatch')
        expected_fk = [tuple(r) for r in layout.execute(f'PRAGMA foreign_key_list("{table}")')]
        actual_fk = [tuple(r) for r in con.execute(f'PRAGMA foreign_key_list("{table}")')]
        require(actual_fk == expected_fk, f'{table}: foreign key declarations mismatch')
    layout.close()
    manifests = rows(con, 'package_manifest')
    require(len(manifests) == 1, 'exactly one package_manifest required')
    m = manifests[0]
    require(m['schema_version'] == CONTRACT['schema_version'], 'schema_version unsupported')
    require(str(m['package_major_version']) == '2' and m['product_line'] == 'safemed_pro', 'product compatibility mismatch')
    require(m['requires_entitlement'] in [0,1] and (m['license_tier'] == 'professional' or (test_only and m['license_tier'] == 'testing')), 'paid product entitlement mismatch')
    require(2 in unique_list(m['compatible_app_major_versions'], int, 'app versions'), 'App major 2 absent')
    require(m['package_format'] == 'sqlite3+gzip' and m['quality_gate_result'] == 'PASS' and m['locked_regression_result'] == 'PASS', 'package gates not PASS')
    require(all(nonempty(m[k]) for k in ['package_id', 'data_version', 'rules_version']) and stamp(m['created_at']), 'manifest version/date missing')
    pc_rows = rows(con, 'package_contract')
    require(len(pc_rows) == 1, 'exactly one package_contract required')
    pc = pc_rows[0]
    require(pc['package_id'] == m['package_id'] and pc['contract_version'] == '1.0.0', 'contract identity mismatch')
    require(pc['core_namespace'] == CONTRACT['core_namespace'] and nonempty(pc['core_version']), 'core namespace/version mismatch')
    require(pc['snapshot_kind'] == 'COMPOSED_SNAPSHOT' and type(pc['release_sequence']) is int and pc['release_sequence'] > 0, 'snapshot/release invalid')
    markets = unique_list(pc['market_codes_json'], str, 'markets')
    require(markets and all(x in CONTRACT['iso_3166_1_alpha2'] for x in markets), 'markets must be ISO alpha2 countries')
    capabilities = unique_list(pc['required_capabilities_json'], str, 'capabilities')
    require(set(capabilities) == set(CONTRACT['required_capabilities']), 'required/unknown capability mismatch')
    coverage = parse(pc['coverage_json'], dict, 'coverage')
    require(set(coverage) == {'GLOBAL', *markets}, 'coverage must describe GLOBAL and every market')
    executable = set(CONTRACT['coverage_domains'][:5])
    for market, domains in coverage.items():
        require(isinstance(domains, dict) and set(domains) == set(CONTRACT['coverage_domains']), f'{market}: coverage domains missing')
        for domain, item in domains.items():
            require(isinstance(item, dict) and set(item) == {'status', 'scope', 'limitations'}, f'{market}/{domain}: coverage shape invalid')
            require(item['status'] in CONTRACT['coverage_states'] and nonempty(item['scope']) and nonempty(item['limitations']), f'{market}/{domain}: coverage description missing')
            require(domain in executable or item['status'] == 'NONE', f'{domain}: runtime unsupported coverage claim')
            require(market == 'GLOBAL' or item['status'] != 'REVIEWED_SCOPE', f'{market}: market-specific runtime not supported')
    sources = table_map(con, 'source_registry', 'source_id')
    rights = table_map(con, 'source_rights', 'source_id')
    require(sources and set(rights) == set(sources), 'all source snapshots require rights records')
    for sid, src in sources.items():
        require(nonempty(sid) and nonempty(src['version_label']) and nonempty(src['source_name']) and stamp(src['retrieved_at']), f'{sid}: snapshot identity/date missing')
        require(https(src['source_url']) and re.fullmatch(r'[0-9a-f]{64}', src['checksum'] or ''), f'{sid}: HTTPS or SHA256 missing')
        if src['source_type'] == 'TEST_FIXTURE':
            require(test_only, f'{sid}: test source prohibited in production')
        else:
            require(src['source_type'] in ['OFFICIAL_LABEL', 'OFFICIAL_REGULATOR', 'LICENSED_REVIEWED_DB', 'REVIEWED_GUIDELINE', 'PEER_REVIEWED'], f'{sid}: unqualified source type')
        r = rights[sid]
        require(r['commercial_use_allowed'] == 1 and r['mobile_redistribution_allowed'] == 1 and r['review_status'] == 'APPROVED', f'{sid}: redistribution/commercial rights not approved')
        require(https(r['license_evidence_url']) and nonempty(r['attribution_text']) and nonempty(r['review_reference']) and stamp(r['reviewed_at']), f'{sid}: rights audit missing')
    snapshots = parse(m['source_snapshots'], list, 'source snapshots')
    require(all(isinstance(x, dict) and set(x) == {'source_id', 'version_label', 'checksum'} for x in snapshots), 'snapshot inventory shape invalid')
    require(len(snapshots) == len(sources) and {x['source_id'] for x in snapshots} == set(sources), 'snapshot inventory mismatch')
    for x in snapshots:
        require(all(x[k] == sources[x['source_id']][k] for k in x), 'snapshot inventory version/checksum mismatch')
    def evidence(sid, locator, label):
        require(sid in sources and nonempty(locator), f'{label}: direct evidence missing')
        require((locator.startswith('record:') and len(locator[7:].strip()) >= 3) or (https(locator) and urlparse(locator).path not in ['', '/']), f'{label}: direct record/section locator required')
    ingredients = table_map(con, 'ingredients', 'ingredient_id')
    drugs = table_map(con, 'drugs', 'drug_id')
    classes = table_map(con, 'classes', 'class_id')
    rules = table_map(con, 'rules', 'rule_id')
    require(ingredients and drugs, 'empty drug/ingredient dataset')
    integer_maps = {}
    for kind, records, field in [('INGREDIENT', ingredients, 'ingredient_int_id'), ('CLASS', classes, 'class_int_id'), ('RULE', rules, 'rule_int_id')]:
        ids = [r[field] for r in records.values()]
        require(all(type(x) is int and 1 <= x <= 2147483647 for x in ids) and len(set(ids)) == len(ids), f'{kind}: compact IDs invalid')
        integer_maps[kind] = {key: val[field] for key, val in records.items()}
    ingredient_evidence = rows(con, 'ingredient_sources')
    require({r['ingredient_id'] for r in ingredient_evidence} == set(ingredients), 'canonical ingredient evidence missing')
    for r in ingredient_evidence:
        evidence(r['source_id'], r['source_locator'], 'ingredient')
    for r in ingredients.values():
        require(nonempty(r['canonical_name']) and nonempty(r['normalized_name']), 'canonical ingredient name missing')
        unique_list(r['synonyms_json'], str, 'ingredient synonyms')
        unique_list(r['atc_seed_codes_json'], str, 'ingredient ATC seeds')
    ledger_rows = rows(con, 'id_ledger')
    ledger = {(r['entity_kind'], r['stable_id']): r for r in ledger_rows}
    expected_active = {}
    for kind, records in [('INGREDIENT', ingredients), ('CLASS', classes), ('RULE', rules), ('DRUG', drugs)]:
        for stable in records:
            expected_active[(kind, stable)] = integer_maps.get(kind, {}).get(stable)
    require({key for key, r in ledger.items() if r['lifecycle'] == 'ACTIVE'} == set(expected_active), 'active ID ledger mismatch')
    allocated = set()
    for key, r in ledger.items():
        require(r['entity_kind'] in ['INGREDIENT', 'CLASS', 'RULE', 'DRUG'] and nonempty(r['stable_id']) and len(r['stable_id'].encode()) <= 200, 'ledger stable ID invalid')
        require(r['lifecycle'] in ['ACTIVE', 'RETIRED'], 'ledger lifecycle invalid')
        if r['entity_kind'] == 'DRUG':
            require(r['compact_int_id'] is None, 'DRUG has no compact ID in v1')
        else:
            number = r['compact_int_id']
            require(type(number) is int and 1 <= number <= 2147483647 and (r['entity_kind'], number) not in allocated, 'ledger compact ID invalid/reused')
            allocated.add((r['entity_kind'], number))
        if key in expected_active:
            require(r['compact_int_id'] == expected_active[key], 'ledger compact projection mismatch')
    if previous:
        validate(previous, test_only=test_only)
        with connect(previous) as old:
            old_pc = rows(old, 'package_contract')
            require(len(old_pc) == 1 and old_pc[0]['core_namespace'] == pc['core_namespace'], 'previous core namespace mismatch')
            require(pc['release_sequence'] > old_pc[0]['release_sequence'], 'release sequence must increase for update')
            for old_r in rows(old, 'id_ledger'):
                key = (old_r['entity_kind'], old_r['stable_id'])
                require(key in ledger and ledger[key]['compact_int_id'] == old_r['compact_int_id'], 'stable ID changed or tombstone removed')
                require(old_r['lifecycle'] != 'RETIRED' or ledger[key]['lifecycle'] == 'RETIRED', 'retired ID resurrected')
            current_identity = table_map(con, 'drug_product_identity', 'drug_id')
            for did, old_identity in table_map(old, 'drug_product_identity', 'drug_id').items():
                if did in current_identity and old_identity['jurisdiction'] is not None:
                    require(all(old_identity[k] == current_identity[did][k] for k in ['jurisdiction','identifier_namespace','local_product_id']), f'{did}: stable product identity changed')
            for sid, src in table_map(old, 'source_registry', 'source_id').items():
                if sid in sources:
                    require(src == sources[sid], f'{sid}: immutable source snapshot changed')
    identities = table_map(con, 'drug_product_identity', 'drug_id')
    compositions = table_map(con, 'product_composition', 'drug_id')
    indices = table_map(con, 'drug_compact_index', 'drug_id')
    require(set(identities) == set(drugs) == set(compositions) == set(indices), 'every drug requires identity/composition/compact rows')
    components = rows(con, 'product_ingredient_rows')
    projection = rows(con, 'drug_ingredients')
    links = rows(con, 'drug_source_links')
    memberships = rows(con, 'drug_class_memberships')
    class_evidence = rows(con, 'class_membership_evidence')
    for r in links:
        require(r['purpose'] in ['IDENTITY', 'COMPOSITION', 'LABEL'], 'drug source purpose invalid')
        evidence(r['source_id'], r['source_locator'], 'drug')
    seen_identity = set()
    complete_count = 0
    for did, drug in drugs.items():
        require(nonempty(drug['display_name']) and drug['data_completeness'] in ['COMPLETE', 'PARTIAL', 'UNKNOWN'] and drug['is_combination'] in [-1, 0, 1], f'{did}: product flags invalid')
        identity = identities[did]
        triple = tuple(identity[k] for k in ['jurisdiction', 'identifier_namespace', 'local_product_id'])
        unknown = all(x is None for x in triple)
        if not unknown:
            require(triple[0] in markets and all(nonempty(x) and len(x.encode()) <= 200 for x in triple), f'{did}: identity must be a full supported-market triple')
            require(triple not in seen_identity, f'{did}: local identity duplicate')
            seen_identity.add(triple)
        require(identity['prescription_status'] in CONTRACT['prescription_states'] and identity['market_status'] in ['ACTIVE', 'ARCHIVED', 'UNKNOWN'], 'product market/prescription flag invalid')
        metadata = parse(drug['metadata_json'], dict, f'{did} metadata')
        local_links = [r for r in links if r['drug_id'] == did]
        mirror = metadata.get('safemed_product_identity')
        if unknown:
            require(mirror is None, f'{did}: unknown identity cannot have a metadata identity')
        else:
            require(isinstance(mirror, dict) and mirror.get('contract_version') == 'safemed-product-identity-v1', f'{did}: identity mirror missing')
            require(tuple(mirror.get(k) for k in ['jurisdiction', 'identifier_namespace', 'local_product_id']) == triple, f'{did}: identity mirror mismatch')
            expected_sources = {r['source_id'] for r in local_links if r['purpose'] in ['IDENTITY', 'COMPOSITION']}
            require(isinstance(mirror.get('source_ids'), list) and len(mirror['source_ids']) <= 32 and all(isinstance(x,str) and len(x.encode())<=200 for x in mirror['source_ids']) and len(mirror['source_ids']) == len(set(mirror['source_ids'])) and set(mirror['source_ids']) == expected_sources and expected_sources, f'{did}: identity source mirror mismatch')
        local_components = sorted([r for r in components if r['drug_id'] == did], key=lambda r:r['source_order'])
        require(len({r['source_order'] for r in local_components}) == len(local_components), f'{did}: repeated source order')
        active_groups = {}
        for r in local_components:
            require(nonempty(r['component_id']) and nonempty(r['name_as_listed']) and r['role'] in CONTRACT['ingredient_roles'] and r['mapping_status'] in CONTRACT['mapping_states'], f'{did}: raw ingredient invalid')
            require(type(r['source_order']) is int and r['source_order'] >= 0, f'{did}: source order invalid')
            if r['source_id'] is not None or r['source_locator'] is not None:
                evidence(r['source_id'], r['source_locator'], f'{did} component')
            if r['strength_value'] is not None:
                require(isinstance(r['strength_value'], (int,float)) and math.isfinite(r['strength_value']) and r['strength_value'] >= 0 and nonempty(r['strength_unit']), f'{did}: strength unit/value invalid')
            if r['mapping_status'] == 'UNMAPPED':
                require(r['ingredient_id'] is None, f'{did}: unmapped component carries canonical ID')
            if r['mapping_status'] == 'VERIFIED':
                require(r['ingredient_id'] in ingredients and nonempty(r['mapping_review_reference']) and stamp(r['mapping_reviewed_at']), f'{did}: ingredient mapping review missing')
                evidence(r['source_id'], r['source_locator'], f'{did} mapped component')
                evidence(r['mapping_source_id'], r['mapping_source_locator'], f'{did} mapping')
                if r['role'] == 'ACTIVE':
                    active_groups.setdefault(r['ingredient_id'], []).append(r)
        canon = {r['ingredient_id']: r for r in projection if r['drug_id'] == did}
        require(set(canon) == set(active_groups), f'{did}: active canonical projection mismatch')
        for iid, rs in active_groups.items():
            projected = canon[iid]
            joined = ' | '.join(r['strength_text'] for r in rs if nonempty(r['strength_text'])) or None
            require(projected['role'] == 'ACTIVE' and projected['ingredient_int_id'] == ingredients[iid]['ingredient_int_id'], f'{did}: role/compact ID projection mismatch')
            require(projected['ingredient_name_as_listed'] == rs[0]['name_as_listed'] and projected['strength_text'] == joined, f'{did}: raw text projection mismatch')
            require(projected['strength_value'] == (rs[0]['strength_value'] if len(rs)==1 else None) and projected['strength_unit'] == (rs[0]['strength_unit'] if len(rs)==1 else None), f'{did}: repeated moiety dose must not be inferred')
            require(projected['source'] == rs[0]['source_id'] and projected['source_version'] == sources[rs[0]['source_id']]['version_label'] and projected['confidence'] == 1, f'{did}: compatibility source projection mismatch')
        ints = unique_list(indices[did]['ingredient_int_ids_json'], int, f'{did} compact ingredients')
        require(ints == sorted(ingredients[iid]['ingredient_int_id'] for iid in active_groups), f'{did}: compact ingredient projection mismatch')
        class_ids = {r['class_id'] for r in memberships if r['drug_id'] == did}
        compact_classes = unique_list(indices[did]['class_int_ids_json'], int, f'{did} compact classes')
        require(compact_classes == sorted(classes[cid]['class_int_id'] for cid in class_ids), f'{did}: compact class projection mismatch')
        for membership in [r for r in memberships if r['drug_id'] == did]:
            require(membership['review_status'] == 'APPROVED_FOR_V2', f'{did}: unreviewed class mapping')
            proof = [r for r in class_evidence if r['drug_id']==did and r['class_id']==membership['class_id']]
            require(proof, f'{did}: class mapping evidence missing')
            for r in proof:
                evidence(r['source_id'],r['source_locator'],f'{did} class')
                verified_reviewer(r['reviewer_kind'],r['review_reference'],r['reviewed_at'],test_only,f'{did} class')
        require(drug['active_ingredient_count'] == len(active_groups), f'{did}: active count is distinct verified canonical IDs')
        composition = compositions[did]
        require(composition['review_status'] in ['APPROVED','PENDING','REJECTED'] and composition['reviewer_kind'] in ['PHARMACIST','PHYSICIAN','AUTOMATED','UNREVIEWED','TEST_FIXTURE'], f'{did}: composition review flags invalid')
        expected_count = composition['expected_active_row_count']
        require(expected_count is None or (type(expected_count) is int and expected_count >= 0), f'{did}: expected active count invalid')
        require(composition['composition_status'] in CONTRACT['composition_states'] and nonempty(composition['completeness_note']), f'{did}: composition state/note missing')
        require(test_only or composition['reviewer_kind'] != 'TEST_FIXTURE', 'test composition prohibited in production')
        if composition['composition_status'] == 'VERIFIED_COMPLETE':
            complete_count += 1
            require(composition['review_status'] == 'APPROVED', f'{did}: composition review not approved')
            verified_reviewer(composition['reviewer_kind'],composition['review_reference'],composition['reviewed_at'],test_only,f'{did} composition')
            require(not unknown and {'IDENTITY','COMPOSITION'} <= {r['purpose'] for r in local_links}, f'{did}: full product identity/composition evidence missing')
            require(local_components and active_groups and all(r['role'] != 'UNKNOWN' and (r['role'] != 'ACTIVE' or r['mapping_status']=='VERIFIED') and r['source_id'] in sources and nonempty(r['source_locator']) for r in local_components), f'{did}: unknown/unverified/raw evidence gap in complete product')
            raw_active = sum(r['role']=='ACTIVE' for r in local_components)
            expected = composition['expected_active_row_count']
            require(expected is None or (type(expected) is int and expected == raw_active), f'{did}: expected active raw row count mismatch')
            require(drug['data_completeness'] == 'COMPLETE' and drug['is_combination'] == int(len(active_groups)>1), f'{did}: complete/combination flags inconsistent')
        else:
            require(drug['data_completeness'] != 'COMPLETE', f'{did}: incomplete composition cannot be COMPLETE')
    source_join = rows(con,'rule_sources')
    proofs = rows(con,'rule_evidence')
    scopes = table_map(con,'rule_applicability','rule_id')
    require(set(scopes) == set(rules), 'every rule needs explicit scope')
    for rid, rule in rules.items():
        require(nonempty(rule['rule_code']) and nonempty(rule['patient_plain_text']) and nonempty(rule['action_text']), f'{rid}: rule text missing')
        declared = unique_list(rule['source_ids_json'],str,f'{rid} source IDs')
        joined = {r['source_id'] for r in source_join if r['rule_id']==rid}
        require(set(declared)==joined and joined, f'{rid}: rule source join mismatch')
        rule_proofs = [r for r in proofs if r['rule_id']==rid]
        require({r['source_id'] for r in rule_proofs} == joined, f'{rid}: direct rule citations missing')
        for r in rule_proofs:
            evidence(r['source_id'],r['source_locator'],rid)
            require(r['evidence_type'] in ['OFFICIAL_LABEL','LICENSED_REVIEWED_DB','REVIEWED_GUIDELINE','PEER_REVIEWED','TEST_FIXTURE'], f'{rid}: evidence type invalid')
            require(test_only or r['evidence_type'] != 'TEST_FIXTURE', 'test evidence prohibited in production')
        scope = scopes[rid]
        require(scope['jurisdiction_scope'] in ['GLOBAL','MARKET_SPECIFIC'] and scope['reviewer_kind'] in ['PHARMACIST','PHYSICIAN','AUTOMATED','UNREVIEWED','TEST_FIXTURE'], f'{rid}: scope/reviewer flags invalid')
        require(test_only or scope['reviewer_kind']!='TEST_FIXTURE', 'test rule review prohibited in production')
        markets_rule = unique_list(scope['market_codes_json'],str,f'{rid} markets')
        context = parse(scope['required_context_json'],dict,f'{rid} context')
        require(set(markets_rule) <= set(markets), f'{rid}: scope outside package markets')
        if rule['review_status'] == 'APPROVED_FOR_V2':
            domain_by_type = {'INGREDIENT_PAIR':'ingredient_pair_interaction','CLASS_PAIR':'class_pair_interaction','THERAPEUTIC_DUPLICATE':'therapeutic_duplicate','MULTI_CLASS_PATTERN':'multi_class_pattern'}
            require(rule['rule_type'] in domain_by_type and coverage['GLOBAL'][domain_by_type[rule['rule_type']]]['status'] != 'NONE', f'{rid}: active rule contradicts coverage')
            verified_reviewer(scope['reviewer_kind'],scope['review_reference'],scope['reviewed_at'],test_only,rid)
            require(scope['jurisdiction_scope']=='GLOBAL' and not markets_rule and not context, f'{rid}: active scoped/conditional rule requires future capability')
            require(rule['evidence_quality'] in ['OFFICIAL', 'HIGH', 'REVIEWED', 'TEST_FIXTURE'] and (test_only or rule['evidence_quality']!='TEST_FIXTURE'), f'{rid}: active rule evidence quality invalid')
            require(rule['minimum_status'] == rule['severity'] and rule['severity'] in ['BLUE','ORANGE','RED'], f'{rid}: active rule severity/status invalid')
        else:
            require(rule['review_status'] in ['CANDIDATE_ONLY','PENDING_REVIEW','REJECTED'], f'{rid}: invalid review status')
    type_tables = [('ingredient_pair_rules','INGREDIENT_PAIR'), ('class_pair_rules','CLASS_PAIR'), ('therapeutic_duplicate_rules','THERAPEUTIC_DUPLICATE'), ('multi_class_pattern_rules','MULTI_CLASS_PATTERN')]
    typed = {rid:set() for rid in rules}
    for table, kind in type_tables:
        for r in rows(con,table):
            rid=r['rule_id']; typed[rid].add(kind)
            require(rules[rid]['rule_type']==kind, f'{rid}: rule type/index mismatch')
            if table in ['ingredient_pair_rules','class_pair_rules']:
                prefix='ingredient' if table=='ingredient_pair_rules' else 'class'
                mapping = integer_maps['INGREDIENT' if prefix=='ingredient' else 'CLASS']
                left=mapping[r[f'left_{prefix}_id']]; right=mapping[r[f'right_{prefix}_id']]
                require(left != right and r['pair_key']==f'{min(left,right)}:{max(left,right)}', f'{rid}: pair key invalid')
            if table=='multi_class_pattern_rules':
                required = unique_list(r['required_class_ids_json'],str,f'{rid} required classes')
                optional = unique_list(r['optional_context_class_ids_json'],str,f'{rid} optional classes')
                require(len(required)>=2 and set(required+optional)<=set(classes) and r['min_distinct_drugs']>=2, f'{rid}: pattern invalid')
                require(not optional or rules[rid]['review_status']!='APPROVED_FOR_V2', f'{rid}: conditional pattern requires future capability')
    require(all(len(typed[rid])==1 for rid in rules), 'every rule must have exactly one supported runtime index')
    for alias in rows(con,'drug_aliases'):
        require(nonempty(alias['alias_id']) and nonempty(alias['alias']) and nonempty(alias['normalized_alias']) and nonempty(alias['language']) and math.isfinite(alias['confidence']) and 0 <= alias['confidence'] <= 1, 'drug alias fields invalid')
    for conflict in rows(con,'normalization_conflicts'):
        conflicted = unique_list(conflict['drug_ids_json'], str, 'conflict drug IDs')
        require(len(conflicted) >= 2 and set(conflicted) <= set(drugs), 'normalization conflict must name existing distinct products')
        parse(conflict['ingredient_signatures_json'], (dict,list), 'conflict ingredient signatures')
        require(nonempty(conflict['recommended_user_action']), 'normalization conflict action missing')
    for candidate in rows(con,'herb_western_candidate_rules'):
        require(candidate['candidate_status']=='CANDIDATE_ONLY' and candidate['activation_gate']=='NOT_RUNTIME_ACTIVE', 'herb candidate must not activate')
    # Coverage describes reviewed limitations, never an all-drugs/zero-risk guarantee.
    return {'schema_version':m['schema_version'],'contract_version':pc['contract_version'],'test_only':test_only,'drug_count':len(drugs),'verified_complete_count':complete_count,'ingredient_count':len(ingredients),'rule_count':len(rules),'markets':markets,'release_sequence':pc['release_sequence']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    parser.add_argument('--test-only',action='store_true')
    parser.add_argument('--previous',type=Path)
    args=parser.parse_args()
    try:
        result=validate(args.database,test_only=args.test_only,previous=args.previous)
        print(json.dumps({'status':'PASS','database_sha256':hashlib.sha256(args.database.read_bytes()).hexdigest(),**result},ensure_ascii=False,indent=2))
    except ContractError as e:
        print(json.dumps({'status':'FAIL','reason':str(e)},ensure_ascii=False))
        raise SystemExit(1)
if __name__=='__main__': main()
