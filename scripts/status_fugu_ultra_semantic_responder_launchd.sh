#!/usr/bin/env bash
set -euo pipefail
DOMAIN="gui/$(id -u)"
LABEL="com.dharma.fugu-ultra-semantic-responder"
LAUNCHCTL_BIN="${LAUNCHCTL_BIN:-launchctl}"
STATE_DIR="${HOME}/.dharma/external_agents/fugu_ultra/nest/semantic_responder"
HEARTBEAT="${STATE_DIR}/heartbeat.json"
STDOUT_LOG="${HOME}/.dharma/logs/${LABEL}.stdout.log"
STDERR_LOG="${HOME}/.dharma/logs/${LABEL}.stderr.log"
launch_state="not_loaded"
launchd_state="missing"
launchd_pid="missing"
out=$("${LAUNCHCTL_BIN}" print "${DOMAIN}/${LABEL}" 2>&1) && rc=0 || rc=$?
if [[ "$rc" -eq 0 ]]; then
  launch_state="loaded"
  launchd_state=$(printf '%s\n' "$out" | awk '$1 == "state" && $2 == "=" {print $3; exit}')
  launchd_pid=$(printf '%s\n' "$out" | awk '$1 == "pid" && $2 == "=" {print $3; exit}')
fi
echo "label=${LABEL}"
echo "launchd=${launch_state}"
echo "launchd_state=${launchd_state:-missing}"
echo "launchd_pid=${launchd_pid:-missing}"
echo "heartbeat=${HEARTBEAT}"
if [[ -f "${HEARTBEAT}" ]]; then
  python3 - "$HEARTBEAT" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
for k in ['status','timestamp','pending_delivery_count','live_model_call_claimed','semantic_reply_claim','domain_receipt_claim']:
    print(f"heartbeat_{k}={d.get(k, 'missing')}")
print('latest_receipt=' + str((d.get('latest_receipt') or {}).get('receipt_path') or ''))
PY
else
  echo "heartbeat_status=missing"
fi
echo "stdout=${STDOUT_LOG}"
echo "stderr=${STDERR_LOG}"
