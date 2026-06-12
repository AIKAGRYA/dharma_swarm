#!/usr/bin/env bash
# F-161 check: no pane displays a 'loading' token while the bridge is down.
# Boots the app hermetically offline in tmux (120x40), walks every static
# tab, and asserts:
#   - NO frame contains a 'loading' token (case-insensitive) once offline
#   - the Models pane frame, re-captured 5s after arrival, contains the
#     explicit "no signal (backend offline)" message
# Exit 0 = law holds on every walked pane; exit 1 names the offending pane
# and shows the matching line(s).
#
# Evidence frames land in $OUT_DIR (default: a mktemp dir, path printed).
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
NO_SIGNAL='no signal (backend offline)'

TAB_IDS="chat mission repo commands models ontology runtime sessions approvals control agents evolution"
BOOT_TIMEOUT=${F161_BOOT_TIMEOUT:-20}
NAV_TIMEOUT=${F161_NAV_TIMEOUT:-10}

OUT_DIR=${F161_OUT_DIR:-$(mktemp -d)}
mkdir -p "$OUT_DIR"

SESS=""
STATEDIR=""

cleanup() {
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
trap cleanup EXIT

fail() {
  echo "offline_no_signal_check: FAIL — $1" >&2
  exit 1
}

frame() {
  tmux capture-pane -t "$SESS" -p 2>/dev/null || true
}

# Arrival marker per pane (projected offline text for the placeholder panes —
# kept in sync with scripts/golden_capture.sh marker_for).
marker_for() {
  case $1 in
    chat) printf 'Use plain prompts or slash commands' ;;
    mission) printf 'One state model. One bridge.' ;;
    repo) printf 'Workspace snapshot: no signal' ;;
    commands) printf 'Command graph: no signal' ;;
    models) printf 'Model policy: no signal' ;;
    ontology) printf 'Ontology snapshot: no signal' ;;
    runtime) printf 'Frontend runtime: Bun' ;;
    sessions) printf 'No selected session.' ;;
    approvals) printf 'No selected approval.' ;;
    control) printf 'Control-plane snapshot: no signal' ;;
    agents) printf 'No selected route.' ;;
    evolution) printf 'Cascade and self-improvement surface: no signal' ;;
    *) return 1 ;;
  esac
}

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

assert_no_loading() {
  local pane=$1 file=$2
  if grep -qi 'loading' "$file"; then
    echo "offline_no_signal_check: 'loading' token rendered offline on pane '$pane' ($file):" >&2
    grep -ni 'loading' "$file" >&2
    fail "pane '$pane' shows a pending/loading state while the bridge is down"
  fi
}

command -v tmux >/dev/null 2>&1 || fail "tmux not available"

SESS="helm-f161-$$-$RANDOM"
STATEDIR=$(mktemp -d)
tmux new-session -d -s "$SESS" -x 120 -y 40 \
  "cd '$TERMINAL_DIR' && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR='$STATEDIR' DHARMA_TERMINAL_SUPERVISOR_STATE_DIR='$STATEDIR' bun run start" \
  || fail "could not create tmux session"

booted=0
deadline=$(( $(date +%s) + BOOT_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  tmux has-session -t "$SESS" 2>/dev/null || fail "app died during boot"
  if frame | grep -q "backend offline"; then
    booted=1
    break
  fi
  sleep 0.5
done
[ "$booted" -eq 1 ] || fail "no 'backend offline' degradation within ${BOOT_TIMEOUT}s"

walked=0
first=1
for id in $TAB_IDS; do
  if [ "$first" -eq 1 ]; then
    first=0
  else
    tmux send-keys -t "$SESS" Tab
  fi
  marker=$(marker_for "$id") || fail "no marker registered for pane $id"
  settled=$(wait_settled "$marker" "$NAV_TIMEOUT") || fail "pane '$id' never settled with marker '$marker' (${NAV_TIMEOUT}s) — offline frame may still claim a pending state"
  printf '%s\n' "$settled" > "$OUT_DIR/$id.txt"
  assert_no_loading "$id" "$OUT_DIR/$id.txt"
  walked=$(( walked + 1 ))

  if [ "$id" = "models" ]; then
    sleep 5
    late=$(wait_settled "$marker" "$NAV_TIMEOUT") || fail "Models pane did not re-settle 5s after arrival"
    printf '%s\n' "$late" > "$OUT_DIR/models_plus5s.txt"
    assert_no_loading "models(+5s)" "$OUT_DIR/models_plus5s.txt"
    grep -qF -- "$NO_SIGNAL" "$OUT_DIR/models_plus5s.txt" \
      || fail "Models pane at +5s offline does not render '$NO_SIGNAL' ($OUT_DIR/models_plus5s.txt)"
  fi
done

[ "$walked" -eq 12 ] || fail "walked $walked panes, expected 12"

echo "offline_no_signal_check: OK (12 panes offline: 0 'loading' tokens; Models +5s renders '$NO_SIGNAL'; frames in $OUT_DIR)"
exit 0
