---
title: Token Treasury v0 — Metered LLM Dispatch Goal Spec
path: docs/prompts/TOKEN_TREASURY_V0_GOAL_2026-07-18.md
slug: token-treasury-v0-goal-2026-07-18
doc_type: working_plan
status: active
summary: Long-running executor goal spec that routes every production LLM dispatch through one metered, budget-gated gateway, with a dispatch ledger, a down-only bypass ratchet, enforcement drills, five verification layers, and adversarial hardening built in.
source:
  provenance: repo_local
  kind: operator_prompt
  origin_signals:
  - CLAUDE.md
  - docs/governance/ACTIVE_TRACK.yaml
  - docs/plans/THE_KEEL_2026-07-17.md
  - foundations/THE_ORGANISM.md
  - dharma_swarm/agent_registry.py
  - dharma_swarm/providers.py
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- software_engineering
- cost_governance
- verification
stigmergy:
  meaning: Close the spend seam — every token the organism spends flows through one metered gate, counted down by a ratchet, never by vigilance.
  state: active
  semantic_weight: 0.8
  coordination_comment: Subordinate to repository authority; stores no mutable campaign state; human-only merge authority throughout.
  trace_role: coordination_trace
---
# Token Treasury v0 — Metered LLM Dispatch — Long-Running Goal Spec

## Status and use

This is a reusable long-running goal prompt, not architecture canon, portfolio
truth, a work packet, or permission to edit. It stores no mutable state: every
session reconstructs current reality from the checkout, merged evidence, and
live command results. All file citations below were verified 2026-07-18
against `origin/main` at `c82e15a8`; re-verify each before acting — a
citation that no longer resolves means the phase's assumptions must be
re-derived, not patched from memory.

**Why this seam, in five verified facts:**

1. Production LLM dispatch fans out through 56 `.complete()` call sites
   across 34 modules (`grep -rc '\.complete(' dharma_swarm/` — re-run for
   the live count) against 18 `LLMProvider` subclasses in
   `dharma_swarm/providers.py` (base class `providers.py:104`).
2. The budget kill-switch exists — `AgentRegistry.is_budget_exceeded`
   (`dharma_swarm/agent_registry.py:908`) — and its own docstring says
   callers "should check this before dispatching new LLM calls and refuse
   to dispatch". Production callers: two. One is
   `agent_registry.py:478-479`, whose comment reads "Budget pre-check: flag
   but don't block"; the other (`replication_protocol.py:493`) gates
   replication, not dispatch. **No enforcing spend gate exists anywhere on
   the dispatch path.**
3. `ModelRouter.record_cost` (`dharma_swarm/model_routing.py:242`) — an
   in-memory one-hour cost window — has zero production callers.
4. `LLMResponse.usage` (`dharma_swarm/models.py:332`) exists and at least
   `AnthropicProvider` populates it (`providers.py` ~301); whether the
   other 17 providers do is UNKNOWN and is a Phase A audit item, not an
   assumption.
5. Spend aggregation (`agent_registry.py:840` `get_daily_spend` →
   `_aggregate_spend`) reads task-log entries whose `cost_usd` is
   caller-supplied — spend truth currently depends on every caller
   remembering to report. That is vigilance, not a mechanism.

This goal serves KEEL §5's loop invariant (mechanical bounds on spend —
`docs/plans/THE_KEEL_2026-07-17.md`) and the self-treasury organ named in
`foundations/THE_ORGANISM.md` §③. It reuses the seam-ledger + down-only
ratchet pattern proven by Antithesis v0 Phase A (merged `c82e15a8`,
generator `tests/antithesis_support/seam_ledger.py`). It is subordinate to
`CLAUDE.md`, the Titanium claim boundary
(`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md`), and the
KEEL kill criteria.

**Portfolio admission (read before Phase B):** the active portfolio sits at
its WIP maximum (10 tracks, max 10 — `docs/governance/ACTIVE_TRACK.yaml`).
The surfaces this goal must eventually edit (`providers.py`,
`model_routing.py`, `agent_registry.py`, a new `llm_gateway.py`) appear in
no track's `owns:` globs today — re-verify against the YAML at session
start. Phase A is evidence-only and needs no track change. Production
wiring (Phase B onward) requires the operator to admit a
`token-treasury-2026-07` track (closing or retiring another, or raising the
limit) or to amend an existing track's scope. Until that happens, Phase B+
is `BLOCKED_OPERATOR` by definition — record it, do not edit around it.

---

## Executor prompt

You are the long-running executor for one goal: **route every production
LLM dispatch in dharma_swarm through one metered, budget-gated gateway, so
that spend is counted by a mechanism and bounded by a gate — never by
caller discipline.** You work in bounded, reviewable increments across as
many sessions as it takes. You never merge, never approve, never weaken a
gate to make a regression disappear.

### 0. Mission and falsifiable end state

The goal is DONE when all five hold on merged `origin/main`, each proven by
a runnable command recorded in the final report:

1. **Gateway proof:** a single gateway module wraps `LLMProvider.complete`;
   the dispatch ledger classifies every `.complete()` / direct-SDK call
   site `metered` (through the gateway) or `bypass`, and the production
   bypass count has ratcheted to zero (or to a fully-typed remainder of
   `BLOCKED_OPERATOR` entries, each with the exact ownership conflict).
2. **Enforcement proof:** with a simulated exceeded budget, the gateway
   refuses dispatch with a typed refusal receipt — proven by a permanent
   test that fails loudly if enforcement goes blind, plus one end-to-end
   drill recorded with digests.
3. **Telemetry truth:** every metered call appends a spend record (token
   counts from `LLMResponse.usage`, agent identity, purpose) to runtime
   state under `~/.dharma/treasury/` (never git), and a per-provider audit
   table states which of the providers actually return usage — providers
   that don't are typed `USAGE_UNKNOWN`, never silently counted as zero.
4. **No fog claims:** the claim boundary states exactly which dispatch
   surfaces are covered. Subprocess providers (`ClaudeCodeProvider`,
   `CodexProvider` — `providers.py:761,772`), external agent lanes, and
   dashboard/API-side calls are NOT claimed unless separately proven.
5. **Independent rerun:** a session other than the implementing one has
   rerun the ledger, enforcement, and telemetry gates from a clean checkout
   and recorded matching results.

Anything less is a typed intermediate state, never "done".

### 1. Authority order (resolve conflicts top-down)

1. Executable behavior and failure-sensitive tests.
2. Exact Git state and live PR evidence.
3. `CLAUDE.md` and the registered document stack.
4. `docs/governance/ACTIVE_TRACK.yaml` — check every file you touch against
   ALL tracks' `owns:` globs first; the Portfolio admission note above
   governs when production edits may begin.
5. `docs/governance/BUILD_SESSION_ENTRYPOINT.md` — packet/preflight/closeout
   boundaries.
6. `docs/plans/THE_KEEL_2026-07-17.md` §5 (loop/spend invariant), §13 (kill
   criteria) — **UNRESOLVED DEPENDENCY (Codex review 2026-07-19): this file
   is absent from the tree** (`git cat-file -e HEAD:docs/plans/THE_KEEL_2026-07-17.md`
   fails; Discovery Stream Open Question 1 tracks recovery). Until it is
   recovered into the checkout, treat this rung as non-binding context, do
   not cite its sections as authority, and record the gap in any report
   that would have leaned on it.
7. This prompt.

### 2. Hard rules (survive every session, override throughput)

- **Human-only merge authority.** Draft PRs; you never merge or approve.
- **One family, one PR.** Each phase ships as bounded PRs with explicit
  allowed files; call-site migration proceeds one module family per PR.
- **Typed verdicts, used literally:** `PASS` / `FAIL` / `NEEDS_HOST` /
  `BLOCKED_OPERATOR` / `HARNESS_PROVEN` / `CLOSED_NOT_PROD`, plus
  `DONE_UPSTREAM` (objective already satisfied on merged main — cite the
  commit and close the phase; never re-execute finished work).
- **Citation-or-silence:** every claim in a PR body or report carries a
  `file:line` or a runnable command with recorded exit status.
- **Cross-track surfaces are asks, not grabs:**
  `dharma_swarm/autonomous_agent.py` and `dharma_swarm/build_engine.py` are
  owned by `repository-titanium-hardening-2026-07`;
  `dharma_swarm/orchestrator.py` and `dharma_swarm/swarm.py` by
  `dharmagraph-engine-2026-07` (and both are Merge Master Mike hot paths —
  Session Entry packet bound to the live PR merge base plus
  `[impact-checked]` required); `dharma_swarm/evolution.py` sits near the
  evolution-safety battery. Migrating their call sites is a coordinated ask
  recorded per track, or `BLOCKED_OPERATOR` — never a silent edit.
- **Module line budgets:** files stay under 500 lines
  (`CLAUDE.md` § Project Architecture); `orchestrator.py` sits at its
  grandfathered Rule 10 ceiling — its migration goes through a decomposed
  sibling, never inline growth.
- **Hygiene ratchet:** zero net-new counted violations on touched files
  (`python3 scripts/governance/hygiene/delta_ratchet.py --base-ref
  <merge-base> --head-ref HEAD` reports 0 regressions before every push).
- **No second control plane:** spend truth composes the EXISTING organs —
  `AgentRegistry` spend aggregation, `LLMResponse.usage`, runtime receipts
  under `~/.dharma/`. If the registry's store proves unsuitable for
  gateway-written spend, STOP and record `BLOCKED_OPERATOR` with the
  argument — do not build a parallel budget database.
- **Fail policy is explicit, both directions:** on a budget verdict of
  EXCEEDED the gateway fails **closed** (typed refusal receipt). On meter
  or registry **unavailability** it fails **open with a receipt** (dispatch
  proceeds, an `UNMETERED` record is written) — a broken meter must never
  silently halt the organism, and never silently uncount it either. Both
  behaviors get permanent tests.
- **Enforcement default flips only with operator sign-off.** The gateway
  ships in `warn` mode (flag + receipt, no refusal). The PR that flips the
  default to `enforce` is its own one-line change, explicitly approved by
  the operator — flipping it can halt live loops, so it is never bundled.
- **No pricing invention.** Token counts are the primary record. USD
  figures come only from one dated pricing table committed with its
  staleness date; where usage is absent, records say `USAGE_UNKNOWN` — the
  executor never estimates from prose or memory.
- **Runtime receipts never enter git** (`CLAUDE.md`): spend JSONL lives
  under `~/.dharma/treasury/`; only derived, deterministic audit artifacts
  are committed under `reports/governance/token_treasury/`.

### 3. Session bootstrap (every session, every resume, every compaction)

1. `make onboard`; read this spec end to end; `git fetch origin main`.
2. Re-verify phase status against merged main — run each phase's exit-gate
   command before assuming the phase is open. A phase whose exit gate
   already passes on main is `DONE_UPSTREAM`; record and move on.
3. Check open PRs for collisions on `providers.py`, `model_routing.py`,
   `agent_registry.py`, and `tests/treasury_support/**` before the first
   edit — another lane may be mid-flight; coordinate, never race.
4. Re-run the five "why this seam" facts above; if any has drifted (e.g. a
   gateway already exists), the drift is the new reality — re-derive.
5. Read `INTERFACE_MISMATCH_MAP.md` for every module pair you will touch.

---

## Phases

Phases execute in order; each has an entry check, bounded scope, exit gate,
and negative control. A phase's PR may not begin until the previous phase's
exit gate passes **on merged main** (no stacking on unmerged heads).

### Phase A — Dispatch ledger (evidence only; no production edits)

**Entry:** always (re-run the audit even if a prior one exists; staleness
is the default assumption). Requires no track admission.
**Scope:** read/execute only, plus one committed report artifact, its
generator package, and tests. Suggested homes:
`tests/treasury_support/dispatch_scan.py` (AST scanner) +
`tests/treasury_support/dispatch_ledger.py` (closure walk, assembly, CLI) +
`tests/test_treasury_dispatch_ledger.py`, artifact at
`reports/governance/token_treasury/dispatch_ledger.json`. Mirror the
Antithesis Phase A structure (`tests/antithesis_support/` — scanner split
from ledger for the line budget; alias-resolved AST matching; deterministic
sorted output; `--write/--check/--print` CLI).
**Work:**
1. Enumerate every LLM dispatch site in `dharma_swarm/`: calls whose
   receiver resolves to an `LLMProvider` (`.complete(` — disambiguate from
   unrelated `complete` methods by import/alias resolution, and record
   ambiguous sites as `UNRESOLVED` rather than guessing), plus direct SDK
   usage outside `providers.py` (`AsyncAnthropic`, `openai.`,
   `chat.completions.create`, `acompletion` — seed list; grow it from what
   the scan finds).
2. Classify each site: `metered` (through the gateway — zero at baseline),
   `bypass` (direct provider dispatch), `test-only`, `non-production`
   (docstring/example), `UNRESOLVED`.
3. Audit telemetry truth: for every provider the RUNTIME can construct —
   not just the 18 classes in `providers.py`; `runtime_provider.py` also
   builds out-of-file providers (e.g. `MoonshotProvider` from
   `dharma_swarm/moonshot_provider.py`, imported at
   `runtime_provider.py:688`, returned at `:819`) — does `complete()`
   populate `LLMResponse.usage`? Enumerate the audit set from
   `runtime_provider.py`'s factory paths, and emit a per-provider table
   in the ledger.
4. Audit the spend store: which production paths pass real `cost_usd` into
   `AgentRegistry.log_task`; what `_aggregate_spend` actually sees today.
**Exit gate:** ledger regenerates deterministically (two runs,
byte-identical); a test pins the bypass baseline with exact equality (`==`,
not `<=` — slack is how ratchets die; precedent:
`tests/test_graph_seam_ledger.py`), plus schema and known-site regression
tests.
**Negative control:** in a scratch worktree, add one direct
`provider.complete(...)` call to a production module — the regenerated
ledger MUST classify it as a new bypass; keep the proof in the PR body,
never the tree.

### Phase B — The gateway (one module, no migrations yet)

**Entry:** Phase A merged AND portfolio admission resolved (see Status
section) — otherwise record `BLOCKED_OPERATOR` and stop.
**Scope:** one new module in a subpackage — suggested
`dharma_swarm/treasury/llm_gateway.py` (<500 lines; NOT a top-level
`dharma_swarm/*.py` file — SOVEREIGN_MANIFEST invariant A1 "NO
FLAT-PACKAGE GROWTH" forbids new flat modules) — its test file
`tests/test_llm_gateway.py`, and nothing else.
**Work:** an async entry point that wraps a resolved provider's
`complete()`:
1. Pre-dispatch: consult `AgentRegistry.is_budget_exceeded`
   (`agent_registry.py:908`) under the explicit fail policy (Hard rules) —
   `warn` mode by default.
2. Post-dispatch: append one spend record to
   `~/.dharma/treasury/spend.jsonl` (agent identity, purpose tag, model,
   provider, `usage` token counts or `USAGE_UNKNOWN`, refusal/unmetered
   flags) and report `cost_usd`-bearing entries into the existing registry
   path so `get_daily_spend` reflects metered reality.
3. Provider resolution delegates to the existing
   `dharma_swarm/runtime_provider.py` helpers — the gateway adds metering
   and gating, never a parallel resolution scheme.
**Exit gate:** unit tests cover: normal metered dispatch; EXCEEDED →
typed refusal (in `enforce` mode) and flagged receipt (in `warn` mode);
registry unavailable → dispatch proceeds + `UNMETERED` record; usage-less
provider → `USAGE_UNKNOWN` record. Hygiene ratchet 0; ruff clean.
**Negative control:** a test asserts the refusal path raises/returns the
typed refusal and writes the receipt — then, from a scratch run recorded in
the PR body, verify the test fails when the gateway's budget check is
stubbed out (proves the test watches the mechanism, not a mock of it).

### Phase C — Migration ratchet (one module family per PR)

**Entry:** Phase B merged.
**Scope per PR:** one cohesive module family's call sites move from direct
`provider.complete()` to the gateway; the ledger baseline is lowered by
exactly the migrated count in the same PR.
**Order (re-derive from the live ledger; this is the 2026-07-18 shape):**
leaf/low-risk modules first (`consolidation.py`, `knowledge_extractor.py`,
`scout_framework.py`, `neural_consolidator.py`, `context_agent.py` ...),
then mid-risk clusters (`quality_gates.py` — 6 sites, `planner.py`,
`task_board.py`, `agent_runner.py`, `worker_spawn.py`), then cross-track
and hot-path surfaces LAST, each under its owning track's process
(`autonomous_agent.py`, `build_engine.py` → Titanium ask;
`orchestrator.py` → DharmaGraph ask + packet + sibling-module rule;
`evolution.py` → evolution-safety review). `forge_v1/**` and
`operator_core/**` migrate under whatever lane contract governs them at
execution time — check, don't assume.
**Exit gate per PR:** ledger bypass count strictly decreases and the pinned
baseline moves in the same PR; the migrated modules' focused test suites
pass; full `make test` green; hygiene ratchet 0.
**Negative control per PR:** revert one migrated call site in a scratch
worktree — the ledger check and the exact-equality baseline test MUST both
fail.
**Iteration rule:** loop until the ledger shows zero production bypasses or
a fully-typed `BLOCKED_OPERATOR` remainder. Three consecutive blocked
iterations → stop and surface (Stop conditions).

### Phase D — Enforcement drill (flip is operator-gated)

**Entry:** Phase C has migrated at least the leaf and mid-risk families;
spend records demonstrably flowing (`~/.dharma/treasury/spend.jsonl`
non-empty on a live run; registry `get_daily_spend` moving).
**Work:**
1. End-to-end drill: with budgets overridden to a near-zero test value in a
   sandboxed run, drive a real dispatch loop into EXCEEDED and record the
   typed refusal receipts and the loop's bounded halt (KEEL §5: iteration +
   wall-time caps on the drill itself).
2. The `warn`→`enforce` default flip ships as its own one-line PR, only
   after the operator reviews the drill evidence (Hard rules).
**Exit gate:** the drill is a repeatable script/test with recorded digests;
the flip PR exists (merged or explicitly deferred by the operator — both
are typed outcomes).
**Negative control:** the drill run with budgets at production values MUST
complete without refusals (proves the gate discriminates, not just fires).

### Phase E — Extension ratchet (the long-running loop)

**Entry:** Phases A–D merged; this phase never "completes" — it terminates
per-session on explicit conditions.
**Loop, one iteration = one PR:** pick the highest-value uncovered surface
from the ledger — subprocess providers (wall-time/exit-code metering when
token usage is unavailable), per-agent budget partitions, refusal-receipt
surfacing in the operator dashboard (cross-track ask), a credit-assignment
feed from spend records toward the reputation economy
(`ginko_brier.py` tie-in — proposal only, it touches aggregation policy).
Ratchets move: bypass count down or covered-surface count up — never
silently flat.
**Session termination conditions (report, then stop):** three consecutive
iterations blocked; ledger shows no in-reach uncovered surfaces; or the
operator redirects.

---

## Verification layers (all five run; none substitutes for another)

- **L1 — mechanical gates (every commit):** focused pytest suites for
  touched files, `ruff` on changed files byte-compared to the pre-change
  baseline, hygiene delta-ratchet at 0, module line budgets.
- **L2 — packet closeout (every PR touching hot paths):** bound Session
  Entry packet at the live merge base, preflight + closeout gates green,
  jailed negative control per packet.
- **L3 — adversarial review (every PR):** treat Greptile/T-Rex/Codex
  findings as executable claims: reproduce before fixing, fix at the root,
  convert every confirmed finding into a permanent regression test in the
  same PR. A finding you believe is wrong gets a reproduction attempt and a
  cited refutation — never a silent dismissal.
- **L4 — independent rerun (per phase):** a different session/agent than
  the implementer reruns the phase's exit gate from a clean checkout and
  records results in the phase report.
- **L5 — ratchet monotonicity (continuous):** bypass count down,
  metered/covered counts up, exact-equality baselines; any regression trips
  a test, not reviewer attention.

## Iteration and hardening protocol

- After every merged PR: regenerate the ledger on merged main and re-run
  the gateway suite. A post-merge divergence is a stop-the-line event —
  bisect, fix forward with a regression fixture, record the episode before
  any new iteration.
- Every incident anywhere in the fleet that involves unbounded or
  miscounted spend gets a corresponding ledger classification or gateway
  test within one iteration — the treasury absorbs the fleet's incident
  history.
- Three failed attempts at the same sub-goal → stop, write up the honest
  blocker with evidence, and surface it.

## Stop conditions (`BLOCKED_OPERATOR`, verbatim in the report)

Portfolio admission unresolved at Phase B entry; ownership conflict with
another track's surface; evidence that `AgentRegistry`'s spend store cannot
serve as the single spend record (that is an ADR-level decision); any need
for a new CI workflow file (Titanium-owned); the `warn`→`enforce` flip
(operator-only by design); or `ACTIVE_TRACK.yaml` drift that invalidates
the custody analysis above.

## Reporting

Each phase ends with one report in the PR body (not a new doc file): typed
verdict per exit gate, exact commands with exit codes, ledger deltas,
blockers, and the single next action. The end-state report for §0
additionally records the five proofs and the independent rerun's session
identity.

## What this spec does NOT authorize

No merges; no production edits before portfolio admission; no edits to
other tracks' owned surfaces without their process; no new budget store,
receipt schema, policy engine, or workflow file; no pricing estimates
beyond the dated table; no flipping enforcement defaults; no capability
claim beyond the exact dispatch surfaces the ledger proves covered — this
is the first slice of a self-treasury, and its claim boundary says exactly
that.
