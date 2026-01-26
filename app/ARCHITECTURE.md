# app/ Directory Layout

本文件說明 app/ 目錄內的模組分工與職責。

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

### app/services/
- 外部 I/O 或可替換的 service
- 例如：KV、Webhook、Vision、匯率查詢

### app/shared/
- 純規則與 resolver
- 例如：分類/付款方式/專案解析

### app/line/
- LINE 專屬處理（格式化、更新流程等）
