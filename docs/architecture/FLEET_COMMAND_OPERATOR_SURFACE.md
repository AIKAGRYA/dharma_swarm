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

Status: DRAFT — implementation-driving design; six operator decisions remain open.

## Intent and status

This document ports the revised Fleet Hub plan into the repository's architecture-document convention. It is a design for a thin, phone-first operator client over existing `dharma_swarm` owners. It does not create a new A2A envelope, roster, board, authority, or truth store.

The source plan is authoritative for this design. The diagnosis below names candidate causes that are each sufficient to explain the observed symptom; it does **not** claim that one candidate has been confirmed as the cause firing in live traffic.

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

### Current diagnosis: candidate causes, not a confirmed live root cause

The symptom can be explained by several independently sufficient candidates. The evidence establishes these candidates exist and are reachable in the relevant design, but does not establish which one is firing in live traffic:

1. The Fleet Hub prototype publishes ad-hoc messages instead of using the versioned canonical envelope.
2. It uses a parallel roster rather than `FLEET_FIELD_REGISTRY.yaml`, `contact_registry.py`, `agent_directory.py`, and Agent Cards.
3. It uses a flat Kanban API rather than the canonical TaskBoard and BoardStore projection.
4. It uses a new dashboard rather than extending or sharing DHARMA COMMAND.
5. It tails flat-file chat history rather than JetStream and task receipts.
6. It uses callsign subjects rather than the UID-derived topology.

The one known design hazard is direct operator publication: it bypasses Telos gates, TaskBoard transition validation, claim leases, cost ceilings, and the witness/receipt trail. The ADR in `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md` records that boundary.

### Live-versus-target topology seam

`NatsTransportConfig` defaults to `DS_TASKS`/`DS_DLQ`, but `docs/ops/FLEET_FIELD_REGISTRY.yaml` states that **no DS_* stream runs live anywhere** and that live traffic is on `DHARMA_A2A`. A contractor reading only the transport defaults could wire the hub to a stream that does not exist and receive silence. This seam must remain prominent until a dated topology decision closes it.

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
  -> A2A task envelope on the selected live topology
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

| Route | Subject |
|---|---|
| UID inbox | `dharma.agent.<uid>.inbox` |
| compatibility recipient | `dharma.a2a.<recipient>` |
| reply | `dharma.a2a.reply.<packet_id>` |
| DLQ | `dharma.dlq.<stream>.<consumer>` |

The hub must not silently select `DS_TASKS`/`DS_DLQ` while the field registry says live traffic is `DHARMA_A2A`. The decision is open and must be dated before production wiring.

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
| operator UI | DHARMA COMMAND or separate phone client, decision open | Thin client over shared API |

The architecture doc is a DRAFT and does not itself become repo-level canon. It is subordinate to the canonical owners in `docs/governance/CANONICAL_DOC_STACK.md`.

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
| **M0** | **Reconcile identity** | One canonical roster; FFR-D2 closed (hermes/rushabdev collision resolved); Devin drains UID inbox + reply/ACK; `perplexity-computer` drift closed. Verify: every agent gets a probe DM and replies, on subjects derived solely from the canonical roster |
| **M1** | Lock down + topology decision | Hub reachable only via Tailscale/mTLS; exposed credential rotated; NATS perms subject-scoped per node; DHARMA_A2A vs DS_* written down as a dated decision |
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

1. **Reframe accepted?** Fleet Hub as a thin phone client onto existing canonical surfaces, rather than a parallel implementation. Everything above depends on this answer.
2. **Phone client: extend DHARMA COMMAND, or separate lightweight app?** The Next.js dashboard has the panels but is laptop-shaped; a separate phone client duplicates rendering but ships faster and will not destabilize the cockpit. The source plan leans separate client, shared API.
3. **Tailscale on the phone?** Still unanswered; it collapses most of the auth problem.
4. **DHARMA_A2A or DS_\*** for the hub to build against?
5. **Per-objective cost ceiling default**, and who may raise it — the field exists and needs a number.
6. **Authority tiers**: which agents are `command` versus `worker`? At 50 agents this is the difference between an organization and a mob.

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
