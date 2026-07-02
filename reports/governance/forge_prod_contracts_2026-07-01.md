# Forge Production Contracts - 2026-07-01

## Scope

This lane implements the first two Forge production-contract candidates:

1. Offline Forge scoreboard and regression harness.
2. Fresh private code-repair taskbed.

It intentionally does not touch the active Forge v1/v2 scoreboard worktree,
PR #723, the Forge Learning Spine scope, either Forge Proving Ground 10/10
worktree, the `forge-swebench` VM, live model routing, Darwin apply paths, or
archive fitness.

## Implemented Surface

- `dharma_swarm.forge_prod_contracts.taskbed`
  - Generates seed-stable private code-repair tasks.
  - Withholds hidden tests from candidate arm manifests.
  - Grades submitted source in a temporary Python subprocess sandbox.
- `dharma_swarm.forge_prod_contracts.scoreboard`
  - Runs `strong_single`, `same_budget_self_moa`, and `swarm_topology` arms.
  - Uses equal budget caps for every arm.
  - Records execution-graded pass/fail rows and aggregate lift.
  - Refuses promotion for the first local shadow contract.
- `dharma_swarm.forge_prod_contracts.receipts`
  - Writes JSON, Markdown, and receipt artifacts with stable hashes and
    authority attestations.
- `dharma_swarm.forge_prod_contracts.cli`
  - Runs the harness from the command line.

## Local Run Evidence

Generated run artifacts are intentionally under ignored `reports/forge/`:

`reports/forge/production_contracts/20260701T0015JST-offline-scoreboard-private-taskbed/`

Files written:

- `scoreboard_report.json`
- `scoreboard_report.md`
- `scoreboard_receipt.json`

Receipt summary:

- run id: `forge-prod-contracts-20260701T0015JST`
- task count: 3
- arms: `strong_single`, `same_budget_self_moa`, `swarm_topology`
- equal budget: true
- contamination state: `fresh_private_local_generated`
- hidden tests withheld from arms: true
- execution graded: true
- strong single baseline: 2/3, average `0.6667`
- same-budget self-MoA: 3/3, average `1.0`
- swarm topology: 3/3, average `1.0`
- swarm lift vs strong single: `0.3333`
- promotion allowed: false
- blocked gates:
  - `shadow_only_first_production_contract`
  - `local_task_count_below_confirm_threshold`
  - `no_independent_external_countercheck`
  - `no_frozen_confirm_manifest`

Authority attestation:

- offline: true
- network calls: 0
- provider keys read: false
- router mutated: false
- Darwin apply called: false
- archive fitness mutated: false
- public benchmark submission: false

## Verification

Passed:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q tests/test_forge_prod_contracts.py --tb=short
/Users/dhyana/dharma_swarm/.venv/bin/python -m dharma_swarm.forge_prod_contracts.cli --run-id forge-prod-contracts-20260701T0015JST --output-dir reports/forge/production_contracts/20260701T0015JST-offline-scoreboard-private-taskbed
/Users/dhyana/dharma_swarm/.venv/bin/python -m compileall -q dharma_swarm/forge_prod_contracts tests/test_forge_prod_contracts.py
git diff --check
env PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH make module-budget
/Users/dhyana/dharma_swarm/.venv/bin/python tools/manifest_check.py
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/docops/check_docops_integrity.py
```

Results:

- focused tests: `6 passed`
- compileall: passed
- diff whitespace check: passed
- module budget: passed
- manifest check: passed
- DocOps integrity: passed

## Remaining Production Gates

This is a production-contract harness, not a live Forge promotion. Before any
router, Darwin, archive, or external claim can use the result, Forge still needs:

- at least a larger frozen private confirm set;
- preregistration and alpha-spending records;
- independent grader/countercheck;
- explicit integration decision with the active Forge v1/v2 lane;
- current-main CI after the files are promoted through PR review.
