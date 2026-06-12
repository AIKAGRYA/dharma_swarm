#!/usr/bin/env bash
# Golden-frame capture (F-016): boots one hermetic tmux session per size
# (80x24, 100x30, 120x40), walks every golden-stable offline surface, and
# captures plain text frames (tmux capture-pane -p) into
# <out>/<size>/<surface>.txt.
#
# Surface inventory (offline golden corpus) = 12 static tabs + 2 overlays = 14:
#   tabs: chat mission repo commands models ontology runtime sessions
#         approvals control agents evolution           (mockContent.ts)
#   overlays: modelPicker (^P), paneSwitcher (^K)      (app.tsx)
# The bridge tabs thinking/tools/timeline DO exist offline (ensureRuntimeTabs
# appends them at boot) but are deliberately NOT inventoried: their lines
# project the execution-event log, which accumulates timestamped offline
# probe errors every SNAPSHOT_REFRESH_INTERVAL_MS — never byte-stable, so
# never golden material.
#
# Determinism law: every frame is captured only when it shows the steady
# "backend offline" status AND two consecutive captures are byte-identical.
# Transient status text ("pane switcher ready") is reset to the steady
# offline line by the 15s reconnect probe, so settled frames are
# reproducible run-to-run.
#
# Arrival detection uses pane-body content markers, not the TabBar active
# marker: tall panes (repo/runtime/control) overflow short frames and push
# the TabBar off the top of the visible screen, while pane bodies sit
# bottom-anchored and stay visible at every size.
#
# Output root override: GOLDEN_OUT_DIR=<dir> (default tests/golden) so the
# F-018 diff checker can capture into a temp dir without dirtying the corpus.
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
OUT_ROOT=${GOLDEN_OUT_DIR:-$TERMINAL_DIR/tests/golden}

SIZES="80x24 100x30 120x40"
TAB_IDS="chat mission repo commands models ontology runtime sessions approvals control agents evolution"
OVERLAY_IDS="modelPicker paneSwitcher"
EXPECTED_PER_SIZE=14
EXPECTED_TOTAL=42

BOOT_TIMEOUT=${GOLDEN_BOOT_TIMEOUT:-20}
NAV_TIMEOUT=${GOLDEN_NAV_TIMEOUT:-10}
# Overlay settles may wait out one full 15s reconnect probe (transient
# status text -> steady offline line), so their deadline is longer.
OVERLAY_TIMEOUT=${GOLDEN_OVERLAY_TIMEOUT:-25}

# Unique, bottom-anchored pane-body text per surface (verified against live
# 80x24 frames; mock content from mockContent.ts and pane components).
marker_for() {
  case $1 in
    chat) printf 'Use plain prompts or slash commands' ;;
    mission) printf 'One state model. One bridge.' ;;
    repo) printf 'Workspace snapshot loading' ;;
    commands) printf 'Command graph loading' ;;
    models) printf 'Model policy loading' ;;
    ontology) printf 'Ontology snapshot loading' ;;
    runtime) printf 'selected runtime card' ;;  # F-163 clamp: 'Frontend runtime: Bun' sits below the 80x24 clip line now
    sessions) printf 'No selected session.' ;;
    approvals) printf 'No selected approval.' ;;
    control) printf 'Control-plane snapshot loading' ;;
    agents) printf 'No selected route.' ;;
    evolution) printf 'Cascade and self-improvement surface loading' ;;
    modelPicker) printf 'No model targets loaded.' ;;
    paneSwitcher) printf '1. Chat' ;;  # F-163 clamp: deep list rows clip at 80x24; switcher needs selection-windowing (logged)
    *) return 1 ;;
  esac
}

SESS=""
STATEDIR=""

cleanup_session() {
  if [ -n "$SESS" ]; then
    tmux kill-session -t "$SESS" 2>/dev/null
    SESS=""
  fi
  if [ -n "$STATEDIR" ]; then
    find "$STATEDIR" -mindepth 1 -delete 2>/dev/null
    rmdir "$STATEDIR" 2>/dev/null
    STATEDIR=""
  fi
}
trap cleanup_session EXIT

fail() {
  echo "golden_capture: FAIL — $1" >&2
  if [ -n "$SESS" ]; then
    echo "golden_capture: last frame head:" >&2
    tmux capture-pane -t "$SESS" -p 2>/dev/null | head -c 400 >&2 || true
    echo >&2
  fi
  exit 1
}

frame() {
  tmux capture-pane -t "$SESS" -p 2>/dev/null || true
}

# Poll until the frame contains marker $1 (literal) AND the steady
# "backend offline" status AND two consecutive captures are byte-identical;
# echoes the settled frame. Deadline seconds in $2.
wait_settled() {
  local marker=$1 timeout=$2 prev="" cur="" deadline
  deadline=$(( $(date +%s) + timeout ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    cur=$(frame)
    if [ -n "$cur" ] && printf '%s' "$cur" | grep -qF -- "$marker" && printf '%s' "$cur" | grep -q "backend offline"; then
      if [ "$cur" = "$prev" ]; then
        printf '%s\n' "$cur"
        return 0
      fi
      prev=$cur
    else
      prev=""
    fi
    sleep 0.3
  done
  return 1
}

# Poll until marker $1 no longer renders (overlay closed).
wait_gone() {
  local marker=$1 deadline
  deadline=$(( $(date +%s) + NAV_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if ! frame | grep -qF -- "$marker"; then
      return 0
    fi
    sleep 0.3
  done
  return 1
}

capture_to() {
  local id=$1 out=$2 timeout=$3 marker settled
  marker=$(marker_for "$id") || fail "no marker registered for surface $id"
  settled=$(wait_settled "$marker" "$timeout") || fail "surface $id never settled with marker '$marker' (${timeout}s)"
  printf '%s\n' "$settled" > "$out"
  [ -s "$out" ] || fail "captured frame $out is empty"
}

for size in $SIZES; do
  width=${size%x*}
  height=${size#*x}
  outdir="$OUT_ROOT/$size"
  mkdir -p "$outdir"
  find "$outdir" -maxdepth 1 -name '*.txt' -delete

  SESS="helm-golden-$$-$RANDOM"
  STATEDIR=$(mktemp -d)
  tmux new-session -d -s "$SESS" -x "$width" -y "$height" \
    "cd '$TERMINAL_DIR' && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR='$STATEDIR' DHARMA_TERMINAL_SUPERVISOR_STATE_DIR='$STATEDIR' bun run start" \
    || fail "could not create tmux session at $size"

  # Boot: wait for the offline degradation to render (boot_smoke.sh pattern)
  # so every captured frame shares the settled offline status.
  booted=0
  deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    tmux has-session -t "$SESS" 2>/dev/null || fail "app died during boot at $size"
    if frame | grep -q "backend offline"; then
      booted=1
      break
    fi
    sleep 0.5
  done
  [ "$booted" -eq 1 ] || fail "no 'backend offline' degradation within ${BOOT_TIMEOUT}s at $size"

  # Walk the 12 static tabs with forward Tab only (Shift-Tab is broken;
  # [ ] 1 2 3 are intercepted printables). Poll arrival before each capture.
  first=1
  for id in $TAB_IDS; do
    if [ "$first" -eq 1 ]; then
      first=0
    else
      tmux send-keys -t "$SESS" Tab
    fi
    capture_to "$id" "$outdir/$id.txt" "$NAV_TIMEOUT"
  done

  # Return to chat via ^G (direct tab.activate — Tab-count independent: the
  # cycle also holds the non-inventoried bridge tabs) so both overlays sit
  # on the same deterministic background tab.
  tmux send-keys -t "$SESS" C-g
  wait_settled "$(marker_for chat)" "$NAV_TIMEOUT" > /dev/null || fail "did not return to chat at $size"

  tmux send-keys -t "$SESS" C-p
  capture_to "modelPicker" "$outdir/modelPicker.txt" "$OVERLAY_TIMEOUT"
  tmux send-keys -t "$SESS" Escape
  wait_gone "$(marker_for modelPicker)" || fail "modelPicker did not close on Esc at $size"

  tmux send-keys -t "$SESS" C-k
  capture_to "paneSwitcher" "$outdir/paneSwitcher.txt" "$OVERLAY_TIMEOUT"
  tmux send-keys -t "$SESS" Escape
  wait_gone "$(marker_for paneSwitcher)" || fail "paneSwitcher did not close on Esc at $size"

  # Clean shutdown (best effort): Ctrl-C, brief poll, then hard cleanup.
  tmux send-keys -t "$SESS" C-c
  deadline=$(( $(date +%s) + 5 ))
  while tmux has-session -t "$SESS" 2>/dev/null; do
    [ "$(date +%s)" -lt "$deadline" ] || break
    sleep 0.5
  done
  cleanup_session

  # Mechanical inventory check: every inventoried surface present, non-empty,
  # and nothing extra.
  count=$(find "$outdir" -maxdepth 1 -name '*.txt' | wc -l | tr -d ' ')
  [ "$count" -eq "$EXPECTED_PER_SIZE" ] || fail "$outdir holds $count frames, inventory expects $EXPECTED_PER_SIZE"
  for id in $TAB_IDS $OVERLAY_IDS; do
    [ -s "$outdir/$id.txt" ] || fail "missing or empty frame $outdir/$id.txt"
  done
  echo "golden_capture: $size OK ($count frames)"
done

total=0
for size in $SIZES; do
  n=$(find "$OUT_ROOT/$size" -maxdepth 1 -name '*.txt' | wc -l | tr -d ' ')
  total=$(( total + n ))
done
[ "$total" -eq "$EXPECTED_TOTAL" ] || fail "corpus totals $total frames, inventory expects $EXPECTED_TOTAL"
echo "golden_capture: OK ($total frames in $OUT_ROOT)"
exit 0
