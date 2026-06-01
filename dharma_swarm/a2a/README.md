# A2A Runtime Spine Boundary

This directory contains the external agent interoperability boundary for
dharma_swarm. The A2A layer may accept or return remote task identifiers, but
runtime lineage joins through `ExecutionIdentity` and `RuntimeStateStore`
receipts.

The correlation spine has three receipt layers:

- A2A request/response receipts use `correlation_id` for external task joins.
- Runtime spine receipts use `run_id`, `trace_id`, and `correlation_id` for
  internal execution lineage.
- Test and acceptance receipts must preserve the same correlation value when a
  request crosses layers.

A2A is not the workflow ledger, graph checkpoint store, or internal transport.
Remote task IDs should be mapped to runtime IDs through explicit receipt or
identity metadata before side effects.
