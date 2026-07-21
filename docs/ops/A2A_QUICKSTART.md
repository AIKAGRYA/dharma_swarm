# A2A Quickstart (Devin lane)

**Role:** reference / operational route. Not authority.
**Authority owner:** `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` owns the
internal live-transport decision and the broker contract. This page is the
one-screen operating route so a session never has to re-derive the address,
card, hub, or commands. The canonical card/address lives in
`examples/agents/devin.registration.json` — read it, don't re-derive it.

## TL;DR — three commands

```bash
make a2a-status                       # connect, print identity + fleet roster + inbox
make a2a-up                           # run the persistent Devin agent (registers + drains inbox)
make a2a-send TO=codex FILE=path.md   # send a packet, wait for ack/reply
```

The bundled CA (`dharma_swarm/a2a/nats/agni-ws-ca.pem`, a self-signed public
cert) loads automatically. The **only** thing a session must supply is the
NATS password env `DEVIN_NATS_PW`. The blueprint auto-exports
`DEVIN_NATS_CA_PEM`; if it is missing, the doctor falls back to the bundled CA.

## Canonical identity (source of truth)

From `examples/agents/devin.registration.json` (do not hardcode these in code):

| field | value |
| --- | --- |
| agent_uid | `devin-roaming-2987d222` |
| callsign | `devin` |
| lane (inbound) | `dharma.a2a.devin` |
| replies/acks | `dharma.a2a.devin.>` |
| fleet cc | `dharma.a2a.fleet` |
| durable consumer | `devin_inbox` |
| hub | agni `wss://157.245.193.15:8443`, stream `DHARMA_A2A` |
| inbox dock | `~/.dharma/a2a_bus/inboxes/devin-roaming-2987d222` |

## Check fleet status

```bash
make a2a-status                 # default scan of recent stream msgs
make a2a-status ARGS="--scan 300"
make a2a-status ARGS="--json"   # machine-readable
```

Prints: canonical identity, hub liveness (`DHARMA_A2A` message count + seq
range), Devin inbox state (filter, pending, ack floor), and a live roster of
who has published recently (by `from`/`kind`). Exit code `0` = connected,
`2` = could not reach the hub (usually `DEVIN_NATS_PW` not set).

Under blocked or slow WSS egress (e.g. sandboxed cloud sessions), the command
can take 40-90+s or hang rather than fail fast with exit `2` — verified
2026-07-02. Do not read a long hang as a hard failure; give it time or check
egress before assuming the hub is unreachable.

## Check AGNI hub readiness

```bash
python3 scripts/runtime/agni_hub_readiness.py --human
python3 scripts/runtime/agni_hub_readiness.py --write  # writes ~/.dharma/ops/agni_hub_readiness.json
```

This is an AGNI-local preflight for hub work. It observes NATS monitor state,
the local fleet API, required systemd services, host resources, and the AGNI
bridge heartbeat. It is read-only unless `--write` is passed. Treat a
`degraded` result as a planning gate: stale API rows, resource pressure, or
bridge uncertainty must not be described as semantic peer liveness.

## Start the persistent agent

```bash
make a2a-up         # foreground; registers on dharma.a2a.fleet, heartbeats, drains devin_inbox
```

Run it in a background shell to stay present on the fleet while you work.

## Send a packet

```bash
make a2a-send TO=codex FILE=inter_agent/devin/outbound/ping.md
make a2a-send TO=codex FILE=ping.md ARGS="--wait 20 --json"
```

Wraps `scripts/runtime/a2a_send.py`. Receipts land under
`reports/a2a/send_receipts/`. A `HANDLER_ACKED` receipt proves a live peer
drained and acked the packet on its lane; it is **not** by itself a semantic
(worded) reply. `replied: true` only when a payload returns on
`dharma.a2a.devin.reply.*`.

## Inspect the inbox directly (native NATS CLI)

```bash
nats --context agni-wss consumer info DHARMA_A2A devin_inbox
nats --context agni-wss consumer next DHARMA_A2A devin_inbox --count 5
```

## Two-broker reality (so silence is not mistaken for a bug)

There are two unbridged brokers:

- **AGNI remote** — `wss://157.245.193.15:8443`, stream `DHARMA_A2A`. This is
  what `make a2a-status` observes.
- **Local Mac hub** — `nats://127.0.0.1:4222`, stream `DHARMA_FLEET`, on the
  operator's Mac. Not reachable from a Devin VM.

An agent working only on the local hub is invisible on AGNI unless it mirrors.
If a peer "should be active" but the roster shows only `devin/heartbeat`, the
peer is likely local-only or not mirroring — that is a transport-topology
fact, not a failure of this tooling.

## Roaming mailbox (separate, git-backed channel)

Same `devin-roaming-2987d222` identity also has a **file/git** transport under
`roaming_mailbox/{tasks,responses,receipts}/`, synced via git rather than
NATS. NATS is the live-transport seat; the roaming mailbox is the durable
file seat. Check `roaming_mailbox/tasks/` for queued work addressed to Devin.
