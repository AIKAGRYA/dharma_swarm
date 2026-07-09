# Adversarial Due-Diligence Audit — Integrated Master Prompt (2026-07-09)

**Doc role (per `docs/AGENTS.md`):** `working_plan` — a bounded handoff instrument, not repo-level authority. It replaces no existing repo doc: it is the first landing of two operator-authored prompt drafts that previously existed only in chat (an original 6-step version and an expanded v2), which it supersedes. It is subordinate to `CLAUDE.md` and the canonical doc stack; any audit produced from it is a dated `report` artifact, and nothing in this file overrides the repo's own governance owners.

**Provenance.** This document integrates three inputs into one audit prompt (the single current source for this instrument):

1. The original operator audit prompt ("Adversarial Due-Diligence Audit Prompt", ~270k-line framing, 6-step method).
2. The expanded v2 prompt ("Adversarial Due-Diligence Audit Prompt for `dharma_swarm`", 9-step method, systems-programming checks, enterprise maturity scorecard, machine-readable YAML appendix). v2 is a strict superset of v1; every v1 requirement (access statement first, claims-vs-reality ledger, smell hunt, delete-the-logic test-quality standard, no-averaging severity weighting, citation-or-silence rule) is preserved inside the v2 structure below.
3. A session-verified repo snapshot from 2026-07-09 (Appendix A) plus four additional falsifiable hypotheses (#10–#13) derived from live observations that neither prompt contained.

**How to use.** Hand everything from "## THE PROMPT" through the end of this document — including Appendix A — to an auditing agent verbatim, on a fresh clone, with no other repo context. Appendix A is included as dated prior evidence the auditor must re-verify, never trust.

**Status of this file.** It is a prompt + dated snapshot, not a report. It asserts no facts about current system state; every claim in Appendix A carries its observation date and decays from there.

---

## THE PROMPT

# Adversarial Due-Diligence Audit Prompt for `dharma_swarm`

You are conducting independent technical due diligence on a large codebase, in the manner of a skeptical staff engineer evaluating an acquisition target. You have no relationship with the author, no stake in the project's success, and no incentive toward diplomacy. Your only obligation is ground truth: what is actually built, wired together, tested, and running, versus what is merely named, commented, documented, scaffolded, or aspired to.

Be severe about evidence, not tone. The goal is not to insult the project; the goal is to make the next engineering decisions obvious.

The final result must be both human-readable and machine-readable. It must explain in plain English what this system is trying to do, how it ties together, how it resembles or differs from serious corporate/enterprise systems, and how far it is from a legitimate enterprise-grade codebase.

---

## The project

You are auditing `dharma_swarm`, a large mixed-language AI control-plane anchored in Python (on the order of hundreds of thousands of lines). It was built mostly by one developer working in parallel with multiple AI coding agents across many sessions, including Claude Code, Codex, Devin, and others. There was not one continuous human reviewer reading every line.

Per its own documentation, it includes multi-agent orchestration, governance layers, "telos gates," a Darwin/evolution engine, a runtime state spine, a dashboard/control plane, receipts, memory systems, Go "sense organs," a terminal UI, and internal frameworks meant to compare declared capabilities against actual ones.

Treat every one of those descriptions as an unverified claim, not a fact. An impressively named class, file, track, report, or receipt is not evidence the impressive thing is happening. It is only a hypothesis to test against code that is actually imported, called, state-changing, and covered by meaningful tests.

Some naming draws on contemplative/philosophical vocabulary: dharma, telos, witness, gnani, organism, spine, etc., reflecting the author's background. Do not let unfamiliar vocabulary itself count as a red flag. Translate the vocabulary into normal engineering terms and judge only whether the code does what it claims.

This development pattern — many independent AI agents building on one codebase without a single consistent architectural reviewer — has a predictable failure signature:

- redundant reimplementations of the same functionality;
- scaffolding built in one session and never wired into later ones;
- inconsistent conventions that reveal session boundaries;
- documentation that was accurate when written but drifted from code;
- generated "governance" artifacts that look authoritative but are not enforced;
- test suites that prove existence, not behavior;
- local-host state hidden outside the repo;
- "production-ready" language around systems only the author has ever run.

Hunt specifically for those.

The author has separately noticed a recurring pattern in this project: sophisticated-looking internal architecture with little external validation. Check explicitly for evidence of real users, real non-mocked third-party calls, real external benchmarks, real revenue/billing paths, or external humans acting on the system's output — versus internal demos, mock providers, local receipts, and self-referential "production" claims.

---

## Before you start

Start the report with a section titled exactly:

# Before you start

State plainly what access you actually have right now:

- full clone;
- partial clone;
- Cursor workspace;
- uploaded files;
- flattened digest;
- GitHub search only;
- local runtime files;
- CI logs;
- no live daemon access;
- no `~/.dharma` access;
- etc.

Include:

- current branch;
- current commit hash;
- whether the worktree is clean or dirty;
- whether dependencies are installed;
- which commands you ran;
- which commands failed;
- what important context is missing.

If you cannot see the whole repo, say exactly which files or directories would most reduce uncertainty, ranked by priority. Do not substitute generic or hedged analysis for saying "I need X."

Do not begin the audit synthesis until this access statement is complete.

---

## Evidence standard

Documentation, comments, generated reports, active-track files, receipts, dashboards, and self-described governance claims are claims, not proof.

Proof requires at least one of:

1. a reachable execution path from a real entry point;
2. a test that asserts meaningful behavior and would fail if the implementation were removed, inverted, or bypassed;
3. a command you personally ran and can quote, provided the command exercises behavior or replays an independent verifier — merely printing the contents of a generated report or doc (`cat`/`rg` over prose) does not upgrade that content beyond documentation-only evidence;
4. a live runtime artifact whose producer path is also verified;
5. a CI workflow whose actual execution result is available and linked to the current commit.

For every major finding, include:

- Evidence type: code path / test / command run / CI run / live artifact / documentation only.
- Reachability: entrypoint-reachable / imported but not called / test-only / docs-only / dead / unknown.
- Confidence: high / medium / low.
- Reproduction command where possible.
- File path and line/function/class evidence.

No path, no specific claim.

If you did not inspect something, say "not reviewed," not a guess dressed as a finding.

Distinguish explicitly between:

- wired into a real execution path;
- defined but never called;
- referenced only in tests;
- referenced only in documentation;
- generated artifact with no verifier;
- dead or unreachable code;
- live-host-only claim not verifiable from repo.

---

## Minimum commands to run if possible

If the repository is available as a full clone, run at minimum:

```bash
make onboard   # the repo's required front door; treat its rendered prose as claims to verify, but run it first
git rev-parse HEAD
git branch --show-current
git status --short
find . -maxdepth 3 -type f | sed 's#^\./##' | sort | head -300
python -m compileall -q dharma_swarm api scripts
pytest --collect-only -q
make verifier-selfcheck
make test-fast
make lint-blockers
```

Then, if dependencies/tooling are available, run:

```bash
make governance-all
make go-ci
make docops-report
python scripts/governance/check_track_status.py
python scripts/governance/agent_onboard.py
```

If any command cannot run, report it as an audit fact, including exact failure text. Do not silently substitute a document claim for a failed command.

If command runtime is too expensive, run the smallest safe subset and explain exactly what was skipped.

---

## Method

Work in this order. Do not jump to synthesis before doing the legwork.

### 1. Structural recon

Map:

- directory tree;
- major languages;
- file sizes and line counts;
- largest modules/classes/functions;
- package boundaries;
- every real entry point:
  - CLI commands;
  - API routes;
  - FastAPI app;
  - daemon/service entry points;
  - scheduled jobs;
  - Makefile targets;
  - GitHub Actions;
  - Docker/compose entrypoints;
  - terminal/dashboard entrypoints;
  - scripts that appear operational.

Identify the actual spine: the reachable path from operator/user input to task/state/result. Separate that from everything else.

Tag each major component as:

- **LIVE** — reachable from a real entry point and has meaningful behavior;
- **PARTIAL** — some real behavior, but incomplete, fail-open, dev-only, or not fully wired;
- **DORMANT** — defined and maybe tested, but not reachable from normal execution;
- **VAPORWARE** — docs/names/scaffolding with no meaningful implementation.

### 2. Claims harvest

Pull architectural claims out of:

- README files;
- docs;
- active tracks;
- reports;
- docstrings;
- comments;
- generated receipts;
- dashboard copy;
- Makefile target descriptions;
- CI workflow names;
- issue/PR references visible in repo.

This is the vision side of the ledger. Do not treat a claim as true because the repo says it. Claims are things to verify.

### 3. Reality check

For each major claim:

- Is the code imported?
- Is it called from a real execution path?
- Does data actually flow through it?
- Does it mutate durable state?
- Does it have meaningful tests?
- Would those tests fail if the implementation were deleted or inverted?
- Is it only a report/doc/receipt?
- Is there a second, slightly different implementation elsewhere?
- Does the repo claim production behavior but the code only runs in dev/local mode?

### 4. Systems-programming checks

Pay special attention to systems-level correctness, not just application shape.

**State authority.** Identify every durable store:

- SQLite DBs;
- JSONL ledgers;
- generated receipts;
- docs-as-state;
- YAML track files;
- cron files;
- env files;
- dashboard projections;
- memory/vector stores;
- local operator directories such as `~/.dharma`.

For each, answer: What writes it? What reads it? Is it canonical or derived? Can it diverge? Is there migration logic? Is there backup/restore logic? Does it survive daemon restart? Is it repo-local or host-local?

**Crash recovery.** Trace what happens if the process dies:

- before dispatch starts;
- after task claim;
- after provider call starts;
- after provider call returns;
- after receipt write;
- before task completion;
- during DB write;
- during dashboard/API startup;
- during self-modification apply.

**Idempotency.** Identify which side effects are: exactly-once; effectively-once; at-least-once; best-effort; not protected. Be precise. A comment saying "exactly-once" is not enough.

**Concurrency.** Look for:

- SQLite write contention;
- async task leaks;
- duplicate daemon assumptions;
- missing locks;
- file-locking;
- races between boot reconcile and task reaper;
- stale heartbeat windows;
- duplicate provider calls;
- multiple writers to the same state;
- assumptions that only one host/process is active.

**Fail-open vs fail-closed.** For each of these, state whether failure permits action or blocks it:

- provider dispatch;
- auth;
- dashboard/API access;
- governance gates;
- evolution/self-modification;
- key loading;
- runtime state;
- receipt writing;
- memory retrieval;
- CI gates;
- external tool calls.

A fail-open path may be acceptable in dev mode and unacceptable in production. Say which.

**Trust boundaries.** Map: user input; API input; WebSocket input; model-provider calls; shell execution; subprocess calls; file writes; repo mutation; secrets; database writes; dashboard routes; external web/network calls; CI workflow authority.

**Deployment reality.** Distinguish: local/dev mode; author laptop mode; macOS launchd mode; daemon-host mode; Docker/compose mode; CI mode; actual production mode. A feature that only works in one mode should be labeled that way.

**Operator dependency.** Identify anything that depends on: the author's local `~/.dharma`; macOS keychain; launchd plists; shell profile; uncommitted files; local cron state; manually refreshed status; manually provisioned keys; local daemon receipts.

### 5. Smell hunt

Search for:

- `pass`;
- `NotImplementedError`;
- `TODO` / `FIXME`;
- stub / mock / fake / placeholder;
- always-passes / hardcoded success;
- broad `except Exception`;
- silent exception swallowing;
- `shell=True`;
- `eval`;
- unreachable code;
- dead imports;
- near-duplicate modules (copy-pasted near-duplicate blocks);
- God files/classes;
- circular imports;
- config flags nothing reads;
- abstraction layers with exactly one real implementation;
- tests that assert only that something exists;
- generated reports with no verifier;
- mocked or hardcoded logic dressed up as a real integration.

### 6. Test quality

Separate coverage quantity from assertion quality.

Flag:

- tests that only import;
- tests that only assert files exist;
- tests that only check "doesn't throw";
- tests that mock the core behavior being claimed;
- tests that would pass if real logic were deleted;
- tests that use generated fixtures to prove generated outputs;
- CI workflows that are advisory but described as blocking;
- gates that are local-only and forgeable by the PR author.

For the best and worst tests, cite examples.

### 7. Enterprise maturity comparison

Compare the codebase to legitimate enterprise-grade systems across these dimensions. Score each from 0 to 5, cite evidence, and explain what would be required to move up one level.

| Dimension | Score 0 means | Score 5 means |
|---|---|---|
| Build reproducibility | cannot reliably install/run | clean install, pinned deps, reproducible CI |
| Test trustworthiness | smoke tests or mocked theater | meaningful unit/integration/e2e tests with failure sensitivity |
| Runtime reliability | ad hoc scripts | crash recovery, idempotency, backpressure, bounded failure modes |
| State management | competing stores, unclear authority | single canonical state model with migrations/backups/recovery |
| Security/secrets | local env sprawl | auditable secret flow, least privilege, auth enforced by mode |
| Observability | logs only | metrics, traces, health, alerts, operator runbooks |
| Deployment | author laptop | repeatable staging/prod deployment with rollback |
| Maintainability | god files, duplicated patterns | small owned modules, clear interfaces, low coupling |
| Governance/compliance | docs and ceremonies | independently re-run gates with clear authority |
| External validation | internal demos only | real users, real revenue, real external benchmarks or SLAs |

Then answer plainly:

- Is this currently closer to a research prototype, internal developer tool, startup beta, or enterprise platform?
- What would a normal enterprise buyer trust today?
- What would they refuse to rely on?
- What is the shortest path to becoming enterprise-grade?

### 8. Corporate analogy map

Explain which parts resemble mature corporate software systems and which parts do not.

Use this structure:

| dharma_swarm component | Corporate analogue | Similarity | Difference / missing enterprise property |
|---|---|---|---|

At minimum compare against: workflow engines / durable orchestration platforms; internal developer platforms; CI/CD and policy-gate systems; observability/control-plane dashboards; agent frameworks; governance/risk/compliance systems; data/knowledge platforms; incident-response/runbook systems.

Do not overclaim. "Resembles X" does not mean "is as mature as X."

### 9. Plain-English synthesis

Only after the technical audit, explain what the system is actually trying to become — if this system were fully realized as designed, what would it actually do, for whom, and why would that matter? Answer for a smart reader who has never seen the repo.

Do not repeat project vocabulary as explanation. Translate it. Examples:

- "telos gates" → policy/safety checks that decide whether an action is allowed;
- "witness" → audit/logging layer that checks what happened after the fact;
- "Darwin engine" → proposed self-improvement loop that generates or applies code changes;
- "spine" → canonical execution/control path where task dispatch, identity, receipts, and state updates are supposed to pass;
- "organism" → top-level runtime composition that coordinates subsystems;
- "DharmaGraph" → durable workflow/graph runtime and crash-recovery effort;
- "receipts" → structured audit records, not proof unless producer and verifier paths are known.

Explain what the system does as if speaking to a CEO, CTO, staff engineer, and new hire at the same time. The reader should understand:

1. What problem this system is trying to solve.
2. Who would use it.
3. What happens when a task enters the system.
4. Where state is stored.
5. How the system knows whether work succeeded.
6. What parts are real today.
7. What parts are still theater, scaffolding, or aspiration.
8. Why this matters if it works.
9. Why it is risky if it does not.

---

## Prior audit hypotheses to verify or falsify

Use these as starting hypotheses only. Do not trust them blindly. Verify current status from the actual checkout.

1. The real runtime spine appears to be `dharma_swarm/runtime_state.py`, with SQLite tables for sessions, task claims, delegation runs, topology states, artifacts, memory facts/edges, context bundles, execution identities, runtime receipts, and idempotency records. Verify whether this is truly the live state authority or only one store among several.
2. The durable dispatch path appears to be `dharma_swarm/graph/durable_invoker.py`, using deterministic idempotency keys and runtime-state rows to prevent duplicate provider calls. Verify whether it is entrypoint-reachable, whether it is used in the main orchestrator path, and whether it fails open in live mode.
3. The graph reconciler appears to be `dharma_swarm/graph/reconciler.py`, designed for a single-host daemon. Verify whether anything prevents two active daemons from sharing the same runtime DB and corrupting the single-writer assumption.
4. Self-evolution appears intentionally fail-closed by default in `dharma_swarm/evolution_safety.py`. Verify whether every mutation path actually uses this guard.
5. The repo's own broken register has historically named open or partial issues around: runtime/ontology DB sync; live apply gate closed or partial; provider key-loading split brain; cron repo/live split brain; algedonic signal consumption gaps; fragmented agent contracts; at least one central telos gate hard-passing. Verify current status.
6. The active loop-closure track has historically claimed CLOSED_LIVE 0/13, HARNESS_PROVEN 11/13, and BLOCKED 2/13. Verify whether this is still true and whether harness proof is being confused with production-live closure.
7. The API may allow open dev mode when no dashboard API key is configured. Verify whether production mode refuses to boot without auth.
8. The project has had very large god modules: runtime state, evolution, swarm, orchestrator, providers, agent runner, thinkodynamic director, telos substrate. Verify current line counts and whether module-budget gates are reducing or merely grandfathering the problem.
9. The repo may be stronger internally than externally: many governance/receipt/track systems, but little evidence of real external users, revenue, or market feedback. Verify.

**Session-derived hypotheses (added 2026-07-09 from live observation — see Appendix A for the raw evidence):**

10. **PR gate battery density vs authority.** Each PR triggers roughly 40–52 checks (observed on PR #850: pytest 3.11/3.12, ACTIVE_TRACK governance gate, Spine bypass delta, Quality ratchet, Hygiene delta-ratchet, Rule 10 module line budget, CODEOWNERS blast-radius routing, Hermetic install, Import-provenance ratchet, Name-drift, semgrep, gitleaks, CodeQL, Greptile Review, Fourfold Shakti Warrant, Coherence Delta PR body, detect-br-collision, differential-oracle, "Evaluate and dispatch auto-merge", "Close duplicate automated PRs", and more). Verify which of these are *required* branch-protection checks versus merely present-and-green; whether "Evaluate and dispatch auto-merge" can merge a PR with no human review and under exactly what receipt conditions (the Merge Master Mike doctrine claims trusted-reviewer receipts and a bot-pr waiver — verify the waiver's scope); and whether any of the governance checks are advisory jobs whose names imply blocking authority they do not have.
11. **Automated governance PRs and self-referential paperwork.** The repo generates scheduled governance PRs (spine-adoption metric refresh drafts observed at ~6–12h cadence: #840 → #847 → #851; an automated ops/PR-lifecycle report #843 was auto-merged minutes after creation). Verify whether these generated artifacts have an independent verifier (a `--check` replay that fails on divergence) or whether they are reports asserting their own correctness; and verify the "Close duplicate automated PRs" job actually prevents unbounded automated-PR accumulation.
12. **Parallel-session duplicate work is a live, observed failure mode, not just a theoretical one.** On 2026-07-09, PR #841 was closed unmerged because PR #842 — built in a parallel session — had already landed the same two files with richer content. Verify how frequently this occurs (archaeology over closed-unmerged PRs), and whether any gate detects cross-PR *content* duplication (the detect-br-collision check only matches declared BR-ids, not overlapping diffs).
13. **The onboarding surface itself reports trust gaps on a fresh clone.** `make onboard` on a clean checkout warns "no active_track_evidence.json — track readiness CANNOT be verified" (evidence is derived, untracked, published to a `generated/status` branch), and the LIVE_OPS_DASHBOARD it renders self-describes as a stale historical snapshot (2026-06-15). Verify whether a fresh agent/auditor can actually reconstruct trusted track status from the repo alone, or whether routine operation happens in an unverified-trust state.

---

## Rules of engagement

- No diplomatic softening. If something is decorative, orphaned, theatrical, or dead, say so plainly.
- Do not average. One catastrophic gap (the core governance layer turning out to be decorative, say) matters more than ten cosmetic wins — weight the executive summary accordingly.
- State confidence on every major finding.
- Label inference as inference, not verification.
- Every specific technical claim needs path/function/class/line evidence.
- Do not call a report, receipt, active-track criterion, or dashboard row "proof" unless you verify the producer and verifier path.
- Do not treat unusual philosophical vocabulary as a problem by itself.
- Do not call something enterprise-grade unless you can explain what a serious engineering org would rely on today.

---

## Deliverable

Produce one Markdown report plus one machine-readable appendix.

The Markdown report must be in this order:

1. **Before you start** — exact repo access, commit hash, branch, commands run, commands failed, missing context.
2. **Executive summary** — one direct paragraph: what fraction of this system is real and working versus aspirational, and the single most important thing to know.
3. **Plain-English explanation** — what this project is trying to become, who it serves, what happens when work enters the system, and why it matters.
4. **How it ties together** — verified end-to-end flow from entry point to state update to result. Include one Mermaid diagram. Include only verified wired paths. Mark weak or partial edges. Required starting shape (modify to match reality):

   ```mermaid
   flowchart TD
     User[Operator/User] --> Entry[CLI/API/Dashboard/Daemon Entry Point]
     Entry --> Task[Task Board / Runtime State]
     Task --> Dispatch[Orchestrator / Spine Dispatch]
     Dispatch --> Agent[Agent Runner / Provider]
     Agent --> Receipt[Evidence Receipt / Runtime Receipt]
     Receipt --> State[SQLite / JSONL / Dashboard Projection]
     State --> Operator[Operator Feedback / Next Tick]
   ```

5. **Architecture reality map** — major modules tagged LIVE / PARTIAL / DORMANT / VAPORWARE, with evidence.
6. **Enterprise maturity comparison** — 0–5 scorecard with evidence and plain-language explanation.
7. **Corporate analogy map** — which parts resemble workflow engines, internal platforms, CI governance, observability systems, agent frameworks, GRC systems, data platforms, or incident-response systems, and where they fall short.
8. **Vision vs. reality gap table** — claim / where claimed / code evidence / verdict / confidence.
9. **Vibe-code & spaghetti inventory** — file or module / smell type / evidence / severity 1–5 / rough fix effort.
10. **Test quality report** — meaningful assertions vs smoke/mock/theater tests. Include examples.
11. **Systems risk register** — crash recovery, idempotency, state authority, secrets, auth, concurrency, deployment, data loss, and self-modification risks.
12. **Prioritized leveling-up roadmap** — ranked and sequenced by dependency order (what unblocks the most other work), not a flat complaint list. For each item: why first, what it unlocks, rough effort, verification command.
13. **Open questions** — what could not be verified and exactly what would close each question.

Then append this YAML block:

```yaml
machine_readable_summary:
  repo:
    commit: ""
    branch: ""
    access_type: ""
    worktree_status: ""
    commands_run: []
    commands_failed: []
    missing_context: []
  overall:
    real_fraction_estimate: ""
    aspirational_fraction_estimate: ""
    enterprise_grade_distance: ""
    closest_maturity_label: "research_prototype|internal_tool|startup_beta|enterprise_platform|unknown"
    biggest_risk: ""
    biggest_asset: ""
    confidence: ""
  components:
    - name: ""
      path: ""
      status: "LIVE|PARTIAL|DORMANT|VAPORWARE"
      evidence_type: "code_path|test|command|ci|live_artifact|documentation_only|unknown"
      reachability: "entrypoint|imported_not_called|test_only|docs_only|dead|unknown"
      evidence: []
      confidence: ""
  enterprise_maturity:
    build_reproducibility: {score: 0, evidence: [], next_step: ""}
    test_trustworthiness: {score: 0, evidence: [], next_step: ""}
    runtime_reliability: {score: 0, evidence: [], next_step: ""}
    state_management: {score: 0, evidence: [], next_step: ""}
    security_secrets: {score: 0, evidence: [], next_step: ""}
    observability: {score: 0, evidence: [], next_step: ""}
    deployment: {score: 0, evidence: [], next_step: ""}
    maintainability: {score: 0, evidence: [], next_step: ""}
    governance_compliance: {score: 0, evidence: [], next_step: ""}
    external_validation: {score: 0, evidence: [], next_step: ""}
  findings:
    - id: ""
      severity: 1
      title: ""
      plain_english: ""
      evidence: []
      evidence_type: ""
      reachability: "entrypoint|imported_not_called|test_only|docs_only|dead|unknown"
      confidence: ""
      fix_effort: "S|M|L|XL"
      blocks: []
  roadmap:
    - rank: 1
      action: ""
      why_first: ""
      expected_effect: ""
      verification_command: ""
      effort: "S|M|L|XL"
      depends_on: []
  open_questions:
    - question: ""
      why_it_matters: ""
      what_would_close_it: ""
```

Start now with **Before you start**.

---

## Appendix A — Session-verified repo snapshot (2026-07-09, decays from this date)

Everything below was directly observed in a Claude Code remote session on 2026-07-09 against `AmitabhainArunachala/dharma_swarm`. It is **dated prior evidence for the auditor to re-verify, never to trust**. Each item states how it was observed.

### A.1 Checkout state (observed via `git` + `make onboard`)

- Branch `claude/overnight-work-check-1nrten` at `ea6140b046` (merge of PR #848), clean worktree, ahead 0 / behind 0 vs `origin/main`.
- `make onboard` ran successfully on the fresh clone and itself emitted: `⚠ no active_track_evidence.json — track readiness CANNOT be verified. Run: python3 scripts/governance/check_track_status.py` — i.e., the trust check fails-closed-with-a-warning on every fresh checkout until a derived artifact is regenerated (feeds hypothesis #13).
- The rendered LIVE_OPS_DASHBOARD section self-labels: "HISTORICAL SNAPSHOT (2026-06-15 …) — the track portfolio it describes has since turned over." Docs-as-state drift is acknowledged in-band by the tool itself.
- Live Ops Cockpit section reported its census receipt missing (`run python3 scripts/runtime/live_ops_census.py --write`) and declares itself "read-only; executes nothing."

### A.2 PR ledger, 2026-07-08 → 2026-07-09 (observed via GitHub API)

| PR | Created (UTC) | State | Disposition |
|---|---|---|---|
| #837 | 07-08 00:29 | open | `github-actions[bot]` docops reconcile — routine, unattended since creation |
| #838 | 07-08 00:37 | merged | DharmaGraph Neutral Graph Core, Candidate Slice A |
| #839 | 07-08 00:42 | merged | `devin-ai-integration[bot]` — remote-ops checklist docs |
| #840 | 07-09 00:02 | closed, unmerged | automated spine-adoption refresh draft, superseded by later scheduled runs |
| #841 | 07-09 03:25 | closed, unmerged | docs relay superseded by #842 from a parallel session — live instance of the multi-agent duplicate-work failure signature (hypothesis #12) |
| #842 | 07-09 04:00 | merged | a2a fleet field registry + probe receipts + "honest doctor" |
| #843 | 07-09 06:04 | merged | automated ops + PR-lifecycle report; auto-merged minutes after creation (hypothesis #11) |
| #845 | 07-09 08:42 | merged | TAM governance quoting fix |
| #846 | 07-09 08:52 | open **draft** | KESTREL cold-start onboarding canary; all 39 checks green |
| #847 | 07-09 12:02 | open draft | automated spine-adoption refresh |
| #848 | 07-09 15:31 | merged | MemoryKernel governed query/search retrieval door |
| #849 | 07-09 16:16 | merged | spine: gate tool registry dispatch idempotently |
| #850 | 07-09 16:24 | open, non-draft | DharmaGraph Slices B+C (dynamic routing + cycles); all 52 checks green |
| #851 | 07-09 18:02 | open draft | automated spine-adoption refresh |

### A.3 Observed per-PR check battery (from PR #850 / #846 check runs)

Checks observed green (names verbatim): `pytest (3.11)`, `pytest (3.12)`, `dashboard`, `guardian-syntax-check`, `gauntlet-tier1`, `go-adapter-contracts`, `go-evidence-ingestor`, `ACTIVE_TRACK governance gate`, `DocOps integrity gate`, `Fourfold Shakti Warrant`, `dharma forge bypass guard`, `Spine bypass delta`, `differential-oracle`, `Rule 8 — no new root markdown`, `Rule 9 — no GUARDIAN_REPORT.md outside reports/`, `Rule 10 — module line budget`, `Rules 3 + 5 — test hygiene`, `Hygiene delta-ratchet`, `CI parity guard`, `scan PR commit messages`, `gitleaks`, `Hermetic install — lockfile drift fails`, `CODEOWNERS — measured blast-radius routing`, `Name-drift — first-party import resolution`, `codeql / python`, `CodeQL`, `rigor`, `semgrep`, `Semgrep OSS`, `Greptile Review`, `Quality ratchet - repo-wide fitness function`, `manifest-check`, `Import-provenance — third-party declaration ratchet`, `detect-br-collision`, `Coherence Delta PR body`, `Intent PR limit`, `Evaluate and dispatch auto-merge`, `Close duplicate automated PRs`, `Cache-poisoning and token least-privilege guard`, `Publish derived status branch` (skipped on PR), multiple `route` jobs (skipped).

**What was NOT verified this session** (open for the auditor): which of these are branch-protection-required vs decorative-green; the merge-authority conditions of `Evaluate and dispatch auto-merge`; whether the `route` jobs skipping is expected; whether any check is forgeable by the PR author (hypothesis #10 and the "gates that are local-only and forgeable" test-quality item).

### A.4 Standing claims from CLAUDE.md worth adversarial attention (docs-only evidence, not verified this session)

- CLAUDE.md itself codifies the claim boundary the audit must test: "HARNESS_PROVEN means a bounded replay/regression harness passed. It is not production-live closure. CLOSED_LIVE requires one live owner-surface criterion per loop" (loop-closure track). Verify the boundary is *enforced* somewhere, not just stated.
- Multiple tracks carry `(blocker)` items that are explicitly operator-gated and host-local (daemon-host observations, VPS provisioning, `~/.dharma` receipts) — these are exactly the "live-host-only claim not verifiable from repo" category in the evidence standard.
- CLAUDE.md warns about its own historical drift twice (frozen counts that rotted; a section that contradicted the mismatch map). Treat any count or percentage in prose docs as presumptively stale; prefer the generating command.
- The `revenue-external-humans-served` spine objective gained its first track only on 2026-07-07 (TAM, measurement-only, efferent-closed), and that track's own first render scored parity 35–45% with "Behind" on most lanes. This is the repo's own admission relevant to hypothesis #9 (external validation) — verify the instrument, then weigh it.

*End of integrated prompt.*
