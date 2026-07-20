#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMINAL_ROOT="$ROOT/terminal"
EXPECTED_BUN_VERSION="1.3.11"

SMOKE_LOG=""
TMUX_SOCKET=""
TMUX_SESSION="guardian-smoke"
# Bash 3.2 (the macOS system Bash) considers an empty array unset under
# `set -u`. Keep one inert sentinel until the live process tree is captured.
SMOKE_PIDS=("")

process_is_alive() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

collect_descendants() {
  local parent_pid="$1"
  local child_pid

  while IFS= read -r child_pid; do
    if [[ -z "$child_pid" ]]; then
      continue
    fi
    SMOKE_PIDS+=("$child_pid")
    collect_descendants "$child_pid"
  done < <(pgrep -P "$parent_pid" 2>/dev/null || true)
}

stop_smoke_server() {
  local socket_path

  if [[ -n "$TMUX_SOCKET" ]] && command -v tmux >/dev/null 2>&1; then
    tmux -L "$TMUX_SOCKET" kill-server >/dev/null 2>&1 || true
    # tmux 3.6b on macOS can leave a dead named socket after kill-server.
    # This path is derived from our private, PID-qualified socket label only.
    socket_path="${TMUX_TMPDIR:-/tmp}/tmux-$(id -u)/$TMUX_SOCKET"
    rm -f "$socket_path"
  fi
}

cleanup() {
  local pid

  set +e
  stop_smoke_server
  for pid in "${SMOKE_PIDS[@]}"; do
    if [[ -z "$pid" ]]; then
      continue
    fi
    if process_is_alive "$pid"; then
      kill -TERM "$pid" >/dev/null 2>&1 || true
    fi
  done
  if [[ -n "$SMOKE_LOG" ]]; then
    rm -f "$SMOKE_LOG"
  fi
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

fail_smoke() {
  local message="$1"

  echo "[terminal-guardian] compact smoke failed: $message" >&2
  if [[ -n "$SMOKE_LOG" && -s "$SMOKE_LOG" ]]; then
    echo "[terminal-guardian] captured screen:" >&2
    sed -n '1,160p' "$SMOKE_LOG" >&2
  fi
  return 1
}

wait_for_smoke_screen() {
  local attempt

  for ((attempt = 1; attempt <= 80; attempt += 1)); do
    if ! tmux -L "$TMUX_SOCKET" has-session -t "$TMUX_SESSION" 2>/dev/null; then
      return 1
    fi
    tmux -L "$TMUX_SOCKET" capture-pane -p -t "$TMUX_SESSION:0.0" -S - >"$SMOKE_LOG"
    if grep -qiE "DHARMA|Dharma Terminal" "$SMOKE_LOG"; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

wait_for_smoke_exit() {
  local attempt
  local pid
  local survivors

  for ((attempt = 1; attempt <= 50; attempt += 1)); do
    survivors=0
    for pid in "${SMOKE_PIDS[@]}"; do
      if process_is_alive "$pid"; then
        survivors=1
        break
      fi
    done
    if [[ "$survivors" -eq 0 ]]; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

run_compact_smoke() {
  local pane_dimensions
  local pane_pid
  local pid
  local process_command
  local bridge_pid=""

  if ! command -v tmux >/dev/null 2>&1; then
    fail_smoke "tmux is required for the bounded 80x24 PTY check"
    return 1
  fi
  if ! command -v pgrep >/dev/null 2>&1; then
    fail_smoke "pgrep is required to verify bridge cleanup"
    return 1
  fi

  SMOKE_LOG="$(mktemp "${TMPDIR:-/tmp}/dharma-terminal-guardian-smoke.XXXXXX")"
  TMUX_SOCKET="dharma-guardian-$$-${RANDOM}"

  # Delay the application for one second so tmux can disable its status row
  # and establish the exact PTY dimensions before Ink reads stdout.columns.
  tmux -L "$TMUX_SOCKET" -f /dev/null new-session \
    -d -x 80 -y 24 -s "$TMUX_SESSION" -c "$TERMINAL_ROOT" \
    "sleep 1; exec env COLUMNS=80 LINES=24 bun run start"
  tmux -L "$TMUX_SOCKET" set-option -g status off
  tmux -L "$TMUX_SOCKET" resize-window -t "$TMUX_SESSION:0" -x 80 -y 24

  pane_dimensions="$(tmux -L "$TMUX_SOCKET" display-message -p -t "$TMUX_SESSION:0.0" '#{pane_width}x#{pane_height}')"
  if [[ "$pane_dimensions" != "80x24" ]]; then
    fail_smoke "expected an 80x24 pane, got $pane_dimensions"
    return 1
  fi

  if ! wait_for_smoke_screen; then
    tmux -L "$TMUX_SOCKET" capture-pane -p -t "$TMUX_SESSION:0.0" -S - >"$SMOKE_LOG" 2>/dev/null || true
    fail_smoke "Helm did not render its compact Dharma shell within 8 seconds"
    return 1
  fi

  pane_pid="$(tmux -L "$TMUX_SOCKET" display-message -p -t "$TMUX_SESSION:0.0" '#{pane_pid}')"
  SMOKE_PIDS=("$pane_pid")
  collect_descendants "$pane_pid"
  for pid in "${SMOKE_PIDS[@]}"; do
    process_command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$process_command" == *"dharma_swarm.terminal_bridge"* ]]; then
      bridge_pid="$pid"
      break
    fi
  done
  if [[ -z "$bridge_pid" ]]; then
    fail_smoke "Helm rendered, but its terminal bridge was not running"
    return 1
  fi

  if grep -qiE "Cannot find module|SyntaxError|ReferenceError|TypeError|bridge_spawn_error" "$SMOKE_LOG"; then
    fail_smoke "fatal startup error found in the captured screen"
    return 1
  fi

  tmux -L "$TMUX_SOCKET" send-keys -t "$TMUX_SESSION:0.0" C-c
  if ! wait_for_smoke_exit; then
    stop_smoke_server
    if ! wait_for_smoke_exit; then
      fail_smoke "Ctrl-C left a Bun or terminal-bridge process alive"
      return 1
    fi
  fi
  stop_smoke_server
  if process_is_alive "$bridge_pid"; then
    fail_smoke "terminal bridge $bridge_pid survived smoke cleanup"
    return 1
  fi
}

cd "$ROOT"

echo "[terminal-guardian] architecture spec"
test -s specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md
grep -q '^\*\*Version:\*\* 1\.1' specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md

echo "[terminal-guardian] bridge syntax"
python3 -m py_compile dharma_swarm/terminal_bridge.py

echo "[terminal-guardian] Bun $EXPECTED_BUN_VERSION and dependency presence"
if ! command -v bun >/dev/null 2>&1; then
  echo "bun missing; install Bun $EXPECTED_BUN_VERSION" >&2
  exit 2
fi
if [[ "$(bun --version)" != "$EXPECTED_BUN_VERSION" ]]; then
  echo "expected Bun $EXPECTED_BUN_VERSION, got $(bun --version)" >&2
  exit 2
fi
if [[ ! -d terminal/node_modules ]]; then
  echo "terminal/node_modules missing; run: cd terminal && bun install" >&2
  exit 2
fi

echo "[terminal-guardian] typecheck"
(cd terminal && bun run typecheck)

echo "[terminal-guardian] focused protocol/route/continuity/render/input/scheduler tests"
(cd terminal && bun test \
  tests/protocol.test.ts \
  tests/routePolicy.test.ts \
  tests/sessionContinuity.test.ts \
  tests/sessionRender.test.ts \
  tests/paneSwitcher.test.ts \
  tests/inputPolicy.test.ts \
  tests/bridgeScheduler.test.ts \
  tests/bridge.test.ts)

echo "[terminal-guardian] compact terminal smoke"
run_compact_smoke

echo "terminal-guardian preflight: OK"
