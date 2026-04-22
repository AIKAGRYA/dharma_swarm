#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/dharma_swarm"
STATE_DIR="${HOME}/.dharma"
RUN_ROOT="${STATE_DIR}/review_readiness"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${RUN_ROOT}/${RUN_ID}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_FILE="${RUN_DIR}/manifest.env"
LATEST_RUN_FILE="${RUN_ROOT}/latest_run.txt"
FINAL_PROBE_PID_FILE="${RUN_DIR}/final_probe.pid"

HOURS="${1:-8}"
TARGET_JST="${2:-06:30}"
MISSION_FILE="${MISSION_FILE:-${ROOT}/docs/missions/REVIEW_READINESS_NIGHT_2026-04-22.md}"

CODEX_SESSION="${CODEX_SESSION_NAME:-dgc_codex_review_ready}"
CAFFEINE_SESSION="${CAFFEINE_SESSION_NAME:-dgc_caffeine_review_ready}"
CODEX_LABEL="${CODEX_LABEL:-review-readiness-${RUN_ID}}"
USE_CAFFEINATE="${USE_CAFFEINATE:-1}"
REVIEW_SPLIT_BRAIN_MODE="${REVIEW_SPLIT_BRAIN_MODE:-check}"
START_CODEX="${START_CODEX:-1}"
START_VERIFY="${START_VERIFY:-1}"
START_CAFFEINE="${START_CAFFEINE:-1}"
RUN_BASELINE_PROBE="${RUN_BASELINE_PROBE:-1}"
SCHEDULE_FINAL_PROBE="${SCHEDULE_FINAL_PROBE:-1}"
DEFAULT_REPO_PYTHON="${ROOT}/.venv/bin/python"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "${DEFAULT_REPO_PYTHON}" ]]; then
    PYTHON_BIN="${DEFAULT_REPO_PYTHON}"
  else
    PYTHON_BIN="python3"
  fi
fi

mkdir -p "${LOG_DIR}"

if [[ ! -d "${ROOT}" ]]; then
  echo "Missing repo directory: ${ROOT}" >&2
  exit 1
fi

if [[ ! -f "${MISSION_FILE}" ]]; then
  echo "Mission file not found: ${MISSION_FILE}" >&2
  exit 1
fi

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

run_logged() {
  local name="$1"
  shift
  log "STEP ${name}: $*"
  "$@" > "${LOG_DIR}/${name}.log" 2>&1
  log "OK   ${name} -> ${LOG_DIR}/${name}.log"
}

run_optional() {
  local name="$1"
  shift
  log "STEP ${name}: $*"
  if "$@" > "${LOG_DIR}/${name}.log" 2>&1; then
    log "OK   ${name} -> ${LOG_DIR}/${name}.log"
  else
    local rc=$?
    log "WARN ${name} rc=${rc} -> ${LOG_DIR}/${name}.log"
  fi
}

cat > "${MANIFEST_FILE}" <<EOF
RUN_ID='${RUN_ID}'
RUN_DIR='${RUN_DIR}'
MISSION_FILE='${MISSION_FILE}'
HOURS='${HOURS}'
TARGET_JST='${TARGET_JST}'
CODEX_SESSION='${CODEX_SESSION}'
CAFFEINE_SESSION='${CAFFEINE_SESSION}'
CODEX_LABEL='${CODEX_LABEL}'
EOF

echo "${RUN_DIR}" > "${LATEST_RUN_FILE}"

cd "${ROOT}"

if [[ "${REVIEW_SPLIT_BRAIN_MODE}" == "fix" ]]; then
  run_optional split_brain_guard_fix bash scripts/split_brain_guard.sh --fix
else
  run_optional split_brain_guard_check bash scripts/split_brain_guard.sh
fi

run_optional dashboard_start bash scripts/dashboard_ctl.sh start

if [[ "${RUN_BASELINE_PROBE}" == "1" ]]; then
  run_optional baseline_probe "${PYTHON_BIN}" scripts/review_readiness_probe.py \
    --run-dir "${RUN_DIR}" \
    --phase baseline \
    --mode quick
fi

if [[ "${START_CODEX}" == "1" ]]; then
  run_logged start_codex env \
    SESSION_NAME="${CODEX_SESSION}" \
    DGC_CODEX_NIGHT_MISSION_FILE="${MISSION_FILE}" \
    DGC_CODEX_NIGHT_LABEL="${CODEX_LABEL}" \
    USE_CAFFEINATE="${USE_CAFFEINATE}" \
    scripts/start_codex_overnight_tmux.sh "${HOURS}"
fi

if [[ "${START_VERIFY}" == "1" ]]; then
  run_logged start_verification bash scripts/start_verification_lane.sh "${HOURS}"
fi

if [[ "${START_CAFFEINE}" == "1" ]]; then
  run_logged start_caffeine env \
    SESSION_NAME="${CAFFEINE_SESSION}" \
    AUTONOMY_PROFILE="workspace_auto" \
    MISSION_PROFILE="workspace_auto" \
    MISSION_PREFLIGHT="0" \
    USE_CAFFEINATE="${USE_CAFFEINATE}" \
    scripts/start_caffeine_tmux.sh "${TARGET_JST}"
fi

if [[ "${SCHEDULE_FINAL_PROBE}" == "1" && "${HOURS}" != "0" && "${HOURS}" != "forever" ]]; then
  SLEEP_SECS="$(
    "${PYTHON_BIN}" - <<'PY' "${HOURS}"
from __future__ import annotations
import sys
hours = float(sys.argv[1])
print(max(1, int(hours * 3600)))
PY
  )"
  (
    sleep "${SLEEP_SECS}"
    cd "${ROOT}"
    "${PYTHON_BIN}" scripts/review_readiness_probe.py \
      --run-dir "${RUN_DIR}" \
      --phase final \
      --mode full
  ) > "${LOG_DIR}/final_probe.log" 2>&1 &
  echo "$!" > "${FINAL_PROBE_PID_FILE}"
  log "OK   final_probe_scheduler pid=$(cat "${FINAL_PROBE_PID_FILE}")"
fi

cat <<EOF
Review readiness night prepared.
Run dir: ${RUN_DIR}
Mission file: ${MISSION_FILE}
Status: bash scripts/status_review_readiness_night.sh
Stop:   bash scripts/stop_review_readiness_night.sh
EOF
