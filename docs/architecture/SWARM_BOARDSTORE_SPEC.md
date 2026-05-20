# Swarm BoardStore Facade and Client Participation Spec

Date: 2026-05-20
Status: implementation spec
Scope: spec only. No runtime implementation is introduced by this document.

This specification defines Item A of the swarm substrate buildout: the
`BoardStore` facade and the `dharma_swarm.client` participation library.

The goal is one trustable participation surface for heterogeneous agents:
Cursor, Codex, Claude Code, Devin, Warp, Perplexity, local daemons, remote
mailbox workers, and future arrivals. The facade does not replace existing
stores. It sublates them: each store keeps the truth it already owns, while the
facade exposes one card contract, one write path, one lease model, and one
append-only audit stream.

## 1. Executive Summary

`BoardStore` is a local-first facade over seven existing truth-bearing stores:

1. `TaskBoard` for task CRUD, priority, dependencies, and the current task
   status finite-state machine.
2. `OperatorBridge` for operator work orders, external-agent claim,
   heartbeat, partial artifacts, response, recovery, and acknowledgement.
3. `RuntimeStateStore` for sessions, task claims, delegation runs, workspace
   leases, artifacts, memory facts, context bundles, and operator actions.
4. `RoamingMailbox` for git-friendly remote task transport.
5. `ControlSurface` for declared-vs-observed runtime projections.
6. `IntentRouter` plus `MissionState` for intent decomposition, routing, and
   mission continuity.
7. `AutoProposer` plus `recursive_discovery` for observation, proposal
   evidence, recursive receipts, and promotion holds.

`BoardStore` is not a new isolated board database. It introduces a small local
SQLite append-only event log and facade metadata tables for idempotency,
versioning, projection indexes, and replay. The durable domain state remains in
the existing stores. The event log records what the facade did, not a parallel
world.

`BoardStore` is not kanban. Kanban is one renderer. The board can also render
as a table, map, CLI list, Telegram thread, A2A envelope, MCP tools/resources,
or AG-UI stream. Views do not own state.

`BoardStore` is not an orchestrator. It does not choose models, edit files,
execute tasks, merge PRs, or feed evolution loops. It coordinates safe
participation: create cards, claim leases, heartbeat, release, transition,
attach receipts, post handoffs, and record control events.

`dharma_swarm.client` is the participation boundary. Internal code may adapt
existing stores during migration, but no human-facing or external agent path is
allowed to mutate board state except through the client or a facade-owned admin
adapter. Raw HTTP is internal/admin. The client owns schema validation,
idempotency keys, optimistic locking, auth identity, lease renewal, cost
ceilings, retry policy, and error taxonomy.

This is substrate work, not a feature, because it defines how every future
agent and surface participates without schema churn. A new agent kind in 2027
adds a capability declaration or adapter. A new surface adds a renderer. A new
store adds a store adapter. None of those changes require breaking the `Card`
schema or the client write contract.

The ARJUNA gate is part of the write path. Every card carries an
`arjuna_weight`, and cards below the configured threshold require explicit,
audited override. The doctrine anchor is `docs/doctrine/OPERATIONAL_DOCTRINE.md`:
the system is "the Palantir of good works" at lines 28-39, and the Arjuna test
is "Does this point a weapon at something broken in the world?" at lines 52-58.

## 2. Repo State Evidence

### Current branch and governance state

This spec is written after PR #313 landed on `main`:

- `HEAD` is `d557f4e6`, `chore(governance): convergence layer - single-door
  onboarding + stale-pointer cleanup (#313)`.
- PR #313 added `make onboard`, registered in the Makefile help at
  [Makefile:45](../../Makefile#L45) and implemented by
  [scripts/governance/agent_onboard.py:1](../../scripts/governance/agent_onboard.py#L1).
- `agent_onboard.py` explicitly says it owns no facts and renders
  `ACTIVE_TRACK.yaml`, `LIVE_OPS_DASHBOARD.md`, `BROKEN_REGISTER.md`,
  `SOVEREIGN_MANIFEST.md`, git, and the surface manifest
  [scripts/governance/agent_onboard.py:1](../../scripts/governance/agent_onboard.py#L1).
- The governance hub now points to `make onboard` as the single door, while
  remaining only a depth pointer
  [docs/governance/README.md:1](../governance/README.md#L1).
- The active track remains cockpit/control-surface hardening, with
  `ACTIVE_TRACK.yaml` as the single owner of current intent
  [docs/governance/ACTIVE_TRACK.yaml:1](../governance/ACTIVE_TRACK.yaml#L1).

PR #313 did not land `BoardStore`, `dharma_swarm.client`, a board event log,
the noticer daemon, cost-cap enforcement, a kanban, or a substrate spec on
`main`. The prompt referenced `docs/architecture/SWARM_SUBSTRATE.md`, but that
file is absent on merged `main`. A prior draft exists in the separate worktree
`/Users/dhyana/dharma_swarm_substrate_spec`; this spec treats it as prior
background, not an authority on this branch.

### GitNexus index state

`npx gitnexus list` on this worktree reports:

| Worktree | Commit | Symbols | Edges | Clusters | Flows |
|---|---:|---:|---:|---:|---:|
| `/Users/dhyana/dharma_swarm_boardstore_spec` | `d557f4e` | 95,987 | 165,553 | 2,050 | 300 |
| `/Users/dhyana/dharma_swarm_substrate_spec` | `8837a3f` | 96,009 | 165,596 | 2,050 | 300 |

The user-supplied number, 96,009 nodes and 165,596 edges, is the prior
substrate worktree. The boardstore branch was re-indexed after PR #313 and is
up to date at 95,987 symbols and 165,553 edges.

### Seven-store impact evidence

GitNexus and direct source reads show the stores have different blast radii.
That is exactly why `BoardStore` must be a facade instead of a replacement.

| Store | Current implementation | GitNexus signal | Load-bearing interpretation |
|---|---|---:|---|
| TaskBoard | [dharma_swarm/task_board.py:1](../../dharma_swarm/task_board.py#L1) | Prior full pass: 56 impacted, 8 direct importers; current CLI sees two `TaskBoard` symbols and requires disambiguation. | Canonical task CRUD/FSM is load-bearing. There is also a duplicate protocol/class in `orchestrator.py`, so migration must be adapter-first. |
| OperatorBridge | [dharma_swarm/operator_bridge.py:1](../../dharma_swarm/operator_bridge.py#L1) | Current GitNexus: 8 impacted, 4 direct importers, low risk. | It is the strongest existing external-agent work-order lifecycle. Keep it intact and route through it. |
| RuntimeStateStore | [dharma_swarm/runtime_state.py:1](../../dharma_swarm/runtime_state.py#L1) | Current GitNexus: 99 impacted, 30 direct importers, critical risk. | This is the runtime spine. `BoardStore` may mirror into it, but must not rewrite it casually. |
| RoamingMailbox | [dharma_swarm/roaming_mailbox.py:1](../../dharma_swarm/roaming_mailbox.py#L1) | Current GitNexus: 3 impacted, 3 direct importers, low risk. | It is a transport adapter, not a board authority. |
| ControlSurface | [dharma_swarm/operator_core/control_surface.py:1](../../dharma_swarm/operator_core/control_surface.py#L1) | Prior full pass: `build_control_surface_rows` 9 impacted, 4 direct callers. | It is a projection/read model. It must consume board events, not own writes. |
| IntentRouter + MissionState | [dharma_swarm/intent_router.py:1](../../dharma_swarm/intent_router.py#L1), [dharma_swarm/mission_contract.py:104](../../dharma_swarm/mission_contract.py#L104) | Prior full pass: `IntentRouter` 44 impacted, 5 direct; `MissionState` 29 impacted, 9 direct. Current index resolves lower direct class-only impact because several uses flow through files/functions. | Intent and mission continuity are planning inputs. They should create cards and objective trees, not claim work. |
| AutoProposer + recursive_discovery | [dharma_swarm/auto_proposer.py:1](../../dharma_swarm/auto_proposer.py#L1), [dharma_swarm/recursive_discovery.py:1](../../dharma_swarm/recursive_discovery.py#L1) | Prior full pass: `AutoProposer` 41 impacted; `RecursiveDiscoveryRecorder` 10 impacted. Current index resolves class-only `AutoProposer` as low direct impact. | These are notice/evidence loops. They must be prevented by contract from executing through the board. |

### Store source facts

`TaskBoard` already owns task persistence and the task FSM. The file docstring
states "Async task management with CRUD, dependency tracking, and status FSM"
[dharma_swarm/task_board.py:1](../../dharma_swarm/task_board.py#L1). Its
SQLite tables are `tasks` and `task_dependencies`
[dharma_swarm/task_board.py:28](../../dharma_swarm/task_board.py#L28), it
enables WAL for concurrency
[dharma_swarm/task_board.py:84](../../dharma_swarm/task_board.py#L84), and it
defines valid status transitions
[dharma_swarm/task_board.py:19](../../dharma_swarm/task_board.py#L19).

`OperatorBridge` already stores live queue state in SQLite inside the canonical
message-bus database and emits append-only audit facts through the session
ledger [dharma_swarm/operator_bridge.py:1](../../dharma_swarm/operator_bridge.py#L1).
It has an `operator_bridge_tasks` table with claim timeout, claimed actor,
response, retry, and metadata fields
[dharma_swarm/operator_bridge.py:51](../../dharma_swarm/operator_bridge.py#L51).

`RuntimeStateStore` already declares itself as the "structured source-of-truth
layer for single-host orchestration"
[dharma_swarm/runtime_state.py:1](../../dharma_swarm/runtime_state.py#L1). It
has first-class `task_claims`, `delegation_runs`, and `workspace_leases` tables
[dharma_swarm/runtime_state.py:43](../../dharma_swarm/runtime_state.py#L43).
Its dataclasses include `TaskClaim`, `DelegationRun`, `WorkspaceLease`,
`ArtifactRecord`, `MemoryFact`, and `OperatorAction`
[dharma_swarm/runtime_state.py:351](../../dharma_swarm/runtime_state.py#L351).

`RoamingMailbox` is explicitly a git-friendly cross-harness exchange where
tasks and responses are one JSON file each
[dharma_swarm/roaming_mailbox.py:1](../../dharma_swarm/roaming_mailbox.py#L1).
Its adapter to `OperatorBridge` says the mailbox is transport, not a second task
system [dharma_swarm/roaming_operator_bridge.py:1](../../dharma_swarm/roaming_operator_bridge.py#L1).

`ControlSurface` is a projector over declared intent and observed reality, not
a write owner [dharma_swarm/operator_core/control_surface.py:1](../../dharma_swarm/operator_core/control_surface.py#L1).
Its row model carries `authority_role`, `truth_owner`, `evidence`, `source_refs`,
`verification_timeline`, and `display_hints`
[dharma_swarm/operator_core/control_surface_models.py:148](../../dharma_swarm/operator_core/control_surface_models.py#L148).

`IntentRouter` already analyzes natural-language tasks, estimates complexity,
decomposes compound work, and routes to skills
[dharma_swarm/intent_router.py:1](../../dharma_swarm/intent_router.py#L1).
`MissionState` already captures objective continuity, task titles, delegated
task ids, blockers, and review summaries
[dharma_swarm/mission_contract.py:104](../../dharma_swarm/mission_contract.py#L104).

`AutoProposer` already observes fitness, repeated failures, stigmergy hotspots,
provider failure, stale tasks, test clusters, and evolution stagnation
[dharma_swarm/auto_proposer.py:1](../../dharma_swarm/auto_proposer.py#L1).
`recursive_discovery` explicitly records evidence and recommendations but does
not apply diffs or mutate runtime code
[dharma_swarm/recursive_discovery.py:1](../../dharma_swarm/recursive_discovery.py#L1).

### Radon complexity hot spots

Targeted Radon on substrate-adjacent files plus orchestration hot paths produced
average complexity `A (4.72)`. The highest relevant hot spots are:

| Location | Grade | CC | Spec consequence |
|---|---:|---:|---|
| `SwarmManager.tick` [dharma_swarm/swarm.py:2093](../../dharma_swarm/swarm.py#L2093) | F | 96 | Do not add another orchestrator loop. BoardStore must reduce dispatch ambiguity. |
| `AgentRunner.run_task` [dharma_swarm/agent_runner.py:2077](../../dharma_swarm/agent_runner.py#L2077) | F | 88 | Client contract should isolate agent participation from runner internals. |
| `Orchestrator._execute_task` [dharma_swarm/orchestrator.py:2163](../../dharma_swarm/orchestrator.py#L2163) | F | 48 | Execution stays out of BoardStore. |
| `AgentRunner._execute_local_tool` [dharma_swarm/agent_runner.py:1774](../../dharma_swarm/agent_runner.py#L1774) | F | 48 | Side-effectful tool execution must remain behind leases, cost caps, receipts, and sandbox rules. |
| `Orchestrator._assign_dispatch` [dharma_swarm/orchestrator.py:1908](../../dharma_swarm/orchestrator.py#L1908) | E | 33 | Claim semantics should move to a small facade contract. |
| `OperatorBridge._record_bridge_lifecycle_telemetry` [dharma_swarm/operator_bridge.py:1650](../../dharma_swarm/operator_bridge.py#L1650) | D | 21 | Bridge telemetry is rich; facade should call it rather than duplicate it. |
| `TaskBoard.update_task` [dharma_swarm/task_board.py:355](../../dharma_swarm/task_board.py#L355) | C | 11 | Keep status updates behind optimistic locking and event append. |
| `build_control_surface_rows` [dharma_swarm/operator_core/control_surface.py:855](../../dharma_swarm/operator_core/control_surface.py#L855) | C | 13 | Projection can grow to include board rows, but must remain read-only. |

Ruff and Vulture found small pre-existing unused-import rot in
`operator_core/control_surface.py`; no code is changed in this spec PR.

### Existing tests and missing tests

Targeted tests run for this spec pass:

```text
pytest -q tests/test_task_board.py tests/test_operator_bridge.py \
  tests/test_operator_bridge_runtime.py tests/test_operator_bridge_telemetry.py \
  tests/test_runtime_state.py tests/test_roaming_mailbox.py \
  tests/test_roaming_poller.py tests/test_roaming_operator_bridge.py \
  tests/test_roaming_dispatch_daemon.py tests/test_control_surface.py \
  tests/test_intent_router.py tests/test_intent_router_semantic.py \
  tests/test_mission_contract.py tests/test_auto_proposer.py \
  tests/test_recursive_discovery.py tests/test_swarm_health_api.py --tb=short
```

Result: 221 passed, 1 pytest config warning about unknown `timeout`.

Tests that exist:

- `tests/test_task_board.py`
- `tests/test_operator_bridge.py`
- `tests/test_operator_bridge_runtime.py`
- `tests/test_operator_bridge_telemetry.py`
- `tests/test_runtime_state.py`
- `tests/test_roaming_mailbox.py`
- `tests/test_roaming_poller.py`
- `tests/test_roaming_operator_bridge.py`
- `tests/test_roaming_dispatch_daemon.py`
- `tests/test_control_surface.py`
- `tests/test_intent_router.py`
- `tests/test_intent_router_semantic.py`
- `tests/test_mission_contract.py`
- `tests/test_auto_proposer.py`
- `tests/test_recursive_discovery.py`
- `tests/test_swarm_health_api.py`

Tests missing:

- `tests/test_boardstore.py`
- `tests/test_boardstore_event_log.py`
- `tests/test_swarm_client.py`
- `tests/test_boardstore_lifecycle_integration.py`
- `tests/test_boardstore_cohort_e2e.py`
- `tests/test_boardstore_replay.py`
- `tests/test_boardstore_chaos.py`
- `tests/test_boardstore_cost_caps.py`
- `tests/test_boardstore_noticer_contract.py`
- `tests/test_boardstore_adapters.py`

## 3. The Card Schema

The `Card` schema is stable for the next one-to-three years. Additive changes
must go through adapters, capabilities, receipts, or render hints. A new agent
kind, surface, or store must not require changing these fields.

### Type aliases

```python
CardId = NewType("CardId", str)
ObjectiveId = NewType("ObjectiveId", str)
AgentId = NewType("AgentId", str)
LeaseId = NewType("LeaseId", str)
ReceiptId = NewType("ReceiptId", str)
EventId = NewType("EventId", str)
IsoDatetime = NewType("IsoDatetime", str)
MoneyUSD = Decimal
Version = NewType("Version", int)

CardStatus = Literal[
    "inbox",
    "triaged",
    "planned",
    "blocked",
    "claimable",
    "claimed",
    "running",
    "review",
    "done",
    "failed",
    "cancelled",
    "quarantined",
]

AssigneeKind = Literal[
    "human",
    "codex",
    "claude_code",
    "cursor",
    "devin",
    "warp",
    "perplexity",
    "daemon",
    "roaming",
    "unknown",
]

SourceSurface = Literal[
    "dashboard",
    "cli",
    "telegram",
    "github",
    "email",
    "voice",
    "noticer",
    "ci",
    "recursive_discovery",
    "operator_bridge",
    "task_board",
    "runtime_state",
    "api_admin",
    "unknown",
]
```

### Nested objects

```python
class ClaimLease(BaseModel):
    lease_id: LeaseId
    card_id: CardId
    agent_id: AgentId
    agent_kind: AssigneeKind
    claimed_at: IsoDatetime
    heartbeat_at: IsoDatetime | None = None
    expires_at: IsoDatetime
    revoked_at: IsoDatetime | None = None
    revoke_reason: str = ""
    cost_burn_usd: MoneyUSD = Decimal("0.00")
    capability_manifest: dict[str, str | int | float | bool | list[str]] = {}

class AcceptanceCriterion(BaseModel):
    id: str
    text: str
    kind: Literal["test", "doc", "artifact", "manual", "external", "receipt"]
    required: bool = True
    verifier: str = ""
    evidence_ref: str = ""

class ReceiptRef(BaseModel):
    receipt_id: ReceiptId
    kind: str
    store: Literal["runtime_state", "event_log", "roaming_mailbox", "artifact_store", "external"]
    uri: str
    checksum: str = ""
    created_at: IsoDatetime
    summary: str = ""

class AuditEntry(BaseModel):
    event_id: EventId
    actor_id: str
    actor_kind: Literal["operator", "agent", "noticer", "facade", "admin"]
    action: str
    at: IsoDatetime
    idempotency_key: str
    previous_version: Version | None = None
    next_version: Version | None = None
    reason: str = ""

class RenderHints(BaseModel):
    view_priority: int = 0
    color_key: str = ""
    icon_key: str = ""
    column_hint: str = ""
    lane_hint: str = ""
    thread_hint: str = ""
    map_node_kind: str = ""
```

`capability_manifest` and `render_hints` are extension points. They are display
and routing hints, not truth owners. Store-specific native data must remain in
the store adapter and be exposed through `receipt_refs` or store-specific read
methods, not by adding unbounded top-level `Card` fields.

### Card fields

```python
class Card(BaseModel):
    id: CardId
    parent_objective: ObjectiveId | None
    title: str
    body: str
    status: CardStatus
    claim_lease: ClaimLease | None
    assignee_kind: AssigneeKind
    capability_required: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    receipt_refs: list[ReceiptRef]
    cost_ceiling_usd: MoneyUSD
    audit_log: list[AuditEntry]
    version: Version
    idempotency_key: str
    arjuna_weight: float
    created_by: str
    created_at: IsoDatetime
    updated_at: IsoDatetime
    last_transitioned_at: IsoDatetime
    source_surface: SourceSurface
    render_hints: RenderHints
```

| Field | Type | Required | Why it exists | Extension rule |
|---|---|---:|---|---|
| `id` | `CardId` | yes | Stable cross-store identity. It maps to TaskBoard task id, OperatorBridge task id, or facade-generated `card_*` id. | Never reused. Adapter maps native ids through a `card_identities` table. |
| `parent_objective` | `ObjectiveId | None` | yes | Connects work packets to intent trees and cohorts. | New objective stores adapt into this id; no schema change. |
| `title` | `str` | yes | Human and agent scannability. | Max 160 chars in v1 client validation. |
| `body` | `str` | yes | Full work packet, context, constraints, and handoff text. | Large payloads should move to artifact refs once above 32 KiB. |
| `status` | `CardStatus` | yes | Shared lifecycle across all surfaces. | New native statuses map to nearest enum plus receipt/audit detail. |
| `claim_lease` | `ClaimLease | None` | yes | Prevents two agents mutating the same work. | Lease subfields may add optional capability keys only. |
| `assignee_kind` | `AssigneeKind` | yes | Distinguishes Cursor, Codex, Claude Code, daemons, roaming agents, and humans without schema churn. | Unknown future kinds use `unknown` plus capability manifest until enum addition is approved. |
| `capability_required` | `list[str]` | yes | Capability matching independent of vendor. | Capability strings are registry/adaptor owned, e.g. `code.modify`, `research.web`, `slides.pptx`. |
| `acceptance_criteria` | `list[AcceptanceCriterion]` | yes | Prevents "done" without a measurable contract. | Criterion kinds are additive only through verifier adapters. |
| `receipt_refs` | `list[ReceiptRef]` | yes | Keeps verification, artifacts, and handoffs durable without widening Card. | New receipt stores add `store="external"` and URI until first-class adapter exists. |
| `cost_ceiling_usd` | `Decimal` | yes | Cost control must be visible before claim. | Per-card ceiling; cohort ceilings live in cohort state. |
| `audit_log` | `list[AuditEntry]` | yes | Human-readable audit projection. Event log remains the source for replay. | Truncated in list views; full audit via `get_audit_log`. |
| `version` | `int` | yes | Optimistic locking. Every successful write increments by 1. | Never reset during migration. |
| `idempotency_key` | `str` | yes | Dedupes repeated writes from flaky clients and noticers. | Client-generated; facade stores uniqueness by actor + operation + key. |
| `arjuna_weight` | `float` | yes | Encodes world-facing value against the Arjuna test. | Range `[0.0, 1.0]`. Below threshold requires override. |
| `created_by` | `str` | yes | Actor attribution. | Must be a registered agent id, operator id, or facade system actor. |
| `created_at` | ISO string | yes | Replay and ordering. | UTC only. |
| `updated_at` | ISO string | yes | Freshness and sync. | UTC only. |
| `last_transitioned_at` | ISO string | yes | Staleness, lease recovery, and dashboards. | Updated only on status transitions. |
| `source_surface` | `SourceSurface` | yes | Lets multiple surfaces create work without owning schema. | Unknown future surfaces use `unknown` plus audit reason until registered. |
| `render_hints` | `RenderHints` | yes | Allows kanban/map/table/Telegram to render without schema churn. | Views may ignore. Views must not write truth here except through facade. |

### Status mapping

| Card status | TaskBoard | OperatorBridge | RuntimeStateStore | Meaning |
|---|---|---|---|---|
| `inbox` | pending with `metadata.board_status=inbox` | queued | no live claim | Captured but not triaged. Only humans/planners/noticers may create here. |
| `triaged` | pending | queued | no live claim | Work is understood and deduped. |
| `planned` | pending with dependencies | queued | optional delegation run queued | Acceptance criteria and dependencies are known. |
| `blocked` | pending or failed with blocker metadata | queued or in_progress | claim may be stale/recovered | Cannot progress until blocker clears. |
| `claimable` | pending and dependencies satisfied | queued | no active claim | Agents may claim if capability/cost/auth match. |
| `claimed` | assigned | in_progress | task claim `claimed` or `acknowledged` | Lease exists but work may not have started. |
| `running` | running | in_progress | delegation run active | Agent is actively working and heartbeating. |
| `review` | running or completed with review metadata | acknowledged or completed pending ack | artifact/receipt exists | Work is awaiting verification or human spot-check. |
| `done` | completed | done/completed/acknowledged | claim/run closed completed | Acceptance met and receipts landed. |
| `failed` | failed | failed/error | claim/run closed failed | Work failed with receipt or failure reason. |
| `cancelled` | cancelled | cancelled | operator action recorded | Human/facade intentionally stopped work. |
| `quarantined` | cancelled or pending with quarantine metadata | queued or in_progress with admin hold | operator action recorded | Unsafe or contradictory state; only operator/admin can release. |

## 4. The Seven Contracts

Each contract below states non-overlapping truth ownership. If implementation
finds a conflict, the store owner wins for its domain and the facade emits a
projection-conflict event.

### 4.1 TaskBoard contract

**Truth owned**

`TaskBoard` owns task rows, status FSM, priorities, dependencies, ready-task
selection, task metadata, and task result text. Evidence:
`TaskBoard` declares SQLite tasks/dependencies at
[dharma_swarm/task_board.py:28](../../dharma_swarm/task_board.py#L28), valid
transitions at [dharma_swarm/task_board.py:19](../../dharma_swarm/task_board.py#L19),
creation at [dharma_swarm/task_board.py:197](../../dharma_swarm/task_board.py#L197),
listing at [dharma_swarm/task_board.py:331](../../dharma_swarm/task_board.py#L331),
status updates at [dharma_swarm/task_board.py:409](../../dharma_swarm/task_board.py#L409),
and dependencies/readiness at [dharma_swarm/task_board.py:541](../../dharma_swarm/task_board.py#L541).

**Facade reads**

- task rows through `get`, `list_tasks`, `get_ready_tasks`;
- dependency edges through `get_dependencies`;
- status/priority/assigned_to/metadata/result for card projection;
- trace/correlation metadata already persisted in task metadata.

**Facade writes**

- `TaskBoard.create` for cards whose native owner is task state;
- `assign`, `start`, `complete`, `fail`, `cancel`, `requeue` during card
  transitions;
- `add_dependency` when objective decomposition creates card DAGs;
- metadata keys under the reserved namespace `board.*`, never unscoped
  arbitrary metadata.

**Out of facade scope**

- Telos witness internals in `_witness_transition`;
- low-level SQL migrations;
- current CLI thin-path internals;
- direct task-board analytics other than projection.

**Facade signatures for this domain**

```python
async def create_task_card(
    self,
    request: CreateCardRequest,
    *,
    idempotency_key: str,
    actor: ActorRef,
) -> Card: ...

async def set_task_card_status(
    self,
    card_id: CardId,
    status: CardStatus,
    *,
    expected_version: Version,
    idempotency_key: str,
    actor: ActorRef,
    reason: str = "",
) -> Card: ...

async def add_card_dependency(
    self,
    card_id: CardId,
    depends_on_id: CardId,
    *,
    expected_version: Version,
    idempotency_key: str,
    actor: ActorRef,
) -> Card: ...
```

**Migration risk and back-compat**

Risk is medium. TaskBoard is already used by SwarmManager, CLI helpers, and
scripts. Existing calls keep working. BoardStore first reads existing tasks and
writes reserved metadata. Cutover only occurs when `tests/test_task_board.py`,
dashboard task tests, and boardstore lifecycle tests pass.

### 4.2 OperatorBridge contract

**Truth owned**

`OperatorBridge` owns external work-order queue state, claim timeout,
claimed-by identity, heartbeats, partial artifacts, responses, stale recovery,
delivery acknowledgement, and bridge lifecycle telemetry. Evidence:
`operator_bridge_tasks` DDL at
[dharma_swarm/operator_bridge.py:51](../../dharma_swarm/operator_bridge.py#L51),
enqueue at [dharma_swarm/operator_bridge.py:347](../../dharma_swarm/operator_bridge.py#L347),
heartbeat at [dharma_swarm/operator_bridge.py:623](../../dharma_swarm/operator_bridge.py#L623),
partial artifact at [dharma_swarm/operator_bridge.py:689](../../dharma_swarm/operator_bridge.py#L689),
response at [dharma_swarm/operator_bridge.py:820](../../dharma_swarm/operator_bridge.py#L820).

**Facade reads**

- bridge tasks by id/status/sender;
- claim state and `claimed_by`;
- heartbeat/progress metadata;
- response summary, report path, patch path, error;
- delivery acknowledgement state.

**Facade writes**

- enqueue external work-order cards when card source is operator/human;
- claim bridge tasks for clients whose transport is `bridge` or `mailbox`;
- heartbeat progress;
- record partial artifacts;
- respond when an external worker posts a receipt or terminal result;
- acknowledge response on operator acceptance.

**Out of facade scope**

- MessageBus transport details;
- SessionLedger record format;
- TelemetryPlane internals;
- legacy bridge queue compatibility outside current adapter.

**Facade signatures for this domain**

```python
async def create_bridge_card(
    self,
    request: CreateCardRequest,
    *,
    idempotency_key: str,
    actor: ActorRef,
) -> Card: ...

async def claim_bridge_card(
    self,
    card_id: CardId,
    *,
    claim: ClaimRequest,
    idempotency_key: str,
) -> ClaimLease: ...

async def post_bridge_progress(
    self,
    lease_id: LeaseId,
    *,
    summary: str,
    progress: float | None,
    artifact_ref: str | None,
    idempotency_key: str,
) -> Card: ...

async def post_bridge_response(
    self,
    lease_id: LeaseId,
    *,
    receipt: VerificationReceipt,
    idempotency_key: str,
) -> Card: ...
```

**Migration risk and back-compat**

Risk is low to medium. OperatorBridge has fewer importers but is semantically
rich. Existing `RoamingOperatorBridge` must keep working. The facade should call
bridge methods rather than reimplement lifecycle logic.

### 4.3 RuntimeStateStore contract

**Truth owned**

`RuntimeStateStore` owns sessions, claims, delegation runs, workspace leases,
artifacts, memory facts, context bundles, operator actions, and session events.
It declares itself the canonical SQLite runtime state spine
[dharma_swarm/runtime_state.py:1](../../dharma_swarm/runtime_state.py#L1).
Claims/runs/leases DDL begins at
[dharma_swarm/runtime_state.py:43](../../dharma_swarm/runtime_state.py#L43);
recording task claims begins at
[dharma_swarm/runtime_state.py:1115](../../dharma_swarm/runtime_state.py#L1115);
workspace lease and artifact methods begin at
[dharma_swarm/runtime_state.py:1542](../../dharma_swarm/runtime_state.py#L1542);
memory fact methods begin at
[dharma_swarm/runtime_state.py:1727](../../dharma_swarm/runtime_state.py#L1727);
operator actions begin at
[dharma_swarm/runtime_state.py:1955](../../dharma_swarm/runtime_state.py#L1955).

**Facade reads**

- active and historical claims;
- delegation runs;
- workspace leases;
- artifact records;
- memory facts and context bundles relevant to card receipts;
- operator actions/control events.

**Facade writes**

- one `TaskClaim` per successful card claim;
- claim heartbeat, close, recovery, and revocation;
- one `DelegationRun` per executing agent run;
- `WorkspaceLease` when a card reserves paths or zones;
- `ArtifactRecord` for receipts and work products;
- `OperatorAction` for control events;
- `MemoryFact` only when receipt policy explicitly permits write-back.

**Out of facade scope**

- generic runtime state search;
- low-level memory-plane schema;
- existing session-ledger indexing behavior;
- direct mutation of unrelated `MemoryFact` truth state.

**Facade signatures for this domain**

```python
async def mirror_claim_to_runtime(
    self,
    card: Card,
    lease: ClaimLease,
    *,
    idempotency_key: str,
) -> TaskClaim: ...

async def mirror_run_to_runtime(
    self,
    card: Card,
    lease: ClaimLease,
    *,
    requested_output: list[str],
    idempotency_key: str,
) -> DelegationRun: ...

async def record_card_artifact(
    self,
    card_id: CardId,
    receipt: VerificationReceipt,
    *,
    idempotency_key: str,
) -> ReceiptRef: ...

async def record_card_control_action(
    self,
    event: ControlEvent,
    *,
    idempotency_key: str,
) -> OperatorAction: ...
```

**Migration risk and back-compat**

Risk is critical because GitNexus reports 99 impacted symbols and 30 direct
importers. RuntimeStateStore remains authoritative. The facade may only add
new records with stable ids and reserved metadata. No existing runtime table is
renamed in v1.

### 4.4 RoamingMailbox contract

**Truth owned**

`RoamingMailbox` owns git-friendly transport files under `roaming_mailbox/tasks`,
`responses`, and `receipts`. It does not own canonical card truth. Evidence:
file transport is described at
[dharma_swarm/roaming_mailbox.py:1](../../dharma_swarm/roaming_mailbox.py#L1);
task/response dataclasses begin at
[dharma_swarm/roaming_mailbox.py:39](../../dharma_swarm/roaming_mailbox.py#L39);
claim/respond methods begin at
[dharma_swarm/roaming_mailbox.py:160](../../dharma_swarm/roaming_mailbox.py#L160).
The adapter to OperatorBridge says the mailbox is transport, not a second task
system [dharma_swarm/roaming_operator_bridge.py:1](../../dharma_swarm/roaming_operator_bridge.py#L1).

**Facade reads**

- queued/claimed/responded mailbox tasks;
- response files and imported receipts;
- mailbox metadata carrying bridge/card ids.

**Facade writes**

- mailbox task files only when dispatching a bridge-backed card to a remote
  recipient;
- imported receipt files after collecting a response;
- no direct canonical card transitions except by calling facade methods.

**Out of facade scope**

- git fetch/pull/push policy;
- remote responder command execution;
- filesystem conflict resolution beyond idempotent import receipts.

**Facade signatures for this domain**

```python
async def export_card_to_mailbox(
    self,
    card_id: CardId,
    *,
    recipient: str,
    idempotency_key: str,
    actor: ActorRef,
) -> MailboxTask: ...

async def import_mailbox_response(
    self,
    mailbox_task_id: str,
    *,
    responder: str,
    idempotency_key: str,
    actor: ActorRef,
) -> Card: ...
```

**Migration risk and back-compat**

Risk is low. The mailbox stays a transport. Existing `RoamingPoller` and
`RoamingDispatchDaemon` keep their current flow
[dharma_swarm/roaming_poller.py:118](../../dharma_swarm/roaming_poller.py#L118),
[dharma_swarm/roaming_dispatch_daemon.py:116](../../dharma_swarm/roaming_dispatch_daemon.py#L116).

### 4.5 ControlSurface contract

**Truth owned**

ControlSurface owns projections: rows, summaries, evidence labels, freshness,
coherence state, and display hints. It does not own source truth. Evidence:
the module says the manifest is declared intent and observed reality comes from
runtime/code/evidence adapters
[dharma_swarm/operator_core/control_surface.py:1](../../dharma_swarm/operator_core/control_surface.py#L1).
`build_control_surface_rows` reads manifest, code, operating facts, module
truth, broken register, runtime state, and recursive discovery
[dharma_swarm/operator_core/control_surface.py:855](../../dharma_swarm/operator_core/control_surface.py#L855).
The API exposes summary/rows/row/stream as envelope responses
[api/routers/control_surface.py:1](../../api/routers/control_surface.py#L1).

**Facade reads**

- no facade write depends on ControlSurface;
- facade may read rows for operator context and ARJUNA/debug displays.

**Facade writes**

- none to ControlSurface source code or projection rows;
- facade only emits board events that a future ControlSurface adapter can read.

**Out of facade scope**

- deciding truth owner for non-board rows;
- changing row kinds unrelated to board cards;
- dashboard-specific rendering state.

**Facade signatures for this domain**

```python
async def project_cards_for_control_surface(
    self,
    query: CardQuery,
) -> list[ControlSurfaceRowLike]: ...

async def get_cohort_state(
    self,
    cohort_id: str,
) -> CohortState: ...
```

**Migration risk and back-compat**

Risk is medium for UI coherence, low for state. Board rows should be added as a
new projection source. Existing `/api/control-surface/*` endpoints keep their
current response envelope.

### 4.6 IntentRouter and MissionState contract

**Truth owned**

`IntentRouter` owns derived task intent: primary skill, confidence, complexity,
recommended agent count, parallel flag, risk level, tags, and decomposition.
Evidence: `TaskIntent` and `DecomposedTask` are defined at
[dharma_swarm/intent_router.py:163](../../dharma_swarm/intent_router.py#L163);
analysis, explanation, decomposition, and routing are defined at
[dharma_swarm/intent_router.py:370](../../dharma_swarm/intent_router.py#L370).

`MissionState` owns active mission title, thesis, theme, cycle, status, task
count, task titles, delegated task ids, blockers, and prior missions
[dharma_swarm/mission_contract.py:104](../../dharma_swarm/mission_contract.py#L104).
`CompletionContract`, `JudgePack`, and `HonorsCheckpoint` already encode
acceptance and judge information
[dharma_swarm/mission_contract.py:284](../../dharma_swarm/mission_contract.py#L284),
[dharma_swarm/mission_contract.py:409](../../dharma_swarm/mission_contract.py#L409).

**Facade reads**

- decomposed work packets from `IntentRouter.decompose`;
- skill/risk/capability hints from `TaskIntent`;
- active mission state for `parent_objective`, title context, and cohort state;
- completion contract fields to seed `acceptance_criteria`.

**Facade writes**

- cards generated from decomposed tasks;
- no direct mutation of mission JSON except through existing mission contract
  helpers if a separate mission-state feature owns that change.

**Out of facade scope**

- changing routing heuristics;
- altering mission history policy;
- making mission state a task board.

**Facade signatures for this domain**

```python
async def create_objective_cards(
    self,
    objective: ObjectiveCreate,
    *,
    idempotency_key: str,
    actor: ActorRef,
) -> ObjectiveTree: ...

async def get_objective_tree(
    self,
    objective_id: ObjectiveId,
) -> ObjectiveTree: ...
```

**Migration risk and back-compat**

Risk is medium. IntentRouter is pure and easy to call; mission state is shared
with broader runtime flows. BoardStore must treat mission state as context and
only create cards unless a future ADR approves write-back.

### 4.7 AutoProposer and recursive_discovery contract

**Truth owned**

`AutoProposer` owns observations and proposal records, not execution. It
observes sources concurrently
[dharma_swarm/auto_proposer.py:505](../../dharma_swarm/auto_proposer.py#L505),
maps observations to proposal parameters
[dharma_swarm/auto_proposer.py:540](../../dharma_swarm/auto_proposer.py#L540),
and can submit proposals to DarwinEngine today
[dharma_swarm/auto_proposer.py:783](../../dharma_swarm/auto_proposer.py#L783).
The facade contract intentionally does not expose that submit path to noticers.

`recursive_discovery` owns shadow receipts for limitations, generated evals,
candidate diffs, experiment results, witness verdicts, and promotion decisions.
It explicitly does not apply diffs or mutate runtime code
[dharma_swarm/recursive_discovery.py:1](../../dharma_swarm/recursive_discovery.py#L1).
It writes receipt envelopes to `EventLog`
[dharma_swarm/recursive_discovery.py:172](../../dharma_swarm/recursive_discovery.py#L172).

**Facade reads**

- AutoProposer observations and proposal descriptions;
- recursive receipt summaries and content hashes;
- noticer source signals from CI, active-track TTL, manifest health, PR age,
  broken register changes, and recursive shadow receipts.

**Facade writes**

- cards in `inbox` or `triaged` only;
- noticer audit events with reasoning;
- dedupe/rank updates that do not claim or execute work.

**Out of facade scope**

- DarwinEngine submission from noticer mode;
- applying candidate diffs;
- mutating code;
- pushing/merging branches;
- autonomous external side effects.

**Facade signatures for this domain**

```python
async def create_notice_card(
    self,
    notice: NoticeInput,
    *,
    idempotency_key: str,
    actor: ActorRef,
) -> Card: ...

async def dedupe_notice_cards(
    self,
    notice: NoticeInput,
    *,
    threshold: float = 0.86,
) -> DedupeResult: ...

async def rank_notice_cards(
    self,
    query: NoticeRankQuery,
) -> list[RankedCard]: ...
```

**Migration risk and back-compat**

Risk is high if the notice/do boundary is blurred, low if it is encoded in
types. The noticer client must have a restricted capability token that cannot
call claim, transition past `triaged`, post receipt, post handoff, or post
control events other than a noticer-scoped annotation.

## 5. The BoardStore Facade Interface

### Core request and result types

```python
class ActorRef(BaseModel):
    actor_id: str
    actor_kind: Literal["operator", "agent", "noticer", "facade", "admin"]
    assignee_kind: AssigneeKind = "unknown"
    display_name: str = ""
    auth_subject: str = ""

class CardQuery(BaseModel):
    statuses: list[CardStatus] = []
    assignee_kind: AssigneeKind | None = None
    capability_any: list[str] = []
    source_surface: SourceSurface | None = None
    parent_objective: ObjectiveId | None = None
    created_by: str | None = None
    updated_after: IsoDatetime | None = None
    limit: int = 100
    cursor: str = ""

class CreateCardRequest(BaseModel):
    parent_objective: ObjectiveId | None = None
    title: str
    body: str
    source_surface: SourceSurface
    capability_required: list[str] = []
    acceptance_criteria: list[AcceptanceCriterion] = []
    cost_ceiling_usd: MoneyUSD = Decimal("0.00")
    arjuna_weight: float
    render_hints: RenderHints = RenderHints()
    initial_status: CardStatus = "inbox"

class ClaimRequest(BaseModel):
    card_id: CardId | None = None
    capabilities: list[str]
    agent_id: AgentId
    agent_kind: AssigneeKind
    lease_seconds: int = 1800
    projected_cost_usd: MoneyUSD = Decimal("0.00")
    cohort_id: str = ""

class TransitionRequest(BaseModel):
    card_id: CardId
    to_status: CardStatus
    expected_version: Version
    reason: str = ""

class HandoffPayload(BaseModel):
    from_lease_id: LeaseId
    to_agent_kind: AssigneeKind | None = None
    to_capability: list[str] = []
    summary: str
    artifact_refs: list[ReceiptRef] = []
    next_status: CardStatus = "claimable"
```

### Read methods

```python
class BoardStore(Protocol):
    async def list_cards(self, query: CardQuery) -> Page[Card]: ...
    async def get_card(self, card_id: CardId) -> Card | None: ...
    async def watch_cards(
        self,
        query: CardQuery,
        *,
        after_event_id: EventId | None = None,
    ) -> AsyncIterator[BoardEvent]: ...
    async def get_lease(self, lease_id: LeaseId) -> ClaimLease | None: ...
    async def get_receipt(self, receipt_id: ReceiptId) -> VerificationReceipt | None: ...
    async def get_audit_log(
        self,
        card_id: CardId,
        *,
        limit: int = 200,
    ) -> list[AuditEntry]: ...
    async def get_objective_tree(self, objective_id: ObjectiveId) -> ObjectiveTree: ...
    async def get_cohort_state(self, cohort_id: str) -> CohortState: ...
```

### Write methods

Every write takes `idempotency_key`. Every write records a `BoardEvent`. Every
write either succeeds atomically or returns a typed error.

```python
    async def create_card(
        self,
        request: CreateCardRequest,
        *,
        actor: ActorRef,
        idempotency_key: str,
    ) -> Card: ...

    async def claim_card(
        self,
        request: ClaimRequest,
        *,
        actor: ActorRef,
        idempotency_key: str,
    ) -> ClaimLease: ...

    async def heartbeat_claim(
        self,
        lease_id: LeaseId,
        *,
        actor: ActorRef,
        idempotency_key: str,
        progress: float | None = None,
        summary: str = "",
        incremental_cost_usd: MoneyUSD = Decimal("0.00"),
    ) -> ClaimLease: ...

    async def release_claim(
        self,
        lease_id: LeaseId,
        *,
        actor: ActorRef,
        idempotency_key: str,
        terminal_status: Literal["done", "failed", "cancelled"] | None = None,
        reason: str = "",
    ) -> Card: ...

    async def transition_card(
        self,
        request: TransitionRequest,
        *,
        actor: ActorRef,
        idempotency_key: str,
    ) -> Card: ...

    async def post_receipt(
        self,
        card_id: CardId,
        receipt: VerificationReceipt,
        *,
        actor: ActorRef,
        expected_version: Version,
        idempotency_key: str,
    ) -> Card: ...

    async def post_handoff(
        self,
        card_id: CardId,
        handoff: HandoffPayload,
        *,
        actor: ActorRef,
        expected_version: Version,
        idempotency_key: str,
    ) -> Card: ...

    async def post_control_event(
        self,
        event: ControlEvent,
        *,
        actor: ActorRef,
        idempotency_key: str,
    ) -> ControlEventResult: ...
```

### Idempotency rules

- Idempotency key scope is `(actor_id, operation, idempotency_key)`.
- Repeating the same write with byte-identical payload returns the original
  result.
- Reusing a key with a different payload returns `IdempotencyConflict`.
- Client-generated keys must be deterministic for retries and unique for new
  intent, e.g. `sha256(actor_id + operation + source_ref + payload_hash)`.
- The facade stores idempotency records in a local SQLite table:

```sql
CREATE TABLE board_idempotency (
    actor_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_event_id TEXT NOT NULL,
    result_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (actor_id, operation, idempotency_key)
);
```

### Optimistic locking

- Every `Card` has `version`.
- Any write that mutates card state, receipts, handoffs, render hints, or
  status must include `expected_version`, except `claim_card`, which locks by
  lease acquisition.
- If the stored projection version differs from `expected_version`, return
  `VersionConflict(current_card=...)`.
- Successful writes increment `version` by exactly 1 and append an event with
  `previous_version` and `next_version`.

### Append-only event log

The existing `EventLog` is append-only JSONL over `RuntimeEnvelope`
[dharma_swarm/event_log.py:1](../../dharma_swarm/event_log.py#L1). It validates
runtime envelopes and can verify streams
[dharma_swarm/event_log.py:33](../../dharma_swarm/event_log.py#L33). BoardStore
uses that contract for board events, under stream `board`.

`BoardEvent` payload:

```python
class BoardEvent(BaseModel):
    schema_version: Literal["board.event.v1"] = "board.event.v1"
    event_id: EventId
    card_id: CardId | None
    objective_id: ObjectiveId | None = None
    cohort_id: str = ""
    event_type: Literal[
        "card.created",
        "card.claimed",
        "claim.heartbeat",
        "claim.released",
        "card.transitioned",
        "receipt.posted",
        "handoff.posted",
        "control.posted",
        "noticer.deduped",
        "noticer.ranked",
        "projection.conflict",
        "replay.snapshot",
    ]
    actor: ActorRef
    idempotency_key: str
    previous_version: Version | None = None
    next_version: Version | None = None
    store_refs: list[StoreRef] = []
    payload: dict[str, Any]
    emitted_at: IsoDatetime
```

`RuntimeEnvelope.create` already provides event id, event type, emitted time,
source, agent id, session id, trace id, payload, and checksum
[dharma_swarm/runtime_contract.py:40](../../dharma_swarm/runtime_contract.py#L40).
The board event is stored inside `payload`.

Retention:

- JSONL board events are retained indefinitely.
- Snapshot compaction is allowed only as an optimization. It never replaces the
  raw event stream for audit.
- Snapshot cadence starts at every 500 events or 10 minutes, whichever comes
  first.
- Replay must be possible from event 0 plus store adapters, or from latest
  snapshot plus events after snapshot.

Replay semantics:

1. Load native store rows through adapters.
2. Load `board` event stream sorted by `(emitted_at, event_id)`.
3. Apply events idempotently by `event_id`.
4. Rebuild card projection and versions.
5. Compare projection hash with the latest snapshot hash.
6. Emit `projection.conflict` if native store state contradicts event-derived
   state.

### Failure modes and recovery

| Failure | Facade behavior | Recovery |
|---|---|---|
| SQLite busy/locked | Retry with bounded exponential backoff and jitter. | Existing TaskBoard uses WAL and busy timeout [dharma_swarm/task_board.py:84](../../dharma_swarm/task_board.py#L84); facade does the same. |
| Idempotency replay | Return original result if request hash matches. | No new event. |
| Idempotency conflict | Return permanent error. | Caller must generate a new key or resend identical payload. |
| Version conflict | Return current card. | Client reloads, merges, retries with new version. |
| Lease expired | Reject heartbeat/release from old lease. | Card returns to `claimable` unless cancelled/quarantined. |
| STOP sentinel present | Reject claim/heartbeat/transition to running. | Operator removes sentinel and posts `resume`. |
| Cost ceiling exceeded | Reject claim or heartbeat. | Operator raises ceiling or card transitions to review/blocked. |
| Native store write succeeds but event append fails | Facade writes a compensating `projection.conflict` on next startup; until then card is quarantined. | Replay scanner reconciles native row and event log. |
| Event append succeeds but native write fails | Event carries failure result and card stays prior version. | Retry or operator quarantine. |

## 6. The dharma_swarm.client Library

### Public API

`dharma_swarm.client` is small and typed. It is the only documented write path
for agents.

```python
class SwarmClient:
    @classmethod
    def from_env(
        cls,
        *,
        agent_uid: str | None = None,
        agent_kind: AssigneeKind = "unknown",
        transport: Literal["local", "http", "mailbox"] = "local",
    ) -> "SwarmClient": ...

    async def create_card(
        self,
        title: str,
        body: str,
        *,
        parent_objective: str | None = None,
        source_surface: SourceSurface = "cli",
        capability_required: list[str] = [],
        acceptance_criteria: list[AcceptanceCriterion] = [],
        cost_ceiling_usd: Decimal = Decimal("0.00"),
        arjuna_weight: float,
        idempotency_key: str | None = None,
    ) -> Card: ...

    async def list_cards(self, query: CardQuery | None = None) -> Page[Card]: ...
    async def get_card(self, card_id: str) -> Card: ...
    async def claim_next(
        self,
        *,
        capabilities: list[str],
        cohort_id: str = "",
        projected_cost_usd: Decimal = Decimal("0.00"),
        lease_seconds: int = 1800,
        idempotency_key: str | None = None,
    ) -> ClaimedCard | None: ...
    async def claim_card(
        self,
        card_id: str,
        *,
        capabilities: list[str],
        projected_cost_usd: Decimal = Decimal("0.00"),
        lease_seconds: int = 1800,
        idempotency_key: str | None = None,
    ) -> ClaimedCard: ...
    async def heartbeat(
        self,
        lease_id: str,
        *,
        progress: float | None = None,
        summary: str = "",
        incremental_cost_usd: Decimal = Decimal("0.00"),
        idempotency_key: str | None = None,
    ) -> ClaimLease: ...
    async def release(
        self,
        lease_id: str,
        *,
        terminal_status: Literal["done", "failed", "cancelled"] | None = None,
        reason: str = "",
        idempotency_key: str | None = None,
    ) -> Card: ...
    async def transition(
        self,
        card_id: str,
        to_status: CardStatus,
        *,
        expected_version: int,
        reason: str = "",
        idempotency_key: str | None = None,
    ) -> Card: ...
    async def post_receipt(
        self,
        card_id: str,
        receipt: VerificationReceipt,
        *,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> Card: ...
    async def post_handoff(
        self,
        card_id: str,
        handoff: HandoffPayload,
        *,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> Card: ...
```

`ClaimedCard`:

```python
class ClaimedCard(BaseModel):
    card: Card
    lease: ClaimLease
```

### Auth model

Authentication is local-first and capability-bound.

| Actor | Identity source | Client auth | Allowed writes |
|---|---|---|---|
| Operator | local user or dashboard session | `DHARMA_OPERATOR_TOKEN` or local socket | all non-admin writes, control events |
| Codex | agent uid + harness token | `DHARMA_AGENT_TOKEN`, `agent_kind=codex` | claim, heartbeat, receipts, handoff, release |
| Claude Code | agent uid + harness token | `agent_kind=claude_code` | same as Codex |
| Cursor | agent uid + harness token or local plugin token | `agent_kind=cursor` | same as Codex |
| Devin/Warp/Perplexity | remote token or mailbox identity | `agent_kind` specific | constrained by capability grant |
| Noticer | restricted noticer token | `actor_kind=noticer` | create/dedupe/rank only |
| Facade | internal service account | local-only | projection, recovery, replay, quarantine |
| Admin | explicit admin token | `actor_kind=admin` | migration and repair |

The token grants capabilities, not trust in the executable. Every write is still
schema-validated, idempotent, audited, and cost-gated.

### Schema validation

- The client validates request models before transport.
- The facade validates again before write.
- Raw dict writes are not exposed.
- Unknown fields are rejected by default.
- `arjuna_weight`, `cost_ceiling_usd`, `title`, `status`, and
  `idempotency_key` are never silently defaulted on create.

### Lease lifecycle

1. `claim_next` or `claim_card` requests a lease with capabilities and projected
   cost.
2. Facade checks STOP sentinel, status, capability match, cost ceilings, noticer
   restrictions, and existing live lease.
3. Facade writes native claim state (`TaskBoard.assign`,
   `OperatorBridge.claim_task`, `RuntimeStateStore.record_task_claim`).
4. Facade appends `card.claimed`.
5. Agent heartbeats before `expires_at`.
6. On heartbeat, facade updates runtime claim heartbeat and cost burn.
7. On expiry, the card becomes `claimable` unless paused/cancelled/quarantined.
8. On revocation, future heartbeat/release returns `LeaseRevoked`.

### Cost ceiling enforcement

- Per-card: `cost_ceiling_usd`.
- Per-cohort: `CohortState.cost_ceiling_usd`.
- Per-agent optional cap from auth grant.
- `claim_card` refuses if `projected_cost_usd > remaining_card_budget`.
- `heartbeat_claim` refuses if `current_burn + incremental_cost_usd` exceeds
  card or cohort ceiling.
- Rejected cost events append an audit entry and return `CostCeilingExceeded`.

### Idempotency-key generation

Client defaults:

```python
def default_idempotency_key(actor_id: str, operation: str, payload: BaseModel) -> str:
    canonical = payload.model_dump_json(sort_keys=True)
    return sha256(f"{actor_id}:{operation}:{canonical}".encode()).hexdigest()
```

For create calls from external surfaces, include the source id:
`telegram:<chat_id>:<message_id>`, `github:<repo>:<issue_or_pr>:<comment_id>`,
or `mailbox:<task_id>:<response_path_hash>`.

### Retry and backoff

- Retry transient errors: `SQLiteBusy`, `TransportUnavailable`, `Timeout`,
  `EventAppendRace`, HTTP 429/503.
- Do not retry permanent errors: `ValidationError`, `AuthDenied`,
  `CapabilityDenied`, `ArjunaRejected`, `CostCeilingExceeded`,
  `IdempotencyConflict`.
- Version conflicts may retry only after refetch and caller-provided merge.
- Default backoff: 100 ms, 250 ms, 500 ms, 1 s, 2 s, max 5 attempts, jittered.
- Heartbeats retry more aggressively but stop before lease expiry minus 5 sec.

### Error taxonomy

```python
class BoardError(Exception): ...
class TransientBoardError(BoardError): ...
class PermanentBoardError(BoardError): ...
class ContractViolation(BoardError): ...

class SQLiteBusy(TransientBoardError): ...
class TransportUnavailable(TransientBoardError): ...
class VersionConflict(PermanentBoardError): ...
class IdempotencyConflict(PermanentBoardError): ...
class ValidationFailed(ContractViolation): ...
class AuthDenied(ContractViolation): ...
class CapabilityDenied(ContractViolation): ...
class NoticerForbidden(ContractViolation): ...
class ArjunaRejected(ContractViolation): ...
class CostCeilingExceeded(ContractViolation): ...
class LeaseExpired(PermanentBoardError): ...
class LeaseRevoked(PermanentBoardError): ...
class KillSwitchActive(PermanentBoardError): ...
```

### Test harness for agent authors

The client package must ship:

```python
class BoardClientHarness:
    async def make_temp_store(self) -> BoardStore: ...
    async def register_agent(self, kind: AssigneeKind, capabilities: list[str]) -> SwarmClient: ...
    async def assert_can_claim_and_complete(self, client: SwarmClient) -> None: ...
    async def assert_notices_cannot_claim(self, client: SwarmClient) -> None: ...
```

Agent authors verify by running:

```text
python -m dharma_swarm.client.harness --agent-kind codex --capability code.modify
```

Success proves schema validation, auth identity, idempotency, claim, heartbeat,
receipt, and release against a temporary local store.

## 7. Control Plane Contract

### Control event schema

```python
ControlEventType = Literal[
    "pause",
    "resume",
    "cancel",
    "reassign",
    "revoke_lease",
    "quarantine",
    "kill_cohort",
    "raise_cost_ceiling",
    "drop_cost_ceiling",
]

class ControlEvent(BaseModel):
    event_type: ControlEventType
    card_id: CardId | None = None
    cohort_id: str = ""
    lease_id: LeaseId | None = None
    reason: str
    payload: dict[str, Any] = {}
    expected_version: Version | None = None
```

### Who can emit

| Event | Operator | Agent | Noticer | Facade | Admin |
|---|---:|---:|---:|---:|---:|
| `pause` | yes | no | no | yes, recovery only | yes |
| `resume` | yes | no | no | no | yes |
| `cancel` | yes | current claimant can request only | no | yes, expired unsafe lease only | yes |
| `reassign` | yes | no | no | no | yes |
| `revoke_lease` | yes | no | no | yes, expiry/cost/kill only | yes |
| `quarantine` | yes | no | no | yes, projection conflict only | yes |
| `kill_cohort` | yes | no | no | yes, STOP sentinel only | yes |
| `raise_cost_ceiling` | yes | no | no | no | yes |
| `drop_cost_ceiling` | yes | no | no | yes, policy only | yes |

Noticers cannot emit control events. They may create a notice card that
recommends a control action.

### Propagation semantics

- `pause`: card status becomes `blocked`; active lease remains recorded but
  heartbeat returns `Paused`. Agent must stop work and may post a receipt with
  partial state.
- `resume`: paused card returns to prior claimable/claimed state if lease is
  still valid; otherwise `claimable`.
- `cancel`: card becomes `cancelled`; active lease is revoked; future receipts
  are rejected unless marked `late_cancelled`.
- `reassign`: current lease revoked; card becomes `claimable` with new
  capability/assignee hints.
- `revoke_lease`: active lease gets `revoked_at`; card becomes `claimable`,
  `blocked`, or `quarantined` depending on reason.
- `quarantine`: card becomes `quarantined`; only operator/admin can change it.
- `kill_cohort`: facade creates STOP sentinel and rejects all claims/heartbeats
  for cohort.
- `raise_cost_ceiling` / `drop_cost_ceiling`: updates cohort/card budget and
  appends audit.

### Kill switch

Kill switch is file and facade enforced:

```text
~/.dharma/cohorts/<cohort_id>/STOP
```

Rules:

- If STOP exists, `claim_card` for that cohort returns `KillSwitchActive`.
- If STOP exists, `heartbeat_claim` returns `KillSwitchActive` and revokes the
  lease.
- If STOP exists, `transition_card` to `running` or `claimed` is rejected.
- If STOP exists, `post_receipt` is allowed only for `partial`, `failure`, or
  `stopped` receipts.
- Removing STOP does not resume work. Operator must emit `resume`.

### Cost cap

Facade refuses claim if projected cost exceeds remaining card or cohort budget.
Facade refuses heartbeat if incremental cost would exceed remaining budget. A
claim that crosses 80 percent of budget emits alert metric
`board.cost_ceiling.approaching`.

## 8. Noticer Contract

The noticer is a restricted client role, not a daemon with special back doors.
This contract is enforced by auth grants and method allowlists.

### Allowed actions

- `create_card` with `source_surface="noticer"` and status `inbox` or
  `triaged`;
- `dedupe_cards` by idempotency key and semantic similarity;
- `rank_cards` by explicit signals;
- append noticer audit reason to cards it created;
- refresh a notice card with new evidence refs while it remains not claimed.

### Forbidden actions

- `claim_card`;
- `heartbeat_claim`;
- `release_claim`;
- transition past `triaged`;
- `post_receipt`;
- `post_handoff`;
- file edits;
- shell commands that mutate repo or external systems;
- `git push`, PR merge, or branch deletion;
- direct Darwin/evolution submission;
- external side effects with money or user-facing messaging.

### Ranking signals

No learned ranking in v1. Ranking is a deterministic weighted sum of explicit
signals:

| Signal | Range | Source |
|---|---:|---|
| `arjuna_weight` | 0.0-1.0 | card field |
| `recency` | 0.0-1.0 | card/event timestamps |
| `blocker_proximity` | 0.0-1.0 | whether card unblocks active track, CI, or claimed work |
| `vision_file_proximity` | 0.0-1.0 | citation proximity to active vision/doctrine files |
| `ci_signal` | 0.0-1.0 | failing check severity or PR blocker |

Default formula:

```text
rank = 0.40*arjuna_weight
     + 0.20*blocker_proximity
     + 0.15*ci_signal
     + 0.15*vision_file_proximity
     + 0.10*recency
```

### Dedupe strategy

1. If `(source_surface, source_ref)` idempotency key matches, return original.
2. Else compute semantic similarity over normalized title/body/evidence refs.
3. If similarity >= 0.86 and capability/acceptance overlap >= 0.50, mark as
   duplicate.
4. Append `noticer.deduped` audit event with compared ids and score.
5. Never delete duplicate cards automatically. Mark duplicate and link.

### Audit trail

Every noticer action logs:

- observed signal;
- source refs;
- ranking inputs;
- dedupe comparison ids;
- reason for create/update;
- explicit statement that noticer did not claim or execute.

## 9. Verification and Receipts

### VerificationReceipt schema

```python
class VerificationReceipt(BaseModel):
    schema_version: Literal["board.verification_receipt.v1"] = "board.verification_receipt.v1"
    receipt_id: ReceiptId
    card_id: CardId
    lease_id: LeaseId | None = None
    produced_by: str
    produced_at: IsoDatetime
    receipt_kind: Literal[
        "deterministic_check",
        "llm_judge",
        "human_spot_check",
        "artifact",
        "handoff",
        "failure",
        "partial",
        "stopped",
    ]
    verdict: Literal["passed", "warned", "failed", "blocked", "recorded"]
    summary: str
    acceptance_criteria_ids: list[str]
    artifact_refs: list[str] = []
    commands: list[CommandReceipt] = []
    judge_refs: list[JudgeRef] = []
    cost_usd: MoneyUSD = Decimal("0.00")
    wall_time_seconds: float | None = None
    memory_write_policy: Literal["none", "candidate_fact", "verified_fact"] = "none"
    checksum: str
```

`recursive_discovery` already has a receipt pattern with receipt type, content
hash, files touched, commands, witness verdicts, rollback pointer, and status
[dharma_swarm/recursive_discovery.py:78](../../dharma_swarm/recursive_discovery.py#L78).
Board receipts generalize that structure for cards.

### Multi-judge orchestration

Current `quality_gates.py` supports structural checks and one LLM-as-judge
path. It defines rubrics and `QualityGate.evaluate`
[dharma_swarm/quality_gates.py:1](../../dharma_swarm/quality_gates.py#L1),
[dharma_swarm/quality_gates.py:566](../../dharma_swarm/quality_gates.py#L566).
BoardStore v1 does not replace it. It specifies a path to triangulation:

1. Deterministic check: tests, lint, schema validation, file existence, command
   exit codes.
2. LLM judge: one or more model/provider judges using existing quality gates.
3. Human spot-check: required for high-risk, high-cost, external-user-impact,
   security, or vulnerable-person cards.

Receipt policy:

- Low-risk cards may complete with deterministic receipt only if acceptance
  criteria allow it.
- Medium-risk cards require deterministic receipt plus either LLM judge or
  explicit no-judge reason.
- High-risk cards require deterministic receipt plus LLM judge plus human
  spot-check or explicit operator override.
- `done` without any receipt is rejected unless card carries a
  `no_check_reason` acceptance criterion.

### Replay harness

Given `card_id`:

1. Read native store rows from adapters.
2. Read `board` events filtered by `card_id`.
3. Rebuild projected `Card` from creation through terminal state.
4. Load receipt refs and verify receipt checksums.
5. Re-run deterministic commands only if marked reproducible and safe.
6. Compare final replay projection with current `get_card`.
7. Return `ReplayReport`.

```python
class ReplayReport(BaseModel):
    card_id: CardId
    replayed_events: int
    receipt_count: int
    state_matches: bool
    receipt_checksums_match: bool
    non_replayable_steps: list[str] = []
    conflicts: list[str] = []
```

### Memory write-back

Only receipts with `memory_write_policy="verified_fact"` may mutate
`RuntimeStateStore.record_memory_fact`
[dharma_swarm/runtime_state.py:1727](../../dharma_swarm/runtime_state.py#L1727).

Rules:

- Deterministic test receipts do not write memory by default.
- Failure receipts may write candidate facts only when they describe a stable
  failure signature.
- LLM judge receipts never become verified facts alone.
- Human spot-check may promote candidate to verified fact.
- Recursive-discovery receipts can write candidate facts, as existing
  `EvaluationRegistry` tests already assert
  [tests/test_recursive_discovery.py:110](../../tests/test_recursive_discovery.py#L110).

## 10. Surfaces and Their Contracts

Surfaces are read-only projections by default. Any state change they initiate
goes through `dharma_swarm.client` or a facade-owned admin adapter.

### Kanban view

Location: existing dashboard under `dashboard/`. The current task table already
renders tasks and opens a create-task dialog
[dashboard/src/app/dashboard/tasks/page.tsx:36](../../dashboard/src/app/dashboard/tasks/page.tsx#L36).

Contract:

- Reads `list_cards`.
- Groups by `Card.status`.
- Shows title, assignee, claim lease, blockers, receipt count, cost burn, and
  arjuna weight.
- Drag/drop is not a direct write. It calls `client.transition`.
- Claim buttons call `client.claim_card`.
- Pause/cancel/reassign controls call `post_control_event`.

### Map view

Existing map-like surfaces include `signal_map.py`, which tracks semantic
density and agent briefing context
[dharma_swarm/signal_map.py:1](../../dharma_swarm/signal_map.py#L1), plus
ecosystem/living map modules. Board map is a projection over objectives, cards,
claims, receipts, and dependencies.

Contract:

- Reads `get_objective_tree` and `get_cohort_state`.
- Renders nodes and edges.
- No direct mutations.
- Node actions call client methods.

### Dashboard table view

The existing table can continue as the dense work queue. Contract:

- Reads `list_cards`.
- Keeps current `/api/commands/tasks` compatibility until cutover
  [api/routers/commands.py:56](../../api/routers/commands.py#L56).
- New board table uses `/api/board/cards` or equivalent facade route.
- Create task dialog migrates to `client.create_card`.

### CLI view

`dgc task create/list` currently uses the thin TaskBoard path without booting
the full swarm [dharma_swarm/terminal_commands/agents.py:88](../../dharma_swarm/terminal_commands/agents.py#L88),
[dharma_swarm/terminal_commands/_helpers.py:155](../../dharma_swarm/terminal_commands/_helpers.py#L155).

Contract:

- `dgc board list`, `dgc board claim`, `dgc board receipt`, and `dgc board
  control` use `SwarmClient`.
- Existing `dgc task` remains backward compatible until cutover.
- CLI output is a view, not a store.

### Telegram thread view

Telegram adapter already receives text and can send responses
[dharma_swarm/gateway/telegram.py:57](../../dharma_swarm/gateway/telegram.py#L57).

Contract:

- Incoming text normalizes to `CreateCardRequest` or `ObjectiveCreate`.
- Message id becomes idempotency source.
- Thread id maps to `parent_objective` or cohort.
- Replies render card state.
- Mutations require authorized operator or registered agent identity.

## 11. ARJUNA Gate Integration

The Arjuna test is doctrine, but the gate must be code. Doctrine defines the
test at [docs/doctrine/OPERATIONAL_DOCTRINE.md:52](../doctrine/OPERATIONAL_DOCTRINE.md#L52):
before a build, hook, skill, plan, doc, or agent, ask whether it points at
something broken in the world.

Rules:

- Every `Card` carries `arjuna_weight` in `[0.0, 1.0]`.
- Default threshold: `0.35`.
- `create_card` refuses `arjuna_weight < threshold` unless `override` is
  supplied by operator/admin.
- Noticer cannot override.
- Agents cannot override.
- Override creates `control.posted` with event type `arjuna_override`.
- Override reason must name external user, dataset, partner, measurable impact,
  or active-track dependency.

Suggested scoring:

| Weight | Meaning |
|---:|---|
| `0.00-0.19` | Internal recursion, no named external target. Reject. |
| `0.20-0.34` | Possible indirect value. Needs operator override. |
| `0.35-0.59` | Plausible substrate or operational value linked to active work. Accept. |
| `0.60-0.84` | Clear external-user, funding, impact, or safety leverage. Prioritize. |
| `0.85-1.00` | Directly blocks or enables real-world action, vulnerable-person safety, revenue, or high-leverage external work. Highest priority. |

The gate does not force every card to be outward-facing product work. It allows
infrastructure only when the causal link to outward action is explicit and
auditable.

## 12. Adapter Strategy

Adapters are translators. They are never truth owners.

### A2A adapter

External alignment target:
<https://a2aproject.github.io/A2A/latest/specification/>

Local evidence: `AgentCard` already maps local identity to a simplified A2A
agent card with capabilities, endpoint, auth type, role, model, provider, and
status [dharma_swarm/a2a/agent_card.py:67](../../dharma_swarm/a2a/agent_card.py#L67).

Spec:

```python
class A2ABoardAdapter:
    def card_to_a2a_task(self, card: Card) -> dict[str, Any]: ...
    def receipt_to_a2a_artifact(self, receipt: VerificationReceipt) -> dict[str, Any]: ...
    def agent_identity_to_agent_card(self, actor: ActorRef) -> dict[str, Any]: ...
```

Rules:

- A2A ids carry `card.id` in metadata.
- A2A task status maps from `CardStatus`.
- Incoming A2A task updates call `SwarmClient`, not native stores.
- Exact compliance can be a later ADR after local board semantics are proven.

### MCP adapter

External alignment target:
<https://modelcontextprotocol.io/specification/2025-06-18>

Spec:

- Expose read resources: `board://cards`, `board://cards/{id}`,
  `board://objectives/{id}`, `board://cohorts/{id}`.
- Expose write tools only through schema-gated facade calls:
  `create_card`, `claim_card`, `heartbeat_claim`, `post_receipt`,
  `post_handoff`, `post_control_event`.
- Tool output is untrusted until validated.
- MCP caller identity maps to `ActorRef`.
- MCP never receives direct SQLite handles or raw native store writes.

### AG-UI adapter

External alignment target:
<https://docs.ag-ui.com/>

Spec:

```python
class AgUiBoardAdapter:
    def board_event_to_agui_event(self, event: BoardEvent) -> dict[str, Any]: ...
    def card_stream(self, query: CardQuery) -> AsyncIterator[dict[str, Any]]: ...
```

Rules:

- AG-UI renders board event streams for dashboard and agent activity.
- It does not own card state.
- UI-originated commands call `SwarmClient` and return resulting board events.

### OpenTelemetry GenAI spans

External alignment target:
<https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/>

Every facade method emits spans. Adapter spans include protocol name, transport,
agent kind, card id, cohort id, event id, and cost.

## 13. Migration Plan

### Step 0: spec registration

Files touched:

- add `docs/architecture/SWARM_BOARDSTORE_SPEC.md`;
- update `docs/architecture/README.md` with a depth pointer;
- update `docs/docops/assertions.yaml` registered docs list.

Lines added: spec only. Lines removed: none except incidental generated counts
if DocOps requires refresh.

Cutover criteria: DocOps and governance checks pass.

Rollback: remove the spec and registration entries.

### Step 1: facade scaffolding

Files to add:

- `dharma_swarm/board/__init__.py`
- `dharma_swarm/board/models.py`
- `dharma_swarm/board/store.py`
- `dharma_swarm/board/events.py`
- `tests/test_boardstore.py`

Expected size: 250-450 LOC plus tests.

Back-compat: no existing call path changes.

Cutover criteria:

- model validation tests;
- event log append/replay tests;
- no imports from SwarmManager/AgentRunner.

Rollback: delete new package and tests.

### Step 2: Card schema

Files touched:

- `dharma_swarm/board/models.py`
- `tests/test_boardstore.py`
- `tests/test_boardstore_event_log.py`

Back-compat: no existing store changes.

Cutover criteria:

- all fields validated;
- extension rules tested;
- idempotency key hashing tested.

Rollback: delete new models.

### Step 3: first store adapter, TaskBoard

Files touched:

- `dharma_swarm/board/adapters/task_board.py`
- `dharma_swarm/board/store.py`
- `tests/test_boardstore_taskboard_adapter.py`

Writes:

- create task rows;
- set status through TaskBoard methods;
- reserved `board.*` metadata only.

Cutover criteria:

- existing `tests/test_task_board.py` still pass;
- board create/list/transition projects existing task rows;
- existing `dgc task create/list` still works.

Rollback: stop using adapter; existing tasks unaffected.

### Step 4: second store adapter, RuntimeStateStore

Files touched:

- `dharma_swarm/board/adapters/runtime_state.py`
- `tests/test_boardstore_runtime_adapter.py`

Writes:

- task claims;
- delegation runs;
- workspace leases;
- artifact records;
- operator actions for control events.

Cutover criteria:

- existing `tests/test_runtime_state.py` pass;
- claim/heartbeat/release mirrored to runtime;
- replay sees runtime refs.

Rollback: disable adapter writes via feature flag; existing runtime records stay
valid.

### Step 5: OperatorBridge adapter

Files touched:

- `dharma_swarm/board/adapters/operator_bridge.py`
- `tests/test_boardstore_operator_bridge_adapter.py`

Cutover criteria:

- existing bridge/roaming tests pass;
- bridge enqueue/claim/response maps to cards;
- no duplicate mailbox task system appears.

Rollback: keep OperatorBridge direct paths.

### Step 6: RoamingMailbox adapter

Files touched:

- `dharma_swarm/board/adapters/roaming_mailbox.py`
- `tests/test_boardstore_roaming_adapter.py`

Cutover criteria:

- existing roaming tests pass;
- mailbox response import is idempotent;
- remote agents can use mailbox transport with client-compatible receipts.

Rollback: leave current `RoamingOperatorBridge` flow untouched.

### Step 7: Intent and mission adapter

Files touched:

- `dharma_swarm/board/objectives.py`
- `dharma_swarm/board/adapters/intent.py`
- `tests/test_boardstore_objectives.py`

Cutover criteria:

- objective -> card DAG creation works;
- mission state remains read-only context;
- acceptance criteria are seeded from completion contracts.

Rollback: objective feature off; manual card creation remains.

### Step 8: noticer adapter

Files touched:

- `dharma_swarm/noticer.py`
- `dharma_swarm/board/noticer_contract.py`
- `tests/test_boardstore_noticer_contract.py`

Cutover criteria:

- noticer can create/dedupe/rank only;
- forbidden methods raise `NoticerForbidden`;
- AutoProposer direct evolution submission is not reachable through noticer.

Rollback: disable noticer service. Existing cards remain.

### Step 9: client library

Files touched:

- `dharma_swarm/client.py` or `dharma_swarm/client/__init__.py`
- `dharma_swarm/client/transports.py`
- `dharma_swarm/client/harness.py`
- `tests/test_swarm_client.py`

Cutover criteria:

- local/http/mailbox transports pass contract tests;
- Codex/Claude/Cursor simulated identities can claim/update different cards;
- idempotency, version conflict, and cost cap tests pass.

Rollback: clients not advertised; facade still usable internally.

### Step 10: API and dashboard projection

Files touched:

- `api/routers/board.py`
- `api/main.py`
- dashboard board/table pages under `dashboard/`
- `tests/test_board_api.py`

Cutover criteria:

- existing `/api/commands/tasks` remains compatible;
- new board routes are facade-backed;
- dashboard uses board read API and client mutations.

Rollback: route removal; existing task dashboard remains.

## 14. Test Strategy

### Unit tests per facade method

- `create_card`: validation, ARJUNA rejection, idempotency replay/conflict,
  native store refs, version 1.
- `list_cards`: status/source/capability/objective filters, pagination.
- `get_card`: native projection and not found.
- `claim_card`: capability match, live lease exclusion, STOP sentinel, cost cap,
  runtime claim mirror.
- `heartbeat_claim`: lease freshness, cost burn, expired/revoked handling.
- `release_claim`: terminal statuses, runtime close, audit event.
- `transition_card`: status matrix, optimistic lock.
- `post_receipt`: checksum, acceptance coverage, memory write policy.
- `post_handoff`: claim release and downstream claimability.
- `post_control_event`: permission matrix and propagation.

### Integration lifecycle test

`tests/test_boardstore_lifecycle_integration.py`:

1. Create objective.
2. Decompose into one card.
3. Claim with mocked agent.
4. Heartbeat.
5. Post deterministic receipt.
6. Transition to review.
7. Human spot-check.
8. Transition to done.
9. Assert TaskBoard, RuntimeStateStore, event log, and projection agree.

### End-to-end cohort test

`tests/test_boardstore_cohort_e2e.py`:

- 10 cards;
- 5 simulated agents with different `AssigneeKind`;
- random claim order;
- no double-claim;
- all terminal cards have receipts;
- cohort cost burn <= ceiling;
- event replay equals current projection.

### Replay test

`tests/test_boardstore_replay.py`:

- create 20 mixed events;
- snapshot at event 10;
- replay from zero and snapshot;
- assert final state hash matches.

### Chaos test

`tests/test_boardstore_chaos.py`:

- agent claims card;
- heartbeat once;
- agent disappears;
- lease expires;
- facade recovers card to `claimable`;
- audit log captures expiry and recovery.

### Cost-cap test

`tests/test_boardstore_cost_caps.py`:

- claim with projected cost above ceiling refused;
- heartbeat crossing ceiling refused;
- audit event includes attempted cost, ceiling, and actor;
- operator can raise ceiling;
- subsequent heartbeat succeeds.

### Noticer contract test

`tests/test_boardstore_noticer_contract.py`:

- noticer creates card;
- duplicate source id returns same card;
- semantic duplicate links but does not delete;
- noticer claim/transition/receipt/handoff/control methods raise
  `NoticerForbidden`.

## 15. Operational Concerns

### Observability

Every facade method emits OpenTelemetry spans:

| Span | Attributes |
|---|---|
| `board.create_card` | actor, source_surface, card_id, arjuna_weight, status |
| `board.claim_card` | card_id, lease_id, agent_kind, capabilities, projected_cost |
| `board.heartbeat_claim` | lease_id, card_id, progress, incremental_cost |
| `board.transition_card` | card_id, from_status, to_status, previous_version, next_version |
| `board.post_receipt` | card_id, receipt_id, receipt_kind, verdict |
| `board.post_control_event` | event_type, actor_kind, card_id/cohort_id |
| `board.replay` | card_id, event_count, state_matches |

### Metrics

- `board.cards_per_state`
- `board.claim_latency_ms`
- `board.lease_expiry_rate`
- `board.receipt_rate`
- `board.cost_burn_rate_usd`
- `board.idempotency_replay_count`
- `board.version_conflict_count`
- `board.noticer_forbidden_count`
- `board.arjuna_rejection_count`
- `board.kill_switch_active`

### Alerting

Alert when:

- claim latency p95 > 5 seconds;
- lease expiry rate > 10 percent over 15 minutes;
- cost burn reaches 80 percent of cohort ceiling;
- STOP sentinel appears;
- projection conflict event appears;
- noticer forbidden calls > 0;
- card remains `running` without heartbeat beyond lease expiry;
- event append fails after native write.

### Backup and restore

- Native stores remain local SQLite/file stores.
- Board event log is the audit source of truth for facade behavior.
- Projections are reconstructible from native stores plus event log.
- Backup includes:
  - `~/.dharma/state/runtime.db`
  - task db under state dir
  - message-bus/bridge db
  - `~/.dharma/events/board.jsonl`
  - `roaming_mailbox/`
  - artifact directories referenced by receipts

Restore:

1. Restore native stores.
2. Restore board events.
3. Run replay.
4. Quarantine conflicts.
5. Rebuild projection indexes.

### Multi-instance considerations

v1 is single-writer, multi-reader.

- The facade acquires a lock file: `~/.dharma/boardstore/WRITER.lock`.
- Lock contains pid, hostname, started_at, and heartbeat timestamp.
- Second writer refuses to start unless lock is stale and owner process is dead.
- Readers can run without writer lock.
- Future remote sync must keep the client contract unchanged and implement
  single-writer or transactional distributed locking behind the adapter.

## 16. Open Questions and Explicit Non-Goals

### Load-bearing contradiction found

The prompt says an existing `docs/architecture/SWARM_SUBSTRATE.md` exists in
the repository after PR #313. On merged `main`, it does not. A draft exists in
`/Users/dhyana/dharma_swarm_substrate_spec`, a separate worktree at commit
`8837a3f`. Resolution: this spec cites the current repo as authority and treats
the prior draft as background only. A later PR may add a substrate overview, but
BoardStore implementation should not depend on a missing file.

### Open questions

1. Should `CardStatus` add `waiting_for_operator` as a first-class status, or
   should it remain `blocked` plus render hint?
   Decision for v1: keep `blocked`.

2. Should board event log use a new SQLite event table instead of the existing
   JSONL `EventLog`?
   Decision for v1: use existing `EventLog` for audit and a small SQLite table
   only for idempotency/projection indexes. A v2 ADR can move event storage if
   throughput proves JSONL insufficient.

3. Should A2A compliance be exact in v1?
   Decision for v1: no. Render A2A-compatible envelopes through an adapter
   after local card semantics are proven.

4. Should ControlSurface rows become write targets?
   Decision for v1: no. ControlSurface remains projection.

5. Should AutoProposer continue direct Darwin submission?
   Decision for v1 BoardStore: existing code can remain, but noticer-mode
   AutoProposer integration cannot access direct submit through the board.
   A later ADR should decide whether AutoProposer direct submission is retired
   or gated behind cards.

6. Should card schema include arbitrary `metadata`?
   Decision for v1: no. Unbounded metadata is how schemas rot. Use
   `render_hints`, `capability_manifest`, receipt refs, and adapter-owned native
   stores.

### Explicit non-goals

- Implement BoardStore in this PR.
- Replace TaskBoard.
- Replace OperatorBridge.
- Replace RuntimeStateStore.
- Create a new isolated board database.
- Make kanban the substrate.
- Let external agents write raw HTTP directly.
- Give noticers execution rights.
- Solve distributed multi-writer remote sync in v1.
- Solve exact A2A/MCP/AG-UI compliance in v1.
- Redesign AgentRunner or SwarmManager.
- Refactor orchestration hot spots as part of this spec.
- Build voice capture before text capture and idempotency are proven.

### Self-audit

This spec may age badly if local-first single-writer SQLite stops matching the
actual deployment pattern, or if A2A/MCP/AG-UI converge on a dominant shared
task-state contract that makes a local card envelope redundant. The v2 ADR
should be "BoardStore Remote Sync and Protocol Compliance": it would evaluate
whether the facade stays local with sync adapters, moves to a server-backed
transaction log, or adopts an external protocol as a wire format while keeping
the same `Card` and `SwarmClient` semantics.
