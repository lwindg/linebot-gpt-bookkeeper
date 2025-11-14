# LINE Bot GPT 記帳中介系統

一個智慧的記帳助手，透過 LINE Bot 和 GPT-4o-mini 將自然語言轉換為結構化記帳資料。

## ✨ 功能特色

- 🗣️ **自然語言記帳**：用對話方式記錄支出，如「午餐花了150元刷卡」
- 🤖 **GPT 智慧解析**：自動識別品項、金額、付款方式、分類等資訊
- 📅 **智慧日期處理**：支援「今天」、「昨天」、「前天」等語義化日期
- 🔗 **Webhook 整合**：將解析結果發送到外部記帳系統（如 Make.com、Google Sheets）
- ☁️ **Serverless 架構**：部署在 Vercel，無需維護伺服器
- 🧪 **本地測試工具**：無需 LINE webhook 即可快速測試 GPT 解析功能

## 📦 版本資訊

**當前版本**：v1.0.0 MVP

### v1.0.0 MVP 特色

- ✅ 處理**資訊完整**的單筆台幣記帳
- ✅ 簡單的一般對話回應
- ✅ 無狀態 Serverless 架構
- ✅ 智慧日期解析（語義化日期 + 數字格式）
- ✅ 自動推斷分類、必要性、專案等欄位
- ✅ 完整的 14 欄位 JSON 輸出

### v1.0.0 MVP 限制

- ❌ 僅支援台幣（TWD）
- ❌ 單次訊息僅處理單筆支出
- ❌ 不支援圖片/收據識別
- ❌ 不儲存對話歷史（無多輪對話）
- ❌ 不支援外幣和匯率查詢
- ❌ 無持久化重試機制

### 未來版本規劃

- **v1.5.0**：單一訊息多筆支出、圖片/收據識別（GPT Vision）
- **v2.0.0**：對話脈絡管理、多輪對話、外幣支援、即時資訊查詢

詳細版本規劃請參考 [specs/001-linebot-gpt-bookkeeper/spec.md](specs/001-linebot-gpt-bookkeeper/spec.md)

## 🏗️ 技術架構

```
LINE Platform → Vercel Serverless Function → GPT-4o-mini → Webhook (記帳系統)
                       ↓
                   LINE Bot API (回覆使用者)
```

### 技術棧

- **Backend**: Python 3.9+
- **Framework**: Flask (Serverless)
- **LINE SDK**: line-bot-sdk 3.8.0
- **OpenAI SDK**: openai >= 1.12.0
- **部署平台**: Vercel
- **開發方法論**: Spec Kit

## 🚀 快速開始

### 環境需求

- Python 3.9 或以上
- LINE Developer Account（[申請連結](https://developers.line.biz/)）
- OpenAI API Key（[取得連結](https://platform.openai.com/api-keys)）
- Make.com 帳號或其他 Webhook 接收端（選用）

### 安裝

1. **Clone 專案**

```bash
git clone https://github.com/lwindg/linebot-gpt-bookkeeper.git
cd linebot-gpt-bookkeeper
```

2. **安裝相依套件**

```bash
pip install -r requirements.txt
```

3. **設定環境變數**

複製 `.env.example` 為 `.env` 並填入您的金鑰：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：

```env
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token_here
LINE_CHANNEL_SECRET=your_line_channel_secret_here

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-your_openai_api_key_here

# GPT Model (選用，預設為 gpt-4o-mini)
GPT_MODEL=gpt-4o-mini

# Webhook Configuration
WEBHOOK_URL=https://hook.us2.make.com/your_webhook_url_here

# Webhook timeout in seconds (選用，預設為 10)
WEBHOOK_TIMEOUT=10
```

### 本地測試

使用 `test_local.py` 測試 GPT 解析功能，無需 LINE webhook：

```bash
# 互動模式（推薦）
python test_local.py

# 單次測試（注意：使用單引號避免 shell 特殊字元問題）
python test_local.py '午餐$120現金'
python test_local.py '前天 花磚甜點$410大戶'
```

### 部署到 Vercel

1. **安裝 Vercel CLI**

```bash
npm install -g vercel
```

2. **部署**

```bash
vercel
```

3. **設定 LINE Webhook URL**

在 [LINE Developers Console](https://developers.line.biz/console/) 設定 Webhook URL：

```
https://your-project.vercel.app/api/webhook
```

4. **驗證部署**

發送訊息到您的 LINE Bot，確認收到回應。

## 📝 使用範例

### 記帳範例

| 使用者輸入 | 解析結果 |
|-----------|---------|
| `午餐花了150元刷卡` | 品項：午餐<br>金額：150 TWD<br>付款：刷卡<br>分類：家庭／餐飲／午餐 |
| `今天 早餐$80現金` | 品項：早餐<br>金額：80 TWD<br>付款：現金<br>日期：2025-11-14 |
| `11/12 花磚甜點$410大戶` | 品項：花磚甜點<br>金額：410 TWD<br>付款：大戶信用卡<br>日期：2025-11-12 |
| `前天 午餐$120現金` | 品項：午餐<br>金額：120 TWD<br>付款：現金<br>日期：2025-11-12（假設今天是 11/14） |

### 一般對話

| 使用者輸入 | 系統回應 |
|-----------|---------|
| `你好` | 友善的問候回應 |
| `我可以記帳什麼？` | 說明記帳功能和支援格式 |
| `買了咖啡` | 抱歉，請提供完整資訊（品項、金額、付款方式）以便記帳 |

### Webhook JSON 格式

系統會發送以下格式的 JSON 到您設定的 Webhook URL：

```json
{
  "日期": "2025-11-14",
  "時間": "12:00",
  "品項": "午餐",
  "原幣別": "TWD",
  "原幣金額": 150.00,
  "匯率": 1.0,
  "付款方式": "信用卡",
  "交易ID": "20251114-120000",
  "明細說明": "午餐花了150元刷卡",
  "分類": "家庭／餐飲／午餐",
  "專案": "日常",
  "必要性": "必要日常支出",
  "代墊狀態": "無",
  "收款／支付對象": "",
  "附註": ""
}
```

## 🛠️ 開發指南

### 專案結構

```
linebot-gpt-bookkeeper/
├── api/
│   └── webhook.py          # Vercel Serverless 入口點
├── app/
│   ├── config.py           # 環境變數載入
│   ├── gpt_processor.py    # GPT 處理邏輯、日期解析
│   ├── line_handler.py     # LINE 訊息處理
│   ├── prompts.py          # GPT System Prompt
│   └── webhook_sender.py   # Webhook 發送邏輯
├── specs/                  # Spec Kit 規格文件
│   └── 001-linebot-gpt-bookkeeper/
│       ├── spec.md         # 功能規格
│       ├── plan.md         # 技術規劃
│       └── tasks.md        # 任務清單
├── .specify/               # Spec Kit 配置
│   └── memory/
│       └── constitution.md # 專案憲章
├── test_local.py           # 本地測試工具
├── requirements.txt        # Python 相依套件
├── vercel.json             # Vercel 部署設定
├── .env.example            # 環境變數範例
├── CLAUDE.md               # Claude AI 開發指南
└── README.md               # 本檔案
```

### 使用 Spec Kit 開發

本專案採用 Spec Kit 開發方法論，詳細開發規範請參考 [CLAUDE.md](CLAUDE.md)。

#### 快速參考

```bash
# 建立功能規格
/speckit.specify

# 執行實作規劃
/speckit.plan

# 釐清規格不明確之處
/speckit.clarify

# 生成可執行任務清單
/speckit.tasks

# 執行實作計畫
/speckit.implement

# 分析一致性和品質
/speckit.analyze
```

### Git 工作流程

遵循專案憲章定義的 Git 規範：

- **分支命名**：`$action/$description`（例如：`feat/multi-entries`, `fix/date-parsing`）
- **提交格式**：`$action(module): $message`（例如：`feat(gpt): add semantic date parsing`）
- **允許的動作**：`feat`, `fix`, `refactor`, `docs`, `test`, `style`, `chore`

### 測試

```bash
# 執行單元測試
pytest

# 執行本地整合測試
python test_local.py
```

## 📚 相關文件

- [功能規格書](specs/001-linebot-gpt-bookkeeper/spec.md) - 完整的功能需求和驗收標準
- [專案憲章](.specify/memory/constitution.md) - 核心開發原則
- [Claude 開發指南](CLAUDE.md) - AI 助手開發規範

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request！

在提交 PR 前，請確保：
- 遵循 [CLAUDE.md](CLAUDE.md) 定義的開發規範
- 更新相關的 Spec Kit 文件（spec.md, plan.md, tasks.md）
- 通過所有測試
- 提交訊息符合 Git 規範

## 📄 授權

MIT License

## 🙏 致謝

- [LINE Messaging API](https://developers.line.biz/en/docs/messaging-api/)
- [OpenAI GPT-4o-mini](https://platform.openai.com/docs/)
- [Vercel](https://vercel.com/)
- [Spec Kit](https://github.com/speckai/specify)

---

**專案維護者**：lwindg
**最後更新**：2025-11-14
**版本**：v1.0.0
