# Worktree Triage Report — 2026-06-10

**Inputs:** `reports/worktree_triage_manifest_2026-06-10.json` (83 worktrees) + fleet verdicts (multi-agent review of worktrees needing eyes).
**Executor script:** `scripts/governance/worktree_cleanup_2026-06-10.sh` (NOT yet run).
**Compost destination:** `~/.claude/cabinet/_compost/worktrees_2026-06-10/`

## Summary

| Category | Count | Action |
|---|---|---|
| **Provably removable** (dirty=0, untracked=0, head on GitHub) | 29 | `git worktree remove` (no `--force`; failures logged + skipped) |
| **GOLD** (active/substantive work) | 12 (incl. primary) | NEVER touched. Surfaced for operator. |
| **BUNDLE** (preserve then remove) | 11 | tar dirty+untracked → git bundle → `worktree remove --force` |
| **UNSURE** (operator decides) | 3 | Untouched. |
| **Protected** (`dharma_swarm` primary, `dharma_swarm_live` daemon) | 2 | Never touched. Daemon cwd is `/Users/dhyana/dharma_swarm`. |
| **No verdict, not provably removable** (untouched this pass) | 27 | Left in place; candidates for a second triage pass. |
| **Total** | **83** | |

Disk recoverable this pass: roughly 2.0 GB from provably-removable + ~2.5 GB from BUNDLE (boardstore_spec alone is 646 MB).

## GOLD — never touched (operator: this is where the live value is)

| Path | Why GOLD | Notable files |
|---|---|---|
| `/Users/dhyana/dharma_swarm` | Primary worktree, 58 dirty / 260 untracked on qwen/spine-adoption; WIP infra changes not on GitHub. Daemon cwd. | orchestrator.py, evolution.py, api_keys.py, witness.py, pulse.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516` | Conflicted verdicts (3 GOLD / 2 BUNDLE) → kept GOLD. 18 dirty files; prod_preflight.py + memory_kernel readiness/hardening; commits Jun 9-10 on the preflight lane. | scripts/prod_preflight.py, memory_kernel/adapters/file_snapshot.py, tests/test_prod_preflight.py, memory_kernel/facade.py, memory_kernel/readiness.py |
| `/Users/dhyana/dharma_swarm_cashclaw` | Unanimous GOLD (4 passes). Live revenue-hydra loop; scan script modified Jun 8; 13 generated evolution reports Jun 8-10; 8 ahead of main, not on GitHub. | scripts/revenue/cashclaw_multi_platform_scan.py, scripts/revenue/cashclaw_revenue_hydra.py, reports/revenue_wedge/evolution/20260610T112428Z/ |
| `/Users/dhyana/dharma_swarm_opus_identity` | opus persistent-agent level-up WIP (Jun 7); agent_runner.py + agent_memory_manager.py refactor; not on GitHub. | agent_runner.py, agent_memory_manager.py, tests/test_agent_memory_manager.py |
| `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v1` | Runtime Truth Spine v1 in-flight (7 dirty, 3 untracked). New spine/identity.py (ExecutionIdentity join-key) + tests + report. | spine/identity.py, tests/test_runtime_truth_spine_v1.py, reports/governance/runtime_truth_spine_v1_report.md, a2a/node_gateway.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr323` | 3 GOLD / 1 UNSURE → GOLD. May 28 dkeys/evolution/dgm_loop repair, 15 ahead, NOT on GitHub; unique ADR-0002 + boot-sub-swarm plan docs exist nowhere else. | docs/architecture/adr/0002-trace-coverage-gate.md, docs/plans/2026-05-28-boot-sub-swarm-dry-run-plan.md, evolution.py, dgm_loop.py, diff_applier.py |
| `/Users/dhyana/dharma_capital_lab` | Unanimous GOLD. honest_evidence.py (Bailey-Lopez de Prado DSR, Jun 6-7) + acceptance tests, untracked; 127 ahead, not on GitHub. Core Capital Lab R3 gate work. | capital_lab/honest_evidence.py, tests/test_capital_lab_honest_evidence.py, capital_lab/risk_governor.py, capital_lab/broker_paper_membrane.py |
| `/Users/dhyana/.qwen/worktrees/holon-agent` | 1 UNSURE / 1 GOLD → GOLD (conservative). Sovereign holon implementation staged, head NOT on GitHub (946e876), clean tree but commits unexported. | dharma_swarm/holon/, tests/test_holon_*.py, ACTIVE_SURFACE_MANIFEST.yaml |
| `/Users/dhyana/dharma_swarm_governed_recursive_proof` | Recursive-discovery proof lane; large additions (recursive_discovery.py +673 lines, swarm_integrity_benchmark.py 736 lines) not merged; head not on GitHub. | recursive_discovery.py, swarm_integrity_benchmark.py, operator_core/control_surface_recursive.py |
| `/Users/dhyana/worktrees/dharma_swarm_honest_spine_v2` | Jun 10 WIP — spine v2 provider message-extraction refactor across 6 OpenAI-compatible providers; 2 dirty, ahead 1, not on GitHub. | providers.py, providers_extended.py, pulse.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516` | 5 dirty + 4 untracked experimental control-surface code (control_surface_recursive.py, benchmark, shadow foundry). | operator_core/control_surface_recursive.py, swarm_integrity_benchmark.py, scripts/recursive_shadow_foundry.py |
| `/Users/dhyana/dharma_swarm_substrate_spec` | Unanimous GOLD on second pass. SWARM_SUBSTRATE.md spec (new) + 5 dirty governance docs; recent commit Jun 6. | docs/architecture/SWARM_SUBSTRATE.md, docs/governance/CANONICAL_DOC_STACK.md, docs/docops/assertions.yaml |

## BUNDLE — tar uncommitted files + git bundle, then remove

| Path | Why BUNDLE |
|---|---|
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_codex_lane_runner` | Clean; May 13 codex lane runner; 312 behind; head NOT on GitHub (bundle preserves the 3 ahead commits). |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_interop_fleet` | Clean; May 12 interop-fleet review branch; 618 behind; not on GitHub. |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_knowledge` | Clean; May 12 memory-knowledge review branch; 618 behind; not on GitHub. |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr325` | Clean; May 19 pr-325-toolbelt repair; 256 behind; head NOT on GitHub (4 ahead — bundle preserves). |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_root_governance_residue` | Clean; parked governance cleanup residue; not on GitHub (107 ahead of stale base — bundle preserves). |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_viz_invariant` | Clean; viz invariant projection complete; not on GitHub — bundle preserves. |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe2_20260524` | Stale May 24 probe, detached, 8 dirty incl. merge-conflict (UU) docs + docops inventory; superseded. Tar dirty files + bundle HEAD. |
| `/Users/dhyana/dharma_swarm-go-ingest-spine-clean` | Clean; Jun 4 go-ingest-spine PoC, evaluated; head not on GitHub — bundle preserves. |
| `/Users/dhyana/dharma_swarm_boardstore_spec` | 2 dirty files = regenerated active_track_evidence.{json,md}; head on GitHub; 646 MB mostly data. Tar the 2 files, bundle, remove. |
| `/Users/dhyana/worktrees/dharma_swarm_spine_slice_c` | Spine slice C done (runlog/wording docs); clean; NOTE: manifest says head NOT on GitHub (3 ahead) — bundle preserves regardless. |
| `/Users/dhyana/promotion_worktrees/dharma_swarm_mask_prereg` | Stale exploratory R_V whitebox secondary analysis (1 untracked file, May 15, 26 days). Tar the file, bundle, remove. |

## UNSURE — untouched, operator decides

| Path | Question for operator |
|---|---|
| `/Users/dhyana/worktrees/dharma_swarm_spine_slice_b` | Clean but head 6c793fa NOT on GitHub; completed adapter-saturation experiment? Push branch or bundle? |
| `/Users/dhyana/dharma_swarm_main_cutover` | Conflicting verdicts (GOLD vs BUNDLE). 20 dirty hot-path files (agent_runner, orchestrate_live, providers, swarm, evolution) but 332 behind main — active recovery work or abandoned May cutover test? |
| `/Users/dhyana/dharma_swarm_pr_review_control` | Conflicting verdicts (GOLD vs BUNDLE). 3 dirty docs + FRONTIER_AGENT_DOSSIER.md + dharma_swarm_agent_spine/ agents dir; head not on GitHub. Governance surface — is the hygiene-lifecycle-v2 lane still live? |

## Provably removable (dirty=0, untracked=0, head on GitHub) — 29

Script removes these with plain `git worktree remove` (no `--force`); any failure is logged and skipped.

1. `/private/tmp/chetana-restoration`
2. `/Users/dhyana/.dharma/codex_lanes/worktrees/cleanup-audit`
3. `/Users/dhyana/.dharma/marathon/repo` ⚠️ marathon harness checkout — if a marathon process is live it will fail non-force and be skipped (intended)
4. `/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_hardening_20260523`
5. `/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_discovery`
6. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr314`
7. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr320`
8. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr324`
9. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr326`
10. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr327`
11. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr328`
12. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr338`
13. `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr341`
14. `/Users/dhyana/cleanup_worktrees/dharma_swarm_route_witness_main`
15. `/Users/dhyana/dharma_swarm_brakes`
16. `/Users/dhyana/dharma_swarm_budget_fix`
17. `/Users/dhyana/dharma_swarm_codex_mention_main`
18. `/Users/dhyana/dharma_swarm_core_scan`
19. `/Users/dhyana/dharma_swarm_dgmd_smoke_20260514T045353Z`
20. `/Users/dhyana/dharma_swarm_integrate_chetana`
21. `/Users/dhyana/dharma_swarm_lak_e2e`
22. `/Users/dhyana/dharma_swarm_main_verify`
23. `/Users/dhyana/dharma_swarm_pr319`
24. `/Users/dhyana/dharma_swarm_tcs_heartbeat`
25. `/Users/dhyana/dharma_swarm_trace_attractor_causal_spine`
26. `/Users/dhyana/ds_ws4` ⚠️ WS4a / PR #558 worktree — clean and head on GitHub so removal loses nothing (branch ref survives), but if you intend more local WS4b work here, pull it from this list before running
27. `/Users/dhyana/promotion_worktrees/dharma_swarm_go_g06_local_model_inventory`
28. `/Users/dhyana/promotion_worktrees/dharma_swarm_runtime_projector`
29. `/Users/dhyana/worktrees/dharma_swarm_spine_slice_a`

## Untouched this pass (no verdict, not provably removable) — 27

Left in place; second triage pass candidates: dharma_swarm_identity, memory_kernel_default_context_20260523, pr_queue_probe_20260524, proof_artifacts, route_witness, worker4_pr323_codeql, worker4_pr332_codeql, world_radar_live, action_authority_spec, cwt_v0, governed_memory_recursive_integration, kaizen_review, moltbook_research_wt, opus_traverse, pr326, pr_392, pr_398, pr_399, toolbelt_push, truth_spine, ds_ws3 (WS3 merged — likely next-pass removable), chetana-wiki-verify, kaizen_exec_loop_pr, live_ops_cockpit_v1, live_ops_cockpit_v1_docops_fix, live_ops_cockpit_v2, runtime_truth_spine_v2.

## Safety properties of the script

- Never uses `--force` on provably-removable paths; failures are logged and skipped.
- BUNDLE paths get BOTH a tar of uncommitted files AND a full `git bundle` of HEAD before `--force` removal — nothing is destroyed, everything routes to compost (kill-nothing/metabolize doctrine).
- GOLD and UNSURE paths are hard-coded into a deny-list; the script refuses to act on them even if mislisted.
- `/Users/dhyana/dharma_swarm` and `/Users/dhyana/dharma_swarm_live` are protected; the daemon cwd is `/Users/dhyana/dharma_swarm` — check `dgc status` / running processes before executing.
- Idempotent: re-running skips already-removed paths and already-written archives.

## Second pass 2026-06-11

**Inputs:** fleet verdicts on the second-pass worktrees (the "untouched this pass" set above).
**Executor script:** `scripts/governance/worktree_cleanup_second_pass_2026-06-11.sh` (NOT yet run).
**Compost destination:** `~/.claude/cabinet/_compost/worktrees_2026-06-11/`

| Category | Count | Action |
|---|---|---|
| **GOLD** | 14 | NEVER touched. Hard-coded into deny-list. |
| **BUNDLE** | 12 | tar dirty+untracked → git bundle → `worktree remove --force` |
| **UNSURE** | 3 | Untouched. Hard-coded into deny-list. Operator decides. |

Note: `world_radar_live` received conflicting verdicts (GOLD + BUNDLE) from two fleet lanes → demoted to UNSURE, same rule as `main_cutover` in the first pass. Three first-pass GOLDs (`memory_kernel_preflight_20260516`, `recursive_evolution_20260516`, `repair_pr323`) were re-confirmed GOLD by the second-pass fleet and remain in the deny-list.

### GOLD (second pass) — never touched

| Path | Why GOLD | Notable files |
|---|---|---|
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_identity` | 107 unmerged commits on `cleanup/identity-onboarding-2026-05-12`: agent online identity anchor + catalytic-graph parent-selection bias + evolution test fixes. Not merged to main. | .github/workflows/agent-online-integrity.yml, dharma_swarm/agent_identity_spec.md |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516` | Re-confirmed GOLD. Vaulted work Jun 10; strict kernel readiness (`fix(memory): require strict readiness in operator smoke`), new memory_kernel adapters + prod_preflight.py. Active operator work. | memory_kernel/adapters/file_snapshot.py, memory_kernel/readiness.py, scripts/prod_preflight.py, tests/test_memory_kernel_readiness.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_proof_artifacts` | 107 unmerged commits on `review/proof-artifacts-2026-05-12`; agentic immune proof artifacts parked; ACTION_REQUIRED doc with Welfare-ton MRV blocking analysis exists nowhere else. | campaigns/ACTION_REQUIRED_2026-05-10.md |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516` | Re-confirmed GOLD. Vaulted Jun 10; catalytic-graph parent-selection bias (spine §9 closure) + evolution/selection/memory-kernel work. | dharma_swarm/catalytic_graph.py, dharma_swarm/evolution.py, tests/test_catalytic_selection.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr323` | Re-confirmed GOLD. Vaulted Jun 10; dkeys analyzer-safe export security fix + targeted PR #323 repair. | scripts/normalize_dkeys_env.py, tests/test_env_alias_normalization.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_route_witness` | 107 unmerged commits incl. `feat(routing): add route witness telemetry` — phase-1 routing witness feature, not on main. | dharma_swarm/inquiry_substrate_chew.py, docs/plans/2026-05-10-phase1-routing-witness.md |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_worker4_pr323_codeql` | Live repair lane for PR #323 (dkeys security); CodeQL analyzer-compat fix, focused diff, NOT merged. | scripts/normalize_dkeys_env.py, tests/test_env_alias_normalization.py |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_worker4_pr332_codeql` | Live repair lane for PR #332; ADR-007 (autoproposer darwin submission) + cwt_collect/cwt_report runtime tooling (921 new lines), NOT merged. | scripts/runtime/cwt_collect.py, scripts/runtime/cwt_report.py, docs/ADRs/ADR-007-autoproposer-darwin-submission.md |
| `/Users/dhyana/dharma_swarm_governed_memory_recursive_integration` | 7 commits May 13-17, 12,051 lines across 44 files: memory_kernel + recursive_proof_ontology + 9 test modules; 11 dirty (incl. Makefile, SOVEREIGN_MANIFEST) + 17 untracked — active development, possibly unmerged. | assurance/recursive_proof_ontology.py, memory_kernel/__init__.py, scripts/memory_kernel_plan_observer.py, tests/test_memory_context_eval.py |
| `/Users/dhyana/dharma_swarm_opus_traverse` | 123 commits May 21–Jun 3 tracking `origin/capital-lab/build`: operator-os preflight closure, A2A, runtime_truth, command-plane infra; untracked pre-commit-blocked fix ledger needs operator visibility. | reports/audit/2026-06-05_opus_traverse_fix_ledger.md, a2a/nats_transport.py, dashboard/src/hooks/useCommandPlaneTruth.ts, api/routers/goodworks_dgm.py |
| `/Users/dhyana/dharma_swarm_truth_spine` | LOCAL-ONLY `chore/agent-truth-spine`, 97 substantive commits ahead of main: operator command spine v0, agent truth spine, work packet runner; no open PR — operator intent/merge/compost decision needed. | operator_core/command_spine.py, docs/governance/OPERATOR_COMMAND_SPINE.md, tests/test_operator_command_spine.py, a2a/a2a_server.py |
| `/Users/dhyana/worktrees/chetana-wiki-verify` | `fix/chetana-wiki-multiroot`, 10+ unique commits Jun 1-8: unified query across multiple wiki roots, fairness-fixed round-robin merge, defect fixes; 68/68 tests passing; not on origin, not merged. | chetana/graph_unifier.py, chetana/cli.py, chetana/README.md |
| `/Users/dhyana/worktrees/dharma_swarm_kaizen_exec_loop_pr` | `codex/kaizen-exec-loop-20260601`, 1 unique Jun 1 commit: `feat(kaizen): bind reviews to runtime truth refs` — active-track kaizen exec loop work, not on origin. | dharma_swarm/kaizen/ |
| `/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v2` | `codex/live-ops-cockpit-v2-slice-d`, 7 unique commits Jun 1-5: typed ProposalPacket + ControlSurfaceRow, decision buckets, PR-queue projection — most advanced cockpit iteration, not on origin/main. | operator_core/control_surface_proposals.py, dashboard/src/components/cockpit/OpsDecisionModel.ts, OpsRunbookPanel.tsx |

### BUNDLE (second pass) — tar uncommitted + git bundle, then remove

| Path | Why BUNDLE |
|---|---|
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_default_context_20260523` | Merge-only lane (merges from main #338); no independent work. |
| `/Users/dhyana/dharma_swarm_action_authority_spec` | Stale May 4-5 governance branch (`chore/action-authority-gate-spec`); orphaned, no open/recent PRs, predates current governance work. |
| `/Users/dhyana/dharma_swarm_cwt_v0` | CWT v0 collector merged to main via PR #324 (2026-05-24); worktree superseded. |
| `/Users/dhyana/dharma_swarm_moltbook_research_wt` | May 20 R_V calibration / SAB investigation research docs; documentation-focused, 3+ weeks stale — extract via compost rather than keep as orphaned worktree. |
| `/Users/dhyana/dharma_swarm_pr326` | Detached HEAD on origin/main; 1 stale docs commit (May 21); refetchable from origin. |
| `/Users/dhyana/dharma_swarm_pr_392` | Dead codex repair branch (`codex/repair-pr-392`, local-only, 2 minimal commits); PR #392 merged 2026-06-05. |
| `/Users/dhyana/dharma_swarm_pr_398` | Dead codex repair branch (`codex/fix-pr-398-coherence`, local-only); PR #398 merged 2026-06-01. |
| `/Users/dhyana/dharma_swarm_pr_399` | Dead codex repair branch (`codex/repair-pr-399`, local-only); PR #399 merged 2026-06-01. |
| `/Users/dhyana/dharma_swarm_toolbelt_push` | Stale codex onboarding branch, origin branch `[gone]`, 1 doc commit, no unique work. |
| `/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v1` | 2 unique commits of cockpit scaffolding superseded by v2 (GOLD above); intermediate working point — bundle preserves. |
| `/Users/dhyana/worktrees/dharma_swarm_live_ops_cockpit_v1_docops_fix` | 3 unique commits of tactical docops gate fixes layered on v1; superseded by v2 — bundle preserves. |
| `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` | HEAD (2ea5a8e8f) already merged on origin/main; 2 dirty files are pre-commit-blocked generated governance reports (Jun 7) — tarred before removal. |

### UNSURE (second pass) — untouched, operator decides

| Path | Question for operator |
|---|---|
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe_20260524` | PR-queue probe worktree (detached, merge from pr-338, May 24); no substantive independent work visible — were the probe findings captured elsewhere? |
| `/Users/dhyana/dharma_swarm_kaizen_review` | 96 commits Apr 6–May 5 (ontology, control surface, graphql, fleet routing). PR #431 merged kaizen binding 2026-06-05 — is this branch (a) fully merged via multiple PRs, (b) a parallel implementation, or (c) outdated? |
| `/Users/dhyana/cleanup_worktrees/dharma_swarm_world_radar_live` | CONFLICTING verdicts: GOLD lane says 1 unmerged commit (world-scout cron + zeitgeist radar consolidation, May 13); BUNDLE lane says PR #296 merged the feature to main May 14. Resolve: is `1ff15b98d` represented in #296? |

### Safety properties (second-pass script)

- Same idempotent pattern as the first-pass script: re-running skips already-removed paths and already-written archives.
- All GOLD + UNSURE paths (both passes) hard-coded into the deny-list; script refuses to act on them even if mislisted.
- Protected, always refused: `/Users/dhyana/dharma_swarm`, `/Users/dhyana/dharma_swarm_live`, `/Users/dhyana/ds_ws3`, `/Users/dhyana/ds_ws4`, and any `/Users/dhyana/ds_stitch_*` path (prefix-matched).
- BUNDLE paths get BOTH a tar of dirty+untracked files AND a full `git bundle` of HEAD before `--force` removal — kill-nothing/metabolize doctrine; everything routes to `~/.claude/cabinet/_compost/worktrees_2026-06-11/`.
