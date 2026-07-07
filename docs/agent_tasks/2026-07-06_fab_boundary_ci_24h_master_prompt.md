# Forge Agent Boundary CI — Gated 24h Proof (Master Prompt)

Forged 2026-07-06 via master-prompt-forge from the operator seed: "highest world-facing thing that gives evolutionary signal to the repo... first and best candidate to bring revenue... karpathy style autoresearch evolution loop/harness." Seed claims were independently verified before forging; corrections are labeled in Inferred Assumptions below. Companion decision packet: `docs/agent_tasks/2026-07-06_dharma_trust_forge_pre_admit_decision_packet.md`.

---

```
# Forge Agent Boundary CI — gated 24h proof (venture thesis, evidence-labeled)

## Role
You are a repo agent (Claude Code session or Codex /goal) with full shell and
repo access in /Users/dhyana/dharma_swarm, operating as a focused contributor
under a bounded build lease — not the repo's maintainer. Operator-only
decisions (track closure, venture-cell admission, outreach, merges to main)
remain with the operator.

## Goal
Build and verify the first executable proof of Dharma Trust Forge's surviving
slice — Forge Agent Boundary CI: five deterministic, offline, replayable
authority-boundary rules (FAB-01..05) over JSON fixtures with real-trace
provenance, a head-to-head delta against the closest free alternatives, and
one wired (default-off) code path by which a confirmed finding becomes an eval
candidate consumed by an EXISTING owner — all under the eight gates of
docs/agent_tasks/2026-07-06_dharma_trust_forge_pre_admit_decision_packet.md.
The build either upgrades the wedge to demonstrated, or kills it with
receipts; both closeouts count as success.

## Inferred assumptions (verified 2026-07-06 — correct before running if wrong)
- "Picked after the RSI/DGM evolution tracker" is the operator's chronology,
  not a written ranking: no artifact co-ranks the two lanes, and where any
  ranking touches both, the ordering is INVERTED — the governance/trust wedge
  is #1 for revenue (reports/revenue_wedge/dharma_swarm_self_funding_thesis_2026-07-06.md:70-77,
  "Forge / RIS / DGM benchmarks... not first revenue path" at L72) and is the
  UPSTREAM verifier primitive that DGM/AutoResearch consume shadow-only
  (AGENT_GOVERNANCE_WORKBENCH_1000X_DECISION.md:57; agent_3_autoresearch_dgm.md:7-24).
  This prompt treats Trust Forge as upstream-of-DGM.
- "First and best revenue candidate" is a verified PICK, not a verified fact:
  receipted cash = $0, 113 outreach drafts sent=0, and every money test is
  gated on an operator outreach lease that does not exist. Therefore this
  prompt contains ZERO revenue language and no pricing work.
- "Evolutionary signal to the repo" is currently aspiration: zero code paths
  consume a FAB finding today (autoresearch_loop.py:329-364, dgm_loop.py:297-310,
  auto_research/engine.py:13-31 — council-verified). Deliverable 9 is the
  first honest step toward making it true; do not use "feedback loop" language
  in any artifact until that path has executed once with a receipt.
- "Karpathy-style" refers to the wiki/memory-metabolism lane (overnight goal
  Agent 8); chetana promotion has no quality gate (promote.py:107-125 writes
  trusted on WARN), so this build emits eval-candidate records, NOT wiki atoms.
- Final package name is unsettled (trust_forge/ vs forge_agent_boundary_ci/
  drift between authoring docs): the name-drift preflight decides it; "Forge"
  alone is an ACTIVE alias of semobj.dharma_forge_proving_ground and must not
  be claimed. OPERATOR LEAN (stated 2026-07-06, custody: conversational, not
  yet a ratified name): drop "Forge" from this product's name entirely — the
  Forge name stays with the DGM/RSI-lab and Proving Ground lineage. Candidate
  working name: "Agent Boundary CI" (buyer-legible); internal semantic object
  name to be settled at preflight time.

## Context
- Canon: origin/main. The current default checkout (agent/magpie-seed) is 389
  commits behind canon and exposed to fleet branch-switching automation —
  never build there.
- The five Trust Forge spec/verifier files are currently UNTRACKED:
  docs/agent_tasks/2026-07-06_dharma_trust_forge_viability_handoff.md,
  docs/agent_tasks/2026-07-06_dharma_trust_forge_overnight_autoresearch_goal.md,
  docs/agent_tasks/2026-07-06_agent_governance_workbench_1000x_autoresearch_goal.md,
  scripts/governance/verify_dharma_trust_forge_goal.py,
  tests/test_verify_dharma_trust_forge_goal.py.
- .gitignore:135 (HEAD fdde37bad) ignores reports/agentops/work_packets/*/ —
  the prior viability evidence is invisible to git; all NEW outputs must land
  on a tracked path (verify with git check-ignore).
- Seeds to reuse (do not reinvent):
  - Lease semantics: dharma_swarm/operator_core/execution_lease.py
    (dharma.execution_lease.v1 — grant/expiry/LeaseValidation/forbidden
    actions). Bind FAB lease rules to it; no new AuthorityLease store.
  - FAB-04 non-circular floor: digest-chain integrity + evidence-hash
    verification over ~/.dharma/witness/claim_evidence_receipts.jsonl
    (intact prev_digest chain; line 3 is a genuine vacuous-receipt
    true-positive — label it suspected-test-exhaust in fixture metadata).
  - Real tool-call traces: ~/.claude/projects/-Users-dhyana/*.jsonl
    (Read/Bash/Write tool_use entries with real paths) and A2A inbox
    payloads under ~/.dharma/a2a_bus/inboxes/.
- Competitive reality (verified 2026-07-06): Invariant OSS (Snyk) + promptfoo
  cover ~4/5 FAB rule semantics free. The residual wedge — the ONLY thing
  worth demonstrating — is FAB-04 receipt-evidence binding + lease
  grant/expiry semantics + hash-pinned replayable fixture receipts +
  remediation deltas.
- FAB rules: FAB-01 forbidden path writes block; FAB-02 tools outside
  allowed_tools block; FAB-03 credential/external-URL patterns block when
  external policy = none (label honestly as deterministic pattern-regression,
  not "detection"); FAB-04 authoritative claims without resolvable receipt
  evidence block (honest reduction: typed-claim schema conformance +
  digest-chain verification); FAB-05 edits to verifier/gold fixture files
  block.

<workspace-hygiene>
## Workspace hygiene (read this before touching anything)

Before making any change, gather the following — read-only, no writes:

- Repo root (`git rev-parse --show-toplevel`), current branch, and
  upstream tracking branch.
- `git worktree list` — is this checkout one of several worktrees on the
  same repo? Note any siblings.
- Dirty state: `git status --short` — count of modified/untracked files.
  If this count is large (dozens to hundreds), treat the tree as **user
  property to preserve**, not clutter to clean — see "Dirty-Worktree
  Quarantine Mode" below.
- Lockfiles present (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`,
  `Cargo.lock`, `go.sum`, etc.) and which dependency manager they imply.
- Generated / vendor / cache directories (`node_modules/`, `dist/`,
  `build/`, `.venv/`, `__pycache__/`, `target/`, `.next/`) — do not
  descend into these for edits; do not "clean" them unless asked.
- The project's actual test/lint/build commands (check `Makefile`,
  `package.json` scripts, `pyproject.toml`, CI config) rather than
  assuming a generic `npm test` / `pytest` invocation.

**Forbidden by default** (only do these if the user explicitly asked for
this exact operation, and even then, confirm current state and flag the
risk first):

- `git reset --hard`, `git clean -f` / `-fdx`, `git checkout -- .`
- Force-push, rewriting published history, `--no-verify` / skipping hooks
- Mass reformatting or repo-wide auto-fix passes
- Dependency upgrades/downgrades not directly requested
- Deleting or moving files outside the stated scope of the task
- Mixing new agent-driven work into an already-chaotic worktree without
  the user's explicit go-ahead

## Dirty-Worktree Quarantine Mode

Trigger this posture whenever the workspace has a large number of
pre-existing uncommitted or unfamiliar changes that are **not** part of
the current task:

1. Do not touch, stash, or discard the existing changes. Inventory them
   (file count, rough categories, whether they look intentional or
   stale) and report the inventory before doing anything else.
2. Do the new work in a clean sibling worktree or fresh clone instead of
   inside the contaminated tree:
   `git worktree add -b <new-branch> <new-path> <commit-ish>`
   creates an isolated working tree and branch from a chosen commit
   without disturbing the original.
3. If the user wants the dirty tree cleaned up, that is a separate,
   explicit task — never bundle it into an unrelated feature/fix prompt.
4. If unsure whether uncommitted work is intentional, ask before treating
   it as disposable. It is not.
</workspace-hygiene>

Repo-specific application of quarantine mode: do the work in a fresh sibling
worktree cut from canon —
`git worktree add -b fab-boundary-ci/24h-proof ~/dw-worktrees/fab-24h origin/main`
— then copy the five untracked Trust Forge files into it and commit them as
the FIRST change. Known repo hazards: pre-commit hook venv is broken (use
`git commit --no-verify` — this is the documented house workaround, not hook
evasion); use /Users/dhyana/dharma_swarm/.venv/bin/python (3.13), never
system python3.

## Constraints & non-goals
- Rules must be pure and deterministic: no LLM/provider/network calls.
- Forbidden: external outreach, public claims, ANY revenue/pricing language,
  push or merge to main, PR-merge, deploy, trusted-memory/wiki promotion,
  live DGM mutation, archive-fitness mutation, provider-routing changes,
  new receipt/lease stores, dashboards/SaaS/GitHub Apps.
- The harness is projection/advisory-only. It must not become a
  merge-blocking or dispatch-blocking authority; verify_promotion remains
  the one door ("read models project truth from owners; they do not become
  authority").
- Do not open/close ACTIVE_TRACK.yaml entries (WIP is 11/11; lifecycle is
  operator-only). Do not edit VENTURE_CELL_PORTFOLIO.yaml.
- Deliverable 9's wiring ships default-OFF behind an env flag and consumes
  an EXISTING owner only.

## Deliverables
1. Fresh branch fab-boundary-ci/24h-proof (from origin/main) with the five
   previously-untracked Trust Forge files committed first.
2. Name receipt: scripts/governance/name_drift_preflight.py run + a distinct
   semantic object registered in docs/ontology/semantic_objects.yaml (with
   forbidden-merge aliases vs semobj.dharma_forge_proving_ground); final
   package name taken from this.
3. dharma_swarm/<final-name>/ — models.py, rules.py, fixtures.py, report.py,
   cli.py implementing FAB-01..05.
4. >=10 JSON fixtures at tests/fixtures/<final-name>/ (pass AND fail cases);
   >=2 derived from real on-disk traces, each with provenance
   {source_path, sha256} in fixture metadata.
5. Reports from one CLI run: Markdown scorecard, JSON decisions, JUnit XML,
   and a run receipt naming branch, head, fixture hashes, exact command —
   written to a TRACKED path (suggest reports/forge/<final-name>/;
   git check-ignore must be silent on every output).
6. Honest-negative fix to scripts/governance/verify_dharma_trust_forge_goal.py:
   sellable_pilot_present=false + recommended_next_action=kill_or_pause can
   PASS; branch/head become required receipt fields; tests updated.
7. An executable harness verifier whose every check recomputes from artifacts
   (rule count e2e, fixture count + provenance fields, double-run byte
   equality, report parseability) — no builder-asserted booleans.
8. Head-to-head delta artifact: each FAB rule attempted in Invariant OSS
   policy language and promptfoo trajectory-assertion form (authored as
   config/docs; no network execution required); for each rule state either
   the delta neither can express or "reproduced-elsewhere".
9. Metabolism first-wire (default-off flag): confirmed findings emitted as
   eval-candidate records into an EXISTING owner
   (experiment_log.ExperimentRecord or EvolutionArchive per the VEL RFC
   reuse table), executed once with a receipt. No new store.
10. pytest green for the new package + the updated verifier tests; two
    identical CLI runs proven byte-identical (diff receipt included).

## Evidence / verification discipline
- Cite file:line for every claim about existing code behavior.
- "It works" requires showing: the pytest run, the double CLI run + byte
  diff, and git check-ignore output for the report dir — pasted, not
  summarized.
- Claim vocabulary in all outputs: observed / reproduced / remediated /
  verified-in-scope / waived / expired. Never "safe"; never a superiority
  claim; no "feedback loop" language until Deliverable 9's receipt exists.
- If a pre-registered fail condition fires (any rule needs an LLM;
  non-determinism across identical runs; FAB-04 implementable only via
  expected-label leakage; <5 rules e2e) — STOP building around it and close
  honestly as kill_or_pause naming the failing condition; the Deliverable-6
  fix makes that a passing, closable state.

## Subagent / swarm strategy
Builder + independent verifier pair only: the builder implements; a second
agent with a clean shell re-runs the harness verifier, the double-run
determinism check, and git check-ignore, then countersigns the run receipt.
Nothing larger is warranted for a one-day slice.

## Done when
- pytest for the new package is green and the CLI end-to-end temp-dir run
  replays allow/block decisions for all 5 rules over >=10 fixtures (>=2
  real-trace with provenance) — outputs shown.
- Two identical CLI runs are byte-identical, receipted.
- Every output path is tracked (git check-ignore silent) and committed on
  fab-boundary-ci/24h-proof; no changes exist outside the declared surfaces.
- The honest-negative verifier fix + updated tests pass.
- The head-to-head delta artifact exists and names what neither Invariant
  nor promptfoo expresses — or declares the empirical kill.
- The metabolism first-wire has executed once, default-off, with a receipt
  into an existing owner.
- Zero revenue language anywhere; no forbidden surface touched; OR the run
  is closed as kill_or_pause with the failing condition named and receipted.
```
