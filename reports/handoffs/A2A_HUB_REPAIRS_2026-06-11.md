# A2A Hub Repairs — 2026-06-11

Hub-side repair pass following Devin's topology confirmation: AGNI NATS
(`wss://157.245.193.15:8443`, JetStream stream `DHARMA_A2A`, local context
`agni-wss`) is the working rendezvous. Companion document:
`reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md`.

---

## 1. devin_inbox consumer — FIXED ✅

**Problem:** durable consumer `devin_inbox` on `DHARMA_A2A` filtered
`dharma.a2a.claude` instead of `dharma.a2a.devin` (created 2026-06-01, last
delivered stream seq 188 — dead since June 1).

**Action taken** (via `nats --context agni-wss`, trishula creds):

```bash
nats --context agni-wss consumer rm DHARMA_A2A devin_inbox -f
nats --context agni-wss consumer add DHARMA_A2A devin_inbox \
  --filter=dharma.a2a.devin --pull --deliver=8106880 \
  --ack=explicit --wait=30s --max-pending=1000 --replay=instant \
  --max-deliver=-1 --max-waiting=512 --defaults
```

**Verified output** (`nats consumer info DHARMA_A2A devin_inbox`, 2026-06-11 10:47 JST):

```
Filter Subject: dharma.a2a.devin
Deliver Policy: From Sequence 8106880
Ack Policy: Explicit          Ack Wait: 30.00s
Last Delivered: Consumer seq 0, Stream seq 8,106,879
Unprocessed Messages: 3
```

Notes:
- Only delivery state was lost (acceptable — consumer dead since June 1). The
  stream was not touched; nothing purged.
- Observed backlog on `dharma.a2a.devin` from seq 8,106,880 is **3 messages**
  (not ~30). The ~30-message figure matches the `merge_master_mike_inbox`
  pending count — most of today's traffic went to `dharma.a2a.fleet` /
  `dharma.a2a.merge_master_mike` subjects, which this consumer correctly
  excludes.

**Mirror-check `merge_master_mike_inbox`: NO FIX NEEDED.** Its filter is
already correct (`dharma.a2a.merge_master_mike`, Deliver Policy New, last
delivered seq 41, 30 unprocessed). It is simply not being pulled — a consumer
liveness issue on Mike's side, not a filter defect. Left untouched.

---

## 2. AGNI NATS server config (devin permissions) — FIXED ✅ (applied + reloaded)

SSH worked (`Host agni` → root@157.245.193.15 in `~/.ssh/config`). Server:
`nats-server -c /etc/nats-server.conf` under systemd unit `nats.service`
(no docker).

**Root-cause refinement:** the running config *already* allowed devin
subscribe on `dharma.a2a.devin` / `dharma.a2a.devin.>` and the
`devin_inbox` JS API subjects. The actual violations in
`/var/log/nats-server.log` were:

```
Publish Violation - User "devin", Subject "$JS.API.STREAM.NAMES"      (repeated, Jun 2–10)
Publish Violation - User "devin", Subject "$JS.API.STREAM.LIST"       (Jun 10)
Publish Violation - User "devin", Subject "$JS.API.STREAM.MSG.GET.DHARMA_FLEET"
Publish Violation - User "devin", Subject "$JS.API.CONSUMER.CREATE.DHARMA_FLEET"
Subscription Violation - User "devin", Subject "dharma.agent.devin.inbox"  (Jun 11 01:13Z)
```

i.e. Devin's client fails at JetStream *discovery* (`STREAM.NAMES`/`LIST`,
which nats CLI/libraries call first) and at the `dharma.agent.devin.inbox`
plain subscribe. (`DHARMA_FLEET` violations are expected — that stream lives
on the Mac-local broker, not AGNI; see §3.)

**Diff applied** (backup at
`/etc/nats-server.conf.pre-devin-jsread-20260611T0150Z.bak`):

```diff
           "$JS.API.CONSUMER.INFO.DHARMA_A2A.devin_inbox",
           "$JS.API.CONSUMER.MSG.NEXT.DHARMA_A2A.devin_inbox",
           "$JS.API.CONSUMER.DELETE.DHARMA_A2A.devin_inbox",
+          "$JS.API.STREAM.NAMES",
+          "$JS.API.STREAM.LIST",
+          "$JS.API.STREAM.MSG.GET.DHARMA_A2A",
+          "$JS.API.CONSUMER.LIST.DHARMA_A2A",
+          "$JS.API.CONSUMER.NAMES.DHARMA_A2A",
           "$JS.API.STREAM.INFO.DHARMA_A2A",
           "$JS.ACK.DHARMA_A2A.devin_inbox.>"
         ] }
-        subscribe: { allow: [ "dharma.a2a.fleet", "dharma.a2a.claude", "dharma.a2a.devin", "dharma.a2a.devin.>", "_INBOX.>" ] }
+        subscribe: { allow: [ "dharma.a2a.fleet", "dharma.a2a.claude", "dharma.a2a.devin", "dharma.a2a.devin.>", "dharma.agent.devin.inbox", "dharma.agent.devin.>", "_INBOX.>" ] }
```

Purely additive; only the `devin` user block touched.

**Reload verified** (in-place, same PID 3872266 — no restart, no disconnects):

```
nats-server: configuration file /etc/nats-server.conf is valid
[3872266] 2026/06/11 02:05:42 [INF] Reloaded: authorization users
[3872266] 2026/06/11 02:05:42 [INF] Reloaded server configuration
```

**Devin should now retest** (his creds were not exercised from the hub —
deliberately, to keep credential material out of this session):

```bash
nats consumer info DHARMA_A2A devin_inbox        # should succeed now
nats consumer next DHARMA_A2A devin_inbox --count 5 --ack   # drain the 3-message backlog
nats sub dharma.agent.devin.inbox                # subscribe should no longer be denied
```

If anything is still denied, the violation will land in
`/var/log/nats-server.log` on AGNI with the exact subject — extend the allow
list the same way.

---

## 3. Codex publishes to the wrong broker — ROOT CAUSE FOUND, recommendation only (code untouched)

### Topology found

Two disjoint brokers, no bridge between them:

| | Mac-local "fleet" broker | AGNI rendezvous |
|---|---|---|
| Endpoint | `nats://127.0.0.1:4222` (loopback-only) | `wss://157.245.193.15:8443` |
| Config | `~/.dharma/nats/local-nats.conf` | `/etc/nats-server.conf` on AGNI |
| Stream | `DHARMA_FLEET` (8,275 msgs, ~4.5 MiB, active) | `DHARMA_A2A` (seq ~8.1M) |
| Process | `com.dhyana.nats` launchd (PID 2011) | `nats.service` systemd (PID 3872266) |

### Where codex's endpoint comes from (pure config)

`~/.dharma/agent_keys.env` line 51 (sourced everywhere, THE ONE WAY):

```bash
export DHARMA_NATS_URL=nats://127.0.0.1:4222
```

Code-side resolution chains (all consistent, all land on loopback by default):

- `scripts/runtime/a2a_send.py` → `pr_merge_control._nats_config`:
  `MERGE_MASTER_MIKE_NATS_URL` → `DEVIN_NATS_URL` → `DHARMA_NATS_URL` → `NATS_URL`
- `dharma_swarm/operator_core/nats_live_contact.py` + `nats_substrate_status.py`:
  `DHARMA_NATS_URL` → `NATS_URL` → default `nats://127.0.0.1:4222`
- `dharma_swarm/a2a/nats_transport.py` `NatsTransportConfig.endpoint`
  default `nats://127.0.0.1:4222`, stream `DHARMA_A2A` (NATS-track owned
  surface — **not modified**)

`DEVIN_NATS_URL` / `DEVIN_NATS_USER` / `DEVIN_NATS_PW` are only defined as
GitHub Actions secrets (`.github/workflows/codex-mention-router.yml`,
`merge-master-mike-backlog.yml`) — they are **not** in the local env, so any
local codex send that doesn't explicitly export them falls through to
`DHARMA_NATS_URL` = loopback = `DHARMA_FLEET`. That is the whole bug.

### Why I did NOT flip `DHARMA_NATS_URL` directly

Changing that one value to AGNI would (a) silently retarget every local
fleet-fabric consumer (live contact, substrate status, receipts) that
correctly depends on the loopback broker, and (b) fail anyway — the AGNI
endpoint needs wss + custom CA (`~/.dharma/nats/agni-ws-ca.pem`) + user/pass,
which a bare URL doesn't carry. The local broker is not "wrong" — it is the
intra-Mac fleet fabric. Codex's *outbound-to-Devin* lane is what needs AGNI.

### Recommended fix (pick one; #1 is the smallest)

1. **Add devin-family env vars via dkeys (operator action, one command each):**

   ```bash
   dkeys add DEVIN_NATS_URL=wss://157.245.193.15:8443
   dkeys add DEVIN_NATS_USER=devin
   dkeys add DEVIN_NATS_PW=<from /etc/nats-server.conf on agni>
   ```

   `a2a_send.py`'s chain then resolves AGNI ahead of the loopback default
   with zero code change, matching exactly how today's successful hub→Devin
   sends worked (see `reports/a2a/send_receipts/20260611T013655Z-devin-*.json`:
   `endpoint wss://157.245.193.15:8443`, `seq 8106884`, `status DEVIN_CONSUMED`).
   Codex's sender should call `scripts/runtime/a2a_send.py` (the receipted,
   AGNI-capable door) rather than raw-publishing to the local broker.

2. **Leafnode bridge (durable, structural):** Mac is NAT'd (can dial out;
   AGNI can't dial in), so a NATS *leafnode* from the Mac-local server to
   AGNI is the canonical topology: AGNI adds a `leafnodes { port: 7422 }`
   listener; `~/.dharma/nats/local-nats.conf` adds a `leafnodes { remotes:
   [{ url: "tls://157.245.193.15:7422", ... }] }` block. Then
   `dharma.a2a.>` published on 127.0.0.1:4222 propagates to AGNI and codex
   needs no retarget at all. Plain stream `sources`/`mirror` on DHARMA_A2A
   cannot reach the Mac broker without this (or a gateway), because the two
   servers are unclustered and AGNI cannot initiate the connection.

3. Decision belongs to the NATS track (`runtime-truth-nats-2026-06`,
   @codex): `dharma_swarm/a2a/nats_transport.py` and the planned
   `a2a_nats_contact.py` / `a2a_core_contact.py` are its owned surfaces.
   Note: those two contact modules **do not exist in this worktree yet**.

### Bonus finding — dead fleet bridge launchd job

`com.dhyana.nats-a2a-bridge` (plist:
`~/Library/LaunchAgents/com.dhyana.nats-a2a-bridge.plist`, env
`DHARMA_NATS_URL=nats://127.0.0.1:4222`) is **crash-looping with status 1**:

```
/Users/dhyana/dharma_swarm/.venv/bin/python: No module named dharma_swarm.operator_core.nats_a2a_bridge
```

The module was removed from the repo (mdfind finds no copy anywhere), so the
local NATS↔file-inbox bridge (`dharma.agent.*.inbox` →
`~/.dharma/a2a_bus/inboxes/`) is down. Operator decision needed: restore the
module, repoint the plist, or `launchctl bootout gui/$UID/com.dhyana.nats-a2a-bridge`
and retire it.

---

## Status summary

| Item | Status |
|---|---|
| `devin_inbox` filter → `dharma.a2a.devin`, from seq 8,106,880 | **FIXED + verified** (3 pending) |
| `merge_master_mike_inbox` filter | Already correct — no change (30 pending, unconsumed) |
| AGNI server config: devin JS discovery + `dharma.agent.devin.inbox`/`.>` subscribe | **APPLIED + reloaded in place** (backup on AGNI) |
| Devin-side retest of creds | Pending Devin (commands above) |
| Codex broker retarget | Root cause = `DHARMA_NATS_URL` loopback default in `~/.dharma/agent_keys.env`; recommendation #1 (dkeys add DEVIN_NATS_*) or #2 (leafnode); no code touched |
| `com.dhyana.nats-a2a-bridge` launchd | Found dead (module deleted) — operator decision |

---

## Delivery log

- **2026-06-11T02:16:26Z** — Consolidated packet (hub repairs + 3-PR pre-review + codex root cause + bridge FYI) sent to Devin over AGNI NATS by `fable_5_cursor`. Devin lane: `dharma.a2a.devin` packet_id `3c323c365793`, **JetStream pub-ack seq 8,106,890** on `DHARMA_A2A`; fleet CC: `dharma.a2a.fleet` packet_id `70272d836214`, **seq 8,106,891**. **No ack/reply from Devin** within a ~7-min poll window (02:16–02:23Z); his live listener was last seen acking at 02:07:37Z (`ack.f09b890507cf`), so the session likely ended between 02:08 and 02:16 — packet is durably persisted in `devin_inbox` backlog (deliver-from seq 8,106,880) for his next drain. Packet: `inter_agent/devin/inbound/2026-06-11T0220Z-hub-consolidated-repairs-pr-prereview.md`; receipts: `reports/a2a/send_receipts/20260611T021928Z-devin-3c323c365793.json`, `reports/a2a/send_receipts/20260611T021951Z-fleet-70272d836214.json`.
