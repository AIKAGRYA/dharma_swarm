#!/usr/bin/env bash
set -u

REPO_ROOT="/Users/dhyana/dharma_swarm"
MISSION_ID="20260605T140100Z-dharma-capital-lab-goal-a-alpha-evidence-12h"
TASK_ID="${MISSION_ID}-t02-builder"
PROMPT_PATH="/Users/dhyana/.dharma/autonomy_spine/${MISSION_ID}/artifacts/prompts/${TASK_ID}.prompt.md"
LOG_DIR="${REPO_ROOT}/reports/capital_lab/goal_a_12h/session_logs"
LOG_PATH="${LOG_DIR}/builder_$(date -u +%Y%m%dT%H%M%SZ).log"

mkdir -p "${LOG_DIR}"
cd "${REPO_ROOT}" || exit 2

PYTHONPATH=. python3 scripts/runtime/autonomy_spine.py progress \
  --mission-id "${MISSION_ID}" \
  --task-id "${TASK_ID}" \
  --agent codex-goal-a-builder \
  --status heartbeat \
  --evidence "Goal A builder launcher started with supported codex exec flags; no completion claim." \
  --artifact "${PROMPT_PATH}" \
  --json || true

{
  echo "[goal-a-builder] started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[goal-a-builder] prompt=${PROMPT_PATH}"
  echo "[goal-a-builder] repo=${REPO_ROOT}"
} | tee "${LOG_PATH}"

codex exec -s workspace-write --cd "${REPO_ROOT}" "$(cat "${PROMPT_PATH}")" 2>&1 | tee -a "${LOG_PATH}"
rc=${PIPESTATUS[0]}

{
  echo "[goal-a-builder] exited_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[goal-a-builder] rc=${rc}"
} | tee -a "${LOG_PATH}"

PYTHONPATH=. python3 scripts/runtime/autonomy_spine.py progress \
  --mission-id "${MISSION_ID}" \
  --task-id "${TASK_ID}" \
  --agent codex-goal-a-builder \
  --status heartbeat \
  --evidence "Goal A builder codex exec exited rc=${rc}; see session log. This is not a completion claim." \
  --artifact "${LOG_PATH}" \
  --json || true

sleep 3600
exit "${rc}"
