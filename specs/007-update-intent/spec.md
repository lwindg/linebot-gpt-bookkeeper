# Feature Specification: Update Intent Prompt Split

**Feature Branch**: `007-update-intent`  
**Created**: 2026-01-19  
**Status**: Draft  
**Input**: User description: "依前面提到的需求進行規格設計"
**Language**: 本文件內容以正體中文撰寫，程式碼/識別符/錯誤訊息維持英文

## Clarifications

### Session 2026-01-19

- Q: 未提供欄位名稱時是否仍判定為更新 → A: 不判定，必須提供明確欄位名稱
- Q: 是否允許一次更新多個欄位 → A: 不允許，一次只更新單一欄位
- Q: 是否支援欄位同義詞 → A: 不支援，只接受明確欄位詞彙

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 更新語句穩定辨識 (Priority: P1)

使用者輸入更新語句（例如「修改付款方式為狗卡」或「前一筆分類改成交通/接駁」），
系統穩定辨識為更新上一筆記帳，並只更新指定欄位。

**Why this priority**: 更新是高頻操作，若辨識失敗會造成使用者中斷與信任下降。

**Independent Test**: 輸入包含「修改/改/更新」與欄位名稱的訊息，應輸出更新意圖且
`fields_to_update` 僅包含指定欄位。

**Acceptance Scenarios**:

1. **Given** 使用者輸入「修改付款方式為狗卡」, **When** 系統解析訊息, **Then**
   產生更新意圖且付款方式為標準名稱「台新狗卡」。
2. **Given** 使用者輸入「前一筆分類改成交通/接駁」, **When** 系統解析訊息, **Then**
   產生更新意圖且欄位只包含「分類」。

---

### User Story 2 - 更新語句允許指向詞 (Priority: P2)

使用者可用「上一筆/前一筆/最後一筆/剛剛/剛才」搭配更新語句，系統依然判斷為更新上一筆。

**Why this priority**: 使用者習慣使用指向詞，若僅支援部分語句會降低可用性。

**Independent Test**: 以不同指向詞輸入更新語句，應一致回傳更新意圖。

**Acceptance Scenarios**:

1. **Given** 使用者輸入「上一筆付款方式改 狗卡」, **When** 系統解析訊息, **Then**
   產生更新意圖且付款方式為「台新狗卡」。
2. **Given** 使用者輸入「剛剛改金額 350」, **When** 系統解析訊息, **Then**
   產生更新意圖且金額為 350。

---

### User Story 3 - 更新錯誤訊息一致 (Priority: P3)

使用者缺少必要資訊時，系統回傳清楚且一致的錯誤訊息，不誤導為其他意圖。

**Why this priority**: 清楚的錯誤訊息能讓使用者快速修正輸入，避免誤判為其他意圖。

**Independent Test**: 輸入缺少欄位或新值的更新語句，應回傳明確錯誤。

**Acceptance Scenarios**:

1. **Given** 使用者輸入「修改付款方式」, **When** 系統解析訊息, **Then**
   回傳錯誤訊息，指出缺少付款方式新值。
2. **Given** 使用者輸入「更新金額 -100」, **When** 系統解析訊息, **Then**
   回傳錯誤訊息，指出金額不可為負數。

---

### Edge Cases

- 同一句話同時包含多個欄位（例如「改付款方式與分類」）時，回傳錯誤並要求一次只改一項。
- 使用者輸入只有「改/更新」但沒有欄位名稱與新值時，回傳錯誤。
- 使用者輸入只有付款方式關鍵字（例如「狗卡」）時，不視為更新。
- 欄位名稱與指向詞順序不同（例如「付款方式改為狗卡 前一筆」）仍需判定為更新。
- 欄位名稱使用同義詞（例如「金額」與「費用」）時，僅支援明確欄位詞彙清單。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 將包含更新語意（修改/更改/改/更新）且包含欄位名稱的訊息
  判定為更新上一筆記帳。
- **FR-002**: System MUST 支援指向詞（上一筆/前一筆/最後一筆/剛剛/剛才）並仍判定為更新。
- **FR-003**: System MUST 在更新意圖中輸出 `fields_to_update`，且只包含被指定的欄位。
- **FR-004**: System MUST 允許只更新單一欄位，且不允許一次更新多欄位。
- **FR-005**: System MUST 在付款方式更新時輸出標準名稱（依對照表轉換），不得回錯誤。
- **FR-006**: System MUST 在金額為負數時回傳錯誤。
- **FR-007**: System MUST 在缺少欄位名稱或新值時回傳錯誤，且不得推測欄位。
- **FR-008**: System MUST 在無更新語意或欄位名稱時，不得誤判為更新。

### Key Entities *(include if feature involves data)*

- **Update Request**: 使用者對上一筆記帳的更新指令。
- **Update Fields**: 允許更新的欄位集合（品項、分類、專案、原幣金額、付款方式、明細說明、必要性）。
- **Canonical Payment Method**: 付款方式標準名稱，需由對照表正規化後輸出。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在 20 筆更新語句測試中，意圖辨識正確率達 95% 以上。
- **SC-002**: 在 10 筆付款方式更新測試中，100% 輸出標準名稱且不回錯誤。
- **SC-003**: 缺少欄位或新值的輸入 100% 回傳清楚錯誤訊息。
- **SC-004**: 更新語句在 5 種指向詞下皆能成功解析（至少 90% 成功率）。
