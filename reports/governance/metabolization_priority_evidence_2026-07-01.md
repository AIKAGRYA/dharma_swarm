# Metabolization Sweep Priority Evidence - 2026-07-01

This packet records the judgement-heavy items from the 2026-07-01 ecosystem
audit without forcing a merge choice. The terminal ledger points here for items
that are intentionally `flagged_for_operator`.

## Scope Boundary

- Source checkout under audit: `/Users/dhyana/dharma_swarm`.
- Sweep integration checkout: `/Users/dhyana/ds_metabolization_sweep_20260701`.
- The sweep did not delete worktrees, delete branches, force-push, push main, or
  choose between competing architecture lines.
- The shared checkout was treated as read-only for source triage; fixes and
  governance artifacts were prepared in the isolated clone.

## Vector Fallback Guard

Status: `pr_opened`

- Clean branch: `codex/metabolize-vector-fallback-guard-20260701`.
- Draft PR: <https://github.com/AmitabhainArunachala/dharma_swarm/pull/736>.
- Validation: `/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q tests/test_vector_store.py`
  returned `30 passed, 24 warnings`.

This closes the audit's highest-leverage small fix without carrying unrelated
`agent/magpie-seed` WIP into the PR.

## DarwinEngine Reconciliation

Status: `flagged_for_operator`

Audit evidence:

- `/Users/dhyana/dharma_swarm/docs/governance/AUDIT_2026-07-01.md:62`
  confirms DarwinEngine is live and records the unreconciled caveat.
- `origin/main` contains targeted commit `dbdd24167`:
  `fix(evolution): honest archive status, real gates_passed, lineage parent_id (#562)`.
- The local `agent/magpie-seed` side contains `260a11539`:
  `snapshot: preserve agent/magpie-seed WIP before metabolize (rescue; guards intentionally bypassed)`.
- The focused delta between `dbdd24167..260a11539` across
  `dharma_swarm/evolution.py`, `dharma_swarm/archive.py`,
  `dharma_swarm/dgm_loop.py`, and `tests/test_evolution.py` is
  `4 files changed, 77 insertions(+), 103 deletions(-)`.
- `260a11539` is not a narrow evolution fix; it is a broad rescue snapshot with
  hundreds of files changed and its subject explicitly says "rescue".

Operator decision needed:

1. Treat `origin/main`/#562 as the canonical evolution status fix unless a
   focused review proves the rescue snapshot contains a needed follow-up.
2. Diff only the evolution/archive status logic first; do not promote the broad
   rescue snapshot as a DarwinEngine fix.
3. Keep archive-fitness mutation and self-modifying production paths gated until
   this reconciliation is explicit.

## SWE-Bench / Forge Consolidation

Status: `flagged_for_operator`

Audit evidence:

- `/Users/dhyana/dharma_swarm/docs/governance/AUDIT_2026-07-01.md:66`
  records 152 real Docker-graded runs, zero positive lift candidates, and
  fragmentation across inconsistent forge worktrees.
- `/Users/dhyana/dw-worktrees/mem/reports/forge/FORGE_CANONICAL_INDEX.md`
  states that no single production-grade 100-iteration external loop exists and
  that the strongest official external path is the Forge v1 SWE-bench Verified
  runner under `/Users/dhyana/ds_forge_v1_scoreboard`.
- PR #723 (`codex/routing-canon-20260630`) carries a Forge v1/v2 surface with
  `dharma_swarm/forge_v1/forge_v2/provenance.py` and related v2 code.
- PR #734 (`codex/forge-prod-contracts-20260701`) carries a shadow-only
  production-contract scaffold. Its adversarial council synthesis concludes
  `SHADOW ONLY` and says the current fixture lift is not evidence that Forge
  beats a strong baseline.

Current forge-related worktrees seen in the latest sweep include:

- `/Users/dhyana/ds_forge_v1_scoreboard` -
  `forge-v1/tokenbroker-scoreboard-20260620`, dirty, legacy scoreboard and
  SWE-bench runner evidence.
- `/Users/dhyana/ds_routing_canon_20260630` -
  `codex/routing-canon-20260630`, clean, PR #723.
- `/Users/dhyana/ds_forge_prod_contracts_20260701` -
  `codex/forge-prod-contracts-20260701`, dirty, PR #734 plus local council
  artifacts.
- `/Users/dhyana/ds_forge_proving_ground_10_10_20260626` and
  `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626` -
  proving-ground variants with local dirty state.
- `/Users/dhyana/ds_forge_spine_v0` and
  `/Users/dhyana/ds_forge_nvidia_foundry_mvp_20260701` -
  additional forge-labeled active worktrees.

Operator decision needed:

1. Pick one canonical integration root before merging any more Forge surfaces.
   A conservative default is to keep PR #723 and PR #734 as draft evidence
   lanes, not a single production claim.
2. Declare `ds_forge_v1_scoreboard` the evidence archive for historical
   SWE-bench Docker runs until its runner is promoted through a focused PR.
3. Treat PR #734 as shadow-only unless the fixture arms are renamed or replaced
   by real arm adapters and hidden tests move out of repo source.
4. Do not mutate Darwin fitness, routing, public claims, or benchmark
   submissions from Forge results until the canonical root and missing design
   elements are closed.

## Ledger Policy Used

The terminal statuses in `metabolization_sweep_ledger.jsonl` use conservative
rules:

- `pr_opened`: an open GitHub PR exists for the branch head.
- `keep_active`: a remote tracking ref, a stale local branch shadow whose
  matching `origin/<branch>` ref is still live, the primary live checkout, the
  current sweep branch before PR publication, or an active local
  worktree/branch that should not be archived silently.
- `archived`: a local branch has no unique commits relative to `origin/main`, or
  a stale ledger item is no longer present in the latest full scan and has no
  matching live remote-tracking ref. Archived rows must carry either an archive
  tag or a PR artifact; the verifier fails on artifact-free archived rows.
- `flagged_for_operator`: unique unmerged local branch tips, dirty worktrees,
  detached scratch checkouts with local edits, DarwinEngine reconciliation, and
  Forge consolidation states that need human choice.
