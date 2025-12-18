# 進度紀錄（重啟友善版）

## 重啟指南（下次從這裡開始）
- 先確認單元/整合測試：`uv run pytest`
- 確認 tests lint（已用 ruff 修過）：`uv tool run ruff check tests`
- 確認 suites 設定/篩選（不呼叫 OpenAI）：`./run_tests.sh --all --list`
- 需要測「修改上一筆」分類驗證時（會呼叫 OpenAI）：`uv run python test_local.py --full --user test_local_user "<訊息>"`

## 目前狀態
- 測試重構已完成：runner + suites（JSONL、expected v2）可用於回歸；pytest 全套可跑。
- `update_last_entry` 已加入「分類不新建」保護：短分類會解析成既有分類路徑，未知/新分類會拒絕；並以原始訊息抽取分類做驗證，避免 GPT 轉寫繞過。

## 已完成（里程碑）
- Functional runner：`run_tests.sh`（`--suite/--all/--smoke/--only/--list/--auto`），執行前會驗 suite JSONL schema
- Functional suites：`tests/functional/suites/*.jsonl`（expected v2 typed；見 `specs/004-prompt-refactor/expected_v2.md`）
- pytest：`tests/` 分層與 markers 正規化；共用 helpers/fixtures 已抽出；全套 pytest 已可跑
- `test_local.py`：支援 `--full/--raw/--kv/--clear`，且 dry-run 也會執行 `update_last_entry` 驗證流程
- `update_last_entry` 分類驗證：新增 `app/category_resolver.py` + 在 `app/line_handler.py` 內驗證/正規化分類
- GPT 輸出穩定性補強：付款方式在程式端做正規化（避免暱稱），並調整部分 functional suites 的錯誤訊息比對更穩健（commit: `1fda8cc`）

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

## 接下來要做什麼（從 plan.md 推導）
1. 信息盤點（必要性/分類/代墊/專案）：整理必填欄位、預設值、關鍵字映射與 few-shot 覆蓋範圍
2. Prompt 重構：重寫 `app/prompts.py`（降低 token、提高欄位準確；用現有 suites 回歸）
3. Schema 更新：`app/schemas.py` 的 `items` 增加 `專案`（並確保 runner/解析/對外 webhook 一致）
4. 擴充 functional cases：補外幣、多項、代墊錯誤、專案預設等案例（依 `expected_v2.md` 編寫）
5. 風險檢查與 baseline：跑 `./run_tests.sh --smoke --all --auto`，必要時再跑 full regression
6.（可選）補純離線 `--validate`：CI 只做 suites JSONL/schema/id 檢查，不呼叫 OpenAI
