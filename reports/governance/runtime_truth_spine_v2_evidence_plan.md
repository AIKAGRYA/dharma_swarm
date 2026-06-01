# Runtime Truth Spine v2 Evidence Bundle Plan

Subagent: Tracer/Evidence Captain

Audit source boundary:

- Clean audit baseline: `d5ebc456` from the clean-main architecture audit.
- v2 worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`.
- v2 HEAD inspected by this subagent: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`.
- Source truth rule: tracked clean-main files are source truth. Current v2 working-tree edits are build candidates until committed. Untracked files are evidence candidates only after they are intentionally added.
- External systems: no live Palantir, NATS, Temporal, or paid LLM calls.

## Evidence Bundle Layout

The final v2 evidence bundle should be written under:

`reports/governance/runtime_truth_spine_v2_evidence/`

Expected files:

- `evidence_manifest.md` - SHA, branch, dirty status, test commands, runtime restrictions.
- `surface_matrix.md` - every major organ with `joined`, `adapter-ready`, `quarantine`, or `missing`.
- `surface_matrix.json` - machine-readable copy of the same matrix.
- `tracer_payload.json` - fixed TRCR-9999-ALPHA IDs and expected fields.
- `id_mapping_table.md` - external A2A task ID, task ID, run ID, trace ID, correlation ID, claim ID, idempotency key, artifact ID.
- `trace_timeline.md` - ingress, claim, run, artifact, idempotency, completion receipts.
- `sqlite_query_results.txt` - selected read-only SQL proving runtime tables contain the chain.
- `pytest_results.txt` - exact test command and result.
- `verdict.md` - coverage percentage, proven surfaces, quarantines, missing surfaces, next slices.

## Surface Matrix

Coverage definition:

- `joined`: carries Canonical ExecutionIdentity and writes RuntimeStateStore facts/receipts on the selected path.
- `adapter-ready`: can accept or emit ExecutionIdentity through a compatibility surface, but enforcement is not complete.
- `quarantine`: intentionally excluded from runtime truth claims until wrapped or demoted.
- `missing`: no sufficient identity/ledger enforcement on the selected evidence surface.

| Surface | Status | Evidence expectation |
| --- | --- | --- |
| A2A local submit | joined | RuntimeStateStore identity, A2A receipt, idempotency record before handler side effect |
| A2A HTTP node gateway | adapter-ready | Top-level identity fields are parsed/serialized across request/response |
| RuntimeLifecycle task claim | joined | `record_task_claim(require_identity=True)` fails without identity and writes receipt with run/trace |
| RuntimeLifecycle delegation run | joined | `record_delegation_run(require_identity=True)` writes run facts and receipt |
| RuntimeLifecycle artifact record | joined | `record_artifact(require_identity=True)` persists artifact with run_id and trace_id |
| MessageBus emit_event with idempotency_key | joined | RuntimeStateStore idempotency begins before event insert; duplicate emits no second event |
| Orchestrator result persistence | adapter-ready | Provenance/artifact path carries run_id, trace_id, correlation_id; hard boundary still pending |
| TaskBoard task metadata | adapter-ready | Metadata can carry execution_identity; mandatory enforcement still pending |
| Checkpoint human interrupt | adapter-ready | Checkpoint can carry identity; durable wait/approval receipts still pending |
| Ontology execute_action | missing | C2 tollbooth slice must enforce `ActionDef.modifies` and `requires_approval` |
| Tool registry side effects | missing | Tool calls need mandatory identity plus side_effect_intent/complete receipts |
| Graph/workflow checkpoints | missing | Graph checkpoint identity and resume receipts are not saturated |
| Self-modification proposals | missing | proposal/gate/apply/verify/promote/revert receipts are not saturated |
| NATS/JetStream path | quarantine | Not selected for local deterministic evidence; no live NATS calls |
| MCP server/tool access | missing | MCP/tool boundary needs an adapter before side effects |
| Free-text file extraction | quarantine | Regex path writes must stay quarantined until deterministic tollbooth exists |

Coverage:

- Classified surfaces: 16/16 = 100%.
- Joined surfaces: 5/16 = 31.25%.
- Joined or adapter-ready surfaces: 9/16 = 56.25%.
- Missing or quarantined surfaces: 7/16 = 43.75%.

## TRCR-9999-ALPHA Expectations

Fixed IDs:

- `external_a2a_task_id`: `TRCR-9999-ALPHA`
- `task_id`: `task-trcr-9999-alpha`
- `run_id`: `run-trcr-9999-alpha`
- `trace_id`: `trc-trcr-9999-alpha`
- `correlation_id`: `corr-trcr-9999-alpha`
- `claim_id`: `claim-trcr-9999-alpha`
- `artifact_id`: `artifact-trcr-9999-alpha`
- `idempotency_key`: `idem-trcr-9999-alpha`

Required proof:

- `RuntimeStateStore.get_run_ledger(run_id)` returns identity, run, artifacts, receipts, children, and idempotency records.
- A2A ingress maps `TRCR-9999-ALPHA` to internal `task_id`, `run_id`, `trace_id`, and `correlation_id`.
- Parent run can answer "who spawned this child" through `list_child_runs(parent_run_id)` / `get_run_ledger(parent).children`.
- Every selected artifact has non-empty `run_id` and `trace_id`.
- A2A handler side effect sees an idempotency row with status `started` before handler execution.
- MessageBus event insert sees RuntimeStateStore idempotency before the event row exists.
- Duplicate idempotency key does not repeat the selected side effect.

## Missing Identity Failure Boundaries

Selected hard-fail boundaries:

- `RuntimeLifecycle.record_task_claim(..., require_identity=True)`
- `RuntimeLifecycle.record_delegation_run(..., require_identity=True)`
- `RuntimeLifecycle.record_artifact(..., require_identity=True)`

Expected result:

- Missing trace/correlation/claim identity raises `MissingExecutionIdentity`.
- No partial rows are written to `task_claims`, `delegation_runs`, or `artifact_records`.

Not yet hard-fail by design:

- A2A local ingress currently adapts and fills missing fields where possible. It is selected as an adapter/join surface, not as the missing-identity hard boundary.

## Tests Added By This Subagent

New test scaffold:

`tests/test_runtime_truth_spine_v2_evidence.py`

Test cases:

- `test_v2_surface_matrix_is_classified_and_quantified`
- `test_v2_missing_identity_fails_selected_runtime_boundaries`
- `test_v2_trcr_9999_alpha_reconstructs_chain_of_custody`
- `test_v2_a2a_idempotency_exists_before_handler_side_effect`
- `test_v2_message_bus_idempotency_happens_before_event_insert`

## Verification Commands

Run from `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`:

```bash
python -m compileall -q dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/a2a/a2a_server.py dharma_swarm/a2a/node_gateway.py dharma_swarm/message_bus.py dharma_swarm/checkpoint.py dharma_swarm/orchestrator.py dharma_swarm/spine
pytest -q tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py
pytest -q tests/test_runtime_state.py tests/test_runtime_lifecycle.py tests/test_a2a_spec_conformance.py tests/test_message_bus.py tests/test_checkpoint.py
git diff --check
```

## Final Report Outline

The synthesis report should include:

1. Clean-Source Boundary
2. Changed Files
3. Surface Coverage Table
4. TRCR-9999-ALPHA Chain of Custody
5. Missing Identity Failure Results
6. Idempotency Before Side Effect Results
7. Artifact and Side-Effect Identity Results
8. Quarantined Surfaces
9. Remaining Gaps
10. Next Three Slices

Next three slices:

1. Make A2A ingress require externally supplied identity for production-mode boundaries instead of always adapting missing fields.
2. Convert C2 ontology tollbooth declarations into enforced `ActionDef.modifies` and `requires_approval` behavior with ontology action receipts.
3. Add mandatory side_effect_intent and side_effect_complete receipts to tool, graph checkpoint, and self-modification proposal paths.
