---

description: "Task list for Update Intent Prompt Split"
---

# Tasks: Update Intent Prompt Split

**Input**: Design documents from `/specs/007-update-intent/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/
**Language**: 本文件內容以正體中文撰寫，程式碼/識別符/任務路徑維持英文

**Tests**: 每個使用者旅程**必須**包含整合測試；外部 API 互動**必須**包含契約測試。
單元測試為選用，僅在複雜邏輯需要隔離時加入。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 對齊規格與測試基礎

- [x] T001 Align update-intent test data layout in tests/functional/suites/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 更新意圖分流的共用基礎

- [x] T002 Define update intent contract checks using specs/007-update-intent/contracts/update-intent.schema.json
- [x] T003 Add shared update intent fixtures in tests/functional/fixtures/update_intent.json

---

## Phase 3: User Story 1 - 更新語句穩定辨識 (Priority: P1) 🎯 MVP

**Goal**: 明確欄位與更新語意的輸入可穩定輸出 update_last_entry

**Independent Test**: 以 `test_local.py` 與 functional suite 驗證單欄位更新輸出

### Tests for User Story 1 (REQUIRED) ⚠️

- [x] T004 [P] [US1] Add contract tests for update intent in tests/contract/test_update_intent.py
- [x] T005 [P] [US1] Add integration tests for update messages in tests/functional/suites/update_intent.jsonl

### Implementation for User Story 1

- [x] T006 [US1] Add update intent prompt split in app/prompts.py
- [x] T007 [US1] Implement update intent routing in app/gpt_processor.py
- [x] T008 [US1] Ensure update outputs normalize payment methods via app/payment_resolver.py
- [x] T009 [US1] Update update_last_entry examples in app/prompts.py to cover dog card variants
- [x] T010 [US1] Prune update-related rules/examples from main bookkeeping prompt in app/prompts.py

---

## Phase 4: User Story 2 - 更新語句允許指向詞 (Priority: P2)

**Goal**: 支援上一筆/前一筆/最後一筆/剛剛/剛才等指向詞

**Independent Test**: functional suite 覆蓋 5 種指向詞

### Tests for User Story 2 (REQUIRED) ⚠️

- [x] T011 [P] [US2] Extend update intent suite for pointer terms in tests/functional/suites/update_intent.jsonl

### Implementation for User Story 2

- [x] T012 [US2] Add pointer-term rules to update intent prompt in app/prompts.py

---

## Phase 5: User Story 3 - 更新錯誤訊息一致 (Priority: P3)

**Goal**: 缺少欄位或新值時回傳一致錯誤

**Independent Test**: functional suite 覆蓋缺欄位/負數金額/多欄位更新

### Tests for User Story 3 (REQUIRED) ⚠️

- [x] T013 [P] [US3] Add error cases to update intent suite in tests/functional/suites/update_intent.jsonl

### Implementation for User Story 3

- [x] T014 [US3] Standardize update error messages in app/prompts.py
- [x] T015 [US3] Enforce single-field update rule in app/gpt_processor.py

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T016 [P] Sync quickstart examples with update intent prompt in specs/007-update-intent/quickstart.md
- [ ] T017 Run quickstart checks referenced in specs/007-update-intent/quickstart.md

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)** → **US1 (Phase 3)** → **US2 (Phase 4)** → **US3 (Phase 5)** → **Polish (Phase 6)**

## Parallel Example: User Story 1

```bash
Task: "Add contract tests for update intent in tests/contract/test_update_intent.py"
Task: "Add integration tests for update messages in tests/functional/suites/update_intent.jsonl"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 + Phase 2
2. 完成 US1 測試 → US1 實作
3. 獨立驗證更新語句輸出

### Incremental Delivery

1. 加入 US2 指向詞
2. 加入 US3 錯誤一致性
3. 更新 quickstart 驗證
