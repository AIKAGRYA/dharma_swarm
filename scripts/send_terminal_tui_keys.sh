#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-dharma_terminal_tui}"

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 [--literal <text> | <keys...>]"
  echo "Example: $0 Tab Enter"
  echo "Example: $0 --literal '/help'"
  exit 1
fi

if ! tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' not running."
  exit 1
fi

if [[ "${1:-}" == "--literal" || "${1:-}" == "--text" ]]; then
  if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 --literal <text>"
    exit 1
  fi
  tmux send-keys -l -t "${SESSION}" "$2"
  echo "Sent literal text to '${SESSION}': $2"
  exit 0
fi

tmux send-keys -t "${SESSION}" "$@"
echo "Sent keys to '${SESSION}': $*"
