#!/usr/bin/env bash
# chetana SessionStart hook — runs at every session boot, including subagent
# sessions and `claude -p` headless invocations.
#
# Behavior:
#   1. Run a quick decay scan against the trusted wiki.
#   2. Find atoms due for revival (read-only proposal, no apply).
#   3. Surface top gaps and open questions.
#   4. Inject a compact systemMessage into the session context so Claude
#      starts with awareness of what's stale, what needs answers, and what's
#      been recently captured.
#
# Hard timeout 8s (set in hooks.json). Script must NEVER block longer.
# Failures degrade gracefully — the session always boots.

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_chetana_lib.sh
. "${HERE}/_chetana_lib.sh"

chetana_log "SessionStart fired (cwd=$(pwd))"

# Find chetana python; bail silently if not installed.
PY="$(chetana_find_python)" || {
  echo '{"continue": true}'
  exit 0
}

# Run all probes in parallel via background jobs. Cap at 6s wall total.
TMP_STATUS="$(mktemp -t chetana_st.XXXXXX)"
TMP_DECAY="$(mktemp -t chetana_dc.XXXXXX)"
TMP_GAPS="$(mktemp -t chetana_gp.XXXXXX)"

(
  "${PY}" -m dharma_swarm.chetana.cli status >"${TMP_STATUS}" 2>>"${CHETANA_LOG}"
) &
PID_STATUS=$!

(
  "${PY}" -m dharma_swarm.chetana.cli decay >"${TMP_DECAY}" 2>>"${CHETANA_LOG}"
) &
PID_DECAY=$!

(
  "${PY}" -m dharma_swarm.chetana.cli gap-scan >"${TMP_GAPS}" 2>>"${CHETANA_LOG}"
) &
PID_GAPS=$!

# Wait with a soft cap (kill at 6s).
SECONDS=0
while (( SECONDS < 6 )); do
  if ! kill -0 "${PID_STATUS}" "${PID_DECAY}" "${PID_GAPS}" 2>/dev/null; then
    break
  fi
  sleep 0.2
done

# Best-effort kill of any stragglers; don't escalate to SIGKILL on session boot.
kill "${PID_STATUS}" "${PID_DECAY}" "${PID_GAPS}" 2>/dev/null || true
wait 2>/dev/null

# Build the systemMessage body.
BODY=$(cat <<'EOF_HEAD'
## chetana — session-start brief

EOF_HEAD
)

# Status
if [[ -s "${TMP_STATUS}" ]]; then
  STATUS_LINE="$(grep -E '^- (staged|trusted|quarantine)' "${TMP_STATUS}" | tr '\n' ' | ' | sed 's/ | $//')"
  BODY+=$'\n'"**Memory state**: ${STATUS_LINE}"
fi

# Decay headline
if [[ -s "${TMP_DECAY}" ]]; then
  STALE_COUNT="$(grep -E '^- Stale: ' "${TMP_DECAY}" | head -1 | sed 's/[^0-9]//g')"
  STALE_COUNT="${STALE_COUNT:-0}"
  if [[ "${STALE_COUNT}" -gt 0 ]]; then
    BODY+=$'\n\n'"**${STALE_COUNT} atoms past stale_after** — run \`/chetana-revive\` to re-integrate (default move) or \`/chetana-decay --quarantine\` for last-resort exile."
  fi
fi

# Gap headline
if [[ -s "${TMP_GAPS}" ]]; then
  TOP_GAPS="$(awk '/^## Topic gaps/{flag=1; next} /^##/{flag=0} flag && /^- /' "${TMP_GAPS}" | head -3 | sed 's/^- /  - /')"
  if [[ -n "${TOP_GAPS}" ]]; then
    BODY+=$'\n\n'"**Top wiki gaps** (heavily referenced but no article):"$'\n'"${TOP_GAPS}"
  fi
fi

# Recent capture
LATEST_CAP="$(find "${CHETANA_DAILY_DIR}" -type f -name '*.md' -exec ls -t {} + 2>/dev/null | head -1)"
if [[ -n "${LATEST_CAP}" ]]; then
  REL_NAME="$(basename "${LATEST_CAP}")"
  BODY+=$'\n\n'"**Last session captured**: \`${REL_NAME}\`"
fi

BODY+=$'\n\n_Use `/chetana-status`, `/chetana-revive`, `/chetana-gap-scan` for details. Stale → revive (re-integrate), not exile._'

# Cleanup tmps
rm -f "${TMP_STATUS}" "${TMP_DECAY}" "${TMP_GAPS}" 2>/dev/null

# Emit JSON for Claude Code to inject the systemMessage.
python3 - "${BODY}" <<'PY'
import json, sys
print(json.dumps({"continue": True, "systemMessage": sys.argv[1]}))
PY
