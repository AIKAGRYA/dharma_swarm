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

echo "Run dir: ${RUN_DIR:-"(none)"}"

if [[ -n "${RUN_DIR}" && -f "${RUN_DIR}/manifest.env" ]]; then
  echo
  echo "== Manifest =="
  cat "${RUN_DIR}/manifest.env"
fi

echo
echo "== Dashboard Runtime =="
bash "${ROOT}/scripts/dashboard_ctl.sh" status || true

echo
echo "== Codex Lane =="
SESSION_NAME="${CODEX_SESSION}" bash "${ROOT}/scripts/status_codex_overnight_tmux.sh" || true

echo
echo "== Verification Lane =="
if [[ -f "${STATE_DIR}/verification_lane.pid" ]]; then
  PID="$(cat "${STATE_DIR}/verification_lane.pid" 2>/dev/null || true)"
  if [[ -n "${PID}" ]] && kill -0 "${PID}" 2>/dev/null; then
    echo "verification_lane: RUNNING (PID ${PID})"
  else
    echo "verification_lane: NOT RUNNING"
  fi
else
  echo "verification_lane: NOT RUNNING"
fi

echo
echo "== Caffeine Lane =="
SESSION_NAME="${CAFFEINE_SESSION}" bash "${ROOT}/scripts/status_caffeine_tmux.sh" || true

if [[ -n "${RUN_DIR}" && -d "${RUN_DIR}/probes" ]]; then
  echo
  echo "== Latest Probes =="
  find "${RUN_DIR}/probes" -maxdepth 1 -type f | sort | while read -r path; do
    echo "--- ${path} ---"
    tail -n 40 "${path}" || true
    echo
  done
fi
