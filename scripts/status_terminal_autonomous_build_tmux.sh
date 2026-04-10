#!/usr/bin/env bash
set -euo pipefail

SESSION="${SESSION_NAME:-dharma_terminal_autonomous_build}"
STATE_DIR="${DGC_TERMINAL_AUTONOMOUS_BUILD_STATE_DIR:-${HOME}/.dharma/terminal_autonomous_build}"
RUN_FILE="${STATE_DIR}/latest_run.txt"

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}': RUNNING"
else
  echo "Session '${SESSION}': NOT RUNNING"
fi

if [[ -f "${RUN_FILE}" ]]; then
  echo
  RUN_DIR="$(cat "${RUN_FILE}")"
  echo "Run dir: ${RUN_DIR}"

  if [[ -f "${RUN_DIR}/manifest.env" ]]; then
    echo
    echo "Manifest:"
    cat "${RUN_DIR}/manifest.env"
  fi

  if [[ -f "${RUN_DIR}/terminal_autonomous_build_prompt.md" ]]; then
    echo
    echo "Prompt:"
    sed -n '1,220p' "${RUN_DIR}/terminal_autonomous_build_prompt.md"
  fi

  if [[ -f "${RUN_DIR}/claude_terminal_autonomous_build.log" ]]; then
    echo
    echo "Latest log tail:"
    tail -n 40 "${RUN_DIR}/claude_terminal_autonomous_build.log"
  fi
fi
