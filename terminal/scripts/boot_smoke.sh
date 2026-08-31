#!/usr/bin/env bash
# L0 boot smoke (F-002): hermetic tmux boot of the Dharma Terminal at 80x24.
# Green = the app renders a non-empty frame with graceful offline degradation
# (no Python bridge present; the boot frame is ZEN, whose status line carries
# the durable "offline" token — FACE-1), then exits cleanly on Ctrl-C.
# Override the start command for negative checks: BOOT_SMOKE_START_CMD="..."
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
# shellcheck source=terminal/scripts/lib/codex_managed_tmux.sh
source "$SCRIPT_DIR/lib/codex_managed_tmux.sh"

SESS="helm-smoke-$$-$RANDOM"
STATEDIR=$(mktemp -d)
START_CMD=${BOOT_SMOKE_START_CMD:-bun run start}
BOOT_TIMEOUT=${BOOT_SMOKE_TIMEOUT:-20}
EXIT_TIMEOUT=${BOOT_SMOKE_EXIT_TIMEOUT:-10}

# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2329
cleanup() {
  codex_managed_tmux_cleanup || true
  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null
  rmdir "$STATEDIR" 2>/dev/null
}
trap cleanup EXIT

fail() {
  echo "boot_smoke: FAIL — $1" >&2
  exit 1
}

codex_managed_tmux_init boot_smoke || fail "could not initialize private tmux server"

codex_managed_tmux new-session -d -s "$SESS" -x 80 -y 24 \
  "sleep 1; cd '$TERMINAL_DIR' && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR='$STATEDIR' DHARMA_TERMINAL_SUPERVISOR_STATE_DIR='$STATEDIR' $START_CMD" \
  || fail "could not create tmux session"
codex_managed_tmux set-option -g status off \
  || fail "could not disable private tmux status row"
codex_managed_tmux resize-window -t "$SESS:0" -x 80 -y 24 \
  || fail "could not resize private tmux window"
dimensions=$(codex_managed_tmux display-message -p -t "$SESS:0.0" \
  '#{pane_width}x#{pane_height}')
[ "$dimensions" = "80x24" ] || fail "expected 80x24 pane, got $dimensions"

# Poll until the offline-degradation text renders (no fixed-sleep-only race).
frame=""
deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! codex_managed_tmux has-session -t "$SESS" 2>/dev/null; then
    break # app process died before rendering — negative path
  fi
  frame=$(codex_managed_tmux capture-pane -t "$SESS" -p 2>/dev/null || true)
  if grep -q "offline" <<<"$frame"; then
    break
  fi
  sleep 0.5
done

[ -n "$(printf '%s' "$frame" | tr -d '[:space:]')" ] || fail "captured frame is empty"
grep -q "offline" <<<"$frame" \
  || fail "frame lacks 'offline' degradation text; frame was: $(printf '%s' "$frame" | head -c 400)"

printf '%s\n' "$frame"

# Clean exit: Ctrl-C into the app, then poll until the session is gone.
codex_managed_tmux send-keys -t "$SESS" C-c
deadline=$(( $(date +%s) + EXIT_TIMEOUT ))
while codex_managed_tmux has-session -t "$SESS" 2>/dev/null; do
  [ "$(date +%s)" -lt "$deadline" ] || fail "app did not exit within ${EXIT_TIMEOUT}s of Ctrl-C"
  sleep 0.5
done

echo "boot_smoke: OK"
exit 0
