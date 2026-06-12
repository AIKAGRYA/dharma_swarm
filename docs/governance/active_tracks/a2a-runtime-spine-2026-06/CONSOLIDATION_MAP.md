# A2A Runtime Spine Consolidation Map

This map folds existing A2A/NATS work into the active track subtree. It is not a
new authority surface; it points to the owner files that already exist.

## Already Landed And Track-Owned

| Surface | Role | Current Reading |
|---|---|---|
| `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` | Canonical internal transport contract | Strong doctrine; explicitly separates publish, delivery, handler ack, and domain receipt. |
| `scripts/runtime/a2a_send.py` | Operator send surface | Records runtime refs and classifies publish-only as non-collaboration. |
| `scripts/runtime/a2a_inbox_bridge.py` | Agent inbox delivery handler | Can prove filesystem delivery and handler ack, not semantic peer response. |
| `scripts/runtime/a2a_reply_capture.py` | Reply-subject receipt capture | Separates no reply, untyped reply, and typed domain receipt. |
| `scripts/runtime/a2a_domain_reply_worker.py` | Target-owned domain receipt publisher | Prevents Codex-authored files from laundering into fake peer replies. |
| `scripts/runtime/a2a_live_handler_repair_plan.py` | Daemon/delivery repair planner | Joins daemon audit and quorum delivery state without mutating runtime. |
| `scripts/runtime/a2a_reset_quorum_consumers.py` | Explicit stale quorum consumer reset | Deletes/recreates selected durables as reset only; never peer evidence. |
| `scripts/runtime/a2a_quorum_blocker_status.py` | Quorum blocker classifier | Separates stale reviewer red-blocker text from current machine-evidenced production blockers. |
| `scripts/runtime/a2a_reviewer_route_health.py` | Reviewer route-health classifier | Explains missing Fable/Hermes reviewer records as provider/handler route failures without substituting for review. |
| `scripts/runtime/a2a_inbox_quarantine.py` | Legacy filesystem inbox quarantine | Moves stale mirror entries to dated quarantine and writes dry-run/apply receipts. |
| `scripts/runtime/a2a_file_bus_guard.py` | Legacy broadcast amplification guard | Fails when one `to: all` file-bus payload is mirrored into many inboxes. |
| `scripts/runtime/a2a_hermes_broadcast_guard.py` | Hermes alert-router broadcast disable guard | Backs up and patches the external Hermes alert router so it no longer mirrors alerts into every filesystem inbox. |
| `scripts/runtime/a2a_launchagent_quarantine.py` | Stale LaunchAgent declaration quarantine | Moves broken A2A/NATS plist declarations to dated backup with one pointer README. |
| `dharma_swarm/a2a/nats_transport.py` | A2A JetStream adapter | Provides typed transport adapter with execution identity and idempotency. |
| `dharma_swarm/operator_core/nats_live_contact.py` | Live JetStream verifier | Honest proof path for publish/consumer ack; no fake success if nats-py or broker is missing. |
| `dharma_swarm/operator_core/nats_substrate_status.py` | Operator projection | Keeps open-port checks below live-contact proof. |

## Existing Evidence And Reports

| Surface | Role | Fold Into |
|---|---|---|
| `reports/handoffs/A2A_HUB_REPAIRS_2026-06-11.md` | Broker split and repair evidence | `01-canonical-nats-topology` |
| `reports/handoffs/PHANTOM_ACKER_FINDINGS_2026-06-11.md` | Devin ack topology clarification | `02-hot-contact-ack-and-domain-receipts` |
| `reports/handoffs/A2A_TO_DEVIN_2026-06-11_0915Z.md` | Devin delivery/reply history | `02-hot-contact-ack-and-domain-receipts` |
| `reports/a2a/mike_inbox_drain_20260612T0158Z.txt` | Prior durable drain receipt | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/nats_reset/2026-06-13/NATS_CONSUMER_INBOX_RESET_APPLIED.json` | AGNI durable consumer inbox reset receipt | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json` | Live-handler repair plan receipt | `01-canonical-nats-topology` |
| `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_APPLIED.json` | Stale Fable/Hermes quorum consumer reset receipt | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_POST_QWEN_APPLIED.json` | Post-Qwen Fable/Hermes consumer reset receipt: clears current backlog without claiming peer review | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json` | Stale LaunchAgent quarantine receipt: five broken A2A/NATS plists backed up and removed from `~/Library/LaunchAgents` | `01-canonical-nats-topology` |
| `reports/a2a/inbox_quarantine_receipts/20260612T182948Z-a2a-inbox-quarantine.json` | Fourth-pass apply receipt: 380 Hermes `to: all` mirror files moved to quarantine | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/inbox_quarantine_receipts/20260612T183000Z-a2a-inbox-quarantine.json` | Post-quarantine dry-run receipt: zero current candidates | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json` | Hermes alert-router broadcast source disabled with backup and flag file | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/inbox_quarantine_receipts/20260612T192816Z-a2a-inbox-quarantine.json` | Post-Hermes-guard apply receipt: 229 mirrored files moved to quarantine | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json` | Current file-bus guard receipt: zero broadcast candidates after source disable and quarantine | `03-inbox-drain-reset-and-retention` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/codex_composer.json` | Codex ops reviewer record: `not_ready`, red blockers present | `05-persistent-agent-workflow-and-quorum` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/qwen_code.json` | Qwen adversarial reviewer record: `not_ready`, adds Alibaba-family diversity but keeps blockers red | `05-persistent-agent-workflow-and-quorum` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/gemini_reviewer.json` | Gemini independent reviewer record: third model family, still `not_ready` | `05-persistent-agent-workflow-and-quorum` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json` | Machine classifier: 4 stale/resolved blockers, 2 partially resolved, 7 current | `05-persistent-agent-workflow-and-quorum` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json` | Machine classifier: Fable provider-credit blocked, Hermes provider-timeout/handler-stalled | `05-persistent-agent-workflow-and-quorum` |
| `reports/a2a/prod_readiness_quorum/2026-06-13/reviewer_attempts/` | Failed/partial reviewer attempts for Fable, Hermes, Devin, and raw Qwen output | `05-persistent-agent-workflow-and-quorum` |
| `docs/plans/2026-06-11-dharma-a2a-stream-retention-proposal.md` | AGNI retention proposal | `03-inbox-drain-reset-and-retention` |
| `docs/agent_tasks/2026-06-12_runtime_truth_command_cutover_goal.md` | Runtime-truth command cutover plan | `05-persistent-agent-workflow-and-quorum` |
| `docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml` | Old proposed cloud-agent bridge | Folded into this track; no separate active track unless external gateway surfaces exceed five subtracks. |

## Open Branches And PRs To Fold Here

| Lane | Proposed Fold |
|---|---|
| `origin/codex/truth-graph-v1` / PR #586 | Fold shared-state projection into subtrack `04-shared-state-graph-and-vector-memory`. |
| `origin/feat/trust-gate-scoreboard` / PR #578 | Fold production readiness signal into subtrack `05-persistent-agent-workflow-and-quorum`. |
| `origin/organ/03-seat` | Fold harness seat/dispatch hardening into spine adoption first, then expose A2A staffing readiness through this track. |
| `docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml` | Treat as cloud-edge seam, not a new track yet. |

## Explicit Non-Authority

- File inboxes under `~/.dharma/a2a_bus/` are dock/mirror surfaces.
- `reports/a2a/**` receipts are evidence and projections.
- Orientation graph, truth graph, board cards, and vector search are fast views.
- Authority remains with the runtime store, NATS broker state, source docs,
  active track YAML, and typed receipts.
