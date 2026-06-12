# NATS/A2A Common Failure Modes

Date: 2026-06-13 JST
Worktree: `/Users/dhyana/dharma_swarm_a2a_active`
Branch: `codex/a2a-active-track-20260613`
Track: `runtime-truth-nats-2026-06` / `docs/governance/active_tracks/a2a-runtime-spine-2026-06/`

This receipt summarizes the recurring A2A/NATS problems found in recent handoffs,
fleet captures, reset receipts, and local identity state. It is not a production
readiness claim.

## 72-Hour Interaction Counts

Machine-readable receipt:
`reports/a2a/nats_reset/2026-06-13/NATS_INTERACTION_HISTORY_72H.json`.

- Send receipts scanned: 45. Statuses: `PUBLISH_ACKED=28`,
  `HERMES_M5_CONSUMED=7`, `PUBLISH_FAILED=6`, `DEVIN_CONSUMED=3`,
  `NATS_CLIENT_MISSING=1`.
- Contact tiers: `PUBLISH_ACCEPTED=18`, `JETSTREAM_PUB_ACK=13`,
  `HANDLER_ACKED=7`, `NO_CONTACT=2`, with 5 unknown/older receipts.
- Endpoint split: 33 receipts used local `nats://127.0.0.1:4222`; 12 used AGNI
  `wss://157.245.193.15:8443`.
- Reply receipts scanned: 11. `NO_REPLY=10`; `DOMAIN_RECEIPTED=1`.
- Domain-reply receipts scanned: 3. `ARTIFACT_INVALID=2`;
  `DOMAIN_REPLY_PUBLISHED=1`; semantic reply claim was false in all 3.
- Hermes pending alerts in the 72-hour window: 138 files. Sources:
  `autonomous_controller=138`, `cron_health=120`, `nikki=6`.
- A2A fleet logs in the 72-hour window: 288 files, 20,858,758 bytes scanned.
  Dominant patterns: `dark_or_dormant=80`, `alert_router_payload=28`,
  `broadcast_to_all=22`, `sample_broadcast=20`, `unprocessed=11`.

## Why `fable_composer` Was Checked

Checking `~/.dharma/a2a_bus/inboxes/fable_composer/` is locally understandable
because `fable_composer` has a filesystem inbox declared in
`/Users/dhyana/.dharma/a2a_bus/state/fable_composer.json`, and the address
`a42b313fc7e15cba` resolves to that seat in
`/Users/dhyana/.dharma/agents/fable_composer/identity.json`.

It is not, by itself, a production contact path. The same state file says
`wake_loop_active: false` and `process_running: false`; liveness is
session-borne. Early in the audit, the declared AGNI durable consumer was
`fable_5_cursor_inbox`, filtered to `dharma.a2a.fable_5_cursor`, not
`fable_composer`; the later provisioning receipt now adds
`fable_composer_inbox` filtered to `dharma.a2a.fable_composer`.

The repeated file-inbox repopulations after quarantine were Hermes broadcast
payloads addressed to `all`, mirrored into 76 inboxes. The second quarantine
moved 152 files, exactly two per inbox. The third quarantine moved one later
Hermes alert, `97ae3152f3a94abf.json`, copied into each inbox after
`~/.hermes/scripts/alert_router.py` queued
`~/.hermes/comms/pending/alerts_2026-06-13_0045.json` and called
`~/.hermes/scripts/a2a_bus.py broadcast`. A fourth observed pass found five
more Hermes `to: all` payloads, `4fd26831cb2ffdca`, `5425adfa653fab9e`,
`61646cfaa9b87d11`, `6769b6ce24c32471`, and `b15cef2a14366376`, copied into
76 inboxes for 380 mirrored files. Receipt
`reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json`
moved all 380 files to
`/Users/dhyana/.dharma/a2a_bus/quarantine/inboxes/20260612T182947Z`. A
follow-up dry-run receipt,
`reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json`,
records `candidate_count: 0`; the current file-bus broadcast guard is passing:
`scripts/runtime/a2a_file_bus_guard.py --json --check`.

A later live check found the same failure class from a different Hermes script:
`~/.hermes/comms/DISABLE_A2A_BROADCAST` existed at 2026-06-13 04:27:47 JST,
but `~/.hermes/scripts/dharma_bridge.py` still called
`~/.hermes/scripts/a2a_bus.py broadcast`. At 2026-06-13 05:23:15 JST it copied
message `1fd00b161ad1c2ee.json` from `hermes-m5` to `all` into 76 inboxes,
including `fable_composer`. That is why checking the `fable_composer`
filesystem inbox was understandable; the content was still not a target-owned
Fable response or NATS production contact.

## Recurring Failure Modes

1. Publish ack is confused with agent contact.

   Evidence: `reports/handoffs/HUB_INBOUND_2026-06-12.md` records
   JETSTREAM_PUB_ACK receipts while also noting that Codex had no durable
   consumer on `dharma.a2a.codex`. Publish acceptance proves broker persistence,
   not target wake, target read, semantic reply, or work completion.

2. Durable consumers exist but are not drained.

   Evidence: `reports/handoffs/MIKE_INBOX_DIGEST_2026-06-12.md` shows
   `merge_master_mike_inbox` was dark for 11 days and accumulated 30 messages.
   The reset baseline shows `claude_from_devin` and `merge_master_mike_fleet`
   each with about 4.05M unprocessed messages and last delivery `never`.

3. AGNI retention was unbounded.

   Evidence: `reports/a2a/nats_reset/2026-06-13/BASELINE.md` records
   `DHARMA_A2A` at 8,106,912 messages and 1,427,133,017 bytes, with unlimited
   `max_msgs`, `max_bytes`, `max_age`, and `max_msgs_per_subject`. The top two
   subjects, `dharma.a2a.fleet` and `dharma.a2a.devin`, account for nearly all
   retained messages. Follow-up receipt `DRAIN_APPLIED_RECEIPT.json` records
   bounded retention and a 43-message post-drain state.

4. Local broker and AGNI broker are split.

   Evidence: `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md` found no
   phantom acker. Devin's ack path was real, but Codex publishes to local
   `DHARMA_FLEET` while Devin listens on AGNI `DHARMA_A2A`; there is no bridge
   between them.

5. File inboxes are still a noisy mirror/fallback surface.

   Evidence: the first quarantine moved 34,717 files. The second quarantine
   moved 152 files after Hermes mirrored two `to: all` payloads into every inbox.
   The third quarantine moved 76 files after a single Hermes alert-router payload
   was mirrored once into each inbox. The fourth quarantine moved 380 files
   after five Hermes alert-router / dharma-bridge payloads were mirrored into
   76 inboxes. `~/.dharma/a2a_bus/inboxes/fable_composer/README.md` now states
   that the filesystem inbox is a dock/mirror surface and not proof of live
   reachability. A later pass found three more mirrored Hermes payload groups
   plus one extra file, then moved 229 files to quarantine after disabling the
   alert-router broadcast source.

6. Identity and route names were not yet unified.

   Evidence: `fable_composer` is the master-composer seat with address
   `a42b313fc7e15cba`, but the declared AGNI durable consumer was only
   `fable_5_cursor_inbox`. This created a real routing ambiguity: local identity
   could exist without a production NATS consumer. Follow-up receipt
   `FABLE_COMPOSER_CONSUMER_PROVISIONED.json` now records a fresh
   `fable_composer_inbox` durable consumer with `deliver_policy=new` and
   `num_pending=0`.

7. Permission and launchd drift create false negatives and stale daemons.

   Evidence: `reports/handoffs/MIKE_INBOX_DIGEST_2026-06-12.md` cites repeated
   Devin reports of "JetStream durable subscribe denied (permissions)".
   `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md` also found launchd
   jobs referencing missing bridge/contact modules.

8. Long-running daemon declarations can rot independently of repo code.

   Evidence: `reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json`
   initially reported `FAIL`. Five A2A/NATS-like LaunchAgents pointed at
   missing modules, missing scripts, local broker scope where AGNI was expected,
   or crash-looping imports. Receipt
   `reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json`
   moved those five stale plist declarations to
   `/Users/dhyana/.dharma/a2a_bus/quarantine/launch_agents/20260612T184702Z`
   and left `/Users/dhyana/Library/LaunchAgents/DHARMA_A2A_RUNTIME_SPINE_README.md`.
   The refreshed daemon audit now reports top-level `PASS`. This cleanup removes
   false local daemon surfaces; it does not create target-owned Fable/Hermes
   handlers.

9. A stored AGNI message still needs a live target-owned handler.

   Evidence:
   `reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json`
   currently reports `READY_TO_MUTATE`. It joins the daemon audit with
   `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json`
   and separates delivery gaps from missing reviewer records. Before reset they were pending
   durable messages (`fable_composer_inbox` pending 2 and `claude_from_hermes`
   pending 1). After explicit reset, both consumers were `num_pending=0`.
   Fresh post-quarantine solicitation then added one pending message each; the
   post-Qwen reset cleared those consumers back to `num_pending=0` with
   `production_claim=false`. The current delivery status is
   `CONSUMER_EMPTY_NO_DELIVERY` for `fable_composer` and `hermes_m5`. These are
   not peer replies; quorum still requires target-owned handler receipts.

## What Has Improved

- All 11 AGNI durable consumers were reset to `deliver_policy=new`, explicit
  ack, `max_deliver=5`, and `num_pending=0`. Receipt:
  `reports/a2a/nats_reset/2026-06-13/NATS_CONSUMER_INBOX_RESET_APPLIED.json`.
- File inbox quarantine now leaves README pointers and has a verifier:
  `scripts/runtime/a2a_inbox_quarantine.py --include-recent --json`.
- The active-track subtree now names five bounded subtracks and separates
  publish ack, handler ack, domain receipt, semantic reply, and completion.
- `fable_composer` now has an AGNI durable pull consumer filtered to
  `dharma.a2a.fable_composer`, so the local seat no longer depends only on the
  filesystem inbox as its declared route.
- AGNI `DHARMA_A2A` now has bounded retention (`72h`, 256MB,
  10,000 messages per subject) and has been reduced from 8,106,912 retained
  messages to 43.
- `scripts/runtime/a2a_file_bus_guard.py --json --check` now fails if a legacy
  `to: all` filesystem broadcast is mirrored into many inboxes and would be
  mistaken for many independent live tasks.
- The latest file-inbox cleanup receipt moved 380 mirrored Hermes payloads and
  left a zero-candidate dry-run receipt. Current guard state is clean, but this
  is a cleanup baseline, not a fix for the upstream broadcast source.
- `scripts/runtime/a2a_hermes_broadcast_guard.py --apply --write --json`
  patched `~/.hermes/scripts/alert_router.py` with a disable guard and wrote
  `~/.hermes/comms/DISABLE_A2A_BROADCAST`. Receipt:
  `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json`.
- The post-disable quarantine moved 229 already-mirrored files to
  `/Users/dhyana/.dharma/a2a_bus/quarantine/inboxes/20260612T192816Z`. Receipt:
  `reports/a2a/inbox_quarantine_receipts/20260612T192816Z-a2a-inbox-quarantine.json`.
- `reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json`
  now records `status: PASS`, `entry_count: 0`, and
  `broadcast_candidate_count: 0`.
- `scripts/runtime/a2a_hermes_broadcast_guard.py --apply --write --json` now
  also patches `~/.hermes/scripts/dharma_bridge.py`, so both known Hermes
  legacy file-bus broadcasters honor the same disable flag. Receipt:
  `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_LEGACY_BROADCAST_GUARD_APPLIED.json`.
- `scripts/runtime/a2a_inbox_quarantine.py` now supports an exact
  `--filename` filter. The post-bridge pass quarantined only
  `1fd00b161ad1c2ee.json` from 76 inboxes and left the unrelated
  `opus_composer/revenue_wedge_transition_20260612T200519Z.json` in place.
  Receipt:
  `reports/a2a/inbox_quarantine_receipts/20260612T203408Z-a2a-inbox-quarantine.json`.
- `reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_DHARMA_BRIDGE_DISABLE.json`
  records the current file-bus guard state: `status: PASS`,
  `broadcast_candidate_count: 0`, and one remaining non-broadcast inbox entry.
- `scripts/runtime/a2a_daemon_wiring_audit.py --write --json` records whether
  declared A2A/NATS LaunchAgents point at live targets and the expected broker
  scope. Its first receipt was red; after stale LaunchAgent quarantine, the
  refreshed receipt is top-level `PASS`.
- `scripts/runtime/a2a_launchagent_quarantine.py --apply --json` now provides a
  reversible, receipted cleanup path for broken launchd declarations. The first
  applied receipt moved five stale A2A/NATS plist files out of
  `~/Library/LaunchAgents`.
- `scripts/runtime/a2a_live_handler_repair_plan.py --write --json` joins daemon
  wiring and quorum delivery state into one non-mutating repair plan. The latest
  receipt is `READY_TO_MUTATE`: no failing daemons and no delivery gaps, with
  two missing reviewer records still blocking production quorum.
- `scripts/runtime/a2a_quorum_blocker_status.py --write --write-latest --json`
  now classifies stale vs current reviewer red blockers. Latest receipt:
  `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json`.
  It reports 13 reviewer red blockers total: 4 stale/resolved by current
  receipts, 2 partially resolved, and 7 still current.
- `scripts/runtime/a2a_reviewer_route_health.py --write --write-latest --json`
  now classifies missing reviewer records by route health. Latest receipt:
  `reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json`.
  It reports three reviewer records present, with `fable_composer` blocked by
  provider credit on `claude -p` and `hermes_m5` blocked by provider timeout or
  handler stall on `hermes -z`.
- `scripts/runtime/a2a_reset_quorum_consumers.py --apply --write --json` now
  records the explicit reset of stale Fable/Hermes quorum consumers. The receipt
  shows `after_pending_total=0`, `stream_messages_mutated=false`, and
  `production_claim=false`.
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_POST_QWEN_APPLIED.json`
  records the later scoped Fable/Hermes consumer reset after Qwen review was
  added. It also shows `after_pending_total=0`, `stream_messages_mutated=false`,
  and `production_claim=false`.

## Remaining Production Blockers

- The backup used for the drain is a server-side filesystem tar fallback, not a
  broker-native `nats stream backup`.
- The Hermes alert-router broadcast source is now suppressed by a guarded patch
  and flag file, but it remains an external `~/.hermes` surface. Keep
  `scripts/runtime/a2a_hermes_broadcast_guard.py --check` and
  `scripts/runtime/a2a_file_bus_guard.py --json --check` green before any
  production claim.
- Readiness quorum is collected but not ready. The current aggregate has
  reviewer records for three persistent agent IDs (`codex_composer`,
  `qwen_code`, `gemini_reviewer`) and three model families (`openai`,
  `alibaba`, `google`), but median readiness is below 80 and all three
  reviewers report red blockers. The blocker-status receipt narrows the
  actionable current blockers to missing target-owned Fable/Hermes receipts,
  median readiness below 80, and stale reviewer records that must be refreshed
  rather than edited.
- Declared local daemon wiring is clean after quarantine, but this is cleanup
  evidence only. It does not prove target-owned Fable/Hermes handler delivery.
- Production quorum messages for Fable and Hermes were reset as stale inbox
  state, not peer evidence. The current consumers are empty, so the remaining
  blocker is not backlog; it is missing target-owned reviewer/domain receipts.
  Fable, Hermes, and Devin reviewer attempts are recorded under
  `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/` and
  currently failed due provider credit, timeout, or quota limits.
- Route health is now explicit: Fable has a reachable `claude` command and a
  registered identity at address `a42b313fc7e15cba`, but the documented
  headless route most recently failed with `PROVIDER_CREDIT_EXHAUSTED`. Hermes
  has an operational state file and reachable `hermes` command, but the latest
  target-owned attempt timed out before a reviewer record was written.
  Latest Hermes timeout receipt:
  `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T202230Z-hermes_m5-hermes_cli_timeout.json`.

## Immediate Invariants To Add

1. A direct agent route is production-valid only if its identity has a durable
   AGNI consumer or a documented bridge path.
2. `PUBLISH_ACCEPTED` must not satisfy any criterion named live contact,
   collaboration, completion, or production readiness.
3. `DHARMA_A2A` cannot be production-ready while any retention limit is unlimited.
4. File-inbox mirror writes to `all` must not create unread work claims for each
   mirrored recipient.
5. Every active A2A target must have a last-drain receipt newer than the
   configured freshness window.
6. Legacy file-bus broadcasts must be either rerouted through AGNI as typed
   telemetry or explicitly suppressed from per-agent inboxes.
7. A2A/NATS LaunchAgents must point at existing modules/scripts and the intended
   broker scope before any durable-consumer route can satisfy production
   readiness.
8. A pending production-quorum durable consumer must be resolved as either
   target-owned handler delivery or explicit reset; it must not remain a
   publish-only artifact while readiness is claimed.
