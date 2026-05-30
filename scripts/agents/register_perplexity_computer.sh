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
ROLE="external_evidence_worker"
DEPARTMENT="synthesis"
DESCRIPTION="Perplexity Computer roaming agent: cross-agent synthesizer / verdict reconciler / persistent-index keeper. Stage 1 external-evidence-only. Identity nest: docs/agents/perplexity-computer/."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Honor DHARMA_HOME if set; fall back to ~/.dharma. Without this, the
# idempotency probe at the bottom of this script checks the wrong path
# when DHARMA_HOME is set to a non-default location (the CLI writes
# receipts to $DHARMA_HOME but the script was probing $HOME). Fix per
# devin review item 2, 2026-05-30.
DHARMA_HOME_RESOLVED="${DHARMA_HOME:-${HOME}/.dharma}"
RECEIPT_DIR="${DHARMA_HOME_RESOLVED}/onboarding/receipts"
RECEIPT_FILE="${DHARMA_HOME_RESOLVED}/onboarding/receipts.jsonl"

cd "$REPO_ROOT"

echo "[register_perplexity_computer] repo=${REPO_ROOT}"
echo "[register_perplexity_computer] callsign=${CALLSIGN}"
echo "[register_perplexity_computer] harness=${HARNESS}"
echo "[register_perplexity_computer] role=${ROLE}"
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
  --role "$ROLE" \
  --department "$DEPARTMENT" \
  --description "$DESCRIPTION" \
  --registration-source "docs/agents/perplexity-computer/SOUL.md" \
  --capability "synthesis" \
  --capability "verdict_reconciliation" \
  --capability "persistent_agent_index"
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
