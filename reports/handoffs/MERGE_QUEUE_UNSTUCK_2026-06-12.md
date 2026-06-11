# Merge Queue Unstuck — Operator One-Click Sequence (2026-06-12 ~02:10 JST)

**Author:** fable_5_cursor worker (merge-queue unstick pass)
**Baseline:** `reports/handoffs/FLEET_RESURVEY_2026-06-12.md`
**Authority note:** NO merges were performed. All actions below were PR-branch maintenance
(body fix on #561; merge-origin/main + DocOps regen pushes to #562/#564/#574 PR branches).
Merges remain operator/Mike-gated.

---

## What was done tonight

| PR | Action taken | Result |
|---|---|---|
| #561 provider-honesty-g6 | Appended an honest 4-field Coherence Delta block to the PR body (`gh pr edit 561 --body-file`); content sourced from the PR's own verification section + pre-review packets. No code change. | **Coherence Delta check: PASS** (run 27363198280). MERGEABLE / CLEAN. |
| #562 evolution-archive-honesty | Fresh worktree, reset to origin tip, `git merge origin/main`; one conflict (AUTO_INVENTORY.md, generated) resolved via `check_docops_integrity.py --write-auto-sections`; `pytest tests/test_evolution.py tests/test_evolution_runtime_fields.py` → **102 passed**; pushed `f8fb428bc`. | MERGEABLE; CI re-running at write time. |
| #567 pr-mike make targets | **Not touched** — Devin's janitor refreshed the branch tonight (fba5a5535) and it reads MERGEABLE / CLEAN on its own. | MERGEABLE / CLEAN. |
| #574 qwen/spine-adoption | Fresh worktree off origin tip (local `~/dharma_swarm` checkout is dirty + behind — deliberately untouched); `git merge origin/main`; 5 conflicts, **all generated files** (AUTO_INVENTORY, SOVEREIGN_MANIFEST, active_track_evidence.{json,md}, track_portfolio.json); resolved via `check_track_status.py` + `--write-auto-sections` + manual SOVEREIGN_MANIFEST row sync (675 modules / 392 top-level / 25 bridges / 11,117 test fns / 898 md files / 221,655 md lines); `pytest -k "holon or spine"` → **116 passed, 3 skipped**; pushed `a041e3f0c`. | MERGEABLE; CI re-running at write time. |
| #564 honest-spine handoff | Same procedure; 2 conflicts (both generated); regen + md-count row sync; pushed `3941d39cd`. | CI re-running at write time. |
| #568 A2A retention | **Not touched** — Devin refreshed it tonight (ecfa99f9e); MERGEABLE / CLEAN. | MERGEABLE / CLEAN. |

Zero non-generated conflicts were encountered anywhere — the SEAT_REBASE_PREVIEW prediction held exactly.

## #579 verdict (Coherence-Delta gate-softening PR)

**Do NOT treat #579 as the unblock; it wasn't needed.** #561 was fixed by simply writing the
four required fields into its body — 10 minutes, zero governance surface. #579 is a real
governance change (comment-fallback validation source, label aliases, workflow change to
fetch comments via `gh api`): substance-strict in its tests, but it widens *who* can satisfy
the gate (any commenter, including bots) and is a self-applying meta-PR. That deserves a
deliberate operator review on its own merits, not a side-door merge to unstick a queue.
Recommendation: review #579 separately after the queue clears; it is MERGEABLE and all
checks pass.

---

## Operator one-click merge sequence

Pre-flight (every shell): `unset GITHUB_TOKEN` (stale env token overrides keyring).

**The standing rule: 5 of these 6 PRs touch the two generated counter files
(`docs/docops/AUTO_INVENTORY.md`, `docs/governance/SOVEREIGN_MANIFEST.md`), so each merge
re-dirties the next PR. Merge strictly one at a time and run the refresh loop between each.
Do not batch.**

The refresh loop (run after EACH merge, against the NEXT PR's branch):

```bash
# REFRESH <branch>  — run from a clean worktree/checkout of <branch>
git fetch origin && git merge origin/main --no-edit || {
  # expect conflicts ONLY in the two generated files (+ track-evidence reports on #574-like lanes)
  git checkout --theirs docs/docops/AUTO_INVENTORY.md docs/governance/SOVEREIGN_MANIFEST.md
  git add docs/docops/AUTO_INVENTORY.md docs/governance/SOVEREIGN_MANIFEST.md
}
.venv/bin/python scripts/docops/check_docops_integrity.py --write-auto-sections
# if it still FAILs on manifest-* assertions: hand-sync the named SOVEREIGN_MANIFEST rows
# to the printed live values, re-run until "DocOps integrity checks passed"
git add -A && git commit --no-edit && git push origin HEAD:<branch>
```

The sequence (established order, per A2A_DEVIN_PR_RECONCILE + resurvey):

```bash
# 1. provider honesty (queue head; Coherence Delta now green)
make pr-merge PR=561        # or: gh pr merge 561 --squash

# 2. evolution archive honesty
#    refresh fix/evolution-archive-honesty per loop above, wait for CI green, then:
make pr-merge PR=562

# 3. pr-mike make targets (Makefile-only, no counter files — usually needs no refresh)
make pr-merge PR=567

# 4. spine-adoption lane (lands fable_5_cursor registration + holon substrate)
#    refresh qwen/spine-adoption per loop above (NOTE: this lane also regenerates
#    reports/governance/active_track_evidence.{json,md} + track_portfolio.json via
#    .venv/bin/python scripts/governance/check_track_status.py), CI green, then:
make pr-merge PR=574

# 5. seat lane (~/dharma_swarm_live, organ/03-seat) — open its two-PR split now;
#    it was held only behind this queue (SEAT_REBASE_PREVIEW_2026-06-11.md).

# 6. docs tail, serialized (both rewrite the same counter lines — refresh between):
#    refresh devin/honest-spine-handoff-20260611, CI green:
make pr-merge PR=564
#    refresh devin/1781142673-a2a-retention-proposal, CI green:
make pr-merge PR=568
```

Caveats:

- `mergeStateStatus=BLOCKED` on #562/#574 at write time = required checks still running
  and/or branch-protection review requirement — the operator's review/approve IS the unlock;
  nothing else is missing.
- `~/dharma_swarm` (the main workspace) is checked out on `qwen/spine-adoption`, dirty and
  now ~14 behind its origin. Before working there: stash/commit the local mods, then
  `git pull --ff-only`. The #574 refresh was done in a disposable worktree precisely to
  avoid touching that tree.
- Temp worktrees used tonight: `/tmp/mq_562`, `/tmp/mq_574` (branch `mq/spine-adoption-refresh`),
  `/tmp/mq_564` (branch `mq/564-refresh`). Safe to remove with
  `git worktree remove /tmp/mq_562 /tmp/mq_574 /tmp/mq_564 --force` + `git branch -D mq/spine-adoption-refresh mq/564-refresh` once merged.
- Untouched live lanes (other session): trust-gate (#578), hygiene-lifecycle-v2,
  opus-traverse, governed-recursive. #578 reads CONFLICTING — leave it to its owner.
- #576 (DocOps TTL renewal) and #577 (provider hardening 1a) are MERGEABLE Devin PRs outside
  this queue; merging them mid-sequence will re-dirty counters — slot them after the queue
  or accept an extra refresh loop.
