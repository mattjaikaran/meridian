#!/usr/bin/env bash
# Meridian Python runner — handles PYTHONPATH and uv project resolution
# Usage: meridian-run '<python code>'
#   or:  meridian-run script.py [args...]

set -euo pipefail

MERIDIAN_ROOT="${MERIDIAN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

if [[ "${1:-}" == *.py ]]; then
    PYTHONPATH="$MERIDIAN_ROOT" exec uv run --project "$MERIDIAN_ROOT" python "$@"
else
    PYTHONPATH="$MERIDIAN_ROOT" exec uv run --project "$MERIDIAN_ROOT" python -c "$1"
fi
