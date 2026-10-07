# 來源、授權與真人審閱缺口

現存包：111,389 商品、8,120 成分、186,690 drug_ingredients、259,918 分類 mapping、50 規則、18 source registry。舊 COMPLETE 96,988，INSUFFICIENT 14,401；規則 APPROVED_FOR_MVP 38、APPROVED_FOR_MVP_SEEDED_RULE 1、APPROVED_FOR_V2 11。這些字串不能證明新契約完整性或真人 review。

| 項目 | 可保留證據 | 新契約尚缺 |
| --- | --- | --- |
| 商品與成分 | 全部舊表與原值、舊 stable/compact IDs | 每市場唯一 triple、原始完整標示、逐行角色/劑量/basis、直接來源、mapping review |
| 完整組成 | 舊 count 與舊 COMPLETE 原樣封存 | 完整標示清單依據、PHARMACIST/PHYSICIAN 識別與日期、明示完整清單確認；不能靠 count/AI |
| canonical core | 8,120 舊成分 assertions | 每個 canonical 的直接來源、化學實體/鹽類 equivalence 內容審閱；未依字串合併 |
| 分類與規則 | 舊引用/狀態原樣保留 | 逐列 direct locator、真人適用範圍與分類審閱；舊 APPROVED_FOR_V2 也未證實新 gate |
| 商業權利 | source_registry 原 license_note | 分來源版本 commercial_use/mobile redistribution evidence URL、APPROVED 授權 review；官方來源不等於商業授權 |
| 穩定 ledger | 舊 stable/compact IDs 保留在候選封存 | 首版人工核對 canonical 身分與歷史 tombstones，之後必須 previous 比對；不能以新排序改號 |
| 來源 immutable | 舊完整包 checksum 封存；新版 intake 按原文 hash 分版 | 真正原始 label/source bytes、版本與 retrieval dates；舊抽象入口不能當逐行證據 |
| 正式發行 | 本機 gate logs | 獲授權且真人已審阅資料、512 MiB 內 composed snapshot、簽章互通及 App 驗收 |

沒有本輪新增的真實醫學規則；舊中西藥 assertions 留候選封存。正式 runtime 只允許 GLOBAL unconditional；dose、allergy、disease_renal、food、herb_western 必須 NONE，未知 required capability 拒絕。MARKET_SPECIFIC、context、equivalence、多包掛載仍不支援。

候選 ingest 不把 source website 公告當 composition/interaction 證據，不推論品牌同名就是同商品，不把 label ID 當 product ID。來源合法使用、內容正確性與完整性要分開審查。下一次請在本 repo 做逐源權利清單與逐商品原標示/真人 review；未完成前不能產出正式 APPROVED rows。
