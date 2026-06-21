---
name: testing-governance-gates
description: Test dharma_swarm CI governance gates, CI Truth rollups, and automerge advisory/required check behavior. Use when changes touch .github workflows, docs/governance/CI_TRUTH_CONTRACT.json, scripts/runtime/ci_truth.py, or automerge readiness logic.
---

# Testing dharma_swarm Governance Gates

Use this skill when validating changes to advisory/required CI gate semantics, automerge readiness, or CI Truth rollup evaluation.

## Devin Secrets Needed

- None for local shell-only testing of CI Truth and automerge jq filters.
- GitHub access is handled by Devin's built-in git/PR tools; do not require `GITHUB_TOKEN` for local rollup tests.

## Environment

- Prefer a clean checkout of merged `origin/main` or the PR branch under test.
- If the checkout lacks `.venv`, you can run Python using the repo snapshot venv from the primary clone, for example:
  ```bash
  PYTHONPATH=/path/to/clean/checkout PATH=/home/ubuntu/repos/dharma-swarm/.venv/bin:$PATH \
    /home/ubuntu/repos/dharma-swarm/.venv/bin/python ...
  ```
- Run `make onboard` in the primary repo before code investigation; it may update generated governance reports, so avoid using that dirty worktree for final assertions if those files affect the test.

## Minimal Advisory-Gate Test

Create a synthetic rollup where required checks pass and advisory governance checks fail:

```json
[
  {"name":"DocOps integrity gate","status":"COMPLETED","conclusion":"SUCCESS"},
  {"name":"Coherence Delta PR body","status":"COMPLETED","conclusion":"FAILURE"},
  {"name":"ACTIVE_TRACK governance gate","status":"COMPLETED","conclusion":"FAILURE"}
]
```

Run:

```bash
python scripts/runtime/ci_truth.py --rollup-json /path/to/rollup.json --json
```

Expected:

- `verdict` is `DEGRADED`.
- `merge_blockers` is `[]`.
- `coherence_delta` and `active_track` appear in `advisory` with `status: "FAIL"`.

## Required-Check Control Test

Create the same rollup but set `DocOps integrity gate` to `FAILURE`.

Expected:

- `verdict` is `FAIL`.
- `merge_blockers` contains a required-CI blocker for `docops_integrity`.
- Governance failures remain warnings, not merge blockers.

## Automerge Filter Test

Use the jq filter from `.github/workflows/automerge.yml` against two synthetic `statusCheckRollup` fixtures:

1. Failed `Coherence Delta PR body`, failed `ACTIVE_TRACK governance gate`, and failed `pytest (3.12)`.
   - Expected `not_green=1`.
2. Only failed `Coherence Delta PR body` and failed `ACTIVE_TRACK governance gate`.
   - Expected `not_green=0`.

This proves advisory checks are ignored without ignoring real blocking test failures.

## Common Gotchas

- PR check runs may be stale after a PR is merged; verify the clean target checkout separately instead of assuming stale PR checks describe current `main`.
- Synthetic rollups with only a few checks will produce many missing advisory warnings because the contract includes many advisory entries. This is okay if `merge_blockers` and the targeted advisory statuses match expectations.
- Do not record a screen video for shell-only governance tests; provide command output artifacts instead.
