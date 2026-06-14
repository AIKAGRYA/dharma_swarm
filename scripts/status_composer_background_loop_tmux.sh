#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-composer_background_loop}"
STATE_DIR="${DHARMA_COMPOSER_BACKGROUND_STATE_DIR:-${HOME}/.dharma/a2a_bus/operator/composer_background_loop}"
HEARTBEAT_FILE="${STATE_DIR}/heartbeat.json"
RUN_FILE="${STATE_DIR}/latest_run_dir.txt"
LOG_FILE="${STATE_DIR}/session.log"
RECEIPTS_FILE="${STATE_DIR}/receipts.jsonl"

SESSION_RUNNING=0
if tmux has-session -t "${SESSION}" 2>/dev/null; then
  SESSION_RUNNING=1
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

evidence_heading() {
  local label="$1"
  if [[ "${SESSION_RUNNING}" == "1" ]]; then
    echo "${label} (session is running; pane snapshot below is stronger liveness proof):"
  else
    echo "${label} (historical; not liveness proof because session is NOT RUNNING):"
  fi
}

if [[ -f "${RUN_FILE}" ]]; then
  echo
  evidence_heading "Run dir"
  cat "${RUN_FILE}"
fi

if [[ -f "${HEARTBEAT_FILE}" ]]; then
  echo
  evidence_heading "Heartbeat"
  cat "${HEARTBEAT_FILE}"
fi

if [[ -f "${RECEIPTS_FILE}" ]]; then
  echo
  evidence_heading "Recent receipts"
  tail -n 8 "${RECEIPTS_FILE}"
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo
  evidence_heading "Recent log"
  tail -n 40 "${LOG_FILE}"
fi

if [[ "${SESSION_RUNNING}" == "1" ]]; then
  echo
  echo "Pane snapshot:"
  tmux capture-pane -pt "${SESSION}" -S -80
fi
