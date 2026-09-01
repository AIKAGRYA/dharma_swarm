#!/usr/bin/env bash
# PTY input-probe smoke (F-005): drives the real app through a tmux
# pseudo-terminal, sends the probe string one keystroke at a time, and asserts
# every character echoes in the composer. This is the green-gate for any
# future Bun version bump (stdin raw-mode handling through a real TTY).
# Overrides: PTY_SMOKE_START_CMD (negative checks), PTY_SMOKE_PROBE,
#            PTY_SMOKE_TIMEOUT, PTY_SMOKE_ECHO_TIMEOUT, PTY_SMOKE_EXIT_TIMEOUT.
# Probe characters must avoid the globally bound printables: [ ] 1 2 3
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
# shellcheck source=terminal/scripts/lib/codex_managed_tmux.sh
source "$SCRIPT_DIR/lib/codex_managed_tmux.sh"

SESS="helm-pty-$$-$RANDOM"
STATEDIR=$(mktemp -d)
START_CMD=${PTY_SMOKE_START_CMD:-bun run start}
PROBE=${PTY_SMOKE_PROBE:-helmprobe}
BOOT_TIMEOUT=${PTY_SMOKE_TIMEOUT:-20}
ECHO_TIMEOUT=${PTY_SMOKE_ECHO_TIMEOUT:-10}
EXIT_TIMEOUT=${PTY_SMOKE_EXIT_TIMEOUT:-10}

# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2329
cleanup() {
  codex_managed_tmux_cleanup || true
  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null
  rmdir "$STATEDIR" 2>/dev/null
}
trap cleanup EXIT

fail() {
  echo "pty_smoke: FAIL — $1" >&2
  exit 1
}

codex_managed_tmux_init pty_smoke || fail "could not initialize private tmux server"

[ "${#PROBE}" -ge 5 ] || fail "probe must be at least 5 keystrokes (got ${#PROBE})"
case "$PROBE" in
  *\[*|*\]*|*1*|*2*|*3*) fail "probe contains a globally bound key ([ ] 1 2 3) that will not echo" ;;
esac

echo "pty_smoke: bun $(bun --version 2>/dev/null || echo '?') — probe '$PROBE' (${#PROBE} keystrokes)"

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

# Wait until the app is interactive (same readiness signal as boot_smoke).
frame=""
deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! codex_managed_tmux has-session -t "$SESS" 2>/dev/null; then
    break # app died before rendering — negative path
  fi
  frame=$(codex_managed_tmux capture-pane -t "$SESS" -p 2>/dev/null || true)
  # FACE-1: zen boot frame carries the durable "offline" token in its status line.
  if grep -q "offline" <<<"$frame"; then
    break
  fi
  sleep 0.5
done
grep -q "offline" <<<"$frame" \
  || fail "app never rendered interactive frame; frame was: $(printf '%s' "$frame" | head -c 300)"

# Send the probe one keystroke at a time through the pty (-l = literal).
i=0
while [ "$i" -lt "${#PROBE}" ]; do
  ch=${PROBE:$i:1}
  codex_managed_tmux send-keys -t "$SESS" -l "$ch" \
    || fail "send-keys failed at keystroke $((i + 1))"
  i=$((i + 1))
  sleep 0.05
done

# Poll until the full probe has echoed after the composer caret.
deadline=$(( $(date +%s) + ECHO_TIMEOUT ))
echoed=""
while [ "$(date +%s)" -lt "$deadline" ]; do
  frame=$(codex_managed_tmux capture-pane -t "$SESS" -p 2>/dev/null || true)
  if grep -qF "> $PROBE" <<<"$frame"; then
    echoed=yes
    break
  fi
  sleep 0.5
done
[ -n "$echoed" ] \
  || fail "probe '$PROBE' did not echo in the composer; frame was: $(printf '%s' "$frame" | head -c 600)"

printf '%s\n' "$frame"

# Clean exit: Ctrl-C into the app, then poll until the session is gone.
codex_managed_tmux send-keys -t "$SESS" C-c
deadline=$(( $(date +%s) + EXIT_TIMEOUT ))
while codex_managed_tmux has-session -t "$SESS" 2>/dev/null; do
  [ "$(date +%s)" -lt "$deadline" ] || fail "app did not exit within ${EXIT_TIMEOUT}s of Ctrl-C"
  sleep 0.5
done

echo "pty_smoke: OK — ${#PROBE} keystrokes echoed in composer"
exit 0
