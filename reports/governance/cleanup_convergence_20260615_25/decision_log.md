# Cleanup Convergence Decision Log

## 2026-06-25 JST - Baseline Selection

Decision: create the convergence worktree from refreshed `origin/main`, not from
the dirty primary checkout.

Reasoning: the task names `origin/main` as the clean baseline. The primary
checkout is on `recover/dharma-capital-2026-06-24`, is far behind `origin/main`,
and has 210 current status lines. Using it as a base would preserve confusion.

Evidence:

- `git -C /Users/dhyana/dharma_swarm fetch origin main`
- `git -C /Users/dhyana/dharma_swarm rev-parse origin/main` -> `a46522040cc6d4ec80cf9f1466a81c7dac33c616`
- `git worktree add -b cleanup/convergence-20260615-25 /Users/dhyana/ds_cleanup_convergence_20260625 origin/main`

## 2026-06-25 JST - Onboard Side Effect Reverted

Decision: run `make onboard` as requested, then restore generated report churn
that came only from the local tool environment.

Reasoning: onboarding in the convergence worktree wrote
`reports/governance/active_track_evidence.*` and `track_portfolio.json` because
this checkout lacked local dependencies such as `pytest` and `pydantic`. Those
edits were environment artifacts, not cleanup-map content.

Evidence:

- `make -C /Users/dhyana/ds_cleanup_convergence_20260625 onboard`
- Generated diff showed tests failed with `No module named pytest`
- Restored only the three generated files changed by onboarding

## 2026-06-25 JST - Preservation Is Sufficient For Non-Destructive Planning

Decision: continue classification work, but do not delete or prune anything.

Reasoning: the June 24 preservation pass has local and off-machine evidence. It
does not authorize deletion by itself; it only closes the immediate loss-risk
blocker enough to classify.

Evidence:

- `BACKUP_RECEIPT.md`: bundle verify OK for shared and old clone bundles.
- `BACKUP_RECEIPT.md`: off-machine archive copied to `agni` and verified OK.
- `BACKUP_RECEIPT.md`: 686 stable recorded files checksum-verified OK.
- `TRIANGULATION_SUMMARY.md`: cleanup should wait for promote/port,
  archive-only, or discard-after-operator-approval classification.

## 2026-06-25 JST - No Whole-Tree Porting

Decision: this branch ports the convergence report packet only. It does not copy
A2A/NATS code, Helm terminal files, Cashclaw artifacts, Forge v1 code, or old
clone files.

Reasoning: source-bearing worktrees are dirty, stale relative to current main,
or require track-specific gates. Copying them here would create another dirty
merge tree and erase ownership boundaries.

Evidence:

- A2A/NATS worktree is 174 behind `origin/main` and has 82 current status lines.
- Helm branch is 57 ahead and needs live-use validation.
- Cashclaw has generated untracked output from 2026-06-10 through 2026-06-14.
- Forge v1 is a clean but separate 24-file branch.
- Old clone is 16 local commits ahead of stale clone origin and far behind current main.

## 2026-06-25 JST - PR Truth Overrides Stale Local Claims

Decision: current git and GitHub state override stale audit assertions when they
disagree.

Reasoning: the June 24 audit is valuable but not timeless. Current evidence
shows PR #648 and #674 are merged, but the local supply-chain worktree still has
additional unmerged local state beyond the merged PR.

Evidence:

- GitHub PR #648: closed and merged at 2026-06-21T13:23:13Z.
- GitHub PR #674: closed and merged at 2026-06-23T22:32:24Z.
- `/Users/dhyana/ds_supplychain_slice` still has local commit `11de04fb7` and
  dirty overlay files.

## 2026-06-25 JST - Palantir Ontology Notes Stay Proposed Only

Decision: add an ontology meta scratchpad under this cleanup packet, but do not
edit `docs/ontology/semantic_objects.yaml` or create new ontology classes.

Reasoning: the user explicitly requested a scratchpad of proposed-only typed
objects and reasoning. The repo already has an ontology roadmap that warns
against `OntologyManager`, `BaseObject`, and `LineageRecord`. A scratchpad is
appropriate; schema mutation is not.

Evidence:

- `reports/audit/palantir_grade_ontology_roadmap_2026-06-16.md`
- `docs/ontology/semantic_objects.yaml`
- `docs/ontology/SEMANTIC_COMMONS.md`
