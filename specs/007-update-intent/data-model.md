# Data Model: Update Intent Prompt Split

## Entities

### UpdateRequest

- **Description**: 使用者對上一筆記帳的更新指令。
- **Attributes**:
  - **intent**: 固定為 `update_last_entry`
  - **fields_to_update**: UpdateFields

### UpdateFields

- **Description**: 可更新的欄位集合（一次只允許一個欄位）。
- **Allowed fields**:
  - **品項**: string
  - **分類**: string
  - **專案**: string
  - **原幣金額**: number (must be >= 0)
  - **付款方式**: CanonicalPaymentMethod
  - **明細說明**: string
  - **必要性**: string (must be one of allowed values)

### CanonicalPaymentMethod

- **Description**: 付款方式標準名稱，由對照表正規化輸出。
- **Examples**: 現金, 台新狗卡, 富邦 Costco, Line 轉帳

## Relationships

- UpdateRequest **contains** UpdateFields

## Validation Rules

- 欄位名稱必須明確出現於使用者語句
- 一次只允許更新單一欄位
- 付款方式必須輸出標準名稱
- 原幣金額不可為負數
