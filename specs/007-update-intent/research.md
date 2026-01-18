# Research: Update Intent Prompt Split

## Decision 1: 更新意圖分流準則

**Decision**: 只要訊息包含更新語意（修改/更改/改/更新）且包含明確欄位名稱，即判定為更新意圖；
若缺少欄位名稱或新值，回傳錯誤。

**Rationale**: 避免僅靠值猜測導致誤判，並與規格要求一致（必須提供明確欄位）。

**Alternatives considered**:
- 允許僅輸入值時推測欄位（風險高，誤判率增加）

## Decision 2: 付款方式輸出標準化

**Decision**: 付款方式欄位必須輸出標準名稱，依對照表轉換，且不得回錯誤。

**Rationale**: 使用者常用別名（狗卡、富邦等），必須正規化才能與既有資料一致。

**Alternatives considered**:
- 拒絕非標準名稱輸入（實務上易失敗且降低可用性）

## Decision 3: 更新欄位數量限制

**Decision**: 一次只允許更新單一欄位，若同時指定多欄位則回錯誤。

**Rationale**: 降低更新範圍不清與誤改風險，保持使用者心智模型清晰。

**Alternatives considered**:
- 允許多欄位更新（增加解析與回覆複雜度）

## Decision 4: 主記帳 prompt 瘦身

**Decision**: 主記帳 prompt 只保留更新意圖的分流提示，移除詳細更新規則與範例。

**Rationale**: 降低主 prompt 複雜度並避免更新規則干擾其他記帳判斷。

**Alternatives considered**:
- 同時保留更新規則於主 prompt（造成 token 膨脹與誤判）

## Decision 5: 規模與效能假設

**Decision**: 以個人記帳低流量場景為主，延續 3 秒內 webhook 回應限制。

**Rationale**: 符合現有使用模式與 LINE 平台限制。

**Alternatives considered**:
- 針對高並發情境設計（超出當前需求）
