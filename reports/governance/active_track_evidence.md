# Track Portfolio Evidence

Generated: 2026-07-02T13:03:15+00:00 (schema v2)
Active tracks: **5** (warn 5, max 10) — shippable 0

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

## `loop-closure-2026-06` — 11/11

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

## `organism-rewire-2026-07` — 0/0

- serves: `substrate-nativeness` · complements: ['runtime-truth-spine-adoption-2026-06', 'loop-closure-2026-06', 'orchestration-arena-v1-2026-06'] · depends_on: [] · conflicts_with: []
- owned_surfaces: ['tools/world_scout_go/**', 'tools/world_signal_ingestor_go/**', 'tools/github_ingestor_go/**', 'tools/evidence_ingestor_go/**', 'dharma_swarm/world_radar/**', 'dharma_swarm/organism.py', 'dharma_swarm/strange_loop.py', 'dharma_swarm/diversity_archive.py', 'dharma_swarm/archive.py', 'docker-compose.yml', 'Dockerfile.swarm']
- moves_vital_signs: ['quality_gates', 'eval_coverage']


## Findings

- **WARN** `spine-uncovered:research-depth`: Spine objective 'research-depth' has no ACTIVE track serving it (coverage gap).
- **WARN** `spine-uncovered:revenue-external-humans-served`: Spine objective 'revenue-external-humans-served' has no ACTIVE track serving it (coverage gap).
- **WARN** `track-stale:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] verified_at is 22 days old (ttl_days=21). Re-verify and bump verified_at, or retire the track.
- **INFO** `track-in-progress:runtime-truth-spine-adoption-2026-06`: [runtime-truth-spine-adoption-2026-06] 7/8 completion criteria pass.
- **INFO** `track-provisional:loop-closure-2026-06`: [loop-closure-2026-06] 11/11 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S1_PRESENT < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification). Existence checks are not closure (see REALITY_DEBT_LEDGER.md / cybernetics_codex._evaluate_loop_closure_replay).
- **INFO** `track-provisional:orchestration-arena-v1-2026-06`: [orchestration-arena-v1-2026-06] 9/9 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S1_PRESENT < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification). Existence checks are not closure (see REALITY_DEBT_LEDGER.md / cybernetics_codex._evaluate_loop_closure_replay).
- **INFO** `track-in-progress:merge-master-mike-d4-2026-06`: [merge-master-mike-d4-2026-06] 3/4 completion criteria pass.
