# Phantom Acker Investigation — RESOLVED (No Phantom)

**Date:** 2026-06-11 · **Status:** CLOSED — stood down by operator before live probing; no test probes were published.

## Resolution

**There is no phantom acker.** The acks on `dharma.a2a.devin.ack.<packet_id>` with payload
`{"ack":true,"from":"devin-roaming-2987d222"}` are **Devin's own live listener's by-design
ack-on-receipt behavior** — his listener publishes that payload to each packet's `ack_subject`
on receipt. Devin's earlier "received nothing" report was sent at ~01:05Z, **before** the
01:17Z send — a timing mix-up, not a delivery failure.

**Both delivery proofs were genuine.** Sends at stream seqs 8,106,881 and 8,106,884 were
received by Devin with full content; the acks at seqs 8,106,882 and 8,106,885 were his.

## The real topology finding

**Codex publishes to a different broker than Devin listens on.** Codex's sends go to the
local hub (`nats://127.0.0.1:4222`, stream `DHARMA_FLEET`); Devin listens on AGNI
(`wss://157.245.193.15:8443`, stream `DHARMA_A2A`). There is **no bridge** between the two —
which is why codex's sends never reach Devin. The local broker is loopback-only
(`~/.dharma/nats/local-nats.conf`: host 127.0.0.1, no leafnode/gateway stanza), confirming
the two brokers are fully disconnected.

## Verified facts from the hunt (before stand-down)

1. **`scripts/runtime/a2a_send.py` does NOT self-ack.** Read end-to-end: it only
   *subscribes* to `ack_subject`/`reply_subject` (lines 138–139) and waits; it never
   publishes to either. `DEVIN_CONSUMED` status can only come from an external publisher.
   (Minor robustness note: its `on_ack` callback accepts *any* payload on the ack subject
   without sender verification — fine today, but worth knowing.)
2. **No code on this Mac constructs the ack payload.** Repo-wide and `~/.dharma`-wide
   searches for `{"ack": true...}` / `devin-roaming-2987d222` found only logs, receipts,
   and handoff docs — no publisher code. Consistent with the acker being Devin's remote listener.
3. **AGNI `DHARMA_A2A` consumers (read-only `nats --context agni-wss consumer ls`):**
   10 durable consumers (`claude_from_devin`, `devin_inbox`, `merge_master_mike_*`, etc.).
   `claude_from_devin` and `merge_master_mike_fleet` each show **~4.05M unprocessed** messages
   and "Last Delivery: never" — dead/abandoned consumers accumulating backlog; candidates for cleanup.

## Incidental breakage found (worth fixing)

- **`com.dhyana.nats-a2a-bridge` (launchd, KeepAlive=true) is crash-looping:** it runs
  `python -m dharma_swarm.operator_core.nats_a2a_bridge --bridge` but that module no longer
  exists in this worktree (`No module named ...` repeating in `~/.dharma/nats/bridge.err.log`).
  It previously bridged `dharma.agent.*.inbox` subjects to `~/.dharma/a2a_bus/inboxes/`.
- **`com.dhyana.a2a-core-contact` (launchd, every 300s)** references
  `scripts/runtime/a2a_core_contact.py`, which also does not exist in this worktree (exit status 2).
- Track-owned surfaces `dharma_swarm/a2a/a2a_nats_contact.py` and `a2a_core_contact.py`
  (per ACTIVE_TRACK `runtime-truth-nats-2026-06`) are not present in this checkout; only
  `dharma_swarm/a2a/nats/agni-ws-ca.pem` exists.

## Recommendation

1. No fix needed for the "phantom" — it was Devin's listener working as designed.
2. To make codex→Devin delivery work, route codex sends to the AGNI broker (agni-wss context /
   `DHARMA_A2A`) or stand up an explicit local↔AGNI bridge — currently none exists.
3. Repair or unload the two broken launchd jobs (`com.dhyana.nats-a2a-bridge`,
   `com.dhyana.a2a-core-contact`) so they stop crash-looping.
4. Consider pruning the dead AGNI consumers with multi-million unprocessed backlogs.
