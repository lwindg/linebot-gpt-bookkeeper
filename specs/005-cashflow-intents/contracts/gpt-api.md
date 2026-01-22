# GPT API Contract: Cashflow Intents

本文件定義現金流意圖的 GPT 輸出格式，延續既有 structured output 流程。

## Intent

允許的意圖：
- `cashflow_intents`
- `multi_bookkeeping`（維持既有行為）
- `update_last_entry`
- `conversation`
- `error`

## cashflow_intents 輸出

```json
{
  "intent": "cashflow_intents",
  "items": [
    {
      "品項": "合庫提款",
      "原幣金額": 5000,
      "原幣別": "TWD",
      "付款方式": "合庫",
      "分類": "提款",
      "交易類型": "提款",
      "日期": "2026-01-08"
    },
    {
      "品項": "合庫提款",
      "原幣金額": 5000,
      "原幣別": "TWD",
      "付款方式": "現金",
      "分類": "提款",
      "交易類型": "收入",
      "日期": "2026-01-08"
    }
  ]
}
```

## 驗證規則

- `原幣金額` 必須 > 0
- 付款方式未提供時輸出 `NA`
- 多意圖同時命中時採用固定優先序
- 交易類型僅允許：`提款` / `轉帳` / `收入` / `支出` / `折扣`

## 錯誤輸出

```json
{
  "intent": "error",
  "message": "缺少金額，請提供完整資訊"
}
```
