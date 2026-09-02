#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_tui_tmux_common.sh
source "${SCRIPT_DIR}/terminal_tui_tmux_common.sh"
terminal_tui_tmux_init

SESSION="${TERMINAL_TUI_TMUX_SESSION}"

if terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
  terminal_tui_tmux kill-session -t "=${SESSION}"
  echo "Stopped session '${SESSION}' on socket '${TERMINAL_TUI_TMUX_SOCKET}'."
else
  echo "Session '${SESSION}' not running on socket '${TERMINAL_TUI_TMUX_SOCKET}'."
fi
