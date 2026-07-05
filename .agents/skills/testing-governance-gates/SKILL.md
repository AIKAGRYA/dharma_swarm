---
name: testing-governance-gates
description: Test dharma_swarm CI governance gates, CI Truth rollups, and automerge advisory/required check behavior. Use when changes touch .github workflows, docs/governance/CI_TRUTH_CONTRACT.json, scripts/runtime/ci_truth.py, or automerge readiness logic.
---

# Testing dharma_swarm Governance Gates

**Purpose:** prove the advisory/required split holds after a change — advisory governance checks may fail without blocking merge, while required checks always block. The invariant under test, in one sentence: **a governance failure is a warning; a required-CI failure is a merge blocker; a change that flips either direction is a bug.**

Definitions (from `docs/governance/CI_TRUTH_CONTRACT.json`):
- **Required check** — listed as required in the contract; failure ⇒ `verdict: FAIL` and an entry in `merge_blockers`.
- **Advisory check** — governance signal (Coherence Delta, ACTIVE_TRACK gate, ...); failure ⇒ `verdict: DEGRADED`, `merge_blockers: []`.

## Environment

- Prefer a clean checkout of `origin/main` or the PR branch under test; run from its repo root (`cd "$(git rev-parse --show-toplevel)"`).
- If the checkout lacks a `.venv`, either `python3 -m pip install -e ".[dev]"` or point `PYTHONPATH` at the clean checkout while borrowing another checkout's venv binary — but only after confirming that venv belongs to this repo and dependency set.
- `make onboard` may regenerate governance reports and dirty the worktree; don't run final assertions in a worktree it just dirtied if those files feed the test.
- No secrets or `GITHUB_TOKEN` needed for local rollup tests — everything below is shell-only against synthetic JSON.

## Procedure

### 1. Advisory-gate test (governance fails, required passes)

Write a synthetic rollup to a temp file:

```json
[
  {"name":"DocOps integrity gate","status":"COMPLETED","conclusion":"SUCCESS"},
  {"name":"Coherence Delta PR body","status":"COMPLETED","conclusion":"FAILURE"},
  {"name":"ACTIVE_TRACK governance gate","status":"COMPLETED","conclusion":"FAILURE"}
]
```

```bash
python scripts/runtime/ci_truth.py --rollup-json /path/to/rollup.json --json
```

Expected: `verdict` = `DEGRADED`; `merge_blockers` = `[]`; `coherence_delta` and `active_track` appear under `advisory` with `status: "FAIL"`.

### 2. Required-check control test (proves the gate still bites)

Same rollup, but set `DocOps integrity gate` to `FAILURE`.

Expected: `verdict` = `FAIL`; `merge_blockers` contains a required-CI blocker for `docops_integrity`; the governance failures remain warnings. **Never ship the advisory test without this control** — a filter that ignores everything also "passes" test 1.

### 3. Automerge filter test

Extract the jq filter from `.github/workflows/automerge.yml` (read it from the workflow at test time — do not paste a remembered copy) and run it against two synthetic `statusCheckRollup` fixtures:

1. Failed `Coherence Delta PR body` + failed `ACTIVE_TRACK governance gate` + failed `pytest (3.12)` → expect `not_green=1`.
2. Only the two failed governance checks → expect `not_green=0`.

Together these prove advisory checks are ignored without ignoring real blocking test failures.

## Output Format

```
GOVERNANCE GATE VERDICT: PASS | FAIL
- advisory-gate test:   verdict=<...> merge_blockers=<...>  (expected DEGRADED / [])
- required-control test: verdict=<...> blocker=<...>         (expected FAIL / docops_integrity)
- automerge filter:     case1 not_green=<n> case2 not_green=<n> (expected 1 / 0)
```

Attach the exact commands and rollup JSON used as artifacts. Command output is the evidence; do not record a screen video for shell-only tests.

## Common Gotchas

- PR check runs go stale after merge — verify against a clean target checkout, not stale PR check UI.
- Small synthetic rollups produce many "missing advisory" warnings because the contract lists many advisory entries. That's fine as long as `merge_blockers` and the targeted advisory statuses match expectations.

## Do NOT

- Do not run only the advisory test — the required-check control is mandatory (a dead filter passes the first test).
- Do not weaken or reclassify a required check to make a test pass; that's the exact failure this skill exists to catch.
- Do not test against a jq filter pasted from memory — read it out of the workflow file in the checkout under test.
- Do not require `GITHUB_TOKEN` or any secret for local rollup tests.
