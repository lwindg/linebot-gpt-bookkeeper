# Implementation Plan: v1.7 代墊與需支付功能

**Branch**: `002-advance-payment` | **Date**: 2025-11-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-advance-payment/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

本功能為 LINE Bot GPT Bookkeeper v1.7 版本，新增代墊支付管理能力：

**核心需求**：
- 使用者能記錄「代墊」支出（代他人支付，需日後收款）
- 使用者能記錄「需支付」項目（他人代墊，需償還對方）
- 使用者能記錄「不索取」代墊（代家人支付但不收回）
- 系統智慧識別自然語言中的代墊關鍵字和收款/支付對象
- 支援與現有多項目記帳功能整合（部分項目代墊，部分一般支出）

**技術方法**：
- 增強 GPT prompt 以識別代墊關鍵字（「代」、「幫」、對象+「代訂」等）
- 擴充資料模型新增「代墊狀態」和「收款／支付對象」欄位
- 付款方式預設規則：代墊項目保留實際方式，需支付項目預設「NA」
- 更新 webhook JSON schema 包含新欄位
- 調整 LINE 回覆訊息格式顯示代墊狀態和對象資訊

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- LINE Bot SDK 3.8.0（LINE Messaging API 整合）
- OpenAI SDK ≥1.12.0（GPT-4o 自然語言處理）
- Flask ≥3.0.0（Web 框架，Vercel 部署）
- Redis ≥5.0.0（Vercel KV，用於儲存最後一筆交易）
- Requests ≥2.31.0（Webhook HTTP 請求）

**Storage**:
- Vercel KV (Redis)（儲存最後一筆交易，支援「修改上一筆」功能）
- 外部 Make.com webhook（實際記帳資料儲存）

**Testing**: pytest ≥7.4.0, pytest-mock ≥3.12.0
**Target Platform**: Vercel Serverless Functions（部署環境）
**Project Type**: Single project（Serverless 單體架構）

**Performance Goals**:
- LINE webhook 回應時間 < 3 秒（LINE 平台限制）
- GPT API 回應時間 < 5 秒（使用者體驗目標）

**Constraints**:
- LINE webhook timeout: 3 秒內必須回應 200 OK
- GPT prompt token 限制：需精簡 prompt 以控制成本
- 代墊狀態識別準確率目標：≥ 90%（基於測試資料集）

**Scale/Scope**:
- 個人使用者專案（1 位主要使用者）
- 支援 6 種代墊狀態值（v1.7 支援 4 種：無、代墊、需支付、不索取）
- 整合至現有 v1.5.0 多項目記帳架構（~1500 LOC Python）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. MVP 優先開發 ✅

**符合**：本功能以最小可行產品方式實作
- ✅ v1.7 僅實作核心代墊功能（記錄代墊、需支付、不索取）
- ✅ 明確排除非核心功能（狀態更新、提醒追蹤、收據自動識別）
- ✅ 每個使用者故事可獨立測試和交付
- ✅ P1 功能優先（代墊、需支付），P2 延後（不索取）

### II. 透過測試確保品質 ✅

**符合**：測試策略務實且專注使用者場景
- ✅ 整合測試覆蓋完整使用者旅程（LINE 訊息 → GPT 識別 → Webhook → 確認回覆）
- ✅ 每個驗收場景都有對應測試案例
- ✅ 目標：90% 識別準確率（可測量的品質標準）

### III. 簡單勝過完美 ✅

**符合**：選擇最簡單可行方案
- ✅ 重用現有架構（v1.5.0 多項目記帳）
- ✅ 不新增抽象層或複雜模式
- ✅ 直接擴充 GPT prompt 和資料模型欄位
- ✅ 不引入新依賴或框架

### IV. 便利性和開發者體驗 ✅

**符合**：最小化開發摩擦
- ✅ 使用現有測試框架 pytest
- ✅ 重用現有 webhook 發送邏輯
- ✅ 清晰的錯誤訊息（缺少收款對象時提示使用者）

### V. 可用性和使用者價值 ✅

**符合**：優化終端使用者體驗
- ✅ 自然語言識別（使用者不需學習特殊語法）
- ✅ 友善錯誤處理（缺少資訊時明確提示）
- ✅ 清晰的確認訊息（顯示代墊狀態和對象）
- ✅ 解決真實痛點（追蹤代墊款項避免遺忘）

**檢查點結論**：✅ 通過所有憲章原則檢查，可進入 Phase 0 研究階段

---

## Phase 2: Constitution Re-check（設計完成後）

*執行時間*：2025-11-18（Phase 1 完成後）

### I. MVP 優先開發 ✅

**重新檢查**：設計階段是否維持 MVP 原則？
- ✅ research.md 拒絕過度工程方案（Function Calling API、獨立 enum 類別）
- ✅ data-model.md 重用現有欄位，無新增複雜度
- ✅ quickstart.md 預估 2-3 小時完成（符合快速交付）
- ✅ 無新增依賴或框架

**結論**：✅ 通過 MVP 原則複查

### II. 透過測試確保品質 ✅

**重新檢查**：測試策略是否務實？
- ✅ quickstart.md 定義 25 個測試案例（覆蓋所有驗收場景）
- ✅ 整合測試為主（端到端使用者旅程）
- ✅ 90% 準確率目標可測量

**結論**：✅ 通過測試品質複查

### III. 簡單勝過完美 ✅

**重新檢查**：設計是否保持簡單？
- ✅ 重用現有資料模型（無 schema 變更）
- ✅ 僅修改 5 個模組（prompts.py、gpt_processor.py、line_handler.py、webhook_sender.py、測試）
- ✅ 表格格式 prompt 控制 token 成本（+10% = 300 tokens）
- ✅ 無新增檔案、無新增依賴

**結論**：✅ 通過簡單性原則複查

### IV. 便利性和開發者體驗 ✅

**重新檢查**：開發流程是否便利？
- ✅ quickstart.md 提供清晰實作步驟
- ✅ 實作檢查清單幫助追蹤進度
- ✅ 常見問題排查指引
- ✅ 預估工時明確（2.5-3 小時）

**結論**：✅ 通過開發者體驗複查

### V. 可用性和使用者價值 ✅

**重新檢查**：使用者價值是否最大化？
- ✅ 自然語言識別（無需學習特殊語法）
- ✅ 清晰確認訊息（圖示區分代墊狀態）
- ✅ 友善錯誤處理（缺少對象時明確提示）
- ✅ 解決真實痛點（追蹤代墊款項）

**結論**：✅ 通過使用者價值複查

---

### Phase 2 最終檢查結論

✅ **所有憲章原則再次通過驗證**
✅ **設計階段無違反原則**
✅ **可進入 Phase 3：任務生成（/speckit.tasks）**

**Phase 1 (Planning) 完成**：plan.md、research.md、data-model.md、contracts/、quickstart.md 已生成

## Project Structure

### Documentation (this feature)

```text
specs/002-advance-payment/
├── spec.md              # 功能規格書（已存在）
├── plan.md              # 本文件（/speckit.plan 輸出）
├── research.md          # Phase 0 輸出（/speckit.plan 生成）
├── data-model.md        # Phase 1 輸出（/speckit.plan 生成）
├── quickstart.md        # Phase 1 輸出（/speckit.plan 生成）
├── contracts/           # Phase 1 輸出（/speckit.plan 生成）
│   └── advance-payment-webhook.json  # Webhook JSON Schema
└── tasks.md             # Phase 2 輸出（/speckit.tasks 生成，非 /speckit.plan）
```

### Source Code (repository root)

本專案為 **Single project** 架構（Serverless 單體）

```text
/
├── api/
│   └── webhook.py           # Vercel serverless endpoint（需修改：處理代墊資料）
├── app/
│   ├── config.py            # 配置（無需修改）
│   ├── gpt_processor.py     # [修改] 新增代墊狀態和對象欄位到 BookkeepingEntry
│   ├── prompts.py           # [修改] 增強 MULTI_EXPENSE_PROMPT 識別代墊關鍵字
│   ├── line_handler.py      # [修改] 更新確認訊息格式顯示代墊資訊
│   ├── webhook_sender.py    # [修改] Webhook payload 包含代墊欄位
│   ├── kv_store.py          # 無需修改（已支援儲存任意欄位）
│   └── image_handler.py     # 無需修改（v1.7 不支援收據識別代墊）
├── tests/
│   ├── test_integration.py       # [新增] v1.7 代墊整合測試
│   ├── test_gpt_processor.py     # [修改] 新增代墊識別測試案例
│   ├── test_webhook_sender.py    # [修改] 驗證代墊欄位 webhook
│   └── test_multi_expense.py     # [修改] 多項目含代墊測試
├── test_local.py            # [修改] 本地測試工具支援代墊顯示
└── requirements.txt         # 無需修改（無新依賴）
```

**Structure Decision**: 採用現有 Single project 架構，透過修改 5 個核心模組實作代墊功能，無需新增抽象層或重構專案結構。所有變更集中在 `app/` 和 `tests/` 目錄。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**無違反項目**：本功能完全符合憲章原則，無需複雜度理由說明。
