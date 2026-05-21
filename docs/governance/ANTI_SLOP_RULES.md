# Anti-Slop Rules (10)

Phase 4 of the governance install. Each rule is anchored to a canonical
surface verified during the 2026-04-26 audit. The full rule definitions
live in `.semgrep/dharma-anti-slop.yml`, plus three GitHub Actions
workflows for things Semgrep cannot express.

| # | ID | Where | Severity | Status |
|---|---|---|---|---|
| 1 | `dharma.no-unauthorized-dharma-write` | `.semgrep/dharma-anti-slop.yml` | WARNING | Active (advisory) |
| 2 | `dharma.no-new-substrate` | `.semgrep/dharma-anti-slop.yml` | WARNING | Active |
| 3 | `dharma.test-no-default-state` | `scripts/governance/check_test_hygiene.py` (Semgrep auto-excludes `tests/`) | warn-only locally, hard fail on PR for NEW offenders | Active |
| 4 | `dharma.scripts-no-git-add-all` | `.semgrep/dharma-anti-slop.yml` | ERROR | Active — 1 known violation in `dharma_swarm/build_engine.py:269` |
| 5 | `dharma.tests-no-dgc-subprocess` | `scripts/governance/check_test_hygiene.py` (Semgrep auto-excludes `tests/`) | hard fail on PR | Active |
| 6 | `dharma.providers-canonical` | `.semgrep/dharma-anti-slop.yml` | WARNING (→ ERROR after offender fix) | Active |
| 7 | `dharma.no-lf5-whole-file-restore` | `.github/workflows/commit-lint.yml` | hard fail on PR | Active |
| 8 | `dharma.no-root-markdown` | `.github/workflows/structure.yml` | hard fail on PR | Active |
| 9 | `dharma.no-committed-guardian-report` | `.github/workflows/structure.yml` | hard fail on PR | Active |
| 10 | `dharma.module-line-budget` | `.github/workflows/module-budget.yml` + `scripts/governance/check_module_budget.py` | hard fail on PR | Active |

## Known offenders (fix before promoting Rule 3 / Rule 4 / Rule 6)

Three violations were known at the time the rules were introduced.
Each gets its own micro-PR; once all land, promote the corresponding
rule severity from WARNING to ERROR (or, for Rule 4 already at ERROR,
remove the inline allowlist).

- **Rule 3 (`test-no-default-state`)**:
  `tests/test_full_loop.py:343` — `state = RuntimeStateStore()` without
  `db_path=tmp_path / "test.db"`. Auto-allowlisted in
  `scripts/governance/check_test_hygiene.py::known_offender_3()`.
- **Rule 4 (`scripts-no-git-add-all`)**:
  `dharma_swarm/build_engine.py:269` — `subprocess.run(["git","add","-A"],
  cwd=project_path, ...)` inside `_git_commit()` for the build engine's
  managed projects. Either pass an explicit pathspec or document why
  this specific path is allowed.
- **Rule 6 (`providers-canonical`)**:
  `dharma_swarm/autonomous_agent.py:468` — direct `from anthropic import
  AsyncAnthropic`. Either move into `providers.py` or call through the
  existing factory. Plus 3 `experiments/` files (`live_pulse_v3.py:106`,
  `live_pulse_v4.py:138`, `petri_dish/llm_client.py:35`) — research
  scratch code; either migrate to canonical providers or extend the
  allowlist with `experiments/` if research velocity matters more.

## Grandfathered modules (Rule 10)

These modules already exceed the 1000-line budget at install time and
are grandfathered. Each gets a tracking issue tagged `decomposition`.
Each is allowed to grow up to **+10%** beyond its grandfathered line
count before Rule 10 fails.

| Module | Lines (2026-04-26) | Ceiling (+10%) |
|---|---|---|
| `dharma_swarm/dgc_cli.py` | 7115 | 7826 |
| `dharma_swarm/thinkodynamic_director.py` | 5215 | 5736 |
| `dharma_swarm/telos_substrate.py` | 4511 | 4962 |
| `dharma_swarm/agent_runner.py` | 3691 | 4060 |
| `dharma_swarm/evolution.py` | 3401 | 3741 |
| `dharma_swarm/swarm.py` | 3252 | 3577 |
| `dharma_swarm/providers.py` | 3096 | 3405 |
| `dharma_swarm/orchestrator.py` | 2525 | 2777 |
| `dharma_swarm/tui/app.py` | 2520 | 2772 |
| `dharma_swarm/terminal_bridge.py` | 2192 | 2411 |

When one of these crosses its ceiling, the PR fails until either:
- the file is decomposed (preferred), or
- the GRANDFATHERED dict in `scripts/governance/check_module_budget.py`
  is updated AND the corresponding decomposition tracking issue is
  linked in the PR description with a concrete decomposition plan.

## Allowlists by rule

### Rule 1: `~/.dharma` write owners (do not extend casually)
Verified during audit; each module owns one slice of `~/.dharma`:
`runtime_state.py`, `system_rv.py`, `daemon_config.py`, `experiment_log.py`,
`pulse.py`, `custodians.py`, `kaizen_ops_local.py`, `scout_report.py`,
`review_cycle.py`, `ginko_backtest.py`, `ginko_evolution.py`.

To add a new owner: open a governance issue, document the surface in
`docs/governance/STATE_DIR_OWNERS.md` (create if needed), then update
`.semgrep/dharma-anti-slop.yml` paths.exclude.

### Rule 8: root markdown allowlist
`README.md`, `CLAUDE.md`, `CHANGELOG.md`, `LICENSE.md`,
`INTERFACE_MISMATCH_MAP.md`, `SWARM_HOT_ITEMS.md`, `MODEL_ROUTING_MAP.md`,
`CYBERNETIC_LOOP_MAP.md`, `AGENT_IDENTITY_UNIFICATION.md`.

To add a new root-level `.md`: edit
`.github/workflows/structure.yml` `allow=(...)` and justify in PR.

## Rule testing

`.semgrep/tests/` contains positive (`# ruleid:`) and negative (`# ok:`)
test cases for the four Semgrep rules that are pure Python AST patterns.
Run locally:

```bash
semgrep --test .semgrep/tests/ --metrics=off
```

Expected: `4/4: ✓ All tests passed`.

The non-Semgrep workflows (`commit-lint.yml`, `structure.yml`,
`module-budget.yml`) are tested by intentionally violating each gate
on a draft PR and observing the failure.

## Promotion path

1. Fix the two known offenders (Rule 3 + Rule 6) in their own micro-PRs.
2. Promote Rules 3 and 6 from WARNING to ERROR
   (`.semgrep/dharma-anti-slop.yml` `severity:` field).
3. Re-run `semgrep --test .semgrep/tests/` and the strict gate.
4. Optionally extend Rule 2 (`no-new-substrate`) to ERROR after observing
   for a few PRs — pattern detection accuracy is harder for that rule.
