#!/usr/bin/env bash
# F-172 verification: trace collapse by default.
# Boots the app against scripts/stub_bridge.py (scripted wire-protocol stub),
# completes one turn, then asserts:
#   1. response text renders ABOVE exactly one collapsed trace summary line
#      matching '■ <n>s · <route> · ^T details' (FACE-1 zen summary);
#   2. no hex-id token [0-9a-f]{12,} anywhere in the captured transcript frame;
#   3. trace step detail absent before ^T, present after ^T, absent again
#      after a second ^T — hex ids absent in BOTH expansion states.
# Exit 0 = PASS, exit 1 = FAIL naming the violated assertion.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=terminal/scripts/lib/codex_managed_tmux.sh
source "${SCRIPT_DIR}/lib/codex_managed_tmux.sh"

SESS="helm-f172-$RANDOM"
STATEDIR="$(mktemp -d)"
CAPDIR="${TRACE_CHECK_OUT_DIR:-$(mktemp -d)}"
RESPONSE_TEXT="The Helm hears you loud and clear."
STEP_DETAIL="weighing the reply"
SUMMARY_EXPAND='■ ([0-9]+s|done) · .+ · \^T details'
HEX_ID='[0-9a-fA-F]{12,}'

cleanup() {
  local status="$1"

  trap - EXIT
  if ! codex_managed_tmux_cleanup; then
    echo "trace_collapse_check: managed tmux cleanup failed — preserving state dir '$STATEDIR' and capture dir '$CAPDIR'" >&2
    if [ "$status" -eq 0 ]; then
      return 1
    fi
    return "$status"
  fi

  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$STATEDIR" 2>/dev/null || true
  if [ -z "${TRACE_CHECK_OUT_DIR:-}" ]; then
    find "$CAPDIR" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$CAPDIR" 2>/dev/null || true
  fi
  return "$status"
}
trap 'cleanup "$?"; exit $?' EXIT

fail() {
  echo "trace_collapse_check: FAIL — $1" >&2
  codex_managed_tmux capture-pane -t "$SESS" -p 2>/dev/null \
    | sed 's/^/  | /' >&2 || true
  exit 1
}

capture() {
  codex_managed_tmux capture-pane -t "$SESS" -p
}

wait_for() {
  # wait_for <egrep pattern> <label> [absent-pattern]
  local pattern="$1" label="$2" _attempt frame
  for _attempt in $(seq 1 40); do
    frame="$(capture 2>/dev/null || true)"
    if grep -qE "$pattern" <<<"$frame"; then
      if [ -n "${3:-}" ] && grep -qE "$3" <<<"$frame"; then
        sleep 0.5
        continue
      fi
      return 0
    fi
    sleep 0.5
  done
  fail "$label never appeared (waited 20s)"
}

codex_managed_tmux_init trace_collapse \
  || fail "could not initialize private tmux server"
codex_managed_tmux new-session -d -s "$SESS" -x 100 -y 30 \
  "sleep 1; cd '$TERMINAL_DIR' && COLORTERM=truecolor DHARMA_PYTHON='$TERMINAL_DIR/scripts/stub_bridge.py' DHARMA_TERMINAL_STATE_DIR='$STATEDIR' DHARMA_TERMINAL_SUPERVISOR_STATE_DIR='$STATEDIR' bun run start" \
  || fail "private tmux session failed to start"
codex_managed_tmux set-option -g status off \
  || fail "could not disable private tmux status row"
codex_managed_tmux resize-window -t "$SESS:0" -x 100 -y 30 \
  || fail "could not resize private tmux window"
dimensions="$(codex_managed_tmux display-message -p -t "$SESS:0.0" \
  '#{pane_width}x#{pane_height}')"
[ "$dimensions" = "100x30" ] \
  || fail "expected 100x30 pane, got $dimensions"

wait_for "Dharma Helm" "app boot frame"
# FACE-1: zen names bridge connectivity without claiming provider liveness
# (transient statusLine text no longer renders in zen).
wait_for "backend connected|bridge ready|resyncing|bridge connected|● bridge" "stub bridge handshake"

codex_managed_tmux send-keys -t "$SESS" -l "what is the helm"
sleep 0.5
codex_managed_tmux send-keys -t "$SESS" Enter

wait_for "$SUMMARY_EXPAND" "collapsed trace summary line"
sleep 0.5
capture > "$CAPDIR/collapsed.txt"

# 1. response present, exactly one summary line, response ABOVE it
grep -qF "$RESPONSE_TEXT" "$CAPDIR/collapsed.txt" || fail "response text missing from collapsed frame"
summary_count="$(grep -cE "$SUMMARY_EXPAND" "$CAPDIR/collapsed.txt")"
[ "$summary_count" -eq 1 ] || fail "expected exactly 1 collapsed summary line, found $summary_count"
response_line="$(grep -nF "$RESPONSE_TEXT" "$CAPDIR/collapsed.txt" | head -1 | cut -d: -f1)"
summary_line="$(grep -nE "$SUMMARY_EXPAND" "$CAPDIR/collapsed.txt" | head -1 | cut -d: -f1)"
[ "$response_line" -lt "$summary_line" ] || fail "response (line $response_line) not above summary (line $summary_line)"

# 2. no expanded step detail on first paint, no hex ids anywhere
grep -qF "$STEP_DETAIL" "$CAPDIR/collapsed.txt" && fail "trace step detail visible before ^T"
grep -qE "$HEX_ID" "$CAPDIR/collapsed.txt" && fail "hex id token rendered in collapsed frame: $(grep -oE "$HEX_ID" "$CAPDIR/collapsed.txt" | head -1)"

# 3. ^T expands: step detail visible, still no hex ids. The expanded trace can be
# taller than the transcript window (the summary line scrolls above the fold), so
# the visible-frame anchor is the step detail; exactly-one-summary-line in the
# expanded projection is asserted by the F-172 unit test in executionLog.test.ts.
codex_managed_tmux send-keys -t "$SESS" Escape
sleep 0.2
codex_managed_tmux send-keys -t "$SESS" C-t
wait_for "$STEP_DETAIL" "expanded trace step detail"
sleep 0.5
capture > "$CAPDIR/expanded.txt"
grep -qF "$STEP_DETAIL" "$CAPDIR/expanded.txt" || fail "trace step detail missing after ^T expand"
grep -qE "$HEX_ID" "$CAPDIR/expanded.txt" && fail "hex id token rendered in expanded frame: $(grep -oE "$HEX_ID" "$CAPDIR/expanded.txt" | head -1)"

# 4. second ^T collapses back: detail gone again
codex_managed_tmux send-keys -t "$SESS" C-t
wait_for "$SUMMARY_EXPAND" "re-collapsed trace summary line"
sleep 0.5
capture > "$CAPDIR/recollapsed.txt"
grep -qF "$STEP_DETAIL" "$CAPDIR/recollapsed.txt" && fail "trace step detail still visible after second ^T"
grep -qE "$HEX_ID" "$CAPDIR/recollapsed.txt" && fail "hex id token rendered in re-collapsed frame"

cleanup 0
cleanup_status=$?
[ "$cleanup_status" -eq 0 ] || exit "$cleanup_status"
echo "trace_collapse_check: OK (response-first, 1 collapsed summary line, ^T toggle round-trip, 0 hex ids in all 3 frames)"
