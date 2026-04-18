#!/usr/bin/env bash
# Run backend tests using the project virtual environment.
# Usage: ./scripts/test.sh [pytest args...]
# Examples:
#   ./scripts/test.sh                                     # all tests
#   ./scripts/test.sh app/routers/groups_test.py -v       # specific file
#   ./scripts/test.sh app/routers/ -v                     # directory
#   ./scripts/test.sh -k "TestGroupCreate" -v             # keyword filter
#   ./scripts/test.sh --cov=app                           # with coverage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

if [[ ! -f "$VENV_PYTHON" ]]; then
  echo "ERROR: venv not found at $VENV_PYTHON"
  echo "Run: cd backend && python -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

cd "$BACKEND_DIR"
exec "$VENV_PYTHON" -m pytest "$@"
