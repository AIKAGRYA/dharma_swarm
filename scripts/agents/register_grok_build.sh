#!/usr/bin/env bash
# register_grok_build.sh
#
# Idempotent registration of the grok_build persistent agent into
# dharma_swarm via the existing roaming_onboarding CLI. Run on meghadharma
# (or any host with dharma_swarm importable).
#
# Witness:
#   ~/.dharma/onboarding/receipts.jsonl
#   ~/.dharma/agents/grok_build/
#   ~/.dharma/a2a/cards/grok-build.json
#
# Canonical card:
#   examples/agents/grok_build.registration.json
#
# Usage:
#   bash scripts/agents/register_grok_build.sh

set -euo pipefail

CALLSIGN="grok-build"
AGENT_UID="grok_build"
HARNESS="grok_build_cli"
ROLE="software_engineering_agent"
DEPARTMENT="engineering"
SQUAD_ID="persistent_agents"
MODEL="grok-4.5"
PROVIDER="xai"
ENDPOINT="nats://agni-remote/DHARMA_A2A/dharma.agent.grok_build.inbox"
DESCRIPTION="Grok Build 4.5 persistent agent on meghadharma-cloud. Software engineering, repo exploration, tests, ops research, fleet inventory, A2A correspondence, evidence synthesis. Canonical card: examples/agents/grok_build.registration.json."

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DHARMA_HOME_RESOLVED="${DHARMA_HOME:-${HOME}/.dharma}"
RECEIPT_FILE="${DHARMA_HOME_RESOLVED}/onboarding/receipts.jsonl"

cd "$REPO_ROOT"

echo "[register_grok_build] repo=${REPO_ROOT}"
echo "[register_grok_build] callsign=${CALLSIGN}"
echo "[register_grok_build] agent_uid=${AGENT_UID}"
echo "[register_grok_build] harness=${HARNESS}"

if [ -f "$RECEIPT_FILE" ] && grep -q "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE"; then
  echo "[register_grok_build] receipt already present in ${RECEIPT_FILE}"
  echo "[register_grok_build] idempotent skip; existing entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1
  exit 0
fi

if ! python3 -c "import dharma_swarm.roaming_onboarding" 2>/dev/null; then
  echo "[register_grok_build] ERROR: cannot import dharma_swarm.roaming_onboarding"
  exit 1
fi

set +e
python3 -m dharma_swarm.roaming_onboarding \
  --callsign "$CALLSIGN" \
  --agent-uid "$AGENT_UID" \
  --harness "$HARNESS" \
  --role "$ROLE" \
  --department "$DEPARTMENT" \
  --squad-id "$SQUAD_ID" \
  --model "$MODEL" \
  --provider "$PROVIDER" \
  --endpoint "$ENDPOINT" \
  --description "$DESCRIPTION" \
  --registration-source "examples/agents/grok_build.registration.json" \
  --capability "code_generation" \
  --capability "code_review" \
  --capability "testing" \
  --capability "repo_exploration" \
  --capability "ops_research" \
  --capability "fleet_inventory" \
  --capability "a2a_correspondence" \
  --capability "packet_generation" \
  --capability "governance_navigation" \
  --capability "evidence_synthesis" \
  --capability "holon_structure_mapping"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  echo "[register_grok_build] CLI exited rc=${rc}"
  exit 2
fi

echo "[register_grok_build] CLI succeeded"
if [ -f "$RECEIPT_FILE" ]; then
  echo "[register_grok_build] latest receipt entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1 || true
fi

echo "[register_grok_build] done."
