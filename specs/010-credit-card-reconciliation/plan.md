# 010 - 信用卡對帳：技術規劃（plan）

> 本文件為規劃文件（中文）。程式碼/註解/commit message 仍遵守英文政策。

## 0. 目標回顧

以台新帳單（PDF/截圖）匯入後，在 Notion：
- 產生「信用卡帳單明細」資料庫的明細列
- 自動比對到「新帳目」交易（含批次ID一對多）
- 支援國外交易服務費（手續費）列的匹配與分攤回寫 `手續費`
- 產出 Matched / Need Confirm / Missing 清單，並將匹配結果寫回 Notion relation（新帳目↔帳單明細↔帳單）

## 1. Notion 資料設計

### 1.1 既有資料庫：新帳目（book ledger）
- 既有欄位：日期、付款方式、批次ID、交易ID、原幣別、原幣金額、匯率、手續費…
- **已新增（採用）**：
  - `對應帳單明細`（relation → 信用卡帳單明細）
  - `對應帳單`（relation → 信用卡帳單）

> 不再使用 `對帳月份(select)` 作為主要對帳依據（選項會無限增長）。

### 1.2 新增資料庫：信用卡帳單明細（cc_statement_lines）
MVP 欄位建議（對應 spec 4.1）：
- 帳單月份（YYYY-MM）
- 付款方式（對應：台新狗卡 / FlyGo 信用卡；用詞需與新帳目一致）
- 消費日（date）
- 入帳起息日（date）
- 新臺幣金額（number）
- 幣別（select，可空）
- 外幣金額（number，可空）
- 消費明細（rich_text）
- 是否手續費（checkbox）
- 手續費參考金額（number，可空；對應 `國外交易服務費—93.00` 的 93.00）
- raw_text（rich_text，可選）
- 對帳狀態（select：unmatched/proposed/matched/ignored，可選）
- 對應帳目（relation → 新帳目，多對多）

> 關鍵：台新手續費行的「—93.00」是 reference，不是 fee amount；fee amount 取該行新臺幣金額欄位。

## 2. 匯入與解析（台新模板）

### 2.1 輸入
- PDF 或 圖片（截圖）

### 2.2 解析策略
- 先做 OCR：取得文字（含表格行）
- 以規則/模板切行：
  - 欄位：消費日、入帳起息日、消費明細、新臺幣金額、外幣折算日、消費地、幣別、外幣金額
- 解析「卡片段落」：
  - 遇到 `Richart卡(原@GoGoicash...)` → current_card=台新狗卡
  - 遇到 `Richart卡(原FlyGo...)` → current_card=FlyGo 信用卡
  - 後續明細列繼承 current_card，寫入 statement_line.付款方式
- 手續費行判斷：消費明細以 `國外交易服務費` 開頭
  - 抽出 `reference_amount`（破折號後面的數字）

### 2.3 Notion 寫入
- 將每列寫入 cc_statement_lines
- 對於解析不完整的列：仍寫入 + raw_text，狀態設 unmatched

## 3. 比對引擎（matching）

### 3.1 候選生成
對每個 statement_line：
- 篩選新帳目：付款方式一致（台新狗卡 or FlyGo 信用卡）
- 日期窗：以 **消費日** 為主（±2 天）；缺消費日才 fallback 入帳起息日
- 金額：
  - 若 statement 有外幣金額/幣別 → 優先比對新帳目的 原幣別+原幣金額
  - 否則比對台幣（容忍少量誤差）

### 3.2 批次ID聚合匹配
- 先將候選新帳目依批次ID分組
- 若 batch_id 存在：用批次內各筆金額加總對比 statement amount
- 匹配成功：建立 statement_line ↔ 多筆帳目的 relation

### 3.3 手續費匹配與分攤
- 對 `是否手續費=true`：
  - 使用 `手續費參考金額(reference_amount)` 去找同卡、日期窗內的新臺幣金額=reference_amount 的消費行（或其 batch）
  - 成功後，把 fee line 的新臺幣金額（例如 1、55、30）依比例分攤到對應 batch 的每筆帳目 `手續費`

### 3.4 Need Confirm
- 若候選多筆或分數相近：標 proposed，交由 LINE review

## 4. LINE bot 流程（MVP）

### 4.1 現況（已存在）
- Flex Menu：`功能` / `選單`
- lock 指令：`鎖定專案`、`鎖定付款`、`鎖定幣別`、`鎖定狀態`、`全部解鎖`

### 4.2 新增：鎖定對帳模式（因 LINE 圖文分離限制）

- `鎖定對帳 台新 2026-01`
- 上傳帳單截圖（可多張）→ 匯入 Notion 明細 + 建立/更新 Notion「信用卡帳單」
- `執行對帳` → matching + 寫回 relation（對應帳目/對應帳單明細/對應帳單）+ 更新對帳狀態
- `解除對帳` / `全部解鎖`

> MVP 先不做 close 與對帳月份；以 Notion view 篩 `matched/unmatched` 即可。

## 5. 交付順序（推薦）

1) Notion：建立/確認 statements + statement_lines + ledger relations（不使用對帳月份 select）
2) 匯入：台新 OCR + 解析模板（含卡段落與手續費 reference）
3) Matching：同卡 + 日期窗 + 金額 + batch_id 聚合
4) 手續費：reference_amount 對應 + 分攤回寫
5) LINE：summary/review/close
6) 回歸測試：以你提供的帳單樣本做 golden test

## 6. 風險與對策

- OCR 失誤：保留 raw_text，允許人工修正後再跑 matching
- 同金額多筆：依卡別段落 + reference_amount + merchant（簡易 normalize）降低歧義
- 不同銀行格式：模板化（bank plugins），但 MVP 只做台新
