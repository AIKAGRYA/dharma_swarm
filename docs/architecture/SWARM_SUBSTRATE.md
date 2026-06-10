---
title: Swarm Substrate Architecture
date: 2026-05-20
status: active_spec
---

# Swarm Substrate Architecture

This document answers one question:

`What stable substrate lets one human express intent once, while heterogeneous
agents coordinate real work across code, docs, research, slides, sites, trades,
and future surfaces without losing trust or legibility?`

It is an architecture spec, not a live-state owner. Live operating facts still
belong to:

- Intent: [`docs/governance/ACTIVE_TRACK.yaml`](../governance/ACTIVE_TRACK.yaml)
- Surface: [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml)
- State: [`docs/state/LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md)

This document gives future agents the contract surface for building the next
substrate layer without collapsing it into one local feature such as "kanban",
"daemon", "agent client", or "single door". Those are faces of the substrate.
The substrate is the system of contracts between them.

## One Sentence

Dharma Swarm should become a local-first, shared-board multi-agent operating
substrate: the human states intent once; agents decompose it into typed work,
claim visible cards, produce receipts, verify outcomes, and remain interruptible
through one observable control plane.

## Confidence Claim

This spec targets 90% confidence for a one-to-three-year architecture decision.
That confidence comes from three checks:

1. It maps onto the existing repo instead of inventing a new system.
2. It aligns with current external agent patterns without depending on any one
   framework.
3. It turns the hard questions into explicit contracts and defers only the
   details that can be safely deferred.
4. It was checked against the repo with GitNexus, Context+, xray, radon, ruff,
   vulture, import-linter, and direct source reads on 2026-05-20.

Remaining uncertainty is real:

- exact A2A compatibility should wait until the local card/task schema settles;
- the remote sync store should wait until local board semantics are proven;
- mobile and voice surfaces should not drive schema design before text-based
  objective capture is reliable;
- background agents should remain notice-only until there is enough receipt,
  cost, and rollback discipline to justify promotion.

## Local Evidence

The repo already has most of the substrate in pieces:

| Existing piece | Evidence | What it means |
|---|---|---|
| Task states, priorities, roles, provider types, autonomy levels | [`dharma_swarm/models.py`](../../dharma_swarm/models.py#L19-L170) | The board already has core vocabulary for card state, priority, ownership, and heterogeneous agents. |
| Explicit async task board | [`dharma_swarm/task_board.py`](../../dharma_swarm/task_board.py#L1-L120) | The repo already has SQLite task CRUD, dependencies, WAL concurrency, and a status finite-state machine. It should be wrapped or migrated, not ignored. |
| Task creation, batch creation, dispatch tick | [`dharma_swarm/swarm.py`](../../dharma_swarm/swarm.py#L1115-L1461) | `SwarmManager` already treats tasks as the operational unit and gates creation through Telos. |
| Notice-like task creation | [`dharma_swarm/swarm.py`](../../dharma_swarm/swarm.py#L1238-L1338) | Latent branches can already become tasks. This is the seed of the noticer daemon pattern. |
| Disagreement-to-task synthesis | [`dharma_swarm/swarm.py`](../../dharma_swarm/swarm.py#L1367-L1451) | Productive uncertainty can already be transformed into bounded work. |
| Operator bridge lifecycle | [`dharma_swarm/operator_bridge.py`](../../dharma_swarm/operator_bridge.py#L1-L90) | The repo already has a canonical queue over MessageBus, SessionLedger, SQLite, RuntimeStateStore, and TelemetryPlane. This is the strongest existing external-agent participation seed. |
| Atomic bridge claim/response path | [`dharma_swarm/operator_bridge.py`](../../dharma_swarm/operator_bridge.py#L347-L571) | Enqueue, list, get, and atomic claim already exist. A substrate client should adapt this lifecycle before inventing another claim protocol. |
| Runtime mirroring for claims, runs, artifacts, recovery | [`dharma_swarm/operator_bridge.py`](../../dharma_swarm/operator_bridge.py#L1076-L1468) | Bridge actions already mirror into runtime task claims, delegation runs, partial artifacts, recovery, and responses. |
| Canonical runtime state spine | [`dharma_swarm/runtime_state.py`](../../dharma_swarm/runtime_state.py#L1-L80) | Live control-plane state is already local-first, transactional, and inspectable in SQLite. |
| Runtime claim/run/artifact models | [`dharma_swarm/runtime_state.py`](../../dharma_swarm/runtime_state.py#L339-L410) | The substrate should reuse `TaskClaim`, `DelegationRun`, `WorkspaceLease`, and `ArtifactRecord` instead of creating parallel concepts. |
| Sync runtime helpers | [`dharma_swarm/runtime_state.py`](../../dharma_swarm/runtime_state.py#L1368-L1502) | Non-async callers already have claim heartbeat/close and delegation-run helpers. This matters for CLIs, daemons, and external harness glue. |
| Git-friendly roaming mailbox | [`dharma_swarm/roaming_mailbox.py`](../../dharma_swarm/roaming_mailbox.py#L1-L120) | Cross-harness task exchange already exists as plain JSON files syncable through git. It should become a client transport, not a competing board. |
| Remote roaming poller | [`dharma_swarm/roaming_poller.py`](../../dharma_swarm/roaming_poller.py#L1-L140) | Remote agents can already fetch, claim, execute a responder command, write a response, and push mailbox changes. |
| API task surface | [`api/routers/commands.py`](../../api/routers/commands.py#L27-L107) | The dashboard and external clients already have task create/list/dispatch endpoints. |
| Dashboard task view | [`dashboard/src/app/dashboard/tasks/page.tsx`](../../dashboard/src/app/dashboard/tasks/page.tsx#L36-L190) | The visible board already exists as a table; the kanban is an evolution, not a new product surface. |
| Dashboard polling and creation hooks | [`dashboard/src/hooks/useTasks.ts`](../../dashboard/src/hooks/useTasks.ts#L7-L33) | The dashboard already treats tasks as live data with 5-second refresh. |
| Product-surface discipline | [`PRODUCT_SURFACE.md`](../../PRODUCT_SURFACE.md#L1-L14) | New control planes should converge on the dashboard, not spawn parallel GUIs. |
| Control surface projector | [`dharma_swarm/operator_core/control_surface.py`](../../dharma_swarm/operator_core/control_surface.py#L1-L90) | Observability should extend the existing declared-vs-observed projector rather than creating another truth surface. |
| Surface manifest | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml#L1-L120) | Active routers, dashboard nav, state dirs, and control-plane workflow are already declared. |
| Tasks declared live | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml#L240-L247) | The task surface is already P0 and live. |
| Swarm manager wired to tasks | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml#L370-L377) | The task board is connected to the live swarm manager surface. |
| Shadow discovery safety | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml#L433-L543) | Recursive discovery already records receipts and recommends promotion without autonomous apply. |
| Feedback loops | [`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml#L545-L619) | Stigmergy, recursive discovery, and world-radar loops already exist as declared loops. |
| Intent decomposition | [`dharma_swarm/intent_router.py`](../../dharma_swarm/intent_router.py#L1-L120) | Natural-language routing, complexity estimation, decomposition, and skill matching already exist. This is the planning seed. |
| Mission contract | [`dharma_swarm/mission_contract.py`](../../dharma_swarm/mission_contract.py#L1-L130) | Mission state already captures objective continuity, task counts, delegated IDs, blockers, and review summaries. |
| Agent registry | [`dharma_swarm/agent_registry.py`](../../dharma_swarm/agent_registry.py#L146-L235) | Agents already have identity directories, task logs, fitness history, and prompt lineage. |
| A2A-style agent cards | [`dharma_swarm/a2a/agent_card.py`](../../dharma_swarm/a2a/agent_card.py#L43-L183) | Agent capability discovery already has a local-first bridge to A2A-style cards. |
| Durable workflow DAG | [`dharma_swarm/durable_execution.py`](../../dharma_swarm/durable_execution.py#L44-L248) | Crash-recoverable DAG execution already exists and should become the substrate's workflow primitive. |
| Auto-proposal loop | [`dharma_swarm/auto_proposer.py`](../../dharma_swarm/auto_proposer.py#L1-L180) | The system already observes stale tasks, failures, hotspots, provider issues, and fitness drift. The substrate should route those observations into notice cards before autonomous execution. |
| Recursive-discovery receipts | [`dharma_swarm/recursive_discovery.py`](../../dharma_swarm/recursive_discovery.py#L1-L120) | Shadow-mode receipts already encode limitations, candidate diffs, experiment results, witness verdicts, and promotion decisions without mutating runtime code. |
| Human promotion hold | [`dharma_swarm/recursive_discovery.py`](../../dharma_swarm/recursive_discovery.py#L300-L321) | The repo already has the right safety line: candidates wait for human-reviewed PRs. |
| One protocol, every surface vision | [`docs/plans/OPERATOR_COMMAND_VISION.md`](../plans/OPERATOR_COMMAND_VISION.md#L7-L159) | The repo already rejects surface entropy and wants thin clients over shared typed protocols. |
| Living agent identity plane | [`docs/plans/2026-03-26-living-agent-roaming-onboarding-architecture.md`](../plans/2026-03-26-living-agent-roaming-onboarding-architecture.md#L7-L157) | The repo already names the missing identity plane for agents across devices and harnesses. |

The missing layer is not capability. It is convergence: one contract set that
binds task board, operator bridge, runtime state, roaming mailbox, agent
identity, durable workflow, receipts, surface routing, and human control into
the same operating substrate.

### 2026-05-20 Structural Pass

The spec branch was indexed with GitNexus after this document was drafted:
96,009 nodes, 165,596 edges, 2,050 clusters, and 300 flows at commit `8837a3f`.
The structural result changes the implementation route:

- `RuntimeStateStore` is critical infrastructure: GitNexus reports 101 upstream
  impacted symbols and 31 direct importers. It must be the runtime spine.
- `TaskBoard` is already load-bearing: GitNexus reports 58 upstream impacted
  symbols and 9 direct importers for the canonical `task_board.py` class. There
  is also a smaller duplicate `TaskBoard` in `orchestrator.py`, so consolidation
  must be deliberate.
- `OperatorBridge` is not peripheral: GitNexus reports 10 upstream impacted
  symbols and 5 direct non-test importers, plus runtime-factory/adapters and
  roaming bridge dependencies. It is the existing claim/heartbeat/response seed.
- Radon places the worst complexity in execution/orchestration hot paths
  (`SwarmManager.tick`, `AgentRunner.run_task`, `Orchestrator._execute_task`),
  not in `TaskBoard` or `DurableWorkflow`. The substrate should reduce
  orchestration entropy by routing through the board contract, not create a
  fifth orchestrator.
- Ruff found only small unused-import rot in the inspected substrate-adjacent
  files. The problem is architectural convergence, not basic code hygiene.

## External Alignment

External systems confirm the direction, but none should become the root design:

- A2A defines an Agent Card discovery model and a task-oriented agent protocol.
  Dharma should keep local objects compatible with A2A concepts, but not block
  local substrate design on exact wire compliance yet:
  <https://a2aproject.github.io/A2A/latest/specification/>
- MCP is the tool and context bridge, not the shared work-state layer. Tool
  outputs cross trust boundaries and must be schema-gated, audited, and treated
  as untrusted input:
  <https://modelcontextprotocol.io/> and
  <https://owasp.org/www-community/attacks/MCP_Tool_Poisoning>
- AG-UI is a good candidate for frontend event streaming between agents and
  user interfaces, but it should render substrate events rather than own them:
  <https://docs.ag-ui.com/>
- LangGraph validates durable checkpoints, interruptible execution, memory, and
  human-in-the-loop patterns:
  <https://docs.langchain.com/oss/python/langgraph/overview>
- CrewAI validates the split between autonomous crews and event-driven flows,
  with guardrails, memory, knowledge, and observability:
  <https://docs.crewai.com/>
- AutoGen validates multi-agent group conversations and runtime-level agent
  coordination, but the board should remain framework-agnostic:
  <https://microsoft.github.io/autogen/stable/>
- OpenAI Agents SDK validates handoffs, guardrails, tracing, and tool-mediated
  execution as first-class agent runtime concerns:
  <https://openai.github.io/openai-agents-python/>
- Temporal-style durable execution validates the durability requirement for
  long-running work, but Dharma can start from its existing local durable DAG:
  <https://temporal.io/>
- BeeAI reinforces the same portability lesson: heterogeneous agent platforms
  need open participation boundaries rather than one framework lock-in:
  <https://docs.beeai.dev/>

The conclusion is conservative: use external protocols as alignment targets and
adapters. Do not let any one protocol own Dharma's internal board, identity, or
receipt model.

## Decision Questions

These were the important open questions before this spec. The answers below are
the recommended decisions for the next implementation tranche.

| Question | Importance | Decision | Reason |
|---|---:|---|---|
| Board store: SQLite/local-first or Postgres/remote-sync first? | P0 critical | Start SQLite/local-first, but do it as a `BoardStore` facade over `TaskBoard`, `OperatorBridge`, and `RuntimeStateStore`, with an append-only event log. | Current repo already has local SQLite task state, bridge queue state, and runtime claim/run/artifact state. Moving too early to a server store makes every agent dependent on distributed infrastructure before the contract is stable. Creating a fourth isolated board database would be worse. The future-proof move is an adapter boundary over existing truth-bearing stores. |
| First non-dashboard intent surface: Telegram or phone/voice? | P1 high | Telegram/text first. Voice second. | Text gives lower ambiguity, easier dedupe, easier receipts, and immediate mobile capture. Voice should normalize into the same `Objective` contract later. |
| External agents: direct board API or client wrapper? | P0 critical | External agents use `dharma_swarm.client`, a CLI wrapper, or the roaming-mailbox transport. Raw HTTP is internal/admin. | The client enforces schema validation, optimistic locking, idempotency keys, leases, auth headers, and audit fields. The roaming mailbox gives remote or sandboxed agents a git-friendly transport when they cannot import Python or reach local HTTP. |
| Noticer daemon: create cards only or execute too? | P0 critical | Notice-only. It can create, dedupe, rank, and refresh cards. It cannot claim or execute them without a separate explicit promotion. | "Notice" and "do" are different jobs. Keeping them separate protects trust, keeps background behavior legible, matches recursive-discovery shadow mode, and prevents `AutoProposer` from bypassing board review by submitting directly into execution/evolution loops. |
| A2A compatibility: inspired-by or valid server/client now? | P1 high | Inspired-by now, A2A-compatible envelope later. | Local `AgentCard` and task concepts already align with A2A. Exact compliance is valuable, but forcing it before the board contract stabilizes risks bending local design around a moving external interface. |

The P0 decisions are the ones future agents must not casually overturn:
local-first board facade over existing stores, client-mediated writes,
mailbox-compatible remote participation, and notice-only background agents. The
P1 decisions can change when evidence changes, but only without changing the
core contracts.

## Seven-Layer Architecture

### Layer 1: Intent Capture

Purpose: many input surfaces become one normalized objective.

Input surfaces may include dashboard, CLI, TUI, Telegram, email, voice notes,
phone messages, GitHub issues, PR comments, research notes, or future device
surfaces. They all produce the same substrate object:

`Objective`

Required fields:

- `objective_id`
- `source_surface`
- `source_ref`
- `raw_input_ref`
- `normalized_intent`
- `requested_outputs`
- `human_priority`
- `constraints`
- `approval_policy`
- `cost_policy`
- `created_by`
- `created_at`
- `idempotency_key`
- `schema_version`

Rules:

- Intent capture may be lossy about phrasing, but not about constraints.
- Voice, Telegram, CLI, and board cards must converge into the same object.
- Every objective must preserve a raw-input reference for replay.
- Every objective must declare whether it is asking for code, docs, research,
  slides, sites, financial analysis, task triage, or another artifact family.
- Intent capture does not execute. It only normalizes and files.

Existing anchors:

- The operator command vision already states "one protocol, every surface".
- The command API and dashboard task creation already provide a minimal path
  from user action to task.
- The surface manifest already declares dashboard tasks and commands as live.
- `IntentRouter` already turns natural language into decomposed routed work.
- `MissionState` already preserves objective continuity across cycles.

### Layer 2: Decomposition and Planning

Purpose: objective becomes a DAG of work packets with acceptance criteria.

Core object:

`WorkPacket`

Required fields:

- `packet_id`
- `objective_id`
- `title`
- `description`
- `acceptance`
- `artifact_contracts`
- `dependencies`
- `preferred_capabilities`
- `forbidden_actions`
- `risk_class`
- `verification_plan`
- `estimated_cost`
- `estimated_time`
- `owner_role`
- `created_by`
- `created_at`
- `schema_version`

Rules:

- Decomposition produces a DAG, not a loose bullet list.
- A packet without acceptance criteria is not claimable.
- A packet that touches code must name verification commands or explain why
  none apply.
- A packet that touches money, infrastructure, credentials, data deletion, or
  external publishing must carry an approval policy.
- The planner can propose, but the board is the coordination primitive.

Existing anchors:

- `Task.depends_on` and `Task.blocked_by` already exist.
- `DurableWorkflow` already has step dependencies and ready-step logic.
- `IntentRouter.decompose` is the first local planner to harden, not a thing
  to replace.
- `MissionState` and completion/judge contracts provide the durable mission
  envelope around a packet DAG.
- Existing governance already routes active work through explicit tracks and
  gates.

### Layer 3: Shared Task Board

Purpose: the board is the blackboard. It is the visible, shared coordination
primitive for all human and agent work.

Core object:

`Card`

Required fields:

- `card_id`
- `objective_id`
- `packet_id`
- `status`
- `priority`
- `title`
- `description`
- `acceptance`
- `assigned_agent_id`
- `claimed_by_session`
- `lease_expires_at`
- `depends_on`
- `blocked_by`
- `artifact_refs`
- `receipt_refs`
- `risk_class`
- `cost_policy`
- `approval_policy`
- `version`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`
- `schema_version`

Minimum states:

- `inbox`
- `triaged`
- `ready`
- `claimed`
- `running`
- `blocked`
- `review`
- `done`
- `failed`
- `cancelled`
- `archived`

Mapping to current `TaskStatus`:

- `pending` maps to `inbox`, `triaged`, or `ready` depending on metadata.
- `assigned` maps to `claimed`.
- `running` maps to `running`.
- `completed` maps to `done`.
- `failed` maps to `failed`.
- `cancelled` maps to `cancelled`.

Rules:

- Whoever holds a live lease owns the card until the lease expires, is released,
  or is revoked.
- All writes are optimistic-lock writes against `version`.
- Every state transition emits an append-only board event.
- The dashboard renders the board, but the dashboard does not own board truth.
- The table view can remain; kanban is the natural visual evolution.
- Cards may be created by humans, planners, noticers, CI, GitHub, Telegram, or
  future surfaces, but must pass the same schema and gate checks.

First implementation:

- Extend the existing task API and task dashboard instead of introducing a new
  surface.
- Add `BoardStore` as a facade over the current `TaskBoard`,
  `OperatorBridge`, and `RuntimeStateStore`.
- Add event log table or JSONL equivalent before remote sync.
- Keep SQLite as first store and avoid a fourth isolated board database.
- Treat the dashboard board/kanban as a projection over the facade, not a new
  source of truth.

### Layer 4: Agent Registry and Capability Plane

Purpose: agents are discoverable, typed, and accountable across harnesses.

Core object:

`LivingAgent`

Required fields:

- `agent_uid`
- `callsign`
- `harness`
- `provider`
- `model`
- `role`
- `capabilities`
- `endpoint`
- `status`
- `autonomy_policy`
- `cost_policy`
- `workspace_policy`
- `memory_namespace`
- `card_ref`
- `home_dock`
- `last_seen_at`
- `trace_identity`
- `created_at`
- `updated_at`
- `schema_version`

Rules:

- Agents are runtime identities, not Python files.
- An agent may have many sessions and workspaces, but one stable identity.
- A2A-style cards advertise capabilities; they do not replace local identity.
- Registry status is advisory unless backed by heartbeat or recent event.
- Capability matching should use role, card capabilities, observed history, and
  cost/quality telemetry.

Existing anchors:

- `AgentIdentity` already stores role, model, status, task counts, tokens,
  quality, prompt generation, and task history.
- `AgentCard` already maps identity to local-first A2A-style capability cards.
- The living-agent architecture doc already separates identity, embodiment, and
  temporary task sessions.
- `RuntimeStateStore` records live claims and runs, so registry status should
  be derived from identity plus runtime events, not only static files.

### Layer 5: Execution and Handoff

Purpose: agents claim work, execute in bounded workspaces, and hand off typed
artifacts without corrupting the board.

Core objects:

`ClaimLease`

- `lease_id`
- `card_id`
- `agent_uid`
- `session_id`
- `workspace_ref`
- `claimed_at`
- `expires_at`
- `heartbeat_at`
- `version`

`Handoff`

- `handoff_id`
- `from_agent_uid`
- `to_agent_uid`
- `card_id`
- `artifact_refs`
- `context_summary`
- `open_questions`
- `next_actions`
- `verification_state`
- `created_at`

Rules:

- Agents claim through `dharma_swarm.client`, not raw ad hoc writes.
- Claims are leased. Stale claims can be recovered.
- Handoffs are typed and visible on the card timeline.
- Artifacts are referenced, not pasted into the board as unbounded text.
- Workspaces are leased per task or mission; they are not identity.
- Long-running execution uses durable workflow steps when there is more than
  one dependent action.

Existing anchors:

- `OperatorBridge` already implements enqueue, atomic claim, heartbeat,
  partial artifact, stale recovery, response, and response acknowledgement.
- `RuntimeStateStore` already stores task claims, delegation runs, workspace
  leases, artifacts, operator actions, and session events.
- `RoamingMailbox` and `RoamingPoller` already let remote agents exchange JSON
  tasks and responses through git.
- `DurableWorkflow` already checkpoints DAG execution and computes ready steps.
- `AgentRegistry` already has task logs and prompt lineage.
- The current task API already exposes dispatch.

### Layer 6: Verification, Receipts, and Memory

Purpose: done means verified, replayable, and memorable.

Core objects:

`VerificationReceipt`

- `receipt_id`
- `card_id`
- `artifact_refs`
- `checks_run`
- `commands`
- `exit_codes`
- `test_results`
- `reviewer`
- `judge_results`
- `known_gaps`
- `rollback_ref`
- `cost_actual`
- `created_at`

`MemoryWrite`

- `memory_id`
- `card_id`
- `objective_id`
- `agent_uid`
- `layer`
- `content_ref`
- `summary`
- `valid_until`
- `created_at`

Rules:

- Completion requires at least one receipt or an explicit no-check reason.
- Memory writes must be summaries with source references, not ungrounded lore.
- A future agent joining mid-flight should hydrate from card history, receipts,
  artifacts, and memory references before re-deriving context.
- External tool outputs are untrusted until schema-validated and linked to a
  receipt.
- Multi-judge review is optional for low-risk cards and required for high-risk
  cards.

Existing anchors:

- `RuntimeStateStore.ArtifactRecord` is already a receipt-adjacent artifact
  reference model.
- `OperatorBridge.record_partial_artifact` already mirrors artifacts into
  runtime state.
- `recursive_discovery` already has shadow receipts, witness verdicts, rollback
  pointers, and human promotion holds.
- The manifest already has recursive discovery receipts and promotion queue
  surfaces.
- The onboarding convergence PR already makes stale state visible without
  making soft warnings into hard gates.
- The repo has memory, lineage, telemetry, and witness surfaces that should
  become receipt viewers rather than competing state owners.

### Layer 7: Observability and Control

Purpose: the human can see, pause, redirect, kill, take over, and resume work
without guessing what agents are doing.

Core object:

`ControlEvent`

- `event_id`
- `target_type`
- `target_id`
- `action`
- `reason`
- `actor`
- `before_state`
- `after_state`
- `created_at`

Required controls:

- pause card
- resume card
- cancel card
- revoke lease
- take over card
- reassign card
- quarantine agent
- set cost cap
- require approval
- promote noticer recommendation
- archive stale card

Rules:

- Every control action emits an audit event.
- Kill switches and cost caps are not optional UI features; they are substrate
  primitives.
- The dashboard is the primary control surface.
- CLI, Telegram, or future mobile controls are thin clients over the same
  control event protocol.
- Observability includes board, agent map, per-agent stream, receipts, cost, and
  blocked/stale views.

Existing anchors:

- `PRODUCT_SURFACE.md` says the dashboard is the primary operator surface.
- The manifest already declares dashboard tasks, agents, telemetry, control
  surface, audit, lineage, and stigmergy surfaces.
- `ControlSurface` already reconciles declared intent with observed runtime,
  code, evidence, and docs. The swarm map and board should feed this projector.

## Storage Decision

Start with SQLite and explicit event append, but do not start with an isolated
greenfield board database.

The first `BoardStore` should be a facade over three existing stores:

1. `TaskBoard`: task CRUD, dependencies, priority, and the current task FSM.
2. `OperatorBridge`: external queue, claim, heartbeat, recovery, partial
   artifact, response, and delivery acknowledgement lifecycle.
3. `RuntimeStateStore`: canonical runtime claims, delegation runs, workspace
   leases, artifacts, operator actions, memory facts, and session events.

That facade gives agents one board contract while preserving the repo's current
durable spine. Later migrations can collapse duplicated tables after behavior
is proven; the first tranche should make existing truth legible rather than
forking it.

The first implementation should define:

```python
class BoardStore(Protocol):
    def create_card(self, card: CardCreate) -> Card: ...
    def get_card(self, card_id: str) -> Card | None: ...
    def list_cards(self, query: CardQuery) -> list[Card]: ...
    def update_card(self, card_id: str, patch: CardPatch, version: int) -> Card: ...
    def append_event(self, event: BoardEvent) -> None: ...
    def claim(self, request: ClaimRequest) -> ClaimLease: ...
    def heartbeat(self, lease_id: str) -> ClaimLease: ...
    def release(self, lease_id: str, result: ReleaseResult) -> Card: ...
```

The SQLite facade is the first adapter. A future Postgres, Litestream,
Electric, Turso, NATS, or CRDT-backed store is a second adapter. The contract
must not leak SQLite row details, `TaskBoard` row details, bridge row details,
or runtime-state row details to clients.

Required persistence guarantees:

- monotonic card version;
- append-only event log;
- idempotency key on external card creation;
- lease expiry and heartbeat;
- atomic card update plus event append;
- audit actor on every write;
- migration path from existing `Task` rows;
- runtime-state mirroring for every claim, run, artifact, and control action;
- bridge/mailbox mapping for external-agent participation.

## Participation Boundary

External agents participate through a small client library with multiple
transports:

```python
from dharma_swarm.client import SwarmClient

client = SwarmClient.from_env(agent_uid="codex-local", transport="local")
card = client.claim_next(capabilities=["code", "docs"])
client.append_progress(card.id, "Mapped existing task API and dashboard.")
client.attach_artifact(card.id, path="docs/architecture/SWARM_SUBSTRATE.md")
client.request_review(card.id, receipt=receipt)
```

The client owns:

- schema validation;
- auth and actor identity;
- idempotency keys;
- optimistic lock retries;
- lease renewal;
- event writing;
- artifact upload/reference rules;
- receipt helpers;
- safe defaults for cost and approval policy.

Required transports:

- `local`: in-process Python adapter for first-party repo code;
- `http`: dashboard/API adapter for local services and admin tooling;
- `mailbox`: git-friendly `RoamingMailbox` adapter for remote or sandboxed
  agents that cannot import Dharma or reach localhost;
- `a2a`: later adapter after local card semantics stabilize.

Raw HTTP endpoints may exist for dashboard and admin use, but external agents
should not be instructed to write the board directly.

## Noticer Boundary

The noticer daemon is a first-class substrate component, but it is not an
executor. It should start as an adapter over existing observation loops, not as
a second autonomous system.

Allowed:

- observe CI failures;
- observe stale docs;
- observe PRs waiting on review;
- observe untriaged objectives;
- observe active-track TTL drift;
- observe broken-register changes;
- observe failing scheduled checks;
- create or update cards with evidence;
- dedupe cards;
- rank cards;
- reopen cards when new evidence appears;
- escalate blocked cards to the human.

Existing seeds:

- `AutoProposer` already observes stale tasks, repeated failures, provider
  issues, stigmergy hotspots, fitness drops, and test clusters.
- `recursive_discovery` already records shadow receipts and promotion holds.
- manifest health and onboarding already surface staleness without gating.
- GitHub/CI signals can become cards through the same evidence schema.

Forbidden in the first architecture generation:

- claiming execution cards;
- editing files;
- pushing branches;
- merging PRs;
- spending money;
- calling external systems with side effects;
- applying recursive-discovery diffs;
- overriding card leases.
- submitting directly to Darwin/evolution pipelines from notice-only mode.

Promotion rule:

If a noticer action should become executable, promote that capability through an
explicit ADR or active track with tests, receipts, cost caps, rollback, and human
approval. Do not blur notice and execution by convenience.

## Build Tranches

### Tranche 0: Spec and Registration

- Add this document.
- Register it as a depth-on-demand architecture doc.
- Do not make it a first-read surface.
- Keep PR #313 focused on onboarding convergence if possible.

### Tranche 1: Board Contract

- Add `dharma_swarm/board/` models and `BoardStore` protocol.
- Add a SQLite facade adapter over `TaskBoard`, `OperatorBridge`, and
  `RuntimeStateStore`.
- Add board event log if no existing runtime event cleanly covers the event.
- Map existing `Task`, `OperatorBridgeTask`, `TaskClaim`, `DelegationRun`,
  `WorkspaceLease`, and `ArtifactRecord` to card projections.
- Keep writes single-path through the facade; reads may project from existing
  stores.
- Extend `/api/commands/tasks` or add `/api/board/cards` without breaking the
  current dashboard.
- Add tests for version conflicts, idempotency, and lease expiry.

### Tranche 2: Dashboard Kanban

- Evolve `dashboard/tasks` from table-only into board/table tabs.
- Keep existing create flow.
- Add status columns, claim owner, stale lease marker, blockers, receipts, and
  review state.
- Do not create a parallel GUI.

### Tranche 3: Agent Client

- Add `dharma_swarm.client`.
- Support claim, heartbeat, progress, artifact ref, receipt, review request,
  release, and fail.
- Support local, HTTP, and roaming-mailbox transports.
- Provide CLI wrappers for tools that cannot import Python directly.
- Add contract tests simulating Codex, Claude Code, Cursor, and a daemon.

### Tranche 4: Noticer

- Add `dharma_swarm/noticer.py` as a notice-only adapter over AutoProposer,
  recursive discovery, manifest health, CI/GitHub, and active-track signals.
- Watch CI, doc staleness, broken register, active track TTL, PR age, and
  latent-gold/high-salience memory.
- Create cards only.
- Add dedupe and evidence refs.
- Add dashboard filters for noticer-created cards.

### Tranche 5: Control and Cost

- Add control event API.
- Add pause/resume/cancel/reassign/revoke lease/quarantine.
- Add per-card and per-agent cost cap enforcement.
- Add receipt display and audit trail.

### Tranche 6: Multi-Surface Capture

- Add Telegram text ingestion into `Objective`.
- Add email/GitHub issue ingestion only after dedupe and idempotency are proven.
- Add voice normalization after text capture works.
- All surfaces remain thin clients over the same objective and card contracts.

### Tranche 7: Protocol Adapters

- Expose A2A-compatible AgentCard and Task envelopes.
- Add MCP resource/tool views for board read and controlled write.
- Add AG-UI event stream for dashboard agent activity.
- Keep local contracts as the internal source of behavior.

## Required Tests

Minimum test set before calling the substrate usable:

- card create/list/update preserves version and emits events;
- duplicate idempotency key does not create duplicate card;
- two agents cannot hold the same live claim lease;
- stale lease can be recovered with an audit event;
- noticer can create/dedupe cards but cannot claim or execute;
- client wrapper writes valid actor/audit fields;
- dashboard reads existing tasks after migration;
- raw task API remains backward compatible;
- cost cap blocks or pauses execution before budget breach;
- control event pause prevents further lease heartbeat from continuing work;
- A2A adapter can render an AgentCard from `LivingAgent`;
- MCP exposure treats tool output as untrusted and schema-validates writes;
- durable workflow resumes after checkpoint;
- high-risk card cannot move to done without verification receipt;
- low-risk card can complete with explicit no-check reason.

## Anti-Goals

Do not:

- replace the dashboard with a new standalone kanban app;
- make the noticer an autonomous executor;
- expose raw mutable board HTTP as the recommended external-agent contract;
- make Postgres or cloud sync a prerequisite for the first board contract;
- force exact A2A compliance before local card semantics are stable;
- let MCP tools write arbitrary board fields without schema gates;
- create another orchestrator/router instead of using the board and client;
- duplicate existing task models without a migration path;
- treat docs, memory, dashboard state, and runtime state as interchangeable;
- bury control and cost caps as optional UI polish.

## Definition Of Done

The first substrate implementation is done when:

- `make onboard` points agents to this spec as depth-on-demand, not first-read;
- a human can create one objective from the dashboard or CLI;
- the objective becomes cards with acceptance criteria;
- two different agent harnesses can claim/update different cards through the
  client;
- a noticer can create a card but cannot execute it;
- every state transition is visible in the dashboard;
- every claimed card has a lease and audit trail;
- completion requires a receipt or explicit no-check reason;
- pause/cancel/reassign works from the dashboard;
- tests cover the race conditions and safety boundaries above.

That is the smallest real version of the multi-agent intelligence substrate:
one intent, shared visible work, typed participants, durable execution,
verifiable outputs, and human control.
