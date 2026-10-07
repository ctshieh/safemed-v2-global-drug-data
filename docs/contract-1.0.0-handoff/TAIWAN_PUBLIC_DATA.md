# 台灣官方公開資料已納入候選區

五個 TFDA 官方資料集頁面均明示政府資料開放授權條款第1版。條款二允許不限目的利用、散布/改作與開發產品，依條款無須另取得書面授權；條款三要求顯名聲明，六不代表機關背書。使用授權與真人醫學審閱是不同 gate，不能把明示開放資料全部擱置至額外函詢，也不能自動把來源內容升為醫學規則 APPROVED。

授權全文：https://data.gov.tw/license 。本次只下載該五項明示開放資料 CSV，保存 ZIP transport bytes、原 CSV、checksum、逐行 locator、原始欄位和署名。仿單/外盒資料是連結 metadata；未下載 PDF/圖片，也不把該 metadata 授權推論為連結文件全部權利。

| 資料集 | 官方頁 | 本機實際原始行數 |
| --- | --- | ---: |
| 全部藥品許可證 | https://data.gov.tw/dataset/9122 | 72,062 |
| 詳細處方成分 | https://data.gov.tw/dataset/9121 | 126,017 |
| 仿單/外盒連結 | https://data.gov.tw/dataset/9117 | 29,880 |
| ATC 分類 | https://data.gov.tw/dataset/9119 | 80,584 |
| AHFS/DI 分類 | https://data.gov.tw/dataset/9118 | 6,363 |

共 314,906 原始行，全部保留於候選 SQLite，成分原始行 126,017。這是下載當下五個官方 export 的全部資料，不是宣稱台灣所有有效上市商品或全套交互作用。許可證資料包含註銷/原料藥等，原欄位不刪；CSV 缺少成分 ACTIVE/EXCIPIENT 角色時維持 UNKNOWN，所有 mapping UNMAPPED、不指定全球 canonical，不假造完整組成真人 review。不刪第三以上成分或重複行。

Source snapshot ID 依解壓 CSV checksum 決定，同 ID 原文不可覆寫；ZIP transport checksum 另記，下載時間與來源版本分开。不把 repo 更新日期當原始資料發布日。資料提供者未在 CSV 明示 release date 時，以 content-sha256 作版本。

本機候選：dist/taiwan-public-20261008/TW_UNREVIEWED_candidate.sqlite3。該檔只有候選表，沒有 App runtime manifest、規則索引或假 APPROVED，不能掛載到 App。正式組成/分類 promotion 仍需 contract 1.0.0 人工 review 與來源 rights 正式記錄。本機逐來源完整記錄見 taiwan-public-intake-report.json。

Actions：.github/workflows/taiwan-public-data.yml，手動 dispatch 下載相同五項完整 export、跑未知第三成分/重複行與 ZIP/欄位拒絕測試，保存有署名的候選 artifact 30 天，不建立 Release。原本其他 dirty 工作未提交。

本機命令：

```sh
python3 scripts/test_tfda_intake.py
python3 scripts/ingest_tfda_open_data.py --output-dir dist/taiwan-public-20261008
actionlint .github/workflows/taiwan-public-data.yml
```

结果：2 tests PASS、actionlint PASS、五項完整下載/CSV索引成功。中西藥查詢系統仍只找到公開入口；未把網站公告或查詢頁冒充完整可下載 DDI 数据集。已實際納入的是許可證/成分/分類/標示連結，不是已啟用交互作用規則。
