#!/usr/bin/env bash
# chetana Stop hook — runs when a Claude session ends.
#
# Captures the just-finished JSONL transcript via chetana.ingest --kind session,
# producing one staged atom per substantive assistant turn. The staged atoms
# remain unpromoted until human/agent review — chetana NEVER auto-promotes
# session content into the trusted wiki without explicit /chetana-promote or
# /chetana-revive --apply.
#
# Async (set in hooks.json), 30s budget.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/_chetana_lib.sh"

chetana_log "Stop fired (cwd=$(pwd))"

PY="$(chetana_find_python)" || {
  chetana_log "skip Stop: chetana not installed"
  exit 0
}

# Find the just-finished session JSONL.
JSONL="$(chetana_current_session_jsonl)" || {
  chetana_log "skip Stop: no session JSONL found for $(pwd)"
  exit 0
}
SESSION_ID="$(basename "${JSONL}" .jsonl)"
chetana_log "ingesting session: ${SESSION_ID}"

# Append to a daily session log first (always succeeds, even if chetana ingest fails).
TODAY="$(date +%Y-%m-%d)"
DAILY_DIR="${CHETANA_DAILY_DIR}/${TODAY}"
mkdir -p "${DAILY_DIR}"
SUMMARY_PATH="${DAILY_DIR}/session_${SESSION_ID}.md"
{
  echo "---"
  echo "session_id: ${SESSION_ID}"
  echo "captured_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cwd: $(pwd)"
  echo "jsonl_path: ${JSONL}"
  echo "jsonl_size_bytes: $(stat -f %z "${JSONL}" 2>/dev/null || echo 0)"
  echo "type: session_capture_summary"
  echo "---"
  echo ""
  echo "# Session ${SESSION_ID}"
  echo ""
  echo "## Source JSONL"
  echo "- \`${JSONL}\`"
  echo ""
  echo "## Ingest"
} > "${SUMMARY_PATH}"

# Run chetana ingest in background and tee its stdout into the summary.
{
  "${PY}" -m dharma_swarm.chetana.cli ingest "${JSONL}" \
    --kind session \
    --captured-by "chetana_session_stop_hook" \
    --tag session-extract --tag auto-captured \
    >> "${SUMMARY_PATH}" 2>>"${CHETANA_LOG}"
} &
INGEST_PID=$!

# Wait up to 25s for ingest.
SECONDS=0
while (( SECONDS < 25 )); do
  kill -0 "${INGEST_PID}" 2>/dev/null || break
  sleep 0.5
done
kill "${INGEST_PID}" 2>/dev/null || true
wait 2>/dev/null

# Append a tail with the next-step suggestion.
{
  echo ""
  echo "## Next step"
  echo "- Review staged atoms: \`chetana status\`"
  echo "- Promote good ones: \`chetana promote <staged_path>\`"
  echo "- Or skip review and let next-session decay handle them."
} >> "${SUMMARY_PATH}"

chetana_log "Stop complete: ${SUMMARY_PATH}"
exit 0
