# Quick Start: 修改上一次交易記錄

**Date**: 2025-11-29
**Feature**: 001-edit-last-transaction

## Overview

本文件提供開發者快速入門指南，說明如何在本地開發和測試「修改上一次交易記錄」功能。

---

## Prerequisites

### 環境需求

- **Python**: 3.11+
- **uv**: Python package manager（專案使用）
- **Redis**: Vercel KV 或本地 Redis（用於 KV 儲存）
- **LINE Bot**: LINE Developer Console 設定的 Bot
- **OpenAI**: OpenAI API Key（GPT-4）

### 環境變數

在 `.env` 檔案中設定：

```bash
# LINE Bot
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

# OpenAI
OPENAI_API_KEY=your_openai_api_key
GPT_MODEL=gpt-4o-2024-08-06

# Vercel KV (Redis)
REDIS_URL=redis://localhost:6379  # 本地開發
# REDIS_URL=your_vercel_kv_url     # 生產環境

# KV Configuration
KV_ENABLED=true
LAST_TRANSACTION_TTL=3600  # 1 hour
```

---

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd linebot-gpt-bookkeeper
git checkout 001-edit-last-transaction
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Start Local Redis (Optional)

若無 Vercel KV，可使用本地 Redis：

```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

---

## Development Workflow

### Step 1: Understand Existing Code

閱讀以下檔案以了解現有架構：

```bash
# 資料模型
app/gpt_processor.py:28-72    # BookkeepingEntry, MultiExpenseResult

# KV 儲存
app/kv_store.py:18-80          # KVStore.get(), KVStore.set()

# LINE 訊息處理
app/line_handler.py            # handle_text_message()

# GPT 提示詞
app/prompts.py                 # MULTI_EXPENSE_PROMPT
```

### Step 2: Implement GPT Prompt Extension

修改 `app/prompts.py`，新增 `update_last_entry` 意圖支援：

```python
# app/prompts.py
MULTI_EXPENSE_PROMPT = f"""
# 現有內容 ...

## 支援的意圖類型

### 4. update_last_entry（修改上一筆交易）

**觸發條件**：
- 使用者訊息包含「修改」、「改」、「更新」、「上一筆」、「最後一筆」等關鍵詞
- 明確指出要修改的欄位（品項、分類、專案、金額）

**回應格式**：
```json
{{
  "intent": "update_last_entry",
  "fields_to_update": {{
    "品項": "新品項名稱",    // 選填
    "分類": "新分類名稱",    // 選填
    "專案": "新專案名稱",    // 選填
    "原幣金額": 350.0        // 選填
  }}
}}
```

**欄位規則**：
- `fields_to_update` 只包含使用者想修改的欄位
- 金額欄位統一使用「原幣金額」
- 若金額為 0，允許（免費項目）
- 若金額為負數，返回 `error` 意圖並提示「金額不可為負數」

**範例**：
- "修改品項為工作午餐" → {{"intent": "update_last_entry", "fields_to_update": {{"品項": "工作午餐"}}}}
- "改金額 350" → {{"intent": "update_last_entry", "fields_to_update": {{"原幣金額": 350.0}}}}
- "改金額 -100" → {{"intent": "error", "error_message": "金額不可為負數"}}
"""
```

### Step 3: Update Schema

修改 `app/schemas.py`，擴充 `MULTI_BOOKKEEPING_SCHEMA`：

```python
# app/schemas.py
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
            ]
        },
        # ... 現有欄位 ...
        "fields_to_update": {  # 新增
            "type": "object",
            "properties": {
                "品項": {"type": "string"},
                "分類": {"type": "string"},
                "專案": {"type": "string"},
                "原幣金額": {"type": "number", "minimum": 0}
            },
            "additionalProperties": False
        }
    },
    "required": ["intent"]
}
```

### Step 4: Implement Update Logic

在 `app/line_handler.py` 新增 `handle_update_last_entry` 函式：

```python
# app/line_handler.py
from app.kv_store import KVStore, get_last_transaction
from app.config import LAST_TRANSACTION_TTL

def handle_update_last_entry(user_id: str, fields_to_update: dict) -> str:
    """
    Handle update last transaction request

    Args:
        user_id: LINE user ID
        fields_to_update: Dict of fields to update (from GPT)

    Returns:
        str: Reply message
    """
    if not fields_to_update:
        return "請指定要修改的欄位（品項、分類、專案或金額）"

    key = f"user:{user_id}:last_transaction"
    kv_store = KVStore()

    # Step 1: Read original transaction
    original_tx = kv_store.get(key)
    if not original_tx:
        return "目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）"

    target_id = original_tx.get("交易ID")

    # Step 2: Update fields
    updated_tx = original_tx.copy()
    for field, value in fields_to_update.items():
        # Skip empty values (preserve original)
        if value == "" or value is None:
            continue
        updated_tx[field] = value

    # Step 3: Verify ID (optimistic lock)
    current_tx = kv_store.get(key)
    if not current_tx or current_tx.get("交易ID") != target_id:
        return "交易已變更，請重新操作"

    # Step 4: Write back
    success = kv_store.set(key, updated_tx, LAST_TRANSACTION_TTL)
    if not success:
        return "儲存失敗，請稍後再試"

    # Step 5: Format success message
    updated_fields = ", ".join([f"{k}: {v}" for k, v in fields_to_update.items()])
    return f"✅ 修改成功！\n已更新：{updated_fields}"
```

### Step 5: Integrate with Message Handler

修改 `app/line_handler.py` 的 `handle_text_message` 函式：

```python
# app/line_handler.py
def handle_text_message(event, line_bot_api):
    """Handle LINE text message event"""
    user_id = event.source.user_id
    user_message = event.message.text

    # Process with GPT
    result = process_multi_expense(user_message, user_id)

    # 新增：處理 update_last_entry 意圖
    if result.intent == "update_last_entry":
        reply_text = handle_update_last_entry(user_id, result.fields_to_update)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return

    # 現有邏輯：multi_bookkeeping, conversation, error
    # ...
```

---

## Local Testing

### Option 1: Manual Testing (test_local.py)

使用現有的本地測試腳本：

```bash
# 執行本地測試
uv run python test_local.py
```

在互動式 CLI 中測試：

```
> 午餐 100
✅ 記帳成功！...

> 修改品項為工作午餐
✅ 修改成功！
已更新：品項: 工作午餐

> 改金額 150
✅ 修改成功！
已更新：原幣金額: 150.0
```

### Option 2: Integration Test

撰寫整合測試（`tests/integration/test_edit_last_transaction.py`）：

```python
import pytest
from app.kv_store import KVStore
from app.line_handler import handle_update_last_entry

class TestEditLastTransaction:
    def setup_method(self):
        """Setup test environment"""
        self.kv_store = KVStore()
        self.user_id = "test_user_12345"
        self.key = f"user:{self.user_id}:last_transaction"

    def teardown_method(self):
        """Cleanup test data"""
        self.kv_store.client.delete(self.key)

    def test_edit_item_name_success(self):
        """Test: 修改品項成功"""
        # Given: KV 中有一筆交易
        original_tx = {
            "intent": "bookkeeping",
            "品項": "午餐",
            "原幣金額": 100.0,
            "交易ID": "20251129-140000"
        }
        self.kv_store.set(self.key, original_tx, 3600)

        # When: 修改品項
        result = handle_update_last_entry(self.user_id, {"品項": "工作午餐"})

        # Then: 品項已更新
        updated_tx = self.kv_store.get(self.key)
        assert updated_tx["品項"] == "工作午餐"
        assert updated_tx["原幣金額"] == 100.0  # 其他欄位不變
        assert "修改成功" in result

    def test_edit_with_no_transaction(self):
        """Test: 無交易記錄時修改"""
        # Given: KV 為空
        # (teardown 已清空)

        # When: 嘗試修改
        result = handle_update_last_entry(self.user_id, {"品項": "測試"})

        # Then: 返回錯誤訊息
        assert "無可修改的交易記錄" in result

    def test_edit_amount_to_zero(self):
        """Test: 金額修改為 0"""
        # Given: 有一筆交易
        original_tx = {
            "品項": "免費試吃",
            "原幣金額": 100.0,
            "交易ID": "20251129-140000"
        }
        self.kv_store.set(self.key, original_tx, 3600)

        # When: 修改金額為 0
        result = handle_update_last_entry(self.user_id, {"原幣金額": 0.0})

        # Then: 金額已更新為 0
        updated_tx = self.kv_store.get(self.key)
        assert updated_tx["原幣金額"] == 0.0
        assert "修改成功" in result
```

執行測試：

```bash
uv run pytest tests/integration/test_edit_last_transaction.py -v
```

---

## Debugging

### 檢查 KV 儲存

使用 Redis CLI 檢查儲存的交易：

```bash
# 連接本地 Redis
redis-cli

# 檢查鍵是否存在
EXISTS user:U123456789:last_transaction

# 檢查值內容
GET user:U123456789:last_transaction

# 檢查 TTL
TTL user:U123456789:last_transaction
```

### 日誌輸出

檢查 Python 日誌：

```python
# app/line_handler.py
import logging
logger = logging.getLogger(__name__)

def handle_update_last_entry(user_id, fields_to_update):
    logger.info(f"Updating transaction for user={user_id}, fields={fields_to_update}")
    # ...
    logger.info(f"Update result: success={success}, message={message}")
```

執行時查看日誌：

```bash
# 本地測試時日誌會輸出到終端
uv run python test_local.py

# 或設定日誌級別
export LOG_LEVEL=DEBUG
uv run python test_local.py
```

---

## Common Issues

### Issue 1: Redis 連線失敗

**症狀**: `KVStore.get()` 返回 `None`，日誌顯示 `Failed to connect to Redis`

**解決方案**:
1. 檢查 `.env` 中的 `REDIS_URL` 是否正確
2. 確認本地 Redis 已啟動：`redis-cli ping`（應返回 `PONG`）
3. 若使用 Vercel KV，確認 URL 格式正確（包含密碼）

### Issue 2: GPT 未識別修改意圖

**症狀**: 使用者輸入「修改品項」但 GPT 返回 `conversation` 意圖

**解決方案**:
1. 檢查 `app/prompts.py` 是否已新增 `update_last_entry` 說明
2. 檢查 `app/schemas.py` 的 `intent` enum 是否包含 `update_last_entry`
3. 重新啟動測試腳本以載入最新 prompt

### Issue 3: 交易已過期

**症狀**: 使用者嘗試修改但返回「無可修改的交易記錄」

**解決方案**:
1. 檢查距離上次記帳是否超過 1 小時
2. 使用 Redis CLI 檢查 TTL：`TTL user:{user_id}:last_transaction`
3. 若需要延長 TTL，修改 `.env` 的 `LAST_TRANSACTION_TTL`

---

## Next Steps

完成本地開發後：

1. **撰寫測試**：補充整合測試案例（參考 `tests/integration/test_edit_last_transaction.py`）
2. **提交程式碼**：遵循 Git 工作流程（`git commit -m "feat(line-handler): add update last entry feature"`）
3. **部署到 Vercel**：推送到 GitHub，Vercel 自動部署
4. **手動驗證**：在 LINE Bot 中實際測試所有場景

---

## Resources

- **規格文件**: [spec.md](./spec.md)
- **研究文件**: [research.md](./research.md)
- **資料模型**: [data-model.md](./data-model.md)
- **API 合約**: [contracts/gpt-api.md](./contracts/gpt-api.md)
- **KV 合約**: [contracts/kv-storage.md](./contracts/kv-storage.md)

---

## Support

遇到問題？檢查：
1. `.env` 環境變數設定
2. Redis 連線狀態
3. GPT API Key 有效性
4. Python 日誌輸出

或參考專案 README.md 和 CLAUDE.md 文件。
