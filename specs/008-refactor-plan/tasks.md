# 008 記帳重構任務清單（Parser-first + AI Enrichment）

> 依據 `specs/008-refactor-plan/plan.md`
> 基於現有 `app/` 模組結構優化

## 現有模組對應

| 現有模組 | 用途 | 重構策略 |
|---------|------|---------|
| `gpt_processor.py` | 主處理器（1149 行） | 抽取邏輯移至 Parser |
| `category_resolver.py` | 分類驗證（讀 `CLASSIFICATION_RULES`） | 改讀 YAML |
| `payment_resolver.py` | 付款方式正規化 | 改讀 YAML |
| `cashflow_rules.py` | 現金流規則 | 整合至 Parser |
| `schemas.py` | GPT Structured Output Schema | 擴充權威 JSON Schema |
| `prompts.py` | GPT System Prompts（764 行） | 瘦身至 <200 行 |

---

## Phase 0: Schema + Config 外部化

- [ ] T001 建立權威 JSON Schema（擴充 `app/schemas.py`）
  - 新增 `AUTHORITATIVE_ENVELOPE_SCHEMA`
  - 定義 version 相容策略（v1 → v1.1）
- [ ] T002 建立 AI Enrichment Schema（擴充 `app/schemas.py`）
  - 新增 `ENRICHMENT_RESPONSE_SCHEMA`
- [ ] T003 抽出分類清單到 `app/config/classifications.yaml`
  - 從 `prompts.py:CLASSIFICATION_RULES` 抽取 50+ 分類
- [ ] T004 抽出付款方式到 `app/config/payment_methods.yaml`
  - 從 `payment_resolver.py:_PAYMENT_ALIASES` 抽取 mapping
- [ ] T005a 更新 `app/category_resolver.py` 讀取 YAML
  - 移除對 `prompts.CLASSIFICATION_RULES` 的依賴
- [ ] T005b 更新 `app/payment_resolver.py` 讀取 YAML
  - 移除硬編碼 `_PAYMENT_ALIASES`

---

## Phase 1: Parser 核心模組

- [ ] T006 建立 Parser 模組骨架 `app/parser/__init__.py`
  - 定義 `parse(message: str) -> AuthoritativeEnvelope`
- [ ] T007 實作交易類型 enum `app/parser/types.py`
  - `TransactionType`: expense, advance_paid, advance_due, income, transfer, card_payment, withdrawal
- [ ] T008 實作金額/幣別抽取 `app/parser/extract_amount.py`
  - 複用 `gpt_processor._extract_first_amount()` 邏輯
  - 支援連寫格式（魚$395現金）
- [ ] T009 實作付款方式抽取 `app/parser/extract_payment.py`
  - 複用 `payment_resolver.detect_payment_method()` 邏輯
  - 載入 YAML mapping
- [ ] T010 實作日期解析 `app/parser/extract_date.py`
  - 複用 `gpt_processor._extract_semantic_date_token()` 與 `_extract_explicit_date()`
  - 接收 context（執行日期）
- [ ] T011 實作代墊狀態/對象抽取 `app/parser/extract_advance.py`
  - Pattern Matching 策略（不用 jieba）
  - 優先序：不索取 > 代墊 > 需支付 > 無
- [ ] T012 實作現金流辨識 `app/parser/extract_cashflow.py`
  - 複用 `gpt_processor._detect_cashflow_intent()` 與 `cashflow_rules`
  - 帳戶抽取整合 `cashflow_rules.infer_transfer_accounts()`
- [ ] T013 實作多項目切割 `app/parser/split_items.py`
  - 分隔符號：逗號、分號、頓號、換行
  - 處理複合品項（和/跟/與/加 不拆）
- [ ] T014 實作 Envelope 組裝 `app/parser/build_envelope.py`
  - 組合各模組輸出為 `AuthoritativeEnvelope`
- [ ] T015 定義 Parser error 類型 `app/parser/errors.py`
  - `MISSING_AMOUNT`, `MISSING_ITEM`, `INVALID_PAYMENT_METHOD`, `AMBIGUOUS_ADVANCE`
  - 統一錯誤訊息模板

---

## Phase 2: AI Enrichment Prompt

- [ ] T016 新增精簡 AI enrichment prompt `app/prompts_enrichment.py`
  - 目標 <200 行（vs 現有 764 行）
  - 移除抽取規則，保留分類/專案/必要性規則
- [ ] T017 製作 Parser → AI payload 轉換 `app/enrichment/prepare_payload.py`
  - `AuthoritativeEnvelope` → GPT messages
- [ ] T018 實作 AI enrichment 呼叫 `app/enrichment/client.py`
  - 呼叫 OpenAI API，解析 `EnrichmentResponse`

---

## Phase 3: Validator & Fallback

- [ ] T019 建立 enrichment validator `app/enrichment/validator.py`
  - 分類必須在 YAML 清單內
  - 必要性必須在 enum 內
- [ ] T020 實作 fallback 策略 `app/enrichment/fallbacks.py`
  - 分類不合法：回退上層（如 `餐飲類` → `家庭/餐飲`）
  - 必要性缺失：預設 `必要日常支出`
  - 專案缺失：依分類推斷或預設 `日常`
- [ ] T021 實作 AI 重試邏輯 `app/enrichment/retry.py`
  - 最多重試 1 次（可配置）

---

## Phase 4: Shadow Mode 驗證（移至路由切換前）

- [ ] T022 實作 shadow mode 比對器 `app/pipeline/shadow.py`
  - 同時執行舊路徑與新路徑
- [ ] T023 記錄比對指標（log/metrics）
  - Parser 成功率、AI 合法率、新舊一致率

---

## Phase 5: 路由切換

- [ ] T024 新增主流程 `app/pipeline/main.py`
  - Parser → AI Enrichment → Validator → 輸出
- [ ] T025 整合至 `app/gpt_processor.py`
  - 新增 `process_message_v2()` 入口
- [ ] T026 保留舊路徑為 fallback（config `USE_PARSER_FIRST`）
- [ ] T027 明確混合句型策略
  - 現金流僅支援單筆
  - 一般支出可多項目
  - 混合 → 回錯
- [ ] T028 新增 error 分類記錄
  - `parser_error` / `ai_error` / `validator_error`

---

## Phase 6: 測試與回歸

- [ ] T029 新增 Parser 單元測試 `tests/parser/`
  - `test_extract_amount.py`、`test_extract_advance.py`、`test_split_items.py`
- [ ] T030 新增 Enrichment contract 測試 `tests/enrichment/`
  - 固定權威 JSON → 驗證 AI 只回 enrichment
- [ ] T031 更新既有 functional suites
  - `tests/test_local.py` 支援新路徑
- [ ] T032 新增一致性測試
  - 同句 3 次輸出一致率 ≥ 95%

---

## 任務依賴圖

```
T001-T005b (Phase 0: Config)
     ↓
T006-T015 (Phase 1: Parser)
     ↓
T016-T018 (Phase 2: AI Prompt)
     ↓
T019-T021 (Phase 3: Validator)
     ↓
T022-T023 (Phase 4: Shadow Mode)
     ↓
T024-T028 (Phase 5: 路由切換)
     ↓
T029-T032 (Phase 6: 測試)
```

