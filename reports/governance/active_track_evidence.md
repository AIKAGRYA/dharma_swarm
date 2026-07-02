# Track Portfolio Evidence

Generated: 2026-07-02T13:05:35+09:00 (schema v2)
Active tracks: **4** (warn 5, max 10) — shippable 0

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✗ (no active track)
- `research-depth` — ✗ (no active track)

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

## `loop-closure-2026-06` — 27/38

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['reports/loop_closure/**', 'CYBERNETIC_LOOP_MAP.md']
- moves_vital_signs: ['quality_gates', 'eval_coverage']

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
  - ✓ `cybernetics_codex_latest_audit_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/latest_audit.json valid (5 keys present)
  - ✓ `cybernetics_codex_11_harness_proven` (file_contains) — pattern '\\| 11 \\| Replication Monitor \\| HARNESS_PROVEN \\|' found in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✓ `cybernetics_codex_12_blocked` (file_contains) — pattern '\\| 12 \\| Self-Improvement \\| BLOCKED \\|' found in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✓ `cybernetics_codex_13_blocked` (file_contains) — pattern '\\| 13 \\| Free Evolution Grind \\| BLOCKED \\|' found in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop1_closed_live` (file_contains) — pattern '\\| 1 \\| Swarm Task Loop \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop2_closed_live` (file_contains) — pattern '\\| 2 \\| Organism Heartbeat \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop3_closed_live` (file_contains) — pattern '\\| 3 \\| Evolution Loop / DarwinEngine \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop4_closed_live` (file_contains) — pattern '\\| 4 \\| Consolidation Loop / Memory \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop5_closed_live` (file_contains) — pattern '\\| 5 \\| Zeitgeist Scanner \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop6_closed_live` (file_contains) — pattern '\\| 6 \\| Witness Auditor \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop7_closed_live` (file_contains) — pattern '\\| 7 \\| Training Flywheel \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop8_closed_live` (file_contains) — pattern '\\| 8 \\| Recognition Loop / eigenform \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop9_closed_live` (file_contains) — pattern '\\| 9 \\| Conductors \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop10_closed_live` (file_contains) — pattern '\\| 10 \\| Context Agent \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✗ `cybernetics_codex_loop11_closed_live` (file_contains) — pattern '\\| 11 \\| Replication Monitor \\| CLOSED_LIVE \\|' NOT FOUND in reports/loop_closure/cybernetics_codex/latest_audit.md
  - ✓ `cybernetics_codex_loop3_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop3_evolution_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop4_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop4_memory_context_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop7_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop7_training_flywheel_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop8_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop8_recognition_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop9_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop9_conductor_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop10_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop10_context_agent_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_loop11_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop11_replication_monitor_closure.json valid (6 keys present)
  - ✓ `cybernetics_codex_one_wire_guard_test_exists` (file_exists) — tests/test_one_wire_archive_fitness_guard.py present
  - ✓ `cybernetics_codex_one_wire_guard_test_passes` (test_passes) — pytest tests/test_one_wire_archive_fitness_guard.py: PASS — 9 passed in 0.21s
  - ✓ `cybernetics_codex_loop12_13_guard_receipt_exists` (file_exists) — reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json present
  - ✓ `cybernetics_codex_loop12_13_guard_receipt_valid` (receipt_valid) — receipt reports/loop_closure/cybernetics_codex/2026-07-01_loop12_13_one_wire_archive_fitness_guard.json valid (5 keys present)

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

## `merge-master-mike-d4-2026-06` — 3/4

- serves: `substrate-nativeness` · complements: ['runtime-truth-reconciliation-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['scripts/runtime/pr_merge_control.py', 'scripts/runtime/merge_master_mike_daemon.py', '.github/workflows/automerge.yml', '.github/workflows/codex-mention-router.yml', '.github/workflows/merge-master-mike-backlog.yml', 'tests/test_pr_merge_control_github_reviews.py']
- moves_vital_signs: ['quality_gates', 'tool_coverage']

  - ✓ `pr_merge_control_exists` (file_exists) — scripts/runtime/pr_merge_control.py present
  - ✓ `mike_daemon_exists` (file_exists) — scripts/runtime/merge_master_mike_daemon.py present
  - ✓ `automerge_workflow_exists` (file_exists) — .github/workflows/automerge.yml present
  - ✓ `router_workflow_exists` (file_exists) — .github/workflows/codex-mention-router.yml present
  - ✓ `github_review_receipt_bridge` (file_contains) — pattern 'github_review' found in scripts/runtime/pr_merge_control.py
  - ✓ `github_review_bridge_tested` (file_exists) — tests/test_pr_merge_control_github_reviews.py present
  - ✓ `automerge_enrolls_all_nondraft` (file_contains) — pattern 'mike-watch' found in .github/workflows/automerge.yml
  - ✗ `mike_cloud_heartbeat` (file_contains) — pattern 'schedule:' NOT FOUND in .github/workflows/merge-master-mike-backlog.yml

## Findings

- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **WARN** `spine-uncovered:revenue-external-humans-served`: Spine objective 'revenue-external-humans-served' has no ACTIVE track serving it (coverage gap).
- **WARN** `track-stale:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] verified_at is 22 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 7/8 completion criteria pass.
- **INFO** `track-in-progress:loop-closure-2026-06`: [loop-closure-2026-06] 27/38 completion criteria pass.
- **INFO** `track-provisional:orchestration-arena-v1-2026-06`: [orchestration-arena-v1-2026-06] 9/9 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S1_PRESENT < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification). Existence checks are not closure (see REALITY_DEBT_LEDGER.md / cybernetics_codex._evaluate_loop_closure_replay).
- **INFO** `track-in-progress:merge-master-mike-d4-2026-06`: [merge-master-mike-d4-2026-06] 3/4 completion criteria pass.
