#!/usr/bin/env bash
# F-157 verification: a prompt sent while the bridge is down renders as
# `queued (backend offline)` within 2 seconds and NEVER a perpetual running
# state; when the bridge connects, queued turns dispatch (or are marked failed).
#
# Mechanism: DHARMA_PYTHON points at a gate path that does not exist at boot
# (hermetic offline, bridge_spawn_error -> offline). Mid-test the gate becomes a
# symlink to scripts/stub_bridge.py; the app's reconnect probe (15s cadence,
# capped backoff) spawns it, the bridge connects, and the queued turn must
# resolve to the stub's response text.
#
# Asserts:
#   1. within 2s of Enter, the turn row matches '○ queued (backend offline) · <route> · ^T details';
#   2. at +10s the turn row is unchanged — no '▶' glyph and no 'running' text anywhere in the frame;
#   3. no optimistic local steps (bootstrapping context / selecting route) in the expanded trace;
#   4. after the gate opens, the turn transitions: response text renders with a ✓ summary,
#      and the queued row is gone.
# Exit 0 = PASS, exit 1 = FAIL naming the violated assertion.
set -u

TERMINAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESS="helm-f157-$RANDOM"
STATEDIR="$(mktemp -d)"
WORKDIR="$(mktemp -d)"
CAPDIR="${OFFLINE_QUEUE_OUT_DIR:-$(mktemp -d)}"
GATE="$WORKDIR/python_gate"
PROMPT="what is the helm"
QUEUED_ROW='○ queued \(backend offline\) · .+ · \^T details'
RESPONSE_TEXT="The Helm hears you loud and clear."
DONE_ROW='✓ ([0-9]+s|done) · .+ · \^T details'

cleanup() {
  tmux kill-session -t "$SESS" 2>/dev/null || true
  for d in "$STATEDIR" "$WORKDIR"; do
    find "$d" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$d" 2>/dev/null || true
  done
  if [ -z "${OFFLINE_QUEUE_OUT_DIR:-}" ]; then
    find "$CAPDIR" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$CAPDIR" 2>/dev/null || true
  fi
}

fail() {
  echo "offline_queue_check: FAIL — $1" >&2
  tmux capture-pane -t "$SESS" -p 2>/dev/null | sed 's/^/  | /' >&2 || true
  cleanup
  exit 1
}

capture() {
  tmux capture-pane -t "$SESS" -p
}

wait_for() {
  # wait_for <egrep pattern> <label> <attempts> <sleep>
  local pattern="$1" label="$2" attempts="$3" pause="$4" _attempt frame
  for _attempt in $(seq 1 "$attempts"); do
    frame="$(capture 2>/dev/null || true)"
    if echo "$frame" | grep -qE "$pattern"; then
      return 0
    fi
    sleep "$pause"
  done
  fail "$label never appeared"
}

[ -e "$GATE" ] && fail "gate path pre-exists"

tmux new-session -d -s "$SESS" -x 120 -y 40 \
  "cd $TERMINAL_DIR && COLORTERM=truecolor DHARMA_PYTHON=$GATE DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start" \
  || fail "tmux session failed to start"

# FACE-1: the boot frame is zen — its status line carries the durable "offline" token.
wait_for "offline" "offline boot frame (zen status line)" 40 0.5

tmux send-keys -t "$SESS" -l "$PROMPT"
sleep 0.3
tmux send-keys -t "$SESS" Enter

# 1. queued row within 2 seconds of Enter (10 polls x 0.2s).
queued_seen=""
for _attempt in $(seq 1 10); do
  frame="$(capture 2>/dev/null || true)"
  if echo "$frame" | grep -qE "$QUEUED_ROW"; then
    queued_seen=1
    break
  fi
  sleep 0.2
done
[ -n "$queued_seen" ] || fail "turn row 'queued (backend offline)' did not appear within 2s of Enter"
capture > "$CAPDIR/queued_2s.txt"

# 2. +10s: still queued, never running.
sleep 10
capture > "$CAPDIR/queued_12s.txt"
grep -qE "$QUEUED_ROW" "$CAPDIR/queued_12s.txt" || fail "queued turn row vanished by +10s without a bridge connection"
grep -q "▶" "$CAPDIR/queued_12s.txt" && fail "running glyph ▶ present on an offline turn at +10s"
grep -qiE "running" "$CAPDIR/queued_12s.txt" && fail "'running' text present in the +10s offline frame"

# 3. no optimistic local steps on the offline turn (expand the trace to look).
tmux send-keys -t "$SESS" C-t
sleep 1
capture > "$CAPDIR/queued_expanded.txt"
grep -qE "bootstrapping context|selecting route" "$CAPDIR/queued_expanded.txt" \
  && fail "optimistic local steps rendered on an offline turn"
grep -qF "Status | queued (backend offline)" "$CAPDIR/queued_expanded.txt" \
  || fail "expanded trace missing the queued status step"
tmux send-keys -t "$SESS" C-t
sleep 1

# 4. open the gate — the reconnect probe (15s cadence + capped backoff) must
#    connect and resolve the queued turn to a dispatched, completed response.
ln -s "$TERMINAL_DIR/scripts/stub_bridge.py" "$GATE" || fail "could not link stub bridge into the gate path"

resolved=""
for _attempt in $(seq 1 120); do
  frame="$(capture 2>/dev/null || true)"
  if echo "$frame" | grep -qF "$RESPONSE_TEXT"; then
    resolved=1
    break
  fi
  sleep 0.5
done
[ -n "$resolved" ] || fail "queued turn never resolved after the bridge became reachable (waited 60s)"
capture > "$CAPDIR/resolved.txt"
grep -qE "$DONE_ROW" "$CAPDIR/resolved.txt" || fail "resolved turn missing its ✓ summary row"
grep -qE "$QUEUED_ROW" "$CAPDIR/resolved.txt" && fail "queued row still present after dispatch"

echo "offline_queue_check: OK (queued (backend offline) within 2s, no running state at +10s, no optimistic steps, dispatched + completed on connect)"
cleanup
exit 0
