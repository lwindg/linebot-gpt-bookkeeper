---

description: "Task list template for feature implementation"
---

# Tasks: Cashflow Intents MVP

**Input**: Design documents from `/specs/005-cashflow-intents/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: 每個使用者旅程**必須**包含整合測試；外部 API 互動**必須**包含契約測試。
單元測試為選用，僅在複雜邏輯需要隔離時加入。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create cashflow functional suite scaffold in tests/functional/suites/cashflow_intents.jsonl

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Update structured output schema to include cashflow intent fields in app/schemas.py
- [X] T003 [P] Add cashflow intent rules and transaction_type mapping in app/prompts.py
- [X] T004 Implement cashflow intent parsing pipeline in app/gpt_processor.py
- [X] T005 Add shared cashflow rules helper in app/cashflow_rules.py
- [X] T006 Update CREATE payload to include 交易類型 in app/webhook_sender.py
- [X] T007 Update confirmation output to show 交易類型 in app/line_handler.py
- [X] T021 Add cashflow keyword routing (withdrawal/transfer/card_payment/income) to use dedicated cashflow prompt in app/prompts.py and app/gpt_processor.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 提款雙筆記錄 (Priority: P1) 🎯 MVP

**Goal**: 提款訊息產生「提款／收入」兩筆記錄且金額一致

**Independent Test**: 輸入提款描述後，確認輸出兩筆記錄、交易類型與付款方式正確

### Tests for User Story 1 (REQUIRED for user journeys / external APIs) ⚠️

- [X] T008 [P] [US1] Add withdrawal double-entry cases in tests/functional/suites/cashflow_intents.jsonl

### Implementation for User Story 1

- [X] T009 [US1] Implement withdrawal double-entry generation in app/gpt_processor.py
- [X] T010 [US1] Map withdrawal default payment methods (account vs cash) in app/cashflow_rules.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 轉帳意圖記錄 (Priority: P2)

**Goal**: 轉帳依情境產生單筆支出或雙筆轉帳/收入

**Independent Test**: 輸入「合庫轉帳給媽媽 2000」與「合庫轉帳到富邦 2000」皆符合規則

### Tests for User Story 2 (REQUIRED for user journeys / external APIs) ⚠️

- [X] T011 [P] [US2] Add transfer cases (to-person, account-to-account) in tests/functional/suites/cashflow_intents.jsonl

### Implementation for User Story 2

- [X] T012 [US2] Implement transfer classification rules in app/cashflow_rules.py
- [X] T013 [US2] Implement transfer entry generation in app/gpt_processor.py
- [X] T014 [US2] Ensure to-person transfers map to 交易類型「支出」 in app/gpt_processor.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - 收入與繳卡費意圖記錄 (Priority: P3)

**Goal**: 收入單筆與繳卡費雙筆記錄一致可用

**Independent Test**: 輸入「薪水入帳 60000」與「合庫繳卡費到富邦 1500」後，輸出對應交易類型與金額

### Tests for User Story 3 (REQUIRED for user journeys / external APIs) ⚠️

- [X] T015 [P] [US3] Add income and card_payment cases in tests/functional/suites/cashflow_intents.jsonl

### Implementation for User Story 3

- [X] T016 [US3] Implement income entry generation in app/gpt_processor.py
- [X] T017 [US3] Implement card_payment as transfer (轉帳/收入) in app/gpt_processor.py
- [X] T018 [US3] Normalize missing payment/account to NA in app/gpt_processor.py

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T019 [P] Add error edge cases (missing/zero/negative amount) in tests/functional/suites/cashflow_intents.jsonl
- [ ] T020 [P] Validate quickstart examples against implementation in specs/005-cashflow-intents/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Shared rules before entry generation
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T003 can run in parallel with T002
- T005 can run in parallel with T004 once schema is ready
- Story test tasks T008, T011, T015 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch tests for User Story 1 together:
Task: "Add withdrawal double-entry cases in tests/functional/suites/cashflow_intents.jsonl"

# Launch rules and implementation:
Task: "Map withdrawal default payment methods in app/cashflow_rules.py"
Task: "Implement withdrawal double-entry generation in app/gpt_processor.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
