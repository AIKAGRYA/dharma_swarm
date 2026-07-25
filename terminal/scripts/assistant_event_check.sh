#!/usr/bin/env bash
# F-173 verification: the `assistant` bridge event renders as the turn's response,
# and a turn that ends with NO response-bearing event renders an explicit
# no-response marker — never a bare complete with an empty body.
# Boots the app against scripts/stub_bridge.py (STUB_BRIDGE_SCENARIO=assistant_then_empty):
#   turn 1: session.ack + {type:"assistant", request_id, message} + synth session_end
#           (the identity-intent shortcut shape, bridge_events.md §1.16)
#   turn 2: session.ack + session_end only (no response-bearing event)
# Asserts:
#   1. turn 1: the assistant message renders as the turn's response text in the
#      transcript, ABOVE that turn's ✓ trace summary line — no no-response marker;
#   2. turn 2: an explicit "no response" marker renders, the turn's summary line
#      carries the failed glyph ✖, and NO second ✓-complete summary appears
#      (a completed turn with zero response text is the graded violation).
# Exit 0 = PASS, exit 1 = FAIL naming the violated assertion.
set -u

TERMINAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESS="helm-f173-$RANDOM"
STATEDIR="$(mktemp -d)"
CAPDIR="${ASSISTANT_CHECK_OUT_DIR:-$(mktemp -d)}"
ASSISTANT_TEXT="I am the Helm. Identity intents route straight through me."
NO_RESPONSE_MARKER="no response — turn ended without output"
SUMMARY_OK='✓ ([0-9]+s|done) · .+ · \^T details'
SUMMARY_FAILED='✖ failed · .+ · \^T details'

cleanup() {
  tmux kill-session -t "$SESS" 2>/dev/null || true
  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$STATEDIR" 2>/dev/null || true
  if [ -z "${ASSISTANT_CHECK_OUT_DIR:-}" ]; then
    find "$CAPDIR" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$CAPDIR" 2>/dev/null || true
  fi
}

fail() {
  echo "assistant_event_check: FAIL — $1" >&2
  tmux capture-pane -t "$SESS" -p 2>/dev/null | sed 's/^/  | /' >&2 || true
  cleanup
  exit 1
}

capture() {
  tmux capture-pane -t "$SESS" -p
}

wait_for() {
  # wait_for <egrep pattern> <label>
  local pattern="$1" label="$2" _attempt frame
  for _attempt in $(seq 1 40); do
    frame="$(capture 2>/dev/null || true)"
    if echo "$frame" | grep -qE "$pattern"; then
      return 0
    fi
    sleep 0.5
  done
  fail "$label never appeared (waited 20s)"
}

tmux new-session -d -s "$SESS" -x 100 -y 30 \
  "cd $TERMINAL_DIR && COLORTERM=truecolor STUB_BRIDGE_SCENARIO=assistant_then_empty DHARMA_PYTHON=$TERMINAL_DIR/scripts/stub_bridge.py DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start" \
  || fail "tmux session failed to start"

wait_for "Dharma Terminal" "app boot frame"
# FACE-1: the zen status line names bridge connectivity without claiming provider liveness.
wait_for "backend connected|bridge ready|resyncing|bridge connected|● bridge" "stub bridge handshake"

# ---- turn 1: answered via the assistant event ----
tmux send-keys -t "$SESS" -l "who are you and what can you do"
sleep 0.5
tmux send-keys -t "$SESS" Enter

wait_for "Identity intents route straight" "assistant message in transcript"
sleep 0.5
capture > "$CAPDIR/turn1.txt"

grep -qF "$ASSISTANT_TEXT" "$CAPDIR/turn1.txt" || fail "assistant event message missing from transcript (turn 1)"
ok_count="$(grep -cE "$SUMMARY_OK" "$CAPDIR/turn1.txt")"
[ "$ok_count" -eq 1 ] || fail "expected exactly 1 completed-turn summary line after turn 1, found $ok_count"
response_line="$(grep -nF "$ASSISTANT_TEXT" "$CAPDIR/turn1.txt" | head -1 | cut -d: -f1)"
summary_line="$(grep -nE "$SUMMARY_OK" "$CAPDIR/turn1.txt" | head -1 | cut -d: -f1)"
[ "$response_line" -lt "$summary_line" ] || fail "assistant response (line $response_line) not above the turn summary (line $summary_line)"
grep -qF "$NO_RESPONSE_MARKER" "$CAPDIR/turn1.txt" && fail "no-response marker rendered on an answered turn"

# ---- turn 2: session ends with no response-bearing event ----
tmux send-keys -t "$SESS" -l "second question with no answer"
sleep 0.5
tmux send-keys -t "$SESS" Enter

wait_for "no response" "explicit no-response marker (turn 2)"
sleep 0.5
capture > "$CAPDIR/turn2.txt"

grep -qF "$NO_RESPONSE_MARKER" "$CAPDIR/turn2.txt" || fail "explicit no-response marker missing on the empty turn"
grep -qE "$SUMMARY_FAILED" "$CAPDIR/turn2.txt" || fail "empty turn's summary line does not carry the failed glyph ✖"
ok_count_after="$(grep -cE "$SUMMARY_OK" "$CAPDIR/turn2.txt")"
[ "$ok_count_after" -eq 1 ] || fail "empty turn rendered as a completed turn (✓ summaries went from 1 to $ok_count_after)"

cleanup
echo "assistant_event_check: OK (assistant message rendered as turn response; empty turn carries explicit no-response marker + ✖, never bare complete)"
