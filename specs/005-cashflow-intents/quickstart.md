# Quick Start: Cashflow Intents MVP

本文件提供現金流意圖功能的本地驗證流程。

## 前置條件

- 已設定 `OPENAI_API_KEY`
- 依照專案既有流程可執行 `python test_local.py`

## 測試範例

### 1. 提款雙筆記錄

```bash
python test_local.py "合庫提款 5000"
```

預期：
- 產生兩筆記錄
- 交易類型分別為「提款」與「收入」
- 付款方式分別為「合庫」與「現金」
- 交易ID 以同批次 `-01` / `-02` 結尾，且 webhook payload 會包含 `批次ID`
- LINE 回應摘要：
  - `🏧 提款：合庫 → 現金 5000`
  - `📅 日期：YYYY-MM-DD`
  - `🔖 批次ID：YYYYMMDD-HHMMSS`

### 2. 轉帳給他人

```bash
python test_local.py "合庫轉帳給媽媽 2000"
```

預期：
- 產生單筆記錄
- 交易類型為「支出」

### 3. 帳戶間轉帳

```bash
python test_local.py "合庫轉帳到富邦 2000"
```

預期：
- 產生兩筆記錄（轉帳/收入）
- 金額一致
- 交易ID 以同批次 `-01` / `-02` 結尾，且 webhook payload 會包含 `批次ID`
- LINE 回應摘要：
  - `🔁 轉帳：合庫 → 富邦 2000`
  - `📅 日期：YYYY-MM-DD`
  - `🔖 批次ID：YYYYMMDD-HHMMSS`

### 4. 繳卡費

```bash
python test_local.py "合庫繳卡費到富邦 1500"
```

預期：
- 交易類型為「轉帳／收入」
- 第二筆付款方式為「富邦 Costco」
- 方向為「帳戶 → 目標帳戶（未指定時為信用卡）」
- 交易ID 以同批次 `-01` / `-02` 結尾，且 webhook payload 會包含 `批次ID`
- LINE 回應摘要：
  - `🔁 轉帳：合庫 → 富邦 Costco 1500`
  - `📅 日期：YYYY-MM-DD`
  - `🔖 批次ID：YYYYMMDD-HHMMSS`

### 5. 錯誤情境

```bash
python test_local.py "提款"
```

預期：
- 回傳錯誤訊息提示缺少金額
