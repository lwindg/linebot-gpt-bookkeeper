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
- 付款方式分別為「合庫轉帳」與「現金」

### 2. 轉帳雙筆記錄

```bash
python test_local.py "轉帳給媽媽 2000"
```

預期：
- 產生單筆記錄
- 交易類型為「支出」

### 2b. 帳戶間轉帳

```bash
python test_local.py "合庫轉帳到台新 2000"
```

預期：
- 產生兩筆記錄（轉帳/收入）
- 金額一致

### 3. 繳卡費

```bash
python test_local.py "繳卡費 15000"
```

預期：
- 交易類型為「轉帳／收入」
- 方向為「帳戶 → 信用卡」

### 4. 錯誤情境

```bash
python test_local.py "提款"
```

預期：
- 回傳錯誤訊息提示缺少金額
