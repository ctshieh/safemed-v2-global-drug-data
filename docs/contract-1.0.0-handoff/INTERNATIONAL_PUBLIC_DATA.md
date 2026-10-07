# 其他國家/區域官方公開資料納入

本輪已實際下載與索引加拿大、法國、EMA 的六份官方公開資料，不是只列來源清單或使用工程 fixture。原始 bytes/全欄位/來源 ID/checksum/取得時間/授權連結/署名均保存，候選 runtime_active=false、release_eligible=false。

| 來源 | 本機原始行數 | 開放授權證據與 scope |
| --- | ---: | --- |
| Health Canada DPD products | 58,324 | 加拿大 Open Government Licence；所有 API 回傳產品，包括歷史/非人用產品，不表示當前上市全集 |
| Health Canada DPD active ingredients | 120,863 | 同一 DPD 開放資料；保留成分名稱與原始 strength 等全部欄位，不以 count 證明完整組成 |
| EMA centralised procedure medicines JSON | 2,746 | EMA copyright notice 可署名商用再利用但排除第三方內容；本輪只取官方 JSON metadata，不取連結 PDF/圖片 |
| 法國 BDPM CIS 商品資料 | 15,883 | 官方下載頁明示 Licence Ouverte；保存資料與日期證據，不暗示 ANSM/HAS/UNCAM 背書 |
| 法國 BDPM CIS_COMPO 成分資料 | 32,439 | 同上；保留所有原始 positional tab columns，不猜 role/canonical mapping |
| 法國 BDPM CIS_CIP 包裝資料 | 20,920 | 同上；保留所有包裝 assertions，不把名稱相同視為同商品 |

合计 251,175 原始行。CA 原始 ingredient rows 120,863；FR 組成文件 32,439 行完整保存。產品/成分/包裝/區域 metadata 行不可加總成「全球藥品數」。

加拿大來源与授權：

- https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe （dataset明示 Open Government Licence–Canada）
- https://open.canada.ca/en/open-government-licence-canada/ （允許商用、copy/modify/publish/distribute，要求 attribution，不授與第三方未授權權利或背書）
- https://health-products.canada.ca/api/documentation/dpd-documentation-en.html?wbdisable=true

EMA 來源与授權：

- https://www.ema.europa.eu/en/scientific-guidelines/download-website-data-json-data-format （官方給自動化使用的完整 JSON；meta.total_records 與保留筆數核對）
- https://www.ema.europa.eu/en/about-us/about-website/legal-notice （commercial reproduction permitted with attribution，third-party content exceptions）

法國來源与授權：

- https://base-donnees-publique.medicaments.gouv.fr/telechargement （明示 reproduce/distribute/reuse，要求不扭曲、來源及更新日期、不得暗示背書）
- https://base-donnees-publique.medicaments.gouv.fr/docs/telechargement/licence_bdpm.pdf
- https://www.data.gouv.fr/datasets/base-de-donnees-publique-des-medicaments-base-officielle （官方 dataset 指定 Licence Ouverte）

EMA 是區域中央程序文件：jurisdiction=NULL，不能設成某個會員國，不把 EU 當 ISO 國碼，也不是全部歐盟國家產品。CA 來源 native drug_code 是來源紀錄鍵，DIN 原值在 row 中；本輪未將 source native ID 升為已驗收 product identity。FR native CIS reference 原值保存；CIP/組成多行不因相同 CIS 刪掉。

所有 canonical mapping 未核實，未產生任何真人醫學審閱、VERIFIED_COMPLETE 或 APPROVED interaction。沒有命中交互作用不代表沒有風險；App 僅提供參考並建議諮詢藥師與醫師，不作醫療決策。

本機候選目錄：dist/international-public-20261008、dist/france-public-20261008。永久版本化稽核 metadata 位於 canada-ema-intake-report.json、france-intake-report.json；資料 archive 由 Actions artifact 保存30天，正式來源證據長期保存政策仍需落實。

Actions workflow：.github/workflows/international-public-data.yml；Canada/EMA 與 France 分成兩個 job，不建立 Release。script/input tests 2+2 PASS，actionlint PASS，全量 API/file 下載與 SQLite integrity PASS。日本、韓國、澳洲等仍待具體可下載資料集與條款核實，不能宣稱已納入。
