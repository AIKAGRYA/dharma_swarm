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

if ! TMUX_BIN="$(command -v tmux)"; then
  echo "golden_capture: tmux is required" >&2
  exit 127
fi
if ! BUN_BIN="$(command -v bun)"; then
  echo "golden_capture: bun is required" >&2
  exit 127
fi
if [[ ! "${SIZE}" =~ ^([1-9][0-9]*)x([1-9][0-9]*)$ ]]; then
  echo "golden_capture: invalid GOLDEN_SIZE '${SIZE}' (expected WIDTHxHEIGHT)" >&2
  exit 2
fi

WIDTH="${BASH_REMATCH[1]}"
HEIGHT="${BASH_REMATCH[2]}"
OUT_DIR="${OUT_ROOT}/${SIZE}"
OUT_FILE="${OUT_DIR}/chat.txt"
SESSION_NAME="${GOLDEN_SESSION_NAME:-dharma_terminal_golden_$$}"
if [[ ! "${SESSION_NAME}" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "golden_capture: invalid GOLDEN_SESSION_NAME '${SESSION_NAME}'" >&2
  exit 2
fi

STATE_DIR="$(mktemp -d)"
SESSION_STARTED=false

# Invoked through the EXIT trap below.
# shellcheck disable=SC2329
cleanup() {
  if [[ "${SESSION_STARTED}" == true ]]; then
    "${TMUX_BIN}" kill-session -t "=${SESSION_NAME}" >/dev/null 2>&1 || true
  fi
  rm -r -- "${STATE_DIR}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

mkdir -p "${OUT_DIR}"

if "${TMUX_BIN}" has-session -t "=${SESSION_NAME}" >/dev/null 2>&1; then
  echo "golden_capture: tmux session '${SESSION_NAME}' already exists" >&2
  exit 2
fi

printf -v START_COMMAND \
  'env DHARMA_PYTHON=%q DHARMA_TERMINAL_STATE_DIR=%q DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=%q COLUMNS=%q LINES=%q %q run start' \
  "/nonexistent/dharma-terminal-golden-python" "${STATE_DIR}" "${STATE_DIR}" "${WIDTH}" "${HEIGHT}" "${BUN_BIN}"
"${TMUX_BIN}" new-session -d -s "${SESSION_NAME}" -x "${WIDTH}" -y "${HEIGHT}" -c "${TERMINAL_DIR}" \
  "${START_COMMAND}"
SESSION_STARTED=true

ACTUAL_SIZE="$("${TMUX_BIN}" display-message -p -t "${SESSION_NAME}:0.0" '#{pane_width}x#{pane_height}')"
if [[ "${ACTUAL_SIZE}" != "${SIZE}" ]]; then
  echo "golden_capture: tmux geometry is ${ACTUAL_SIZE}, expected ${SIZE}" >&2
  exit 1
fi

deadline=$(( $(date +%s) + 12 ))
while [ "$(date +%s)" -lt "${deadline}" ]; do
  if ! "${TMUX_BIN}" has-session -t "=${SESSION_NAME}" >/dev/null 2>&1; then
    echo "golden_capture: terminal exited before capture" >&2
    exit 1
  fi
  frame="$("${TMUX_BIN}" capture-pane -t "${SESSION_NAME}:0.0" -p 2>/dev/null || true)"
  if [[ "${frame}" == *"Operator Prompt"* \
    && "${frame}" == *"backend offline, retrying"* \
    && "${frame}" == *"route"* \
    && "${frame}" == *"keys"* ]]; then
    printf "%s\n" "${frame}" > "${OUT_FILE}"
    echo "golden_capture: wrote ${OUT_FILE}"
    exit 0
  fi
  sleep 0.3
done

echo "golden_capture: shell did not settle at ${SIZE}" >&2
"${TMUX_BIN}" capture-pane -t "${SESSION_NAME}:0.0" -p 2>/dev/null | sed -n '1,80p' >&2 || true
exit 1
