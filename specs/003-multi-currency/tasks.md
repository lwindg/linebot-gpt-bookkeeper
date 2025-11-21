# Tasks: 多幣別記帳功能

**Input**: Design documents from `/specs/003-multi-currency/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 確認開發環境就緒，無需新增依賴套件

- [x] T001 確認 Python 3.11+ 環境和 uv 套件管理工具可用
- [x] T002 確認現有依賴套件已安裝（requests, openai, linebot-sdk, flask, pytest）
- [x] T003 確認 Vercel KV 環境變數已設定（KV_REST_API_URL, KV_REST_API_TOKEN）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 建立匯率查詢服務和更新資料結構，MUST 在任何 User Story 實作前完成

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 [P] 在 app/schemas.py 的 MULTI_BOOKKEEPING_SCHEMA 中新增「原幣別」欄位（type: string, enum: ["TWD", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CNY"]）
- [x] T005 [P] 在 app/gpt_processor.py 的 BookkeepingEntry 資料類別中新增「原幣別」欄位（Optional[str], default="TWD"）和「匯率」欄位（Optional[float], default=1.0）
- [x] T006 建立 app/exchange_rate.py 並實作 ExchangeRateService 類別骨架（包含 __init__, CURRENCY_SYNONYMS, BACKUP_RATES 常數定義）
- [x] T007 在 app/exchange_rate.py 實作 normalize_currency() 方法（將幣別文字轉換為 ISO 4217 代碼）
- [x] T008 在 app/exchange_rate.py 實作 get_rate_from_finmind() 方法（呼叫 FinMind API 查詢匯率，包含錯誤處理和重試機制）
- [x] T009 在 app/exchange_rate.py 實作 get_rate_from_csv() 方法（作為備用方案，從台灣銀行 CSV 解析匯率）
- [x] T010 在 app/exchange_rate.py 實作 get_rate() 方法（整合快取、FinMind API、CSV 和備用匯率的降級機制）
- [x] T011 在 app/exchange_rate.py 實作 convert_to_twd() 方法（外幣金額換算為新台幣）
- [x] T012 在 app/exchange_rate.py 實作匯率快取機制（使用 KVStore，key 格式: exchange_rate:{currency}:{date}，TTL 3600 秒）
- [x] T013 [P] 在 app/prompts.py 新增幣別識別指令（CURRENCY_DETECTION 常數，定義支援的幣別關鍵字對照）
- [x] T014 在 app/prompts.py 將 CURRENCY_DETECTION 整合至 MULTI_EXPENSE_PROMPT

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 外幣消費記錄與自動換算 (Priority: P1) 🎯 MVP

**Goal**: 使用者可透過 LINE 訊息輸入單筆外幣消費（如「WSJ 4.99美元 大戶」），系統自動識別幣別、查詢匯率並儲存完整記錄

**Independent Test**: 發送「WSJ 4.99美元 大戶」至 LINE Bot，驗證回覆訊息包含匯率和新台幣金額，且資料正確儲存至 Google Sheets

### Implementation for User Story 1

- [x] T015 [US1] 在 app/gpt_processor.py 的 process_multi_expense() 函式中整合 ExchangeRateService（初始化服務實例）
- [x] T016 [US1] 在 app/gpt_processor.py 的 process_multi_expense() 函式中新增外幣處理邏輯（當 原幣別 != "TWD" 時查詢匯率並設定 匯率 欄位）
- [x] T017 [US1] 在 app/gpt_processor.py 中新增匯率查詢失敗的錯誤處理（記錄日誌並向使用者回傳友善錯誤訊息）
- [x] T018 [US1] 在 app/webhook_sender.py 的 send_to_webhook() 函式中確保「原幣別」和「匯率」欄位正確傳送至 Make.com webhook
- [x] T019 [US1] 在 app/line_handler.py 中更新回覆訊息格式（當為外幣消費時，顯示原幣金額、匯率和新台幣金額）
- [x] T020 [US1] 建立 tests/test_exchange_rate.py 並實作幣別同義詞轉換測試（測試 normalize_currency 方法）
- [x] T021 [P] [US1] 在 tests/test_exchange_rate.py 實作 FinMind API 查詢測試（使用 mock 測試成功和失敗情境）
- [x] T022 [P] [US1] 在 tests/test_exchange_rate.py 實作快取機制測試（驗證快取命中和未命中情境）
- [x] T023 [P] [US1] 在 tests/test_exchange_rate.py 實作降級機制測試（測試 API 失敗時切換至 CSV 和備用匯率）
- [x] T024 [US1] 在 tests/test_gpt_processor.py 新增外幣消費解析測試案例（測試「WSJ 4.99美元 大戶」識別為 USD, 4.99）
- [x] T025 [P] [US1] 在 tests/test_gpt_processor.py 新增幣別同義詞測試案例（測試「10美金」識別為 USD, 10）
- [x] T026 [P] [US1] 在 tests/test_gpt_processor.py 新增歐元消費測試案例（測試「290.97歐元」識別為 EUR, 290.97）
- [ ] T027 [US1] 建立 tests/test_multi_currency.py 並實作單筆外幣消費端對端整合測試（測試完整流程：訊息解析 → 匯率查詢 → webhook 發送）
- [ ] T028 [US1] 在 test_local.py 新增外幣消費手動測試案例（用於本地開發驗證）
- [ ] T029 [US1] 執行所有 User Story 1 相關測試並確保通過（uv run pytest tests/test_exchange_rate.py tests/test_gpt_processor.py tests/test_multi_currency.py -v）

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 多筆外幣項目同時處理 (Priority: P2)

**Goal**: 使用者可在單一訊息中輸入多筆外幣消費（如「WSJ 4.99美元 大戶\nNetflix 10歐元 大戶」），系統分別查詢匯率並儲存

**Independent Test**: 發送包含多筆不同幣別消費的訊息至 LINE Bot，驗證每筆記錄都有正確的匯率和新台幣金額

### Implementation for User Story 2

- [ ] T030 [US2] 在 app/gpt_processor.py 的 process_multi_expense() 函式中實作批次匯率查詢優化（收集所有需要查詢的幣別，去重後批次查詢）
- [ ] T031 [US2] 在 app/exchange_rate.py 新增 get_rates_batch() 方法（批次查詢多種幣別的匯率，減少 API 呼叫次數）
- [ ] T032 [US2] 在 app/gpt_processor.py 中處理混合新台幣和外幣消費的情境（確保新台幣消費不觸發匯率查詢）
- [ ] T033 [US2] 在 tests/test_multi_currency.py 新增多筆外幣消費整合測試（測試「WSJ 4.99美元 大戶\nOpenAI API Key 10美金 大戶」）
- [ ] T034 [P] [US2] 在 tests/test_multi_currency.py 新增混合新台幣和外幣消費測試（測試「便當 80 現金\nWSJ 4.99美元 大戶」）
- [ ] T035 [P] [US2] 在 tests/test_multi_currency.py 新增不同幣別多筆消費測試（測試「WSJ 4.99美元 大戶\nNetflix 10歐元 大戶」）
- [ ] T036 [US2] 在 tests/test_exchange_rate.py 新增批次查詢測試（測試 get_rates_batch 方法）
- [ ] T037 [US2] 執行所有 User Story 2 相關測試並確保通過（uv run pytest tests/test_multi_currency.py::test_multi_item_foreign_currency -v）

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: 改善程式碼品質、錯誤處理和監控

- [ ] T038 [P] 在 app/exchange_rate.py 新增詳細日誌記錄（記錄 API 呼叫、快取命中率、降級觸發等關鍵事件）
- [ ] T039 [P] 在 app/gpt_processor.py 新增外幣處理相關日誌（記錄幣別識別、匯率查詢結果）
- [ ] T040 實作預存備用匯率更新機制（在 app/exchange_rate.py 新增 update_backup_rates() 方法，可手動或定期更新 USD, EUR, JPY 備用匯率）
- [ ] T041 [P] 在 tests/test_webhook_sender.py 新增外幣欄位測試案例（確保 原幣別 和 匯率 正確傳送至 webhook）
- [ ] T042 [P] 更新 README.md 或建立 docs/multi-currency.md 說明多幣別功能使用方式（包含支援幣別、範例訊息格式）
- [ ] T043 執行 quickstart.md 中的驗證清單（確認所有功能驗證、錯誤處理驗證項目通過）
- [ ] T044 執行完整測試套件並確保所有測試通過（uv run pytest tests/ -v）
- [ ] T045 程式碼審查和重構（檢查程式碼品質、移除重複程式碼、確保符合專案憲章原則）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2)
- **Polish (Phase 5)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories ✅ INDEPENDENT
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 but can be tested independently ✅ INDEPENDENT

### Within Each User Story

- Implementation tasks before test execution
- Core logic before edge cases
- Unit tests can run in parallel (marked [P])
- Integration tests run after unit tests pass
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: All tasks can run sequentially (quick verification)
- **Phase 2**: T004, T005 can run in parallel; T013 can run in parallel with T006-T012
- **Phase 3 (US1)**:
  - T020, T021, T022, T023 (unit tests) can run in parallel
  - T025, T026 can run in parallel
- **Phase 4 (US2)**:
  - T034, T035 can run in parallel
- **Phase 5**: T038, T039, T041, T042 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all unit tests for exchange_rate.py together:
Task: "在 tests/test_exchange_rate.py 實作 FinMind API 查詢測試"
Task: "在 tests/test_exchange_rate.py 實作快取機制測試"
Task: "在 tests/test_exchange_rate.py 實作降級機制測試"

# Launch all GPT processor tests together:
Task: "在 tests/test_gpt_processor.py 新增幣別同義詞測試案例"
Task: "在 tests/test_gpt_processor.py 新增歐元消費測試案例"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T014) - CRITICAL
3. Complete Phase 3: User Story 1 (T015-T029)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (T001-T014)
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!) (T015-T029)
3. Add User Story 2 → Test independently → Deploy/Demo (T030-T037)
4. Polish & Optimize → Final release (T038-T045)
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T014)
2. Once Foundational is done:
   - Developer A: User Story 1 (T015-T029)
   - Developer B: User Story 2 (T030-T037) - can start in parallel if US1 foundation is solid
3. Stories complete and integrate independently

---

## Task Summary

### Total Tasks: 45

**Phase 1 (Setup)**: 3 tasks
**Phase 2 (Foundational)**: 11 tasks (CRITICAL - blocks all user stories)
**Phase 3 (User Story 1 - MVP)**: 15 tasks
**Phase 4 (User Story 2)**: 8 tasks
**Phase 5 (Polish)**: 8 tasks

### Tasks per User Story

- **User Story 1 (P1)**: 15 implementation + test tasks
- **User Story 2 (P2)**: 8 implementation + test tasks

### Parallel Opportunities Identified

- **10 tasks** marked [P] can run in parallel within their phase
- **2 user stories** can be developed in parallel after Foundational phase
- **Unit tests** within each story can run concurrently

### Independent Test Criteria

**User Story 1**:
- ✅ 發送「WSJ 4.99美元 大戶」
- ✅ 驗證回覆包含：原幣金額 4.99、匯率（如 31.5）、新台幣金額（如 157.19）
- ✅ 驗證資料正確儲存至 Google Sheets

**User Story 2**:
- ✅ 發送「WSJ 4.99美元 大戶\nNetflix 10歐元 大戶」
- ✅ 驗證兩筆記錄分別有正確匯率
- ✅ 驗證兩筆記錄正確儲存

### Suggested MVP Scope

**MVP = User Story 1 Only** (外幣消費記錄與自動換算)

包含：
- 幣別識別（USD, EUR, JPY, GBP, AUD, CAD, CNY）
- 匯率查詢（FinMind API + CSV 備用 + 預存備用匯率）
- 匯率快取（1 小時 TTL）
- 新台幣換算
- 完整測試覆蓋

**User Story 2 可在 MVP 驗證後新增**，不影響 MVP 功能。

---

## Format Validation

✅ **All tasks follow the checklist format**:
- ✅ Checkbox prefix: `- [ ]`
- ✅ Task ID: T001-T045 (sequential)
- ✅ [P] marker: 10 tasks marked as parallelizable
- ✅ [Story] label: All user story tasks labeled (US1, US2)
- ✅ File paths: Included in all implementation tasks
- ✅ Clear descriptions: Action-oriented with specific deliverables

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Tests are included as this is a critical feature requiring quality assurance
- MVP focuses on User Story 1 for fastest time-to-value
