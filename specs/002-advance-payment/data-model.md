# Data Model: v1.7 代墊與需支付功能

**日期**：2025-11-18
**狀態**：Phase 1 Complete

## 概述

本文件定義 v1.7 代墊功能的資料模型。基於 research.md 的決策，我們**重用現有資料結構**，無需新增 entity 或修改 schema。

## 核心實體

### BookkeepingEntry（記帳項目）

**位置**：`app/gpt_processor.py`

**現有定義**（v1.5.0）：
```python
@dataclass
class BookkeepingEntry:
    """記帳資料結構"""

    intent: Literal["bookkeeping", "conversation"]

    # 記帳欄位
    日期: Optional[str] = None              # YYYY-MM-DD
    時間: Optional[str] = None              # HH:MM
    品項: Optional[str] = None
    原幣別: Optional[str] = "TWD"
    原幣金額: Optional[float] = None
    匯率: Optional[float] = 1.0
    付款方式: Optional[str] = None
    交易ID: Optional[str] = None           # YYYYMMDD-HHMMSS
    明細說明: Optional[str] = ""
    分類: Optional[str] = None
    專案: Optional[str] = "日常"
    必要性: Optional[str] = None
    代墊狀態: Optional[str] = "無"          # ⭐ v1.7 啟用
    收款支付對象: Optional[str] = ""        # ⭐ v1.7 啟用
    附註: Optional[str] = ""

    # 對話欄位
    response_text: Optional[str] = None
```

**v1.7 變更**：
- ✅ **無結構變更**
- ✅ 啟用 `代墊狀態` 欄位：從 GPT prompt 識別並填充
- ✅ 啟用 `收款支付對象` 欄位：從 GPT prompt 提取對象名稱

### MultiExpenseResult（多項目支出結果）

**位置**：`app/gpt_processor.py`

**現有定義**（v1.5.0）：
```python
@dataclass
class MultiExpenseResult:
    """多項目支出處理結果"""

    intent: Literal["multi_bookkeeping", "conversation", "error", "update_last_entry"]

    entries: List[BookkeepingEntry] = field(default_factory=list)
    fields_to_update: Optional[dict] = None
    error_message: Optional[str] = None
    response_text: Optional[str] = None
```

**v1.7 變更**：
- ✅ **無變更**
- ✅ `entries` 列表中的每個 `BookkeepingEntry` 包含代墊資訊

## 欄位規範

### 代墊狀態（advance_payment_status）

**欄位名稱**：`代墊狀態`
**型別**：`Optional[str]`
**預設值**：`"無"`

**允許值**（v1.7）：
| 值 | 說明 | 使用場景 |
|---|------|---------|
| `"無"` | 一般支出（預設） | 本人支出，無代墊情況 |
| `"代墊"` | 代他人支付，需收款 | 「代妹買Pizza」、「幫同事墊車費」 |
| `"需支付"` | 他人代墊，需償還 | 「弟代訂房間」、「朋友幫我買票」 |
| `"不索取"` | 代墊但不收回 | 「幫媽買藥，不用還」 |

**保留值**（v1.8 規劃）：
- `"已支付"` — 需支付項目已完成支付
- `"已收款"` — 代墊項目已收到還款

**驗證規則**：
- GPT 必須回傳允許值之一（v1.7 不驗證，信任 GPT）
- 若代墊狀態為「代墊」、「需支付」、「不索取」，必須包含收款支付對象
- 若缺少對象，回傳 error intent

### 收款／支付對象（recipient_or_payer）

**欄位名稱**：`收款支付對象`
**型別**：`Optional[str]`
**預設值**：`""`（空字串）

**格式**：
- 自然語言名稱（如「妹」、「弟」、「同事」、「朋友」、「媽媽」）
- 不進行正規化或驗證
- 保留使用者原始輸入的稱呼

**提取規則**（GPT prompt）：
| 訊息模式 | 提取結果 |
|---------|---------|
| 「代**妹**買」 | `"妹"` |
| 「幫**同事**墊」 | `"同事"` |
| 「**弟**代訂」 | `"弟"` |
| 「**朋友**幫我買」 | `"朋友"` |

**條件顯示**：
- 代墊狀態為「無」→ 保持空字串 `""`
- 代墊狀態為「代墊」、「需支付」、「不索取」→ 必填

## 資料流

### 1. 使用者輸入 → GPT 處理

```
使用者訊息：「代妹購買Pizza兌換券979元現金」

↓ GPT 識別（使用 ADVANCE_PAYMENT_RULES）

GPT 回應 JSON：
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [{
    "品項": "Pizza兌換券",
    "原幣金額": 979,
    "分類": "家庭支出",
    "必要性": "想吃想買但合理",
    "代墊狀態": "代墊",      // ⭐ 新識別
    "收款支付對象": "妹"      // ⭐ 新提取
  }]
}

↓ process_multi_expense() 轉換

BookkeepingEntry(
  品項="Pizza兌換券",
  原幣金額=979.0,
  付款方式="現金",
  代墊狀態="代墊",         // ⭐
  收款支付對象="妹",       // ⭐
  ...
)
```

### 2. BookkeepingEntry → Webhook Payload

```python
payload = {
    "operation": "CREATE",
    "日期": "2025-11-17",
    "品項": "Pizza兌換券",
    "原幣金額": 979.0,
    "付款方式": "現金",
    "代墊狀態": "代墊",          // ⭐ 傳送到 Make.com
    "收款支付對象": "妹",        // ⭐ 傳送到 Make.com
    ...
}
```

### 3. BookkeepingEntry → LINE 確認訊息

```
✅ 記帳成功！

📋 Pizza兌換券
💰 金額：979 元 TWD
💳 付款方式：現金
📂 分類：家庭支出
⭐ 必要性：想吃想買但合理
💸 代墊給：妹              // ⭐ 條件顯示
🔖 交易ID：20251117-143052
📅 日期：2025-11-17
```

## 狀態轉換（未來版本）

v1.7 **不支援**狀態更新，以下為 v1.8 規劃：

```
[代墊] --使用者收到款項--> [已收款]
[需支付] --使用者已支付--> [已支付]
[不索取] --不可轉換-->
```

v1.7 限制：
- ❌ 不支援「代墊」→「已收款」
- ❌ 不支援「需支付」→「已支付」
- ❌ 不支援透過 `update_last_entry` 修改代墊狀態

## 多項目代墊範例

### 情境：部分項目代墊

**使用者訊息**：「早餐80元，午餐150元幫同事代墊，現金」

**GPT 回應**：
```json
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "代墊狀態": "無",          // 一般支出
      "收款支付對象": ""
    },
    {
      "品項": "午餐",
      "原幣金額": 150,
      "代墊狀態": "代墊",        // 代墊項目
      "收款支付對象": "同事"
    }
  ]
}
```

**結果**：
- 生成 2 個 `BookkeepingEntry`
- 共用交易ID：`20251117-143052`
- 發送 2 個 webhook（各自包含代墊狀態）

## 驗證規則摘要

| 規則 | 檢查時機 | 錯誤處理 |
|-----|---------|---------|
| 代墊狀態非「無」時必須有對象 | GPT 處理 | 回傳 error intent |
| 收款支付對象不可為空字串（當代墊狀態非「無」） | GPT 處理 | 回傳 error intent |
| 代墊狀態值必須為允許值之一 | 信任 GPT | 無驗證 |

## 向下相容性

✅ **完全向下相容**：
- 現有 v1.5.0 程式碼已包含 `代墊狀態` 和 `收款支付對象` 欄位
- 預設值確保舊記錄和新記錄格式一致
- Webhook payload 結構無變更
- KV store 無需遷移（儲存任意欄位）

## Phase 1 資料模型完成確認

✅ 核心實體定義完成（重用現有結構）
✅ 欄位規範明確（代墊狀態、收款支付對象）
✅ 資料流設計完整（輸入 → GPT → Entry → Webhook → 回覆）
✅ 驗證規則定義清晰
✅ 向下相容性確認

**可繼續 Phase 1：生成 contracts/**
