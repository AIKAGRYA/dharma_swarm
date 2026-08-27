#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION="${SESSION_NAME:-dharma_a2a_inbox_bridge_hermes_m5}"
AGENT_UID="${AGENT_UID:-hermes-m5}"
CONSUMER="${CONSUMER:-hermes_inbox}"
STREAM="${STREAM:-DHARMA_FLEET}"
FETCH_TIMEOUT="${FETCH_TIMEOUT:-30}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"
MAX_MESSAGES="${MAX_MESSAGES:-10}"
LOG_DIR="${HOME}/.dharma/logs/a2a_inbox_bridge"
HEARTBEAT_DIR="${HOME}/.dharma/a2a_bus/bridge_heartbeats"
LOG_FILE="${LOG_DIR}/${SESSION}.log"
HEARTBEAT_FILE="${HEARTBEAT_DIR}/${AGENT_UID}.json"

mkdir -p "${LOG_DIR}" "${HEARTBEAT_DIR}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  echo "Status: bash scripts/status_a2a_inbox_bridge_tmux.sh"
  exit 0
fi

tmux_cmd="cd '${ROOT}' && PYTHONDONTWRITEBYTECODE=1 uv run --with nats-py python -B scripts/runtime/a2a_inbox_bridge.py --agent-uid '${AGENT_UID}' --consumer '${CONSUMER}' --stream '${STREAM}' --fetch-timeout '${FETCH_TIMEOUT}' --poll-interval '${POLL_INTERVAL}' --max-messages '${MAX_MESSAGES}' --heartbeat-file '${HEARTBEAT_FILE}' --loop --suppress-no-messages"

tmux new-session -d -s "${SESSION}" "${tmux_cmd}"
tmux pipe-pane -o -t "${SESSION}" "cat >> '${LOG_FILE}'"

echo "Started ${SESSION}"
echo "Agent UID: ${AGENT_UID}"
echo "Consumer: ${CONSUMER}"
echo "Log: ${LOG_FILE}"
echo "Heartbeat: ${HEARTBEAT_FILE}"
echo "Attach: tmux attach -t ${SESSION}"
echo "Status: bash scripts/status_a2a_inbox_bridge_tmux.sh"
