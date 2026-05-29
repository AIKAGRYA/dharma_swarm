#!/usr/bin/env bash
# register_perplexity_computer.sh
#
# Idempotent registration of the perplexity-computer roaming agent into
# dharma_swarm via the existing roaming_onboarding CLI. Run this on any
# host with the dharma_swarm repo and a Python env that can import
# dharma_swarm.roaming_onboarding.
#
# Witness:
#   ~/.dharma/onboarding/receipts/receipts.jsonl  (kaizenops trail)
#   ~/.dharma/external_agents/perplexity-computer/
#   ~/.dharma/a2a/cards/perplexity-computer.json
#
# Callsign and authority are pre-bound to match the nest declared in
# docs/agents/perplexity-computer/ (PR #375).
#
# Usage:
#   bash scripts/agents/register_perplexity_computer.sh
#
# Exit codes:
#   0  success or already-registered (idempotent)
#   1  python import failed (env not set up for dharma_swarm)
#   2  CLI returned non-zero

set -euo pipefail

CALLSIGN="perplexity-computer"
HARNESS="perplexity_computer"
AUTHORITY="external_worker_evidence_only"
DEPARTMENT="synthesis"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RECEIPT_DIR="${HOME}/.dharma/onboarding/receipts"
RECEIPT_FILE="${RECEIPT_DIR}/receipts.jsonl"

cd "$REPO_ROOT"

echo "[register_perplexity_computer] repo=${REPO_ROOT}"
echo "[register_perplexity_computer] callsign=${CALLSIGN}"
echo "[register_perplexity_computer] harness=${HARNESS}"
echo "[register_perplexity_computer] authority=${AUTHORITY}"
echo "[register_perplexity_computer] department=${DEPARTMENT}"

# Idempotency probe — if a receipt already exists for this callsign, skip.
if [ -f "$RECEIPT_FILE" ] && grep -q "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE"; then
  echo "[register_perplexity_computer] receipt already present in ${RECEIPT_FILE}"
  echo "[register_perplexity_computer] idempotent skip; existing entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1
  exit 0
fi

# Sanity: dharma_swarm must be importable.
if ! python3 -c "import dharma_swarm.roaming_onboarding" 2>/dev/null; then
  echo "[register_perplexity_computer] ERROR: cannot import dharma_swarm.roaming_onboarding"
  echo "[register_perplexity_computer] activate the project's venv first, e.g.:"
  echo "    source .venv/bin/activate   # or: poetry shell"
  exit 1
fi

set +e
python3 -m dharma_swarm.roaming_onboarding \
  --callsign "$CALLSIGN" \
  --harness "$HARNESS" \
  --authority "$AUTHORITY" \
  --department "$DEPARTMENT"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  echo "[register_perplexity_computer] CLI exited rc=${rc}"
  exit 2
fi

echo "[register_perplexity_computer] CLI succeeded"
if [ -f "$RECEIPT_FILE" ]; then
  echo "[register_perplexity_computer] latest receipt entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1 || true
else
  echo "[register_perplexity_computer] NOTE: receipt file not found at ${RECEIPT_FILE}"
  echo "[register_perplexity_computer] (registration may have used a different DHARMA_HOME)"
fi

echo "[register_perplexity_computer] done."
