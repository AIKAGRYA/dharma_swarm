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
| 11 | Duplicate automated PR dedupe | `pr-dedupe.yml` | Auto-closes older trusted same-repo duplicates of `[automated]`/`[auto]` PRs, keeping the newest |
| 12 | Automerge lane | `automerge.yml` | Auto-enrolls bot/automated PRs; on opt-in + the manifest-required checks green + no changes-requested, dispatches MMM with `merge_when_clean` |

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

## MMM Merge Protocol (pointer)

The merge authority charter for **Merge Master Mike** (conditional-merge
coordinator) is [`MMM_CHARTER.md`](MMM_CHARTER.md). Operational commands and
the gate logic MMM uses to evaluate whether a PR is mergeable live in
[`../ops/PR_REVIEW_CONTROL.md`](../ops/PR_REVIEW_CONTROL.md). Every gate in
this document is a precondition MMM checks; none of them are sufficient on
their own.

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
| `spine-adoption-refresh` | `*spine-adoption*` (anywhere in headRef) | 1 |
| `docops-autorefresh` | `chore/docops-autorefresh*` | 1 |
| `verdict-inter-agent` | `verdict/inter_agent*` | 3 |
| `chore-inter-agent` | `chore/inter-agent*` | 3 |
| `spine-surface-join` | `chore/spine/*` | 2 |

The spine-adoption lane was originally `chore/governance*spine-adoption*`, but
the refresher spawned siblings under `chore/spine-adoption-…`,
`chore/auto-spine-adoption-…`, and `ops/spine-adoption-metric-…`, all of which
evaded the throttle (the #559/#571/#580/#583 pile). The pattern now matches
the intent token anywhere in the headRef so renamed lanes cannot slip through.

Human PRs on non-lane branches are unaffected. To add a new automation lane,
add a `case` arm to the `Resolve intent from headRef` step and a row to this
table in the same PR.

The spine-adoption refresher has used several branch prefixes
(`chore/governance/...`, `chore/auto-spine-adoption...`, and
`ops/spine-adoption-metric...`). The throttle matches the intent token anywhere
in the headRef so renamed refresher branches cannot evade the one-open-PR
limit.

### Rule: Deduplication by intent

The `pr-collision-detect.yml` workflow detects duplicate PRs by:
1. **BR-id overlap** — two PRs citing the same `BR-NNN` identifier
2. **Title prefix match** — bot PRs with identical title prefixes
   (e.g., `verdict(inter_agent):`, `chore(inter-agent):`) that indicate
   the same task attempted multiple times

When duplicates are detected, only the **latest/most complete** PR
should remain open. Earlier attempts should be closed with a comment
linking to the successor.

### Duplicate Automated PR Dedupe (`pr-dedupe.yml`)

The collision detector only warns. The `pr-dedupe.yml` workflow **acts**, but
title markers are not trusted by themselves because this workflow runs under
`pull_request_target` with write permissions. It groups open PRs by normalized
title only when all of these are true:

1. The title carries an automation marker (`[automated]` or `[auto]`).
2. The PR head is in the same repository.
3. The PR has a trusted automation signal: bot author, trusted automation head
   prefix, or maintainer-applied `bot-pr` / `automerge` label.

For any trusted group of 2+ PRs, it closes all but the newest PR (highest
number), comments a governance explanation, and deletes the orphaned branches.
It runs on PR open/reopen, every 6 hours on a schedule, and on
`workflow_dispatch` (with a `dry_run` input). PRs without an automation marker
or trusted same-repo automation signal are never touched, and nothing is ever
merged by this lane.

### Ephemeral snapshot-report PRs (`pr-dedupe.yml`, Pass 1)

An external ops automation (running under a maintainer PAT, not an in-repo
workflow) opens a fresh draft PR every few hours that is a pure **status
snapshot** rather than a change to merge:

- `report(governance): PR lifecycle + spine adoption ops report <timestamp>`
- `chore(governance): refresh spine adoption metric [automated] <timestamp>`

Each title carries a unique timestamp, so the title-grouping dedupe above never
collapses them and they accumulate (12+ at once), burying real PRs. Their data
is a projection already rendered from owners (`make onboard`,
`reports/governance/**`), so a snapshot report should be emitted as an
artifact/comment, never as a standing PR.

Pass 1 of `pr-dedupe.yml` therefore **closes every such snapshot PR outright**
(not keep-newest), comments a governance explanation pointing at the rendered
projection, and deletes the branch. The match is deliberately conservative — a
PR is closed only when **all** hold:

1. The PR head is in the same repository (repo owner).
2. The title carries an automation marker (`[automated]` or `[auto]`).
3. A known snapshot intent matches — either the title phrase (`PR lifecycle +
   spine adoption ops report`, `refresh spine adoption metric`) or the headRef
   lane (`pr-lifecycle-spine`, `spine-adoption-metric`).

A PR that does not match a declared snapshot intent is never touched. If a real
change is mis-titled into this set, reopen it and retitle so it no longer
matches. Runs on PR open/reopen, the 6-hourly schedule, and `workflow_dispatch`
(honors `dry_run`).

---

## 2b. Automerge Lane (`automerge.yml`)

The fully automated merge path for clean bot PRs and simple human PRs.
Opt in by labeling a PR `automerge` (human work) or `bot-pr` (automation
lanes should add it at creation time):

```bash
gh pr edit <N> --add-label automerge
```

Trigger surface: label added, ready-for-review, `check_suite` completion,
review submitted/dismissed, plus an hourly sweep. When **all** status checks
are green/completed, the PR is not a draft, and no review requests changes,
the lane dispatches the existing Merge Master Mike router
(`codex-mention-router.yml`) with `merge_when_clean: true`.

Dispatch markers are keyed to a readiness fingerprint, not just the head SHA:
head SHA, review decision, status-check count, comment count, and review count.
If Mike blocks because reviewer receipts, threads, or checks were not yet
present, later review/comment/check changes can dispatch again for the same
head SHA.

Nothing is weakened: Mike still runs his full deterministic gate
(fourfold-warrant, coherence-delta, CI rollup, unresolved review threads,
reviewer receipts) before arming auto-merge. The lane never merges directly.
Remove the label to leave the lane.

### Required reviewer receipts

Mike's required reviewer receipts are **`copilot,claude`**. Devin is a
*committer* agent (it opens PRs); it does not post review receipts, so
requiring a `devin` receipt left the gate permanently unclearable. If Devin
gains a review surface later, add it back to `REQUIRED_REVIEWERS` in
`codex-mention-router.yml` and the `merge-master-mike-backlog.yml` default.

#### `bot-pr` waiver (trusted automation merges when green)

A PR carrying the **`bot-pr`** label is produced by trusted automation
(`automerge.yml` enrolls bot/automated PRs). For these — and **only** these —
Mike's gate in `scripts/runtime/pr_merge_control.py` (`build_gate`) waives the
human/agent reviewer-receipt requirement and ignores **advisory review-bot**
comment threads, so a genuinely green automation PR can merge without a human
in the loop:

- **Reviewer receipts waived.** The `copilot,claude` receipt requirement is
  dropped (these PRs never receive human reviews); the waiver is surfaced in
  the gate's `bot_pr.waivers` output for transparency.
- **Advisory-bot threads ignored.** Review threads whose every comment is
  authored by an advisory review bot (`ADVISORY_REVIEW_BOTS`, e.g. Greptile's
  `greptile-apps`) post perpetually-unresolved informational summaries that
  never represent a human change request. They are not counted as blocking
  unresolved threads for a `bot-pr`. A thread with **any** non-advisory
  participant (a human, Copilot, Codex, Devin, …) still blocks.

Everything else stays strict, for `bot-pr` and non-`bot-pr` alike: mergeability,
failing/pending CI checks, `CHANGES_REQUESTED`, the Coherence Delta gate, CI
truth, and HIGH/CRITICAL risk all still block. Non-`bot-pr` PRs are unaffected
— they still require the full reviewer receipts and are still blocked by any
unresolved thread, advisory or not. This neither silences Greptile nor relaxes
substance for human reviewers; it only scopes a narrow waiver to trusted,
labeled automation.

---

## 2c. Merge Queue Readiness

When the open-PR count floats high, sequential merging hits the rebase loop:
each merge invalidates every other branch. The long-term fix is GitHub's
**merge queue** + **auto-merge**, which batch-tests queued PRs against a
temporary branch and merge them together.

All gating workflows now carry the `merge_group:` trigger so the queue can be
enabled without stranding required checks:

- **Tree-shaped gates** (`tests`, `docops`, `test-hygiene`, `manifest-check`,
  `semgrep`, `gitleaks`, `codeql`, `active-track`) run **fully** on the
  queued batch -- this is the point of the queue.
- **Batch-aware comparison gates** (`module-budget`) compare the merge-group
  base/head SHAs on `merge_group`, so Rule 10 still evaluates the queued batch.
- **PR-shaped gates** (`coherence-delta`, `fourfold-warrant`, `commit-lint`,
  `structure`) need PR context (body or PR-specific file list) that a
  `merge_group` event does not carry. They already passed on the PR run before
  the PR could be queued, so their jobs skip on `merge_group` (skipped =
  satisfied for required checks).

One-time repository settings (operator action, cannot be done from the repo):

1. **Settings → General** → check **Allow auto-merge**.
2. **Settings → Branches → `main` rule** → check **Require merge queue**.
3. Keep the existing required status checks; they now report on
   `merge_group` events.

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
2. **Apply the packet policy.** Packet-bound preflight and closeout are required
   when changed paths match Merge Master Mike's `HOT_PATH_PATTERNS` in
   `scripts/runtime/pr_merge_control.py`; they are optional otherwise. When
   required, run `make agent-build-preflight PACKET=<path>` before
   implementation work.
3. **Run `make agent-build-closeout PACKET=<path>`** before opening the PR when
   a packet is required or voluntarily used. This runs a no-worktree hygiene
   scan plus `make governance-all`. You do not need to hand-refresh DocOps
   counts — the `docops-autorefresh.yml` feeder reconciles them on the first CI
   run (see §1, "Self-healing DocOps counts").
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
| **Rebase** | Force-rebases conflict-free behind-main branches onto `origin/main` via `pr_ci_safe_rebase.py`, except packet-bound / non-same-repo / race-failed PRs |

### Session Entry branch preservation

The rebase action must never rewrite a PR whose changed-file set contains a
Session Entry packet under `reports/agentops/work_packets/*.json` (current
`.filename` or rename-away `.previous_filename`). Those packets bind `base_ref`,
collision evidence, and packet digest to a specific merge base; an automated
rebase makes those claims stale even when the resulting source tree is
byte-identical.

`pr-ci-health.yml` delegates each candidate to
`scripts/governance/pr_ci_safe_rebase.py` **before** any PR-head
fetch/checkout/rebase/push. The helper is fail-closed and claims only:

1. **Count-bound explicit page enumeration** — `?per_page=100&page=N` raw JSON
   arrays; total entries must equal metadata `.changed_files`. Because the
   endpoint hard-caps at 3000, `changed_files >= 3000` skips (equality is
   ambiguous). When the expected final page is full
   (`changed_files % 100 == 0`, including zero), one sentinel next page must
   return a valid empty JSON array; API failure, malformed JSON, or a
   nonempty sentinel skips. A short final page is proved by its length plus
   exact metadata count.
2. **Current and previous filenames** — both `.filename` and
   `.previous_filename` are checked for the packet prefix + `.json` suffix.
3. **Same-repo / head-SHA / race / lease / restore binding** — head must be
   same-repo; inspected `head.sha` is re-checked after enumeration and before
   push; fetch uses `refs/pull/<n>/head`; push uses explicit
   `--force-with-lease=refs/heads/<ref>:<inspected_sha>`. A valid 40-hex
   restore target (`--restore-to` or `$GITHUB_SHA`) is required before any
   PR-head mutation; restore checkout failures surface as local `ERROR` and
   never retain a `REBASED` success.
4. **API / malformed / count failures skip** — API errors, malformed JSON,
   malformed entries, count mismatch, premature empty pages, sentinel
   failures, missing restore target, or head movement print `SKIP PR #N: …`
   and perform no rewrite.
5. **Owner append-only reseal required** — a packet-bound PR may remain behind
   `main`; only the owner may append a governed reseal and rerun packet
   scope/preflight/closeout. The hourly backstop has no authority to rewrite
   that history.

Branch names and draft status are not safety signals. Local AgentOps closeout
reports are self-reported evidence only; GitHub packet-scope/CI handles are the
external authority.

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
