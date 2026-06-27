#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="gui/$(id -u)"
STREAM="${STREAM:-DHARMA_FLEET}"
LOG_DIR="${HOME}/.dharma/logs/a2a_inbox_bridge"
HEARTBEAT_DIR="${HOME}/.dharma/a2a_bus/bridge_heartbeats"
RECEIPT_DIR="${ROOT}/reports/a2a/inbox_bridge_receipts"
NATS_BIN="${NATS_BIN:-/opt/homebrew/bin/nats}"

FLEET_ROWS=(
  "hermes-m5|hermes_inbox|com.dharma.a2a-inbox-bridge.hermes-m5"
  "codex_composer|codex_composer_inbox|com.dharma.a2a-inbox-bridge.codex-composer"
  "fable_composer|fable_composer_inbox|com.dharma.a2a-inbox-bridge.fable-composer"
  "opus_composer|opus_composer_inbox|com.dharma.a2a-inbox-bridge.opus-composer"
  "devin-roaming-2987d222|devin_roaming_2987d222_inbox|com.dharma.a2a-inbox-bridge.devin-roaming-2987d222"
  "perplexity-computer|perplexity_computer_inbox|com.dharma.a2a-inbox-bridge.perplexity-computer"
)

json_field() {
  local path="$1"
  local key="$2"
  python3 - "$path" "$key" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    print("")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
print(payload.get(key, ""))
PY
}

latest_receipt_for() {
  local agent_uid="$1"
  if [[ ! -d "${RECEIPT_DIR}" ]]; then
    return 0
  fi
  find "${RECEIPT_DIR}" -maxdepth 1 -type f -name "*-${agent_uid}-*.json" -print \
    | sort \
    | tail -1
}

for row in "${FLEET_ROWS[@]}"; do
  IFS='|' read -r agent_uid consumer label <<< "${row}"
  heartbeat_file="${HEARTBEAT_DIR}/${agent_uid}.json"
  stdout_log="${LOG_DIR}/${label}.stdout.log"
  stderr_log="${LOG_DIR}/${label}.stderr.log"
  launch_state="not_loaded"
  if launchctl print "${DOMAIN}/${label}" >/dev/null 2>&1; then
    launch_state="loaded"
  fi
  heartbeat_status="$(json_field "${heartbeat_file}" status)"
  heartbeat_ts="$(json_field "${heartbeat_file}" timestamp)"
  latest_receipt="$(latest_receipt_for "${agent_uid}")"

  echo "agent_uid=${agent_uid}"
  echo "  label=${label}"
  echo "  launchd=${launch_state}"
  echo "  consumer=${consumer}"
  echo "  heartbeat=${heartbeat_file}"
  echo "  heartbeat_status=${heartbeat_status:-missing}"
  echo "  heartbeat_timestamp=${heartbeat_ts:-missing}"
  echo "  latest_receipt=${latest_receipt:-missing}"
  echo "  stdout=${stdout_log}"
  echo "  stderr=${stderr_log}"
  if [[ -x "${NATS_BIN}" ]]; then
    if "${NATS_BIN}" --no-context -s nats://127.0.0.1:4222 consumer info "${STREAM}" "${consumer}" -j --no-select >/dev/null 2>&1; then
      echo "  nats_consumer=inspectable"
    else
      echo "  nats_consumer=missing_or_uninspectable"
    fi
  else
    echo "  nats_consumer=nats_cli_missing"
  fi
done
