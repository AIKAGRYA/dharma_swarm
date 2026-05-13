#!/usr/bin/env bash
set -euo pipefail

LANE="${1:-${CODEX_LANE_NAME:-maintenance}}"
SESSION="codex_lane_${LANE}"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  tmux kill-session -t "${SESSION}"
  echo "Stopped session '${SESSION}'"
else
  echo "Session '${SESSION}' is not running"
fi
