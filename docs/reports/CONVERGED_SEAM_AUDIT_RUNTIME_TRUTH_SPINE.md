# Converged Seam Audit — Runtime Truth Spine

**Date:** 2026-05-28  
**Repo:** `AmitabhainArunachala/dharma_swarm`  
**Status:** Converged audit between the Perplexity seam audit provided by John and Codex review in ChatGPT.  
**Purpose:** Establish one shared diagnosis and one shared build direction before more agent-fabric work begins.

---

## 0. Signature / Sign-off

This document is the single consensus artifact for the current routing × pool × A2A × provider seam review.

- **Perplexity audit position:** Accepted as the implementation-level diagnosis: the A2A module is clean, while `agent_runner.py`, `swarm.py`, `orchestrator.py`, and `providers.py` carry the bulk of the complexity and accretion.
- **Codex / ChatGPT position:** Accepted as the system-level prescription: do not add more fabric first; compress the system around one blessed runtime rail.
- **Converged position:** Build the Runtime Truth Spine before expanding persistent agent fabric.

This is not a claim that every line below was independently authored by both systems. It is the shared synthesis John asked to preserve as the working doctrine for the next build step.

---

## 1. Final Verdict

Dharma Swarm is not fake AI vapor. It is a real system with several strong organs.

But it is not elegant and simple across the board yet.

The accurate diagnosis is:

> **Dharma Swarm is agent-built system accretion: roughly real engineering with concentrated bloat in a few high-gravity files.**

The strongest recent layer is A2A. The most tangled older layers are the orchestrator / runner / swarm lifecycle core.

The system is bleeding-edge in selected places:

- A2A Tier-1 compatibility
- cross-agent task semantics
- context IDs
- cycle detection
- many provider lanes
- telos / witness / extension concepts
- lifecycle and evidence ambitions

But it is behind its own ambition in one critical way:

> There is no single obvious path an agent author should call when they want work to happen.

An agent still has to infer whether to use:

- `A2AClient`
- `SwarmManager`
- `Orchestrator`
- `AgentPool`
- `AgentRunner`
- provider router
- `MessageBus`
- `SessionLedger`
- runtime lifecycle
- telemetry plane
- witness
- telos seam
- provenance log
- operator brief persistence

That is the core problem.

---

## 2. Shared Diagnosis

Perplexity and Codex converged on the same root issue from two angles.

| Axis | Implementation audit | System audit | Joint verdict |
|---|---|---|---|
| A2A | Clean, focused modules | Real protocol substrate after PR #362 | Good foundation |
| Orchestrator | Architecturally right, organizationally heavy | Too many responsibilities in dispatch path | Needs compression |
| AgentRunner | `run_task` is too large and accreted | Provider call, memory, evidence, registry, telos, lineage all mixed | Biggest tangle |
| SwarmManager | Wiring god object | Too many subsystem references and unclear entrypoint | Needs assembly boundary |
| providers.py | Functionally useful, file-level hoarding | Provider abstraction is good but bloated | Split later, not first |
| Truth surfaces | Many overlapping persistence systems | No canonical receipt | Biggest cognitive load |

The disease is not lack of features. The disease is unclear ownership of runtime truth.

---

## 3. What Is Clean

### A2A Layer

The A2A layer is now the cleanest major seam.

It has focused files:

- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/a2a_client.py`
- `dharma_swarm/a2a/agent_card.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/a2a/node_registry.py`
- `dharma_swarm/a2a/a2a_bridge.py`

After PR #362 it supports:

- 8 task states
- `context_id`
- strict-ish part construction
- artifacts/history split
- AgentSkill / AgentCard
- supported interfaces and security declarations
- gateway paths
- cycle detection lifecycle
- backward compatibility

This layer should be treated as infrastructure, not rewritten.

### Provider Abstraction

The provider abstraction itself is good:

- providers implement `complete()`
- providers implement `stream()`
- missing API keys are tolerated until use
- many provider lanes exist

The problem is organizational, not conceptual: too many provider classes live in one file.

### AgentPool Concept

`AgentPool` is simple and lock-protected. Its design is mostly fine.

The problems are:

- it is buried inside `agent_runner.py`
- `get_result()` returns `None` only to satisfy an interface
- the dispatch path still relies on looking runners back up after routing

---

## 4. What Is Tangled

### `AgentRunner.run_task`

This is the biggest localized tangle.

It nominally means:

> take a task, produce a result string

But it also performs or triggers:

- lifecycle event emission
- provider routing
- provider call
- response interpretation
- observability traces
- guardrails
- memory write-back
- mem-action parsing
- lineage recording
- retrieval outcome recording
- idea uptake
- fitness signaling
- AgentRegistry logging
- telic seam outcome/value/contribution recording
- error handling
- state transitions

That is too much for one method.

However, decomposing it immediately is not the first move. If it is decomposed before the blessed rail exists, the repo may simply get 12 helper methods orbiting the same unclear center.

### `SwarmManager`

`SwarmManager` currently acts as a manual dependency-injection container, lifecycle shell, subsystem registry, crew spawner, bootstrapper, and runtime coordinator.

This is understandable historically, but it creates high cognitive load.

The long-term direction is to extract assembly/wiring into a dedicated assembly layer. But again, not first.

### `Orchestrator`

The orchestrator has good basic architecture:

- ready tasks
- idle agents
- dispatch assignment
- fan-out/fan-in
- topology genome handling

But it also owns too much lifecycle and failure complexity.

The immediate problem is not that the orchestrator is large. The immediate problem is that the dispatch boundary is not canonicalized into one receipt and one invocation path.

### Truth-Surface Explosion

The repo has too many plausible answers to the question:

> Where does “what happened” get recorded?

Known truth/persistence surfaces include:

- `session_ledger.py`
- `runtime_lifecycle.py`
- `telemetry_plane.py`
- `agent_registry.py`
- `witness.py`
- `engine/event_memory.py`
- `operator_brief/persistence.py`
- `board/event_log.py`
- `sakshi/provenance_log.py`
- `message_bus.py`
- `lineage.py`
- `telic_seam.py`

Some of these may be valuable. The issue is not that they exist. The issue is that none is clearly the canonical record.

The system needs one root fact stream and derived views.

---

## 5. Current Root Invariant

The next layer should be built around this invariant:

```text
Task exists
+ Runner exists
+ Dispatch claim exists
+ Context exists
+ Routing decision exists
+ Provider call is attempted or explicitly skipped
+ Evidence receipt exists
= safe execution path
```

If any link fails, the system must say which link failed.

No more generic `dispatch_dropoff` ambiguity.

No more guessing whether a failure was provider/API-key related when execution never reached the provider.

---

## 6. The Blessed Spine

The system should converge on one runtime rail:

```text
Objective
  → Task
  → RoutingDecision
  → DispatchClaim
  → Runner
  → ProviderCall
  → Artifact
  → EvidenceReceipt
```

Everything else attaches to this spine:

- A2A attaches at Task / context / Artifact boundaries.
- Telos attaches as pre/post gates on RoutingDecision and EvidenceReceipt.
- Witness attaches as an audit plugin over EvidenceReceipt.
- AgentRegistry becomes a derived identity/fitness view.
- Telemetry becomes an export of EvidenceReceipt.
- Dashboard reads EvidenceReceipt or derived projections.
- Provider feedback becomes part of RoutingDecision and EvidenceReceipt.
- SessionLedger/runtime lifecycle become canonical sinks or compatibility mirrors during migration.

---

## 7. Tier 1 Build Direction

### Fix 1 — Runtime Truth Spine

Define one canonical `EvidenceReceipt` for dispatch execution.

A receipt should include at minimum:

```yaml
evidence_id:
trace_id:
context_id:
task_id:
agent_id:
routing_decision_id:
claim_id:
runner_exists:
task_exists:
claim_status:
provider:
model:
provider_attempted:
result_artifact_ids:
error:
error_source:
started_at:
finished_at:
latency_ms:
metadata:
```

Result and error should be one-of in spirit: a completed receipt has result artifacts; a failed receipt has error/error_source.

Every dispatch should produce exactly one receipt.

During migration, this receipt may also write to existing surfaces. But the receipt is the canonical object.

### Fix 2 — One Agent Invocation API

Create a single blessed API:

```python
async def invoke_agent(task: Task, agent_id: str, context_id: str) -> EvidenceReceipt:
    ...
```

This is the internal rail agents call.

It can delegate internally to existing systems:

- Orchestrator
- AgentPool
- AgentRunner
- A2AClient
- provider router
- runtime lifecycle

But callers should not need to know those details.

The agent-author question becomes simple:

> “How do I ask an agent to do work?”

Answer:

> `invoke_agent(...)`

### Fix 3 — One RoutingDecision Object

Define one canonical routing object:

```python
@dataclass
class RoutingDecision:
    decision_id: str
    context_id: str
    task_id: str
    agent_id: str
    provider: str
    model: str
    reason: str
    scores: dict[str, float]
    fallback_plan: list[str]
    created_at: str
```

This should replace scattered implicit decisions across:

- `_select_idle_agent`
- A2A discovery
- ModelRouter
- IntentRouter
- topology genome selection
- provider fallback

Do not replace all of those systems in one PR. First make them emit or consume this shared object.

---

## 8. OTel / GenAI Position

The EvidenceReceipt should be designed so it can serialize cleanly into OpenTelemetry GenAI spans.

Important nuance:

OpenTelemetry has official GenAI semantic conventions for agent spans, model spans, events, exceptions, metrics, and provider-specific systems such as OpenAI and Anthropic. But the OpenTelemetry GenAI page currently marks the status as **Development**, with explicit opt-in guidance for latest experimental GenAI conventions.

Therefore:

- Do not claim OTel GenAI is a fully stable default standard.
- Do design EvidenceReceipt with OTel-compatible field names where practical.
- Do include `trace_id`, `span_id` or equivalent, provider, model, operation, token counts, latency, error type, and result metadata.
- Do make OTel export an adapter, not a second truth surface.

The correct framing:

> EvidenceReceipt is the canonical internal receipt. OTel GenAI serialization is an export format / interoperability lane.

---

## 9. Anti-Accretion Rule

To prevent another truth surface from appearing, add a CI/governance rule:

> Any new file under `dharma_swarm/` that imports `sqlite3` or `aiosqlite` must declare in its module docstring how it relates to the `EvidenceReceipt` stream.

Allowed roles:

- canonical store
- derived view
- plugin sink
- denormalized cache
- migration compatibility mirror

If a file cannot state its relation to EvidenceReceipt, it should not create a new persistence surface.

This is the kill switch against future AI-accretion.

---

## 10. What Not To Do Next

Do not immediately:

- build a new agent fabric framework
- introduce NATS / Redis / gRPC
- shard providers first
- rewrite SwarmManager first
- decompose all of `run_task` first
- create another dashboard truth source
- add another registry
- create another event log
- add another spiritual/metaphoric naming layer

Those may all become valid later. But doing them before the spine will increase surface area.

---

## 11. Recommended PR Sequence

### PR 1 — Runtime Truth Spine

Goal:

- Add `EvidenceReceipt`
- Add receipt creation at the dispatch boundary
- Split `dispatch_dropoff` into precise reasons
- Confirm task-missing vs runner-missing vs both-missing
- Store or mirror receipts through existing runtime lifecycle without creating a new competing truth surface if possible

Acceptance tests:

- normal task + runner path emits success receipt
- missing task emits `task_missing` receipt
- missing runner emits `runner_missing` receipt
- missing both emits `task_and_runner_missing` receipt
- provider failure is not confused with dispatch dropoff

### PR 2 — Blessed Invocation API

Goal:

- Add `invoke_agent(task, agent_id, context_id)`
- Make it return `EvidenceReceipt`
- Use existing Orchestrator/AgentPool/AgentRunner underneath
- Do not change broad behavior

Acceptance tests:

- one local agent invocation succeeds
- failed invocation returns structured receipt
- A2A task context flows into receipt
- existing orchestrator tests still pass

### PR 3 — RoutingDecision

Goal:

- Add canonical `RoutingDecision`
- Make current routing emit it
- Attach it to dispatch claim / receipt metadata
- Do not rewrite all routing logic yet

Acceptance tests:

- route_next emits decision
- A2A delegation can attach decision
- provider/model selection recorded
- fallback plan recorded when used

### PR 4 — Refactor After Spine

Only after PRs 1–3:

- decompose `AgentRunner.run_task`
- move `AgentPool` to `agent_pool.py`
- remove or fix lying `get_result` protocol
- split provider classes into provider files
- extract `SwarmAssembly` from `swarm.py`

The spine tells us where to cut.

---

## 12. Final Consensus Statement

Is Dharma Swarm elegant and simple across the board?

No.

Is it AI slop?

Not primarily. It is real engineering with agent-built accretion. The bloat is concentrated and fixable.

Is it bleeding-edge?

Selectively yes. A2A and multi-provider ambition are strong. Runtime truth and observability need compression.

What is the next move?

Not more fabric. Not more abstractions. Not a rewrite.

The next move is:

```text
One invariant.
One invocation path.
One routing decision.
One evidence receipt.
One dashboard truth surface.
```

That is the 1000x simplification.

---

## 13. Master Prompt for Devin

Use this prompt for the next implementation agent:

```markdown
You are Devin working in `AmitabhainArunachala/dharma_swarm` after PR #362 merged.

Do not build new agent fabric first.

Read `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md` completely before touching code.

Your mission is PR 1: Runtime Truth Spine.

Implement the smallest behavior-preserving spine that makes every dispatch produce one canonical EvidenceReceipt or equivalent runtime lifecycle record.

Start by auditing the current dispatch boundary in `dharma_swarm/orchestrator.py`, especially `_assign_dispatch`, `route_next`, `_handle_task_failure`, and runtime lifecycle claim recording.

Confirm the current `dispatch_dropoff` failure shape from `state/runtime.db` if a live DB is available. If no live DB is available, add tests that simulate:

1. task missing after route selection
2. runner missing after route selection
3. both missing
4. normal execution path
5. provider failure after runner/task exist

Then implement:

- precise dropoff error sources: `task_missing`, `runner_missing`, `task_and_runner_missing`
- structured receipt metadata with task/runner/claim/context fields
- one receipt per attempted dispatch
- no provider/API-key blame unless execution reaches provider call
- no new persistence surface unless it is explicitly declared as canonical/derived/plugin/cache/migration mirror

Do not decompose `AgentRunner.run_task` in this PR except where absolutely necessary.
Do not split providers.
Do not rewrite SwarmManager.
Do not introduce NATS, Redis, gRPC, or a new daemon.
Do not create a second event log.

Add tests and documentation.

PR title suggestion:

`feat(runtime): add dispatch EvidenceReceipt spine and precise dropoff causes`

Success criteria:

- every dispatch path has a receipt
- missing task and missing runner are distinguishable
- existing A2A/fleet/handoff/orchestrator tests pass
- no new truth surface appears without declaration
- the next PR can cleanly add `invoke_agent(...)`
```
