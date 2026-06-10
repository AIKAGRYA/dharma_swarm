# PR Quality Gates & Governance Rules

This document defines the quality gates every pull request must pass, the
lifecycle rules that keep the PR backlog healthy, and the onboarding
expectations for agents and contributors.

---

## 1. Quality Gates (CI Enforcement)

Every PR targeting `main`, `promote/**`, `governance/**`, or `codex/**`
must pass these gates before merge:

| # | Gate | Workflow | Enforcement |
|---|------|----------|-------------|
| 1 | Coherence Delta body fields | `coherence-delta.yml` | Hard-fail if the 4 fields are missing or UNKNOWN |
| 2 | Fourfold Shakti Warrant | `fourfold-warrant.yml` | Hard-fail on BLOCK/HOLD verdict |
| 3 | DocOps integrity | `docops.yml` | Hard-fail on count drift or TTL violations |
| 4 | Test hygiene (Rules 3 + 5) | `test-hygiene.yml` | Hard-fail (currently warn-only for legacy) |
| 5 | Structure (Rule 8) | `structure.yml` | Hard-fail on new repo-root `.md` files |
| 6 | Module budget | `module-budget.yml` | Hard-fail on budget overrun |
| 7 | CodeQL / Semgrep / Gitleaks | `codeql.yml`, `semgrep.yml`, `gitleaks.yml` | Hard-fail on secrets; advisory on CodeQL |
| 8 | PR collision detect | `pr-collision-detect.yml` | Warning comment (non-blocking) |
| 9 | Intent PR limit | `bot-pr-limit.yml` | Hard-fail when an automation lane (headRef pattern) has more open PRs than its declared limit |
| 10 | Stale PR lifecycle | `stale-pr.yml` | Warning label at 11 days (bot) / 27 days (human); auto-close at 14 / 30 |

### Local pre-flight

Before opening a PR, run locally:

```bash
make governance-all       # full governance gate bundle
make test-smoke           # quick smoke tests
make semgrep              # security rules
make gitleaks             # secret scanning
make docops-integrity     # documentation invariants
```

### Self-healing DocOps counts (why gate #3 rarely blocks anymore)

Gate #3 (DocOps integrity) verifies that count-sensitive generated sections
(file / test / module counts) match the filesystem. Historically *any* PR that
added or removed a file invalidated those counts and the read-only gate failed,
so nearly the entire queue sat blocked until someone hand-ran the repair. That
failure mode produced the 57-PR jam of 2026-06-05.

This is now self-healing. The `docops-autorefresh.yml` feeder runs on every
same-repo PR (triggers on `pull_request` to `main`, `promote/**`,
`governance/**`, plus `workflow_dispatch`). It reuses the existing writer
`scripts/docops/check_docops_integrity.py --write-auto-sections`, refreshes the
generated count sections, and commits them back to the PR head branch with
`--force-with-lease`. It adds no new writer (Axiom A2), performs no merge
(Merge Master Mike still owns merges), and skips forked-PR heads for safety.

Practical consequence for authors and reviewers:

- You do **not** need to hand-refresh counts before opening a PR. Push your
  change; the feeder reconciles counts on the next CI run.
- If gate #3 still fails after the feeder ran, the drift is *real* (a
  hand-edited count section, or a count section the writer does not own) and
  must be fixed by hand.
- The feeder only runs for same-repo branches. Fork contributors must run
  `make docops-integrity` and commit the refresh themselves.

---

## 2. Intent PR Proliferation Control

### Rule: Max open PRs per intent lane

Automation lanes are identified by **headRef pattern**, not by author login.
The original gate was scoped to `[bot]`-suffixed logins, but the actual dupe
spawners (governance/spine-adoption-refresh, docops-autorefresh, etc.) run
under human PATs, so the bot filter never matched. Throttling on intent
(what the PR is _doing_) catches duplication regardless of author. See #533.

Declared lanes and limits (defined in `.github/workflows/bot-pr-limit.yml`):

| Lane | headRef pattern | Max open |
|---|---|---|
| `spine-adoption-refresh` | `chore/governance*spine-adoption*` | 1 |
| `docops-autorefresh` | `chore/docops-autorefresh*` | 1 |
| `verdict-inter-agent` | `verdict/inter_agent*` | 3 |
| `chore-inter-agent` | `chore/inter-agent*` | 3 |
| `spine-surface-join` | `chore/spine/*` | 2 |

Human PRs on non-lane branches are unaffected. To add a new automation lane,
add a `case` arm to the `Resolve intent from headRef` step and a row to this
table in the same PR.

### Rule: Deduplication by intent

The `pr-collision-detect.yml` workflow detects duplicate PRs by:
1. **BR-id overlap** — two PRs citing the same `BR-NNN` identifier
2. **Title prefix match** — bot PRs with identical title prefixes
   (e.g., `verdict(inter_agent):`, `chore(inter-agent):`) that indicate
   the same task attempted multiple times

When duplicates are detected, only the **latest/most complete** PR
should remain open. Earlier attempts should be closed with a comment
linking to the successor.

---

## 3. Stale PR Lifecycle

| Actor | Warning | Auto-close | Exempt |
|-------|---------|------------|--------|
| Bot (`[bot]` suffix) | Label `stale` at 11 days | Close at 14 days | Draft PRs |
| Human | Label `stale` at 27 days | Close at 30 days | Draft PRs |

The `stale-pr.yml` cron workflow runs weekly and:
1. Labels PRs approaching their staleness threshold
2. Posts a warning comment 3 days before auto-close
3. Closes truly stale PRs with a governance comment
4. Deletes branches of closed PRs (orphan cleanup)

PRs marked as **draft** are exempt from auto-close but still receive
the stale label as an informational signal.

---

## 4. Onboarding Rules (Agent & Contributor Entry)

Every agent or contributor must:

1. **Run `make onboard`** at session start to see the current operating
   reality (active track, live ops, broken register, PR hygiene summary)
2. **Run `make agent-build-preflight`** before implementation work when the
   session will edit code, docs, tests, workflows, or governance surfaces.
3. **Run `make agent-build-closeout`** before opening any PR. This runs a
   no-worktree hygiene scan plus `make governance-all`. You do not need to
   hand-refresh DocOps counts — the `docops-autorefresh.yml` feeder reconciles
   them on the first CI run (see §1, "Self-healing DocOps counts").
4. **Check for existing open PRs** on the same topic before opening a new one:
   ```bash
   gh pr list --state open --search "<your topic keywords>"
   ```
5. **Fill the PR template completely** — all sections must have content
6. **Mark WIP/scaffold PRs as drafts** — use `[SHELVED]` prefix for
   intentionally paused work

### Bot-specific rules

- Must check open PR count before creating a new PR
- Must search for existing PRs with matching intent before opening duplicates
- Must close superseded PRs when opening a replacement
- Must include `[bot]` identifier in commits for traceability

---

## 5. PR Body Completeness

The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) requires:

- **Why** — problem statement (1-3 sentences)
- **Surface area touched** — checked module list
- **Interface mismatch impact** — checked options
- **Coherence Delta** — 4 mandatory fields
- **Pre-flight check** — BR-id collision verification
- **Verification** — which gates were run
- **DocOps impact** — documentation effect
- **Risk + rollback** — blast radius assessment
- **Checklist** — final review items

The `coherence-delta.yml` gate enforces the Coherence Delta fields.
The remaining sections are enforced by code review convention and
the bot-PR-limit gate (bots that skip the template accumulate
open PRs faster).

---

## 6. Mechanical Backstop (`pr-ci-health.yml`)

An hourly cron workflow provides automated triage and healing:

| Action | What it does |
|--------|-------------|
| **Report** | Classifies all open PRs into categories and updates a tracking issue |
| **Re-run** | Re-triggers failed runs caused by transient infra (umbrella status flakes) |
| **Rebase** | Force-rebases conflict-free behind-main branches onto `origin/main` |

Categories: `green`, `behind_main`, `merge_conflict`, `docops_drift`,
`coherence_delta`, `fourfold_warrant`, `transient_infra`, `real_test_lint`.

---

## 7. Governance Commands Reference

```bash
# Full onboarding view
make onboard

# All governance gates
make governance-all

# Individual gates
make test-hygiene
make docops-integrity
make semgrep
make gitleaks
make module-budget

# PR health triage (requires gh CLI auth)
python3 scripts/governance/pr_ci_health.py --repo AmitabhainArunachala/dharma_swarm

# Track status
python3 scripts/governance/check_track_status.py
```
