#!/usr/bin/env bash
# Launch backend and frontend in a split tmux session for local development.
# Usage: scripts/dev.sh [session-name]
set -e

SESSION="${1:-spinshare}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v tmux &>/dev/null; then
  echo "tmux is not installed. Run the servers manually — see README.md." >&2
  exit 1
fi

# Attach to existing session rather than creating a duplicate
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists — attaching."
  tmux attach-session -t "$SESSION"
  exit 0
fi

tmux new-session -d -s "$SESSION" -x 220 -y 50

# Left pane: backend
tmux send-keys -t "$SESSION" "cd '$REPO_ROOT/backend' && source .venv/bin/activate && uvicorn app.main:app --reload" Enter

# Right pane: frontend
tmux split-window -h -t "$SESSION"
tmux send-keys -t "$SESSION" "cd '$REPO_ROOT/frontend' && npm install --prefer-offline && npm run dev" Enter

# Label panes
tmux select-pane -t "$SESSION:0.0" -T "backend :8000"
tmux select-pane -t "$SESSION:0.1" -T "frontend :5173"

# Focus left pane and attach
tmux select-pane -t "$SESSION:0.0"
tmux attach-session -t "$SESSION"
