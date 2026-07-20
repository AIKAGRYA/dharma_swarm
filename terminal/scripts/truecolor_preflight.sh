#!/usr/bin/env bash
# Truecolor preflight gate (F-019): asserts the three links of the truecolor
# chain so overnight aesthetic grading never judges quantized colors.
#   link 1 — COLORTERM=truecolor reaches a launched pane's environment
#            (the run env injects it per pane command, boot_smoke.sh pattern;
#            this script propagates the HOST's COLORTERM into the pane, so the
#            whole host -> pane -> app chain is what gets verified)
#   link 2 — tmux RGB terminal capability is on (client_termfeatures RGB/Tc,
#            or server terminal-features / terminal-overrides advertise it)
#   link 3 — a literal 38;2 SGR sequence survives tmux capture-pane -e
# The app emits ZERO 38;2 sequences pre-S4 (theme.ts is named ANSI-16), so the
# 38;2 evidence comes from a synthetic printf probe — that is the point: it
# proves the terminal chain will not quantize S4's colors when they arrive.
# Negative check: env -u COLORTERM bash scripts/truecolor_preflight.sh -> exit 1.
# This script only READS tmux options; it never mutates server state.
set -u

SESS="helm-truecolor-$$-$RANDOM"
PROBE_TIMEOUT=${PREFLIGHT_TIMEOUT:-15}

# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2329
cleanup() {
  tmux kill-session -t "$SESS" 2>/dev/null
}
trap cleanup EXIT

fail() {
  echo "truecolor_preflight: FAIL — $1" >&2
  exit 1
}

HOST_COLORTERM=${COLORTERM:-}
case "$HOST_COLORTERM" in
  *"'"*) fail "link 1 (COLORTERM): host COLORTERM contains a quote, refusing to inject: [$HOST_COLORTERM]" ;;
esac

# No single quotes inside: this string is wrapped in single quotes for bash -c.
# The expansions must occur inside that child shell, not while assigning here.
# shellcheck disable=SC2016
PROBE_CMD='printf "PANE-COLORTERM=[%s]\n" "${COLORTERM:-MISSING}"; printf "\033[38;2;255;158;59mTRUECOLOR-PROBE\033[39m\n"; printf "PROBE-DONE\n"; sleep 60'

if [ -n "$HOST_COLORTERM" ]; then
  PANE_CMD="COLORTERM='$HOST_COLORTERM' bash -c '$PROBE_CMD'"
else
  # Host did not provide COLORTERM: launch with it explicitly absent so link 1
  # reports the broken chain instead of inheriting stale server environment.
  PANE_CMD="env -u COLORTERM bash -c '$PROBE_CMD'"
fi

tmux new-session -d -s "$SESS" -x 80 -y 24 "$PANE_CMD" \
  || fail "could not create tmux probe session (is tmux available?)"

# Poll until the probe finishes rendering (no fixed-sleep-only race).
plain=""
deadline=$(( $(date +%s) + PROBE_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  plain=$(tmux capture-pane -t "$SESS" -p 2>/dev/null || true)
  if printf '%s' "$plain" | grep -q "PROBE-DONE"; then
    break
  fi
  tmux has-session -t "$SESS" 2>/dev/null || break
  sleep 0.3
done
printf '%s' "$plain" | grep -q "PROBE-DONE" \
  || fail "probe pane never rendered PROBE-DONE within ${PROBE_TIMEOUT}s; frame was: $(printf '%s' "$plain" | head -c 300)"

status=0

# --- link 1: COLORTERM=truecolor present in the pane environment ---
pane_colorterm=$(printf '%s\n' "$plain" | grep -m1 '^PANE-COLORTERM=' || true)
if [ "$pane_colorterm" = "PANE-COLORTERM=[truecolor]" ]; then
  echo "truecolor_preflight: link 1 OK — COLORTERM=truecolor in pane env ($pane_colorterm)"
else
  echo "truecolor_preflight: FAIL — link 1 (COLORTERM): pane env saw ${pane_colorterm:-no PANE-COLORTERM line}, expected PANE-COLORTERM=[truecolor]; the run env must export COLORTERM=truecolor so pane commands inject it (boot_smoke.sh pattern)" >&2
  status=1
fi

# --- link 2: tmux RGB terminal capability is on ---
client_features=$(tmux display -p '#{client_termfeatures}' 2>/dev/null || true)
server_features=$(tmux show -gs terminal-features 2>/dev/null || true)
server_overrides=$(tmux show -gs terminal-overrides 2>/dev/null || true)
rgb_evidence=""
if printf '%s' "$client_features" | grep -qE 'RGB|Tc'; then
  rgb_evidence="client_termfeatures: $client_features"
elif printf '%s' "$server_features" | grep -qE 'RGB|Tc'; then
  rgb_evidence="terminal-features: $(printf '%s\n' "$server_features" | grep -E 'RGB|Tc' | head -1)"
elif printf '%s' "$server_overrides" | grep -qE 'RGB|Tc'; then
  rgb_evidence="terminal-overrides: $(printf '%s\n' "$server_overrides" | grep -E 'RGB|Tc' | head -1)"
fi
if [ -n "$rgb_evidence" ]; then
  echo "truecolor_preflight: link 2 OK — tmux RGB on via $rgb_evidence"
else
  echo "truecolor_preflight: FAIL — link 2 (tmux RGB terminal-features): no RGB/Tc in client_termfeatures [$client_features], terminal-features, or terminal-overrides; tmux will quantize 38;2 colors — add e.g. terminal-overrides ',xterm-256color:Tc' (do NOT let this script set it)" >&2
  status=1
fi

# --- link 3: literal 38;2 SGR survives tmux capture -e ---
sgr=$(tmux capture-pane -t "$SESS" -e -p 2>/dev/null || true)
probe_line=$(printf '%s\n' "$sgr" | grep -F '38;2;255;158;59' | head -1 || true)
if [ -n "$probe_line" ]; then
  echo "truecolor_preflight: link 3 OK — 38;2 SGR survived capture; probe capture: $probe_line"
else
  echo "truecolor_preflight: FAIL — link 3 (38;2 survival): probe SGR did not survive tmux capture -e (quantized or stripped); captured probe region: $(printf '%s\n' "$sgr" | grep -F 'TRUECOLOR-PROBE' | head -1 | cat -v)" >&2
  status=1
fi

if [ "$status" -ne 0 ]; then
  echo "truecolor_preflight: FAIL — chain broken, see link diagnostics above" >&2
  exit 1
fi

echo "truecolor_preflight: OK"
exit 0
