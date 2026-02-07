# 開發與部署指導原則 (Development & Deployment Guidelines)

本文件紀錄了 Nenya 與小精靈（Agent）協作開發 `linebot-gpt-bookkeeper` 專案時所遵循的核心原則，旨在確保開發效率、代碼品質與環境穩定。

## 1. 開發環境與工具 (Tooling)

- **環境管理**：統一使用 `uv` 管理 Python 虛擬環境與依賴項目。執行指令應優先使用 `uv run`。
- **子代理協作**：粗重或涉及大量邏輯編寫的開發工作，優先委派給 `Codex` (openai-codex/gpt-5.2-codex) 執行，以節省主 Agent 額度並確保代碼精準。
- **測試優先**：
    - 在部署前必須執行 `./run_tests.sh` 進行 smoke test 或全量測試。
    - 腳本應支援自動偵測 `uv` 環境，避免硬編碼 `python` 指令（因系統環境多為 `python3`）。

## 2. 代碼架構原則 (Architecture)

- **Parser-First 策略**：優先嘗試使用 Regex/邏輯解析器 (`app/parser/`) 提取權威欄位（如金額、日期、時間、付款方式），僅將模糊描述與分類委託給 GPT 進行 Enrichment。
- **權威欄位不可侵犯**：經由 Parser 解析出的欄位（Authority Fields），AI 不得隨意修改，以確保數據一致性。
- **模組化與解耦**：
    - 避免循環引用（Circular Imports），將共用邏輯（如 `generate_transaction_id`）抽離至獨立的 pipeline 或 shared 模組。
    - 區分 `GPT-first` 與 `Parser-first` 路徑，並保留 `Shadow Mode` 用於比對驗證。

## 3. 記帳邏輯特化 (Bookkeeping Logic)

- **幣別優先權**：當同時出現 `$` 符號與具體幣別後綴（如 `日圓`）時，應優先採納具體幣別。
- **時間同步**：
    - 盡可能從訊息或收據圖片中提取 HH:MM 時間。
    - 交易 ID (Transaction ID) 必須與提取的時間同步（格式：`YYYYMMDD-HHMMSS`），而非使用系統處理時間。
- **付款方式清理**：在提取付款方式（如「日圓現金」）後，應確保品項名稱中的殘留關鍵字（如單獨的「現金」）被完全清理，避免品項名稱污染。
- **多重編輯支援**：KV 存儲應保留最後一筆交易記錄，直到新的記帳行為開始，以支援同一筆項目的多次修改（Task 3 支援修改原幣與匯率）。

## 4. Git 流程 (Git Workflow)

- **分支管理**：在特定的 Task 分支（如 `100-try-with-claw-dev`）進行開發。
- **小步快跑**：每個獨立任務（Task）完成並通過測試後，立即進行 Commit。
- **Push 與權限**：
    - 使用 GitHub CLI (`gh`) 配合適當權限的 PAT (Contents: Write, Pull Requests: Write) 進行遠端同步。
    - 優先使用 HTTPS 協議配合 `gh auth setup-git` 以簡化 Agent 操作。

## 5. 部署原則 (Deployment)

- **一鍵部署**：利用 Vercel Token 實現自動化部署。指令統一為 `npx vercel --prod --token $VERCEL_TOKEN --yes`。
- **部署前檢查**：確保所有 Commit 已推送到 GitHub 分支後，再執行 Vercel 部署。
- **環境變數同步**：若有新的配置項，需同步更新 Vercel 上的 Environment Variables。

---
_最後更新日期：2026-02-07_
