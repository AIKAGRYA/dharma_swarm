# Track Portfolio Evidence

Generated: 2026-06-12T20:05:25+09:00 (schema v2)
Active tracks: **3** (warn 5, max 10) — shippable 2

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✓
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

## `go-ingest-intelligence-flow-2026-06` — 4/7

- serves: `revenue-external-humans-served` · complements: ['runtime-truth-reconciliation-2026-06', 'runtime-truth-nats-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md', 'docs/architecture/WORLD_ZEITGEIST.md', 'docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md', 'tools/go_sdk/**', 'tools/evidence_ingestor_go/**', 'tools/github_ingestor_go/**', 'tools/world_signal_ingestor_go/**', 'tools/world_scout_go/**', 'dharma_swarm/world_radar/**', 'dharma_swarm/revenue/**', 'tests/test_go_*.py', 'tests/test_world_radar_go_bridge.py', 'tests/test_revenue_scout_daemon.py']
- moves_vital_signs: ['tool_coverage', 'quality_gates', 'memory_persistence', 'cost_efficiency']

  - ✓ `go_idea_spark_master_spec_exists` (file_exists) — docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md present
  - ✓ `world_zeitgeist_contract_exists` (file_exists) — docs/architecture/WORLD_ZEITGEIST.md present
  - ✓ `business_intelligence_noticers_contract_exists` (file_exists) — docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md present
  - ✓ `venture_cell_portfolio_exists` (file_exists) — docs/governance/VENTURE_CELL_PORTFOLIO.yaml present
  - ✓ `world_scout_declared_in_go_ci` (file_contains) — pattern 'GO_WORLD_SCOUT_MODULE' found in Makefile
  - ✓ `go_ci_covers_world_scout` (file_contains) — pattern 'GO_MODULES :=.*GO_WORLD_SCOUT_MODULE' found in Makefile
  - ✓ `spool_replay_idempotency_tested` (file_contains) — pattern 'TestReplayPendingIsIdempotentAfterDelivery' found in tools/go_sdk/spool/spool_test.go
  - ✓ `world_receipt_projection_bridge_present` (file_contains) — pattern 'project_world_signal_receipts' found in dharma_swarm/world_radar/go_bridge.py
  - ✓ `ingest_cost_idempotency_tested` (file_contains) — pattern 'test_record_ingest_cost_event_is_idempotent' found in tests/test_world_radar_go_bridge.py
  - ✗ `multi_domain_e2e_test_exists` (file_exists) — tests/test_go_ingest_intelligence_flow_e2e.py MISSING
  - ✗ `e2e_feeds_venture_consumer` (file_contains) — tests/test_go_ingest_intelligence_flow_e2e.py missing
  - ✗ `e2e_runtime_receipt_association` (file_contains) — tests/test_go_ingest_intelligence_flow_e2e.py missing

## Findings

- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **INFO** `track-shippable:runtime-truth-reconciliation-2026-06`: [runtime-truth-reconciliation-2026-06] all 11 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-shippable:runtime-truth-nats-2026-06`: [runtime-truth-nats-2026-06] all 2 completion criteria pass — SHIPPABLE; close it (and optionally open the next).
- **INFO** `track-in-progress:go-ingest-intelligence-flow-2026-06`: [go-ingest-intelligence-flow-2026-06] 4/7 completion criteria pass.
