#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_tui_tmux_common.sh
source "${SCRIPT_DIR}/terminal_tui_tmux_common.sh"
terminal_tui_tmux_init

SESSION="${TERMINAL_TUI_TMUX_SESSION}"
STATE_DIR="${TERMINAL_TUI_TMUX_STATE_DIR}"
LOG_FILE="${STATE_DIR}/session.log"
RUNNING=0

terminal_tui_print_receipt 80
echo

if terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
  RUNNING=1
  echo "Session '${SESSION}' on socket '${TERMINAL_TUI_TMUX_SOCKET}': RUNNING"
else
  echo "Session '${SESSION}' on socket '${TERMINAL_TUI_TMUX_SOCKET}': NOT RUNNING"
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo
  echo "Recent log:"
  tail -n 40 "${LOG_FILE}"
fi

if [[ "${RUNNING}" -eq 1 ]]; then
  echo
  echo "Pane snapshot:"
  terminal_tui_tmux capture-pane -pt "=${SESSION}:" -S -80
fi
