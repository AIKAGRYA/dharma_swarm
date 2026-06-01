# Slice D — Workflow State Ownership

**Agent:** devin-roaming-2987d222 (serial AGT-DEVIN_ROAMING_2987D222)
**Verdict date:** 2026-06-01T07:20Z
**Codex claim:** Multiple workflow-state owners. No `workflowRun` boundary. LangGraph-style state graph absent.

---

## Method

Grep + read across all `dharma_swarm/**/*.py` for classes containing `State`, `Run`, `Loop`, `Workflow`, `Task`, `Session` in their names. Traced state persistence (SQLite, JSONL, in-memory) and ownership (who writes, who reads).

---

## Findings

### 1. Inventory of state owners

| # | Module | State class | Persistence | Scope |
|---|--------|------------|-------------|-------|
| 1 | `runtime_state.py` | `SessionState`, `TaskClaim`, `DelegationRun`, `RuntimeStateStore` | SQLite (`~/.dharma/state/runtime.db`) | **Primary control plane** — sessions, task claims, delegation runs, session events |
| 2 | `models.py` | `AgentState`, `SwarmState`, `Task` | In-memory (via SwarmManager) | Agent pool + task board snapshots |
| 3 | `swarm.py` | `SwarmCoordinationState`, `SwarmManager` | In-memory + delegates to `TaskBoard` | Top-level coordinator; owns agent pool, orchestrator, task board |
| 4 | `orchestrate_live.py` | (no dedicated class) | Passes `STATE_DIR` to ~15 subsystems | **Loop host** — `run_swarm_loop()` instantiates SwarmManager, MessageBus, LoopSupervisor, all subsystem agents |
| 5 | `loop_supervisor.py` | `LoopHealth`, `StateChangeTracker`, `LoopSupervisor` | JSONL at `~/.dharma/loop_supervisor/` | Watchdog over orchestrate_live loops — stall detection, retry storms |
| 6 | `mission_contract.py` | `MissionState`, `CampaignState` | JSONL at `~/.dharma/missions/` | Mission lifecycle (planned→active→complete) |
| 7 | `iteration_depth.py` | `InitiativeStatus`, ledger | JSONL at `~/.dharma/iteration/` | Quality ratchet — seed→growing→solid→shipped |
| 8 | `overnight_director.py` | `DurableState` | JSON/JSONL at `~/.dharma/overnight/<run>/` | Long-horizon run persistence (spec + plan + runbook + audit) |
| 9 | `operator_core/contracts.py` | `CanonicalWorkflowState` | Not persisted (contract type) | Typed contract for workflow snapshots |
| 10 | `rea_runtime.py` | `WaitState`, `WaitStateKind` | SQLite (runtime.db) | REA wait states (approval, feedback, resource) |
| 11 | `amiros.py` | `AMIROSRegistry` | JSONL at `~/.dharma/amiros/` | Research provenance chain (experiments, claims, artifacts) |
| 12 | `hibernation.py` | `JobState` | Not examined in detail | Hibernation job lifecycle |
| 13 | `economic_spine.py` | `MissionState` (enum) | Via runtime_state tables | Economic mission lifecycle states |

### 2. Who is the primary state owner?

**`runtime_state.py:RuntimeStateStore`** is the primary durable state surface. It's a WAL-backed SQLite store providing:
- Session lifecycle (`sessions` table)
- Task claim tracking (`task_claims` table)
- Delegation run tracking (`delegation_runs` table)
- Session event log (`session_events` table with FTS5)
- Correlation context threading

`orchestrate_live.py` is the primary **loop host** — it instantiates `SwarmManager`, which in turn owns `TaskBoard` and the agent pool. But `orchestrate_live.py` doesn't own state itself; it delegates state persistence to `RuntimeStateStore` + various JSONL ledgers.

### 3. Is there a missing `workflowRun` boundary?

**Partially confirmed.** There is no single `workflowRun` type that encapsulates a full execution lifecycle (start→tasks→outcome→feedback). Instead:

- `DelegationRun` (`runtime_state.py:368`) tracks individual task delegations but not the enclosing workflow
- `MissionState` (`mission_contract.py:104`) tracks mission-level lifecycle but not individual run instances
- `LoopHealth` (`loop_supervisor.py:32`) tracks tick-level health but not semantic workflow boundaries
- `CanonicalWorkflowState` (`operator_core/contracts.py:217`) exists as a **typed contract** with `workflow_id`, `status`, `active_lane_ids`, `blocked_by` — but it is not persisted or populated at runtime. It's a declared shape with no producer.

The gap: a workflow starts in `orchestrate_live.py`, tasks get claimed via `RuntimeStateStore`, results flow back through agent responses, but there is no durable record that says "workflow run X started at T1, included tasks [A, B, C], ended at T2 with outcome Y." The `DelegationRun` comes closest but is scoped to a single delegation, not a workflow boundary.

### 4. Multiple owners — harmful or cosmetic?

**Cosmetic fragmentation, not operational collision.** The state owners serve different scopes:
- `RuntimeStateStore` = durable control plane (sessions, claims, delegations)
- `SwarmManager` = in-memory runtime snapshot
- `LoopSupervisor` = health watchdog (read-only consumer of loop ticks)
- `MissionState` = strategic planning layer
- `IterationDepth` = quality ratchet

No two modules write to the same table or file. The "multiple owners" are layered, not competing. The issue is not that they collide — it's that no layer unifies them into a single `workflowRun` boundary.

---

## Headline Verdict: **partially_confirmed**

Codex's claim that "multiple workflow-state owners" exist is **confirmed** — there are at least 13 distinct state surfaces. The claim that they lack a `workflowRun` boundary is **confirmed** — `CanonicalWorkflowState` exists as a contract but has no runtime producer. However, the claim is **overstated** in framing: these are **layered** state surfaces serving different concerns (control plane, mission strategy, quality tracking, health monitoring), not competing owners fighting over the same data. The fragmentation is structural (missing unifying type), not pathological (conflicting writes).

The "LangGraph-style state graph absent" observation is **confirmed** and the most actionable finding: there is no first-class `workflowRun` that traces from dispatch through execution to outcome.
