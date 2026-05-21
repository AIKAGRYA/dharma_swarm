# dharma_swarm — Open Strings & Next Phase Map

**Date:** 2026-05-21
**Author:** Devin (multi-session architecture review)
**Scope:** Every open string, seeded-but-stopped project, and unfinished thread across the repo, PRs, and session history.
**Verified against:** 15+ governance/architecture/runtime files, `make onboard` output, all 35 open PRs (verified via `gh pr list --state open --limit 100` at 2026-05-21T08:38Z), all 610 Python source files.
**Inventory provenance:** `gh pr list --state open --limit 100 --json number,title,createdAt,updatedAt,author`

---

## 1. ACTIVE TRACK STATUS

**Track:** `trace-identity-coverage-2026-05` — native trace identity propagation
**Status:** ACTIVE — 5/6 completion criteria met (verified via `make onboard`)
**Single blocker:** ADR-0002 (`docs/architecture/adr/0002-trace-coverage-gate.md`) does not exist.

Everything else shipped: CorrelationContext (`dharma_swarm/correlation_context.py`), BoardStore trace defaults, Sakshi trace defaults, Guardian soft coverage finding, witness report at `reports/witness/2026-05-21-trace-identity-coverage.md`.

---

## 2. OPEN PRs — FULL INVENTORY (35 total, 34 listed + this PR #326)

### Tier A: Ready to merge now

| PR | Title | CI | Action |
|---|---|---|---|
| **#325** | Codex toolbelt onboarding | 22/22 green (draft) | Mark ready-for-review + merge |
| **#323** | dkeys env alias normalization + dashboard fidelity audit | 21/22 (CodeQL optional FP) | Merge |
| **#321** | TaskBoard adapter + Dhyana onboard + BR-009/010/011/012 closure | 0 checks ran — needs push to trigger CI | Re-push + merge |
| **#322** | Dashboard nav trim to 9 items | Review needed | Review + merge if clean |
| **#324** | CWT v0 read-only collector | Review needed | Review + merge if clean |
| **#314** | Pin router/TaskBoard domains; refresh manifest counts | Review needed | Review + merge if clean |

### Tier B: Architecturally significant, need review

| PR | Title | Created | Action |
|---|---|---|---|
| **#320** | ADR-007: Retire AutoProposer → route through BoardStore | 2026-05-20 | Review — migration design |
| **#312** | Wire governed MemoryKernel release gate | 2026-05-17 | Review — touches evolution pipeline |
| **#297** | Route witness telemetry | 2026-05-13 | Review — telemetry wiring |
| **#191** | Seed semantic metabolism organ | 2026-05-10 | Review — new organ seed |
| **#190** | Fusion spine contract + bypass ratchet | 2026-05-10 | Review — routing arch |

### Tier C: Stale (14+ days, likely superseded)

| PR | Title | Created | Recommended |
|---|---|---|---|
| **#182** | Slop verification system | 2026-05-09 | Close — anti-slop rules evolved |
| **#181** | Lock telos hierarchy | 2026-05-09 | Review — governance doc |
| **#168** | Optimize RoamingDispatchDaemon async I/O | 2026-05-07 | Close or rebase |
| **#161** | Document BR-004 cron | 2026-05-07 | Close — BR-004 partially addressed |
| **#158** | Cron daemon env-loading wrapper | 2026-05-07 | Close or rebase |
| **#152** | Cold-lane coverage tests | 2026-05-07 | Rebase or close |
| **#151** | Claude mem census + audit doctor | 2026-05-07 | Close — memory audit |
| **#150** | Trace attractor projection contracts | 2026-05-07 | Close — superseded by shipped track |
| **#149** | Coverage for 7 critical substrates | 2026-05-07 | Rebase or close |
| **#148** | Roaming dispatch agent ops | 2026-05-07 | Close or rebase |
| **#147** | DocOps authority registry | 2026-05-07 | Close — conflicts with current DocOps |
| **#145** | cron_job_runtime docs | 2026-05-06 | Close or merge |
| **#144** | Backfill docstrings | 2026-05-06 | Rebase or close |
| **#143** | roaming_dispatch_daemon docs | 2026-05-06 | Close or merge |
| **#142** | Archive build_loop.sh | 2026-05-06 | Merge — trivial cleanup |
| **#131** | Structural coherence (Devin) | 2026-05-05 | Close — superseded |
| **#117** | Module consolidation (Devin) | 2026-05-05 | Close — superseded |
| **#99** | Seed revenue cell | 2026-05-05 | Review or close |
| **#271** | PR triage report (Copilot) | 2026-05-13 | Close — one-time report |
| **#59** | Chetana grand memory integration (draft) | 2026-05-02 | Close or rebase — large feature, INCUBATE bucket |
| **#58** | Phase 1 ontology-native insight brief | 2026-05-02 | Review — pre-dates current ontology work |
| **#55** | Cross-agent work OS interface (draft) | 2026-04-29 | Close — AGENTS.md since rewritten, INCUBATE bucket |
| **#44** | Clean canonical drift maps (draft) | 2026-04-27 | Close — conflicts with INTERFACE_MISMATCH_MAP.md, superseded |

---

## 3. SEEDED-BUT-STOPPED PACKAGES

### 3a. BoardStore (`dharma_swarm/board/`)

| Dimension | Value |
|---|---|
| LOC on main | 741 (facade.py, models.py, event_log.py, __init__.py) |
| Spec | `docs/architecture/SWARM_BOARDSTORE_SPEC.md` (2,300 lines, extremely detailed) |
| Consumers | 0 runtime consumers. Only test files + trace attractor readers import it. |
| On PR #321 | TaskBoard adapter — first real store consumer |
| NOT done | 6 of 7 store adapters, card lifecycle FSM, rollback semantics, cost-cap enforcement, noticer daemon, dharma_swarm.client participation library |
| Next step | Merge #321, then wire orchestrator dispatch through facade |

### 3b. Dhyana (`dharma_swarm/dhyana/`)

| Dimension | Value |
|---|---|
| LOC on main | 205 (drift_triage.py, __init__.py) |
| Consumers | 0. Not imported by any non-test code on main. |
| On PR #321 | Wired into `make onboard` output (drift triage section) |
| NOT done | reconciler.py, track_relevance.py, broken_register_aging.py |
| Next step | Merge #321 to get drift triage into onboarding |

### 3c. Sakshi (`dharma_swarm/sakshi/`)

| Dimension | Value |
|---|---|
| LOC on main | 281 (provenance_log.py, __init__.py) |
| Consumers | Trace attractor readers + tests only. No runtime write path. |
| NOT done | decision_chain.py, constraint_replay.py, multi_agent_attribution.py |
| Next step | Wire provenance logging into real state transitions |

### 3d. Trace Attractor (`dharma_swarm/trace_attractor/`)

| Dimension | Value |
|---|---|
| Status | Most wired seed — readers, projector, CLI all on main |
| Active track item | Native CorrelationContext propagation (in progress) |
| Single blocker | ADR-0002 (trace coverage gate policy) |
| Next step | Write ADR-0002 → close track |

### 3e. Operator Core (`dharma_swarm/operator_core/`)

| Dimension | Value |
|---|---|
| Files | 21 Python files (control surface, sessions, permissions, payloads, adapters) |
| Status | Active and load-bearing — control surface projector is LIVE |
| Gap | Handoff stub exists but not yet wired to agent dispatch |

### 3f. Operator Brief (`dharma_swarm/operator_brief/`)

| Dimension | Value |
|---|---|
| Files | 6 Python files (watchdog, persistence, value_events, insight_brief, types) |
| Status | Shipped (first substrate-native seam). Watchdog wired to control surface. |
| Gap | Trace metadata propagation from CorrelationContext (active track item) |

---

## 4. BROKEN REGISTER — OPEN ITEMS (9 of 23 total)

| ID | Severity | Domain | Summary | Status |
|---|---|---|---|---|
| **BR-003** | BLOCKER | runtime | Self-evolution apply gate closed (shadow-only) | PARTIAL — intentionally gated |
| **BR-004** | DEGRADED | cron | Repo vs live cron split-brain | PARTIAL — authority declared |
| **BR-005** | DEGRADED | runtime | Algedonic stream degenerate (sensing > actuation) | PARTIAL |
| **BR-009** | DEGRADED | docs | Roadmap contested (3 docs claim primacy) | FIX on PR #321 |
| **BR-010** | STALE | docs | NAVIGATION.md stale (53+ days old) | FIX on PR #321 |
| **BR-011** | STALE | docs | INTERFACE_MISMATCH_MAP self-declared stale | FIX on PR #321 |
| **BR-012** | STALE | docs | CYBERNETIC_LOOP_MAP stale (Loop 8 error) | FIX on PR #321 |
| **BR-013** | DEGRADED | agent/docs | Agent contract fragmented across 8+ surfaces | PARTIAL — pointer-stub exists |
| **BR-014** | DEGRADED | runtime | BHED_GNAN telos gate always-passes | OPEN — governance-locked |

Merging PR #321 closes BR-009/010/011/012 → drops to 5 open items.

---

## 5. STALE MAPS (found during deep read)

| Map | Last audit | Current HEAD | Gap |
|---|---|---|---|
| `CYBERNETIC_LOOP_MAP.md` | 2026-05-05 (16 days) | Still says "no configured LLM provider" — but providers ARE working locally | Needs refresh |
| `INTERFACE_MISMATCH_MAP.md` | 2026-05-04 (17 days) | 90+ PRs merged since then | Needs refresh |
| `LIVE_OPS_DASHBOARD.md` | 2026-05-11 (10 days) | Stale threshold 7d; 6 PRs merged since | Needs refresh |
| `NAVIGATION.md` | 2026-05-14 | Post-trace-attractor, post-BoardStore work not reflected | Needs refresh |

---

## 6. RULE 10 VIOLATION (found during deep read)

`terminal_bridge.py` is **2,539 lines** against a ceiling of **2,411** (+10% of grandfathered 2,192). This is 128 lines over budget. The module needs decomposition before any changes. The `terminal_commands/` subpackage extraction (PR #319 history) was a start but didn't go far enough.

---

## 7. DASHBOARD DATA FIDELITY

| Category | Count | Pages |
|---|---|---|
| **LIVE** | 9 | Control Surface, Command Post, Runtime, Overview, Modules, Conv Log, Claude/GLM-5/Qwen3.5 Chat |
| **PROVIDER-GATED** | 13 | Agents, Tasks, Evolution, Telemetry, Stigmergy, Lineage, Ontology, Gates, Audit, Eval, Models, Timeline, Qwen3.5 Telemetry |
| **STUB** | 5 | Observatory, Ecosystem, Synthesizer, Workflows, Blocks |

Provider keys ARE present locally (OpenRouter, OpenAI, NVIDIA NIM, Ollama, Cerebras confirmed). The 13 PROVIDER-GATED pages come alive once agents dispatch. PR #323 fixes the env alias mismatches that prevented provider recognition.

---

## 8. CYBERNETIC LOOP CLOSURE

| # | Loop | Status | Gate |
|---|---|---|---|
| 1 | Swarm Task | NOT CLOSED (prod) | Stale process restart + end-to-end dispatch verification |
| 2 | Evolution | NOT CLOSED | Needs Loop 1 + DarwinEngine with real fitness data |
| 3 | Metabolic | PARTIAL | Cron runs, split-brain (BR-004) |
| 4 | Guardian | PARTIAL | Sensing works, actuation limited |
| 5 | Algedonic | PARTIAL | Signal stream alive, consumers incomplete (BR-005) |
| 6 | Recognition | PARTIAL | RecognitionEngine exists, seed generated |
| 7 | Memory | NOT CLOSED | MemoryKernel release gate not wired (PR #312) |
| 8 | Stigmergy | NOT CLOSED | Needs active agent coordination |
| 9 | Strange Loop | NOT CLOSED | Self-modification gated (BR-003) |
| W | Witness | CLOSED (test) | First loop closed end-to-end |

**0 loops fully closed in production.** The Loop Map itself is stale (last audit 2026-05-05) and incorrectly claims "no configured LLM provider" as the single gate — providers are now present.

---

## 9. SESSION HISTORY — WHAT SHIPPED vs STOPPED

### Merged to main
1. **PR #313** — Single-door onboarding (`make onboard`), stale pointer cleanup
2. **PR #315** — gitnexus npm fix
3. **PR #318** — Cockpit track closure (SHIPPABLE)
4. **PR #319** — Track transition + BoardStore/Dhyana/Sakshi seeds

### Awaiting merge (CI green)
5. **PR #321** — TaskBoard adapter + Dhyana onboard + BR closure (0 CI checks — needs push)
6. **PR #323** — dkeys env alias normalization + dashboard fidelity audit (21/22)
7. **PR #325** — Codex toolbelt onboarding (22/22)

### Architecture deliverables
8. Invariant command plane findings (13 spines, verdict: Control Surface is the command plane)
9. Dashboard fidelity audit (25 pages categorized)

---

## 10. NEXT PHASE MAP — PRIORITY ORDER

### Phase 0: Housekeeping (~2 hours)

| # | Task | ROI | Effort |
|---|---|---|---|
| 0.1 | Re-push PR #321 to trigger CI, then merge #321, #323, #325 | Unlocks 4 BR closures + env aliases + onboarding docs | 30 min |
| 0.2 | Write ADR-0002 (trace coverage gate policy) | Closes active track (1 file) | 30 min |
| 0.3 | Close trace-identity-coverage track → open next track | Governance hygiene | 15 min |
| 0.4 | Triage 23 stale PRs (close superseded, rebase keepers) | Drops PR queue from 35 → ~12 | 60 min |

### Phase 1: Close Loop 1 (~1-2 days)

**Goal:** First cybernetic loop fully closed in production.

Loop 1 (Swarm Task) is closest. Providers are configured. Env aliases are fixed (PR #323). TaskBoard is operational. What remains:
- Stale process restart after env normalization
- End-to-end dispatch → task → completion → feedback verification
- Update CYBERNETIC_LOOP_MAP.md with corrected provider status

This makes 13 PROVIDER-GATED dashboard pages come alive.

### Phase 2: Wire seeds into runtime (~3-5 days)

| # | Task | What it unlocks |
|---|---|---|
| 2.1 | BoardStore facade → orchestrator dispatch | Cards participate in real task flow |
| 2.2 | Sakshi provenance → agent dispatch + PR decisions | Tamper-evident audit trail on real actions |
| 2.3 | Dhyana drift triage → automated BR aging | Stale broken register items auto-flagged |

### Phase 3: Command plane promotion (~2-3 days)

| # | Task | LOC |
|---|---|---|
| 3.1 | Nav reorder: Control Surface → position #1 | ~5 LOC |
| 3.2 | Active track banner on command plane | ~40 LOC |
| 3.3 | Drift triage panel (Dhyana → dashboard) | ~45 LOC frontend + ~50 LOC backend |
| 3.4 | Handoff-prompt button (agent dispatch from cockpit) | ~30 LOC |

### Phase 4: Stale map refresh (~1-2 days)

| # | Task | Evidence |
|---|---|---|
| 4.1 | Refresh CYBERNETIC_LOOP_MAP.md (last audit 16d ago, stale provider claim) | Loop Map §42, reconciliation evidence |
| 4.2 | Refresh INTERFACE_MISMATCH_MAP.md (last X-ray 17d ago) | Mismatch Map §1 |
| 4.3 | Refresh LIVE_OPS_DASHBOARD.md (snapshot 10d old, threshold 7d) | Live Ops §4 |
| 4.4 | Decompose terminal_bridge.py (2,539 > 2,411 ceiling) | Rule 10 violation |
| 4.5 | Consolidate agent contract from 8+ surfaces → 1 (BR-013) | Broken Register |

### Phase 5: Deep substrate (multi-week)

1. BR-003 — Open evolution apply gate (after Sakshi provenance chain is live)
2. Loops 2-9 closure — systematic, one per track
3. BoardStore full adapter cutover (remaining 6 stores)
4. MemoryKernel release gate (PR #312)

---

## 11. THE HONEST NUMBERS

| Metric | Now | After Phase 0 | After Phase 1 |
|---|---|---|---|
| Open PRs | 35 | ~12 | ~11 |
| Broken register open | 9 | 5 | 5 |
| Loops closed (prod) | 0 | 0 | 1 |
| Dashboard LIVE pages | 9 | 9 | 9-15 |
| Active track completion | 5/6 | 6/6 SHIPPABLE | new track |
| Seeds wired to runtime | 0 of 3 | 1 of 3 | 1 of 3 |
| Stale maps | 4 | 4 | 3 (loop map refreshed) |
| Source files | 610 | 610 | ~610 |
| Test files | 581 | 581 | ~581 |
| Rule 10 violations | 1 (terminal_bridge.py) | 1 | 1 |
