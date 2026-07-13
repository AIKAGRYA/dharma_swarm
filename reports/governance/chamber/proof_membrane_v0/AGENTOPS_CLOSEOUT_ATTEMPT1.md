# AgentOps Report: hyperbolic-time-chamber-WP-O99-proof-membrane-v0-2026-07-14

- Status: failed
- Base ref: `2d2de7b1bfdd982b09334b7154e3e26425c55211`
- Branch: `codex/hyperbolic-chamber-v0-20260714`
- Worktree: `.`
- Commit hash: ``

## Intent

Extend the existing hyperbolic-time-chamber track with one bounded proof membrane: preserve the live DharmaGraph RunCheckpoint fork-alias counterexample as an exact-scope replay bundle, verify it in fresh processes against a corrected control, and demonstrate proposition-specific evaluator-owned promotion authority. Do not fix graph code, add a scheduler, or connect any external simulator to authority.

## Scope

- Scope passed: `True`
- Changed files: `16`
- Violations: `0`

## Gates

| Gate | Expected | Actual | Result |
|---|---:|---:|---|
| diff-check | 0 | 0 | PASS |
| proof-membrane-tests | 0 | 0 | PASS |
| existing-chamber-regression-tests | 0 | 1 | FAIL |
| proof-membrane-semantic-negative-tests | 0 | 0 | PASS |
| graph-adjacent-regression-tests | 0 | 1 | FAIL |
| proof-membrane-ruff | 0 | 0 | PASS |

## Negative Controls

| Control | Expected | Actual | Result |
|---|---:|---:|---|
| agentops-custody-write-probe | 0 | 71 | FAIL |

## Final Git Status

```

```
