#!/usr/bin/env bash
set -euo pipefail

LANE="${1:-${CODEX_LANE_NAME:-maintenance}}"
SESSION="codex_lane_${LANE}"
STATE_ROOT="${CODEX_LANE_STATE_ROOT:-${HOME}/.dharma/codex_lanes}"
LANE_DIR="${STATE_ROOT}/${LANE}"
REPO_ROOT="${CODEX_LANE_REPO_ROOT:-${HOME}/dharma_swarm}"
RUNNER_REPO="${CODEX_LANE_RUNNER_REPO:-${REPO_ROOT}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  exit 0
fi

mkdir -p "${LANE_DIR}"

cmd=(
  "${PYTHON_BIN}" "${RUNNER_REPO}/scripts/codex_lane_runner.py"
  --lane "${LANE}"
  --repo-root "${REPO_ROOT}"
  --state-root "${STATE_ROOT}"
)

if [[ -n "${CODEX_LANE_MISSION_FILE:-}" ]]; then
  cmd+=(--mission-file "${CODEX_LANE_MISSION_FILE}")
fi
if [[ -n "${CODEX_LANE_MISSION:-}" ]]; then
  cmd+=(--mission "${CODEX_LANE_MISSION}")
fi
if [[ -n "${CODEX_LANE_MODEL:-}" ]]; then
  cmd+=(--model "${CODEX_LANE_MODEL}")
fi
if [[ -n "${CODEX_LANE_BASE_REF:-}" ]]; then
  cmd+=(--base-ref "${CODEX_LANE_BASE_REF}")
fi
if [[ -n "${CODEX_LANE_HOURS:-}" ]]; then
  cmd+=(--hours "${CODEX_LANE_HOURS}")
fi
if [[ -n "${CODEX_LANE_MAX_CYCLES:-}" ]]; then
  cmd+=(--max-cycles "${CODEX_LANE_MAX_CYCLES}")
fi
if [[ -n "${CODEX_LANE_POLL_SECONDS:-}" ]]; then
  cmd+=(--poll-seconds "${CODEX_LANE_POLL_SECONDS}")
fi
if [[ -n "${CODEX_LANE_CYCLE_TIMEOUT:-}" ]]; then
  cmd+=(--cycle-timeout "${CODEX_LANE_CYCLE_TIMEOUT}")
fi
if [[ "${CODEX_LANE_DANGEROUS_FULL_AUTO:-0}" == "1" ]]; then
  cmd+=(--dangerous-full-auto)
fi
if [[ "${CODEX_LANE_ONCE:-0}" == "1" ]]; then
  cmd+=(--once)
fi

printf '%q ' "${cmd[@]}" > "${LANE_DIR}/last_start_command.sh"
printf '\n' >> "${LANE_DIR}/last_start_command.sh"

tmux new-session -d -s "${SESSION}" "cd '${RUNNER_REPO}' && bash '${LANE_DIR}/last_start_command.sh' 2>&1 | tee -a '${LANE_DIR}/tmux.log'"

echo "Started Codex lane '${LANE}'"
echo "Session: ${SESSION}"
echo "State: ${LANE_DIR}"
echo "Status: scripts/status_codex_lane_tmux.sh ${LANE}"
echo "Attach: tmux attach -t ${SESSION}"
