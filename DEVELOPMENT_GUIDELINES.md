# 開發與部署指導原則 (Development & Deployment Guidelines)

本文件紀錄了 Nenya 與小精靈（Agent）協作開發 `linebot-gpt-bookkeeper` 專案時所遵循的核心原則，旨在確保開發效率、代碼品質與環境穩定。

## 1. 開發環境與工具 (Tooling)

- **環境管理**：統一使用 `uv` 管理 Python 虛擬環境與依賴項目。執行指令應優先使用 `uv run`。
- **子代理協作**：粗重或涉及大量邏輯編寫的開發工作，優先委派給高階大腦（如 `claude-opus-4.6-thinking` 或 `Codex`）執行，以節省主 Agent 額度並確保代碼精準。
- **額度管理策略**：開發專用模型（目前為 Opus 與 Codex）在額度使用剩餘 **20%** 或以下時，必須立即暫停並回報，切換至下一個可用的開發模型，以確保開發連續性。
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
- **付款方式清理**：在提取付款方式（如「日圓現金」）後，應確保品項名稱中的殘留關鍵字（如單獨的「現金」）被完全清理。
- **多重編輯支援**：KV 存儲應保留最後一筆交易記錄，直到新的記帳行為開始，以支援同一筆項目的多次修改。
- **結算計算對齊 (v3.0)**：專案結算時，每筆項目必須先獨立進行四捨五入至整數（含手續費計算），再進行總額加總，以確保 LINE 回報與 Notion 視圖數據完全對齊。

## 4. Git 流程 (Git Workflow)

- **分支管理**：在特定的 Task 分支進行開發，完成後經測試才合併至 `main`。
- **小步快跑**：每個獨立任務（Task）完成並通過測試後，立即進行 Commit。
- **謹慎標記 (Tagging Policy)**：嚴禁在驗證完成前急於打上 Release Tag。必須先完成 Vercel 部署並經過實測確認「功能完全正確」後，方可執行 Git Tag (如 `v3.0.0`)。
- **Push 與權限**：使用 GitHub CLI (`gh`) 配合適當權限的 PAT 進行遠端同步。

## 5. 部署原則 (Deployment)

- **一鍵部署**：利用 Vercel Token 實現自動化部署。指令統一為 `npx vercel --prod --token $VERCEL_TOKEN --yes`。
- **部署後驗證**：部署完成後應立即針對關鍵路徑進行實測，若有異常需立即 Rollback 或修正。
- **環境變數同步**：若有新的配置項，需同步更新 Vercel 上的 Environment Variables（如 `NOTION_TOKEN`）。

---
_最後更新日期：2026-02-10 (v3.0 Milestone)_
