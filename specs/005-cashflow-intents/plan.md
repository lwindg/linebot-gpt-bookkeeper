# Implementation Plan: Cashflow Intents MVP

**Branch**: `005-cashflow-intents` | **Date**: 2026-01-09 | **Spec**: specs/005-cashflow-intents/spec.md
**Input**: Feature specification from `/specs/005-cashflow-intents/spec.md`
**Language**: 本文件內容以正體中文撰寫，程式碼/識別符/指令維持英文

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

目標是新增現金流意圖（withdrawal/transfer/income/card_payment）與記錄規則，
確保提款、帳戶間轉帳能生成雙筆資金流向，而對他人轉帳僅記單筆支出。
驗證方式以 `python test_local.py` 為主，涵蓋：
「合庫轉帳給媽媽 2000」、「合庫轉帳到富邦 2000」、「合庫繳卡費到富邦 1500」。

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Flask, OpenAI SDK, LINE Messaging API SDK  
**Storage**: SQLite（主要資料）、Vercel KV（最後一筆交易暫存）  
**Testing**: pytest  
**Target Platform**: Vercel Serverless (LINE webhook)  
**Project Type**: single (API + app modules)  
**Performance Goals**: LINE webhook 回應時間 ≤ 3 秒  
**Constraints**: 不新增替代框架；維持現有結構與命名規範；延續既有錯誤處理與日誌  
**Scale/Scope**: 單一機器人、低至中等流量，重視正確性與一致性

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- MVP 優先：P1 使用者故事可獨立交付，P2/P3 延後至 MVP 驗證
- 測試品質：每個使用者旅程具備整合測試；外部 API 有契約測試
- 簡單性：新增抽象/框架需在 Complexity Tracking 說明當前需求
- 開發者體驗：本地設定最少化；錯誤/日誌可快速除錯
- 使用者價值：需求對應真實痛點與可用性目標
- 文件語言：規格/規劃/任務以正體中文撰寫，程式碼產物以英文

## Project Structure

### Documentation (this feature)

```text
specs/005-cashflow-intents/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
api/
└── webhook.py

app/
├── gpt_processor.py
├── line_handler.py
├── prompts.py
├── schemas.py
└── webhook_sender.py

tests/
├── functional/
├── unit/
└── ...
```

**Structure Decision**: 使用既有單一專案結構，擴充 app/ 模組與 tests/ 測試套件。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
