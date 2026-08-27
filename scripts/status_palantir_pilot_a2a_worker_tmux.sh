#!/usr/bin/env bash
set -euo pipefail

STATE_ROOT="${DHARMA_STATE_DIR:-${DHARMA_HOME:-${HOME}/.dharma}}"
case "${STATE_ROOT}" in
  "~") STATE_ROOT="${HOME}" ;;
  "~/"*) STATE_ROOT="${HOME}/${STATE_ROOT#\~/}" ;;
esac
RECEIPT_DIR="${STATE_ROOT}/reports/a2a/palantir_pilot_worker_receipts"
SESSION="${SESSION_NAME:-dharma_palantir_pilot_a2a_worker}"
SUBJECT="${SUBJECT:-dharma.a2a.palantir-pilot}"
CONSUMER="${CONSUMER:-palantir_pilot_a2a}"
STREAM="${STREAM:-DHARMA_FLEET}"
HEARTBEAT_FILE="${HOME}/.dharma/a2a_bus/worker_heartbeats/palantir-pilot.json"
LOG_FILE="${HOME}/.dharma/logs/palantir_pilot_a2a_worker/${SESSION}.log"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "status=running session=${SESSION}"
else
  echo "status=stopped session=${SESSION}"
fi

echo "subject=${SUBJECT}"
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
  nats --no-context -s nats://127.0.0.1:4222 consumer info "${STREAM}" "${CONSUMER}" -j --no-select || true
fi

if [[ -d "${RECEIPT_DIR}" ]]; then
  echo "--- latest worker receipts ---"
  find "${RECEIPT_DIR}" -maxdepth 1 -type f -name '*.json' -print \
    | sort -r \
    | head -5
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "--- pane tail ---"
  tmux capture-pane -pt "${SESSION}" -S -60 || true
fi
