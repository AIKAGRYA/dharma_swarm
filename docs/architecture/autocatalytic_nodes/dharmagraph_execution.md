---
title: DharmaGraph Durable Execution
status: active_reference
authority: local_evidence
---

# DharmaGraph Durable Execution

Producer: `DurableInvoker` and the production orchestrator bind execution identity, idempotency, and `EvidenceReceipt` persistence. This node is bound to `dharmagraph-engine-2026-07`.

Contract: consume `prioritized_work`; apply `execute_durably`; emit `execution_receipt` to [Cybernetic Supervision](cybernetic_supervision.md).

Proof surfaces: [`durable_invoker.py`](../../../dharma_swarm/graph/durable_invoker.py) and [`test_graph_durable_invoker.py`](../../../tests/test_graph_durable_invoker.py).

Current adapter projection: `dharmagraph.pure_execution_identity` derives the real side-effect and claim idempotency keys without dispatching. It emits `rehearsal_intent_no_domain_execution`; no causally matched domain receipt is claimed.

Promotion obligations:

- reject `unprotected_dispatch` for consequential work;
- bind graph events to persisted `EvidenceReceipt` rows in `RuntimeStateStore`;
- prove replay, checkpoint, and idempotent recovery on the adopted production path.

Forbidden claim: `TypedStateGraph` compilation or an event-shaped record alone is not a durable domain receipt.

Operator page: `/dashboard/organism/dharmagraph_execution`.
