# LINE Bot GPT Bookkeeper - v1 MVP 技術規劃

**版本**：1.0.0 | **規劃日期**：2025-11-12 | **目標版本**：v1 MVP

---

## 📋 規劃摘要

### 目標

構建 **v1 MVP - Serverless 最簡版**，驗證「用自然語言記帳」的核心價值，以最簡單的方式快速上線。

### 核心功能範圍

- ✅ 接收 LINE 訊息，用 GPT 識別記帳意圖
- ✅ 處理**資訊完整**的單筆台幣記帳（有品項、金額、付款方式）
- ✅ 發送 webhook 到記帳系統（Make.com）
- ✅ 回覆使用者確認訊息
- ✅ 簡單的一般對話回應（透過 GPT，不需外部 API）

### 架構特點

- **無狀態** Serverless function（部署於 Vercel）
- **不儲存**對話歷史或任何資料
- 每次請求獨立處理
- 僅支援**台幣**（TWD）

### 明確排除（延後到 v2）

- ❌ 多輪對話（處理不完整項目）
- ❌ 對話脈絡管理和儲存
- ❌ 圖片/收據識別
- ❌ 即時資訊查詢（天氣、新聞、匯率 API）
- ❌ 單一訊息多筆支出
- ❌ 外幣支援和匯率 API
- ❌ 持久化重試佇列

---

## 🏗️ 系統架構

### 高階架構圖

```
使用者
  ↓ 發送 LINE 訊息
LINE Platform
  ↓ Webhook
Vercel Serverless Function (/api/webhook.py)
  ├→ 驗證 LINE 簽章
  ├→ 解析訊息
  ├→ 呼叫 OpenAI GPT-4o-mini
  │   └→ 判斷意圖 + 結構化資料
  ├→ 若為記帳：發送 webhook 到 Make.com
  └→ 回覆 LINE 使用者
```

### 技術棧

| 層級 | 技術選擇 | 理由 |
|------|---------|------|
| **語言** | Python 3.11+ | 團隊熟悉、SDK 支援完整、適合快速開發 |
| **框架** | Flask（精簡版） | 輕量、無狀態、適合 Serverless |
| **部署平台** | Vercel Serverless Functions | 免費方案、零配置部署、自動 HTTPS |
| **LINE SDK** | `line-bot-sdk` (官方) | 完整支援 Messaging API、簽章驗證 |
| **OpenAI SDK** | `openai>=1.0` | 官方 SDK、支援 Chat Completions API |
| **HTTP Client** | `requests` | 標準函式庫、用於發送 Make.com webhook |
| **環境變數** | Vercel Environment Variables | 安全儲存敏感資訊 |

---

## 📁 專案結構

```
linebot-gpt-bookkeeper/
├── api/
│   └── webhook.py              # Vercel Serverless Function 入口
├── app/
│   ├── __init__.py
│   ├── config.py               # 環境變數管理
│   ├── line_handler.py         # LINE Bot 訊息處理邏輯
│   ├── gpt_processor.py        # GPT 意圖識別和資料結構化
│   ├── webhook_sender.py       # 發送 webhook 到 Make.com
│   └── prompts.py              # GPT System Prompt 定義
├── tests/
│   ├── test_gpt_processor.py   # GPT 處理器單元測試
│   ├── test_webhook_sender.py  # Webhook 發送器測試
│   └── test_integration.py     # 整合測試
├── vercel.json                 # Vercel 配置
├── requirements.txt            # Python 依賴
├── .env.example                # 環境變數範例
├── .gitignore
└── README.md
```

---

## 🔧 核心模組設計

### 1. `api/webhook.py` - Vercel Function 入口

**職責**：
- 接收 LINE Webhook POST 請求
- 驗證 X-Line-Signature
- 解析 LINE event 並呼叫處理器
- 返回 200 OK（LINE 平台要求）

**流程**：
```python
def handler(request):
    # 1. 取得 request body 和 signature
    # 2. 驗證 LINE 簽章
    # 3. 解析 events
    # 4. 處理 MessageEvent (text)
    # 5. 回傳 200 OK
```

**錯誤處理**：
- 簽章驗證失敗 → 返回 400
- 解析失敗 → 記錄錯誤，返回 200（避免 LINE 重試）
- 處理失敗 → 記錄錯誤，回覆使用者錯誤訊息，返回 200

---

### 2. `app/line_handler.py` - LINE 訊息處理

**職責**：
- 接收已驗證的 LINE MessageEvent
- 呼叫 GPT 處理器分析訊息
- 根據結果執行對應動作（記帳 or 對話）
- 呼叫 LINE API 回覆使用者

**主要函式**：

```python
def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    處理文字訊息的主流程

    流程：
    1. 取得使用者訊息文字
    2. 呼叫 GPT 處理器分析意圖
    3. 若為記帳 → 發送 webhook + 回覆確認
    4. 若為對話 → 回覆 GPT 生成的回應
    5. 錯誤處理 → 回覆友善錯誤訊息
    """
```

**錯誤處理策略**：
- GPT API 失敗 → 「抱歉，目前無法處理您的訊息，請稍後再試」
- Webhook 失敗 → 「記帳資料處理失敗，請稍後重試」
- LINE API 失敗 → 記錄日誌（使用者看不到）

---

### 3. `app/gpt_processor.py` - GPT 意圖識別

**職責**：
- 呼叫 OpenAI Chat Completions API
- 使用 System Prompt 引導 GPT 判斷意圖
- 解析 GPT 回應（JSON or 純文字）
- 回傳結構化結果

**資料結構**：

```python
from typing import Literal, Optional
from dataclasses import dataclass
from datetime import date

@dataclass
class BookkeepingEntry:
    """記帳資料結構"""
    intent: Literal["bookkeeping", "conversation"]

    # 若 intent == "bookkeeping"，以下欄位必填
    日期: Optional[str] = None              # YYYY-MM-DD
    品項: Optional[str] = None
    原幣別: Optional[str] = "TWD"
    原幣金額: Optional[float] = None
    匯率: Optional[float] = 1.0
    付款方式: Optional[str] = None
    交易ID: Optional[str] = None           # 自動生成：YYYYMMDD-001
    明細說明: Optional[str] = ""
    分類: Optional[str] = None             # GPT 根據品項判斷
    專案: Optional[str] = "日常"
    必要性: Optional[str] = None
    代墊狀態: Optional[str] = "無"
    收款支付對象: Optional[str] = ""
    附註: Optional[str] = ""

    # 若 intent == "conversation"
    response_text: Optional[str] = None    # GPT 生成的對話回應
```

**主要函式**：

```python
def process_message(user_message: str) -> BookkeepingEntry:
    """
    處理使用者訊息並回傳結構化結果

    流程：
    1. 構建 GPT messages（system + user）
    2. 呼叫 OpenAI API
    3. 解析回應（判斷 intent）
    4. 若為記帳 → 驗證必要欄位、生成交易ID
    5. 回傳 BookkeepingEntry
    """
```

**GPT 回應格式**：

記帳意圖：
```json
{
  "intent": "bookkeeping",
  "data": {
    "品項": "午餐便當",
    "原幣金額": 120,
    "付款方式": "現金",
    "分類": "家庭／餐飲／午餐",
    "必要性": "必要日常支出"
  }
}
```

一般對話：
```json
{
  "intent": "conversation",
  "response": "您好！我是記帳助手，可以幫您記錄日常開支。請告訴我品項、金額和付款方式喔！"
}
```

---

### 4. `app/prompts.py` - System Prompt 定義

**職責**：
- 定義 GPT 的角色和任務
- 整合 knowledge/ 的欄位標準值
- 提供輸出格式範例

**System Prompt 設計**：

```python
SYSTEM_PROMPT = """你是專業的記帳助手，協助使用者記錄日常開支。

## 你的任務

1. **判斷意圖**：使用者訊息是「記帳」還是「一般對話」
   - 記帳特徵：包含品項、金額、付款方式（如：「午餐 120 現金」、「200 點心 狗卡」）
   - 一般對話：打招呼、詢問功能、閒聊等

2. **記帳處理**（若為記帳意圖）：
   - 提取：品項、金額、付款方式
   - 判斷：分類（根據品項內容）、必要性
   - 預設值：
     - 日期：今天
     - 原幣別：TWD
     - 匯率：1
     - 專案：日常
     - 代墊狀態：無
   - **重要**：v1 僅處理完整項目（有品項、金額、付款方式）
   - 若資訊不完整：回傳 conversation intent，回應「請提供品項、金額及付款方式」

3. **對話處理**（若為一般對話）：
   - 友善、簡潔地回應使用者
   - 必要時說明記帳格式：「您可以這樣記帳：午餐 120 現金」

## 欄位標準值

### 分類（根據品項判斷）
- 家庭／食材：生鮮、米、蔬菜等
- 家庭／餐飲／早餐、午餐、晚餐：外出用餐、早餐店、便當等
- 家庭／點心：零食、餅乾、糖果等
- 家庭／飲品：飲料、果汁、咖啡等
- 個人／餐飲：公司聚餐、單人外食
- 行程／餐飲／＊＊餐：行程中的餐飲
- 健康／醫療／本人、家庭成員：醫療、藥品
- 教育／子女、進修：課程、教材
- 交通／接駁、加油：交通費用
- 禮物／家庭、外部贈送：送禮
- 收款／代墊回收：回收款項
（完整分類見 knowledge/basic-structure.txt）

### 付款方式（精確匹配使用者說法）
- 現金
- Line Pay
- 合庫
- 台新狗卡（別名：狗卡）
- 台新 Richart
- FlyGo 信用卡（別名：FlyGo）
- 大戶信用卡（別名：大戶）
- 聯邦綠卡（別名：綠卡、聯邦）
- 富邦 Costco（別名：Costco 卡）
- 星展永續卡（別名：星展）

### 必要性
- 必要日常支出：三餐、醫療等必要開支
- 想吃想買但合理：生日慶祝、合理點心
- 療癒性支出：甜點、舒壓用品
- 衝動購物（提醒）：非必要消費

### 專案
- 日常（預設）
- 家庭年度支出、子女年度支出
- 紀念日／送禮
- 健康檢查、登山行程
- 折扣／優惠

### 代墊狀態
- 無（預設）
- 不索取、代墊、需支付、已支付、已收款

## 輸出格式

### 記帳意圖
```json
{
  "intent": "bookkeeping",
  "data": {
    "品項": "午餐便當",
    "原幣金額": 120,
    "付款方式": "現金",
    "分類": "家庭／餐飲／午餐",
    "必要性": "必要日常支出",
    "明細說明": ""
  }
}
```

### 一般對話
```json
{
  "intent": "conversation",
  "response": "您好！有什麼可以幫您的嗎？"
}
```

請嚴格按照以上格式輸出 JSON。
"""
```

---

### 5. `app/webhook_sender.py` - Webhook 發送器

**職責**：
- 接收 BookkeepingEntry
- 轉換為 Make.com 需要的格式
- 發送 POST 請求到 webhook URL
- 處理失敗情況

**Make.com Webhook 格式**：

```json
{
  "日期": "2025-11-12",
  "品項": "午餐便當",
  "原幣別": "TWD",
  "原幣金額": 120,
  "匯率": 1,
  "付款方式": "現金",
  "交易ID": "20251112-001",
  "明細說明": "",
  "分類": "家庭／餐飲／午餐",
  "專案": "日常",
  "必要性": "必要日常支出",
  "代墊狀態": "無",
  "收款／支付對象": "",
  "附註": ""
}
```

**主要函式**：

```python
def send_to_webhook(entry: BookkeepingEntry) -> bool:
    """
    發送記帳資料到 Make.com webhook

    參數：
        entry: BookkeepingEntry 物件

    回傳：
        bool: 成功 True，失敗 False

    錯誤處理：
        - 網路錯誤：記錄日誌，回傳 False
        - HTTP 4xx/5xx：記錄日誌，回傳 False
        - Timeout（10秒）：記錄日誌，回傳 False
    """
```

---

### 6. `app/config.py` - 環境變數管理

**職責**：
- 載入環境變數
- 提供預設值
- 驗證必要變數存在

**環境變數清單**：

| 變數名稱 | 說明 | 範例值 | 必要性 |
|---------|------|--------|--------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot 存取 Token | `xxx...` | ✅ 必要 |
| `LINE_CHANNEL_SECRET` | LINE Bot Secret | `xxx...` | ✅ 必要 |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-proj-...` | ✅ 必要 |
| `WEBHOOK_URL` | Make.com Webhook URL | `https://hook.us2.make.com/...` | ✅ 必要 |
| `GPT_MODEL` | GPT 模型名稱 | `gpt-4o-mini` | ⚠️ 選用（預設 gpt-4o-mini） |
| `WEBHOOK_TIMEOUT` | Webhook 超時秒數 | `10` | ⚠️ 選用（預設 10） |

---

## 🔄 完整流程圖

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 使用者在 LINE 發送訊息：「午餐 120 現金」                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. LINE Platform 發送 Webhook POST 到 Vercel                 │
│    URL: https://<app>.vercel.app/api/webhook                │
│    Headers: X-Line-Signature                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. api/webhook.py 接收請求                                   │
│    - 驗證 LINE 簽章 ✓                                         │
│    - 解析 MessageEvent                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. line_handler.handle_text_message()                       │
│    - 取得文字：「午餐 120 現金」                               │
│    - 呼叫 gpt_processor.process_message()                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. gpt_processor.process_message()                          │
│    - 構建 GPT messages（System Prompt + User Message）        │
│    - 呼叫 OpenAI API                                         │
│    - GPT 回應：                                              │
│      {                                                       │
│        "intent": "bookkeeping",                             │
│        "data": {                                            │
│          "品項": "午餐",                                      │
│          "原幣金額": 120,                                     │
│          "付款方式": "現金",                                  │
│          "分類": "家庭／餐飲／午餐"                            │
│        }                                                    │
│      }                                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. 處理 bookkeeping intent                                   │
│    - 生成交易ID：20251112-001                                │
│    - 補充預設值：日期（今天）、匯率（1）、專案（日常）等         │
│    - 呼叫 webhook_sender.send_to_webhook()                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. webhook_sender.send_to_webhook()                         │
│    POST https://hook.us2.make.com/9mz4ke8r17a8knwrbyoxr62dg4lz│
│    Body: { "日期": "2025-11-12", "品項": "午餐", ... }        │
│    - Make.com 回應 200 OK ✓                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. 構建確認訊息                                               │
│    「✅ 記帳成功！                                             │
│                                                              │
│     日期：2025-11-12                                         │
│     品項：午餐                                                │
│     金額（台幣）：120 元                                       │
│     付款方式：現金                                            │
│     分類：家庭／餐飲／午餐                                     │
│     必要性：必要日常支出                                       │
│     交易ID：20251112-001」                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. line_bot_api.reply_message()                             │
│    - 回覆使用者確認訊息 ✓                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. 回傳 200 OK 給 LINE Platform                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧪 測試策略

### 單元測試

**test_gpt_processor.py**：
- ✅ 測試記帳意圖識別（完整資訊）
- ✅ 測試一般對話識別
- ✅ 測試不完整資訊處理（應回傳 conversation + 提示訊息）
- ✅ 測試付款方式別名映射（狗卡 → 台新狗卡）
- ✅ 測試分類判斷邏輯
- ✅ 測試交易ID生成

**test_webhook_sender.py**：
- ✅ 測試正常發送（mock requests）
- ✅ 測試網路錯誤處理
- ✅ 測試 HTTP 錯誤處理（4xx/5xx）
- ✅ 測試超時處理

### 整合測試

**test_integration.py**：
- ✅ 模擬完整 LINE Webhook 請求
- ✅ 驗證端到端流程（記帳）
- ✅ 驗證端到端流程（對話）
- ✅ 測試錯誤情境（GPT API 失敗、Webhook 失敗）

### 手動測試

部署到 Vercel 後的手動測試清單：
- ✅ LINE Bot 接收訊息並正確回覆
- ✅ 記帳成功並在 Make.com 接收到資料
- ✅ 一般對話正常運作
- ✅ 不完整資訊提示訊息
- ✅ 錯誤處理（故意觸發 API 失敗）

---

## 🚀 部署規劃

### Vercel 配置

**vercel.json**：

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/webhook.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/webhook",
      "dest": "api/webhook.py"
    }
  ],
  "env": {
    "PYTHON_VERSION": "3.11"
  }
}
```

### 環境變數設定

在 Vercel Dashboard → Settings → Environment Variables 設定：

| 變數 | 類型 | 說明 |
|------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Secret | LINE Bot 存取 Token |
| `LINE_CHANNEL_SECRET` | Secret | LINE Bot Secret |
| `OPENAI_API_KEY` | Secret | OpenAI API Key |
| `WEBHOOK_URL` | Sensitive | Make.com Webhook URL |
| `GPT_MODEL` | Plain Text | `gpt-4o-mini` |

### 部署步驟

1. **連接 GitHub Repository**
   - Vercel Dashboard → New Project → Import Git Repository
   - 選擇 `linebot-gpt-bookkeeper` repository

2. **配置環境變數**
   - 在 Vercel Dashboard 設定所有必要環境變數

3. **部署**
   - Vercel 自動偵測 `vercel.json` 並部署
   - 取得部署 URL：`https://<your-app>.vercel.app`

4. **設定 LINE Bot Webhook URL**
   - 前往 LINE Developers Console
   - Messaging API → Webhook settings
   - 設定 Webhook URL：`https://<your-app>.vercel.app/api/webhook`
   - 啟用 "Use webhook"
   - 驗證 Webhook（Vercel Function 必須回傳 200 OK）

5. **測試**
   - 在 LINE 加入 Bot 為好友
   - 發送測試訊息：「午餐 120 現金」
   - 確認回覆正確且 Make.com 接收到資料

---

## 📊 效能考量

### Vercel Free Plan 限制

- **Function 執行時間**：10 秒（Hobby plan）
- **Function 記憶體**：1024 MB
- **每月 Function 執行次數**：100 GB-Hours（約 100,000 次呼叫）

### 預估效能

**單次請求流程**：
1. LINE Webhook 接收：< 100ms
2. GPT API 呼叫：1-3 秒
3. Make.com Webhook 發送：< 500ms
4. LINE 回覆訊息：< 500ms

**總計**：約 2-4 秒 / 次請求

✅ **符合** LINE Webhook 3 秒 timeout 要求（在 GPT 快速回應的情況下）

### 風險緩解

- GPT API 設定 timeout（5 秒）
- Make.com Webhook timeout（10 秒）
- 若 GPT 超時 → 回覆「處理中，請稍候」並記錄錯誤

---

## 🔒 安全性考量

### 1. 敏感資訊保護

- ✅ 所有 API Keys 存在 Vercel Environment Variables（Secret 類型）
- ✅ **不**將 `.env` 提交到 Git（.gitignore 排除）
- ✅ 提供 `.env.example` 作為範本

### 2. LINE Webhook 簽章驗證

- ✅ 每次請求驗證 `X-Line-Signature`
- ✅ 使用 LINE SDK 內建驗證機制
- ✅ 驗證失敗立即回傳 400

### 3. Make.com Webhook 安全

- ✅ Webhook URL 包含隨機長字串（Make.com 內建保護）
- ✅ 僅透過 HTTPS 發送
- ✅ 無需額外認證（Make.com 設計如此）

### 4. 錯誤訊息處理

- ✅ **不**在 LINE 回覆中洩露內部錯誤細節
- ✅ 敏感錯誤僅記錄在 Vercel Logs
- ✅ 使用者看到的錯誤訊息：「抱歉，處理失敗，請稍後再試」

---

## 📝 開發檢查清單

### Phase 1: 基礎架構（P1）

- [ ] 建立專案結構
- [ ] 設定 `vercel.json`
- [ ] 建立 `requirements.txt`
- [ ] 實作 `app/config.py`（環境變數管理）
- [ ] 建立 `.env.example`

### Phase 2: 核心功能（P1）

- [ ] 實作 `app/prompts.py`（System Prompt）
- [ ] 實作 `app/gpt_processor.py`
  - [ ] `process_message()` 函式
  - [ ] `BookkeepingEntry` 資料類別
  - [ ] 交易ID生成邏輯
- [ ] 實作 `app/webhook_sender.py`
  - [ ] `send_to_webhook()` 函式
  - [ ] 錯誤處理和 timeout
- [ ] 實作 `app/line_handler.py`
  - [ ] `handle_text_message()` 函式
  - [ ] 確認訊息格式化
- [ ] 實作 `api/webhook.py`
  - [ ] Vercel Function handler
  - [ ] LINE 簽章驗證
  - [ ] Event 路由

### Phase 3: 測試（P1）

- [ ] 撰寫 `test_gpt_processor.py`
- [ ] 撰寫 `test_webhook_sender.py`
- [ ] 撰寫 `test_integration.py`
- [ ] 執行所有測試並確保通過

### Phase 4: 部署（P1）

- [ ] 連接 Vercel GitHub Repository
- [ ] 設定 Vercel 環境變數
- [ ] 部署到 Vercel
- [ ] 設定 LINE Bot Webhook URL
- [ ] 驗證 Webhook 連線

### Phase 5: 驗證（P1）

- [ ] 手動測試：記帳功能
- [ ] 手動測試：一般對話
- [ ] 手動測試：不完整資訊提示
- [ ] 手動測試：錯誤處理
- [ ] 確認 Make.com 接收資料正確

---

## 🎯 成功標準

### 功能驗收

- ✅ 使用者發送「午餐 120 現金」→ 正確記帳並回覆確認
- ✅ 使用者發送「你好」→ GPT 回應友善對話
- ✅ 使用者發送「午餐 120」（缺付款方式）→ 提示「請提供品項、金額及付款方式」
- ✅ Make.com 接收正確的 JSON 格式資料
- ✅ 確認訊息包含「金額（台幣）」計算結果

### 非功能驗收

- ✅ 回應時間 < 3 秒（90% 情況）
- ✅ 錯誤時回覆友善訊息，不洩露內部資訊
- ✅ 所有敏感資訊使用環境變數管理
- ✅ 測試覆蓋率 > 80%（核心模組）

### v1 MVP 排除項目確認

- ❌ 多輪對話（正確行為：不完整資訊直接提示，不繼續追問）
- ❌ 對話歷史（正確行為：每次請求獨立處理）
- ❌ 外幣支援（正確行為：僅處理 TWD）
- ❌ 圖片識別（正確行為：僅處理文字訊息）
- ❌ Webhook 重試（正確行為：失敗僅告知使用者）

---

## 📚 依賴套件清單

**requirements.txt**：

```txt
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
```

---

## 🔄 未來擴充方向（v2+）

以下功能明確**不**在 v1 MVP 範圍，記錄供未來參考：

### v2 計畫功能

1. **多輪對話**：處理不完整資訊（追問機制）
2. **對話歷史**：引入資料庫（Redis/DynamoDB）儲存 session
3. **單一訊息多筆支出**：「早餐 50 現金；午餐 120 狗卡」
4. **外幣支援**：整合匯率 API
5. **Webhook 重試佇列**：使用 SQS 或 Redis Queue
6. **定期提醒**：信用卡繳費、週期性支出提醒

### v3 實驗功能

1. **圖片/收據識別**：OCR + GPT Vision
2. **即時資訊查詢**：整合天氣、新聞 API
3. **智慧分析**：月度支出報表、預算提醒

---

## 📞 問題與決策記錄

### Q1: 為何不使用資料庫？

**決策**：v1 MVP 採用完全無狀態設計
- **理由**：
  - 符合 MVP 原則（最簡單可行方案）
  - Vercel Serverless 天然適合無狀態
  - 降低基礎設施複雜度
  - Make.com 已處理資料持久化
- **權衡**：無法處理多輪對話 → 延後到 v2

### Q2: 為何使用 GPT 判斷意圖而非規則引擎？

**決策**：使用 GPT 自動判斷
- **理由**：
  - 使用者輸入格式多樣（「午餐120現金」、「現金 午餐 120」都要支援）
  - GPT 可處理自然語言變化
  - 開發速度快，無需維護複雜正則表達式
  - 符合「簡單勝過完美」原則
- **權衡**：每次請求呼叫 GPT API（但 gpt-4o-mini 成本低）

### Q3: 為何 Webhook 失敗不重試？

**決策**：v1 失敗僅告知使用者
- **理由**：
  - 重試機制需引入佇列（增加複雜度）
  - MVP 驗證核心價值，重試為次要功能
  - 使用者可重新發送訊息（手動重試）
- **權衡**：偶發網路錯誤會遺失資料 → v2 加入重試佇列

### Q4: 交易ID 如何確保唯一性？

**決策**：使用 `YYYYMMDD-序號` 格式，序號為時間戳記後4碼
- **理由**：
  - v1 無資料庫，無法查詢當日最大序號
  - 使用時間戳記（秒級）後4碼，單日重複機率極低
  - 範例：`20251112-5347`（13:53:47 的後4碼）
- **權衡**：理論上可能重複（同一秒內多筆） → v2 引入資料庫後改用自增序號

---

## ✅ 規劃完成確認

- [x] 架構設計完成
- [x] 模組職責明確
- [x] 資料結構定義
- [x] 流程圖繪製
- [x] 錯誤處理策略
- [x] 測試策略規劃
- [x] 部署步驟文件化
- [x] 安全性檢查
- [x] 依賴套件清單
- [x] 開發檢查清單
- [x] 成功驗收標準

**下一步**：執行 `/speckit.tasks` 生成可執行任務清單

---

**版本歷史**：
- v1.0.0 (2025-11-12) - 初版技術規劃完成
