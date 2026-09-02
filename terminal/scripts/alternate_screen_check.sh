#!/usr/bin/env bash
# Ink 7 runtime verifier: prove the root renderer owns the terminal alternate
# buffer and survives a compact -> panorama -> compact resize round trip.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=terminal/scripts/lib/codex_managed_tmux.sh
source "${SCRIPT_DIR}/lib/codex_managed_tmux.sh"
BUN_BIN="$(command -v bun || true)"
SESSION="helm"
STATE_DIR="$(mktemp -d)"

cleanup() {
  codex_managed_tmux_cleanup || true
  find "${STATE_DIR}" -mindepth 1 -delete 2>/dev/null || true
  rmdir "${STATE_DIR}" 2>/dev/null || true
}
trap cleanup EXIT

fail() {
  echo "alternate_screen_check: FAIL — $1" >&2
  if [[ -n "${CODEX_MANAGED_TMUX_SOCKET:-}" ]]; then
    codex_managed_tmux capture-pane -pt "${SESSION}:0.0" 2>/dev/null \
      | head -24 >&2 || true
  fi
  exit 1
}

codex_managed_tmux_init alternate_screen \
  || fail "could not initialize private tmux server"
[[ -n "${BUN_BIN}" ]] || fail "bun is required"
[[ -d "${TERMINAL_DIR}/node_modules" ]] || fail "terminal/node_modules is missing"

printf -v START_COMMAND \
  'env DHARMA_PYTHON=%q DHARMA_TERMINAL_STATE_DIR=%q DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=%q %q run start' \
  "/nonexistent/dharma-terminal-alternate-screen-check-python" \
  "${STATE_DIR}" \
  "${STATE_DIR}" \
  "${BUN_BIN}"

codex_managed_tmux new-session \
  -d -s "${SESSION}" -x 80 -y 24 -c "${TERMINAL_DIR}" \
  "sleep 1; exec ${START_COMMAND}" \
  || fail "could not create isolated tmux session"
codex_managed_tmux set-option -g status off \
  || fail "could not disable private tmux status row"
codex_managed_tmux resize-window -t "${SESSION}:0" -x 80 -y 24 \
  || fail "could not resize private tmux window"

deadline=$(( $(date +%s) + 20 ))
while [[ "$(date +%s)" -lt "${deadline}" ]]; do
  frame="$(codex_managed_tmux capture-pane -pt "${SESSION}:0.0" 2>/dev/null || true)"
  if [[ "${frame}" == *"Dharma Helm"* || "${frame}" == *"DHARMA HELM"* ]]; then
    break
  fi
  sleep 0.25
done

assert_state() {
  local expected_geometry=$1
  local state
  state="$(codex_managed_tmux display-message -p -t "${SESSION}:0.0" \
    '#{pane_width}x#{pane_height} alternate=#{alternate_on} dead=#{pane_dead}')"
  [[ "${state}" == "${expected_geometry} alternate=1 dead=0" ]] \
    || fail "observed '${state}', expected '${expected_geometry} alternate=1 dead=0'"
  echo "alternate_screen_check: ${state}"
}

assert_state "80x24"
codex_managed_tmux resize-window -t "${SESSION}" -x 120 -y 40
sleep 0.5
assert_state "120x40"
codex_managed_tmux resize-window -t "${SESSION}" -x 80 -y 24
sleep 0.5
assert_state "80x24"

frame="$(codex_managed_tmux capture-pane -pt "${SESSION}:0.0")"
[[ "${frame}" == *"?/7"* ]] || fail "compact truth band disappeared after resize"
[[ "${frame}" == *"offline"* || "${frame}" == *"bridge"* ]] \
  || fail "bridge/offline status disappeared after resize"

echo "alternate_screen_check: OK"
