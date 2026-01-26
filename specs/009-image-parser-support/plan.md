# 009 圖片 Parser 模式支援 - 實作計畫

## 目標

讓圖片收據流程改走 Parser-first pipeline：Vision 抽取權威欄位、批次 GPT enrichment、Validator 校正、Converter 輸出。

## 設計概覽

### 新的流程

Image → Vision → ImageAuthoritativeEnvelope → Batch Enrichment → Validator → Converter → Webhook/LINE

### 重要原則

- 權威欄位不可覆寫（品項/金額/日期/幣別/付款方式）
- 批次 GPT：一次傳入所有 items，不逐筆
- 外幣在程式端換算，保留原幣資訊

## 變更範圍

### 新增 / 調整模組

- `app/pipeline/image_flow.py`：圖片專用 pipeline（或整合到 `app/pipeline/main.py`）
- `app/services/image_handler.py`：輸出 ImageAuthoritativeEnvelope
- `app/enricher/receipt_batch.py`：批次 enrichment
- `app/enricher/validator.py`：擴充支援 image items
- `app/converter.py`：新增 image envelope 轉換

### 資料模型

- ImageAuthoritativeEnvelope
  - `items`: list[{item, amount, currency, date?, payment?}]
  - `receipt_date`（optional）
  - `payment_method`（optional）

## 實作步驟（小增量）

### Step 1：Image envelope 產生

**測試**：Mock Vision 回傳，能產生 ImageAuthoritativeEnvelope
**實作**：在 `image_handler` 新增轉換函式
**完成條件**：單元測試通過

### Step 2：批次 enrichment

**測試**：items 批次送 GPT，回傳分類/專案/必要性陣列
**實作**：新增 `app/enricher/receipt_batch.py`
**完成條件**：一個 GPT 呼叫可補齊多筆 items

### Step 3：外幣換算

**測試**：JPY 收據能換算 TWD，保留原幣別/匯率
**實作**：使用 `ExchangeRateService` 針對 image items 批次換算
**完成條件**：entries 有原幣金額/幣別/匯率

### Step 4：Pipeline 整合

**測試**：圖片訊息在 parser 模式走 image flow
**實作**：在 `pipeline/main.py` 加入 image 分支
**完成條件**：產出 MultiExpenseResult

### Step 5：功能測試

**測試**：TC-IMG-001 ~ TC-IMG-005
**完成條件**：所有圖片測試通過

## 測試

- 單元測試：image envelope / batch enrichment / exchange rate
- 整合測試：圖片訊息 end-to-end

## 風險與對策

- Vision 輸出不完整 → 回錯誤並停止
- 外幣匯率不可用 → 回錯誤並提示
- GPT 分類不穩定 → validator fallback

