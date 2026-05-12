#!/usr/bin/env bash
set -euo pipefail

SESSION="dharma-interop-workers"

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "$SESSION not running"
  exit 1
fi

tmux list-windows -t "$SESSION"
tmux list-panes -s -t "$SESSION" -F '#S:#I.#P pid=#{pane_pid} command=#{pane_current_command}'
