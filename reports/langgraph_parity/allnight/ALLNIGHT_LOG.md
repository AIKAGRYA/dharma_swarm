# LangGraph Parity All-Night Log

## 2026-06-30T15:59:09Z - Phase 0 Baseline Start

- Worktree: `/Users/dhyana/ds_langgraph_parity_20260701`
- Branch: `codex/langgraph-orchestration-parity-20260701`
- Base: `origin/main` at `f84f40344cbdfab9d236239b0d3ec00718e10bf9`
- PR #727 merge `3c2e4a684` is an ancestor of this branch.
- Dirty `agent/magpie-seed` checkout was not used.
- Current target gate: Phase 0 clean baseline.
- Current blockers: baseline commands not yet run; `scripts/governance/spine_dispatch_mode_report.py` not found in initial file scan.
- Files touched this round: this log and `SCOREBOARD.json`.
- Tests run this round: pending.

## 2026-06-30T16:12:53Z - Rounds 1-2 Implementation Slice

- Target gates:
  - Phase 1 deterministic conformance oracle expansion.
  - Phase 2 runtime spine default-on slice.
  - Phase 3 live topology enum/metadata slice.
- Code changes landed:
  - Expanded `default_benchmark_tasks()` from 4 to 26 deterministic cases.
  - Added machine-readable benchmark `case_tags` and required coverage summary.
  - Added `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS` to `TopologyType`.
  - Wired those topology modes into `Orchestrator.dispatch()` with active-agent, handoff, delegation, checkpoint, and parent graph metadata.
  - Inverted orchestrator dispatch from `DHARMA_SPINE_DISPATCH=1` opt-in to default-on with explicit false-like opt-out values.
  - Added `scripts/governance/spine_dispatch_mode_report.py`; `--strict` now passes on this branch.
  - Stamped run/idempotency/side-effect/topology/planned-provider/actual-provider fields into orchestrator `EvidenceReceipt.attributes`.
- Generated artifacts:
  - `reports/langgraph_parity/benchmark/benchmark_report.json`
  - `reports/langgraph_parity/benchmark/benchmark_report.md`
  - `reports/langgraph_parity/benchmark/benchmark_receipt.json`
- Verification:
  - `make onboard` -> pass after `.venv` exists; first run failed under system `python3` 3.9 before `uv run` created a Python 3.12 venv.
  - `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py` -> `20 passed in 0.37s`.
  - `.venv/bin/python -m pytest -q tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `66 passed in 28.95s`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; reports `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=19`, `unknown_status_tasks=2`, `unverified_closed_tasks=19`.
- Current blockers:
  - A2A strict green is blocked by live queue state in `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl`.
  - Full LangGraph parity remains unproven: live restart/resume topology, MemoryKernel live retrieval isolation, full provider served-model truth, and cockpit/API graph inspection are not complete.
- Next target gate:
  - Build live restart/resume topology proof backed by `RuntimeStateStore`, then attack A2A blockers with receipts or operator-approved external closure.

## 2026-06-30T16:18:59Z - Round 3 Start

- Current branch: `codex/langgraph-orchestration-parity-20260701` at `f081de65d`.
- Worktree status at round start: clean.
- Current blockers:
  - Phase 3 is still partial: topology metadata exists, but live restart/resume is not proven from `RuntimeStateStore`.
  - A2A strict readiness remains red from live queue state.
  - Memory live retrieval and cockpit/API surfaces remain pending.
- Files touched this round before implementation: this log.
- Tests run this round before implementation:
  - `make onboard` -> pass.
- Next target gate: persist topology state and handoff receipts in `RuntimeStateStore`, then prove SWARM restart/resume and SUBAGENTS_AS_TOOLS child/parent run records with tests.

## 2026-06-30T16:31:54Z - Round 3 Runtime Topology Proof

- Target gate: persist topology state and handoff receipts in `RuntimeStateStore`, then prove restart-readable SWARM state and SUBAGENTS_AS_TOOLS child/parent run records.
- Code changes landed:
  - Added first-class `topology_states` runtime DB table, `TopologyStateRecord`, and async store accessors.
  - Wired `RuntimeLifecycle.record_delegation_run()` to persist topology state receipts and topology handoff receipts through the same runtime-state spine as delegation runs.
  - Stamped SWARM accepted/rejected handoff receipts in dispatch metadata and topology state.
  - Stamped SUBAGENTS_AS_TOOLS child run IDs before assignment and persisted child `delegation_runs` with `parent_run_id`.
  - Exposed topology state through `RuntimeStateStore.describe_run()`.
- Verification:
  - `.venv/bin/python -m compileall -q dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/orchestrator.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> pass.
  - `.venv/bin/python -m pytest -q tests/test_runtime_state.py::test_topology_state_survives_store_restart tests/test_orchestrator.py::test_swarm_handoff_persists_restartable_topology_state tests/test_orchestrator.py::test_subagents_as_tools_persists_parent_and_child_runs tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state` -> `4 passed in 2.35s`.
  - `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 30.44s`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; reports `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=19`, `unknown_status_tasks=2`, `unverified_closed_tasks=19`.
  - `make agent-build-preflight` -> pass; compileall clean, F821 clean, 12,328 tests collected, onboard OK, hygiene integrity OK.
  - `make agent-build-closeout` -> fail exit 2; semgrep skipped because it is not installed on PATH, then gitleaks reported 68 redacted findings after scanning 2,720 commits.
- Scoreboard: `44/100`, still explicitly not 100/100.
- Current blockers:
  - A2A strict green remains blocked by live queue state in `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl`.
  - Build closeout remains blocked by the aggregate gitleaks gate; findings were not expanded here to avoid exposing secret material.
  - Supervisor final-output restart/resume semantics still need a dedicated live acceptance test.
  - Memory live retrieval isolation, full provider served-model truth, and cockpit/API graph inspection remain pending.

## 2026-06-30T16:48:44Z - PR CI Governance Repair

- Trigger: draft PR #732 first CI run failed `Fourfold Shakti Warrant`, `Rule 10 — module line budget`, and `Quality ratchet - repo-wide fitness function`.
- Repair changes:
  - Moved topology helper and persistence glue into `dharma_swarm/runtime_topology.py`, shrinking `dharma_swarm/orchestrator.py` to 3,204 lines and `dharma_swarm/runtime_lifecycle.py` to 497 lines.
  - Added `TopologyStateRecord.schema_version` so the assurance-boundary unfrozen-record ratchet does not grow.
  - Moved the 26 deterministic benchmark case catalogue into `dharma_swarm/langgraph_parity/benchmark_tasks.py`, shrinking `benchmark_runner.py` to 390 lines.
- Verification:
  - `.venv/bin/python -m compileall -q dharma_swarm/langgraph_parity/benchmark_runner.py dharma_swarm/langgraph_parity/benchmark_tasks.py dharma_swarm/runtime_state.py dharma_swarm/runtime_lifecycle.py dharma_swarm/runtime_topology.py dharma_swarm/orchestrator.py` -> pass.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`, `modules_over_500_lines` stayed `207 -> 207`, and `boundary_unfrozen_records` stayed `7 -> 7`.
  - `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 37.48s`.
  - `make agent-build-preflight` -> pass; compileall clean, F821 clean, 12,328 tests collected, onboard OK, hygiene integrity OK.
- Current blockers remain unchanged: A2A strict readiness, full-history closeout gitleaks aggregate, supervisor restart semantics, memory retrieval isolation, provider truth, and cockpit/API inspection.

## 2026-06-30T16:58:31Z - PR CI Pytest Enum Repair

- Trigger: draft PR #732 second CI run passed the repaired governance gates, but `pytest (3.12)` failed in `tests/test_models.py::test_all_enums`.
- Root cause: the model enum test still asserted the old `TopologyType` count of 4 after this branch intentionally added `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS`.
- Repair change:
  - Replaced the brittle `len(TopologyType) == 4` assertion with an explicit set of expected topology values covering all 7 current modes.
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_models.py` -> `16 passed in 0.13s`.
- Current blockers remain unchanged: A2A strict readiness, full-history closeout gitleaks aggregate, supervisor restart semantics, memory retrieval isolation, provider truth, and cockpit/API inspection.

## 2026-06-30T17:15:54Z - Phase 4 A2A Reconciliation Start

- Target gate: move A2A strict readiness toward green without weakening `check_a2a_readiness.py`.
- Current branch: `codex/langgraph-orchestration-parity-20260701` at `86c975319`.
- Worktree status at round start: clean after restoring unrelated `make onboard` governance projection churn.
- Baseline verification:
  - `make onboard` -> pass; reports PR #732 healthy, but runtime receipt fill rate remains 2460/8090.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=19`, `unknown_status_tasks=2`, `unverified_closed_tasks=19`.
- Current blocker classes:
  - Two `expired` queue rows already contain valid embedded terminal `blocked` receipts but are still counted as open/unknown because the row status was never normalized.
  - Seventeen stale open/claimed/pending rows remain unresolved.
  - Nineteen `completed` rows are unverified because they do not embed a valid `dharma_a2a_task_receipt.v1` receipt, even when a non-A2A semantic receipt id/path is present.
- Next target gate: add a narrow, tested reconciliation path for rows that already carry valid embedded terminal A2A receipts, run it on the live queue with a backup, rerun strict readiness, and record remaining blockers exactly.

## 2026-06-30T17:23:08Z - Phase 4 A2A Embedded Receipt Reconciliation

- Target gate: eliminate false unknown/open blockers for queue rows that already contain valid terminal A2A receipts.
- Code changes landed locally:
  - Added `scripts/governance/a2a_reconcile_embedded_receipts.py`.
  - Added `tests/test_a2a_embedded_receipt_reconciler.py`.
  - Added blocker receipt `reports/langgraph_parity/allnight/A2A_PHASE4_BLOCKER_RECEIPT.md`.
- Live queue action:
  - Backed up `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl` to `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.pr732-phase4-20260630T171554Z.bak`.
  - Dry-run receipt: `reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_dry_run_20260630T171554Z.json`.
  - Apply receipt: `reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_apply_20260630T171554Z.json`.
  - Normalized two rows from `expired` to `blocked`: `collab:fleet-health-collab-20260528:reviewer:opus_composer` and `collab:fleet-health-collab-20260528:infra-audit:devin-roaming-2987d222`.
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `19 passed in 0.44s`.
  - `.venv/bin/python -m compileall -q scripts/governance/a2a_reconcile_embedded_receipts.py` -> pass.
  - `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py --output reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_dry_run_20260630T171554Z.json` -> `candidate_count=2`.
  - `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py --apply --output reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_apply_20260630T171554Z.json` -> 2 rows normalized.
  - `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py` after apply -> `candidate_count=0`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `git diff --no-index --stat /Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.pr732-phase4-20260630T171554Z.bak /Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl` -> `1 file changed, 2 insertions(+), 2 deletions(-)`.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass; existing warnings unchanged for `orchestrator.py` and `runtime_state.py`.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- Scoreboard: `46/100`, still explicitly not 100/100.
- Current blockers:
  - A2A strict green still fails on 17 open/claimed/pending rows and 19 completed rows without embedded A2A task receipts.
  - Full-history closeout gitleaks aggregate, supervisor final-output restart semantics, memory retrieval isolation, provider truth, and cockpit/API inspection remain pending.

## 2026-06-30T17:46:37Z - Phase 4 A2A Blocker Audit

- Target gate: produce a concrete, replayable blocker receipt for the remaining A2A strict-readiness failures without weakening `check_a2a_readiness.py`.
- Code changes landed locally:
  - Added `scripts/governance/a2a_readiness_blocker_audit.py`.
  - Added `tests/test_a2a_readiness_blocker_audit.py`.
- Generated artifact:
  - `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json`
- Audit result:
  - Total live queue rows: 44.
  - Remaining blocker rows: 36.
  - Lifecycle counts: `claimed_open=11`, `open_unclaimed=6`, `completed_unverified=19`.
  - Classification counts: `open_stale_claimed_without_terminal_receipt=11`, `open_stale_unclaimed_without_terminal_receipt=6`, `closed_semantic_receipt_present_non_a2a=18`, `closed_missing_a2a_receipt_no_pointer=1`.
  - All 18 SAB semantic receipt pointers resolve to valid `sab.semantic_receipt.v1` artifacts only via `/Users/dhyana/dharma_swarm`; the clean parity branch does not contain those receipt artifacts, and they still are not embedded `dharma_a2a_task_receipt.v1` receipts.
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py` -> `4 passed in 0.39s`.
  - `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `23 passed in 0.41s`.
  - `.venv/bin/python -m compileall -q scripts/governance/a2a_readiness_blocker_audit.py tests/test_a2a_readiness_blocker_audit.py` -> pass.
  - `.venv/bin/python scripts/governance/a2a_readiness_blocker_audit.py --artifact-root /Users/dhyana/ds_langgraph_parity_20260701 --artifact-root /Users/dhyana/dharma_swarm --output reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json` -> pass.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `git diff --check` -> pass.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings for `orchestrator.py` and `runtime_state.py`.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- Scoreboard: remains `46/100`, explicitly not 100/100.
- Current blocker:
  - Phase 4 is still red: the live queue needs task-specific terminal A2A receipts or governed blocked receipts for 17 stale open rows, plus an accepted semantic-to-A2A bridge or proper A2A receipts for 18 SAB rows and one receipt-less `ts-converge-0611` completion.

## 2026-06-30T18:10:38Z - Phase 5 Memory Text Query Live Context Slice

- Target gate: make `MemoryKernel` text query support real enough for live graph context, using the existing `ContextCompiler` and MemoryKernel facade rather than a side retrieval lane.
- Code changes landed locally:
  - Added `MemoryQuery.text_query` and central normalized-atom text filtering in `dharma_swarm/memory_kernel/atoms.py`.
  - Wired `build_memory_kernel_default_context()` to pass the compiler `recall_query` into `MemoryQuery.text_query`.
  - Added a MemoryKernel facade test proving a text query admits the matching witness atom and excludes an unrelated witness atom.
  - Added a live `ContextCompiler.compile_bundle()` test with a temporary `home.witness` surface proving the Memory Kernel section includes only matching admitted memory, carries `memory_kernel:home.witness`, and records `text_query_applied=true`.
- Generated artifact:
  - `reports/langgraph_parity/allnight/memory_live_retrieval_text_query_20260630T181038Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py::test_memory_query_filters_atoms_by_text_query tests/test_context_compiler_memory_kernel.py` -> `4 passed in 0.40s`.
  - `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py` -> `26 passed in 0.47s`.
  - `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py tests/test_context_compiler.py` -> `69 passed in 0.48s`.
  - `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/atoms.py dharma_swarm/memory_kernel/default_context.py tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py` -> pass.
- Scoreboard: raised conservatively to `50/100`, still explicitly not 100/100.
- Current blockers:
  - Phase 5 remains partial: MemoryKernel text-query live context is now proven, but topology-wide memory/tool isolation across live SWARM, SUPERVISOR, and SUBAGENTS_AS_TOOLS remains unproven.
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Full provider served-model truth and cockpit/API graph inspection remain pending.
