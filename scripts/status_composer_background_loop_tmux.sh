#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-composer_background_loop}"
STATE_DIR="${DHARMA_COMPOSER_BACKGROUND_STATE_DIR:-${HOME}/.dharma/a2a_bus/operator/composer_background_loop}"
HEARTBEAT_FILE="${STATE_DIR}/heartbeat.json"
RUN_FILE="${STATE_DIR}/latest_run_dir.txt"
LOG_FILE="${STATE_DIR}/session.log"
RECEIPTS_FILE="${STATE_DIR}/receipts.jsonl"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

if [[ -f "${RUN_FILE}" ]]; then
  echo
  echo "Run dir: $(cat "${RUN_FILE}")"
fi

if [[ -f "${HEARTBEAT_FILE}" ]]; then
  echo
  echo "Heartbeat:"
  cat "${HEARTBEAT_FILE}"
fi

if [[ -f "${RECEIPTS_FILE}" ]]; then
  echo
  echo "Recent receipts:"
  tail -n 8 "${RECEIPTS_FILE}"
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
