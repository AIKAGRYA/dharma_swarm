# Anti-AI-Slop Control Backlog

Status: local execution backlog. Do not treat as merged doctrine until promoted
through governance review.

Related artifacts:

- Research deep dive:
  `reports/governance/anti_ai_slop_futureproof_deep_dive_2026-06-07.md`
- Scan snapshot:
  `reports/governance/anti_ai_slop_scan_snapshot_2026-06-08.json`
- Hygiene PR:
  <https://github.com/AmitabhainArunachala/dharma_swarm/pull/551>

## Operating Rule

The anti-slop system should mature by ratchet, not by panic. Promote one
deterministic, low-noise control at a time; record false positives; make the
review burden proportional to risk.

## Priority Legend

- P0: unblock hygiene substrate or stop high-risk governance drift.
- P1: high leverage, should become advisory or enforced soon.
- P2: important culture/control work that needs staging.
- P3: trend and excellence layer after the core gates are stable.

## Ranked Backlog

### P0-001: Land The Hygiene Substrate Without Scope Creep

Control family: lifecycle substrate

Problem:

PR #551 is the foundation that makes future hygiene work systematic. It should
not absorb every idea in the deep dive.

Evidence:

- PR #551 observed as open, draft, and unstable on 2026-06-08.
- Current catalogue already has 70 patterns, generated docs, and integrity
  checks.

Next implementation:

- Keep #551 scoped to lifecycle, catalogue, AI-agent tranche, onboarding
  surfacing, and integrity checks.
- Remove draft only after operator review and required checks are green.
- Do not add the future-proof backlog into #551 unless reviewers ask.

Verification:

- `make hygiene-check`
- PR checks green
- generated docs match pattern files

Promotion criteria:

- #551 merged.
- Follow-up issues or PRs opened for P0/P1 controls.

Risk:

- Scope creep could make the substrate harder to review and delay the very
  mechanism needed for future hygiene.

### P0-002: Instruction Surface Registry And Taint Labels

Control family: trusted instruction boundary

Problem:

Agents can accidentally treat docs, reports, memory, PR comments, logs, and
retrieved web text as authority.

Evidence:

- Instruction-shaped heuristic found 142 files.
- Only 9 were trusted or skill-like by rough path classification.
- 133 were data-like or untrusted by default.
- The current detector is noisy enough that raw blocking would be harmful.

Next implementation:

- Add `docs/governance/hygiene/instruction_surfaces.yaml`.
- Classify surfaces as `operator`, `repo_policy`, `skill`, `prompt_builder`,
  `test_fixture`, `archive`, `report`, `memory`, `retrieved_data`, or `log`.
- Add `check_instruction_surfaces.py` in advisory mode.
- Update `AI-A1` detector to read the registry instead of raw grep only.

Verification:

- Detector prints grouped findings by authority class.
- Test fixture proves an instruction-shaped report is data, not authority.
- Test fixture proves a new unregistered instruction authority is flagged.

Promotion criteria:

- Two review cycles with low-noise output.
- Every finding has an owner class and remediation path.

Risk:

- Too broad a blocker would punish legitimate tests and prompt-builder code.

### P0-003: Evidence Receipt Contract For "Verified" Claims

Control family: evidence hierarchy

Problem:

AI agents overstate verification. "Tests passed" is not enough unless it names
the command, cwd, exit code, commit, and output.

Evidence:

- `AI_AGENT_GOVERNANCE.md` already defines evidence grades.
- The repo has many receipt/identity-related surfaces, but PR closeout claims
  still need a uniform machine-readable contract.

Next implementation:

- Define `reports/governance/receipts/schema/pr_verification_receipt.schema.json`
  or a stdlib-validated equivalent.
- Add a lightweight `scripts/governance/hygiene/check_pr_receipts.py`.
- PR packets should include command receipts for every "verified" claim.

Verification:

- Fixture with vague "tests passed" fails.
- Fixture with command/cwd/exit-code/output-path passes.

Promotion criteria:

- Mike/onboarding output points agents to the receipt contract.
- Medium/high-risk PRs include receipt pointers.

Risk:

- Overly heavy receipt format could slow low-risk docs work. Use risk tiers.

### P0-004: Workflow Trust-Boundary Linter

Control family: CI/supply-chain boundary

Problem:

Workflow privilege should be explicit and least-privileged, especially for
agent-triggered PRs.

Evidence:

- 20 workflow files scanned.
- 0 `pull_request_target`, 0 `write-all`, 0 unpinned action refs, 0 `curl | sh`.
- 2 workflows missing explicit `permissions`.
- 6 workflows use secrets and 6 use `GITHUB_TOKEN`.

Next implementation:

- Add advisory `check_workflow_security.py`.
- Flag missing `permissions`, `pull_request_target`, `write-all`, non-SHA
  action refs, `curl | sh`, and secret availability on untrusted events.
- Maintain allowlist comments for deliberate exceptions.

Verification:

- Fixture workflows cover each risk.
- Current repo scan reports two missing-permission findings and no criticals.

Promotion criteria:

- Missing permissions fixed or explicitly waived.
- Detector has no false criticals for two cycles.

Risk:

- Secrets/GITHUB_TOKEN are not inherently bad; the linter must judge event and
  permission context, not string presence alone.

### P1-005: Sync-In-Async Ratchet

Control family: runtime reliability

Problem:

Blocking subprocess or sleep calls inside async functions can stall runtime
loops and agent orchestration.

Evidence:

- `sync_in_async.py` found 11 sites.
- Production-ish sites include `autoresearch_loop.py`, `review_cycle.py`,
  `roaming_dispatch_daemon.py`, `thinkodynamic_director.py`, and `zeitgeist.py`.

Next implementation:

- Promote detector to touched-file advisory gate.
- Maintain allowlist for demos/tests.
- Require new async code to use async subprocess APIs, executor boundaries, or
  documented isolation.

Verification:

- Existing detector test stays green.
- New fixture proves touched production async regression is flagged.

Promotion criteria:

- No new production sync-in-async sites for two cycles.
- Existing sites either fixed, quarantined, or grandfathered.

Risk:

- Some subprocess usage may be intentionally isolated; detector should ratchet
  touched files first.

### P1-006: Tool Capability Ledger Saturation

Control family: agent capability and side-effect receipts

Problem:

Agentic risk is mostly capability risk: tools, files, network, GitHub, memory,
runtime state, and public claims.

Evidence:

- `ToolRegistry.dispatch` already includes optional `ExecutionIdentity` and
  side-effect intent/complete hooks in this worktree.
- Existing spine docs identify broader side-effect boundaries that need
  saturation and fail-closed modes.

Next implementation:

- Add capability profiles for agent-build preflight:
  `docs/governance/hygiene/capability_profiles.yaml`.
- Add advisory check for side-effecting boundaries without
  `ExecutionIdentity`/receipt coverage.
- Flip `require_identity=True` only for high-risk profiles after coverage is
  complete.

Verification:

- Tool dispatch tests prove missing identity raises in required mode.
- Boundary coverage report lists joined, adapter-ready, quarantined, and
  missing surfaces.

Promotion criteria:

- 100% of high-risk side-effect boundaries are joined or quarantined.

Risk:

- Premature fail-closed mode could break legacy runtime flows.

### P1-007: Touched-File Architecture Ratchet

Control family: architecture budget

Problem:

Large files are where vibe-coded patches hide complexity and future review
burden.

Evidence:

- 41 Python files exceed 1000 LOC.
- Largest files include `thinkodynamic_director.py` at 5173 LOC,
  `telos_substrate.py` at 4512 LOC, `runtime_state.py` at 3796 LOC, and
  `agent_runner.py` at 3355 LOC.

Next implementation:

- Add advisory `check_architecture_ratchet.py`.
- Compare touched-file LOC, imports, public symbol count, and duplicate helper
  count against base branch.
- Require waiver for worsening metrics.

Verification:

- Fixture shows a touched grandfathered file can pass if unchanged or improved.
- Fixture shows a new oversized file fails.

Promotion criteria:

- Ratchet runs in PR packets without blocking unrelated legacy debt.

Risk:

- Global debt gates would freeze work. Make it touched-file scoped.

### P1-008: Shared Primitive Clone Detector

Control family: duplication and drift

Problem:

Repeated local helpers drift over time and create inconsistent behavior.

Evidence:

- `_utc_now`: 73 definitions.
- `_utc_now_iso`: 40 definitions.
- `_new_id`: 24 definitions.
- `_read_json`: 19 definitions.
- `_clamp01`: 12 definitions.
- `_build_prompt`: 7 definitions.

Next implementation:

- Add AST-based advisory detector for repeated private helper names.
- Classify helpers as `shared_candidate`, `test_fixture`, `local_intentional`,
  or `ignore`.
- Start with warnings on new duplicate helper names or increased counts.

Verification:

- Detector can separate tests from production paths.
- New duplicate in production is flagged.

Promotion criteria:

- Top 5 shared candidates have owner decisions.

Risk:

- Blind centralization can create bad coupling. The control should require an
  ownership decision, not automatic refactor.

### P1-009: Dependency Provenance Gate

Control family: supply chain and package hallucination

Problem:

AI-generated dependency names and casual semver ranges can introduce supply
chain risk.

Evidence:

- Python manifests looked comparatively clean in this scan.
- JS manifests have semver ranges:
  `dashboard/package.json` 26, `terminal/package.json` 11,
  `desktop-shell/package.json` 1.

Next implementation:

- Add new-dependency admission fields to PR packets:
  registry URL, lockfile diff, license, runtime/dev scope, install scripts,
  maintainer signal, and reason.
- Advisory detector flags new package names without a provenance note.

Verification:

- Fixture adding a package without a note fails.
- Fixture adding dev-only package with lockfile and note passes.

Promotion criteria:

- New runtime dependencies always include provenance.

Risk:

- Existing semver ranges should not be mass-blocked; focus on new or changed
  dependencies.

### P1-010: Prompt And Memory Promotion Quarantine

Control family: memory/context poisoning

Problem:

Long-lived memory and generated reports can smuggle instruction-shaped content
into future prompts.

Evidence:

- Instruction-shaped surfaces are widespread.
- Existing injection scanner and prompt-builder tests prove the repo already
  takes this seriously.

Next implementation:

- Memory writes require source, confidence, scope, expiry, and authority class.
- Instruction-shaped memory defaults to quarantine.
- Prompt builders label every block by provenance and authority.

Verification:

- Test fixture with "ignore previous instructions" in memory is quarantined.
- Prompt rendering test shows tainted blocks cannot become system authority.

Promotion criteria:

- All memory promotion paths carry taint metadata.

Risk:

- Over-filtering useful doctrine; promotion path must exist with review.

### P2-011: Hidden And Rotating Governance Fixtures

Control family: anti-Goodhart verification

Problem:

Agents optimize visible gates. A stable checklist is necessary but gameable.

Evidence:

- Same-PR gate rule already exists in AI governance.
- Future agents will keep learning the visible checklist.

Next implementation:

- Maintain a small hidden/rotating fixture bank for gate weakening, fake
  verification, prompt injection, package hallucination, and architecture
  accretion.
- Governance gate changes must pass old/new behavior fixtures.

Verification:

- A seeded fake-verification PR fails.
- A seeded gate-weakening PR fails unless reviewed as governance-only.

Promotion criteria:

- Fixture bank rotates monthly.

Risk:

- Hidden checks must not become arbitrary. Keep categories public, examples
  rotating.

### P2-012: External Framework Crosswalk Fields

Control family: standards mapping

Problem:

Pattern records should show which external risk frameworks they satisfy.

Evidence:

- Pattern sources currently skew heavily toward `initial-field-guide`.
- OWASP/NIST coverage exists mostly in the `AI-*` tranche.

Next implementation:

- Add optional fields:
  `owasp_llm`, `owasp_mcp`, `owasp_agentic`, `nist_ai_rmf`, `nist_ssdf`,
  `ncsc`, `slsa`, `openssf_scorecard`, `cisa_secure_by_design`.
- Generate a crosswalk table from pattern YAML.

Verification:

- Integrity check validates field shapes.
- Generated crosswalk has no orphan framework IDs.

Promotion criteria:

- Security and operational patterns have framework mappings or a reason they do
  not apply.

Risk:

- Crosswalk can become theater if it is not tied to detectors and evidence.

### P2-013: Multi-Agent Independence Receipt

Control family: review quorum

Problem:

Several agents agreeing is weak evidence if they share prompts, files, and
summaries.

Evidence:

- AI governance already says multiple agents need independent evidence, not
  just agreement.

Next implementation:

- Add independence classes:
  `same_context`, `same_evidence_different_model`, `independent_scan`,
  `external_ci`, `operator_review`.
- PR packets classify each review receipt.

Verification:

- Fixture with two model summaries from the same packet is weak corroboration.
- Fixture with independent command output is stronger.

Promotion criteria:

- Runtime/governance-high PRs include at least one independent evidence class.

Risk:

- Extra agents can add noise. Evidence independence matters more than headcount.

### P3-014: Hygiene Trend Dashboard

Control family: trend metrics

Problem:

Single-point checks miss slow quality decay.

Evidence:

- Current baseline and scan snapshot establish first trendable metrics:
  pattern stages, large files, sync-in-async sites, duplicate helpers,
  workflow flags, dependency ranges, and instruction surfaces.

Next implementation:

- Store monthly scan JSON in `reports/governance/hygiene_trends/`.
- Render trend report for operator review.
- Track false positives and waived debt.

Verification:

- Trend renderer can compare two snapshots.
- Metrics include "improved", "unchanged", "worse", and "waived".

Promotion criteria:

- Monthly trend report becomes part of governance-all or onboarding summary.

Risk:

- Metrics can become vanity. Tie each metric to an owner action.

### P3-015: Maintenance-Burden Delta

Control family: deletion and simplification incentive

Problem:

AI agents are good at adding code and weak at paying future maintenance costs.

Evidence:

- `AI-K1` and `AI-L1` already encode simplification and maintainer burden.
- `AI-L1` was the only pattern without a recognized source in the source scan,
  so it needs explicit grounding or local evidence.

Next implementation:

- PR packet asks:
  "What did this delete, collapse, simplify, or make easier to verify?"
- If the PR increases maintenance burden, require explicit owner acceptance.
- Add a source/evidence note to `AI-L1`.

Verification:

- Docs-only and tiny fixes can answer "not applicable".
- Medium/high-risk PRs must include a concrete burden delta.

Promotion criteria:

- Rework rate and review burden trend downward.

Risk:

- This should stay lightweight; otherwise it becomes another prose ritual.

## Suggested Promotion Sequence

1. Merge #551 once ready.
2. Add P0-002 instruction registry in advisory mode.
3. Add P0-004 workflow linter in advisory mode.
4. Promote P1-005 sync-in-async ratchet for touched production files.
5. Add P0-003 receipt contract for medium/high-risk PRs.
6. Add P1-009 dependency provenance for new runtime dependencies.
7. Add P1-007 touched-file architecture ratchet.
8. Add P1-006 side-effect/capability ledger saturation.
9. Add P1-010 memory/context quarantine.
10. Add P3-014 trend dashboard.

## Merge Advice

Do not wait for this backlog to be implemented before merging #551. The backlog
depends on #551's lifecycle substrate. The correct move is:

1. stabilize #551;
2. merge it through normal operator authority;
3. convert this backlog into small follow-up PRs;
4. promote controls only after measured false-positive review.
