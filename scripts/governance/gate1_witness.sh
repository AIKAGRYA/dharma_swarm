#!/usr/bin/env bash
# GATE 1 witness kit — spine-adoption track (runtime-truth-spine-adoption-2026-06).
#
# The one act no agent may self-certify: the OPERATOR observes a real
# EvidenceReceipt fire on the live orchestrator dispatch chokepoint (#557).
# Test-green does not clear this gate. An observed receipt does.
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
  echo "watching for a receipt beyond baseline=${BASE} (current=${C}); Ctrl-C to stop"
  while :; do
    N=$(count)
    if [[ "${N}" != "ERR" && "${N}" -gt "${BASE}" ]]; then
      echo ""
      echo "*** GATE 1 EVIDENCE: receipt count ${BASE} -> ${N} ***"
      show_new "${BASE}"
      echo ""
      echo "GATE 1 CLEARED if the receipt above corresponds to the dispatch you just ran."
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
