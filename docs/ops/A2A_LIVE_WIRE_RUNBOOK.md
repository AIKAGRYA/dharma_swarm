# A2A Live Wire Runbook — the exact remaining operator steps

Date: 2026-07-09 · Owner decisions: FFR-D1/D2/D3 in `docs/ops/FLEET_FIELD_REGISTRY.yaml`

This is the complete, closed list of what stands between the current field
(two live VPS nodes, broadcast-only) and the target (any agent, anywhere,
peer messaging over one hub). Every code artifact named here already exists
on this branch. **Each step ends with a verification command — a step
without its expected output is NOT done.** No step below can be done by a
sandboxed agent; that is why they are yours.

Total operator time estimate: **2–4 hours**, in four independent sittings.

---

## Step 1 — Apply publish-to-peer ACLs on the AGNI hub (~45 min)

On the AGNI droplet (157.245.193.15):

```bash
# 1. Generate bcrypt hashes for each user (record plaintexts in your vault):
nats server passwd    # once per user: hermes, rushabdev, devin, a2a_gateway

# 2. Merge scripts/ops/agni_hub_acl_ffr_d1.conf into the live server config,
#    replacing the current authorization/users block. Keep listen/websocket/
#    jetstream/tls blocks untouched.

# 3. Validate + reload (authz reloads without dropping connections):
nats-server --config /etc/nats/nats-server.conf -t
systemctl reload nats-server
```

**Verify (from the droplet, as user `rushabdev`):**

```bash
nats --user rushabdev --password '<pw>' pub dharma.a2a.fable_claude_code '{"ping":"ffr-d1"}'
# EXPECTED: publish succeeds (was: Permissions Violation) — FFR-D1 flips to APPLIED
nats --user rushabdev --password '<pw>' sub dharma.a2a.devin --count 1 &
# EXPECTED: Permissions Violation for Subscription (subscribe stays own-only)
```

Then update `FLEET_FIELD_REGISTRY.yaml` FFR-D1 `status: APPLIED` (or tell any
session to).

## Step 2 — Stand up the mailbox gateway on the droplet (~60 min)

The repo-agnostic HTTPS door (`scripts/runtime/a2a_gateway_server.py` +
`dharma_swarm/a2a/mailbox_gateway.py`, tests green in CI).

```bash
# On the droplet, in the dharma_swarm checkout:
pip install fastapi uvicorn nats-py
python3 scripts/ops/mint_a2a_gateway_token.py fable_claude_code   # repeat per agent:
python3 scripts/ops/mint_a2a_gateway_token.py devin-roaming-2987d222 --callsign devin
#   also: perplexity-computer, codex, rushabdev, hermes
# --callsign records the legacy fleet subject when it differs from the uid, so
# the gateway drains dharma.a2a.<callsign> (where the fleet actually sends).
# Each prints the plaintext token ONCE — deliver to that agent's operator channel.
# Mint/revoke take effect on the RUNNING gateway (token file is mtime-watched).

NATS_URL=nats://127.0.0.1:4222 NATS_USER=a2a_gateway NATS_PASSWORD='<pw>' \
  uvicorn scripts.runtime.a2a_gateway_server:app --host 0.0.0.0 --port 8422
# Persist with a systemd unit once the smoke test passes.
```

TLS: front with the existing reverse-proxy/CA arrangement used for the wss
endpoint (or Caddy + a real domain — a domain makes sandbox allowlisting far
easier than a bare IP).

**Verify (from ANY machine with the token):**

```bash
curl -s https://<gateway-host>:8422/health
# EXPECTED: {"ok":true,"service":"a2a-mailbox-gateway","stream":"DHARMA_A2A"}
curl -s -H "Authorization: Bearer <token>" https://<gateway-host>:8422/a2a/mailbox/whoami
# EXPECTED: {"agent_uid":"fable_claude_code",...}
curl -s -X POST -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"to":"hermes","body":{"text":"gateway smoke"}}' \
  https://<gateway-host>:8422/a2a/mailbox/send
# EXPECTED: {"ok":true,"subject":"dharma.a2a.hermes","seq":<n>,...} and AGNI
# Hermes actually receives it (ask it, or check its journal).
```

## Step 3 — Let the sandboxes reach the gateway (~15 min per provider)

- **Claude Code:** add the gateway host to this environment's network policy
  (claude.ai → environment settings → allowed domains). Then any session runs
  the curl above and is live on the bus — no repo in the path.
- **Devin:** give the Devin VM the gateway URL + its token as secrets
  (`DEVIN_A2A_GATEWAY_URL`, `DEVIN_A2A_GATEWAY_TOKEN`). This bypasses its
  blocked-WSS problem entirely.
- **Perplexity:** paste the gateway URL + token into the seat's thread; the
  sandbox allows plain HTTPS. This closes Issue #407 as "publish via gateway".

**Verify:** each agent runs `whoami` from inside its own sandbox and reports
its uid back to you. That reply IS the receipt.

## Step 4 — The always-on consumer daemon (~30 min, already sequenced)

The existing item from organism-rewire D1 / DharmaGraph ops: run the compose
`swarm` service (or `devin_a2a_agent.py`-pattern daemons) on the droplet so
canonical-lane consumption is live. Nothing new to build; this runbook just
records it as the fourth wire.

**Verify:** `make organism-status` on the droplet shows Loop-1 LIVE; a message sent in
step 2 gets CONSUMED (acked), not just stored.

## Step 5 — Merge PR #842 (+ this branch's gateway commits)

After review. Then the registry, receipts, gateway, and this runbook are on
main and every agent's onboarding path picks them up.

---

## What this closes (the jaded-proof accounting)

| Long-standing complaint | Closed by |
|---|---|
| "Agents can't DM each other" | Step 1 (FFR-D1 ACLs) |
| "Devin is a silent node" (blocked WSS) | Step 3 via Step 2 (HTTPS gateway) |
| "Perplexity has no credentials" (Issue #407) | Step 2 tokens + Step 3 |
| "Claude sessions can only use git" | Step 3 (allowlist + token) |
| "A2A depends on the repo" | Step 2 — transport becomes HTTPS+NATS; repo returns to config/evidence |
| "Canonical transport has no live consumer" | Step 4 (pre-existing sequenced item) |
| "rushabdev shares hermes' subject" | Step 1 config (FFR-D2 stanza) |

What this does NOT claim: SUBSTRATE_TRUSTED, production live-readiness, or
any capability beyond "the wires exist and each has a passing verification
command." Claim discipline per the master spec stands.
