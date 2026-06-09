# Anti-AI-Slop Future-Proofing Deep Dive

Status: research and local scan packet. Not a PR, not a merge blocker by itself.
Prepared: 2026-06-07
Worktree: `/Users/dhyana/dharma_swarm_pr_review_control`

## Executive Thesis

The durable answer is not "more rules." It is a living quality-control system
that treats AI-assisted engineering as an untrusted, high-throughput production
input.

The repo already has the right beginning: stable hygiene pattern IDs, generated
catalogue docs, onboarding hooks, baseline scans, docops checks, and a
governance vocabulary. The missing layer is a stronger operating model that
binds five things together:

1. instruction authority;
2. agent/tool capability;
3. objective evidence;
4. architecture budgets;
5. trend-based ratchets.

The north star: no code path, tool call, dependency, governance change, memory
promotion, public claim, or merge authority should be accepted because an agent
sounds confident. It should be accepted because it has identity, provenance,
deterministic verification, bounded blast radius, rollback, and a measured
quality trend.

## Research Inputs

External sources consulted:

- OWASP LLM Top 10: prompt injection, insecure output handling, supply-chain
  risk, excessive agency, overreliance, and related LLM application risks.
  <https://owasp.org/www-project-top-10-for-large-language-model-applications/>
- OWASP MCP Top 10: tool poisoning, context injection/over-sharing, shadow MCP
  servers, weak authz/authn, insufficient telemetry, command execution, and
  intent-flow subversion. <https://owasp.org/www-project-mcp-top-10/>
- OWASP Agentic AI / agentic application risks: goal hijack, tool misuse,
  identity and privilege abuse, memory/context poisoning, insecure inter-agent
  communication, cascading failures, trust exploitation, and rogue agents.
  <https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/>
- NIST AI RMF and GenAI Profile: govern/map/measure/manage framing and the
  need to map AI-specific risks to operational controls.
  <https://www.nist.gov/itl/ai-risk-management-framework>
- NIST SP 800-218A: AI-specific secure software development practices layered
  onto SSDF. <https://www.nist.gov/publications/secure-software-development-practices-generative-ai-and-dual-use-foundation-models-ssdf>
- NCSC prompt injection analysis: current LLMs do not enforce a reliable
  security boundary between instructions and data; deterministic guardrails and
  least privilege matter more than prompt wording.
  <https://www.ncsc.gov.uk/blog-post/prompt-injection-is-not-sql-injection>
- NCSC vibe-coding/SaaS analysis: AI-written code can increase speed and
  surface area while leaving maintainability, provenance, hosting, and review
  economics unresolved.
  <https://www.ncsc.gov.uk/blogs/vibe-check-ai-may-replace-saas-but-not-for-a-while>
- METR experienced-developer study and 2026 update: mature repos contain
  implicit requirements that benchmark-style coding success can miss; review
  and cleanup overhead are first-class costs.
  <https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/>
  <https://metr.org/blog/2026-02-24-uplift-update/>
- SLSA: provenance and tamper-resistant supply-chain evidence are necessary but
  not sufficient for architecture quality. <https://slsa.dev/spec/v1.1/about>
- OpenSSF Scorecard: useful heuristics for supply-chain posture, but individual
  checks and exceptions matter more than an aggregate score.
  <https://github.com/ossf/scorecard>
- CISA Secure by Design: security outcomes, secure defaults, least privilege,
  transparency, and manufacturer accountability should be product principles,
  not after-the-fact cleanup. <https://www.cisa.gov/securebydesign>

## Local Scan Receipts

Commands run in `/Users/dhyana/dharma_swarm_pr_review_control`:

- `python3 scripts/governance/hygiene/scan.py --output /private/tmp/dharma_hygiene_research_scan_2026-06-07.txt`
- `python3 scripts/governance/hygiene/sync_in_async.py`
- pattern catalogue summary via JSON parsing of `docs/governance/hygiene/patterns/*.yaml`
- Python LOC scan for `dharma_swarm/**/*.py`
- AST scan for duplicate private helpers
- package dependency range scan across `package.json` manifests
- workflow heuristic scan across `.github/workflows/*.yml`
- instruction-shaped text scan outside approved instruction surfaces
- side-effect/ExecutionIdentity/MCP boundary scan across docs, reports, code,
  and scripts

Scan notes:

- The generated hygiene baseline was written to
  `/private/tmp/dharma_hygiene_research_scan_2026-06-07.txt`.
- The baseline header may show 2026-06-08 because the shell is in Asia/Tokyo
  while the requested research date was 2026-06-07.
- No changes were staged, pushed, or PR-opened by this packet.

## Current Hygiene System Snapshot

`docs/governance/hygiene/patterns/` currently has 70 pattern records:

| Dimension | Counts |
|---|---:|
| Namespaces | `VC`: 58, `AI`: 12 |
| Stages | `advisory`: 15, `measured`: 27, `observed`: 28 |
| Severities | security 13, operational 13, correctness 16, structural 19, performance 4, distributed 4, informational 1 |
| Detector types | command 39, manual 28, external 3 |
| Enforcement-rule pointers | 2 |

Current rule pointers:

- `VC-C4` -> `docs/governance/ANTI_SLOP_RULES.md#rule-10`
- `VC-L1` -> `.github/workflows/bot-pr-limit.yml`

Interpretation: the repo has a strong catalogue, but most signals are still
observed/measured/advisory. That is correct for a young governance system. The
next maturity step is not to promote everything at once; it is to promote cheap,
deterministic, low-noise checks one at a time and track false positives.

## What The Repo Is Already Doing Well

- Single hygiene home exists under `docs/governance/hygiene/`.
- Pattern-per-file structure gives stable IDs, cheap diffs, and low merge
  conflict risk.
- `CATALOGUE.md` and `AUDIT_PROMPT.md` are generated from the pattern records.
- `AI_AGENT_GOVERNANCE.md` correctly introduces evidence grades, trusted
  instruction boundaries, review quorum profiles, and same-PR gate rules.
- PR #551 adds the right kind of substrate: lifecycle, generated docs,
  AI-agent tranche, scanner scripts, and tests.
- The onboarding updates currently in this worktree surface hygiene to future
  agents before they start implementation.
- Existing repo doctrine already has strong anti-fake-done instincts:
  receipts, docops, governance checks, merge authority boundaries, and runtime
  truth spine concepts.

## Highest-Value Gaps

### 1. Instruction Authority Is Still Too Implicit

The current `AI-A1` detector found many instruction-shaped strings outside
approved authority surfaces. Many are legitimate code, tests, skills, docs, or
archives, so the raw grep is noisy. The risk is still real: future agents will
read reports, memory summaries, PR comments, retrieved web pages, generated
markdown, and code comments. Without explicit tainting, they may treat data as
authority.

Required direction:

- Maintain an approved instruction-surface registry.
- Treat all other text as tainted data by default.
- Require explicit promotion before repo text becomes agent instruction.
- In generated prompts, mark each content block with provenance and authority:
  `operator`, `repo_policy`, `skill`, `retrieved_data`, `memory`, `log`,
  `issue_comment`, `tool_output`, etc.

### 2. Agent Tool Privileges Need A Capability Ledger

OWASP MCP and agentic AI risks map directly to this repo: tool poisoning,
shadow tools, excessive agency, weak telemetry, and context injection.

Local evidence already points to the same risk. Existing spine-adoption docs
identify `ToolRegistry.dispatch` and other side-effecting surfaces as not fully
saturated with `ExecutionIdentity`, idempotency, and side-effect receipts.

Required direction:

- Every tool-capable agent run should have a declared capability profile.
- Capability profiles should include filesystem, network, GitHub, secrets,
  process execution, MCP servers, memory writes, and merge/public-claim rights.
- Every side-effecting tool call should record intent, caller identity,
  target, args hash, output hash, exit status, and rollback/retry semantics.
- Missing identity should be a hard failure for high-risk side effects.

### 3. Evidence Grades Exist, But Evidence Receipts Are Not Yet Universal

`AI_AGENT_GOVERNANCE.md` has a good evidence-grade ladder. The next step is
machine-readable receipts that future agents can query.

Required direction:

- Local command receipts: command, cwd, git SHA, exit code, start/end time,
  output path, changed-file fingerprint.
- CI receipts: GitHub run ID, check suite, commit SHA, artifact links.
- Review receipts: reviewer identity, independence class, reviewed diff SHA,
  risk tier, unresolved questions.
- Runtime receipts: side-effect intent/complete/fail records.
- Claim receipts: no "passed", "verified", "merged", "safe", or "fixed" claim
  without a pointer to evidence.

### 4. Architecture Ratchets Need To Be Per-Touched-File

The repo has 41 Python files over 1000 LOC. Top files:

| LOC | File |
|---:|---|
| 5173 | `dharma_swarm/thinkodynamic_director.py` |
| 4512 | `dharma_swarm/telos_substrate.py` |
| 3796 | `dharma_swarm/runtime_state.py` |
| 3465 | `dharma_swarm/evolution.py` |
| 3355 | `dharma_swarm/agent_runner.py` |
| 3227 | `dharma_swarm/swarm.py` |
| 3022 | `dharma_swarm/providers.py` |
| 2777 | `dharma_swarm/orchestrator.py` |
| 2539 | `dharma_swarm/terminal_bridge.py` |
| 2520 | `dharma_swarm/tui/app.py` |

Hard fail on all legacy large files would be paralyzing. The better rule is a
ratchet:

- touched file must not increase LOC, cyclomatic risk, import fan-out, or
  public-symbol count unless explicitly waived;
- new files have stricter budgets;
- grandfathered files require a local extraction/deletion note when touched;
- repeated touching of a grandfathered file without improvement escalates risk.

### 5. Sync-In-Async Is A Concrete Reliability Pattern

`scripts/governance/hygiene/sync_in_async.py` found 11 sites:

- production-ish: `autoresearch_loop.py`, `review_cycle.py`,
  `roaming_dispatch_daemon.py`, `thinkodynamic_director.py`, `zeitgeist.py`
- demos/self-optimization tests: lower risk but still illustrative

This is a good candidate for promotion from measured/advisory to a real
ratchet, because the detector is concrete and the false-positive set is small.

### 6. Duplicate Local Primitives Are A Maintenance Smell

AST scan found repeated private helpers:

- `_utc_now`: 73 definitions
- `_utc_now_iso`: 40 definitions
- `_new_id`: 24 definitions
- `_read_json`: 19 definitions
- `_clamp01`: 12 definitions
- `_build_prompt`: 7 definitions

Some local helpers are fine, but common primitives should either be centralized
or intentionally local with a reason. The anti-slop version is not "ban helper
functions"; it is "ban unowned behavior clones."

### 7. Dependency Provenance Is Mostly Good In Python, Looser In JS

The scan did not find obvious loose Python requirements in the checked
manifests. JS manifests still use semver ranges:

- `dashboard/package.json`: 26 range/caret dependencies
- `terminal/package.json`: 11 range/caret dependencies
- `desktop-shell/package.json`: 1 range/caret dependency

Lockfiles reduce risk, but a future-proof repo needs a dependency admission
rule:

- real package exists in registry;
- package owner/reputation checked for new dependencies;
- lockfile updated;
- license acceptable;
- no typosquat-like name;
- no new install scripts unless reviewed;
- justification for runtime dependencies versus dev/test-only dependencies.

### 8. Workflow Security Needs A Purpose-Built Linter

The workflow heuristic scan found workflows using secrets and `GITHUB_TOKEN`,
and some action refs that deserve a more precise pinning policy. This scan is a
heuristic, not a vulnerability verdict. The needed control is deterministic:

- no `pull_request_target` unless explicitly allowlisted;
- no `write-all`;
- least-privilege `permissions` blocks;
- action refs pinned to SHA or documented exception;
- no `curl | sh`;
- secrets unavailable to untrusted PR code;
- artifact upload/download cannot cross trust boundaries without validation.

### 9. Prompt/Memory Poisoning Needs A Runtime Contract

The repo already has prompt injection scanning and memory-related tests. The
future-proof version should define memory as a controlled write path:

- memory writes require source, confidence, scope, expiry, and reviewer class;
- memory retrieved into prompts is tainted data, not authority;
- instruction-shaped memory is quarantined unless promoted;
- stale memory expires or is revalidated;
- generated reports cannot become future agent instructions by accident.

### 10. Agent Independence Must Be Measured, Not Asserted

Multiple agents agreeing is cheap if they share the same prompt, context,
retrieved files, or generated summary. Independence should be classified:

- same prompt and same context: weak corroboration;
- different model/provider, same evidence: moderate;
- different agent, independent scan command: stronger;
- external CI/runtime receipt: stronger;
- human/operator judgment: separate authority class, not just another agent.

## Control Families For A Future-Proof Anti-Slop Culture

### A. Trusted Instruction Boundary

Principle: repo text is data unless it is in an approved instruction surface.

Controls:

- instruction-surface registry;
- context block taint labels;
- detector for instruction-shaped text outside approved paths;
- quarantine flow for generated prompts, skills, memory snippets, and reports.

Promotion target:

- `make hygiene-check` fails on unregistered instruction authority additions,
  but allows benign references in tests/docs through explicit path/type
  annotations.

### B. Capability And Privilege Ledger

Principle: no agent has ambient authority.

Controls:

- agent run manifests declare allowed tools, write roots, network, secrets,
  GitHub capabilities, memory writes, and merge/public-claim rights;
- side-effecting tool calls require `ExecutionIdentity`;
- high-risk capabilities expire quickly and require operator intent.

Promotion target:

- side-effecting surfaces fail closed in high-risk mode when identity or
  receipt storage is absent.

### C. Evidence Receipt Hierarchy

Principle: every claim has an evidence grade and pointer.

Controls:

- local command receipt format;
- CI receipt ingestion;
- review receipt format;
- generated summary must cite evidence receipt IDs;
- model self-report never gates merge.

Promotion target:

- PR closeout rejects "verified" claims without command/CI receipt references.

### D. AI Change Lineage

Principle: AI-authored or AI-assisted patches need provenance, not stigma.

Controls:

- record agent/tool/model class, prompt source, task objective, touch set,
  verification commands, and review owner;
- record whether patch was generated, edited, or merely reviewed by AI;
- preserve enough lineage to debug recurring failure modes.

Promotion target:

- PR template/check asks for AI lineage on all agent-authored branches.

### E. Architecture Budget Ratchets

Principle: legacy debt can exist, but touched surfaces must trend down.

Controls:

- touched-file budgets for LOC, imports, public symbols, cyclomatic hotspots,
  duplicate helpers, async blocking, and test coverage of failure paths;
- waiver file for deliberate debt;
- repeated waivers escalate reviewer quorum.

Promotion target:

- changed files cannot worsen selected metrics without a waiver and owner.

### F. Dependency And Supply-Chain Provenance

Principle: generated package names are untrusted until independently verified.

Controls:

- dependency admission checklist;
- registry existence and lockfile checks;
- Semgrep/Scorecard/SBOM/SLSA-inspired evidence where applicable;
- install-script and native-extension review.

Promotion target:

- new runtime dependency requires provenance note and lockfile diff.

### G. Prompt, Context, And Memory Poisoning Defense

Principle: retrieved data and memory are hostile until classified.

Controls:

- taint labels;
- memory write receipts;
- expiry and revalidation;
- prompt-injection detector on new memory/report inputs;
- privilege drop when processing untrusted content.

Promotion target:

- memory promotion command refuses instruction-shaped text without reviewer
  override.

### H. Deterministic Verifiers And Holdout Evals

Principle: agents will optimize visible gates.

Controls:

- visible tests plus rotating hidden/holdout checks;
- mutation/failure-injection tests for critical gates;
- same-PR gate weakening blocked;
- detector false-positive/false-negative log.

Promotion target:

- governance gate changes require old/new behavior comparison and a fixture
  proving the previous failure.

### I. Review Quorum By Risk Tier

Principle: evidence burden should match consequence.

Controls:

- docs-low, code-low, runtime-medium, governance-high, repair-needed profiles;
- high-risk surfaces require independent evidence, not just more prose;
- same author/agent cannot be the sole certifier for its own gate.

Promotion target:

- PR packet chooses a risk tier and required evidence class before merge.

### J. Safe Execution And Sandbox Profiles

Principle: generated code should run in the narrowest environment that can
  verify it.

Controls:

- no network by default for tests unless explicitly required;
- no secrets in generated-code test runs;
- disposable worktrees for risky modifications;
- command allowlist per task class;
- bounded timeouts and resource ceilings.

Promotion target:

- agent-build preflight chooses sandbox profile and records it in the receipt.

### K. Trend Metrics And Anti-Goodhart Dashboards

Principle: one green check can lie; trends are harder to fake.

Controls:

- track warning counts, file-size distribution, duplicate helpers, flaky tests,
  runtime gate coverage, dependency age/risk, prompt-surface counts, evidence
  grade distribution, and PR rework rate;
- sample false positives manually;
- rotate detectors and holdouts.

Promotion target:

- monthly hygiene report shows trend lines and top regressions.

### L. Maintenance Burden And Deletion Incentives

Principle: quality is not just adding more machinery; it is reducing future
maintainer load.

Controls:

- every nontrivial PR states what it simplified, deleted, or made easier to
  verify;
- new abstractions require owner and retirement criteria;
- stale patterns archive instead of accumulating forever;
- generated docs must be regenerated by command, not hand-edited.

Promotion target:

- PR packet includes a maintenance-burden delta for medium/high-risk changes.

## Questions The Repo Should Start Asking

These are the questions I would add to the governance culture, because they
catch failures that ordinary lint/test gates miss:

1. What text in this PR is allowed to instruct future agents?
2. What text in this PR must forever remain data, even if it sounds imperative?
3. What side effects can this agent perform, and where are those permissions
   recorded?
4. If this agent is prompt-injected, what is the maximum damage it can do?
5. Did the agent change a gate that judges the same PR?
6. Does the verification prove the bug failed before the fix?
7. What evidence would convince a skeptical maintainer who distrusts all model
   prose?
8. What part of this patch would be hardest to debug six months from now?
9. Which invariant did the agent have to understand, and how was that
   understanding tested?
10. Does this PR reduce future reviewer burden or merely move it somewhere else?
11. What hidden/rotating check could catch an agent optimizing for the visible
   gate?
12. If this dependency disappears, is compromised, or changes behavior, what
   breaks?
13. What memory/context did the agent rely on, and could that memory be stale or
   poisoned?
14. Are multiple agents truly independent, or just echoing the same packet?
15. What would we delete if we had to make the repo simpler before adding this?

## Recommended New Pattern Families

These should become new pattern files only after the current PR settles, to
avoid muddling #551 review scope.

| Proposed family | Purpose | First detector idea |
|---|---|---|
| `AI-M` Context taint and authority labels | Prevent data/instruction confusion | scan prompt builders for unlabeled context blocks |
| `AI-N` Tool/MCP side-effect ledger | Prevent ambient agent authority | scan tool dispatch paths for identity/receipt hooks |
| `AI-O` Agent lineage provenance | Make AI-authored change history auditable | PR packet requires agent/model/tool/evidence fields |
| `AI-P` Hidden/rotating gate defense | Reduce gate gaming | require old/new fixture for governance gate changes |
| `AI-Q` Safe execution profiles | Limit generated-code blast radius | require sandbox profile on agent-build preflight |
| `VC-M` Touched-file architecture ratchet | Stop legacy accretion without paralyzing work | compare LOC/import/public-symbol deltas for touched files |
| `VC-N` Shared primitive clone detector | Stop unowned helper drift | AST count of repeated private helpers above threshold |
| `VC-O` Dependency provenance | Block package hallucination and risky deps | new dependency requires registry+lock+justification |
| `VC-P` Prompt surface registry | Make instruction authority explicit | registry check for prompt/skill/system-message surfaces |
| `SEC-A` Workflow trust boundary | Prevent CI privilege accidents | lint permissions/action refs/secrets/pull_request_target |

## Proposed Scripts And Gates

Add these incrementally, not all at once:

- `scripts/governance/hygiene/check_instruction_surfaces.py`
- `scripts/governance/hygiene/check_agent_capabilities.py`
- `scripts/governance/hygiene/check_ai_lineage_receipts.py`
- `scripts/governance/hygiene/check_dependency_provenance.py`
- `scripts/governance/hygiene/check_architecture_ratchet.py`
- `scripts/governance/hygiene/check_prompt_context_taint.py`
- `scripts/governance/hygiene/check_workflow_security.py`
- `scripts/governance/hygiene/check_quality_trends.py`

Promotion order should prefer high-signal, low-noise checks:

1. `sync_in_async.py` ratchet for touched production files.
2. workflow security linter in advisory mode.
3. dependency provenance note for new runtime dependencies.
4. instruction-surface registry check.
5. touched-file architecture ratchet.
6. tool side-effect identity/receipt saturation checks.
7. memory/context promotion quarantine.
8. rotating holdout/eval gate.

## Merge/Wait Recommendation For #551

PR #551 should not wait for this full deep-dive system to be implemented.

Recommendation:

1. Keep #551 focused on the lifecycle substrate and AI-agent advisory tranche.
2. Merge #551 after normal checks/review are green and the draft state is
   intentionally removed by the operator.
3. Treat this report as the follow-up roadmap for promotion from advisory
   governance into enforceable repo culture.
4. Do not promote many patterns to blocking at once; promote one detector per
   review cycle after false-positive review.

Rationale: the lifecycle substrate is the thing that allows the deeper system to
evolve safely. Waiting for perfect anti-slop governance before merging the
governance substrate would invert the dependency.

## 0-30-60-90 Day Roadmap

### 0-7 Days

- Land #551 once checks and operator review are satisfied.
- Preserve this report as research evidence.
- Add external framework mapping fields to pattern records:
  `owasp_llm`, `owasp_mcp`, `nist_ssdf`, `nist_ai_rmf`, `ncsc`, `slsa`,
  `openssf`, `cisa`.
- Re-run baseline and record false-positive notes for `AI-A1`.
- Pick one cheap detector to promote next.

### 30 Days

- Add instruction-surface registry.
- Add workflow security advisory linter.
- Add dependency provenance notes for new runtime dependencies.
- Add touched-file architecture ratchet in advisory mode.
- Require command/CI receipt IDs in PR packets for "verified" claims.

### 60 Days

- Wire capability profiles into agent-build preflight.
- Add side-effect ledger coverage checks for tool/MCP/runtime boundaries.
- Add memory/context promotion quarantine.
- Add monthly hygiene trend report.
- Establish holdout fixtures for governance gates.

### 90 Days

- Promote the lowest-noise checks to enforced.
- Require risk-tier review quorum for merge packets.
- Make high-risk side-effecting tool calls fail closed without
  `ExecutionIdentity` and receipt storage.
- Run an audit drill: intentionally seed a prompt-injection/data-authority
  fixture, package-hallucination fixture, and gate-weakening fixture; verify the
  system catches them.

## Guru-Level Engineering Principles

These are the compact principles I would bake into repo culture:

- No authority without identity.
- No claim without a receipt.
- No generated code without provenance.
- No new dependency without registry, lockfile, license, and reason.
- No prompt boundary treated as a security boundary.
- No side effect without intent, idempotency, and completion/failure record.
- No agent certifies the gate that admits its own change.
- No hidden maintainer burden disguised as velocity.
- No growth without a deletion or simplification budget.
- No architecture debt increase without a named waiver and review tier.
- No multi-agent consensus without independence classification.
- No memory promotion without source, confidence, expiry, and taint status.
- No public/security/merge claim from model prose alone.
- No legacy debt panic; use ratchets so touched surfaces improve.

## Bottom Line

The anti-vibe-code future is not "AI writes less." It is "AI writes inside a
system that is hostile to unsupported claims, ambient authority, invisible
side-effects, unbounded context trust, and architectural entropy."

The repo is already pointed in the right direction. The next step is turning
the hygiene catalogue into a measured ratchet: one detector promoted at a time,
with evidence receipts, privilege boundaries, and trend reporting. That gives
past, present, and future code the same culture: clarity, provenance, small
blast radius, and proof.
