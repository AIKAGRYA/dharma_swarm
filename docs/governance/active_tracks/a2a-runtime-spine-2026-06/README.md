# A2A Runtime Spine Track

Status: active-track subtree for `runtime-truth-nats-2026-06`.

This subtree is the findable home for the A2A/NATS seam while the repo moves
from "messages can publish" to production-grade agent contact. It consolidates
NATS transport, A2A protocol semantics, inbox bridges, reply/domain receipts,
graph/shared-state projections, and long-running agent workflows into one
governed build lane.

## Why This Exists

The current repo already contains strong pieces:

- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- `scripts/runtime/a2a_send.py`
- `scripts/runtime/a2a_inbox_bridge.py`
- `scripts/runtime/a2a_reply_capture.py`
- `scripts/runtime/a2a_domain_reply_worker.py`
- `scripts/runtime/a2a_prod_readiness_quorum.py`
- `scripts/runtime/a2a_prod_readiness_solicit.py`
- `scripts/runtime/a2a_reviewer_route_health.py`
- `dharma_swarm/a2a/nats_transport.py`
- `tests/test_a2a_send.py`
- `tests/test_a2a_inbox_bridge.py`
- `tests/test_a2a_reply_capture.py`
- `tests/test_nats_live_contact.py`

The problem is composition. A publish ack is still too easy to confuse with
agent contact; AGNI and the local broker have diverged; file inboxes remain
useful but ambiguous; graph/shared-state surfaces are not yet part of the
operator contact contract.

## Five-Level Operating Model

1. Transport: NATS JetStream streams, subjects, durable consumers, retention,
   deduplication, and bridge health.
2. Protocol: A2A agent cards, tasks, messages, artifacts, authentication, and
   external gateway boundaries.
3. Evidence: publish ack, handler ack, domain receipt, semantic reply, and
   completion remain separate states.
4. Shared State: orientation graph, truth graph, runtime packets, vector memory,
   and board projections are read models over owners, not authority.
5. Production Governance: active-track criteria, quorum readiness, drain
   receipts, hygiene gates, docops, and long-running mission receipts.

## Subtrack Map

Machine-readable subtracks live in `SUBTRACKS.yaml`.

- `01-canonical-nats-topology`
- `02-hot-contact-ack-and-domain-receipts`
- `03-inbox-drain-reset-and-retention`
- `04-shared-state-graph-and-vector-memory`
- `05-persistent-agent-workflow-and-quorum`

Each subtrack has at most three seams. If more are needed, split the work into a
new active track rather than hiding unbounded complexity under this one.

## Track Files

- `SUBTRACKS.yaml` - machine-readable subtrack map.
- `CONSOLIDATION_MAP.md` - existing specs, reports, scripts, tests, and branches
  folded into this track.
- `NATS_DRAIN_AND_RESET_RUNBOOK.md` - reversible drain/reset process for brokers
  and filesystem inboxes.
- `DAEMON_WIRING_AUDIT.md` - LaunchAgent, broker-scope, and stale-handler
  witness for long-running A2A/NATS daemons.
- `LIVE_HANDLER_REPAIR_PLAN.md` - non-mutating repair plan that joins daemon
  wiring failures with pending AGNI durable-consumer delivery gaps.
- `PRODUCTION_READINESS_QUORUM.md` - two persistent-agent and three-model
  readiness consensus rule, plus blocker-status refresh rules.
- `WORKFLOW.md` - ds-goal, long harness, and Codex loop operating workflow.

## External Standards Anchors

- NATS JetStream streams support retention limits, discard policy,
  deduplication via `Nats-Msg-Id`, and per-subject limits:
  <https://docs.nats.io/nats-concepts/jetstream/streams>
- NATS consumers support explicit ack, redelivery, and `MaxDeliver`/backoff:
  <https://docs.nats.io/nats-concepts/jetstream/consumers>
- A2A defines agent cards, messages, tasks, artifacts, and security semantics:
  <https://a2a-protocol.org/latest/specification/>
- OpenTelemetry messaging spans define message ids, operation names, system
  names, producer/consumer spans, and trace context patterns:
  <https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/>

## Current Baseline

The first baseline receipt is:

- `reports/a2a/nats_reset/2026-06-13/BASELINE.md`
- `reports/a2a/nats_reset/2026-06-13/BASELINE.json`
- `reports/a2a/nats_reset/2026-06-13/BACKUP_MANIFEST.json`
- `reports/a2a/nats_reset/2026-06-13/NATS_CONSUMER_INBOX_RESET_APPLIED.json`
- `reports/a2a/nats_reset/2026-06-13/AFTER.json`
- `reports/a2a/nats_reset/2026-06-13/FILE_INBOX_QUARANTINE_SECOND_PASS_APPLIED.json`
- `reports/a2a/nats_reset/2026-06-13/FILE_INBOX_QUARANTINE_THIRD_PASS_APPLIED.json`
- `reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json`
- `reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json`
- `reports/a2a/inbox_quarantine_receipts/20260612T192811Z-a2a-inbox-quarantine.json`
- `reports/a2a/inbox_quarantine_receipts/20260612T192816Z-a2a-inbox-quarantine.json`
- `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_DRY_RUN.json`
- `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json`
- `reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json`
- `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_LEGACY_BROADCAST_GUARD_APPLIED.json`
- `reports/a2a/inbox_quarantine_receipts/20260612T203408Z-a2a-inbox-quarantine.json`
- `reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_DHARMA_BRIDGE_DISABLE.json`
- `reports/a2a/nats_reset/2026-06-13/NATS_COMMON_FAILURES.md`
- `reports/a2a/nats_reset/2026-06-13/FABLE_COMPOSER_CONSUMER_PROVISIONED.json`
- `reports/a2a/nats_reset/2026-06-13/DRAIN_APPLIED_RECEIPT.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json`
- `reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_DRY_RUN.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_APPLIED.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_POST_QWEN_DRY_RUN.json`
- `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_POST_QWEN_APPLIED.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/SOLICITATION_RECEIPT.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/FABLE_COMPOSER_SOLICITATION_NATS_SEND.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/HERMES_M5_SOLICITATION_NATS_SEND.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/codex_composer.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/qwen_code.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/gemini_reviewer.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T190713Z-fable_composer-claude_cli_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T195938Z-fable_composer-claude_cli_credit_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T201843Z-fable_composer-claude_cli_smoke_credit_failed.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T190826Z-hermes_m5-hermes_cli_timeout.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T202230Z-hermes_m5-hermes_cli_timeout.json`
- `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/20260612T191130Z-devin-roaming-2987d222-devin_cli_quota_failed.json`
- `reports/a2a/advisory_requests/2026-06-13/FABLE_COMPOSER_ACTIVE_TRACK_ARCHITECTURE_REVIEW.json`
- `reports/a2a/advisory_requests/2026-06-13/FABLE_COMPOSER_ACTIVE_TRACK_ARCHITECTURE_REVIEW_NATS_SEND.json`
- `reports/a2a/routing_scope_receipts/2026-06-13/AGNI_SCOPE_GUARD_LOCAL_MISMATCH.json`
- `reports/a2a/live_contact_drill/2026-06-13/LOCAL_LIVE_CONTACT_DRILL_RECEIPT.json`
- `reports/a2a/live_contact_drill/2026-06-13/PYTHON_TOOL_LIVE_CONTACT_DRILL_RECEIPT.json`
- `reports/a2a/agni_live_contact_drill/2026-06-13/AGNI_A2A_LIVE_CONTACT_DRILL_RECEIPT.json`
- `reports/a2a/prod_readiness_quorum/latest.json` (currently useful only as a
  `NOT_READY` receipt; it must contain `"status": "READY"` before production
  readiness can pass)
- `reports/a2a/prod_readiness_quorum/latest_blocker_status.json` (currently
  `BLOCKED_BY_CURRENT_EVIDENCE`; it classifies stale vs current reviewer red
  blockers but does not clear quorum)
- `reports/a2a/prod_readiness_quorum/latest_route_health.json` (currently
  `ROUTE_HEALTH_BLOCKED`; it records Fable as provider-credit blocked and
  Hermes as provider-timeout/handler-stalled, without substituting for review)

At baseline, AGNI `DHARMA_A2A` was not production-clean: it had unbounded
retention and 8.1M retained messages, almost all on `dharma.a2a.fleet` and
`dharma.a2a.devin`. Local `DHARMA_FLEET` was small and bounded.

After the first reset pass, all 11 AGNI durable consumers were deleted and
recreated with `deliver_policy=new`, explicit ack, `max_deliver=5`, and
`num_pending=0`. That proved consumer inbox reset, not stream cleanup.

After the second filesystem quarantine pass, Hermes broadcast mirror traffic was
confirmed as the source of fresh file-inbox noise: two `to: all` payloads were
copied into 76 inboxes and then quarantined. The post-pass dry run returned
`candidate_count: 0`.

After the third filesystem quarantine pass, the source was traced more tightly:
`~/.hermes/scripts/alert_router.py` routed a Slack alert to
`~/.hermes/comms/pending/alerts_2026-06-13_0045.json`, then called
`~/.hermes/scripts/a2a_bus.py broadcast`. That legacy script copies `to: all`
messages into every filesystem inbox. The repo now has
`scripts/runtime/a2a_file_bus_guard.py --json --check`, which passes after the
third quarantine and fails if the amplified broadcast pattern reappears.

After the fourth filesystem quarantine pass, the same class of legacy mirror
noise reappeared at larger volume: five Hermes `to: all` alert-router /
dharma-bridge payloads were copied into 76 inboxes, producing 380 files. The
apply receipt
`reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json`
moved them to
`/Users/dhyana/.dharma/a2a_bus/quarantine/inboxes/20260612T182947Z`; the
follow-up dry-run receipt
`reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json`
records `candidate_count: 0`. This proves the mirror is currently clean, not
that Hermes file-bus broadcast has been retired.

After the Hermes broadcast-guard pass, the upstream source was disabled without
deleting the old script. `scripts/runtime/a2a_hermes_broadcast_guard.py` backed
up `~/.hermes/scripts/alert_router.py` to
`~/.dharma/a2a_bus/quarantine/hermes_broadcast_guard/2026-06-12T192747Z0000/alert_router.py`,
inserted a guard in `broadcast_a2a`, and wrote
`~/.hermes/comms/DISABLE_A2A_BROADCAST` as the operator-readable explanation
and flag. A final quarantine moved 229 already-mirrored inbox files, and
`reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json`
records `status: PASS` with zero broadcast candidates.

A later live check found a second Hermes source: `~/.hermes/scripts/dharma_bridge.py`
also called `~/.hermes/scripts/a2a_bus.py broadcast` after the alert-router
guard was already in place. It mirrored Hermes message
`1fd00b161ad1c2ee.json` into 76 inboxes, including `fable_composer`, which is
why checking that filesystem inbox was understandable but not authoritative.
The guard now covers both `alert_router.py` and `dharma_bridge.py`, the live
bridge script was backed up to
`~/.dharma/a2a_bus/quarantine/hermes_broadcast_guard/2026-06-12T203310Z0000/dharma_bridge.py`,
and the exact broadcast filename was quarantined by
`reports/a2a/inbox_quarantine_receipts/20260612T203408Z-a2a-inbox-quarantine.json`.
The follow-up guard receipt
`reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_DHARMA_BRIDGE_DISABLE.json`
records `status: PASS`, with one unrelated direct file left in `opus_composer`.

After the fable-composer provisioning pass, AGNI has a durable
`fable_composer_inbox` pull consumer filtered to `dharma.a2a.fable_composer`,
with `deliver_policy=new`, explicit ack, `max_deliver=5`, and `num_pending=0`.

After the drain/retention pass, AGNI `DHARMA_A2A` has bounded retention
(`max_age=72h`, `max_bytes=268435456`, `max_msgs_per_subject=10000`) and 43
retained messages. The two formerly runaway subjects now retain 15
`dharma.a2a.devin` messages and 9 `dharma.a2a.fleet` messages. The fallback
backup is a server-side filesystem tar, not a broker-native snapshot, because
the broker-native backup command timed out and the AGNI host does not have the
NATS CLI on PATH.

After the quorum-solicitation pass, three reviewer request packets exist for
`codex_composer`, `fable_composer`, and `hermes_m5`. The `fable_composer`
packet was published to AGNI `dharma.a2a.fable_composer` and stored in
`DHARMA_A2A` at stream sequence `8106913`; the `fable_composer_inbox` durable
consumer then showed one unprocessed message. This proves broker storage and
pending delivery only. It does not prove handler ack, semantic reply, or
production readiness.

After the composer-advisory pass, a separate high-level active-track
architecture review request was also published to `dharma.a2a.fable_composer`
and stored in `DHARMA_A2A` at stream sequence `8106914`. The durable consumer
then showed two unprocessed messages. This proves both composer requests are
pending for pull, not that Composer has reviewed or approved them.

After the routing-scope guard pass, `scripts/runtime/a2a_send.py` receipts now
classify the broker as `local`, `agni`, `external`, or `unknown`, and
`--require-broker-scope agni` refuses to publish when the configured endpoint is
the local broker. The first guard receipt shows the current default
`nats://127.0.0.1:4222` was blocked before publish. This proves local-vs-AGNI
discipline only; it does not prove AGNI handler contact.

After the daemon-wiring audit pass, the local LaunchAgent layer is explicitly
witnessed. The first receipt reported `FAIL`: five A2A/NATS-like LaunchAgents
pointed at missing modules, missing scripts, local broker scope where AGNI was
expected, or crash-looping imports. Those five stale plist declarations were
then moved to
`/Users/dhyana/.dharma/a2a_bus/quarantine/launch_agents/20260612T184702Z` by
`reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json`.
The refreshed audit now reports top-level `PASS`. This explains why filesystem
inboxes had remained the visible fallback surface and removes that stale local
daemon noise. It does not prove target-owned Fable/Hermes handler contact.

After the first live-handler repair-plan pass, the diagnosis was joined into one
operator-safe action map: five failing daemon declarations plus two pending
production-quorum delivery gaps (`fable_composer_inbox` pending 2 and
`claude_from_hermes` pending 1). After daemon quarantine and quorum-consumer
reset, the stale messages were cleared as non-peer evidence. Fresh
post-quarantine solicitation briefly left one pending message each for
`fable_composer_inbox` and `claude_from_hermes`; the post-Qwen reset cleared
those consumers back to `num_pending=0` as explicit non-peer evidence. The
latest plan reports `READY_TO_MUTATE`: there are no delivery gaps or failing
daemons, and the remaining work is to attach or re-solicit target-owned
Fable/Hermes handlers so they produce reviewer records. This is not production
readiness.

After the quorum-consumer reset pass, those two stale quorum consumers were
deleted and recreated with `deliver_policy=new`, explicit ack, `max_deliver=5`,
and `num_pending=0`. The stream messages were not purged. This reset proves a
clean inbox baseline only; it is not peer review, handler ack, domain receipt,
or production readiness. The refreshed delivery-status receipt now reports
`CONSUMER_EMPTY_NO_DELIVERY` for Fable and Hermes, which is correct until fresh
target-owned handlers produce reviewer records.

After the local live-contact drill, local `DHARMA_FLEET` proved the complete
mechanical chain: publish, durable pull, handler ack payload, typed domain
receipt publish, reply pull, and both drill consumers drained to zero. The
receipt is `LOCAL_DOMAIN_RECEIPTED` and intentionally says
`production_broker_claim: false`. This proves the mechanism, not production
AGNI contact.

After the Python-tool live-contact drill, `nats-py==2.15.0` is declared in
`pyproject.toml`, and the repo runtime tools themselves completed the local
chain: `a2a_send.py` reached `HANDLER_ACKED`, `a2a_inbox_bridge.py` wrote
`DELIVERED_AND_ACKED`, `a2a_domain_reply_worker.py` published a target-owned
domain receipt, and `a2a_reply_capture.py` recorded `DOMAIN_RECEIPTED`. The
receipt is still local-only and carries `production_broker_claim: false`.

After the AGNI synthetic live-contact drill, `a2a_send.py --nats-context
agni-wss --require-broker-scope agni` published through the governed sender to
`dharma.a2a.codex_agni_drill_20260613`. A fresh AGNI durable consumer pulled
and acked the message, a handler-ack payload was published, a typed domain
receipt was published to the recorded reply subject, and the reply consumer
pulled and acked that domain receipt. Both AGNI drill consumers ended with zero
outstanding acks and zero unprocessed messages. This proves the synthetic AGNI
mechanics, not Fable/Composer review or production quorum.

Topology lesson: the attempted AGNI `dharma.agent.*` drill failed with no
responders. The currently live AGNI stream family for this track is
`dharma.a2a.*`; `dharma.agent.*` needs explicit stream support before it can be
treated as a production route on AGNI.

Quorum-solicitation lesson: the Hermes-model-family request was published to
`dharma.a2a.hermes`, and the matching AGNI durable is currently named
`claude_from_hermes`. Consumer names do not reliably identify ownership; use
`filter_subject` and receipts as authority.

After the quorum-delivery-status pass,
`reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json`
records live read-only AGNI `consumer info` state for reviewer requests. It
shows Codex, Qwen, and Gemini reviewer records are present, while
`fable_composer` and `hermes_m5` are `CONSUMER_EMPTY_NO_DELIVERY`: their
consumers are empty, but no target-owned reviewer record exists. The quorum
aggregate has three persistent agent IDs and three model families, but remains
`NOT_READY` because median readiness is below 80 and all three reviewers
reported red blockers. The receipt is not a production-readiness claim; it only
makes the current quorum and durable state explicit.

After the quorum-blocker-status pass,
`reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json`
classifies old reviewer red blockers against current machine receipts. The
current count is 13 reviewer red blockers: 4 are now stale/resolved by current
receipts, 2 are partially resolved because pending/backlog claims are gone but
target-owned records remain missing, and 7 are still current. The current
production blocker is therefore narrower than the old review text: produce
target-owned `fable_composer.json` and `hermes_m5.json`, then collect fresh
reviewer percentages with no red blockers. The blocker-status receipt is not a
production-readiness claim.

After the route-health pass,
`reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json`
classifies each requested reviewer route. Three records are present. Fable is
blocked by `PROVIDER_CREDIT_EXHAUSTED` on the documented `claude -p` headless
route. Hermes is blocked by `PROVIDER_TIMEOUT` / handler-stalled evidence on
the `hermes -z` route. This explains why the route is blocked, but it is not a
reviewer record and does not satisfy production quorum.
