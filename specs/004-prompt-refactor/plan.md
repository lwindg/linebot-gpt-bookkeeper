# Prompt 重構計畫（記帳準確度與 Token 優化）

## 🎯 目標
- 提高欄位準確率：品項、金額、付款方式、分類、專案、必要性、代墊狀態。
- 降低 token：精簡敘述、移除重複範例，保留必要 few-shot（含 USD/EUR/JPY/TWD）。
- 專案輸出：新增專案推斷規則，避免一律預設「日常」。
- 測試可用性：先建立功能分類的統一測試入口，作為後續 Prompt/Schema 迭代的回歸驗證基礎。

## 🧭 範圍與輸出
- 重寫 `app/prompts.py`（不動程式邏輯，先討論後實作）。
- 同步 schema：`MULTI_BOOKKEEPING_SCHEMA` 新增 items 專案欄位（待開發）。
- 新增精簡版規則與 few-shot 覆蓋：單/多項、外幣（含 JPY）、代墊缺對象錯誤。
- 專案映射：健康/醫療→健康檢查；行程分類→登山行程；禮物/節慶→紀念日／送禮；其餘預設日常；活動專案（如 20250517-18 玉山南稜）暫保留手動。
- 測試腳本整合：改用功能分類套件（`expense`/`multi_expense`/`advance_payment`…），統一入口與解析策略（以 `jq` 為必備），保留舊檔名 shim。

## ✅ 當前狀態
- 測試重構已完成並可用於回歸；Prompt/Schema 重構尚未開始。
  - Functional runner：`run_tests.sh`（支援 `--suite`/`--all`/`--smoke`/`--only`/`--list`/`--auto`）
  - Suites：`tests/functional/suites/*.jsonl`（v2 typed `expected`）
  - 里程碑 commits（摘要）：
    - `3002bb7` `refactor(tests): validate suites and align docs`
    - `efd5385` `refactor(tests): type expected v2 and migrate suites`
    - `f627c7b` `refactor(tests): remove v1 expected fallback`
    - `f1620c6` `feat(tests): add --all and --smoke runners`

## 🛠️ 執行步驟（草案）
1) ✅ 測試腳本整合（已完成）：定義 suite（`expense`/`multi_expense`/`advance_payment`/`date`）、統一入口與參數（`--suite`、`--auto/--manual`、`--only`、`--list`、`--all`、`--smoke`），保留舊檔名 shim。  
   - 應測：CLI 參數行為一致；suite 選擇正確；舊檔名 shim 可正確轉呼叫。  
   - 風險：介面變更造成使用習慣斷裂（需 shim）；不同腳本既有行為不一致導致整合困難。
2) ✅ 解析與欄位對照統一（已完成）：以 `jq` 解析 JSON 為必備（若未安裝則直接報錯並提示安裝），統一欄位鍵（intent、item_count、payment、category、advance_status…）與比對規則。  
   - 應測：同一案例在新入口下可取得與原腳本一致的欄位值；分類/錯誤訊息的匹配策略不誤判。  
   - 風險：環境缺少 `jq` 導致無法執行（需明確安裝指引）；輸出格式不穩定導致解析失敗；分類「部分匹配」規則需一致化。
3) ✅ 案例搬移與基準鎖定（已完成）：把現有腳本案例搬到 `tests/functional/suites/*.jsonl`，並把 `expected` 升級為 v2 分型（typed），移除 v1 fallback，建立可重跑 baseline。  
   - 應測：`expense`/`multi_expense`/`advance_payment` 三套 suite 都能跑完；與舊腳本結果一致（以欄位比對或摘要比對）。  
   - 風險：測試依賴 GPT 回應的非決定性；需要明確哪些欄位可比對、哪些必須忽略（如交易ID）。
4) 信息盤點：拆出必填欄位與預設值清單；確定必要性、分類、代墊、專案的關鍵字映射，幣別/付款 few-shot 範圍。  
   - 應測：高頻用語涵蓋度（餐飲/點心/行程/健康/教育/禮物/交通）、代墊關鍵字覆蓋。  
   - 風險：缺詞導致分類/代墊漏判，專案預設過度單一。
5) Prompt 重構草稿：改為「欄位需求 checklist → 判斷步驟 → 對照表 → 簡短 few-shot」的扁平格式（含 JPY 範例）。  
   - 應測：few-shot 覆蓋單/多項、USD/EUR/JPY/TWD、代墊缺對象 error、活動專案未明示預設日常；用既有 suite 快速回歸。  
   - 風險：文字過度精簡導致模型忽略硬規則；few-shot 不足覆蓋邊界。
6) Schema 更新草稿：items 增加 `專案`，並確保 enum/描述一致。  
   - 應測：JSON schema 驗證四種 intent，items 必填欄位一致（含專案）；兼容既有解析與 webhook 欄位需求。  
   - 風險：schema 變更破壞解析/測試腳本；專案欄位變更影響 webhook payload。
7) 擴充自測案例集：新增/補足外幣（USD/EUR/JPY/TWD）、多項共用付款方式、代墊缺對象 error、活動專案未明示時預設日常；避免只重複舊案例。  
   - 應測：每類至少 1~2 條；錯誤路徑（缺品項/金額/付款）仍能觸發 error。  
   - 風險：案例不足無法捕捉新規則；新增案例與既有比對規則衝突。
8) 風險檢查：確認 token 下降幅度、分類/必要性誤判風險、專案預設是否過度簡化，並微調。  
   - 應測：粗估 prompt token 數；抽查分類/必要性/專案輸出；代墊對象缺失時的 error 文案。  
   - 風險：token 未顯著下降、精簡後準確度下滑，或 error 文案不一致。

## ⚠️ 風險與待確認
- 活動專案無法穩定從文字推斷，暫時只保守預設日常，後續若要自動生成需額外規則或 UI 介面。
- 分類/必要性關鍵字需覆蓋現有高頻用語，避免過度簡化導致誤判。
- 代墊四態保留，未處理「已支付/已收款」，後續如需擴充再加。

## 🧪 測試腳本整合構想（功能分類）
- 目標：用功能類別（核心記帳、多項目、代墊等）取代版本區分，統一入口腳本，降低重複維護。
- 分類構想：`expense`（單項/基本欄位）、`multi_expense`（多項目共用付款/日期/交易ID）、`advance_payment`（代墊/需支付/不索取），後續可擴充 `fx`（多幣別）等。
- 介面：單一 `run_tests.sh --suite <expense|multi_expense|advance_payment|date> [--auto|--manual] [--only pattern] [--list] [--smoke]` 或 `run_tests.sh --all`。
- 解析策略：以 `jq` 解析 JSON 為必備；若 `jq` 缺失則直接報錯並提示安裝；欄位對照統一（intent、item_count、payment、category、advance_status 等）。
- 測試案例來源：將現有三個腳本的案例搬到資料檔（shell 陣列或簡單 JSON），避免硬編碼；比較規則（分類允許部分匹配 vs 完整匹配）需在統一層定義。
- 風險：環境是否有 `jq`（無則無法跑測試）；舊腳本習慣需緩衝期（shim）。
