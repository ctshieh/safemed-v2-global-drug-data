# GitHub Actions 資料包建置

2026-10-07：使用者已授權本次契約與 Actions 檔案提交、推送並啟動候選建置，不發布正式 Release。

GitHub repo API 回報 2026-10-06 更新，但 branches/commits API 回報空 repo；因此不能將該日期當成來源資料更新日。此次初次推送會包含本機既有 HEAD 歷史與本次指定新檔；不提交其他既有 dirty 成果。

`build-global-drug-candidate.yml` 是本次入口。push main 執行工程建置；手動 dispatch 預設另收集美國 openFDA 100 筆有界 label 候選。兩個 jobs 產物名稱和目錄分開。

- TEST-ONLY-composed： frozen 62 正反例、producer/intake tests、SQLite、mtime=0 gzip、兩次建置 SHA256 比對、來源 disclosure、旁附 gate logs。來源是人造 TEST_FIXTURE，不是正式醫學資料。
- UNREVIEWED-US-label-candidates：完整原始 bytes、每筆全部 label assertions、checksum snapshot ID、retrieval time；身分與組成待審、權利 PENDING，不產生已啟用醫學規則。

contents:read；未使用私鑰、Release API、entitlement 或 App 啟用。Artifacts 是候選建置紀錄，不是已授權發行資料；14/30 天留存不是永久來源證據庫。正式發行前另須受控保存 source snapshot、權利與真人審閱證據。

App 定位：只提供參考並建議用戶諮詢藥師和醫師，不作醫療決策。來源頁應從實際啟用包讀取版本與 direct evidence；repo 更新日期不能代替每個來源 snapshot 的資料日期。

手動啟動命令：

```sh
gh workflow run build-global-drug-candidate.yml --repo ctshieh/safemed-v2-global-drug-data --ref main -f collect_us_labels=true
```

正式 reviewed rows 仍用 produce_contract_snapshot.py，必須通過正式模式 gate、previous ledger 比對或人工初版 ledger 確認；未有人審與授權前不將其作為正式包。GitHub Actions 成功只證明執行及工程一致性，不表示取得資料使用權或專業背書。

公開 repo 的真實來源 artifact 只提供 source URL、checksum、擷取時間、筆數、權利/審閱狀態，不上傳未確認再散布權的標示原文。原始標示只在 CI ephemeral intake 供檢查。正式持久保存須先完成權利審核或受控私有來源存放流程。
