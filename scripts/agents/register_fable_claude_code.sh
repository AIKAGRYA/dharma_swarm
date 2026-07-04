#!/usr/bin/env bash
# register_fable_claude_code.sh
#
# Idempotent registration of the fable_claude_code persistent agent into
# dharma_swarm via the existing roaming_onboarding CLI. Run this on any
# host with the dharma_swarm repo and a Python env that can import
# dharma_swarm.roaming_onboarding.
#
# Witness:
#   ~/.dharma/onboarding/receipts.jsonl  (kaizenops trail)
#   ~/.dharma/agents/fable_claude_code/
#   ~/.dharma/a2a/cards/fable-claude-code.json
#
# Callsign, uid, and authority are pre-bound to match the canonical card
# in examples/agents/fable_claude_code.registration.json.
#
# Usage:
#   bash scripts/agents/register_fable_claude_code.sh
#
# Exit codes:
#   0  success or already-registered (idempotent)
#   1  python import failed (env not set up for dharma_swarm)
#   2  CLI returned non-zero

set -euo pipefail

CALLSIGN="fable-claude-code"
AGENT_UID="fable_claude_code"
HARNESS="claude_code_cloud"
ROLE="hub_coordinator"
DEPARTMENT="coordination"
MODEL="claude-fable-5"
PROVIDER="anthropic"
DESCRIPTION="Fable 5 persistent agent in Claude Code (cloud remote sessions). Branch-scoped building with tests, cross-lane synthesis, PR pre-review, A2A correspondence. Canonical card: examples/agents/fable_claude_code.registration.json."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DHARMA_HOME_RESOLVED="${DHARMA_HOME:-${HOME}/.dharma}"
RECEIPT_FILE="${DHARMA_HOME_RESOLVED}/onboarding/receipts.jsonl"

cd "$REPO_ROOT"

echo "[register_fable_claude_code] repo=${REPO_ROOT}"
echo "[register_fable_claude_code] callsign=${CALLSIGN}"
echo "[register_fable_claude_code] agent_uid=${AGENT_UID}"
echo "[register_fable_claude_code] harness=${HARNESS}"

# Idempotency probe — if a receipt already exists for this callsign, skip.
if [ -f "$RECEIPT_FILE" ] && grep -q "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE"; then
  echo "[register_fable_claude_code] receipt already present in ${RECEIPT_FILE}"
  echo "[register_fable_claude_code] idempotent skip; existing entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1
  exit 0
fi

# Sanity: dharma_swarm must be importable.
if ! python3 -c "import dharma_swarm.roaming_onboarding" 2>/dev/null; then
  echo "[register_fable_claude_code] ERROR: cannot import dharma_swarm.roaming_onboarding"
  echo "[register_fable_claude_code] activate the project's venv first, e.g.:"
  echo "    source .venv/bin/activate   # or: poetry shell"
  exit 1
fi

set +e
python3 -m dharma_swarm.roaming_onboarding \
  --callsign "$CALLSIGN" \
  --agent-uid "$AGENT_UID" \
  --harness "$HARNESS" \
  --role "$ROLE" \
  --department "$DEPARTMENT" \
  --squad-id hub \
  --model "$MODEL" \
  --provider "$PROVIDER" \
  --endpoint "claude-code://fable_claude_code/cloud" \
  --description "$DESCRIPTION" \
  --registration-source "examples/agents/fable_claude_code.registration.json" \
  --capability "code_generation" \
  --capability "code_review" \
  --capability "testing" \
  --capability "cross_lane_synthesis" \
  --capability "pr_pre_review" \
  --capability "a2a_correspondence" \
  --capability "packet_generation" \
  --capability "governance_navigation" \
  --capability "evidence_synthesis"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  echo "[register_fable_claude_code] CLI exited rc=${rc}"
  exit 2
fi

echo "[register_fable_claude_code] CLI succeeded"
if [ -f "$RECEIPT_FILE" ]; then
  echo "[register_fable_claude_code] latest receipt entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1 || true
else
  echo "[register_fable_claude_code] NOTE: receipt file not found at ${RECEIPT_FILE}"
  echo "[register_fable_claude_code] (registration may have used a different DHARMA_HOME)"
fi

echo "[register_fable_claude_code] done."
