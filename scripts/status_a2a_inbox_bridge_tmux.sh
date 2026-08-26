#!/usr/bin/env bash
set -euo pipefail

RECEIPT_DIR="${DHARMA_STATE_DIR:-${DHARMA_HOME:-${HOME}/.dharma}}/reports/a2a/inbox_bridge_receipts"
SESSION="${SESSION_NAME:-dharma_a2a_inbox_bridge_hermes_m5}"
AGENT_UID="${AGENT_UID:-hermes-m5}"
CONSUMER="${CONSUMER:-hermes_inbox}"
STREAM="${STREAM:-DHARMA_FLEET}"
HEARTBEAT_FILE="${HOME}/.dharma/a2a_bus/bridge_heartbeats/${AGENT_UID}.json"
LOG_FILE="${HOME}/.dharma/logs/a2a_inbox_bridge/${SESSION}.log"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "status=running session=${SESSION}"
else
  echo "status=stopped session=${SESSION}"
fi

echo "agent_uid=${AGENT_UID}"
echo "consumer=${CONSUMER}"
echo "stream=${STREAM}"
echo "heartbeat=${HEARTBEAT_FILE}"
echo "log=${LOG_FILE}"

if [[ -f "${HEARTBEAT_FILE}" ]]; then
  echo "--- heartbeat ---"
  python3 -m json.tool "${HEARTBEAT_FILE}" || true
fi

if command -v nats >/dev/null 2>&1; then
  echo "--- consumer ---"
  nats --no-context --server nats://127.0.0.1:4222 consumer info "${STREAM}" "${CONSUMER}" --json || true
fi

if [[ -d "${RECEIPT_DIR}" ]]; then
  echo "--- latest bridge receipts ---"
  find "${RECEIPT_DIR}" -maxdepth 1 -type f -name '*.json' -print \
    | sort -r \
    | head -5
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "--- pane tail ---"
  tmux capture-pane -pt "${SESSION}" -S -60 || true
fi
