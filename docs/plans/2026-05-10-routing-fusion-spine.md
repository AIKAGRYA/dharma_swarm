# Routing Fusion Spine

**Date:** 2026-05-10
**Branch:** `design/routing-fusion-spine`
**Workspace:** `/Users/dhyana/dharma_swarm_routing_fusion`
**Status:** design workspace opened; implementation not started here

## Purpose

Build a lightning-fast, dynamic, multi-layer routing spine that can use every
available model lane, add new model lanes cheaply, pull local models when
appropriate, and stay plugged into the whole swarm without creating a second
router or a hidden policy brain.

The goal is contract fusion, not file fusion:

```text
intent -> policy -> provider candidates -> attempts -> witness -> outcome
       -> routing memory -> budget state -> resident handoff/retry
```

Every LLM/provider call should either pass through this contract or explicitly
declare why it is outside the routing plane.

## Current Inventory Snapshot

The first read-only scan of the active dirty checkout found:

- 590 Python modules under `dharma_swarm/`
- 719 source Python modules under `dharma_swarm/`, `api/`, and `scripts/`
- 1,342 Python files total including tests
- 12 existing core routing substrate modules
- 84 non-core modules directly importing routing substrate
- 83 modules touching `ProviderType`, `LLMRequest`, or `LLMResponse`
- 23 suspected direct provider-call bypass surfaces
- 111 strong "integrate now" candidates
- 236 next-ring candidates
- 143 Rust-shaped deterministic/data-plane candidates

This clean PR workspace now has an executable scanner in
`dharma_swarm/routing_fusion_inventory.py`. Its current generated manifest is
`docs/plans/routing-fusion-inventory.json` and records:

- 555 Python modules under `dharma_swarm/`
- 670 source Python modules under `dharma_swarm/`, `api/`, and `scripts/`
- 1,288 Python files total including tests
- 11 current main-branch core routing substrate modules
- 83 non-core modules directly importing routing substrate
- 78 modules touching `ProviderType`, `LLMRequest`, or `LLMResponse`
- 35 current direct provider-call suspects

The count difference is expected: this PR branch starts from `origin/main` and
does not include the unmerged Phase 1 `route_witness.py` work from the dirty
local routing worktree.

## Hard Constraints

- No magic router: no decorators, monkey patches, metaclasses, or hidden global
  reranking.
- `ModelRouter` remains execution control plane.
- `ProviderPolicyRouter` remains policy control plane.
- `route_witness` remains emission/normalization only once the Phase 1 witness
  stack is merged into this branch.
- `TelemetryPlaneStore` remains low-level persistence.
- Resident degraded handoff means provider failure is visible and queued; it
  does not fabricate provider success.
- New model lanes must be data/config driven where possible.
- Every failure path must write a witness or a resident handoff unless the
  operator explicitly disables the witness layer.

## Core Modules

These are already routing substrate and should be unified by contract, not
collapsed into one file:

- `dharma_swarm/providers.py`
- `dharma_swarm/provider_policy.py`
- `dharma_swarm/telemetry_plane.py`
- `dharma_swarm/runtime_provider.py`
- `dharma_swarm/routing_memory.py`
- `dharma_swarm/decision_router.py`
- `dharma_swarm/router_v1.py`
- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/agent_registry.py`
- `dharma_swarm/stigmergy.py`

## First Bypass Surfaces To Fuse

These direct provider-call surfaces are the first hardening target. They should
route through a shared routing contract or explicitly emit the canonical witness
and resident handoff:

- `api/routers/chat.py`
- `dharma_swarm/autonomous_agent.py`
- `dharma_swarm/consolidation.py`
- `dharma_swarm/context_agent.py`
- `dharma_swarm/inquiry_substrate_chew.py`
- `dharma_swarm/neural_consolidator.py`
- `dharma_swarm/provider_matrix.py`
- `dharma_swarm/provider_smoke.py`
- `dharma_swarm/scout_framework.py`
- `dharma_swarm/subconscious_hum.py`
- `dharma_swarm/thinkodynamic_director.py`
- `scripts/system_integration_probe.py`

Script/demo callers can follow after production paths are fused.

## Architecture Shape

Introduce a narrow routing contract module only if it removes duplicated
call-site logic. It should be a port/facade over existing systems, not a new
policy brain.

Candidate API:

```python
async def complete_routed(
    *,
    action_name: str,
    request: LLMRequest,
    context: dict[str, Any] | None = None,
    available_provider_types: list[ProviderType] | None = None,
    preferred_runtime: str | None = None,
    caller: str,
    task_type: str = "unknown",
) -> RoutedCompletion:
    ...
```

Required output:

```python
class RoutedCompletion(BaseModel):
    decision: ProviderRouteDecision | None
    response: LLMResponse | None
    outcome: str
    task_signature: str
    resident_handoff: bool = False
```

Rules:

- Calls `ModelRouter.complete_for_task()` for dynamic provider execution.
- Uses `complete_via_preferred_runtime_providers()` only for cheap-first
  runtime chains that are intentionally outside full policy routing.
- Never instantiates raw providers at call sites unless the call is a provider
  smoke/probe and records a probe witness.
- Sends terminal provider failure to resident handoff.
- Emits canonical route witness for every decision and attempt.

## Dynamic Model-Lane Requirements

New model lanes need one place to land:

- provider type
- provider capabilities
- default model
- cost/tier
- local pull instruction if applicable
- health probe
- auth/env requirement
- max context/window hints
- tool support
- structured-output support
- safe fallback class

`model_hierarchy.py` is the current catalog authority. If it becomes too large,
split data from behavior:

```text
model_hierarchy.py          public API + validation
model_catalog.yaml/json     canonical lane data
runtime_provider.py         instantiation/probe
provider_policy.py          candidate selection
```

## Rust/Metalization Boundary

Rust is valuable only after the Python contract stabilizes. Do not rewrite
agent orchestration, provider clients, ontology, or policy objects first.

Good first Rust candidates:

- redaction scanner
- error classifier
- route/cost scoring kernel
- routing-memory ranking
- JSONL schema validation and batch ingest
- circuit-breaker state transition kernel
- graph/SCC and constellation aggregation

Poor first Rust candidates:

- `ModelRouter` orchestration
- provider SDK clients
- `AgentRunner`
- ontology/TelicSeam logic
- launchd/conductor glue

Target shape:

```text
Python policy/orchestration
  -> optional Rust deterministic kernel
  -> Python fallback implementation
```

No required Rust dependency until the Python behavior is fully tested.

## Milestones

1. **Inventory Lock**
   - Done: `dharma_swarm/routing_fusion_inventory.py`.
   - Done: generated manifest at `docs/plans/routing-fusion-inventory.json`.
   - Done: guard test fails when a new raw provider call appears without an
     allowlist update.

2. **Routing Contract Facade**
   - Done: `dharma_swarm/routing_contract.py`.
   - Port one low-risk direct caller.
   - Prove witness, attempts, cost, and resident handoff still emit.

3. **Bypass Collapse**
   - Port production bypasses in batches.
   - Leave smoke/probe/demo bypasses explicit and witness-emitting.

4. **Model Lane Catalog**
   - Normalize provider capability/cost/tier/pull/probe metadata.
   - Add a lane-discovery command that reports available, missing auth, and
     pullable local models.

5. **Resident Consumer**
   - Continuous consumer for resident handoff/action queue.
   - Dedupes handoffs.
   - Retries when lanes recover.
   - Escalates only with typed reason.

6. **Rust Spike**
   - Add optional Rust extension only for redaction or route scoring.
   - Keep Python fallback and parity tests.

## Open Questions

- Should `complete_routed()` return a degraded `LLMResponse` in operator-facing
  flows, or should it keep raising provider failure while resident handoff keeps
  the system awake?
- Should cheap-first runtime chains be absorbed into `ModelRouter`, or remain a
  separate intentional path with canonical witness?
- Should pullable local models be managed by Ollama only at first?
- What is the operator UI for selecting "model lane installed but disabled" vs
  "missing but pullable"?

## Immediate Next Task

Port one low-risk caller to `dharma_swarm.routing_contract.complete_routed()`.
Recommended first target: `api/routers/chat.py` or `dharma_swarm/context_agent.py`.
After that, reduce the allowlist one file at a time as bypasses are fused.
