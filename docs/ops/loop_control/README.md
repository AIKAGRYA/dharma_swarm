# Loop Control — KILLSWITCH (Tier 2, operator-only)

**Role:** operational contract for the loop kill-switch. This directory and
the workflows that write it are **Tier 2 / referee layer** under the
operator ruling of 2026-07-29 (DOOR = AUTO_WITH_DECORRELATED_REVIEW):
operator hand-merge forever; no automation may modify this surface.

## The switch

- **Path:** `docs/ops/loop_control/KILLSWITCH`
- **Ref:** the dedicated `loop-control` branch — NOT `main`. `main` is
  branch-protected, so an emergency write cannot go through a PR; the
  `loop-control` branch keeps the switch git-versioned, auditable, and
  writable in one tap while leaving `main`'s protections intact.
- **Semantics:** file **present** on `loop-control` ⇒ every lane and
  unattended-merge workflow halts at job start with a non-zero exit — the
  guarded runs show **red with "HALTED BY KILLSWITCH"** while the stop is
  engaged; red-while-halted is deliberate signal, not noise. File
  **absent** (404 on the file or the branch) ⇒ proceed. State-unknown
  (any other API error) ⇒ **fail closed**: the guarded job exits non-zero
  and does nothing.

## Operator ritual (phone, no terminal)

- **STOP:** GitHub app/web → Actions → `loop-emergency-stop` → Run
  workflow. This writes the KILLSWITCH file (timestamped, actor-stamped)
  to the `loop-control` branch. Effective at the next job start of every
  guarded workflow; the hourly sweeps observe it within one tick.
- **RESUME:** Actions → `loop-resume` → Run workflow → type `resume` in
  the confirmation box. Removes the file. A blank or wrong confirmation
  refuses.

Both workflows are `workflow_dispatch`-only — they can never fire on a
schedule or event; each run is a deliberate human tap.

## Guarded workflows (each carries the same first step, "Halt on loop kill-switch")

- `.github/workflows/automerge.yml` — the unattended dispatch lane
- `.github/workflows/codex-mention-router.yml` — Merge Master Mike's
  merge-executing router
- `.github/workflows/merge-master-mike-backlog.yml` — Mike's hourly
  cloud backlog fanout
- All future loop lane workflows (hardening lane, brief, watcher) MUST
  add the same guard step; the test
  `tests/test_loop_killswitch_workflows.py` pins the guard's presence in
  the three chain workflows above and the dispatch-only contract of the
  STOP/RESUME workflows.

## What the switch does NOT do

- It does not block operator hand-merges through the GitHub UI — the
  operator is outside the graph.
- It does not revert anything already merged.
- It does not stop non-merge CI (tests, gates) on open PRs.
