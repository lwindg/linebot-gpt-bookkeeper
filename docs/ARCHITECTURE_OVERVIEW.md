# Architecture Overview

本文件說明本專案的解析流程與資料流分工。

## 核心流程

```
User message
   │
   ├─ Parser-first
   │   └─ app/parser → app/enricher → app/converter
   │
   └─ GPT-first
       └─ app/gpt → app/gpt_processor
```

## 模組分工

### app/parser/
- 純規則解析（不依賴 GPT）
- 輸出權威 JSON（Authoritative Envelope）
- 權威欄位不得在後續流程被覆寫

### app/enricher/
- 在 parser 結果上補齊分類、專案、必要性等
- 可使用 GPT 或規則
- **不得修改 parser 權威欄位**

### app/converter.py
- 將 EnrichedEnvelope 轉換為 BookkeepingEntry/MultiExpenseResult
- 套用批次 ID、交易 ID、雙分錄等規則

### app/gpt/
- GPT-first / GPT-only 的邏輯與提示處理
- 包含 update、receipt、cashflow 的 GPT 邏輯
- 對應輸出與 parser pipeline 的資料格式一致

### app/gpt_processor.py
- GPT 路徑入口
- 負責組裝 prompt、呼叫 GPT、轉換結果

### app/pipeline/
- GPT / Parser 共用的流程與工具
- 包含 routing 與共用 normalization（transaction id / batch id）

## 模式

- **Parser-first**：先跑 `app/parser`，再 `app/enricher`，最後 `app/converter`
- **GPT-first**：直接使用 `app/gpt` + `app/gpt_processor`
- **Auto**：由 `app/pipeline/router.py` 決定路徑

