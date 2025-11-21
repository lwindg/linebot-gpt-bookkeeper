# Implementation Plan: 多幣別記帳功能

**Branch**: `003-multi-currency` | **Date**: 2025-11-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-multi-currency/spec.md`

## Summary

本功能擴充現有 LINE Bot 記帳系統，支援外幣消費記錄。使用者可透過 LINE 訊息輸入外幣金額（如「WSJ 4.99美元 大戶」），系統自動識別幣別、查詢台灣銀行匯率、換算新台幣金額並儲存完整記錄。

**技術方案**：採用 FinMind API 查詢匯率，搭配台灣銀行 CSV 作為備用，並預存常用幣別（USD、EUR、JPY）的備用匯率。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- OpenAI API (GPT-4，用於訊息解析)
- FinMind API (匯率查詢)
- requests (HTTP 請求)
- 現有依賴：linebot-sdk, flask

**Storage**: Vercel KV (現有，用於匯率快取和備用匯率儲存)
**Testing**: pytest (現有測試框架)
**Target Platform**: Vercel Serverless Functions (現有部署平台)
**Project Type**: single (單體應用，擴充現有系統)
**Performance Goals**:
- 外幣消費記錄處理時間 < 10 秒（從訊息到回覆）
- 匯率查詢回應時間 < 3 秒
- 幣別識別準確率 > 95%

**Constraints**:
- LINE webhook 回應時間 < 3 秒（平台限制）
- FinMind API 頻率限制：300 請求/小時（未認證）
- 必須相容現有資料結構和 webhook 格式

**Scale/Scope**:
- 支援 7 種常見幣別（USD、EUR、JPY、GBP、AUD、CAD、CNY）
- 預計 100 位活躍使用者
- 每日約 1000 筆外幣消費記錄

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. MVP 優先開發 ✅

- ✅ P1 功能（外幣消費記錄與自動換算）提供即時使用者價值
- ✅ 每個使用者故事可獨立測試和交付
- ✅ 延後 P2 功能（多筆外幣項目同時處理）直到 MVP 驗證
- ✅ 未包含推測性功能（查詢功能已明確標註為 Out of Scope）

### II. 透過測試確保品質 ✅

- ✅ 規劃整合測試：完整的外幣消費記錄流程（LINE 訊息 → GPT 解析 → 匯率查詢 → 儲存）
- ✅ 規劃契約測試：FinMind API 整合測試
- ✅ 單元測試：匯率查詢、幣別識別、降級機制

### III. 簡單勝過完美 ✅

- ✅ 直接使用 FinMind API，避免自建匯率服務
- ✅ 擴充現有 `BookkeepingEntry` 資料結構，而非建立新的抽象層
- ✅ 使用現有 `KVStore` 儲存匯率快取，而非引入 Redis
- ✅ 無過早優化：僅在需要時才實作批次查詢

### IV. 便利性和開發者體驗 ✅

- ✅ 清晰的錯誤訊息（對應 FR-008）
- ✅ 本地開發支援：FinMind API 無需認證即可測試
- ✅ 使用現有測試框架（pytest）

### V. 可用性和使用者價值 ✅

- ✅ 使用者體驗優先：自動識別幣別同義詞（「美金」→「USD」）
- ✅ 解決真實痛點：外幣消費需手動換算的問題
- ✅ 錯誤處理對使用者友善：提供明確的錯誤訊息和建議

### 複雜度理由

無需額外理由。本功能採用簡單直接的方案，符合憲章原則。

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-currency/
├── spec.md              # 功能規格（已完成）
├── plan.md              # 本檔案（實作規劃）
├── research.md          # Phase 0 研究報告（已完成）
├── data-model.md        # Phase 1 資料模型（下一步）
├── quickstart.md        # Phase 1 快速入門（下一步）
├── contracts/           # Phase 1 API 契約（下一步）
├── checklists/
│   └── requirements.md  # 規格品質檢查清單（已完成）
└── tasks.md             # Phase 2 任務清單（/speckit.tasks 產生）
```

### Source Code (repository root)

```text
app/                          # 主要應用程式碼
├── __init__.py
├── config.py                 # 配置設定
├── schemas.py                # 【修改】新增外幣欄位
├── prompts.py                # 【修改】更新 prompt 以識別幣別
├── gpt_processor.py          # 【修改】整合匯率查詢邏輯
├── line_handler.py           # LINE webhook 處理（無需修改）
├── webhook_sender.py         # 【修改】支援外幣欄位
├── kv_store.py               # KV 儲存（用於匯率快取）
├── image_handler.py          # 圖片處理（無需修改）
└── exchange_rate.py          # 【新增】匯率查詢服務

tests/                        # 測試程式碼
├── test_exchange_rate.py     # 【新增】匯率服務單元測試
├── test_multi_currency.py    # 【新增】多幣別整合測試
├── test_gpt_processor.py     # 【修改】新增外幣解析測試
├── test_webhook_sender.py    # 【修改】新增外幣欄位測試
└── test_webhook_batch.py     # 現有批次測試

api/
└── webhook.py                # Vercel webhook 端點（無需修改）
```

**Structure Decision**: 採用單體應用架構（Option 1: Single project），擴充現有模組。新增 `exchange_rate.py` 模組負責匯率查詢，修改現有模組以支援外幣欄位。

### 檔案修改清單

**新增檔案**：
- `app/exchange_rate.py`：匯率查詢服務
- `tests/test_exchange_rate.py`：匯率服務測試
- `tests/test_multi_currency.py`：端對端整合測試

**修改檔案**：
- `app/schemas.py`：在 `MULTI_BOOKKEEPING_SCHEMA` 中新增 `原幣別`、`匯率` 欄位
- `app/prompts.py`：新增幣別識別指令
- `app/gpt_processor.py`：整合匯率查詢，擴充 `BookkeepingEntry`
- `app/webhook_sender.py`：確保外幣欄位正確傳送至 Make.com
- `tests/test_gpt_processor.py`：新增外幣解析測試案例
- `tests/test_webhook_sender.py`：新增外幣欄位測試案例

## Complexity Tracking

**無違反憲章原則**，無需填寫此表格。
