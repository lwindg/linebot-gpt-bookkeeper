# 測試指南

本目錄包含單元測試、整合測試、功能回歸（functional suites）與測試文件。

---

## 📦 目錄結構

- `tests/unit/`: 單元測試（pytest）
- `tests/integration/`: 整合測試（pytest，跨模組流程）
- `tests/functional/`: 功能回歸測試資料（由 `./run_tests.sh` 執行）
- `tests/docs/`: 測試文件與案例（人工參考）

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

#### Functional suite runner (source of truth)

```bash
# Manual mode (default)
./run_tests.sh --suite expense
./run_tests.sh --suite multi_expense
./run_tests.sh --suite advance_payment
./run_tests.sh --suite date
./run_tests.sh --suite update_intent

# Run all suites
./run_tests.sh --all

# Smoke subset (per-suite)
./run_tests.sh --smoke --all
./run_tests.sh --suite expense --smoke

# Auto compare (requires OpenAI)
./run_tests.sh --suite expense --auto
./run_tests.sh --suite multi_expense --auto
./run_tests.sh --suite advance_payment --auto
./run_tests.sh --suite date --auto
./run_tests.sh --suite update_intent --auto
./run_tests.sh --suite update_intent --auto

# Auto compare smoke subset (requires OpenAI)
./run_tests.sh --smoke --all --auto

# List-only (offline, no OpenAI calls)
./run_tests.sh --suite expense --list
./run_tests.sh --suite multi_expense --list
./run_tests.sh --suite advance_payment --list
./run_tests.sh --suite date --list
./run_tests.sh --suite update_intent --list

# List-only smoke subset
./run_tests.sh --smoke --all --list
```

**Suites**:
- `expense`: single expense + conversation + core capability cases
- `multi_expense`: multiple expenses (and related error handling)
- `advance_payment`: advance payment tracking
- `date`: date extraction / normalization
- `update_intent`: update intent parsing and validation

**Comparison notes**:
- `transaction_id` is not compared (non-deterministic)
- `date` supports `{YEAR}` placeholder (expanded at runtime)

**詳細使用說明**：參見 `docs/AUTO_TEST_GUIDE.md`

---

## 🎯 測試執行流程

### 方法 1：自動驗證測試（推薦用於回歸測試）

適合快速驗證所有功能，特別是修改 prompt 後。

```bash
./run_tests.sh --suite expense --auto
./run_tests.sh --suite multi_expense --auto
./run_tests.sh --suite advance_payment --auto
./run_tests.sh --suite date --auto
```

**優點**：
- 快速執行所有測試
- 自動比對結果
- 統計通過率
- 顯示詳細差異

### 方法 2：人工檢視測試（推薦用於初次驗證）

適合逐個檢視測試結果，確保理解測試意圖。

```bash
./run_tests.sh --suite expense
./run_tests.sh --suite multi_expense
./run_tests.sh --suite advance_payment
./run_tests.sh --suite date
./run_tests.sh --suite update_intent
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
# Run all unit tests
uv run pytest

# Run specific test files
uv run pytest tests/unit/test_multi_expense.py
uv run pytest tests/unit/test_webhook_batch.py

# Verbose
uv run pytest -v

# Run a single class
uv run pytest tests/unit/test_multi_expense.py::TestMultiExpenseMultipleItems

# Run a single test
uv run pytest tests/unit/test_multi_expense.py::TestMultiExpenseSingleItem::test_single_item_standard_format

# 顯示測試覆蓋率（需安裝 pytest-cov）
uv run pytest --cov=app --cov-report=html
```

**注意**：單元測試需要設置 `.env` 文件或環境變數才能執行。

---

## ✅ 測試檢查清單

### expense suite 驗證重點

- [ ] 單項目記帳正確處理
- [ ] 付款方式暱稱正確轉換（狗卡→台新狗卡）
- [ ] 語義化日期正確解析（昨天、今天）
- [ ] 品項分類符合規則（點心→家庭／點心）
- [ ] 自然語句流暢處理
- [ ] 對話意圖正確識別
- [ ] 錯誤提示清晰友善

### multi_expense suite 驗證重點

#### 核心功能
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
- [ ] Functional suites compare extracted JSON fields (intent/item/amount/payment/...) rather than human-readable formatting
- [ ] Multi-entry shared fields behave consistently (date/payment/transaction_id rules)

---

## 📊 Suite coverage

- `expense`: single expense + conversation + core capability cases
- `multi_expense`: multi-item expense + validation errors
- `advance_payment`: advance payment tracking
- `date`: date extraction / normalization

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
Permission denied: ./run_tests.sh
```

**解決方式**：添加可執行權限
```bash
chmod +x run_tests.sh
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

**更新日期**：2025-12-16
**版本**：functional suites testing guide
