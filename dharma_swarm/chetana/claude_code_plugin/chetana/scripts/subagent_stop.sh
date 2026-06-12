#!/usr/bin/env bash
# chetana SubagentStop hook — captures subagent outputs for the lattice.
#
# Subagent transcripts are smaller, more focused, and often higher-signal than
# main-session transcripts. Capture them under captures/subagents/ so the
# memory-weave loop can pick them up alongside the main captures.
#
# Opt-out: export CHETANA_CAPTURE_SUBAGENTS=0 in shell to disable.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/_chetana_lib.sh"

if [[ "${CHETANA_CAPTURE_SUBAGENTS:-1}" == "0" ]]; then
  exit 0
fi

chetana_log "SubagentStop fired"

# Subagent transcripts live under /tmp/claude-<uid>/-Users-.../tasks/<aid>.output
# We don't tail them (could be large + structured JSONL). Write a manifest row
# so the next memory-weave run knows a subagent finished.
TODAY="$(date +%Y-%m-%d)"
MANIFEST="${CHETANA_SUBAGENTS_DIR}/${TODAY}_stops.jsonl"
{
  printf '{"event":"subagent_stop","at":"%s","cwd":"%s","pid":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$(pwd)" \
    "$$"
} >> "${MANIFEST}" 2>/dev/null

exit 0
