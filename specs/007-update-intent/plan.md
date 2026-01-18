# Implementation Plan: Update Intent Prompt Split

**Branch**: `007-update-intent` | **Date**: 2026-01-19 | **Spec**: specs/007-update-intent/spec.md
**Input**: Feature specification from `/specs/007-update-intent/spec.md`
**Language**: 本文件內容以正體中文撰寫，程式碼/識別符/指令維持英文

## Summary

針對「修改上一筆」的語句建立獨立更新意圖流程與規則，確保更新辨識穩定、
付款方式輸出統一為標準名稱，且僅允許單欄位更新。

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Flask, OpenAI SDK, LINE Messaging API SDK  
**Storage**: SQLite（主要資料）、Vercel KV（最後一筆交易暫存）  
**Testing**: pytest（整合測試為主，單元測試視需要）  
**Target Platform**: Linux server（LINE webhook 服務）
**Project Type**: 單一後端服務（LINE bot）  
**Performance Goals**: LINE webhook 回應 < 3 秒  
**Constraints**: 不新增不必要抽象；維持 prompt 精簡；錯誤訊息清楚一致  
**Scale/Scope**: 個人記帳使用情境，低流量、單使用者為主

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- MVP 優先：P1 更新語句辨識可獨立交付，P2/P3 延後至 MVP 驗證
- 測試品質：更新語句需具備整合測試；無外部 API 新增契約測試
- 簡單性：不新增框架與不必要抽象，維持最小分流規則
- 開發者體驗：錯誤訊息一致、可快速定位
- 使用者價值：更新成功率提升，減少誤判與回錯誤
- 文件語言：規格/規劃/任務以正體中文撰寫，程式碼產物以英文

## Phase 0: Outline & Research

- 已完成 research.md，聚焦更新意圖分流規則、付款方式正規化與單欄位限制
- 無新增外部整合或風險性依賴

## Phase 1: Design & Contracts

- 已完成 data-model.md（更新意圖與欄位集合）
- 已完成 contracts/update-intent.schema.json（更新意圖輸出格式）
- 已完成 quickstart.md（主要情境與錯誤案例）
- 已更新 agent context（AGENTS.md）
- 任務將包含主記帳 prompt 瘦身（移除 update 相關規則與範例）

## Project Structure

### Documentation (this feature)

```text
specs/007-update-intent/
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
├── gpt_processor.py
├── prompts.py
├── payment_resolver.py
├── line_handler.py
└── ...

tests/
├── unit/
├── integration/
└── functional/
```

**Structure Decision**: 使用既有單一後端結構（app/ + tests/）。

## Complexity Tracking

> 無需新增複雜度，維持最小分流與 prompt 拆分。

## Constitution Check (Post-Design)

- MVP 優先：P1 可獨立交付 ✅
- 測試品質：Quickstart 覆蓋主要更新情境 ✅
- 簡單性：無新增框架與抽象 ✅
- 開發者體驗：規則清楚、錯誤訊息一致 ✅
- 使用者價值：降低更新誤判與失敗率 ✅
- 文件語言：符合憲章 ✅
