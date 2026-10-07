# SafeMed 全球／複方藥資料契約 1.0.0

本目錄是第一版唯一規範來源：`contract.json`（版本、能力、合法值）、`schema.sql`（29 張表）、`SCHEMA_FIELDS.md`（由 SQL 自動產生的完整欄位表）、`validate_contract.py`（內容驗收）、`test_contract.py`（明示 TEST ONLY 的正反例）。正式資料 repo 是 `ctshieh/safemed-v2-global-drug-data`；目前本機仍位於原名 `ai-pharmacist-taiwan-data-v2`。此契約不改 V1、不建立新 App，不代表 App consumer 已完成或正式資料已取得授權。

## 版本與包裝

- 新資料格式識別 `safemed-mobile-safety-v2.1`，契約 `1.0.0`，SQLite `user_version=20100`，App/package major 維持 2，產品 `safemed_pro`。
- 商品＋全球成分核心＋規則合成一個 `COMPOSED_SNAPSHOT` SQLite 檔。第一版不支援任意多包掛載；各市場可以逐步加入同一經驗收的 snapshot。全球涵蓋度仍須逐市場揭露。
- SQLite manifest 的 `package_format=sqlite3+gzip` 是既有傳輸格式識別；App 解壓後讀 SQLite。外部 envelope 延續現有 Ed25519 契約；不增加 verifier 會拒絕的未知外部欄位。核心版本、能力、coverage、release_sequence 都在 SQLite 內，受 envelope 的 SQLite SHA-256 與簽章保護。
- `license_tier=professional`，`requires_entitlement` 為 0/1 的既有宣告；是否需另驗 entitlement 依發行方式決定，宣告與簽章不能授予購買權益。TEST ONLY 可用 `testing`。
- `compatible_app_major_versions` 為不重複的 integer array，包含 2。單一 manifest、單一 package_contract；版本非空，時間皆有時區的 ISO 8601。發布 gate 欄位為 `PASS`，producer 必須保存實際驗收 log，不能只填 PASS。
- `core_namespace=safemed-global-core-v1`，`core_version` 非空。`release_sequence` 正整數；更新比已驗收前一版大。此 producer 檢查不等於 App 已實作防重播；App 的 previous 故障復原可以回到曾驗收的舊檔。正式公鑰、發行 anti-replay 與可信序號策略仍需協同落實。

## 身分與穩定 ID

`ingredients` 是全球 canonical 成分；市場商品位於 `drugs`，由 `drug_product_identity` 明確提供 `(jurisdiction, identifier_namespace, local_product_id)`。國別採 contract.json 內 ISO 3166-1 alpha2 清單，必須包含在 market_codes_json。名稱、介面語言、網站域名都不能推論國別或將商品合併。RxNorm、ATC 是外部識別／分類，不直接當作全球商品身分。

身分可全 NULL（未知），不能部分 NULL；未知商品不得標 COMPLETE。相同商品 triple 不重複，跨國同名保留不同 drug_id，別名搜尋由 App 要求選擇市場／商品。既有 `metadata_json.safemed_product_identity` v1 mirror 保留，已知身分必須與主表相同，`source_ids` 恰為 IDENTITY／COMPOSITION 的直接來源聯集；App 原有 optional metadata 契約可繼續讀取。主表是新格式權威，mirror 只作相容。

全域 ingredient/class/rule/drug stable ID 為非空 UTF-8（上限 200 bytes）。ingredient/class/rule compact 整數範圍 1…2147483647、各類別唯一；drug 第一版無 compact ID。`id_ledger` 必須跨次建置保存，包含 RETIRED tombstone。舊 ID 不能改號、刪 tombstone、復活 tombstone 或換成另一個商品 triple。未知身分可補足；已知商品若是新註冊識別需新 drug_id。ledger 本身不能證明兩化學實體相同，canonical 對應仍需審阅及來源。

## 複方逐成分與完整性

`product_ingredient_rows` 是完整原始標示行，不因 canonical mapping 失敗而丟掉。每筆有 component_id、穩定 source_order、原名、ACTIVE／EXCIPIENT／UNKNOWN、原始劑量與 basis、mapping 狀態及直接證據。第三成分、重複 canonical 的不同原始行都必須保存。

- `VERIFIED` mapping 必須有 ingredient_id、mapping source＋record/section locator、審閱 reference 與時間；不存在對應為 UNMAPPED 且 ingredient_id=NULL。未確認／衝突行可以保留為 UNVERIFIED／CONFLICT。
- 原成分證據與 mapping 證據分開保存；來源名稱與抽象網站清單不等於每行依據。
- `drug_ingredients` 是 **VERIFIED ACTIVE 的 canonical 聚合相容投影**；其他角色及未映射行仍在原始行表。每 canonical 一筆，int ID 必須與 ingredients 相符。
- 相同 canonical 多個原始行：strength_text 依 source_order，以 ` | ` 合併非空原文；strength_value/unit 設 NULL，避免相加／猜測劑量。单行保持原值；名稱採首行原名，source/source_version 採首行 snapshot ID／version_label 作相容。各行完整證據仍以原始行為準；數值非負且有限，有數值必須有單位。
- `active_ingredient_count` 是 distinct VERIFIED ACTIVE canonical 數，不是原標示行數。`drug_compact_index` 必須精確等於 sorted canonical 成分 int IDs 與已審閱 class int IDs。
- `is_combination`：-1 未知、0 已知單一、1 已知多種 ACTIVE canonical。已完整時須與 canonical 數一致。
- `product_composition.expected_active_row_count` 是原標示預期 ACTIVE 行數；來源無明確數量可 NULL。**數量相同不能證明成分清單完整**。
- VERIFIED_COMPLETE 必須有 APPROVED 審閱、真人 PHARMACIST／PHYSICIAN 的審閱識別與有時區日期、完整清單確認說明、已知市場身分、IDENTITY＋COMPOSITION 直接來源、非空 ACTIVE，以及每原始行有來源、無 UNKNOWN role、所有 ACTIVE VERIFIED。producer 要確認來源涵蓋整份標示，不能只以已解析行數或 AI 審閱宣告完整。
- PARTIAL／UNKNOWN／CONFLICT 必須 `drugs.data_completeness!=COMPLETE`；仍檢查已知成分，並顯示缺口。TEST_FIXTURE 審閱只在 `--test-only` 接受，沒有真人審閱意義。

逐成分重複與交互作用使用所有 ACTIVE canonical，含複方↔單方、複方↔複方、第三以上成分；不能用藥名或首成分替代。canonical equivalence（鹽類／酯／活性 moiety 互換）、條件式及劑量判斷不在第一版默認啟用範圍，未來須有新 required capability。

## 可追溯來源與商業授權

`source_registry` 每筆是 **不可變來源版本 snapshot**：ID、名稱、HTTPS URL、version_label、擷取日期、SHA-256、來源類型與授權說明。source ID 若原文版本改變需新 ID，不可覆寫舊 snapshot。manifest.source_snapshots 是 array，元素精確為 source_id／version_label／checksum，與 registry 一一相符。

`source_rights` 每筆明示商用與 App 再散布權、授權證據 HTTPS URL、attribution、APPROVED 審閱識別與時間；第一版發行檔不包含 PENDING／DENIED 權利的原文／事實列。純官方網址不等於可商用再散布。來源候選與待授權來源維持在 ingest 工作區，不得冒充已可發行 registry。

直接 locator 是 `record:<來源原生文件／紀錄 ID 及段落或欄位>`（冒號後至少三字元）或有路徑的絕對 HTTPS 深層網址。首頁／公告只證明服務存在，不能當交互作用列或完整成分的證據。locator 的語法檢查不能判斷引用內容實際支持結論；須真人逐內容核實。

- 商品資料：drug_source_links 的 IDENTITY／COMPOSITION／LABEL＋直接 locator。
- 原始成分与對應：product_ingredient_rows 各自 source/mapping_source 欄位。
- canonical 來源：ingredient_sources。
- 分類 mapping：drug_class_memberships 為 APPROVED_FOR_V2，且 class_membership_evidence 有直接來源與真人審閱；不能用未審閱 ATC 推測高風險分類。
- 規則：rule_sources 原有 join 保留；rule_evidence 提供 direct locator 与 evidence_type，rule_applicability 提供審閱與適用範圍。

正式來源類型：OFFICIAL_LABEL、OFFICIAL_REGULATOR、LICENSED_REVIEWED_DB、REVIEWED_GUIDELINE、PEER_REVIEWED。`TEST_FIXTURE` 僅工程模式接受；通過測試不能改名偽裝官方。

## 規則與 coverage

rule_type 使用既有 INGREDIENT_PAIR／CLASS_PAIR／THERAPEUTIC_DUPLICATE／MULTI_CLASS_PATTERN，每規則有恰一種對應 index。pair_key 為排序後 compact int 的 `小:大`，不能以名字產生。THERAPEUTIC_DUPLICATE 分類及 MULTI_CLASS_PATTERN 都需完整 reviewed mappings；pattern 的 required classes 至少兩種，min_distinct_drugs>=2。

只有 `review_status=APPROVED_FOR_V2` 啟用。severity 採既有 BLUE／ORANGE／RED，minimum_status 必須等於 severity（目前 consumer 不另算不同 floor，故禁止較弱或不同值）。evidence_quality 為 OFFICIAL／HIGH／REVIEWED，明示 TEST ONLY 可 TEST_FIXTURE。候選狀態 CANDIDATE_ONLY／PENDING_REVIEW／REJECTED 可保留但不能加入 runtime 結論；其直接來源與 scope 一樣需明示。不能偷偷接受舊 ACTIVE／MVP 標記。

第一版 active scope 僅 `jurisdiction_scope=GLOBAL`、market_codes_json=[]、required_context_json={}；**GLOBAL 表示規則的經審閱適用范围，不表示已涵蓋全世界藥品**。MARKET_SPECIFIC／非空 required_context／有 optional_context pattern 需要未來能力，現 consumer 必須拒絕包或維持候選，不能忽略條件而啟用。中西藥候選維持 CANDIDATE_ONLY＋NOT_RUNTIME_ACTIVE，不得啟用。

`coverage_json` 必須包含 GLOBAL 與每個 package market，各包含 contract.json 的十領域；每領域結構精確 `{status,scope,limitations}`，status=NONE／PARTIAL／REVIEWED_SCOPE，scope/limitations 非空。REVIEWED_SCOPE 是寫明範圍已審阅，不表示零風險；市場特定第一版不能宣告 REVIEWED_SCOPE。dose／allergy／disease_renal／food／herb_western 的初版狀態必須 NONE，直到相應 consumer／證據與新 capability 就緒。

## 相容與擴充

既有 v1／v2 個人紀錄不丟棄、不原地改 ID。旧 v2 可讀；旧 COMPLETE 或原 count 不等於新的完整組成證明，需保留「成分完整性尚待確認」缺口。當新包提供身分與原始行證據，App 只在既有身分／原成分 snapshot 相容時重新驗證索引；不能靠同名替換歷史商品。

consumer 尚未支援 v2.1 前，必須拒絕新 schema。契約 patch 僅說明／不改安全語意；增加可選欄位與向下相容資訊走 minor，新增必要能力／安全語意使用新 schema 與 required capability；破壞欄位走 major。未知 required capability 一律拒絕，不把未知欄位當已支援功能。第一版固定要求五能力：composition-v1、product-identity-v1、direct-evidence-v1、stable-ids-v1、coverage-v1。

本包不存病患姓名、健康檢驗、個人用藥、API 金鑰或簽章私鑰。App 個人資料與 snapshot 分離。外部包上限 512 MiB；下載／解壓另須已有管線上限。

## 可重現驗收

```sh
python3 contracts/global-drug-data/1.0.0/test_contract.py --output outputs/schema-20261007
python3 contracts/global-drug-data/1.0.0/validate_contract.py /path/to/candidate.sqlite3 --previous /path/to/previous.sqlite3
```

正式命令不使用 --test-only。生成的 TEST_ONLY_global_compound.sqlite3 只用于 CLI／獨立模擬器；不能混進正式包或當作來源證明。新 snapshot 的 release gate 必須用 previous 比對，第一版初始化需人工確認初始 ledger。工程 gate 只能檢查聲明、相容與一致性，不能替代真人醫療審阅、授權、來源實際正確性、App Store 審查或實機 QA。
