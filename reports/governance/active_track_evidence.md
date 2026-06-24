# Track Portfolio Evidence

Generated: 2026-06-24T09:04:03+00:00 (schema v2)
Active tracks: **9** (warn 5, max 10) — shippable 5

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✗ (no active track)
- `research-depth` — ✗ (no active track)

## `runtime-truth-reconciliation-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-nats-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/operator_core/**', 'scripts/governance/agent_onboard.py', 'dharma_swarm/runtime_state.py']
- moves_vital_signs: ['quality_gates', 'memory_persistence']

  - ✓ `runtime_spine_package_exists` (file_exists) — dharma_swarm/spine/__init__.py present
  - ✓ `receipt_equivalence_matrix_exists` (file_exists) — docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md present
  - ✓ `a2a_persistence_invariant_tests_exist` (file_exists) — tests/test_spine_persistence_invariant.py present
  - ✓ `runtime_truth_packet_defined` (file_contains) — pattern 'class RuntimeTruthPacket' found in dharma_swarm/operator_core/contracts.py
  - ✓ `runtime_truth_axes_defined` (file_contains) — pattern 'class RuntimeTruthState' found in dharma_swarm/operator_core/contracts.py
  - ✓ `onboard_runtime_truth_render` (file_contains) — pattern 'render_runtime_truth' found in scripts/governance/agent_onboard.py
  - ✓ `onboard_runtime_truth_no_write_test` (file_contains) — pattern 'test_runtime_truth_render_is_read_only' found in tests/test_agent_onboard.py
  - ✓ `runtime_truth_packet_axis_test` (file_contains) — pattern 'test_runtime_truth_packet_keeps_state_axes_separate' found in tests/test_operator_core_contracts.py
  - ✓ `a2a_single_persistence_invariant` (file_contains) — pattern 'test_submit_via_spine_retry_does_not_create_second_runtime_receipt' found in tests/test_spine_persistence_invariant.py
  - ✓ `spine_bypass_report_exists` (file_exists) — scripts/governance/spine_bypass_report.py present
  - ✓ `receipt_json_projection_only_doc` (file_contains) — pattern 'projection/cache only' found in docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md
  - ✓ `correlation_spine_manifest_still_declared` (file_contains) — pattern 'correlation_spine:' found in ACTIVE_SURFACE_MANIFEST.yaml
  - ✓ `evidence_receipt_still_defined` (file_contains) — pattern 'class EvidenceReceipt' found in dharma_swarm/spine/receipt.py
  - ✓ `runtime_receipt_still_defined` (file_contains) — pattern 'class RuntimeReceipt' found in dharma_swarm/runtime_state.py
  - ✓ `operator_core_contracts_pass` (test_passes) — pytest tests/test_operator_core_contracts.py: PASS — 7 passed in 0.79s

## `runtime-truth-nats-2026-06` — 2/2

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md', 'dharma_swarm/a2a/a2a_nats_contact.py', 'dharma_swarm/a2a/a2a_core_contact.py']
- moves_vital_signs: ['tool_coverage']

  - ✓ `nats_master_spec_exists` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `nats_master_spec_present` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `nats_transport_landed` (file_contains) — pattern 'NATS' found in docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md

## `runtime-truth-spine-adoption-2026-06` — 7/8

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'runtime-truth-nats-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/spine/**', 'dharma_swarm/a2a/a2a_bridge.py', 'dharma_swarm/orchestrator.py', 'dharma_swarm/agent_runner.py', 'scripts/uplift_guards/check_spine_ownership.py']
- moves_vital_signs: ['quality_gates', 'tool_coverage']

  - ✓ `spine_package_exists` (file_exists) — dharma_swarm/spine/__init__.py present
  - ✓ `invoke_agent_defined` (file_contains) — pattern 'async def invoke_agent' found in dharma_swarm/spine/invoke.py
  - ✓ `a2a_bridge_calls_spine` (file_contains) — pattern '(?m)^\\s*from dharma_swarm\\.spine' found in dharma_swarm/a2a/a2a_bridge.py
  - ✓ `orchestrator_calls_spine` (file_contains) — pattern '(?m)^\\s*from dharma_swarm\\.spine' found in dharma_swarm/orchestrator.py
  - ✓ `agent_runner_calls_spine` (file_contains) — pattern '(?m)^\\s*from dharma_swarm\\.spine' found in dharma_swarm/agent_runner.py
  - ✓ `dispatch_emits_evidence_receipt` (file_contains) — pattern 'test_every_dispatch_emits_exactly_one_evidence_receipt' found in tests/test_spine_adoption_dispatch.py
  - ✓ `zero_dropoff_sources` (file_contains) — pattern 'test_no_dropoff_sources_remain' found in tests/test_spine_adoption_dispatch.py
  - ✗ `bypass_allowlist_empty` (file_contains) — pattern '(?m)^_INTENTIONAL_BYPASS: dict\\[tuple\\[str, int\\], str\\] = \\{\\s*\\}' NOT FOUND in scripts/governance/spine_bypass_report.py
  - ✓ `adoption_narrative_docs` (file_exists) — docs/architecture/SPINE_ADOPTION_NARRATIVE.md present
  - ✓ `gate1_witnessed` (file_exists) — reports/governance/GATE1_WITNESSED.md present

## `loop-closure-2026-06` — 10/11

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['reports/loop_closure/**', 'CYBERNETIC_LOOP_MAP.md']
- moves_vital_signs: ['quality_gates', 'eval_coverage']

  - ✓ `loop_map_exists` (file_exists) — CYBERNETIC_LOOP_MAP.md present
  - ✓ `loop_supervisor_exists` (file_exists) — dharma_swarm/loop_supervisor.py present
  - ✓ `phase0_dossier_exists` (file_exists) — reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md present
  - ✓ `phase0_fresh_status_table` (file_contains) — pattern 'Fresh 13-loop status table' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `one_wire_invariant_stated` (file_contains) — pattern 'never let internal artifacts touch archive fitness' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `loop1_closure_receipt_exists` (file_exists) — reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md present
  - ✗ `campaign_retrospective_exists` (file_exists) — reports/loop_closure/RETROSPECTIVE.md MISSING
  - ✓ `cybernetics_codex_manifest_registered` (file_contains) — pattern 'id: cybernetics_codex' found in ACTIVE_SURFACE_MANIFEST.yaml
  - ✓ `cybernetics_codex_seed_exists` (file_exists) — docs/agents/cybernetics_codex/agent.seed.yaml present
  - ✓ `cybernetics_codex_soul_exists` (file_exists) — docs/agents/cybernetics_codex/SOUL.md present
  - ✓ `cybernetics_codex_context_desk_exists` (file_exists) — docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md present
  - ✓ `cybernetics_codex_audit_script_exists` (file_exists) — scripts/governance/cybernetics_codex_audit.py present
  - ✓ `cybernetics_codex_registration_script_exists` (file_exists) — scripts/governance/register_cybernetics_codex.py present

## `truth-graph-platform-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'runtime-truth-nats-2026-06'] · depends_on: ['orientation-graph-2026-06'] · conflicts_with: []
- owned_surfaces: ['scripts/governance/orientation_graph.py', 'scripts/governance/truth_graph_nats_e2e_demo.py', 'scripts/governance/run_truth_graph_nats_e2e_demo.sh', 'tests/test_orientation_graph.py', 'tests/test_truth_graph_repo_context.py', 'dharma_swarm/a2a/task_receipt.py', 'dharma_swarm/a2a/agent_presence.py', 'tests/test_a2a_gate.py', 'tests/test_agent_registry_presence.py', 'reports/orientation/**']
- moves_vital_signs: ['quality_gates', 'tool_coverage', 'memory_persistence']

  - ✓ `identity_owner_on_branch` (file_exists) — foundations/THE_ORGANISM.md present
  - ✓ `vision_owner_on_branch` (file_exists) — docs/vision_maps/NORTH_STAR.md present
  - ✓ `orientation_graph_owner_exists` (file_exists) — scripts/governance/orientation_graph.py present
  - ✓ `expanded_orientation_packet_defined` (file_contains) — pattern 'class OrientationPacket' found in scripts/governance/orientation_graph.py
  - ✓ `repo_context_writer_defined` (file_contains) — pattern 'def write_repo_context' found in scripts/governance/orientation_graph.py
  - ✓ `repo_context_hash_defined` (file_contains) — pattern 'context_hash' found in scripts/governance/orientation_graph.py
  - ✓ `make_orient_writes_context` (file_contains) — pattern '--write-context' found in Makefile
  - ✓ `orientation_default_read_only_test` (file_contains) — pattern 'test_orientation_graph_render_is_read_only' found in tests/test_orientation_graph.py
  - ✓ `repo_context_test_exists` (file_contains) — pattern 'test_truth_graph_repo_context_writes_json_and_markdown' found in tests/test_truth_graph_repo_context.py
  - ✓ `a2a_receipt_gate_exists` (file_exists) — dharma_swarm/a2a/task_receipt.py present
  - ✓ `a2a_receipt_schema_declared` (file_contains) — pattern 'dharma_a2a_task_receipt.v1' found in dharma_swarm/a2a/task_receipt.py
  - ✓ `a2a_receipted_inbox_reader_defined` (file_contains) — pattern 'def read_receipted_inbox' found in dharma_swarm/a2a/task_receipt.py
  - ✓ `agent_presence_projection_exists` (file_exists) — dharma_swarm/a2a/agent_presence.py present
  - ✓ `agent_presence_stale_red` (file_contains) — pattern 'age > 2' found in dharma_swarm/a2a/agent_presence.py
  - ✓ `nats_e2e_demo_exists` (file_exists) — scripts/governance/truth_graph_nats_e2e_demo.py present
  - ✓ `nats_e2e_shell_wrapper_exists` (file_exists) — scripts/governance/run_truth_graph_nats_e2e_demo.sh present
  - ✓ `a2a_gate_tests_exist` (file_contains) — pattern "receipt or it didn't happen" found in tests/test_a2a_gate.py
  - ✓ `registry_presence_tests_exist` (file_contains) — pattern 'heartbeat_status' found in tests/test_agent_registry_presence.py
  - ✓ `repo_context_projection_passes` (test_passes) — pytest tests/test_truth_graph_repo_context.py: PASS — 1 passed in 0.45s
  - ✓ `truth_graph_projection_on_main` (commit_on_main) — 936d365db is an ancestor of origin/main

## `composer-holon-spine-longrun-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'runtime-truth-nats-2026-06'] · depends_on: ['runtime-truth-spine-adoption-2026-06'] · conflicts_with: []
- owned_surfaces: ['docs/sovereign_holons/**', 'reports/sovereign_holons/**', 'dharma_swarm/holon_*.py', 'scripts/holon_*.py', 'tests/test_holon_*.py']
- moves_vital_signs: ['quality_gates', 'tool_coverage', 'memory_persistence']

  - ✓ `evidence_receipt_exists` (file_contains) — pattern 'class EvidenceReceipt' found in dharma_swarm/spine/receipt.py
  - ✓ `holon_orchestrator_spec_exists` (file_exists) — docs/sovereign_holons/HOLON_ORCHESTRATOR_BUILD_SPEC.md present
  - ✓ `holon_runtime_exists` (file_exists) — dharma_swarm/holon_runtime.py present
  - ✓ `readiness_packet_exists` (file_exists) — reports/sovereign_holons/BUILD_A_90_READINESS_PACKET.md present
  - ✓ `receipt_profile_documented` (file_contains) — pattern 'The command receipt is a profile of `dharma_swarm.spine.receipt.EvidenceReceipt`' found in reports/sovereign_holons/BUILD_A_90_READINESS_PACKET.md
  - ✓ `frozen_verifier_runbook_present` (file_contains) — pattern 'Frozen Non-Implementer Verifier Runbook' found in reports/sovereign_holons/BUILD_A_90_READINESS_PACKET.md
  - ✓ `holon_bridge_verifier_exists` (file_exists) — tests/test_holon_bridge.py present
  - ✓ `holon_runtime_verifier_exists` (file_exists) — tests/test_holon_runtime.py present
  - ✓ `composer_wake_witness_pending` (file_exists) — reports/sovereign_holons/COMPOSER_WAKE_WITNESSED.md present
  - ✓ `holon_bridge_verifier_passes` (test_passes) — pytest tests/test_holon_bridge.py: PASS — 15 passed, 1 skipped in 0.32s
  - ✓ `holon_substrate_on_main` (commit_on_main) — 9c76b210 is an ancestor of origin/main

## `provider-routing-consolidation-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-spine-adoption-2026-06', 'loop-closure-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/providers.py', 'dharma_swarm/provider_policy.py', 'dharma_swarm/model_hierarchy.py', 'dharma_swarm/model_pool.py', 'dharma_swarm/model_defaults.py', 'dharma_swarm/runtime_provider.py', 'dharma_swarm/router_v1.py', 'dharma_swarm/smart_router.py', 'dharma_swarm/decision_router.py', 'docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md']
- moves_vital_signs: ['quality_gates', 'tool_coverage', 'cost_efficiency']

  - ✓ `model_pool_owner_exists` (file_exists) — dharma_swarm/model_pool.py present
  - ✓ `provider_policy_owner_exists` (file_exists) — dharma_swarm/provider_policy.py present
  - ✓ `model_hierarchy_owner_exists` (file_exists) — dharma_swarm/model_hierarchy.py present
  - ✓ `routing_architecture_doc_exists` (file_exists) — docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md present
  - ✓ `routing_precedence_documented` (file_contains) — pattern 'explicit > capability' found in docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md
  - ✓ `explicit_provider_honored` (file_contains) — pattern 'preferred_provider' found in dharma_swarm/provider_policy.py
  - ✓ `explicit_wins_test_exists` (file_contains) — pattern 'test_explicit_provider_is_selected' found in tests/test_provider_routing_explicit.py
  - ✓ `power_first_default` (file_contains) — pattern 'power_first' found in dharma_swarm/provider_policy.py
  - ✓ `zhipu_provider_enum` (file_contains) — pattern 'ZHIPU' found in dharma_swarm/models.py
  - ✓ `zhipu_provider_class` (file_contains) — pattern 'class ZhipuProvider' found in dharma_swarm/providers.py
  - ✓ `precedence_invariant_test_passes` (test_passes) — pytest tests/test_provider_routing_explicit.py::test_precedence_explicit_beats_power_beats_cost: PASS — 1 passed in 0.34s
  - ✓ `stage4_precedence_locked_on_main` (commit_on_main) — bc110d84 is an ancestor of origin/main

## `orchestration-arena-v1-2026-06` — 9/9

- serves: `substrate-nativeness` · complements: ['provider-routing-consolidation-2026-06', 'loop-closure-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/coordination/**', 'dharma_swarm/council/**', 'tests/test_arena_v1.py', 'tests/test_dpi.py', 'tests/test_orchestration_genome.py', 'tests/test_orchestrator_v1.py', 'tests/test_council_profiles.py', 'tests/test_coordination_closure_checks.py']
- moves_vital_signs: ['eval_coverage', 'quality_gates']

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

## `filesystem-native-substrate-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['truth-graph-platform-2026-06', 'runtime-truth-spine-adoption-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md', 'docs/research/FILESYSTEM_SUBSTRATE_SLICE_A_SPEC.md', 'docs/ontology/ONTOLOGY_PROPOSAL_LOG.md', 'dharma_swarm/fs_substrate/**', 'tests/test_stage_contracts.py', 'tests/test_okf_projection.py', 'tests/test_semantic_fs.py', 'tests/test_organizer.py']
- moves_vital_signs: ['context_efficiency', 'tool_coverage', 'memory_persistence']

  - ✓ `dossier_exists` (file_exists) — docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md present
  - ✓ `spine_invoke_owner_exists` (file_contains) — pattern 'async def invoke_agent' found in dharma_swarm/spine/invoke.py
  - ✓ `handoff_owner_exists` (file_exists) — dharma_swarm/handoff.py present
  - ✓ `dossier_consolidates_four_powers` (file_contains) — pattern 'The four powers at a glance' found in docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md
  - ✓ `dossier_carries_organism_tie` (file_contains) — pattern 'How this serves the organism' found in docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md
  - ✓ `stage_contract_reader_exists` (file_contains) — pattern 'class StageContract' found in dharma_swarm/fs_substrate/stage_contracts.py
  - ✓ `stage_reader_routes_through_spine` (file_contains) — pattern 'invoke_agent' found in dharma_swarm/fs_substrate/stage_executor.py
  - ✓ `stage_contract_test_passes` (test_passes) — pytest tests/test_stage_contracts.py: PASS — 8 passed in 0.32s
  - ✓ `okf_projector_exists` (file_contains) — pattern 'def project_semantic_objects' found in dharma_swarm/fs_substrate/okf.py
  - ✓ `okf_roundtrip_test_passes` (test_passes) — pytest tests/test_okf_projection.py: PASS — 6 passed in 0.35s
  - ✓ `semantic_fs_facade_exists` (file_contains) — pattern 'def semantic_retrieve' found in dharma_swarm/fs_substrate/semantic_fs.py
  - ✓ `semantic_fs_test_passes` (test_passes) — pytest tests/test_semantic_fs.py: PASS — 5 passed in 0.34s
  - ✓ `organizer_dry_run_first_exists` (file_contains) — pattern 'def propose_organization' found in dharma_swarm/fs_substrate/organizer.py
  - ✓ `organizer_test_passes` (test_passes) — pytest tests/test_organizer.py: PASS — 5 passed in 0.30s

## Findings

- **WARN** `wip-high`: 9 ACTIVE tracks exceed warn_active=5 — focus is spreading thin.
- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **WARN** `spine-uncovered:revenue-external-humans-served`: Spine objective 'revenue-external-humans-served' has no ACTIVE track serving it (coverage gap).
- **INFO** `track-shippable:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] all 12 criteria pass, rigorous evidence present, no open blockers — SHIPPABLE (rigorous bar). Close it.
- **INFO** `track-provisional:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] 2/2 criteria pass but NOT shippable under the rigorous bar: no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid). Existence checks are not closure (see REALITY_DEBT_LEDGER.md / cybernetics_codex._evaluate_loop_closure_replay).
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 7/8 completion criteria pass.
- **INFO** `track-in-progress:loop-closure-2026-06`: [loop-closure-2026-06] 10/11 completion criteria pass.
- **INFO** `track-shippable:truth-graph-platform-2026-06`: [truth-graph-platform-2026-06] all 17 criteria pass, rigorous evidence present, no open blockers — SHIPPABLE (rigorous bar). Close it.
- **INFO** `track-shippable:composer-holon-spine-longrun-2026-06`: [composer-holon-spine-longrun-2026-06] all 8 criteria pass, rigorous evidence present, no open blockers — SHIPPABLE (rigorous bar). Close it.
- **INFO** `track-shippable:provider-routing-consolidation-2026-06`: [provider-routing-consolidation-2026-06] all 9 criteria pass, rigorous evidence present, no open blockers — SHIPPABLE (rigorous bar). Close it.
- **INFO** `track-provisional:orchestration-arena-v1-2026-06`: [orchestration-arena-v1-2026-06] 9/9 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid). Existence checks are not closure (see REALITY_DEBT_LEDGER.md / cybernetics_codex._evaluate_loop_closure_replay).
- **INFO** `track-shippable:filesystem-native-substrate-2026-06`: [filesystem-native-substrate-2026-06] all 11 criteria pass, rigorous evidence present, no open blockers — SHIPPABLE (rigorous bar). Close it.
