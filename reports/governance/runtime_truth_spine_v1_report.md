# Runtime Truth Spine v1 Report

## Audit Surface

- Worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v1`
- Branch: `codex/runtime-truth-spine-v1`
- Base: `7198f340ce623124c75c945b21a950634619783a`
- Base commit: `feat(ontology): OMS hardening - TypeStatus lifecycle, api_name, uniqueness guard (#409)`
- Audit baseline used as ground truth: clean-main audit at `d5ebc456`, plus Claude/fan-out corroboration.
- Dirty source rule: no implementation evidence was taken from `/Users/dhyana/dharma_swarm`.
- External systems: no live Palantir, NATS, Temporal, or paid LLM calls.

Origin/main had advanced past `d5ebc456`; this build was taken from a clean branch off current `origin/main` and used the `d5ebc456` audit as the problem statement, not as a mutable source tree.

## Six Bounded Subagents

Exactly six bounded subagents were used:

1. Identity Contract: `019e82af-3764-7392-b513-497acdbc79c2`
2. Runtime Ledger: `019e82af-47f3-70a3-bff7-44ea7a143ba2`
3. Ingress/A2A Adapter: `019e82af-58dc-7001-93bb-f806c9d9de1f`
4. Dispatch/Artifact Spine: `019e82af-69ad-7e43-94dd-cc7ba894afc9`
5. Idempotency/Event Adapter: `019e82af-7f51-73e0-a4bd-acd14cd4f662`
6. Tracer/Test/Integration Captain: `019e82af-9106-7210-8098-d1c0d9896cc8`

## Changed Files

- `dharma_swarm/spine/identity.py`
- `dharma_swarm/spine/__init__.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`
- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/orchestrator.py`
- `tests/test_runtime_truth_spine_v1.py`

## Invariants Locked In This Slice

1. A canonical `ExecutionIdentity` now exists in `dharma_swarm/spine/identity.py`.
   It carries `trace_id`, `correlation_id`, `task_id`, `run_id`, `claim_id`, `idempotency_key`, optional parent/external IDs, and metadata.

2. The selected path can require identity.
   `RuntimeLifecycle.ensure_execution_identity(..., require=True)` fails fast if required identity fields are missing.

3. `RuntimeStateStore` now has durable spine tables:
   `execution_identities`, `runtime_receipts`, and `idempotency_records`.

4. `RuntimeStateStore.get_run_ledger(run_id)` answers the selected audit question:
   identity, run, artifacts, receipts, child runs, and idempotency records for a run.

5. A2A ingress can persist external/internal identity mapping.
   `A2AServer(..., runtime_state=store, require_execution_identity=True)` records `external_a2a_task_id` mapped to internal `task_id`, `run_id`, `trace_id`, and `correlation_id`.

6. Artifact writes in the selected path carry `run_id` and `trace_id`.
   `ArtifactRecord` and `artifact_records` now include `trace_id`.

7. Duplicate idempotency keys can suppress repeated side effects in the selected path.
   `RuntimeStateStore.try_begin_idempotent_side_effect*` gates A2A handler execution and optional `MessageBus.emit_event(..., idempotency_key=...)`.

8. Orchestrator dispatch now attaches execution identity before dispatch metadata leaves `_assign_dispatch`.
   The path records task-claim and delegation-run receipts before dispatch proceeds.

## Evidence

Key code locations:

- `ExecutionIdentity`: `dharma_swarm/spine/identity.py:29`
- Required identity helper: `dharma_swarm/spine/identity.py:175`
- Runtime lifecycle identity enforcement: `dharma_swarm/runtime_lifecycle.py:76`
- Runtime lifecycle delegation receipts: `dharma_swarm/runtime_lifecycle.py:285`
- Runtime lifecycle artifact receipts: `dharma_swarm/runtime_lifecycle.py:367`
- RuntimeStateStore identity writes: `dharma_swarm/runtime_state.py:2002`
- RuntimeStateStore idempotency gate: `dharma_swarm/runtime_state.py:2187`
- RuntimeStateStore run ledger query: `dharma_swarm/runtime_state.py:2411`
- A2A ingress identity mapping: `dharma_swarm/a2a/a2a_server.py:313`
- A2A identity normalization: `dharma_swarm/a2a/a2a_server.py:399`
- Optional MessageBus idempotency gate: `dharma_swarm/message_bus.py:591`
- Orchestrator identity attach point: `dharma_swarm/orchestrator.py:2003`
- Orchestrator dispatch/delegation receipt point: `dharma_swarm/orchestrator.py:2036`

Tracer tests:

- Missing identity fails: `tests/test_runtime_truth_spine_v1.py:73`
- Lifecycle/artifact/run reconstruction: `tests/test_runtime_truth_spine_v1.py:110`
- A2A external/internal ID mapping and duplicate suppression: `tests/test_runtime_truth_spine_v1.py:181`
- MessageBus idempotency suppression: `tests/test_runtime_truth_spine_v1.py:239`

Tracer identity:

- `external_a2a_task_id`: `TRCR-9999-ALPHA`
- `trace_id`: `trc-trcr-9999-alpha`
- `correlation_id`: `corr-trcr-9999-alpha`
- `run_id`: `run-trcr-9999-alpha`
- `task_id`: `task-trcr-9999-alpha`
- `claim_id`: `claim-trcr-9999-alpha`
- `artifact_id`: `artifact-trcr-9999-alpha`
- `idempotency_key`: `idem-trcr-9999-alpha`

## Tests Run

Commands:

```bash
python -m compileall -q dharma_swarm/spine/identity.py dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/a2a/a2a_server.py dharma_swarm/a2a/node_gateway.py dharma_swarm/message_bus.py dharma_swarm/orchestrator.py
git diff --check
env HOME=/private/tmp/dharma_spine_test_home pytest -q tests/test_orchestrator.py tests/test_runtime_truth_spine_v1.py
env HOME=/private/tmp/dharma_spine_test_home pytest -q tests/test_runtime_truth_spine_v1.py tests/test_runtime_state.py tests/test_runtime_lifecycle.py tests/test_a2a_spec_conformance.py tests/test_message_bus.py tests/test_orchestrator.py
```

Results:

- `compileall`: passed
- `git diff --check`: passed
- Orchestrator plus tracer tests: `38 passed, 2 warnings in 11.89s`
- Focused runtime/A2A/message/orchestrator suite: `133 passed, 2 warnings in 13.78s`

The tests were run with an isolated `HOME` so the default local runtime DB did not contend with stale developer-local SQLite locks. A prior non-isolated orchestrator run completed but took 132 seconds because it shared the developer-local `~/.dharma/state/runtime.db`.

## Done Criteria Status

- Missing identity fails on selected path: done.
- A2A/local ingress durably maps external/internal IDs: done for A2A ingress and RuntimeLifecycle local path.
- Every selected-path artifact has `run_id` and `trace_id`: done.
- Duplicate idempotency key does not repeat selected side effect: done for A2A handler and optional MessageBus event emission.
- `TRCR-9999-ALPHA` reconstructs ingress-to-artifact by run/trace/correlation: done in `test_trcr_9999_alpha_lifecycle_artifact_and_run_reconstruct` and `test_trcr_9999_alpha_a2a_ingress_maps_ids_and_dedupes`.
- Final report lists changed files, tests, remaining gaps, and next slice: done.

## Remaining Gaps

1. This is one tracer-backed path, not a universal runtime migration.
   Legacy callers can still use RuntimeStateStore, MessageBus, A2A, and Orchestrator without strict identity enforcement unless they opt into the selected path or pass `require_execution_identity=True`.

2. A2A task lifecycle is not fully restart-safe yet.
   The selected path records identity/idempotency facts durably, but full A2A task status/result durability is still outside this slice.

3. MessageBus idempotency is optional.
   Callers that omit `idempotency_key` still use legacy behavior.

4. Idempotency conflict checking is minimal.
   Duplicate suppression is keyed by `(idempotency_key, side_effect_key)`; this slice does not yet reject the same idempotency key reused with a semantically different operation payload.

5. Parent/child query support exists through `parent_run_id` and `list_child_runs`, but this slice does not migrate every swarm child-spawn surface to require `parent_run_id`.

6. Default local state contention remains an operator hygiene issue.
   Existing tests and local runs still default to `~/.dharma/state/runtime.db` unless isolated via `HOME`, explicit ledger/runtime paths, or future config.

## C2 Ontology Tollbooth Queue

Queued, not mixed into this slice:

- `ActionDef.modifies` is declared at `dharma_swarm/ontology.py:172`.
- `ActionDef.requires_approval` is declared at `dharma_swarm/ontology.py:174`.
- `OntologyRegistry.execute_action` reaches success at `dharma_swarm/ontology.py:876` after gates, but this slice did not change ontology mutation/application behavior.

Next C2 slice should make `ActionDef.modifies` and `requires_approval` enforced contracts:

1. Add an approval provider/interface that blocks `requires_approval=True` actions unless approval is present.
2. Add a deterministic mutation gateway for `modifies` that applies allowed object-property changes and rejects undeclared changes.
3. Add tests proving declared modifies mutate state, undeclared modifies are blocked, and approval-required actions cannot succeed without approval.

## Next Slice

Make Runtime Truth Spine mandatory for one more boundary at a time:

1. Promote `ExecutionIdentity` to a required constructor/input for selected A2A/local task creation APIs.
2. Make all selected path artifacts and side effects require a pre-existing idempotency receipt before write.
3. Implement the C2 ontology tollbooth fix separately so domain mutation governance becomes enforcement, not declaration.

