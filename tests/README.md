# 測試指南

本目錄包含測試案例與測試工具。

---

## 📋 測試文件

### 測試案例文件

- **`test_cases_v1.md`** - v1 MVP 測試案例（60+ 個測試案例）
- **`test_cases_v1.5.md`** - v1.5.0 測試案例（50+ 個測試案例）

### 單元測試文件

- **`test_multi_expense.py`** - v1.5.0 多項目支出單元測試
  - 單項目記帳（向後相容）
  - 多項目記帳（核心功能）
  - 共用付款方式驗證
  - 錯誤處理與邊界案例
  - 對話意圖識別
  - 複雜場景測試

- **`test_webhook_batch.py`** - Webhook 批次發送單元測試
  - send_multiple_webhooks() 函式測試
  - 批次發送成功/失敗處理
  - 共用交易ID驗證
  - 順序發送驗證
  - 錯誤處理

---

## 🛠️ 測試工具

### 1. 互動式測試工具 - `test_local.py`

Located at repo root. No version switching; it always runs the unified parser.

#### 使用方式

```bash
# Interactive mode
python test_local.py

# Single-run mode (human-readable output)
python test_local.py '早餐80元，午餐150元，現金'

# Single-run mode (raw JSON only; for automated runners)
python test_local.py --raw '11/12 午餐120元現金'
```

#### 互動模式指令

- 直接輸入測試訊息
- `json` - 切換 JSON 顯示
- `exit` / `quit` - 離開

---

### 2. 自動化測試腳本（支援自動判斷）

位於專案根目錄，提供人工檢視和自動驗證兩種模式。

#### v1 測試腳本

```bash
# 人工判斷模式（預設，逐個檢視結果）
./run_v1_tests.sh

# 自動判斷模式（快速驗證所有測試）
./run_v1_tests.sh --auto

# 顯示說明
./run_v1_tests.sh --help
```

**包含測試**：
- 基本功能：3 個測試
- 日期處理：5 個測試
- 付款方式：6 個測試
- 品項分類：7 個測試
- 自然語句：3 個測試
- 對話意圖：3 個測試
- 錯誤處理：3 個測試
- **總計：30 個測試**

**自動判斷項目**：
- ✅ 意圖、品項、金額、付款方式、分類
- ❌ 交易ID（每次都不同）

#### v1.5.0 測試腳本

```bash
# 人工判斷模式（預設，逐個檢視結果）
./run_v15_tests.sh

# 自動判斷模式（快速驗證所有測試）
./run_v15_tests.sh --auto

# 顯示說明
./run_v15_tests.sh --help
```

**包含測試**：
- 向後相容：3 個測試
- 多項目核心功能：6 個測試
- 共用驗證：3 個測試
- 錯誤處理：6 個測試
- 對話意圖：3 個測試
- 複雜場景：2 個測試
- **總計：23 個測試**

**自動判斷項目**：
- ✅ 意圖、項目數量、共用付款方式、錯誤訊息
- ❌ 交易ID（每次都不同）

**詳細使用說明**：參見專案根目錄的 `AUTO_TEST_GUIDE.md`

---

## 🎯 測試執行流程

### 方法 1：自動驗證測試（推薦用於回歸測試）

適合快速驗證所有功能，特別是修改 prompt 後。

```bash
# v1 自動測試
./run_v1_tests.sh --auto

# v1.5.0 自動測試
./run_v15_tests.sh --auto
```

**優點**：
- 快速執行所有測試
- 自動比對結果
- 統計通過率
- 顯示詳細差異

### 方法 2：人工檢視測試（推薦用於初次驗證）

適合逐個檢視測試結果，確保理解測試意圖。

```bash
# v1 人工測試
./run_v1_tests.sh

# v1.5.0 人工測試
./run_v15_tests.sh
```

每個測試案例會逐個執行，按 Enter 查看下一個測試。

### 方法 3：互動式測試（推薦用於調試）

適合快速驗證特定功能。

```bash
python test_local.py
```

然後依照測試案例文件逐個輸入測試。

### 方法 4：單次快速測試

適合驗證特定功能。

```bash
# 測試多項目功能
python test_local.py '早餐80元，午餐150元，現金'

# 測試錯誤處理
python test_local.py '早餐80元現金，午餐150元刷卡'
```

### 方法 5：單元測試（推薦用於 CI/CD）

適合自動化測試和持續整合。

```bash
# 執行所有單元測試
pytest

# 執行特定測試文件
pytest tests/test_multi_expense.py
pytest tests/test_webhook_batch.py

# 詳細輸出模式
pytest -v

# 執行特定測試類別
pytest tests/test_multi_expense.py::TestMultiExpenseMultipleItems

# 執行特定測試函式
pytest tests/test_multi_expense.py::TestMultiExpenseSingleItem::test_single_item_standard_format

# 顯示測試覆蓋率（需安裝 pytest-cov）
pytest --cov=app --cov-report=html
```

**注意**：單元測試需要設置 `.env` 文件或環境變數才能執行。

---

## ✅ 測試檢查清單

### v1 MVP 驗證重點

- [ ] 單項目記帳正確處理
- [ ] 付款方式暱稱正確轉換（狗卡→台新狗卡）
- [ ] 語義化日期正確解析（昨天、今天）
- [ ] 品項分類符合規則（點心→家庭／點心）
- [ ] 自然語句流暢處理
- [ ] 對話意圖正確識別
- [ ] 錯誤提示清晰友善

### v1.5.0 驗證重點

#### 核心功能
- [ ] 單項目記帳正常運作（向後相容 v1）
- [ ] 雙項目記帳正確處理
- [ ] 三項目及以上記帳正確處理
- [ ] 所有項目共用交易ID
- [ ] 所有項目共用付款方式
- [ ] 所有項目共用日期

#### 錯誤處理
- [ ] 不同付款方式被拒絕
- [ ] 缺少金額被提示
- [ ] 缺少付款方式被提示
- [ ] 缺少品項名稱被提示
- [ ] 模糊情況（「和」連接詞）被拒絕

#### 輸出格式
- [ ] 單項目使用 v1 格式顯示
- [ ] 多項目使用 v1.5.0 格式顯示
- [ ] 項目編號正確（#1, #2, ...）
- [ ] 共用資訊正確標註

---

## 📊 關鍵差異：v1 vs v1.5.0

| 特性 | v1 MVP | v1.5.0 |
|------|--------|--------|
| 單項目記帳 | ✅ | ✅（向後相容）|
| 多項目記帳 | ❌ | ✅ |
| 共用交易ID | N/A | ✅ |
| 共用付款方式 | N/A | ✅ |
| 錯誤處理 | 基本 | 增強（多種付款方式、模糊情況）|
| 顯示格式 | 單項目 | 單項目 + 多項目列表 |

---

## 🐛 常見問題排查

### 問題 1：import 錯誤

```bash
ModuleNotFoundError: No module named 'app'
```

**解決方式**：確保在專案根目錄執行測試
```bash
cd /home/user/linebot-gpt-bookkeeper
python test_local.py
```

### 問題 2：API Key 未設定

```bash
Error: OPENAI_API_KEY not found
```

**解決方式**：檢查 `.env` 文件或環境變數
```bash
# 檢查環境變數
echo $OPENAI_API_KEY

# 或檢查 .env 文件
cat .env | grep OPENAI_API_KEY
```

### 問題 3：測試腳本無法執行

```bash
Permission denied: ./run_v1_tests.sh
```

**解決方式**：添加可執行權限
```bash
chmod +x run_v1_tests.sh run_v15_tests.sh
```

---

## 📝 測試報告建議

執行完測試後，建議記錄：

1. **測試日期和版本**
2. **通過的測試案例數量**
3. **失敗的測試案例和原因**
4. **發現的 Bug 或異常行為**
5. **建議的改進方向**

---

**更新日期**：2025-11-15
**版本**：v1.5.0 Testing Guide
