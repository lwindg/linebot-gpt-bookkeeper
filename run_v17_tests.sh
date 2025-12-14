#!/usr/bin/env bash
set -euo pipefail

# Legacy shim for v1.7 test script.
# Delegates to the unified functional-suite runner.

AUTO=false
ONLY_PATTERN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --auto)
      AUTO=true
      shift
      ;;
    --only)
      ONLY_PATTERN="${2:-}"
      shift 2
      ;;
    --help|-h)
      cat <<'EOF'
Deprecated: use ./run_tests.sh instead.

This script is a shim for backward compatibility.

Usage:
  ./run_v17_tests.sh [--auto] [--only <pattern>]

Equivalent:
  ./run_tests.sh --suite advance_payment [--auto] [--only <pattern>]
EOF
      exit 0
      ;;
    *)
      shift
      ;;
  esac
done

args=(--suite advance_payment)
if [[ "$AUTO" == true ]]; then
  args+=(--auto)
else
  args+=(--manual)
fi
if [[ -n "$ONLY_PATTERN" ]]; then
  args+=(--only "$ONLY_PATTERN")
fi

./run_tests.sh "${args[@]}"

