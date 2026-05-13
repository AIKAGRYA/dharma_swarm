#!/usr/bin/env bash
set -euo pipefail

LANE="${1:-${CODEX_LANE_NAME:-maintenance}}"
SESSION="codex_lane_${LANE}"
STATE_ROOT="${CODEX_LANE_STATE_ROOT:-${HOME}/.dharma/codex_lanes}"
LANE_DIR="${STATE_ROOT}/${LANE}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

echo "State: ${LANE_DIR}"

if [[ -f "${LANE_DIR}/manifest.json" ]]; then
  echo
  echo "Manifest:"
  cat "${LANE_DIR}/manifest.json"
fi

if [[ -f "${LANE_DIR}/heartbeat.json" ]]; then
  echo
  echo "Heartbeat:"
  cat "${LANE_DIR}/heartbeat.json"
fi

if [[ -f "${LANE_DIR}/latest_run.txt" ]]; then
  RUN_DIR="$(cat "${LANE_DIR}/latest_run.txt")"
  echo
  echo "Latest run: ${RUN_DIR}"
  if [[ -f "${RUN_DIR}/report.md" ]]; then
    echo
    echo "Report tail:"
    tail -n 80 "${RUN_DIR}/report.md"
  fi
fi

WORKTREE="$(python3 - <<PY
import json
from pathlib import Path
p = Path("${LANE_DIR}") / "manifest.json"
if p.exists():
    print(json.loads(p.read_text()).get("worktree", ""))
PY
)"
if [[ -n "${WORKTREE}" && ( -d "${WORKTREE}/.git" || -f "${WORKTREE}/.git" ) ]]; then
  echo
  echo "Worktree status:"
  git -C "${WORKTREE}" status --short --branch
fi
