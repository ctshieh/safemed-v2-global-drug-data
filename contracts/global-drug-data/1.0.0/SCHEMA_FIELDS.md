# SQL 欄位清單（自動產生）

來源：schema.sql。不可手動新增欄位；語意与合法值以 README.md／contract.json 為準。

## package_manifest

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| package_id | TEXT | False | — | 1 |
| schema_version | TEXT | True | — | 0 |
| package_major_version | TEXT | True | — | 0 |
| product_line | TEXT | True | — | 0 |
| license_tier | TEXT | True | — | 0 |
| requires_entitlement | INTEGER | True | — | 0 |
| compatible_app_major_versions | TEXT | True | — | 0 |
| data_version | TEXT | True | — | 0 |
| rules_version | TEXT | True | — | 0 |
| created_at | TEXT | True | — | 0 |
| package_format | TEXT | True | — | 0 |
| source_snapshots | TEXT | True | '[]' | 0 |
| quality_gate_result | TEXT | True | — | 0 |
| locked_regression_result | TEXT | True | — | 0 |

## ingredients

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| ingredient_id | TEXT | False | — | 1 |
| ingredient_int_id | INTEGER | True | — | 0 |
| canonical_name | TEXT | True | — | 0 |
| normalized_name | TEXT | True | — | 0 |
| rxnorm_ingredient_rxcui | TEXT | False | — | 0 |
| atc_seed_codes_json | TEXT | True | '[]' | 0 |
| synonyms_json | TEXT | True | '[]' | 0 |
| source | TEXT | True | — | 0 |
| source_version | TEXT | True | — | 0 |
| evidence_quality | TEXT | True | — | 0 |

## drugs

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | False | — | 1 |
| display_name | TEXT | True | — | 0 |
| generic_name | TEXT | True | — | 0 |
| chinese_name | TEXT | False | — | 0 |
| english_name | TEXT | False | — | 0 |
| nhi_code | TEXT | False | — | 0 |
| tfda_license_no | TEXT | False | — | 0 |
| rxnorm_rxcui | TEXT | False | — | 0 |
| atc_codes_json | TEXT | True | '[]' | 0 |
| ahfs_codes_json | TEXT | True | '[]' | 0 |
| dosage_form | TEXT | False | — | 0 |
| route | TEXT | False | — | 0 |
| source | TEXT | True | — | 0 |
| source_version | TEXT | True | — | 0 |
| evidence_quality | TEXT | True | — | 0 |
| data_completeness | TEXT | True | — | 0 |
| is_combination | INTEGER | True | — | 0 |
| active_ingredient_count | INTEGER | True | — | 0 |
| safety_classes_json | TEXT | True | '[]' | 0 |
| therapeutic_classes_json | TEXT | True | '[]' | 0 |
| metadata_json | TEXT | True | '{}' | 0 |

## drug_ingredients

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | True | — | 1 |
| ingredient_id | TEXT | True | — | 2 |
| ingredient_int_id | INTEGER | True | — | 0 |
| ingredient_name_as_listed | TEXT | True | — | 0 |
| ingredient_code_as_listed | TEXT | False | — | 0 |
| strength_text | TEXT | False | — | 0 |
| strength_value | REAL | False | — | 0 |
| strength_unit | TEXT | False | — | 0 |
| role | TEXT | True | — | 0 |
| source | TEXT | True | — | 0 |
| source_version | TEXT | True | — | 0 |
| confidence | REAL | True | — | 0 |

外鍵：ingredient_id → ingredients.ingredient_id; drug_id → drugs.drug_id

## drug_aliases

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| alias_id | TEXT | False | — | 1 |
| drug_id | TEXT | True | — | 0 |
| alias | TEXT | True | — | 0 |
| normalized_alias | TEXT | True | — | 0 |
| alias_type | TEXT | True | — | 0 |
| language | TEXT | True | — | 0 |
| source | TEXT | True | — | 0 |
| source_version | TEXT | True | — | 0 |
| confidence | REAL | True | — | 0 |
| ambiguity_group_id | TEXT | False | — | 0 |

外鍵：drug_id → drugs.drug_id

## normalization_conflicts

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| conflict_id | TEXT | False | — | 1 |
| normalized_alias | TEXT | True | — | 0 |
| drug_ids_json | TEXT | True | — | 0 |
| ingredient_signatures_json | TEXT | True | — | 0 |
| resolution_status | TEXT | True | — | 0 |
| recommended_user_action | TEXT | True | — | 0 |

## classes

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| class_id | TEXT | False | — | 1 |
| class_int_id | INTEGER | True | — | 0 |
| class_name | TEXT | True | — | 0 |
| class_type | TEXT | True | — | 0 |
| parent_class_id | TEXT | False | — | 0 |
| description | TEXT | True | — | 0 |

## drug_class_memberships

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | True | — | 1 |
| class_id | TEXT | True | — | 2 |
| source | TEXT | True | — | 0 |
| source_version | TEXT | True | — | 0 |
| evidence_quality | TEXT | True | — | 0 |
| mapping_method | TEXT | True | — | 0 |
| review_status | TEXT | True | — | 0 |

外鍵：class_id → classes.class_id; drug_id → drugs.drug_id

## drug_compact_index

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | False | — | 1 |
| ingredient_int_ids_json | TEXT | True | — | 0 |
| class_int_ids_json | TEXT | True | — | 0 |

外鍵：drug_id → drugs.drug_id

## rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | False | — | 1 |
| rule_int_id | INTEGER | True | — | 0 |
| rule_code | TEXT | True | — | 0 |
| rule_type | TEXT | True | — | 0 |
| severity | TEXT | True | — | 0 |
| minimum_status | TEXT | True | — | 0 |
| title | TEXT | True | — | 0 |
| mechanism | TEXT | True | — | 0 |
| clinical_concern | TEXT | True | — | 0 |
| patient_plain_text | TEXT | True | — | 0 |
| action_text | TEXT | True | — | 0 |
| watch_for_json | TEXT | True | '[]' | 0 |
| evidence_quality | TEXT | True | — | 0 |
| review_status | TEXT | True | — | 0 |
| source_ids_json | TEXT | True | '[]' | 0 |
| created_at | TEXT | True | — | 0 |
| updated_at | TEXT | True | — | 0 |

## ingredient_pair_rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| left_ingredient_id | TEXT | True | — | 0 |
| right_ingredient_id | TEXT | True | — | 0 |
| pair_key | TEXT | True | — | 2 |

外鍵：right_ingredient_id → ingredients.ingredient_id; left_ingredient_id → ingredients.ingredient_id; rule_id → rules.rule_id

## class_pair_rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| left_class_id | TEXT | True | — | 0 |
| right_class_id | TEXT | True | — | 0 |
| pair_key | TEXT | True | — | 2 |

外鍵：right_class_id → classes.class_id; left_class_id → classes.class_id; rule_id → rules.rule_id

## therapeutic_duplicate_rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| duplicate_group_class_id | TEXT | True | — | 2 |
| severity_if_same_ingredient | TEXT | True | — | 0 |
| severity_if_same_class | TEXT | True | — | 0 |

外鍵：duplicate_group_class_id → classes.class_id; rule_id → rules.rule_id

## multi_class_pattern_rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| required_class_ids_json | TEXT | True | — | 0 |
| optional_context_class_ids_json | TEXT | True | '[]' | 0 |
| min_distinct_drugs | INTEGER | True | — | 0 |
| severity | TEXT | True | — | 0 |

外鍵：rule_id → rules.rule_id

## source_registry

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| source_id | TEXT | False | — | 1 |
| source_name | TEXT | True | — | 0 |
| source_url | TEXT | True | — | 0 |
| version_label | TEXT | True | — | 0 |
| license_note | TEXT | True | — | 0 |
| source_type | TEXT | True | — | 0 |
| retrieved_at | TEXT | True | — | 0 |
| checksum | TEXT | False | — | 0 |

## rule_sources

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| source_id | TEXT | True | — | 2 |
| evidence_note | TEXT | True | — | 0 |

外鍵：source_id → source_registry.source_id; rule_id → rules.rule_id

## herbs

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| herb_id | TEXT | False | — | 1 |
| herb_int_id | INTEGER | True | — | 0 |
| display_name | TEXT | True | — | 0 |
| pinyin_name | TEXT | False | — | 0 |
| normalized_name | TEXT | True | — | 0 |
| synonyms_json | TEXT | True | '[]' | 0 |
| source_ids_json | TEXT | True | '[]' | 0 |
| evidence_quality | TEXT | True | — | 0 |
| data_completeness | TEXT | True | — | 0 |

## herb_western_candidate_rules

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| candidate_id | TEXT | False | — | 1 |
| herb_id | TEXT | True | — | 0 |
| western_target_type | TEXT | True | — | 0 |
| western_target_id | TEXT | True | — | 0 |
| concern | TEXT | True | — | 0 |
| mechanism | TEXT | True | — | 0 |
| suggested_runtime_status | TEXT | True | — | 0 |
| candidate_status | TEXT | True | — | 0 |
| activation_gate | TEXT | True | — | 0 |
| patient_plain_text_draft | TEXT | True | — | 0 |
| action_text_draft | TEXT | True | — | 0 |
| source_ids_json | TEXT | True | '[]' | 0 |
| evidence_quality | TEXT | True | — | 0 |
| review_notes | TEXT | True | — | 0 |

外鍵：herb_id → herbs.herb_id

## package_contract

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| package_id | TEXT | False | — | 1 |
| contract_version | TEXT | True | — | 0 |
| core_namespace | TEXT | True | — | 0 |
| core_version | TEXT | True | — | 0 |
| release_sequence | INTEGER | True | — | 0 |
| snapshot_kind | TEXT | True | — | 0 |
| market_codes_json | TEXT | True | — | 0 |
| required_capabilities_json | TEXT | True | — | 0 |
| coverage_json | TEXT | True | — | 0 |

外鍵：package_id → package_manifest.package_id

## source_rights

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| source_id | TEXT | False | — | 1 |
| commercial_use_allowed | INTEGER | True | — | 0 |
| mobile_redistribution_allowed | INTEGER | True | — | 0 |
| license_evidence_url | TEXT | False | — | 0 |
| attribution_text | TEXT | True | — | 0 |
| review_status | TEXT | True | — | 0 |
| review_reference | TEXT | False | — | 0 |
| reviewed_at | TEXT | False | — | 0 |

外鍵：source_id → source_registry.source_id

## drug_product_identity

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | False | — | 1 |
| jurisdiction | TEXT | False | — | 0 |
| identifier_namespace | TEXT | False | — | 0 |
| local_product_id | TEXT | False | — | 0 |
| market_status | TEXT | True | — | 0 |
| prescription_status | TEXT | True | — | 0 |

外鍵：drug_id → drugs.drug_id

## drug_source_links

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | True | — | 1 |
| source_id | TEXT | True | — | 2 |
| purpose | TEXT | True | — | 3 |
| source_locator | TEXT | True | — | 4 |

外鍵：source_id → source_registry.source_id; drug_id → drugs.drug_id

## ingredient_sources

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| ingredient_id | TEXT | True | — | 1 |
| source_id | TEXT | True | — | 2 |
| source_locator | TEXT | True | — | 3 |

外鍵：source_id → source_registry.source_id; ingredient_id → ingredients.ingredient_id

## product_ingredient_rows

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| component_id | TEXT | False | — | 1 |
| drug_id | TEXT | True | — | 0 |
| source_order | INTEGER | True | — | 0 |
| ingredient_id | TEXT | False | — | 0 |
| name_as_listed | TEXT | True | — | 0 |
| role | TEXT | True | — | 0 |
| strength_text | TEXT | False | — | 0 |
| strength_value | REAL | False | — | 0 |
| strength_unit | TEXT | False | — | 0 |
| basis_text | TEXT | False | — | 0 |
| mapping_status | TEXT | True | — | 0 |
| source_id | TEXT | False | — | 0 |
| source_locator | TEXT | False | — | 0 |
| mapping_source_id | TEXT | False | — | 0 |
| mapping_source_locator | TEXT | False | — | 0 |
| mapping_review_reference | TEXT | False | — | 0 |
| mapping_reviewed_at | TEXT | False | — | 0 |

外鍵：mapping_source_id → source_registry.source_id; source_id → source_registry.source_id; ingredient_id → ingredients.ingredient_id; drug_id → drugs.drug_id

## product_composition

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | False | — | 1 |
| composition_status | TEXT | True | — | 0 |
| expected_active_row_count | INTEGER | False | — | 0 |
| review_status | TEXT | True | — | 0 |
| reviewer_kind | TEXT | True | — | 0 |
| review_reference | TEXT | False | — | 0 |
| reviewed_at | TEXT | False | — | 0 |
| completeness_note | TEXT | True | — | 0 |

外鍵：drug_id → drugs.drug_id

## rule_evidence

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | True | — | 1 |
| source_id | TEXT | True | — | 2 |
| source_locator | TEXT | True | — | 3 |
| evidence_type | TEXT | True | — | 0 |

外鍵：rule_id → rule_sources.rule_id; source_id → rule_sources.source_id

## rule_applicability

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| rule_id | TEXT | False | — | 1 |
| jurisdiction_scope | TEXT | True | — | 0 |
| market_codes_json | TEXT | True | '[]' | 0 |
| required_context_json | TEXT | True | '{}' | 0 |
| reviewer_kind | TEXT | True | — | 0 |
| review_reference | TEXT | False | — | 0 |
| reviewed_at | TEXT | False | — | 0 |

外鍵：rule_id → rules.rule_id

## id_ledger

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| entity_kind | TEXT | True | — | 1 |
| stable_id | TEXT | True | — | 2 |
| compact_int_id | INTEGER | False | — | 0 |
| lifecycle | TEXT | True | — | 0 |

## class_membership_evidence

| 欄位 | SQLite 型別 | NOT NULL | Default | PK 順序 |
|---|---|---|---|---|
| drug_id | TEXT | True | — | 1 |
| class_id | TEXT | True | — | 2 |
| source_id | TEXT | True | — | 3 |
| source_locator | TEXT | True | — | 4 |
| reviewer_kind | TEXT | True | — | 0 |
| review_reference | TEXT | True | — | 0 |
| reviewed_at | TEXT | True | — | 0 |

外鍵：drug_id → drug_class_memberships.drug_id; class_id → drug_class_memberships.class_id; source_id → source_registry.source_id

