#!/usr/bin/env bash
set -e

echo "Running Ruff (auto-fix)..."
ruff check . --fix

echo "Running Black..."
black .

echo "Lint complete ✔"
