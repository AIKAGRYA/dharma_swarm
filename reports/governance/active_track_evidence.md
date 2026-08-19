# Track Portfolio Evidence

Generated: 2026-08-19T18:04:15+00:00 (schema v2)
Active tracks: **10** (warn 8, max 10) — shippable 0

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✓
- `research-depth` — ✓

## `loop-closure-2026-06` — 32/32

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: ['organism-rewire-2026-07'] · conflicts_with: []
- owned_surfaces: ['reports/loop_closure/**', 'CYBERNETIC_LOOP_MAP.md', 'docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md', 'scripts/governance/loop1_consumption_check.py', 'tests/test_loop_supervisor_tristate.py', 'tests/test_loop1_consumption.py', 'tests/test_loop1_consumption_check.py']
- moves_vital_signs: ['quality_gates', 'eval_coverage']
- claim_boundary: CLOSED_LIVE 0/13; HARNESS_PROVEN 11/13; BLOCKED 2/13. Completion criteria only prove the claim-boundary artifact set, not production-live closure.
- ship_blocks: 3 open blocker next-item(s); 1 active ship veto(es): cybernetics_codex_harness_proven_blocks_live_ship: reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'HARNESS_PROVEN': 11 > 0; outcome receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json reports verdict='BLOCKED' — not a passing verdict; the track's own scoreboard does not say the work is done

  - ACTIVE ship veto `cybernetics_codex_harness_proven_blocks_live_ship` (json_count_greater_than) — reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'HARNESS_PROVEN': 11 > 0

  - ✓ `loop_map_exists` (file_exists) — CYBERNETIC_LOOP_MAP.md present
  - ✓ `loop_supervisor_exists` (file_exists) — dharma_swarm/loop_supervisor.py present
  - ✓ `phase0_dossier_exists` (file_exists) — reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md present
  - ✓ `phase0_fresh_status_table` (file_contains) — pattern 'Fresh 13-loop status table' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `one_wire_invariant_stated` (file_contains) — pattern 'never let internal artifacts touch archive fitness' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `loop1_closure_receipt_exists` (file_exists) — reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md present
  - ✓ `campaign_retrospective_exists` (file_exists) — reports/loop_closure/RETROSPECTIVE.md present
  - ✓ `cybernetics_codex_manifest_registered` (file_contains) — pattern 'id: cybernetics_codex' found in ACTIVE_SURFACE_MANIFEST.yaml
  - ✓ `cybernetics_codex_seed_exists` (file_exists) — docs/agents/cybernetics_codex/agent.seed.yaml present
  - ✓ `cybernetics_codex_soul_exists` (file_exists) — docs/agents/cybernetics_codex/SOUL.md present
  - ✓ `cybernetics_codex_context_desk_exists` (file_exists) — docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md present
  - ✓ `cybernetics_codex_audit_script_exists` (file_exists) — scripts/governance/cybernetics_codex_audit.py present
  - ✓ `cybernetics_codex_registration_script_exists` (file_exists) — scripts/governance/register_cybernetics_codex.py present
  - ✓ `cybernetics_codex_latest_audit_exists` (file_exists) — reports/loop_closure/cybernetics_codex/latest_audit.json present
  - ✓ `cybernetics_codex_latest_audit_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/latest_audit.json valid (5 keys present, fresh)
  - ✓ `cybernetics_codex_loop_verdict_map_matches_claim_boundary` (json_collection_values_match) — reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses 13 expected verdict value(s) matched
  - ✓ `cybernetics_codex_live_owner_criteria_declared` (json_mapping_keys_nonempty) — reports/loop_closure/cybernetics_codex/latest_audit.json.live_owner_surface_criteria has non-empty values for 13 key(s)
  - ✓ `cybernetics_codex_closed_live_count_zero` (json_count_equals) — reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'CLOSED_LIVE': 0 == 0
  - ✓ `cybernetics_codex_harness_proven_count_11` (json_count_equals) — reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'HARNESS_PROVEN': 11 == 11
  - ✓ `cybernetics_codex_blocked_count_2` (json_count_equals) — reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'BLOCKED': 2 == 2
  - ✓ `cybernetics_codex_loop3_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop3_evolution_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop4_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop4_memory_context_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop7_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop7_training_flywheel_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop8_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop8_recognition_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop9_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop9_conductor_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop10_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop10_context_agent_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop11_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop11_replication_monitor_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_one_wire_guard_test_exists` (file_exists) — tests/test_one_wire_archive_fitness_guard.py present
  - ✓ `cybernetics_codex_one_wire_guard_test_passes` (test_passes) — pytest tests/test_one_wire_archive_fitness_guard.py: PASS — 19 passed in 0.82s
  - ✓ `cybernetics_codex_loop12_13_guard_receipt_exists` (file_exists) — reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json present
  - ✓ `cybernetics_codex_loop12_13_guard_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json valid (5 keys present)
  - ✓ `loop_supervisor_tristate_honest` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_loop_supervisor_tristate.py -q exited 0 (resolved from python3 -m pytest tests/test_loop_supervisor_tristate.py -q); output: ......................                                                   [100%] | 22 passed in 0.64s
  - ✓ `loop1_consumption_unit_proof` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_loop1_consumption.py -q exited 0 (resolved from python3 -m pytest tests/test_loop1_consumption.py -q); output: ......                                                                   [100%] | 6 passed in 0.52s
  - ✓ `loop1_consumption_check_replays` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 scripts/governance/loop1_consumption_check.py --check exited 0 (resolved from python3 scripts/governance/loop1_consumption_check.py --check); output: { | "authorized_provider_order": [ | "anthropic", | "openai", | "openrouter", | "ollama" | ], | "chain_verified": false, | "consumed_trace_ids": [], | "consumer_boot_id": "", | "consumer_trace_id": "", | "container_image_digest": "", | "container_image_provenance": "", | "content_digest": "71fd5c8676a51c0afab175530fdcbf56bed17623e2445434961e14934428d267", | "db_path": "/home/runner/.dharma/state/runtime.db", | "decision_delta": {}, | "delegation_runs_row_count": 0, | "host_sha": "abc8bd35c34c...

## `orchestration-arena-v1-2026-06` — 11/12

- serves: `substrate-nativeness` · complements: ['provider-routing-consolidation-2026-06', 'loop-closure-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/coordination/**', 'dharma_swarm/council/**', 'scripts/governance/arena_truth_report.py', 'reports/governance/arena/**', 'tests/test_arena_v1.py', 'tests/test_dpi.py', 'tests/test_orchestration_genome.py', 'tests/test_orchestrator_v1.py', 'tests/test_council_profiles.py', 'tests/test_coordination_closure_checks.py', 'tests/test_arena_truth_report.py']
- moves_vital_signs: ['eval_coverage', 'quality_gates']
- ship_blocks: 1 open blocker next-item(s)

  - ✓ `arena_runner_exists` (file_exists) — dharma_swarm/coordination/arena/runner.py present
  - ✓ `arena_scorer_exists` (file_exists) — dharma_swarm/coordination/arena/scorer.py present
  - ✓ `orchestration_genome_exists` (file_exists) — dharma_swarm/coordination/genome.py present
  - ✓ `frozen_taskpack_present` (file_contains) — pattern 'TASK_PACK_ID' found in dharma_swarm/coordination/arena/taskpack.py
  - ✓ `deterministic_scorer_hash` (file_contains) — pattern 'def scorer_hash' found in dharma_swarm/coordination/arena/scorer.py
  - ✓ `orchestration_genome_class` (file_contains) — pattern 'class OrchestrationGenome' found in dharma_swarm/coordination/genome.py
  - ✓ `zero_weight_orchestrator_map_elites` (file_contains) — pattern 'class MapElitesArchive' found in dharma_swarm/coordination/orchestrator_v1.py
  - ✓ `dpi_decorrelation_gated_on_correctness` (file_contains) — pattern 'def decorrelation_bonus' found in dharma_swarm/coordination/dpi.py
  - ✓ `council_trace_verification` (file_contains) — pattern 'class Council' found in dharma_swarm/council/council.py
  - ✓ `arena_v1_test_exists` (file_contains) — pattern 'def test_positive_lift_candidate_beats_best_single_at_parity' found in tests/test_arena_v1.py
  - ✓ `dpi_test_exists` (file_exists) — tests/test_dpi.py present
  - ✓ `closure_checks_test_exists` (file_exists) — tests/test_coordination_closure_checks.py present
  - ✓ `arena_v1_controls_tests_pass` (test_passes) — pytest tests/test_arena_v1.py: PASS — 15 passed in 0.80s
  - ✓ `arena_truth_surface_tests_pass` (test_passes) — pytest tests/test_arena_truth_report.py: PASS — 8 passed in 6.20s
  - ✗ `arena_truth_receipt_valid` (receipt_valid) — receipt reports/governance/arena/arena_truth_receipt.json is stale: 23d old > fresh_ttl_days=21

## `merge-master-mike-d4-2026-06` — 7/7

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'repository-titanium-hardening-2026-07'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['scripts/runtime/pr_merge_control.py', 'scripts/runtime/merge_master_mike_daemon.py', '.github/workflows/automerge.yml', '.github/workflows/codex-mention-router.yml', '.github/workflows/merge-master-mike-backlog.yml', 'tests/test_merge_master_mike_daemon.py', 'tests/test_pr_merge_control.py', 'tests/test_pr_merge_control_github_reviews.py']
- moves_vital_signs: ['quality_gates', 'tool_coverage']
- claim_boundary: Native Codex/Copilot reviews are accepted only from trusted installed-App identities; unattended human-PR merge is authorized only after every existing deterministic gate is clean. Claude remains an optional deep/backup lane with no new credential. This policy and its hermetic behavior are landed; PRODUCTION_READY is not claimed until a live cloud canary and a ship_safe Final Boss manifest are attached. The current 7/7 criteria prove the landed D4 slice only; they do not cover Titanium WP-0F2 required-check authority convergence, so Mike remains active.
- ship_blocks: 1 open blocker next-item(s)

  - ✓ `pr_merge_control_exists` (file_exists) — scripts/runtime/pr_merge_control.py present
  - ✓ `mike_daemon_exists` (file_exists) — scripts/runtime/merge_master_mike_daemon.py present
  - ✓ `automerge_workflow_exists` (file_exists) — .github/workflows/automerge.yml present
  - ✓ `router_workflow_exists` (file_exists) — .github/workflows/codex-mention-router.yml present
  - ✓ `github_review_receipt_bridge` (file_contains) — pattern 'github_review' found in scripts/runtime/pr_merge_control.py
  - ✓ `github_review_bridge_tested` (file_exists) — tests/test_pr_merge_control_github_reviews.py present
  - ✓ `automerge_enrolls_all_nondraft` (file_contains) — pattern 'mike-watch' found in .github/workflows/automerge.yml
  - ✓ `mike_cloud_heartbeat` (file_contains) — pattern 'schedule:' found in .github/workflows/merge-master-mike-backlog.yml
  - ✓ `github_review_bridge_landed` (commit_on_main) — 751c5ba8a8 is an ancestor of origin/main
  - ✓ `github_review_bridge_test_passes` (test_passes) — pytest tests/test_pr_merge_control_github_reviews.py: PASS — 17 passed in 0.47s
  - ✓ `pr_merge_control_gate_fail_closed_test_passes` (test_passes) — pytest tests/test_pr_merge_control.py: PASS — 158 passed in 5.57s

## `organism-rewire-2026-07` — 2/2

- serves: `substrate-nativeness` · complements: ['runtime-truth-spine-adoption-2026-06', 'loop-closure-2026-06', 'orchestration-arena-v1-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['tools/world_scout_go/**', 'tools/world_signal_ingestor_go/**', 'tools/github_ingestor_go/**', 'tools/evidence_ingestor_go/**', 'dharma_swarm/world_radar/**', 'scripts/runtime/github_ingestor_runner.py', 'tests/test_github_ingestor_runner.py', 'tests/test_go_evidence_ingestor_bridge.py', 'tests/test_go_github_ingestor_bridge.py', 'tests/test_go_world_signal_bridge.py', 'tests/test_go_receipt_identity_verify.py', 'tests/test_go_adapter_contracts.py', 'tests/test_world_radar_go_bridge.py', 'dharma_swarm/organism.py', 'dharma_swarm/strange_loop.py', 'dharma_swarm/diversity_archive.py', 'dharma_swarm/archive.py', 'docker-compose.yml', 'Dockerfile.swarm', 'ACTIVE_SURFACE_MANIFEST.yaml', 'dharma_swarm/runtime_state.py', 'dharma_swarm/sarathi/**', 'tests/test_runtime_state.py', 'tests/test_sarathi_public_api.py', 'tests/test_sarathi_shell.py', 'tests/test_sarathi_import_boundaries.py', 'docs/README.md', 'docs/persistent_agents/**', 'reports/agentops/work_packets/organism-rewire-WP-SARATHIROOT-P0.json', 'dharma_swarm/mission_control.py', 'dharma_swarm/mission_control_contract.py', 'dharma_swarm/mission_control_execution.py', 'dharma_swarm/mission_control_execution_support.py', 'dharma_swarm/mission_control_lifecycle.py', 'dharma_swarm/mission_control_mcp.py', 'dharma_swarm/mission_control_mcp_mutations.py', 'dharma_swarm/mission_control_projection.py', 'dharma_swarm/mission_control_reconciliation.py', 'dharma_swarm/mission_control_recovery.py', 'dharma_swarm/mission_control_dispatch.py', 'dharma_swarm/mission_control_a2a.py', 'dharma_swarm/mission_control_sarathi.py', 'tests/test_mission_control.py', 'tests/test_mission_control_execution.py', 'tests/test_mission_control_mcp.py', 'tests/test_mission_control_dispatch.py', 'tests/test_mission_control_a2a.py', 'tests/test_mission_control_sarathi.py', 'api/routers/control_surface.py', 'tests/test_control_surface.py', 'tests/test_control_surface_router_threadpool.py', 'tests/test_control_surface_mission_sarathi.py', 'dashboard/src/app/dashboard/control-surface/page.tsx', 'dashboard/src/hooks/useMissionSarathi.ts', 'dashboard/src/components/cockpit/MissionSarathiStrip.tsx', 'dharma_swarm/operator_brief/mission_control_citations.py', 'tests/test_operator_brief_mission_control_citations.py', 'reports/agentops/work_packets/organism-rewire-WP-MISSIONCONTROL-P2-ADMISSION.json', 'dharma_swarm/foundry/**', 'tests/test_foundry_*.py', 'scripts/foundry/**', '.github/workflows/foundry-lane.yml', 'docs/foundry/**', 'docs/offers/agent-behavior-verification.md', 'reports/foundry/**']
- moves_vital_signs: ['quality_gates', 'eval_coverage']
- ship_blocks: 6 open blocker next-item(s)

  - ✓ `rewire_done_slices_landed` (commit_on_main) — 4c4f5aa47c is an ancestor of origin/main
  - ✓ `go_sense_organ_toolchain_closure_tests_pass` (test_passes) — pytest tests/test_world_radar_go_bridge.py: PASS — 20 passed in 0.58s

## `dharmagraph-engine-2026-07` — 8/10

- serves: `substrate-nativeness` · complements: ['loop-closure-2026-06', 'orchestration-arena-v1-2026-06', 'organism-rewire-2026-07'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/graph/**', 'dharma_swarm/workflow.py', 'dharma_swarm/topology_genome.py', 'dharma_swarm/checkpoint.py', 'dharma_swarm/swarm.py', 'dharma_swarm/orchestrator.py', 'pyproject.toml', '.github/workflows/langgraph-oracle.yml', 'tests/test_workflow.py', 'tests/test_topology_execution.py', 'tests/test_checkpoint.py', 'tests/test_graph_checkpoint.py', 'tests/test_graph_reconciler.py', 'tests/test_graph_durable_invoker.py', 'tests/test_langgraph_differential_oracle.py', 'tests/test_graph_neutral_langgraph_oracle.py', 'tests/test_graph_pregel_properties.py', 'docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md', 'docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md', 'docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md', 'scripts/governance/dharmagraph_parity_gauntlet.py', 'tests/oracle_support/dharmagraph_gauntlet.py', 'tests/test_dharmagraph_parity_gauntlet.py', 'docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json', 'docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json', 'docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V3.json', 'docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json', 'reports/governance/dharmagraph_parity/**', 'docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md', 'docs/plans/handoffs/DHARMAGRAPH_ASCENT_*.md', 'docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_*.md', 'docs/governance/CAMPAIGN_KERNEL.md', 'tests/oracle_support/scenarios.py', 'tests/oracle_support/outcomes.py']
- moves_vital_signs: ['quality_gates', 'eval_coverage']
- claim_boundary: Phases 0a-3 consolidate the engine federation onto one durable graph runtime. No production capability claim before the differential oracle is in CI; no topology-evolution unlock (Phase 6 wall stays operator-gated per organism-rewire D4).
- ship_blocks: 1 open blocker next-item(s); outcome receipt reports/governance/dharmagraph_parity/builder_receipt.json reports verdict='NOT_FINISHED', score={'display': '58.00/100', 'earned': '58.00', 'possible': '100.00'} — not a passing verdict; the track's own scoreboard does not say the work is done; outcome receipt reports/governance/dharmagraph_parity/judge_receipt.json reports verdict='NOT_FINISHED', score={'display': '58.00/100', 'earned': '58.00', 'possible': '100.00'} — not a passing verdict; the track's own scoreboard does not say the work is done

  - ✓ `dharmagraph_spec_exists` (file_exists) — docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md present
  - ✓ `spine_invoke_seam_exists` (file_exists) — dharma_swarm/spine/invoke.py present
  - ✓ `handoff_briefs_exist` (file_exists) — docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md present
  - ✓ `phase0a_dead_engines_deleted` (command_passes) — bash -c test ! -f dharma_swarm/workflow_graph.py && test ! -f dharma_swarm/durable_execution.py && ! grep -rE 'import (workflow_graph|durable_execution)|from dharma_swarm(\.| import )(workflow_graph|durable_execution)' dharma_swarm/ tests/ --include='*.py' -q exited 0
  - ✓ `phase0b_reconciler_tests_pass` (test_passes) — pytest tests/test_graph_reconciler.py: PASS — 28 passed in 1.36s
  - ✓ `phase0b_durable_invoker_tests_pass` (test_passes) — pytest tests/test_graph_durable_invoker.py: PASS — 22 passed in 2.56s
  - ✗ `phase1_oracle_tests_pass` (test_passes) — pytest tests/test_langgraph_differential_oracle.py: FAIL — 1 skipped in 0.10s
  - ✓ `phase0b_chaos_receipt` (test_passes) — pytest tests/test_graph_chaos_receipt.py: PASS — 3 passed in 1.56s
  - ✓ `spec_kill_criteria_stated` (file_contains) — pattern 'Kill criterion' found in docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md
  - ✓ `parity_builder_receipt_valid` (receipt_valid) — receipt reports/governance/dharmagraph_parity/builder_receipt.json valid (8 keys present, digest intact)
  - ✓ `parity_judge_receipt_valid` (receipt_valid) — receipt reports/governance/dharmagraph_parity/judge_receipt.json valid (3 keys present, digest intact)
  - ✗ `parity_gauntlet_check_passes` (command_passes) — bash scripts/governance/run_python_with_repo_env.sh scripts/governance/dharmagraph_parity_gauntlet.py --check exited 2; output: {"check": "FAIL", "error": "comparison environment mismatch for langgraph_version: installed='NOT_INSTALLED' expected='1.2.4'"}

## `helm-worldclass-terminal-2026-06` — 2/4

- serves: `substrate-nativeness` · complements: ['merge-master-mike-d4-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['terminal/**']
- moves_vital_signs: ['tool_coverage', 'context_efficiency']
- ship_blocks: 1 open blocker next-item(s)

  - ✗ `terminal_tui_test_suite_passes` (command_passes) — bash -c cd terminal && bun install --frozen-lockfile && bun test exited 127; output: bash: line 1: bun: command not found
  - ✗ `terminal_app_test_passes` (command_passes) — bash -c cd terminal && bun install --frozen-lockfile && bun test tests/app.test.ts exited 127; output: bash: line 1: bun: command not found
  - ✓ `app_test_exists` (file_exists) — terminal/tests/app.test.ts present
  - ✓ `terminal_behavioral_suite_landed` (commit_on_main) — 1d8dae2943 is an ancestor of origin/main

## `sovereign-safety-tcb-2026-07` — 4/4

- serves: `substrate-nativeness` · complements: ['loop-closure-2026-06', 'merge-master-mike-d4-2026-06', 'organism-rewire-2026-07'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/evolution_safety.py', 'scripts/governance/check_claim_evidence_binding.py', 'scripts/governance/pramana_probe.py', 'scripts/governance/branch_janitor.py', 'scripts/governance/verify_corral_findings.py', 'scripts/governance/hygiene/**', 'docs/governance/hygiene/patterns/AI-M1.yaml', 'packages/telos-kernel/**', 'packages/titanium-verify/**', '.github/workflows/pudgala-rigor.yml', '.github/workflows/pramana-probe.yml', '.github/workflows/kernel-titanium-verify.yml', '.github/workflows/kernel-tests.yml', '.github/workflows/branch-janitor.yml', 'tests/test_evolution_safety.py', 'tests/test_claim_evidence_binding.py', 'tests/test_pramana_probe.py', 'tests/test_pramana.py', 'tests/test_branch_janitor.py', 'tests/test_verify_corral_findings.py']
- moves_vital_signs: ['quality_gates', 'security_guardrails']
- claim_boundary: The gate MACHINERY is landed and CI-enforced (each completion criterion
is independently re-run by a pull_request-triggered GitHub Actions
workflow the PR author cannot forge). Two ratchets remain deliberately
un-flipped and are NOT claimed closed: (a) the AI-M1 hygiene pattern is
stage=advisory (docs/governance/hygiene/patterns/AI-M1.yaml) so the
graded-binding gate reports but does not yet block merges; (b) the
PR-001 fail-closed evolution guarantee is proven at unit level, but the
live-host observation (DHARMA_EVOLUTION_SHADOW default + read-only
source mount denying live-checkout mutation on the daemon host) is an
operator observation still owned by organism-rewire D4. Completion
criteria prove the gates are green + wired, not that every ratchet is at
its blocking terminal stage.

- ship_blocks: 1 open blocker next-item(s)

  - ✓ `evolution_safety_module_exists` (file_exists) — dharma_swarm/evolution_safety.py present
  - ✓ `track_status_checker_exists` (file_exists) — scripts/governance/check_track_status.py present
  - ✓ `ai_m1_binding_pattern_exists` (file_exists) — docs/governance/hygiene/patterns/AI-M1.yaml present
  - ✓ `telos_kernel_pkg_exists` (file_exists) — packages/telos-kernel/telos_kernel/__init__.py present
  - ✓ `titanium_verify_pkg_exists` (file_exists) — packages/titanium-verify/titanium_verify/cli.py present
  - ✓ `evolution_fail_closed_tests_pass` (test_passes) — pytest tests/test_evolution_safety.py: PASS — 29 passed in 0.51s
  - ✓ `pudgala_ai_m1_binding_tests_pass` (test_passes) — pytest tests/test_claim_evidence_binding.py: PASS — 57 passed in 1.46s
  - ✓ `pramana_phantom_gate_tests_pass` (test_passes) — pytest tests/test_pramana_probe.py: PASS — 16 passed in 0.48s
  - ✓ `telos_kernel_tcb_tests_pass` (test_passes) — pytest packages/telos-kernel/telos_kernel/tests/: PASS — 180 passed, 3 skipped in 2.64s

## `hyperbolic-time-chamber-2026-07` — 10/11

- serves: `research-depth` · complements: ['organism-rewire-2026-07', 'orchestration-arena-v1-2026-06', 'loop-closure-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md', 'docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md', 'docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md', 'docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md', 'scripts/governance/inward_ascent_baseline.py', 'scripts/governance/frontier_ledger.py', 'scripts/governance/transcendence_ledger.py', 'dharma_swarm/chamber/**', 'tests/test_chamber_traces.py', 'tests/test_chamber_gym_git_history.py', 'tests/test_chamber_daily_delta.py', 'tests/test_chamber_predictions.py', 'tests/test_chamber_sandbox.py', 'tests/test_chamber_ledger_history.py', 'tests/test_transcendence_ledger.py', 'reports/governance/inward_ascent/**', 'reports/governance/chamber/**']
- moves_vital_signs: ['eval_coverage', 'quality_gates']
- claim_boundary: Phase 0 proved the dossier + two replayable instruments; Phase 1 Slice A proves a HARNESS-level G1 gym (fixture solver, deterministic scorer, leak guard) plus the E1/E3/E4/E5/E6 wiring. Gym results are internal-gym numbers, never benchmark or capability claims; C2 stays owned by the RSI/arena lab; live solver evolution waits on operator keys/compute. Archive fitness remains behind the One Wire external quorum.
- ship_blocks: 1 open blocker next-item(s)

  - ✓ `chamber_doctrine_exists` (file_exists) — docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md present
  - ✓ `phase0_dossier_exists` (file_exists) — docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md present
  - ✓ `phase0_firewall_stated` (file_contains) — pattern 'archive fitness for self-modification still requires the One Wire external quorum' found in docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md
  - ✓ `baseline_receipt_valid` (receipt_valid) — receipt reports/governance/inward_ascent/baseline_receipt.json valid (4 keys present, digest intact)
  - ✗ `frontier_ledger_receipt_valid` (receipt_valid) — receipt reports/governance/chamber/frontier_ledger_receipt.json is stale: 43d old > fresh_ttl_days=30
  - ✓ `frontier_ledger_replays` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 scripts/governance/frontier_ledger.py --check exited 0 (resolved from python3 scripts/governance/frontier_ledger.py --check); output: frontier_ledger --check: OK — seal intact, inputs pinned, page renders purely, history+velocity replay, door fresh.
  - ✓ `chamber_traces_tests_pass` (test_passes) — pytest tests/test_chamber_traces.py: PASS — 6 passed in 0.41s
  - ✓ `chamber_g1_run_receipt_valid` (receipt_valid) — receipt reports/governance/chamber/g1_run_receipt.json valid (5 keys present, digest intact)
  - ✓ `chamber_daily_delta_tests_pass` (test_passes) — pytest tests/test_chamber_daily_delta.py: PASS — 10 passed in 0.44s
  - ✓ `chamber_predictions_tests_pass` (test_passes) — pytest tests/test_chamber_predictions.py: PASS — 10 passed in 0.42s
  - ✓ `transcendence_ledger_tests_pass` (test_passes) — pytest tests/test_transcendence_ledger.py: PASS — 7 passed in 0.42s
  - ✓ `transcendence_receipt_valid` (receipt_valid) — receipt reports/governance/chamber/transcendence_receipt.json valid (3 keys present, digest intact)
  - ✓ `transcendence_ledger_replays` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 scripts/governance/transcendence_ledger.py --check exited 0 (resolved from python3 scripts/governance/transcendence_ledger.py --check); output: transcendence_ledger --check: OK — decomposition replays from the pinned corpus.

## `repository-titanium-hardening-2026-07` — 8/9

- serves: `substrate-nativeness` · complements: ['merge-master-mike-d4-2026-06', 'sovereign-safety-tcb-2026-07', 'dharmagraph-engine-2026-07', 'organism-rewire-2026-07', 'helm-worldclass-terminal-2026-06', 'loop-closure-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['Makefile', 'Dockerfile', '.github/workflows/hermetic.yml', '.github/workflows/tests.yml', '.github/workflows/ci-parity.yml', '.github/workflows/docops.yml', '.github/workflows/docops-reconcile-main.yml', '.github/workflows/pr-dedupe.yml', '.github/workflows/bot-pr-limit.yml', '.github/workflows/a2a-agni-live-contact.yml', 'docs/governance/CI_TRUTH_CONTRACT.json', 'scripts/governance/ci_parity_manifest.json', 'scripts/governance/check_ci_parity.py', 'scripts/runtime/ci_truth.py', 'scripts/governance/run_semgrep_with_ca.sh', 'scripts/uplift_guards/shakti_warrant_guard.py', 'scripts/uplift_guards/run_pre_commit.py', 'scripts/governance/check_shakti_warrant.py', 'scripts/governance/check_nats_substrate_contract.py', 'scripts/governance/check_nats_live_production_evidence.py', 'scripts/governance/run_nats_live_production_matrix.py', 'scripts/docops/**', 'dharma_swarm/build_engine.py', 'dharma_swarm/autonomous_agent.py', 'dharma_swarm/diff_applier.py', 'dharma_swarm/sandbox.py', 'dharma_swarm/docker_sandbox.py', 'docs/docops/AUTO_INVENTORY.md', 'api/main.py', 'tests/test_api_auth.py', 'tests/test_verify_api.py', 'tests/test_bootstrap_contract.py', 'tests/test_verifier_selfcheck_contract.py', 'tests/test_semgrep_wrapper.py', 'tests/test_uplift_guard_subprocess.py', 'tests/test_fast_suite_isolation.py', 'tests/test_agent_work_packet.py', 'tests/test_make_onboarding_contract.py', 'tests/test_diff_applier.py', 'tests/test_sandbox.py', 'tests/test_docker_sandbox.py', 'tests/test_nats_verification_split.py', 'tests/test_nats_substrate_contract.py', 'tests/test_nats_live_production_evidence.py', 'tests/test_nats_live_contact.py', 'tests/governance/test_ci_parity_guard.py', 'tests/test_ci_truth.py', 'tests/test_docops_integrity.py', 'tests/test_docops_reconcile_workflow.py', 'tests/test_pr_dedupe_workflow.py', 'tests/test_polyglot_ci_contract.py', 'tests/test_hermetic_supply_chain.py', 'docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md', 'docs/prompts/TITANIUM_HARDENING_CAMPAIGN_EXECUTOR_2026-07-17.md', 'reports/governance/titanium/**', 'dashboard/src/lib/operatorCoherence.ts', 'dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts', 'dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx', 'dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts']
- moves_vital_signs: ['quality_gates', 'eval_coverage', 'security_guardrails', 'tool_coverage']
- claim_boundary: WP-00 admits the bounded Phase 0 ownership and execution graph from the integrated Titanium specification. Passing criteria may establish only truthful repository verification and an independent clean-room CLOSED_NOT_PROD result. They do not prove production liveness, complete security, deployment readiness, Phase 1-7 completion, or authority over Mike, Go, terminal, graph, organism, Safety TCB, or Loop Closure surfaces. Adding Docker-sandbox ownership and WP-DSI admits only a later bounded implementation review. It is not implementation evidence, container-start proof, generated-code isolation, or authority to re-arm evolution.
- ship_blocks: 5 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S0_EXISTS < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification)

  - ✓ `titanium_bootstrap_contract_passes` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_bootstrap_contract.py -q exited 0 (resolved from python3 -m pytest tests/test_bootstrap_contract.py -q); output: .........                                                                [100%] | 9 passed in 0.42s
  - ✓ `titanium_verifier_truth_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_verifier_selfcheck_contract.py -q exited 0 (resolved from python3 -m pytest tests/test_verifier_selfcheck_contract.py -q); output: ..........                                                               [100%] | 10 passed in 60.16s (0:01:00)
  - ✓ `titanium_verifier_support_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_fast_suite_isolation.py tests/test_semgrep_wrapper.py tests/test_uplift_guard_subprocess.py -q exited 0 (resolved from python3 -m pytest tests/test_fast_suite_isolation.py tests/test_semgrep_wrapper.py tests/test_uplift_guard_subprocess.py -q); output: ...............................s...............                          [100%] | 46 passed, 1 skipped in 5.58s
  - ✓ `titanium_ingress_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_api_auth.py tests/test_verify_api.py -q exited 0 (resolved from python3 -m pytest tests/test_api_auth.py tests/test_verify_api.py -q); output: .................................................................        [100%] | 65 passed in 10.03s
  - ✓ `titanium_hermetic_live_split_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_nats_verification_split.py tests/test_nats_substrate_contract.py tests/test_nats_live_production_evidence.py -q exited 0 (resolved from python3 -m pytest tests/test_nats_verification_split.py tests/test_nats_substrate_contract.py tests/test_nats_live_production_evidence.py -q); output: ....................................                                     [100%] | 36 passed in 1.03s
  - ✓ `titanium_ci_authority_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/governance/test_ci_parity_guard.py tests/test_ci_truth.py -q exited 0 (resolved from python3 -m pytest tests/governance/test_ci_parity_guard.py tests/test_ci_truth.py -q); output: .............................                                            [100%] | 29 passed in 0.97s
  - ✓ `titanium_docops_contracts_pass` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_docops_integrity.py tests/test_docops_reconcile_workflow.py tests/test_pr_dedupe_workflow.py -q exited 0 (resolved from python3 -m pytest tests/test_docops_integrity.py tests/test_docops_reconcile_workflow.py tests/test_pr_dedupe_workflow.py -q); output: .........................................                                [100%] | 41 passed in 5.24s
  - ✓ `titanium_polyglot_contract_passes` (command_passes) — /opt/hostedtoolcache/Python/3.11.16/x64/bin/python3 -m pytest tests/test_polyglot_ci_contract.py tests/test_hermetic_supply_chain.py -q exited 0 (resolved from python3 -m pytest tests/test_polyglot_ci_contract.py tests/test_hermetic_supply_chain.py -q); output: ......................s.......                                           [100%] | 29 passed, 1 skipped in 14.63s
  - ✗ `titanium_independent_clean_room_receipt_valid` (receipt_valid) — receipt reports/governance/titanium/phase0_clean_room_receipt.json MISSING

## `darshan-publication-2026-07` — 1/2

- serves: `revenue-external-humans-served` · complements: ['company-builder-parity-2026-07'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/plans/DARSHAN_CHARTER_2026-07-12.md', 'reports/darshan/**', 'reports/tam/**']
- moves_vital_signs: ['eval_coverage']
- claim_boundary: Admitted by operator DECREE (GOLDEN SEAL, 2026-07-12 00:36 JST; canonical text at ~/.dharma/agents/darshan_fable/DECREE_GOLDEN_SEAL.md). Criteria prove the publication organ exists and its output is receipted — never audience, revenue, or influence claims (those are TAM-board readings, measured not narrated). Posting to third-party platforms (Medium, Substack, Reddit, etc.) stays operator-gated per platform regardless of criteria state. The Darshan-owned site itself may publish pieces that have passed the editorial law (both-fires + discernment + operator read).
- ship_blocks: 2 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S1_PRESENT < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification)

  - ✓ `darshan_charter_exists` (file_contains) — pattern 'editorial law' found in docs/plans/DARSHAN_CHARTER_2026-07-12.md
  - ✗ `darshan_issue_one_receipt_valid` (receipt_valid) — receipt reports/darshan/issue_one_receipt.json MISSING

## Findings

- **WARN** `wip-high`: 10 ACTIVE tracks exceed warn_active=8 — focus is spreading thin.
- **WARN** `track-stale:loop-closure-2026-06`: [loop-closure-2026-06] verified_at is 39 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-provisional:loop-closure-2026-06`: [loop-closure-2026-06] 32/32 criteria pass but NOT shippable under the rigorous bar: 3 open blocker next-item(s); 1 active ship veto(es): cybernetics_codex_harness_proven_blocks_live_ship: reports/loop_closure/cybernetics_codex/latest_audit.json.loop_statuses[].verdict == 'HARNESS_PROVEN': 11 > 0; outcome receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json reports verdict='BLOCKED' — not a passing verdict; the track's own scoreboard does not say the work is done. Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **WARN** `track-stale:orchestration-arena-v1-2026-06`: [orchestration-arena-v1-2026-06] verified_at is 33 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:orchestration-arena-v1-2026-06`: [orchestration-arena-v1-2026-06] 11/12 completion criteria pass.
- **WARN** `track-stale:merge-master-mike-d4-2026-06`: [merge-master-mike-d4-2026-06] verified_at is 34 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-provisional:merge-master-mike-d4-2026-06`: [merge-master-mike-d4-2026-06] 7/7 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s). Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **INFO** `track-provisional:organism-rewire-2026-07`: [organism-rewire-2026-07] 2/2 criteria pass but NOT shippable under the rigorous bar: 6 open blocker next-item(s). Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **INFO** `track-in-progress:dharmagraph-engine-2026-07`: [dharmagraph-engine-2026-07] 8/10 completion criteria pass.
- **WARN** `track-stale:helm-worldclass-terminal-2026-06`: [helm-worldclass-terminal-2026-06] verified_at is 43 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:helm-worldclass-terminal-2026-06`: [helm-worldclass-terminal-2026-06] 2/4 completion criteria pass.
- **WARN** `track-stale:sovereign-safety-tcb-2026-07`: [sovereign-safety-tcb-2026-07] verified_at is 43 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-provisional:sovereign-safety-tcb-2026-07`: [sovereign-safety-tcb-2026-07] 4/4 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s). Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **WARN** `track-stale:hyperbolic-time-chamber-2026-07`: [hyperbolic-time-chamber-2026-07] verified_at is 43 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:hyperbolic-time-chamber-2026-07`: [hyperbolic-time-chamber-2026-07] 10/11 completion criteria pass.
- **WARN** `track-underclaim:repository-titanium-hardening-2026-07:WP-0F1`: [repository-titanium-hardening-2026-07] blocker next-item WP-0F1 is still listed as open work but its linked evidence criterion 'titanium_ci_authority_contracts_pass' PASSES — the ledger may be behind reality. Reconcile: annotate the item DONE, narrow it to the remaining live edge, or strengthen the criterion.
- **WARN** `track-underclaim:repository-titanium-hardening-2026-07:WP-0G`: [repository-titanium-hardening-2026-07] blocker next-item WP-0G is still listed as open work but its linked evidence criterion 'titanium_docops_contracts_pass' PASSES — the ledger may be behind reality. Reconcile: annotate the item DONE, narrow it to the remaining live edge, or strengthen the criterion.
- **WARN** `track-underclaim:repository-titanium-hardening-2026-07:WP-0S`: [repository-titanium-hardening-2026-07] blocker next-item WP-0S is still listed as open work but its linked evidence criterion 'titanium_ingress_contracts_pass' PASSES — the ledger may be behind reality. Reconcile: annotate the item DONE, narrow it to the remaining live edge, or strengthen the criterion.
- **INFO** `track-in-progress:repository-titanium-hardening-2026-07`: [repository-titanium-hardening-2026-07] 8/9 completion criteria pass.
- **WARN** `track-stale:darshan-publication-2026-07`: [darshan-publication-2026-07] verified_at is 38 days old (ttl_days=30). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:darshan-publication-2026-07`: [darshan-publication-2026-07] 1/2 completion criteria pass.
