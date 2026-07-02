# Dharma Swarm Final Readiness Matrix - 2026-06-30

Agent 6 verifier pass, with coordinator reconciliation after Agent 1-5 receipts landed.

Coordinator reconciliation at `2026-06-29T16:09:36Z`:

- Present lane receipts: `inventory.json`, `open_prs.md`, `ci_repair_log.md`, `dirty_worktrees.md`, `branch_cemetery.md`, `promotion_candidates.md`.
- Inventory count proof after live-state refresh: 26 registered worktrees, 239 local branches, 13 open PRs, 18 dirty registered worktrees, 8 clean registered worktrees. The newly observed checkout is `/Users/dhyana/ds_routing_canon_20260630` on `codex/routing-canon-20260630`; it tracks `origin/main`, has zero ahead/behind, has no open PR, and is dirty with 18 modified tracked files plus 9 untracked status entries.
- Pre-refresh inventory count proof retained for provenance: 25 registered worktrees, 238 local branches, 17 dirty registered worktrees, 54 live-upstream branches, 68 deleted-upstream branches, 116 no-upstream branches.
- Dirty-worktree receipt scope: 20 dirty Dharma-family checkouts identified after live-state refresh, consisting of 18 dirty registered worktrees plus 2 additional dirty Dharma-family checkouts from a shallow `/Users/dhyana` scan. It also records one stale temporary pytest worktree path that was missing at inspection time.
- Branch cemetery scope: 184 stale branches classified, from 68 deleted-upstream plus 116 no-upstream branches.
- PR/CI scope: all 13 open PRs have dispositions; no PR is `MERGE_READY`.
- Promotion scope: all 7 named candidates have ranked dispositions and next verifier commands.

The score tables below remain first-pass scores because no rebases, local test suites, merge simulations, branch deletions, PR closures, pushes, or source fixes were authorized or performed.

## Rubric

Total: 100 points.

- 20: clean Git state, or explicit preserved WIP receipt
- 15: current base, or concrete rebase plan
- 15: narrow tests pass
- 15: full CI green, or exact failing checks known
- 10: no conflicts, or mergeability known
- 10: risk and rollback documented
- 10: ownership / PR / archive decision clear
- 5: no duplicate or superseded drift

Scoring policy: missing evidence is scored low. Draft PRs are not release-ready without an operator decision. Merge conflicts, dirty worktrees without a preserved WIP receipt, absent local test evidence, gone upstream branches, and duplicate ops-report branches cap scores even when some other signals are good.

## Evidence Commands Rerun

Required independent checks were rerun directly by this verifier.

```bash
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm remote -v
git -C /Users/dhyana/dharma_swarm status --short --branch
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
git -C /Users/dhyana/dharma_swarm log -1 --format='%H %ci %s' origin/main
gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --limit 100 --json number,title,headRefName,baseRefName,mergeStateStatus,isDraft,updatedAt,url,headRefOid --jq '...'
gh pr checks <PR> --repo AmitabhainArunachala/dharma_swarm --json name,state,link --jq '...'
gh pr view 716 --repo AmitabhainArunachala/dharma_swarm --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus,reviewDecision,updatedAt,commits,files,url --jq '...'
git -C /Users/dhyana/dharma_swarm branch -vv --list 'chore/render-on-demand-stop-churn-20260625'
git -C /Users/dhyana/dharma_swarm cherry -v origin/main chore/render-on-demand-stop-churn-20260625
git -C /Users/dhyana/dharma_swarm log --oneline --decorate -5 chore/render-on-demand-stop-churn-20260625
git -C /Users/dhyana/worktrees/ds_reconciliation_promotion_20260626 diff --stat origin/main...HEAD
git -C /Users/dhyana/worktrees/ds_reconciliation_promotion_20260626 status --short --branch
```

Evidence limits:

- The first `gh pr list` attempt used `dhyana/dharma_swarm` and failed because the actual remote is `AmitabhainArunachala/dharma_swarm`; it is ignored as non-evidence.
- One batch `git status` loop used the zsh special variable name `path`, which clobbered `PATH`; it is ignored as non-evidence and was rerun with `wt`.
- I did not run local test suites for dirty worktrees. Test scores for PRs come from GitHub checks; local worktree test scores are low unless explicit evidence was visible.
- I did not run merge simulations or rebases. Mergeability uses GitHub `mergeStateStatus` for PRs and local branch tracking/cherry/log evidence for the selected stale branch.
- `origin/main` in this checkout resolved to `bd121c8279fcd0ad712d6cc60fe0a69bc635be31` (`2026-06-28 14:49:47 +0000`, `governance: hardwire quality ratchet feedback edge (#698)`).
- No fixes, pushes, branch deletes, PR closes, deploys, or external actions were performed.

## Spot Checks

Dirty worktree: `/Users/dhyana/dharma_swarm` on `agent/magpie-seed`.

- `git status --short --branch` shows a large dirty tree: many modified files, one deleted test, many untracked implementation/test/report paths, and the readiness receipt directory itself untracked before this file was added.
- `git diff --stat` showed 60 tracked files changed with 4531 insertions and 369 deletions, excluding untracked files.
- Ready claim challenged: not release-ready until WIP is preserved or split into intentional PRs with tests.

Stale branch: `chore/render-on-demand-stop-churn-20260625`.

- `git branch -vv --list` shows it checked out at `/Users/dhyana/dharma_swarm_wt/render-on-demand`, tracking `origin/main`, behind 37.
- `git cherry -v origin/main chore/render-on-demand-stop-churn-20260625` returned no unique commits, indicating the branch tip is already contained in `origin/main` as far as committed history is concerned.
- `git log --oneline --decorate -5` shows HEAD `21ee18b36 ... (#685)`.
- However the worktree itself is dirty with modifications and deletions, so archive/delete is blocked until those local deltas are preserved or explicitly discarded by an operator.

PR spot-check: PR #716, `slice/roast-skill`.

- `gh pr view 716` shows draft, base `main`, `mergeStateStatus=UNSTABLE`, 2 commits, 2 files: `.warp/skills/roast/SKILL.md`, `docs/docops/assertions.yaml`.
- `gh pr checks 716 --json` shows exact failing check: `pytest (3.11)`. `pytest (3.12)` and the governance checks passed.
- Ready claim challenged: narrow and likely closeable, but not release-ready until the 3.11 failure is fixed or proven unrelated.

Promotion candidate spot-check: `/Users/dhyana/worktrees/ds_reconciliation_promotion_20260626`.

- `git status --short --branch` shows a clean worktree on `codex/reconciliation-promotion-20260626`, but upstream `origin/codex/reconciliation-promotion-20260626` is gone.
- `git diff --stat origin/main...HEAD` shows one docs file, 155 insertions: `...ON_RECONCILIATION_DECISION_PACKET_2026-06-26.md`.
- Ready claim challenged: clean and narrow, but not production-ready because there is no live PR/upstream branch decision.

## Open PR Matrix

| PR | Branch | State | CI evidence | Score | Blockers | Next operator decision |
|---:|---|---|---|---:|---|---|
| 722 | `ops/ops-report-2026-06-29T0600Z` | Draft, UNSTABLE | Failing: `Quality ratchet - repo-wide fitness function`, `pytest (3.11)`, `pytest (3.12)` | 43 | Draft; CI red; duplicate/supersedes older ops reports unclear | Keep only if this is the current ops report line; fix CI or archive in favor of a newer report |
| 720 | `ops/report-2026-06-28T1800Z` | Draft, UNSTABLE | Failing: `pytest (3.11)`, `pytest (3.12)`, `Quality ratchet - repo-wide fitness function` | 38 | Draft; CI red; likely superseded by #722 | Archive/close after operator confirms #722 or later report supersedes it |
| 719 | `claude/sis-seed1-carbon-attribution` | Open, BLOCKED | Failing: `DocOps integrity gate`, `pytest (3.11)`, `pytest (3.12)` | 32 | BLOCKED mergeability; CI red; no rollback evidence inspected | Needs rebase/conflict plan and DocOps/test repair before promotion |
| 718 | `claude/monetization-strategy-team-rgn7g6` | Open, BLOCKED | Failing: `DocOps integrity gate`, `Import-provenance third-party declaration ratchet`, `pytest (3.11)`, `pytest (3.12)` | 28 | BLOCKED; multiple governance/test failures | Do not merge; owner must decide repair vs archive |
| 717 | `ops/report-2026-06-27T1800Z` | Draft, BLOCKED | Failing: `pytest (3.12)`, `pytest (3.11)`, `DocOps integrity gate` | 30 | Draft; BLOCKED; older ops report likely superseded | Archive/close after choosing current ops report |
| 716 | `slice/roast-skill` | Draft, UNSTABLE | Failing: `pytest (3.11)` | 57 | Draft; one CI failure; risk/rollback not inspected | Good repair candidate; fix 3.11 failure and decide whether to undraft |
| 715 | `ops/report-2026-06-27T0000Z` | Draft, BLOCKED | Failing: `DocOps integrity gate` | 40 | Draft; BLOCKED; likely superseded by newer ops reports | Archive/close after operator confirms supersession |
| 714 | `ops/report-2026-06-26T1800Z` | Draft, CLEAN | All checks pass | 67 | Draft; older ops report likely superseded | Green but not release-ready; decide archive vs keep as historical receipt |
| 713 | `claude/anti-slop-enforcement-2026-06` | Open, DIRTY | Failing: `Quality ratchet whole-tree regression + baseline freshness` | 48 | Merge conflicts; quality gate red | Needs conflict resolution and quality-ratchet repair before merge |
| 710 | `chore/spine-adoption-metric-refresh` | Draft, UNSTABLE | Failing: `Quality ratchet - repo-wide fitness function`, `pytest (3.11)`, `pytest (3.12)` | 38 | Draft; CI red; duplicate metric-refresh drift likely | Archive unless this exact metric refresh is still needed |
| 708 | `oz/spine-metric-refresh-2026-06-26` | Draft, UNSTABLE | Failing: `pytest (3.11)`, `pytest (3.12)` | 42 | Draft; CI red; older metric refresh | Archive or rebase/test only if still semantically current |
| 706 | `ops/report-2026-06-26T0000Z` | Draft, CLEAN | All checks pass | 69 | Draft; old ops report likely superseded | Highest green ops-report candidate, but likely historical; choose archive vs retain |
| 704 | `codex/pudgala-autopoiesis-protostar-20260626` | Draft, DIRTY | All checks pass | 60 | Merge conflicts despite green CI; draft; broad governance surface | Needs rebase/conflict resolution before any ready claim |

## Checked-Out Worktree Matrix

| Worktree | Branch | Git state evidence | Score | Blockers | Next operator decision |
|---|---|---|---:|---|---|
| `/Users/dhyana/dharma_swarm` | `agent/magpie-seed` | Dirty, large tracked/untracked WIP | 18 | No clean state; no current base evidence; no local tests | Preserve WIP receipt or split into intentional PRs before any production claim |
| `/private/tmp/ds_loop` | `ratchet/loop-phases-1-3` | Clean; ahead 19, behind 23 vs `origin/main` | 54 | Needs rebase/PR/test evidence | Candidate for PR after rebase and narrow tests |
| `/Users/dhyana/dharma-debug-corral` | `claude/debug-corral` | Clean; tracks live remote | 52 | No PR/test/rollback evidence found | Decide PR vs archive; run targeted tests before promotion |
| `/Users/dhyana/dharma_helm_build` | `helm/worldclass-20260612` | Dirty modified terminal/intent/governance files plus untracked reports/tests | 26 | Dirty WIP; no preserved receipt found | Preserve WIP or abandon by explicit operator decision |
| `/Users/dhyana/dharma_swarm_cashclaw` | `cashclaw/revenue-hydra-v1` | Dirty `dharma_swarm/claude_cli.py` plus many untracked revenue reports | 22 | Dirty WIP; no tests; revenue risk surface | Preserve WIP receipt and decide whether reports are artifacts or source |
| `/Users/dhyana/dharma_swarm_live` | `organ/03-seat` | Dirty added handoff report | 35 | Not clean; no test evidence | Preserve/commit handoff or archive if already represented elsewhere |
| `/Users/dhyana/dharma_swarm_main` | detached | Dirty governance reports on detached HEAD | 18 | Detached dirty state; no owner/PR path | Preserve receipt, then move/PR or discard only with explicit approval |
| `/Users/dhyana/dharma_swarm_oz_integration` | `oz/integration-2026-06-25` | Clean; upstream gone | 45 | No live upstream/PR; no test evidence | Archive or recreate PR only if unique value remains |
| `/Users/dhyana/dharma_swarm_slice_roast` | `slice/roast-skill` | Clean; maps to PR #716 | 57 | PR #716 failing `pytest (3.11)` and draft | Repair PR #716 or archive the slice |
| `/Users/dhyana/dharma_swarm_wt/render-on-demand` | `chore/render-on-demand-stop-churn-20260625` | Dirty; committed branch has no unique cherry vs `origin/main`; behind 37 | 32 | Local dirty deltas block archive; committed tip already merged | Preserve or discard local dirty deltas by approval, then archive worktree/branch |
| `/Users/dhyana/dharma_ws_idea_spark` | `feat/operator-idea-spark-ingest` | Dirty modified `promote.py` plus untracked quality gate and tests | 32 | Dirty WIP; no PR/test evidence | Preserve WIP, run targeted tests, then decide PR |
| `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618` | `runtime-truth/nats-rebuild-preflight-20260618` | Dirty large A2A/NATS surface; behind 212 | 20 | Large dirty WIP, stale base, no test evidence | Must be preserved and decomposed before any production path |
| `/Users/dhyana/ds_cleanup_convergence_20260625` | `codex/governance-fitness-ci-20260625-225920` | Dirty governance reports; upstream gone | 30 | Dirty and orphaned; no test evidence | Preserve or fold into governance receipt, then archive |
| `/Users/dhyana/ds_forge_proving_ground_10_10_20260626` | `codex/dharma-forge-proving-ground-10-10-20260626` | Dirty Makefile/docs plus many untracked forge scripts/tests; behind 10 | 36 | Dirty WIP; no CI/PR evidence in this pass | Potential promotion track, but needs WIP receipt, rebase, tests |
| `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626` | `droid/dharma-forge-proving-ground-10-10-20260626` | Dirty staged adds including `.venv`; behind 10 | 22 | `.venv` staged; dirty duplicate-looking forge work | Preserve only source deltas; do not promote before cleanup |
| `/Users/dhyana/ds_forge_v1_scoreboard` | `forge-v1/tokenbroker-scoreboard-20260620` | Dirty broad provider/model surface; ahead 9, behind 212 | 28 | Stale base; dirty runtime/provider changes; no tests rerun | Needs isolation, rebase plan, and focused verification |
| `/Users/dhyana/ds_mike_nonstop_20260626` | `codex/mike-nonstop-dedupe-20260626` | Clean; upstream gone | 45 | No live PR/upstream; no test evidence | Archive if merged/superseded, or recreate PR with proof |
| `/Users/dhyana/ds_routing_canon_20260630` | `codex/routing-canon-20260630` | Dirty; tracks `origin/main`; zero ahead/behind; no PR; 18 tracked files changed plus 9 untracked entries | 28 | Dirty model-routing/Forge WIP with no branch commits yet | Preserve WIP or split into a candidate PR before cleanup |
| `/Users/dhyana/ds_semantic_commons_100` | `codex/semantic-commons-livingdock-composer-100` | Dirty broad semantic commons WIP; behind 23 | 34 | Dirty broad surface; no current PR evidence | Preserve WIP and split into smaller promotion candidates |
| `/Users/dhyana/ds_supplychain_slice` | `loop-closure/supplychain-bronze-20260620` | Dirty governance/test/report changes; upstream gone | 32 | Orphaned upstream and dirty local deltas | Preserve deltas; archive only after confirming bronze work is landed/superseded |
| `/Users/dhyana/worktrees/ds_a2a_governance_readiness_20260626` | `codex/a2a-governance-readiness-20260626` | Clean; upstream gone | 45 | No live PR/test evidence | Archive or recreate PR only if unique readiness work remains |
| `/Users/dhyana/worktrees/ds_cockpit_grafana_static_20260626` | `scratch/cockpit-grafana-static-20260626` | Dirty untracked `cockpit_static/` | 30 | Untracked artifact tree; no tests/owner decision | Preserve artifact receipt or archive scratch lane |
| `/Users/dhyana/worktrees/ds_mike_arbiter_20260626` | `governance/mike-trust-arbiter-2026-06` | Clean; upstream gone | 45 | No live PR/test evidence | Archive or recreate PR if arbiter work is still needed |
| `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` | `repair/pr674-track-closure-gate-20260624` | Dirty governance reports and `uv.lock`; upstream gone | 26 | Dirty orphaned rebase lane | Preserve/compare against landed PR #674, then archive |
| `/Users/dhyana/worktrees/ds_reconciliation_promotion_20260626` | `codex/reconciliation-promotion-20260626` | Clean; upstream gone; one docs diff, 155 insertions | 58 | No live PR/upstream; no tests, though docs-only | Best promotion candidate: create/restore PR or archive as receipt |
| `/Users/dhyana/worktrees/pr689_closure` | `pr-689-closure` | Dirty governance reports; no upstream shown | 26 | Dirty local closure lane; no PR/test evidence | Compare with PR #689 state, preserve if unique, then archive |

## Unsupported Ready Claims Challenged

- No open PR should be called production-ready in this pass. #706 and #714 have green CI and clean merge status, but both are draft ops-report branches and likely superseded. #704 has green CI but `mergeStateStatus=DIRTY`.
- Clean worktrees are not automatically ready. Several clean worktrees have gone upstream branches and no current PR/test evidence.
- `chore/render-on-demand-stop-churn-20260625` is committed-history stale/merged, but the checked-out worktree is dirty. Archive is blocked until local deltas are preserved or explicitly discarded.
- `ds_reconciliation_promotion_20260626` is the strongest promotion candidate observed, but it still needs a live PR or explicit archive/promotion decision.

## Next Operator Decisions

1. Pick the canonical ops-report PR, if any, then archive/close superseded draft ops-report PRs (#706, #714, #715, #717, #720, #722) after approval.
2. Treat #716 as the most tractable repair candidate: one failing check, narrow file surface, clean local worktree.
3. Do not merge #704 until conflicts are resolved despite green CI.
4. Require preserved WIP receipts for dirty high-blast-radius worktrees before cleanup: `agent/magpie-seed`, A2A/NATS preflight, forge proving ground, forge v1 scoreboard, semantic commons, and cashclaw.
5. Archive gone-upstream clean worktrees only after confirming landed/superseded status: Oz integration, Mike nonstop, A2A governance readiness, Mike arbiter, reconciliation promotion.
6. For `render-on-demand`, preserve or discard dirty local changes first; committed branch history appears already merged.
