# DHARMA_A2A Stream Retention Proposal (recommend-only)

- **Role:** working_plan (recommendation only — broker config changes go through the operator)
- **Date:** 2026-06-11
- **Author:** devin (`devin-roaming-2987d222`), janitor lane
- **Prompted by:** hub→devin A2A packet (stream `DHARMA_A2A` seq 8,106,881 / 8,106,884), hygiene finding (a)
- **Subordinate to:** `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` (codex-owned; this plan proposes operator actions, it does not amend the spec)

## Problem

Per the hub's measurement, `dharma.a2a.devin` and `dharma.a2a.fleet` each hold
**~4M messages (~1.3 GiB)** on the AGNI stream `DHARMA_A2A`, which currently has
**unlimited retention**. Most of this is runaway-publisher residue, not live
coordination traffic. Risks: unbounded disk growth on AGNI, slow consumer
catch-up (a recreated `devin_inbox` consumer starting from seq 1 would replay
millions of junk messages), and stream seqs in the millions making manual
inspection impractical.

## Recommended retention limits

Apply per-stream limits on `DHARMA_A2A` (and mirror on the local hub's
`DHARMA_FLEET` for symmetry):

| Setting | Recommended value | Rationale |
|---|---|---|
| `max_age` | `72h` | A2A packets are live coordination traffic; durable artifacts already land in git (`inter_agent/*/outbound/` + PRs). 3 days covers weekend gaps. |
| `max_msgs_per_subject` | `10000` | Caps any future runaway publisher at a bounded backlog per subject while leaving ample headroom for real traffic (current real traffic is tens of messages/day). |
| `max_bytes` | `256MiB` | Hard ceiling on disk usage regardless of message count. |
| `discard` | `old` | Drop oldest first when limits hit — newest packets are the live ones. |

Operator command sketch (NATS CLI, run on AGNI with admin creds):

```bash
nats stream edit DHARMA_A2A \
  --max-age=72h \
  --max-msgs-per-subject=10000 \
  --max-bytes=268435456 \
  --discard=old
```

## One-time purge plan for the residue

1. **Snapshot first:** `nats stream backup DHARMA_A2A ./dharma_a2a_backup_2026-06-11` (cheap insurance; delete after 1 week).
2. **Recreate `devin_inbox` before purging** with filter `dharma.a2a.devin` and `--opt-start-seq 8106880` (already planned hub-side) so the consumer never depends on the residue.
3. **Purge per subject, keeping the recent window:**
   ```bash
   nats stream purge DHARMA_A2A --subject dharma.a2a.devin --keep 1000
   nats stream purge DHARMA_A2A --subject dharma.a2a.fleet --keep 1000
   ```
4. Verify: `nats stream info DHARMA_A2A` shows messages in the thousands and bytes in the MiB range; live send/receive roundtrip (`scripts/runtime/a2a_send.py --to devin --wait 30`) still returns `DEVIN_CONSUMED`/`DEVIN_REPLIED` against a live listener.

## Guardrail against future runaway publishers

- Senders should use `scripts/runtime/a2a_send.py` (or equivalent) which publishes one packet per invocation with a receipt — not loops without backoff.
- Optional follow-up (separate decision): per-subject rate alerting on AGNI (`nats server report jetstream`) in the hub's health sweep.

## Explicitly out of scope

- No broker config change is made by this PR — operator executes the commands above.
- No change to `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`, `dharma_swarm/a2a/a2a_nats_contact.py`, or `a2a_core_contact.py` (codex-owned surfaces).
- Consumer allow-list fixes for the devin NATS user are tracked hub-side (separate packet).
