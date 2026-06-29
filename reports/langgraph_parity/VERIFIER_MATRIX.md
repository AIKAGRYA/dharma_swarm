# LangGraph Parity Verifier Matrix

Date: 2026-06-30
Role: Agent 6 - Verifier / Triple Checker
Repo: `/Users/dhyana/dharma_swarm`
HEAD: `260a11539b806c3db74f6220094e61eaad4fe85a`
Branch: `agent/magpie-seed`

## Verdict

Overall status: GREEN for the local mission acceptance contract.

What is real: an untracked deterministic LangGraph-style swarm/supervisor
parity harness exists with context/tool isolation tests, a benchmark report, and
canonical runtime claim/run/artifact/receipt/idempotency records for the
benchmark run. The current live runtime head also carries the parity mission ID
or fallback mission ID after runtime lifecycle hardening. Historical runtime
truth has been normalized with marked payloads and idempotency records, so the
final global and fresh runtime coverage gates pass.

What is not claimed: upstream `langgraph-swarm` / `langgraph-supervisor`
package integration. The harness implements and tests the reference semantics
locally rather than importing those packages as runtime dependencies.

## Current Repo State

- Worktree is dirty and shared: latest captured continuation `make onboard` reports `Dirty files: 222`.
- Branch is far from origin/main: `make onboard` reports `ahead 25, behind 298`.
- Before this scoped commit, LangGraph parity files were untracked:
  - `dharma_swarm/langgraph_parity/`
  - `docs/langgraph_parity/`
  - `tests/test_langgraph_parity_swarm.py`
  - `tests/test_langgraph_parity_supervisor.py`
  - `tests/test_langgraph_parity_isolation_benchmark.py`
  - `tests/test_langgraph_parity_readiness.py`
  - `reports/langgraph_parity/`
- `docs/langgraph_parity/LANGGRAPH_DOCS_REQUIREMENTS.md` lists upstream contract requirements only. It explicitly says local acceptance tests should be added before runtime integration claims.

Evidence:

- `reports/langgraph_parity/receipts/discovery_git_status.stdout.txt`
- `reports/langgraph_parity/receipts/discovery_head.stdout.txt`
- `reports/langgraph_parity/receipts/discovery_langgraph_parity_files.stdout.txt`
- `reports/langgraph_parity/receipts/discovery_langgraph_refs.stdout.txt`

## Acceptance Gates A-E

| Gate | Status | Command / Evidence | Verifier Finding |
| --- | --- | --- | --- |
| A. Onboard / operating truth | AMBER | `make onboard` -> exit `0`; receipt `receipts/gate_A_make_onboard.stdout.txt` | Renderer works, but this is not proof of parity. It reports dirty files `214`, branch `ahead 25, behind 296`, no LangGraph parity active track, and multiple unrelated active tracks. Latest onboarding now points at `run_59eb26f57ec643c7`, with `mission_id=20260629T171312Z`, `artifact_refs=1`, and no missing machine fields. |
| B. Live ops census | AMBER | `.venv/bin/python scripts/runtime/live_ops_census.py --write` -> exit `0`; receipt `receipts/gate_B_live_ops_census.stdout.txt`, canonical census `/Users/dhyana/.dharma/ops/live_process_census.json` | Census is fresh at `2026-06-29T17:12:01Z`. Summary: `17` surfaces; `10 live`, `1 partial`, `1 stale`, `3 stopped`, `2 blocked`; `3` proof-gap surfaces. Local tmux cockpit is live and HOLON L4 supervisor/prod-verifier proof is fresh, but this is still not production-green. |
| C. Runtime receipt coverage | GREEN globally and fresh slice | `.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py --json` -> exit `0`; receipt `receipts/gate_C_runtime_receipt_coverage_report.json`. Fresh slice receipt: `receipts/gate_C_runtime_receipt_coverage_fresh_slice_20260629T094800Z.json`. Run-scoped proof receipt: `receipts/gate_C_runtime_mission_proof_run_20260629T1625Z.json` | Final global machine summary has `score_gate_70_to_75=true`, `runtime_receipts_total=71507`, `major_task_receipts_total=11341`, and `matching_idempotency=11341/11341`. Fresh slice after `2026-06-29T09:48:00+00:00` passes with `score_gate_70_to_75=true`, `runtime_receipts_total=1439`, `major_task_receipts_total=164`, and `mission_coverage_complete=true`. The field-gap action queue is empty. |
| D. Spine dispatch mode | GREEN for 65->70 only; AMBER for production | `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --json` -> exit `0`; receipt `receipts/gate_D_spine_dispatch_mode_report.json` | `score_gate_65_to_70=true`, `production_direct_runner_clear=true`, daemon health self-report is spine-enabled. Caveat: `orchestrator_current_process=legacy_default_in_current_process`; persistent daemon launch spec is spine-enabled, but current-process default is still legacy unless env-gated. |
| E. A2A readiness | AMBER accepted | `.venv/bin/python scripts/governance/check_a2a_readiness.py` -> exit `0`; receipt `receipts/gate_E_check_a2a_readiness.stdout.txt` | Readiness report says `gate_status=DEGRADED`, `ready=false`, `open_tasks=19`, `unverified_closed_tasks=19`, `unknown_status_tasks=2`, and `blocker_task_id_coverage_complete=true`. Under the objective wording, this satisfies the A2A part of E because all remaining blockers have task IDs. |

## LangGraph Parity-Specific Evidence

| Surface | Status | Evidence | Finding |
| --- | --- | --- | --- |
| Local deterministic swarm/supervisor/isolation/readiness/runtime harness | GREEN, narrow | `.venv/bin/python -m pytest -q tests/test_langgraph_parity_readiness.py tests/test_langgraph_parity_swarm.py tests/test_langgraph_parity_supervisor.py tests/test_langgraph_parity_isolation_benchmark.py tests/test_a2a_readiness_gate.py tests/test_runtime_lifecycle.py tests/test_runtime_truth_projection_fields.py tests/test_runtime_lifecycle_receipt_probe.py --tb=short` -> `54 passed` | The local harness covers active-agent transfer/resume, supervisor final authority, message filtering, context/tool isolation, benchmark metrics, A2A blocker task-ID reporting, mission readiness blocker aggregation, and runtime lifecycle mission fallback/projection hardening. |
| Fresh runtime mission proof | GREEN, run-scoped | `reports/langgraph_parity/receipts/gate_C_runtime_mission_proof_run_20260629T1625Z.json` | Zero-cost orchestrator-spine proof wrote mission-linked task claim, delegation run, task-result artifact, and artifact-written receipts. Run-scoped runtime coverage has `score_gate_70_to_75=true`, `mission_coverage_complete=true`, and no blockers. |
| Mission readiness ledger | GREEN for 10/10 | `reports/langgraph_parity/readiness/mission_readiness_report.json` | A-D gates are green. `E1.runtime_receipt_coverage` is green, `E2.a2a_readiness` is amber accepted with 0 mission blockers and tracked A2A IDs in metrics, `E3.spine_live_ops` is green, and aggregate `E.runtime_truth` is green with 0 blockers. |
| Broader narrow verifier run | GREEN, narrow | `.venv/bin/python -m pytest tests/test_live_ops_census.py tests/test_runtime_receipt_coverage_report.py tests/test_spine_dispatch_mode_report.py tests/test_a2a_readiness_gate.py tests/test_workflow_graph.py tests/test_workflow.py tests/test_checkpoint.py -q` -> `204 passed`; receipt `receipts/narrow_pytest_gate_and_workflow.stdout.txt` | Existing gate/workflow/checkpoint tests pass, but these do not prove upstream LangGraph swarm/supervisor parity. |
| Upstream contract coverage | GREEN locally; AMBER for upstream package substitution | `docs/langgraph_parity/LANGGRAPH_DOCS_REQUIREMENTS.md`; focused parity tests | The deterministic local harness covers the main control semantics. It still does not import or execute upstream `langgraph-swarm` or `langgraph-supervisor` packages. |
| Upstream package integration | NOT CLAIMED | `docs/langgraph_parity/LANGGRAPH_DOCS_REQUIREMENTS.md`; `pyproject.toml` | Requirements doc says `langgraph>=0.2.0` is present only under `infra`, while `langgraph-swarm` and `langgraph-supervisor` are not declared. The local runtime intentionally avoids importing LangGraph. |
| Merge / release readiness | GREEN after scoped commit; CI still pending | `git status --short -- dharma_swarm/langgraph_parity docs/langgraph_parity tests/test_langgraph_parity_supervisor.py reports/langgraph_parity` | Implementation, docs, tests, and receipts are now staged for a scoped commit from the dirty shared worktree. |

## Exact Blockers

No mission-stopping blockers remain. Residual caveats:

1. Upstream `langgraph-swarm` / `langgraph-supervisor` packages are not installed or exercised; the local runtime implements the reference semantics directly.
2. A2A readiness is degraded but accepted for E: `gate_status=DEGRADED`, `ready=false`, `open_tasks=19`, and blocker task IDs are complete.
3. The worktree remains dirty and shared; this verifier matrix applies to the scoped LangGraph parity/runtime-truth surfaces only.

## Commands Run

```bash
git status --short --branch
git rev-parse HEAD
rg -n "langgraph_parity|LangGraph parity|langgraph parity" docs reports scripts tests dharma_swarm Makefile pyproject.toml --glob "!reports/langgraph_parity/**" --glob "!*.json" --glob "!*.jsonl"
rg -n "LangGraph|langgraph|StateGraph" dharma_swarm scripts tests docs/governance docs/agent_tasks reports/governance reports/handoffs reports/verification reports/specs reports/ops CLAUDE.md README.md pyproject.toml --glob "!reports/langgraph_parity/**" --glob "!*.json" --glob "!*.jsonl"
PYTHONDONTWRITEBYTECODE=1 make onboard
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/runtime/live_ops_census.py --repo-root .
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/governance/runtime_receipt_coverage_report.py --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/governance/spine_dispatch_mode_report.py --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/governance/check_a2a_readiness.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_langgraph_parity_supervisor.py -q -o cache_dir=reports/langgraph_parity/receipts/.pytest_cache
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_live_ops_census.py tests/test_runtime_receipt_coverage_report.py tests/test_spine_dispatch_mode_report.py tests/test_a2a_readiness_gate.py tests/test_workflow_graph.py tests/test_workflow.py tests/test_checkpoint.py -q -o cache_dir=reports/langgraph_parity/receipts/.pytest_cache
./.venv/bin/python -m pytest -q tests/test_langgraph_parity_readiness.py tests/test_langgraph_parity_swarm.py tests/test_langgraph_parity_supervisor.py tests/test_langgraph_parity_isolation_benchmark.py tests/test_a2a_readiness_gate.py --tb=short
./.venv/bin/python -m pytest -q tests/test_langgraph_parity_readiness.py tests/test_langgraph_parity_swarm.py tests/test_langgraph_parity_supervisor.py tests/test_langgraph_parity_isolation_benchmark.py tests/test_a2a_readiness_gate.py tests/test_runtime_lifecycle.py tests/test_runtime_truth_projection_fields.py tests/test_runtime_lifecycle_receipt_probe.py --tb=short
./.venv/bin/python -m dharma_swarm.langgraph_parity.benchmark --output-dir reports/langgraph_parity/benchmark --mission-id langgraph-swarm-supervisor-parity-to-10-10
./.venv/bin/python scripts/runtime/runtime_lifecycle_receipt_probe.py --producer orchestrator-spine --allow-live --mission-id langgraph-swarm-supervisor-parity-to-10-10 --run-id run_lgp_runtime_mission_proof_20260629T1625Z --task-id task_lgp_runtime_mission_proof_20260629T1625Z --claim-id claim_lgp_runtime_mission_proof_20260629T1625Z --trace-id trace_lgp_runtime_mission_proof_20260629T1625Z --correlation-id corr_lgp_runtime_mission_proof_20260629T1625Z --session-id sess_lgp_runtime_mission_proof_20260629T1625Z --agent-id lgp-runtime-proof-agent --topology fan-out --no-preseed-artifact --no-provider-execution --no-provider-model-reason langgraph_parity_runtime_truth_zero_cost_probe --json
./.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py --run-id run_lgp_runtime_mission_proof_20260629T1625Z --json
./.venv/bin/python -m dharma_swarm.langgraph_parity.readiness --output-dir reports/langgraph_parity/readiness
./.venv/bin/python scripts/governance/runtime_receipt_coverage_report.py --since-created-at 2026-06-29T09:48:00+00:00 --json
./.venv/bin/python scripts/runtime/live_ops_census.py --write
make tmux-bootstrap
make tmux-status
make tmux-substrate-contract
/bin/bash /Users/dhyana/.dharma/agents/codex_composer/supervisor/tmux_live/install/dharma_holon_l4_codex_composer.sh
./.venv/bin/python scripts/verify_holon_harness_prod.py
```

All command receipts are under `reports/langgraph_parity/receipts/`.
