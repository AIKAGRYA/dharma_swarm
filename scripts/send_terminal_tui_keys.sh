#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_tui_tmux_common.sh
source "${SCRIPT_DIR}/terminal_tui_tmux_common.sh"
terminal_tui_tmux_init

SESSION="${TERMINAL_TUI_TMUX_SESSION}"

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 [--literal <text> | <keys...>]"
  echo "Example: $0 Tab Enter"
  echo "Example: $0 --literal '/help'"
  exit 1
fi

if ! terminal_tui_tmux has-session -t "=${SESSION}" 2>/dev/null; then
  echo "Session '${SESSION}' not running on socket '${TERMINAL_TUI_TMUX_SOCKET}'."
  exit 1
fi

if [[ "${1:-}" == "--literal" || "${1:-}" == "--text" ]]; then
  if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 --literal <text>"
    exit 1
  fi
  terminal_tui_tmux send-keys -l -t "=${SESSION}:" "$2"
  echo "Sent literal text to '${SESSION}' on socket '${TERMINAL_TUI_TMUX_SOCKET}': $2"
  exit 0
fi

terminal_tui_tmux send-keys -t "=${SESSION}:" "$@"
echo "Sent keys to '${SESSION}' on socket '${TERMINAL_TUI_TMUX_SOCKET}': $*"
