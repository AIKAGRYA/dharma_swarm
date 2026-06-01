# Runtime Truth Spine v2 Report

## Executive Summary

Runtime Truth Spine v2 was built from a clean worktree at current `origin/main`, not from the dirty developer checkout.

- Worktree: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`
- Branch: `codex/runtime-truth-spine-v2`
- Base SHA: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`
- Base commit: `feat(governance): schema-alignment gate (KARMA) + typed-proposal envelope [Stage-1 additive, post-OMS] (#408)`
- Tracked files at base: 2737
- External systems: no live Palantir, NATS, Temporal, or paid LLM calls were made.

The v1 claim was independently verified and corrected:

- Clean `HEAD` did not contain the v1 spine. Static checks found no `ExecutionIdentity`, `runtime_receipts`, idempotency ledger table, or `TRCR-9999-ALPHA` tracer.
- The v1 spine was ported into this clean v2 branch from the v1 worktree, then verified with tests.
- v2 broadens the spine with compatibility adapters, receipt vocabulary and helpers, fail-closed human interrupt behavior, a gated free-text result path, surface coverage tests, and evidence documentation.

Final verification:

- `159 passed, 2 warnings in 11.99s`
- `python -m compileall` passed on the changed runtime modules.
- `git diff --check` passed before the final report was written.

## Six-Subagent Build

Exactly six bounded subagents were spawned and all completed before synthesis.

1. Surface Inventory Agent, Poincare, `019e830f-d1bf-7791-9c7f-9c361f2927c7`
   - Mapped ingress, dispatch, event, artifact, tool, ontology, graph, and self-mod surfaces.
   - Classified each as joined, adapter-ready, quarantine/transitional, or missing.

2. V1 Verification Agent, Halley, `019e830f-e9fd-7ea3-bef9-f070c27de852`
   - Falsified v1 presence on clean `HEAD`.
   - Verified the ported v1 candidate with focused and adjacent test suites.
   - Wrote `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`.

3. Organ Adapter Agent, Sagan, `019e830f-fd39-7db0-be92-84621d5c0ea9`
   - Added spine adapter helpers in `dharma_swarm/spine/adapters.py`.
   - Covered A2A tasks, TaskBoard tasks, Orchestrator dispatch, MessageBus/event payloads, artifact records, tool calls, ontology action payloads, graph/checkpoint payloads, and self-mod/proposal payloads.

4. Receipt Saturation Agent, Archimedes, `019e8310-1662-70b2-9809-bdecb8ae17f1`
   - Added receipt vocabulary and RuntimeStateStore helper APIs.
   - Added durable receipt support for side-effect intent/completion, artifact writes, message consumption, idempotency consumption, ontology action receipts, child run receipts, and self-mod receipts.

5. Bypass/Tollbooth Agent, Huygens, `019e8310-35db-73c3-90bb-2369debda844`
   - Changed `InterruptGate` to fail closed by default.
   - Gated Orchestrator free-text file writes behind explicit structured metadata.
   - Queued C2 ontology enforcement for the next slice instead of overmixing it into this runtime spine build.

6. Tracer/Evidence Captain, Peirce, `019e8310-563d-7ed2-b86d-cbbd9b041897`
   - Added v2 evidence tests and surface matrix.
   - Verified tracer reconstruction, missing identity failures, idempotency before side effects, and artifact identity fields.
   - Wrote `reports/governance/runtime_truth_spine_v2_evidence_plan.md`.

## Changed Files

Runtime spine and adapters:

- `dharma_swarm/spine/identity.py`
- `dharma_swarm/spine/adapters.py`
- `dharma_swarm/spine/__init__.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`

Ingress, dispatch, events, artifacts, and tollbooths:

- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/checkpoint.py`

Tests and evidence:

- `tests/test_runtime_truth_spine_v1.py`
- `tests/test_runtime_truth_spine_v2_adapters.py`
- `tests/test_runtime_truth_spine_v2_evidence.py`
- `tests/test_runtime_truth_spine_v2_tollbooth.py`
- `tests/test_runtime_state.py`
- `tests/test_runtime_lifecycle.py`
- `tests/test_checkpoint.py`
- `reports/governance/runtime_truth_spine_v2_subagent2_v1_verification.md`
- `reports/governance/runtime_truth_spine_v2_evidence_plan.md`
- `reports/governance/runtime_truth_spine_v2_report.md`

## Main Implementation Points

Canonical identity:

- `ExecutionIdentity` is defined in `dharma_swarm/spine/identity.py:29`.
- `RuntimeLifecycle.ensure_execution_identity` enforces identity creation and persistence for selected runtime paths in `dharma_swarm/runtime_lifecycle.py:76`.

Compatibility adapters:

- `identity_from_carrier` in `dharma_swarm/spine/adapters.py:155`
- `adapt_execution_identity` in `dharma_swarm/spine/adapters.py:276`
- `runtime_receipt_kwargs` in `dharma_swarm/spine/adapters.py:303`

Durable ledger and receipts:

- Runtime receipt vocabulary starts at `dharma_swarm/runtime_state.py:308`.
- Side-effect intent/completion helpers start at `dharma_swarm/runtime_state.py:2229`.
- Message consumption helper starts at `dharma_swarm/runtime_state.py:2299`.
- Ontology action receipt helper starts at `dharma_swarm/runtime_state.py:2314`.
- Self-mod receipt helper starts at `dharma_swarm/runtime_state.py:2364`.
- Run ledger reconstruction starts at `dharma_swarm/runtime_state.py:2765`.

Tollbooth changes:

- `InterruptGate` now defaults to `auto_approve=False` in `dharma_swarm/checkpoint.py:78` and `dharma_swarm/checkpoint.py:102`.
- Orchestrator free-text path extraction now requires `task_metadata.get("allow_free_text_result_path") is True` in `dharma_swarm/orchestrator.py:2467`.

## Surface Coverage

The v2 evidence matrix classifies 16 surfaces.

- Classified: 16 / 16, 100%
- Joined: 5 / 16, 31.25%
- Joined or adapter-ready: 9 / 16, 56.25%

Joined surfaces include the selected runtime spine path:

- A2A/local ingress
- RuntimeLifecycle delegation path
- RuntimeStateStore ledger
- selected artifact/completion receipt path
- selected idempotency path

Adapter-ready surfaces include:

- TaskBoard task payloads
- Orchestrator dispatch payloads
- MessageBus/event payloads
- tool call payloads
- ontology action payloads
- graph/checkpoint payloads
- self-mod/proposal payloads

Remaining quarantined or missing surfaces are listed in the evidence plan and should not be treated as canonical until joined or wrapped.

## Done Criteria Status

- V1 claims independently verified or corrected: done. Clean `HEAD` lacked v1; ported candidate passes tests.
- Every major organ has status joined, adapter, quarantine, or missing: done in the v2 surface matrix.
- At least three real surfaces beyond original tracer path wired or adapter-ready: done.
  - Tool call payloads can carry adapted identity.
  - Ontology action payloads can carry adapted identity.
  - Graph/checkpoint payloads can carry adapted identity.
  - Self-mod/proposal payloads can carry adapted identity.
  - MessageBus/event payloads can carry adapted identity.
- No artifact/side effect in selected surfaces lacks `run_id` and `trace_id`: done for selected tested surfaces.
- Duplicate idempotency tested before side effects: done for selected RuntimeStateStore/A2A and MessageBus paths.
- Missing identity fails on selected runtime boundaries: done for selected RuntimeStateStore and RuntimeLifecycle boundaries.
- TRCR-9999-ALPHA tracer reconstructs ingress-to-artifact by `run_id`, `trace_id`, and `correlation_id`: done in `tests/test_runtime_truth_spine_v2_evidence.py`.

## Tests Run

Focused and adjacent verification:

```bash
env HOME=/private/tmp/dharma_spine_v2_test_home pytest -q \
  tests/test_runtime_truth_spine_v1.py \
  tests/test_runtime_truth_spine_v2_adapters.py \
  tests/test_runtime_truth_spine_v2_evidence.py \
  tests/test_runtime_truth_spine_v2_tollbooth.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py \
  tests/test_a2a_spec_conformance.py \
  tests/test_message_bus.py \
  tests/test_checkpoint.py \
  tests/test_orchestrator.py
```

Result:

```text
159 passed, 2 warnings in 11.99s
```

Compile verification:

```bash
python -m compileall -q \
  dharma_swarm/spine/identity.py \
  dharma_swarm/spine/adapters.py \
  dharma_swarm/runtime_state.py \
  dharma_swarm/runtime_lifecycle.py \
  dharma_swarm/a2a/a2a_server.py \
  dharma_swarm/a2a/node_gateway.py \
  dharma_swarm/message_bus.py \
  dharma_swarm/orchestrator.py \
  dharma_swarm/checkpoint.py
```

Result: passed.

Diff whitespace check:

```bash
git diff --check
```

Result: passed before this final report was added.

## Remaining Gaps

1. C2 ontology tollbooth is still queued, not completed in this slice.
   - `ActionDef.modifies` and `ActionDef.requires_approval` still need to become enforced runtime contracts.
   - This was intentionally not mixed into the v2 runtime spine saturation work.

2. Receipt helpers are broader than their call-site coverage.
   - RuntimeStateStore can now record message, ontology, self-mod, idempotency, side-effect, artifact, and child receipts.
   - Actual hot-path call sites still need to be wired one by one for MessageBus consumption, OntologyRegistry action execution, and self-mod proposal/gate/apply/verify/promote/revert.

3. More runtime boundaries need mandatory identity.
   - TaskBoard create/create_batch, ArtifactStore and EngineArtifactStore writes, ToolRegistry side effects, graph/checkpoint resume, and ontology action execution should reject missing identity or adapt from a parent identity.

4. Compatibility adapters are intentionally permissive.
   - They make identity carryable across organs.
   - They do not yet make every organ canonical. Canonical enforcement belongs at the runtime ledger boundary and selected hot-path gateways.

5. Context+ static analysis was not accepted as final evidence.
   - The Context+ tool targeted `/Users/dhyana/dharma_swarm`, the dirty default checkout, not this clean v2 worktree.
   - Compile and pytest results from this clean worktree are the valid evidence.

## Next Three Slices

1. Close the C2 ontology tollbooth.
   - Enforce `ActionDef.modifies` and `ActionDef.requires_approval` in the action execution chokepoint.
   - Write `ontology_action_requested` before the mutation and `ontology_action_applied` only after the mutation.
   - Tests must prove that declared modifies actually mutate, approval-required actions block without approval, and missing identity fails.

2. Wire receipt helpers into hot call sites.
   - MessageBus: record `message_consumed` and idempotency receipts before handler side effects.
   - Ontology: record action request/apply receipts around enforced mutations.
   - Self-mod: record proposal, gate, apply, verify, promote, and revert receipts as a closed loop.
   - Tests must prove ledger reconstruction by `run_id`, `trace_id`, `correlation_id`, and proposal/action/message IDs.

3. Promote adapter-ready surfaces to mandatory identity boundaries.
   - TaskBoard task creation, artifact stores, tool runner side effects, graph/checkpoint resume, and self-mod proposal ingestion should require identity or derive it from a parent identity.
   - Tests must prove missing identity fails and duplicate idempotency does not repeat side effects.

## Bottom Line

The v2 branch does not claim the entire platform is canonical yet. It makes the spine real on one tracer-backed path, verifies v1 instead of trusting it, broadens identity compatibility across connected organs, adds durable receipt vocabulary and helper APIs, closes two concrete bypasses, and leaves a classified surface matrix for the remaining saturation work.
