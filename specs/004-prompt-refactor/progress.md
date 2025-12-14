# 進度紀錄（測試重構階段）

## 狀態
- 已完成測試入口與 suite 架構重構，但尚未在可連網環境下執行完整回歸（會呼叫 OpenAI）。

## 已完成變更（摘要）
- 新增統一測試入口：`run_tests.sh`
- suites（功能分類）：
  - `tests/suites/expense.sh`
  - `tests/suites/date.sh`
  - `tests/suites/multi_expense.sh`
  - `tests/suites/advance_payment.sh`
- legacy shim：
  - `run_v1_tests.sh` → `--suite expense`
  - `run_v15_tests.sh` → `--suite multi_expense`
  - `run_v17_tests.sh` → `--suite advance_payment`
- 解析依賴：`jq` 必備（缺少會直接報錯提示安裝）
- 調整案例分組：
  - 移除「向後相容」概念：每個 suite 只測該功能
  - 移除重複案例：刪除 `TC-V15-032`，保留 `expense` 的 `TC-V17-015`
  - 新增 `date` suite，並加入 `TC-DATE-006`（日期+時間，時間先不比對）

## 待驗證（尚未執行）
> 以下命令會觸發 GPT 呼叫；需環境可連網、並具備必要環境變數（如 OpenAI key）。

### 0) 依賴檢查
- `jq --version`

### 1) smoke（建議先跑）
- `./run_tests.sh --suite expense --auto --only "TC-V1-001|TC-V17-015"`
- `./run_tests.sh --suite date --auto --only "TC-DATE-003|TC-DATE-006"`
- `./run_tests.sh --suite multi_expense --auto --only "TC-V15-010|TC-V15-030"`
- `./run_tests.sh --suite advance_payment --auto --only "TC-V17-001|TC-V17-005|TC-V17-010"`

### 2) full regression（確認 baseline）
- `./run_tests.sh --suite expense --auto`
- `./run_tests.sh --suite date --auto`
- `./run_tests.sh --suite multi_expense --auto`
- `./run_tests.sh --suite advance_payment --auto`

## 已知限制（目前設計）
- `transaction_id` 不比對（非決定性）
- `date` 比對使用 `{YEAR}` 佔位（由執行當下年份展開）
- `TC-DATE-006` 目前只驗證日期，不驗證時間（因程式端尚未明確支援時間提取/回填）

