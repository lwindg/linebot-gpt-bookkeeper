# KV Storage Contract: 修改上一次交易記錄

**Date**: 2025-11-29
**Feature**: 001-edit-last-transaction
**Storage**: Vercel KV (Redis)

## Overview

本文件定義 Vercel KV (Redis) 的儲存合約，包括鍵命名規範、值結構、TTL 策略和操作介面。功能重用現有的 `KVStore` 類別（`app/kv_store.py`），無需修改其實作。

---

## Storage Provider

**Provider**: Vercel KV
**Backend**: Redis 7.x (Upstash)
**Client**: `redis-py` 5.0+
**Connection**: 透過 `REDIS_URL` 環境變數

---

## Key Naming Convention

### Pattern

```
user:{user_id}:last_transaction
```

### Components

| 部分 | 型別 | 描述 | 範例 |
|------|------|------|------|
| `user` | 固定前綴 | 標識使用者資料命名空間 | `user` |
| `{user_id}` | LINE User ID | LINE Bot 提供的使用者唯一識別碼 | `U123456789abcdef` |
| `last_transaction` | 固定後綴 | 標識最新交易資料 | `last_transaction` |

### Examples

```
user:U123456789abcdef:last_transaction
user:Uabcdef123456789:last_transaction
```

---

## Value Structure

### Format

JSON 序列化的 `BookkeepingEntry` 物件。

### Schema

```json
{
  "intent": "bookkeeping",
  "日期": "2025-11-29",
  "時間": "14:30",
  "品項": "午餐",
  "原幣別": "TWD",
  "原幣金額": 100.0,
  "匯率": 1.0,
  "付款方式": "信用卡",
  "交易ID": "20251129-143000",
  "明細說明": "",
  "分類": "飲食",
  "專案": "日常",
  "必要性": "必要",
  "代墊狀態": "無",
  "收款支付對象": "",
  "附註": ""
}
```

### Field Constraints

| 欄位 | 型別 | 必填 | 約束 |
|------|------|------|------|
| intent | string | ✅ | 固定為 "bookkeeping" |
| 日期 | string | ✅ | YYYY-MM-DD 格式 |
| 時間 | string | ✅ | HH:MM 格式 |
| 品項 | string | ✅ | 非空字串 |
| 原幣別 | string | ✅ | ISO 4217 代碼 |
| 原幣金額 | number | ✅ | >= 0 |
| 匯率 | number | ✅ | > 0 |
| 付款方式 | string | ✅ | 非空字串 |
| 交易ID | string | ✅ | YYYYMMDD-HHMMSS 格式 |
| 明細說明 | string | ❌ | 任意字串 |
| 分類 | string | ✅ | 非空字串 |
| 專案 | string | ✅ | 非空字串 |
| 必要性 | string | ✅ | 非空字串 |
| 代墊狀態 | string | ✅ | "無", "代墊", "需支付", "不索取" |
| 收款支付對象 | string | ❌ | 任意字串 |
| 附註 | string | ❌ | 任意字串 |

---

## TTL (Time To Live)

### Configuration

```python
# app/config.py
LAST_TRANSACTION_TTL = int(os.getenv("LAST_TRANSACTION_TTL", "3600"))  # 1 hour
```

### Behavior

- **值**: 3600 秒（1 小時）
- **自動刪除**: 超過 TTL 後，Redis 自動刪除鍵
- **使用者影響**: 1 小時後無法修改舊交易（符合規格「不保留歷史」）

### Renewal Policy

- **每次修改**: 重新設定 TTL 為 3600 秒
- **讀取操作**: 不更新 TTL（Redis 預設行為）

---

## Operations

### 1. Get（讀取交易）

**Method**: `KVStore.get(key: str) -> Optional[dict]`

**Input**:
```python
key = f"user:{user_id}:last_transaction"
```

**Output**:
```python
# Success
{
  "intent": "bookkeeping",
  "日期": "2025-11-29",
  "品項": "午餐",
  # ... 其他欄位
}

# Not Found
None
```

**Error Handling**:
- Redis 連線失敗 → 返回 `None`，記錄 ERROR 日誌
- JSON 解析失敗 → 返回 `None`，記錄 ERROR 日誌

---

### 2. Set（更新交易）

**Method**: `KVStore.set(key: str, value: dict, ttl: int) -> bool`

**Input**:
```python
key = f"user:{user_id}:last_transaction"
value = {
  "intent": "bookkeeping",
  "品項": "工作午餐",  # 修改後的值
  # ... 其他欄位
}
ttl = 3600
```

**Output**:
```python
# Success
True

# Failure
False
```

**Error Handling**:
- Redis 連線失敗 → 返回 `False`，記錄 ERROR 日誌
- JSON 序列化失敗 → 返回 `False`，記錄 ERROR 日誌

---

### 3. Delete（刪除交易）

**Method**: `delete_last_transaction(user_id: str) -> bool`（現有函式）

**Input**:
```python
user_id = "U123456789abcdef"
```

**Output**:
```python
# Success
True

# Failure
False
```

**Usage**:
- 使用者手動刪除交易（現有功能）
- 測試清理（整合測試用）

---

## Concurrency Control

### Strategy

樂觀鎖（Optimistic Locking）+ 交易 ID 驗證。

### Implementation

```python
def update_last_transaction(user_id: str, fields_to_update: dict) -> dict:
    """
    Update last transaction with optimistic locking

    Returns:
        dict: {"success": bool, "message": str}
    """
    key = f"user:{user_id}:last_transaction"
    kv_store = KVStore()

    # Step 1: Read original transaction
    original_tx = kv_store.get(key)
    if not original_tx:
        return {"success": False, "message": "無可修改的交易記錄"}

    target_id = original_tx["交易ID"]

    # Step 2: Update fields
    updated_tx = original_tx.copy()
    for field, value in fields_to_update.items():
        updated_tx[field] = value

    # Step 3: Verify ID (optimistic lock)
    current_tx = kv_store.get(key)
    if not current_tx or current_tx["交易ID"] != target_id:
        return {"success": False, "message": "交易已變更，請重新操作"}

    # Step 4: Write back
    success = kv_store.set(key, updated_tx, LAST_TRANSACTION_TTL)
    if not success:
        return {"success": False, "message": "儲存失敗，請稍後再試"}

    return {"success": True, "message": "修改成功", "updated_tx": updated_tx}
```

### Race Condition Handling

| 情境 | 檢測機制 | 使用者回饋 |
|------|---------|-----------|
| 修改期間有新交易 | 交易 ID 不一致 | "交易已變更，請重新操作" |
| 修改期間交易過期 | `get` 返回 `None` | "交易已過期（1 小時限制）" |
| 多次連續修改 | 每次修改重設 TTL | 正常執行（最後一次修改有效） |

---

## Performance Characteristics

### Latency

| 操作 | 平均延遲 | P95 延遲 | 目標 |
|------|---------|---------|------|
| Get | < 10 ms | < 20 ms | < 50 ms |
| Set | < 15 ms | < 30 ms | < 50 ms |
| Delete | < 10 ms | < 20 ms | < 50 ms |

### Throughput

- **讀取**: > 1000 ops/sec
- **寫入**: > 500 ops/sec
- **預期負載**: < 10 ops/sec（單使用者場景）

---

## Error Scenarios

### 1. Redis 連線失敗

**觸發條件**:
- Vercel KV 服務中斷
- 網路問題
- 錯誤的 `REDIS_URL`

**系統行為**:
- `KVStore.get()` 返回 `None`
- `KVStore.set()` 返回 `False`
- 記錄 ERROR 日誌：`"Failed to connect to Redis: {error}"`

**使用者回饋**:
- "系統暫時無法讀取交易記錄，請稍後再試"
- "系統暫時無法儲存變更，請稍後再試"

---

### 2. 交易已過期（TTL）

**觸發條件**:
- 距離上次記帳超過 1 小時
- TTL 自動刪除鍵

**系統行為**:
- `KVStore.get()` 返回 `None`

**使用者回饋**:
- "目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）"

---

### 3. JSON 格式錯誤

**觸發條件**:
- Redis 中的值被外部工具破壞
- 編碼問題

**系統行為**:
- `KVStore.get()` 捕獲 `json.JSONDecodeError`，返回 `None`
- 記錄 ERROR 日誌

**使用者回饋**:
- "資料格式錯誤，請重新記帳"

---

## Testing Contract

### Unit Test

```python
def test_kv_store_get_returns_none_when_key_not_found():
    """Test KVStore.get returns None for missing key"""
    kv_store = KVStore()
    result = kv_store.get("nonexistent:key")
    assert result is None

def test_kv_store_set_and_get():
    """Test KVStore set and get roundtrip"""
    kv_store = KVStore()
    key = "test:user:last_transaction"
    value = {"品項": "測試項目", "原幣金額": 100.0}

    # Set
    success = kv_store.set(key, value, ttl=60)
    assert success is True

    # Get
    retrieved = kv_store.get(key)
    assert retrieved == value
```

### Integration Test

```python
def test_optimistic_lock_concurrency_conflict():
    """Test optimistic lock detects concurrent modification"""
    user_id = "test_user"
    key = f"user:{user_id}:last_transaction"
    kv_store = KVStore()

    # Setup: Original transaction
    original_tx = {"交易ID": "20251129-140000", "品項": "午餐"}
    kv_store.set(key, original_tx, 3600)

    # Simulate concurrent update (external change)
    new_tx = {"交易ID": "20251129-140100", "品項": "晚餐"}
    kv_store.set(key, new_tx, 3600)

    # Attempt update with original ID
    result = update_last_transaction(user_id, {"品項": "工作午餐"})

    # Assert: Conflict detected
    assert result["success"] is False
    assert "交易已變更" in result["message"]
```

---

## Monitoring & Observability

### Metrics

| 指標 | 描述 | 閾值 |
|------|------|------|
| `kv_get_latency` | Get 操作延遲 | P95 < 50ms |
| `kv_set_latency` | Set 操作延遲 | P95 < 50ms |
| `kv_error_rate` | 錯誤率（連線失敗、timeout） | < 1% |
| `kv_hit_rate` | 快取命中率（有交易可修改） | > 80% |

### Logging

```python
logger.info(f"KV Get: user={user_id}, found={tx is not None}")
logger.info(f"KV Set: user={user_id}, success={success}")
logger.error(f"KV Error: operation={op}, error={str(e)}")
```

---

## Migration & Backward Compatibility

### No Breaking Changes

- 重用現有 `KVStore` 類別（無介面變更）
- 鍵命名規範與現有模式一致（`user:{user_id}:*`）
- 值結構為 `BookkeepingEntry`（無需遷移）

### Feature Flag

無需 Feature Flag，功能透過 GPT 意圖隔離：
- 現有功能：`multi_bookkeeping` 意圖
- 新功能：`update_last_entry` 意圖
- 互不影響，向後相容

---

## Summary

KV 儲存合約完全重用現有架構：
- ✅ 鍵命名：`user:{user_id}:last_transaction`（既有模式）
- ✅ 值格式：JSON 序列化的 `BookkeepingEntry`（無變更）
- ✅ TTL 策略：1 小時（既有配置）
- ✅ 操作介面：`KVStore.get/set`（無修改）
- ✅ 併發控制：樂觀鎖（新增邏輯，但不影響既有功能）

無需資料庫遷移或架構變更，符合憲章簡單性原則。
