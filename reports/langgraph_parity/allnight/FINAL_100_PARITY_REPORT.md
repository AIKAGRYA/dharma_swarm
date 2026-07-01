# Final 100 Parity Report

Status: **not 100/100**.

Current score: **84/100**.

Branch: `codex/langgraph-orchestration-parity-20260701`.

Implementation commits: branch history through the current runtime multi-process resume proof on this branch.

Remote branch: `origin/codex/langgraph-orchestration-parity-20260701`.

This branch made real progress but does not satisfy the definition of 100/100. The strongest evidence is:

- `reports/langgraph_parity/benchmark/benchmark_report.json` now contains 26 deterministic benchmark cases, 12 multi-hop cases, and complete coverage for all required Phase 1 tags.
- Runtime orchestrator dispatch is default-on through `invoke_agent`; `DHARMA_SPINE_DISPATCH` is now an explicit false-like opt-out.
- `scripts/governance/spine_dispatch_mode_report.py --strict` passes and reports `orchestrator_mode: spine_default_on`.
- Live topology enum modes exist: `SWARM`, `SUPERVISOR`, `SUBAGENTS_AS_TOOLS`; dispatch stamps active-agent/delegation/parent graph metadata.
- `RuntimeStateStore` now has first-class `topology_states` rows. SWARM accepted handoff state and SUBAGENTS_AS_TOOLS parent/child run IDs are written through `RuntimeLifecycle.record_delegation_run`.
- Restart-readable proof exists: a fresh `RuntimeStateStore` instance reopens the same DB and reads the SWARM active agent/handoff receipt plus subagent child delegation rows.
- Orchestrator `EvidenceReceipt` now stamps run/idempotency/side-effect/topology/planned-provider/actual-provider attributes.
- Orchestrator spine `EvidenceReceipt` provider/model fields now prefer actual `LLMResponse` served provider/model, fall back to `ProviderRouteDecision`, then runner config. Receipt attributes also preserve requested/planned/actual/served provider-model values, route path, route confidence, route reasons, fallback plan, and normalized token counts.
- `MemoryKernel` now supports `MemoryQuery.text_query`, and the default live `ContextCompiler` Memory Kernel section passes `recall_query` into that lane. A live bundle test proves a matching witness atom is admitted while an unrelated witness atom is excluded.
- Live topology context now derives agent memory isolation from `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS` compiler metadata. `MemoryContextBudget.allowed_agent_ids` blocks cross-agent `AGENT`-scoped atoms, and orchestrator dispatch metadata mirrors the isolation policy for operator inspection.
- Live Memory Kernel context now rejects stale memory by policy: `MemoryContextBudget.reject_stale` blocks snapshot/dormant/missing/unknown freshness values and expired `valid_until` atoms. Default `ContextCompiler` Memory Kernel metadata now includes retrieval telemetry with admitted/omitted surface IDs and selection/omission/warning reason counts.
- Live Memory Kernel context now enforces curated-source admission coverage with `MemoryContextBudget.require_source_digest` and `require_source_row_key`, while preserving the existing `MemoryQuery` source requirements. It also blocks structured tool-exposure metadata such as visible tool lists, tool calls/results, tool plans, and tool schemas from default live context packs.
- Runtime topology graph state is now inspectable through `GET /api/runtime/graph` and `/dashboard/runtime`, backed by `RuntimeStateStore` rather than a parallel store. The graph snapshot includes active agents, checkpoints, topology states, runs, receipts, handoffs, parent/child edges, active-agent edges, and checkpoint edges.
- Runtime platform state is now inspectable through `GET /api/runtime/sessions`, `/api/runtime/runs`, `/api/runtime/runs/{run_id}`, `/api/runtime/checkpoints`, and `/api/runtime/events`, backed by the same `RuntimeStateStore`. The API surfaces session/thread state, run listings, run ledger detail via `describe_run`, checkpoint/topology snapshots, and session/runtime event history.
- Persisted runtime events now have an SSE transport at `GET /api/runtime/events/stream`, and interrupt/resume/human-approval state is projected from `session_events` through `GET /api/runtime/interrupts`, `OperatorViews.runtime_interrupts()`, and `/dashboard/runtime` control-event summaries. This is state/transport proof, not approval action execution.
- Runtime Agent Server-style assistants/configurations and background/cron jobs are now inspectable through `RuntimeAgentServerViews`, `OperatorViews`, `GET /api/runtime/assistants`, `GET /api/runtime/background-jobs`, and `/dashboard/runtime`, deriving state from `RuntimeStateStore` plus existing cron scheduler storage rather than adding a parallel dashboard store.
- Runtime approve/reject/resume actions are now exposed through `POST /api/runtime/interrupts/approve`, `/reject`, and `/resume`. They write canonical `OperatorAction` audit rows, emit `operator_control` `SessionEventRecord` rows, return refreshed interrupt snapshots, and best-effort write checkpoint interrupt responses when an `interrupt_id` is supplied.
- Runtime resume now has fresh-process proof: a child Python process calls the configured `runtime_interrupt_resume` API route against `DHARMA_RUNTIME_DB`, then the parent process reopens the same `RuntimeStateStore` and verifies the `runtime_resume_requested` event, `runtime_control.resume` action row, resume token, and checkpoint detail.
- Supervisor restart-readable proof now exists: `SUPERVISOR` topology persists delegated agent IDs, `supervisor_final_output_only: true`, and `user_visible_output: supervisor_final` in `TopologyStateRecord.state`; `describe_run()` and `topology_state` receipts expose the same persisted state.

## Verification

- `make onboard` -> pass after `.venv` exists.
- `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py` -> `20 passed in 0.37s`.
- `.venv/bin/python -m pytest -q tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `66 passed in 28.95s`.
- `.venv/bin/python -m pytest -q tests/test_runtime_state.py::test_topology_state_survives_store_restart tests/test_orchestrator.py::test_swarm_handoff_persists_restartable_topology_state tests/test_orchestrator.py::test_subagents_as_tools_persists_parent_and_child_runs tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state` -> `4 passed in 2.35s`.
- `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 30.44s`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2.
- `make agent-build-preflight` -> pass; compileall clean, F821 clean, 12,328 tests collected, onboard OK, hygiene integrity OK.
- `make agent-build-closeout` -> fail exit 2; semgrep skipped because it is not installed on PATH, then gitleaks reported 68 redacted findings after scanning 2,720 commits.
- CI repair after draft PR #732 first run: extracted topology helpers to `dharma_swarm/runtime_topology.py` and the benchmark case catalogue to `dharma_swarm/langgraph_parity/benchmark_tasks.py`.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `modules_over_500_lines` stayed `207 -> 207`, `boundary_unfrozen_records` stayed `7 -> 7`.
- `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 37.48s` after the CI repair extraction.
- CI repair after draft PR #732 second run: `pytest (3.12)` found a stale `TopologyType` enum count assertion in `tests/test_models.py`; it now asserts the explicit 7 topology values.
- `.venv/bin/python -m pytest -q tests/test_models.py` -> `16 passed in 0.13s`.
- Phase 4 A2A reconciliation: added `scripts/governance/a2a_reconcile_embedded_receipts.py` and normalized two live queue rows that already had valid embedded terminal `a2a_supervisor` receipts.
- `.venv/bin/python -m pytest -q tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `19 passed in 0.44s`.
- `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py` after apply -> `candidate_count=0`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` after reconciliation -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- Phase 4 blocker audit: added `scripts/governance/a2a_readiness_blocker_audit.py`.
- `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py` -> `4 passed in 0.39s`.
- `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `23 passed in 0.41s`.
- `.venv/bin/python -m compileall -q scripts/governance/a2a_readiness_blocker_audit.py tests/test_a2a_readiness_blocker_audit.py` -> pass.
- `.venv/bin/python scripts/governance/a2a_readiness_blocker_audit.py --artifact-root /Users/dhyana/ds_langgraph_parity_20260701 --artifact-root /Users/dhyana/dharma_swarm --output reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json` -> pass; `blocker_count=36`.
- `git diff --check` -> pass.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- Phase 5 MemoryKernel text-query live context slice: added `MemoryQuery.text_query` filtering and wired `build_memory_kernel_default_context()` to use the compiler `recall_query`.
- `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py::test_memory_query_filters_atoms_by_text_query tests/test_context_compiler_memory_kernel.py` -> `4 passed in 0.40s`.
- `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py` -> `26 passed in 0.47s`.
- `.venv/bin/python -m pytest -q tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py tests/test_context_compiler.py` -> `69 passed in 0.48s`.
- `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/atoms.py dharma_swarm/memory_kernel/default_context.py tests/test_memory_kernel_readiness.py tests/test_context_compiler_memory_kernel.py` -> pass.
- Phase 5 receipt: `reports/langgraph_parity/allnight/memory_live_retrieval_text_query_20260630T181038Z.json`.
- Phase 5 topology agent-memory isolation slice: added `MemoryContextBudget.allowed_agent_ids`, topology-derived isolation policy metadata, and dispatch-level isolation telemetry.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py::test_context_compiler_applies_live_topology_agent_memory_isolation tests/test_orchestrator.py::test_attach_context_bundle_exposes_memory_kernel_metadata` -> `4 passed in 0.19s`.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_context_eval.py tests/test_memory_kernel_readiness.py tests/test_memory_kernel_prod_bar.py tests/test_context_compiler.py tests/test_context_compiler_vnext.py tests/test_context_compiler_cache.py` -> `84 passed in 0.85s`.
- `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `75 passed in 30.52s`.
- `.venv/bin/ruff check dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/context_compiler.py dharma_swarm/memory_kernel/orchestrator_context.py tests/test_context_compiler_memory_kernel.py tests/test_orchestrator.py` -> pass.
- `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/context_compiler.py dharma_swarm/memory_kernel/orchestrator_context.py tests/test_context_compiler_memory_kernel.py tests/test_orchestrator.py` -> pass.
- Phase 5 isolation receipt: `reports/langgraph_parity/allnight/memory_topology_agent_isolation_20260630T183905Z.json`.
- Phase 5 stale-memory/retrieval-telemetry slice: default live Memory Kernel context packs now reject stale/expired atoms and expose retrieval telemetry in `memory_kernel_default` metadata.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py::test_context_compiler_rejects_stale_memory_with_retrieval_telemetry --tb=short` -> `1 passed in 0.38s`.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_kernel_readiness.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py` -> `30 passed in 0.63s`.
- `.venv/bin/python -m pytest -q tests/test_context_compiler.py tests/test_context_compiler_vnext.py tests/test_context_compiler_cache.py` -> `55 passed in 0.80s`.
- `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py tests/test_context_compiler_memory_kernel.py` -> pass.
- `.venv/bin/ruff check dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py tests/test_context_compiler_memory_kernel.py` -> pass.
- `git diff --check` -> pass.
- Phase 5 stale-memory/retrieval-telemetry receipt: `reports/langgraph_parity/allnight/memory_stale_rejection_telemetry_20260630T234621Z.json`.
- Phase 5 curated-source/tool-exposure isolation slice: default live Memory Kernel context packs now require source digest/row key at query and admission layers, and block structured tool-exposure metadata.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py::test_context_compiler_enforces_curated_source_and_tool_exposure_isolation --tb=short` -> `1 passed in 0.22s`.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_kernel_readiness.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py` -> `31 passed in 0.60s`.
- `.venv/bin/python -m pytest -q tests/test_context_compiler.py tests/test_context_compiler_vnext.py tests/test_context_compiler_cache.py` -> `55 passed in 0.65s`.
- CI line-budget repair: split structured tool exposure detection to `dharma_swarm/memory_kernel/tool_exposure.py`; `context_admission.py` is now 472 lines.
- `.venv/bin/python -m pytest -q tests/test_context_compiler_memory_kernel.py tests/test_memory_kernel_readiness.py tests/test_memory_context_eval.py tests/test_memory_kernel_prod_bar.py tests/test_context_compiler.py tests/test_context_compiler_vnext.py tests/test_context_compiler_cache.py` -> `86 passed in 0.94s`.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `modules_over_500_lines` stayed `207 -> 207`.
- `.venv/bin/python -m compileall -q dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/memory_kernel/tool_exposure.py tests/test_context_compiler_memory_kernel.py` -> pass.
- `.venv/bin/ruff check dharma_swarm/memory_kernel/context_admission.py dharma_swarm/memory_kernel/default_context.py dharma_swarm/memory_kernel/tool_exposure.py tests/test_context_compiler_memory_kernel.py` -> pass.
- `git diff --check` -> pass.
- Phase 5 curated-source/tool-exposure isolation receipt: `reports/langgraph_parity/allnight/memory_curated_source_tool_isolation_20260701T000816Z.json`.
- Phase 6 provider-truth spine receipt slice: added `AgentRunner` last-dispatch route/response telemetry, `dharma_swarm/provider_truth.py`, and updated orchestrator spine receipts to bind requested, planned, actual, and served provider/model truth.
- `.venv/bin/python -m pytest tests/test_orchestrator_spine_dispatch.py tests/test_loop1_spine_provider_model.py -q` -> `8 passed in 0.35s`.
- `.venv/bin/python -m pytest tests/test_orchestrator.py::test_orchestrator_spine_dispatch_is_default_and_persists_receipt tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state -q` -> `2 passed in 7.42s`.
- `.venv/bin/python -m compileall -q dharma_swarm/agent_runner.py dharma_swarm/orchestrator.py dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> pass.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with warnings; `orchestrator.py` is 3205 lines against ceiling 3215.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- `.venv/bin/python -m ruff check dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> pass.
- `git diff --check` -> pass.
- `.venv/bin/python -m ruff check dharma_swarm/agent_runner.py dharma_swarm/orchestrator.py dharma_swarm/provider_truth.py tests/test_orchestrator_spine_dispatch.py` -> fail on pre-existing lint debt outside this diff: unused legacy imports, semicolon statements, unused locals, and one ambiguous variable name.
- Phase 6 receipt: `reports/langgraph_parity/allnight/provider_truth_spine_receipt_20260630T190422Z.json`.
- Phase 7 runtime graph API/cockpit slice: added `dharma_swarm/runtime_graph_views.py`, `api/routers/runtime.py`, dashboard runtime graph types/fetch/control-plane fields, and a `/dashboard/runtime` graph panel.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py` -> `4 passed in 0.95s`.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `55 passed in 31.54s`.
- `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py tests/test_runtime_graph_api.py` -> `23 passed in 0.82s`.
- `.venv/bin/python -m compileall -q dharma_swarm/operator_views.py dharma_swarm/runtime_graph_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/ruff check dharma_swarm/operator_views.py dharma_swarm/runtime_graph_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `npm run lint` -> pass with existing warnings only: 0 errors, 19 warnings.
- `npm run build` -> pass; `/dashboard/runtime` prerenders successfully.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`, `modules_over_500_lines` remained `207 -> 207`.
- Phase 7 receipt: `reports/langgraph_parity/allnight/runtime_graph_api_cockpit_20260630T194846Z.json`.
- Phase 7 runtime platform API surface slice: added `dharma_swarm/runtime_platform_views.py`, `OperatorViews` facades, and API routes for sessions, runs, run detail, checkpoints, and events.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py` -> `5 passed in 0.68s`.
- `.venv/bin/python -m compileall -q dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/ruff check dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `57 passed in 34.45s`.
- `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py tests/test_runtime_graph_api.py` -> `25 passed in 1.10s`.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- Phase 7 platform receipt: `reports/langgraph_parity/allnight/runtime_platform_surfaces_20260630T203945Z.json`.
- Supervisor restart final-output proof: persisted `supervisor_final_output_only`, delegated agent IDs, and user-visible-output policy in restartable topology state and topology-state receipts.
- `.venv/bin/python -m pytest -q tests/test_orchestrator.py::test_supervisor_persists_restartable_final_output_policy_and_delegated_state tests/test_orchestrator.py::test_swarm_handoff_persists_restartable_topology_state tests/test_orchestrator.py::test_subagents_as_tools_persists_parent_and_child_runs tests/test_topology_execution.py::test_orchestrator_live_langgraph_topologies_stamp_graph_state` -> `4 passed in 2.30s`.
- `.venv/bin/python -m compileall -q dharma_swarm/orchestrator.py dharma_swarm/runtime_topology.py tests/test_orchestrator.py tests/test_topology_execution.py tests/test_runtime_state.py` -> pass.
- `.venv/bin/python -m pytest -q tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `51 passed in 46.26s`.
- `.venv/bin/ruff check dharma_swarm/runtime_topology.py tests/test_orchestrator.py` -> pass.
- `.venv/bin/ruff check --select F821 dharma_swarm/orchestrator.py` -> pass.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings; `orchestrator.py` is 3206 lines against ceiling 3215.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> expected fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- `make onboard` -> pass; known governance projection churn restored.
- Runtime Agent Server/background receipt: `reports/langgraph_parity/allnight/runtime_agent_server_background_20260630T222517Z.json`.
- `make agent-build-preflight` -> pass; compileall clean, F821 clean, 12,347 tests collected, onboard OK, hygiene integrity OK.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py` -> `6 passed in 1.78s`.
- `.venv/bin/ruff check dharma_swarm/runtime_agent_server_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/python -m compileall -q dharma_swarm/runtime_agent_server_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `node --experimental-strip-types --test src/lib/runtimeControlPlane.test.ts` from `dashboard/` -> `11 passed`; Node emitted experimental type-stripping warnings only.
- `npm run lint -- --quiet` from `dashboard/` -> pass.
- `npm run build` from `dashboard/` -> pass; `/dashboard/runtime` prerendered successfully.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `59 passed in 197.43s`.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> expected fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- `git diff --check` -> pass.
- Runtime control action receipt: `reports/langgraph_parity/allnight/runtime_control_actions_20260630T225400Z.json`.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py` -> `7 passed in 1.23s`.
- `.venv/bin/ruff check dharma_swarm/runtime_control_actions.py dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/python -m compileall -q dharma_swarm/runtime_control_actions.py dharma_swarm/runtime_platform_views.py dharma_swarm/operator_views.py api/routers/runtime.py tests/test_runtime_graph_api.py` -> pass.
- `node --experimental-strip-types --test src/lib/runtimeControlPlane.test.ts` from `dashboard/` -> `11 passed`; Node emitted experimental type-stripping warnings only.
- `npm run lint -- --quiet` from `dashboard/` -> pass.
- `npm run build` from `dashboard/` -> pass; `/dashboard/runtime` prerendered successfully.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_orchestrator.py tests/test_topology_execution.py` -> `60 passed in 29.29s`.
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings.
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`, `modules_over_500_lines` stayed `207 -> 207`.
- `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; `orchestrator_mode: spine_default_on`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> expected fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`.
- `make agent-build-preflight` -> pass; compileall clean, F821 clean, 12,349 tests collected, onboard OK, hygiene integrity OK.
- `git diff --check` -> pass.
- Supervisor proof receipt: `reports/langgraph_parity/allnight/supervisor_restart_final_output_20260630T210549Z.json`.
- Runtime interrupts/streaming receipt: `reports/langgraph_parity/allnight/runtime_interrupts_streaming_20260630T213755Z.json`.
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
- Runtime multi-process resume receipt: `reports/langgraph_parity/allnight/runtime_multiprocess_resume_20260701T003444Z.json`.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py::test_runtime_resume_action_survives_fresh_python_process --tb=short` -> `1 passed in 0.61s`.
- `.venv/bin/python -m pytest -q tests/test_runtime_graph_api.py tests/test_operator_views.py tests/test_api_main_bootstrap.py tests/test_runtime_state.py tests/test_runtime_state_invariants.py tests/test_runtime_state_recovery.py` -> `24 passed in 3.84s`.
- `.venv/bin/python -m compileall -q tests/test_runtime_graph_api.py` -> pass.
- `.venv/bin/ruff check tests/test_runtime_graph_api.py` -> pass.
- `jq -e . reports/langgraph_parity/allnight/SCOREBOARD.json` -> pass.
- `git diff --check` -> pass.

## Failing Gates

- A2A strict readiness: `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`; queue path `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl`.
- A2A remaining blocker receipt: `reports/langgraph_parity/allnight/A2A_PHASE4_BLOCKER_RECEIPT.md`; replayable JSON audit: `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json`.
- A2A blocker audit classification: 11 stale claimed rows without terminal receipts, 6 stale unclaimed rows, 18 valid SAB semantic receipts that are still non-A2A evidence, and 1 completed `ts-converge-0611` row with no receipt pointer.
- Closeout governance: `make agent-build-closeout` fails at the secrets scan gate (`gitleaks` aggregate: 68 redacted findings). Findings were not expanded in this report to avoid exposing secret material.
- Memory live retrieval: current executable lane passed. MemoryKernel text-query selection now feeds live `ContextCompiler` bundles with safety filters preserved, topology-derived agent memory isolation is proven across `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS` compiler metadata, stale/expired atoms are rejected from default live packs, retrieval telemetry is emitted, source digest/row key admission is enforced, and structured tool-exposure metadata is blocked.
- Provider truth: partial. Orchestrator spine receipts now capture actual served provider/model from `LLMResponse`/`ProviderRouteDecision` when `AgentRunner` has telemetry, with runner config as fallback. This is not yet an exhaustive live-provider matrix proof.
- Cockpit/API: partial. Runtime graph inspection is wired for active agent, handoffs, checkpoints, runs, and receipts; sessions/threads, run listings, run detail, checkpoint snapshots, runtime event history, SSE runtime-event transport, interrupt/resume/human-approval state, assistants/configurations, background/cron runs, approve/reject/resume action endpoints, and fresh-process resume persistence are visible through `RuntimeStateStore`-backed API/operator views, with dashboard summary coverage and typed action helpers.

## Next Patch Sequence

1. Build a safe A2A blocker closure workflow that verifies or externally quarantines each listed task ID with receipts; rerun `check_a2a_readiness.py --strict`.
2. Extend provider-truth proof to an exhaustive live-provider matrix and make every live provider completion receipt assert route plan, fallback behavior, and actual served model.
3. Add dashboard action UI on top of the accepted approve/reject/resume backend contract without creating dashboard-only control state.
4. Keep widening cockpit/API proof only from canonical `RuntimeStateStore` sources.

## Residual Risk

The conformance oracle is stronger now, but it is still not the live runtime backbone. The branch should not claim production-grade LangGraph parity until the failing gates above have direct runtime evidence.
