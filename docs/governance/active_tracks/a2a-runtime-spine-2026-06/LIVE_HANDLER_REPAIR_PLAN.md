# A2A Live Handler Repair Plan

Status: diagnostic, non-mutating.

This page owns the bridge from red A2A/NATS evidence to live-handler repair.
The repair-plan tool joins two existing receipts:

- `reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json`

Command:

```bash
python3 scripts/runtime/a2a_live_handler_repair_plan.py --write --json
```

Current receipts:

- `reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_APPLIED.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_POST_QWEN_APPLIED.json`
- `reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json`

## Current Finding

The current repair-plan receipt is `READY_TO_MUTATE`.

It records:

- Zero failing A2A/NATS-like LaunchAgents after stale plist quarantine.
- Zero unsafe AGNI delivery gaps after post-Qwen reset.
- Two missing reviewer records that still block production quorum:
  - `fable_composer_inbox` on `dharma.a2a.fable_composer`, `num_pending=0`,
    missing `fable_composer.json`.
  - `claude_from_hermes` on `dharma.a2a.hermes`, `num_pending=0`, missing
    `hermes_m5.json`.

This proves the remaining production blocker is live-handler ownership and
reviewer quorum, not stale local daemon declarations, NATS storage, or durable
backlog. `READY_TO_MUTATE` means the system is safe to attach or re-solicit
target-owned handlers. It does not mean the target-owned handlers have reviewed
or approved the track.

## Safe Execution Order

The repair-plan receipt defines the next safe order:

1. Back up current LaunchAgent plists and current AGNI consumer info.
2. Decide for each pending consumer whether the target-owned handler exists now
   or whether this is a reset.
3. If resetting, reset consumers with an explicit reset receipt and no peer
   review claim. This was done for both the stale Fable/Hermes quorum messages
   and the later post-Qwen backlog.
4. If repairing handlers, add repo-owned AGNI-aware handlers and rerun the
   daemon audit before loading anything.
5. Attach or re-solicit target-owned handlers only after daemon audit passes and
   delivery gaps are empty.
6. Claim production readiness only after reviewer/domain receipts exist and the
   quorum validator writes `status: READY`.

## Non-Claims

The repair plan is not:

- Production readiness.
- Handler acknowledgement.
- Domain receipt.
- Peer-agent review.
- Evidence that filesystem inbox files were read by a live agent.

It is only the deterministic bridge from diagnosis to a safe operational
change.
