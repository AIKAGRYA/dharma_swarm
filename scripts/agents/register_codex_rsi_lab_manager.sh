#!/usr/bin/env bash
# register_codex_rsi_lab_manager.sh
#
# Idempotent registration of the codex_rsi_lab_manager persistent agent into
# dharma_swarm via the existing roaming_onboarding CLI.
#
# Witness:
#   ~/.dharma/onboarding/receipts.jsonl
#   ~/.dharma/agents/codex_rsi_lab_manager/
#   ~/.dharma/a2a/cards/codex-rsi-lab-manager.json
#
# On MeghaDharma's isolated RSI lab clone, run with:
#   BASE=/root/rsi-lab/current
#   cd "$BASE/repo"
#   DHARMA_HOME="$BASE/state/.dharma" bash scripts/agents/register_codex_rsi_lab_manager.sh

set -euo pipefail

CALLSIGN="codex-rsi-lab-manager"
AGENT_UID="codex_rsi_lab_manager"
HARNESS="codex_cli"
ROLE="lab_manager"
DEPARTMENT="rsi_lab"
MODEL="codex-runtime-selected"
PROVIDER="openai"
DESCRIPTION="Codex CLI manager for the isolated MeghaDharma RSI/Forge lab. Monitors experiments, runs explicitly assigned bounded lab operations, preserves logs and after-run notes, and enforces no-positive-lift claim boundaries."

LAB_BASE="${RSI_LAB_BASE:-/root/rsi-lab/current}"
REPO_ROOT="${RSI_LAB_REPO:-${LAB_BASE}/repo}"
STATE_ROOT="${RSI_LAB_STATE:-${LAB_BASE}/state}"
VENV_ROOT="${RSI_LAB_VENV:-${LAB_BASE}/.venv}"
PYDEPS_ROOT="${RSI_LAB_PYDEPS:-${LAB_BASE}/pydeps}"
PYTHON_BIN="${RSI_LAB_PYTHON:-${VENV_ROOT}/bin/python}"
DHARMA_HOME_RESOLVED="${DHARMA_HOME:-${STATE_ROOT}/.dharma}"
RECEIPT_FILE="${DHARMA_HOME_RESOLVED}/onboarding/receipts.jsonl"
export DHARMA_HOME="${DHARMA_HOME_RESOLVED}"

cd "$REPO_ROOT"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[register_codex_rsi_lab_manager] ERROR: canonical Python is not executable: ${PYTHON_BIN}"
  exit 1
fi

if [ -d "$PYDEPS_ROOT" ]; then
  export PYTHONPATH="${REPO_ROOT}:${PYDEPS_ROOT}:${PYTHONPATH:-}"
else
  export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
fi

echo "[register_codex_rsi_lab_manager] repo=${REPO_ROOT}"
echo "[register_codex_rsi_lab_manager] callsign=${CALLSIGN}"
echo "[register_codex_rsi_lab_manager] agent_uid=${AGENT_UID}"
echo "[register_codex_rsi_lab_manager] harness=${HARNESS}"
echo "[register_codex_rsi_lab_manager] dharma_home=${DHARMA_HOME_RESOLVED}"

if [ -f "$RECEIPT_FILE" ] && grep -q "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE"; then
  echo "[register_codex_rsi_lab_manager] receipt already present in ${RECEIPT_FILE}"
  echo "[register_codex_rsi_lab_manager] idempotent skip; existing entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1
  exit 0
fi

if ! "$PYTHON_BIN" -c "import dharma_swarm.roaming_onboarding" 2>/dev/null; then
  echo "[register_codex_rsi_lab_manager] ERROR: cannot import dharma_swarm.roaming_onboarding"
  echo "[register_codex_rsi_lab_manager] Check canonical repo, venv, and pydeps paths under ${LAB_BASE}"
  exit 1
fi

set +e
"$PYTHON_BIN" -m dharma_swarm.roaming_onboarding \
  --callsign "$CALLSIGN" \
  --agent-uid "$AGENT_UID" \
  --harness "$HARNESS" \
  --role "$ROLE" \
  --department "$DEPARTMENT" \
  --squad-id forge_rsi \
  --model "$MODEL" \
  --provider "$PROVIDER" \
  --endpoint "ssh://meghadharma/root/rsi-lab/current/repo" \
  --description "$DESCRIPTION" \
  --registration-source "examples/agents/codex_rsi_lab_manager.registration.json" \
  --capability "forge_lab_monitoring" \
  --capability "bounded_experiment_orchestration" \
  --capability "result_receipt_audit" \
  --capability "after_run_notes" \
  --capability "a2a_correspondence" \
  --capability "agent_card_maintenance" \
  --capability "ssh_remote_lab_operations" \
  --capability "test_execution" \
  --capability "evidence_synthesis" \
  --capability "honesty_boundary_enforcement"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  echo "[register_codex_rsi_lab_manager] CLI exited rc=${rc}"
  exit 2
fi

echo "[register_codex_rsi_lab_manager] CLI succeeded"
if [ -f "$RECEIPT_FILE" ]; then
  echo "[register_codex_rsi_lab_manager] latest receipt entry:"
  grep "\"callsign\": *\"${CALLSIGN}\"" "$RECEIPT_FILE" | tail -1 || true
else
  echo "[register_codex_rsi_lab_manager] NOTE: receipt file not found at ${RECEIPT_FILE}"
  echo "[register_codex_rsi_lab_manager] registration may have used a different DHARMA_HOME"
fi

echo "[register_codex_rsi_lab_manager] done."
