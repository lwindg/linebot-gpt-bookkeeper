# LINE Bot GPT Bookkeeper - v1.5.0 技術規劃

**版本**：1.5.0 | **規劃日期**：2025-11-14 | **目標版本**：v1.5.0 多筆支出與視覺識別版
**基於**：v1 MVP (已完成) | **規格**：[spec.md](./spec.md)

---

## 📋 規劃摘要

### 目標

在 **v1 MVP 無狀態架構**基礎上，增加以下能力：
1. **單一訊息多筆支出處理**
2. **圖片/收據識別（GPT Vision API）**

### 與 v1 的差異

#### ✅ 新增功能
- 單一訊息可包含多筆記帳（如「早餐80元現金，午餐150元刷卡」）
- 支援 LINE 圖片訊息類型
- 使用 GPT-4 Vision API 識別收據內容
- 從收據圖片提取品項、金額、付款方式等資訊

#### ✅ 維持 v1 架構
- **無狀態** Serverless function（Vercel）
- **不儲存**對話歷史或任何資料
- 每次請求獨立處理
- 僅支援**台幣**（TWD）
- 簡化的交易ID（時間戳記格式）

#### ❌ 仍然排除（延後到 v2）
- 多輪對話和對話脈絡管理
- 外幣支援和匯率 API
- 即時資訊查詢
- 持久化重試佇列
- 複雜交易ID（YYYYMMDD-NNN 格式）

---

## 🏗️ 系統架構更新

### v1.5.0 架構圖

```
使用者
  ↓ 發送 LINE 訊息（文字 或 圖片）
LINE Platform
  ↓ Webhook
Vercel Serverless Function (/api/webhook.py)
  ├→ 驗證 LINE 簽章
  ├→ 解析訊息類型
  │   ├─ 文字訊息 → 多筆支出解析
  │   │   ├→ 呼叫 OpenAI GPT-4o-mini
  │   │   └→ 識別多筆記帳項目
  │   └─ 圖片訊息 → 收據識別
  │       ├→ 下載圖片內容
  │       ├→ 呼叫 OpenAI GPT-4o (Vision)
  │       └→ 提取收據資訊
  ├→ 若為記帳：為每一筆發送 webhook 到 Make.com（共用交易ID）
  └→ 回覆 LINE 使用者
```

### 技術棧更新

| 層級 | v1 技術 | v1.5.0 新增 | 理由 |
|------|---------|-------------|------|
| **OpenAI 模型** | gpt-4o-mini | **gpt-4o** (Vision) | 支援圖片分析 |
| **LINE 訊息類型** | 文字 | **文字 + 圖片** | 收據上傳功能 |
| **GPT Prompt** | 單筆記帳 | **多筆記帳識別** | 處理「早餐80，午餐150」格式 |
| **HTTP Client** | requests | **requests** (新增圖片下載) | 下載 LINE 圖片內容 |

---

## 📁 專案結構變更

### 新增/修改檔案

```diff
linebot-gpt-bookkeeper/
├── api/
│   └── webhook.py              # 修改：新增圖片訊息處理邏輯
├── app/
│   ├── __init__.py
│   ├── config.py               # 修改：新增 LINE_IMAGE_DOWNLOAD_URL
│   ├── line_handler.py         # 修改：新增 handle_image_message()
│   ├── gpt_processor.py        # 修改：新增 process_multi_expense(), process_image()
│   ├── webhook_sender.py       # 修改：支援發送多個 webhook
+   ├── image_handler.py         # 新增：圖片下載和處理
│   └── prompts.py              # 修改：新增多筆支出 prompt、Vision prompt
├── tests/
│   ├── test_gpt_processor.py   # 修改：新增多筆支出測試
+   ├── test_image_handler.py    # 新增：圖片處理測試
│   └── test_integration.py     # 修改：新增圖片訊息測試案例
```

---

## 🔧 核心模組設計更新

### 1. 新增模組：`app/image_handler.py`

**職責**：
- 從 LINE 下載圖片內容
- 將圖片轉換為 base64 編碼
- 呼叫 GPT-4 Vision API 分析收據
- 回傳結構化收據資料

**主要函式**：

```python
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class ReceiptItem:
    """單筆收據項目"""
    品項: str
    原幣金額: float
    付款方式: Optional[str] = None
    分類: Optional[str] = None

def download_image(message_id: str, line_bot_api: LineBotApi) -> bytes:
    """
    從 LINE 下載圖片內容

    參數：
        message_id: LINE 訊息 ID
        line_bot_api: LINE Bot API 實例

    回傳：
        bytes: 圖片二進位內容

    錯誤處理：
        - 下載失敗：拋出 ImageDownloadError
        - 圖片過大（>10MB）：拋出 ImageTooLargeError
    """
    pass

def encode_image_base64(image_data: bytes) -> str:
    """
    將圖片轉換為 base64 編碼

    參數：
        image_data: 圖片二進位資料

    回傳：
        str: base64 編碼字串（用於 GPT Vision API）
    """
    import base64
    return base64.b64encode(image_data).decode('utf-8')

def process_receipt_image(
    image_data: bytes,
    openai_client
) -> List[ReceiptItem]:
    """
    使用 GPT-4 Vision API 分析收據圖片

    參數：
        image_data: 圖片二進位資料
        openai_client: OpenAI client 實例

    回傳：
        List[ReceiptItem]: 識別出的收據項目列表

    流程：
        1. 將圖片編碼為 base64
        2. 呼叫 GPT-4o Vision API
        3. 解析回應（JSON 格式）
        4. 驗證資料完整性
        5. 回傳 ReceiptItem 列表

    錯誤處理：
        - 圖片模糊/無法識別 → 回傳空列表 + 錯誤訊息
        - 非收據圖片 → 回傳空列表 + 提示訊息
        - API 失敗 → 拋出 VisionAPIError
    """
    pass
```

---

### 2. 更新模組：`app/gpt_processor.py`

#### 新增資料結構

```python
from typing import List, Literal, Optional
from dataclasses import dataclass

@dataclass
class BookkeepingEntry:
    """單筆記帳資料（與 v1 相同）"""
    intent: Literal["bookkeeping", "conversation"]
    # ... (其他欄位同 v1)

@dataclass
class MultiExpenseResult:
    """多筆支出處理結果（新增）"""
    intent: Literal["multi_bookkeeping", "conversation", "error"]
    entries: List[BookkeepingEntry]  # 多筆記帳項目
    error_message: Optional[str] = None  # 錯誤訊息（若有）
```

#### 新增函式

```python
def process_multi_expense(user_message: str) -> MultiExpenseResult:
    """
    處理可能包含多筆支出的訊息（新增）

    參數：
        user_message: 使用者訊息文字

    回傳：
        MultiExpenseResult: 處理結果

    流程：
        1. 呼叫 GPT 識別是否包含多筆支出
        2. 若是單筆 → 使用原有 process_message() 處理
        3. 若是多筆 → 解析每一筆支出
        4. 驗證每一筆資料完整性（品項、金額、付款方式）
        5. 生成共用交易ID（時間戳記格式）
        6. 回傳 MultiExpenseResult

    範例輸入：
        「早餐80元現金，午餐150元刷卡」

    範例輸出：
        MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[
                BookkeepingEntry(品項="早餐", 原幣金額=80, 付款方式="現金", ...),
                BookkeepingEntry(品項="午餐", 原幣金額=150, 付款方式="信用卡", ...)
            ]
        )

    錯誤處理：
        - 任一筆資訊不完整 → intent="error", error_message="第N筆缺少..."
        - 無法區分多筆 → intent="error", error_message="無法確定是一筆還是多筆..."
    """
    pass

def process_receipt_data(
    receipt_items: List[ReceiptItem]
) -> MultiExpenseResult:
    """
    將收據資料轉換為記帳項目（新增）

    參數：
        receipt_items: 從圖片識別出的收據項目

    回傳：
        MultiExpenseResult: 包含完整記帳資料的結果

    流程：
        1. 為每個 ReceiptItem 補充預設值
        2. 生成共用交易ID
        3. 推斷分類、必要性等欄位
        4. 回傳 MultiExpenseResult
    """
    pass
```

---

### 3. 更新模組：`app/line_handler.py`

#### 新增函式

```python
def handle_image_message(
    event: MessageEvent,
    line_bot_api: LineBotApi
) -> None:
    """
    處理圖片訊息的主流程（新增）

    流程：
        1. 取得圖片訊息 ID
        2. 呼叫 image_handler.download_image() 下載圖片
        3. 呼叫 image_handler.process_receipt_image() 分析收據
        4. 若識別成功：
           - 轉換為 BookkeepingEntry 列表
           - 為每一筆發送 webhook
           - 回覆確認訊息（列出所有項目）
        5. 若識別失敗：
           - 回覆「無法辨識收據資訊，請提供文字描述」

    錯誤處理：
        - 下載失敗 → 「圖片下載失敗，請稍後再試」
        - Vision API 失敗 → 「無法處理圖片，請改用文字描述」
        - 非台幣收據 → 「v1.5.0 僅支援台幣，請提供文字描述並換算台幣金額」
    """
    pass
```

#### 修改函式

```python
def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    處理文字訊息的主流程（修改）

    v1.5.0 變更：
        - 原本呼叫 process_message() → 改為呼叫 process_multi_expense()
        - 支援處理多筆支出結果
        - 為每一筆發送獨立 webhook（共用交易ID）

    新流程：
        1. 取得使用者訊息文字
        2. 呼叫 gpt_processor.process_multi_expense() 分析
        3. 根據 intent 處理：
           - multi_bookkeeping → 發送多個 webhook + 回覆確認
           - conversation → 回覆對話
           - error → 回覆錯誤訊息
    """
    pass
```

---

### 4. 更新模組：`app/webhook_sender.py`

#### 新增函式

```python
def send_multiple_webhooks(
    entries: List[BookkeepingEntry],
    transaction_id: str
) -> tuple[int, int]:
    """
    為多筆記帳項目發送 webhook（新增）

    參數：
        entries: 記帳項目列表
        transaction_id: 共用的交易ID

    回傳：
        tuple[int, int]: (成功數量, 失敗數量)

    流程：
        1. 為每個 entry 使用相同的 transaction_id
        2. 依序呼叫 send_to_webhook()
        3. 記錄成功/失敗數量
        4. 回傳統計結果

    錯誤處理：
        - 部分失敗：繼續處理剩餘項目，最後回報「N筆成功，M筆失敗」
        - 全部失敗：回報「記帳失敗，請稍後重試」
    """
    pass
```

---

### 5. 更新模組：`app/prompts.py`

#### 新增 Prompt

```python
# ===== 多筆支出識別 Prompt（新增） =====

MULTI_EXPENSE_PROMPT = """你是專業的記帳助手，協助使用者記錄日常開支。

## v1.5.0 新功能：支援單一訊息多個項目（同一次支出）

**重要概念**：一條訊息代表「一次支出行為」，可能包含多個項目，但只有「一種付款方式」。

使用者可能在一條訊息中描述多個項目，例如：
- 「早餐80元，午餐150元，現金」（兩個項目，共用付款方式「現金」）
- 「咖啡50，三明治35，用狗卡」（兩個項目，共用付款方式「台新狗卡」）
- 「早餐三明治35，飲料30，現金」（兩個項目，共用付款方式「現金」）

## 你的任務

1. **判斷意圖**：
   - 單項記帳：僅包含一個品項的支出
   - 多項記帳：包含多個品項的支出（用逗號、分號、頓號、換行分隔），但只有一種付款方式
   - 一般對話：非記帳相關訊息
   - 錯誤：資訊不完整或包含多種付款方式

2. **多項記帳處理**：
   - 識別每一個獨立的項目
   - 為每個項目提取：品項、金額
   - 識別共用的付款方式（通常在最後或前面統一說明）
   - **重要**：所有項目必須共用同一種付款方式
   - 若任一項目缺少金額，回傳 error intent
   - 若缺少付款方式，回傳 error intent

3. **區分不同情況**：
   - 「三明治和咖啡80元現金」 → **模糊**：無法確定是一個項目還是兩個項目，回傳 error，提示「無法確定是一個項目還是多個項目（三明治、咖啡），請分別描述金額」
   - 「早餐80元現金，午餐150元刷卡」 → **兩次獨立支出**（不同付款方式），回傳 error，提示「偵測到不同付款方式，請分開記帳」
   - 「早餐80元，午餐150元，現金」 → **正確**：一次支出，兩個項目，共用付款方式

## 輸出格式

### 多項記帳（共用付款方式）
```json
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [
    {
      "品項": "早餐",
      "原幣金額": 80,
      "分類": "家庭／餐飲／早餐",
      "必要性": "必要日常支出"
    },
    {
      "品項": "午餐",
      "原幣金額": 150,
      "分類": "家庭／餐飲／午餐",
      "必要性": "必要日常支出"
    }
  ]
}
```

**注意**：付款方式在最外層，所有項目共用。

### 錯誤（資訊不完整或多種付款方式）
```json
{
  "intent": "error",
  "message": "第二個項目缺少金額，請提供完整資訊"
}
```

或

```json
{
  "intent": "error",
  "message": "偵測到不同付款方式，請分開記帳"
}
```

（其他欄位標準值和單筆處理邏輯與 v1 相同）
"""

# ===== GPT Vision 收據識別 Prompt（新增） =====

RECEIPT_VISION_PROMPT = """你是專業的收據辨識助手，協助使用者從收據圖片中提取記帳資訊。

## 你的任務

1. **判斷圖片類型**：
   - 是否為收據或發票
   - 若非收據（如風景照、人物照），回傳 "not_receipt"

2. **提取資訊**（若為收據）：
   - 品項名稱（多筆則列出所有品項）
   - 金額（每個品項的金額）
   - 總金額
   - 日期（若有）
   - 付款方式（若圖片上有標示，如「現金」、「信用卡」）

3. **幣別判斷**：
   - **重要**：v1.5.0 僅支援台幣（TWD、NT$、元）
   - 若為其他幣別（USD、JPY等），回傳 "unsupported_currency"

4. **品質檢查**：
   - 圖片模糊、資訊不清晰 → 回傳 "unclear"
   - 缺少關鍵資訊（品項或金額） → 回傳 "incomplete"

## 輸出格式

### 成功識別
```json
{
  "status": "success",
  "currency": "TWD",
  "date": "2025-11-14",
  "items": [
    {
      "品項": "美式咖啡",
      "金額": 50
    },
    {
      "品項": "三明治",
      "金額": 80
    }
  ],
  "total": 130,
  "payment_method": "現金"
}
```

### 錯誤情況
```json
{
  "status": "not_receipt",
  "message": "這不是收據圖片"
}
```

```json
{
  "status": "unsupported_currency",
  "message": "收據幣別為 JPY，v1.5.0 僅支援台幣"
}
```

```json
{
  "status": "unclear",
  "message": "圖片模糊，無法辨識品項和金額"
}
```

請嚴格按照以上格式輸出 JSON。
"""
```

---

## 🔄 完整流程圖

### 流程 A：多項目文字支出（共用付款方式）

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用者在 LINE 發送：「早餐80元，午餐150元，現金」          │
│    （一次支出行為，兩個項目，共用付款方式）                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. LINE Platform → Vercel /api/webhook                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. webhook.py 驗證簽章，解析 MessageEvent（文字）            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. line_handler.handle_text_message()                       │
│    呼叫 gpt_processor.process_multi_expense()               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. GPT-4o-mini 分析多項目支出                                │
│    回傳：                                                    │
│    {                                                        │
│      "intent": "multi_bookkeeping",                        │
│      "payment_method": "現金",                             │
│      "items": [                                            │
│        { 品項:"早餐", 金額:80 },                            │
│        { 品項:"午餐", 金額:150 }                            │
│      ]                                                     │
│    }                                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. 生成共用交易ID：20251114-143052                           │
│    為兩個項目分別補充預設值（共用付款方式「現金」）            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. webhook_sender.send_multiple_webhooks()                  │
│    POST #1: { 品項:"早餐", 金額:80, 付款:"現金",            │
│               交易ID:20251114-143052 }                      │
│    POST #2: { 品項:"午餐", 金額:150, 付款:"現金",           │
│               交易ID:20251114-143052 }                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. 構建確認訊息（列出兩個項目）                               │
│    「✅ 記帳成功！已記錄 2 個項目：                            │
│                                                             │
│     📋 #1 早餐                                               │
│     💰 80 元 | 現金                                          │
│     📂 家庭／餐飲／早餐                                       │
│                                                             │
│     📋 #2 午餐                                               │
│     💰 150 元 | 現金                                         │
│     📂 家庭／餐飲／午餐                                       │
│                                                             │
│     🔖 交易ID：20251114-143052                               │
│     💳 付款方式：現金（共用）」                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. line_bot_api.reply_message() 回覆使用者                   │
└─────────────────────────────────────────────────────────────┘
```

### 流程 B：收據圖片識別

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用者在 LINE 上傳收據圖片                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. LINE Platform → Vercel /api/webhook                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. webhook.py 驗證簽章，解析 MessageEvent（圖片）            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. line_handler.handle_image_message()                      │
│    呼叫 image_handler.download_image()                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. 從 LINE 下載圖片內容（bytes）                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. image_handler.process_receipt_image()                    │
│    - 圖片編碼為 base64                                       │
│    - 呼叫 GPT-4o Vision API                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. GPT-4o Vision 分析收據                                    │
│    回傳：                                                    │
│    {                                                        │
│      "status": "success",                                  │
│      "currency": "TWD",                                    │
│      "items": [                                            │
│        { 品項:"咖啡", 金額:50 },                            │
│        { 品項:"三明治", 金額:80 }                           │
│      ],                                                    │
│      "payment_method": "現金"                               │
│    }                                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. gpt_processor.process_receipt_data()                     │
│    轉換為 BookkeepingEntry 列表並補充預設值                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. webhook_sender.send_multiple_webhooks()                  │
│    POST #1: { 品項:"咖啡", 金額:50, ... }                   │
│    POST #2: { 品項:"三明治", 金額:80, ... }                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. 構建確認訊息並回覆                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 測試策略

### 單元測試更新

#### **test_gpt_processor.py**（新增測試案例）

```python
# 多項目支出測試（共用付款方式）
def test_multi_items_shared_payment():
    """測試識別多個項目（共用付款方式）"""
    result = process_multi_expense("早餐80元，午餐150元，現金")
    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 2
    assert result.entries[0].品項 == "早餐"
    assert result.entries[1].品項 == "午餐"
    # 驗證共用付款方式
    assert result.entries[0].付款方式 == "現金"
    assert result.entries[1].付款方式 == "現金"

def test_multi_items_incomplete_amount():
    """測試多項目但第二項缺少金額"""
    result = process_multi_expense("早餐80元，午餐買了便當，現金")
    assert result.intent == "error"
    assert "第二個項目缺少金額" in result.error_message

def test_multi_items_missing_payment():
    """測試多項目但缺少付款方式"""
    result = process_multi_expense("早餐80元，午餐150元")
    assert result.intent == "error"
    assert "請提供付款方式" in result.error_message

def test_multi_items_ambiguous():
    """測試模糊情況（無法區分一個項目還是多個項目）"""
    result = process_multi_expense("三明治和咖啡80元現金")
    assert result.intent == "error"
    assert "無法確定是一個項目還是多個項目" in result.error_message

def test_multi_items_different_payments():
    """測試包含不同付款方式（應拒絕）"""
    result = process_multi_expense("早餐80元現金，午餐150元刷卡")
    assert result.intent == "error"
    assert "偵測到不同付款方式" in result.error_message

def test_multi_items_shared_transaction_id():
    """測試多項目共用交易ID"""
    result = process_multi_expense("早餐50，午餐120，用現金")
    tx_id = result.entries[0].交易ID
    assert all(e.交易ID == tx_id for e in result.entries)
```

#### **test_image_handler.py**（新增檔案）

```python
def test_download_image_success(mocker):
    """測試成功下載圖片"""
    # Mock LINE API
    pass

def test_download_image_failure(mocker):
    """測試圖片下載失敗"""
    pass

def test_process_receipt_success(mocker):
    """測試成功識別收據（單筆項目）"""
    pass

def test_process_receipt_multi_items(mocker):
    """測試成功識別收據（多筆項目）"""
    pass

def test_process_receipt_not_receipt(mocker):
    """測試非收據圖片（風景照）"""
    pass

def test_process_receipt_unsupported_currency(mocker):
    """測試非台幣收據（日幣）"""
    pass

def test_process_receipt_unclear(mocker):
    """測試模糊收據圖片"""
    pass
```

### 整合測試更新

#### **test_integration.py**（新增測試案例）

```python
def test_end_to_end_multi_expense():
    """端到端測試：多筆文字支出"""
    # 模擬 LINE webhook 請求（多筆支出）
    # 驗證 webhook 發送兩次
    # 驗證回覆訊息格式正確
    pass

def test_end_to_end_receipt_image():
    """端到端測試：收據圖片識別"""
    # 模擬 LINE webhook 請求（圖片訊息）
    # Mock 圖片下載
    # Mock GPT Vision API 回應
    # 驗證 webhook 發送
    # 驗證回覆訊息
    pass

def test_image_message_download_failure():
    """測試圖片下載失敗情境"""
    pass

def test_image_message_vision_api_failure():
    """測試 Vision API 失敗情境"""
    pass
```

### 手動測試清單

#### 多項目文字支出（共用付款方式）
- [ ] 「早餐80元，午餐150元，現金」 → 記錄兩個項目，共用付款方式和交易ID
- [ ] 「咖啡50，三明治35，用狗卡」 → 正確識別兩個項目，共用「台新狗卡」
- [ ] 「早餐三明治35，飲料30，現金」 → 兩個項目都用現金
- [ ] 「早餐80元，午餐買了便當，現金」（第二項不完整） → 錯誤提示「第二個項目缺少金額」
- [ ] 「早餐80元，午餐150元」（缺少付款方式） → 錯誤提示「請提供付款方式」
- [ ] 「三明治和咖啡80元現金」（模糊） → 錯誤提示「無法確定是一個項目還是多個項目」
- [ ] 「早餐80元現金，午餐150元刷卡」（不同付款方式） → 錯誤提示「偵測到不同付款方式，請分開記帳」

#### 收據圖片
- [ ] 上傳清晰台幣收據（單筆項目） → 正確識別並記帳
- [ ] 上傳清晰台幣收據（多筆項目） → 識別所有項目
- [ ] 上傳模糊收據 → 錯誤訊息「圖片不清晰，請用文字描述」
- [ ] 上傳非收據圖片（風景照） → 錯誤訊息「無法識別收據」
- [ ] 上傳日幣收據 → 錯誤訊息「僅支援台幣」

---

## 🚀 部署規劃

### 環境變數更新

**新增變數**：

| 變數 | 說明 | 範例值 | 必要性 |
|------|------|--------|--------|
| `GPT_VISION_MODEL` | GPT Vision 模型 | `gpt-4o` | ⚠️ 選用（預設 gpt-4o） |

**維持不變**：
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `OPENAI_API_KEY`
- `WEBHOOK_URL`
- `GPT_MODEL` (用於文字分析，保持 gpt-4o-mini)

### Vercel 配置更新

**vercel.json** 維持不變（無需修改）

### 部署步驟

1. **更新程式碼**
   - 將 v1.5.0 變更推送到 GitHub
   - Vercel 自動偵測並部署

2. **更新環境變數**
   - 在 Vercel Dashboard 新增 `GPT_VISION_MODEL`

3. **測試**
   - 執行手動測試清單
   - 確認圖片訊息功能正常

---

## 📊 效能考量

### 成本估算（OpenAI API）

#### v1 成本
- **文字分析**：gpt-4o-mini ($0.15 / 1M input tokens, $0.60 / 1M output tokens)
- 平均每次：約 500 input + 200 output tokens ≈ $0.0002 / 次

#### v1.5.0 新增成本
- **圖片分析**：gpt-4o Vision ($2.50 / 1M input tokens, $10.00 / 1M output tokens)
- 每張圖片：約 1000 input (含圖片) + 300 output tokens ≈ $0.006 / 次
- **預估**：假設 20% 訊息使用圖片，月成本增加約 $3-5 USD（1000 次請求）

### 回應時間

#### v1 回應時間
- 文字訊息：2-4 秒

#### v1.5.0 回應時間
- 文字訊息（多筆）：2-4 秒（與 v1 相同）
- 圖片訊息：4-7 秒
  - 圖片下載：0.5-1 秒
  - Vision API：3-5 秒
  - Webhook 發送：0.5-1 秒

✅ 仍在 LINE Webhook 10 秒 timeout 範圍內

### Vercel Function 限制檢查

- **執行時間**：最長 7 秒（圖片訊息） < 10 秒限制 ✅
- **記憶體**：圖片處理約需 200MB < 1024MB 限制 ✅
- **Function 大小**：新增模組約 50KB < 50MB 限制 ✅

---

## 🔒 安全性考量

### 1. LINE 圖片存取

- ✅ LINE 圖片 URL 包含簽章參數（自動過期）
- ✅ 使用 LINE Bot API 官方方法下載（內建驗證）
- ✅ 圖片下載後立即處理，不儲存到磁碟

### 2. OpenAI Vision API

- ✅ 圖片以 base64 編碼傳送（HTTPS）
- ✅ 不儲存圖片資料
- ✅ API Key 使用環境變數保護

### 3. 圖片大小限制

- ✅ 限制圖片大小 < 10MB（避免超時和記憶體問題）
- ✅ 超過限制時回覆「圖片過大，請重新上傳」

---

## 📝 開發檢查清單

### Phase 1: 多筆支出功能（P1）

- [ ] 更新 `app/prompts.py` - 新增 MULTI_EXPENSE_PROMPT
- [ ] 更新 `app/gpt_processor.py`
  - [ ] 新增 MultiExpenseResult 資料類別
  - [ ] 實作 process_multi_expense() 函式
  - [ ] 測試多筆支出解析邏輯
- [ ] 更新 `app/line_handler.py`
  - [ ] 修改 handle_text_message() 支援多筆
  - [ ] 修改確認訊息格式（列出所有項目）
- [ ] 更新 `app/webhook_sender.py`
  - [ ] 實作 send_multiple_webhooks() 函式
- [ ] 撰寫測試
  - [ ] test_gpt_processor.py - 多筆支出測試
  - [ ] test_integration.py - 端到端測試

### Phase 2: 圖片識別功能（P1）

- [ ] 新增 `app/image_handler.py`
  - [ ] 實作 download_image() 函式
  - [ ] 實作 encode_image_base64() 函式
  - [ ] 實作 process_receipt_image() 函式
- [ ] 更新 `app/prompts.py` - 新增 RECEIPT_VISION_PROMPT
- [ ] 更新 `app/gpt_processor.py`
  - [ ] 實作 process_receipt_data() 函式
- [ ] 更新 `app/line_handler.py`
  - [ ] 實作 handle_image_message() 函式
- [ ] 更新 `api/webhook.py`
  - [ ] 新增圖片訊息 event 處理
- [ ] 撰寫測試
  - [ ] test_image_handler.py - 圖片處理測試
  - [ ] test_integration.py - 圖片訊息端到端測試

### Phase 3: 整合測試（P1）

- [ ] 執行所有單元測試
- [ ] 執行整合測試
- [ ] 手動測試：多筆文字支出
- [ ] 手動測試：收據圖片識別
- [ ] 效能測試：圖片處理時間 < 7 秒

### Phase 4: 部署（P1）

- [ ] 更新 Vercel 環境變數
- [ ] 部署到 Vercel
- [ ] 驗證 LINE Bot 運作正常
- [ ] 確認 Make.com 接收多筆 webhook

### Phase 5: 驗證（P1）

- [ ] 完成手動測試清單（多筆文字）
- [ ] 完成手動測試清單（圖片）
- [ ] 確認錯誤處理正常
- [ ] 確認成本在預期範圍內

---

## 🎯 成功標準

### 功能驗收（多項目文字支出）

- ✅ 「早餐80元，午餐150元，現金」 → 記錄兩個項目，共用交易ID和付款方式
- ✅ 兩個項目分別發送 webhook 到 Make.com，共用付款方式「現金」
- ✅ 確認訊息列出所有項目，並標註「付款方式：現金（共用）」
- ✅ 不完整資訊提示清楚（如「第二個項目缺少金額」、「請提供付款方式」）
- ✅ 模糊情況提示清楚（如「無法確定是一個項目還是多個項目」）
- ✅ 不同付款方式拒絕（如「偵測到不同付款方式，請分開記帳」）

### 功能驗收（圖片識別）

- ✅ 清晰台幣收據正確識別並記帳
- ✅ 多筆項目收據全部識別
- ✅ 模糊收據回覆錯誤訊息
- ✅ 非收據圖片回覆錯誤訊息
- ✅ 非台幣收據回覆「僅支援台幣」

### 非功能驗收

- ✅ 文字訊息回應時間 < 4 秒
- ✅ 圖片訊息回應時間 < 7 秒
- ✅ 測試覆蓋率 > 80%
- ✅ 維持 v1 的無狀態架構（不引入資料庫）
- ✅ API 成本增加在預期範圍內（< $10/月）

### v1.5.0 維持 v1 限制

- ❌ 仍不支援多輪對話（圖片識別失敗不追問）
- ❌ 仍不支援外幣（收據必須為台幣）
- ❌ 仍無 Webhook 重試（失敗僅告知使用者）

---

## 📚 依賴套件更新

### requirements.txt 新增

```diff
  # LINE Bot SDK
  line-bot-sdk==3.8.0

  # OpenAI SDK
  openai>=1.12.0

  # HTTP Client
  requests>=2.31.0

  # Web Framework (for Vercel)
  Flask>=3.0.0

  # Environment Variables
  python-dotenv>=1.0.0

  # Testing
  pytest>=7.4.0
  pytest-mock>=3.12.0
+
+ # Image Processing (若需要本地驗證圖片格式)
+ # Pillow>=10.0.0  # 選用，Vercel 環境不一定需要
```

**備註**：v1.5.0 主要使用 OpenAI Vision API，無需額外圖片處理庫（除非需要本地驗證）。

---

## 📞 問題與決策記錄

### Q1: 為何圖片識別失敗時不追問使用者？

**決策**：維持 v1 無狀態架構，識別失敗直接提示「請用文字描述」

- **理由**：
  - v1.5.0 目標是增加圖片識別「能力」，不改變架構
  - 追問機制需要對話脈絡儲存（v2 才引入）
  - 使用者可立即改用文字訊息記帳（體驗仍佳）
- **權衡**：圖片識別失敗時需重新輸入 → v2 加入多輪對話改善

### Q2: 多項目支出為何共用交易ID和付款方式？

**決策**：單一訊息的所有項目共用同一個時間戳記交易ID和付款方式

- **理由**：
  - 符合「同一次支出行為」的概念（如超商一次購買多個商品）
  - 實務上，一次購物行為通常只有一種付款方式
  - 方便使用者追蹤「這次買了哪些東西」
  - Make.com 可透過相同 ID 關聯多個項目
- **實作**：在 `附註` 欄位標註「與交易ID XXX 的其他項目為同一訊息」
- **特殊情況**：若使用者在同一訊息中混合不同付款方式（如「早餐80元現金，午餐150元刷卡」），系統應拒絕並提示「偵測到不同付款方式，請分開記帳」，因為這代表兩次獨立的支出行為

### Q3: 為何使用 gpt-4o Vision 而非 OCR？

**決策**：使用 GPT-4o Vision API 進行收據識別

- **理由**：
  - GPT Vision 可同時做 OCR + 語義理解（提取品項、分類）
  - 無需額外 OCR 服務或模型
  - 符合「簡單勝過完美」原則
  - 開發速度快
- **權衡**：成本較高（$0.006/次 vs 免費 OCR） → 但符合 MVP 快速驗證原則

### Q4: 圖片大小限制為何設為 10MB？

**決策**：限制圖片大小 < 10MB

- **理由**：
  - LINE 原生支援最大 10MB 圖片
  - Vercel Function 1024MB 記憶體足夠處理
  - 避免超大圖片導致 timeout
- **實作**：下載時檢查 Content-Length，超過則拒絕

---

## ✅ 規劃完成確認

- [x] v1.5.0 功能範圍明確
- [x] 與 v1 的差異清楚定義
- [x] 新增模組設計完成
- [x] 更新模組職責明確
- [x] 資料結構定義
- [x] 完整流程圖（文字多筆 + 圖片）
- [x] 錯誤處理策略
- [x] 測試策略規劃
- [x] 效能和成本評估
- [x] 安全性考量
- [x] 開發檢查清單
- [x] 成功驗收標準

**下一步**：執行 `/speckit.tasks` 生成 v1.5.0 可執行任務清單

---

**版本歷史**：
- v1.5.0 (2025-11-14) - v1.5.0 技術規劃完成
