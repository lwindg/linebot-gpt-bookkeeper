# 進度紀錄（測試重構階段）

## 狀態
- smoke 已通過、依賴確認無誤；full regression 先暫緩（會呼叫 OpenAI）。
- 已補強 suites 文件一致性與 runner 的 JSONL schema 驗證（可在離線模式提前擋錯）。
- 已完成 `expected` v2 分型並遷移四個 suites；runner 已移除 v1 fallback（只接受 v2）。
- 已新增 `--all` 與 `--smoke` 便於快速回歸與全量回歸。

## 已完成變更（摘要）
- 新增統一測試入口：`run_tests.sh`
- pytest 整頓（已完成）：
  - 自動依路徑標記 `unit/integration`（`tests/conftest.py`）
  - 移除未使用的 legacy markers（`v1/v15`）
  - 移除測試檔內 `__main__` 直跑入口（統一用 `uv run pytest`）
  - 已提交：`refactor(tests): normalize pytest markers`（commit: `60e7844`）
  - 已提交：`refactor(tests): remove unused imports`（commit: `505950e`）
  - 已提交：`refactor(tests): add shared OpenAI mock helper`（commit: `0e2390f`）
  - 已提交：`refactor(tests): use shared OpenAI mock helper`（commit: `866c848`）
  - 已提交：`refactor(tests): split advance payment unit tests`（commit: `fcd9021`）
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
- 文件與 runner 一致性：
  - 更新 `tests/README.md` 與 `tests/docs/*`，統一以 suite 名稱描述（expense/multi_expense/date/advance_payment），並移除失效的版本切換說明。
  - `run_tests.sh` 新增 suite JSONL schema 驗證（JSON 格式、必要欄位/型別、`expected.date` 格式、`intent=錯誤` 必填錯誤訊息 contains、id 重複檢查）。
  - 已提交：`refactor(tests): validate suites and align docs`（commit: `3002bb7`）
- Suite `expected` v2 分型（已完成）：
  - v2 規格：`specs/004-prompt-refactor/expected_v2.md`
  - `run_tests.sh` 僅支援 v2（分型）並在執行前做 schema 驗證（依 intent 分型檢查）
  - 四個 suites 已遷移到 v2：`expense/multi_expense/advance_payment/date`
  - 已提交：`refactor(tests): type expected v2 and migrate suites`（commit: `efd5385`）
  - 已提交：`refactor(tests): remove v1 expected fallback`（commit: `f627c7b`）
  - 已提交：`feat(tests): add --all and --smoke runners`（commit: `f1620c6`）

## 待驗證（尚未執行）
> 以下命令會觸發 GPT 呼叫；需環境可連網、並具備必要環境變數（如 OpenAI key）。

### 0) 依賴檢查
- `jq --version`

### 1) dry-run / list（不需連網，先確認 filter 匹配正確）
- `./run_tests.sh --suite expense --list --only 'TC-V1-001|TC-V17-015'`
- `./run_tests.sh --suite date --list --only 'TC-DATE-003|TC-DATE-006'`
- `./run_tests.sh --suite multi_expense --list --only 'TC-V15-010|TC-V15-030'`
- `./run_tests.sh --suite advance_payment --list --only 'TC-V17-001|TC-V17-005|TC-V17-010'`
- `./run_tests.sh --smoke --all --list`

### 2) smoke（建議先跑）
- `./run_tests.sh --suite expense --auto --only 'TC-V1-001|TC-V17-015'`
- `./run_tests.sh --suite date --auto --only 'TC-DATE-003|TC-DATE-006'`
- `./run_tests.sh --suite multi_expense --auto --only 'TC-V15-010|TC-V15-030'`
- `./run_tests.sh --suite advance_payment --auto --only 'TC-V17-001|TC-V17-005|TC-V17-010'`
- `./run_tests.sh --smoke --all --auto`

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
- ✅ Functional cases：已將 `tests/docs/test_cases_v1*.md` 改為指向 JSONL suites（保留文件作為人工參考），避免維護兩套案例來源。
- ✅ Functional runner：已補上 suite JSONL schema 驗證，在執行前驗證每筆 JSONL 欄位完整性。
- ✅ 文件：已更新 `tests/README.md` 的「v1/v1.5」殘留文字，統一以 suite 名稱描述。
- ✅ Suite 規格：已將 `expected` 從「一律攤平」改為針對 intent 分型（維持 intent=記帳/對話/錯誤 三類），降低誤填欄位機率。

## 下一步（預計）
1. ✅ 已完成：v2 suites smoke 通過（會呼叫 OpenAI）。
2. ✅ 已完成：移除 runner 對 v1（攤平 expected）的 fallback 支援，避免長期維護兩套格式。
3.（可選）補一個純離線的 `--validate` 命令/腳本：只做 JSONL schema 驗證與 id 重複檢查，方便 CI 或 pre-commit。
4. pytest 測試整頓（部分完成）：已先完成 markers 正規化；其餘待辦為測試檔命名整理、處理空檔測試、抽共用 fixtures/helpers。
5. full regression baseline（可選，會呼叫 OpenAI）：`./run_tests.sh --all --auto`。

### 盤點結果（v1 實際用法摘要）
- `expense.jsonl`：`intent=記帳` 主要用 `item/amount/payment/category`；`intent=對話` 不比對欄位。
- `multi_expense.jsonl`：`intent=記帳` 主要用 `payment/item_count`；`intent=錯誤` 用 error message contains。
- `advance_payment.jsonl`：`intent=記帳` 主要用 `item/amount/payment/advance_status/recipient`（少量用 `item_count/date`）。
- `date.jsonl`：`intent=記帳` 主要用 `item/amount/payment/category/date`（少量用 `item_count`）。

### v2 規格草案
- 見 `specs/004-prompt-refactor/expected_v2.md`
