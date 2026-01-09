# Data Model: Cashflow Intents MVP

本文件定義現金流意圖功能所需的資料結構與驗證規則。

## Entity 1: CashflowIntentResult

代表 GPT 解析結果的現金流意圖輸出。

| 欄位 | 型別 | 必填 | 預設值 | 說明 | 驗證規則 |
|------|------|------|--------|------|----------|
| intent | string | ✅ | - | 現金流意圖類型 | 僅允許 `withdrawal` / `transfer` / `income` / `card_payment` |
| amount | number | ✅ | - | 原幣金額 | 必須 > 0 |
| currency | string | ✅ | TWD | 原幣別 | 未指定則為 TWD |
| date | string | ❌ | - | 交易日期 | 允許空值 |
| item | string | ✅ | - | 品項名稱 | 不可為空字串 |
| payment_method | string | ✅ | NA | 付款方式/帳戶 | 未提供則 `NA` |
| category | string | ✅ | - | 分類 | 需符合既有分類規則 |
| transaction_type | string | ✅ | - | 交易類型 | `提款` / `轉帳` / `收入` / `支出` / `折扣` |
| memo | string | ❌ | - | 備註 | 可空 |

## Entity 2: CashflowEntry

代表實際寫入的現金流記錄（可由一個輸入產生 1~2 筆）。

| 欄位 | 型別 | 必填 | 預設值 | 說明 | 驗證規則 |
|------|------|------|--------|------|----------|
| 品項 | string | ✅ | - | 品項名稱 | 不可為空 |
| 原幣金額 | number | ✅ | - | 金額 | 必須 > 0 |
| 原幣別 | string | ✅ | TWD | 幣別 | 無幣別時預設 TWD |
| 付款方式 | string | ✅ | NA | 付款方式/帳戶 | 未提供則 `NA` |
| 分類 | string | ✅ | - | 分類 | 必須為既有分類 |
| 交易類型 | string | ✅ | - | 交易類型 | `提款` / `轉帳` / `收入` / `支出` / `折扣` |
| 日期 | string | ❌ | - | 交易日期 | 可空 |
| 附註 | string | ❌ | - | 附註 | 可空 |

## 規則與關係

1. **提款 (withdrawal)**：產生兩筆記錄
   - 帳戶流出：交易類型「提款」
   - 現金流入：交易類型「收入」
   - 兩筆金額必須一致
2. **轉帳 (transfer)**：依情境產生記錄
   - 帳戶間移轉：雙筆（交易類型「轉帳／收入」）
   - 對他人轉帳：單筆（交易類型「支出」）
3. **繳卡費 (card_payment)**：視為 transfer，方向為「帳戶 → 信用卡」，交易類型「轉帳／收入」
4. **收入 (income)**：單筆記錄，欄位結構與支出一致，交易類型「收入」
5. **優先序**：多意圖同時命中時固定為 `card_payment` > `transfer` > `withdrawal` > `income`
6. **錯誤**：金額缺失、金額為 0 或負數時回傳錯誤
