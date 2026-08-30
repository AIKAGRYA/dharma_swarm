# Track Portfolio Evidence

Generated: 2026-08-30T16:18:40+00:00 (schema v2)
Active tracks: **4** (warn 5, max 10) — shippable 0

Scoped WIP `mac_build`: **4** (warn 4, max 4; Mac build admission only). This is declared build admission, not host/runtime evidence.

## Spine coverage

- `substrate-nativeness` — ✓
- `revenue-external-humans-served` — ✓
- `research-depth` — ✓

## `fleet-advancement-2026-08` — 3/3

- serves: `substrate-nativeness` · complements: ['sadhana-10-day-program-2026-08', 'rsi-lab-meghadharma-2026-08', 'sublimation-forge-2026-08'] · depends_on: [] · conflicts_with: []
- admission scopes: ['mac_build'] (declared build authority; not runtime evidence)
- owned_surfaces: ['dharma_swarm/mission_control*.py', 'tests/test_mission_control.py', 'dashboard/src/app/dashboard/cockpit/**', 'dashboard/src/components/cockpit/**', 'dashboard/src/components/operator-coherence/v2/**', 'terminal/**', 'docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md', 'specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md']
- moves_vital_signs: ['tool_coverage', 'context_efficiency', 'quality_gates', 'security_guardrails']
- claim_boundary: Fleet Hub, Mission Control, and HELM are bounded prototype deliverables inside this one program lane. A prototype, local process, or attempt record does not prove a production adapter, command authority, or executor liveness.
- ship_blocks: 2 open blocker next-item(s)

  - ✓ prerequisite `focus_reset_receipt_valid` (receipt_valid) — receipt reports/governance/mac_active_programs/2026-08-27-focus-reset.json valid (6 keys present, fresh)
  - ✓ completion `mission_control_contract_tests_pass` (test_passes) — pytest tests/test_mission_control.py: PASS — 63 passed in 21.16s
  - ✓ completion `cockpit_route_exists` (file_exists) — dashboard/src/app/dashboard/cockpit/page.tsx present
  - ✓ completion `helm_shell_contract_exists` (file_exists) — terminal/tests/nihongaShell.test.ts present

## `sadhana-10-day-program-2026-08` — 0/2

- serves: `revenue-external-humans-served` · complements: ['fleet-advancement-2026-08', 'rsi-lab-meghadharma-2026-08'] · depends_on: [] · conflicts_with: []
- admission scopes: ['mac_build'] (declared build authority; not runtime evidence)
- owned_surfaces: ['deploy/sadhana/**', 'scripts/runtime/sadhana_release.py', 'tests/test_sadhana_release.py', 'dashboard/src/app/dashboard/sadhana/**']
- moves_vital_signs: ['quality_gates', 'eval_coverage', 'security_guardrails']
- claim_boundary: The provisional release package is preserved at /Users/dhyana/ds_sadhana_10day_release_final_20260827 and on draft PR #1453. Custody, tests in that worktree, and code volume do not prove the package is landed or a participant journey, release, or program outcome is live.
- ship_blocks: 2 open blocker next-item(s); no rigorous evidence (criteria are existence-only: file_exists/file_contains — add test_passes / commit_on_main / receipt_valid); strongest evidence S0_EXISTS < required S2_LANDED (raise evidence strength or lower min_evidence_grade with justification)

  - ✓ prerequisite `focus_reset_receipt_valid` (receipt_valid) — receipt reports/governance/mac_active_programs/2026-08-27-focus-reset.json valid (6 keys present, fresh)
  - ✗ completion `sadhana_release_contract_landed` (file_exists) — scripts/runtime/sadhana_release.py MISSING
  - ✗ completion `sadhana_release_tests_landed` (test_passes) — pytest tests/test_sadhana_release.py: FAIL — ERROR: file or directory not found: tests/test_sadhana_release.py

## `rsi-lab-meghadharma-2026-08` — 3/3

- serves: `research-depth` · complements: ['fleet-advancement-2026-08', 'sadhana-10-day-program-2026-08', 'sublimation-forge-2026-08'] · depends_on: [] · conflicts_with: []
- admission scopes: ['mac_build'] (declared build authority; not runtime evidence)
- owned_surfaces: ['dharma_swarm/forge_lab/**', 'scripts/forge_lab/**', 'tests/forge_lab_v1/**', 'docs/ops/RSI_LAB_SYNC.md']
- moves_vital_signs: ['eval_coverage', 'memory_persistence', 'cost_efficiency', 'security_guardrails']
- claim_boundary: The rsi sync owner proves exact code identity only. Commit b148f55e is active and ready on Mac and Meghadharma under plan digest sha256:38410a2e9b3caaae29f37b9492d01261560865f452210c7c3ef582b6e6da3db7; state, secrets, provider credentials, and research quality remain separate claims.
- ship_blocks: 1 open blocker next-item(s)

  - ✓ prerequisite `focus_reset_receipt_valid` (receipt_valid) — receipt reports/governance/mac_active_programs/2026-08-27-focus-reset.json valid (6 keys present, fresh)
  - ✓ completion `exact_sync_observation_receipt_valid` (receipt_valid) — receipt reports/governance/mac_active_programs/2026-08-27-rsi-exact-sync-witness.json valid (8 keys present, digest intact, fresh)
  - ✓ completion `exact_sync_host_commits_match` (json_collection_values_match) — reports/governance/mac_active_programs/2026-08-27-rsi-exact-sync-witness.json.host_observations 2 expected commit value(s) matched
  - ✓ completion `exact_sync_host_trees_match` (json_collection_values_match) — reports/governance/mac_active_programs/2026-08-27-rsi-exact-sync-witness.json.host_observations 2 expected tree value(s) matched

## `sublimation-forge-2026-08` — 2/3

- serves: `research-depth` · complements: ['fleet-advancement-2026-08', 'rsi-lab-meghadharma-2026-08'] · depends_on: [] · conflicts_with: []
- admission scopes: ['mac_build'] (declared build authority; not runtime evidence)
- owned_surfaces: ['dharma_swarm/foundry/__init__.py', 'dharma_swarm/foundry/army.py', 'dharma_swarm/foundry/artifacts.py', 'dharma_swarm/foundry/campaign.py', 'dharma_swarm/foundry/daemon.py', 'dharma_swarm/foundry/elite_grid.py', 'dharma_swarm/foundry/evaluator.py', 'dharma_swarm/foundry/heldout.py', 'dharma_swarm/foundry/kill_metrics.py', 'dharma_swarm/foundry/killswitch.py', 'dharma_swarm/foundry/loop.py', 'dharma_swarm/foundry/patches.py', 'dharma_swarm/foundry/receipts.py', 'dharma_swarm/foundry/report_card.py', 'dharma_swarm/foundry/runner_isolation.py', 'dharma_swarm/foundry/shakti_local_world.py', 'dharma_swarm/foundry/shakti_system.py', 'dharma_swarm/foundry/target_ingest.py', 'dharma_swarm/foundry/targets.py', 'dharma_swarm/foundry/tripwires.py', 'scripts/foundry/**', 'tests/test_foundry_army.py', 'tests/test_foundry_artifacts.py', 'tests/test_foundry_campaign.py', 'tests/test_foundry_daemon.py', 'tests/test_foundry_evaluator.py', 'tests/test_foundry_heldout.py', 'tests/test_foundry_kill_metrics.py', 'tests/test_foundry_killswitch.py', 'tests/test_foundry_loop.py', 'tests/test_foundry_patches.py', 'tests/test_foundry_receipts.py', 'tests/test_foundry_report_card.py', 'tests/test_foundry_runner_isolation.py', 'tests/test_foundry_shakti_system.py', 'tests/test_foundry_target_ingest.py', 'tests/test_foundry_tripwires.py', 'docs/foundry/**', 'dharma_swarm/rudra/**', 'dharma_swarm/terminal_commands/rudra.py', 'tests/test_rudra_*.py', 'tests/fixtures/rudra/**', 'reports/rudra/**', 'docs/plans/rudra_v0/**']
- moves_vital_signs: ['quality_gates', 'eval_coverage', 'cost_efficiency']
- claim_boundary: The active Sublimation Forge packet authorizes an offline pilot only. Local loops and scorecards do not authorize live providers, deployment, VPS mutation, outreach, or promotion. RUDRA v0 carve-out (amended 2026-08-28, operator RUDRA ASCENT campaign): the RUDRA v0 release proof — and only that proof, on operator-authored mission contracts under docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md — may drive the operator-authenticated Codex app-server executor with provider egress to the configured model service only and tool network denied. This is not a standing license for track agents: every live-executor run requires its own admitted mission contract, and COMPLETE_REPRODUCED grants no push, merge, deploy, publish, or spend authority. Custody ruling 2026-08-30 (ONE_WORLD unification program, docs/plans/ONE_WORLD_2026-08-30.md; PR #1493): the guardian-feed surface — dharma_swarm/foundry/guardian_feed.py and tests/test_foundry_guardian_feed.py — is ceded from this track's owned_surfaces. The ONE_WORLD integration reconciles the Mac silvering (efca57e40: operator_approved flag replacing One Wire quorum arithmetic) with the quorum-pinning guardian-feed tests, and that reconciliation content is already CI-green on #1493; the sole red check was the fail-closed AgentOps packet-scope union of this track's immutable merge-base ownership, which no integration packet could satisfy while the foundry globs stood. Every other foundry and RUDRA surface remains owned by this track; the ceded globs are now explicit file lists, so any NEW foundry file or foundry test is unowned until a future track amendment re-admits it.
- ship_blocks: 2 open blocker next-item(s)

  - ✓ prerequisite `focus_reset_receipt_valid` (receipt_valid) — receipt reports/governance/mac_active_programs/2026-08-27-focus-reset.json valid (6 keys present, fresh)
  - ✓ completion `foundry_loop_tests_pass` (test_passes) — pytest tests/test_foundry_loop.py: PASS — 20 passed in 0.57s
  - ✓ completion `foundry_heldout_tests_pass` (test_passes) — pytest tests/test_foundry_heldout.py: PASS — 23 passed in 0.53s
  - ✗ completion `rudra_ab_proof_receipt_valid` (receipt_valid) — receipt reports/rudra/AB_PROOF_V0.json MISSING

## Findings

- **INFO** `track-provisional:fleet-advancement-2026-08`: [fleet-advancement-2026-08] 3/3 criteria pass but NOT shippable under the rigorous bar: 2 open blocker next-item(s). Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **INFO** `track-in-progress:sadhana-10-day-program-2026-08`: [sadhana-10-day-program-2026-08] 0/2 completion criteria pass.
- **INFO** `track-provisional:rsi-lab-meghadharma-2026-08`: [rsi-lab-meghadharma-2026-08] 3/3 criteria pass but NOT shippable under the rigorous bar: 1 open blocker next-item(s). Criteria passing is not closure, and a valid receipt is not a passing outcome (see REALITY_DEBT_LEDGER.md / the Final Boss closure gauntlet).
- **INFO** `track-in-progress:sublimation-forge-2026-08`: [sublimation-forge-2026-08] 2/3 completion criteria pass.
