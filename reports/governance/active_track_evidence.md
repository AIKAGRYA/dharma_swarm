# Track Portfolio Evidence

Generated: 2026-07-25T20:45:43+09:00 (schema v2)
Active tracks: **11** (warn 11, max 11) — shippable 8

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✓
- `research-depth` — ✓

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

## `runtime-truth-nats-2026-06` — 1/3

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md', 'dharma_swarm/a2a/nats_transport.py', 'dharma_swarm/a2a/a2a_server.py', 'dharma_swarm/operator_core/nats_live_contact.py', 'dharma_swarm/operator_core/nats_substrate_status.py', 'scripts/runtime/a2a_send.py', 'scripts/runtime/a2a_inbox_bridge.py', 'scripts/runtime/a2a_domain_reply_worker.py', 'scripts/runtime/a2a_reply_capture.py', 'scripts/governance/check_nats_substrate_contract.py', 'scripts/governance/run_nats_live_production_matrix.py', 'scripts/governance/check_nats_live_production_evidence.py', 'tests/test_nats_transport.py', 'tests/test_nats_substrate_contract.py', 'reports/governance/nats_live_production_matrix/**', 'reports/governance/runtime_truth_nats_closeout_packet_2026-07-01.md', 'reports/governance/runtime_truth_nats_final_evidence_2026-07-01.md', 'reports/governance/runtime_truth_nats_compact_raw_evidence_2026-07-01.json']
- moves_vital_signs: ['tool_coverage', 'quality_gates']

  - ✓ `nats_master_spec_exists` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `nats_transport_owner_exists` (file_exists) — dharma_swarm/a2a/nats_transport.py present
  - ✓ `nats_contract_checker_exists` (file_exists) — scripts/governance/check_nats_substrate_contract.py present
  - ✓ `nats_transport_tests_exist` (file_exists) — tests/test_nats_transport.py present
  - ✓ `nats_contract_tests_exist` (file_exists) — tests/test_nats_substrate_contract.py present
  - ✗ `nats_substrate_contract_checker_passes` (command_passes) — ./.venv/bin/python scripts/governance/check_nats_substrate_contract.py exited 1; output: NATS_CONTRACT_FAIL fresh live NATS production evidence check failed: EvidenceError: evidence is stale: age=24 days, 11:10:37.636294
  - ✓ `nats_transport_regression_tests_pass` (command_passes) — pytest -q tests/test_nats_transport.py tests/test_nats_substrate_contract.py exited 0; output: ...................                                                      [100%] | 19 passed in 1.57s
  - ✗ `nats_live_production_evidence_fresh` (command_passes) — ./.venv/bin/python scripts/governance/check_nats_live_production_evidence.py --max-age-hours 24 exited 1; output: NATS_LIVE_PRODUCTION_EVIDENCE_FAILED EvidenceError: evidence is stale: age=24 days, 11:10:39.522197

## `runtime-truth-spine-adoption-2026-06` — 9/10

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'runtime-truth-nats-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['dharma_swarm/spine/**', 'dharma_swarm/a2a/a2a_bridge.py', 'dharma_swarm/orchestrator.py', 'dharma_swarm/agent_runner.py', 'docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md', 'scripts/uplift_guards/check_spine_ownership.py']
- moves_vital_signs: ['quality_gates', 'tool_coverage']
- readiness_score_cap: current=70/100 · cap=70/100 · within cap

  - ✓ `spine_package_exists` (file_exists) — dharma_swarm/spine/__init__.py present
  - ✓ `invoke_agent_defined` (file_contains) — pattern 'async def invoke_agent' found in dharma_swarm/spine/invoke.py
  - ✓ `a2a_bridge_calls_spine` (file_contains) — pattern '(?m)^\\s*from dharma_swarm\\.spine' found in dharma_swarm/a2a/a2a_bridge.py
  - ✓ `orchestrator_calls_spine` (file_contains) — pattern '(?m)^\\s*from dharma_swarm\\.spine' found in dharma_swarm/orchestrator.py
  - ✓ `agent_runner_direct_paths_drained` (file_contains) — pattern 'assert report\\["summary"\\]\\["agent_runner_legacy_direct"\\] == 0' found in tests/test_spine_dispatch_mode_report.py
  - ✓ `dispatch_emits_evidence_receipt` (file_contains) — pattern 'test_every_dispatch_emits_exactly_one_evidence_receipt' found in tests/test_spine_adoption_dispatch.py
  - ✓ `zero_dropoff_sources` (file_contains) — pattern 'test_no_dropoff_sources_remain' found in tests/test_spine_adoption_dispatch.py
  - ✓ `bypass_allowlist_empty` (file_contains) — pattern '(?m)^_INTENTIONAL_BYPASS: dict\\[tuple\\[str, int\\], str\\] = \\{\\s*\\}' found in scripts/governance/spine_bypass_report.py
  - ✓ `adoption_narrative_docs` (file_exists) — docs/architecture/SPINE_ADOPTION_NARRATIVE.md present
  - ✓ `gate1_witnessed` (file_exists) — reports/governance/GATE1_WITNESSED.md present
  - ✓ `hardening_goal_exists` (file_exists) — docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md present
  - ✗ `hardening_score_at_least_75` (hardening_score_at_least) — hardening_status.current_score=70/100; requires >= 75/100 before this track can render shippable

## `loop-closure-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['reports/loop_closure/**', 'CYBERNETIC_LOOP_MAP.md']
- moves_vital_signs: ['quality_gates', 'eval_coverage']

  - ✓ `loop_map_exists` (file_exists) — CYBERNETIC_LOOP_MAP.md present
  - ✓ `loop_supervisor_exists` (file_exists) — dharma_swarm/loop_supervisor.py present
  - ✓ `phase0_dossier_exists` (file_exists) — reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md present
  - ✓ `phase0_fresh_status_table` (file_contains) — pattern 'Fresh 13-loop status table' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `one_wire_invariant_stated` (file_contains) — pattern 'never let internal artifacts touch archive fitness' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `cybernetics_codex_manifest_registered` (file_contains) — pattern 'id: cybernetics_codex' found in ACTIVE_SURFACE_MANIFEST.yaml
  - ✓ `cybernetics_codex_seed_exists` (file_exists) — docs/agents/cybernetics_codex/agent.seed.yaml present
  - ✓ `cybernetics_codex_soul_exists` (file_exists) — docs/agents/cybernetics_codex/SOUL.md present
  - ✓ `cybernetics_codex_context_desk_exists` (file_exists) — docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md present
  - ✓ `cybernetics_codex_audit_script_exists` (file_exists) — scripts/governance/cybernetics_codex_audit.py present
  - ✓ `cybernetics_codex_registration_script_exists` (file_exists) — scripts/governance/register_cybernetics_codex.py present
  - ✓ `loop1_closure_receipt_exists` (file_exists) — reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md present
  - ✓ `campaign_retrospective_exists` (file_exists) — reports/loop_closure/RETROSPECTIVE.md present

## `orientation-graph-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['scripts/governance/orientation_graph.py', 'tests/test_orientation_graph.py']
- moves_vital_signs: ['quality_gates']

  - ✓ `identity_owner_on_branch` (file_exists) — foundations/THE_ORGANISM.md present
  - ✓ `vision_owner_on_branch` (file_exists) — docs/vision_maps/NORTH_STAR.md present
  - ✓ `orientation_graph_exists` (file_exists) — scripts/governance/orientation_graph.py present
  - ✓ `orientation_packet_defined` (file_contains) — pattern 'class OrientationPacket' found in scripts/governance/orientation_graph.py
  - ✓ `orientation_read_only_test` (file_contains) — pattern 'test_orientation_graph_render_is_read_only' found in tests/test_orientation_graph.py
  - ✓ `onboard_identity_render` (file_contains) — pattern 'render_identity' found in scripts/governance/agent_onboard.py
  - ✓ `make_orient_target` (file_contains) — pattern 'orient:' found in Makefile
  - ✓ `megafile_points_at_north_star` (file_contains) — pattern 'NORTH_STAR.md' found in docs/MEGAFILE_INDEX.md

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

## `agent-admission-semantic-commons-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['cybernetics-codex-stewardship-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/ontology/**', 'docs/ops/AGENT_ADMISSION.md', 'dharma_swarm/semantic_commons.py', 'dharma_swarm/engine/hybrid_retriever.py', 'dharma_swarm/context.py', 'scripts/governance/agent_admission*.py', 'scripts/governance/name_drift*.py', 'tests/test_agent_admission*.py', 'tests/test_semantic_commons*.py', 'tests/test_hybrid_retriever.py']
- moves_vital_signs: ['quality_gates', 'memory_persistence']

  - ✓ `generic_onboarding_doc_exists` (file_exists) — docs/ops/AGENT_ONBOARDING.md present
  - ✓ `living_agent_kernel_exists` (file_exists) — dharma_swarm/operator_core/living_agent_kernel.py present
  - ✓ `semantic_commons_doc_exists` (file_exists) — docs/ontology/SEMANTIC_COMMONS.md present
  - ✓ `semantic_objects_index_exists` (file_exists) — docs/ontology/semantic_objects.yaml present
  - ✓ `semantic_aliases_index_exists` (file_exists) — docs/ontology/semantic_aliases.yaml present
  - ✓ `agent_admission_doc_exists` (file_exists) — docs/ops/AGENT_ADMISSION.md present
  - ✓ `name_drift_preflight_exists` (file_exists) — scripts/governance/name_drift_preflight.py present
  - ✓ `agent_admission_verifier_exists` (file_exists) — scripts/governance/agent_admission.py present
  - ✓ `semantic_commons_tests_exist` (file_exists) — tests/test_semantic_commons.py present
  - ✓ `agent_admission_tests_exist` (file_exists) — tests/test_agent_admission.py present
  - ✓ `pkm_projection_config_exists` (file_exists) — docs/ontology/pkm_projection.yaml present
  - ✓ `retrieval_scope_contract_exists` (file_exists) — docs/ontology/retrieval_scope.yaml present
  - ✓ `pkm_projection_script_exists` (file_exists) — scripts/governance/agent_admission_projection.py present
  - ✓ `semantic_commons_projection_tests_exist` (file_exists) — tests/test_semantic_commons_projection.py present
  - ✓ `semantic_commons_projection_manifest_exists` (file_exists) — reports/governance/semantic_commons_projection_manifest.json present
  - ✓ `semantic_commons_runtime_helper_exists` (file_exists) — dharma_swarm/semantic_commons.py present
  - ✓ `hybrid_retriever_scope_consumes_semantic_commons` (file_contains) — pattern 'orientation_route' found in dharma_swarm/engine/hybrid_retriever.py
  - ✓ `retrieval_scope_runtime_test_exists` (file_contains) — pattern 'test_hybrid_retriever_exposes_semantic_commons_scope_first' found in tests/test_hybrid_retriever.py

## `cybernetics-codex-stewardship-2026-06` — SHIPPABLE

- serves: `research-depth` · complements: ['agent-admission-semantic-commons-2026-06'] · depends_on: ['loop-closure-2026-06'] · conflicts_with: []
- owned_surfaces: ['docs/ops/CYBERNETICS_CODEX.md', 'docs/agents/cybernetics_codex/**', 'dharma_swarm/cybernetics_codex.py', 'scripts/governance/cybernetics_codex_audit.py', 'scripts/governance/register_cybernetics_codex.py', 'tests/test_cybernetics_codex.py', 'reports/loop_closure/cybernetics_codex/**']
- moves_vital_signs: ['quality_gates', 'eval_coverage', 'memory_persistence']

  - ✓ `loop_closure_track_exists` (file_contains) — pattern 'id: loop-closure-2026-06' found in docs/governance/ACTIVE_TRACK.yaml
  - ✓ `cybernetics_codex_manifest_registered` (file_contains) — pattern 'id: cybernetics_codex' found in ACTIVE_SURFACE_MANIFEST.yaml
  - ✓ `cybernetics_codex_charter_exists` (file_exists) — docs/ops/CYBERNETICS_CODEX.md present
  - ✓ `cybernetics_codex_seed_exists` (file_exists) — docs/agents/cybernetics_codex/agent.seed.yaml present
  - ✓ `cybernetics_codex_soul_exists` (file_exists) — docs/agents/cybernetics_codex/SOUL.md present
  - ✓ `cybernetics_codex_wake_context_exists` (file_exists) — docs/agents/cybernetics_codex/WAKE_CONTEXT.md present
  - ✓ `cybernetics_codex_protocols_exists` (file_exists) — docs/agents/cybernetics_codex/PROTOCOLS.md present
  - ✓ `cybernetics_codex_context_desk_exists` (file_exists) — docs/agents/cybernetics_codex/CONTEXT_ENGINEERING.md present
  - ✓ `cybernetics_codex_audit_script_exists` (file_exists) — scripts/governance/cybernetics_codex_audit.py present
  - ✓ `cybernetics_codex_registration_script_exists` (file_exists) — scripts/governance/register_cybernetics_codex.py present
  - ✓ `cybernetics_codex_tests_exist` (file_exists) — tests/test_cybernetics_codex.py present
  - ✓ `cybernetics_codex_admission_receipt_exists` (file_exists) — reports/loop_closure/cybernetics_codex/ADMISSION_RECEIPT.md present
  - ✓ `cybernetics_codex_runtime_receipt_exists` (file_exists) — reports/loop_closure/cybernetics_codex/RUNTIME_HEARTBEAT_RECEIPT.md present

## `telos-ai-morning-refinery-2026-06` — 6/7

- serves: `revenue-external-humans-served` · complements: [] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md', 'docs/vision_maps/TELOS_MORNING_REFINERY_V0.md', 'docs/research/telos_ai/**', 'PRODUCT_SURFACE.md', 'dashboard/src/app/dashboard/telos*/**', 'dashboard/src/components/telos*/**', 'tests/test_telos*.py']
- moves_vital_signs: ['eval_coverage', 'cost_efficiency']

  - ✓ `telos_seed_spec_exists` (file_exists) — docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md present
  - ✓ `morning_refinery_spec_exists` (file_exists) — docs/vision_maps/TELOS_MORNING_REFINERY_V0.md present
  - ✓ `seed_research_exists` (file_exists) — docs/research/telos_ai/2026-06-13_seed_research.md present
  - ✓ `feasibility_audit_exists` (file_exists) — docs/research/telos_ai/2026-06-13_codex_feasibility_audit.md present
  - ✓ `persona_council_exists` (file_exists) — docs/research/telos_ai/persona_agents/README.md present
  - ✓ `refinery_example_exists` (file_exists) — docs/research/telos_ai/refinery_examples/2026-06-13_ARTICULATE_ESSENCE_EXTRATOR_NODE_trial_001.md present
  - ✓ `telos_product_surface_registered` (file_contains) — pattern 'TELOS' found in PRODUCT_SURFACE.md
  - ✓ `consent_boundary_test_exists` (file_exists) — tests/test_telos_morning_refinery.py present
  - ✗ `first_external_receipt_exists` (external_acted_receipt) — reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md MISSING

## `helm-worldclass-terminal-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: [] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['terminal/**', 'docs/TERMINAL_TUI_TMUX_HARNESS_2026-04-02.md', 'docs/plans/2026-04-02-terminal-*.md', 'reports/terminal/**']
- moves_vital_signs: ['quality_gates', 'tool_coverage']

  - ✓ `terminal_package_exists` (file_exists) — terminal/package.json present
  - ✓ `terminal_app_exists` (file_exists) — terminal/src/app.tsx present
  - ✓ `app_test_exists` (file_exists) — terminal/tests/app.test.ts present
  - ✓ `golden_capture_exists` (file_exists) — terminal/scripts/golden_capture.sh present
  - ✓ `ratchet_script_exists` (file_exists) — terminal/scripts/ratchet.sh present
  - ✓ `chat_golden_exists` (file_exists) — terminal/tests/golden/120x40/chat.txt present
  - ✓ `compact_shell_test_exists` (file_exists) — terminal/tests/compactShell.test.tsx present
  - ✓ `live_tmux_receipt_exists` (file_exists) — reports/terminal/HELM_WORLDCLASS_LIVE_TMUX_RECEIPT.md present
  - ✓ `merge_readiness_packet_exists` (file_exists) — reports/terminal/HELM_WORLDCLASS_CLOSEOUT.md present

## `a2a-cloud-agent-bridge-2026-06` — SHIPPABLE

- serves: `substrate-nativeness` · complements: ['agent-admission-semantic-commons-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml', 'docs/architecture/A2A_CLOUD_BRIDGE.md', 'dharma_swarm/a2a/a2a_cloud_contact.py', 'dharma_swarm/a2a/contact_registry.py', 'dharma_swarm/a2a/verifier.py', 'reports/state/a2a_score_denominator.md', 'tests/test_a2a_cloud_contact.py']
- moves_vital_signs: ['tool_coverage', 'memory_persistence']

  - ✓ `proposed_bridge_packet_exists` (file_exists) — docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml present
  - ✓ `nats_spec_exists` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `cloud_contact_module_exists` (file_exists) — dharma_swarm/a2a/a2a_cloud_contact.py present
  - ✓ `cloud_contact_publishes_to_nats` (file_contains) — pattern 'jetstream.publish' found in dharma_swarm/a2a/a2a_cloud_contact.py
  - ✓ `contact_registry_supports_cloud_agents` (file_contains) — pattern 'cloud_agent' found in dharma_swarm/a2a/contact_registry.py
  - ✓ `verifier_includes_cloud_population` (file_contains) — pattern 'cloud_agent_denominator' found in dharma_swarm/a2a/verifier.py
  - ✓ `score_denominator_doc_exists` (file_exists) — reports/state/a2a_score_denominator.md present
  - ✓ `design_doc_exists` (file_exists) — docs/architecture/A2A_CLOUD_BRIDGE.md present
  - ✓ `round_trip_test_exists` (file_contains) — pattern 'test_round_trip_without_operator_transport' found in tests/test_a2a_cloud_contact.py

## Findings

- **WARN** `gauntlet-gate-missing:runtime-truth-reconciliation-2026-06`: ACTIVE track 'runtime-truth-reconciliation-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:runtime-truth-nats-2026-06`: ACTIVE track 'runtime-truth-nats-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:runtime-truth-spine-adoption-2026-06`: ACTIVE track 'runtime-truth-spine-adoption-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:loop-closure-2026-06`: ACTIVE track 'loop-closure-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:orientation-graph-2026-06`: ACTIVE track 'orientation-graph-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:composer-holon-spine-longrun-2026-06`: ACTIVE track 'composer-holon-spine-longrun-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:agent-admission-semantic-commons-2026-06`: ACTIVE track 'agent-admission-semantic-commons-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:cybernetics-codex-stewardship-2026-06`: ACTIVE track 'cybernetics-codex-stewardship-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:telos-ai-morning-refinery-2026-06`: ACTIVE track 'telos-ai-morning-refinery-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:helm-worldclass-terminal-2026-06`: ACTIVE track 'helm-worldclass-terminal-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **WARN** `gauntlet-gate-missing:a2a-cloud-agent-bridge-2026-06`: ACTIVE track 'a2a-cloud-agent-bridge-2026-06' declares no 'gauntlet_verified' completion criterion — it can currently render SHIPPABLE without passing the gauntlet. Add a gauntlet_verified gate to its completion_criteria.
- **ERROR** `track-stale:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] all 11 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] verified_at is 26 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] 1/3 completion criteria pass.
- **ERROR** `track-stale:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] verified_at is 45 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 9/10 completion criteria pass.
- **ERROR** `track-stale:loop-closure-2026-06`: [loop-closure-2026-06] verified_at is 26 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:loop-closure-2026-06`: [loop-closure-2026-06] all 11 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:orientation-graph-2026-06`: [orientation-graph-2026-06] verified_at is 44 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:orientation-graph-2026-06`: [orientation-graph-2026-06] all 6 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:composer-holon-spine-longrun-2026-06`: [composer-holon-spine-longrun-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:composer-holon-spine-longrun-2026-06`: [composer-holon-spine-longrun-2026-06] all 6 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:agent-admission-semantic-commons-2026-06`: [agent-admission-semantic-commons-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:agent-admission-semantic-commons-2026-06`: [agent-admission-semantic-commons-2026-06] all 16 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:cybernetics-codex-stewardship-2026-06`: [cybernetics-codex-stewardship-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:cybernetics-codex-stewardship-2026-06`: [cybernetics-codex-stewardship-2026-06] all 12 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:telos-ai-morning-refinery-2026-06`: [telos-ai-morning-refinery-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:telos-ai-morning-refinery-2026-06`: [telos-ai-morning-refinery-2026-06] 6/7 completion criteria pass.
- **ERROR** `track-stale:helm-worldclass-terminal-2026-06`: [helm-worldclass-terminal-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:helm-worldclass-terminal-2026-06`: [helm-worldclass-terminal-2026-06] all 7 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
- **ERROR** `track-stale:a2a-cloud-agent-bridge-2026-06`: [a2a-cloud-agent-bridge-2026-06] verified_at is 26 days old (ttl_days=14). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-shippable:a2a-cloud-agent-bridge-2026-06`: [a2a-cloud-agent-bridge-2026-06] all 7 completion criteria pass — SHIPPABLE; operator lifecycle review required. Do not close an active track solely from gate output.
