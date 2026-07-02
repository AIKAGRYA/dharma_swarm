# Operator Idea Spark Real Semantic Drill - 2026-06-27T23:00:21Z

## Scope

Two existing system ideas were selected from the repo corpus and pushed through the live Operator Idea Spark intake path:

1. A2A consumer-liveness projection from `reports/handoffs/HUB_INBOUND_2026-06-12.md`.
2. Revenue Wedge Pipeline loop from `dharma_swarm/revenue/wedge_pipeline.py`.

The drill used the live default state root:

`/Users/dhyana/.dharma/meta/idea_spark`

Authority was kept at `proposal`; no dispatch authority was granted.

## First Run Result

Both ideas completed ingestion, Chetana staging, MemoryKernel write/canonical receipt creation, proposal queueing, and retrieval by correlation ID.

Both also failed the real semantic routing check:

- `corr_7c9508b889225b21` / `cand_f1c963ef7278827c` - blocker: `semantic_commons_unresolved`
- `corr_26ced8dd92591a85` / `cand_501e055d55f9db4f` - blocker: `semantic_commons_unresolved`

Direct routing receipts showed:

- no `canonical_targets`
- no `matched_aliases`
- no `owner_surface`
- unresolved semantic route

This was a real ontology coverage gap, not an ingest or retrieval failure.

## Repairs Made

Added Semantic Commons coverage for:

- `semobj.a2a_consumer_liveness_projection`
  - owner surface: `scripts/governance/agent_onboard.py`
  - source path: `reports/handoffs/HUB_INBOUND_2026-06-12.md`
- `semobj.revenue_wedge_pipeline`
  - owner surface: `dharma_swarm/revenue/wedge_pipeline.py`
  - source path: `dharma_swarm/revenue/wedge_pipeline.py`

Added matching aliases in `docs/ontology/semantic_aliases.yaml`.

Fixed lifecycle receipt consistency:

- `update_lifecycle_receipt(..., blockers=[])` now clears resolved blockers.
- resolved semantic routing now passes `blockers=[]`.
- regression test added for unresolved-then-resolved routing on the same correlation ID.

## Final Live Result

After repair, rerunning the same two ideas produced clean semantic routes and clear retrieval:

### A2A Consumer Liveness Projection

- correlation ID: `corr_7c9508b889225b21`
- candidate ID: `cand_f1c963ef7278827c`
- semantic object: `semobj.a2a_consumer_liveness_projection`
- lifecycle route: `route.semantic_commons_campaign`
- owner surface: `scripts/governance/agent_onboard.py`
- blockers: `[]`
- retrieval: `found: true`
- latest Chetana staged atom: `/Users/dhyana/.dharma/knowledge/staging/2026-06-28/e162ef47-3e87-4720-841f-69c0a65385b6.md`
- latest MemoryKernel write receipt: `memory_kernel_write_receipt:5e511a36b2c50bf78820e8bc`
- latest MemoryKernel canonical receipt: `memory_kernel_canonical_receipt:b390b445853f7ade4bc9edb2`

### Revenue Wedge Pipeline

- correlation ID: `corr_26ced8dd92591a85`
- candidate ID: `cand_501e055d55f9db4f`
- semantic object: `semobj.revenue_wedge_pipeline`
- lifecycle route: `route.semantic_commons_campaign`
- owner surface: `dharma_swarm/revenue/wedge_pipeline.py`
- blockers: `[]`
- retrieval: `found: true`
- latest Chetana staged atom: `/Users/dhyana/.dharma/knowledge/staging/2026-06-28/83e36e34-972c-49fa-82ba-fcf144653607.md`
- latest MemoryKernel write receipt: `memory_kernel_write_receipt:6089fe6bcbc9cf26b39052d4`
- latest MemoryKernel canonical receipt: `memory_kernel_canonical_receipt:5532415236875a94188f0353`

## Health Output

`python -m dharma_swarm.idea_spark.cli health --include-chetana-backlog --json`

Key fields:

- `input_receipts`: 3
- `candidates.total`: 3
- `routing_receipts`: 3
- `memory_canonical_receipts`: 7
- `lifecycle.total`: 3
- `lifecycle.routed`: 3
- `lifecycle.blocked`: 0
- `lifecycle.completion_rate`: 1.0

## Verification

Commands passed:

```bash
./.venv/bin/python -m py_compile dharma_swarm/idea_spark/store.py dharma_swarm/idea_spark/semantic_routing.py
./.venv/bin/python -m pytest -q tests/test_semantic_commons.py tests/test_semantic_commons_projection.py tests/test_idea_spark_semantic_routing.py
./.venv/bin/python -m pytest -q tests/test_idea_spark_cli.py tests/test_operator_input_receipts.py tests/test_idea_spark_candidate_projection.py tests/test_idea_spark_chetana_adapter.py tests/test_idea_spark_memory_bridge.py tests/test_idea_spark_semantic_routing.py tests/test_idea_spark_action_routing.py tests/test_idea_spark_health.py tests/test_operator_input_retrieval_roundtrip.py tests/test_operator_idea_spark_ingest_e2e.py dharma_swarm/chetana/tests/test_graph_unifier.py tests/test_semantic_commons.py tests/test_semantic_commons_projection.py
```

Observed results:

- Semantic focused suite: `37 passed in 1.58s`
- Broader Idea Spark focused suite: `95 passed in 4.74s`

## Verdict

The live semantic drill exposed two real gaps:

1. Real system ideas outside the initial Operator Idea Spark domain failed closed because Semantic Commons had no canonical objects for them.
2. Re-resolving the same deterministic correlation after ontology repair left a stale blocker in lifecycle receipts.

Both gaps are fixed. The two tested system ideas now ingest end-to-end with semantic routing, owner surfaces, MemoryKernel receipts, Chetana staged atoms, proposal queue IDs, and correlation retrieval.
