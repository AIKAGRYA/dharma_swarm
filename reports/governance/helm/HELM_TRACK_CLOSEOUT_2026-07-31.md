# Helm track closeout — 2026-07-31

**Doc role:** `report` (dated descriptive output)

**Subordinates to:** `docs/governance/ACTIVE_TRACK.yaml` — the canonical track
owner. This receipt replaces no existing doc; it is the evidence attachment for
the `helm-worldclass-terminal-2026-06` entry under `closed_tracks` there. If the
two ever disagree, the YAML wins and this file is history.

**Track:** `helm-worldclass-terminal-2026-06`

**Closure kind:** `CLOSED_NOT_PROD`

**Branch:** `governance/close-helm-track-v2-20260803` (repair lane F6)

**Closed by:** governance closeout (this receipt)

## Re-proof on then-current main — 2026-08-03

The behavioral and closure evidence in this receipt was proved against
`origin/main` @ `f3eb5b397`. The complete pre-closure track contract is
preserved from the PR's repository-reachable merge base
`f2ffb4390c603dc9f8f2c36fcaaca0c4ba0ce9cd`, of which `f3eb5b397` is an
ancestor. The closure was drafted 2026-07-31 on an operator-local branch that
never reached origin; that draft is **not fetchable from this repository and
carries zero evidentiary weight** — no claim here rests on it, and it is
deliberately left uncited rather than presented as a checkable reference. The
work was re-applied semantically on `f3eb5b397` and every check below was
re-executed 2026-08-03; current-head CI binds the resulting closure to the PR:

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

Fix: export `DHARMA_PYTHON` only for Python/wrapper-shaped commands (`_command_should_export_dharma_python`), and explicitly remove any inherited parent value from non-Python child environments. Merely declining to add the variable is insufficient because `subprocess.run(..., env=None)` inherits an operator-level pin. The wrapper allowlist `_DHARMA_PYTHON_WRAPPERS` names **both** repo wrappers that read `DHARMA_PYTHON` as the interpreter (`scripts/governance/run_python_with_repo_env.sh:18-26`, `scripts/governance/run_pytest_with_repo_env.sh:6-7`); their underscore-delimited names cannot match the `python3?|pytest` token regex, so omitting either would reintroduce the checkout-local-`.venv` split-brain for criteria routed through it.

Regression tests: `test_command_passes_does_not_export_dharma_python_for_non_python`, `test_command_passes_scrubs_inherited_dharma_python_for_non_python` (pre-set parent-variable control), `test_every_dharma_python_wrapper_is_pinned` (derives the wrapper set from the scripts themselves, so a new `DHARMA_PYTHON`-honoring wrapper fails until allowlisted), and negative control `test_bun_command_is_not_pinned_negative_control` (broadening the allowlist must not start poisoning bun criteria).

## Portfolio change

- Removed `helm-worldclass-terminal-2026-06` from `active_tracks`.
- Appended closed entry under `closed_tracks` with `status: SHIPPED`, `closure_kind: CLOSED_NOT_PROD`.
- Preserved all 15 pre-closure fields from reachable merge base `f2ffb4390c603dc9f8f2c36fcaaca0c4ba0ce9cd`; only `status` transitions, while closure state and evidence are additive.
- Sibling edge `repository-titanium-hardening-2026-07.complements` still names helm; active→closed edges resolve.
- Managed digest blocks in `CLAUDE.md` and `docs/governance/SOVEREIGN_MANIFEST.md` regenerated via `scripts/governance/render_active_track_includes.py` (never hand-edited); `--check` exits 0.

### Generated DocOps counts deliberately NOT touched

`docs/docops/AUTO_INVENTORY.md` and the asserted count tokens in `SOVEREIGN_MANIFEST.md` are left at main's values on purpose, for two independent reasons:

1. **Ownership.** `docs/docops/AUTO_INVENTORY.md` is inside `repository-titanium-hardening-2026-07`'s `owns:` globs. This PR serves the helm closure, not Titanium, and `CLAUDE.md` puts owned surfaces off-limits except through the owning track's next-items.
2. **The DocOps contract already forbids it.** `.github/workflows/docops.yml:44-47` — "Generated counts … are advisory on PRs: PRs no longer hand-commit them, and docops-reconcile-main.yml reconciles them after each merge." Hand-committing counts in a feature PR is the O(n²) counter cascade that design removed.

Verified with the CI invocation: `python3 scripts/docops/check_docops_integrity.py --report-json reports/docops/check.json --counts-advisory --changed-from f3eb5b397` → **exit 0** ("DocOps integrity checks passed"; count drift reported as WARN, as designed). Pre-existing count drift on main is `docops-reconcile-main.yml`'s job, not this closure's.

## Explicit non-claims

- No production Helm install or launchd service claim.
- No golden_diff live re-capture required for this closeout (corpus + compactShell tests already on main).
- No audience/revenue claim.
