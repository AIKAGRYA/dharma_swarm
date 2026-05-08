# Organism Closure v0 — Fixtures

These JSON fixtures drive `tests/test_organism_closure_v0.py`. The closure
proof: replaying the loop with `fixture_agentops_success.json` produces a
different `expected_next_decision_*.json` than replaying with
`fixture_agentops_failure.json`. Specifically, `chosen_packet_id` and
`reason` differ. That difference IS the proof that evidence changes the next
decision.

## Files

| File | Role |
|---|---|
| `fixture_objective.json` | TelosObjective stub (jagat_kalyan / purpose) |
| `fixture_venture_cell.json` | VentureCellRef stub |
| `fixture_work_packet.json` | The single WorkPacket the loop is closing |
| `fixture_operating_bundle.json` | OperatingFactBundle stub (empty, missing sources only) |
| `fixture_agentops_success.json` | AgentOpsRunFact: gate_state=all_green, scope_state=scope_clean |
| `fixture_agentops_failure.json` | AgentOpsRunFact: gate_state=some_red, scope_state=scope_violation |
| `expected_evidence_*.json` | Frozen output of `record_evidence_receipt` |
| `expected_vsm_*.json` | Frozen output of `project_vsm` |
| `expected_kaizen_*.json` | Frozen output of `kaizen_link` |
| `expected_next_decision_*.json` | Frozen output of `decide_next` (THE proof artifact) |
| `replay.sh` | Pytest wrapper |

## Determinism

- `correlation_id = "corr_v0_test_001"` is hard-coded.
- `created_at`, `captured_at`, `decided_at`, `expires_at` are fixed strings.
- Object IDs use `blake2s` of `(prefix, correlation_id, ...)` — fully deterministic.
- No `time.time()`, `uuid4`, or random in the loop.

## Verifying closure (the one-liner)

```bash
diff expected_next_decision_success.json expected_next_decision_failure.json
# Exit non-zero. That non-zero IS the closure proof.
```
