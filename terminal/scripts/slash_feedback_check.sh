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
# shellcheck source=terminal/scripts/lib/codex_managed_tmux.sh
source "$TERMINAL_DIR/scripts/lib/codex_managed_tmux.sh"
SESS="helm-f158-$RANDOM"
STATEDIR="$(mktemp -d)"
CAPDIR="${SLASH_FEEDBACK_OUT_DIR:-$(mktemp -d)}"
QUEUED_ROW='○ queued \(backend offline\) · .+ · \^T details'

cleanup() {
  local original_status="$1"

  trap - EXIT
  if ! codex_managed_tmux_cleanup; then
    echo "slash_feedback_check: CLEANUP FAILED — managed tmux shutdown failed; preserving STATEDIR=$STATEDIR CAPDIR=$CAPDIR" >&2
    if [ "$original_status" -eq 0 ]; then
      return 1
    fi
    return "$original_status"
  fi
  find "$STATEDIR" -mindepth 1 -delete 2>/dev/null || true
  rmdir "$STATEDIR" 2>/dev/null || true
  if [ -z "${SLASH_FEEDBACK_OUT_DIR:-}" ]; then
    find "$CAPDIR" -mindepth 1 -delete 2>/dev/null || true
    rmdir "$CAPDIR" 2>/dev/null || true
  fi
  return "$original_status"
}

# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2329
on_exit() {
  local original_status=$?

  cleanup "$original_status"
  exit $?
}
trap on_exit EXIT

fail() {
  echo "slash_feedback_check: FAIL — $1" >&2
  codex_managed_tmux capture-pane -t "$SESS" -p 2>/dev/null \
    | sed 's/^/  | /' >&2 || true
  exit 1
}

capture() {
  codex_managed_tmux capture-pane -t "$SESS" -p
}

send_command() {
  # send_command <slash command> <capture name>
  local cmd="$1" name="$2" _attempt frame
  codex_managed_tmux send-keys -t "$SESS" -l "$cmd"
  sleep 0.3
  codex_managed_tmux send-keys -t "$SESS" Enter
  for _attempt in $(seq 1 15); do
    frame="$(capture 2>/dev/null || true)"
    if grep -qF "> $cmd" <<<"$frame" \
      && grep -qE "queued \(backend offline\)|failed" <<<"$frame"; then
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
  if ! grep -qF "> $cmd" <<<"$frame"; then
    fail "echoed turn '> $cmd' missing from the transcript within 3s"
  fi
  fail "no 'queued (backend offline)' or 'failed' status for $cmd within 3s"
}

codex_managed_tmux_init slash_feedback \
  || fail "could not initialize private tmux server"

codex_managed_tmux new-session -d -s "$SESS" -x 120 -y 40 \
  "sleep 1; cd $TERMINAL_DIR && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start" \
  || fail "tmux session failed to start"
codex_managed_tmux set-option -g status off \
  || fail "could not disable private tmux status row"
codex_managed_tmux resize-window -t "$SESS:0" -x 120 -y 40 \
  || fail "could not resize private tmux window"
dimensions="$(codex_managed_tmux display-message -p -t "$SESS:0.0" \
  '#{pane_width}x#{pane_height}')"
[ "$dimensions" = "120x40" ] || fail "expected 120x40 pane, got $dimensions"

offline_seen=""
for _attempt in $(seq 1 40); do
  frame="$(capture 2>/dev/null || true)"
  # FACE-1: zen boot frame carries the durable "offline" token in its status line.
  if grep -q "offline" <<<"$frame"; then
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

cleanup 0
cleanup_status=$?
[ "$cleanup_status" -eq 0 ] || exit "$cleanup_status"
echo "slash_feedback_check: OK (/help + /status echoed with explicit queued (backend offline) status; transcript never silently unchanged)"
exit 0
