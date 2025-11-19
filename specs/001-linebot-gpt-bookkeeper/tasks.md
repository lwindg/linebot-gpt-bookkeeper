# LINE Bot GPT Bookkeeper - v1.5.0 任務清單

**版本**：1.5.0 | **建立日期**：2025-11-14 | **目標版本**：v1.5.0 多筆支出與視覺識別版
**輸入**：[spec.md](./spec.md), [plan-v1.5.0.md](./plan-v1.5.0.md)

---

## 📋 任務概覽

本文件定義 v1.5.0 的所有開發任務，按照依賴順序和優先級組織。

### 任務統計

- **總任務數**：60+ 個任務
- **P1（必要）**：58 個
- **P2（文件）**：2 個
- **預估總工時**：約 16-24 小時（2-3 個工作天）

### 階段劃分

1. **Phase 0 - 前置準備**：3 個任務（已完成）
2. **Phase 1 - 多項目支出功能**：13 個任務（6-8 小時）
3. **Phase 2 - 圖片識別功能**：11 個任務（6-8 小時）
4. **Phase 3 - 整合測試**：5 個任務（2-3 小時）
5. **Phase 4 - 部署準備**：5 個任務（1-2 小時）
6. **Phase 5 - 手動驗證**：20 個測試案例（2-3 小時）
7. **Phase 6 - 文件更新**：2 個任務（1 小時）

---

## 任務格式說明

**格式**：`[ID] [P?] [Story] 任務描述`

- **[P]**: 可平行執行（不同檔案，無相依性）
- **[Story]**: 任務所屬使用者故事（US1, US2）
- 每個任務包含完整檔案路徑

---

## Phase 0: 前置準備

**目的**：確認 v1 MVP 基礎已就緒

### T000: 驗證 v1 MVP 功能運作正常

**優先級**：P1
**狀態**：✅ 已完成
**預估時間**：30 分鐘
**依賴**：無

**描述**：
確認 v1 MVP 的單筆記帳功能正常運作，作為 v1.5.0 的基礎。

**驗收標準**：
- [x] 單筆記帳功能正常（如「午餐120元現金」）
- [x] Webhook 正確發送到 Make.com
- [x] 確認訊息格式正確
- [x] 錯誤處理正常

---

### T001: 確認現有專案結構符合規劃

**優先級**：P1
**狀態**：✅ 已完成
**預估時間**：15 分鐘
**依賴**：T000

**描述**：
檢查現有專案結構是否符合 plan-v1.5.0.md 的規劃，確認可以直接擴充。

**驗收標準**：
- [x] `api/webhook.py` 存在
- [x] `app/` 目錄包含所有 v1 模組
- [x] `tests/` 目錄結構正確

---

### T002: 確認環境變數設定完整

**優先級**：P1
**狀態**：✅ 已完成
**預估時間**：15 分鐘
**依賴**：T001

**描述**：
確認 Vercel 環境變數包含所有 v1 必要變數，準備新增 v1.5.0 變數。

**驗收標準**：
- [x] `LINE_CHANNEL_ACCESS_TOKEN` 已設定
- [x] `LINE_CHANNEL_SECRET` 已設定
- [x] `OPENAI_API_KEY` 已設定
- [x] `WEBHOOK_URL` 已設定
- [x] `GPT_MODEL` 已設定（gpt-4o-mini）

**Checkpoint 0.1**: v1 MVP 基礎驗證完成，可開始 v1.5.0 開發

---

## Phase 1: 多項目支出功能

**目標**：支援單一訊息多個項目，共用付款方式和交易ID

**使用者故事**：US1 場景 6-7（多項目文字支出）

**獨立測試**：發送「早餐80元，午餐150元，現金」，驗證記錄兩個項目且共用付款方式

---

### T101 [P] [US1]: 建立 MULTI_EXPENSE_PROMPT

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T002
**檔案**：`app/prompts.py`

**描述**：
在 `app/prompts.py` 中建立 `MULTI_EXPENSE_PROMPT`，定義多項目識別邏輯。

**驗收標準**：
- [ ] 定義「一條訊息 = 一次支出 = 一種付款方式」的概念
- [ ] 說明如何識別多個項目（逗號、分號、頓號、換行分隔）
- [ ] 定義共用付款方式的提取邏輯
- [ ] 定義錯誤情況（不同付款方式、模糊情況、缺少資訊）
- [ ] 定義 JSON 輸出格式（payment_method 在最外層，items 陣列）
- [ ] 包含完整範例（正確、錯誤情況）

**實作筆記**：
```python
MULTI_EXPENSE_PROMPT = """你是專業的記帳助手...

## v1.5.0 新功能：支援單一訊息多個項目（同一次支出）

**重要概念**：一條訊息代表「一次支出行為」，可能包含多個項目，但只有「一種付款方式」。

## 輸出格式

### 多項記帳（共用付款方式）
{
  "intent": "multi_bookkeeping",
  "payment_method": "現金",
  "items": [...]
}
"""
```

---

### T102 [P] [US1]: 更新資料類別

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：45 分鐘
**依賴**：T002
**檔案**：`app/gpt_processor.py`

**描述**：
在 `app/gpt_processor.py` 中新增 `MultiExpenseResult` 資料類別。

**驗收標準**：
- [ ] 新增 `MultiExpenseResult` dataclass
- [ ] 包含欄位：`intent`, `entries: List[BookkeepingEntry]`, `error_message: Optional[str]`
- [ ] intent 類型：`Literal["multi_bookkeeping", "conversation", "error"]`
- [ ] 確保 `BookkeepingEntry` 可被重複使用（多項目情況）

**實作筆記**：
```python
@dataclass
class MultiExpenseResult:
    """多項目支出處理結果"""
    intent: Literal["multi_bookkeeping", "conversation", "error"]
    entries: List[BookkeepingEntry] = field(default_factory=list)
    error_message: Optional[str] = None
```

---

### T103 [US1]: 實作 process_multi_expense() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：2 小時
**依賴**：T101, T102
**檔案**：`app/gpt_processor.py`

**描述**：
實作 `process_multi_expense()` 函式，處理單一訊息的多項目支出。

**驗收標準**：
- [ ] 函式簽章：`def process_multi_expense(user_message: str) -> MultiExpenseResult`
- [ ] 使用 `MULTI_EXPENSE_PROMPT` 呼叫 GPT-4o-mini
- [ ] 解析 JSON 回應（payment_method + items）
- [ ] 驗證所有項目資訊完整性（品項、金額）
- [ ] 驗證付款方式存在
- [ ] 處理錯誤情況：
  - 不同付款方式 → error intent
  - 缺少金額 → error intent
  - 缺少付款方式 → error intent
  - 模糊情況 → error intent
- [ ] 生成共用交易ID（時間戳記格式，如 `20251114-143052`）
- [ ] 為所有項目補充預設值（日期、原幣別=TWD、匯率=1.0、共用付款方式）
- [ ] 回傳 `MultiExpenseResult`

**實作筆記**：
- 使用 OpenAI SDK 呼叫 API
- JSON 解析錯誤應回傳 error intent
- 交易ID 使用 `datetime.now().strftime("%Y%m%d-%H%M%S")`

---

### T104 [US1]: 更新 handle_text_message() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1.5 小時
**依賴**：T103
**檔案**：`app/line_handler.py`

**描述**：
更新 `handle_text_message()` 函式，改為呼叫 `process_multi_expense()`。

**驗收標準**：
- [ ] 改為呼叫 `gpt_processor.process_multi_expense()` 取代原有 `process_message()`
- [ ] 處理 `MultiExpenseResult` 的三種 intent：
  - `multi_bookkeeping` → 發送多個 webhook + 回覆確認
  - `conversation` → 回覆對話
  - `error` → 回覆錯誤訊息
- [ ] 支援單項目和多項目兩種情況（單項目時 entries 長度為 1）
- [ ] 呼叫 `send_multiple_webhooks()` 發送 webhook

**實作筆記**：
- 保持與 v1 的向後相容性（單項目情況）
- 錯誤訊息從 `result.error_message` 取得

---

### T105 [P] [US1]: 實作 send_multiple_webhooks() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T002
**檔案**：`app/webhook_sender.py`

**描述**：
實作 `send_multiple_webhooks()` 函式，為多個項目發送 webhook。

**驗收標準**：
- [ ] 函式簽章：`def send_multiple_webhooks(entries: List[BookkeepingEntry], transaction_id: str) -> tuple[int, int]`
- [ ] 為每個 entry 使用相同的 transaction_id
- [ ] 依序呼叫 `send_to_webhook()` 發送每個項目
- [ ] 記錄成功/失敗數量
- [ ] 回傳 `(成功數量, 失敗數量)`
- [ ] 即使部分失敗，仍繼續處理剩餘項目

**實作筆記**：
```python
def send_multiple_webhooks(entries: List[BookkeepingEntry], transaction_id: str) -> tuple[int, int]:
    success_count = 0
    failure_count = 0
    for entry in entries:
        entry.交易ID = transaction_id
        if send_to_webhook(entry):
            success_count += 1
        else:
            failure_count += 1
    return (success_count, failure_count)
```

---

### T106 [US1]: 更新確認訊息格式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：45 分鐘
**依賴**：T104, T105
**檔案**：`app/line_handler.py`

**描述**：
更新確認訊息格式，支援列出多個項目。

**驗收標準**：
- [ ] 單項目時維持原有格式（向後相容）
- [ ] 多項目時列出所有項目，使用 emoji 區分（📋 #1, #2...）
- [ ] 標註「💳 付款方式：XXX（共用）」
- [ ] 顯示共用交易ID
- [ ] 訊息格式清晰易讀

**實作筆記**：
```python
# 多項目格式範例
"""
✅ 記帳成功！已記錄 2 個項目：

📋 #1 早餐
💰 80 元 | 現金
📂 家庭／餐飲／早餐

📋 #2 午餐
💰 150 元 | 現金
📂 家庭／餐飲／午餐

🔖 交易ID：20251114-143052
💳 付款方式：現金（共用）
"""
```

---

### T107 [P] [US1]: 撰寫多項目支出單元測試

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：2 小時
**依賴**：T103
**檔案**：`tests/test_gpt_processor.py`

**描述**：
在 `tests/test_gpt_processor.py` 中新增多項目支出測試案例。

**驗收標準**：
- [ ] `test_multi_items_shared_payment()` - 驗證共用付款方式
- [ ] `test_multi_items_incomplete_amount()` - 第二項缺少金額
- [ ] `test_multi_items_missing_payment()` - 缺少付款方式
- [ ] `test_multi_items_ambiguous()` - 模糊情況（三明治和咖啡80元）
- [ ] `test_multi_items_different_payments()` - 不同付款方式拒絕
- [ ] `test_multi_items_shared_transaction_id()` - 驗證共用交易ID
- [ ] 所有測試使用 mock 避免實際呼叫 GPT API
- [ ] 測試覆蓋率 > 80%

---

### T108 [P] [US1]: 撰寫 webhook 批次發送測試

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T105
**檔案**：`tests/test_webhook_sender.py`

**描述**：
在 `tests/test_webhook_sender.py` 中新增批次發送測試案例。

**驗收標準**：
- [ ] `test_send_multiple_webhooks_success()` - 全部成功
- [ ] `test_send_multiple_webhooks_partial_failure()` - 部分失敗
- [ ] `test_send_multiple_webhooks_all_failure()` - 全部失敗
- [ ] 使用 mock 避免實際發送 webhook
- [ ] 驗證回傳的成功/失敗數量正確

**Checkpoint 1.1**: 多項目文字支出功能完整，單元測試通過

---

## Phase 2: 圖片識別功能

**目標**：使用 GPT-4 Vision API 識別收據圖片

**使用者故事**：US1 場景 8-9（收據圖片識別）

**獨立測試**：上傳清晰台幣收據圖片，驗證正確提取品項和金額

---

### T201 [P] [US2]: 建立 image_handler.py 模組

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：30 分鐘
**依賴**：T002
**檔案**：`app/image_handler.py`（新增）

**描述**：
建立 `app/image_handler.py` 模組，定義收據項目資料類別。

**驗收標準**：
- [ ] 新增檔案 `app/image_handler.py`
- [ ] 定義 `ReceiptItem` dataclass
- [ ] 包含欄位：品項、原幣金額、付款方式（Optional）、分類（Optional）
- [ ] 匯入必要套件（typing, dataclasses, base64, requests）

**實作筆記**：
```python
@dataclass
class ReceiptItem:
    """單筆收據項目"""
    品項: str
    原幣金額: float
    付款方式: Optional[str] = None
    分類: Optional[str] = None
```

---

### T202 [P] [US2]: 實作 download_image() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T201
**檔案**：`app/image_handler.py`

**描述**：
實作 `download_image()` 函式，從 LINE 下載圖片內容。

**驗收標準**：
- [ ] 函式簽章：`def download_image(message_id: str, line_bot_api: LineBotApi) -> bytes`
- [ ] 使用 `line_bot_api.get_message_content(message_id)` 下載圖片
- [ ] 驗證圖片大小 < 10MB（檢查 Content-Length）
- [ ] 回傳圖片 bytes
- [ ] 錯誤處理：
  - 下載失敗 → 拋出 `ImageDownloadError`
  - 圖片過大 → 拋出 `ImageTooLargeError`

---

### T203 [P] [US2]: 實作 encode_image_base64() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：T201
**檔案**：`app/image_handler.py`

**描述**：
實作 `encode_image_base64()` 函式，將圖片轉換為 base64 編碼。

**驗收標準**：
- [ ] 函式簽章：`def encode_image_base64(image_data: bytes) -> str`
- [ ] 使用 `base64.b64encode()` 轉換
- [ ] 回傳 UTF-8 字串

**實作筆記**：
```python
def encode_image_base64(image_data: bytes) -> str:
    return base64.b64encode(image_data).decode('utf-8')
```

---

### T204 [US2]: 實作 process_receipt_image() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：2 小時
**依賴**：T201, T203, T205
**檔案**：`app/image_handler.py`

**描述**：
實作 `process_receipt_image()` 函式，使用 GPT Vision API 分析收據。

**驗收標準**：
- [ ] 函式簽章：`def process_receipt_image(image_data: bytes, openai_client) -> List[ReceiptItem]`
- [ ] 呼叫 `encode_image_base64()` 轉換圖片
- [ ] 使用 GPT-4o Vision API（`gpt-4o`）
- [ ] 使用 `RECEIPT_VISION_PROMPT`
- [ ] 解析 JSON 回應（status, currency, items, payment_method）
- [ ] 處理各種狀態：
  - `success` → 轉換為 `List[ReceiptItem]` 並回傳
  - `not_receipt` → 回傳空列表 + 錯誤訊息
  - `unsupported_currency` → 回傳空列表 + 錯誤訊息
  - `unclear` → 回傳空列表 + 錯誤訊息
- [ ] 錯誤處理：API 失敗 → 拋出 `VisionAPIError`

---

### T205 [P] [US2]: 建立 RECEIPT_VISION_PROMPT

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T002
**檔案**：`app/prompts.py`

**描述**：
在 `app/prompts.py` 中建立 `RECEIPT_VISION_PROMPT`，定義收據識別邏輯。

**驗收標準**：
- [ ] 定義收據識別任務（品項、金額、付款方式）
- [ ] 檢查圖片類型（是否為收據）
- [ ] 檢查幣別（僅支援 TWD）
- [ ] 檢查清晰度
- [ ] 定義錯誤狀態 JSON 格式（not_receipt, unsupported_currency, unclear）
- [ ] 定義成功 JSON 格式（status, currency, items, payment_method）
- [ ] 包含完整範例

---

### T206 [US2]: 實作 process_receipt_data() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：T201, T102
**檔案**：`app/gpt_processor.py`

**描述**：
實作 `process_receipt_data()` 函式，將收據資料轉換為記帳項目。

**驗收標準**：
- [ ] 函式簽章：`def process_receipt_data(receipt_items: List[ReceiptItem], payment_method: str) -> MultiExpenseResult`
- [ ] 為每個 ReceiptItem 建立 BookkeepingEntry
- [ ] 生成共用交易ID（時間戳記格式）
- [ ] 補充預設值（日期=今天、原幣別=TWD、匯率=1.0、共用付款方式）
- [ ] 推斷分類、必要性等欄位
- [ ] 回傳 `MultiExpenseResult` (intent="multi_bookkeeping")

---

### T207 [US2]: 實作 handle_image_message() 函式

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1.5 小時
**依賴**：T202, T204, T206
**檔案**：`app/line_handler.py`

**描述**：
實作 `handle_image_message()` 函式，處理圖片訊息的主流程。

**驗收標準**：
- [ ] 函式簽章：`def handle_image_message(event: MessageEvent, line_bot_api: LineBotApi) -> None`
- [ ] 取得圖片訊息 ID
- [ ] 呼叫 `download_image()` 下載圖片
- [ ] 呼叫 `process_receipt_image()` 分析收據
- [ ] 若成功（有 receipt_items）：
  - 呼叫 `process_receipt_data()` 轉換為 BookkeepingEntry
  - 呼叫 `send_multiple_webhooks()` 發送 webhook
  - 回覆確認訊息（列出所有項目）
- [ ] 若失敗（空列表）：
  - 根據錯誤訊息回覆適當提示
- [ ] 錯誤處理：
  - 下載失敗 → 「圖片下載失敗，請稍後再試」
  - Vision API 失敗 → 「無法處理圖片，請改用文字描述」

---

### T208 [US2]: 更新 webhook.py 處理圖片訊息

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：30 分鐘
**依賴**：T207
**檔案**：`api/webhook.py`

**描述**：
更新 `api/webhook.py` 新增圖片訊息事件處理。

**驗收標準**：
- [ ] 識別 `ImageMessage` 訊息類型
- [ ] 呼叫 `line_handler.handle_image_message(event, line_bot_api)`
- [ ] 保持與文字訊息處理的一致性（簽章驗證、錯誤處理）

**實作筆記**：
```python
from linebot.models import ImageMessage

if isinstance(event.message, TextMessage):
    handle_text_message(event, line_bot_api)
elif isinstance(event.message, ImageMessage):
    handle_image_message(event, line_bot_api)
```

---

### T209 [P] [US2]: 更新 config.py 新增環境變數

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：T002
**檔案**：`app/config.py`

**描述**：
更新 `app/config.py` 新增 GPT Vision 相關環境變數。

**驗收標準**：
- [ ] 新增 `GPT_VISION_MODEL` 環境變數
- [ ] 預設值：`gpt-4o`
- [ ] 驗證邏輯（若未設定則使用預設值）

**實作筆記**：
```python
GPT_VISION_MODEL = os.getenv('GPT_VISION_MODEL', 'gpt-4o')
```

---

### T210 [P] [US2]: 更新 .env.example 文件

**優先級**：P2
**狀態**：⏳ 待執行
**預估時間**：10 分鐘
**依賴**：T209
**檔案**：`.env.example`

**描述**：
更新 `.env.example` 新增 v1.5.0 環境變數說明。

**驗收標準**：
- [ ] 新增 `GPT_VISION_MODEL=gpt-4o` 說明
- [ ] 註明用途（圖片收據識別）

---

### T211 [P] [US2]: 撰寫圖片處理單元測試

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：2 小時
**依賴**：T204
**檔案**：`tests/test_image_handler.py`（新增）

**描述**：
建立 `tests/test_image_handler.py` 測試圖片處理功能。

**驗收標準**：
- [ ] `test_download_image_success()` - Mock 成功下載
- [ ] `test_download_image_failure()` - Mock 下載失敗
- [ ] `test_download_image_too_large()` - Mock 圖片過大
- [ ] `test_encode_image_base64()` - 驗證 base64 編碼
- [ ] `test_process_receipt_success()` - Mock Vision API 成功（單項目）
- [ ] `test_process_receipt_multi_items()` - Mock Vision API 成功（多項目）
- [ ] `test_process_receipt_not_receipt()` - Mock 非收據圖片
- [ ] `test_process_receipt_unsupported_currency()` - Mock 非台幣
- [ ] `test_process_receipt_unclear()` - Mock 模糊圖片
- [ ] 所有測試使用 mock 避免實際呼叫 API
- [ ] 測試覆蓋率 > 80%

**Checkpoint 2.1**: 圖片識別功能完整，單元測試通過

---

## Phase 3: 整合測試

**目的**：端到端測試完整流程

---

### T301 [P] [US1]: 整合測試（多項目文字）

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：Phase 1 完成
**檔案**：`tests/test_integration.py`

**描述**：
更新 `tests/test_integration.py` 新增多項目文字支出的端到端測試。

**驗收標準**：
- [ ] `test_end_to_end_multi_items_text()` - 端到端多項目文字支出
- [ ] `test_multi_items_text_missing_payment()` - 缺少付款方式錯誤
- [ ] `test_multi_items_text_different_payments()` - 不同付款方式拒絕
- [ ] 模擬 LINE webhook 請求
- [ ] 驗證 webhook 發送次數和內容
- [ ] 驗證回覆訊息格式

---

### T302 [P] [US2]: 整合測試（圖片訊息）

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：1 小時
**依賴**：Phase 2 完成
**檔案**：`tests/test_integration.py`

**描述**：
更新 `tests/test_integration.py` 新增圖片訊息的端到端測試。

**驗收標準**：
- [ ] `test_end_to_end_receipt_image()` - 端到端收據圖片識別
- [ ] `test_receipt_image_download_failure()` - 圖片下載失敗
- [ ] `test_receipt_image_vision_api_failure()` - Vision API 失敗
- [ ] `test_receipt_image_not_receipt()` - 非收據圖片
- [ ] `test_receipt_image_unsupported_currency()` - 非台幣收據
- [ ] Mock 圖片下載和 Vision API 回應
- [ ] 驗證錯誤訊息正確

---

### T303: 執行所有單元測試

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：T107, T108, T211

**描述**：
執行所有單元測試並確保通過。

**驗收標準**：
- [ ] `pytest tests/test_gpt_processor.py -v` 全部通過
- [ ] `pytest tests/test_webhook_sender.py -v` 全部通過
- [ ] `pytest tests/test_image_handler.py -v` 全部通過
- [ ] 無失敗案例

---

### T304: 執行所有整合測試

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：T301, T302

**描述**：
執行所有整合測試並確保通過。

**驗收標準**：
- [ ] `pytest tests/test_integration.py -v` 全部通過
- [ ] 無失敗案例

---

### T305: 執行完整測試套件並檢查覆蓋率

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：T303, T304

**描述**：
執行完整測試套件並驗證測試覆蓋率。

**驗收標準**：
- [ ] `pytest tests/ -v --cov=app` 執行成功
- [ ] 測試覆蓋率 > 80%
- [ ] 所有測試通過

**Checkpoint 3.1**: 所有自動化測試通過，覆蓋率達標

---

## Phase 4: 部署準備

**目的**：準備部署到 Vercel

---

### T401 [P]: 更新依賴套件

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：15 分鐘
**依賴**：Phase 3 完成
**檔案**：`requirements.txt`

**描述**：
更新 `requirements.txt` 確認所有依賴版本正確。

**驗收標準**：
- [ ] 確認 `openai>=1.12.0` 版本支援 Vision API
- [ ] 確認所有依賴版本正確
- [ ] 執行 `pip install -r requirements.txt` 無錯誤

---

### T402 [P]: 驗證 Vercel 配置

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：10 分鐘
**依賴**：Phase 3 完成
**檔案**：`vercel.json`

**描述**：
驗證 `vercel.json` 配置正確。

**驗收標準**：
- [ ] Python 版本設定正確（3.11）
- [ ] 路由設定正確（`/api/webhook`）
- [ ] builds 配置正確

---

### T403: 設定 Vercel 環境變數

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：10 分鐘
**依賴**：T209

**描述**：
在 Vercel Dashboard 設定 v1.5.0 環境變數。

**驗收標準**：
- [ ] 在 Vercel Dashboard → Settings → Environment Variables
- [ ] 新增 `GPT_VISION_MODEL=gpt-4o`
- [ ] 驗證所有必要環境變數存在（LINE, OpenAI, Webhook）

---

### T404: 部署到 Vercel

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：20 分鐘
**依賴**：T401, T402, T403

**描述**：
部署 v1.5.0 到 Vercel 並驗證部署成功。

**驗收標準**：
- [ ] 推送所有變更到 GitHub 分支
- [ ] Vercel 自動偵測並開始部署
- [ ] 部署成功（無錯誤）
- [ ] 取得部署 URL（`https://<app>.vercel.app`）
- [ ] 驗證 Function 正常運作

---

### T405: 驗證 Webhook 連線

**優先級**：P1
**狀態**：⏳ 待執行
**預估時間**：10 分鐘
**依賴**：T404

**描述**：
驗證 LINE Bot Webhook 連線正常。

**驗收標準**：
- [ ] LINE Developers Console → Webhook URL 正確設定
- [ ] URL: `https://<app>.vercel.app/api/webhook`
- [ ] 啟用 "Use webhook"
- [ ] 執行 Webhook 驗證（回應 200 OK）

**Checkpoint 4.1**: 部署完成，準備進行手動測試

---

## Phase 5: 手動驗證

**目的**：實際在 LINE 中測試所有功能

**總測試案例**：20 個

---

### 5.1 多項目文字支出測試（7 個案例）

**T501**: 測試「早餐80元，午餐150元，現金」

- [ ] 發送訊息
- [ ] 驗證：記錄兩個項目
- [ ] 驗證：Make.com 接收兩個 webhook，共用交易ID
- [ ] 驗證：確認訊息列出所有項目，標註「付款方式：現金（共用）」

**T502**: 測試「咖啡50，三明治35，用狗卡」

- [ ] 發送訊息
- [ ] 驗證：正確識別「台新狗卡」
- [ ] 驗證：兩個項目共用付款方式

**T503**: 測試「早餐三明治35，飲料30，現金」

- [ ] 發送訊息
- [ ] 驗證：正確處理項目中包含品項名稱的情況

**T504**: 錯誤測試「早餐80元，午餐買了便當，現金」

- [ ] 發送訊息（第二項缺少金額）
- [ ] 驗證：回覆「第二個項目缺少金額，請提供完整資訊」
- [ ] 驗證：不觸發 webhook

**T505**: 錯誤測試「早餐80元，午餐150元」

- [ ] 發送訊息（缺少付款方式）
- [ ] 驗證：回覆「請提供付款方式」
- [ ] 驗證：不觸發 webhook

**T506**: 錯誤測試「三明治和咖啡80元現金」

- [ ] 發送訊息（模糊情況）
- [ ] 驗證：回覆「無法確定是一個項目還是多個項目」
- [ ] 驗證：不觸發 webhook

**T507**: 錯誤測試「早餐80元現金，午餐150元刷卡」

- [ ] 發送訊息（不同付款方式）
- [ ] 驗證：回覆「偵測到不同付款方式，請分開記帳」
- [ ] 驗證：不觸發 webhook

---

### 5.2 收據圖片測試（5 個案例）

**T508**: 測試上傳清晰台幣收據（單項目）

- [ ] 上傳收據圖片
- [ ] 驗證：正確識別品項、金額、付款方式
- [ ] 驗證：Make.com 接收 webhook
- [ ] 驗證：確認訊息正確

**T509**: 測試上傳清晰台幣收據（多項目）

- [ ] 上傳多項目收據圖片（如超商收據）
- [ ] 驗證：識別所有項目
- [ ] 驗證：Make.com 接收多個 webhook，共用交易ID

**T510**: 測試上傳模糊收據

- [ ] 上傳模糊收據圖片
- [ ] 驗證：回覆「收據圖片不清晰，請用文字描述」
- [ ] 驗證：不觸發 webhook

**T511**: 測試上傳非收據圖片

- [ ] 上傳風景照或人物照
- [ ] 驗證：回覆「無法從圖片中識別收據資訊」
- [ ] 驗證：不觸發 webhook

**T512**: 測試上傳日幣收據

- [ ] 上傳日幣或其他外幣收據
- [ ] 驗證：回覆「v1.5.0 僅支援台幣」
- [ ] 驗證：不觸發 webhook

---

### 5.3 效能與錯誤處理驗證（3 個案例）

**T513**: 驗證回應時間

- [ ] 文字訊息（多項目）：< 4 秒
- [ ] 圖片訊息：< 7 秒
- [ ] 記錄實際回應時間

**T514**: 驗證錯誤處理

- [ ] 模擬 GPT API 失敗（暫時關閉網路）
- [ ] 驗證：回覆友善錯誤訊息
- [ ] 模擬 Webhook 失敗（錯誤 URL）
- [ ] 驗證：回覆錯誤訊息

**T515**: 驗證向後相容性（v1 MVP 功能）

- [ ] 測試單筆記帳「午餐120元現金」
- [ ] 驗證：正常運作（向後相容）
- [ ] 驗證：Make.com 接收 webhook
- [ ] 驗證：確認訊息格式正確

**Checkpoint 5.1**: 所有手動測試通過，v1.5.0 功能完整驗證

---

## Phase 6: 文件更新

**目的**：更新專案文件

---

### T601 [P]: 更新 README.md

**優先級**：P2
**狀態**：⏳ 待執行
**預估時間**：30 分鐘
**依賴**：Phase 5 完成
**檔案**：`README.md`

**描述**：
更新 `README.md` 新增 v1.5.0 功能說明。

**驗收標準**：
- [ ] 新增 v1.5.0 功能說明章節
- [ ] 新增多項目支出使用範例
- [ ] 新增圖片識別使用說明
- [ ] 更新環境變數說明（GPT_VISION_MODEL）
- [ ] 新增範例截圖（可選）

---

### T602 [P]: 最終檢查 .env.example

**優先級**：P2
**狀態**：⏳ 待執行
**預估時間**：10 分鐘
**依賴**：T210
**檔案**：`.env.example`

**描述**：
最終檢查 `.env.example` 包含所有必要變數。

**驗收標準**：
- [ ] 所有 v1.5.0 環境變數都有說明
- [ ] 範例值正確
- [ ] 註解清楚

**Checkpoint 6.1**: 文件更新完成，v1.5.0 開發全部完成

---

## 執行策略

### 推薦執行順序（單人開發）

```
Phase 0 (已完成)
    ↓
Phase 1: 多項目支出 (6-8 小時)
    T101 [P], T102 [P], T105 [P] ← 平行執行
    ↓
    T103 ← 依賴 T101, T102
    ↓
    T104 ← 依賴 T103
    ↓
    T106 ← 依賴 T104, T105
    ↓
    T107 [P], T108 [P] ← 平行執行測試
    ↓
Phase 2: 圖片識別 (6-8 小時)
    T201 [P], T202 [P], T203 [P], T205 [P], T209 [P], T210 [P] ← 平行執行
    ↓
    T204 ← 依賴 T201, T203, T205
    ↓
    T206 ← 依賴 T201, T102
    ↓
    T207 ← 依賴 T202, T204, T206
    ↓
    T208 ← 依賴 T207
    ↓
    T211 ← 測試
    ↓
Phase 3: 整合測試 (2-3 小時)
    T301 [P], T302 [P] ← 平行執行
    ↓
    T303, T304, T305 ← 依序執行
    ↓
Phase 4: 部署 (1-2 小時)
    T401 [P], T402 [P] ← 平行執行
    ↓
    T403, T404, T405 ← 依序執行
    ↓
Phase 5: 手動驗證 (2-3 小時)
    T501-T515 ← 依序測試
    ↓
Phase 6: 文件 (1 小時)
    T601 [P], T602 [P] ← 平行執行
```

### 平行團隊策略（雙人開發）

```
開發者 A: Phase 1 (多項目支出)
開發者 B: Phase 2 (圖片識別)

完成後會合 → Phase 3-6 一起完成
```

---

## 提交策略

### 建議的 Git Commit 節奏

**Phase 1**:
- Commit 1: `feat(prompt): add multi-expense prompt` (T101)
- Commit 2: `feat(gpt): add multi-expense data structures` (T102)
- Commit 3: `feat(gpt): implement process_multi_expense` (T103)
- Commit 4: `feat(line): update text handler for multi-expense` (T104)
- Commit 5: `feat(webhook): implement batch webhook sender` (T105)
- Commit 6: `feat(line): update confirmation message format` (T106)
- Commit 7: `test(gpt): add multi-expense unit tests` (T107, T108)

**Phase 2**:
- Commit 8: `feat(image): add image handler module` (T201-T203)
- Commit 9: `feat(image): implement receipt vision processing` (T204)
- Commit 10: `feat(prompt): add receipt vision prompt` (T205)
- Commit 11: `feat(gpt): implement receipt data processing` (T206)
- Commit 12: `feat(line): implement image message handler` (T207-T208)
- Commit 13: `feat(config): add vision model environment variable` (T209-T210)
- Commit 14: `test(image): add image handler unit tests` (T211)

**Phase 3**:
- Commit 15: `test(integration): add multi-expense integration tests` (T301-T302)
- Commit 16: `test: run full test suite and verify coverage` (T303-T305)

**Phase 4**:
- Commit 17: `chore(deps): update requirements for v1.5.0` (T401-T402)
- Commit 18: `deploy: configure v1.5.0 deployment` (T403-T405)

**Phase 6**:
- Commit 19: `docs: update README for v1.5.0` (T601-T602)

---

## 總結

### 關鍵里程碑

1. **Checkpoint 1.1**: 多項目文字支出功能完成
2. **Checkpoint 2.1**: 圖片識別功能完成
3. **Checkpoint 3.1**: 所有自動化測試通過
4. **Checkpoint 4.1**: 部署到 Vercel 完成
5. **Checkpoint 5.1**: 所有手動測試通過
6. **Checkpoint 6.1**: v1.5.0 開發全部完成 🎉

### 時間預估

- **Phase 0**: 已完成
- **Phase 1**: 6-8 小時
- **Phase 2**: 6-8 小時
- **Phase 3**: 2-3 小時
- **Phase 4**: 1-2 小時
- **Phase 5**: 2-3 小時
- **Phase 6**: 1 小時

**總計**: 18-25 小時（2-3 個工作天）

### 下一步

執行 `/speckit.implement` 開始實作 v1.5.0！

---

**版本歷史**：
- v1.5.0-tasks (2025-11-14) - v1.5.0 任務清單完成
