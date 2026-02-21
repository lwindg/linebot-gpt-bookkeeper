# LINE Bot GPT 記帳中介系統 (v3.0)

一個智慧的記帳助手，透過 LINE Bot 和 GPT-4o-mini 將自然語言轉換為結構化記帳資料。**Version 3.0 實現了 Notion 直接整合、智慧會話鎖定與強大的專案結算功能，為您提供更穩定、更專業的理財體驗。**

## ✨ 功能特色

- 🗣️ **自然語言記帳**：用對話方式記錄支出，如「午餐花了150元刷卡」。
- 🤖 **GPT 智慧解析**：自動識別品項、金額、付款方式、分類等資訊。
- 📊 **Notion 直接整合**：直連 Notion API，擺脫 Make.com 等第三方中介的配額限制與延遲，穩定性大幅提升。
- 🔒 **智慧會話鎖定**：支援「鎖定專案」、「鎖定付款」與「鎖定幣別」指令，搭配模糊匹配，連續記帳免重複輸入。
- 📑 **一鍵專案結算**：發送「結算」指令，系統自動依專案產生財務統計摘要，並生成專屬的 Notion 結算連結。
- 📱 **動態 Flex Menu**：精緻的 LINE Flex Message 介面，提供常用指令的快速操作按鈕。
- 💴 **增強型 OCR 辨識**：深度優化日文收據辨識，支援多行合併、總價自動偵測與品項語義修正。
- 🔄 **多重編輯修正**：在下一筆記帳開始前，可無限次修正上一筆記錄（支援修改幣別、匯率）。
- 🧪 **自動化測試體系**：整合 `./run_tests.sh` 確保系統邏輯與 Notion 寫入的準確性。

## ✅ 現況功能 (v3.0 Milestone)

- **Notion 原生對接**：完整支援 Notion Database 寫入，取代傳統 Webhook 模式（仍保留 Webhook 作為備援）。
- **會話狀態管理**：智慧記憶當前使用的專案與支付方式，大幅簡化旅遊或特定專案期間的記帳流程。
- **Parser-first 策略**：優先使用正則與邏輯解析 Authority Fields（金額、日期、時間、付款方式），GPT 僅負責語義 Enrichment。
- **時間與 ID 同步**：從文字或圖片中提取時間 (HH:MM)，交易 ID 格式統一為 `YYYYMMDD-HHMMSS`。
- **進階修正意圖**：支援「改幣別為日圓」、「匯率 0.22」等精確修正，自動查詢最新匯率。

## 🏗️ 技術架構

```
LINE Platform → Vercel Serverless Function → Parser → GPT → Notion API / Webhook
                       ↓
                   LINE Bot API (回覆使用者)
```

### 技術棧

- **Environment Management**: [uv](https://astral.sh/uv) (快速、可靠的 Python 套件管理)
- **Backend**: Python 3.11+
- **Framework**: Flask (Serverless)
- **Database**: Notion API (Primary Storage)
- **LINE SDK**: line-bot-sdk 3.8.0
- **OpenAI SDK**: openai >= 1.12.0
- **部署平台**: Vercel

## 🚀 快速開始

### 環境需求

- Python 3.11 或以上
- LINE Developer Account（[申請連結](https://developers.line.biz/)）
- OpenAI API Key（[取得連結](https://platform.openai.com/api-keys)）
- Notion Integration Token（[申請連結](https://www.notion.so/my-integrations)）

### 設定環境變數

複製 `.env.example` 為 `.env` 並填入您的金鑰：

```env
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_CHANNEL_SECRET=...

# OpenAI Configuration
OPENAI_API_KEY=...
GPT_MODEL=gpt-4o-mini

# Notion Configuration (v3.0+)
USE_NOTION_API=true
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=...

# Webhook Configuration (選用，備援用)
WEBHOOK_URL=...
```

### Notion 結算中心設定 (Settlement View)

為了完美搭配「結算」功能，建議在 Notion 資料庫中建立專屬視圖：

1.  **建立視圖**：新增一個 Table View，命名為 `💵 專案結算中心`。
2.  **新增公式欄位**：
    *   欄位名稱：`結算小計 (台幣)`
    *   公式內容：`round(prop("原幣金額") * prop("匯率") + prop("手續費"))`
3.  **設定群組 (Grouping)**：
    *   依「專案」進行分組。
    *   開啟「計算總和 (Sum)」於 `結算小計 (台幣)` 欄位，即可即時查看各專案總支出。
4.  **設定篩選 (Filtering)**：
    *   建議篩選「日期」為「本月」或特定旅遊區間。

## 📝 指令範例

> **重要**：LINE 指令需以 `/` 開頭（避免一般對話被誤判成指令）。

### LINE 常用指令
- `/功能` / `/選單`：開啟功能選單（Flex Menu）
- `/鎖定狀態`：查看目前鎖定（專案/付款/幣別/對帳）
- `/全部解鎖`：解除所有鎖定
- `/記帳教學`：查看記帳教學

### 信用卡對帳（台新）
1) `/鎖定對帳 台新 YYYY-MM`
2) 直接上傳帳單明細截圖（可多張）
3) `/執行對帳`
4) `/解除對帳`（完成後退出對帳模式）

> 對帳結果會寫回 Notion relation（matched/unmatched 以 Notion 為準）。

### 智慧鎖定 (Session Locks)
- `鎖定專案 日本旅遊`：後續記帳將自動歸類至「日本旅遊」。
- `鎖定付款 日圓現金`：後續記帳將自動設為「日圓現金」並套用匯率。
- `鎖定幣別 JPY`：強制使用日圓記帳。
- `解除鎖定`：清除所有目前的會話鎖定。

### 結算功能
- `結算`：系統會回傳目前活躍專案的支出統計與 Notion 連結。

### 記帳範例
- `今天 早餐$80現金`
- `幫同事墊付計程車費300元` (自動標記為代墊)
- `修正匯率 0.215` (針對最後一筆交易)

## 🛠️ 開發與貢獻

### 開發規範
本專案遵循嚴謹的開發原則與 AI 協作流程，詳細內容請參考：
👉 **[DEVELOPMENT_GUIDELINES.md](DEVELOPMENT_GUIDELINES.md)**

### 測試 (Testing)
```bash
# 執行全量測試
./run_tests.sh

# 執行本地互動式測試
python test_local.py
```

## 📚 相關文件
- [收據辨識指南](docs/RECEIPT_USAGE_GUIDE.md)
- [版本發布紀錄](docs/releases/)
- [功能規格書](specs/001-linebot-gpt-bookkeeper/spec.md)

---
**專案維護者**：lwindg
**最後更新**：2026-02-10 (v3.0 Milestone)
