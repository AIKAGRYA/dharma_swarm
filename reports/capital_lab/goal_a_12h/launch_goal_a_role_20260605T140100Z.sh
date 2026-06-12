#!/usr/bin/env bash
set -u

ROLE="${1:-}"
REPO_ROOT="/Users/dhyana/dharma_swarm"
MISSION_ID="20260605T140100Z-dharma-capital-lab-goal-a-alpha-evidence-12h"
LOG_DIR="${REPO_ROOT}/reports/capital_lab/goal_a_12h/session_logs"

case "${ROLE}" in
  planner)
    TASK_ID="${MISSION_ID}-t01-planner"
    AGENT="claude-goal-a-planner"
    ;;
  adversary)
    TASK_ID="${MISSION_ID}-t03-adversary"
    AGENT="hermes-goal-a-adversary"
    ;;
  reporter)
    TASK_ID="${MISSION_ID}-t05-reporter"
    AGENT="claude-goal-a-reporter"
    ;;
  *)
    echo "usage: $0 planner|adversary|reporter" >&2
    exit 2
    ;;
esac

PROMPT_PATH="/Users/dhyana/.dharma/autonomy_spine/${MISSION_ID}/artifacts/prompts/${TASK_ID}.prompt.md"
LOG_PATH="${LOG_DIR}/${ROLE}_$(date -u +%Y%m%dT%H%M%SZ).log"

mkdir -p "${LOG_DIR}"
cd "${REPO_ROOT}" || exit 2

PYTHONPATH=. python3 scripts/runtime/autonomy_spine.py progress \
  --mission-id "${MISSION_ID}" \
  --task-id "${TASK_ID}" \
  --agent "${AGENT}" \
  --status heartbeat \
  --evidence "Goal A ${ROLE} launcher started; no completion claim." \
  --artifact "${PROMPT_PATH}" \
  --json || true

{
  echo "[goal-a-${ROLE}] started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[goal-a-${ROLE}] prompt=${PROMPT_PATH}"
  echo "[goal-a-${ROLE}] repo=${REPO_ROOT}"
} | tee "${LOG_PATH}"

case "${ROLE}" in
  planner|reporter)
    claude -p "$(cat "${PROMPT_PATH}")" --effort max 2>&1 | tee -a "${LOG_PATH}"
    rc=${PIPESTATUS[0]}
    ;;
  adversary)
    hermes -z "$(cat "${PROMPT_PATH}")" 2>&1 | tee -a "${LOG_PATH}"
    rc=${PIPESTATUS[0]}
    ;;
esac

{
  echo "[goal-a-${ROLE}] exited_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[goal-a-${ROLE}] rc=${rc}"
} | tee -a "${LOG_PATH}"

PYTHONPATH=. python3 scripts/runtime/autonomy_spine.py progress \
  --mission-id "${MISSION_ID}" \
  --task-id "${TASK_ID}" \
  --agent "${AGENT}" \
  --status heartbeat \
  --evidence "Goal A ${ROLE} launcher exited rc=${rc}; see session log. This is not a completion claim." \
  --artifact "${LOG_PATH}" \
  --json || true

sleep 3600
exit "${rc}"
