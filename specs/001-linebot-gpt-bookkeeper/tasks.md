# LINE Bot GPT Bookkeeper - v1 MVP 任務清單

**版本**：1.0.0 | **建立日期**：2025-11-12 | **目標版本**：v1 MVP

---

## 📋 任務概覽

本文件定義 v1 MVP 的所有開發任務，按照依賴順序和優先級組織。

### 任務統計

- **總任務數**：25 個
- **P1（必要）**：25 個
- **預估總工時**：約 16-20 小時

### 階段劃分

1. **Phase 1 - 基礎架構**：5 個任務（2-3 小時）
2. **Phase 2 - 核心功能**：10 個任務（8-10 小時）
3. **Phase 3 - 測試**：4 個任務（3-4 小時）
4. **Phase 4 - 部署**：4 個任務（2-3 小時）
5. **Phase 5 - 驗證**：2 個任務（1 小時）

---

## Phase 1: 基礎架構設定

### T-001: 建立專案目錄結構

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：無

**描述**：
建立完整的專案目錄結構，包括所有必要的資料夾和空檔案。

**驗收標準**：
- [x] 建立 `api/` 目錄及 `webhook.py`
- [x] 建立 `app/` 目錄及所有模組檔案（`__init__.py`, `config.py`, `line_handler.py`, `gpt_processor.py`, `webhook_sender.py`, `prompts.py`）
- [x] 建立 `tests/` 目錄及測試檔案骨架
- [x] 目錄結構符合 plan.md 定義

**實作筆記**：
```bash
mkdir -p api app tests
touch api/webhook.py
touch app/{__init__.py,config.py,line_handler.py,gpt_processor.py,webhook_sender.py,prompts.py}
touch tests/{test_gpt_processor.py,test_webhook_sender.py,test_integration.py}
```

---

### T-002: 設定 .gitignore

**優先級**：P1
**預估時間**：15 分鐘
**依賴**：T-001

**描述**：
設定 .gitignore 排除不應提交的檔案（環境變數、Python cache 等）。

**驗收標準**：
- [x] 排除 `.env`
- [x] 排除 `__pycache__/` 和 `*.pyc`
- [x] 排除 `.pytest_cache/`
- [x] 排除 `.vercel/`
- [x] 排除 `venv/` 和 `.venv/`

**實作筆記**：
參考標準 Python .gitignore 模板。

---

### T-003: 建立 requirements.txt

**優先級**：P1
**預估時間**：15 分鐘
**依賴**：T-001

**描述**：
定義所有 Python 依賴套件及版本。

**驗收標準**：
- [x] 包含 `line-bot-sdk==3.8.0`
- [x] 包含 `openai>=1.12.0`
- [x] 包含 `requests>=2.31.0`
- [x] 包含 `Flask>=3.0.0`
- [x] 包含 `python-dotenv>=1.0.0`
- [x] 包含測試依賴：`pytest>=7.4.0`, `pytest-mock>=3.12.0`

**實作筆記**：
參考 plan.md 的「依賴套件清單」章節。

---

### T-004: 設定 vercel.json

**優先級**：P1
**預估時間**：20 分鐘
**依賴**：T-001

**描述**：
建立 Vercel 部署配置檔，定義 Serverless Function 設定。

**驗收標準**：
- [x] 設定 Python 3.11 runtime
- [x] 定義 `api/webhook.py` 為 Serverless Function
- [x] 設定路由：`/api/webhook` → `api/webhook.py`
- [x] 符合 plan.md 的 vercel.json 範例

**實作筆記**：
```json
{
  "version": 2,
  "builds": [{"src": "api/webhook.py", "use": "@vercel/python"}],
  "routes": [{"src": "/api/webhook", "dest": "api/webhook.py"}],
  "env": {"PYTHON_VERSION": "3.11"}
}
```

---

### T-005: 建立 .env.example

**優先級**：P1
**預估時間**：15 分鐘
**依賴**：T-001

**描述**：
建立環境變數範例檔，供開發者參考。

**驗收標準**：
- [x] 包含所有必要環境變數（見下方）
- [x] 提供說明註解
- [x] 敏感值使用 placeholder

**實作筆記**：
```bash
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here
LINE_CHANNEL_SECRET=your_line_channel_secret_here

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-your_openai_api_key_here
GPT_MODEL=gpt-4o-mini

# Webhook Configuration
WEBHOOK_URL=https://hook.us2.make.com/your_webhook_url_here
WEBHOOK_TIMEOUT=10
```

---

## Phase 2: 核心功能實作

### T-006: 實作 app/config.py

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-003, T-005

**描述**：
實作環境變數管理模組，載入並驗證所有配置。

**驗收標準**：
- [x] 使用 `python-dotenv` 載入 `.env`
- [x] 定義所有環境變數（LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, OPENAI_API_KEY, WEBHOOK_URL, GPT_MODEL, WEBHOOK_TIMEOUT）
- [x] 驗證必要變數存在（若缺少則拋出 `ValueError`）
- [x] 提供預設值（GPT_MODEL, WEBHOOK_TIMEOUT）
- [x] 通過單元測試（測試缺少必要變數時的行為）

**實作筆記**：
```python
import os
from dotenv import load_dotenv

load_dotenv()

# 必要變數
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# 選用變數（有預設值）
GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4o-mini')
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', '10'))

# 驗證
required_vars = {
    'LINE_CHANNEL_ACCESS_TOKEN': LINE_CHANNEL_ACCESS_TOKEN,
    'LINE_CHANNEL_SECRET': LINE_CHANNEL_SECRET,
    'OPENAI_API_KEY': OPENAI_API_KEY,
    'WEBHOOK_URL': WEBHOOK_URL,
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"Missing required environment variable: {var_name}")
```

---

### T-007: 實作 app/prompts.py

**優先級**：P1
**預估時間**：1 小時
**依賴**：T-001

**描述**：
定義 GPT System Prompt，整合 knowledge/ 的所有欄位標準值。

**驗收標準**：
- [x] 定義 `SYSTEM_PROMPT` 常數
- [x] 包含角色定義（「你是專業的記帳助手」）
- [x] 包含任務說明（判斷意圖、記帳處理、對話處理）
- [x] 整合完整的欄位標準值：
  - [x] 分類（所有類別及說明）
  - [x] 付款方式（包含別名映射）
  - [x] 專案、必要性、代墊狀態
- [x] 提供 JSON 輸出格式範例（bookkeeping + conversation）
- [x] 符合 plan.md 的 System Prompt 設計

**實作筆記**：
參考 plan.md 第 4 節「app/prompts.py - System Prompt 定義」的完整內容。

---

### T-008: 實作 app/gpt_processor.py - 資料結構

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-007

**描述**：
定義 `BookkeepingEntry` 資料類別，用於表示處理結果。

**驗收標準**：
- [x] 使用 `dataclasses` 定義 `BookkeepingEntry`
- [x] 包含所有欄位（日期、品項、原幣別、原幣金額等 14 個記帳欄位）
- [x] 包含 `intent` 欄位（Literal["bookkeeping", "conversation"]）
- [x] 包含 `response_text` 欄位（用於對話回應）
- [x] 適當的型別標註（使用 `Optional`, `Literal`）

**實作筆記**：
```python
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import date

@dataclass
class BookkeepingEntry:
    intent: Literal["bookkeeping", "conversation"]

    # 記帳欄位
    日期: Optional[str] = None
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

    # 對話欄位
    response_text: Optional[str] = None
```

---

### T-009: 實作 app/gpt_processor.py - 交易ID生成

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-008

**描述**：
實作交易ID生成邏輯（`YYYYMMDD-序號` 格式）。

**驗收標準**：
- [x] 函式 `generate_transaction_id()` 回傳字串
- [x] 格式：`YYYYMMDD-HHMM`（日期 + 時分）
- [x] 範例：`20251112-1430`（2025-11-12 14:30）
- [x] 通過單元測試（驗證格式正確）

**實作筆記**：
```python
from datetime import datetime

def generate_transaction_id() -> str:
    """生成交易ID：YYYYMMDD-HHMM"""
    now = datetime.now()
    return now.strftime("%Y%m%d-%H%M")
```

---

### T-010: 實作 app/gpt_processor.py - GPT API 呼叫

**優先級**：P1
**預估時間**：1.5 小時
**依賴**：T-006, T-007, T-008, T-009

**描述**：
實作 `process_message()` 函式，呼叫 OpenAI API 並解析回應。

**驗收標準**：
- [x] 函式簽章：`def process_message(user_message: str) -> BookkeepingEntry`
- [x] 使用 `openai` SDK 呼叫 Chat Completions API
- [x] 使用 `config.OPENAI_API_KEY` 和 `config.GPT_MODEL`
- [x] 構建 messages：`[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}]`
- [x] 解析 GPT JSON 回應
- [x] 判斷 intent：
  - 若為 "bookkeeping" → 驗證必要欄位（品項、原幣金額、付款方式）、生成交易ID、補充預設值（日期、匯率、專案等）
  - 若為 "conversation" → 提取 response_text
- [x] 錯誤處理：
  - GPT API 失敗 → 拋出 `Exception`
  - JSON 解析失敗 → 拋出 `ValueError`
  - 必要欄位缺失 → 拋出 `ValueError`
- [x] 通過單元測試（mock OpenAI API）

**實作筆記**：
```python
import json
from openai import OpenAI
from app.config import OPENAI_API_KEY, GPT_MODEL
from app.prompts import SYSTEM_PROMPT

def process_message(user_message: str) -> BookkeepingEntry:
    client = OpenAI(api_key=OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"}  # 確保 JSON 輸出
    )

    response_text = completion.choices[0].message.content
    data = json.loads(response_text)

    intent = data.get("intent")

    if intent == "bookkeeping":
        entry_data = data.get("data", {})
        # 生成交易ID
        entry_data["交易ID"] = generate_transaction_id()
        # 補充日期
        if not entry_data.get("日期"):
            entry_data["日期"] = datetime.now().strftime("%Y-%m-%d")
        # 驗證必要欄位
        required = ["品項", "原幣金額", "付款方式"]
        for field in required:
            if not entry_data.get(field):
                raise ValueError(f"Missing required field: {field}")

        return BookkeepingEntry(intent="bookkeeping", **entry_data)

    elif intent == "conversation":
        return BookkeepingEntry(
            intent="conversation",
            response_text=data.get("response", "")
        )

    else:
        raise ValueError(f"Unknown intent: {intent}")
```

---

### T-011: 實作 app/webhook_sender.py

**優先級**：P1
**預估時間**：1 小時
**依賴**：T-006, T-008

**描述**：
實作 `send_to_webhook()` 函式，發送記帳資料到 Make.com。

**驗收標準**：
- [x] 函式簽章：`def send_to_webhook(entry: BookkeepingEntry) -> bool`
- [x] 轉換 BookkeepingEntry 為 Make.com JSON 格式（14 個欄位，**不包含**「金額（台幣）」）
- [x] 使用 `requests.post()` 發送到 `config.WEBHOOK_URL`
- [x] 設定 `Content-Type: application/json`
- [x] 設定 timeout（使用 `config.WEBHOOK_TIMEOUT`）
- [x] 錯誤處理：
  - 網路錯誤 → 記錄日誌，回傳 False
  - HTTP 4xx/5xx → 記錄日誌，回傳 False
  - Timeout → 記錄日誌，回傳 False
  - 成功（200/201/202） → 回傳 True
- [x] 通過單元測試（mock requests）

**實作筆記**：
```python
import requests
import logging
from app.config import WEBHOOK_URL, WEBHOOK_TIMEOUT
from app.gpt_processor import BookkeepingEntry

logger = logging.getLogger(__name__)

def send_to_webhook(entry: BookkeepingEntry) -> bool:
    """發送記帳資料到 Make.com webhook"""

    # 轉換為 Make.com 格式
    payload = {
        "日期": entry.日期,
        "品項": entry.品項,
        "原幣別": entry.原幣別,
        "原幣金額": entry.原幣金額,
        "匯率": entry.匯率,
        "付款方式": entry.付款方式,
        "交易ID": entry.交易ID,
        "明細說明": entry.明細說明,
        "分類": entry.分類,
        "專案": entry.專案,
        "必要性": entry.必要性,
        "代墊狀態": entry.代墊狀態,
        "收款／支付對象": entry.收款支付對象,
        "附註": entry.附註,
    }

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=WEBHOOK_TIMEOUT
        )

        if response.status_code in [200, 201, 202]:
            logger.info(f"Webhook sent successfully: {entry.交易ID}")
            return True
        else:
            logger.error(f"Webhook failed with status {response.status_code}")
            return False

    except requests.Timeout:
        logger.error("Webhook request timeout")
        return False
    except requests.RequestException as e:
        logger.error(f"Webhook request failed: {e}")
        return False
```

---

### T-012: 實作 app/line_handler.py - 確認訊息格式化

**優先級**：P1
**預估時間**：45 分鐘
**依賴**：T-008

**描述**：
實作 `format_confirmation_message()` 函式，格式化記帳確認訊息。

**驗收標準**：
- [x] 函式簽章：`def format_confirmation_message(entry: BookkeepingEntry) -> str`
- [x] 顯示所有重要欄位（日期、品項、金額台幣、付款方式、分類、必要性、交易ID）
- [x] **計算並顯示「金額（台幣）」**：`原幣金額 × 匯率`
- [x] 格式清晰、易讀（使用表情符號 ✅）
- [x] 符合 plan.md 的範例格式
- [x] 通過單元測試

**實作筆記**：
```python
def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """格式化記帳確認訊息"""

    # 計算金額（台幣）
    金額台幣 = entry.原幣金額 * entry.匯率

    message = f"""✅ 記帳成功！

日期：{entry.日期}
品項：{entry.品項}
金額（台幣）：{金額台幣:.0f} 元
付款方式：{entry.付款方式}
分類：{entry.分類}
必要性：{entry.必要性}
交易ID：{entry.交易ID}"""

    # 如果有明細說明，加上
    if entry.明細說明:
        message += f"\n明細說明：{entry.明細說明}"

    return message
```

---

### T-013: 實作 app/line_handler.py - 主處理函式

**優先級**：P1
**預估時間**：1.5 小時
**依賴**：T-006, T-010, T-011, T-012

**描述**：
實作 `handle_text_message()` 函式，處理 LINE 文字訊息的主流程。

**驗收標準**：
- [x] 函式簽章：`def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None`
- [x] 取得使用者訊息文字
- [x] 呼叫 `gpt_processor.process_message()`
- [x] 判斷 intent：
  - 若為 "bookkeeping"：
    - 呼叫 `webhook_sender.send_to_webhook()`
    - 若成功 → 回覆確認訊息（使用 `format_confirmation_message()`）
    - 若失敗 → 回覆「記帳資料處理失敗，請稍後重試」
  - 若為 "conversation"：
    - 回覆 GPT 生成的 `response_text`
- [x] 錯誤處理：
  - GPT API 失敗 → 回覆「抱歉，目前無法處理您的訊息，請稍後再試」
  - 其他錯誤 → 回覆通用錯誤訊息
- [x] 使用 `line_bot_api.reply_message()` 回覆
- [x] 記錄適當的日誌
- [x] 通過整合測試

**實作筆記**：
```python
import logging
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi
from app.gpt_processor import process_message
from app.webhook_sender import send_to_webhook

logger = logging.getLogger(__name__)

def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """處理文字訊息"""

    user_message = event.message.text
    reply_token = event.reply_token

    try:
        # 呼叫 GPT 處理
        entry = process_message(user_message)

        if entry.intent == "bookkeeping":
            # 發送 webhook
            success = send_to_webhook(entry)

            if success:
                # 成功：回覆確認訊息
                reply_text = format_confirmation_message(entry)
            else:
                # 失敗：提示使用者
                reply_text = "記帳資料處理失敗，請稍後重試。"

        elif entry.intent == "conversation":
            # 對話：回覆 GPT 生成的文字
            reply_text = entry.response_text

        else:
            reply_text = "抱歉，無法理解您的訊息。"

        # 回覆 LINE 使用者
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="抱歉，目前無法處理您的訊息，請稍後再試。")
        )
```

---

### T-014: 實作 api/webhook.py - LINE 簽章驗證

**優先級**：P1
**預估時間**：45 分鐘
**依賴**：T-006

**描述**：
實作 Vercel Function 入口，驗證 LINE Webhook 簽章。

**驗收標準**：
- [x] 函式名稱：`handler(request)` 或符合 Vercel Python runtime 規範
- [x] 取得 request body（as text）
- [x] 取得 `X-Line-Signature` header
- [x] 使用 `WebhookHandler` 驗證簽章
- [x] 驗證失敗 → 回傳 400
- [x] 驗證成功 → 繼續處理
- [x] 符合 Vercel Serverless Function 格式

**實作筆記**：
```python
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage
from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from app.line_handler import handle_text_message

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.route("/api/webhook", methods=['POST'])
def webhook():
    # 取得簽章
    signature = request.headers.get('X-Line-Signature')

    # 取得 request body
    body = request.get_data(as_text=True)

    # 驗證簽章
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    handle_text_message(event, line_bot_api)
```

---

### T-015: 實作 api/webhook.py - Event 處理

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-013, T-014

**描述**：
完成 Vercel Function，處理 LINE MessageEvent。

**驗收標準**：
- [x] 使用 `@handler.add()` decorator 處理 `MessageEvent`
- [x] 僅處理 `TextMessage` 類型
- [x] 呼叫 `line_handler.handle_text_message()`
- [x] 其他訊息類型（圖片、貼圖等）忽略或回覆提示
- [x] 回傳 200 OK（LINE 平台要求）
- [x] 錯誤時也回傳 200（避免 LINE 重試）
- [x] 記錄適當日誌

**實作筆記**：
整合到 T-014 的程式碼中。

---

## Phase 3: 測試

### T-016: 撰寫 test_gpt_processor.py - 單元測試

**優先級**：P1
**預估時間**：1.5 小時
**依賴**：T-010

**描述**：
撰寫 GPT 處理器的單元測試。

**驗收標準**：
- [x] 測試記帳意圖識別（mock OpenAI API 回傳 bookkeeping intent）
- [x] 測試一般對話識別（mock OpenAI API 回傳 conversation intent）
- [x] 測試交易ID生成（驗證格式 `YYYYMMDD-HHMM`）
- [x] 測試必要欄位驗證（缺少品項/金額/付款方式時拋出 ValueError）
- [x] 測試預設值補充（日期、匯率、專案等）
- [x] 測試 GPT API 錯誤處理
- [x] 所有測試通過（`pytest tests/test_gpt_processor.py`）

**實作筆記**：
使用 `pytest-mock` mock OpenAI API。

---

### T-017: 撰寫 test_webhook_sender.py - 單元測試

**優先級**：P1
**預估時間**：1 小時
**依賴**：T-011

**描述**：
撰寫 Webhook 發送器的單元測試。

**驗收標準**：
- [x] 測試正常發送（mock `requests.post` 回傳 200）→ 回傳 True
- [x] 測試 HTTP 錯誤（mock 回傳 500）→ 回傳 False
- [x] 測試網路錯誤（mock 拋出 `RequestException`）→ 回傳 False
- [x] 測試 Timeout（mock 拋出 `Timeout`）→ 回傳 False
- [x] 驗證發送的 JSON payload 格式正確（14 個欄位）
- [x] 驗證 Content-Type header
- [x] 所有測試通過（`pytest tests/test_webhook_sender.py`）

**實作筆記**：
使用 `pytest-mock` mock `requests` 模組。

---

### T-018: 撰寫 test_integration.py - 整合測試

**優先級**：P1
**預估時間**：1.5 小時
**依賴**：T-015

**描述**：
撰寫端到端整合測試。

**驗收標準**：
- [x] 測試完整記帳流程（模擬 LINE Webhook → GPT → Make.com → LINE 回覆）
- [x] 測試完整對話流程
- [x] 測試不完整資訊處理
- [x] 測試錯誤情境（GPT API 失敗、Webhook 失敗）
- [x] Mock 所有外部 API（LINE、OpenAI、Make.com）
- [x] 驗證回覆訊息內容正確
- [x] 所有測試通過（`pytest tests/test_integration.py`）

**實作筆記**：
使用 Flask test client 模擬 LINE Webhook 請求。

---

### T-019: 執行所有測試並修正

**優先級**：P1
**預估時間**：1 小時
**依賴**：T-016, T-017, T-018

**描述**：
執行完整測試套件，確保所有測試通過。

**驗收標準**：
- [x] 執行 `pytest tests/` 所有測試通過
- [x] 測試覆蓋率 > 80%（核心模組）
- [x] 無 flaky tests（不穩定的測試）
- [x] 修正所有發現的 bug

**實作筆記**：
```bash
pytest tests/ -v --cov=app --cov=api
```

---

## Phase 4: 部署

### T-020: 準備 Vercel 部署

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-019

**描述**：
確認所有部署相關檔案就緒。

**驗收標準**：
- [x] `vercel.json` 配置正確
- [x] `requirements.txt` 包含所有依賴
- [x] `.gitignore` 排除敏感檔案
- [x] `.env.example` 文件化完整
- [x] 程式碼已提交到 Git repository
- [x] README.md 包含基本說明（選用）

---

### T-021: 連接 Vercel 並設定環境變數

**優先級**：P1
**預估時間**：45 分鐘
**依賴**：T-020

**描述**：
在 Vercel Dashboard 連接 GitHub repository 並設定環境變數。

**驗收標準**：
- [x] Vercel 連接到 GitHub repository
- [x] 設定所有環境變數（見下方）：
  - `LINE_CHANNEL_ACCESS_TOKEN` (Secret)
  - `LINE_CHANNEL_SECRET` (Secret)
  - `OPENAI_API_KEY` (Secret)
  - `WEBHOOK_URL` (Sensitive)
  - `GPT_MODEL` (Plain Text)
- [x] 環境變數設定為 Production + Preview
- [x] 截圖保存環境變數設定（記錄用）

**實作筆記**：
Vercel Dashboard → Settings → Environment Variables

---

### T-022: 部署到 Vercel 並驗證

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-021

**描述**：
觸發 Vercel 部署並驗證部署成功。

**驗收標準**：
- [x] Vercel 自動偵測 `vercel.json` 並部署
- [x] 部署成功（Build 狀態為 Ready）
- [x] 取得部署 URL：`https://<your-app>.vercel.app`
- [x] 測試 `/api/webhook` endpoint（使用 curl 或 Postman）
- [x] 檢查 Vercel Function Logs（確認無啟動錯誤）

**實作筆記**：
```bash
# 測試 endpoint（應回傳 400，因為無有效簽章）
curl -X POST https://<your-app>.vercel.app/api/webhook
```

---

### T-023: 設定 LINE Bot Webhook URL

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-022

**描述**：
在 LINE Developers Console 設定 Webhook URL。

**驗收標準**：
- [x] 前往 LINE Developers Console
- [x] 選擇對應的 Channel
- [x] Messaging API → Webhook settings
- [x] 設定 Webhook URL：`https://<your-app>.vercel.app/api/webhook`
- [x] 啟用 "Use webhook"
- [x] 點擊 "Verify" 驗證 Webhook（應顯示成功）
- [x] 關閉 "Auto-reply messages"（避免干擾）
- [x] 關閉 "Greeting messages"（選用）

**實作筆記**：
LINE Developers Console → Messaging API settings

---

## Phase 5: 驗證

### T-024: 手動測試 - 記帳功能

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-023

**描述**：
在 LINE 進行手動測試，驗證記帳功能正常運作。

**驗收標準**：
- [x] 加入 LINE Bot 為好友
- [x] 測試案例 1：「午餐 120 現金」
  - 收到確認訊息
  - Make.com 接收到資料
  - 資料正確（品項、金額、付款方式、分類等）
- [x] 測試案例 2：「200 點心 狗卡」
  - 付款方式正確映射為「台新狗卡」
- [x] 測試案例 3：「早餐 50」（缺付款方式）
  - 收到提示訊息：「請提供品項、金額及付款方式」
- [x] 測試案例 4：多次記帳（驗證交易ID不重複）
- [x] 檢查 Make.com 接收的資料格式正確

**實作筆記**：
準備測試案例清單和預期結果。

---

### T-025: 手動測試 - 一般對話與錯誤處理

**優先級**：P1
**預估時間**：30 分鐘
**依賴**：T-024

**描述**：
測試一般對話和錯誤處理情境。

**驗收標準**：
- [x] 測試一般對話：
  - 「你好」→ GPT 友善回應
  - 「怎麼記帳？」→ GPT 說明記帳格式
- [x] 測試錯誤處理（需臨時調整配置）：
  - 錯誤的 OPENAI_API_KEY → 回覆通用錯誤訊息（不洩露內部資訊）
  - 錯誤的 WEBHOOK_URL → 回覆「記帳資料處理失敗」
- [x] 檢查 Vercel Logs 確認錯誤有正確記錄
- [x] 所有測試案例通過

**實作筆記**：
記錄所有測試結果和截圖。

---

## 📊 任務依賴圖

```
T-001 (專案結構)
  ├─→ T-002 (.gitignore)
  ├─→ T-003 (requirements.txt)
  ├─→ T-004 (vercel.json)
  ├─→ T-005 (.env.example)
  └─→ T-007 (prompts.py)

T-003 → T-006 (config.py)

T-007 → T-008 (資料結構)
       → T-009 (交易ID)
       → T-010 (GPT processor)

T-006, T-008 → T-011 (webhook sender)

T-008 → T-012 (確認訊息)

T-006, T-010, T-011, T-012 → T-013 (line handler)

T-006 → T-014 (webhook 簽章驗證)

T-013, T-014 → T-015 (webhook event 處理)

T-010 → T-016 (GPT 測試)
T-011 → T-017 (Webhook 測試)
T-015 → T-018 (整合測試)

T-016, T-017, T-018 → T-019 (執行所有測試)

T-019 → T-020 (準備部署)
      → T-021 (Vercel 設定)
      → T-022 (部署驗證)
      → T-023 (LINE 設定)
      → T-024 (手動測試 - 記帳)
      → T-025 (手動測試 - 對話)
```

---

## ✅ 完成檢查清單

### Phase 1 完成標準
- [ ] 所有 T-001 至 T-005 完成
- [ ] 專案結構建立
- [ ] 配置檔案就緒

### Phase 2 完成標準
- [ ] 所有 T-006 至 T-015 完成
- [ ] 所有核心模組實作完成
- [ ] 程式碼符合 plan.md 設計

### Phase 3 完成標準
- [ ] 所有 T-016 至 T-019 完成
- [ ] 所有測試通過
- [ ] 測試覆蓋率 > 80%

### Phase 4 完成標準
- [ ] 所有 T-020 至 T-023 完成
- [ ] Vercel 部署成功
- [ ] LINE Bot Webhook 連線驗證成功

### Phase 5 完成標準
- [ ] 所有 T-024 至 T-025 完成
- [ ] 所有手動測試案例通過
- [ ] Make.com 接收資料正確

### v1 MVP 完成標準
- [ ] 所有 25 個任務完成
- [ ] 符合 spec.md 的 v1 MVP 驗收標準
- [ ] 符合 plan.md 的成功標準
- [ ] 系統穩定運作，無重大 bug

---

## 📝 備註

### 開發建議

1. **嚴格按照依賴順序**：不要跳過前置任務
2. **每完成一個 Phase 提交一次 Git**：方便回溯
3. **測試驅動**：Phase 2 實作時可先寫測試（TDD）
4. **日誌記錄**：開發過程記錄遇到的問題和解決方案
5. **環境變數**：本地開發使用 `.env`，部署使用 Vercel Environment Variables

### 時間估算說明

- 預估總工時：16-20 小時
- 建議分配：
  - Day 1：Phase 1 + Phase 2 部分（6-8 小時）
  - Day 2：Phase 2 完成 + Phase 3（6-8 小時）
  - Day 3：Phase 4 + Phase 5（3-4 小時）

### 風險提示

- **GPT API 成本**：開發測試時會產生少量 API 費用（gpt-4o-mini 成本很低）
- **Vercel Cold Start**：首次請求可能較慢（3-5 秒），後續會快速
- **LINE Webhook Timeout**：確保 GPT 回應時間 < 3 秒

---

**版本歷史**：
- v1.0.0 (2025-11-12) - 初版任務清單完成
