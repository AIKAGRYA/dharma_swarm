# Track Portfolio Evidence

Generated: 2026-06-13T05:40:54+09:00 (schema v2)
Active tracks: **6** (warn 5, max 10) — shippable 3

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

## `runtime-truth-nats-2026-06` — 59/60

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06', 'orientation-graph-2026-06', 'composer-holon-spine-longrun-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md', 'docs/governance/active_tracks/a2a-runtime-spine-2026-06/**', 'docs/governance/proposed_tracks/perplexity-a2a-bus-bridge-2026-06.yaml', 'docs/plans/2026-06-11-dharma-a2a-stream-retention-proposal.md', 'dharma_swarm/a2a/**', 'dharma_swarm/operator_core/nats_live_contact.py', 'dharma_swarm/operator_core/nats_substrate_status.py', 'scripts/runtime/a2a_send.py', 'scripts/runtime/a2a_inbox_bridge.py', 'scripts/runtime/a2a_inbox_quarantine.py', 'scripts/runtime/a2a_file_bus_guard.py', 'scripts/runtime/a2a_hermes_broadcast_guard.py', 'scripts/runtime/a2a_daemon_wiring_audit.py', 'scripts/runtime/a2a_launchagent_quarantine.py', 'scripts/runtime/a2a_live_handler_repair_plan.py', 'scripts/runtime/a2a_reset_quorum_consumers.py', 'scripts/runtime/a2a_reply_capture.py', 'scripts/runtime/a2a_domain_reply_worker.py', 'scripts/runtime/a2a_prod_readiness_quorum.py', 'scripts/runtime/a2a_prod_readiness_solicit.py', 'scripts/runtime/a2a_prod_readiness_delivery_status.py', 'scripts/runtime/a2a_quorum_blocker_status.py', 'scripts/runtime/a2a_reviewer_route_health.py', 'reports/a2a/**', 'reports/a2a/hermes_broadcast_guard/**']
- moves_vital_signs: ['tool_coverage', 'memory_persistence', 'eval_coverage', 'quality_gates']

  - ✓ `nats_master_spec_exists` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `a2a_send_exists` (file_exists) — scripts/runtime/a2a_send.py present
  - ✓ `inbox_bridge_exists` (file_exists) — scripts/runtime/a2a_inbox_bridge.py present
  - ✓ `reply_capture_exists` (file_exists) — scripts/runtime/a2a_reply_capture.py present
  - ✓ `inbox_quarantine_exists` (file_exists) — scripts/runtime/a2a_inbox_quarantine.py present
  - ✓ `file_bus_guard_exists` (file_exists) — scripts/runtime/a2a_file_bus_guard.py present
  - ✓ `nats_master_spec_present` (file_exists) — docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md present
  - ✓ `active_track_subtree_exists` (file_exists) — docs/governance/active_tracks/a2a-runtime-spine-2026-06/README.md present
  - ✓ `subtrack_map_exists` (file_exists) — docs/governance/active_tracks/a2a-runtime-spine-2026-06/SUBTRACKS.yaml present
  - ✓ `no_more_than_five_subtracks_declared` (file_contains) — pattern 'max_subtracks: 5' found in docs/governance/active_tracks/a2a-runtime-spine-2026-06/SUBTRACKS.yaml
  - ✓ `publish_only_not_live_contact` (file_contains) — pattern 'live_contact_claim' found in tests/test_a2a_send.py
  - ✓ `inbox_bridge_denies_semantic_claim` (file_contains) — pattern 'peer_model_processed_claim' found in tests/test_a2a_inbox_bridge.py
  - ✓ `reply_capture_domain_receipt_guard` (file_contains) — pattern 'DOMAIN_RECEIPTED' found in tests/test_a2a_reply_capture.py
  - ✓ `drain_reset_runbook_exists` (file_exists) — docs/governance/active_tracks/a2a-runtime-spine-2026-06/NATS_DRAIN_AND_RESET_RUNBOOK.md present
  - ✓ `inbox_quarantine_tool_exists` (file_exists) — scripts/runtime/a2a_inbox_quarantine.py present
  - ✓ `inbox_quarantine_test_exists` (file_contains) — pattern 'test_apply_moves_files_and_leaves_readme' found in tests/test_a2a_inbox_quarantine.py
  - ✓ `file_bus_broadcast_guard_exists` (file_exists) — scripts/runtime/a2a_file_bus_guard.py present
  - ✓ `file_bus_broadcast_guard_test_exists` (file_contains) — pattern 'test_broadcast_copied_into_many_inboxes_fails' found in tests/test_a2a_file_bus_guard.py
  - ✓ `file_bus_guard_after_hermes_disable_passes` (file_contains) — pattern '"status": "PASS"' found in reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json
  - ✓ `hermes_broadcast_guard_tool_exists` (file_exists) — scripts/runtime/a2a_hermes_broadcast_guard.py present
  - ✓ `hermes_broadcast_guard_test_exists` (file_contains) — pattern 'test_apply_patches_router_creates_backup_and_disable_flag' found in tests/test_a2a_hermes_broadcast_guard.py
  - ✓ `hermes_broadcast_guard_receipt_exists` (file_contains) — pattern '"broadcast_disabled": true' found in reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json
  - ✓ `daemon_wiring_audit_tool_exists` (file_exists) — scripts/runtime/a2a_daemon_wiring_audit.py present
  - ✓ `daemon_wiring_audit_test_exists` (file_contains) — pattern 'test_missing_module_and_local_broker_fail' found in tests/test_a2a_daemon_wiring_audit.py
  - ✓ `launchagent_quarantine_tool_exists` (file_exists) — scripts/runtime/a2a_launchagent_quarantine.py present
  - ✓ `launchagent_quarantine_test_exists` (file_contains) — pattern 'test_apply_moves_plist_and_leaves_pointer' found in tests/test_a2a_launchagent_quarantine.py
  - ✓ `launchagent_quarantine_receipt_exists` (file_exists) — reports/a2a/launchagent_quarantine_receipts/20260612T184702Z-a2a-launchagent-quarantine.json present
  - ✓ `daemon_wiring_audit_top_level_passes` (file_contains) — pattern '(?m)^  "status": "PASS"' found in reports/a2a/nats_reset/2026-06-13/A2A_DAEMON_WIRING_AUDIT.json
  - ✓ `live_handler_repair_plan_tool_exists` (file_exists) — scripts/runtime/a2a_live_handler_repair_plan.py present
  - ✓ `live_handler_repair_plan_test_exists` (file_contains) — pattern 'test_build_plan_reports_daemon_and_delivery_gaps' found in tests/test_a2a_live_handler_repair_plan.py
  - ✓ `live_handler_repair_plan_ready` (file_contains) — pattern '"status": "READY_TO_MUTATE"' found in reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json
  - ✓ `quorum_consumer_reset_tool_exists` (file_exists) — scripts/runtime/a2a_reset_quorum_consumers.py present
  - ✓ `quorum_consumer_reset_test_exists` (file_contains) — pattern 'test_build_reset_receipt_applies_delete_and_recreate' found in tests/test_a2a_reset_quorum_consumers.py
  - ✓ `quorum_consumer_reset_receipt_exists` (file_contains) — pattern '"status": "APPLIED"' found in reports/a2a/nats_reset/2026-06-13/A2A_QUORUM_CONSUMER_RESET_APPLIED.json
  - ✓ `broker_scope_guard_test_exists` (file_contains) — pattern 'test_require_agni_broker_scope_blocks_local_publish' found in tests/test_a2a_send.py
  - ✓ `broker_scope_guard_receipt_exists` (file_exists) — reports/a2a/routing_scope_receipts/2026-06-13/AGNI_SCOPE_GUARD_LOCAL_MISMATCH.json present
  - ✓ `file_inbox_quarantine_applied` (file_exists) — reports/a2a/nats_reset/2026-06-13/FILE_INBOX_QUARANTINE_APPLIED.json present
  - ✓ `ds_goal_mission_created` (file_exists) — reports/a2a/nats_reset/2026-06-13/DS_GOAL_MISSION.json present
  - ✓ `live_baseline_receipt_exists` (file_exists) — reports/a2a/nats_reset/2026-06-13/BASELINE.json present
  - ✓ `nats_consumer_inbox_reset_applied` (file_exists) — reports/a2a/nats_reset/2026-06-13/NATS_CONSUMER_INBOX_RESET_APPLIED.json present
  - ✓ `fable_composer_consumer_provisioned` (file_exists) — reports/a2a/nats_reset/2026-06-13/FABLE_COMPOSER_CONSUMER_PROVISIONED.json present
  - ✓ `production_quorum_rule_exists` (file_exists) — docs/governance/active_tracks/a2a-runtime-spine-2026-06/PRODUCTION_READINESS_QUORUM.md present
  - ✓ `production_quorum_validator_exists` (file_exists) — scripts/runtime/a2a_prod_readiness_quorum.py present
  - ✓ `production_quorum_validator_test_exists` (file_contains) — pattern 'test_ready_quorum_requires_two_agents_three_models_and_median_80' found in tests/test_a2a_prod_readiness_quorum.py
  - ✓ `production_quorum_evidence_refs_verified` (file_contains) — pattern 'test_missing_evidence_ref_is_schema_error' found in tests/test_a2a_prod_readiness_quorum.py
  - ✓ `production_quorum_solicitor_exists` (file_exists) — scripts/runtime/a2a_prod_readiness_solicit.py present
  - ✓ `production_quorum_solicitor_test_exists` (file_contains) — pattern 'test_write_solicitations_creates_request_files_and_receipt' found in tests/test_a2a_prod_readiness_solicit.py
  - ✓ `production_quorum_delivery_status_tool_exists` (file_exists) — scripts/runtime/a2a_prod_readiness_delivery_status.py present
  - ✓ `production_quorum_delivery_status_test_exists` (file_contains) — pattern 'test_live_probe_marks_pending_delivery' found in tests/test_a2a_prod_readiness_delivery_status.py
  - ✓ `production_quorum_delivery_status_receipt_exists` (file_contains) — pattern '"status": "PENDING_REVIEWER_RECORDS"' found in reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json
  - ✓ `production_quorum_blocker_status_tool_exists` (file_exists) — scripts/runtime/a2a_quorum_blocker_status.py present
  - ✓ `production_quorum_blocker_status_test_exists` (file_contains) — pattern 'test_pending_delivery_claim_becomes_partially_resolved_when_consumers_empty' found in tests/test_a2a_quorum_blocker_status.py
  - ✓ `production_quorum_blocker_status_receipt_exists` (file_contains) — pattern '"status": "BLOCKED_BY_CURRENT_EVIDENCE"' found in reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_BLOCKER_STATUS.json
  - ✓ `production_quorum_route_health_tool_exists` (file_exists) — scripts/runtime/a2a_reviewer_route_health.py present
  - ✓ `production_quorum_route_health_test_exists` (file_contains) — pattern 'test_provider_credit_blocks_missing_fable_record' found in tests/test_a2a_reviewer_route_health.py
  - ✓ `production_quorum_route_health_receipt_exists` (file_contains) — pattern '"status": "ROUTE_HEALTH_BLOCKED"' found in reports/a2a/prod_readiness_quorum/2026-06-13/REVIEWER_ROUTE_HEALTH.json
  - ✓ `production_quorum_solicitation_receipt_exists` (file_exists) — reports/a2a/prod_readiness_quorum/2026-06-13/SOLICITATION_RECEIPT.json present
  - ✓ `fable_composer_solicitation_sent` (file_exists) — reports/a2a/prod_readiness_quorum/2026-06-13/FABLE_COMPOSER_SOLICITATION_NATS_SEND.json present
  - ✓ `local_live_contact_drill_receipt_exists` (file_contains) — pattern '"status": "LOCAL_DOMAIN_RECEIPTED"' found in reports/a2a/live_contact_drill/2026-06-13/LOCAL_LIVE_CONTACT_DRILL_RECEIPT.json
  - ✓ `nats_py_runtime_dependency_declared` (file_contains) — pattern 'nats-py' found in pyproject.toml
  - ✓ `python_tool_live_contact_drill_receipt_exists` (file_contains) — pattern '"status": "LOCAL_PYTHON_TOOLS_DOMAIN_RECEIPTED"' found in reports/a2a/live_contact_drill/2026-06-13/PYTHON_TOOL_LIVE_CONTACT_DRILL_RECEIPT.json
  - ✓ `agni_context_sender_test_exists` (file_contains) — pattern 'test_main_nats_context_publish_uses_cli_context' found in tests/test_a2a_send.py
  - ✓ `agni_a2a_live_contact_drill_receipt_exists` (file_contains) — pattern '"status": "AGNI_SYNTHETIC_DOMAIN_RECEIPTED"' found in reports/a2a/agni_live_contact_drill/2026-06-13/AGNI_A2A_LIVE_CONTACT_DRILL_RECEIPT.json
  - ✗ `production_quorum_collected` (file_contains) — pattern '"status": "READY"' NOT FOUND in reports/a2a/prod_readiness_quorum/latest.json
  - ✓ `drain_applied_receipt_exists` (file_exists) — reports/a2a/nats_reset/2026-06-13/DRAIN_APPLIED_RECEIPT.json present
  - ✓ `post_reset_receipt_exists` (file_exists) — reports/a2a/nats_reset/2026-06-13/AFTER.json present

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

## `loop-closure-2026-06` — 3/5

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['reports/loop_closure/**', 'CYBERNETIC_LOOP_MAP.md']
- moves_vital_signs: ['quality_gates', 'eval_coverage']

  - ✓ `loop_map_exists` (file_exists) — CYBERNETIC_LOOP_MAP.md present
  - ✓ `loop_supervisor_exists` (file_exists) — dharma_swarm/loop_supervisor.py present
  - ✓ `phase0_dossier_exists` (file_exists) — reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md present
  - ✓ `phase0_fresh_status_table` (file_contains) — pattern 'Fresh 13-loop status table' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✓ `one_wire_invariant_stated` (file_contains) — pattern 'never let internal artifacts touch archive fitness' found in reports/loop_closure/2026-06-11/RESEARCH_DOSSIER.md
  - ✗ `loop1_closure_receipt_exists` (file_exists) — reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md MISSING
  - ✗ `campaign_retrospective_exists` (file_exists) — reports/loop_closure/RETROSPECTIVE.md MISSING

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

## Findings

- **WARN** `wip-high`: 6 ACTIVE tracks exceed warn_active=5 — focus is spreading thin.
- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **WARN** `spine-uncovered:revenue-external-humans-served`: Spine objective 'revenue-external-humans-served' has no ACTIVE track serving it (coverage gap).
- **INFO** `track-shippable:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] all 11 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-in-progress:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] 59/60 completion criteria pass.
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 7/8 completion criteria pass.
- **INFO** `track-in-progress:loop-closure-2026-06`: [loop-closure-2026-06] 3/5 completion criteria pass.
- **INFO** `track-shippable:orientation-graph-2026-06`: [orientation-graph-2026-06] all 6 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-shippable:composer-holon-spine-longrun-2026-06`: [composer-holon-spine-longrun-2026-06] all 6 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
