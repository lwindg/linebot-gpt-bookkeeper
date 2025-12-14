# Test Script Integration Implementation Plan (Functional Suites)

## Goals
- Consolidate the existing version-split scripts (`run_v*_tests.sh`) into a single entrypoint driven by functional suites.
- Provide a consistent CLI and auto/manual modes to support regression testing during Prompt/Schema refactors.
- Standardize parsing on JSON via `jq` as a required dependency (fail fast with install instructions if missing).

## Scope
- Add: `run_tests.sh` (single entrypoint)
- Add: suite case files (functional grouping)
- Change: `run_v1_tests.sh` / `run_v15_tests.sh` / `run_v17_tests.sh` into shims that delegate to `run_tests.sh`
- Do not change: the existing test cases (messages and expectations remain identical initially to establish a baseline)

## Suite Mapping
- `expense`: single-item / basic fields (item, amount, payment method, category, intent/conversation)
- `multi_expense`: multi-item behavior (item count, shared payment method, error handling)
- `advance_payment`: advance-payment behaviors (status, recipient, NA payment rules, date extraction, multi-item integration)

## CLI (run_tests.sh)
- `./run_tests.sh --suite <expense|multi_expense|advance_payment>`
- Optional flags:
  - `--auto` (default: off)
  - `--manual` (default)
  - `--only <pattern>` (regex filter on test id/name/message)
  - `--help`

## Dependencies & Failure Strategy
- Required: `jq`
  - Startup check: if `command -v jq` fails, exit (code 2) with install hints:
    - macOS: `brew install jq`
    - Ubuntu/Debian: `sudo apt-get install -y jq`
- No grep fallback (avoid inconsistent parsing and false positives).

## Data Layout (Proposed)
- `tests/suites/expense.sh`
- `tests/suites/multi_expense.sh`
- `tests/suites/advance_payment.sh`

Each suite file only defines test cases (data), e.g. (concept):
- `TEST_CASES+=("TC-EXP-001|Category|Description|Message|ExpectedIntent|...")`

All parsing/comparison logic lives in `run_tests.sh`, not in suite files.

## Unified Field Abstraction & Comparison Rules
- Common fields:
  - `intent` (from emoji output, or derived from JSON when available)
  - `item_count` (entries/items length)
  - `payment` (shared or single payment)
  - `item` (single item or entries[0])
  - `amount` (numeric)
  - `category` (allow partial match where appropriate)
  - `advance_status`
  - `recipient`
  - `error_message` (substring match)
- Not compared:
  - `transaction_id` (non-deterministic)

## Legacy Script Shim Strategy
- Keep filenames to preserve usage patterns, but delegate:
  - `run_v1_tests.sh` → `./run_tests.sh --suite expense` (translate `--auto`)
  - `run_v15_tests.sh` → `./run_tests.sh --suite multi_expense`
  - `run_v17_tests.sh` → `./run_tests.sh --suite advance_payment` (translate `--only`)
- Shims should not embed cases or parsing logic.

## Baseline Verification
1) Bring up the new entrypoint with a small smoke subset (1–2 cases per suite) to validate CLI/parsing/stats.
2) After migrating all cases, run:
   - `./run_tests.sh --suite expense --auto`
   - `./run_tests.sh --suite multi_expense --auto`
   - `./run_tests.sh --suite advance_payment --auto --only <pattern>`
3) Compare against the legacy scripts using the same field abstraction (ignoring transaction ids).

## Risks & Mitigations
- `jq` missing → fail fast with clear install instructions.
- Non-deterministic GPT output → only compare stable fields; avoid transaction ids.
- Output format differences (entries vs single, shared vs single payment) → handle centrally in the abstraction layer.
