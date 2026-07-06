#!/usr/bin/env bash
set -euo pipefail

ROOT="${DHARMA_SWARM_REPO:-${HOME}/dharma_swarm}"
MISSION_ID="${1:?usage: scripts/start_ds_goal_tmux.sh <mission-id> [duration-hours]}"
DURATION_HOURS="${2:-${DS_GOAL_DURATION_HOURS:-6}}"
STATE_ROOT="${DS_GOAL_STATE_ROOT:-${HOME}/.dharma/ds_goals}"
KERNEL_STORE="${DS_GOAL_KERNEL_STORE:-${HOME}/.dharma/living_agent_kernel}"
SESSION_NAME="${SESSION_NAME:-}"

cmd=(
  "${ROOT}/.venv/bin/python"
  "${ROOT}/scripts/runtime/autonomy_spine.py"
  run
  --mission-id "${MISSION_ID}"
  --state-root "${STATE_ROOT}"
  --kernel-store "${KERNEL_STORE}"
  --duration-hours "${DURATION_HOURS}"
  --dispatch-mode tmux
  --json
)

if [[ -n "${SESSION_NAME}" ]]; then
  cmd+=(--tmux-session "${SESSION_NAME}")
fi

cd "${ROOT}"
exec "${cmd[@]}"
