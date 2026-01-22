# 記帳小幫手重構計畫（Parser-first + AI Enrichment）

> 目標：把「可規則化抽取」移到程式（Parser），讓 AI 只做語意判斷（分類/專案/必要性/明細整理），提升穩定性、可測試性與可維護性。

---

## 0. 重構原則（設計準則）

- **Parser-first**：金額/幣別/付款方式/對象/代墊狀態/現金流類型 → 程式決定（權威）
- **AI-only enrichment**：分類、專案、必要性、明細說明 → AI 決定（可被驗證/回退）
- **權威輸入格式化**：Parser 輸出必須是結構化 JSON（避免括號備註造成模型忽略）
- **單一責任**：Parser 負責「抽取正確」、AI 負責「理解合理」
- **可驗證**：AI 輸出必須能被程式 validator 檢查（分類必須在清單內、必要性必須在 enum）
- **可回退**：驗證失敗時，採用 deterministic fallback（例如上層分類、或要求重試）

---

## 1. 收斂交易世界觀（統一交易類型 Enum）

### 1.1 Transaction Types

- `expense`：支出（品項 + 金額 + 幣別 + 付款方式）
- `advance_paid`：代墊（我先付）（行為/品項 + 金額 + 幣別 + 付款方式 + 對象）
- `advance_due`：需支付（他人先付）（行為/品項 + 金額 + 幣別 + 對象 + 付款方式=NA）
- `income`：收入（收入品項/行為 + 金額 + 幣別 + 入帳帳戶）
- `transfer`：轉帳（轉出帳戶 + 轉入帳戶 + 金額 + 幣別）
- `card_payment`：繳卡費（支出帳戶 + 卡別/帳單 + 金額 + 幣別）
- `withdrawal`（可選）：提款（帳戶 + 金額 + 幣別）

> 規則：任何一筆 item 必須可被映射到上述其中一種 type；無法映射 → parser error（請補資訊）。

---

## 2. 建立 Parser（程式化抽取）模組

### 2.1 Parser 負責的欄位（權威）

- 分項切割：逗號、分號、頓號、換行
- `type`：交易類型判斷（現金流 vs 支出/代墊）
- `amount`：金額（含小數）
- `currency`：幣別（關鍵字/符號；處理 `$`/`€`/`¥` 的歧義規則）
- `date`：日期（YYYY/MM/DD、MM/DD、今天/昨天等）
- `payment_method`：付款方式（字典 mapping；未知→error 或 fallback 策略）
- `accounts`：轉出/轉入帳戶、入帳帳戶（字典 mapping）
- `advance_status`：代墊狀態（無/代墊/需支付/不索取）
- `counterparty`：收款/支付對象（同事/朋友/家人等）
- `raw_item`：原始品項/行為文字（保留，不讓 AI 改動）
- `notes_raw`（可選）：原文中額外描述片段（用途/商家/地點）

### 2.2 Parser 判斷順序（建議）

1) cashflow（繳卡費 > 轉帳 > 提款 > 收入）
2) 代墊狀態（不索取 > 代墊 > 需支付 > 無）
3) 一般支出（expense）

### 2.3 Parser 的「最小必要資訊」規格（可測）

- `expense`：raw_item + amount + (currency default) + payment_method
- `advance_paid`：raw_item + amount + counterparty + payment_method
- `advance_due`：raw_item + amount + counterparty + payment_method=NA
- `income`：raw_item + amount + account
- `transfer`：from_account + to_account + amount
- `card_payment`：from_account + card_name + amount
- `withdrawal`：from_account + amount

> 缺欄位 → parser error（不要丟給 AI 猜）

---

## 3. 定義「權威 JSON」介面（Parser → AI）

### 3.1 Authoritative Envelope（固定格式）

- **強制**：AI 不得改動以下欄位：
  - `type`, `amount`, `currency`, `payment_method`, `counterparty`, `accounts`, `date`, `raw_item`

### 3.2 Schema（最小可行）

```json
{
  "version": "v1",
  "source_text": "原始輸入（可選，用於明細推斷）",
  "transactions": [
    {
      "id": "t1",
      "type": "advance_due",
      "date": "01/22",
      "raw_item": "午餐費",
      "amount": 150.0,
      "currency": "TWD",
      "payment_method": "NA",
      "counterparty": "同事",
      "accounts": {
        "from": null,
        "to": null
      },
      "notes_raw": ""
    }
  ],
  "constraints": {
    "classification_must_be_in_list": true,
    "do_not_modify_authoritative_fields": true,
    "unknown_payment_method_policy": "error"
  }
}
```

---

## 4. AI Enrichment（分類/專案/必要性/明細）模組

### 4.1 AI 的輸入

- Authoritative JSON
- 精簡版分類規則（只留最重要的 10%：早餐/午餐/晚餐三層、預設食品=家庭、禁止自建分類）
- 專案推斷規則（健康→健康檢查、行程→登山行程、禮物→紀念日/送禮，其餘→日常）

### 4.2 AI 的輸出（只回 enrichment，不回抽取欄位）

```json
{
  "version": "v1",
  "enrichment": [
    {
      "id": "t1",
      "分類": "個人/餐飲",
      "專案": "日常",
      "必要性": "必要日常支出",
      "明細說明": ""
    }
  ]
}
```

> 規則：AI 回傳必須能和 transactions 的 `id` 一一對應。

---

## 5. Validator（程式）與回退策略

### 5.1 Validator 檢查項

- `分類` 必須在你的分類清單中（完全匹配路徑）
- `必要性` 必須在 enum：必要日常支出/想吃想買但合理/療癒性支出/衝動購物（提醒）
- `專案` 必須符合允許的集合（或遵循命名規則）
- `明細說明` 必須是字串（可空）

### 5.2 回退策略（穩定性）

- 分類不合法：
  - 策略 A：要求 AI 重試一次（帶回錯原因）
  - 策略 B：回退到最接近上層（例如餐飲類→家庭/餐飲）
- 必要性缺失：預設 `必要日常支出`（或要求重試）
- 專案缺失：依 type/分類規則預設 `日常`

---

## 6. 路由（Routing）與 prompt 管理

### 6.1 推薦路由

- 使用者輸入 → Parser 先跑（永遠先跑）
- Parser 成功 → 呼叫 AI enrichment prompt（唯一一份 prompt）
- Parser 失敗 → 回傳 parser error（提示使用者補欄位）

### 6.2 Prompt 瘦身

- 移除：金額/付款方式/代墊狀態/對象抽取規則（已程式化）
- 保留：分類清單（可縮成 ID list 或引用）、早餐午餐晚餐規則、專案/必要性規則
- 明確宣告：Authoritative JSON 欄位不可改

---

## 7. 測試計畫（讓穩定性可量化）

### 7.1 Parser 單元測試（Deterministic）

- 幣別：USD/EUR/JPY + 符號 € ¥ $ 的規則
- 金額：小數、無元字、連寫（魚$395現金）
- 付款方式：mapping、未知策略
- 代墊：代/幫/先墊/代付/不用還 的優先序
- 多項目：分隔、共用付款方式、混合 type 政策（允許/不允許）

### 7.2 AI 回歸測試（Contract）

- 固定 Authoritative JSON → 檢查 AI 是否只回 enrichment
- 檢查分類合法率、重試率、fallback 次數
- 監控：分類覆蓋率（哪些分類常被打回）

---

## 8. 遷移策略（漸進式替換）

1) 第 1 週：先導入 Parser（仍可保留舊 prompt 作 fallback）
2) 第 2 週：切換到「Parser → AI enrichment」為主路徑
3) 第 3 週：移除舊的抽取型 prompt（或只留 debug 模式）
4) 第 4 週：加上 metrics（成功率、重試率、平均處理時間、錯誤類型分布）

---

## 9. 你目前遇到的案例如何落地（示例）

### 輸入
- `同事先墊午餐費150元`

### Parser 輸出（權威）
```json
{
  "version": "v1",
  "transactions": [
    {
      "id": "t1",
      "type": "advance_due",
      "raw_item": "午餐費",
      "amount": 150.0,
      "currency": "TWD",
      "payment_method": "NA",
      "counterparty": "同事",
      "date": null,
      "accounts": { "from": null, "to": null },
      "notes_raw": ""
    }
  ]
}
```

### AI enrichment 輸出
```json
{
  "version": "v1",
  "enrichment": [
    {
      "id": "t1",
      "分類": "個人/餐飲",
      "專案": "日常",
      "必要性": "必要日常支出",
      "明細說明": ""
    }
  ]
}
```

---

## 10. 最終產出（你會得到什麼）

- 一個穩定的 Parser（可測、可預期、可 debug）
- 一個極短且穩定的 AI prompt（只做分類/專案/必要性）
- 一個 Validator（把 AI 的不確定性框住）
- 一套 metrics（知道不穩在哪裡，而不是猜 prompt 為何失效）
