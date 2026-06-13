#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-composer_console}"
STATE_DIR="${DHARMA_COMPOSER_CONSOLE_STATE_DIR:-${HOME}/.dharma/composer_console}"
LOG_FILE="${STATE_DIR}/session.log"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo
  echo "Recent log:"
  tail -n 40 "${LOG_FILE}"
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo
  echo "Pane snapshot:"
  tmux capture-pane -pt "${SESSION}" -S -80
fi
