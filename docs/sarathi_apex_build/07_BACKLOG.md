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

1. Delete the duplicate `holon/` fork in its own commit after migrating importers.
2. Check known importers:
   - `scripts/verify_holon_harness_prod.py`
   - `tests/test_holon_truth_projection.py`
3. Preserve genuinely useful fork tests or types by porting them to canonical
   modules, not by keeping the fork.
4. Run `python3 scripts/governance/sprawl_guard.py`; it must exit `0`.
5. Run the scoped holon tests and update `06_PROOF_GATES.md` with command output.

## Phase C — facade package + Sarathi source

1. Build fresh thin facades under `dharma_swarm/holon_system/`.
2. Add `tests/test_holon_system_imports.py` proving every facade path imports.
3. Add `dharma_swarm/holon_system/sarathi/{gateway,pulse,roster,brief,scoreboard}.py`.
4. Add only thin runtime wrappers/surfaces under `~/.dharma` after source code exists.
5. Port bridge dialogue/LivingDock additions only as intentional patches with tests.

## Operator-gated cleanup note

The drifted magpie-lineage and `/private/tmp` worktrees are cleanup candidates,
but this lane does not delete them. Cleanup is operator-gated and separate from
Sarathi collapse.
