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

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

usage() {
  cat <<'EOF'
Unified test runner (functional suites)

Usage:
  ./run_tests.sh --suite <expense|multi_expense|advance_payment|date> [--auto|--manual] [--only <pattern>]

Options:
  --suite <name>    Suite name: expense, multi_expense, advance_payment, date
  --auto            Auto-compare expected vs actual (default: manual)
  --manual          Manual mode (default)
  --only <pattern>  Run only tests whose id/name/message matches regex
  --help, -h        Show this help

Notes:
  - Requires jq. If missing, the script exits with install hints.
  - transaction_id is not compared (non-deterministic).
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
      --auto)
        AUTO_MODE=true
        shift
        ;;
      --manual)
        AUTO_MODE=false
        shift
        ;;
      --only)
        ONLY_PATTERN="${2:-}"
        shift 2
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

  if [[ -z "$SUITE" ]]; then
    echo "Error: --suite is required" >&2
    echo "" >&2
    usage >&2
    exit 2
  fi
}

suite_path() {
  case "$SUITE" in
    expense) echo "tests/suites/expense.sh" ;;
    multi_expense) echo "tests/suites/multi_expense.sh" ;;
    advance_payment) echo "tests/suites/advance_payment.sh" ;;
    date) echo "tests/suites/date.sh" ;;
    *)
      echo "Error: unknown suite: $SUITE" >&2
      exit 2
      ;;
  esac
}

extract_json_block() {
  # Extract JSON block printed by test_local.py between "📄 完整 JSON:" and the next separator line of "=".
  local output="$1"
  echo "$output" | awk '
    /📄 完整 JSON:/ {in_json=1; next}
    in_json && /^=+$/ {exit}
    in_json {print}
  '
}

extract_intent_text() {
  local output="$1"
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
  json="$(extract_json_block "$output")"

  if [[ -z "$json" ]]; then
    echo "Error: failed to extract JSON from output." >&2
    echo "Hint: ensure test_local.py prints '📄 完整 JSON:' in single-test mode." >&2
    return 1
  fi

  local has_entries
  has_entries="$(json_has_entries "$json")"

  local item amount payment category advance_status recipient error_message item_count date
  if [[ "$has_entries" == "true" ]]; then
    item="$(json_get "$json" '.entries[0]["品項"] // empty')"
    date="$(json_get "$json" '.entries[0]["日期"] // empty')"
    amount="$(json_get "$json" '.entries[0]["原幣金額"] // empty')"
    payment="$(json_get "$json" '.entries[0]["付款方式"] // empty')"
    category="$(json_get "$json" '.entries[0]["分類"] // empty')"
    advance_status="$(json_get "$json" '.entries[0]["代墊狀態"] // empty')"
    recipient="$(json_get "$json" '.entries[0]["收款支付對象"] // empty')"
    error_message="$(json_get "$json" '.message // empty')"
  else
    item="$(json_get "$json" '.["品項"] // empty')"
    date="$(json_get "$json" '.["日期"] // empty')"
    amount="$(json_get "$json" '.["原幣金額"] // empty')"
    payment="$(json_get "$json" '.["付款方式"] // empty')"
    category="$(json_get "$json" '.["分類"] // empty')"
    advance_status="$(json_get "$json" '.["代墊狀態"] // empty')"
    recipient="$(json_get "$json" '.["收款支付對象"] // empty')"
    error_message="$(json_get "$json" '.message // empty')"
  fi
  item_count="$(actual_item_count "$json")"

  # Tab-separated output for safe parsing (values may contain spaces).
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$item" "$amount" "$payment" "$category" "$advance_status" "$recipient" "$error_message" "$item_count" "$date"
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
  python test_local.py "${SUITE_PY_ARGS[@]}" "$message"
  echo ""
  read -r -p "Press Enter to continue..."
}

run_case_auto() {
  local group="$1" name="$2" message="$3"
  local expected_intent="$4" expected_item="$5" expected_amount="$6" expected_payment="$7"
  local expected_category="$8" expected_item_count="$9" expected_advance_status="${10}" expected_recipient="${11}"
  local expected_error_contains="${12}" expected_date="${13}"

  echo ""
  echo -e "${BLUE}======================================================================${NC}"
  echo "[$group] $name"
  echo -e "${BLUE}======================================================================${NC}"
  echo "Message: $message"

  local output
  output="$(python test_local.py "${SUITE_PY_ARGS[@]}" "$message" 2>&1)"

  local actual_intent
  actual_intent="$(extract_intent_text "$output")"

  local item amount payment category advance_status recipient error_message item_count date
  IFS=$'\t' read -r item amount payment category advance_status recipient error_message item_count date \
    <<<"$(extract_fields "$output")"

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
    ((PASSED_TESTS++))
  else
    echo -e "${RED}❌ FAIL${NC}"
    echo -e "${YELLOW}Differences:${NC}"
    for f in "${failures[@]}"; do
      echo "  - $f"
    done
    ((FAILED_TESTS++))
  fi
}

run_case() {
  local group="$1" name="$2" message="$3" expected_desc="$4"
  shift 4
  ((TOTAL_TESTS++))
  if [[ "$AUTO_MODE" == true ]]; then
    run_case_auto "$group" "$name" "$message" "$@"
  else
    run_case_manual "$group" "$name" "$message" "$expected_desc"
  fi
}

main() {
  require_jq
  parse_args "$@"

  local suite_file
  suite_file="$(suite_path)"
  if [[ ! -f "$suite_file" ]]; then
    echo "Error: suite file not found: $suite_file" >&2
    exit 2
  fi

  # Suite files must define:
  # - SUITE_PY_ARGS: bash array of extra args passed to test_local.py
  # - TEST_CASES: bash array of '|' delimited records
  # Record format (15 fields):
  #   id|group|name|message|expected_desc|expected_intent|expected_item|expected_amount|expected_payment|expected_category|expected_item_count|expected_advance_status|expected_recipient|expected_error_contains|expected_date
  # (expected_desc is used only in manual mode)
  # shellcheck disable=SC1090
  source "$suite_file"

  echo "======================================================================"
  echo "🧪 Test Suite: $SUITE"
  echo "======================================================================"
  echo ""
  if [[ "$AUTO_MODE" == true ]]; then
    echo "Mode: auto"
  else
    echo "Mode: manual"
  fi
  if [[ -n "$ONLY_PATTERN" ]]; then
    echo "Filter: $ONLY_PATTERN"
  fi

  if [[ "$AUTO_MODE" == false ]]; then
    echo ""
    read -r -p "Press Enter to start..."
  fi

  local record
  for record in "${TEST_CASES[@]}"; do
    IFS='|' read -r \
      tc_id tc_group tc_name tc_message \
      expected_desc expected_intent expected_item expected_amount expected_payment \
      expected_category expected_item_count expected_advance_status expected_recipient expected_error_contains expected_date \
      <<<"$record"

    if [[ -n "$ONLY_PATTERN" ]]; then
      if ! echo "$tc_id $tc_group $tc_name $tc_message" | grep -qE "$ONLY_PATTERN"; then
        ((SKIPPED_TESTS++))
        continue
      fi
    fi

    run_case "$tc_group" "$tc_id: $tc_name" "$tc_message" "$expected_desc" \
      "$expected_intent" "$expected_item" "$expected_amount" "$expected_payment" \
      "$expected_category" "$expected_item_count" "$expected_advance_status" "$expected_recipient" \
      "$expected_error_contains" "$expected_date"
  done

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
