# Active Track Evidence

Generated: 2026-05-20T16:49:02+00:00
Track: `trace-identity-coverage-2026-05`
Prerequisites: **OK**
Completion: **5/6**
Shippable: **no**

## Criteria

- ✓ `trace_attractor_causal_spine_closed` (file_contains) — pattern 'Trace Attractor Causal Spine shipped' found in docs/governance/ACTIVE_TRACK.yaml
- ✓ `correlation_context_exists` (file_contains) — pattern 'class CorrelationContext' found in dharma_swarm/correlation_context.py
- ✓ `dgc_trace_attractor_wired` (file_contains) — pattern 'trace-attractor' found in dharma_swarm/dgc_cli.py
- ✓ `operator_brief_consumes_correlation_context` (file_contains) — pattern 'correlation_context' found in dharma_swarm/operator_brief/persistence.py
- ✓ `board_event_context_trace_defaults` (file_contains) — pattern '_current_trace_id' found in dharma_swarm/board/event_log.py
- ✓ `sakshi_context_trace_defaults` (file_contains) — pattern '_current_trace_id' found in dharma_swarm/sakshi/provenance_log.py
- ✓ `guardian_soft_trace_coverage` (file_contains) — pattern 'operator_brief_trace_coverage' found in dharma_swarm/operator_brief/watchdog.py
- ✓ `trace_identity_coverage_witness` (file_exists) — reports/witness/2026-05-21-trace-identity-coverage.md present
- ✗ `hard_gate_policy_adr` (file_exists) — docs/architecture/adr/0002-trace-coverage-gate.md MISSING

## Findings

- **INFO** `track-in-progress`: 5/6 completion criteria pass. Track 'trace-identity-coverage-2026-05' is in progress.
