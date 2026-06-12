#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/dharma_swarm"
SESSION="${SESSION_NAME:-composer_console}"
STATE_DIR="${DHARMA_COMPOSER_CONSOLE_STATE_DIR:-${HOME}/.dharma/composer_console}"
LOG_FILE="${STATE_DIR}/session.log"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  echo "Attach: tmux attach -t ${SESSION}"
  exit 0
fi

mkdir -p "${STATE_DIR}"

tmux new-session -d -s "${SESSION}" "cd '${ROOT}' && python3 scripts/composer_console.py"
tmux pipe-pane -o -t "${SESSION}" "cat >> '${LOG_FILE}'"

echo "Started composer console session '${SESSION}'"
echo "State dir: ${STATE_DIR}"
echo "Log file: ${LOG_FILE}"
echo "Attach: tmux attach -t ${SESSION}"
echo "Status: scripts/status_composer_console_tmux.sh"
