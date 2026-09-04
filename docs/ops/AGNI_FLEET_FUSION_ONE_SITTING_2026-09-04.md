---
role: runbook
date: 2026-09-04
status: ACTIVE — operator-executed; ratified by the operator's "yes to all" on 2026-09-04 against docs/plans/FLEET_FUSION_REVIEW_2026-09-04.md §6 items 1–4
subordinates_to: docs/ops/A2A_LIVE_WIRE_RUNBOOK.md (the authoritative step detail); docs/governance/CANONICAL_DOC_STACK.md
world:
  commit: b59b8ef (branch tip) · host: Claude Code cloud sandbox · branch: claude/dharma-swarm-fusion-review-voer57
---

# AGNI fleet fusion — one sitting, four doors

Everything below runs **on AGNI** (`157.245.193.15`) as an operator. No step
can be done from a sandboxed agent, which is why this exists. Each step ends
with a verification command; a step without its expected output is not done.
Total estimate: 2–3 hours. Steps 1–2 follow `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md`
exactly and are summarized here so one document carries the whole sitting.

Secrets discipline: every password and token below is typed into a prompt or
a root-owned env file. None goes into a shell history line, a commit, a log,
or a chat message. `scripts/ops/agni_fleet_fusion_verify.sh` is the read-only
checker for this sitting; run it after each step.

## Door 1 — peer-to-peer publish on the hub (FFR-D1)

Why: today every seat may only broadcast on `dharma.a2a.fleet`; direct
messages fail with a permissions violation, and Fleet Hub therefore never
marks a seat "heard" (`fleet-hub/src/hub/presence.py:13-15`).

```bash
# 1. One bcrypt hash per user (hermes, rushabdev, devin, a2a_gateway, fleet_hub).
nats server passwd            # run once per user; paste each hash into the template
# 2. Read the REAL durable consumer names first (the template's are placeholders):
nats consumer ls DHARMA_A2A
# 3. Merge scripts/ops/agni_hub_acl_ffr_d1.conf's authorization block into
#    /etc/nats/nats-server.conf (keep listen/websocket/jetstream/tls untouched),
#    with each user's durable names listed EXACTLY (NATS `*` is one token, not a glob).
# 4. Validate and hot-reload (authz reloads without dropping connections):
nats-server --config /etc/nats/nats-server.conf -t && systemctl reload nats-server
```

Verify:

```bash
nats --user rushabdev --password "$(read -rs -p 'rushabdev pw: ' p; echo "$p")" pub dharma.a2a.fable_claude_code '{"ping":"ffr-d1"}'
# EXPECTED: publish succeeds (was: Permissions Violation)
```

Then set `FFR-D1 status: APPLIED` in `docs/ops/FLEET_FIELD_REGISTRY.yaml:47-59`
(any session can do the edit once you confirm the output).

## Door 2 — the HTTPS mailbox gateway (the door every seat uses)

Why: `dharma_swarm/a2a/mailbox_gateway.py` maps one token to one agent
identity and lets any HTTPS-capable seat publish to peers and drain its own
inbox. It has been merged and tested since 2026-07-09 and never run.

```bash
cd /opt/dharma/dharma_swarm   # a checkout of origin/main (create it if absent: git clone https://github.com/AIKAGRYA/dharma_swarm)
python3 -m venv .venv && . .venv/bin/activate && pip install -e . nats-py
# Mint one token per seat; each prints its plaintext ONCE — deliver to that seat's private channel.
python3 scripts/ops/mint_a2a_gateway_token.py hermes                          # AGNI Hermes
python3 scripts/ops/mint_a2a_gateway_token.py rushabdev
python3 scripts/ops/mint_a2a_gateway_token.py meghadharma_hermes --callsign fleet.reply.meghadharma_hermes
python3 scripts/ops/mint_a2a_gateway_token.py hermes-m5 --callsign hermes     # Mac Hermes (see Door 4 note)
python3 scripts/ops/mint_a2a_gateway_token.py fable_claude_code
# Serve on loopback; Caddy fronts it at https://<agni-domain>/a2a-gateway/* (or :8422 behind the existing TLS).
NATS_URL=nats://127.0.0.1:4222 NATS_USER=a2a_gateway NATS_PASSWORD="$(read -rs -p 'gateway pw: ' p; echo "$p")" \
  uvicorn scripts.runtime.a2a_gateway_server:app --host 127.0.0.1 --port 8422
# Persist as a systemd unit (User=a2a-gateway, EnvironmentFile=/etc/dharma/a2a-gateway.env, mode 0640) once verify passes.
```

Verify, from any machine holding a token:

```bash
curl -s https://<gateway-host>/a2a-gateway/health          # EXPECTED {"ok":true,"service":"a2a-mailbox-gateway","stream":"DHARMA_A2A"}
DHARMA_A2A_GATEWAY_URL=https://<gateway-host>/a2a-gateway DHARMA_A2A_GATEWAY_TOKEN=<token> \
  python3 .agents/skills/dharma-fleet-mailbox/mailbox.py whoami   # EXPECTED {"ok": true, "agent_uid": "...", ...}
```

Each seat's `whoami` reply is the receipt the fleet registry wants
(`docs/ops/FLEET_FIELD_REGISTRY.yaml` `last_verified_send`). Hermes seats
install `.agents/skills/dharma-fleet-mailbox/` under `~/.hermes/skills/` and
add two cron lines: drain inbox every 5 min, `heartbeat` every 10 min.

## Door 3 — Fleet Hub owner adapter (Board / Helm / Needs-John light up)

Why: `fleet-hub/src/hub/mission_http_provider.py` (PR AIKAGRYA/fleet-hub#17)
reads the canonical owner over HTTP. It needs an owner API to read from.

**Decision baked in here:** the owner databases (`~/.dharma/db/tasks.db`,
`~/.dharma/state/runtime.db`) must live on the same host that runs the owner
API. The Mac is intermittently off, so the owner API runs on AGNI next to
Fleet Hub, against the AGNI state tree. This means missions created from the
Mac are not visible on the phone until state converges (BR-007 territory);
that is the honest state, and Fleet Hub renders it as such.

```bash
# On AGNI, same checkout as Door 2:
cat > /etc/dharma/dharma-owner-api.env <<'ENV'
DASHBOARD_API_KEY=<long random secret; generate with: python3 -c "import secrets;print(secrets.token_urlsafe(48))">
DASHBOARD_API_MODE=production
DHARMA_STATE_DIR=/var/lib/dharma
ENV
chmod 0640 /etc/dharma/dharma-owner-api.env
# Run the owner API on loopback only; Fleet Hub is on the same host so no proxy route is needed.
set -a; . /etc/dharma/dharma-owner-api.env; set +a
uvicorn api.main:app --host 127.0.0.1 --port 8420
# Persist as a systemd unit (User=dharma-owner) once verify passes.

# Then add three lines to /etc/dharma/fleet-hub.env (root:fleet-hub, 0640):
FLEET_HUB_MISSION_PROVIDER_URL=http://127.0.0.1:8420
FLEET_HUB_MISSION_PROVIDER_TOKEN=<the same DASHBOARD_API_KEY>
FLEET_HUB_MISSION_IDS=<comma-separated mission ids you want on the phone>
systemctl restart fleet-hub
```

Verify:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8420/api/mission-control/missions   # EXPECTED 401 (anonymous refused)
curl -s -H "Authorization: Bearer $DASHBOARD_API_KEY" http://127.0.0.1:8420/api/mission-control/missions | head -c 300
# EXPECTED {"ok": true, ... "authority": "TaskBoard+RuntimeStateStore" ...}
# On the phone: log in, open Board. EXPECTED: configured missions render; bootstrap shows
# connections.mission_provider_kind = "owner_http_read_only".
```

If the AGNI state tree has no missions yet, the owner answers
`503 state_not_initialized` and Fleet Hub shows "unavailable" — correct, not
a bug. Create the first mission through the Mission Control MCP or the
Python adapter to light the board.

## Door 4 — rushabdev gets its own subject (FFR-D2)

Why: AGNI Hermes and rushabdev both drain `dharma.a2a.hermes`, so each
silently steals the other's messages (`docs/ops/FLEET_FIELD_REGISTRY.yaml:60-68`).

```bash
# On rushabdev (openclaw23): change the bridge's subscribe subject and consumer to
NATS_SUBJECT=dharma.a2a.rushabdev NATS_CONSUMER=rushabdev_inbox
# Restart its bridge daemon. In the Door-1 ACL, user rushabdev's subscribe allow list
# must name dharma.a2a.rushabdev (already the roster value in fleet-hub/src/roster.json:24).
```

Verify:

```bash
nats consumer info DHARMA_A2A rushabdev_inbox     # EXPECTED: filter subject dharma.a2a.rushabdev
nats consumer ls DHARMA_A2A | grep -c hermes      # EXPECTED: exactly one hermes durable remains
```

Then set `FFR-D2 status: RESOLVED` in the registry.

Note on the Mac Hermes (`hermes-m5`): it lives behind the Mac's separate,
unbridged broker. With Door 2 open it no longer needs a bridge; it joins
through the gateway like any other seat. Do not bridge the two brokers.

## After the sitting

Run `bash scripts/ops/agni_fleet_fusion_verify.sh` and paste its output into
the PR thread of AIKAGRYA/dharma_swarm#1519. That output, with host and
commit, is the receipt that flips `fleet-advancement-2026-08`'s
`owner-adapters-qualified` item.
