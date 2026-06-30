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

## 2026-06-30T18:39:05Z - Phase 5 Topology Agent Memory Isolation Slice

- Target gate: enforce topology-derived MemoryKernel agent isolation in the live `ContextCompiler` path and expose the policy on orchestrator dispatch metadata.
- Baseline/probe state:
  - `make onboard` -> pass; generated the known governance projection churn, which was inspected and restored before edits.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
- Code changes landed locally:
  - Added `MemoryContextBudget.allowed_agent_ids` and agent-owner omission reasons for `AGENT` scoped atoms: `agent_not_allowed` and `agent_owner_unknown`.
  - Added topology-derived MemoryKernel isolation policy metadata in `dharma_swarm/memory_kernel/default_context.py`.
  - Wired `ContextCompiler.compile_bundle()` to apply the policy for `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS` caller metadata.
  - Extended orchestrator MemoryKernel dispatch metadata with `memory_kernel_isolation_applied`, `memory_kernel_isolation_agent_id`, allowed agent ids, scopes, and memory lanes.
  - Added a parameterized compiler test proving all three live topology modes admit the active agent's scoped memory, admit shared project memory, and omit another agent's scoped memory.
  - Extended the orchestrator context-bundle metadata test to prove isolation telemetry reaches `TaskDispatch.metadata`.
- Generated artifact:
  - `reports/langgraph_parity/allnight/memory_topology_agent_isolation_20260630T183905Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py::test_context_compiler_applies_live_topology_agent_memory_isolation tests/test_orchestrator.py::test_attach_context_bundle_exposes_memory_kernel_metadata` -> `4 passed in 0.19s`.
  - `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_readiness.py tests/test_memory_kernel_prod_bar.py` -> `29 passed in 0.45s`.
  - `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_readiness.py tests/test_memory_kernel_prod_bar.py tests/test_context_compiler.py tests/test_context_compiler_vnext.py tests/test_context_compiler_cache.py` -> `84 passed in 0.85s`.
  - `.venv/bin/python -m pytest -q tests/test_orchestrator.py::test_attach_context_bundle_exposes_memory_kernel_metadata tests/test_orchestrator.py::test_swarm_handoff_persists_restartable_topology_state tests/test_orchestrator.py::test_subagents_as_tools_persists_parent_and_child_runs tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state` -> `4 passed in 1.75s`.
  - `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 30.52s`.
  - `.venv/bin/ruff check dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/context_compiler.py dharma_swarm/memory_kernel/orchestrator_context.py tests/test_context_compiler_memory_kernel.py tests/test_orchestrator.py` -> pass.
  - `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/context_compiler.py dharma_swarm/memory_kernel/orchestrator_context.py tests/test_context_compiler_memory_kernel.py tests/test_orchestrator.py` -> pass.
- Scoreboard: raised conservatively to `54/100`, still explicitly not 100/100.
- Current blockers:
  - Phase 5 remains partial: topology agent memory isolation is now proven at compiler/admission/dispatch-metadata level, but stale-memory rejection, curated-source coverage, retrieval telemetry, and full tool-exposure isolation remain unproven.
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Provider truth and cockpit/API graph inspection remain pending.

## 2026-06-30T19:04:22Z - Phase 6 Provider Truth Spine Receipt Slice

- Target gate: make orchestrator spine receipts bind requested/planned provider-model intent to actual served provider-model telemetry without changing `AgentRunner.run_task()`'s string return contract.
- Code changes landed locally:
  - Added `AgentRunner` last-dispatch telemetry fields: `_last_route_request`, `_last_route_decision`, `_last_response`, and `_last_usage`.
  - Reset those fields at task start and populate them on both success and failure from the existing route decision and `LLMResponse`.
  - Added `dharma_swarm/provider_truth.py` to normalize provider/model truth outside the oversized orchestrator module.
  - Updated `Orchestrator._run_task_via_spine()` to build `EvidenceReceipt.provider`/`model` from `LLMResponse` first, `ProviderRouteDecision` second, and runner config as the final fallback.
  - Extended `EvidenceReceipt.attributes` with `requested_provider`, `requested_model`, `planned_provider`, `planned_model`, `actual_provider`, `actual_model`, `served_provider`, `served_model`, `route_path`, `route_confidence`, `route_reasons`, `route_fallback_plan`, `route_requires_human`, `provider_truth_source`, `fallback_used`, and `actual_differs_from_requested`.
  - Normalized `prompt_tokens`/`completion_tokens` usage into receipt `input_tokens`/`output_tokens`.
  - Added a no-network routed-runner spine dispatch test proving requested Anthropic config can produce an actual OpenRouter served receipt with fallback plan and route confidence preserved.
- Generated artifact:
  - `reports/langgraph_parity/allnight/provider_truth_spine_receipt_20260630T190422Z.json`
- Verification:
  - `.venv/bin/python -m pytest tests/test_orchestrator_spine_dispatch.py tests/test_loop1_spine_provider_model.py -q` -> `8 passed in 0.35s`.
  - `.venv/bin/python -m pytest tests/test_orchestrator.py::test_orchestrator_spine_dispatch_is_default_and_persists_receipt tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state -q` -> `2 passed in 7.42s`.
  - `.venv/bin/python -m compileall -q dharma_swarm/agent_runner.py dharma_swarm/orchestrator.py dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> pass.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with warnings; `orchestrator.py` is 3205 lines against ceiling 3215.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `.venv/bin/python -m ruff check dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> pass.
  - `git diff --check` -> pass.
  - `.venv/bin/python -m ruff check dharma_swarm/agent_runner.py dharma_swarm/orchestrator.py dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> fail on pre-existing lint debt outside this diff: unused legacy imports, semicolon statements, unused locals, and one ambiguous variable name.
- Scoreboard: raised conservatively to `58/100`, still explicitly not 100/100.
- Current blockers:
  - Phase 6 remains partial: routed orchestrator dispatch receipts now bind actual served provider/model when `AgentRunner` has route/response telemetry, but there is no exhaustive live-provider matrix proof.
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Cockpit/API graph inspection remains pending.

## 2026-06-30T19:33:04Z - Phase 7 Runtime Graph API/Cockpit Slice Start

- Target gate: expose live graph state, active agent, handoffs, checkpoints, runs, and receipts through an operator-facing API/cockpit read model backed by `RuntimeStateStore`.
- Current branch: `codex/langgraph-orchestration-parity-20260701` at `ad080cc3d`.
- Worktree status at round start: clean and pushed; PR #732 is draft/open with `mergeStateStatus=CLEAN` and all listed checks green.
- Current implementation probe:
  - `dharma_swarm.operator_views.OperatorViews` already exposes runtime overview, active runs, actions, and bridge queue from canonical runtime state.
  - `RuntimeStateStore` already persists `topology_states`, `delegation_runs`, and `runtime_receipts`.
  - The dashboard runtime page currently reads `/api/chat/status` and `/api/health`, but not topology graph state, active agent, checkpoints, or receipts.
- Next target gate: add a scoped runtime graph read model and FastAPI route, then wire the dashboard runtime control-plane summary to consume it without introducing a parallel truth store.
- Current blockers remain: A2A strict readiness red, deeper memory retrieval/tool-isolation gates, exhaustive live-provider served-model proof, and complete cockpit/API coverage beyond this first graph inspection slice.

## 2026-06-30T19:48:46Z - Phase 7 Runtime Graph API/Cockpit Slice

- Target gate: expose persisted live topology graph state through an operator API/cockpit surface backed by `RuntimeStateStore`.
- Code changes landed locally:
  - Added `dharma_swarm/runtime_graph_views.py`, a sub-500-line graph read model over `topology_states`, `delegation_runs`, and `runtime_receipts`.
  - Kept `OperatorViews.runtime_graph()` as a thin facade over the graph read model.
  - Added `api/routers/runtime.py` with `GET /api/runtime/graph`, using `DHARMA_RUNTIME_DB` when set and `DEFAULT_RUNTIME_DB` otherwise.
  - Registered the runtime router in `api/main.py`.
  - Added dashboard runtime graph types, `fetchRuntimeGraph()`, runtime-control-plane graph summary fields, and a `/dashboard/runtime` graph panel showing active runs, active agents, checkpoints, topology rows, and recent receipts.
  - Added `tests/test_runtime_graph_api.py` proving a seeded runtime DB exposes active agent, checkpoint, parent/child run edges, handoff edges, and receipts through both `OperatorViews` and the API route.
- Generated artifact:
  - `reports/langgraph_parity/allnight/runtime_graph_api_cockpit_20260630T194846Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py` -> `4 passed in 0.95s`.
  - `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `55 passed in 31.54s`.
  - `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py tests/test_runtime_graph_api.py` -> `23 passed in 0.82s`.
  - `.venv/bin/python -m compileall -q dharma_swarm/operator_views.py dharma_swarm/runtime_graph_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `.venv/bin/ruff check dharma_swarm/operator_views.py dharma_swarm/runtime_graph_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `npm run lint` -> pass with existing warnings only: 0 errors, 19 warnings.
  - `npm run build` -> pass; `/dashboard/runtime` prerenders successfully.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`, `modules_over_500_lines` remained `207 -> 207` after extracting the graph view module.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `make onboard` -> pass; generated known governance projection churn, which was restored as unrelated.
  - `git diff --check` -> pass.
- Scoreboard: raised conservatively to `62/100`, still explicitly not 100/100.
- Current blockers:
  - Phase 7 remains partial: assistants/configurations, threads/session API, full checkpoint history, streaming runtime events, background/cron runs, and interrupt/resume/human approval surfaces remain incomplete or unproven.
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Memory stale rejection, curated-source coverage, retrieval telemetry, full tool-exposure isolation, and exhaustive live-provider proof remain pending.

## 2026-06-30T20:39:45Z - Phase 7 Runtime Platform API Surfaces

- Target gate: extend the RuntimeStateStore-backed operator/API platform surface beyond graph inspection to sessions/threads, runs, run detail, checkpoint snapshots, and runtime events.
- Code changes landed locally:
  - Added `dharma_swarm/runtime_platform_views.py`, a sub-500-line read model over `sessions`, `delegation_runs`, `topology_states`, `runtime_receipts`, and `session_events`.
  - Added `OperatorViews` facades for `runtime_sessions`, `runtime_runs`, `runtime_run_detail`, `runtime_checkpoints`, and `runtime_events`.
  - Added FastAPI routes: `GET /api/runtime/sessions`, `/api/runtime/runs`, `/api/runtime/runs/{run_id}`, `/api/runtime/checkpoints`, and `/api/runtime/events`.
  - Extended `tests/test_runtime_graph_api.py` to seed a canonical runtime DB with session state, parent/child runs, topology checkpoint state, receipt, and event history, then prove both operator views and API handlers read that DB through `DHARMA_RUNTIME_DB`.
- Generated artifact:
  - `reports/langgraph_parity/allnight/runtime_platform_surfaces_20260630T203945Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py` -> `5 passed in 0.68s`.
  - `.venv/bin/python -m compileall -q dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `.venv/bin/ruff check dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `57 passed in 34.45s`.
  - `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py tests/test_runtime_graph_api.py` -> `25 passed in 1.10s`.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `git diff --check` -> pass.
- Scoreboard: raised conservatively to `65/100`, still explicitly not 100/100.
- Current blockers:
  - Phase 7 remains partial: sessions/runs/run-detail/checkpoint snapshots/runtime events are API-visible, but assistants/configurations, streaming runtime event transport, background/cron runs, and interrupt/resume/human approval surfaces remain incomplete or unproven.
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Memory stale rejection, curated-source coverage, retrieval telemetry, full tool-exposure isolation, and exhaustive live-provider proof remain pending.

## 2026-06-30T21:05:49Z - Supervisor Restart Final-Output Proof

- Target gate: prove `SUPERVISOR` topology restart/readback semantics for delegated-agent state and final-output-only policy.
- Code changes landed locally:
  - Persisted `supervisor_final_output_only: true` inside the supervisor `topology_state`, alongside delegated agent IDs and `user_visible_output: supervisor_final`.
  - Extended topology-state runtime receipts to include the persisted `state` payload, so operator/API receipt views can inspect the same policy that is stored in `topology_states`.
  - Added a restart-readable orchestrator acceptance test that dispatches a supervisor run, drains execution, reopens a fresh `RuntimeStateStore`, and verifies the supervisor `DelegationRun`, `TopologyStateRecord`, `describe_run()` detail, and `topology_state` receipt.
- Generated artifact:
  - `reports/langgraph_parity/allnight/supervisor_restart_final_output_20260630T210549Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_orchestrator.py::test_supervisor_persists_restartable_final_output_policy_and_delegated_state tests/test_orchestrator.py::test_swarm_handoff_persists_restartable_topology_state tests/test_orchestrator.py::test_subagents_as_tools_persists_parent_and_child_runs tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state` -> `4 passed in 2.30s`.
  - `.venv/bin/python -m compileall -q dharma_swarm/orchestrator.py dharma_swarm/runtime_topology.py tests/test_orchestrator.py tests/test_topology_execution.py tests/test_runtime_state.py` -> pass.
  - `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `51 passed in 46.26s`.
  - `.venv/bin/ruff check dharma_swarm/runtime_topology.py tests/test_orchestrator.py` -> pass.
  - `.venv/bin/ruff check --select F821 dharma_swarm/orchestrator.py` -> pass.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings; `orchestrator.py` is 3206 lines against ceiling 3215.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> expected fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `make onboard` -> pass; known governance projection churn restored.
  - `git diff --check` -> pass.
- Scoreboard: raised conservatively to `67/100`, still explicitly not 100/100.
- Current blockers:
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Memory stale rejection, curated-source coverage, retrieval telemetry, full tool-exposure isolation, and exhaustive live-provider proof remain pending.
  - Runtime platform parity remains partial: assistants/configurations, streaming runtime event transport, background/cron runs, and interrupt/resume/human approval surfaces remain incomplete or unproven.
  - Closeout governance remains blocked by aggregate full-history gitleaks findings.

## 2026-06-30T21:37:55Z - Runtime Interrupts and Streaming Event State

- Target gate: extend the RuntimeStateStore-backed runtime platform surface to streaming runtime event transport plus interrupt/resume/human-approval state.
- Code changes landed locally:
  - Added `RuntimePlatformViews.runtime_interrupts()` and `OperatorViews.runtime_interrupts()`, deriving control state from canonical `session_events`.
  - Added `GET /api/runtime/events/stream` for persisted runtime events over server-sent events, with session, ledger, event-name, limit, poll, and finite-test filters.
  - Added `GET /api/runtime/interrupts` for interrupt/resume/human-approval snapshots.
  - Extended `tests/test_runtime_graph_api.py` to seed `interrupt_requested` and `human_approval_granted` runtime events, then prove operator, API, and SSE readback from `DHARMA_RUNTIME_DB`.
  - Added dashboard runtime interrupt types, `fetchRuntimeInterrupts()`, `runtimeEventsStreamPath()`, control-plane snapshot counts, and `/dashboard/runtime` control-event rendering.
- Generated artifact:
  - `reports/langgraph_parity/allnight/runtime_interrupts_streaming_20260630T213755Z.json`
- Verification:
  - `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py` -> `7 passed in 1.66s`.
  - `.venv/bin/ruff check dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `.venv/bin/python -m compileall -q dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
  - `npm run lint -- --quiet` from `dashboard/` -> pass.
  - `npm run build` from `dashboard/` -> pass; `/dashboard/runtime` prerendered successfully.
  - `.venv/bin/python -m pytest -q tests/test_langgraph_parity_swarm.py tests/test_langgraph_parity_isolation_benchmark.py tests/test_langgraph_parity_readiness.py tests/test_langgraph_parity_supervisor.py tests/test_runtime_state.py tests/test_runtime_state_invariants.py tests/test_runtime_state_recovery.py tests/test_orchestrator.py tests/test_orchestrator_v1.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py` -> `98 passed in 34.54s`.
  - `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
  - `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> expected fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - `make onboard` -> pass; known governance projection churn restored.
  - `git diff --check` -> pass.
- Scoreboard: raised conservatively to `70/100`, still explicitly not 100/100.
- Current blockers:
  - A2A strict readiness remains red: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
  - Runtime platform parity remains partial: assistants/configurations and background/cron run surfaces are still missing.
  - Interrupt/resume/human-approval state is visible, but approval/reject/resume action endpoints are not implemented in this slice.
  - Memory stale rejection, curated-source coverage, retrieval telemetry, full tool-exposure isolation, and exhaustive live-provider proof remain pending.
  - Closeout governance remains blocked by aggregate full-history gitleaks findings.
