# VentureCell Operator OS Verifier Matrix

Generated: 2026-06-02
Mission: `20260602-venturecell-operator-os-8h`

## Commands And Results

| Check | Command | Result |
|---|---|---|
| Darshan external-reader gate | `pytest -q tests/test_darshan_external_reader_gate.py` | `10 passed, 1 warning` |
| Darshan operator log and Go bridges | `pytest -q tests/test_darshan_operator_log.py tests/test_go_evidence_ingestor_bridge.py tests/test_go_world_signal_bridge.py` | `9 passed, 1 warning` |
| Control-surface Darshan gate row | `pytest -q tests/test_control_surface.py -k 'GoReceiptRows or external_reader'` | `1 passed, 74 deselected, 1 warning` |
| Autonomy spine, harness, A2A lifecycle | `pytest -q tests/test_long_running_harness.py tests/test_goal_health.py tests/test_a2a_task_lifecycle.py` | `26 passed, 1 warning` |
| Score-50 harness scaffold | `make long-harness-validate RUN_ID=venturecell-operator-os-8h-score50 PHASE=scaffold` | `valid: True` |
| Operator OS projection brick | `pytest -q tests/test_venture_cell_operator_os_projection.py` | `3 passed, 1 warning` |
| Darshan gate/control regression after projection | `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'` | `11 passed, 74 deselected, 1 warning` |
| Governed admission, A2A, daily brief regression | `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py` | `31 passed, 1 warning` |
| Operator OS compile check | `python -m compileall -q dharma_swarm/venture_cell/operator_os` | `passed` |
| Operator OS digest generation | `python - <<'PY' ... build_operator_projection(...); write_operator_daily_digest(...)` | `wrote reports/venture_operator_os/20260602-8h/operator_os_digest.md; status blocked_on_external_reader_gate; autonomy L0_read_only_plan` |

Warning common to pytest runs:

`PytestConfigWarning: Unknown config option: timeout`

## Mission Ledger Verification

Before the rescue packet:

- mission status: `active`;
- task counts: `open=4 claimed=1 completed=0 failed=0 blocked=0 total=5`;
- runner was heartbeating;
- builder was claimed;
- no mission-specific `reports/venture_operator_os/` output existed.

After the rescue packet is recorded, expected state:

- planner: completed;
- builder: blocked;
- adversary: completed;
- verifier: completed;
- reporter: completed;
- mission: review, not complete, because builder was blocked rather than
  successful.

After the foreground continuation, product-build score has moved to the lower
50s because the read-only projection and digest renderer now exist with focused
tests. The old runner's task-state file may still show open/claimed until that
runner exits or is reconciled; heartbeat health must not be treated as artifact
progress.

Generated digest truth:

- `reports/venture_operator_os/20260602-8h/operator_os_digest.md`
- status: `blocked_on_external_reader_gate`
- autonomy: `L0_read_only_plan`
- MemoryKernel: `large_projection_needs_index`

## Evidence Standard

This matrix accepts command output, artifact paths, and `ds-goal` receipts.
It does not accept narration alone.
