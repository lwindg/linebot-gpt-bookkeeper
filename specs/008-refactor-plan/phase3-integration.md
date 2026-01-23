# Phase 3: 整合與替換 實作計畫

## 目標

將 Parser + Enricher 整合進 `gpt_processor.py`，採用 **Feature Flag** 模式漸進替換，確保向後相容。

---

## 整合策略

**方案：Feature Flag 漸進替換**

```python
# app/config.py
USE_PARSER_FIRST = os.getenv("USE_PARSER_FIRST", "false").lower() == "true"
```

- `USE_PARSER_FIRST=false` (預設): 使用現有 GPT-first 流程
- `USE_PARSER_FIRST=true`: 使用新的 Parser-first 流程

---

## Proposed Changes

### [MODIFY] `app/config.py`

新增 feature flag:
```python
USE_PARSER_FIRST = os.getenv("USE_PARSER_FIRST", "false").lower() == "true"
```

---

### [NEW] `app/processor.py`

**職責**：新的 Parser-first 處理入口

```python
def process_with_parser(user_message: str) -> MultiExpenseResult:
    """
    Parser-first 處理流程：
    1. Parser: parse(message) -> AuthoritativeEnvelope
    2. Enricher: enrich(envelope) -> EnrichedEnvelope
    3. 轉換為 MultiExpenseResult (向後相容)
    """
```

---

### [MODIFY] `app/gpt_processor.py`

在 `process_multi_expense()` 開頭加入分流:
```python
def process_multi_expense(user_message: str, *, debug: bool = False) -> MultiExpenseResult:
    # Feature flag: Parser-first mode
    if USE_PARSER_FIRST:
        return process_with_parser(user_message)
    
    # Legacy GPT-first flow...
```

---

### [NEW] `app/converter.py`

**職責**：EnrichedEnvelope ↔ MultiExpenseResult 轉換

```python
def enriched_to_multi_result(envelope: EnrichedEnvelope) -> MultiExpenseResult:
    """將 EnrichedEnvelope 轉換為舊版 MultiExpenseResult 格式"""
```

---

## 已知限制 (Phase 3 範圍外)

| 意圖 | 處理方式 |
|------|----------|
| `update_last_entry` | Fallback 到 GPT-first |
| `conversation` | Fallback 到 GPT-first |

---

## Verification Plan

1. **預設行為不變**：不設定 flag 時使用舊流程
2. **Parser-first 測試**：`USE_PARSER_FIRST=true pytest tests/`
3. **端對端驗證**：使用 functional suites 檢查輸出一致性
