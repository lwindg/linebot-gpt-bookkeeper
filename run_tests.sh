#!/usr/bin/env bash
set -euo pipefail

# Unified local test runner (functional suites)
# Requires: jq

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AUTO_MODE=false
SUITE=""
ONLY_PATTERN=""
SMOKE_ONLY_PATTERN=""
LIST_MODE=false
DEBUG_MODE=false
ALL_MODE=false
SMOKE_MODE=false

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

usage() {
  cat <<'EOF'
Unified test runner (functional suites)

Usage:
  ./run_tests.sh --suite <expense|multi_expense|advance_payment|date|cashflow> [--auto|--manual] [--only <pattern>] [--smoke] [--list]
  ./run_tests.sh --all [--auto|--manual] [--only <pattern>] [--smoke] [--list]

Options:
  --suite <name>    Suite name: expense, multi_expense, advance_payment, date, cashflow
  --all             Run all suites (expense, multi_expense, advance_payment, date, cashflow)
  --auto            Auto-compare expected vs actual (default: manual)
  --manual          Manual mode (default)
  --only <pattern>  Run only tests whose id/name/message matches regex
  --smoke           Run a small smoke subset per suite (can be combined with --suite/--all)
  --list            List matched tests and exit (no OpenAI calls)
  --debug           Print debug info on failures
  --help, -h        Show this help

Notes:
  - Requires jq. If missing, the script exits with install hints.
  - transaction_id is not compared (non-deterministic).
  - If your pattern contains '|', quote it to avoid shell piping:
      --only 'TC-V1-001|TC-V17-015'
EOF
}

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq is required but not installed." >&2
    echo "Install:" >&2
    echo "  macOS: brew install jq" >&2
    echo "  Ubuntu/Debian: sudo apt-get install -y jq" >&2
    exit 2
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --suite)
        SUITE="${2:-}"
        shift 2
        ;;
      --all)
        ALL_MODE=true
        shift
        ;;
      --auto)
        AUTO_MODE=true
        shift
        ;;
      --manual)
        AUTO_MODE=false
        shift
        ;;
      --smoke)
        SMOKE_MODE=true
        shift
        ;;
      --only)
        # Supports multiple --only flags by OR-ing patterns.
        local new_pattern="${2:-}"
        if [[ -z "$ONLY_PATTERN" ]]; then
          ONLY_PATTERN="$new_pattern"
        else
          ONLY_PATTERN="(${ONLY_PATTERN})|(${new_pattern})"
        fi
        shift 2
        ;;
      --list|--dry-run)
        LIST_MODE=true
        shift
        ;;
      --debug)
        DEBUG_MODE=true
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        echo "Unknown argument: $1" >&2
        echo "" >&2
        usage >&2
        exit 2
        ;;
    esac
  done

  if [[ "$ALL_MODE" == true ]] && [[ -n "$SUITE" ]]; then
    echo "Error: --all cannot be used with --suite" >&2
    echo "" >&2
    usage >&2
    exit 2
  fi

  if [[ "$ALL_MODE" == false ]] && [[ -z "$SUITE" ]]; then
    echo "Error: --suite or --all is required" >&2
    echo "" >&2
    usage >&2
    exit 2
  fi
}

should_run_case() {
  local tc_id="$1" tc_group="$2" tc_name="$3" tc_message="$4"
  local haystack
  haystack="$tc_id $tc_group $tc_name $tc_message"

  if [[ -n "$SMOKE_ONLY_PATTERN" ]]; then
    printf '%s\n' "$haystack" | grep -qE -- "$SMOKE_ONLY_PATTERN" || return 1
  fi

  if [[ -n "$ONLY_PATTERN" ]]; then
    printf '%s\n' "$haystack" | grep -qE -- "$ONLY_PATTERN" || return 1
  fi

  return 0
}

suite_path() {
  case "$SUITE" in
    expense) echo "tests/functional/suites/expense.jsonl" ;;
    multi_expense) echo "tests/functional/suites/multi_expense.jsonl" ;;
    advance_payment) echo "tests/functional/suites/advance_payment.jsonl" ;;
    date) echo "tests/functional/suites/date.jsonl" ;;
    cashflow) echo "tests/functional/suites/cashflow_intents.jsonl" ;;
    *)
      echo "Error: unknown suite: $SUITE" >&2
      exit 2
      ;;
  esac
}

smoke_pattern_for_suite() {
  case "$1" in
    expense) echo 'TC-V1-001|TC-V17-015' ;;
    date) echo 'TC-DATE-003|TC-DATE-006' ;;
    multi_expense) echo 'TC-V15-010|TC-V15-030' ;;
    advance_payment) echo 'TC-V17-001|TC-V17-005|TC-V17-010' ;;
    cashflow) echo 'TC-CF-001|TC-CF-003' ;;
    *) echo "" ;;
  esac
}

validate_suite_jsonl() {
  local suite_file="$1"

  local line_num=0
  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    ((line_num+=1))
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue

    if ! echo "$line" | jq -e . >/dev/null 2>&1; then
      echo "Error: invalid JSON at $suite_file:$line_num" >&2
      echo "Line: $line" >&2
      exit 2
    fi

    if ! echo "$line" | jq -e '
      type == "object"
      and (.id | type == "string" and length > 0)
      and (.group | type == "string" and length > 0)
      and (.name | type == "string" and length > 0)
      and (.message | type == "string" and length > 0)
      and (.expected | type == "object")
      and (.expected.intent | type == "string" and length > 0)
    ' >/dev/null 2>&1; then
      echo "Error: invalid test case schema at $suite_file:$line_num" >&2
      echo "Line: $line" >&2
      exit 2
    fi

    local expected_intent
    expected_intent="$(jq -r '.expected.intent' <<<"$line")"

    local has_bookkeeping has_error has_conversation
    has_bookkeeping="$(jq -r '.expected | has("bookkeeping")' <<<"$line")"
    has_error="$(jq -r '.expected | has("error")' <<<"$line")"
    has_conversation="$(jq -r '.expected | has("conversation")' <<<"$line")"

    case "$expected_intent" in
      記帳|現金流)
        if [[ "$has_bookkeeping" != "true" ]]; then
          echo "Error: expected.bookkeeping is required when expected.intent is 記帳/現金流 at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        if [[ "$has_error" == "true" || "$has_conversation" == "true" ]]; then
          echo "Error: expected.error/conversation is not allowed when expected.intent is 記帳/現金流 at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        if ! echo "$line" | jq -e '
          (.expected.bookkeeping | type == "object")
          and ((.expected.bookkeeping.item? // "" ) | type == "string")
          and ((.expected.bookkeeping.amount? // "" ) | type == "string")
          and ((.expected.bookkeeping.payment? // "" ) | type == "string")
          and ((.expected.bookkeeping.category? // "" ) | type == "string")
          and ((.expected.bookkeeping.project? // "" ) | type == "string")
          and ((.expected.bookkeeping.item_count? // "" ) | type == "string")
          and ((.expected.bookkeeping.advance_status? // "" ) | type == "string")
          and ((.expected.bookkeeping.recipient? // "" ) | type == "string")
          and ((.expected.bookkeeping.date? // "" ) | type == "string")
        ' >/dev/null 2>&1; then
          echo "Error: invalid expected.bookkeeping schema at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi

        local expected_date
        expected_date="$(jq -r '.expected.bookkeeping.date // empty' <<<"$line")"
        if [[ -n "$expected_date" ]] && [[ ! "$expected_date" =~ ^(\{YEAR\}-|[0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
          echo "Error: invalid expected.bookkeeping.date (must be YYYY-MM-DD or {YEAR}-MM-DD) at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        ;;
      錯誤)
        if [[ "$has_error" != "true" ]]; then
          echo "Error: expected.error is required when expected.intent is 錯誤 at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        if [[ "$has_bookkeeping" == "true" || "$has_conversation" == "true" ]]; then
          echo "Error: expected.bookkeeping/conversation is not allowed when expected.intent is 錯誤 at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        if ! echo "$line" | jq -e '(.expected.error | type == "object") and (.expected.error.contains | type == "string" and length > 0)' >/dev/null 2>&1; then
          echo "Error: expected.error.contains must be a non-empty string at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        ;;
      對話)
        if [[ "$has_bookkeeping" == "true" || "$has_error" == "true" ]]; then
          echo "Error: expected.bookkeeping/error is not allowed when expected.intent is 對話 at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        if [[ "$has_conversation" == "true" ]] && ! echo "$line" | jq -e '(.expected.conversation | type == "object")' >/dev/null 2>&1; then
          echo "Error: expected.conversation must be an object at $suite_file:$line_num" >&2
          echo "Line: $line" >&2
          exit 2
        fi
        ;;
      *)
        echo "Error: invalid expected.intent at $suite_file:$line_num (must be 記帳/現金流/對話/錯誤)" >&2
        echo "Line: $line" >&2
        exit 2
        ;;
    esac
  done <"$suite_file"

  local dup_ids
  dup_ids="$(
    jq -Rr 'select(length > 0 and (startswith("#") | not)) | (fromjson? // empty) | .id // empty' "$suite_file" \
      | sort \
      | uniq -d
  )"
  if [[ -n "$dup_ids" ]]; then
    echo "Error: duplicate test case id(s) found in $suite_file:" >&2
    echo "$dup_ids" >&2
    exit 2
  fi
}

extract_json_block() {
  # Extract JSON block printed by test_local.py between "📄 完整 JSON:" and the next separator line of "=".
  local output="$1"
  printf '%s\n' "$output" | awk '
    /📄 完整 JSON:/ {in_json=1; next}
    in_json && /^=+$/ {exit}
    in_json {print}
  '
}

extract_json_fallback() {
  # Fallback JSON extraction when the marker+separator heuristic fails (e.g., separator not matched).
  # Tries (1) first JSON after "📄 完整 JSON:"; otherwise (2) last JSON object/array in the output.
  python - <<'PY'
import json
import re
import sys

text = sys.stdin.read()
marker = "📄 完整 JSON:"
decoder = json.JSONDecoder()

def first_json_from(s: str):
    m = re.search(r"[\{\[]", s)
    if not m:
        return None
    start = m.start()
    try:
        obj, end = decoder.raw_decode(s[start:])
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return None

idx = text.find(marker)
if idx != -1:
    candidate = first_json_from(text[idx + len(marker):])
    if candidate is not None:
        print(candidate)
        sys.exit(0)

i = 0
found = None
while True:
    m = re.search(r"[\{\[]", text[i:])
    if not m:
        break
    j = i + m.start()
    try:
        obj, end = decoder.raw_decode(text[j:])
        found = json.dumps(obj, ensure_ascii=False)
        i = j + end
    except Exception:
        i = j + 1

if found is not None:
    print(found)
PY
}

extract_intent_text() {
  local output="$1"
  if echo "$output" | jq -e . >/dev/null 2>&1; then
    # Prefer the display intent (Chinese) for compatibility with existing test cases.
    echo "$output" | jq -r '.intent_display // .intent // empty' 2>/dev/null | head -n 1 | xargs || true
    return
  fi
  echo "$output" | sed -n 's/.*📝 意圖: //p' | head -n 1 | xargs || true
}

json_has_entries() {
  local json="$1"
  echo "$json" | jq -r 'has("entries")' 2>/dev/null || echo "false"
}

json_get() {
  local json="$1"
  local jq_expr="$2"
  echo "$json" | jq -r "$jq_expr" 2>/dev/null || true
}

actual_item_count() {
  local json="$1"
  local has_entries
  has_entries="$(json_has_entries "$json")"
  if [[ "$has_entries" == "true" ]]; then
    json_get "$json" '.entries | length'
    return
  fi
  if [[ -n "$(json_get "$json" 'has("品項")')" ]] && [[ "$(json_get "$json" 'has("品項")')" == "true" ]]; then
    echo "1"
  else
    echo ""
  fi
}

extract_fields() {
  local output="$1"
  local json
  if echo "$output" | jq -e . >/dev/null 2>&1; then
    json="$output"
  else
    json="$(extract_json_block "$output")"

    if [[ -z "$json" ]] || ! echo "$json" | jq -e . >/dev/null 2>&1; then
      json="$(printf '%s\n' "$output" | extract_json_fallback)"
    fi
  fi

  if [[ -z "$json" ]] || ! echo "$json" | jq -e . >/dev/null 2>&1; then
    echo "Error: failed to extract valid JSON from output." >&2
    echo "Hint: ensure test_local.py prints a JSON object/array for single-test mode." >&2
    return 1
  fi

  local has_entries
  has_entries="$(json_has_entries "$json")"

  local item amount payment category project advance_status recipient error_message item_count date
  if [[ "$has_entries" == "true" ]]; then
    item="$(json_get "$json" '.entries[0]["品項"] // empty')"
    date="$(json_get "$json" '.entries[0]["日期"] // empty')"
    amount="$(json_get "$json" '.entries[0]["原幣金額"] // empty')"
    payment="$(json_get "$json" '.entries[0]["付款方式"] // empty')"
    category="$(json_get "$json" '.entries[0]["分類"] // empty')"
    project="$(json_get "$json" '.entries[0]["專案"] // empty')"
    advance_status="$(json_get "$json" '.entries[0]["代墊狀態"] // empty')"
    recipient="$(json_get "$json" '.entries[0]["收款支付對象"] // empty')"
    error_message="$(json_get "$json" '.error_message // .message // empty')"
  else
    item="$(json_get "$json" '.["品項"] // empty')"
    date="$(json_get "$json" '.["日期"] // empty')"
    amount="$(json_get "$json" '.["原幣金額"] // empty')"
    payment="$(json_get "$json" '.["付款方式"] // empty')"
    category="$(json_get "$json" '.["分類"] // empty')"
    project="$(json_get "$json" '.["專案"] // empty')"
    advance_status="$(json_get "$json" '.["代墊狀態"] // empty')"
    recipient="$(json_get "$json" '.["收款支付對象"] // empty')"
    error_message="$(json_get "$json" '.error_message // .message // empty')"
  fi
  item_count="$(actual_item_count "$json")"

  # Use a non-whitespace delimiter so bash `read` does not collapse empty fields.
  # (IFS treats whitespace specially and will "eat" consecutive delimiters.)
  printf '%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\037%s\n' \
    "$item" "$amount" "$payment" "$category" "$project" "$advance_status" "$recipient" "$error_message" "$item_count" "$date"
}

debug_dump_output_and_json() {
  local output="$1"
  echo -e "${YELLOW}Debug (raw test_local.py output):${NC}" >&2
  echo "$output" >&2

  local json
  json="$(extract_json_block "$output")"
  if [[ -z "$json" ]] || ! echo "$json" | jq -e . >/dev/null 2>&1; then
    json="$(printf '%s\n' "$output" | extract_json_fallback)"
  fi

  echo -e "${YELLOW}Debug (extracted JSON):${NC}" >&2
  echo "$json" >&2
  echo -e "${YELLOW}Debug (jq probes):${NC}" >&2
  local probe
  probe="$(jq -r 'has("entries")' <<<"$json" 2>&1)" || true
  echo "has(entries): $probe" >&2
  probe="$(jq -r '.entries[0] | keys_unsorted? // keys? // empty' <<<"$json" 2>&1)" || true
  echo "entries[0] keys: $probe" >&2
  probe="$(jq -r '.entries[0]["品項"] // empty' <<<"$json" 2>&1)" || true
  echo 'entries[0]["品項"]: '"$probe" >&2
  probe="$(jq -r '.entries[0]["日期"] // empty' <<<"$json" 2>&1)" || true
  echo 'entries[0]["日期"]: '"$probe" >&2
  probe="$(jq -r '.["日期"] // empty' <<<"$json" 2>&1)" || true
  echo 'root["日期"]: '"$probe" >&2
}

normalize_amount() {
  local v="$1"
  v="${v%.0}"
  echo "$v"
}

compare_exact() {
  local actual="$1"
  local expected="$2"
  [[ -z "$expected" ]] && return 0
  [[ "$actual" == "$expected" ]]
}

compare_contains() {
  local actual="$1"
  local expected="$2"
  [[ -z "$expected" ]] && return 0
  [[ "$actual" == *"$expected"* ]]
}

compare_amount() {
  local actual expected
  actual="$(normalize_amount "$1")"
  expected="$(normalize_amount "$2")"
  [[ -z "$expected" ]] && return 0
  [[ "$actual" == "$expected" ]]
}

compare_category() {
  local actual="$1"
  local expected="$2"
  [[ -z "$expected" ]] && return 0
  [[ "$actual" == *"$expected"* ]] || [[ "$expected" == *"$actual"* ]]
}

normalize_expected_date() {
  local expected="$1"
  [[ -z "$expected" ]] && return 0
  local year
  year="$(date +%Y)"
  echo "${expected//\{YEAR\}/$year}"
}

compare_date() {
  local actual="$1"
  local expected="$2"
  [[ -z "$expected" ]] && return 0
  expected="$(normalize_expected_date "$expected")"
  [[ "$actual" == "$expected" ]]
}

run_case_manual() {
  local group="$1" name="$2" message="$3" expected_desc="$4"
  echo ""
  echo "======================================================================"
  echo "[$group] $name"
  echo "======================================================================"
  if [[ -n "$expected_desc" ]]; then
    echo "Expected: $expected_desc"
  fi
  echo ""
  python test_local.py "$message"
  echo ""
  read -r -p "Press Enter to continue..."
}

run_case_auto() {
  local group="$1" name="$2" message="$3"
  local expected_intent="$4" expected_item="$5" expected_amount="$6" expected_payment="$7"
  local expected_category="$8" expected_project="$9" expected_item_count="${10}" expected_advance_status="${11}" expected_recipient="${12}"
  local expected_error_contains="${13}" expected_date="${14}"

  echo ""
  echo -e "${BLUE}======================================================================${NC}"
  echo "[$group] $name"
  echo -e "${BLUE}======================================================================${NC}"
  echo "Message: $message"

  local output
  # Prefer raw JSON output to avoid parsing human-readable text.
  output="$(python test_local.py --raw "$message" 2> >(cat >&2))"

  local actual_intent
  actual_intent="$(extract_intent_text "$output")"

  local item amount payment category advance_status recipient error_message item_count date
  local project
  local extracted
  if ! extracted="$(extract_fields "$output")"; then
    echo -e "${RED}❌ FAIL${NC}"
    echo -e "${YELLOW}Differences:${NC}"
    echo "  - error: failed to extract JSON fields from test_local.py output"
    if [[ "$DEBUG_MODE" == true ]]; then
      echo -e "${YELLOW}Debug (raw test_local.py output):${NC}" >&2
      echo "$output" >&2
    fi
    ((FAILED_TESTS+=1))
    return
  fi
  IFS=$'\037' read -r item amount payment category project advance_status recipient error_message item_count date \
    <<<"$extracted"

  local test_passed=true
  local failures=()

  if ! compare_exact "$actual_intent" "$expected_intent"; then
    test_passed=false
    failures+=("intent: expected[$expected_intent] actual[$actual_intent]")
  fi
  if ! compare_exact "${item:-}" "$expected_item"; then
    test_passed=false
    failures+=("item: expected[$expected_item] actual[${item:-}]")
  fi
  if ! compare_amount "${amount:-}" "$expected_amount"; then
    test_passed=false
    failures+=("amount: expected[$expected_amount] actual[${amount:-}]")
  fi
  if ! compare_exact "${payment:-}" "$expected_payment"; then
    test_passed=false
    failures+=("payment: expected[$expected_payment] actual[${payment:-}]")
  fi
  if ! compare_category "${category:-}" "$expected_category"; then
    test_passed=false
    failures+=("category: expected[contains $expected_category] actual[${category:-}]")
  fi
  if ! compare_exact "${project:-}" "$expected_project"; then
    test_passed=false
    failures+=("project: expected[$expected_project] actual[${project:-}]")
  fi
  if ! compare_exact "${item_count:-}" "$expected_item_count"; then
    test_passed=false
    failures+=("item_count: expected[$expected_item_count] actual[${item_count:-}]")
  fi
  if ! compare_exact "${advance_status:-}" "$expected_advance_status"; then
    test_passed=false
    failures+=("advance_status: expected[$expected_advance_status] actual[${advance_status:-}]")
  fi
  if ! compare_exact "${recipient:-}" "$expected_recipient"; then
    test_passed=false
    failures+=("recipient: expected[$expected_recipient] actual[${recipient:-}]")
  fi
  if ! compare_contains "${error_message:-}" "$expected_error_contains"; then
    test_passed=false
    failures+=("error_message: expected[contains $expected_error_contains] actual[${error_message:-}]")
  fi
  if ! compare_date "${date:-}" "$expected_date"; then
    test_passed=false
    failures+=("date: expected[$(normalize_expected_date "$expected_date")] actual[${date:-}]")
  fi

  if [[ "$test_passed" == true ]]; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((PASSED_TESTS+=1))
  else
    echo -e "${RED}❌ FAIL${NC}"
    echo -e "${YELLOW}Differences:${NC}"
    for f in "${failures[@]}"; do
      echo "  - $f"
    done
    [[ "$DEBUG_MODE" == true ]] && debug_dump_output_and_json "$output"
    ((FAILED_TESTS+=1))
  fi
}

run_case() {
  local group="$1" name="$2" message="$3" expected_desc="$4"
  shift 4
  ((TOTAL_TESTS+=1))
  if [[ "$AUTO_MODE" == true ]]; then
    run_case_auto "$group" "$name" "$message" "$@"
  else
    run_case_manual "$group" "$name" "$message" "$expected_desc"
  fi
}

main() {
  parse_args "$@"
  require_jq

  local suites=()
  if [[ "$ALL_MODE" == true ]]; then
    suites=(expense multi_expense advance_payment date cashflow)
  else
    suites=("$SUITE")
  fi

  if [[ "$SMOKE_MODE" == true ]] && [[ -n "$ONLY_PATTERN" ]]; then
    echo "Note: --smoke AND --only are both set; both filters must match." >&2
  fi

  for suite in "${suites[@]}"; do
    SUITE="$suite"
    if [[ "$SMOKE_MODE" == true ]]; then
      SMOKE_ONLY_PATTERN="$(smoke_pattern_for_suite "$SUITE")"
    else
      SMOKE_ONLY_PATTERN=""
    fi

    local suite_file
    suite_file="$(suite_path)"
    if [[ ! -f "$suite_file" ]]; then
      echo "Error: suite file not found: $suite_file" >&2
      exit 2
    fi
    validate_suite_jsonl "$suite_file"

    echo "======================================================================"
    echo "🧪 Test Suite: $SUITE"
    echo "======================================================================"
    echo ""
    if [[ "$AUTO_MODE" == true ]]; then
      echo "Mode: auto"
    else
      echo "Mode: manual"
    fi
    if [[ -n "$SMOKE_ONLY_PATTERN" ]]; then
      echo "Smoke: $SMOKE_ONLY_PATTERN"
    fi
    if [[ -n "$ONLY_PATTERN" ]]; then
      echo "Filter: $ONLY_PATTERN"
    fi
    if [[ "$LIST_MODE" == true ]]; then
      echo "Mode: list"
    fi

    if [[ "$LIST_MODE" == true ]]; then
      local line tc_id tc_group tc_name tc_message listed=0
      while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^# ]] && continue
        tc_id="$(jq -r '.id // empty' <<<"$line")"
        tc_group="$(jq -r '.group // empty' <<<"$line")"
        tc_name="$(jq -r '.name // empty' <<<"$line")"
        tc_message="$(jq -r '.message // empty' <<<"$line")"
        if should_run_case "$tc_id" "$tc_group" "$tc_name" "$tc_message"; then
          printf '%s\n' "$tc_id | $tc_group | $tc_name"
          ((listed+=1))
        fi
      done <"$suite_file"
      echo ""
      echo "Matched: $listed"
      echo ""
      continue
    fi

    if [[ "$AUTO_MODE" == false ]]; then
      echo ""
      read -r -p "Press Enter to start..."
    fi

    local line
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      [[ "$line" =~ ^# ]] && continue

      local tc_id tc_group tc_name tc_message expected_desc
      local expected_intent expected_item expected_amount expected_payment expected_category
      local expected_project
      local expected_item_count expected_advance_status expected_recipient expected_error_contains expected_date

      tc_id="$(jq -r '.id // empty' <<<"$line")"
      tc_group="$(jq -r '.group // empty' <<<"$line")"
      tc_name="$(jq -r '.name // empty' <<<"$line")"
      tc_message="$(jq -r '.message // empty' <<<"$line")"
      expected_desc="$(jq -r '.expected_desc // empty' <<<"$line")"

      expected_intent="$(jq -r '.expected.intent // empty' <<<"$line")"
      expected_item="$(jq -r '.expected.bookkeeping.item // empty' <<<"$line")"
      expected_amount="$(jq -r '.expected.bookkeeping.amount // empty' <<<"$line")"
      expected_payment="$(jq -r '.expected.bookkeeping.payment // empty' <<<"$line")"
      expected_category="$(jq -r '.expected.bookkeeping.category // empty' <<<"$line")"
      expected_project="$(jq -r '.expected.bookkeeping.project // empty' <<<"$line")"
      expected_item_count="$(jq -r '.expected.bookkeeping.item_count // empty' <<<"$line")"
      expected_advance_status="$(jq -r '.expected.bookkeeping.advance_status // empty' <<<"$line")"
      expected_recipient="$(jq -r '.expected.bookkeeping.recipient // empty' <<<"$line")"
      expected_error_contains="$(jq -r '.expected.error.contains // empty' <<<"$line")"
      expected_date="$(jq -r '.expected.bookkeeping.date // empty' <<<"$line")"

      if ! should_run_case "$tc_id" "$tc_group" "$tc_name" "$tc_message"; then
        ((SKIPPED_TESTS+=1))
        continue
      fi

      run_case "$tc_group" "$tc_id: $tc_name" "$tc_message" "$expected_desc" \
        "$expected_intent" "$expected_item" "$expected_amount" "$expected_payment" \
        "$expected_category" "$expected_project" "$expected_item_count" "$expected_advance_status" "$expected_recipient" \
        "$expected_error_contains" "$expected_date"
    done <"$suite_file"
  done

  if [[ "$LIST_MODE" == true ]]; then
    exit 0
  fi

  echo ""
  echo "======================================================================"
  echo "📊 Summary"
  echo "======================================================================"
  echo "Total:   $TOTAL_TESTS"
  echo "Passed:  $PASSED_TESTS"
  echo "Failed:  $FAILED_TESTS"
  if [[ $SKIPPED_TESTS -gt 0 ]]; then
    echo "Skipped: $SKIPPED_TESTS"
  fi

  if [[ "$AUTO_MODE" == true ]] && [[ $FAILED_TESTS -gt 0 ]]; then
    exit 1
  fi
}

main "$@"
