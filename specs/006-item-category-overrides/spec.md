# Feature Specification: Item Category Overrides

**Feature Branch**: `006-item-category-overrides`  
**Created**: 2026-01-11  
**Status**: Draft  
**Input**: User description: "在思考是否取出品項後，回歸程式試著查表應對分類：有品項則使用表中的分類，沒命中則沿用 GPT 分類。特別是當地特殊物品、食品或興趣類容易誤判。例：兩相好 → 早餐、魚 → 食材、雞胗 → 食材。"
**Language**: 本文件內容以正體中文撰寫，程式碼/識別符/錯誤訊息維持英文

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 品項分類覆蓋 (Priority: P1)

使用者輸入含特定品項時，系統以品項對照表覆蓋 GPT 分類，
避免常見食材/在地品項被誤分類。

**Why this priority**: 分類錯誤會影響統計與帳務分析，且品項規律可被穩定覆蓋。

**Independent Test**: 輸入單項目品項且包含對照表關鍵字後，分類必須覆蓋為對照表指定值。

**Acceptance Scenarios**:

1. **Given** 使用者輸入「兩相好 60 現金」, **When** 系統建立記錄, **Then**
   分類為「家庭/餐飲/早餐」。
2. **Given** 使用者輸入「魚 200 現金」, **When** 系統建立記錄, **Then**
   分類為「家庭/食材」。
3. **Given** 使用者輸入「雞胗 120 現金」, **When** 系統建立記錄, **Then**
   分類為「家庭/食材」。

---

### User Story 2 - 未命中則沿用 GPT 分類 (Priority: P2)

使用者輸入未在對照表中的品項時，系統保留 GPT 分類結果。

**Why this priority**: 避免對照表不足時導致分類失真或被硬套。

**Independent Test**: 輸入非對照表品項後，分類必須與 GPT 分類一致。

**Acceptance Scenarios**:

1. **Given** 使用者輸入「露營瓦斯罐 250 現金」, **When** 系統建立記錄, **Then**
   分類仍沿用 GPT 輸出，不被覆蓋。

---

### Edge Cases

- 品項同時命中多個關鍵字時，優先序如何決定？
- 與非食材同字根衝突時如何避免誤判（例如「魚缸」不應視為食材）？
- 多項目記帳時，僅對命中的項目覆蓋分類，其餘保持 GPT 分類。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST 在品項命中對照表關鍵字時覆蓋 GPT 分類。
- **FR-002**: System MUST 在未命中對照表時保留 GPT 分類結果。
- **FR-003**: System MUST 允許對照表以「關鍵字包含」方式比對品項。
- **FR-004**: System MUST 支援多項目記帳中逐項覆蓋分類。
- **FR-005**: System MUST 提供明確的對照表維護位置（可擴充）。

### Key Entities *(include if feature involves data)*

- **Item Category Override**: 品項關鍵字對照分類（關鍵字、分類、優先序）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 針對對照表中的品項，分類覆蓋正確率達 95% 以上。
- **SC-002**: 未命中對照表的品項，分類輸出與 GPT 一致率達 95% 以上。
- **SC-003**: 覆蓋機制導入後，食材/早餐類錯誤分類回報下降 50% 以上。
