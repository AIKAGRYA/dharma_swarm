# Anti-Slop Rules (10)

Phase 4 of the governance install. Each rule is anchored to a canonical
surface verified during the 2026-04-26 audit. The full rule definitions
live in `.semgrep/dharma-anti-slop.yml`, plus three GitHub Actions
workflows for things Semgrep cannot express.

Broader vibe-code and AI-agent hygiene signals live in
`docs/governance/hygiene/`. They are measured and reviewed there first; only
mature, low-noise signals graduate into this hard-gate list. Merge Master Mike
consumes the same hygiene layer through `docs/ops/PR_REVIEW_CONTROL.md`.

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

## Rule 2 — closure-layer role vocabulary (PR A.5)

Rule 2 (`dharma.no-new-substrate`) historically flagged any new
`Store/Ledger/Registry/Substrate` class that opens its own SQLite or
aiosqlite connection. The runtime truth spine convergence (PR A / A.5)
formalises a richer answer than "don't": every persistence-substrate
introduction must declare a closure-layer role from the vocabulary below.

The vocabulary is shared between Rule 2 and the spine ownership uplift
guard (`scripts/uplift_guards/check_spine_ownership.py`). The guard
requires a `# spine: <role>` comment on every sqlite/aiosqlite importer
under `dharma_swarm/spine/`; the manifest declares the role of each
canonical receipt in the `correlation_spine:` block of
`ACTIVE_SURFACE_MANIFEST.yaml`.

Role vocabulary:

| Role | Meaning |
|---|---|
| `canonical-store` | Owns the source of truth for its closure layer. Other layers must read through this module, not duplicate the data. |
| `canonical-within-layer` | Receipt-level variant of `canonical-store`. Declares that this layer's receipt is canonical (not a derived view of another layer's). Used in the correlation_spine manifest block. |
| `derived-view` | Read-only projection of a canonical-store. Must not accept writes; rebuilds from the canonical source on demand. |
| `plugin-sink` | Write-only export adapter (e.g. OpenTelemetry). Crashes/data-loss here must not affect canonical state. |
| `cache` | Ephemeral and rebuildable from canonical sources without operator intervention. |
| `legacy-mirror` | Transitional dual-write; scheduled for removal with a tracking issue. |
| `migration-mirror` | Active migration target; becomes a `canonical-store` on cutover with an explicit cutover commit. |
| `exempt` | Documented exception. Must justify in the file header and link the governance issue. |

Doctrine line (verbatim, from CONVERGED_SEAM_AUDIT and the
correlation_spine block):

> Receipts may differ by closure layer. Correlation identity must not.
> Each closure layer may have its own canonical receipt. Cross-layer
> identity continuity is the global invariant.

When a PR adds a new `Store/Ledger/Registry/Substrate` class, the
reviewer should ask: which role above does this declare? If the answer
is "none of these," the change should be reshaped, not waived.

### Detector scope (2026-08-04)

From 2026-04-26 to 2026-08-04 Rule 2's message claimed it caught classes that
"append their own JSONL" while the rule carried zero JSONL patterns — the
config-shape contract tests could not see it. The rule now also detects
append-mode file handles, the SQLite forms it previously missed (local
variables, bare calls, `async def`, context managers), and subclasses of the
three ratified exemptions; a companion rule
(`dharma.no-new-substrate-exempt-name-collision`) catches a substrate that
re-uses a ratified exempt class NAME. **The authoritative statement of what
the detector does and does not catch is Rule 2's own `message:` in
`.semgrep/dharma-anti-slop.yml`**, and it is proven — not asserted — by
`tests/test_semgrep_rule2_behavior.py` running semgrep over
`.semgrep/tests/test_no_new_substrate.py`. Receipts and the 17 findings this
broadening surfaced (OWNER_DEFERRED, unadjudicated):
`reports/governance/titanium/wp0c1r_semgrep_adjudication_2026-08-02.md`,
"Amendment 2026-08-04".

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
| `dharma_swarm/orchestrator.py` | 2923 (re-grandfathered 2026-06-12; was 2525 — issue #582) | 3215 |
| `dharma_swarm/tui/app.py` | 2520 | 2772 |
| `dharma_swarm/terminal_bridge.py` | 2192 | 2411 |
| `dharma_swarm/capital_lab/alpha_evidence.py` | 1251 (grandfathered 2026-06-12 — issue #581) | 1376 |

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

To add a new owner: open a governance issue, declare the new surface in
[`ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml) under the
relevant entity, then update `.semgrep/dharma-anti-slop.yml` paths.exclude.
The manifest is the single owner of declared surfaces — do not create a
parallel `STATE_DIR_OWNERS.md` doc.

### Rule 8: root markdown allowlist
`README.md`, `CLAUDE.md`, `CHANGELOG.md`, `LICENSE.md`,
`INTERFACE_MISMATCH_MAP.md`, `SWARM_HOT_ITEMS.md`, `MODEL_ROUTING_MAP.md`,
`CYBERNETIC_LOOP_MAP.md`, `AGENT_IDENTITY_UNIFICATION.md`, `AGENTS.md`.

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


---

## Addendum — Vibe-Code Audit Cross-Reference (2026-06-07)

**Author:** Devin (Cognition AI) — session `7c5c93b8`
**Source:** [`reports/audits/vibe_code_audit_2026-06-07.md`](../../reports/audits/vibe_code_audit_2026-06-07.md)

The 60-question vibe-code audit (2026-06-07) validated the 10 anti-slop rules
and surfaced additional signals that intersect with existing governance:

### Rule 10 — grandfathered module gap

Five modules exceed 1,000 LOC but are **absent from the grandfathered list**:

| Module | LOC (2026-06-07) |
|---|---|
| `runtime_state.py` | 3,796 |
| `ontology.py` | 2,416 |
| `orchestrate_live.py` | 2,257 |
| `operator_bridge.py` | 1,819 |
| `tui_legacy.py` | 1,795 |

These should either be added to the `GRANDFATHERED` dict in
`scripts/governance/check_module_budget.py` with decomposition tracking
issues, or decomposed before the next module-budget CI enforcement pass.

### Candidate new rule — `dharma.no-duplicate-time-helpers`

76 separate `_utc_now()` / `utc_now()` / `_now()` definitions exist across
the codebase (audit Q29). This is the single largest DRY violation and a
prime candidate for a new anti-slop rule:

- **Scope:** flag any `def` matching `_?utc_now|_?now` that returns
  `datetime` or `str` outside a canonical `_time.py` module.
- **Enforcement:** Semgrep pattern or custom script.
- **Prerequisite:** extract to a shared module first, then gate.

### Axiom A7 — existing import cycles

11 import cycles exist (audit Q13), including a 9-module cycle through the
ontology/revenue/lineage subsystem. Axiom A7 ("no new circular imports")
prevents growth but does not track or retire existing cycles. Suggest
adding the top 5 cycles to the Broken Register.

### Cross-reference to audit findings

| Anti-slop rule | Audit question | Status |
|---|---|---|
| Rule 1 (`no-unauthorized-dharma-write`) | Q24 (eval/exec) | clean |
| Rule 2 (`no-new-substrate`) | Q23 (SQL interp) | 41 sites, most with `noqa` |
| Rule 3 (`test-no-default-state`) | Q2 (weak assertions) | 254 weak-only tests |
| Rule 4 (`scripts-no-git-add-all`) | — | not re-audited |
| Rule 5 (`tests-no-dgc-subprocess`) | — | not re-audited |
| Rule 6 (`providers-canonical`) | — | not re-audited |
| Rule 8 (`no-root-markdown`) | Q9 (dead links) | 390 dead links |
| Rule 10 (`module-line-budget`) | Q12 (>1000 LOC) | 5 unlisted modules |
| Axiom A7 (no new cycles) | Q13 (import cycles) | 11 existing cycles |

*Signed: Devin (Cognition AI) — 2026-06-07T12:50Z*

## Companion docs

The 10 rules above are **enforced** — they hard-fail PRs or warn loudly.
The broader, scan-backed catalogue of vibe-coding antipatterns (54 patterns
across 12 clusters, with per-pattern instance counts against this repo)
lives at:

- [`VIBE_CODE_HYGIENE.md`](VIBE_CODE_HYGIENE.md) — catalogue + remediation
  promotion path (signal → advisory → enforced rule).
- `scripts/governance/vibe_code_scan.sh` — the runnable scan.
- `reports/governance/vibe_code_baseline_2026-06-07.txt` — baseline.

When a hygiene signal recurs enough to deserve enforcement, it graduates
into a new Rule 11+ here (with Semgrep or workflow backing) and the
companion doc records the promotion date.
