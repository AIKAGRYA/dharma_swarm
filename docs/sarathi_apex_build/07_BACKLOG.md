# 07 — Backlog / Next Exact Work

## Phase A status

Done:

- Clean worktree created at `/Users/dhyana/ds_holon_collapse_20260707`.
- Reversibility gate, runtime seam, execution lease dependency, Sarathi wake
  profile, and scoped tests ported in commit `8a3a2e657` and pushed.
- Front-door docs normalized to the v1.1 read order.
- Orphan maps committed/linked from the front door.
- `scripts/governance/sprawl_guard.py` ported.

## Phase B — collapse spine

Done:

1. Deleted the duplicate `holon/` fork.
2. Migrated the surviving runtime importer in
   `scripts/verify_holon_harness_prod.py` to canonical
   `dharma_swarm.holon_runtime`.
3. Confirmed no `tests/test_holon_truth_projection.py` exists on this clean
   `origin/main` branch.
4. Ran `python3 scripts/governance/sprawl_guard.py`; it exited `0`.
5. Ran the scoped holon tests; `108 passed, 1 warning`.

## Phase C — facade package + Sarathi source

Done:

1. Built fresh thin facades under `dharma_swarm/holon_system/`.
2. Added `tests/test_holon_system_imports.py` proving every facade path imports.
3. Added `dharma_swarm/holon_system/sarathi/{gateway,pulse,roster,brief,scoreboard}.py`.
4. Added thin runtime wrapper/surfaces under `~/.dharma` after source code existed.
5. Ported bridge dialogue/LivingDock additions as an intentional patch with tests:
   unsafe agentic providers are refused, safe overrides resolve through
   `runtime_provider`, and LivingDock context is bounded/evidence-backed.

Remaining beyond this collapse lane:

1. Open/land PR review into `origin/main`.
2. Run an actual unattended Sarathi proof before any `wake_loop_active=true` promotion.
3. Operator-gated cleanup of stale sibling worktrees if desired.

## Operator-gated cleanup note

The drifted magpie-lineage and `/private/tmp` worktrees are cleanup candidates,
but this lane does not delete them. Cleanup is operator-gated and separate from
Sarathi collapse.
