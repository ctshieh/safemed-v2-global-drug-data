-- SafeMed global/compound contract 1.0.0. Frozen 2026-10-07.
-- New schema identity; never relabel a legacy package. No patient data.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 20100;

CREATE TABLE package_manifest (
    package_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    package_major_version TEXT NOT NULL,
    product_line TEXT NOT NULL,
    license_tier TEXT NOT NULL,
    requires_entitlement INTEGER NOT NULL,
    compatible_app_major_versions TEXT NOT NULL,
    data_version TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    package_format TEXT NOT NULL,
    source_snapshots TEXT NOT NULL DEFAULT '[]',
    quality_gate_result TEXT NOT NULL,
    locked_regression_result TEXT NOT NULL
);

CREATE TABLE ingredients (
    ingredient_id TEXT PRIMARY KEY,
    ingredient_int_id INTEGER NOT NULL UNIQUE CHECK (ingredient_int_id BETWEEN 1 AND 2147483647),
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    rxnorm_ingredient_rxcui TEXT,
    atc_seed_codes_json TEXT NOT NULL DEFAULT '[]',
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL
);

CREATE TABLE drugs (
    drug_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    chinese_name TEXT,
    english_name TEXT,
    nhi_code TEXT,
    tfda_license_no TEXT,
    rxnorm_rxcui TEXT,
    atc_codes_json TEXT NOT NULL DEFAULT '[]',
    ahfs_codes_json TEXT NOT NULL DEFAULT '[]',
    dosage_form TEXT,
    route TEXT,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL,
    data_completeness TEXT NOT NULL,
    is_combination INTEGER NOT NULL CHECK (is_combination IN (-1, 0, 1)),
    active_ingredient_count INTEGER NOT NULL CHECK (active_ingredient_count >= 0),
    safety_classes_json TEXT NOT NULL DEFAULT '[]',
    therapeutic_classes_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE drug_ingredients (
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    ingredient_int_id INTEGER NOT NULL,
    ingredient_name_as_listed TEXT NOT NULL,
    ingredient_code_as_listed TEXT,
    strength_text TEXT,
    strength_value REAL,
    strength_unit TEXT,
    role TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (drug_id, ingredient_id)
);

CREATE TABLE drug_aliases (
    alias_id TEXT PRIMARY KEY,
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    ambiguity_group_id TEXT
);

CREATE TABLE normalization_conflicts (
    conflict_id TEXT PRIMARY KEY,
    normalized_alias TEXT NOT NULL,
    drug_ids_json TEXT NOT NULL,
    ingredient_signatures_json TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    recommended_user_action TEXT NOT NULL
);

CREATE TABLE classes (
    class_id TEXT PRIMARY KEY,
    class_int_id INTEGER NOT NULL UNIQUE CHECK (class_int_id BETWEEN 1 AND 2147483647),
    class_name TEXT NOT NULL,
    class_type TEXT NOT NULL,
    parent_class_id TEXT,
    description TEXT NOT NULL
);

CREATE TABLE drug_class_memberships (
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    class_id TEXT NOT NULL REFERENCES classes(class_id),
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL,
    mapping_method TEXT NOT NULL,
    review_status TEXT NOT NULL,
    PRIMARY KEY (drug_id, class_id)
);

CREATE TABLE drug_compact_index (
    drug_id TEXT PRIMARY KEY REFERENCES drugs(drug_id),
    ingredient_int_ids_json TEXT NOT NULL,
    class_int_ids_json TEXT NOT NULL
);

CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY,
    rule_int_id INTEGER NOT NULL UNIQUE CHECK (rule_int_id BETWEEN 1 AND 2147483647),
    rule_code TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    minimum_status TEXT NOT NULL,
    title TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    clinical_concern TEXT NOT NULL,
    patient_plain_text TEXT NOT NULL,
    action_text TEXT NOT NULL,
    watch_for_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    review_status TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE ingredient_pair_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    left_ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    right_ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    pair_key TEXT NOT NULL,
    PRIMARY KEY (rule_id, pair_key)
);

CREATE TABLE class_pair_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    left_class_id TEXT NOT NULL REFERENCES classes(class_id),
    right_class_id TEXT NOT NULL REFERENCES classes(class_id),
    pair_key TEXT NOT NULL,
    PRIMARY KEY (rule_id, pair_key)
);

CREATE TABLE therapeutic_duplicate_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    duplicate_group_class_id TEXT NOT NULL REFERENCES classes(class_id),
    severity_if_same_ingredient TEXT NOT NULL,
    severity_if_same_class TEXT NOT NULL,
    PRIMARY KEY (rule_id, duplicate_group_class_id)
);

CREATE TABLE multi_class_pattern_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    required_class_ids_json TEXT NOT NULL,
    optional_context_class_ids_json TEXT NOT NULL DEFAULT '[]',
    min_distinct_drugs INTEGER NOT NULL,
    severity TEXT NOT NULL,
    PRIMARY KEY (rule_id)
);

CREATE TABLE source_registry (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    version_label TEXT NOT NULL,
    license_note TEXT NOT NULL,
    source_type TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    checksum TEXT
);

CREATE TABLE rule_sources (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    evidence_note TEXT NOT NULL,
    PRIMARY KEY (rule_id, source_id)
);

CREATE TABLE herbs (
    herb_id TEXT PRIMARY KEY,
    herb_int_id INTEGER NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    pinyin_name TEXT,
    normalized_name TEXT NOT NULL,
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    data_completeness TEXT NOT NULL
);

CREATE TABLE herb_western_candidate_rules (
    candidate_id TEXT PRIMARY KEY,
    herb_id TEXT NOT NULL REFERENCES herbs(herb_id),
    western_target_type TEXT NOT NULL,
    western_target_id TEXT NOT NULL,
    concern TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    suggested_runtime_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    activation_gate TEXT NOT NULL,
    patient_plain_text_draft TEXT NOT NULL,
    action_text_draft TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    review_notes TEXT NOT NULL
);

CREATE INDEX idx_drug_aliases_normalized ON drug_aliases(normalized_alias);
CREATE INDEX idx_drug_ingredients_drug ON drug_ingredients(drug_id);
CREATE INDEX idx_drug_class_memberships_drug ON drug_class_memberships(drug_id);
CREATE INDEX idx_ingredient_pair_rules_pair ON ingredient_pair_rules(pair_key);
CREATE INDEX idx_class_pair_rules_pair ON class_pair_rules(pair_key);

-- Additive companion tables preserve the existing drug/rule indices and raw fields.
CREATE TABLE package_contract (
    package_id TEXT PRIMARY KEY REFERENCES package_manifest(package_id),
    contract_version TEXT NOT NULL CHECK (contract_version = '1.0.0'),
    core_namespace TEXT NOT NULL CHECK (core_namespace = 'safemed-global-core-v1'),
    core_version TEXT NOT NULL,
    release_sequence INTEGER NOT NULL CHECK (release_sequence > 0),
    snapshot_kind TEXT NOT NULL CHECK (snapshot_kind = 'COMPOSED_SNAPSHOT'),
    market_codes_json TEXT NOT NULL,
    required_capabilities_json TEXT NOT NULL,
    coverage_json TEXT NOT NULL
);

-- IDs refer to an immutable source snapshot, not a website or mutable feed name.
CREATE TABLE source_rights (
    source_id TEXT PRIMARY KEY REFERENCES source_registry(source_id),
    commercial_use_allowed INTEGER NOT NULL CHECK (commercial_use_allowed IN (0,1)),
    mobile_redistribution_allowed INTEGER NOT NULL CHECK (mobile_redistribution_allowed IN (0,1)),
    license_evidence_url TEXT,
    attribution_text TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('APPROVED','PENDING','DENIED')),
    review_reference TEXT,
    reviewed_at TEXT
);

CREATE TABLE drug_product_identity (
    drug_id TEXT PRIMARY KEY REFERENCES drugs(drug_id),
    jurisdiction TEXT,
    identifier_namespace TEXT,
    local_product_id TEXT,
    market_status TEXT NOT NULL CHECK (market_status IN ('ACTIVE','ARCHIVED','UNKNOWN')),
    prescription_status TEXT NOT NULL CHECK (prescription_status IN ('RX','OTC','UNKNOWN')),
    CHECK ((jurisdiction IS NULL AND identifier_namespace IS NULL AND local_product_id IS NULL)
        OR (jurisdiction IS NOT NULL AND identifier_namespace IS NOT NULL AND local_product_id IS NOT NULL
            AND length(jurisdiction)=2 AND jurisdiction=upper(jurisdiction)
            AND length(trim(identifier_namespace))>0 AND length(trim(local_product_id))>0)),
    UNIQUE (jurisdiction, identifier_namespace, local_product_id)
);

CREATE TABLE drug_source_links (
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    purpose TEXT NOT NULL CHECK (purpose IN ('IDENTITY','COMPOSITION','LABEL')),
    source_locator TEXT NOT NULL CHECK (length(trim(source_locator))>0),
    PRIMARY KEY (drug_id, source_id, purpose, source_locator)
);

CREATE TABLE ingredient_sources (
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    source_locator TEXT NOT NULL CHECK (length(trim(source_locator))>0),
    PRIMARY KEY (ingredient_id, source_id, source_locator)
);

-- Raw label rows survive even if canonical mapping is missing; do not discard a third ingredient.
CREATE TABLE product_ingredient_rows (
    component_id TEXT PRIMARY KEY,
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    source_order INTEGER NOT NULL CHECK (source_order >= 0),
    ingredient_id TEXT REFERENCES ingredients(ingredient_id),
    name_as_listed TEXT NOT NULL CHECK (length(trim(name_as_listed))>0),
    role TEXT NOT NULL CHECK (role IN ('ACTIVE','EXCIPIENT','UNKNOWN')),
    strength_text TEXT,
    strength_value REAL CHECK (strength_value >= 0),
    strength_unit TEXT,
    basis_text TEXT,
    mapping_status TEXT NOT NULL CHECK (mapping_status IN ('VERIFIED','UNVERIFIED','UNMAPPED','CONFLICT')),
    source_id TEXT REFERENCES source_registry(source_id),
    source_locator TEXT,
    mapping_source_id TEXT REFERENCES source_registry(source_id),
    mapping_source_locator TEXT,
    mapping_review_reference TEXT,
    mapping_reviewed_at TEXT,
    CHECK (mapping_status != 'VERIFIED' OR (ingredient_id IS NOT NULL
        AND mapping_review_reference IS NOT NULL AND length(trim(mapping_review_reference))>0 AND mapping_reviewed_at IS NOT NULL)),
    UNIQUE (drug_id, source_order)
);
CREATE INDEX idx_product_ingredient_rows_drug ON product_ingredient_rows(drug_id);

CREATE TABLE product_composition (
    drug_id TEXT PRIMARY KEY REFERENCES drugs(drug_id),
    composition_status TEXT NOT NULL CHECK (composition_status IN ('VERIFIED_COMPLETE','PARTIAL','UNKNOWN','CONFLICT')),
    expected_active_row_count INTEGER CHECK (expected_active_row_count >= 0),
    review_status TEXT NOT NULL CHECK (review_status IN ('APPROVED','PENDING','REJECTED')),
    reviewer_kind TEXT NOT NULL CHECK (reviewer_kind IN ('PHARMACIST','PHYSICIAN','AUTOMATED','UNREVIEWED','TEST_FIXTURE')),
    review_reference TEXT,
    reviewed_at TEXT,
    completeness_note TEXT NOT NULL,
    CHECK (composition_status != 'VERIFIED_COMPLETE' OR (review_status='APPROVED'
        AND reviewer_kind IN ('PHARMACIST','PHYSICIAN','TEST_FIXTURE')
        AND review_reference IS NOT NULL AND length(trim(review_reference))>0 AND reviewed_at IS NOT NULL))
);

-- Rule sources retain their legacy join; this table adds exact citations and review scope.
CREATE TABLE rule_evidence (
    rule_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_locator TEXT NOT NULL CHECK (length(trim(source_locator))>0),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('OFFICIAL_LABEL','LICENSED_REVIEWED_DB','REVIEWED_GUIDELINE','PEER_REVIEWED','TEST_FIXTURE')),
    PRIMARY KEY (rule_id, source_id, source_locator),
    FOREIGN KEY (rule_id, source_id) REFERENCES rule_sources(rule_id, source_id)
);

CREATE TABLE rule_applicability (
    rule_id TEXT PRIMARY KEY REFERENCES rules(rule_id),
    jurisdiction_scope TEXT NOT NULL CHECK (jurisdiction_scope IN ('GLOBAL','MARKET_SPECIFIC')),
    market_codes_json TEXT NOT NULL DEFAULT '[]',
    required_context_json TEXT NOT NULL DEFAULT '{}',
    reviewer_kind TEXT NOT NULL CHECK (reviewer_kind IN ('PHARMACIST','PHYSICIAN','AUTOMATED','UNREVIEWED','TEST_FIXTURE')),
    review_reference TEXT,
    reviewed_at TEXT
);

-- Persist this ledger across builds; retired IDs remain reserved and cannot change identity.
CREATE TABLE id_ledger (
    entity_kind TEXT NOT NULL CHECK (entity_kind IN ('INGREDIENT','CLASS','RULE','DRUG')),
    stable_id TEXT NOT NULL,
    compact_int_id INTEGER CHECK (compact_int_id BETWEEN 1 AND 2147483647),
    lifecycle TEXT NOT NULL CHECK (lifecycle IN ('ACTIVE','RETIRED')),
    PRIMARY KEY (entity_kind, stable_id),
    UNIQUE (entity_kind, compact_int_id)
);

-- Class-based checks require reviewed, directly traceable product classification too.
CREATE TABLE class_membership_evidence (
    drug_id TEXT NOT NULL,
    class_id TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    source_locator TEXT NOT NULL CHECK (length(trim(source_locator))>0),
    reviewer_kind TEXT NOT NULL CHECK (reviewer_kind IN ('PHARMACIST','PHYSICIAN','TEST_FIXTURE')),
    review_reference TEXT NOT NULL CHECK (length(trim(review_reference))>0),
    reviewed_at TEXT NOT NULL,
    PRIMARY KEY (drug_id,class_id,source_id,source_locator),
    FOREIGN KEY (drug_id,class_id) REFERENCES drug_class_memberships(drug_id,class_id)
);
