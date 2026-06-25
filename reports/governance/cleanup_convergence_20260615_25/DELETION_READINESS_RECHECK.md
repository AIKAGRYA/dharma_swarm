# Deletion Readiness Recheck

Generated: 2026-06-25T10:09:21+0900 JST
Worktree: `/Users/dhyana/ds_cleanup_convergence_20260625`
Branch: `cleanup/convergence-20260615-25`

## Boundary

This is a read-only recheck. No worktree removal, branch deletion, prune,
reset, restore, stash operation, or file deletion was performed.

Deletion remains gated on explicit operator approval of exact paths and exact
commands. Preservation evidence makes cleanup possible; it does not authorize
cleanup by itself.

## Commands Run

```bash
sed -n '1,240p' /Users/dhyana/.codex/attachments/27a5c7a8-1524-486a-8c5a-e86a8bc6bbac/pasted-text-1.txt
git -C /Users/dhyana/dharma_swarm fetch origin main
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm remote -v
git -C /Users/dhyana/ds_cleanup_convergence_20260625 status -sb
git -C /Users/dhyana/ds_cleanup_convergence_20260625 log --oneline --decorate -5
ls -l /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz
ls -l /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz.sha256
ls -l /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/receipts/sha256_verify.txt
sed -n '1,40p' /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/receipts/sha256_verify.txt
sed -n '1,80p' /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/trees/tree_preservation_summary.tsv
```

For the worktree candidates, this loop was run:

```bash
paths=(/private/tmp/dharma_nim_main_check /private/tmp/ds_pr674_merge_check /Users/dhyana/worktrees/ds_cockpit_extract_20260623 /Users/dhyana/worktrees/ds_pr674_rebase_20260624 /Users/dhyana/worktrees/ds_arena_admit_20260623 /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25 /Users/dhyana/ds_governance_fitness_ci_20260620 /private/tmp/ds_provider_review)
for p in $paths; do
  printf 'PATH\t%s\n' "$p"
  if [[ -e "$p" ]]; then printf 'EXISTS\tyes\n'; else printf 'EXISTS\tno\n'; fi
  if git -C "$p" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'STATUS_HEADER\t%s\n' "$(git -C "$p" status -sb | sed -n '1p')"
    printf 'STATUS_SHORT_COUNT\t%s\n' "$(git -C "$p" status --short | wc -l | tr -d ' ')"
    printf 'HEAD\t%s\n' "$(git -C "$p" rev-parse HEAD)"
    printf 'BRANCH\t%s\n' "$(git -C "$p" branch --show-current || true)"
    printf 'UPSTREAM\t%s\n' "$(git -C "$p" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    if git -C "$p" merge-base --is-ancestor HEAD origin/main; then printf 'HEAD_ANCESTOR_ORIGIN_MAIN\tyes\n'; else printf 'HEAD_ANCESTOR_ORIGIN_MAIN\tno\n'; fi
    printf 'TOP_STATUS\n%s\n' "$(git -C "$p" status --short | sed -n '1,20p')"
  else
    printf 'GIT_WORKTREE\tunavailable\n'
  fi
  printf -- '---\n'
done
```

Additional probes:

```bash
git -C /private/tmp/ds_pr674_merge_check show -s --format='%H%n%P%n%s%n%ci' HEAD
git -C /private/tmp/ds_pr674_merge_check branch -a --contains HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 log --oneline --decorate origin/main..HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 log --oneline --decorate HEAD..origin/main | sed -n '1,40p'
git -C /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25 log --oneline --decorate origin/main..HEAD
git -C /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25 branch -a --contains HEAD
git -C /private/tmp/ds_provider_review log --oneline --decorate origin/main..HEAD
git -C /private/tmp/ds_provider_review diff --stat
git -C /Users/dhyana/dharma_swarm show-ref | rg '98a22169883116a8536407dc7700dbbced9ab831|4394d81b201e4a42d3cc30e78dc3f428bf85c506|ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc|f0d52830ebb47f675e5af4b0dd0beea07fb5cef8|55e121b13b048dd750579bf88a566cd86638f462|c69f1cf05bec9b38fa0468135d21a25e7709971d'
rg -n '98a22169883116a8536407dc7700dbbced9ab831|4394d81b201e4a42d3cc30e78dc3f428bf85c506|ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc|f0d52830ebb47f675e5af4b0dd0beea07fb5cef8|55e121b13b048dd750579bf88a566cd86638f462|c69f1cf05bec9b38fa0468135d21a25e7709971d' /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST
```

Generated-output probes:

```bash
find /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution -mindepth 1 -maxdepth 1 -print
du -sh /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution
find /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution -type f | wc -l
find /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution -mindepth 1 -maxdepth 1 -type d | wc -l
git -C /Users/dhyana/dharma_swarm_cashclaw status --short reports/revenue_wedge/evolution | wc -l
git -C /Users/dhyana/dharma_swarm_cashclaw status --short reports/revenue_wedge/evolution | sed -n '1,20p'
git -C /Users/dhyana/dharma_swarm_cashclaw ls-files reports/revenue_wedge/evolution | wc -l
git -C /Users/dhyana/dharma_swarm_cashclaw ls-files reports/revenue_wedge/evolution | sed -n '1,20p'

find /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a -type f | wc -l
find /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a -mindepth 1 -maxdepth 1 -type d -print
find /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a -mindepth 1 -maxdepth 1 -type f -print
du -sh /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 status --short reports/a2a | wc -l
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 status --short reports/a2a | sed -n '1,30p'
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 ls-files reports/a2a | wc -l
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 ls-files reports/a2a | sed -n '1,30p'

find /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22 -mindepth 1 -maxdepth 1 -print
du -sh /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22
find /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22 -type f | wc -l
git -C /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622 status --short reports/governance/reconciliation_2026-06-22 | wc -l
git -C /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622 status --short reports/governance/reconciliation_2026-06-22 | sed -n '1,40p'
git -C /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622 ls-files reports/governance/reconciliation_2026-06-22 | wc -l
```

GitHub connector checks:

```text
PR #674: closed, merged true, head ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc, merged_at 2026-06-23T22:32:24Z.
PR #675: closed, merged true, head f4814580a47608ccd896481352fe2fd76b054cfc, merged_at 2026-06-23T15:01:35Z.
PR #677: closed, merged true, head f0d52830ebb47f675e5af4b0dd0beea07fb5cef8, merged_at 2026-06-23T15:39:26Z.
PR #678: closed, merged true, head 55e121b13b048dd750579bf88a566cd86638f462, merged_at 2026-06-23T15:01:31Z.
Recent PR scan: PR #685 is now closed and merged; `origin/main` includes `21ee18b36 feat(governance): advisory track acceptance-strength membrane (#685)`.
```

## Current Baseline

`git fetch origin main` completed and advanced `origin/main`:

```text
a46522040..21ee18b36 main -> origin/main
```

Current `origin/main`:

```text
21ee18b365a7a0f4b22bb9b087a987973c6fdaa3
```

The cleanup convergence worktree is clean but behind the refreshed main:

```text
## cleanup/convergence-20260615-25...origin/main [ahead 1, behind 1]
```

The new main commit is PR #685. That means any deletion decision made from the
older `a46522040` baseline must be rechecked against `21ee18b36`.

## Preservation Evidence

Verified present:

- `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST`
- `/Users/dhyana/dharma_recover_backups`
- `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/receipts/BACKUP_RECEIPT.md`
- `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz`
- `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz.sha256`
- `/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/receipts/sha256_verify.txt`

The backup receipt states:

- shared repo bundle verify OK
- old independent clone bundle verify OK
- off-machine archive copied to `agni` and verified OK
- all 686 stable recorded files checksum-verified OK
- no cleanup/reset/restore/stash/merge/rebase/branch deletion/worktree removal/file deletion was performed during preservation

The candidate HEADs are covered by preservation refs where relevant, including:

- `refs/preserve/dharma-current-20260624T223009JST/worktrees/private_tmp_dharma_nim_main_check`
- `refs/preserve/dharma-current-20260624T223009JST/worktrees/private_tmp_ds_pr674_merge_check`
- `refs/preserve/dharma-current-20260624T223009JST/worktrees/Users_dhyana_worktrees_ds_cockpit_extract_20260623`
- `refs/preserve/dharma-current-20260624T223009JST/worktrees/Users_dhyana_worktrees_ds_pr674_rebase_20260624`
- `refs/preserve/dharma-current-20260624T223009JST/worktrees/Users_dhyana_worktrees_ds_arena_admit_20260623`
- `refs/preserve/dharma-current-20260624T223009JST/worktrees/Users_dhyana_ds_governance_fitness_ci_20260620`

Do not delete those preservation refs, bundles, receipts, backup roots, or
archive files.

## Verdict Summary

| Candidate | Current evidence | Verdict | Reason |
|---|---|---|---|
| `/private/tmp/dharma_nim_main_check` | Missing path; registered worktree is prunable; HEAD `4394d81b201e4a42d3cc30e78dc3f428bf85c506`; preserve ref exists. | SAFE_TO_REMOVE | Only the stale worktree registration remains. Prune after approval. |
| `/private/tmp/ds_pr674_merge_check` | Exists; detached; clean; HEAD `98a22169883116a8536407dc7700dbbced9ab831`; not ancestor of `origin/main`; preserve ref and `refs/tmp/pr674-merge-20260624` exist. | SAFE_TO_REMOVE | Temporary detached merge-check tree is clean and preserved. Do not delete refs unless separately approved. |
| `/Users/dhyana/worktrees/ds_cockpit_extract_20260623` | Exists; clean; branch `governance/operator-coherence-cockpit-20260623`; HEAD `f0d52830ebb47f675e5af4b0dd0beea07fb5cef8`; ancestor of `origin/main`; PR #677 merged. | SAFE_TO_REMOVE | Clean superseded worktree; branch content is already represented on main. |
| `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` | Exists; branch `repair/pr674-track-closure-gate-20260624`; HEAD `ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc`; ancestor of `origin/main`; PR #674 merged; 4 modified files. | INSPECT_FIRST | HEAD is merged, but current worktree is dirty. Do not remove until the 4 local modifications are approved for discard or preserved separately. |
| `/Users/dhyana/worktrees/ds_arena_admit_20260623` | Exists; clean; branch `governance/arena-v1-admission-20260623`; HEAD `55e121b13b048dd750579bf88a566cd86638f462`; ancestor of `origin/main`; PR #678 merged. | SAFE_TO_REMOVE | Clean superseded worktree; branch content is already represented on main. |
| `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25` | Exists; detached; HEAD `839fd25f43c76375f49e45012fe8f20a324aa74c`; ancestor of `origin/main`; 6 status entries including `reports/governance/prod_readiness/`. | INSPECT_FIRST | Detached tree is dirty and contains prod-readiness report output. Archive/digest decision needed before discard. |
| `/Users/dhyana/ds_governance_fitness_ci_20260620` | Exists; clean; branch `codex/governance-fitness-ci-20260620`; upstream gone; HEAD `c69f1cf05bec9b38fa0468135d21a25e7709971d`; not ancestor of `origin/main`; 5 commits ahead of current main. | INSPECT_FIRST | Clean does not mean redundant. Local commits are not on current main and could still be a PR/archive packet. |
| `/private/tmp/ds_provider_review` | Exists; branch `fix/provider-discoverability`; upstream gone; HEAD `f4814580a47608ccd896481352fe2fd76b054cfc`; ancestor of `origin/main`; PR #675 merged; 2 modified files with 345 insertions. | INSPECT_FIRST | Branch head is merged, but dirty overlay in `dharma_swarm/archive.py` and `tests/test_archive.py` needs review before deletion. |
| Cashclaw `reports/revenue_wedge/evolution/*` | Directory exists; 30M; 33 top-level dirs; 1260 files; 546 tracked files; 17 untracked timestamp dirs. | INSPECT_FIRST | Do not remove the whole evolution directory. Only untracked generated dirs are deletion candidates after approval. |
| A2A `reports/a2a/*` | Directory exists; 5.4M; 548 files; 3 tracked files; 18 untracked generated entries. | INSPECT_FIRST | Do not remove the whole A2A report root. Active runtime substrate worktree remains protected; only explicit untracked generated entries can be considered after approval. |
| Reconciliation raw dumps | Directory exists; 536K; 38 files; entire directory is untracked. | INSPECT_FIRST | Directory mixes raw command dumps with keeper reports. Do not remove the whole directory. Only named raw dumps should be considered after approval. |

## Candidate Details

### `/private/tmp/dharma_nim_main_check`

Current state:

```text
EXISTS: no
worktree list: prunable gitdir file points to non-existent location
HEAD: 4394d81b201e4a42d3cc30e78dc3f428bf85c506
branch: model-routing/nim-live-catalog-fix-20260620
preservation: preserve ref exists and preservation bundle records the HEAD
```

Verdict: SAFE_TO_REMOVE after approval.

Proposed command:

```bash
git -C /Users/dhyana/dharma_swarm worktree prune --verbose
```

Run `git -C /Users/dhyana/dharma_swarm worktree prune --dry-run --verbose`
first if the operator wants a final no-op preview.

### `/private/tmp/ds_pr674_merge_check`

Current state:

```text
EXISTS: yes
STATUS_HEADER: ## HEAD (no branch)
STATUS_SHORT_COUNT: 0
HEAD: 98a22169883116a8536407dc7700dbbced9ab831
HEAD_ANCESTOR_ORIGIN_MAIN: no
commit: Merge 7de1e2230b6597117e8f65ac9478419eba654d4e into fc7d9d1ef7608e2b8a195aa0822aac6c7d942532
branch -a --contains HEAD: only detached no-branch checkout
preservation: preserve ref exists; `refs/tmp/pr674-merge-20260624` also points at this HEAD
```

Verdict: SAFE_TO_REMOVE after approval, for the worktree path only.

Proposed command:

```bash
git -C /Users/dhyana/dharma_swarm worktree remove /private/tmp/ds_pr674_merge_check
```

Do not delete `refs/tmp/pr674-merge-20260624` unless the operator separately
approves ref cleanup.

### `/Users/dhyana/worktrees/ds_cockpit_extract_20260623`

Current state:

```text
STATUS_HEADER: ## governance/operator-coherence-cockpit-20260623...origin/governance/operator-coherence-cockpit-20260623 [gone]
STATUS_SHORT_COUNT: 0
HEAD: f0d52830ebb47f675e5af4b0dd0beea07fb5cef8
HEAD_ANCESTOR_ORIGIN_MAIN: yes
GitHub: PR #677 merged at 2026-06-23T15:39:26Z
preservation: preserve ref exists
```

Verdict: SAFE_TO_REMOVE after approval.

Proposed commands:

```bash
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623
```

Optional branch cleanup, approve separately:

```bash
git -C /Users/dhyana/dharma_swarm branch -d governance/operator-coherence-cockpit-20260623
```

### `/Users/dhyana/worktrees/ds_pr674_rebase_20260624`

Current state:

```text
STATUS_HEADER: ## repair/pr674-track-closure-gate-20260624...origin/chore/reconcile-records-2026-06-22 [gone]
STATUS_SHORT_COUNT: 4
HEAD: ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc
HEAD_ANCESTOR_ORIGIN_MAIN: yes
GitHub: PR #674 merged at 2026-06-23T22:32:24Z
dirty files:
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/track_portfolio.json
 M uv.lock
```

Verdict: INSPECT_FIRST.

Reason: the branch head is merged, but the worktree currently has local
modifications. These are likely generated/local-environment churn, but they
still require explicit discard approval before removal.

Proposed commands only if the operator approves discarding these four modified
files:

```bash
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 restore reports/governance/active_track_evidence.json reports/governance/active_track_evidence.md reports/governance/track_portfolio.json uv.lock
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_pr674_rebase_20260624
```

Optional branch cleanup, approve separately:

```bash
git -C /Users/dhyana/dharma_swarm branch -d repair/pr674-track-closure-gate-20260624
```

### `/Users/dhyana/worktrees/ds_arena_admit_20260623`

Current state:

```text
STATUS_HEADER: ## governance/arena-v1-admission-20260623...origin/governance/arena-v1-admission-20260623 [gone]
STATUS_SHORT_COUNT: 0
HEAD: 55e121b13b048dd750579bf88a566cd86638f462
HEAD_ANCESTOR_ORIGIN_MAIN: yes
GitHub: PR #678 merged at 2026-06-23T15:01:31Z
preservation: preserve ref exists
```

Verdict: SAFE_TO_REMOVE after approval.

Proposed commands:

```bash
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623
```

Optional branch cleanup, approve separately:

```bash
git -C /Users/dhyana/dharma_swarm branch -d governance/arena-v1-admission-20260623
```

### `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25`

Current state:

```text
STATUS_HEADER: ## HEAD (no branch)
STATUS_SHORT_COUNT: 6
HEAD: 839fd25f43c76375f49e45012fe8f20a324aa74c
HEAD_ANCESTOR_ORIGIN_MAIN: yes
dirty files:
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/track_portfolio.json
 M reports/orientation/repo_context.json
 M reports/orientation/repo_context.md
?? reports/governance/prod_readiness/
```

Verdict: INSPECT_FIRST.

Reason: detached HEAD is already on main, but the tree has generated governance
and prod-readiness outputs. Decide whether a digest should be kept before
discarding this tree.

No deletion command is recommended until the prod-readiness output is reviewed.
If the operator explicitly approves discarding it, the command would be:

```bash
git -C /Users/dhyana/dharma_swarm worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
```

### `/Users/dhyana/ds_governance_fitness_ci_20260620`

Current state:

```text
STATUS_HEADER: ## codex/governance-fitness-ci-20260620...origin/codex/governance-fitness-ci-20260620 [gone]
STATUS_SHORT_COUNT: 0
HEAD: c69f1cf05bec9b38fa0468135d21a25e7709971d
HEAD_ANCESTOR_ORIGIN_MAIN: no
local commits not on current origin/main:
c69f1cf05 test: read daemon script from checkout
1cf355ce8 test: refresh routing surface inventory
35bac3f94 test: keep qwen dashboard smoke hermetic
5d236ec2f docs: register model routing semantic commons
fd0e1429c governance: refresh active track and fitness properties [impact-checked]
preservation: preserve ref exists
```

Verdict: INSPECT_FIRST.

Reason: clean worktree, but not redundant. Five commits are not ancestors of
current `origin/main`. This may be archive-only or superseded, but that is not
proven by the current evidence.

No deletion command is recommended until these five commits are reviewed and
classified.

### `/private/tmp/ds_provider_review`

Current state:

```text
STATUS_HEADER: ## fix/provider-discoverability...origin/fix/provider-discoverability [gone]
STATUS_SHORT_COUNT: 2
HEAD: f4814580a47608ccd896481352fe2fd76b054cfc
HEAD_ANCESTOR_ORIGIN_MAIN: yes
GitHub: PR #675 merged at 2026-06-23T15:01:35Z
dirty diff stat:
 dharma_swarm/archive.py | 120 ++++++++++++++++++++++++++
 tests/test_archive.py   | 225 ++++++++++++++++++++++++++++++++++++++++++++++++
```

Verdict: INSPECT_FIRST.

Reason: PR #675 is merged, but this worktree contains a 345-line dirty overlay
touching source and tests. That overlay must be reviewed before removal.

No deletion command is recommended until the overlay is classified.

### Cashclaw Evolution Output

Path:

```text
/Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution
```

Current state:

```text
size: 30M
top-level dirs: 33
files: 1260
tracked files: 546
git status entries under path: 17 untracked timestamp directories
```

Verdict: INSPECT_FIRST.

Reason: the prompt's `evolution/*` wildcard is too broad. The directory mixes
tracked report files with untracked generated run directories. Removing the
whole directory would delete tracked branch content.

Exact untracked generated-output candidates, after approval only:

```bash
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260610T193223Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T073905Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T154212Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T194323Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T234419Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T034600Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T074726Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T155034Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T195220Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T035510Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T075727Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T115830Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T201327Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T001505Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T041649Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T081808Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T122148Z
```

Do not run `rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/*`.

### A2A Generated Reports

Path:

```text
/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a
```

Current state:

```text
size: 5.4M
files: 548
tracked files: 3
tracked files:
  reports/a2a/domain_reply_artifacts/20260611T091552Z-hermes-m5-3a0e3081da8a.json
  reports/a2a/live_listen_20260611T1030Z.jsonl
  reports/a2a/mike_inbox_drain_20260612T0158Z.txt
git status entries under path: 18 untracked generated entries
```

Verdict: INSPECT_FIRST.

Reason: the A2A worktree is an active runtime substrate and must not be cleared
as a whole. The report root also contains three tracked files. Only explicit
untracked generated entries should be considered, and only after the A2A lane
owner approves.

Exact untracked generated-output candidates, after approval only:

```bash
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifact_preflight
rm -f /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifacts/20260619T084913Z-codex_composer-a2a-semantic-signoff-codex_composer-e4778df2dfe6.json
rm -f /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifacts/20260619T085732Z-hermes-m5-a2a-semantic-signoff-hermes-m5-e4778df2dfe6.json
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_requests
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/full_spec_readiness
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/identity_reconcile
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/live_acl
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/live_topology
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/model_reply_captures
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/presence_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/presence_projection
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/rebuild_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/semantic_task_packets
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/semantic_tasks
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/standing_agent_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/standing_wake_loop
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/topology
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/wake_loop_preflight
```

Do not run `rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/*`.

### Reconciliation Raw Dumps

Path:

```text
/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22
```

Current state:

```text
size: 536K
files: 38
tracked files: 0
git status: entire directory is untracked
```

Verdict: INSPECT_FIRST.

Reason: this directory is not tracked, but it mixes raw command dumps with
keeper governance reports. The whole directory should not be removed.

Raw dump candidates only, after approval:

```bash
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/00_environment_receipt.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/01_worktree_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/01_worktree_status_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/02_dirty_checkout_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/02_dirty_checkout_classification.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/03_stash_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/04_branch_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/04_local_branch_ahead_behind.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_heads.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_open_pr_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_relevant_heads.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_specific_prs.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/06_offrepo_dharma_artifacts_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/07_surface_reconciliation_seed.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/08_clean_make_onboard.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/09_clean_make_orient.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/10_clean_make_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/11_clean_check_track_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/12_clean_spine_bypass_report.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/13_pr_662_seeing_organ_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/14_pr_663_markitdown_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/15_local_forge_v1_tokenbroker_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/16_routing_remote_truth.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/17_bronze_throat_grep.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/18_local_forge_v1_tests.txt
```

Keep unless separately reviewed:

- `README.md`
- `NEXT_GOAL_PROMPT.md`
- `DGM_READY_RECONCILIATION_REPORT.md`
- `19_subagent_local_preservation_audit.md`
- `20_subagent_remote_reconciliation_audit.md`
- `21_preservation_receipt.md`
- `21_preservation_receipt.json`
- `22_phase3_red_team_checklist.md`
- `23_reconciliation_worktree_preservation.md`
- `24_phase3_red_team_verdict.md`
- `24_phase3_red_team_verdict.json`
- `25_phase3_red_team_verdict_after_followup.md`
- `25_phase3_red_team_verdict_after_followup.json`

## Second-Pass Inspection Addendum

Generated: 2026-06-25 JST, after the first read-only recheck.

This addendum narrows the `INSPECT_FIRST` bucket. It supersedes the first-pass
verdict for the candidates named here. No destructive command was run.

Additional commands run:

```bash
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff --stat
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff -- reports/governance/active_track_evidence.md | sed -n '1,180p'
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff -- reports/governance/active_track_evidence.json reports/governance/track_portfolio.json | sed -n '1,220p'
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff -- uv.lock | sed -n '1,220p'
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff --stat origin/main -- reports/governance/active_track_evidence.json reports/governance/active_track_evidence.md reports/governance/track_portfolio.json uv.lock
git -C /Users/dhyana/dharma_swarm show origin/main:pyproject.toml | rg -n 'markitdown|ingest'
git -C /Users/dhyana/dharma_swarm show origin/main:uv.lock | rg -n 'name = "markitdown"|ingest =|provides-extras'
git -C /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25 diff --stat
find /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25/reports/governance/prod_readiness -maxdepth 2 -type f -print
git -C /Users/dhyana/dharma_swarm ls-tree -r --name-only origin/main reports/governance/prod_readiness | sed -n '1,120p'
shasum -a 256 /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25/reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25/reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.json
git -C /Users/dhyana/dharma_swarm show origin/main:reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md | shasum -a 256
git -C /Users/dhyana/dharma_swarm show origin/main:reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.json | shasum -a 256
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 diff --stat origin/main...HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 diff --name-status origin/main...HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 cherry -v origin/main HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 log --oneline --decorate --stat origin/main..HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 diff origin/main..HEAD -- docs/ontology/SEMANTIC_COMMONS.md docs/ontology/semantic_aliases.yaml docs/ontology/semantic_objects.yaml | sed -n '1,260p'
git -C /private/tmp/ds_provider_review diff --stat
git -C /private/tmp/ds_provider_review diff -- dharma_swarm/archive.py tests/test_archive.py | sed -n '1,260p'
rg -n 'ArchiveFitnessAuthorityError|fitness_authority_granted|_one_wire_quorum_eligible|One Wire hard guard' /Users/dhyana/dharma_swarm /Users/dhyana/ds_* /private/tmp/ds_provider_review /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25 2>/dev/null
git -C /Users/dhyana/dharma_swarm grep -n 'ArchiveFitnessAuthorityError\|fitness_authority_granted\|_one_wire_quorum_eligible' origin/main -- dharma_swarm/archive.py tests/test_archive.py
```

### Revised Verdicts

| Candidate | Second-pass evidence | Revised verdict | Action |
|---|---|---|---|
| `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` | Three generated governance files contain timestamp/test-duration churn; `uv.lock` adds the MarkItDown ingest dependency set. Current `origin/main:pyproject.toml` declares `ingest = ["markitdown>=0.1.6"]`, while `origin/main:uv.lock` did not show `markitdown` or `ingest`. | DO_NOT_REMOVE_YET | Protect until the lockfile/MarkItDown decision is made. Do not discard the dirty `uv.lock` as cleanup debris. |
| `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25` | Untracked prod-readiness files are byte-identical to `origin/main` (`7993e034...` md, `5830c537...` json), where they landed via `cce2c3e5e`. The remaining modified files are generated governance/orientation projections. | SAFE_TO_REMOVE | Safe for path removal after explicit approval; use `git worktree remove --force` because the worktree is dirty with generated churn. |
| `/Users/dhyana/ds_governance_fitness_ci_20260620` | `git cherry -v origin/main HEAD` marks all five commits as unique. Diff spans ontology, runtime/memory writer policy, orchestrator/runtime lifecycle, tests, and generated governance files. | DO_NOT_REMOVE_YET | This is a stale but source-bearing branch. It needs a port-or-archive decision, not deletion cleanup. |
| `/private/tmp/ds_provider_review` | Dirty diff adds `ArchiveFitnessAuthorityError`, `fitness_authority_granted`, One Wire quorum enforcement in `dharma_swarm/archive.py`, and 225 lines of tests. `origin/main` lacks these archive.py/test_archive.py symbols. | DO_NOT_REMOVE_YET | Treat as source-bearing keeper candidate for One Wire/archive-fitness authority. Port or archive; do not remove as temp cleanup. |

### Updated Approval-Ready Batch

The current exact-path deletion batch that is ready for operator approval is:

```bash
git -C /Users/dhyana/dharma_swarm worktree prune --verbose
git -C /Users/dhyana/dharma_swarm worktree remove /private/tmp/ds_pr674_merge_check
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623
git -C /Users/dhyana/dharma_swarm worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
```

Do not include these in the first deletion batch:

- `/Users/dhyana/worktrees/ds_pr674_rebase_20260624`
- `/Users/dhyana/ds_governance_fitness_ci_20260620`
- `/private/tmp/ds_provider_review`
- any preservation refs, bundles, tarballs, backup roots, old clone, or stash

## Third-Pass Current-State Addendum

Generated: 2026-06-25 JST, after the second-pass inspection.

This pass was triggered because `git worktree list --porcelain` now shows a
new registered worktree that was not present in the earlier cleanup packet.
No destructive command was run.

Additional commands run:

```bash
git -C /Users/dhyana/dharma_swarm fetch origin main
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand status -sb
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand status --short | wc -l
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand rev-parse HEAD
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand branch --show-current
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand merge-base --is-ancestor HEAD origin/main
git -C /Users/dhyana/dharma_swarm_wt/render-on-demand log --oneline --decorate -5
git -C /Users/dhyana/dharma_swarm_cashclaw status --short reports/revenue_wedge/evolution
git -C /Users/dhyana/dharma_swarm_cashclaw ls-files reports/revenue_wedge/evolution | wc -l
du -sh /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 status --short reports/a2a
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 ls-files reports/a2a | wc -l
du -sh /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a
git -C /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622 status --short reports/governance/reconciliation_2026-06-22
find /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22 -maxdepth 1 -type f -exec basename {} \; | sort
```

Current `origin/main` remains:

```text
21ee18b365a7a0f4b22bb9b087a987973c6fdaa3
```

Current registered worktree count is 20.

### New Worktree Observed

```text
path: /Users/dhyana/dharma_swarm_wt/render-on-demand
branch: chore/render-on-demand-stop-churn-20260625
HEAD: 21ee18b365a7a0f4b22bb9b087a987973c6fdaa3
upstream: origin/main
status: clean
HEAD_ANCESTOR_ORIGIN_MAIN: yes
```

Verdict: DO_NOT_REMOVE.

Reason: this worktree appeared after the report was first written, is not named
in the cleanup prompt, and is clean on current `origin/main`. Treat it as active
operator or concurrent-agent state unless the operator separately names it for
cleanup.

### Tier C Recheck

The generated-output candidate lists are still current.

Cashclaw:

```text
path: /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution
size: 30M
top-level directories: 33
tracked files: 546
untracked cleanup candidates: 17 timestamp directories
verdict: EXACT_UNTRACKED_PATHS_ONLY
```

A2A:

```text
path: /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a
size: 5.4M
tracked files: 3
untracked cleanup candidates: 18 entries
verdict: EXACT_UNTRACKED_PATHS_ONLY
```

Reconciliation:

```text
path: /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22
size: 536K
files: 38
tracked files: 0
git status: entire directory untracked
verdict: RAW_DUMPS_ONLY
```

Current reconciliation filenames:

```text
00_environment_receipt.json
01_worktree_inventory.txt
01_worktree_status_inventory.json
02_dirty_checkout_classification.json
02_dirty_checkout_status.txt
03_stash_inventory.txt
04_branch_inventory.txt
04_local_branch_ahead_behind.json
05_remote_heads.txt
05_remote_open_pr_inventory.json
05_remote_relevant_heads.json
05_remote_specific_prs.json
06_offrepo_dharma_artifacts_inventory.json
07_surface_reconciliation_seed.json
08_clean_make_onboard.txt
09_clean_make_orient.txt
10_clean_make_status.txt
11_clean_check_track_status.txt
12_clean_spine_bypass_report.txt
13_pr_662_seeing_organ_diff.txt
14_pr_663_markitdown_diff.txt
15_local_forge_v1_tokenbroker_diff.txt
16_routing_remote_truth.txt
17_bronze_throat_grep.txt
18_local_forge_v1_tests.txt
19_subagent_local_preservation_audit.md
20_subagent_remote_reconciliation_audit.md
21_preservation_receipt.json
21_preservation_receipt.md
22_phase3_red_team_checklist.md
23_reconciliation_worktree_preservation.md
24_phase3_red_team_verdict.json
24_phase3_red_team_verdict.md
25_phase3_red_team_verdict_after_followup.json
25_phase3_red_team_verdict_after_followup.md
DGM_READY_RECONCILIATION_REPORT.md
NEXT_GOAL_PROMPT.md
README.md
```

### Post-Approval Deletion Receipt Template

If exact deletion commands are approved and run, append a completed receipt
below this template:

````markdown
## Deletion Execution Receipt - YYYY-MM-DDTHHMMSSJST

Approved command group:

```text
<paste exact approved commands>
```

Commands actually run:

```text
<paste commands actually run>
```

Removed paths:

- `<path>`

Commands refused or skipped:

- `<command>` - `<reason>`

Post-run verification:

```bash
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm status -sb
git -C /Users/dhyana/ds_cleanup_convergence_20260625 status -sb
```

Post-run status summary:

```text
<paste exact summary>
```

Residual cleanup gates:

- `<remaining gate>`
````

## Approval Checklist

Approve exact paths and command groups. Do not approve by tier name alone.

- [ ] Approve worktree prune for missing `/private/tmp/dharma_nim_main_check`.
- [ ] Approve worktree removal for `/private/tmp/ds_pr674_merge_check`.
- [ ] Approve worktree removal for `/Users/dhyana/worktrees/ds_cockpit_extract_20260623`.
- [ ] Approve worktree removal for `/Users/dhyana/worktrees/ds_arena_admit_20260623`.
- [ ] Approve worktree removal with `--force` for `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25`; prod-readiness keeper files are already byte-identical on `origin/main`.
- [ ] Do not remove `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` until the dirty `uv.lock` MarkItDown ingest dependency decision is made.
- [ ] Approve or reject branch deletion for `governance/operator-coherence-cockpit-20260623`.
- [ ] Approve or reject branch deletion for `governance/arena-v1-admission-20260623`.
- [ ] Do not remove or delete branch `repair/pr674-track-closure-gate-20260624` until the dirty worktree decision is made.
- [ ] Port or archive `/Users/dhyana/ds_governance_fitness_ci_20260620`; do not delete it as cleanup debris.
- [ ] Port or archive `/private/tmp/ds_provider_review`; do not delete it as cleanup debris.
- [ ] Approve the 17 exact Cashclaw untracked timestamp directories, not the whole `evolution/*` wildcard.
- [ ] Approve the 18 exact A2A untracked generated entries, not the whole `reports/a2a/*` wildcard.
- [ ] Approve the exact reconciliation raw dump files, not the whole reconciliation directory.

## Post-Deletion Verification To Run If Approved

After any approved deletion batch:

```bash
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm status -sb
git -C /Users/dhyana/ds_cleanup_convergence_20260625 status -sb
```

Then append a deletion receipt to this packet naming:

- exact commands run
- exact paths removed
- worktrees still registered
- remaining dirty paths
- any refused command or unexpected status

## Fourth-Pass Current-State Recheck (Pass 4)

Generated: 2026-06-25T11:58 JST
Worktree: `/Users/dhyana/ds_cleanup_convergence_20260625`
Branch: `cleanup/convergence-20260615-25`

This pass was triggered because `origin/main` advanced since Pass 3
(`21ee18b36` -> `240a92c6b`). Every verdict and the three prior hold findings
were re-verified against current main. This is a read-only recheck: no
deletion, prune, worktree removal, branch deletion, reset, stash operation,
or file deletion was run.

Pass 4 supersedes the verdict tables in Passes 1-3 where they disagree. In
practice the advanced main resolved none of the hold findings, so the
approval-ready batch and the hold list are unchanged from the Pass 2
addendum, now re-confirmed against `240a92c6b`.

### New Baseline

```bash
git -C /Users/dhyana/dharma_swarm fetch origin main
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
```

Result:

```text
73113dbd0..240a92c6b  main -> origin/main
origin/main = 240a92c6b12b390e429298dfb36661ed8af365a8
registered worktrees = 20 (unchanged set since Pass 3)
```

### Preservation Re-Verified Present

```bash
ls /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST
ls /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz
ls /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz.sha256
ls /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/receipts/BACKUP_RECEIPT.md
ls /Users/dhyana/dharma_recover_backups
ls /Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST/trees/
git -C /Users/dhyana/dharma_swarm stash list | wc -l
```

Result:

- preservation root, portable archive (211562612 bytes), sha256 sidecar, and
  backup root all present
- `BACKUP_RECEIPT.md`: shared and old-clone bundle verify OK; off-machine
  archive copied to `agni` and verified OK; all 686 stable files
  checksum-verified OK; no destructive op performed during preservation
- preservation `trees/` directory contains an overlay for every candidate
  named below, including `tracked_unstaged.diff` for the dirty ones
- 70 stashes exist in `dharma_swarm`. They are not deletion candidates. Do not
  drop, pop, or clear them.

### Commands Run This Pass

Candidate inspection loop (read-only), run for all Tier A, Tier B, and the
do-not-clear paths:

```bash
# per candidate path p:
git -C "$p" rev-parse HEAD
git -C "$p" rev-parse --abbrev-ref HEAD
git -C "$p" rev-parse --abbrev-ref --symbolic-full-name '@{u}'
git -C "$p" status -sb | head -3
git -C "$p" status --short | wc -l
git -C "$p" status --short | grep -c '^??'
git -C "$p" merge-base --is-ancestor HEAD origin/main && echo ANCESTOR=yes || echo ANCESTOR=no
test -d "$p" && echo EXISTS=yes || echo EXISTS=no
```

Hold-finding re-verification against current `origin/main` (240a92c6b):

```bash
git -C /Users/dhyana/dharma_swarm show origin/main:pyproject.toml | rg -n 'markitdown|ingest'
git -C /Users/dhyana/worktrees/ds_pr674_rebase_20260624 diff origin/main -- uv.lock --stat
git -C /Users/dhyana/dharma_swarm grep -n 'ArchiveFitnessAuthorityError|fitness_authority_granted|_one_wire_quorum_eligible' origin/main -- dharma_swarm/archive.py tests/test_archive.py
git -C /private/tmp/ds_provider_review diff origin/main -- dharma_swarm/archive.py tests/test_archive.py --stat
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 cherry -v origin/main HEAD
git -C /Users/dhyana/ds_governance_fitness_ci_20260620 rev-list --left-right --count origin/main...HEAD
shasum -a 256 /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25/reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md
git -C /Users/dhyana/dharma_swarm show origin/main:reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md | shasum -a 256
git -C /Users/dhyana/dharma_swarm ls-tree -r --name-only origin/main reports/governance/prod_readiness
```

### Exact Current Status Per Candidate (origin/main = 240a92c6b)

```text
TIER A
/private/tmp/dharma_nim_main_check
  EXISTS=no (MISSING); worktree list marks prunable
  HEAD=4394d81b201e4a42d3cc30e78dc3f428bf85c506
  branch=model-routing/nim-live-catalog-fix-20260620
  ANCESTOR=n/a (path missing); preserve ref + preservation overlay exist
  Verdict: SAFE_TO_REMOVE (prune stale registration)

/private/tmp/ds_pr674_merge_check
  EXISTS=yes; detached (HEAD no branch); clean (0 dirty)
  HEAD=98a22169883116a8536407dc7700dbbced9ab831
  ANCESTOR=no (throwaway merge-check commit; PR #674 is merged)
  preserve ref + refs/tmp/pr674-merge-20260624 exist
  Verdict: SAFE_TO_REMOVE (worktree remove; keep refs unless separately approved)

/Users/dhyana/worktrees/ds_cockpit_extract_20260623
  EXISTS=yes; clean (0 dirty); 0 untracked
  branch=governance/operator-coherence-cockpit-20260623 (origin gone)
  HEAD=f0d52830ebb47f675e5af4b0dd0beea07fb5cef8
  ANCESTOR=yes; PR #677 merged 2026-06-23T15:39:26Z
  Verdict: SAFE_TO_REMOVE

/Users/dhyana/worktrees/ds_pr674_rebase_20260624
  EXISTS=yes; 4 dirty (0 untracked)
  branch=repair/pr674-track-closure-gate-20260624 (upstream origin/chore/reconcile-records-2026-06-22 gone)
  HEAD=ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc
  ANCESTOR=yes; PR #674 merged 2026-06-23T22:32:24Z
  dirty: reports/governance/active_track_evidence.json, .md, track_portfolio.json (generated churn), uv.lock (markitdown lockfile resolution NOT on main)
  Verdict: INSPECT_FIRST / DO_NOT_REMOVE_YET

/Users/dhyana/worktrees/ds_arena_admit_20260623
  EXISTS=yes; clean (0 dirty); 0 untracked
  branch=governance/arena-v1-admission-20260623 (origin gone)
  HEAD=55e121b13b048dd750579bf88a566cd86638f462
  ANCESTOR=yes; PR #678 merged 2026-06-23T15:01:31Z
  Verdict: SAFE_TO_REMOVE

TIER B
/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
  EXISTS=yes; detached; 6 dirty + 1 untracked (reports/governance/prod_readiness/)
  HEAD=839fd25f43c76375f49e45012fe8f20a324aa74c
  ANCESTOR=yes
  keeper files byte-identical to current main: md=7993e034..., json=5830c537... (origin/main contains the full prod_readiness dir)
  Verdict: SAFE_TO_REMOVE (--force; only generated churn + keeper content already on main)

/Users/dhyana/ds_governance_fitness_ci_20260620
  EXISTS=yes; clean (0 dirty); 0 untracked
  branch=codex/governance-fitness-ci-20260620 (origin gone)
  HEAD=c69f1cf05bec9b38fa0468135d21a25e7709971d
  ANCESTOR=no; git cherry marks all 5 commits unique (+); behind 185 / ahead 5
  Verdict: DO_NOT_REMOVE_YET (source-bearing; port or archive)

/private/tmp/ds_provider_review
  EXISTS=yes; 2 dirty source files (0 untracked)
  branch=fix/provider-discoverability (origin gone)
  HEAD=f4814580a47608ccd896481352fe2fd76b054cfc
  ANCESTOR=yes; PR #675 merged 2026-06-23T15:01:35Z
  dirty: dharma_swarm/archive.py, tests/test_archive.py (389-line ArchiveFitnessAuthorityError / One Wire quorum overlay NOT on main)
  preservation overlay tracked_unstaged.diff=389 lines captures it
  Verdict: DO_NOT_REMOVE_YET (source-bearing keeper candidate; port or archive)

TIER C (generated output; exact paths only, unchanged from prior passes)
/Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution
  33 top-level dirs, 1260 files, 546 tracked; 17 untracked timestamp dirs are the only rm candidates
  Verdict: INSPECT_FIRST (exact untracked dirs only; never evolution/* wildcard)

/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a
  548 files, 3 tracked; 18 untracked generated entries are the only rm candidates
  parent worktree is ACTIVE_RUNTIME_SUBSTRATE (82 dirty, behind 185) -> DO_NOT_CLEAR
  Verdict: INSPECT_FIRST (exact untracked entries only; lane-owner approval; never reports/a2a/* wildcard)

/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22
  38 files, 0 tracked (whole dir untracked); mixes raw dumps with keeper reports
  Verdict: INSPECT_FIRST (numbered raw dumps 00_*..18_* only; keep 19_*..25_* and DGM_READY/NEXT_GOAL/README)

DO NOT CLEAR (confirmed present, source-bearing or active; not deletion candidates)
/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618  82 dirty, behind 185, ACTIVE_RUNTIME_SUBSTRATE
/Users/dhyana/dharma_helm_build                     9 dirty, ahead 57, DASHBOARD_OPERATOR_SURFACE
/Users/dhyana/ds_forge_v1_scoreboard                0 dirty, ahead 9/behind 185, PORT_TO_TRACK
/Users/dhyana/ds_supplychain_slice                 14 dirty, upstream gone, unmerged local commit 11de04fb7, PORT_TO_TRACK
/Users/dhyana/ds_anti_slop_membrane_20260625        0 dirty, PR #685 merged, GOVERNANCE_MEMBRANE
/Users/dhyana/dharma_swarm                         221 dirty, primary checkout on recover/dharma-capital-2026-06-24
/Users/dhyana/dharma_swarm_live                     1 dirty (staged), organ/03-seat
/Users/dhyana/migration_delta/dharma_swarm_old     53 dirty, ahead 16, ARCHIVE_ONLY (old clone)
/Users/dhyana/dharma_swarm_wt/render-on-demand      clean, HEAD=origin/main, DO_NOT_REMOVE (not in cleanup scope)
```

### Hold Findings Re-Verified Against Current Main

1. `ds_pr674_rebase_20260624` uv.lock: STILL DIVERGENT.
   `origin/main:pyproject.toml` declares `ingest = ["markitdown>=0.1.6"]`, but
   the worktree's dirty `uv.lock` resolves dependencies (coloredlogs,
   humanfriendly, ...) that are absent from `origin/main:uv.lock`.
   `git diff origin/main -- uv.lock` is non-empty. The dirty lockfile is an
   unmerged markitdown/ingest resolution, not cleanup debris.
   Verdict: DO_NOT_REMOVE_YET. Note: this candidate was listed in the
   operator's Tier A, but current-state confirmation shows it is NOT yet safe
   to remove; it should be held out of the first deletion batch.

2. `ds_provider_review` archive-fitness overlay: STILL SOURCE-BEARING, NOT ON
   MAIN. `git diff origin/main -- dharma_swarm/archive.py tests/test_archive.py`
   is 389 lines adding `ArchiveFitnessAuthorityError`,
   `fitness_authority_granted`, and One Wire quorum enforcement plus tests.
   `origin/main` lacks these symbols. The preservation overlay captures the
   diff, but the work is a real keeper candidate.
   Verdict: DO_NOT_REMOVE_YET (port or archive; do not delete as temp cleanup).

3. `ds_governance_fitness_ci_20260620`: 5 commits STILL UNIQUE.
   `git cherry -v origin/main HEAD` marks all five `+`; `rev-list --count
   origin/main...HEAD` = behind 185 / ahead 5. Clean does not mean redundant.
   Verdict: DO_NOT_REMOVE_YET (port or archive).

4. `prod_readiness` keeper files: STILL BYTE-IDENTICAL to current main.
   `PROD_GRADE_REVIEW_RESULTS_2026-06-22.md` sha = `7993e034...` and `.json`
   sha = `5830c537...` match `origin/main`; `origin/main` contains the full
   `reports/governance/prod_readiness/` directory. Remaining dirty files are
   generated governance/orientation projections.
   Verdict: SAFE_TO_REMOVE with `--force`.

### Refreshed Verdict Summary (current main 240a92c6b)

| Candidate | Current evidence | Verdict |
|---|---|---|
| `/private/tmp/dharma_nim_main_check` | missing; prunable; preserved | SAFE_TO_REMOVE (prune) |
| `/private/tmp/ds_pr674_merge_check` | detached; clean; throwaway merge-check; preserved | SAFE_TO_REMOVE (worktree remove) |
| `/Users/dhyana/worktrees/ds_cockpit_extract_20260623` | clean; ancestor of main; PR #677 merged | SAFE_TO_REMOVE |
| `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` | ancestor of main; PR #674 merged; dirty uv.lock is unmerged markitdown lockfile resolution | DO_NOT_REMOVE_YET |
| `/Users/dhyana/worktrees/ds_arena_admit_20260623` | clean; ancestor of main; PR #678 merged | SAFE_TO_REMOVE |
| `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25` | detached; ancestor of main; keeper files byte-identical on main; only generated churn dirty | SAFE_TO_REMOVE (--force) |
| `/Users/dhyana/ds_governance_fitness_ci_20260620` | clean; 5 commits unique vs main; source-bearing | DO_NOT_REMOVE_YET |
| `/private/tmp/ds_provider_review` | ancestor of main; PR #675 merged; 389-line source overlay not on main | DO_NOT_REMOVE_YET |
| Cashclaw `reports/revenue_wedge/evolution` | 17 untracked timestamp dirs; 546 tracked files | INSPECT_FIRST (exact untracked dirs only) |
| A2A `reports/a2a` | 18 untracked entries; 3 tracked; active substrate parent | INSPECT_FIRST (exact untracked entries only) |
| Reconciliation raw dumps | 38 untracked files; mixes dumps with keeper reports | INSPECT_FIRST (numbered dumps only) |

### Final Approval-Ready Deletion Batch

These are the only commands ready for operator approval as the first batch.
They are unchanged from the Pass 2 addendum and re-confirmed against current
main. Do not run them until the operator approves exact paths.

```bash
git -C /Users/dhyana/dharma_swarm worktree prune --verbose
git -C /Users/dhyana/dharma_swarm worktree remove /private/tmp/ds_pr674_merge_check
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623
git -C /Users/dhyana/dharma_swarm worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
```

Optional branch cleanup, approve separately and only after the worktree is
removed (use `-d`, not `-D`, so git refuses if the branch is not merged):

```bash
git -C /Users/dhyana/dharma_swarm branch -d governance/operator-coherence-cockpit-20260623
git -C /Users/dhyana/dharma_swarm branch -d governance/arena-v1-admission-20260623
```

### Do Not Include In The First Batch

- `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` (dirty uv.lock markitdown
  resolution; hold for the ingest lockfile decision)
- `/Users/dhyana/ds_governance_fitness_ci_20260620` (5 unique source-bearing
  commits; port or archive)
- `/private/tmp/ds_provider_review` (389-line source-bearing archive-fitness
  overlay; port or archive)
- any preservation refs (`refs/preserve/*`), bundles, tarballs, sha256
  sidecars, `dharma_recover_backups`, the old clone, or any of the 70 stashes
- `/Users/dhyana/dharma_swarm_wt/render-on-demand` (clean, on main, not in
  cleanup scope)
- every do-not-clear worktree listed above

### Final Consolidated Approval Checklist

Approve exact paths and command groups. Do not approve by tier name alone.

- [ ] Approve `worktree prune --verbose` for the missing `/private/tmp/dharma_nim_main_check` registration.
- [ ] Approve `worktree remove /private/tmp/ds_pr674_merge_check`.
- [ ] Approve `worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623`.
- [ ] Approve `worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623`.
- [ ] Approve `worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25` (keeper files are byte-identical on current main; only generated churn is dirty).
- [ ] Do NOT remove `/Users/dhyana/worktrees/ds_pr674_rebase_20260624` until the dirty `uv.lock` markitdown/ingest resolution is captured or explicitly discarded.
- [ ] Port or archive `/Users/dhyana/ds_governance_fitness_ci_20260620`; do not delete as cleanup debris.
- [ ] Port or archive `/private/tmp/ds_provider_review`; do not delete as cleanup debris.
- [ ] Approve or reject branch deletion for `governance/operator-coherence-cockpit-20260623` (separate from worktree removal).
- [ ] Approve or reject branch deletion for `governance/arena-v1-admission-20260623` (separate from worktree removal).
- [ ] Do not delete `repair/pr674-track-closure-gate-20260624` until the dirty worktree decision is made.
- [ ] Approve the 17 exact Cashclaw untracked timestamp directories listed in the Cashclaw section above; never `evolution/*`.
- [ ] Approve the 18 exact A2A untracked generated entries listed above; never `reports/a2a/*`; lane-owner approval required.
- [ ] Approve the exact reconciliation raw dump files `00_*` through `18_*` only; keep `19_*` through `25_*` and `DGM_READY_RECONCILIATION_REPORT.md`, `NEXT_GOAL_PROMPT.md`, `README.md`.
- [ ] Confirm no preservation ref, bundle, tarball, backup root, old clone, or stash is touched.

### Post-Approval Verification

After any approved deletion batch, rerun and append a receipt:

```bash
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm status -sb
git -C /Users/dhyana/ds_cleanup_convergence_20260625 status -sb
```

Then complete the Deletion Execution Receipt template in the Third-Pass
addendum above, naming exact commands run, exact paths removed, worktrees
still registered, remaining dirty paths, and any refused command.

## Deletion Execution Receipt - 2026-06-25T120918JST

This receipt records the first approved worktree deletion batch. Only the exact
commands approved by the operator were run. No branch deletion, stash operation,
preservation ref update, backup removal, clone removal, or Tier C file removal
was performed.

### Operator-Approved Command Group

```bash
git -C /Users/dhyana/dharma_swarm worktree prune --verbose
git -C /Users/dhyana/dharma_swarm worktree remove /private/tmp/ds_pr674_merge_check
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623
git -C /Users/dhyana/dharma_swarm worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
```

### Commands Actually Run

```bash
git -C /Users/dhyana/dharma_swarm fetch origin main
git -C /Users/dhyana/dharma_swarm worktree prune --verbose
git -C /Users/dhyana/dharma_swarm worktree remove /private/tmp/ds_pr674_merge_check
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_cockpit_extract_20260623
git -C /Users/dhyana/dharma_swarm worktree remove /Users/dhyana/worktrees/ds_arena_admit_20260623
git -C /Users/dhyana/dharma_swarm worktree remove --force /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25
```

`fetch origin main` was the read-only freshness check required by the cleanup
protocol before deletion. It left `origin/main` at:

```text
240a92c6b12b390e429298dfb36661ed8af365a8
```

### Command Output

`worktree prune --verbose` output:

```text
Removing worktrees/dharma_nim_main_check: gitdir file points to non-existent location
```

The four `worktree remove` commands completed without stdout or stderr.

### Removed Paths

- `/private/tmp/dharma_nim_main_check` stale registration was pruned.
- `/private/tmp/ds_pr674_merge_check` was removed.
- `/Users/dhyana/worktrees/ds_cockpit_extract_20260623` was removed.
- `/Users/dhyana/worktrees/ds_arena_admit_20260623` was removed.
- `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25` was removed with `--force`.

Filesystem verification:

```text
ls: /Users/dhyana/worktrees/ds_arena_admit_20260623: No such file or directory
ls: /Users/dhyana/worktrees/ds_cockpit_extract_20260623: No such file or directory
ls: /private/tmp/dharma_swarm_prod_readiness_20260623_839fd25: No such file or directory
ls: /private/tmp/ds_pr674_merge_check: No such file or directory
```

### Post-Run Worktree Registry

`git -C /Users/dhyana/dharma_swarm worktree list --porcelain` now reports 15
registered worktrees:

```text
worktree /Users/dhyana/dharma_swarm
HEAD 69506fc803c2b56912a71e0c169a5b37b9ea345d
branch refs/heads/recover/dharma-capital-2026-06-24

worktree /private/tmp/ds_provider_review
HEAD f4814580a47608ccd896481352fe2fd76b054cfc
branch refs/heads/fix/provider-discoverability

worktree /Users/dhyana/dharma_helm_build
HEAD 680b013c027194eb50416840d63055f025ca4bb7
branch refs/heads/helm/worldclass-20260612

worktree /Users/dhyana/dharma_swarm_cashclaw
HEAD c487d2725663bc83d1846bf349763c25930ab2ec
branch refs/heads/cashclaw/revenue-hydra-v1

worktree /Users/dhyana/dharma_swarm_live
HEAD e67b91829cb0b375069a19e4e60125b6d89ba374
branch refs/heads/organ/03-seat

worktree /Users/dhyana/dharma_swarm_main
HEAD 86418541a99c265c09040b9bfc064625c6d59994
detached

worktree /Users/dhyana/dharma_swarm_wt/render-on-demand
HEAD 21ee18b365a7a0f4b22bb9b087a987973c6fdaa3
branch refs/heads/chore/render-on-demand-stop-churn-20260625

worktree /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618
HEAD 86418541a99c265c09040b9bfc064625c6d59994
branch refs/heads/runtime-truth/nats-rebuild-preflight-20260618

worktree /Users/dhyana/ds_cleanup_convergence_20260625
HEAD cffd79ead84eead0d8e8ef2cf06e77e829b97808
branch refs/heads/cleanup/convergence-20260615-25

worktree /Users/dhyana/ds_forge_v1_scoreboard
HEAD d8bca7aab20af7871cff4ef46d08227cdb0923fa
branch refs/heads/forge-v1/tokenbroker-scoreboard-20260620

worktree /Users/dhyana/ds_governance_fitness_ci_20260620
HEAD c69f1cf05bec9b38fa0468135d21a25e7709971d
branch refs/heads/codex/governance-fitness-ci-20260620

worktree /Users/dhyana/ds_supplychain_slice
HEAD 11de04fb743ff9b02a293b248d579bf02fe8fd38
branch refs/heads/loop-closure/supplychain-bronze-20260620

worktree /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622
HEAD 726bc9d4d4add60c46f102d1ceee3a065c474892
detached

worktree /Users/dhyana/worktrees/ds_mandala_cockpit_throwaway_20260624
HEAD 63c4937b33dcef673be53e59368c8eee9293591d
branch refs/heads/scratch/mandala-cockpit-v1-20260624

worktree /Users/dhyana/worktrees/ds_pr674_rebase_20260624
HEAD ebccfb1e2d242f035ac7d9c7a10c3a1ed7d05edc
branch refs/heads/repair/pr674-track-closure-gate-20260624
```

### Protected State Re-Verified

Protected paths still present:

```text
/Users/dhyana/worktrees/ds_pr674_rebase_20260624
/Users/dhyana/ds_governance_fitness_ci_20260620
/private/tmp/ds_provider_review
/Users/dhyana/dharma_swarm_wt/render-on-demand
```

Preservation state still present:

```text
/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST
/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz
/Users/dhyana/.dharma/preservation/dharma_swarm_current_20260624T223009JST.tar.gz.sha256
/Users/dhyana/dharma_recover_backups
```

Stashes remain untouched:

```text
git -C /Users/dhyana/dharma_swarm stash list | wc -l
70
```

### Post-Run Status Summary

```text
git -C /Users/dhyana/dharma_swarm status -sb
## recover/dharma-capital-2026-06-24...origin/recover/dharma-capital-2026-06-24
status --short count: 221

git -C /Users/dhyana/ds_cleanup_convergence_20260625 status -sb
## cleanup/convergence-20260615-25...origin/cleanup/convergence-20260615-25
 M reports/governance/cleanup_convergence_20260615_25/DELETION_READINESS_RECHECK.md
```

### Refused Or Skipped Commands

- Branch deletion was not run; branch cleanup requires separate approval.
- Tier C `rm` commands were not run; exact-path approval is required first.
- No preservation refs, backup tarballs, stashes, old clone bundles, or dirty
  source-bearing worktrees were touched.

## Next Tier C Exact-Path Approval List - Prepared Only, Not Run

The next cleanup decision should approve or reject exact paths only. Do not
approve wildcards such as `evolution/*` or `reports/a2a/*`.

### Cashclaw Generated Evolution Directories

Current evidence:

```bash
git -C /Users/dhyana/dharma_swarm_cashclaw status --short --untracked-files=normal reports/revenue_wedge/evolution
```

Result: 17 untracked timestamp directories. Proposed command group for later
approval only:

```bash
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260610T193223Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T073905Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T154212Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T194323Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260611T234419Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T034600Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T074726Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T155034Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260612T195220Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T035510Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T075727Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T115830Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260613T201327Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T001505Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T041649Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T081808Z
rm -rf /Users/dhyana/dharma_swarm_cashclaw/reports/revenue_wedge/evolution/20260614T122148Z
```

Do not remove the 13 tracked evolution directories dated `20260607` through
`20260610T112428Z`.

### A2A Generated Report Entries

Current evidence:

```bash
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 status --short --untracked-files=normal reports/a2a
git -C /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618 ls-files reports/a2a
```

Result: 18 untracked entries. `reports/a2a/domain_reply_artifacts` contains a
tracked keeper file, so only the two untracked files inside it are proposed;
the directory itself must not be removed.

Proposed command group for later approval only:

```bash
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifact_preflight
rm -f /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifacts/20260619T084913Z-codex_composer-a2a-semantic-signoff-codex_composer-e4778df2dfe6.json
rm -f /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_artifacts/20260619T085732Z-hermes-m5-a2a-semantic-signoff-hermes-m5-e4778df2dfe6.json
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/domain_reply_requests
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/full_spec_readiness
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/identity_reconcile
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/live_acl
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/live_topology
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/model_reply_captures
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/presence_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/presence_projection
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/rebuild_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/semantic_task_packets
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/semantic_tasks
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/standing_agent_preflight
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/standing_wake_loop
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/topology
rm -rf /Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618/reports/a2a/wake_loop_preflight
```

Do not remove these tracked A2A files:

```text
reports/a2a/domain_reply_artifacts/20260611T091552Z-hermes-m5-3a0e3081da8a.json
reports/a2a/live_listen_20260611T1030Z.jsonl
reports/a2a/mike_inbox_drain_20260612T0158Z.txt
```

### Reconciliation Raw Dump Files

Current evidence:

```bash
find /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22 -maxdepth 1 -type f \( -name '0[0-9]_*' -o -name '1[0-8]_*' \) -print | sort
```

Result: 25 raw dump files. Proposed command group for later approval only:

```bash
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/00_environment_receipt.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/01_worktree_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/01_worktree_status_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/02_dirty_checkout_classification.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/02_dirty_checkout_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/03_stash_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/04_branch_inventory.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/04_local_branch_ahead_behind.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_heads.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_open_pr_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_relevant_heads.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/05_remote_specific_prs.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/06_offrepo_dharma_artifacts_inventory.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/07_surface_reconciliation_seed.json
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/08_clean_make_onboard.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/09_clean_make_orient.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/10_clean_make_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/11_clean_check_track_status.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/12_clean_spine_bypass_report.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/13_pr_662_seeing_organ_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/14_pr_663_markitdown_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/15_local_forge_v1_tokenbroker_diff.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/16_routing_remote_truth.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/17_bronze_throat_grep.txt
rm -f /Users/dhyana/worktrees/dharma_swarm_reconcile_20260622/reports/governance/reconciliation_2026-06-22/18_local_forge_v1_tests.txt
```

Do not remove the keeper files in that directory:

```text
19_subagent_local_preservation_audit.md
20_subagent_remote_reconciliation_audit.md
21_preservation_receipt.json
21_preservation_receipt.md
22_phase3_red_team_checklist.md
23_reconciliation_worktree_preservation.md
24_phase3_red_team_verdict.json
24_phase3_red_team_verdict.md
25_phase3_red_team_verdict_after_followup.json
25_phase3_red_team_verdict_after_followup.md
DGM_READY_RECONCILIATION_REPORT.md
NEXT_GOAL_PROMPT.md
README.md
```
