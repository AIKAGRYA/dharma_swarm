# Spine and Opportunity Truth Report — Phase 5

## Result

- Passed: targeted authority/revenue-loop pytest exited 0 (`pytest_authority_revenue_loop.txt`).
- Passed: opportunity stages exactly returned `scope, validate, deep_research, capability, mvp, first_artifact` (`opportunity_stages.json`).
- Passed: fresh dispatch returned 6 successful stage results with task/claim/run ids (`opportunity_dispatch.json`).
- Degraded: repeating the same opportunity id created a second full 6-stage result set rather than visible deduplication (`opportunity_dispatch_repeat_same_id.json`); `idempotency_records` count is 0 in `runtime_db_inspection.json`.
- Passed: refill returned 6 completed stages and persisted durable runtime state (`opportunity_refill.json`, `runtime_db_inspection.json`).
- Failed/degraded input validation: missing-id dispatch returned HTTP 200 with six successful stage results instead of explicit 4xx/error (`opportunity_malformed_missing_id.json`).
- Passed: `tools/spine_adoption_metric.py --print` and `make spine-check` both exited 0 (`spine_adoption_metric.txt`, `make_spine_check.txt`).

## API summary

```json
{
  "opportunity_dispatch.json": {
    "http": 200,
    "result_count": 6,
    "all_success": true,
    "task_ids": [
      "task_6b2cc008c3554a31",
      "task_5619cbb5a05e466e",
      "task_8a0a1c61f3aa4b1b",
      "task_d431ab8def1b434b",
      "task_1feb9ef008b14d0e",
      "task_68ae55d7f5214049"
    ]
  },
  "opportunity_dispatch_repeat_same_id.json": {
    "http": 200,
    "result_count": 6,
    "all_success": true,
    "task_ids": [
      "task_6b8461b5a81b45db",
      "task_344e76dd72e44a45",
      "task_e8b23d0a6a1e4bff",
      "task_2f01fc60fb414650",
      "task_fbe1970c775142c2",
      "task_2fa61859bbde4c10"
    ]
  },
  "opportunity_refill.json": {
    "http": 200,
    "stage_count": 6,
    "statuses": [
      "completed",
      "completed",
      "completed",
      "completed",
      "completed",
      "completed"
    ],
    "total_provider_cost_usd": 0.23,
    "total_net_value_usd": 999.77,
    "revenue_packet": "/home/ubuntu/pr-work/full-swarm-e2e-20260621/.e2e_state/full_swarm_test_20260621/home/.dharma/revenue_packets/revenue_packet_deep-e2e-refill-20260621.md"
  },
  "opportunity_malformed_missing_id.json": {
    "http": 200,
    "result_count": 6,
    "all_success": true,
    "task_ids": [
      "task_2371bbe2457a4627",
      "task_b376891718c04bf9",
      "task_a6d4927a1ece4df9",
      "task_f5ddd9c20e024fb5",
      "task_bf9b6e709dda4da1",
      "task_6849a3a449ab4053"
    ]
  }
}
```

## SQLite evidence

- Runtime DB: `.e2e_state/full_swarm_test_20260621/state/runtime.db`.
- `task_claims`: 24 total after phase-5 probes.
- `delegation_runs`: 24 total after phase-5 probes.
- `runtime_receipts`: 54 total.
- `idempotency_records`: 0 total.
- Opportunity id string matches by table: `{'task_claims': 18, 'delegation_runs': 18, 'runtime_receipts': 42, 'event_log': 0}` (`db_opportunity_id_matches.json`).

## Raw evidence

- `pytest_authority_revenue_loop.txt`
- `spine_adoption_metric.txt`
- `make_spine_check.txt`
- `opportunity_*.json`
- `runtime_db_inspection.json`
- `db_opportunity_id_matches.json`
- `task_claims_latest12.json`, `delegation_runs_latest12.json`, `runtime_receipts_latest12.json`
