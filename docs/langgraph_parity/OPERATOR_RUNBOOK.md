# LangGraph Parity Operator Runbook

This harness is deterministic and local. It proves the control semantics for
LangGraph-style swarm and supervisor modes without invoking paid providers.

## Swarm Mode

```bash
./.venv/bin/python -m pytest -q tests/test_langgraph_parity_swarm.py --tb=short
```

Covered: default active agent, persisted `active_agent`, `transfer_to_<agent>`
handoff tools, next-turn resume, direct active subagent response, transfer back,
invalid transfer rejection, and checkpoint reload.

## Supervisor Mode

```bash
./.venv/bin/python -m pytest -q tests/test_langgraph_parity_supervisor.py --tb=short
```

Covered: supervisor entry, delegation to subagents, subagent return to
supervisor, supervisor-only final visibility, exact `forward_message`
behavior, handoff-message suppression, and `output_mode` history control.

## Isolation And Benchmark

```bash
./.venv/bin/python -m pytest -q tests/test_langgraph_parity_isolation_benchmark.py --tb=short

./.venv/bin/python -m dharma_swarm.langgraph_parity.benchmark \
  --output-dir reports/langgraph_parity/benchmark \
  --mission-id langgraph-swarm-supervisor-parity-to-10-10
```

The benchmark command records canonical runtime claim, run, artifact, receipt,
and idempotency records by default. Use `--runtime-db <path>` for an isolated
runtime store during verification, or `--no-runtime-receipt` only when
intentionally generating artifacts without runtime truth evidence.

Artifacts:

- `reports/langgraph_parity/benchmark/benchmark_report.json`
- `reports/langgraph_parity/benchmark/benchmark_report.md`
- `reports/langgraph_parity/benchmark/benchmark_receipt.json`
- `/Users/dhyana/.dharma/state/runtime.db` receipt `rr_langgraph_parity_benchmark_250ea999acb52eb2`
- `/Users/dhyana/.dharma/state/runtime.db` run `run_langgraph_parity_benchmark_250ea999acb52eb2`

## Readiness Probes

```bash
make onboard
make tmux-bootstrap
make tmux-status
make tmux-substrate-contract
./.venv/bin/python scripts/runtime/live_ops_census.py --write
./.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py --json
./.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py \
  --since-created-at 2026-06-29T09:48:00Z \
  --json
./.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --json
./.venv/bin/python scripts/governance/check_a2a_readiness.py
./.venv/bin/python scripts/verify_holon_harness_prod.py

./.venv/bin/python scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer orchestrator-spine \
  --allow-live \
  --mission-id langgraph-swarm-supervisor-parity-to-10-10 \
  --run-id run_lgp_runtime_mission_proof_20260629T1625Z \
  --task-id task_lgp_runtime_mission_proof_20260629T1625Z \
  --claim-id claim_lgp_runtime_mission_proof_20260629T1625Z \
  --trace-id trace_lgp_runtime_mission_proof_20260629T1625Z \
  --correlation-id corr_lgp_runtime_mission_proof_20260629T1625Z \
  --session-id sess_lgp_runtime_mission_proof_20260629T1625Z \
  --agent-id lgp-runtime-proof-agent \
  --topology fan-out \
  --no-preseed-artifact \
  --no-provider-execution \
  --no-provider-model-reason langgraph_parity_runtime_truth_zero_cost_probe \
  --json

./.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py \
  --run-id run_lgp_runtime_mission_proof_20260629T1625Z \
  --json

./.venv/bin/python -m dharma_swarm.langgraph_parity.readiness \
  --output-dir reports/langgraph_parity/readiness
```

Current mission status is 10/10 for the local acceptance contract when
`reports/langgraph_parity/readiness/mission_readiness_report.json` has
`overall_status=green`, `ten_out_of_ten=true`, and zero blockers. A2A may be
degraded under the objective's E gate only when
`blocker_task_id_coverage_complete=true`; inspect `blocker_task_ids` in the JSON
output before treating the degraded state as accepted.

Readiness artifacts:

- `reports/langgraph_parity/readiness/mission_readiness_report.json`
- `reports/langgraph_parity/readiness/mission_readiness_report.md`
- `reports/langgraph_parity/receipts/gate_C_runtime_mission_proof_run_20260629T1625Z.json`

The readiness command exits zero by default even when the mission is red so it
can be used as a ledger generator. Add `--strict` when a CI or release gate
should fail unless every A-E gate is green.

Runtime lifecycle receipts now fill `mission_id` from explicit mission metadata
or a transparent `runtime_lifecycle_fallback` source when no explicit mission
contract exists. The run-scoped mission proof above is zero-cost and should pass
`score_gate_70_to_75=true`.

Historical runtime receipt normalization is explicit and idempotent:

```bash
./.venv/bin/python scripts/runtime/backfill_runtime_idempotency_records.py --json
./.venv/bin/python scripts/runtime/normalize_runtime_receipt_history.py --json
```

Both commands should report zero candidates after the repair has been applied.
The first script only inserts missing `idempotency_records` when both keys
already exist. The second script normalizes historical receipts to the current
runtime contract, marks payloads with
`historical_runtime_receipt_normalization`, and does not overwrite existing
mission or artifact refs.

The HOLON verifier must run through the repo venv. A bare system `python3` can
fail on missing project dependencies and create a fresh failed verifier receipt.
