#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "— ruff check api/"
ruff check api/
echo "— ruff check sdk/"
ruff check sdk/
echo "— mypy api/"
(cd api && mypy app/) || echo "mypy api/ returned non-zero (non-gating)"
echo "— mypy sdk/"
(cd sdk && mypy langperf/) || echo "mypy sdk/ returned non-zero (non-gating)"
