# GPT API Contract: 修改上一次交易記錄

**Date**: 2025-11-29
**Feature**: 001-edit-last-transaction
**API**: OpenAI GPT-4 (Structured Output)

## Overview

本文件定義 GPT API 的請求格式、回應結構和錯誤處理，用於處理使用者的修改指令。功能重用現有的 `process_multi_expense` 函式（`app/gpt_processor.py`），擴充其支援 `update_last_entry` 意圖。

---

## API Endpoint

**Provider**: OpenAI
**Model**: `gpt-4o-2024-08-06`（或配置的 `GPT_MODEL`）
**Method**: Chat Completions API with Structured Output
**Endpoint**: `https://api.openai.com/v1/chat/completions`

---

## Request Format

### HTTP Request

```http
POST /v1/chat/completions
Host: api.openai.com
Authorization: Bearer {OPENAI_API_KEY}
Content-Type: application/json
```

### Request Body

```json
{
  "model": "gpt-4o-2024-08-06",
  "messages": [
    {
      "role": "system",
      "content": "{MULTI_EXPENSE_PROMPT}"
    },
    {
      "role": "user",
      "content": "修改品項為工作午餐"
    }
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "multi_expense_response",
      "schema": {MULTI_BOOKKEEPING_SCHEMA}
    }
  }
}
```

### Prompt Content (MULTI_EXPENSE_PROMPT)

**擴充內容**（新增於現有 prompt）：

```markdown
## 支援的意圖類型

### 4. update_last_entry（修改上一筆交易）

**觸發條件**：
- 使用者訊息包含「修改」、「改」、「更新」、「上一筆」、「最後一筆」等關鍵詞
- 明確指出要修改的欄位（品項、分類、專案、金額）

**回應格式**：
```json
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "品項": "新品項名稱",    // 選填：若修改品項
    "分類": "新分類名稱",    // 選填：若修改分類
    "專案": "新專案名稱",    // 選填：若修改專案
    "原幣金額": 350.0        // 選填：若修改金額
  }
}
```

**欄位規則**：
- `fields_to_update` 只包含使用者想修改的欄位（部分更新）
- 金額欄位統一使用「原幣金額」（不是「金額」）
- 若金額為 0，允許（代表免費項目）
- 若金額為負數，返回 `error` 意圖並提示「金額不可為負數」

**範例**：

| 使用者輸入 | GPT 回應 |
|-----------|---------|
| "修改品項為工作午餐" | `{"intent": "update_last_entry", "fields_to_update": {"品項": "工作午餐"}}` |
| "改金額 350" | `{"intent": "update_last_entry", "fields_to_update": {"原幣金額": 350.0}}` |
| "把分類改成交通" | `{"intent": "update_last_entry", "fields_to_update": {"分類": "交通"}}` |
| "修改上一筆的專案為 Q4 行銷活動" | `{"intent": "update_last_entry", "fields_to_update": {"專案": "Q4 行銷活動"}}` |
| "改金額 -100" | `{"intent": "error", "error_message": "金額不可為負數，請重新輸入"}` |
```

---

## Response Format

### Success Response (update_last_entry)

```json
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "品項": "工作午餐"
  },
  "entries": [],
  "error_message": null,
  "response_text": null
}
```

### Error Response (validation failure)

```json
{
  "intent": "error",
  "error_message": "金額不可為負數，請重新輸入",
  "fields_to_update": null,
  "entries": [],
  "response_text": null
}
```

### Conversation Response (ambiguous input)

若使用者輸入不明確（如「修改上一筆」未指定欄位），返回對話意圖：

```json
{
  "intent": "conversation",
  "response_text": "請問您要修改哪個欄位呢？可以修改品項、分類、專案或金額。",
  "fields_to_update": null,
  "entries": [],
  "error_message": null
}
```

---

## Schema Definition

### JSON Schema (MULTI_BOOKKEEPING_SCHEMA)

定義於 `app/schemas.py`，需擴充以支援 `update_last_entry`：

```python
MULTI_BOOKKEEPING_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "multi_bookkeeping",
                "conversation",
                "error",
                "update_last_entry"  # 新增
            ],
            "description": "User intent type"
        },
        "entries": {
            "type": "array",
            "items": {
                # ... existing BookkeepingEntry schema ...
            },
            "description": "Bookkeeping entries (for multi_bookkeeping intent)"
        },
        "fields_to_update": {  # 新增
            "type": "object",
            "properties": {
                "品項": {
                    "type": "string",
                    "description": "New item name"
                },
                "分類": {
                    "type": "string",
                    "description": "New category name"
                },
                "專案": {
                    "type": "string",
                    "description": "New project name"
                },
                "原幣金額": {
                    "type": "number",
                    "minimum": 0,
                    "description": "New amount (must be >= 0)"
                }
            },
            "additionalProperties": False,
            "description": "Fields to update (for update_last_entry intent)"
        },
        "error_message": {
            "type": "string",
            "description": "Error message (for error intent)"
        },
        "response_text": {
            "type": "string",
            "description": "Response text (for conversation intent)"
        }
    },
    "required": ["intent"],
    "additionalProperties": False
}
```

---

## Error Handling

### GPT API Errors

| 錯誤類型 | HTTP Status | 處理策略 |
|---------|-------------|---------|
| Rate Limit | 429 | 重試 1 次（指數退避） |
| Timeout | 504 | 返回「系統忙碌中，請稍後再試」 |
| Invalid API Key | 401 | 記錄錯誤，返回「系統錯誤，請聯絡管理員」 |
| Model Overloaded | 503 | 重試 1 次 |

### Schema Validation Errors

若 GPT 回應不符合 schema（如 `fields_to_update` 包含未知欄位）：
- 記錄警告日誌
- 過濾未知欄位
- 僅處理已知欄位（`品項`, `分類`, `專案`, `原幣金額`）

### Business Logic Errors

| 錯誤情境 | GPT 回應 | 系統處理 |
|---------|---------|---------|
| 金額為負數 | `intent: "error"` | 直接返回 `error_message` 給使用者 |
| 未指定修改欄位 | `intent: "conversation"` | 返回 `response_text` 引導使用者 |
| 無法識別意圖 | `intent: "conversation"` | 返回通用回應 |

---

## Performance Requirements

| 指標 | 目標 | 理由 |
|------|------|------|
| GPT API 回應時間 | < 2 秒 | 確保總處理時間 < 3 秒（LINE webhook 限制） |
| 重試次數 | 最多 1 次 | 避免超過 3 秒限制 |
| Timeout | 5 秒 | 允許網路延遲 |

---

## Example Scenarios

### Scenario 1: 修改品項成功

**使用者輸入**：
```
修改品項為工作午餐
```

**GPT Request**：
```json
{
  "model": "gpt-4o-2024-08-06",
  "messages": [
    {"role": "system", "content": "{MULTI_EXPENSE_PROMPT}"},
    {"role": "user", "content": "修改品項為工作午餐"}
  ],
  "response_format": {"type": "json_schema", "json_schema": {...}}
}
```

**GPT Response**：
```json
{
  "intent": "update_last_entry",
  "fields_to_update": {
    "品項": "工作午餐"
  },
  "entries": [],
  "error_message": null,
  "response_text": null
}
```

**系統處理**：
1. 解析 `fields_to_update`
2. 讀取 KV 最新交易
3. 更新 `品項` 欄位
4. 寫回 KV
5. 回應使用者：「✅ 修改成功！品項已更新為：工作午餐」

---

### Scenario 2: 金額為負數（驗證失敗）

**使用者輸入**：
```
改金額 -100
```

**GPT Response**：
```json
{
  "intent": "error",
  "error_message": "金額不可為負數，請重新輸入",
  "fields_to_update": null,
  "entries": [],
  "response_text": null
}
```

**系統處理**：
直接返回 `error_message` 給使用者（不執行 KV 操作）。

---

### Scenario 3: 未指定修改欄位（引導使用者）

**使用者輸入**：
```
修改上一筆
```

**GPT Response**：
```json
{
  "intent": "conversation",
  "response_text": "請問您要修改哪個欄位呢？可以修改品項、分類、專案或金額。",
  "fields_to_update": null,
  "entries": [],
  "error_message": null
}
```

**系統處理**：
返回 `response_text` 引導使用者提供更多資訊。

---

## Testing Contract

### Unit Test (Mock GPT Response)

```python
def test_gpt_update_last_entry_intent():
    """Test GPT returns update_last_entry intent"""
    mock_response = {
        "intent": "update_last_entry",
        "fields_to_update": {"品項": "工作午餐"},
        "entries": [],
        "error_message": None,
        "response_text": None
    }
    # Assert: intent is "update_last_entry"
    # Assert: fields_to_update contains "品項"
    pass
```

### Integration Test (Real GPT API)

在 CI/CD 環境中跳過（避免 API 成本），僅在本地手動測試時執行。

---

## Summary

GPT API 合約擴充最小化：
- ✅ 重用現有 `process_multi_expense` 函式
- ✅ 新增 `update_last_entry` 意圖支援
- ✅ Schema 擴充明確（`fields_to_update` 結構）
- ✅ 錯誤處理策略與現有模式一致

無需獨立的 API 模組或額外依賴。
