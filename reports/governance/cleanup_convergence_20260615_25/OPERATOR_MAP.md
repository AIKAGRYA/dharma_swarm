# Operator Map

## What Is Real?

- The June 24 preservation pass is real enough for non-destructive cleanup
  planning: bundles verified, checksum manifest verified, off-machine archive
  copied to `agni`.
- The A2A/NATS preflight worktree contains real code, scripts, tests, and a
  locked build specification. It is not junk, but it is stale and dirty.
- The reconciliation worktree contains real governance decisions. Its distilled
  conclusions matter; its raw dump files should not become canon.
- Helm terminal work is real operator-surface work with a dated closeout receipt.
- Forge v1/tokenbroker is real and test-backed according to the DGM report, but
  it is a separate local branch and needs a proposed track or explicit PR lane.
- Anti-slop promotion membrane is real and has landed through PR #685.
- The cockpit extract branch and PR #674 repair branch are already represented
  on current `origin/main`.

## What Is Junk?

- Cashclaw untracked `reports/revenue_wedge/evolution/*` run directories are
  generated output. Preserve them as archive evidence, but do not promote them.
- A2A timestamped readiness/topology/preflight reports are mostly generated
  receipts. Keep one closeout receipt later; do not copy the whole tree.
- Reconciliation raw command captures are forensic evidence, not source docs.
- Missing/prunable tmp worktrees are cleanup candidates after approval.

## What Is Preserved But Not Landed?

- `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618`
- `/Users/dhyana/dharma_helm_build`
- `/Users/dhyana/ds_forge_v1_scoreboard`
- `/Users/dhyana/ds_supplychain_slice` local post-PR work
- `/Users/dhyana/worktrees/dharma_swarm_reconcile_20260622`
- `/Users/dhyana/dharma_swarm_cashclaw`
- `/Users/dhyana/migration_delta/dharma_swarm_old`

## What Should Become PRs?

1. Cleanup convergence map: this report packet.
2. A2A/NATS recovery: rebase the locked spec, core modules, scripts, and tests
   onto current main; exclude bulk generated receipts.
3. Helm terminal: run operator live-use gate, then rebase/open a large-diff
   exception PR with `HELM_CLOSEOUT_2026-06-16.md`.
4. Forge v1/tokenbroker: open or revive an evaluation track, then PR the clean
   branch after current-main rebase and tests.
5. Scheduler federation ADR: port ADR-010 only after operator ratification.
6. Supply-chain thin-loop: inspect commit `11de04fb7` separately from merged
   PR #648 and from the dirty governance overlay.
7. Anti-slop membrane: PR #685 is merged; do not duplicate it here.

## What Should Be Archived?

- Old independent clone `/Users/dhyana/migration_delta/dharma_swarm_old`.
- Cashclaw generated evolution run outputs.
- Reconciliation raw command dumps after this distilled map is accepted.
- Old prod-readiness detached worktree unless the operator requests a digest.

## What Should Be Deleted Only After Explicit Approval?

- `/private/tmp/dharma_nim_main_check`
- `/private/tmp/ds_pr674_merge_check`
- Clean/superseded local worktrees whose HEAD is already on main:
  `/Users/dhyana/worktrees/ds_cockpit_extract_20260623`,
  `/Users/dhyana/worktrees/ds_pr674_rebase_20260624`, and likely
  `/Users/dhyana/worktrees/ds_arena_admit_20260623`
- Any branch, stash, tarball, old clone, or preserved overlay.

## What Feeds The Dashboard/Cockpit?

- Helm terminal branch and closeout.
- Operator-coherence cockpit already on main.
- Mandala `CockpitTopology.tsx` as an idea-only comparison source.
- This convergence packet can feed a future cleanup/cockpit panel showing
  worktree status, class, risk, and next action.

## What Feeds Active Tracks?

- `runtime-truth-nats-2026-06`: A2A/NATS preflight work.
- `runtime-truth-reconciliation-2026-06`: cleanup evidence discipline, read
  model boundaries, and preservation receipts.
- `loop-closure-2026-06`: supply-chain thin loop and Bronze/frontier-council
  follow-up.
- `provider-routing-consolidation-2026-06`: already on main; do not reopen from
  dirty branches.
- `orchestration-arena-v1-2026-06`: arena branch already merged; no cleanup port.
- Proposed/renewed tracks: Helm terminal, Forge v1/tokenbroker, scheduler
  federation, revenue/capital experiments.
