# Helm track closeout — 2026-07-31

**Track:** `helm-worldclass-terminal-2026-06`  
**Closure kind:** `CLOSED_NOT_PROD`  
**Branch:** `governance/close-helm-track-v2-20260803` (recreated from stranded local
branch `governance/close-helm-track-20260731`, commit 559908042, which never
reached origin — repair lane F6)  
**Closed by:** governance closeout (this receipt)

## Re-proof on current main — 2026-08-03

This closeout was originally authored 2026-07-31 on a branch that fell ~23
commits behind main before it could land. All evidence below was re-executed
2026-08-03 against `origin/main` @ `f3eb5b397`:

| Check | Result (2026-08-03, main @ f3eb5b397) |
|-------|----------------------------------------|
| `cd terminal && bun install --frozen-lockfile && bun test` | 650 pass / 0 fail / 25 files (exit 0) |
| `cd terminal && bun test tests/app.test.ts` | 218 pass / 0 fail (exit 0) |
| `cd terminal && bun test tests/compactShell.test.tsx` | 4 pass / 0 fail (exit 0) |

Environmental caveat (worth recording): the bridge-spawning app tests require a
3.11+ `python3` on PATH (or `DHARMA_PYTHON`) — under macOS system Python 3.9
they fail with union-type syntax errors, which is precisely the checker-
poisoning failure mode this closure fixes. Additionally, `sidebar.test.ts`
asserts `Root <repo-root>` fits an 80-column sidebar line; extremely long
checkout paths truncate it and fail the test (verified: green at
`/private/tmp/f6h`, red under a 90+-char worktree path).

## Claim boundary

This closeout proves:

1. The operator TUI under `terminal/` has a green hermetic behavioral suite on main.
2. The golden-frame verification lane that was the last open blocker already landed on main (PR #1073, #1078).
3. The track checker no longer poisons bun criteria by exporting `DHARMA_PYTHON` into non-Python `command_passes` environments.

It does **not** claim production daemon readiness, external operator SLOs, or a live tmux operator demo.

## Why not `VERIFIED_SLICE`

Lifecycle rule `verified-slice-erases-blockers` forbids reusing an id that had open blockers on the merge base for `VERIFIED_SLICE`. On `origin/main` the track still listed the golden-frame lane as `blocker: true`. The correct single-PR closure is therefore `CLOSED_NOT_PROD` with explicit evidence that the blocker work already shipped under other PRs.

## Evidence (re-runnable)

| Check | Result |
|-------|--------|
| `git merge-base --is-ancestor 1d8dae2943f48e5ef343e67ee7c4ed084e065ea0 origin/main` | true (behavioral suite anchor) |
| `git merge-base --is-ancestor 8965ffa93 origin/main` | true (PR #1073 golden-frame close) |
| `git merge-base --is-ancestor 88458e06f origin/main` | true (PR #1078 live integration) |
| `cd terminal && bun install --frozen-lockfile && bun test` | 650 pass / 0 fail / 25 files |
| `cd terminal && bun test tests/app.test.ts` | 218 pass / 0 fail |
| `cd terminal && bun test tests/compactShell.test.tsx` | 4 pass / 0 fail |
| Golden corpus present | `terminal/tests/golden/{80x24,100x30,120x40}/` + `closeout_receipt.json` |
| Scripts present | `terminal/scripts/golden_capture.sh`, `ratchet.sh` |

## Root cause of residual red criteria

`check_track_status.check_command_passes` exported `DHARMA_PYTHON=<checker interpreter>` into **every** command criterion environment.

The terminal suite treats `DHARMA_PYTHON` as the **bridge** executable (see `terminal/src/bridge.ts`). When the checker is invoked under macOS system Python 3.9, bun tests spawn a 3.9 bridge, hit `requires-python >=3.11` / union-type failures, and exit 1 — even though the same suite is green without that pin.

Fix: export `DHARMA_PYTHON` only for Python/wrapper-shaped commands (`_command_should_export_dharma_python`). Regression test: `test_command_passes_does_not_export_dharma_python_for_non_python`.

## Portfolio change

- Removed `helm-worldclass-terminal-2026-06` from `active_tracks`.
- Appended closed entry under `closed_tracks` with `status: SHIPPED`, `closure_kind: CLOSED_NOT_PROD`.
- Sibling edge `repository-titanium-hardening-2026-07.complements` still names helm; active→closed edges resolve.

## Explicit non-claims

- No production Helm install or launchd service claim.
- No golden_diff live re-capture required for this closeout (corpus + compactShell tests already on main).
- No audience/revenue claim.
