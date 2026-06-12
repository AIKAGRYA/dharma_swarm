#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/dharma_swarm"
SESSION="${SESSION_NAME:-composer_background_loop}"
STATE_DIR="${DHARMA_COMPOSER_BACKGROUND_STATE_DIR:-${HOME}/.dharma/a2a_bus/operator/composer_background_loop}"
LOG_FILE="${STATE_DIR}/session.log"
POLL_SECONDS="${POLL_SECONDS:-60}"
CYCLE_TIMEOUT="${CYCLE_TIMEOUT:-2700}"
MAX_CYCLES="${MAX_CYCLES:-0}"
AGENTS="${DHARMA_COMPOSER_BACKGROUND_AGENTS:-codex,opus}"
USE_CAFFEINATE="${USE_CAFFEINATE:-1}"
DRY_RUN="${DRY_RUN:-1}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  echo "Attach: tmux attach -t ${SESSION}"
  exit 0
fi

mkdir -p "${STATE_DIR}"

runner="python3 scripts/composer_background_loop.py --agents '${AGENTS}' --poll-seconds '${POLL_SECONDS}' --cycle-timeout '${CYCLE_TIMEOUT}'"
if [[ "${MAX_CYCLES}" != "0" ]]; then
  runner="${runner} --max-cycles '${MAX_CYCLES}'"
fi
if [[ "${DRY_RUN}" == "1" ]]; then
  runner="${runner} --dry-run"
fi

if [[ "${USE_CAFFEINATE}" == "1" ]] && command -v caffeinate >/dev/null 2>&1; then
  runner="caffeinate -i ${runner}"
fi

tmux new-session -d -s "${SESSION}" "cd '${ROOT}' && ${runner}"
tmux pipe-pane -o -t "${SESSION}" "cat >> '${LOG_FILE}'"

echo "Started composer background loop session '${SESSION}'"
echo "Agents: ${AGENTS}"
echo "Poll seconds: ${POLL_SECONDS}"
echo "Cycle timeout: ${CYCLE_TIMEOUT}"
echo "Mode: $([[ "${DRY_RUN}" == "1" ]] && echo "monitor/dry-run" || echo "external wake")"
echo "State dir: ${STATE_DIR}"
echo "Log file: ${LOG_FILE}"
echo "Attach: tmux attach -t ${SESSION}"
echo "Status: scripts/status_composer_background_loop_tmux.sh"
