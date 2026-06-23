# Resolved: `render_active_track_includes.py --check` discrepancy — 2026-06-23

## The contradiction (across multiple agent runs)

- Prod-grade review packet reported: `render_active_track_includes.py --check` = **FAIL** on clean `origin/main`.
- An independent verification reported: same command = **PASS** on clean `origin/main`.

Both were technically observing real outputs. Neither isolated the cause.

## Root cause (settled by direct test in a clean disposable origin/main worktree)

The result depends entirely on **which Python interpreter runs the check**, not on repo state:

| Interpreter | `--check` exit | Reason |
|---|---|---|
| system `python3` | `1` (FAIL) | `ModuleNotFoundError: No module named 'yaml'` path -> renderer falls back to a stdlib YAML-subset parser whose whitespace handling differs, producing a spurious whitespace-only diff in managed blocks |
| repo `.venv/bin/python` (PyYAML 6.0.3, 3.13.12) | `0` (PASS) | canonical YAML parse, managed blocks render byte-identical |

Worktree was confirmed clean (`git status --short` empty) for both runs.

## Verdict

This is an **environment artifact, not a governance defect.**

- The managed blocks in `CLAUDE.md`, `SOVEREIGN_MANIFEST.md`, `BUILD_SESSION_ENTRYPOINT.md` are **NOT actually stale** on `origin/main`.
- The "rendered include check fails" blocker recorded in `PROD_GRADE_REVIEW_RESULTS_2026-06-22.md` should be **downgraded**: it is a clean-tree dependency problem (default `python3` has no PyYAML), the same root cause as the `make orient` / runtime-truth degradation noted in that same packet.

## Action

- Do NOT re-render managed blocks to "fix" this; that would create a spurious whitespace commit.
- The real fix is the dependency-honesty follow-up already on `runtime-truth-reconciliation-2026-06`: governance entrypoints must use the repo venv (or fail loud with a remediation line), never silently fall back to a parser that changes output.
- This single fix clears THREE separately-reported "blockers" (render check, make orient, runtime-truth render) because they share one cause: clean tree has no dependency env.
