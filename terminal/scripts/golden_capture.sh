#!/usr/bin/env bash
# Capture the current terminal shell into the tracked golden corpus.
#
# This is intentionally small and hermetic for the active-track closeout:
# it captures the boot chat surface at 120x40 with an invalid bridge Python,
# so the frame is not coupled to live daemon, provider, or key state.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_ROOT="${GOLDEN_OUT_DIR:-${TERMINAL_DIR}/tests/golden}"
SIZE="${GOLDEN_SIZE:-120x40}"
WIDTH="${SIZE%x*}"
HEIGHT="${SIZE#*x}"
OUT_DIR="${OUT_ROOT}/${SIZE}"
OUT_FILE="${OUT_DIR}/chat.txt"
SESSION_NAME="${GOLDEN_SESSION_NAME:-dharma_terminal_golden_$$}"
STATE_DIR="$(mktemp -d)"

cleanup() {
  tmux kill-session -t "${SESSION_NAME}" >/dev/null 2>&1 || true
  rm -rf "${STATE_DIR}"
}
trap cleanup EXIT

mkdir -p "${OUT_DIR}"

tmux new-session -d -s "${SESSION_NAME}" -x "${WIDTH}" -y "${HEIGHT}" \
  "cd '${TERMINAL_DIR}' && DHARMA_PYTHON=/nonexistent/dharma-terminal-golden-python DHARMA_TERMINAL_STATE_DIR='${STATE_DIR}' DHARMA_TERMINAL_SUPERVISOR_STATE_DIR='${STATE_DIR}' COLUMNS='${WIDTH}' LINES='${HEIGHT}' bun run start"

deadline=$(( $(date +%s) + 12 ))
while [ "$(date +%s)" -lt "${deadline}" ]; do
  if ! tmux has-session -t "${SESSION_NAME}" >/dev/null 2>&1; then
    echo "golden_capture: terminal exited before capture" >&2
    exit 1
  fi
  frame="$(tmux capture-pane -t "${SESSION_NAME}" -p 2>/dev/null || true)"
  if printf "%s" "${frame}" | grep -q "Operator Prompt" \
    && printf "%s" "${frame}" | grep -q "backend offline, retrying" \
    && printf "%s" "${frame}" | grep -q "route" \
    && printf "%s" "${frame}" | grep -q "keys"; then
    printf "%s\n" "${frame}" > "${OUT_FILE}"
    echo "golden_capture: wrote ${OUT_FILE}"
    exit 0
  fi
  sleep 0.3
done

echo "golden_capture: shell did not settle at ${SIZE}" >&2
tmux capture-pane -t "${SESSION_NAME}" -p 2>/dev/null | head -80 >&2 || true
exit 1
