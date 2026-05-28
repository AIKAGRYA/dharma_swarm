# A2A Correlation Spine Architecture

> Receipts may differ by closure layer. Correlation identity must not.

## Three-layer receipt chain

```
A2ATaskReceipt              "did the agent get it?"
     │ correlation_id
     ▼
spine.EvidenceReceipt       "did invocation finish?"
     │ correlation_id (= trace_id)
     ▼
closure_v0.EvidenceReceipt  "did tests pass?"
```

Each layer answers one question. They are distinct dataclasses with distinct
schemas. They link by `correlation_id`, never by inheritance.

- **A2ATaskReceipt** (`operator_core/a2a_task_lifecycle.py`) — request/response
  layer. Stamped at task creation with auto-UUID4 if upstream doesn't provide one.
  Never optional, never empty.

- **SpineEvidenceReceipt** (`spine/receipt.py`) — dispatch/invocation layer.
  Uses `trace_id` as its correlation identity. PR B adds a
  `dharma.correlation_id` alias in `to_otel_span()` so external consumers
  can query uniformly.

- **ClosureEvidenceReceipt** (`closure_v0/`) — test/work-packet layer.
  Links back via its own `correlation_id` field.

## Naming convention (advisory)

When semantic ambiguity exists, prefer layer-prefixed names:
`A2ATaskReceipt`, `SpineEvidenceReceipt`, `ClosureEvidenceReceipt`.
No forced rename during PR A/B turbulence — future receipts pick the right
name from birth.

## What this enables

The correlation spine is the causal thread that makes the full lifecycle
reconstructable as one graph:

```
intent → routing → invocation → execution → artifacts → tests → governance → replay
```

Each node in that chain carries the same `correlation_id`. Future closure
layers (governance receipts, dashboard receipts, evolution receipts) attach
to the same spine without re-architecting.

## Test gate

`tests/test_a2a_gateway_init.py::TestCorrelationIdStamping::test_fail_closed_on_empty_correlation_id`

If that test fails, the spine is broken. Fail-closed, always.
