#!/usr/bin/env bash
# chetana PreCompact hook — last chance to capture before context window collapses.
#
# Writes a checkpoint manifest into in_flight/ so even mid-session compactions
# leave behind a recovery point. The manifest is tagged by session_id and
# timestamp; chetana decay/gap-scan can later read these as additional context
# for the session that owns them.
#
# Hard 10s budget. Failures don't block the compaction.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/_chetana_lib.sh"

chetana_log "PreCompact fired"

JSONL="$(chetana_current_session_jsonl)" || JSONL=""
SESSION_ID=""
[[ -n "${JSONL}" ]] && SESSION_ID="$(basename "${JSONL}" .jsonl)"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"

# Drop a marker file so decay/gap-scan knows when this session was last active.
MARKER="${CHETANA_IN_FLIGHT_DIR}/${SESSION_ID:-unknown}_${TS}.md"
{
  echo "---"
  echo "type: pre_compact_checkpoint"
  echo "session_id: ${SESSION_ID:-unknown}"
  echo "captured_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cwd: $(pwd)"
  echo "reason: pre_compact_hook"
  echo "---"
  echo ""
  echo "# PreCompact checkpoint"
  echo ""
  echo "Session was about to compact. JSONL up to this point: \`${JSONL}\`"
  echo ""
  echo "Recovery: re-ingest from JSONL after the compaction completes; staged atoms will pick up turns the original Stop hook missed."
} > "${MARKER}" 2>/dev/null

chetana_log "PreCompact checkpoint: ${MARKER}"
exit 0
