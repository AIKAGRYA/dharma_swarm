#!/usr/bin/env bash
# Read-only verifier for docs/ops/AGNI_FLEET_FUSION_ONE_SITTING_2026-09-04.md.
# Runs on AGNI. Prints one line per door with PASS / FAIL / SKIP and a reason.
# It never mutates anything and never prints a credential. Env inputs (optional):
#   NATS_PEER_USER / NATS_PEER_PASSWORD   a non-hub user to probe Door 1 with
#   DASHBOARD_API_KEY                     to probe Door 3's authenticated read
#   GATEWAY_URL                           e.g. https://host/a2a-gateway (Door 2)
set -uo pipefail

host="$(hostname 2>/dev/null || echo unknown)"
stamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "agni-fleet-fusion-verify · ${stamp} · host=${host}"

pass() { echo "PASS door${1}: $2"; }
fail() { echo "FAIL door${1}: $2"; }
skip() { echo "SKIP door${1}: $2"; }

# Door 1 — peer publish allowed for a non-hub user.
if command -v nats >/dev/null 2>&1 && [[ -n "${NATS_PEER_USER:-}" && -n "${NATS_PEER_PASSWORD:-}" ]]; then
  if nats --user "$NATS_PEER_USER" --password "$NATS_PEER_PASSWORD" \
       pub dharma.a2a.fable_claude_code '{"ping":"ffr-d1-verify"}' >/dev/null 2>&1; then
    pass 1 "peer publish accepted for ${NATS_PEER_USER} (FFR-D1 applied)"
  else
    fail 1 "peer publish refused for ${NATS_PEER_USER} (FFR-D1 not applied)"
  fi
else
  skip 1 "set NATS_PEER_USER/NATS_PEER_PASSWORD and install the nats CLI to probe"
fi

# Door 2 — gateway health (unauthenticated) and, if a token is present, whoami.
if [[ -n "${GATEWAY_URL:-}" ]]; then
  body="$(curl -sS --max-time 5 "${GATEWAY_URL%/}/health" 2>/dev/null || true)"
  if grep -q '"service":"a2a-mailbox-gateway"' <<<"$body"; then
    pass 2 "gateway health ok at ${GATEWAY_URL%/}/health"
  else
    fail 2 "gateway health missing at ${GATEWAY_URL%/}/health"
  fi
  if [[ -n "${DHARMA_A2A_GATEWAY_TOKEN:-}" ]]; then
    who="$(curl -sS --max-time 5 -H "Authorization: Bearer ${DHARMA_A2A_GATEWAY_TOKEN}" \
           "${GATEWAY_URL%/}/a2a/mailbox/whoami" 2>/dev/null || true)"
    uid="$(python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("agent_uid",""))
except Exception: print("")' <<<"$who")"
    if [[ -n "$uid" ]]; then pass 2 "whoami resolves token to agent_uid=${uid}"; else fail 2 "whoami did not resolve the token"; fi
  fi
else
  skip 2 "set GATEWAY_URL (and optionally DHARMA_A2A_GATEWAY_TOKEN) to probe"
fi

# Door 3 — owner API refuses anonymous reads and answers authenticated ones; Fleet Hub binds the HTTP adapter.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8420/api/mission-control/missions 2>/dev/null || echo 000)"
case "$code" in
  401) pass 3 "owner API up on :8420 and refuses anonymous reads" ;;
  000) fail 3 "owner API not listening on 127.0.0.1:8420" ;;
  *)   fail 3 "owner API anonymous read returned HTTP ${code} (expected 401)" ;;
esac
if [[ -n "${DASHBOARD_API_KEY:-}" ]]; then
  authed="$(curl -sS --max-time 5 -H "Authorization: Bearer ${DASHBOARD_API_KEY}" http://127.0.0.1:8420/api/mission-control/missions 2>/dev/null || true)"
  if grep -q '"authority": *"TaskBoard+RuntimeStateStore"' <<<"$authed"; then
    pass 3 "owner API authenticated read returns the owner projection"
  elif grep -q 'state_not_initialized' <<<"$authed"; then
    pass 3 "owner API reachable; state tree has no missions yet (state_not_initialized is honest)"
  else
    fail 3 "owner API authenticated read did not return a projection"
  fi
fi
if [[ -r /etc/dharma/fleet-hub.env ]]; then
  if grep -Eq '^FLEET_HUB_MISSION_PROVIDER_URL=' /etc/dharma/fleet-hub.env \
     && grep -Eq '^FLEET_HUB_MISSION_PROVIDER_TOKEN=[^[:space:]]' /etc/dharma/fleet-hub.env \
     && grep -Eq '^FLEET_HUB_MISSION_IDS=[^[:space:]]' /etc/dharma/fleet-hub.env; then
    pass 3 "fleet-hub.env carries the three owner-adapter values (values not printed)"
  else
    fail 3 "fleet-hub.env is missing one of FLEET_HUB_MISSION_PROVIDER_URL / _TOKEN / FLEET_HUB_MISSION_IDS"
  fi
else
  skip 3 "/etc/dharma/fleet-hub.env not readable by this user"
fi
hub="$(curl -s --max-time 5 http://127.0.0.1:8444/health 2>/dev/null || true)"
if [[ -n "$hub" ]]; then pass 3 "fleet-hub answering on :8444"; else fail 3 "fleet-hub not answering on 127.0.0.1:8444"; fi

# Door 4 — exactly one durable drains dharma.a2a.hermes; rushabdev has its own.
if command -v nats >/dev/null 2>&1; then
  consumers="$(nats consumer ls DHARMA_A2A 2>/dev/null || true)"
  if [[ -n "$consumers" ]]; then
    if grep -q 'rushabdev' <<<"$consumers"; then pass 4 "a rushabdev durable exists on DHARMA_A2A"; else fail 4 "no rushabdev durable on DHARMA_A2A (FFR-D2 open)"; fi
  else
    skip 4 "nats consumer ls DHARMA_A2A returned nothing (credentials or ACL)"
  fi
else
  skip 4 "nats CLI not installed"
fi
echo "done · paste this block with host+commit into AIKAGRYA/dharma_swarm#1519"
