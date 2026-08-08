---
title: Fleet Command Operator Surface
path: docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md
slug: fleet-command-operator-surface
doc_type: active_spec
status: DRAFT
summary: Reframe Fleet Hub as a thin, phone-first operator client over dharma_swarm canonical A2A, TaskBoard, roster, presence, governance, and dashboard surfaces.
source:
  provenance: operator_design
  kind: architecture_spec
  origin_signals:
    - /home/ubuntu/fleet-hub-plan-v2.md
    - /home/ubuntu/dharma-swarm-survey.md
    - docs/README.md
    - docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md
  cited_urls: []
  generated_hint: human_authored_design_ported_to_repo_convention
connected_relevant_files:
  - scripts/runtime/a2a_topology.py
  - dharma_swarm/a2a/nats_transport.py
  - dharma_swarm/a2a/nats_transport_support.py
  - dharma_swarm/task_board.py
  - dharma_swarm/board/models.py
  - dharma_swarm/board/adapters/agentops_adapter.py
  - docs/ops/FLEET_FIELD_REGISTRY.yaml
  - dharma_swarm/a2a/agent_presence.py
  - dharma_swarm/telos_gates.py
  - dashboard/src/app/dashboard/cockpit/page.tsx
  - dashboard/src/components/cockpit/A2ASendCardsPanel.tsx
  - api/main.py
schema_version: pkm-phd-stigmergy-v1
---

# Fleet Command Operator Surface

Date: 2026-08-07

Status: DRAFT — implementation-driving design; four operator decisions remain open.

## Intent and status

This document ports the revised Fleet Hub plan into the repository's architecture-document convention. It is a design for a thin, phone-first operator client over existing `dharma_swarm` owners. It does not create a new A2A envelope, roster, board, authority, or truth store.

The source plan is authoritative for this design. The live evidence below records what the broker counters and permissions prove, and separates that from what remains unresolved about end-to-end handler behavior.

The spec as written builds a third parallel implementation of things `dharma_swarm` already owns canonically. `/root/agni/fleet_hub/server.py` reinvents:

| Fleet Hub spec invents | Already canonical in dharma_swarm |
|---|---|
| ad-hoc chat message dict | `dharma.nats.envelope.v1` / `dharma.a2a.nats_task.v1` — versioned, with `message_id`, `trace_id`, `span_id`, `correlation_id`, `causation_id`, `context_id`, ACK tiers, DLQ |
| `dispatch-catalog.json` roster of 10 | `FLEET_FIELD_REGISTRY.yaml` (live probed), `contact_registry.py`, `agent_directory.py`, Agent Cards |
| `GET /api/kanban` → flat task list | SQLite `TaskBoard` (canonical, validated transitions, Telos-gated) + `BoardStore` Cards with claim leases, cost ceilings, capability manifests, acceptance criteria, audit log, optimistic concurrency |
| new dark-theme dashboard | Next.js DHARMA COMMAND: `/dashboard/cockpit`, `command-post`, `agents`, `tasks`, `CoherenceKanban`, `A2ASendCardsPanel`, `gates`, `stigmergy` |
| chat history as flat-file tail | JetStream `DHARMA_A2A` + task receipts (`dharma_a2a_task_receipt.v1`) |
| `dharma.a2a.<callsign>` subjects | `a2a_topology.py` — self-described single source of truth: `dharma.agent.<uid>.inbox`, `dharma.a2a.<recipient>` (compat), `dharma.a2a.reply.<packet_id>`, `dharma.dlq.<stream>.<consumer>` |

The existing substrate means the missing product is a **phone-first operator client** on top of it. These are different builds: no new envelope, roster, board, or authority. The client renders `TaskBoard`/`BoardStore`, publishes through `a2a_topology.py`, and reads presence and gate verdicts from existing owners.

Operator actions that change work state must not publish directly to NATS. They must issue TaskBoard commands. Free-text chat may go over A2A directly; consequential work-state mutation may not.

## Current truth

### Existing canonical surfaces

The repository already contains the enterprise A2A substrate:

- `dharma.nats.envelope.v1` / `dharma.a2a.nats_task.v1` carry `message_id`, `trace_id`, `span_id`, `correlation_id`, `causation_id`, and task `context_id`.
- `scripts/runtime/a2a_topology.py` defines `dharma.agent.<uid>.inbox`, compatibility `dharma.a2a.<recipient>`, replies, and DLQ subjects.
- SQLite `TaskBoard` validates transitions and is Telos-gated. BoardStore Cards add claim leases, cost ceilings, capability manifests, acceptance criteria, audit logs, and optimistic concurrency.
- AgentOps JSON packets, BoardStore, and the dashboard are projections around canonical task/runtime owners.
- DHARMA COMMAND already provides cockpit, command-post, agents, tasks, Kanban, A2A receipt, gates, runtime, telemetry, and stigmergy surfaces.

### Delivery symptom: stale durables, visibility failure, and remaining uncertainty

The observed symptom is that messages published to fleet subjects do not reach an agent in a way the operator can observe, and no reply appears. JetStream distinct durable names sharing a filter subject are independent subscriptions: each receives its own copy. Competing delivery requires processes sharing one durable name. The repeated Hermes filter therefore creates approximately 19-way fan-out on `dharma.a2a.hermes`, with duplicate work and duplicate replies as the risk; it does not make messages disappear. The binding map and counters come from the session artifact `/tmp/nats_readonly_inventory.json`, produced by the runnable command `PYTHONPATH=/home/ubuntu/repos/dharma-swarm PATH=.venv/bin:$PATH .venv/bin/python /tmp/nats_readonly_inventory.py > /tmp/nats_readonly_inventory.json`.

The counters evidence delivery into queues with no current drain:

- `agni_hermes_inbox` is at `num_pending=0`, `delivered.stream_seq=8123228` (the captured stream head), and `ack_floor.stream_seq=8123225`.
- `hermes_inbox`, `rushabdev_hermes_inbox`, and `fleet_agni_inbox` each have `num_pending=380`, with delivered sequences `8118474`, `8118756`, and `8118886`, respectively.
- `devin_inbox` has `num_pending=3` and `delivered.stream_seq=8109056`, showing arrival and accumulation rather than disappearance.
- `gw_dharma_command_node_a2a` tracks the fleet stream head at `8123228` with no pending messages, while `merge_master_mike_fleet` has `num_pending=306` and delivered sequence `8106912`.

These counters prove stream acceptance and durable accumulation, and strongly evidence abandoned or unread durables. They do not prove whether an agent receives a newly published message and elects not to reply, or whether an agent replies on a route the operator cannot see. The single-probe session accepted one message (`DHARMA_A2A` head `8123228 → 8123229`), but ACLs blocked the follow-up consumer snapshots and reply watch. The discriminating check is an authorized one-message trace that records the target durable's pending/delivery movement and observes the correlated reply route end to end.

The operator credential itself cannot subscribe to `dharma.a2a.hermes.reply.>` (`permissions violation for subscription to "dharma.a2a.hermes.reply.>"`). It is also denied individual `consumer.info` and `consumer.list` on every stream other than `DHARMA_A2A`; these denials were observed by `PYTHONPATH=/home/ubuntu/repos/dharma-swarm PATH=.venv/bin:$PATH .venv/bin/python /tmp/hermes_single_probe.py`. An operator surface without reply-route visibility cannot display replies regardless of UI quality. A hub ACL grant for reply subscriptions and required consumer metadata is therefore a **blocking dependency** for the phone client.

Approximately 18 stale consumers are largely leftover debug scans, including `temp_full_scan`, `peer_check`, and `temp_wildcard_scan`, accumulating messages indefinitely. Reaping these durables is an M0 item and requires explicit operator approval because it mutates the live hub.

Roster fragmentation remains a real routing and identity risk, not an evidenced cause of silence. Live corroboration includes `gw_perplexity_computer_a2a` filtering `dharma.a2a.perplexity`; the naming drift remains tracked at `docs/ops/FLEET_FIELD_REGISTRY.yaml:179-195`. The Hermes/rushabdev identity seam remains at `docs/ops/FLEET_FIELD_REGISTRY.yaml:84-122`, and Devin's compatibility route remains at `docs/ops/FLEET_FIELD_REGISTRY.yaml:124-141`; these require reconciliation because they can create duplicate delivery or undrained routes, not because distinct durables compete.

The separate direct-operator-publication hazard remains: it bypasses Telos gates, TaskBoard transition validation, claim leases, cost ceilings, and the witness/receipt trail. The ADR in `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md` records that boundary.

### Live topology

The live hub inventory captured on 2026-08-07 contains `DHARMA_A2A` (2,292 messages, 73 consumers), `A2A_INBOX`, `A2A_TASKS`, `A2A_DLQ`, `A2A_RECEIPTS`, `CODEX_COMPOSER_JOBS`, `CODEX_COMPOSER_RESULTS`, `CODEX_COMPOSER_DLQ`, `KV_PRESENCE`, and `DHARMA_TEST`. `DS_TASKS` and `DS_DLQ` do not exist. The evidence source is `/tmp/nats_readonly_inventory.json`, produced by `PYTHONPATH=/home/ubuntu/repos/dharma-swarm PATH=.venv/bin:$PATH .venv/bin/python /tmp/nats_readonly_inventory.py > /tmp/nats_readonly_inventory.json`; the artifact is a session file outside the repository.

UID inbox subjects live on the separate `A2A_INBOX` stream, while compatibility subjects live on `DHARMA_A2A`. The phone client must preserve that stream distinction when presenting route health and selecting subscriptions. The live `A2A_*` names resolve the former `DS_*` topology question as of 2026-08-07; repository transport defaults remain implementation drift to reconcile, not a live topology choice.

### Hard gaps already admitted by the repository

- No proven fleet-wide local-NATS ↔ AGNI mirror.
- No enforced Agent Card signature verification.
- Dashboard authentication is already fail-closed when no key is configured (`api/main.py:234-239`); the hub must match, not loosen, this behavior.

## Principles and non-goals

### Principles

- **Thin client, canonical owners.** Fleet Command renders and commands existing owners; it does not fork them.
- **TaskBoard is canonical.** BoardStore, dashboard Cards, and AgentOps packets remain projections.
- **One topology source.** Conform to `a2a_topology.py`; do not invent a third subject scheme.
- **Honest truth levels.** Distinguish broker publish acceptance, handler contact, receipt-backed completion, recent presence, and live transport contact.
- **Default silence.** An agent speaks when addressed, when it holds the turn, or when it has a receipt to report.
- **Objectives first, exceptions first.** At more than 20 agents, replies are batched into per-objective digests unless flagged urgent.
- **Fail closed.** Authentication, Telos blocks, lease rules, cost ceilings, and receipt requirements must remain visible and enforceable.

### Non-goals

- No new message envelope or parallel chat protocol.
- No new roster or dispatch catalog.
- No new board database or direct dashboard-owned state mutation.
- No direct NATS work-state writes from the phone UI.
- No claim that the unresolved live root cause is confirmed.
- No assumption that DS_* is live merely because code defaults to it.
- No claim that Agent Card identity is authenticated until signature enforcement exists.

## Target architecture

```text
Phone / DHARMA COMMAND / CLI
  -> authenticated OperatorIntent
  -> shared API / policy / human approval
  -> TaskBoard command path for consequential work
  -> BoardStore projection + event stream
  -> A2A task envelope on the live A2A_* topology
  -> A2ANatsTransport / compatibility bridge
  -> agent runtime / handler
  -> RuntimeReceipt + IdempotencyRecord + trace
  -> Telos / gate verdict / DLQ or escalation
  -> BoardStore and presence projections
  -> phone digest, objective thread, exception, or streamed reply
```

The transport contract is more important than the UI. A beautiful phone loop on a weak task path gives a talking puppet. A receipted A2A path with a thin phone adapter gives a real operator surface.

### Mesh progression

The components pay off in this order:

1. Shared board — already exists.
2. Capability-based claim routing — small addition.
3. Per-objective threads.
4. Agent-to-agent direct negotiation within a claimed Card.
5. Cross-node board replication — the current hard gap.

## Contracts

### Envelope contract

Use `dharma.nats.envelope.v1` and `dharma.a2a.nats_task.v1`. Existing fields include:

| Concern | Existing contract |
|---|---|
| message identity | `message_id` |
| thread/objective context | task `context_id` |
| distributed tracing | `trace_id`, `span_id`, `parent_span_id` |
| causal linkage | `correlation_id`, `causation_id` |
| addressing | `from_agent`, `to_agent`, subject, actor |
| delivery | `requires_ack`, ACK tiers, idempotency, redelivery, DLQ |
| task body | task ID, history, artifacts, capability, metadata |

The survey found no existing hop counter. Add `hops` to the envelope and enforce it in bridges before attempting a 50-agent migration. This is the only genuine envelope addition in the revised plan.

Use `context_id` as the thread ID. Do not introduce a parallel `thread_id` field unless a later ADR explicitly establishes a compatibility mapping.

### Subject and stream contract

Use `scripts/runtime/a2a_topology.py` as the subject source:

| Route | Subject / stream |
|---|---|
| UID inbox | `dharma.agent.<uid>.inbox` on `A2A_INBOX` |
| compatibility recipient | `dharma.a2a.<recipient>` on `DHARMA_A2A` |
| reply | `dharma.a2a.reply.<packet_id>` or per-agent reply routes on `DHARMA_A2A` |
| DLQ | `dharma.dlq.<stream>.<consumer>` on `A2A_DLQ` |

The hub must use the live `A2A_TASKS` and `A2A_DLQ` names and must preserve the separate `A2A_INBOX` versus `DHARMA_A2A` route boundary. `DS_TASKS` and `DS_DLQ` are absent from the live hub as of 2026-08-07.

### Identity and roster contract

Establish one canonical roster owning:

- stable agent UID and callsign
- model and host/node
- capabilities
- inbox, reply, and compatibility subjects
- authority tier
- liveness and last verified contact

This supersedes competing projections. The required first milestone is M0:

- resolve FFR-D2's Hermes/rushabdev subject collision;
- make Devin drain UID inbox plus reply/ACK routes;
- close `perplexity`/`perplexity-computer` naming drift;
- probe every agent using subjects derived solely from the canonical roster.

Do not build a 50-agent authority model on unauthenticated identity. Agent Card signature enforcement remains a later hardening milestone.

### Board and work-item contract

TaskBoard is canonical; BoardStore, dashboard Cards, and AgentOps packets are projections. The phone board is not authoritative, and drag-and-drop is not itself a state change. A drag issues a TaskBoard command and renders the returned verdict, including a Telos block and its reason.

Use BoardStore's 12-status set as the display vocabulary:

`inbox`, `triaged`, `planned`, `blocked`, `claimable`, `claimed`, `running`, `review`, `done`, `failed`, `cancelled`, `quarantined`.

Publish an explicit mapping from TaskBoard statuses and `terminal_overnight_supervisor.py`'s local `pending` / `in_progress` / `blocked` / `completed` vocabulary. Do not let the phone UI invent a fourth vocabulary.

Preserve the honest projection rule: `agentops_adapter.py` projects a packet marked *done without runtime truth* as `review`, not `done`. A green `done` without receipt-backed truth would make the board untrustworthy.

### Presence contract

Separate two questions:

| Question | Signal |
|---|---|
| live now | transport truth from `nats_live_contact.py`, including verified JetStream publish/consumer ACK |
| seen recently | `agent_presence.py` projection, which turns RED after more than 2 hours without a usable timestamp |

The 2-hour projection is unsuitable for a live/dead dot: an agent can be dead for 119 minutes and still show green. The phone client must display these as distinct signals rather than collapsing them.

### Governance and authentication contract

- Consequential work-state actions go through TaskBoard command paths.
- Direct free-text chat may use A2A, but must not mutate Board state directly.
- Telos BLOCKs render with the reason.
- Claim leases, capability-gated claims, cost ceilings, escalation SLA, authority tiers, and delegation depth caps are enforced by their owning command/policy paths.
- Dashboard and phone authentication remain fail-closed; Tailscale/mTLS is the preferred unresolved deployment decision.
- Agent identity is not treated as authenticated until Agent Card signatures or an equivalent trust gate are enforced.

## Authority and ownership

| Concern | Owner | Fleet Command role |
|---|---|---|
| A2A envelope and delivery | `A2ANatsTransport`, `nats_transport_support.py`, `a2a_topology.py` | Adapt/render; do not fork |
| work-state transitions | `TaskBoard` and its command paths | Issue commands; render returned state |
| board projection | `BoardStore`, adapters, event log | Read model and event consumer |
| work packet truth | AgentOps packet/runtime receipt owners | Preserve projection semantics |
| roster/routing | canonical roster to be established; currently field registry plus competing projections | Consume one selected owner after M0 |
| presence | transport contact plus presence projection | Display both truth levels |
| governance | TelosGatekeeper, kernel/tool policy, receipt gates | Surface verdicts; never bypass |
| operator UI | separate lightweight phone client; DHARMA COMMAND remains the cockpit | Thin client over shared API |

The architecture doc is a DRAFT and does not itself become repo-level canon. It replaces nothing. It subordinates to `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md` for the A2A spine and to `docs/governance/CANONICAL_DOC_STACK.md` for document authority and hierarchy; executable truth remains with the cited code and runtime owners.

## Failure and migration semantics

### Failure behavior

- A TaskBoard command rejected by transition validation remains rejected; the UI must not optimistically display the requested state.
- A Telos BLOCK remains a block and renders its reason.
- A missing or stale heartbeat is not promoted to “live now.”
- A broker publish ACK is not promoted to handler contact or semantic completion.
- A packet marked done without runtime truth remains `review`.
- A failed handler retries or goes to DLQ with evidence; it is not swallowed.
- Authentication and identity-verification failures fail closed.
- Cross-node replication is not assumed until it has its own evidence and reconciliation contract.

### Migration milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | **Reconcile identity and stale consumers** | One canonical roster; FFR-D2 reconciled; Devin drains UID inbox + reply/ACK; `perplexity-computer` drift closed; operator-approved debug durable reaping; reply-route and consumer-metadata ACLs granted. Verify: every agent gets a probe DM and replies, on subjects derived solely from the canonical roster |
| **M1** | Lock down access | Hub reachable only via Tailscale/mTLS; exposed credential rotated; NATS permissions subject-scoped per node; live `A2A_*` topology is used |
| **M2** | Envelope + repo | `hops` added to envelope + enforced in bridges; Fleet Hub code in git; docker-compose NATS + fake agent so the client is buildable with zero prod access |
| **M3** | Vertical slice | One agent, streamed reply, first token < 2s p95 / complete < 20s p95 over 20 runs. Prove latency before wiring ten |
| **M4** | Board authority + org rules | Phone board issues TaskBoard commands (never direct writes); authority tiers, escalation SLA, delegation depth cap, capability-gated claims enforced; a Telos BLOCK renders with its reason |
| **M5** | Phone client | Objectives-first, exception-first, per-objective threads, SSE with `Last-Event-ID` resume across iOS backgrounding |
| **M6** | Scale rehearsal | 50 simulated agents against the real board: claim contention, lease expiry/revocation, cost ceilings, storm test fails closed |
| **M7** | Mesh + extras | Cross-node board replication, Agent Card signature enforcement, routing tuning, reactions/search/files |

Ordering logic: **M0 first because it is the actual bug**, and every later milestone's verification is unreliable until identity is single-valued.

## Observability and evidence

The operator surface must make evidence tiers explicit:

- objective and Card status from TaskBoard/BoardStore;
- claim lease, expiry, revocation, and cost-burn state;
- A2A message ID, trace/correlation IDs, ACK tier, redelivery, and DLQ state;
- `live now` transport contact versus `seen recently` heartbeat projection;
- receipt verdict, evidence, next action, and files changed;
- Telos and governance decisions, including blocking reason;
- stream/subject selection and whether the observation is live, target, aspirational, or unprobed.

At more than 20 agents, default to per-objective digests; urgent items remain individually surfaced. The dashboard already has the relevant foundation: `A2ASendCardsPanel.tsx`, `AgentOpsWorkPacketCardsPanel.tsx`, `RuntimeRail.tsx`, `SpinePulsePanel.tsx`, `SystemTruthMatrix.tsx`, `CoherenceKanban.tsx`, `ExecutiveBoard.tsx`, and `CockpitV2Board.tsx`.

## Rollout and definition of done

The first vertical slice should prove one agent, one streamed reply, and latency before wiring ten. The client must be buildable against a local NATS plus fake agent with zero production access.

The operator surface is ready for a scale rehearsal when:

- one phone/CLI intent becomes a canonical TaskBoard command;
- the resulting task crosses the selected A2A topology through the canonical transport or explicitly equivalent compatibility path;
- the handler emits a receipt and artifact/reply;
- duplicate sends do not duplicate side effects;
- handler failure redelivers or DLQs with evidence;
- local and AGNI broker status are reported separately;
- a Telos block is visible with its reason;
- live transport and recent heartbeat are shown separately;
- all agent subjects derive from one canonical roster;
- 50 simulated agents can exercise claim contention, lease expiry/revocation, cost ceilings, and storm failure without opening a bypass.

## Open gaps and open decisions

### Open decisions

1. **Tailscale on the phone?** Still unanswered; it collapses most of the auth problem.
2. **Per-objective cost ceiling default**, and who may raise it — the field exists and needs a number.
3. **Authority tiers**: which agents are `command` versus `worker`? At 50 agents this is the difference between an organization and a mob.
4. **Reply and metadata ACL scope:** exact subject and JetStream API permissions for the phone operator credential after the M0 blocking grant.

Resolved on 2026-08-07:

- The thin-client reframe is accepted.
- The operator surface is a separate lightweight phone client rather than an extension of DHARMA COMMAND, so the cockpit remains stable while the phone surface iterates.
- The live topology is `DHARMA_A2A`, `A2A_INBOX`, `A2A_TASKS`, `A2A_DLQ`, and the other streams recorded above; `DS_TASKS` and `DS_DLQ` are absent.

### Hard gaps

- No proven local-fleet to AGNI mirror.
- No enforced Agent Card signature verification.
- No universal hop-count field until M2.
- No single canonical roster until M0.
- No cross-node BoardStore replication until M7.

## References

- `docs/README.md:86-137` — documentation classes and architecture placement.
- `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md` — existing spine structure, current truth, merge order, hard gaps, and definition of done.
- `scripts/runtime/a2a_topology.py` — subject topology.
- `dharma_swarm/a2a/nats_transport_support.py:34-73` — envelope schemas and fields.
- `dharma_swarm/task_board.py:175-230` — transition validation and Telos witness.
- `dharma_swarm/board/models.py:29-42,79-95,153-180` — Card statuses and claim leases.
- `dharma_swarm/board/adapters/agentops_adapter.py` — AgentOps projection semantics.
- `docs/ops/FLEET_FIELD_REGISTRY.yaml` — field-probed roster and live/target topology.
- `dharma_swarm/a2a/agent_presence.py` — recent-presence projection.
- `dharma_swarm/telos_gates.py:233-258,632-685` — blocking and advisory gate tiers.
- `api/main.py:188-203,234-239` — TaskBoard authority and fail-closed dashboard authentication.
- `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md`
- `docs/architecture/ADRs/ADR-012-canonical-fleet-roster.md`
- `docs/architecture/ADRs/ADR-013-separate-phone-client.md`
