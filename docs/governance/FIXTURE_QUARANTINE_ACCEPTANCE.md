# Fixture Quarantine Acceptance — operator decision record

This file is the operator's recorded acceptance for the fixture-quarantine
policy owned by `test_fixtures` (see
`scripts/governance/runtime_receipt_coverage_report.py`,
`_fixture_quarantine_policy` and `_field_gap_action_policy`'s
`quarantine_fixture_debt_or_exclude_from_production_gate` action).

It is read by `_fixture_quarantine_acceptance_evidence()` in that report.
The report only treats acceptance as recorded when the machine-readable
fields below parse and the `detection_rule` lines match the report's live
`_identifier_shape` rule exactly. Editing the rule here without changing the
code (or vice-versa) makes the report refuse to apply the exclusion.

## Operator decision

- accepted: yes
- owner_surface: test_fixtures
- operator: John (Dhyana) Shrader
- accepted_on: 2026-06-15
- decision: Exclude fixture-shaped runtime-receipt rows from the
  production 70->75 score gate denominators (mission and artifact, and the
  idempotency join), so test-fixture debt does not count as production debt.

## Detection rule (must match the report's live `_identifier_shape`)

Fixture-shaped means any of:

- detection_rule: agent_id fullmatch `a\d+`
- detection_rule: task_id fullmatch `t\d+`
- detection_rule: task_id equals `t-ready`

No other row is excluded. Real runtime rows carry 32-hex identifiers
(for example `d05eee3550fc47bd`) and are never fixture-shaped, so they
always remain in the production denominators.

## Preconditions the operator requires (all must hold per report run)

- precondition: active_head_missing == 0
  (no fixture-shaped row appears in active-head windows; current debt is
  historical only)
- precondition: test_runtime_db_isolation enforced
  (`tests/conftest.py` redirects `DHARMA_RUNTIME_DB` + `DGC_LEDGER_DIR` and
  patches `dharma_swarm.runtime_state.DEFAULT_RUNTIME_DB`, so the test suite
  can never write the production `runtime.db` again — this is why 826
  fixture rows once polluted production, and the recurrence is now closed)

## Scope and honesty constraints

- This acceptance excludes only fixture-shaped rows. It does not hide any
  real (non-fixture) production debt.
- The report must still show `fixtures_excluded` count and only report
  `applies_to_score_gate=true` when both preconditions above hold.
- This acceptance does not waive the idempotency-join requirement for real
  rows. If real rows fail to join `idempotency_records`, the gate still
  fails; quarantine never mints idempotency records or mutates the live DB.
