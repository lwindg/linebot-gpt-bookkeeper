# Data Model: 修改上一次交易記錄

**Date**: 2025-11-29
**Feature**: 001-edit-last-transaction

## Overview

本文件定義「修改上一次交易記錄」功能涉及的資料實體、欄位、關係和驗證規則。由於功能重用現有的 `BookkeepingEntry` 資料結構，本文件主要聚焦於：
1. 修改操作的輸入格式（`fields_to_update`）
2. KV 儲存的鍵值結構
3. 欄位驗證規則

---

## Entity 1: BookkeepingEntry（交易記錄）

### Description
代表一筆記帳記錄，包含品項、金額、分類等核心欄位。此實體已存在於 `app/gpt_processor.py:28-53`，本功能重用而不修改其結構。

### Fields

| 欄位名稱 | 型別 | 必填 | 預設值 | 描述 | 驗證規則 |
|---------|------|------|--------|------|---------|
| intent | string | ✅ | - | 意圖類型 | 必須為 "bookkeeping", "conversation" 之一 |
| 日期 | string | ✅ | - | 交易日期 | YYYY-MM-DD 格式 |
| 時間 | string | ✅ | - | 交易時間 | HH:MM 格式 |
| 品項 | string | ✅ | - | 品項名稱 | 非空字串 |
| 原幣別 | string | ✅ | "TWD" | 原始貨幣代碼 | TWD, USD, JPY 等 ISO 4217 代碼 |
| 原幣金額 | float | ✅ | - | 原始貨幣金額 | >= 0（允許 0，不允許負數）|
| 匯率 | float | ✅ | 1.0 | 匯率 | > 0 |
| 付款方式 | string | ✅ | - | 付款方式 | 非空字串（如「信用卡」、「現金」） |
| 交易ID | string | ✅ | - | 唯一交易識別碼 | YYYYMMDD-HHMMSS 格式 |
| 明細說明 | string | ❌ | "" | 額外明細 | 任意字串 |
| 分類 | string | ✅ | - | 分類名稱 | 非空字串 |
| 專案 | string | ✅ | "日常" | 專案名稱 | 非空字串 |
| 必要性 | string | ✅ | - | 必要性分類 | 非空字串（如「必要」、「彈性」） |
| 代墊狀態 | string | ✅ | "無" | 代墊狀態 | "無", "代墊", "需支付", "不索取" |
| 收款支付對象 | string | ❌ | "" | 代墊對象 | 任意字串 |
| 附註 | string | ❌ | "" | 附註 | 任意字串 |

### Relationships
- **儲存位置**: Vercel KV（Redis），鍵為 `user:{user_id}:last_transaction`
- **生命週期**: TTL 1 小時（`LAST_TRANSACTION_TTL` 配置）

### State Transitions
無狀態機制，交易記錄為靜態資料。

---

## Entity 2: UpdateLastEntryRequest（修改請求）

### Description
代表使用者透過 GPT 處理後的修改請求，定義哪些欄位需要更新及其新值。此實體為 `MultiExpenseResult` 的擴充（intent = "update_last_entry"）。

### Fields

| 欄位名稱 | 型別 | 必填 | 預設值 | 描述 | 驗證規則 |
|---------|------|------|--------|------|---------|
| intent | string | ✅ | - | 固定為 "update_last_entry" | 枚舉值 |
| fields_to_update | object | ✅ | {} | 需更新的欄位字典 | 見下方詳細規則 |

### fields_to_update 結構

| 欄位鍵 | 型別 | 驗證規則 | 範例 |
|--------|------|---------|------|
| 品項 | string | 非空字串 | "工作午餐" |
| 分類 | string | 非空字串 | "交通" |
| 專案 | string | 非空字串 | "Q4 行銷活動" |
| 原幣金額 | float | >= 0（允許 0，不允許負數） | 350.0 |

### Relationships
- **來源**: GPT API 回應（`MultiExpenseResult` 的 `fields_to_update` 屬性）
- **目標**: 更新 `BookkeepingEntry` 的對應欄位

### Validation Rules
1. `fields_to_update` 必須至少包含一個欄位
2. 欄位鍵必須為 `["品項", "分類", "專案", "原幣金額"]` 之一
3. 空值處理：若 GPT 返回空值（如 `"品項": ""`），保留原值不更新
4. 金額特殊驗證：
   - 允許 0（代表免費項目）
   - 拒絕負數（返回錯誤）
   - 必須為數字型別

---

## Entity 3: KVStorageKey（KV 儲存鍵）

### Description
定義 Vercel KV (Redis) 中儲存最新交易的鍵格式和值結構。

### Key Format
```
user:{user_id}:last_transaction
```

**範例**：
- `user:U123456789:last_transaction`

### Value Format
JSON 序列化的 `BookkeepingEntry` 物件。

**範例**：
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

### TTL (Time To Live)
- **值**: 3600 秒（1 小時）
- **配置**: `app/config.py` 的 `LAST_TRANSACTION_TTL`
- **行為**: 超過 TTL 後自動刪除，使用者無法修改

---

## Data Flow

### 1. 修改操作流程

```text
使用者訊息
    ↓
LINE Webhook (api/webhook.py)
    ↓
GPT 處理 (app/gpt_processor.py)
    ├─ 解析意圖：update_last_entry
    └─ 提取 fields_to_update
        ↓
KV 讀取 (app/kv_store.py)
    ├─ 鍵：user:{user_id}:last_transaction
    └─ 值：BookkeepingEntry (JSON)
        ↓
欄位驗證與更新
    ├─ 檢查 fields_to_update 合法性
    ├─ 記錄原交易 ID（併發檢查）
    └─ 更新目標欄位
        ↓
併發檢查 (Optimistic Lock)
    ├─ 重新讀取 KV
    ├─ 比對交易 ID
    └─ 若一致 → 繼續；若不一致 → 返回錯誤
        ↓
KV 寫回 (app/kv_store.py)
    ├─ 更新後的 BookkeepingEntry
    └─ TTL: 3600 秒
        ↓
回應使用者
    └─ 成功訊息 + 更新後的欄位值
```

### 2. 資料一致性保證

**樂觀鎖機制**：
```python
# Pseudocode
original_tx = kv_store.get(key)
target_id = original_tx["交易ID"]

# ... 執行修改 ...

current_tx = kv_store.get(key)
if current_tx["交易ID"] != target_id:
    raise ConcurrencyError("交易已變更")

kv_store.set(key, updated_tx, ttl)
```

---

## Validation Summary

### 欄位級別驗證

| 欄位 | 規則 | 錯誤訊息 |
|------|------|---------|
| 品項 | 非空字串 | "品項不可為空" |
| 分類 | 非空字串 | "分類不可為空" |
| 專案 | 非空字串 | "專案不可為空" |
| 原幣金額 | >= 0 | "金額不可為負數，請重新輸入" |
| 原幣金額 | 數字型別 | "金額格式錯誤" |

### 操作級別驗證

| 驗證項目 | 條件 | 錯誤訊息 |
|---------|------|---------|
| 交易存在性 | KV 中有對應鍵 | "目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）" |
| 併發一致性 | 交易 ID 匹配 | "交易已變更，請重新操作" |
| 欄位合法性 | fields_to_update 包含已知欄位 | "不支援修改此欄位" |

---

## Schema Reference

### Python Dataclass（現有）

定義於 `app/gpt_processor.py:28-72`：

```python
@dataclass
class BookkeepingEntry:
    """交易記錄資料結構"""
    intent: Literal["bookkeeping", "conversation"]
    日期: Optional[str] = None
    時間: Optional[str] = None
    品項: Optional[str] = None
    原幣別: Optional[str] = "TWD"
    原幣金額: Optional[float] = None
    匯率: Optional[float] = 1.0
    付款方式: Optional[str] = None
    交易ID: Optional[str] = None
    明細說明: Optional[str] = ""
    分類: Optional[str] = None
    專案: Optional[str] = "日常"
    必要性: Optional[str] = None
    代墊狀態: Optional[str] = "無"
    收款支付對象: Optional[str] = ""
    附註: Optional[str] = ""

@dataclass
class MultiExpenseResult:
    """多項目支出處理結果（包含修改意圖）"""
    intent: Literal["multi_bookkeeping", "conversation", "error", "update_last_entry"]
    entries: List[BookkeepingEntry] = field(default_factory=list)
    fields_to_update: Optional[dict] = None  # 新增：修改請求欄位
    error_message: Optional[str] = None
    response_text: Optional[str] = None
```

### JSON Schema（需擴充）

定義於 `app/schemas.py`，需新增 `update_last_entry` 相關結構：

```python
MULTI_BOOKKEEPING_SCHEMA = {
    # ... existing schema ...
    "properties": {
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
            },
            "additionalProperties": False
        }
    }
}
```

---

## Summary

資料模型完全重用現有架構：
- ✅ `BookkeepingEntry`：無需修改
- ✅ `MultiExpenseResult`：新增 `update_last_entry` 意圖支援
- ✅ `KVStore`：重用現有 get/set 方法
- ✅ 驗證規則：基於規格需求明確定義

無新增實體或複雜關係，符合憲章簡單性原則。
