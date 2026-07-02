# Worktree Production-Readiness Plan

Repository: `AmitabhainArunachala/dharma_swarm`

Plan timestamp: `2026-06-30T04:29:24Z`

## Operating Rule

Preserve first, then promote. Dirty worktrees are evidence, not trash. The current rule is:

1. Do not delete a worktree or branch without a later explicit approval.
2. Do not discard dirty/untracked files.
3. Use the preservation packets as rollback evidence before rebasing, splitting, or archiving.
4. Promote only narrow branches with a clean worktree, current base, and matching tests.

## Immediate Production Order

1. **Done: #724 merged green.** This landed the focused #716 follow-up fix for the Python 3.11 sleep-cycle timeout.
2. **Done: #713 merged green.** This landed the quality-ratchet CI and baseline-freshness enforcement lane.
3. **#704 previously repaired, now conflicting again.** It remains draft and operator/Mike review gated; rebase again before any production merge.
4. **#719 previously repaired, now conflicting again.** Operator-only merge decision remains, and the branch needs a fresh rebase first.
5. **#718 previously repaired, now conflicting again.** Operator-only merge/archive decision remains, and the branch needs a fresh rebase first.
6. **Ready for operator decision: #723 clean draft.** Keep as draft until an explicit undraft/merge decision.
7. **Done: #727 merged green.** LangGraph parity readiness harness was repaired and merged.
8. **Done: #730 merged green.** Protected-branch DocOps count reconciliation after #727 landed through a normal PR.
9. **Done: #729 merged green.** A2A Agni live-contact fleet survey workflow was repaired and merged.
10. **Split dirty WIP into intentional branches:** isolate source changes from generated reports and local artifacts.
11. **Promote clean candidates only after rebase:** start with `/private/tmp/ds_loop` and `/Users/dhyana/worktrees/ds_reconciliation_promotion_20260626`.
12. **Archive only after approval:** clean gone-upstream and stale scratch worktrees can be archived later, but no deletion happened in this pass.

## PR Production Lanes

| PR | What it is | Next production step | Required proof |
| ---: | --- | --- | --- |
| #724 | Post-#716 sleep-cycle fix | Merged at `2026-06-29T17:12:58Z` | GitHub checks green; merge commit `11e84bbf6a0c9c9c4d2784119117e44a636ca1b8`. |
| #713 | Anti-slop quality-ratchet enforcement | Merged at `2026-06-29T17:50:02Z` | GitHub checks green; merge commit `359df82ac73f57ac953c41b4b9fe6d13452fbf2a`. |
| #704 | Pudgala/autopoiesis evidence gate | Draft, currently `DIRTY`/`CONFLICTING` | Was repaired and green earlier; later main merges made it conflicting again. Operator/Mike review required; rebase and rerun gates before merge. |
| #719 | SIS carbon-attribution projector | Operator-only, currently `DIRTY`/`CONFLICTING` | Was repaired and green earlier; later main merges made it conflicting again. Rebase and rerun gates before any operator merge. |
| #718 | Verified Nature House / SIS dossier | Operator-only, currently `DIRTY`/`CONFLICTING` | Was repaired and green earlier; later main merges made it conflicting again. Rebase and rerun gates before any operator merge. |
| #723 | Routing canon / Forge benchmark lane | `CLEAN`/`MERGEABLE` draft; keep operator-gated | GitHub CI green previously; decide undraft/merge or split/harden before production merge. |
| #727 | LangGraph parity readiness harness | Merged at `2026-06-29T20:22:29Z` | Merge commit `3c2e4a684e873320cc183b91c53c1fada35011a4`; focused local tests passed `61 passed`; GitHub CI green before merge; preservation branch `preserve/pr727-observed-20260630` remains. |
| #730 | Post-#727 DocOps count reconciliation | Merged at `2026-06-30T03:55:25Z` | Merge commit `1cb0fce59ca99f2a71834561ab1af45647eaab9d`; strict local DocOps/module-budget/manifest/ratchet/diff-check passed on `origin/main`; GitHub CI green before merge. |
| #729 | A2A Agni live-contact fleet survey workflow | Merged at `2026-06-30T04:24:42Z` | Merge commit `17a55d3465c98b6e728fd1f5bca7ad86cbaac3b6`; preservation branch `preserve/pr729-pre-repair-20260630` remains; local workflow gates passed; GitHub CI green after rerunning a flaky 3.12 timeout. |

## Preserved Dirty Worktrees

All listed paths have preservation packets under `preservation_packets/`. Next step is to decide whether each packet becomes a focused PR, a report-only archive, or an explicitly discarded local artifact later.

| Worktree | Branch | Next action |
| --- | --- | --- |
| `/Users/dhyana/dharma_swarm` | `agent/magpie-seed` | Split high-value source work from generated campaign reports; do not rebase as one blob. |
| `/Users/dhyana/dharma_helm_build` | `helm/worldclass-20260612` | Preserve as WIP; inspect whether terminal/intent/governance changes are still unique. |
| `/Users/dhyana/dharma_swarm_cashclaw` | `cashclaw/revenue-hydra-v1` | Separate source change in `claude_cli.py` from revenue reports; verify no external-action risk. |
| `/Users/dhyana/dharma_swarm_live` | `organ/03-seat` | Commit or archive the handoff report after checking it is not duplicated elsewhere. |
| `/Users/dhyana/dharma_swarm_main` | detached | Move any unique governance receipts onto a named branch or archive receipt-only. |
| `/Users/dhyana/dharma_swarm_wt/render-on-demand` | `chore/render-on-demand-stop-churn-20260625` | Committed branch appears landed; preserve dirty local deltas before later archive approval. |
| `/Users/dhyana/dharma_ws_idea_spark` | `feat/operator-idea-spark-ingest` | Run focused quality-gate tests, then decide PR vs archive. |
| `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618` | `runtime-truth/nats-rebuild-preflight-20260618` | Decompose A2A/NATS surface before any production path. |
| `/Users/dhyana/ds_cleanup_convergence_20260625` | `codex/governance-fitness-ci-20260625-225920` | Fold useful governance reports into the current receipt set, then archive after approval. |
| `/Users/dhyana/ds_forge_proving_ground_10_10_20260626` | `codex/dharma-forge-proving-ground-10-10-20260626` | Split source/tests from generated outputs; rebase and run forge tests. |
| `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626` | `droid/dharma-forge-proving-ground-10-10-20260626` | Remove staged environment artifacts only after explicit approval; preserve source deltas. |
| `/Users/dhyana/ds_forge_v1_scoreboard` | `forge-v1/tokenbroker-scoreboard-20260620` | High-value but stale; isolate provider/model changes and run Forge v1 tests. |
| `/Users/dhyana/ds_routing_canon_20260630` | `codex/routing-canon-20260630` | Align with #723; split large Forge/model-routing changes if CI remains red. |
| `/Users/dhyana/ds_semantic_commons_100` | `codex/semantic-commons-livingdock-composer-100` | Split broad semantic-commons WIP into smaller reviewable changes. |
| `/Users/dhyana/ds_supplychain_slice` | `loop-closure/supplychain-bronze-20260620` | Confirm bronze work already landed/superseded, then archive only after approval. |
| `/Users/dhyana/worktrees/ds_cockpit_grafana_static_20260626` | `scratch/cockpit-grafana-static-20260626` | Preserve static artifact; decide whether it is useful or disposable scratch. |
| `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` | `repair/pr674-track-closure-gate-20260624` | Compare against PR #674 state; archive if no unique fix remains. |
| `/Users/dhyana/worktrees/pr689_closure` | `pr-689-closure` | Compare against PR #689 closure state; archive if receipts are duplicated. |
| `/Users/dhyana/ds_pudgala_autopoiesis_20260626` | unknown checkout | Align with #704 and preserve any unique local receipts. |
| `/Users/dhyana/migration_delta/dharma_swarm_old` | old migration checkout | Treat as migration evidence; do not delete until unique files are compared. |

## Clean or Lower-Risk Promotion Candidates

| Worktree | Branch | Plan |
| --- | --- | --- |
| `/private/tmp/ds_loop` | `ratchet/loop-phases-1-3` | Rebase on `origin/main`, run loop/governance tests, then open a focused PR if still unique. |
| `/Users/dhyana/worktrees/ds_reconciliation_promotion_20260626` | `codex/reconciliation-promotion-20260626` | Docs-only candidate; restore PR or archive as receipt after confirming no duplicate. |
| `/Users/dhyana/dharma-debug-corral` | `claude/debug-corral` | Clean, live remote; needs owner decision and targeted tests before promotion. |
| `/Users/dhyana/dharma_swarm_oz_integration` | `oz/integration-2026-06-25` | Clean but upstream gone; archive unless unique integration proof remains. |
| `/Users/dhyana/ds_mike_nonstop_20260626` | `codex/mike-nonstop-dedupe-20260626` | Clean but upstream gone; archive or recreate PR with proof. |
| `/Users/dhyana/worktrees/ds_a2a_governance_readiness_20260626` | `codex/a2a-governance-readiness-20260626` | Clean but upstream gone; compare for unique readiness work. |
| `/Users/dhyana/worktrees/ds_mike_arbiter_20260626` | `governance/mike-trust-arbiter-2026-06` | Clean but upstream gone; archive or recreate PR with proof. |

## Definition Of Production-Ready

A worktree or branch is production-ready only when all of these are true:

- Clean Git state except intentional committed changes.
- Based on current `origin/main`.
- No merge conflicts.
- Narrow local tests pass for the touched surface.
- GitHub CI is green or every non-green check is proven unrelated and documented.
- PR is not draft.
- Rollback path is clear: branch, commit, bundle, and preservation packet exist.

Current state: #724, #713, #727, #730, and #729 are production-ready and merged. #723 is `CLEAN`/`MERGEABLE` but draft/operator-gated. #704 is draft and currently conflicting. #718 and #719 reserve operator merge authority and are currently conflicting. No remaining open PR should be merged automatically when it is draft or reserves operator merge authority.

## Addendum 2026-06-30T16:43:46Z

This addendum supersedes the stale "currently conflicting" statements above for #704/#718/#719. After the later mainline movement, all four existing operator-gated PRs were repaired again from isolated worktrees and pushed with `--force-with-lease` after local verification.

Current open PR lanes:

| PR | Current disposition | Head | Proof / blocker |
| ---: | --- | --- | --- |
| #704 | Green draft awaiting operator/Mike review | `ffe3ad358aa5ed10f425bdc197a87b8e4fb233c6` | GitHub CI green; local focused suite and governance gates passed. |
| #718 | Green/operator-gated | `f59972b6caf900fc0f2859ec06c835cc43263093` | GitHub CI green; PR body reserves operator-only merge authority. |
| #719 | Green/operator-gated | `c7863e51e5ac670ec20e5ef1eab3010e5332aacc` | GitHub CI green after rerunning a transient Python 3.11 failure; PR body reserves operator-only merge authority. |
| #723 | Green draft awaiting operator | `29bd36aa687c7aca8806464822e7e498322a89dd` | GitHub CI green; draft/operator undraft gate remains. |
| #732 | Blocked draft | `a9f94781cc85589976227112cc6dd9a072b8753e` | Module budget, quality ratchet, Fourfold warrant, and pytest ratchet conformance fail. Preserve branch: `preserve/pr732-observed-20260630`. |

Current worktree/packet snapshot:

- `worktree_status_20260701.json` regenerated at `2026-06-30T16:43:46Z`.
- Worktrees: 40.
- Open PRs: 5.
- Preservation packets: 28.
- Unpacketized dirty worktrees: 0.
- Newly packeted during this addendum: `/Users/dhyana/ds_forge_nvidia_foundry_mvp_20260701`, `/Users/dhyana/ds_forge_spine_v0`, `/Users/dhyana/ds_forge_prod_contracts_20260701`, and the current dirty state of `/Users/dhyana/ds_langgraph_parity_20260701`.

#732 blocker details:

```bash
make module-budget
# Rule 10 violation: dharma_swarm/orchestrator.py is 3252 lines, above ceiling 3215.

/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/hygiene/ratchet.py --json
# FAIL: modules_over_500_lines 207 -> 209; boundary_unfrozen_records 7 -> 8.

gh run view 28460433907 --repo AmitabhainArunachala/dharma_swarm --job 84346527733 --log
# pytest (3.11): FAILED tests/conformance/test_repo_ratchet_holds.py::test_repo_quality_ratchet_has_no_regressions
# modules_over_500_lines baseline=207 current=209; boundary_unfrozen_records baseline=7 current=8.

gh run view 28460433907 --repo AmitabhainArunachala/dharma_swarm --job 84346527786 --log
# pytest (3.12): same conformance failure and same two ratchet regressions.
```

Next production move for #732: decompose the hot-path runtime topology changes so `orchestrator.py` no longer grows past the grandfathered module ceiling, keep `modules_over_500_lines` at or below 207, add schema versions/frozen records for new runtime-state boundary records, and then rerun module budget, quality ratchet, Fourfold warrant, focused runtime/topology tests, and full CI.
