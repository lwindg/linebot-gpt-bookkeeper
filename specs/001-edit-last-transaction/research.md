# Research: 修改上一次交易記錄

**Date**: 2025-11-29
**Feature**: 001-edit-last-transaction

## Overview

本文件記錄為實作「修改上一次交易記錄」功能所進行的技術研究和決策。研究範圍包括：資料存取模式、併發處理策略、GPT 提示詞設計、指令格式定義。

---

## Decision 1: 資料存取模式

### What was chosen
直接使用現有的 `KVStore` 類別操作 Vercel KV (Redis)，透過 `user:{user_id}:last_transaction` 鍵存取最新交易資料。

### Rationale
1. **重用現有基礎設施**：專案已使用 `KVStore` 管理最新交易暫存（見 `app/kv_store.py:58-80`）
2. **符合 TTL 限制**：Vercel KV 的 1 小時 TTL 已足夠覆蓋「剛記完帳立即修改」的使用場景
3. **無需持久化**：規格明確不保留修改歷史，Redis 的暫存特性正好符合需求
4. **簡單直接**：避免引入額外的資料庫或 ORM 框架

### Alternatives considered
- **使用 SQLite 或 PostgreSQL 持久化儲存**
  - **拒絕原因**：過度工程，增加部署複雜度；規格不要求持久化
- **引入 Repository 模式抽象資料存取**
  - **拒絕原因**：違反憲章「簡單勝過完美」原則；當前規模不需要抽象層

### Implementation details
- 鍵格式：`user:{user_id}:last_transaction`（與現有模式一致）
- 值格式：JSON 序列化的 `BookkeepingEntry` 物件
- TTL：1 小時（`LAST_TRANSACTION_TTL` 配置，見 `app/config.py`）
- 操作：
  - 讀取：`KVStore.get(key)` → 返回 dict 或 None
  - 修改：直接更新 dict 的目標欄位，再 `KVStore.set(key, value, ttl)`
  - 刪除：`KVStore.delete(key)`（已有 `delete_last_transaction` 函式可重用）

---

## Decision 2: 併發衝突處理策略

### What was chosen
使用「樂觀鎖」（Optimistic Locking）+ 交易 ID 驗證：在修改操作開始時讀取交易並記錄其 ID，執行修改前再次讀取並驗證 ID 是否一致。

### Rationale
1. **簡單實作**：無需 Redis WATCH/MULTI 等複雜事務機制
2. **符合規格需求**：規格要求「修改操作開始時鎖定目標交易 ID」（FR-006）
3. **低衝突機率**：單使用者場景，併發修改機率極低
4. **快速失敗**：若 ID 不一致（有新交易插入），直接返回錯誤訊息

### Alternatives considered
- **使用 Redis WATCH + MULTI 樂觀事務**
  - **拒絕原因**：過度複雜；`redis-py` 需要額外的事務管理邏輯
- **使用分散式鎖（Redis SETNX）**
  - **拒絕原因**：單使用者場景不需要；增加鎖管理和超時處理的複雜度
- **無併發處理**
  - **拒絕原因**：雖機率低，但規格明確要求處理（Clarification Q1）

### Implementation details
```python
# Pseudocode
def update_last_transaction(user_id, field, new_value):
    # Step 1: Read and lock target ID
    tx = kv_store.get(f"user:{user_id}:last_transaction")
    if not tx:
        return "無可修改的交易記錄"

    target_id = tx["交易ID"]

    # Step 2: Update field
    tx[field] = new_value

    # Step 3: Verify ID before write (optimistic lock)
    current_tx = kv_store.get(f"user:{user_id}:last_transaction")
    if not current_tx or current_tx["交易ID"] != target_id:
        return "交易已變更，請重新操作"

    # Step 4: Write back
    kv_store.set(f"user:{user_id}:last_transaction", tx, TTL)
    return success_message
```

---

## Decision 3: GPT 提示詞設計

### What was chosen
擴充現有的 `MULTI_EXPENSE_PROMPT`（見 `app/prompts.py`），新增 `update_last_entry` 意圖和欄位更新結構。

### Rationale
1. **重用現有架構**：`MultiExpenseResult` 已支援多種意圖（`multi_bookkeeping`, `conversation`, `error`），新增 `update_last_entry` 無縫整合
2. **統一 GPT 處理流程**：所有 LINE 訊息由同一個 GPT 呼叫判斷意圖，無需獨立的指令解析邏輯
3. **自然語言指令**：使用者可用「修改品項為工作午餐」、「改金額 350」等自然語言，無需記憶固定格式
4. **欄位驗證**：GPT 負責將使用者輸入對應到標準欄位名稱（`品項`, `分類`, `專案`, `原幣金額`）

### Alternatives considered
- **正則表達式解析指令**
  - **拒絕原因**：彈性差，使用者需記憶固定格式；與現有 GPT 驅動架構不一致
- **獨立的指令處理模組**
  - **拒絕原因**：增加程式碼複雜度；GPT 已能處理意圖識別

### Implementation details
**Prompt 擴充範例**：
```text
## 支援的意圖類型

4. update_last_entry（修改上一筆交易）
   - 偵測關鍵詞：「修改」、「改」、「更新」、「上一筆」、「最後一筆」
   - 返回格式：
     {
       "intent": "update_last_entry",
       "fields_to_update": {
         "品項": "新品項名稱",  // 若修改品項
         "分類": "新分類名稱",  // 若修改分類
         "專案": "新專案名稱",  // 若修改專案
         "原幣金額": 350.0      // 若修改金額
       }
     }
   - 注意：
     - fields_to_update 只包含使用者想修改的欄位
     - 金額欄位統一使用「原幣金額」（不是「金額」）
     - 若金額為 0，允許（免費項目）；若為負數，返回 error 意圖
```

**Schema 擴充**（`app/schemas.py`）：
```python
MULTI_BOOKKEEPING_SCHEMA = {
    # ... existing properties ...
    "intent": {
        "type": "string",
        "enum": ["multi_bookkeeping", "conversation", "error", "update_last_entry"]
    },
    "fields_to_update": {
        "type": "object",
        "properties": {
            "品項": {"type": "string"},
            "分類": {"type": "string"},
            "專案": {"type": "string"},
            "原幣金額": {"type": "number", "minimum": 0}
        }
    }
}
```

---

## Decision 4: 指令格式與使用者體驗

### What was chosen
支援多種自然語言指令變體，無需固定格式：
- 「修改上一筆的品項為工作午餐」
- 「改品項工作午餐」
- 「更新上一筆金額 350」
- 「把分類改成交通」

### Rationale
1. **符合現有 UX 模式**：現有記帳功能已支援自然語言（如「午餐 100」、「買咖啡 50 元」）
2. **降低學習成本**：使用者無需記憶指令格式，直覺表達即可
3. **GPT 強項**：利用 GPT 的自然語言理解能力，而非強迫使用者適應機器

### Alternatives considered
- **固定格式指令（如 `/edit amount 350`）**
  - **拒絕原因**：增加使用者學習成本；與現有對話式介面不一致
- **選單式操作（LINE Quick Reply buttons）**
  - **拒絕原因**：需要多次互動（選欄位 → 輸入新值），不如文字指令快速

### Implementation details
**支援的指令變體**：
- 修改品項：「修改品項XXX」、「改品項XXX」、「品項改成XXX」
- 修改分類：「修改分類XXX」、「改分類XXX」、「分類改成XXX」
- 修改專案：「修改專案XXX」、「改專案XXX」、「專案改成XXX」
- 修改金額：「修改金額XXX」、「改金額XXX」、「金額改成XXX」

**錯誤處理訊息**：
- 無交易：「目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）」
- 欄位驗證失敗：「金額不可為負數，請重新輸入」
- 併發衝突：「交易已變更，請重新操作」

---

## Decision 5: 測試策略

### What was chosen
撰寫整合測試覆蓋端到端流程，模擬 LINE 訊息事件 → GPT 處理 → KV 更新 → 回應訊息。

### Rationale
1. **符合憲章測試原則**：「專注於驗證端到端使用者旅程的整合測試」
2. **覆蓋關鍵路徑**：測試所有 User Stories（P1-P4）的驗收場景
3. **無需單元測試**：業務邏輯簡單（讀取 KV → 更新欄位 → 寫回 KV），整合測試已足夠

### Alternatives considered
- **單元測試 + 整合測試**
  - **拒絕原因**：過度測試；當前邏輯簡單，單元測試的投資報酬率低

### Implementation details
**測試案例**（`tests/integration/test_edit_last_transaction.py`）：
```python
class TestEditLastTransaction:
    def test_edit_item_name_success(self):
        """User Story 1 - Scenario 1: 修改品項成功"""
        # Given: KV 中有一筆品項為「午餐」的交易
        # When: 使用者發送「修改品項為工作午餐」
        # Then: 品項更新為「工作午餐」，其他欄位不變
        pass

    def test_edit_with_no_transaction(self):
        """User Story 1 - Scenario 3: 無交易記錄"""
        # Given: KV 為空
        # When: 使用者嘗試修改
        # Then: 返回「無可修改的交易記錄」
        pass

    def test_edit_amount_to_zero(self):
        """User Story 4 - Scenario 4: 金額修改為 0"""
        # Given: 有一筆金額 100 的交易
        # When: 使用者修改金額為 0
        # Then: 金額更新為 0（允許免費項目）
        pass

    def test_edit_amount_negative_rejected(self):
        """User Story 4 - Scenario 3: 負數金額被拒絕"""
        # Given: 有一筆交易
        # When: 使用者修改金額為 -100
        # Then: 返回「金額不可為負數」錯誤
        pass
```

**測試工具**：
- `pytest`（現有）
- `pytest-mock`（現有，用於 mock OpenAI API 和 LINE API）
- 重用 `tests/test_local.py` 的本地測試腳本進行手動驗證

---

## Decision 6: 排序規則實作

### What was chosen
由於 KV 儲存的是「最新一筆」交易（非歷史清單），無需額外實作排序邏輯。交易 ID 格式為 `YYYYMMDD-HHMMSS`，天然按時間遞增。

### Rationale
1. **現有設計已滿足需求**：`user:{user_id}:last_transaction` 鍵只儲存最新交易，每次記帳覆蓋
2. **交易 ID 遞增性**：格式確保時間較晚者 ID 較大（符合 Clarification Q4）
3. **無需 tie-breaking 邏輯**：實務上同一秒內不會有多筆交易（LINE Bot 處理速度 < 1 秒）

### Alternatives considered
- **維護交易列表並實作排序**
  - **拒絕原因**：過度工程；規格只需「上一筆」，不需歷史清單

---

## Summary

所有技術決策均符合專案憲章原則：
- ✅ MVP 優先：重用現有 KVStore，不引入新依賴
- ✅ 簡單勝過完美：避免 Repository 模式、分散式鎖等抽象
- ✅ 測試優先：整合測試覆蓋端到端旅程
- ✅ 使用者價值：自然語言指令，無需學習固定格式

無未解決的技術問題或風險。可進入 Phase 1 設計階段。
