#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/dharma_swarm"
STATE_DIR="${HOME}/.dharma"
RUN_ROOT="${STATE_DIR}/review_readiness"
LATEST_RUN_FILE="${RUN_ROOT}/latest_run.txt"
CODEX_SESSION="${CODEX_SESSION_NAME:-dgc_codex_review_ready}"
CAFFEINE_SESSION="${CAFFEINE_SESSION_NAME:-dgc_caffeine_review_ready}"

if [[ -f "${LATEST_RUN_FILE}" ]]; then
  RUN_DIR="$(cat "${LATEST_RUN_FILE}")"
else
  RUN_DIR=""
fi

echo "Stopping review readiness night lanes..."

SESSION_NAME="${CODEX_SESSION}" bash "${ROOT}/scripts/stop_codex_overnight_tmux.sh" || true
bash "${ROOT}/scripts/stop_verification_lane.sh" || true
SESSION_NAME="${CAFFEINE_SESSION}" bash "${ROOT}/scripts/stop_caffeine_tmux.sh" || true

if [[ -n "${RUN_DIR}" && -f "${RUN_DIR}/final_probe.pid" ]]; then
  PID="$(cat "${RUN_DIR}/final_probe.pid" 2>/dev/null || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    kill "${PID}" 2>/dev/null || true
    echo "Stopped final probe scheduler PID=${PID}"
  fi
fi

echo "Stopped."
