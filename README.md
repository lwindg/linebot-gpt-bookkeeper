# LINE Bot GPT 記帳中介系統 (v2.0)

一個智慧的記帳助手，透過 LINE Bot 和 GPT-4o-mini 將自然語言轉換為結構化記帳資料。**Version 2.0 採用 Parser-first 架構，實現更精準、更低延遲的解析體驗。**

## ✨ 功能特色

- 🗣️ **自然語言記帳**：用對話方式記錄支出，如「午餐花了150元刷卡」
- 🤖 **GPT 智慧解析**：自動識別品項、金額、付款方式、分類等資訊
- 📅 **智慧日期時間處理**：支援語義化日期與精確時間 (HH:MM) 提取
- 💴 **深層日圓支援**：精準識別 ¥、円 符號，並支援「日圓現金」等支付方式自動換匯
- 🔄 **多重編輯修正**：在下一筆記帳開始前，可無限次修正上一筆記錄（支援修改幣別、匯率）
- 🔗 **Webhook 整合**：將解析結果發送到外部記帳系統（如 Make.com、Google Sheets）
- ☁️ **Serverless 架構**：部署在 Vercel，無需維護伺服器
- 🧪 **自動化測試體系**：整合 `./run_tests.sh` 確保系統穩定性

## ✅ 現況功能 (v2.0 Parser-first Architecture)

- **Parser-first 策略**：優先使用正則與邏輯解析 Authority Fields（金額、日期、時間、付款方式），GPT 僅負責語義 Enrichment。
- **時間與 ID 同步**：從文字或圖片中提取時間 (HH:MM)，交易 ID 格式統一為 `YYYYMMDD-HHMMSS`。
- **進階修正意圖**：支援「改幣別為日圓」、「匯率 0.22」等精確修正，自動查詢最新匯率。
- **持久化編輯**：支援對最後一筆交易進行多次連續修正，直到開始新的一筆。
- **多項目記帳**：支援單句多項目、現金流（提款、轉帳、繳卡費、收入）。
- **外幣自動換算**：支援多幣別與即時/手動匯率換算。

## 🏗️ 技術架構

```
LINE Platform → Vercel Serverless Function → Parser (Authority Fields) → GPT (Enrichment) → Webhook
                       ↓
                   LINE Bot API (回覆使用者)
```

### 技術棧

- **Environment Management**: [uv](https://astral.sh/uv) (快速、可靠的 Python 套件管理)
- **Backend**: Python 3.11+
- **Framework**: Flask (Serverless)
- **LINE SDK**: line-bot-sdk 3.8.0
- **OpenAI SDK**: openai >= 1.12.0
- **部署平台**: Vercel
- **開發方法論**: Spec Kit & Parser-first Strategy

### 環境需求

- Python 3.11 或以上
- LINE Developer Account（[申請連結](https://developers.line.biz/)）
- OpenAI API Key（[取得連結](https://platform.openai.com/api-keys)）
- Make.com 帳號或其他 Webhook 接收端（選用）

### 安裝

1. **Clone 專案**

```bash
git clone https://github.com/lwindg/linebot-gpt-bookkeeper.git
cd linebot-gpt-bookkeeper
```

2. **安裝相依套件（uv）**

```bash
uv sync
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

### 多項目記帳（Parser-first 注意事項）

- 分隔符號：支援換行、逗號（, / ，）、分號（; / ；）、頓號（、）。
- **付款方式不能被分隔符切成獨立一段**；必須跟最後一個項目同段（前面最多只有空白）。
- 推薦格式：`品項金額、品項金額 付款方式` 或使用換行分隔。

✅ 正確：
- `早餐80、午餐150 現金`
- `早餐80\n午餐150 現金`

❌ 錯誤（付款方式被切成單獨段）：
- `早餐80、午餐150、現金`
- `現金，早餐80，午餐150`

### Advance Payment / Need to Pay (Parser-first)

- **Advance paid (you paid for someone)**: `幫/代 + 對象 + 買/付/墊/代墊/墊付/購買`
- **Need to pay (someone paid for you)**: `對象 + 代訂/代付/幫買/先墊/幫購買`
- **No-claim**: contains `不用還 / 不索取 / 送給 / 請客 / 我請`, or patterns like `請{對象}喝/吃/早餐/午餐/晚餐`
- Keep the counterparty close to the keyword (short phrase works best).
- If you haven't paid yet, omit the payment method to keep it `NA`.
- In multi-item messages, only the item that contains the keyword gets the advance status.

Examples:
- Advance paid: `幫同事墊付計程車費300元現金`
- Need to pay: `同事先墊午餐費150元`
- No-claim: `幫媽媽買藥500元現金不用還`
- Mixed items: `早餐80、午餐150幫同事代墊 現金`

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
│   ├── gpt/                # GPT 解析與提示
│   ├── line/               # LINE 回覆格式與更新流程
│   ├── parser/             # Parser-first 解析
│   ├── services/           # 外部 I/O 與服務
│   ├── shared/             # 共用解析與 resolver
│   ├── pipeline/           # 共用流程與 normalization
│   ├── enricher/           # GPT enrichment
│   ├── config.py           # 環境變數載入
│   ├── gpt_processor.py    # GPT 路徑入口
│   └── line_handler.py     # LINE 訊息處理入口
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
/prompts:specify-specify

# 執行實作規劃
/prompts:specify-plan

# 釐清規格不明確之處
/prompts:specify-clarify

# 生成可執行任務清單
/prompts:specify-tasks

# 執行實作計畫
/prompts:specify-implement

# 分析一致性和品質
/prompts:specify-analyze
```

### Git 工作流程

遵循專案憲章定義的 Git 規範：

- **分支命名**：`$action/$description`（例如：`feat/multi-entries`, `fix/date-parsing`）
- **提交格式**：`$action(module): $message`（例如：`feat(gpt): add semantic date parsing`）
- **允許的動作**：`feat`, `fix`, `refactor`, `docs`, `test`, `style`, `chore`

### 測試 (Testing)

本專案擁有完整的自動化測試套件，涵蓋單元測試、解析器測試與端到端測試。

```bash
# 執行全量測試（推薦）
./run_tests.sh

# 執行單元測試
pytest

# 執行本地互動式測試
python test_local.py
```

## 🔮 未來展望

- **Notion 直接整合**：預計開發直接與 Notion API 對接的功能，擺脫中間人（如 Make.com）的 API 呼叫次數限制。
- **更精細的分類邏輯**：基於歷史記帳習慣的個性化分類推薦。

## 📚 相關文件

### 核心文件
- [功能規格書](specs/001-linebot-gpt-bookkeeper/spec.md) - 完整的功能需求和驗收標準
- [專案憲章](.specify/memory/constitution.md) - 核心開發原則
- [Claude 開發指南](CLAUDE.md) - AI 助手開發規範

### 使用指南
- [收據辨識指南](docs/RECEIPT_USAGE_GUIDE.md) - 收據拍照和圖片辨識使用說明
- [本地 Vision 測試](docs/LOCAL_VISION_TEST.md) - 本地測試 GPT Vision API
- [自動化測試指南](docs/AUTO_TEST_GUIDE.md) - 自動化測試腳本使用說明

### 版本發布
- [Release Notes](docs/releases/) - 所有版本的詳細發布說明

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
**最後更新**：2026-02-07 (v2.0 Milestone)
