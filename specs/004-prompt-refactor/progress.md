# 進度紀錄（測試重構階段）

## 狀態
- 已完成測試入口、runner 穩定性修正、functional suites 資料結構化與 tests 目錄分層，但尚未在可連網環境下執行完整回歸（會呼叫 OpenAI）。

## 已完成變更（摘要）
- 新增統一測試入口：`run_tests.sh`
- suites（功能分類，改為 JSONL，避免 `|` 欄位位移）：
  - `tests/functional/suites/expense.jsonl`
  - `tests/functional/suites/date.jsonl`
  - `tests/functional/suites/multi_expense.jsonl`
  - `tests/functional/suites/advance_payment.jsonl`
- legacy shim：
  - `run_v1_tests.sh` → `--suite expense`
  - `run_v15_tests.sh` → `--suite multi_expense`
  - `run_v17_tests.sh` → `--suite advance_payment`
- runner 介面：
  - `--only` 支援 regex（包含 `|`）與多次 `--only`（OR 合併）
  - `--list/--dry-run`：只列出匹配案例（不呼叫 OpenAI）
  - `--debug`：失敗時輸出 debug 資訊（協助排查解析/比對）
- 解析依賴：`jq` 必備（缺少會直接報錯提示安裝）
- 調整案例分組：
  - 移除「向後相容」概念：每個 suite 只測該功能
  - 移除重複案例：刪除 `TC-V15-032`，保留 `expense` 的 `TC-V17-015`
  - 新增 `date` suite，並加入 `TC-DATE-006`（日期+時間，時間先不比對）
- `test_local.py`：
  - 新增 `--raw`：單次測試只輸出 JSON（runner 不需解析人類可讀輸出）
  - CLI 改用 argparse，`--help` 可直接查參數用途
  - 移除版本切換概念（統一使用同一套解析）
- tests 目錄分層：
  - `tests/unit/`、`tests/integration/`、`tests/functional/`、`tests/docs/`
  - `pytest.ini` 更新 `testpaths` 並加入 `pythonpath=.`（`import app.*` 可用）

## 待驗證（尚未執行）
> 以下命令會觸發 GPT 呼叫；需環境可連網、並具備必要環境變數（如 OpenAI key）。

### 0) 依賴檢查
- `jq --version`

### 1) dry-run / list（不需連網，先確認 filter 匹配正確）
- `./run_tests.sh --suite expense --list --only 'TC-V1-001|TC-V17-015'`
- `./run_tests.sh --suite date --list --only 'TC-DATE-003|TC-DATE-006'`
- `./run_tests.sh --suite multi_expense --list --only 'TC-V15-010|TC-V15-030'`
- `./run_tests.sh --suite advance_payment --list --only 'TC-V17-001|TC-V17-005|TC-V17-010'`

### 2) smoke（建議先跑）
- `./run_tests.sh --suite expense --auto --only 'TC-V1-001|TC-V17-015'`
- `./run_tests.sh --suite date --auto --only 'TC-DATE-003|TC-DATE-006'`
- `./run_tests.sh --suite multi_expense --auto --only 'TC-V15-010|TC-V15-030'`
- `./run_tests.sh --suite advance_payment --auto --only 'TC-V17-001|TC-V17-005|TC-V17-010'`

### 3) full regression（確認 baseline）
- `./run_tests.sh --suite expense --auto`
- `./run_tests.sh --suite date --auto`
- `./run_tests.sh --suite multi_expense --auto`
- `./run_tests.sh --suite advance_payment --auto`

## 已知限制（目前設計）
- `transaction_id` 不比對（非決定性）
- `date` 比對使用 `{YEAR}` 佔位（由執行當下年份展開）
- `TC-DATE-006` 目前只驗證日期，不驗證時間（因程式端尚未明確支援時間提取/回填）

## 後續預計重構（建議）
- Functional cases：將 `tests/docs/test_cases_v1*.md` 逐步改成指向 JSONL suites（或淘汰舊版文件），避免維護兩套案例來源。
- Functional runner：補上 JSON schema 驗證（或 `jq` 檢查）在執行前驗證每筆 JSONL 欄位完整性。
- Suite 規格：將 `expected` 欄位從「一律攤平」改為針對 intent 分型（例如 `intent=錯誤` 只允許 `error_contains`），降低誤填欄位機率。
- 文件：更新 `tests/README.md` 的「v1/v1.5」殘留文字（如仍存在），統一以 suite 名稱（expense/multi_expense/date/advance_payment）描述。
