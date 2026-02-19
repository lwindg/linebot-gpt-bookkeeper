# 010 - 信用卡對帳：任務清單（tasks）

## Phase 0 — Notion 結構就緒（已完成）

- [x] 0.1 在 Notion 新增資料庫：信用卡帳單明細（cc_statement_lines）
- [x] 0.1b 在 Notion 新增資料庫：信用卡帳單（statements）
- [x] 0.1c 關聯欄位：
  - [x] 信用卡帳單明細：`所屬帳單`（→信用卡帳單）
  - [x] 信用卡帳單明細：`對應帳目`（→新帳目）
  - [x] 新帳目：`對應帳單明細`（→信用卡帳單明細）
  - [x] 新帳目：`對應帳單`（→信用卡帳單）
- [x] 0.2 決策：不使用 `對帳月份(select)` 作為主要對帳依據（已刪除/停用）。

## Phase 1 — 台新匯入（OCR + 模板解析）

- [x] 1.0 Vision prompt + 匯入腳本（本機/後端可跑）：台新帳單截圖 → Notion cc_statement_lines
- [ ] 1.1 LINE 端匯入入口：在「鎖定對帳模式」下，收到圖片訊息時改走帳單匯入（而非收據匯入）
- [ ] 1.2 台新模板（保持）：
  - [x] 解析表頭欄位：消費日、入帳起息日、消費明細、新臺幣金額、幣別、外幣金額…
  - [x] 解析卡片段落：@GoGoicash → 台新狗卡；FlyGo → FlyGo 信用卡
  - [x] 解析手續費行：`國外交易服務費—<reference_amount>`
  - [x] 寫入 Notion cc_statement_lines（含帳單ID、連結帳戶等）

## Phase 2 — Matching 引擎（含 batch_id）

- [x] 2.0 報告模式（script）：statement_id → matched/need_confirm/unmatched + diagnostics
- [x] 2.1 候選生成：付款方式 + **消費日**±2（缺消費日 fallback 起息日）
- [x] 2.2 金額匹配：外幣優先（原幣別+原幣金額），台幣則用 `原幣別=TWD` 的 `原幣金額`
- [x] 2.3 批次ID聚合：同批次加總匹配 statement line（含 batch consume 排除、同日優先排序）
- [x] 2.4 匹配結果寫回：
  - [x] statement_line ↔ 新帳目 relation（`對應帳目` / `對應帳單明細`）
  - [x] 新帳目 ↔ 帳單 relation（`對應帳單`）
  - [x] statement_line `對帳狀態`
- [ ] 2.5 LINE 指令：`執行對帳` 觸發 matching + 寫回

## Phase 3 — 手續費匹配與分攤（外幣）

- [ ] 3.1 手續費行對應：用 reference_amount 找到目標消費（或 batch）
- [ ] 3.2 分攤：依比例回寫新帳目 `手續費`
- [ ] 3.3 匯率建議（1% 門檻）：只在 matched 且人工確認後才建議更新匯率（避免誤配污染）

## Phase 4 — LINE bot 互動（鎖定對帳模式）

- [ ] 4.1 新增鎖定對帳 lock：`鎖定對帳 台新 2026-01` / `解除對帳` / `對帳狀態`
- [ ] 4.2 Flex Menu 整合：在「鎖定狀態」中顯示對帳鎖定與快捷按鈕
- [ ] 4.3 在鎖定對帳模式下：圖片訊息走「帳單匯入」而非「收據匯入」
- [ ] 4.4 `執行對帳`：回覆摘要（matched/unmatched/payment_records/credit_offsets）

> MVP 先不做 close 與月份欄位；已對帳以 relation 判斷。

## Phase 5 — 測試與樣本回放

- [ ] 5.1 建立台新帳單樣本的 golden test（匯入 → statement lines 數量/欄位正確）
- [ ] 5.2 matching 測試：
  - [ ] 單筆匹配（同日優先）
  - [ ] batch_id 多筆加總匹配（consume 排除）
  - [ ] credit offsets（信用卡消費折抵）自動補負數記帳並連結
  - [ ] payment_records（上一期扣繳）只提醒
  - [ ] 手續費 reference 匹配 + 分攤（外幣）

## Phase 6 — 擴充（非 MVP）

- [ ] 6.1 永豐模板
- [ ] 6.2 LIFF/小網頁 dashboard（大量對帳更省力）
- [ ] 6.3 many-to-one / one-to-many 手動 match UI
- [ ] 6.4 自動追上一期扣繳對應交易
- [ ] 6.5 安全性/稽核：對帳操作 log、重跑/回滾策略
