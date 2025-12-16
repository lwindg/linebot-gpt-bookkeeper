• 現況分類（tests/ 目錄）

  - 功能型（Functional suites，入口：`./run_tests.sh`）
      - Suites（JSONL，v2 typed `expected`）：
          - `tests/functional/suites/expense.jsonl`
          - `tests/functional/suites/multi_expense.jsonl`
          - `tests/functional/suites/date.jsonl`
          - `tests/functional/suites/advance_payment.jsonl`
      - Runner features：
          - `--suite <name>` / `--all`：跑單一或全部 suites
          - `--smoke`：跑各 suite 的 smoke 子集合
          - `--list`：離線列出匹配案例（不呼叫 OpenAI）
          - `--auto`：自動比對（會呼叫 OpenAI）
      - 優點：接近真實使用者輸入、資料結構化、可在離線先做 schema 驗證；缺點：完整回歸需要可連網環境（OpenAI）。
  - pytest 單元/整合測試（入口：`uv run pytest`）
      - 已分層：`tests/unit/`、`tests/integration/`
      - 仍有待整理：命名/markers 正規化、抽共用 fixtures、處理空檔測試。

  ———

  重構建議（依優先級）

  1. ✅ 把測試分層放進子目錄（降低混雜）

  - tests/unit/：純函式/類別單元測試（現在多數 test_*.py）
  - tests/integration/：跨模組流程（例如 test_multi_currency.py、test_edit_last_transaction.py）
  - tests/functional/：run_tests.sh suites（JSONL）
  - tests/docs/：test_cases_*.md、TEST_GUIDE_*.md

  2. ✅ Functional suite 的資料格式改成結構化（避免再發生欄位位移）

  - 已改為 `tests/functional/suites/*.jsonl`（每行一個 JSON）。
  - `expected` 已改為 v2 分型（`bookkeeping`/`error`/`conversation`），並移除 v1 fallback（避免維護兩套格式）。
  - `run_tests.sh` 負責「讀 case → 呼叫 `test_local.py --raw` → assertions」，case 本身不放解析邏輯。

  3. pytest 測試命名與 marker 正規化（未完成）

  - 用 marker 明確區分：unit、integration、functional、requires_network（即使目前都 mock，也把規則寫清楚）
  - 把 tests/test_multi_currency.py 明確改名成 tests/integration/test_multi_currency_e2e.py（它是流程整合，不是 unit）
  - 移除空檔 tests/test_integration.py、tests/test_webhook_sender.py（或補上真正測試）

  4. 抽共用的 mock/fixture（降低大量重複 JSON 字串）（未完成）

  - 建議新增 tests/helpers/：
      - openai_fixtures.py：產生 mock completion（減少每個測試都手寫三層 Mock）
      - gpt_json_fixtures.py：常見 GPT 回傳模板（items/payment_method/error 等）
  - 對 test_multi_expense.py / test_gpt_processor.py 這類檔案效益最大。

  5. ✅ 文件同步清理（避免誤導）

  - 已改成以 suite/功能命名（expense/multi_expense/advance_payment/date）並指向 `run_tests.sh` + `test_local.py --raw`。

  下一步若要繼續清理測試維護成本，建議先做：
  - (3) pytest markers + 命名整理（讓 CI/本機跑法更清楚）
  - (4) fixtures/helpers 抽取（降低大量重複 mock）
