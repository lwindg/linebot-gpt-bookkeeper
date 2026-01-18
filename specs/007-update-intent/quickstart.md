# Quickstart: Update Intent Prompt Split

## Goal

確認更新語句能穩定輸出 `update_last_entry`，且付款方式已正規化為標準名稱。

## Scenarios

### Scenario 1: 付款方式更新

**Input**: 修改付款方式為狗卡

**Expected**:
- intent = update_last_entry
- fields_to_update.付款方式 = 台新狗卡

### Scenario 2: 指向詞 + 付款方式更新

**Input**: 前一筆付款方式改 狗卡

**Expected**:
- intent = update_last_entry
- fields_to_update.付款方式 = 台新狗卡

### Scenario 3: 缺少欄位名稱

**Input**: 改成狗卡

**Expected**:
- intent = error
- message 指出缺少欄位名稱或新值

### Scenario 4: 多欄位同時更新

**Input**: 改付款方式與分類

**Expected**:
- intent = error
- message 指出一次只允許更新一個欄位

### Scenario 5: 主記帳 prompt 瘦身

**Input**: （檢查主記帳 prompt 內容）

**Expected**:
- update 規則與範例不再出現在主記帳 prompt
