#!/usr/bin/env bash
# GATE 1 witness kit — spine-adoption track (runtime-truth-spine-adoption-2026-06).
#
# The one act no agent may self-certify: the OPERATOR observes a real
# EvidenceReceipt fire on the live orchestrator dispatch chokepoint (#557).
# Test-green does not clear this gate. An observed receipt does.
#
# SCOPE: receipt_json is the ORCHESTRATOR-surface witness column. A2A-surface
# dispatches persist canonically via RuntimeReceipt and leave receipt_json
# empty — an empty blob on an A2A row is success, NOT a failed gate (see
# spine/persistence.py + tests/test_spine_persistence_invariant.py inv. 7).
# This gate counts only flagged ORCHESTRATOR dispatches.
#
# Usage:
#   bash scripts/governance/gate1_witness.sh          # show receipt count + instructions
#   bash scripts/governance/gate1_witness.sh --watch  # poll until a new receipt lands, then print it
set -u
DB="${HOME}/.dharma/state/runtime.db"
BASELINE_FILE="${HOME}/.dharma/state/gate1_baseline.txt"

count() { sqlite3 "${DB}" "SELECT COUNT(*) FROM delegation_runs WHERE receipt_json IS NOT NULL" 2>/dev/null || echo "ERR"; }

show_new() {
  local base="$1"
  sqlite3 -line "${DB}" "
    SELECT run_id, task_id, agent_id, status,
           substr(receipt_json, 1, 200) AS receipt_head
    FROM delegation_runs
    WHERE receipt_json IS NOT NULL
    ORDER BY rowid DESC LIMIT 3" 2>/dev/null
  echo ""
  echo "receipt_json sha256 (latest):"
  sqlite3 "${DB}" "SELECT receipt_json FROM delegation_runs WHERE receipt_json IS NOT NULL ORDER BY rowid DESC LIMIT 1" 2>/dev/null | shasum -a 256 | cut -c1-16
}

C=$(count)
if [[ "${C}" == "ERR" ]]; then echo "FAIL: cannot read ${DB}"; exit 1; fi

if [[ "${1:-}" == "--watch" ]]; then
  BASE=$(cat "${BASELINE_FILE}" 2>/dev/null || echo "${C}")
  # FRESHNESS GUARD: a persisted baseline already below the current count means
  # receipts accrued since it was set (another session, another lane) — watching
  # against it would fire instantly WITHOUT a live dispatch, stamping a "witnessed
  # just now" the data can't back. Reset to current so this watch can only trigger
  # on a receipt that lands AFTER it started.
  if [[ "${C}" -gt "${BASE}" ]]; then
    echo "WARN: baseline ${BASE} is stale (current=${C} already exceeds it) — resetting baseline to ${C}."
    echo "      This watch will only fire on a receipt landing AFTER now. Run your flagged dispatch."
    BASE="${C}"
    echo "${BASE}" > "${BASELINE_FILE}"
  fi
  WATCH_STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "watching for a receipt beyond baseline=${BASE} (current=${C}); Ctrl-C to stop"
  while :; do
    N=$(count)
    if [[ "${N}" != "ERR" && "${N}" -gt "${BASE}" ]]; then
      echo ""
      echo "*** GATE 1 EVIDENCE: receipt count ${BASE} -> ${N} ***"
      show_new "${BASE}"
      echo ""
      echo "GATE 1 CLEARED if the receipt above corresponds to the dispatch you just ran."
      # Write the witness artifact (a completion criterion requires this file —
      # the track cannot flip SHIPPABLE without an operator-witnessed receipt).
      # The hash is checkable against the DB: an agent fabricating this file is
      # telling an auditable lie, not satisfying a proxy.
      ART="$(cd "$(dirname "$0")/../.." && pwd)/reports/governance/GATE1_WITNESSED.md"
      mkdir -p "$(dirname "${ART}")"
      LATEST_SHA=$(sqlite3 "${DB}" "SELECT receipt_json FROM delegation_runs WHERE receipt_json IS NOT NULL ORDER BY rowid DESC LIMIT 1" 2>/dev/null | shasum -a 256 2>/dev/null | cut -c1-16)
      [[ -z "${LATEST_SHA}" ]] && LATEST_SHA="UNAVAILABLE (sqlite3/shasum failed — verify manually before trusting this artifact)"
      {
        echo "# GATE 1 — operator-witnessed EvidenceReceipt"
        echo ""
        echo "- witnessed_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "- watch_started: ${WATCH_STARTED}  (the count moved AFTER this — freshness-guarded)"
        echo "- receipt_count: ${BASE} -> ${N}"
        echo "- latest_receipt_json_sha256_16: ${LATEST_SHA}"
        echo "- db: ${DB}"
        echo ""
        echo "Written by gate1_witness.sh --watch the moment the count moved past a"
        echo "freshness-guarded baseline (stale baselines are reset at watch start, and"
        echo "the baseline advances on success so a re-run cannot re-trigger)."
        echo "Verify anytime: sqlite3 '${DB}' \"SELECT COUNT(*) FROM delegation_runs WHERE receipt_json IS NOT NULL\""
        echo ""
        echo "LIMITATION (by design, documented): file_exists is the criterion, so this"
        echo "file CAN be hand-written — but the sha16 is checkable against the DB row,"
        echo "so fabrication is an auditable lie, not a satisfied proxy."
      } > "${ART}"
      # Advance the baseline so a re-run of --watch cannot re-trigger on this receipt.
      echo "${N}" > "${BASELINE_FILE}"
      echo "witness artifact written: ${ART} (commit it to flip the gate1_witnessed criterion)"
      exit 0
    fi
    sleep 5
  done
fi

echo "${C}" > "${BASELINE_FILE}"
echo "=== GATE 1 baseline ==="
echo "  delegation_runs total:        $(sqlite3 "${DB}" 'SELECT COUNT(*) FROM delegation_runs' 2>/dev/null)"
echo "  with EvidenceReceipt:         ${C}   <- this number going up IS the gate"
echo ""
echo "=== Operator steps (one terminal) ==="
echo "  1. dgc down"
echo "  2. export DHARMA_SPINE_DISPATCH=1 && dgc up --background"
echo "     (or run one real dispatch in the flagged environment)"
echo "  3. bash scripts/governance/gate1_witness.sh --watch"
echo "     -> prints the new receipt (run_id/task_id/status + sha256) the moment it lands"
echo ""
echo "  Afterwards: unset the flag or leave it on — your call. The gate is cleared"
echo "  only by the receipt you SAW, not by any agent's claim that one fired."
