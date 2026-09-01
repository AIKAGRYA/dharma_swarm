#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_tui_tmux_common.sh
source "${SCRIPT_DIR}/terminal_tui_tmux_common.sh"
terminal_tui_tmux_init

SCRIPT_REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROOT="${DHARMA_TERMINAL_ROOT:-${SCRIPT_REPO_ROOT}}"
if CANONICAL_ROOT="$(cd -- "${ROOT}" 2>/dev/null && pwd -P)"; then
  ROOT="${CANONICAL_ROOT}"
fi
SCRIPT_REPO_ROOT="$(cd -- "${SCRIPT_REPO_ROOT}" && pwd -P)"
ROOT_SOURCE="script-tree"
if [[ "${ROOT}" != "${SCRIPT_REPO_ROOT}" ]]; then
  ROOT_SOURCE="env-override"
  if [[ "${DHARMA_TERMINAL_ROOT_OVERRIDE_OK:-0}" != "1" ]]; then
    echo "DHARMA_TERMINAL_ROOT points this launcher at another tree's cockpit:" >&2
    echo "  override root: ${ROOT}" >&2
    echo "  script's tree: ${SCRIPT_REPO_ROOT}" >&2
    echo "A cockpit must not silently run another checkout's code (configured != served)." >&2
    echo "Set DHARMA_TERMINAL_ROOT_OVERRIDE_OK=1 to proceed deliberately, or unset DHARMA_TERMINAL_ROOT." >&2
    exit 2
  fi
  echo "WARNING: booting override root ${ROOT} (this launcher lives in ${SCRIPT_REPO_ROOT})" >&2
fi
SESSION="${TERMINAL_TUI_TMUX_SESSION}"
STATE_DIR="${TERMINAL_TUI_TMUX_STATE_DIR}"
LOG_FILE="${STATE_DIR}/session.log"
TERMINAL_DIR="${ROOT}/terminal"
PYTHON_BIN="${DHARMA_PYTHON:-}"
LIVENESS_TIMEOUT_SECONDS="${TERMINAL_TUI_LIVENESS_TIMEOUT_SECONDS:-10}"
CREATED_SESSION_BY_THIS_INVOCATION=0

if [[ ! "${LIVENESS_TIMEOUT_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "TERMINAL_TUI_LIVENESS_TIMEOUT_SECONDS must be a positive integer." >&2
  exit 2
fi

cleanup_invocation_created_session() {
  local status=$?

  trap - EXIT
  if [[ "${status}" -ne 0 \
    && "${CREATED_SESSION_BY_THIS_INVOCATION}" -eq 1 ]]; then
    terminal_tui_tmux kill-session -t "=${SESSION}" 2>/dev/null || true
    echo "Removed unhealthy session '${SESSION}' created by this launcher invocation." >&2
  fi
  exit "${status}"
}

trap cleanup_invocation_created_session EXIT

find_descendant_bridge_pid() {
  local parent_pid="$1"
  local child_pid=""
  local found=""

  while IFS= read -r child_pid; do
    [[ -z "${child_pid}" ]] && continue
    if ps -p "${child_pid}" -o command= 2>/dev/null \
      | grep -q "dharma_swarm.terminal_bridge stdio"; then
      echo "${child_pid}"
      return 0
    fi
    found="$(find_descendant_bridge_pid "${child_pid}")"
    if [[ -n "${found}" ]]; then
      echo "${found}"
      return 0
    fi
  done < <(pgrep -P "${parent_pid}" 2>/dev/null || true)
  return 1
}

verify_terminal_executor_liveness() {
  local deadline_seconds=$((SECONDS + LIVENESS_TIMEOUT_SECONDS))
  local pane_state=""
  local pane_dead=""
  local pane_pid=""
  local pane_command=""
  local bridge_pid=""

  while (( SECONDS < deadline_seconds )); do
    if ! terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
      echo "Terminal TUI session '${SESSION}' exited before becoming live." >&2
      return 1
    fi
    pane_state="$(
      terminal_tui_tmux display-message -p -t "=${SESSION}:" \
        '#{pane_dead}|#{pane_pid}|#{pane_current_command}' 2>/dev/null || true
    )"
    IFS='|' read -r pane_dead pane_pid pane_command <<<"${pane_state}"
    if [[ "${pane_dead}" == "1" || ! "${pane_pid}" =~ ^[1-9][0-9]*$ ]]; then
      echo "Terminal TUI executor is not live (${pane_state:-no pane state})." >&2
      return 1
    fi
    if ! kill -0 "${pane_pid}" 2>/dev/null; then
      echo "Terminal TUI executor is not live (${pane_state:-no pane state})." >&2
      return 1
    fi
    bridge_pid="$(find_descendant_bridge_pid "${pane_pid}" || true)"
    if [[ "${bridge_pid}" =~ ^[1-9][0-9]*$ ]] \
      && kill -0 "${bridge_pid}" 2>/dev/null; then
      echo "Executor: pid=${pane_pid} command=${pane_command} bridge_pid=${bridge_pid} bridge_process=live"
      return 0
    fi
    sleep 0.1
  done

  echo "Terminal TUI executor stayed live but no live Python bridge child appeared within ${LIVENESS_TIMEOUT_SECONDS} seconds." >&2
  return 1
}

if [[ -z "${PYTHON_BIN}" && -x "${ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT}/.venv/bin/python"
fi

if [[ -z "${PYTHON_BIN}" \
  && -n "${HOME:-}" \
  && -x "${HOME}/dharma_swarm/.venv/bin/python" ]]; then
  PYTHON_BIN="${HOME}/dharma_swarm/.venv/bin/python"
fi

if terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
  if ! verify_terminal_executor_liveness; then
    echo "Existing session '${SESSION}' was left unchanged; stop it explicitly before retrying." >&2
    exit 1
  fi
  echo "Session '${SESSION}' already running on socket '${TERMINAL_TUI_TMUX_SOCKET}' and verified live."
  terminal_tui_print_receipt 120
  exit 0
fi

mkdir -p "${STATE_DIR}"

START_CMD="cd $(printf '%q' "${TERMINAL_DIR}") && "
if [[ -n "${PYTHON_BIN}" ]]; then
  START_CMD+="DHARMA_PYTHON=$(printf '%q' "${PYTHON_BIN}") "
fi
START_CMD+="bun run src/index.tsx"

terminal_tui_tmux new-session -d -s "${SESSION}" "${START_CMD}"
CREATED_SESSION_BY_THIS_INVOCATION=1
terminal_tui_tmux pipe-pane -o -t "=${SESSION}:" \
  "cat >> $(printf '%q' "${LOG_FILE}")"
verify_terminal_executor_liveness
CREATED_SESSION_BY_THIS_INVOCATION=0

echo "Started and verified terminal TUI session '${SESSION}'"
echo "Terminal dir: ${TERMINAL_DIR}"
echo "Root: ${ROOT} (${ROOT_SOURCE})"
echo "Python: ${PYTHON_BIN:-python3}"
echo "State dir: ${STATE_DIR}"
echo "Log file: ${LOG_FILE}"
terminal_tui_print_receipt 120
trap - EXIT
