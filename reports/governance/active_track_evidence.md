# Track Portfolio Evidence

Generated: 2026-06-21T10:55:41+00:00 (schema v2)
Active tracks: **7** (warn 5, max 10) — shippable 5

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

## `runtime-truth-nats-2026-06` — SHIPPABLE

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

## Findings

- **WARN** `wip-high`: 7 ACTIVE tracks exceed warn_active=5 — focus is spreading thin.
- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **WARN** `spine-uncovered:revenue-external-humans-served`: Spine objective 'revenue-external-humans-served' has no ACTIVE track serving it (coverage gap).
- **INFO** `track-shippable:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] all 11 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-shippable:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] all 2 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 7/8 completion criteria pass.
- **INFO** `track-in-progress:loop-closure-2026-06`: [loop-closure-2026-06] 10/11 completion criteria pass.
- **INFO** `track-shippable:truth-graph-platform-2026-06`: [truth-graph-platform-2026-06] all 15 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-shippable:composer-holon-spine-longrun-2026-06`: [composer-holon-spine-longrun-2026-06] all 6 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-shippable:provider-routing-consolidation-2026-06`: [provider-routing-consolidation-2026-06] all 7 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
