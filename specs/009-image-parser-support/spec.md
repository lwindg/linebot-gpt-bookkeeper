# 009 圖片 Parser 模式支援（收據/繳費單）

## 概述

目前圖片流程走 GPT-only：Vision 先抽取項目後，每筆再做一次分類推論。
此模式無法進入 Parser-first 的 pipeline，也無法批次補齊分類/專案/必要性與外幣換算。

本規格目標是讓「圖片訊息」可進入 Parser-first 流程：
- Vision 負責抽取權威欄位（品項/金額/日期/幣別/付款方式）
- GPT 只做**一次**批次 enrichment（分類/專案/必要性），不得逐筆呼叫
- 外幣需在程式端完成換算並保留原幣別資訊

## 目標

- 圖片流程支援 Parser-first pipeline（與文字流程一致的 validator/converter）
- 視覺抽取結果視為權威欄位，不可覆寫
- GPT enrichment 改為一次批次處理
- 外幣收據可被處理與換算

## 現況問題

- 圖片流程未走 pipeline，無法套用 Validator/Converter 規則
- 分類為逐筆 GPT 呼叫，成本高且一致性差
- 外幣收據直接回錯，無法記帳

## 範圍

### In Scope

- 收據/繳費單圖片的 Parser-first 處理
- Vision 抽取欄位的權威化（items + date + currency + payment）
- 批次 enrichment（單次 GPT 對多筆 items）
- 外幣換算（原幣 + 匯率 + 新台幣）

### Out of Scope

- 影像 OCR 本地模型
- 收據辨識對話追問
- 代墊狀態從圖片推斷
- 現金流類型（提款/轉帳/繳卡費）從圖片判斷

## 使用者流程

1. 使用者上傳收據/繳費單圖片
2. 系統呼叫 Vision API，抽取 items（品項/金額/幣別/日期/付款方式）
3. 將 items 轉為 ImageAuthoritativeEnvelope（權威輸出）
4. 呼叫批次 enrichment（分類/專案/必要性）
5. Validator 校正（分類必須在清單內）
6. Converter 產出 entries + webhook + LINE 回覆

## 功能需求

- FR-IMG-01: Vision 抽取結果建立 ImageAuthoritativeEnvelope
- FR-IMG-02: 權威欄位不可被 GPT 覆寫（品項/金額/日期/幣別/付款方式）
- FR-IMG-03: GPT enrichment 必須是**一次批次**呼叫，不得逐筆
- FR-IMG-04: Enrichment 僅回傳分類/專案/必要性，無其他欄位
- FR-IMG-05: 分類需符合清單，否則套用 fallback 規則
- FR-IMG-06: 外幣需換算為 TWD（保留原幣別/原幣金額/匯率）
- FR-IMG-07: 模糊/非收據/無法解析 → 回傳錯誤訊息並停止
- FR-IMG-08: 一張收據多筆項目需共用批次ID（交易ID 末碼序號）

## 驗收標準

- 圖片流程走 Parser-first pipeline（可在 log 或 debug 證明）
- Vision 抽取的 items 數量與 entries 數量一致
- 分類/專案/必要性由批次 enrichment 補齊（單次 GPT）
- 外幣收據可正確換算並輸出匯率
- 錯誤情境有清楚訊息（非收據/模糊/無法解析）

## 測試案例

- TC-IMG-001: 單筆台幣收據（含日期/付款方式）
- TC-IMG-002: 多筆台幣收據（共用付款方式）
- TC-IMG-003: 外幣收據（JPY）→ 轉換 TWD
- TC-IMG-004: 模糊收據 → 回錯誤訊息
- TC-IMG-005: 非收據圖片 → 回錯誤訊息

## 假設

- Vision API 能穩定輸出 items/金額
- 外幣匯率服務可用（失敗時回錯誤）

