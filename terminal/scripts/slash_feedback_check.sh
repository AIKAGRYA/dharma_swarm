#!/usr/bin/env bash
# F-158 verification: every slash command produces visible feedback in the
# transcript — an echoed turn plus a result, or an explicit queued/failed
# status. Zero-visible-feedback command handling is banned (live tour finding 3:
# /help offline was silently swallowed).
#
# Asserts (hermetic offline boot, DHARMA_PYTHON points nowhere):
#   1. typing /help + Enter changes the transcript — the frame is NOT unchanged;
#   2. the frame shows the echoed '> /help' turn AND an explicit
#      'queued (backend offline)' (or 'failed') status;
#   3. a second registered command (/status) echoes the same way — the fix is
#      the command path, not a /help special case;
#   4. no dishonest pending: no '▶' glyph and no 'running' text offline.
# Exit 0 = PASS, exit 1 = FAIL naming the violated assertion.
set -u

TERMINAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESS="helm-f158-$RANDOM"
STATEDIR="$(mktemp -d)"
CAPDIR="${SLASH_FEEDBACK_OUT_DIR:-$(mktemp -d)}"
QUEUED_ROW='○ queued \(backend offline\) · .+ · \^T details'

cleanup() {
  tmux kill-session -t "$SESS" 2>/dev/null || true
  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$STATEDIR" 2>/dev/null || true
  if [ -z "${SLASH_FEEDBACK_OUT_DIR:-}" ]; then
    find "$CAPDIR" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$CAPDIR" 2>/dev/null || true
  fi
}

fail() {
  echo "slash_feedback_check: FAIL — $1" >&2
  tmux capture-pane -t "$SESS" -p 2>/dev/null | sed 's/^/  | /' >&2 || true
  cleanup
  exit 1
}

capture() {
  tmux capture-pane -t "$SESS" -p
}

send_command() {
  # send_command <slash command> <capture name>
  local cmd="$1" name="$2" _attempt frame
  tmux send-keys -t "$SESS" -l "$cmd"
  sleep 0.3
  tmux send-keys -t "$SESS" Enter
  for _attempt in $(seq 1 15); do
    frame="$(capture 2>/dev/null || true)"
    if echo "$frame" | grep -qF "> $cmd" \
      && echo "$frame" | grep -qE "queued \(backend offline\)|failed"; then
      echo "$frame" > "$CAPDIR/$name.txt"
      return 0
    fi
    sleep 0.2
  done
  frame="$(capture 2>/dev/null || true)"
  echo "$frame" > "$CAPDIR/$name.txt"
  if [ "$frame" = "$(cat "$CAPDIR/baseline.txt")" ]; then
    fail "transcript UNCHANGED after sending $cmd — command silently swallowed"
  fi
  if ! echo "$frame" | grep -qF "> $cmd"; then
    fail "echoed turn '> $cmd' missing from the transcript within 3s"
  fi
  fail "no 'queued (backend offline)' or 'failed' status for $cmd within 3s"
}

tmux new-session -d -s "$SESS" -x 120 -y 40 \
  "cd $TERMINAL_DIR && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start" \
  || fail "tmux session failed to start"

offline_seen=""
for _attempt in $(seq 1 40); do
  frame="$(capture 2>/dev/null || true)"
  # FACE-1: zen boot frame carries the durable "offline" token in its status line.
  if echo "$frame" | grep -q "offline"; then
    offline_seen=1
    break
  fi
  sleep 0.5
done
[ -n "$offline_seen" ] || fail "offline boot frame never appeared"
capture > "$CAPDIR/baseline.txt"

# 1+2: /help offline — the graded live-tour case.
send_command "/help" "help_offline"
grep -qE "$QUEUED_ROW" "$CAPDIR/help_offline.txt" || fail "/help turn row missing the explicit queued state"

# 3: a second registered command echoes through the same path.
send_command "/status" "status_offline"
[ "$(grep -cE "$QUEUED_ROW" "$CAPDIR/status_offline.txt")" = "2" ] \
  || fail "second command did not add a second queued turn row"

# 4: no dishonest pending state anywhere in the final offline frame.
grep -q "▶" "$CAPDIR/status_offline.txt" && fail "running glyph ▶ present on offline command turns"
grep -qiE "running" "$CAPDIR/status_offline.txt" && fail "'running' text present in the offline frame"

echo "slash_feedback_check: OK (/help + /status echoed with explicit queued (backend offline) status; transcript never silently unchanged)"
cleanup
exit 0
