#!/usr/bin/env bash
set -euo pipefail

# Legacy shim for v1.5 test script.
# Delegates to the unified functional-suite runner.

AUTO=false

for arg in "$@"; do
  case "$arg" in
    --auto) AUTO=true ;;
    --help|-h)
      cat <<'EOF'
Deprecated: use ./run_tests.sh instead.

This script is a shim for backward compatibility.

Usage:
  ./run_v15_tests.sh [--auto]

Equivalent:
  ./run_tests.sh --suite multi_expense [--auto]
EOF
      exit 0
      ;;
  esac
done

if [[ "$AUTO" == true ]]; then
  ./run_tests.sh --suite multi_expense --auto
else
  ./run_tests.sh --suite multi_expense --manual
fi

