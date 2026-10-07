# 日本、韓國、澳洲納入進度（2026-10-08）

已實際完整下載日本 MHLW 五份現行 Excel 與韓國 HIRA CSV，保存來源檔案、全部原始欄位、原始檔 SHA-256、來源定位、取得時間及署名。資料仍為候選，未映射或經臨床驗收，沒有啟用交互作用規則。

| 市場 | 本機收錄 | 授權與涵蓋限制 |
| --- | ---: | --- |
| JP 日本 MHLW | 24,861 工作表原始列（含 5 列標題） | 五份現行清單，最後一份與前四份重疊，不可相加成獨立藥品數。前四份商品列共 12,428；其他清單同為 12,428 商品列。MHLW PDL1.0 採署名及加工標示，第三方及特定內容例外另查。多成分製劑可能省略成分，不可標 VERIFIED_COMPLETE。 |
| KR 韓國 HIRA | 309,889 CSV 資料列 | 官方藥價主檔／藥品標準碼（2026-08），KOGL 第1類署名可商用改作。含取消/退出給付歷史；不是即時上市／給付全集。入口 metadata 的總列數與下載 CSV 不一致，以實際下載列數報告，不宣稱 metadata reconciliation PASS。 |
| AU 澳洲 | 尚未收錄藥品列 | ARTG 一般網站條款限制商業使用；PBS API 可公開下載，但尚未核實供 App 商業再散布的具體授權。只登錄來源與缺口，不宣稱已納入。 |

日本來源：https://www.mhlw.go.jp/topics/2026/04/tp20260401-01.html 。頁面標題為 2026-10-01 適用，前三份檔案反映8月13日收載，牙科清單4月1日，其他清單反映9月28日通知。保留頁面每份日期，不把下載日當作資料發布日期。

日本條款：https://www.mhlw.go.jp/chosakuken/index.html 及 https://www.digital.go.jp/resources/open_data/public_data_license_v1.0 。PMDA 的 https://www.pmda.go.jp/english/0013.html 明示禁止自動爬取／下載，本輪未爬取 PMDA 添付文書；MHLW 藥品清單不能代替添付文書交互作用證據。

韓國來源與資料集授權聲明：https://www.data.go.kr/data/15067462/fileData.do 。使用該頁免登入下載按鈕的正式檔案流程，而非頁面 schema metadata 誤指的 PNG 附件。保留下載回應、原始 CSV 與所有22欄；識別碼不轉浮點、不刪除重複／空白／第三以上成分。KOGL：https://www.kogl.or.kr/info/licenseType1.do 。

澳洲依據：https://www.tga.gov.au/about-us/using-our-website/copyright 、 https://data.pbs.gov.au/api/api-public.html 、 https://www.pbs.gov.au/general/copyright 。細節見 australia-source-intake-status.json；公開可閱讀／下載與可在 App 再散布分開記錄。未向外寄送授權申請。

Actions workflow：.github/workflows/japan-korea-public-data.yml。JP、KR 獨立 jobs 全量下載，非工程 fixture。3個測試驗證識別碼、重複列、多行文字、拒絕錯誤頁面、富文字與 phonetic 差異、formula/cache/style 的保留。

每份資料包提供 ATTRIBUTION.txt、source.json、intake-report.json，可供 App 來源揭露使用；App consumer 整合尚未在此資料 repository 修改或驗收。

App 必須明示：本 App 僅提供參考並建議用戶諮詢藥師和醫師，不作醫療決策。沒有交互作用命中不代表沒有風險。候選收錄不等於正式 Release、醫學規則 APPROVED、成分完整 VERIFIED_COMPLETE 或全球資料已完備。

## GitHub Actions 實際驗收

https://github.com/ctshieh/safemed-v2-global-drug-data/actions/runs/37697632621 ：SUCCESS，建置 commit ac463ed9579ba5f1d3232e2ce420b060e16aeb28。JP job 18秒、KR job 1分42秒；兩包實際下載後核對原始檔雜湊、逐來源列數、SQLite integrity 與候選狀態全部通過，3個測試各 job PASS。

JP artifact 11515483986（7,038,468 bytes），KR artifact 11516365974（27,698,766 bytes）。包內附原始檔案、來源頁面／授權證據、candidate SQLite 與署名。永久稽核 metadata 位於 japan-korea-actions-audit.json 及各國 intake-report。Actions artifacts保留30天，本機 dist 另保存來源候選。未建立正式 Release、簽章或 App runtime 核准；AU 尚無藥品列。
