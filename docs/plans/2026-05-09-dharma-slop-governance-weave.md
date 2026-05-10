# Dharma Slop Governance Weave

Date: 2026-05-09
Status: proposed implementation plan

## Frame

Fallow is not the right center of gravity for Dharma Swarm because the repo is
primarily Python. The right pattern is to build a Dharma-native governance
spine that composes existing analyzers, normalizes their evidence, and adds the
repo's graph, provenance, behavioral telemetry, and multi-agent review layers
over time.

The durable decision is:

- Do not build a parser or analyzer engine first.
- Finish the existing governance ingress first.
- Treat all detectors as sensors.
- Let Dharma own the schema, correlation, routing, ledger, and action policy.

## Ground Truth Checks

The current checkout supports this build order.

- `scripts/governance/route_quality_findings.py` exists and claims to route
  `vulture`, `radon`, `bandit`, `mypy`, `pyright`, and `fallow`.
- Its implemented parser functions and `--all` registry now cover `vulture`,
  `radon-cc`, `bandit`, `mypy`, `pyright.json`, `fallow`, coverage, deptry,
  import-structure reports, and semgrep JSON. **STATUS: partially closed.**
  **RESOLVED 2026-05-09**: local `make pyright`, CI, and the router now use
  `quality-reports/pyright.json`.
- ~~`pyrightconfig.json` targets Python `3.13`, while
  `.github/workflows/quality.yml` installs Python `3.11`.~~
  **RESOLVED 2026-05-09**: `pyrightconfig.json` now declares
  `"pythonVersion": "3.11"`, matching the CI runner.
- ~~`pyproject.toml` configures mypy with `files = ["dharma_swarm/dharma_swarm"]`,
  while the Makefile invokes `mypy dharma_swarm/`.~~
  **RESOLVED 2026-05-09**: `pyproject.toml [tool.mypy] files = ["dharma_swarm"]`
  now matches `Makefile` target `mypy: ... mypy dharma_swarm/`.
- The advisory Tier-A quality stack is already wired through `pyproject.toml`,
  `Makefile`, `.pre-commit-config.yaml`, and `.github/workflows/quality.yml`.

The two config-drift trust blockers are closed. The remaining Phase 0 trust
blocker is report-contract drift: every advertised report needs an emitted
filename and format that the router actually parses in both local and CI modes.

Live-state divergence from the original hygiene-mesh prompt: the pasted plan
treated Python-version and mypy target drift as active blockers. In this
checkout, both are already fixed and should not be reintroduced.

## Critical Files and Existing Assets

Critical files for the first mesh pass:

- `scripts/governance/route_quality_findings.py`: canonical quality-ingress
  router; report-contract coherence is the first trust gap.
- `quality-reports/`: canonical report directory produced by Makefile and CI.
- `.dharma/slop_ledger/<date>.jsonl`: append-only finding ledger target.
- `pyproject.toml`: package and tool configuration source.
- `pyrightconfig.json`: Python type-check target.
- `Makefile`: local quality command source.
- `.github/workflows/quality.yml`: CI quality report source.
- `.pre-commit-config.yaml`: local advisory gate surface.
- `docs/governance/ANTI_SLOP_RULES.md`: existing Dharma anti-slop policy.
- `docs/governance/CI_GATES.md`: existing security gate policy.
- `docs/governance/QUALITY_GATES.md`: coherence source of truth for this mesh.

Existing assets already available:

- local quality report targets for vulture, radon, bandit, mypy, pyright,
  coverage, Fallow, and report routing
- CI report generation for Python quality and dashboard Fallow scans
- existing Dharma Semgrep anti-slop rules
- CI gate documentation for CodeQL, Semgrep, and Gitleaks
- governance docs covering canonical doc ownership, pre-commit policy, and
  anti-slop rules
- GitNexus, memory, witness, kaizen, stigmergy, and runtime traces available as
  later evidence channels

The first mesh pass should compose these assets before inventing new detectors.

## Unified Architecture

### Prevention Layer

Tighten `docs/governance/FOURFOLD_ACTION_WARRANT.md` and the surrounding agent
workflow so high-risk edits receive file-specific constraints before generation.
The goal is to prevent slop from being written, not only detect it after the
fact.

Examples:

- hot-path file warnings before edits
- active interface contract reminders
- known local patterns and anti-patterns
- required verification command hints
- explicit refusal of ceremonial or disconnected code

This track can run in parallel with detector work because it does not depend on
the quality routing internals.

### Ingress Spine

Finish `scripts/governance/route_quality_findings.py` as the canonical ingress
for all quality findings.

Required capabilities:

- parse all Tier-A report formats
- emit one normalized schema
- support `--changed-since main`
- support `--mode pre-commit|ci|nightly`
- write the slop ledger
- produce governance proposals without mutating authority surfaces directly
- keep advisory and blocking behavior separate

### Unified Finding Schema

Every detector must emit this contract before aggregation:

```json
{
  "tool": "vulture",
  "detector_family": "dead_code",
  "issue_type": "unused_export",
  "path": "dharma_swarm/example.py",
  "line": 42,
  "symbol": "unused_function",
  "severity": "medium",
  "confidence": 0.91,
  "introduced": true,
  "owner": null,
  "evidence": "raw detector excerpt or structured edge",
  "suggested_action": "remove, test, inline, split, suppress, or review",
  "mode": "ci",
  "base_ref": "origin/main",
  "commit": "HEAD"
}
```

The schema is the load-bearing contract. All future graph, provenance,
behavioral, semantic, and adversarial layers must emit the same shape.

### Detector Pool

Operational detector tier, finish first:

- `vulture`: Python dead code
- `ruff`: fast lint, import hygiene, autofixable issues
- `radon`: cyclomatic complexity and maintainability
- `xenon` or `lizard`: hard complexity budgets
- git churn: hotspot multiplier
- `bandit`: Python security
- `gitleaks`: secrets
- `semgrep`: custom security and anti-slop rules
- `pip-audit`: dependency vulnerabilities
- `deptry`: missing and unused dependencies
- `pyright`: type analysis
- `mypy`: type analysis
- `pytest-cov`: coverage and cold-path correlation
- `mutmut`: mutation testing, nightly only
- `import-linter`, `tach`, or `grimp`: boundaries and import graph
- Fallow: JS/TS surfaces only, especially `dashboard/`, `terminal/`, and
  `codex_skills/` where applicable

Dharma extension tier, add after the spine works:

- L1 GitNexus graph queries: cold scaffold, mismatch-extending code,
  architecture-boundary violations, isolated clusters
- L2 provenance score: claude-mem, git blame, witness, and session records
- L3 behavioral cold-path score: kaizen, stigmergy, traces, runtime hits
- L4 semantic ensemble: multi-model scoring plus `ginko_brier.py`
- L5 adversarial test generation: nightly proof attempts against suspect code

### Cross-Validator

The cross-validator combines deterministic correlations first, then optional
semantic intelligence.

Deterministic floor examples:

- `vulture` unused plus zero coverage plus not public API means high-confidence
  dead code.
- high complexity plus high git churn means hotspot risk.
- import boundary violation plus active-surface mismatch means architecture
  drift.
- phantom import plus missing dependency means hallucinated package risk.
- no callers plus no tests plus low behavioral hits means cold scaffold risk.

Minimum aggregation rule:

```text
p_raw = 1 - product(1 - weight_i * score_i)

weights:
  structure   0.25
  dead_code   0.20
  complexity  0.20
  ai_slop     0.20
  provenance  0.15

agreement = count(detector_family_score >= 0.35)

if agreement < 2:
    p = min(p_raw, 0.49)
else:
    p = p_raw
```

No single detector family can trigger a blocking action. One detector can warn;
two independent detector families can block a regression.

The semantic ensemble is additive. It must not replace the deterministic floor.
It should use Brier-weighted model performance and diversity tracking. If
ensemble outputs become highly correlated, lower trust in that ensemble.

### Action Router

The action router implements the probability threshold policy:

| Slop probability | Action |
| --- | --- |
| `p < 0.30` | Log to `.dharma/slop_ledger/<date>.jsonl`; no action |
| `0.30 <= p < 0.50` | Warn in PR comment; no block |
| `0.50 <= p < 0.80` | Block only if regression versus `main`; otherwise open ticket |
| `p >= 0.80` | Create auto-refactor branch and PR for human review |

Hard constraints:

- never auto-merge
- never auto-delete
- never block from a single detector family
- never make authority-surface edits without review

Downstream Dharma surfaces:

- governance proposals
- `BROKEN_REGISTER` candidates
- `INTERFACE_MISMATCH_MAP` candidates
- dashboard cards
- nightly review packets

## Operational Surround

The Detector Pool, Cross-Validator, and Action Router define the *spine* of the
mesh. The Operational Surround names the systems that ALREADY EXIST around the
spine and must feed into it (or be fed by it) for the mesh to be load-bearing
under real operation. These are not new constructions; they are the ambient
machinery the spine is being woven into.

### Hourly Health Loop

`com.dharma.hourly-loop` (launchd plist at
`~/Library/LaunchAgents/com.dharma.hourly-loop.plist`, wrapper at
`~/.dharma/cron/tiers/hourly_loop.sh`, prompt at
`~/.dharma/cron/prompts/hourly_loop.md`) fires every hour at `:07` and dispatches
five Explore subagents — repair, cleanup, symmetry, coherence, sensing — that
write evidence to `~/.dharma/audit/hourly_loop/<TS>/` and append summaries to
`~/.dharma/audit/hourly_loop/INDEX.md`, escalations to
`~/.dharma/witness/hourly_loop/escalations.jsonl`, and stigmergy marks to
`~/.dharma/stigmergy/marks.jsonl`.

Integration requirement: hourly-loop findings must emit the unified schema (or
be transformed at ingress by `route_quality_findings.py`) so they merge with
quality-stack findings instead of living in a parallel audit silo. The hourly
loop is the highest-frequency feed; the slop ledger is its right destination.

Auth path: the wrapper unsets `ANTHROPIC_API_KEY` and prefers Max OAuth, with
API key fallback gated by daily cap. This auth-fork pattern is the operational
prerequisite for any other launchd-fired Claude session that should not silently
burn metered API credits.

### Worktree Drift Surveillance

The hourly loop's symmetry lane already detects hot-path drift across
worktrees. As of 2026-05-09T1016: `telic_seam.py` differs by 25.5%,
`runtime_state.py` by 13.7% across `dharma_swarm`, `dharma_swarm_loomwork`, and
`dharma_swarm_doctrine_correction`; `BROKEN_REGISTER.md` is missing from two of
three worktrees.

Schema mapping: `detector_family: structure`,
`issue_type: cross_worktree_drift`, evidence carries the byte-size or symbol
delta plus the SHA of each worktree's HEAD. This is a Dharma-extension-tier
finding (no off-the-shelf tool tracks it) but the schema must accept it.

### Guardian Integration

`dharma_swarm/guardian_crew.py` and `GUARDIAN_REPORT.md` are dharma's existing
agent-review organ. The mesh routes to Guardian along two edges:

- mesh → Guardian: any finding with `severity: high` or `confidence ≥ 0.85`
  generates a Guardian-readable artifact in the standard report shape, so the
  Guardian's existing pipeline ingests new evidence without bespoke wiring.
- Guardian → mesh: Guardian's behavioral findings (agent claimed completion
  without verification, agent skipped a hot-path acknowledgment, agent rewrote
  a substrate file without `[impact-checked]` tag) emit the unified schema
  with `detector_family: provenance` and feed the slop ledger.

Guardian becomes the bridge between agent-behavior detection (which static
tools cannot see) and the mesh (which then aggregates with static evidence
under the same schema).

### Chetana / Cron Hooks

The chetana metabolic clock at `~/.dharma/cron/` already runs five tiers
(`heartbeat` every :05, `deep_sleep` 02:00, `REM` 03:30, `wake` 04:30,
`continuous` 10:00/14:00/18:00) with a `$3/day` budget cap enforced by
`~/.dharma/cron/budget.py`. The mesh attaches to this stack rather than
spawning a parallel scheduler:

- `pre-commit` mode runs against `git diff --staged` (no schedule).
- `ci` mode runs in `quality.yml` per push/PR.
- `nightly` mode runs as a new chetana tier under `deep_sleep` (02:00) so it
  rides the existing budget plumbing and `chetana_cron.sh` dispatch logic.
- `wake` (04:30) emits the morning slop briefing as part of the existing
  daily synthesis. No new cron file needed.

Promotion of a detector from advisory to blocking pre-commit follows the same
discipline as chetana tier promotion: measure false-positive rate against
fixtures, get a witness log of clean baselines, then flip.

### Autonomous Mesh Plug-Points

The router exposes stable plug-points rather than coupling directly to one
daemon or scheduler:

- quality report collector
- normalized finding schema
- cross-validator
- slop ledger writer
- dashboard artifact writer
- work-packet proposal emitter
- hourly-loop summary emitter
- nightly evidence joiner for graph, provenance, behavior, semantic ensemble,
  and adversarial proof layers

Every plug-point consumes or emits the unified finding schema unless it only
transports summaries. This keeps autonomous agents, cron tiers, Guardian, and
dashboard surfaces aligned without creating parallel governance languages.

### Custom Dharma Semgrep Rules

`.semgrep/dharma-anti-slop.yml` and `.semgrep/security.yml` already host 10+
custom rules (unauthorized-dharma-write, no-new-substrate,
scripts-no-git-add-all, providers-canonical, plus a security pack covering
subprocess/yaml.load/eval/exec/pickle/tempfile/requests-verify-False).

New AI-slop signatures land here, NOT in a parallel rule store:

- duplicate-utility patterns (e.g., `_utc_now()` reimplemented per-module —
  59 occurrences as of 2026-05-09)
- `to_dict()` reimplementation across non-base classes (56 occurrences)
- God-Object indicator (single class with > 50 public methods)
- `as` assertions used to bypass type errors in non-test code
- decorator-without-functools-wraps
- async-iterator stub idiom (yield-after-raise) — whitelist pattern, not flag

Each new rule emits the unified schema via the existing semgrep-text parser
once Phase 1 lands.

### Concrete Cleanup Targets

**Closed 2026-05-09** (acceptance proof that the mesh produces actionable signal):

| Target | Tool | Resolution |
|---|---|---|
| 5 bandit HIGH severity (CWE-327 weak hash) | bandit | `usedforsecurity=False` on each call site (`file_lock.py:124,284`, `memory_palace.py:107`, `operator_core/adapters.py:276`, `vector_store.py:266`) |
| 1 truly-unreachable line | vulture | `scout_framework.py:315` — deleted |
| 6 unused npm dependencies | fallow | removed from `dashboard/package.json` |
| 1 unlisted dependency | fallow | added `postprocessing@^6.39.0` |
| 3 intentional yield-after-raise | vulture | tagged `# noqa: B902 — async generator typing` (idiom whitelist) |

**Open queue (highest leverage)**:

- 154 D-grade complex Python functions per `radon cc` — `SwarmManager.tick`
  (grade F, hot-path) and `ginko_backtest.run_backtest` (grade F) are the
  two smoking-gun God Functions.
- 438 `pyright` strict errors — likely 1–2 patterns repeated; one focused
  pass to characterize and batch-fix.
- 806 `mypy` errors — same pattern; pair with the pyright pass.
- 38 modules with maintainability index `< 65`.
- 8 unused TS exports + 23 unused TS type exports + 3 unused class members
  on `DharmaSocket` per `fallow` — dashboard tail.
- `controlPlaneRouteDeck.js ↔ controlPlaneSurfaces.ts` duplicate export —
  needs `.js → .ts` consolidation; 4 importers must be updated atomically.

### Performance Budgets per Surround Surface

| Surface | Cadence | Wall-time budget | Cost budget |
|---|---|---|---|
| pre-commit (changed files) | every commit | `< 30 sec` | n/a (local) |
| CI quality.yml (changed files + context) | per push/PR | `< 5 min` | included in GH Actions allotment |
| hourly loop | every :07 | `< 8 min` | < $0.50/fire if Max-OAuth path is healthy; daily API fallback cap = 5 fires (~$2.50/day max) |
| chetana nightly (`deep_sleep` 02:00) | once per day | `< 10 min` | shares chetana's `$3/day` cap |
| chetana wake briefing (04:30) | once per day | `< 60 sec` | low (Haiku-tier) |

If a detector misses its budget at one tier, it moves to the next slower tier.
The hourly loop keeps a fire-lock at `~/.dharma/cron/state/hourly_loop.lock`
so concurrent fires (in-session CronCreate + launchd plist) never overlap.

`docs/governance/QUALITY_GATES.md` owns the concise gate budgets used for ratcheting:
pre-commit under 5 seconds, CI under 90 seconds, hourly advisory loop under 2
minutes, and nightly under 10 minutes. The surround table above records the
broader operational envelope for existing cron surfaces.

## Runtime Modes

| Mode | Scope | Budget | Allowed detectors |
| --- | --- | --- | --- |
| pre-commit | changed files | `< 5 sec` | ruff, cheap local rules, cached route checks |
| ci | changed files plus context | `< 90 sec` | Tier-A analyzers, Fallow, import graph |
| nightly | full repo | `< 10 min` | GitNexus, provenance, behavior, LLM ensemble, mutmut |

If a detector misses its budget, it moves to the next slower mode.

## Discipline, E2E Verification, and Risks

Implementation discipline:

- docs first, then schema, then parsers, then ratchets
- advisory before blocking
- deterministic correlations before semantic scoring
- one detector family can warn; at least two independent families are required
  to block a regression
- never make cleanup claims without raw evidence or normalized findings
- never auto-delete, auto-merge, or mutate authority surfaces from a quality
  router
- keep the first commit small enough to review without trusting the whole
  future architecture

End-to-end verification path:

1. produce or reuse Tier-A reports in `quality-reports/`
2. route every expected report without silent drops
3. normalize each finding into one schema
4. write ledger JSONL
5. emit a CI-mode summary under the 90-second budget for changed files
6. prove a single detector family cannot produce blocking status
7. prove pyright, mypy, Makefile, and CI agree on Python/package targets

Risks:

- false confidence from a router that advertises unsupported parsers
- quality report filename drift between Makefile and CI
- expensive detectors leaking into pre-commit or CI
- semantic ensemble output treated as authority before calibration
- worktree-local state mistaken for global repo truth
- blocking gates promoted before the ledger has false-positive evidence
- cleanup automation deleting or rewriting code that only appears unused
- governance docs diverging between root `governance/` and `docs/governance/`

## Revised Build Order

### Phase 0 - Trust the Substrate

Duration: 1 to 2 days.

- Confirm `pyrightconfig.json` Python version remains reconciled with CI.
- Confirm mypy config path remains aligned across `pyproject.toml`, Makefile,
  and CI.
- Confirm Makefile, pyproject, pre-commit, and CI invoke the same tool set.
- Keep local/CI report filename drift closed, especially the `pyright.json`
  contract shared by Makefile, CI, and the router.
- Decide whether Fallow should scan `dashboard/` only or also `terminal/` and
  `codex_skills/`.
- Recover or replace the missing `SOVEREIGN_MANIFEST` circular-dependency
  acceptance fixture if that remains part of the Day-1 test.

Exit criteria:

- all quality commands generate reports in `quality-reports/`
- report names match the router's parser registry
- no config target points at a nonexistent package path

### Phase 1 - Finish the Ingress Spine

Duration: 3 to 5 days.

- Verify and fixture existing parsers for mypy, pyright JSON, Fallow JSON/text,
  coverage, deptry, import-linter, tach or grimp, and semgrep JSON.
- Implement the unified schema as typed Python models.
- Add `--changed-since`.
- Add mode-aware budgets.
- Add deterministic cross-validation floor.
- Emit `.dharma/slop_ledger/<date>.jsonl`.
- Keep everything advisory.

Exit criteria:

- `make quality` routes all generated reports without dropping tools.
- `slop-verify <path> --mode ci` returns normalized JSON.
- A fixture test proves no single detector can trigger blocking status.

### Phase 2 - Add Missing Operational Detectors

Duration: 2 to 3 days.

- Add Ruff.
- Add deptry.
- Add import-linter or Tach, backed by `ACTIVE_SURFACE_MANIFEST.yaml`.
- Add optional `ai-slop-detector` and `sloppylint` as advisory AI-slop sensors.
- Keep `desloppify` and `gptlint` out of the blocking path until measured.

Exit criteria:

- each detector emits the unified schema
- each detector has one fixture test
- each detector has a mode assignment

### Phase 3 - L1 Structural GitNexus Layer

Duration: 3 to 5 days.

- Add graph-query adapters for cold scaffold, mismatch extension,
  boundary-violating imports, and isolated clusters.
- Emit graph evidence as normal findings.
- Compare graph output against import-linter or grimp to estimate correlation.

Exit criteria:

- graph detectors produce findings without replacing static tools
- findings include symbol or edge evidence
- graph detectors are nightly or CI-only unless cached

### Phase 4 - Advisory to Blocking Promotion

Duration: ongoing.

- Promote one gate at a time.
- Start with low-false-positive checks such as Ruff, Bandit high severity,
  Gitleaks, and clear Semgrep rules.
- Use the ledger to measure false-positive rate before promotion.

### Phase 5 - Semantic Ensemble

Duration: 1 to 2 weeks.

- Add multi-model file scoring as detector adapters.
- Aggregate through Brier-weighted scores.
- Track diversity and correlation drift.
- Keep ensemble findings advisory until calibrated.

### Phase 6 - Provenance Layer

Duration: 1 week.

- Join git blame, witness logs, claude-mem, and session records.
- Use provenance as a confidence multiplier, not a standalone verdict.
- Lower trust in code produced without tests or verification.

### Phase 7 - Behavioral Layer

Duration: 1 week.

- Join kaizen, stigmergy, trace, and runtime hit records.
- Feed last-executed and never-executed signals into dead-code scoring.
- Keep production behavior evidence separate from static reachability.

### Phase 8 - Adversarial Proof Layer

Duration: 1 to 2 weeks.

- Generate adversarial tests for high-risk functions.
- Run nightly only.
- Store failures as evidence and successful breakage as refactor candidates.

## Day-1 Acceptance Target

The first useful version does not need all eight phases. It must do the
following:

- rank Python modules by slop probability
- route all current Tier-A reports into one schema
- detect high-confidence dead-code candidates through multi-signal agreement
- detect complexity hotspots with file and symbol evidence
- complete CI-mode scan in under 90 seconds on changed files
- write a ledger without mutating authority surfaces
- execute one read-only E2E path from expected report discovery to normalized
  findings, ledger append, and advisory summary

## Open Decisions

- Use `import-linter`, `tach`, or both for architecture contracts.
- Decide whether `ai-slop-detector` and `sloppylint` are pinned dependencies or
  optional nightly probes.
- Decide whether `gptlint` is useful for JS/TS only or excluded.
- Decide where dashboard cards are produced: existing dashboard API, static
  artifact, or governance report first.
- Decide whether `route_quality_findings.py` remains the CLI or becomes a thin
  wrapper around `dharma_swarm/slop/`.

## Recommended Next Commit Scope

The safest first commit is documentation coherence plus the smallest router
trust repair. Because pyright and mypy drift are already fixed in this checkout,
do not include those config edits unless a later checkout proves they regressed.

Revised first-commit scope:

- add `docs/governance/QUALITY_GATES.md` as the single source of truth for Python
  version, package target, report filenames, modes, budgets, and ratchet policy
- add or update `docs/governance/HYGIENE_MESH.md` only as a hygiene-governance index
- update this plan with operational surround and live-state drift corrections
- add parser coverage for currently advertised reports only if the worker lane
  allows code edits
- add schema skeleton and tests only in a later code lane
- keep the router advisory and read-only

This ships real value without committing to the full 6 to 10 week architecture
up front.
