# Dirty Worktree Stabilizer Receipt

Generated: 2026-06-30 JST

Scope: first-pass inspection only. No cleanup, reset, delete, move, merge, push,
commit, deploy, or external contact was performed. Counts below were captured
before this receipt file was written; the allowed receipt file is now an
additional untracked file under the primary repo receipt directory.

## Summary

- Registered primary-repo worktrees inspected from `git worktree list --porcelain`: 26 entries.
- Priority worktrees inspected: 10/10.
- Dirty worktrees identified so far: 19.
- Dirty priority worktrees: 10/10.
- Additional dirty registered worktrees: 7.
- Additional dirty Dharma-family checkouts from shallow `/Users/dhyana` scan: 2.
- One registered temporary locked pytest worktree path was missing at inspection time.

Coordinator live-state addendum (`2026-06-29T16:18Z`): after this first-pass receipt was written, `/Users/dhyana/ds_routing_canon_20260630` appeared as a registered worktree on `codex/routing-canon-20260630`. It is dirty with 18 modified tracked files and 9 untracked status entries, tracks `origin/main` at `+0/-0`, and has no open PR. Current dirty scope is therefore 20 dirty Dharma-family checkouts: 18 dirty registered worktrees plus the 2 additional dirty checkouts from the shallow scan.

## Commands Run

Discovery:

```bash
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
ls -ld /Users/dhyana/dharma_swarm /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 /Users/dhyana/ds_forge_v1_scoreboard /Users/dhyana/ds_semantic_commons_100 /Users/dhyana/ds_forge_proving_ground_10_10_20260626 /Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626 /Users/dhyana/dharma_swarm_cashclaw /Users/dhyana/dharma_swarm_wt/render-on-demand /Users/dhyana/worktrees/pr689_closure /Users/dhyana/worktrees/ds_pr674_rebase_20260624
find /Users/dhyana -maxdepth 3 -name .git -print
```

Status commands run for registered worktrees and extra Dharma-family hits:

```bash
git -C /Users/dhyana/dharma_swarm status --short --branch
git -C /private/tmp/ds_loop status --short --branch
git -C /private/var/folders/2n/h27kz83n6dn90pzkb_8v3pm80000gn/T/pytest-of-dhyana/pytest-1532/test_origin_main_unchanged0/worktrees/ds_loop_fix_F-APS-01-001 status --short --branch
git -C /Users/dhyana/dharma-debug-corral status --short --branch
git -C /Users/dhyana/dharma_helm_build status --short --branch
git -C /Users/dhyana/dharma_swarm_cashclaw status --short --branch
git -C /Users/dhyana/dharma_swarm_live status --short --branch
git -C /Users/dhyana/dharma_swarm_main status --short --branch
git -C /Users/dhyana/dharma_swarm_oz_integration status --short --branch
git -C /Users/dhyana/dharma_swarm_slice_roast status --short --branch
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand status --short --branch
git -C /Users/dhyana/dharma_ws_idea_spark status --short --branch
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 status --short --branch
git -C /Users/dhyana/ds_cleanup_convergence_20260625 status --short --branch
git -C /Users/dhyana/ds_forge_proving_ground_10_10_20260626 status --short --branch
git -C /Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626 status --short --branch
git -C /Users/dhyana/ds_forge_v1_scoreboard status --short --branch
git -C /Users/dhyana/ds_mike_nonstop_20260626 status --short --branch
git -C /Users/dhyana/ds_semantic_commons_100 status --short --branch
git -C /Users/dhyana/ds_supplychain_slice status --short --branch
git -C /Users/dhyana/worktrees/ds_a2a_governance_readiness_20260626 status --short --branch
git -C /Users/dhyana/worktrees/ds_cockpit_grafana_static_20260626 status --short --branch
git -C /Users/dhyana/worktrees/ds_mike_arbiter_20260626 status --short --branch
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 status --short --branch
git -C /Users/dhyana/worktrees/ds_reconciliation_promotion_20260626 status --short --branch
git -C /Users/dhyana/worktrees/pr689_closure status --short --branch
git -C /Users/dhyana/ds_routing_canon_20260630 status --short --branch
git -C /Users/dhyana/ds_routing_canon_20260630 status --porcelain=v2 --branch
git -C /Users/dhyana/ds_routing_canon_20260630 diff --stat
git -C /Users/dhyana/ds_routing_canon_20260630 ls-files --others --exclude-standard
git -C /Users/dhyana/ds_anti_slop_membrane_20260625 status --short --branch
git -C /Users/dhyana/ds_pudgala_autopoiesis_20260626 status --short --branch
git -C /Users/dhyana/worktrees/ds_pudgala_p3_09_696 status --short --branch
git -C /Users/dhyana/dharmic-agora status --short --branch
git -C /Users/dhyana/migration_delta/dharma_swarm_old status --short --branch
```

For every dirty worktree listed below, these read-only inspection commands were
run with the worktree path substituted literally:

```bash
git -C PATH diff --stat
git -C PATH diff --name-status
git -C PATH diff --cached --stat
git -C PATH diff --cached --name-status
git -C PATH ls-files --others --exclude-standard
```

Additional aggregation commands executed read-only `git status --short`,
`git diff --shortstat`, and the same diff/untracked commands through local
Python loops over the inspected path lists.

## Dirty Worktrees

### 1. `/Users/dhyana/dharma_swarm`

- Branch: `agent/magpie-seed`.
- Priority: yes.
- Dirty counts: 148 status lines; 60 unstaged modified, 1 staged deleted, 87 untracked status entries; 309 untracked files.
- Diff stat: 60 unstaged files changed, 4531 insertions, 369 deletions; cached diff is 1 deleted file, 96 deletions.
- Modified bucket: broad source, docs, ontology, governance reports, scripts, terminal, provider/runtime, and tests.
- Deleted bucket: staged delete of `tests/test_apex_command_map.py`.
- Untracked bucket: new API pool router, Telos dashboard page, LangGraph parity, memory retrieval/common code, model pool registry, venture cell/livelihood code, A2A/domain reply receipts, terminal tests, vector/wiki live gates, and many report directories.
- Likely intentional vs generated: mixed. Code/tests/docs look intentional active feature work; many `reports/` entries are generated receipts.
- Risk: high. This is the primary repo, broad changes span many subsystems, and a staged deletion is present.
- Preservation decision: preserve exactly as-is; do not clean or stage.
- Next action: coordinator should split into topical review batches before any commit, with generated receipts separated from source/test changes.

### 2. `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618`

- Branch: `runtime-truth/nats-rebuild-preflight-20260618...origin/main [behind 212]`.
- Priority: yes.
- Dirty counts: 82 status lines; 28 unstaged modified, 54 untracked status entries; 316 untracked files.
- Diff stat: 28 files changed, 3669 insertions, 233 deletions.
- Modified bucket: A2A transport/gateway/runtime scripts, NATS spec, governance/orientation reports, and A2A tests.
- Deleted bucket: none observed.
- Untracked bucket: A2A roster/topology modules, A2A governance scripts, semantic task artifacts, wake-loop/preflight reports, and corresponding tests.
- Likely intentional vs generated: source/tests/scripts appear intentional rebuild work; `reports/a2a/` trees are generated preflight output.
- Risk: high due size, stale base, and runtime contract surface.
- Preservation decision: preserve.
- Next action: rebase/merge planning only after owner review; separate report artifacts from code before promotion.

### 3. `/Users/dhyana/ds_forge_v1_scoreboard`

- Branch: `forge-v1/tokenbroker-scoreboard-20260620...origin/main [ahead 9, behind 212]`.
- Priority: yes.
- Dirty counts: 26 status lines; 21 unstaged modified, 5 untracked status entries; 12 untracked files.
- Diff stat: 21 files changed, 747 insertions, 43 deletions.
- Modified bucket: model/provider routing, key oracle, model pool/defaults/hierarchy, Forge v1 provider runner, runtime env, governance reports, and tests.
- Deleted bucket: none observed.
- Untracked bucket: `dharma_swarm/forge_v1/autoloop.py`, `canonical.py`, Forge v2 package files, and Forge v2 tests.
- Likely intentional vs generated: mostly intentional model-routing/Forge work; governance reports likely generated.
- Risk: high because branch is both ahead and far behind origin/main, touching provider routing and keys.
- Preservation decision: preserve.
- Next action: owner review for provider/key-routing correctness, then isolate Forge v2 additions from governance report churn.

### 4. `/Users/dhyana/ds_semantic_commons_100`

- Branch: `codex/semantic-commons-livingdock-composer-100...origin/main [behind 23]`.
- Priority: yes.
- Dirty counts: 38 status lines; 9 unstaged modified, 29 untracked status entries; 30 untracked files.
- Diff stat: 9 files changed, 2349 insertions, 451 deletions.
- Modified bucket: Makefile, OKF substrate, persistent agent, semantic aliases/objects, governance reports, and OKF tests.
- Deleted bucket: none observed.
- Untracked bucket: living dock verifier, D-score verifier, agent contracts, architecture docs, ontology projection files, admission docs/scripts, scorecard, and tests.
- Likely intentional vs generated: mostly intentional semantic commons/admission work; governance scorecard/reports generated.
- Risk: high/medium due large ontology changes and many new governance contracts.
- Preservation decision: preserve.
- Next action: run semantic-commons owner review and validate ontology diffs before any cleanup.

### 5. `/Users/dhyana/ds_forge_proving_ground_10_10_20260626`

- Branch: `codex/dharma-forge-proving-ground-10-10-20260626...origin/main [behind 10]`.
- Priority: yes.
- Dirty counts: 25 status lines; 4 unstaged modified, 21 untracked status entries; 25 untracked files.
- Diff stat: 4 files changed, 40 insertions, 1 deletion.
- Modified bucket: Makefile and semantic commons ontology docs/files.
- Deleted bucket: none observed.
- Untracked bucket: benchmark fixtures/adapter, Forge proving-ground task/governance docs, runtime scripts, and tests.
- Likely intentional vs generated: intentional scaffold and tests; fixtures may be generated/static support.
- Risk: medium.
- Preservation decision: preserve.
- Next action: compare with the droid proving-ground worktree to avoid duplicate divergent implementations.

### 6. `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626`

- Branch: `droid/dharma-forge-proving-ground-10-10-20260626...origin/main [behind 10]`.
- Priority: yes.
- Dirty counts: 19 status lines; 17 staged added, 2 untracked status entries; 2 untracked files.
- Diff stat: no unstaged diff; cached diff has 17 files changed, 2021 insertions.
- Modified bucket: none unstaged.
- Deleted bucket: none observed.
- Untracked bucket: `scripts/runtime/forge_swebench_adapter.py`, `tests/test_forge_swebench_adapter.py`.
- Staged added bucket: `.venv`, Forge proving-ground docs/scripts/tests, and real benchmark adapter.
- Likely intentional vs generated: staged scripts/tests/docs look intentional; staged `.venv` is suspicious and likely generated or environment-local.
- Risk: high because generated environment material appears staged and this overlaps the non-droid proving-ground worktree.
- Preservation decision: preserve staged state; do not unstage without coordinator approval.
- Next action: inspect staged `.venv` specifically, then reconcile against `/Users/dhyana/ds_forge_proving_ground_10_10_20260626`.

### 7. `/Users/dhyana/dharma_swarm_cashclaw`

- Branch: `cashclaw/revenue-hydra-v1...origin/cashclaw/revenue-hydra-v1`.
- Priority: yes.
- Dirty counts: 18 status lines; 1 unstaged modified, 17 untracked status entries; 714 untracked files.
- Diff stat: 1 file changed, 1 insertion, 1 deletion.
- Modified bucket: `dharma_swarm/claude_cli.py`.
- Deleted bucket: none observed.
- Untracked bucket: timestamped `reports/revenue_wedge/evolution/` directories.
- Likely intentional vs generated: code tweak may be intentional; untracked evolution directories are likely generated run receipts.
- Risk: medium due high artifact volume and possible receipt retention decisions.
- Preservation decision: preserve.
- Next action: decide artifact retention/archive policy, then inspect the one code diff separately.

### 8. `/Users/dhyana/dharma_swarm_wt/render-on-demand`

- Branch: `chore/render-on-demand-stop-churn-20260625...origin/main [behind 37]`.
- Priority: yes.
- Dirty counts: 12 status lines; 8 unstaged modified, 4 staged deleted, no untracked files.
- Diff stat: 8 unstaged files changed, 74 insertions, 1039 deletions; cached diff has 4 deleted files, 2415 deletions.
- Modified bucket: active-track workflow, `.gitignore`, `CLAUDE.md`, governance docs, `agent_onboard.py`, and render script.
- Deleted bucket: staged deletes for `docs/docops/AUTO_INVENTORY.md`, `reports/governance/active_track_evidence.json`, `active_track_evidence.md`, and `track_portfolio.json`.
- Untracked bucket: none.
- Likely intentional vs generated: likely intentional stop-churn cleanup, but staged deletion of governance/report artifacts is destructive.
- Risk: high.
- Preservation decision: preserve.
- Next action: require explicit owner/coordinator review before committing or unstaging deletes.

### 9. `/Users/dhyana/worktrees/pr689_closure`

- Branch: `pr-689-closure`.
- Priority: yes.
- Dirty counts: 3 status lines; 3 unstaged modified; no untracked files.
- Diff stat: 3 files changed, 32 insertions, 32 deletions.
- Modified bucket: `reports/governance/active_track_evidence.json`, `active_track_evidence.md`, `track_portfolio.json`.
- Deleted bucket: none observed.
- Untracked bucket: none.
- Likely intentional vs generated: generated governance report refresh.
- Risk: low/medium.
- Preservation decision: preserve.
- Next action: compare against PR 689 closure requirements before deciding whether to keep or regenerate.

### 10. `/Users/dhyana/worktrees/ds_pr674_rebase_20260624`

- Branch: `repair/pr674-track-closure-gate-20260624...origin/chore/reconcile-records-2026-06-22 [gone]`.
- Priority: yes.
- Dirty counts: 4 status lines; 4 unstaged modified; no untracked files.
- Diff stat: 4 files changed, 172 insertions, 18 deletions.
- Modified bucket: governance evidence/portfolio files and `uv.lock`.
- Deleted bucket: none observed.
- Untracked bucket: none.
- Likely intentional vs generated: governance files likely generated; `uv.lock` may be dependency-lock drift from rebase/test setup.
- Risk: medium because upstream branch is gone and lockfile changed.
- Preservation decision: preserve.
- Next action: inspect `uv.lock` cause before carrying this forward.

### 11. `/Users/dhyana/dharma_helm_build`

- Branch: `helm/worldclass-20260612...origin/helm/worldclass-20260612`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 9 status lines; 7 unstaged modified, 2 untracked status entries; 2 untracked files.
- Diff stat: 7 files changed, 354 insertions, 13 deletions.
- Modified bucket: intent payloads, terminal bridge, governance reports, tmux start script, and intent payload tests.
- Deleted bucket: none observed.
- Untracked bucket: `reports/terminal/`, `tests/test_terminal_bridge.py`.
- Likely intentional vs generated: terminal/helm changes look intentional; terminal reports generated.
- Risk: medium.
- Preservation decision: preserve.
- Next action: review with terminal/helm owner and separate report artifacts.

### 12. `/Users/dhyana/dharma_swarm_live`

- Branch: `organ/03-seat...origin/organ/03-seat`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 1 status line; 1 staged added; no untracked files.
- Diff stat: no unstaged diff; cached diff has 1 file changed, 161 insertions.
- Modified bucket: none unstaged.
- Deleted bucket: none observed.
- Staged added bucket: `reports/handoffs/SEAT_REBASE_PREVIEW_2026-06-11.md`.
- Likely intentional vs generated: intentional handoff/preview receipt.
- Risk: low.
- Preservation decision: preserve staged file.
- Next action: coordinator decides whether this handoff belongs in branch history.

### 13. `/Users/dhyana/dharma_swarm_main`

- Branch: detached `HEAD (no branch)`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 3 status lines; 3 unstaged modified; no untracked files.
- Diff stat: 3 files changed, 32 insertions, 6 deletions.
- Modified bucket: governance evidence/portfolio files.
- Deleted bucket: none observed.
- Untracked bucket: none.
- Likely intentional vs generated: generated active-track evidence refresh.
- Risk: low/medium because the checkout is detached.
- Preservation decision: preserve.
- Next action: do not commit from detached state; compare or port only if coordinator needs the refresh.

### 14. `/Users/dhyana/dharma_ws_idea_spark`

- Branch: `feat/operator-idea-spark-ingest`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 3 status lines; 1 unstaged modified, 2 untracked files.
- Diff stat: 1 file changed, 64 insertions, 1 deletion.
- Modified bucket: `dharma_swarm/chetana/promote.py`.
- Deleted bucket: none observed.
- Untracked bucket: `dharma_swarm/chetana/quality_gate.py`, `tests/test_chetana_quality_gate.py`.
- Likely intentional vs generated: intentional feature/test work.
- Risk: medium.
- Preservation decision: preserve.
- Next action: run focused quality-gate tests before any promotion.

### 15. `/Users/dhyana/ds_cleanup_convergence_20260625`

- Branch: `codex/governance-fitness-ci-20260625-225920...origin/codex/governance-fitness-ci-20260625-225920 [gone]`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 3 status lines; 3 unstaged modified; no untracked files.
- Diff stat: 3 files changed, 768 insertions, 375 deletions.
- Modified bucket: governance evidence/portfolio files.
- Deleted bucket: none observed.
- Untracked bucket: none.
- Likely intentional vs generated: generated governance convergence refresh.
- Risk: low/medium, raised by gone upstream branch.
- Preservation decision: preserve.
- Next action: compare with current governance reports before deciding whether to migrate or discard later.

### 16. `/Users/dhyana/ds_supplychain_slice`

- Branch: `loop-closure/supplychain-bronze-20260620...origin/loop-closure/supplychain-bronze-20260620 [gone]`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 14 status lines; 9 unstaged modified, 5 untracked files.
- Diff stat: 9 files changed, 39 insertions, 30 deletions.
- Modified bucket: governance reports and loop/organism tests.
- Deleted bucket: none observed.
- Untracked bucket: track acceptance strength report JSON/MD, retrospective, generator script, and test.
- Likely intentional vs generated: intentional loop-closure reporting and tests; reports generated.
- Risk: medium because upstream branch is gone.
- Preservation decision: preserve.
- Next action: confirm whether supply-chain bronze closure is already captured elsewhere before migrating this work.

### 17. `/Users/dhyana/worktrees/ds_cockpit_grafana_static_20260626`

- Branch: `scratch/cockpit-grafana-static-20260626`.
- Priority: no, extra dirty registered worktree.
- Dirty counts: 1 status line; 1 untracked status entry; 1 untracked file.
- Diff stat: none.
- Modified bucket: none.
- Deleted bucket: none observed.
- Untracked bucket: `cockpit_static/data.js`.
- Likely intentional vs generated: generated static cockpit data export.
- Risk: low.
- Preservation decision: preserve.
- Next action: decide whether static export should be ignored, archived, or committed with dashboard work.

### 18. `/Users/dhyana/ds_pudgala_autopoiesis_20260626`

- Branch: `codex/pudgala-autopoiesis-protostar-20260626...github/codex/pudgala-autopoiesis-protostar-20260626`.
- Priority: no, extra dirty Dharma-family checkout from shallow scan.
- Dirty counts: 7 status lines; 6 unstaged modified, 1 untracked file.
- Diff stat: 6 files changed, 115 insertions, 15 deletions.
- Modified bucket: docops inventory, Forge naming boundary, sovereign manifest, ontology aliases/objects, and naming boundary tests.
- Deleted bucket: none observed.
- Untracked bucket: Forge proving-ground readiness goal doc.
- Likely intentional vs generated: intentional ontology/naming-boundary work, with possible copied task doc.
- Risk: medium.
- Preservation decision: preserve.
- Next action: include in follow-up exhaustive Dharma-family scan and compare with proving-ground branches.

### 19. `/Users/dhyana/migration_delta/dharma_swarm_old`

- Branch: `main...origin/main [ahead 16]`.
- Priority: no, extra dirty Dharma-family checkout from shallow scan.
- Dirty counts: 53 status lines; 37 unstaged modified, 16 untracked status entries; 40 untracked files.
- Diff stat: 37 files changed, 2527 insertions, 428 deletions.
- Modified bucket: dashboard layout/viz/workflow code, Dharma runtime/ontology/DGC modules, pyproject, run script, and tests.
- Deleted bucket: none observed.
- Untracked bucket: dashboard layout/background/store files, agentic corporation package, modular DGC package, ontology metadata, autonomy/cleanup plans, research references, and tests.
- Likely intentional vs generated: old migration implementation snapshot; research references may be copied/generated support material.
- Risk: high but isolated under `migration_delta`.
- Preservation decision: preserve and do not mix into primary readiness work without explicit migration decision.
- Next action: coordinator should decide whether this old checkout is archival only or has changes to port.

### 20. `/Users/dhyana/ds_routing_canon_20260630`

- Branch: `codex/routing-canon-20260630...origin/main [ahead 0, behind 0]`.
- Priority: no, live-state delta after first-pass receipt.
- Dirty counts: 27 status entries; 18 modified tracked files and 9 untracked status entries.
- Diff stat: 18 files changed, 438 insertions, 69 deletions.
- Modified bucket: model/key routing code (`api_keys`, provider/runtime/model pool/defaults/hierarchy), routing docs, runtime env loader, and routing tests.
- Deleted bucket: none observed.
- Untracked bucket: `dharma_swarm/forge_v1/`, Runpod SWE-bench runbook/setup script, and Forge v1/v2 tests.
- Likely intentional vs generated: intentional model-routing canon and Forge WIP, with possible generated or copied experiment support files.
- Risk: high because it touches provider/model routing and introduces broad Forge WIP without branch commits or a PR.
- Preservation decision: preserve exactly as-is; do not clean, delete, or mix with existing Forge v1 scoreboard work without explicit sequencing.
- Next action: split model-routing canon changes from Forge experiment files, then run targeted routing/provider tests before any PR.

## Clean, Missing, Or Not Included In Dirty Count

- `/private/tmp/ds_loop`: clean status observed.
- Registered pytest worktree `/private/var/folders/2n/h27kz83n6dn90pzkb_8v3pm80000gn/T/pytest-of-dhyana/pytest-1532/test_origin_main_unchanged0/worktrees/ds_loop_fix_F-APS-01-001`: missing path at status time; `git -C ... status --short --branch` returned `fatal: cannot change to ... No such file or directory`.
- Other registered primary-repo worktrees status-checked and clean: `dharma-debug-corral`, `dharma_swarm_oz_integration`, `dharma_swarm_slice_roast`, `ds_mike_nonstop_20260626`, `worktrees/ds_a2a_governance_readiness_20260626`, `worktrees/ds_mike_arbiter_20260626`, `worktrees/ds_reconciliation_promotion_20260626`.
- Extra shallow-scan Dharma-looking checkouts status-checked and clean: `ds_anti_slop_membrane_20260625`, `worktrees/ds_pudgala_p3_09_696`, `dharmic-agora`.

## First-Pass Gap

The scan is not a perfect global filesystem census. I completed the primary
repo's registered worktree list, a shallow `/Users/dhyana` scan to depth 3, and
the live-state follow-up for `/Users/dhyana/ds_routing_canon_20260630`.

I attempted the exact recursive continuation below. The unconstrained command
walked archived `.Trash` revenue workspaces and cache/vendor repos with hundreds
of unrelated Git directories, so it was interrupted to avoid turning a Dharma
worktree-readiness campaign into a full home-directory archaeology pass. A
second pruned `find` excluding `.Trash`, cache/vendor, virtualenv, and nested
reference directories exited with `find: fts_read: Interrupted system call`
after listing top-level candidates.

Verifier limitation: this receipt is authoritative for the main Dharma Git
store's registered worktrees and the top-level Dharma-family checkouts listed
above. It is not an authority for archived `.Trash` feasibility workspaces,
plugin caches, vendored repos, or deeply nested reference repos.

Exact next command for exhaustive continuation:

```bash
find /Users/dhyana /private/tmp -name .git -print
```

Then run the following for each Dharma-family hit not already covered:

```bash
git -C PATH status --short --branch
git -C PATH diff --stat
git -C PATH diff --name-status
git -C PATH diff --cached --stat
git -C PATH diff --cached --name-status
git -C PATH ls-files --others --exclude-standard
```
