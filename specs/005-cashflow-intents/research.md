# Research: Cashflow Intents MVP

本文件整理現金流意圖功能的關鍵決策與理由，目標是解決規格中的行為與資料需求。

## Decision 1: 意圖辨識沿用 GPT 結構化輸出

**Decision**: 延續現有 `process_multi_expense` 的 GPT structured output 流程，新增現金流意圖欄位與規則。

**Rationale**:
- 現有流程已穩定支援多項目與錯誤處理，擴充成本最低
- 結構化輸出能確保欄位一致性，降低解析錯誤

**Alternatives considered**:
- 以純規則式分流（優點：可解釋；缺點：擴充成本高）

## Decision 2: 多意圖同時命中的固定優先序

**Decision**: 固定優先序為 `card_payment` > `transfer` > `withdrawal` > `income`。

**Rationale**:
- 已由使用者明確指定，避免歧義
- 固定順序可降低回歸風險與測試複雜度

**Alternatives considered**:
- 以關鍵字出現順序決策
- 請使用者二次確認

## Decision 3: 提款雙筆、轉帳視情境

**Decision**: `withdrawal` 固定雙筆；`transfer` 若為帳戶間移轉則雙筆，對他人轉帳則單筆支出。

**Rationale**:
- 與使用者需求一致，並可維持現金流完整性
- 與既有「同批次」處理方式一致，可沿用批次 ID

**Alternatives considered**:
- 全部轉帳都雙筆

## Decision 4: 繳卡費視為 transfer

**Decision**: `card_payment` 轉為 `transfer` 進行處理，方向為「帳戶 → 信用卡」，交易類型為「轉帳／收入」。

**Rationale**:
- 可統一轉帳邏輯與雙筆記錄
- 語意貼近資金移轉而非消費

**Alternatives considered**:
- 另起「card_payment」單筆支出

## Decision 5: 付款方式／帳戶缺失採 NA

**Decision**: 若未提供付款方式或帳戶，欄位填入 `NA`。

**Rationale**:
- 避免錯誤猜測造成誤記
- 與既有代墊情境一致（付款方式可為 NA）

**Alternatives considered**:
- 直接回傳錯誤要求補充

## Decision 6: 非正數金額直接拒絕

**Decision**: 金額為 0 或負數時回傳錯誤並提示補充正數。

**Rationale**:
- 避免資金方向混淆
- 減少後續修正成本

**Alternatives considered**:
- 自動取絕對值
- 視為沖銷紀錄
