# Implementation Plan: 修改上一次交易記錄

**Branch**: `001-edit-last-transaction` | **Date**: 2025-11-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-edit-last-transaction/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

使用者可透過 LINE Bot 文字指令快速修改最近一筆交易記錄的品項、分類、專案或金額，無需手動搜尋交易 ID。系統在修改操作開始時鎖定目標交易，確保併發情況下的資料一致性。採用 Vercel KV (Redis) 作為暫存層，直接修改儲存在 KV 中的最新交易資料。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Flask 3.0+, line-bot-sdk 3.8.0, redis 5.0+, openai 1.12+
**Storage**: Vercel KV (Redis) - 現有架構已使用，TTL 為 1 小時
**Testing**: pytest 7.4+（整合測試優先，覆蓋 LINE 訊息流程）
**Target Platform**: Vercel Serverless Functions（Python runtime）
**Project Type**: Single (LINE Bot backend，無前端）
**Performance Goals**: LINE webhook 回應 < 3 秒（平台限制），修改操作 < 1 秒（SC-002）
**Constraints**:
- Vercel KV 的 TTL 限制（1 小時），不保留歷史記錄
- LINE Bot 對話式介面，文字指令為主
- 無狀態設計，每次請求獨立處理
**Scale/Scope**: 單使用者場景（透過 LINE user ID 隔離），預期 < 100 筆/小時交易量

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ MVP 優先開發
- **符合**: P1 優先實作品項修改（最常用功能），P2-P4 可獨立迭代
- **符合**: 直接修改 KV 儲存的最新交易，無需引入額外持久化層
- **符合**: 不實作歷史記錄功能（非核心需求，且受 KV TTL 限制）

### ✅ 透過測試確保品質
- **符合**: 計畫撰寫整合測試覆蓋 LINE 訊息 → GPT → 修改操作 → 回應流程
- **符合**: 無需單元測試（業務邏輯簡單，直接測試端到端旅程即可）

### ✅ 簡單勝過完美
- **符合**: 重用現有 `KVStore` 類別，不引入新的抽象層
- **符合**: 直接在 `line_handler.py` 新增指令處理邏輯，不建立新模組
- **符合**: 不使用 Repository 模式或 ORM（直接操作 Redis JSON 資料）

### ✅ 便利性和開發者體驗
- **符合**: 重用現有的 GPT prompts 和指令解析邏輯
- **符合**: 錯誤訊息清晰（如「無可修改的交易記錄」）
- **符合**: 本地測試可透過 `test_local.py` 快速驗證

### ✅ 可用性和使用者價值
- **符合**: 文字指令介面符合現有 LINE Bot 使用習慣
- **符合**: SC-001（10 秒內完成）和 SC-002（1 秒回應）確保良好 UX
- **符合**: 錯誤處理對使用者友善（中文提示訊息）

### 無違反項目
- 不引入新框架、函式庫或複雜模式
- 不增加專案複雜度
- 符合所有憲章原則

## Project Structure

### Documentation (this feature)

```text
specs/001-edit-last-transaction/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
app/
├── __init__.py
├── config.py              # Environment variables and settings
├── kv_store.py            # Existing KV wrapper (reuse)
├── line_handler.py        # 修改：新增修改指令處理邏輯
├── gpt_processor.py       # 修改：新增 GPT 提示詞支援修改指令
├── prompts.py             # 修改：新增修改交易的 prompts
├── webhook_sender.py      # 現有：重用以推送交易到 FinMind
└── schemas.py             # 現有：交易資料結構定義

tests/
├── integration/
│   └── test_edit_last_transaction.py  # 新增：整合測試
└── test_local.py          # 現有：本地測試腳本（擴充）

api/
└── webhook.py             # 現有：Vercel 進入點（無需修改）
```

**Structure Decision**:
採用現有的單一專案結構（Option 1: Single project）。本功能為現有 LINE Bot 的功能擴充，不需要獨立模組或微服務。所有變更集中在 `app/` 目錄，主要修改 `line_handler.py`（指令路由）、`gpt_processor.py`（GPT 互動）和 `prompts.py`（提示詞模板）。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

無違反項目，無需填寫。
