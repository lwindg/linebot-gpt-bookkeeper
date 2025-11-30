# Tasks: 修改上一次交易記錄

**Feature**: 001-edit-last-transaction
**Generated**: 2025-11-29
**Status**: Ready for Implementation

---

## Task Summary

| Phase | Total Tasks | Completed | Remaining |
|-------|-------------|-----------|-----------|
| Phase 1: Setup | 1 | 0 | 1 |
| Phase 2: Foundational | 3 | 0 | 3 |
| Phase 3: US1 - Edit Item Name (P1) | 3 | 0 | 3 |
| Phase 4: US2 - Edit Category (P2) | 2 | 0 | 2 |
| Phase 5: US3 - Edit Project (P3) | 2 | 0 | 2 |
| Phase 6: US4 - Edit Amount (P4) | 2 | 0 | 2 |
| Phase 7: Polish & Documentation | 3 | 0 | 3 |
| **Total** | **16** | **0** | **16** |

---

## Dependency Graph

```
Phase 1 (Setup)
  └─ T001

Phase 2 (Foundational - All stories depend on these)
  ├─ T002 (Extend GPT prompt)
  ├─ T003 (Update JSON schema)
  └─ T004 (Update data model)

Phase 3 (US1 - MVP)
  ├─ T005 (Implement handler)
  ├─ T006 (Integrate handler)
  └─ T007 [P] (Integration test)

Phase 4-6 (US2-US4 - Can run in parallel after Phase 3)
  ├─ T008 [P] [US2] (Category test)
  ├─ T009 [P] [US2] (Category error test)
  ├─ T010 [P] [US3] (Project test)
  ├─ T011 [P] [US3] (Project error test)
  ├─ T012 [P] [US4] (Amount test)
  └─ T013 [P] [US4] (Amount validation test)

Phase 7 (Polish - After all US tests pass)
  ├─ T014 (Error messages)
  ├─ T015 (Documentation)
  └─ T016 (Concurrency test)
```

**Parallelization Opportunities**:
- T002, T003, T004 can run in parallel (independent file changes)
- T008-T013 can run in parallel after T007 passes (independent test scenarios)

---

## Phase 1: Setup

**Goal**: Verify environment and prerequisites

- [ ] **T001** Verify development environment and dependencies
  - Confirm Python 3.11+, uv package manager installed
  - Verify Redis connection (local or Vercel KV)
  - Check environment variables: `OPENAI_API_KEY`, `REDIS_URL`, `KV_ENABLED=true`
  - Run `uv sync` to install dependencies
  - Test existing KV functionality: `KVStore.get()`, `KVStore.set()`
  - Files: `.env`, `app/config.py`, `app/kv_store.py`
  - **Acceptance**: All environment checks pass, Redis connection successful

---

## Phase 2: Foundational

**Goal**: Extend GPT and schema infrastructure to support update_last_entry intent

- [ ] **T002** [P] Extend MULTI_EXPENSE_PROMPT in app/prompts.py with update_last_entry intent
  - Add intent type 4 documentation: `update_last_entry`
  - Define trigger conditions: keywords "修改", "改", "更新", "上一筆", "最後一筆"
  - Define response format: `{"intent": "update_last_entry", "fields_to_update": {...}}`
  - Add field rules: 品項/分類/專案/原幣金額 (partial updates)
  - Add validation rule: negative amount → error intent
  - Include 5 examples from gpt-api.md:93-97
  - Files: `app/prompts.py`
  - **Acceptance**: Prompt includes all intent rules and examples from contracts/gpt-api.md

- [ ] **T003** [P] Update MULTI_BOOKKEEPING_SCHEMA in app/schemas.py with fields_to_update
  - Add "update_last_entry" to intent enum list
  - Add `fields_to_update` property (type: object)
  - Define fields_to_update properties: 品項 (string), 分類 (string), 專案 (string), 原幣金額 (number, minimum: 0)
  - Set `additionalProperties: False` for fields_to_update
  - Files: `app/schemas.py`
  - **Acceptance**: Schema matches structure in contracts/gpt-api.md:154-210

- [ ] **T004** [P] Update MultiExpenseResult dataclass in app/gpt_processor.py
  - Add "update_last_entry" to intent Literal type
  - Add `fields_to_update: Optional[dict] = None` field
  - Files: `app/gpt_processor.py:55-72`
  - **Acceptance**: Dataclass supports new intent type and fields_to_update attribute

---

## Phase 3: User Story 1 - Edit Item Name (P1) 🎯 MVP

**Goal**: Implement core update handler and enable item name editing

**User Story**: As a user, I want to modify the item name of my last transaction so that I can correct mistakes without re-entering the entire transaction.

**Acceptance Criteria**:
- When I send "修改品項為工作午餐" after creating a transaction, the item name updates to "工作午餐" and other fields remain unchanged
- When I modify the item name and a new transaction exists, I receive "交易已變更，請重新操作"
- When no transaction exists in KV (expired or empty), I receive "目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）"

---

- [ ] **T005** Implement handle_update_last_entry() in app/line_handler.py
  - Create function signature: `handle_update_last_entry(user_id: str, fields_to_update: dict) -> str`
  - Step 1: Validate fields_to_update is not empty
  - Step 2: Read original transaction from KV (key: `user:{user_id}:last_transaction`)
  - Step 3: Return error if transaction not found
  - Step 4: Record target transaction ID (optimistic lock)
  - Step 5: Update target fields in transaction dict (skip empty/None values)
  - Step 6: Re-read KV and verify transaction ID matches (concurrency check)
  - Step 7: Write updated transaction back to KV with TTL (from `LAST_TRANSACTION_TTL`)
  - Step 8: Format success message: "✅ 修改成功！\n已更新：{field}: {value}"
  - Files: `app/line_handler.py`, `app/kv_store.py`, `app/config.py`
  - **Reference**: contracts/kv-storage.md:214-248, quickstart.md:183-228
  - **Acceptance**: Function implements optimistic locking and returns appropriate messages

- [ ] **T006** Integrate update_last_entry handler in handle_text_message()
  - Import `handle_update_last_entry` function
  - After `process_multi_expense()` call, check `result.intent == "update_last_entry"`
  - If true: call `handle_update_last_entry(user_id, result.fields_to_update)`
  - Reply with returned message using `TextSendMessage`
  - Return early to avoid fallthrough to existing intent handlers
  - Files: `app/line_handler.py:236-255`
  - **Reference**: quickstart.md:236-255
  - **Acceptance**: Update intent triggers handler and sends reply message

- [ ] **T007** [P] [US1] Write integration test for item name editing success scenario
  - Test file: `tests/integration/test_edit_last_transaction.py`
  - Test: `test_edit_item_name_success`
  - Given: KV contains transaction with 品項="午餐", 原幣金額=100.0, 交易ID="20251129-140000"
  - When: Call `handle_update_last_entry(user_id, {"品項": "工作午餐"})`
  - Then:
    - KV transaction updated with 品項="工作午餐"
    - 原幣金額 remains 100.0 (unchanged)
    - Success message contains "修改成功"
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Reference**: quickstart.md:305-323, research.md:199-204
  - **Acceptance**: Test passes, demonstrates item name update without affecting other fields

---

## Phase 4: User Story 2 - Edit Category (P2)

**Goal**: Enable category field editing

**User Story**: As a user, I want to modify the category of my last transaction so that I can correct classification errors without re-entering the entire transaction.

**Acceptance Criteria**:
- When I send "改分類為交通" after creating a transaction, the category updates to "交通" and other fields remain unchanged
- When I modify the category with an empty value, the original category is preserved

---

- [ ] **T008** [P] [US2] Write integration test for category editing success scenario
  - Test: `test_edit_category_success`
  - Given: KV contains transaction with 分類="飲食", 品項="午餐"
  - When: Call `handle_update_last_entry(user_id, {"分類": "交通"})`
  - Then: 分類="交通", 品項="午餐" (unchanged)
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Acceptance**: Test passes, category updates independently

- [ ] **T009** [P] [US2] Write integration test for category editing with empty value
  - Test: `test_edit_category_preserve_on_empty`
  - Given: KV contains transaction with 分類="飲食"
  - When: Call `handle_update_last_entry(user_id, {"分類": ""})`
  - Then: 分類="飲食" (preserved, no update)
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Reference**: data-model.md:210-213
  - **Acceptance**: Test passes, empty values preserve original field

---

## Phase 5: User Story 3 - Edit Project (P3)

**Goal**: Enable project field editing

**User Story**: As a user, I want to modify the project of my last transaction so that I can re-categorize expenses to different projects without re-entering the entire transaction.

**Acceptance Criteria**:
- When I send "修改專案為Q4行銷活動" after creating a transaction, the project updates to "Q4行銷活動" and other fields remain unchanged
- When I modify the project with an empty value, the original project is preserved

---

- [ ] **T010** [P] [US3] Write integration test for project editing success scenario
  - Test: `test_edit_project_success`
  - Given: KV contains transaction with 專案="日常", 品項="午餐"
  - When: Call `handle_update_last_entry(user_id, {"專案": "Q4行銷活動"})`
  - Then: 專案="Q4行銷活動", 品項="午餐" (unchanged)
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Acceptance**: Test passes, project updates independently

- [ ] **T011** [P] [US3] Write integration test for project editing with empty value
  - Test: `test_edit_project_preserve_on_empty`
  - Given: KV contains transaction with 專案="日常"
  - When: Call `handle_update_last_entry(user_id, {"專案": ""})`
  - Then: 專案="日常" (preserved, no update)
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Acceptance**: Test passes, empty values preserve original field

---

## Phase 6: User Story 4 - Edit Amount (P4)

**Goal**: Enable amount field editing with validation

**User Story**: As a user, I want to modify the amount of my last transaction so that I can correct pricing errors without re-entering the entire transaction.

**Acceptance Criteria**:
- When I send "改金額350" after creating a transaction, the amount updates to 350.0 and other fields remain unchanged
- When I attempt to modify the amount to 0, the system allows it (represents free items)
- When I attempt to modify the amount to a negative value, the system rejects it and displays "金額不可為負數"

---

- [ ] **T012** [P] [US4] Write integration test for amount editing success and zero scenarios
  - Test: `test_edit_amount_success`
    - Given: KV contains transaction with 原幣金額=100.0
    - When: Call `handle_update_last_entry(user_id, {"原幣金額": 350.0})`
    - Then: 原幣金額=350.0
  - Test: `test_edit_amount_to_zero`
    - Given: KV contains transaction with 原幣金額=100.0
    - When: Call `handle_update_last_entry(user_id, {"原幣金額": 0.0})`
    - Then: 原幣金額=0.0 (allowed - free item)
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Reference**: quickstart.md:336-352, data-model.md:194
  - **Acceptance**: Tests pass, zero amounts allowed

- [ ] **T013** [P] [US4] Write integration test for negative amount rejection
  - Test: `test_edit_amount_negative_rejected`
  - Given: User sends message "改金額 -100"
  - When: GPT processes message
  - Then:
    - GPT returns `intent="error"` with `error_message="金額不可為負數，請重新輸入"`
    - No KV update occurs
    - User receives error message
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Reference**: contracts/gpt-api.md:97, data-model.md:194
  - **Acceptance**: Test passes, GPT validates negative amounts before handler execution

---

## Phase 7: Polish & Documentation

**Goal**: Refine error messages, update documentation, add concurrency tests

- [ ] **T014** Refine error messages and user feedback
  - Update "無可修改的交易記錄" message to include TTL hint: "目前沒有可修改的交易記錄（交易記錄會在 1 小時後自動清除）"
  - Ensure concurrency conflict message: "交易已變更，請重新操作"
  - Ensure success message format: "✅ 修改成功！\n已更新：{field}: {value}"
  - Add field-specific validation messages (if needed)
  - Files: `app/line_handler.py`
  - **Reference**: research.md:174-177, contracts/kv-storage.md:307-308
  - **Acceptance**: All error messages match specification requirements

- [ ] **T015** [P] Update documentation and quickstart guide
  - Verify `quickstart.md` reflects actual implementation
  - Update README.md if feature impacts user-facing documentation
  - Add usage examples to spec.md if needed
  - Files: `specs/001-edit-last-transaction/quickstart.md`, `README.md`
  - **Acceptance**: Documentation accurate and complete

- [ ] **T016** [P] Write integration test for concurrency conflict scenario
  - Test: `test_edit_with_concurrent_new_transaction`
  - Given: KV contains transaction with 交易ID="20251129-140000"
  - When:
    1. Read original transaction
    2. Simulate external update (new transaction with 交易ID="20251129-140100")
    3. Attempt update with original fields_to_update
  - Then:
    - Optimistic lock detects ID mismatch
    - Returns "交易已變更，請重新操作"
    - No update occurs
  - Files: `tests/integration/test_edit_last_transaction.py`
  - **Reference**: contracts/kv-storage.md:356-376, research.md:60-81
  - **Acceptance**: Test passes, concurrency control works correctly

---

## Verification Checklist

Before marking feature as complete, verify:

- [ ] All 16 tasks completed
- [ ] All integration tests pass (`uv run pytest tests/integration/test_edit_last_transaction.py -v`)
- [ ] Manual testing via `test_local.py` successful for all 4 user stories
- [ ] GPT correctly identifies update_last_entry intent for sample commands
- [ ] KV operations respect 1-hour TTL
- [ ] Optimistic locking prevents concurrent modification issues
- [ ] Error messages match specification requirements
- [ ] Documentation updated and accurate
- [ ] Code follows existing patterns in `app/line_handler.py` and `app/gpt_processor.py`
- [ ] No new dependencies added (reuses existing stack)
- [ ] Constitution principles upheld (MVP, Testing, Simplicity, DX, User Value)

---

## Testing Strategy

### Integration Tests Location
`tests/integration/test_edit_last_transaction.py`

### Test Organization
```python
class TestEditLastTransaction:
    # Setup/Teardown
    def setup_method(self): ...
    def teardown_method(self): ...

    # US1: Item Name
    def test_edit_item_name_success(self): ...
    def test_edit_with_no_transaction(self): ...

    # US2: Category
    def test_edit_category_success(self): ...
    def test_edit_category_preserve_on_empty(self): ...

    # US3: Project
    def test_edit_project_success(self): ...
    def test_edit_project_preserve_on_empty(self): ...

    # US4: Amount
    def test_edit_amount_success(self): ...
    def test_edit_amount_to_zero(self): ...
    def test_edit_amount_negative_rejected(self): ...

    # Concurrency
    def test_edit_with_concurrent_new_transaction(self): ...
```

### Manual Testing
Use `test_local.py` for end-to-end verification:
```
> 午餐 100
✅ 記帳成功！...

> 修改品項為工作午餐
✅ 修改成功！
已更新：品項: 工作午餐

> 改金額 150
✅ 修改成功！
已更新：原幣金額: 150.0
```

---

## Success Metrics Mapping

| Success Criteria | Verification Method |
|-----------------|---------------------|
| SC-001: 10秒內完成操作 | Manual timing test with `test_local.py` |
| SC-002: 回應時間 <1秒 | Integration test assertions + logging |
| SC-003: 95%首次成功率 | Natural language command testing (manual) |
| SC-004: 減少80%搜尋操作 | User feedback (post-deployment) |
| SC-005: 錯誤率 <1% | Integration test coverage + production monitoring |
| SC-006: 滿意度 4.5/5 | User survey (post-deployment) |

---

## Risk Mitigation

| Risk | Mitigation | Related Tasks |
|------|-----------|---------------|
| GPT未識別修改意圖 | Comprehensive prompt examples in T002 | T002 |
| KV過期導致無法修改 | Clear error message with TTL hint in T014 | T014 |
| 併發衝突未處理 | Optimistic lock in T005, test in T016 | T005, T016 |
| 金額驗證規則遺漏 | Schema minimum constraint in T003, test in T013 | T003, T013 |
| 空值覆蓋原值 | Skip empty/None values in T005 | T005 |

---

**Generated by**: `/speckit.tasks`
**Next Step**: Execute `/speckit.implement` to begin implementation
