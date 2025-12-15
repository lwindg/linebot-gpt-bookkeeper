#!/usr/bin/env bash
set -euo pipefail

# Legacy shim for the expense suite.
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
  ./run_v1_tests.sh [--auto]

Equivalent:
  ./run_tests.sh --suite expense [--auto]
EOF
      exit 0
      ;;
  esac
done

if [[ "$AUTO" == true ]]; then
  ./run_tests.sh --suite expense --auto
else
  ./run_tests.sh --suite expense --manual
fi
