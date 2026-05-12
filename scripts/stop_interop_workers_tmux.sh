#!/usr/bin/env bash
set -euo pipefail

SESSION="dharma-interop-workers"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "$SESSION not running"
  exit 0
fi

tmux kill-session -t "$SESSION"
echo "stopped $SESSION"
