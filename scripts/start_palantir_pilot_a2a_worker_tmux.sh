#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION_NAME:-dharma_palantir_pilot_a2a_worker}"
SUBJECT="${SUBJECT:-dharma.a2a.palantir-pilot}"
CONSUMER="${CONSUMER:-palantir_pilot_a2a}"
STREAM="${STREAM:-DHARMA_FLEET}"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-30}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"
MAX_MESSAGES="${MAX_MESSAGES:-5}"
LOG_DIR="${HOME}/.dharma/logs/palantir_pilot_a2a_worker"
HEARTBEAT_DIR="${HOME}/.dharma/a2a_bus/worker_heartbeats"
LOG_FILE="${LOG_DIR}/${SESSION}.log"
HEARTBEAT_FILE="${HEARTBEAT_DIR}/palantir-pilot.json"

mkdir -p "${LOG_DIR}" "${HEARTBEAT_DIR}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  echo "Status: bash scripts/status_palantir_pilot_a2a_worker_tmux.sh"
  exit 0
fi

tmux_cmd="cd '${ROOT}' && uv run --with nats-py python scripts/runtime/palantir_pilot_a2a_worker.py --subject '${SUBJECT}' --consumer '${CONSUMER}' --stream '${STREAM}' --fetch-timeout '${FETCH_TIMEOUT}' --poll-interval '${POLL_INTERVAL}' --max-messages '${MAX_MESSAGES}' --heartbeat-file '${HEARTBEAT_FILE}' --loop --suppress-no-messages"

tmux new-session -d -s "${SESSION}" "${tmux_cmd}"
tmux pipe-pane -o -t "${SESSION}" "cat >> '${LOG_FILE}'"

echo "Started ${SESSION}"
echo "Subject: ${SUBJECT}"
echo "Consumer: ${CONSUMER}"
echo "Log: ${LOG_FILE}"
echo "Heartbeat: ${HEARTBEAT_FILE}"
echo "Attach: tmux attach -t ${SESSION}"
echo "Status: bash scripts/status_palantir_pilot_a2a_worker_tmux.sh"
