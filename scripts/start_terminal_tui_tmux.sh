#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${DHARMA_TERMINAL_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
SESSION="${SESSION_NAME:-dharma_terminal_tui}"
STATE_DIR="${DHARMA_TERMINAL_TUI_STATE_DIR:-${HOME}/.dharma/terminal_tui}"
LOG_FILE="${STATE_DIR}/session.log"
TERMINAL_DIR="${ROOT}/terminal"
PYTHON_BIN="${DHARMA_PYTHON:-}"

if [[ -z "${PYTHON_BIN}" && -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT}/.venv/bin/python"
fi

if [[ -z "${PYTHON_BIN}" && -x "${HOME}/dharma_swarm/.venv/bin/python" ]]; then
  PYTHON_BIN="${HOME}/dharma_swarm/.venv/bin/python"
fi

if tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' already running."
  exit 0
fi

mkdir -p "${STATE_DIR}"

START_CMD="cd $(printf '%q' "${TERMINAL_DIR}") && "
if [[ -n "${PYTHON_BIN}" ]]; then
  START_CMD+="DHARMA_PYTHON=$(printf '%q' "${PYTHON_BIN}") "
fi
START_CMD+="bun run src/index.tsx"

tmux new-session -d -s "${SESSION}" "${START_CMD}"
tmux pipe-pane -o -t "${SESSION}" "cat >> '${LOG_FILE}'"

echo "Started terminal TUI session '${SESSION}'"
echo "Terminal dir: ${TERMINAL_DIR}"
echo "Python: ${PYTHON_BIN:-python3}"
echo "State dir: ${STATE_DIR}"
echo "Log file: ${LOG_FILE}"
echo "Attach: tmux attach -t ${SESSION}"
echo "Capture: scripts/capture_terminal_tui_tmux.sh"
