# NATS And A2A Inbox Drain/Reset Runbook

Role: operator runbook for subtrack `03-inbox-drain-reset-and-retention`.

This runbook exists because the operator requested a clean A2A/NATS start. The
reset must be backed up and receipted. A raw purge is not acceptable because it
would destroy the proof needed to know what changed.

## Preconditions

1. Work in a clean repo worktree.
2. Run `make onboard` and record the worktree/branch/HEAD.
3. Snapshot broker state:
   - `nats --context agni-wss stream info DHARMA_A2A --json`
   - `nats --context agni-wss stream subjects DHARMA_A2A --sort messages --reverse`
   - `nats --context agni-wss consumer ls DHARMA_A2A`
   - `nats stream info DHARMA_FLEET --json`
4. Snapshot filesystem inbox counts under `~/.dharma/a2a_bus/inboxes/`.
5. Write the snapshot to `reports/a2a/nats_reset/<date>/BASELINE.*`.

## Safe Broker Reset Shape

AGNI `DHARMA_A2A` currently has unbounded retention. The first production action
is to add limits before purging. The recommended target is inherited from the
existing retention proposal:

```bash
nats stream edit DHARMA_A2A \
  --max-age=72h \
  --max-msgs-per-subject=10000 \
  --max-bytes=268435456 \
  --discard=old
```

Then purge only the known runaway subjects, keeping a recent window:

```bash
nats stream purge DHARMA_A2A --subject dharma.a2a.devin --keep 1000
nats stream purge DHARMA_A2A --subject dharma.a2a.fleet --keep 1000
```

If the operator wants a full reset, make a stream backup first and record the
backup path and sha256 manifest in the receipt:

```bash
nats --context agni-wss stream backup DHARMA_A2A /path/to/backup
```

If broker-native backup fails, a server-side JetStream directory snapshot may be
used only as an explicitly labeled fallback. It is evidence-preserving but
weaker than `nats stream backup` because it is taken while `nats-server` is
running. The manifest must say so directly.

## Safe Filesystem Inbox Reset Shape

Do not delete files in place. Move stale inbox contents to a dated quarantine
root first:

```text
~/.dharma/a2a_bus/quarantine/inboxes/YYYY-MM-DDTHHMMSSZ/
```

Leave one `README.md` in each drained old inbox explaining:

- where the messages were moved;
- when the drain happened;
- which receipt proves it;
- which new route owns future messages.

Directed messages less than 24 hours old should be reviewed before quarantine
unless the operator explicitly declares them irrelevant for this reset.

The quarantine tool writes receipts for both dry-run and apply modes. Treat a
dry-run receipt as evidence of observed candidates only; it does not prove that
the filesystem inbox was drained. Treat an apply receipt as a move receipt, not
as proof that the upstream broadcast source has been disabled.

After each quarantine pass, run the legacy broadcast guard:

```bash
python3 scripts/runtime/a2a_file_bus_guard.py --json --check
```

This guard fails when one `to: all` payload is mirrored into many filesystem
inboxes. That pattern is broadcast amplification, not many independent live
agent tasks.

Current repeated-source witness: the 2026-06-13 fourth pass moved 380 Hermes
`to: all` alert-router / dharma-bridge files from 76 inboxes. Receipt:
`reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json`.
Follow-up dry-run receipt
`reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json`
records `candidate_count: 0`. If this guard fails again, assume the legacy
Hermes file-bus route has repopulated the mirror until proven otherwise.

## After Reset Verification

Consumer-inbox reset is complete when all active durable consumers have:

- `deliver_policy=new`;
- explicit ack;
- bounded redelivery such as `max_deliver=5`;
- `num_pending=0`;
- a before/after JSON receipt under `reports/a2a/nats_reset/YYYY-MM-DD/`.

Full broker reset is not complete until all of these are true:

- AGNI `DHARMA_A2A` has bounded retention.
- Runaway subject counts are reduced to the agreed keep window.
- No active durable consumer has multi-million unprocessed backlog.
- Local and AGNI routing are either bridged or intentionally separated in the
  active-track docs.
- Production-intended sends use `--require-broker-scope agni` or an equivalent
  receipt field, so the local broker cannot be mistaken for AGNI.
- AGNI production-intended sends use `--nats-context agni-wss` or an equivalent
  governed context route so secrets stay inside the NATS context and receipts
  still carry `broker_scope: agni`.
- A test send to `--route agent-inbox` reaches at least `HANDLER_ACKED`.
- A target-owned reply artifact can be captured as `DOMAIN_RECEIPTED`.
- The Python runtime environment declares `nats-py`, because the bridge, domain
  reply worker, and reply capture verifier use the NATS Python client.
- If the drill runs on local `DHARMA_FLEET`, its receipt must say
  `production_broker_claim: false` and must not satisfy the AGNI production
  contact blocker.
- `make hygiene-check` passes.
- `make docops-integrity` passes or reports only known unrelated baseline drift.

## Receipt Requirements

Write final reset evidence under:

```text
reports/a2a/nats_reset/YYYY-MM-DD/
```

Required files:

- `BASELINE.json`
- `BASELINE.md`
- `BACKUP_MANIFEST.json`
- `NATS_CONSUMER_INBOX_RESET_APPLIED.json`
- `A2A_QUORUM_CONSUMER_RESET_DRY_RUN.json`
- `A2A_QUORUM_CONSUMER_RESET_APPLIED.json`
- `A2A_QUORUM_CONSUMER_RESET_*_APPLIED.json` for any later scoped backlog
  resets
- `A2A_LIVE_HANDLER_REPAIR_PLAN.json`
- `DRAIN_APPLIED_RECEIPT.json`
- `AFTER.json`
- `AFTER.md`
- `NATS_COMMON_FAILURES.md`
- `reports/a2a/inbox_quarantine_receipts/*-a2a-inbox-quarantine.json`
- `reports/a2a/hermes_broadcast_guard/YYYY-MM-DD/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json`
- `FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json`
- `FILE_INBOX_QUARANTINE_*_APPLIED.json`
- `routing_scope_receipts/YYYY-MM-DD/AGNI_SCOPE_GUARD_LOCAL_MISMATCH.json`
- `live_contact_drill/YYYY-MM-DD/LOCAL_LIVE_CONTACT_DRILL_RECEIPT.json`
- `live_contact_drill/YYYY-MM-DD/PYTHON_TOOL_LIVE_CONTACT_DRILL_RECEIPT.json`
- `agni_live_contact_drill/YYYY-MM-DD/AGNI_A2A_LIVE_CONTACT_DRILL_RECEIPT.json`

No production-ready claim is allowed without `DRAIN_APPLIED_RECEIPT.json`,
`AFTER.json`, and a collected readiness quorum. `NATS_CONSUMER_INBOX_RESET_APPLIED.json`
may prove inbox reset only.

AGNI note: `dharma.a2a.*` is currently the proven live subject family on
`DHARMA_A2A`. A `dharma.agent.*` drill returned no responders; do not treat
agent-inbox subject support as production-ready on AGNI until the stream
configuration and a receipt prove it.
