# 資料側契約 1.0.0 交接（2026-10-07）

本目錄為資料 repo 的獨立進度與驗收記錄。未 commit、push、發包、簽章或修改 App/V1。App consumer 整合狀態未在本 session 驗證。

唯一規範已原樣複製到 `contracts/global-drug-data/1.0.0/`；全部七個 SHA256SUMS 檔案雜湊相符，schema.sql 為 a673407b44370f99a264473c89f52303bf06d8858c5ccfb8871fde82490131e3。未覆蓋舊 schema、seed、README 或已有 dirty scripts。

新 producer `scripts/produce_contract_snapshot.py` 接受明確的 29 表 JSON arrays，不依名稱猜 canonical、身分、劑量或醫學規則；建立單一 COMPOSED_SNAPSHOT，正式模式驗完整契約，更新須提供 previous（首版需 explicit initial ledger confirmation）。ledger、tombstone、來源 snapshot、身分不可變與 release_sequence 沿 frozen validator 比對。沒有 previous 卻使用首版確認開關，僅適合經人工確認的首次初始化，不能作更新捷徑。正式輸入仍須由真人檢查其證據內容，工程驗證不能鑑定真人身份或授權真偽。

完整舊資料原樣備份於 `dist/contract-1.0.0-candidates/legacy-full.candidate.sqlite3`，所有原表、未映射文字、既有 ID 與舊 review 狀態都保留；新增候選 metadata 明示不能發行或 runtime 使用。這是候選封存而不是 v2.1 runtime migration；未補捏造逐行來源、未將舊 ACTIVE/COMPLETE 改成 APPROVED。既有 aggregated 原文不是完整標示；原包未保存的原始成分不能逆推。候選 archive 仍為舊格式且超過新 512 MiB 上限，consumer 必須拒絕它。

`ingest_contract_candidate.py` 為離線候選入口：保存完整 openFDA record/原始 bytes，source ID 由原始 checksum 決定；新版原文另建 source ID，拒絕覆寫。原 active/inactive/UNKNOWN assertions 都保留於 raw_label_assertions；未解析行不假造 product_ingredient_rows。label document ID 不當市場商品 local_product_id，商品身分暫 NULL，成分完整性 UNKNOWN，商用及再散布審閱均 PENDING。既有 `ingest_openfda_labels.py` 與舊 builder 保留，請勿將舊流程當作新契約入口。

## 本機已執行

```sh
python3 contracts/global-drug-data/1.0.0/test_contract.py --output dist/contract-1.0.0-tests
python3 contracts/global-drug-data/1.0.0/generate_fields.py --check
python3 scripts/test_contract_producer.py
python3 scripts/test_candidate_intake.py
python3 scripts/archive_legacy_candidate.py --source dist/safemed-mobile-safety-v2-full.sqlite3 --output dist/contract-1.0.0-candidates/legacy-full.candidate.sqlite3
```

結果：frozen 62 PASS / 0 FAIL，234 欄一致；producer 1 個情境 test 覆蓋相同輸入 SQLite/gzip bytes 重現、拒絕覆寫、未確認初始化、正式模式拒絕合成、未知 capability 及失敗不輸出 snapshot；候選 2 tests 覆蓋完整 raw preservation、不可覆寫、新版新 ID、日期拒絕與旧 COMPLETE 原樣候選封存。新版合成 producer 產物 SHA256 與實際 gate 結果在 producer-gate.json。所有 TEST_ONLY 產物只供工程測試，無真實藥物或正式審閱。

合成資料可重現 producer 命令（output 必須不存在）：

```sh
python3 scripts/produce_contract_snapshot.py --input dist/contract-1.0.0-tests/TEST_ONLY_reviewed_rows.json --output dist/contract-1.0.0-tests/TEST_ONLY_rebuild.sqlite3 --test-only
```

正式 reviewed rows 建置用 `--previous /path/to/accepted.sqlite3`，不可 `--test-only`；首次初始化經人工確認才可 `--initial-ledger-confirmed`。輸出為 unsigned SQLite、mtime=0 gzip 與旁附 gate JSON；gate JSON 是本機證據，不是 envelope，不得拿它交給 App verifier。未產生正式資料。

`.github/workflows/contract-1.0.0.yml` 僅執行離線 gates，contents:read，不存私鑰、不發 Release、不抓遠端醫學資料。所有 run 命令已本機執行；未推上 GitHub，所以 hosted Actions 未執行。

簽章沿 App 只讀 `apps/ios-native/DATA_PACKAGE_SIGNING_CONTRACT.md`：core/coverage/capabilities/release_sequence 只在 SQLite，沒有添加外部 envelope 欄位。尚未製作 canonical signing bytes 或簽章；未聲稱 Python JSON 等同 Swift Foundation encoder。正式發行仍需 Swift byte-for-byte signing interoperability、正式公鑰、授權與真人內容 review。

## 未完成的正式資料條件

見 GAPS.md。現存可證實新契約正式核准列數為 0；有 candidate archive 與合成 composed snapshot，沒有正式全球藥物 snapshot。資料側基礎工具完成不能視為全球覆蓋或 App 就緒。
