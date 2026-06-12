#!/usr/bin/env bash
# chetana SessionEnd hook — fires at terminal session shutdown (rarer than Stop).
#
# Currently delegates to session_stop.sh for parity. Keeping a separate hook
# entry means we can diverge later (e.g., SessionEnd writes a closure manifest
# while Stop writes per-turn captures).

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/_chetana_lib.sh"

chetana_log "SessionEnd fired"

# Write a closure manifest noting the session is fully done.
TODAY="$(date +%Y-%m-%d)"
MANIFEST="${CHETANA_MANIFESTS_DIR}/${TODAY}_closures.jsonl"
mkdir -p "$(dirname "${MANIFEST}")"
JSONL="$(chetana_current_session_jsonl)" || JSONL=""
{
  printf '{"event":"session_end","at":"%s","cwd":"%s","jsonl":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$(pwd)" \
    "${JSONL}"
} >> "${MANIFEST}" 2>/dev/null

exit 0
