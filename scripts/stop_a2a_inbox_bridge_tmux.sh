#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-dharma_a2a_inbox_bridge_hermes_m5}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  tmux send-keys -t "${SESSION}" C-c
  sleep 1
  if tmux has-session -t "${SESSION}" 2>/dev/null; then
    tmux kill-session -t "${SESSION}"
  fi
  echo "Stopped ${SESSION}"
else
  echo "Session '${SESSION}' is not running."
fi
