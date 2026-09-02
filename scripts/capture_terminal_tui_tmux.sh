#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_tui_tmux_common.sh
source "${SCRIPT_DIR}/terminal_tui_tmux_common.sh"
terminal_tui_tmux_init

SESSION="${TERMINAL_TUI_TMUX_SESSION}"
LINES="${1:-120}"

if [[ ! "${LINES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Capture line count must be a positive integer (got '${LINES}')." >&2
  exit 2
fi

if ! terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' not running on socket '${TERMINAL_TUI_TMUX_SOCKET}'."
  exit 1
fi

terminal_tui_tmux capture-pane -pt "=${SESSION}:" -S "-${LINES}"
