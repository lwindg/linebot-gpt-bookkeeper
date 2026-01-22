# 008 記帳重構實作計畫（Parser-first + AI Enrichment）

> 版本：v2.0（2026-01-22 更新）
> 基於現有 `prompts.py` 分析與可行性評估後調整

## 目標
- 將「可規則化抽取」移至程式解析（Parser），降低 GPT 不穩定性
- AI 僅負責語意補強（分類、專案、必要性、明細）
- 可測試、可驗證、可回退

## 範圍
- Parser 輸出權威 JSON（交易類型、金額、幣別、付款方式、對象、日期等）
- AI enrichment prompt（僅回分類/專案/必要性/明細）
- Validator + fallback（分類必須在清單內）
- 路由：Parser 成功 → AI enrichment；Parser 失敗 → 回錯

## 非目標
- 不在本階段更換 GPT model
- 不改 LINE webhook/儲存結構（除必要欄位）
- 不新增新功能（僅穩定與重構）

---

## 風險評估矩陣

| 項目 | 風險等級 | 說明 | 對策 |
|------|---------|------|------|
| **品項與代墊關鍵字互動** | 🔴 高 | 「妹9-10月諮商費」vs「代妹付9-10月諮商費」判斷複雜 | Pattern Matching + 字典規則（避免 jieba 依賴） |
| **付款方式 mapping 維護** | 🟡 中 | 目前 12 種 mapping，新增需同步更新 | 抽成外部 YAML，Parser/AI 共用 |
| **多項目分隔邊界情況** | 🟡 中 | 「三明治和咖啡80元」是複合品項不是多項目 | Parser 需處理「和/跟/與/加」連接詞 |
| **日期語意化解析** | 🟡 中 | 「今天/昨天」需依執行時間計算 | Parser 需接收 context（執行日期） |
| **幣別符號歧義** | 🟢 低 | `$` 預設 TWD，需處理歧義 | 明確規則：有 USD/美元關鍵字才判外幣 |

---

## 里程碑

1. **JSON Schema 與分類清單外部化**（新增）
2. Parser 模組化與權威 JSON 介面完成
3. AI enrichment prompt 完成並能通過 validator
4. Shadow Mode 驗證（新增）
5. 路由切換（主路徑改為 Parser → AI）
6. 測試覆蓋與回歸通過

---

## 工作拆解（階段）

### Phase 0: Schema 定義與資料外部化（新增 - 第 1 週優先）

> **目的**：先建立明確 contract，讓 Parser 和 AI 有共同規格

- **Authoritative JSON Schema**（`schemas/authoritative_envelope.json`）
  - 定義 version、source_text、transactions、constraints
  - 每筆 transaction 必須包含：id, type, raw_item, amount, currency, payment_method, counterparty, date, accounts, notes_raw
  - 定義版本相容策略（v1 → v1.1：新增欄位需可選，舊版可解析）
- **AI Enrichment Schema**（`schemas/enrichment_response.json`）
  - 定義 version、enrichment 陣列
  - 每筆 enrichment：id, 分類, 專案, 必要性, 明細說明
- **分類清單外部化**（`config/classifications.yaml`）
  - 從 `CLASSIFICATION_RULES` 抽出約 50+ 分類路徑
  - Parser/AI/Validator 共用單一來源
- **付款方式對照表外部化**（`config/payment_methods.yaml`）
  - 從 `PAYMENT_METHODS` 抽出 12+ mapping

**產出**：
- `app/schemas/authoritative_envelope.json`
- `app/schemas/enrichment_response.json`
- `app/config/classifications.yaml`
- `app/config/payment_methods.yaml`

---

### Phase 1: Parser 抽離與介面定義（第 1-2 週）

- 盤點現有解析邏輯（付款方式/代墊/現金流/日期/幣別/金額）
- 定義 Transaction Type enum：
  ```python
  class TransactionType(Enum):
      EXPENSE = "expense"           # 一般支出
      ADVANCE_PAID = "advance_paid" # 代墊（我先付）
      ADVANCE_DUE = "advance_due"   # 需支付（他人先付）
      INCOME = "income"             # 收入
      TRANSFER = "transfer"         # 轉帳
      CARD_PAYMENT = "card_payment" # 繳卡費
      WITHDRAWAL = "withdrawal"     # 提款（可選）
  ```
- **Parser 技術選型**（零外部依賴，Vercel 相容）：
  - 金額/幣別/付款方式：正規表達式
  - 代墊狀態/品項切割：**Pattern Matching + 字典規則**
    ```python
    # 代墊關鍵字 pattern（優先序：不索取 > 代墊 > 需支付）
    ADVANCE_PATTERNS = [
        (r'不用還|不索取|送給', '不索取'),
        (r'(代|幫)(?P<target>\w{1,3})(買|付|墊|代墊)', '代墊'),
        (r'(?P<target>\w{1,3})(代訂|代付|幫買|先墊)', '需支付'),
    ]
    ```
- 實作 Parser 輸出權威 JSON（符合 Phase 0 schema）
- 定義 Parser error 類型：
  - `MISSING_AMOUNT` / `MISSING_ITEM` / `INVALID_PAYMENT_METHOD` / `AMBIGUOUS_ADVANCE`

---

### Phase 2: AI Enrichment Prompt（第 2-3 週）

- 建立精簡 prompt（目標從 764 行縮減至 <200 行）
  - 移除：金額/付款方式/代墊狀態抽取規則（已程式化）
  - 保留：分類清單（引用 YAML）、早餐/午餐/晚餐三層規則、專案/必要性規則
- AI 輸出僅限 enrichment（以 id 對應）
- 明確宣告：`Authoritative JSON 欄位不可改動`
- Prompt 結構：
  ```
  ## 你的任務
  你將收到已解析的權威 JSON，只需補充以下欄位：分類、專案、必要性、明細說明

  ## 分類規則
  [引用 classifications.yaml]

  ## 輸出格式
  [Enrichment JSON Schema]
  ```

---

### Phase 3: Validator & Fallback（第 3 週）

- **分類合法性檢查**：
  - 載入 `classifications.yaml`，檢查完全匹配
  - 失敗策略 A：要求 AI 重試一次（帶回錯原因）
  - 失敗策略 B：回退到最接近上層（如「餐飲類」→ `家庭/餐飲`）
- **必要性/專案值檢查**：
  - 必要性 enum：`必要日常支出` / `想吃想買但合理` / `療癒性支出` / `衝動購物（提醒）`
  - 專案缺失：依 type/分類規則預設 `日常`
- **重試機制**：可配置最多重試 1 次
- **錯誤訊息模板**：Parser error 統一回應格式（缺付款方式/缺金額/缺對象）

---

### Phase 4: Shadow Mode 驗證（新增 - 第 3-4 週）

> **目的**：切換前量化新舊路徑差異，降低切換風險

- 同時執行舊路徑（現有 prompt）與新路徑（Parser → AI）
- 比對輸出差異：
  - 品項、金額、付款方式、代墊狀態是否一致
  - 分類差異統計（可接受的優化差異 vs 錯誤）
- 記錄指標：
  - Parser 成功率 / Parser error 分布
  - AI enrichment 合法率 / 重試率
  - 新舊路徑一致率
- **混合句型策略**（需明確）：
  - 現金流僅支援單筆（不可多項目）
  - 一般支出可多項目（逗號/分號/頓號/換行分隔）
  - 同句同時包含現金流與一般支出 → 一律回錯（要求拆句）

---

### Phase 5: 路由切換（第 4 週）

- 新路徑：Parser → AI enrichment → Validator → 結果輸出
- 舊路徑保留為 fallback（可由 config 控制）
- 記錄 error 分類（parser error / ai error / validator error）
- **切換策略**：
  - 先切 10% 流量到新路徑
  - 觀察 1-2 天無異常後逐步放大
  - 第 4 週末完全切換

---

### Phase 6: 測試與回歸（持續）

- **Parser 單元測試**（deterministic）：
  - 幣別：USD/EUR/JPY + 符號 € ¥ $ 的規則
  - 金額：小數、無元字、連寫（魚$395現金）
  - 付款方式：mapping 正確性、未知策略
  - 代墊：代/幫/先墊/代付/不用還 的優先序
  - 多項目：分隔、共用付款方式
- **AI enrichment contract 測試**：
  - 固定 Authoritative JSON → 檢查 AI 只回 enrichment
  - 檢查分類合法率
- **既有 functional suites 回歸**：
  - expense / advance / cashflow / update 測試套件

---

## 驗證指標

| 指標 | 目標值 | 量測方式 |
|------|-------|---------|
| Parser 測試通過率 | ≥ 95% | pytest 單元測試 |
| AI enrichment validator 通過率 | ≥ 95% | contract 測試 |
| 代墊/需支付類型穩定 | 同句 3 次輸出一致 | 回歸測試 |
| Shadow Mode 新舊一致率 | ≥ 90%（首週） | 比對 log |
| Parser error 類型分布 | 無單一類型 > 30% | error log 分析 |

---

## 推薦順序（最小可行）

1. **Phase 0**: Schema + 分類/付款方式外部化（Week 1）
2. **Phase 1**: Parser 核心模組（Week 1-2）
3. **Phase 2-3**: AI prompt + Validator（Week 2-3）
4. **Phase 4**: Shadow Mode 驗證（Week 3-4）
5. **Phase 5**: 路由切換（Week 4）
6. **Phase 6**: 測試回歸（持續）

---

## 現有程式碼對應表

| 計畫模組 | 現有對應 | 改動幅度 |
|---------|---------|---------|
| Transaction Types | `cashflow_intents` / `multi_bookkeeping` | 中（統一 enum）|
| Parser 幣別 | `CURRENCY_DETECTION` | 低（移到程式）|
| Parser 付款方式 | `PAYMENT_METHODS` | 低（移到程式）|
| Parser 代墊 | `ADVANCE_PAYMENT_RULES` | 高（邏輯複雜）|
| AI 分類 | `CLASSIFICATION_RULES` | 低（保留但瘦身）|
| Validator | 無 | 新增模組 |

---

## 附錄：關鍵邊界案例

```
# 代墊判斷
✅ 「代妹付9-10月諮商費18900合庫」→ type=advance_paid, counterparty=妹, raw_item=9-10月諮商費
❌ 「妹9-10月諮商費18900合庫」→ type=expense, counterparty="", raw_item=妹9-10月諮商費

# 複合品項（不拆分）
✅ 「三明治和咖啡80元現金」→ 1 item, raw_item=三明治和咖啡
❌ 不應拆成 2 items

# 連寫金額
✅ 「魚$395現金」→ raw_item=魚, amount=395, payment_method=現金
```
