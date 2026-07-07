# ACTIVE_TRACK Reconciliation Receipt — 2026-07-07

Branch: `gov/active-track-reconcile-2026-07` (base origin/main, HEAD 665c90c35)
Worktree: `/Users/dhyana/ds_active_track_reconcile`
Verifier venv: `/Users/dhyana/dharma_swarm/.venv/bin/python`

Goal: kill LANDED-ONLY / existence-only ("rubber-stamp") gates. Every track kept
ACTIVE must carry at least one REAL behavioral criterion (`test_passes` /
`command_passes` / `receipt_valid` / `mutation_score_gte`) whose target EXISTS
and was RUN GREEN this session. `file_exists`/`file_contains`/`commit_on_main`
alone may not be the sole gate.

## Checker verdict

`python scripts/governance/check_track_status.py` -> **EXIT 0** (validates).
Findings: **0 ERROR**, 3 WARN (2 = spine coverage gaps for the two revenue/research
objectives that legitimately have no active track; 1 = mike underclaim), 7 INFO
(all "track-provisional / in-progress" — every ACTIVE track's criteria pass but
none auto-graduates to SHIPPABLE, which is correct: all have open blockers or are
provisional). Both `reports/governance/active_track_evidence.{md,json}` regenerated.

## Per-track dispositions applied

| Track | Disposition | New behavioral criterion | Target | Green output |
|-------|-------------|--------------------------|--------|--------------|
| loop-closure-2026-06 | KEEP AS-IS (already REAL) | (unchanged) test_passes + 12 json/receipt rigorous | tests/test_one_wire_archive_fitness_guard.py etc. | 29/29 criteria pass |
| orchestration-arena-v1-2026-06 | KEEP AS-IS (already REAL) | (unchanged) test_passes x2 + receipt_valid | tests/test_arena_v1.py, tests/test_arena_truth_report.py | 12/12 criteria pass |
| merge-master-mike-d4-2026-06 | UPGRADE-ADD-BEHAVIORAL | `github_review_bridge_test_passes`, `pr_merge_control_gate_fail_closed_test_passes` (test_passes) | tests/test_pr_merge_control_github_reviews.py + tests/test_pr_merge_control.py | 14 passed; 52 passed |
| organism-rewire-2026-07 | UPGRADE-ADD-BEHAVIORAL | `go_sense_organ_toolchain_closure_tests_pass` (test_passes) | tests/test_world_radar_go_bridge.py | 20 passed |
| dharmagraph-engine-2026-07 | KEEP AS-IS (already REAL) | (unchanged) test_passes x4 + command_passes | tests/test_graph_reconciler.py etc. | 7/7 criteria pass |
| helm-worldclass-terminal-2026-06 | UPGRADE-ADD-BEHAVIORAL (stranded -> fresh ACTIVE entry) | `terminal_tui_test_suite_passes`, `terminal_app_test_passes` (command_passes) + `terminal_behavioral_suite_landed` (commit_on_main) | `cd terminal && bun install --frozen-lockfile && bun test`; `... bun test tests/app.test.ts`; commit 1d8dae294 | 527 pass/0 fail exit 0; 208 pass/0 fail exit 0; ancestor of origin/main |
| sovereign-safety-tcb-2026-07 | PROPOSE-NEW-TRACK -> added ACTIVE | `evolution_fail_closed_tests_pass`, `pudgala_ai_m1_binding_tests_pass`, `pramana_phantom_gate_tests_pass`, `telos_kernel_tcb_tests_pass` (test_passes x4) | tests/test_evolution_safety.py; tests/test_claim_evidence_binding.py; tests/test_pramana_probe.py; packages/telos-kernel/telos_kernel/tests/ | 29 passed; 57 passed; 14 passed; 180 passed/3 skipped |

### NOT admitted as ACTIVE (recorded as proposed-hold comment block in the YAML)

| Track | Disposition | Reason |
|-------|-------------|--------|
| telos-ai-morning-refinery-2026-06 | CANT-MAKE-REAL | No shipped product code, no behavioral test; only real gate is an intentionally-absent external human receipt. Recommend design-hold/close. Its only "test" is a doc-lint (file_contains in test clothing) and cannot run on origin/main. |
| agent-admission-semantic-commons-2026-06 | KEEP-INCOMPLETE | Declared CORE (semantic_commons.py, agent_admission.py, test_agent_admission.py, test_semantic_commons.py) ABSENT on origin/main; all 16 existing criteria are file_exists/file_contains. One adjacent slice has a green test (tests/test_a2a_card_semantic_commons.py -> 4 passed) but presenting it as track completion would be a false positive. Recommend: resource the core, or split (CLOSE the naming slice as shipped + re-scope AgentAdmission). |

## Key engineering decision — dropped a recursive criterion

The proposed sovereign-safety-tcb block contained a 5th completion criterion
`final_boss_portfolio_selfgate_passes` = `command_passes: python3
scripts/governance/check_track_status.py`. The checker EXECUTES every
`command_passes` criterion (check_track_status.py:1710) and reads a FIXED path
(`REPO_ROOT/docs/governance/ACTIVE_TRACK.yaml`, line 36). Once this track is in
that file, evaluating that criterion makes the checker recursively invoke itself
-> infinite recursion / process explosion. It was DROPPED (kept as an explanatory
YAML comment). It carried grade 0 (command_passes is not in RIGOROUS_KINDS) and
was never load-bearing: the four `test_passes` criteria (S2/S3) already satisfy
the grade floor. Without this drop the checker would never terminate.

## Portfolio policy

`track_policy.warn_active` bumped 5 -> 7 (7 ACTIVE tracks now; still <= max_active 10).

## Tracks held back because a target was NOT green

None. Every behavioral criterion on every ACTIVE track ran GREEN. (mike shows 6/7
because the PRE-EXISTING existence criterion `mike_cloud_heartbeat` — file_contains
'schedule:' in merge-master-mike-backlog.yml — legitimately fails: Slice 4 cloud
heartbeat is unshipped. That is an honest in-progress signal, not one of the added
behavioral gates; both added mike test_passes are green.)

## Every ACTIVE track has a green behavioral floor (no sole-existence gate)

- loop-closure: test_passes + 12 json/receipt rigorous
- arena: test_passes x2 + receipt_valid
- mike: test_passes x2 (both green)
- organism-rewire: test_passes (green) + commit_on_main
- dharmagraph: test_passes x4
- helm: command_passes x2 (both green) + commit_on_main
- safety-tcb: test_passes x4 (all green)
