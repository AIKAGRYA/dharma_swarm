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
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_ROOT="${GOLDEN_OUT_DIR:-${TERMINAL_DIR}/tests/golden}"

SIZES="80x24 100x30 120x40"
if [[ -n "${GOLDEN_SIZE:-}" ]]; then
  if [[ ! "${GOLDEN_SIZE}" =~ ^[1-9][0-9]*x[1-9][0-9]*$ ]]; then
    echo "golden_capture: invalid GOLDEN_SIZE '${GOLDEN_SIZE}' (expected WIDTHxHEIGHT)" >&2
    exit 2
  fi
  SIZES="${GOLDEN_SIZE}"
fi

if ! TMUX_BIN="$(command -v tmux)"; then
  echo "golden_capture: tmux is required" >&2
  exit 127
fi
if ! BUN_BIN="$(command -v bun)"; then
  echo "golden_capture: bun is required" >&2
  exit 127
fi
if [[ -n "${GOLDEN_SESSION_NAME:-}" && ! "${GOLDEN_SESSION_NAME}" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "golden_capture: invalid GOLDEN_SESSION_NAME '${GOLDEN_SESSION_NAME}'" >&2
  exit 2
fi

TAB_IDS="chat mission repo commands models ontology runtime sessions approvals control agents evolution"
OVERLAY_IDS="modelPicker paneSwitcher"
EXPECTED_PER_SIZE=14
EXPECTED_TOTAL=0
for _size in ${SIZES}; do
  EXPECTED_TOTAL=$((EXPECTED_TOTAL + EXPECTED_PER_SIZE))
done

BOOT_TIMEOUT=${GOLDEN_BOOT_TIMEOUT:-20}
NAV_TIMEOUT=${GOLDEN_NAV_TIMEOUT:-10}
# Overlay settles may wait out one full 15s reconnect probe (transient
# status text -> steady offline line), so their deadline is longer.
OVERLAY_TIMEOUT=${GOLDEN_OVERLAY_TIMEOUT:-25}

# Unique, bottom-anchored pane-body text per surface (verified against live
# 80x24 frames; mock content from mockContent.ts and pane components).
marker_for() {
  case $1 in
    chat) printf 'F2 unfolds the Whole Helm' ;;  # Quiet Field welcome line 2 (mockContent.ts)
    mission) printf 'Mission Control' ;;
    repo) printf 'workspace owner' ;;
    commands) printf 'local command catalog' ;;
    models) printf 'route policy owner' ;;
    ontology) printf 'ontology owner' ;;
    runtime) printf 'runtime owner' ;;
    sessions) printf 'session owner' ;;
    approvals) printf 'permission owner' ;;
    control) printf 'control owner' ;;
    agents) printf 'agent-route owner' ;;
    evolution) printf 'evolution owner' ;;
    modelPicker) printf 'No model targets loaded.' ;;
    paneSwitcher) printf '1. Chat' ;;  # The selected row must remain visible at every governed size.
    *) return 1 ;;
  esac
}

SESS=""
STATEDIR=""
SESSION_STARTED=false

cleanup_session() {
  if [[ "${SESSION_STARTED}" == true && -n "${SESS}" ]]; then
    "${TMUX_BIN}" kill-session -t "=${SESS}" >/dev/null 2>&1 || true
    SESSION_STARTED=false
    SESS=""
  fi
  if [[ -n "${STATEDIR}" ]]; then
    rm -r -- "${STATEDIR}" >/dev/null 2>&1 || true
    STATEDIR=""
  fi
}
trap cleanup_session EXIT

fail() {
  echo "golden_capture: FAIL — $1" >&2
  if [[ "${SESSION_STARTED}" == true && -n "${SESS}" ]]; then
    echo "golden_capture: last frame head:" >&2
    "${TMUX_BIN}" capture-pane -t "=${SESS}:0.0" -p 2>/dev/null | head -c 400 >&2 || true
    echo >&2
  fi
  exit 1
}

frame() {
  "${TMUX_BIN}" capture-pane -t "=${SESS}:0.0" -p 2>/dev/null || true
}

# Poll until the frame contains marker $1 (literal) AND the steady
# "offline" status (zen status token on chat, "backend offline" in cockpit
# footers — FACE-1) AND two consecutive captures are byte-identical;
# echoes the settled frame. Deadline seconds in $2.
wait_settled() {
  local marker=$1 timeout=$2 prev="" cur="" deadline
  deadline=$(( $(date +%s) + timeout ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    cur=$(frame)
    if [[ -n "${cur}" && "${cur}" == *"${marker}"* && "${cur}" == *offline* ]]; then
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
  local marker=$1 deadline cur
  deadline=$(( $(date +%s) + NAV_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    cur="$(frame)"
    if [[ "${cur}" != *"${marker}"* ]]; then
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
  SESS="${GOLDEN_SESSION_NAME:-helm-golden-$$-$RANDOM}"
  if "${TMUX_BIN}" has-session -t "=${SESS}" >/dev/null 2>&1; then
    echo "golden_capture: tmux session '${SESS}' already exists" >&2
    exit 2
  fi
  STATEDIR="$(mktemp -d)"
  printf -v START_COMMAND \
    'env COLORTERM=truecolor DHARMA_PYTHON=%q DHARMA_TERMINAL_STATE_DIR=%q DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=%q COLUMNS=%q LINES=%q %q run start' \
    "/nonexistent/dharma-terminal-golden-python" "${STATEDIR}" "${STATEDIR}" "${width}" "${height}" "${BUN_BIN}"
  "${TMUX_BIN}" new-session -d -s "${SESS}" -x "${width}" -y "${height}" -c "${TERMINAL_DIR}" \
    "${START_COMMAND}" || fail "could not create tmux session at $size"
  SESSION_STARTED=true

  actual_size="$("${TMUX_BIN}" display-message -p -t "=${SESS}:0.0" '#{pane_width}x#{pane_height}')"
  [[ "${actual_size}" == "${size}" ]] || fail "tmux geometry is ${actual_size}, expected ${size}"

  # Do not mutate the output corpus until this process has proved it owns
  # the exact tmux session and the requested geometry.
  outdir="${OUT_ROOT}/${size}"
  mkdir -p "${outdir}"
  find "${outdir}" -maxdepth 1 -name '*.txt' -delete

  # Boot: wait for the offline degradation to render (boot_smoke.sh pattern)
  # so every captured frame shares the settled offline status.
  booted=0
  deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    "${TMUX_BIN}" has-session -t "=${SESS}" 2>/dev/null || fail "app died during boot at $size"
    current_frame="$(frame)"
    if [[ "${current_frame}" == *offline* ]]; then
      booted=1
      break
    fi
    sleep 0.5
  done
  [ "$booted" -eq 1 ] || fail "no 'offline' degradation within ${BOOT_TIMEOUT}s at $size"

  # Capture boot Chat in Zen, then enter Cockpit explicitly before walking
  # the remaining static panes. Tab does not navigate while Zen owns input.
  first=1
  for id in $TAB_IDS; do
    if [ "$first" -eq 1 ]; then
      first=0
    else
      if [[ "${id}" == mission ]]; then
        "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" F2
        wait_settled "◆ DHARMA HELM" "${NAV_TIMEOUT}" >/dev/null \
          || fail "did not enter the Nihonga Helm at ${size}"
        # Keyboard ownership is explicit: Cockpit keeps the composer focused
        # until Escape hands control to navigation. Without this boundary the
        # following Tab is correctly consumed by the composer and the walk
        # never leaves Chat.
        "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" Escape
        wait_settled "Navigation active" "${NAV_TIMEOUT}" >/dev/null \
          || fail "navigation focus did not settle at ${size}"
      fi
      "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" Tab
    fi
    capture_to "$id" "$outdir/$id.txt" "$NAV_TIMEOUT"
  done

  # Return to chat via ^G (direct tab.activate — Tab-count independent: the
  # cycle also holds the non-inventoried bridge tabs) so both overlays sit
  # on the same deterministic background tab.
  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" C-g
  wait_settled "$(marker_for chat)" "$NAV_TIMEOUT" > /dev/null || fail "did not return to chat at $size"

  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" C-p
  capture_to "modelPicker" "$outdir/modelPicker.txt" "$OVERLAY_TIMEOUT"
  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" Escape
  wait_gone "$(marker_for modelPicker)" || fail "modelPicker did not close on Esc at $size"

  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" C-k
  capture_to "paneSwitcher" "$outdir/paneSwitcher.txt" "$OVERLAY_TIMEOUT"
  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" Escape
  wait_gone "$(marker_for paneSwitcher)" || fail "paneSwitcher did not close on Esc at $size"

  # Clean shutdown (best effort): Ctrl-C, brief poll, then hard cleanup.
  "${TMUX_BIN}" send-keys -t "=${SESS}:0.0" C-c
  deadline=$(( $(date +%s) + 5 ))
  while "${TMUX_BIN}" has-session -t "=${SESS}" 2>/dev/null; do
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
