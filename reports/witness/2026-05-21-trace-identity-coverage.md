# Trace Identity Coverage Witness

Date: 2026-05-21
Track: trace-identity-coverage-2026-05

## Verdict

The trace spine no longer depends only on manual trace arguments or synthetic
legacy aliases for new records. Operator Brief, BoardStore, and Sakshi now
consume `CorrelationContext` when it is present, while preserving explicit
operator-supplied trace IDs and the existing synthetic fallback for legacy
operator-brief artifacts.

## Evidence

- Operator Brief runtime artifacts use `correlation_context` as
  `trace_id_source` when a current trace is present.
- BoardStore `BoardEvent` defaults `trace_id` / `trace_id_source` from
  `CorrelationContext`.
- Sakshi `ProvenanceEntry` defaults `trace_id` / `trace_id_source` from
  `CorrelationContext`.
- Guardian ledger watcher emits a DEGRADED
  `LEDGER_WATCHER:operator_brief_trace_coverage` finding for operator-brief
  artifact records that lack `metadata.trace_id`.

## Test Evidence

Focused suite:

```text
83 passed, 1 warning
```

Scope:

```text
tests/test_guardian_crew.py
tests/test_board_facade.py
tests/test_sakshi_provenance.py
tests/test_operator_brief_insight_brief.py
tests/test_trace_attractor_readers.py
tests/test_trace_attractor_projection.py
tests/test_dgc_trace_attractor_cli.py
```

## Remaining Boundary

The coverage check is intentionally soft. A later ADR must decide when missing
trace identity becomes a hard CI or Guardian blocker for value-bearing records.
