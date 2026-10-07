# 全球公開來源納入評估（2026-10-07）

目標是合法擴大藥品/成分/交互作用證據覆蓋；不宣稱已涵蓋全部全球藥物。品牌身分依市場區分，成分 canonical core 全球共享；每個交互作用都須有直接內容佐證及真人審閱，不能由「來源官方」或資料量推論完整。只提供參考並建議用戶諮詢藥師和醫師，不作醫療決策。

本清單是 intake 決策記錄，不是正式包 source_registry。所有列 runtime_active=false；本輪未新增真實 APPROVED 規則。網站一般條款僅作初步評估，逐資料集、逐文件權利與版本仍須審核。

| 來源/區域 | 可評估用途 | 初步權利/納入狀態 | 直接依據 |
| --- | --- | --- | --- |
| TFDA、健保署／TW | 市場商品、成分、分類 | 保留舊候選；逐源條款及逐行成分證據待確認 | 舊包 source_registry；GAPS.md |
| NLM RxNorm／US | canonical name/RXCUI 對照 | 候選；不是 DDI 完整來源，不把 RXCUI 當市場商品 ID | https://www.nlm.nih.gov/research/umls/rxnorm/index.html |
| NLM DailyMed／US | 標示、成分、標示 interaction 章節 | 優先評估；具體標示權利與真人內容審查待完成 | https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm |
| FDA openFDA／US | 结构化 label 原文候選 | Actions 已擷取 100 筆有界樣本；權利/真人 review PENDING，不是完整市場或 DDI 資料 | https://open.fda.gov/apis/drug/label/ |
| EMA／歐盟 | EPAR/product information/SmPC 交互作用章節 | 優先評估；一般 notice 允許署名商用再利用，但排除第三方內容；不能將整站 blanket APPROVED | https://www.ema.europa.eu/en/about-us/about-website/legal-notice |
| PMDA／JP | 添付文書、成分、interaction 章節 | 候選；逐文件網站政策/第三方權利/批次入口待確認；未下載全集 | https://www.pmda.go.jp/english/0013.html |
| Health Canada DPD／CA | 商品與成分基礎資料 | Dataset 標示 Open Government Licence–Canada；優先核實可納入欄位。產品 monograph 權利另查，DPD 不當 DDI DB | https://open.canada.ca/data/en/dataset/bf55e42a-63cb-4556-bfd8-44f26e5a36fe?wbdisable=true |
| MFDS／KR | 市場商品、標示與 DUR 候選 | 待選定具體資料集、授權、API quota；不得以 portal 名稱代表資料已取得 | https://data.mfds.go.kr/ |
| TGA／AU | 商品、PI/CMI safety/interaction 章節 | 待審；PI/CMI 有專用 licence，不能把政府網站開放政策套到所有標示 | https://www.ebs.tga.gov.au/ebs/picmi/picmirepository.nsf/pdf?OpenAgent=&id=CP-2020-PI-01836-1 |
| DrugCentral／跨市場 | 成分/藥物知識 core 候選 | 現包用 2023-11-01；不可把最新下載頁日期改成現包版本。逐欄位 rights/ShareAlike 待審；不當完整 DDI DB | https://www.drugcentral.org/download |
| DDInter 2.0／跨成分 | 結構化 DDI 候選 | BLOCKED_COMMERCIAL：CC BY-NC-SA 4.0，未取得另外授權不下載/納入商業 App 包 | https://ddinter2.scbdd.com/terms/ |
| Liverpool HIV interactions／專科跨成分 | HIV/comedication DDI | BLOCKED_PENDING_PERMISSION：commercial exploitation/再散布/改作須書面同意。未爬取、未聯絡 | https://www.hiv-druginteractions.org/terms |
| Phansalkar 2012／文獻 | 高優先級 DDI evidence | 逐規則內容/權利/適用範圍待人審；不是全球全部 pair | https://pubmed.ncbi.nlm.nih.gov/22539083/ |
| STOPP/START v3、AGS Beers 2023／文獻 | 高齡處方/特定條件 evidence | 多含病人條件；第一版不得當 GLOBAL unconditional 偷啟用；授權與 scope 分別審 | https://pmc.ncbi.nlm.nih.gov/articles/10447584/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC12478568/ |

## 完備性的驗收方式

每個市場保存來源實際總數、擷取/解析/保留/未映射/待人審筆數；有界樣本必須明示不是全量。每個商品保存完整原始 label 清單，UNKNOWN、未 mapping、第三以上成分全部保留。每條 DDI 的 evidence locator 必須定位內容，條件與市場 scope 不得丟失；條件式規則目前只能候選。

涵蓋表要按 market/domain 揭露，不用「全球」二字取代資料量/缺口。dose、allergy、disease_renal、food、herb_western 初版 NONE。沒有命中不代表沒有交互作用；來源網站存在也不能證明內容或授權已驗收。

## 後續實作順序

1. 優先具明確商用再散布條款的商品/成分資料與標示證據，逐來源保存 immutable source version、原文 checksum 與權利證據。
2. 建立逐市場全量候選 adapter；目前 openFDA 100 筆只是 intake smoke run。EMA/PMDA/CA/KR/AU 尚無本輪完成的 adapter 或全量資料，不冒充已匯入。
3. 逐標示解析交互作用內容保留原條件，canonical mapping 和 rule applicability 進真人審閱 queue，未審不啟用。
4. 由藥師/醫師確認完整成分與 GLOBAL unconditional 適用範圍；完成權利 review 才進 reviewed table input。
5. Actions 正式模式驗收單一 composed snapshot、previous ledger/immutable sources、來源 disclosure 與 coverage，再進後續簽章/consumer 驗收。正式發行未授權。

## 後續實際納入更新

其他國家來源現已完成 Canada DPD products/activeingredient、EMA centralised medicines metadata 與 France BDPM 三份全量檔案 adapter。前文「尚無本輪完成的 adapter」對這三者已由本更新取代；詳見 INTERNATIONAL_PUBLIC_DATA.md 與實際 intake reports。JP/KR 已完成官方原始資料候選收錄；AU 仍有商業再散布授權缺口。詳見 JAPAN_KOREA_AUSTRALIA.md。所有醫學規則審閱未完成。
