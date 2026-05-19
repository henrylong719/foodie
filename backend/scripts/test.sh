#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export DEBUG=false

tests=(
  smoke_test.py
  test_seed.py
  test_resolution.py
  test_customer_history.py
  test_item_resolver.py
  test_calls.py
  test_event_hub.py
  test_sse_e2e.py
)

for test_file in "${tests[@]}"; do
  echo "==> uv run python ${test_file}"
  uv run python "${test_file}"
done
