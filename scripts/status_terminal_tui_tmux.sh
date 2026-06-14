#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-dharma_terminal_tui}"
STATE_DIR="${DHARMA_TERMINAL_TUI_STATE_DIR:-${HOME}/.dharma/terminal_tui}"
LOG_FILE="${STATE_DIR}/session.log"

SESSION_RUNNING=0
if tmux has-session -t "${SESSION}" 2>/dev/null; then
  SESSION_RUNNING=1
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo
  if [[ "${SESSION_RUNNING}" == "1" ]]; then
    echo "Recent log (session is running; pane snapshot below is stronger liveness proof):"
  else
    echo "Recent log (historical; not liveness proof because session is NOT RUNNING):"
  fi
  tail -n 40 "${LOG_FILE}"
fi

if [[ "${SESSION_RUNNING}" == "1" ]]; then
  echo
  echo "Pane snapshot:"
  tmux capture-pane -pt "${SESSION}" -S -80
fi
