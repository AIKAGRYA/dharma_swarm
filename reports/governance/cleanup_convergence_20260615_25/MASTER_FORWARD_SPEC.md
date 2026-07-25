# Master Forward Spec: Cleanup Convergence To Safe Motion

Generated: 2026-06-26 JST
Scope: Dharma Swarm branch/worktree cleanup and forward-lane readiness
Primary packet: `reports/governance/cleanup_convergence_20260615_25/`

## Purpose

This spec turns the June 15-25 cleanup convergence work into an executable
master goal. The target state is not "delete more stuff." The target state is a
repo that can move forward from a current baseline, with old worktrees either
landed, protected, archived, or removed only after exact-path approval.

The cleanup movement already produced a trustworthy map and one approved
worktree deletion receipt. This spec defines the next pass: refresh reality,
separate active lanes from stale debris, resolve the remaining protected
worktrees, and leave a current receipt that future agents can trust.

## Goal Prompt

Use this block as the next high-level goal if handing the work to another agent:

```text
Goal: Continue the Dharma Swarm cleanup convergence from the existing packet at
reports/governance/cleanup_convergence_20260615_25/. Refresh git, GitHub PR,
worktree, and dirty-state truth first. Do not assume the June 25 inventory is
current. Produce an updated forward-state receipt that classifies every current
worktree and relevant branch as one of: active lane, merge/rebase lane,
protected source-bearing work, archive-only, duplicate/superseded, or exact-path
deletion candidate. Do not merge dirty worktrees wholesale. Do not delete
branches, stashes, preservation refs, backup roots, old clones, generated
outputs, or worktrees unless the operator explicitly approves exact commands and
paths. Move forward lane-by-lane from current origin/main or from clean active
PR branches, with verification for each material action.
```

## Source Of Truth

Read these files first:

- `reports/governance/cleanup_convergence_20260615_25/INDEX.md`
- `reports/governance/cleanup_convergence_20260615_25/CLOSEOUT.md`
- `reports/governance/cleanup_convergence_20260615_25/DELETION_READINESS_RECHECK.md`
- `reports/governance/cleanup_convergence_20260615_25/worktree_inventory.tsv`
- `reports/governance/cleanup_convergence_20260615_25/keeper_matrix.md`

Then treat current command output as higher authority than any stale line in the
packet. The packet is provenance and prior classification, not a substitute for
fresh state.

## Known Last-Audit State

At the last audit, after `git fetch --all --prune`:

- `origin/main` was `c53721d5f8aa713db88b5647b06682fa8ea50e98`.
- Local `main` was stale at `103311acc` and behind `origin/main` by 2.
- Cleanup branches had been pruned from origin:
  - `origin/cleanup/convergence-20260615-25`
  - `origin/codex/cleanup-deletion-receipt-20260625`
  - `origin/codex/onboard-swarm-bulletins-20260625`
- Cleanup PRs were landed:
  - PR #688: cleanup convergence packet.
  - PR #691: approved worktree deletion receipt.
  - PR #692: cleanup bulletins in onboarding.
- The registered worktree count was 17, not the 15 recorded immediately after
  the deletion batch, because new active worktrees had been created afterward.
- Follow-up execution on 2026-06-26 advanced PR #698 to commit `791801e0f`
  with the explicit raw-LOC ratchet rebaseline applied. GitHub checks are now
  green and the PR remains draft.
- Follow-up execution on 2026-06-26 advanced PR #693 to commit `b3cf8f855`
  with review-blocker fixes applied. GitHub checks are now green, but review
  threads remain unresolved because resolving them is a separate GitHub write
  action.
- `/Users/dhyana/worktrees/ds_pudgala_autopoiesis_protostar_20260625` was present during the
  initial audit but is no longer a registered worktree or existing path. The
  branch `anti-slop/pudgala-autopoiesis-protostar-2026-06` remains present locally and pushed.

These facts must be refreshed before acting.

## Non-Negotiable Safety Rules

1. Do not use local `main` as a baseline until it is explicitly refreshed or a
   fresh worktree is created from `origin/main`.
2. Do not infer safe deletion from branch ancestry alone. Some PRs landed via
   merge or squash patterns that make raw ancestry misleading.
3. Do not delete any branch with `-D`. If branch cleanup is approved later, use
   `branch -d` so git can refuse unmerged content.
4. Do not run wildcard deletion commands such as `rm -rf reports/a2a/*` or
   `rm -rf evolution/*`.
5. Do not delete preservation refs, bundles, tarballs, sha256 sidecars,
   `/Users/dhyana/dharma_recover_backups`, old clone bundles, or stashes.
6. Do not remove dirty worktrees unless their dirty overlay is separately
   reviewed and the operator approves exact discard/removal commands.
7. Do not port generated reports as source. Generated reports can be evidence,
   receipts, or archive material.
8. Do not merge any dirty worktree wholesale.
9. Do not claim a lane is live, shippable, merged, closed, or safe to remove
   unless fresh command output proves that exact claim.
10. If network, GitHub, or filesystem access fails, record the blocker and stop
    before destructive or irreversible actions.

## Refresh Protocol

Run this before any decision:

```bash
git -C /Users/dhyana/dharma_swarm fetch --all --prune
git -C /Users/dhyana/dharma_swarm rev-parse origin/main
git -C /Users/dhyana/dharma_swarm worktree list --porcelain
git -C /Users/dhyana/dharma_swarm branch -vv --sort=-committerdate
```

Then collect a compact per-worktree table:

```text
path
branch or detached state
HEAD
upstream
ahead/behind, if upstream exists
dirty status count
first status header
```

Also collect GitHub PR truth:

```bash
gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --limit 30 \
  --json number,title,headRefName,isDraft,mergeStateStatus,statusCheckRollup
```

Summarize only failing, pending, or cancelled checks. Do not paste full check
rollups into the final receipt unless needed for debugging.

## Classification Model

Every current worktree and relevant branch must receive exactly one current
classification:

- `ACTIVE_LANE`: clean or intentionally dirty lane with an open PR or explicit
  ongoing goal.
- `MERGE_OR_REBASE_LANE`: real source work that needs rebase, tests, and PR.
- `PROTECTED_SOURCE_BEARING`: dirty or unique source work not safe to remove.
- `ARCHIVE_ONLY`: preserved material retained for history unless revived.
- `DUPLICATE_OR_SUPERSEDED`: represented on main or superseded by merged PRs.
- `GENERATED_OUTPUT_CANDIDATE`: generated files or directories eligible only
  for exact-path approval.
- `EXACT_PATH_DELETE_CANDIDATE`: clean duplicate/superseded worktree or named
  generated path ready for operator approval.
- `NEEDS_OPERATOR_DECISION`: technically understood but policy/product choice
  is required.

For each classification, record evidence:

- current path exists or is missing;
- dirty file count and top dirty paths;
- whether HEAD is ancestor/equivalent to `origin/main`, when meaningful;
- related PR number and state, if any;
- whether preservation coverage exists;
- recommended next action.

## Current Priority Lanes

Refresh before acting, but use this as the expected ordering:

1. PR #693, Pudgala Autopoiesis Protostar:
   - Treat as the highest-ready active forward lane.
   - CI is green at `b3cf8f855`.
   - Remaining work is GitHub review-thread/receipt/human-gate handling, not
     failing tests.
   - Do not duplicate older closed draft #690.

2. PR #698, governance quality ratchet:
   - It is intentionally draft and now green at `791801e0f`.
   - The explicit raw-LOC rebaseline decision has been applied and documented.
   - Do not undraft or merge until the operator accepts that policy decision.

3. PR #700, Mike unchanged fanout dedupe:
   - New draft active lane, green at the latest refresh.
   - Keep separate from cleanup convergence unless the operator asks to work
     the Mike lane.

4. Cleanup receipt maintenance:
   - The cleanup packet is landed.
   - Add a new follow-up receipt only if current state materially changed or
     additional approved cleanup commands run.

5. A2A/NATS:
   - Real runtime substrate.
   - Rebase into a dedicated lane.
   - Exclude bulk generated receipts.
   - Run targeted tests before any PR.

6. Helm terminal:
   - Real operator surface work.
   - Needs live-use gate before PR.
   - Expect large-diff exception if landing.

7. Forge v1/tokenbroker:
   - Clean local source-bearing branch at last audit.
   - Needs a proposed/admitted track and rebase.
   - Do not treat as cleanup debris.

8. Supply-chain thin loop:
   - Separate merged PR #648 history from local commit `11de04fb7` and dirty
     governance overlay.
   - Port or archive deliberately.

9. Provider review and PR674 rebase leftovers:
   - Heads may be merged or superseded, but dirty overlays block deletion.
   - Inspect dirty files before any removal.

## Deletion Approval Protocol

This spec does not authorize deletion.

If deletion is needed:

1. Re-read `DELETION_READINESS_RECHECK.md`.
2. Re-run current evidence for the exact path.
3. Prepare exact commands with no wildcards.
4. Ask the operator to approve the exact command group.
5. Run only the approved commands.
6. Append a deletion execution receipt naming:
   - exact commands approved;
   - exact commands actually run;
   - exact paths removed;
   - protected paths re-verified;
   - post-run worktree registry;
   - skipped/refused commands.

Branch deletion requires separate approval from worktree removal.

## Implementation Protocol

When a lane needs code changes:

1. Prefer a fresh worktree from current `origin/main` unless continuing an
   existing clean PR branch.
2. Cherry-pick or port only classified source files, not raw dirty trees.
3. Keep generated output out of source commits unless the lane explicitly owns a
   generated receipt.
4. Run the narrowest meaningful tests for the lane.
5. For broad governance changes, run the relevant governance hooks or document
   why local environment prevents them.
6. Push and open/update PR only after local verification is recorded.
7. Monitor CI and fix follow-up failures.

## Receipt Requirements

Any completed pass must leave a receipt under the cleanup packet or the lane's
own report directory. The receipt must include:

- date/time and timezone;
- worktree path and branch;
- refreshed `origin/main` SHA;
- commands run;
- current worktree table summary;
- current open PR summary;
- classification changes since the June 25 packet;
- files changed;
- verification performed;
- decisions still requiring the operator;
- exact next action.

If no file changes are made, the final answer must still state the refreshed
state and why no receipt was needed.

## Definition Of Done

The master goal is complete when all of these are true:

1. Current `origin/main`, open PRs, branch tracking, and registered worktrees are
   refreshed and summarized.
2. Every current registered worktree has an up-to-date classification.
3. Active forward lanes are named and ranked.
4. Dirty/protected worktrees have explicit next actions, not vague cleanup
   labels.
5. Any deletion performed has exact-path operator approval and a receipt.
6. Any implementation lane touched has relevant local verification and CI
   status recorded.
7. No unrelated user changes are reverted.
8. No broad cleanup claim is made without command evidence.

## Expected Output Shape

The final response should be short and operational:

```text
Refreshed origin/main: <sha>
Registered worktrees: <n>
Open PRs: <n>; green/draft/red summary
Cleanup packet status: landed/current/stale with path to receipt
Ready lanes: <ordered list>
Blocked lanes: <ordered list with exact blocker>
Deletions run: none, or exact command receipt path
Verification: <commands/checks>
Next move: <one concrete recommendation>
```

## Operator-Level Recommendation

Treat the June 25 cleanup as successful governance work, not as finished repo
hygiene. The safest forward path is:

1. move active development from current `origin/main` or clean PR worktrees;
2. finish the non-code gates for PR #693 and the operator draft decision for
   PR #698 independently;
3. classify and port the remaining source-bearing worktrees one at a time;
4. run exact-path deletion only after approval; and
5. keep onboarding cleanup bulletins as the propagation mechanism for future
   agents.
