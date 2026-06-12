#!/bin/bash
# Standard live-interaction tour of the Helm TUI. Run after each batch; diff against prior tours.
# Usage: bash spec-forge/tour.sh          → frames in spec-forge/tours/<timestamp>/
set -u
ROOT=/Users/dhyana/dharma_helm_build
OUT=$ROOT/spec-forge/tours/$(date +%Y%m%dT%H%M%S)
S=helm-tour-$$
mkdir -p "$OUT"
snap() { tmux capture-pane -t "$S" -p > "$OUT/$1.txt"; tmux capture-pane -t "$S" -p -e > "$OUT/$1.sgr.txt"; }

tmux kill-session -t "$S" 2>/dev/null
cd "$ROOT/terminal" || exit 1
tmux new-session -d -s "$S" -x 120 -y 40 \
  "DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$(mktemp -d) DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$(mktemp -d) COLORTERM=truecolor bun run start"
sleep 6;  snap 00_boot

# Probe text must NOT contain the token "tour" (or any plain-language UI-intent
# phrase from src/uiIntents.ts) — "tour probe message" matched the /tour intent
# and was answered locally, so frames 02/03 stopped exercising the offline
# natural-prompt queue path they grade.
tmux send-keys -t "$S" "namaste helm probe"; sleep 2;   snap 01_typed
tmux send-keys -t "$S" Enter;               sleep 3;   snap 02_sent
sleep 6;                                                snap 03_turn_state        # honest queued/failed vs perpetual running?
tmux send-keys -t "$S" "/help"; sleep 1; tmux send-keys -t "$S" Enter; sleep 2.5; snap 04_help   # silent-swallow regression
tmux send-keys -t "$S" Tab;   sleep 1.5;               snap 05_tab_fwd
tmux send-keys -t "$S" BTab;  sleep 1.5;               snap 06_tab_back           # Shift-Tab direction regression
tmux send-keys -t "$S" "?";   sleep 1.5;               snap 07_question           # help overlay vs typed-into-composer

tmux set -t "$S" window-size manual 2>/dev/null
tmux resize-window -t "$S" -x 80 -y 24;  sleep 0.5;    snap 08_resize_immediate   # artifact check
sleep 2.5;                                              snap 09_resize_settled     # settle-time check
tmux resize-window -t "$S" -x 120 -y 40; sleep 2.5;    snap 10_resize_back

tmux send-keys -t "$S" C-c; sleep 2
tmux capture-pane -t "$S" -p > "$OUT/11_after_ctrlc.txt" 2>/dev/null || echo "session ended cleanly" > "$OUT/11_after_ctrlc.txt"
tmux kill-session -t "$S" 2>/dev/null

{ echo "tour: $OUT"; echo "head: $(git -C "$ROOT" rev-parse --short HEAD)"; echo "date: $(date -u +%FT%TZ)"
  echo "frames:"; ls "$OUT"; } > "$OUT/MANIFEST.txt"
echo "TOUR COMPLETE → $OUT"
