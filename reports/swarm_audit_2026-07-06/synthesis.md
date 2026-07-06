# FINAL AUDIT REPORT — dharma_swarm whole-repository archaeological audit

*Read-only audit. Synthesized from orchestrator orientation, a 16-agent scout wave, and nine fresh-context-verified deep-dive clusters (C1–C9). No code was changed; the roadmap in §9 is a proposal for a future session.*

---

## 1. Executive diagnosis

dharma_swarm is a large (1,319 commits, ~4 months, 4,631 tracked files, 2,144 `.py`), unusually **self-aware** codebase: it documents its own gaps in prose, redirects volatile facts to live commands (`make onboard`), and has built real governance machinery (telos gates, MAP-Elites diversity archive, docops reconcile, track-closure gates). The core engineering primitives named in CLAUDE.md are genuinely wired, not stubs.

The endemic problem is **not** rot or abandonment — it is a single recurring shape that appears at seven different altitudes: **one concept materialized in N unreconciled places, where at least one materialization silently drifts, lies, or is dead, and no boundary forces reconciliation.** The repo's own DharmaGraph track already half-diagnoses this ("consolidate 5+ executors, 3 checkpoint mechanisms, 3 workflow compilers"), but the pattern is broader than graph dispatch:

- **Agent persona** lives in ≥4 registries + 2 assemblers; the `skill.md` pipeline the docs call canonical is *dead* (C1).
- **The ReAct execution loop** is duplicated across two god-files that no active track owns (C4).
- **"A measured value"** has no provenance type, so hardcoded `0.0`/`7.0`/`None` cross receipt boundaries wearing the costume of measurements (C2).
- **Resolution status** of interface mismatches is asserted in six places in one 190-line file that lies about being machine-maintained (C3).
- **The active-track portfolio** is byte-duplicated across three files and restated-and-drifted in per-agent instruction files (C6), on a shared unlocked YAML with no merge-time invariant (C9).
- **R_V geometry** is a research-grade vocabulary reused by four proxies that measure nothing transformer-shaped (C5).

The good news: because the pattern is uniform, the fixes are uniform and mostly *subtractive* — extract one shared surface, add one merge-time invariant, mark one boundary. The highest-leverage moves are cheap. The largest *hidden* liability is C4 (the busiest execution surface in the system is governance-unowned) and the largest *trust* liability is C3 (the doc CLAUDE.md calls "the #1 source of runtime failures" is itself unreliable).

Two important corrections from verification: the "false-success" and "R_V proxy" findings are real, but the C5 claim that **MemoryKernel is shadow-only was REJECTED** — it is in fact wired into live orchestrator dispatch (§6, §10). And several C4 findings are directionally right but had inaccurate specifics (§10). Rank by leverage, not ugliness — most of this is attention-tax, not runtime breakage.

---

## 2. Repo map

| Area | Size / note |
|---|---|
| `dharma_swarm/` | 437 flat top-level `.py` + ~35 subpackages (a2a, coordination, council, graph, memory_kernel, operator_core, spine, world_radar) |
| God-files (>500-line rule violated pervasively) | `thinkodynamic_director.py` 5255, `evolution.py` 3632, `providers.py` 3402, `agent_runner.py` 3385, `swarm.py` 3284, `orchestrator.py` 3210, `runtime_state.py` 4111 |
| `tests/` | 813–845 files (largest dir); satellite-file sprawl (5–6 test files per hot module) |
| `scripts/` | 182 files, 78 under `scripts/governance/` |
| `.github/workflows/` | 41 files |
| `reports/` | 907 files, 35 top-level dirs, only 10 in `reports/historical/` |
| Undocumented top-level | `terminal/` (Bun/TS), `desktop-shell/` (Rust/Tauri) — absent from CLAUDE.md File Organization |
| Top churn (touch-count) | SOVEREIGN_MANIFEST.md 319, AUTO_INVENTORY.md 316 (both machine-generated), then orchestrator.py 56, agent_runner.py 51 |

Active portfolio: 5 co-equal tracks, all serving `substrate-nativeness`. Neither `revenue-external-humans-served` nor `research-depth` has an active track (contrary to the brief's framing — both are equally track-less per `active_track_evidence.md`).

---

## 3. Six-month persistence map

Which pathologies survived multiple sessions / refactors untouched:

| Pathology | First seen | Still live at HEAD | Persistence signal |
|---|---|---|---|
| `cost_usd=0.0` TODO in economic_agent | 2026-03-27 (307ea506) | Yes | Survived 3+ commits to same file |
| GraphQL resolvers all-empty stubs | 2026-03-23 (ef531941) | Yes (but unmounted/dead) | Untouched ~3.5 months |
| 3 provider streaming `NotImplementedError` | 2026-03-09 (3ffe5b7c) | Yes | Survived provider-key unification #795 |
| `jikoku with_span_metadata` no-op | 2026-03-09 | Yes | Untouched ~4 months |
| Dead `skill.md` persona pipeline | ~2026-03 | Yes | Edited 2026-07-05 (ede67de1) with zero runtime effect |
| Two divergent ReAct engines | accretive | Yes | No track ever owned agent_runner.py / autonomous_agent.py |
| `providers.py` content-collapse honesty bug | 2026-04-06 | Fixed 2026-06-12 (6491e9bb) after ≥4 piecemeal re-fixes; one prior fix "never on main" |
| `INTERFACE_MISMATCH_MAP` header/table self-contradiction | recurring | Yes | Flip-flopped 3× (6d812b5→b2c65c51→e28b253) |
| WorldModelAgent API mismatch (MM-13→NEW-14) | 2026-04-08 marked RESOLVED on unmerged branch | Fixed on main 2026-06-22 | Dead in production ~147 crashes/day 2026-06-10 while doc said "All BLOCKERs resolved" |
| docops counter cascade | chronic (100 fix(docops) commits) | **Structurally closed** 2026-06-16 (#616/#617) | The one endemic problem genuinely retired |
| VPS-provisioning restated across 3 tracks | 2026-06-24 | Yes | Restated near-verbatim, zero resolution |

The dominant six-month signature: **research/measurement substrate is repeatedly built and left unwired** (cost_tracker, rv.py, skill.md bodies, MemoryKernel), and **honesty bugs recur because there is no shared "report truthfully" contract** (re-fixed per-subsystem across CI, providers, evolution archive, A2A).

---

## 4. Top endemic problems

### 4.1 — Two divergent ReAct execution engines, governance-unowned (C4)

- **Severity:** High · **Confidence:** High (core), Medium (specific tool-set claims — see §10)
- **What is happening:** The agent execution loop (LLM call → parse tool-calls → run tool → gate → loop) exists twice: `AgentRunner._complete_with_tool_loop` (agent_runner.py:1916, OpenAI tool_calls shape) and `AutonomousAgent._reason_and_act` (autonomous_agent.py:480, Anthropic content-block shape). Each carries its own tool registry and its own telos-gate invocation scope. `persistent_agent.py:3` explicitly declares AutonomousAgent the canonical ReAct kernel — "AgentRunner never got the memo."
- **Evidence:** AutonomousAgent tool dict has 14 tools incl. bash/memory/stigmergy/ginko (autonomous_agent.py:963-978); AgentRunner's `_execute_local_tool` has a different set (agent_runner.py:1792-1914). Gate scope differs: AutonomousAgent gates *per tool call* for 4 named side-effect tools (`_SIDE_EFFECT_TOOLS`:951); AgentRunner gates *once per task* before execution (agent_runner.py:2163) — both ultimately call the same `TelosGatekeeper`, so the divergence is **invocation granularity, not two gate batteries** (verifier correction). The DharmaGraph spec's "Executors (5+)" inventory (DHARMAGRAPH_PHASED_SPEC:34) is entirely graph/dispatch-altitude; grep for `autonomous|ReAct|wake` across the whole spec = 0 hits. Neither `agent_runner.py` nor `autonomous_agent.py` appears in any track's owned-surfaces.
- **Why agents get stuck:** The duplication is one altitude *below* the class names — scouts see `Orchestrator` vs `AgentOrchestrator` and debate "dispatcher duplication vs layering," but the real duplicate is two ~40-line loop bodies buried in a 3385- and a 1525-line file. `swarm.py` never imports `autonomous_agent.py`, so a call-graph trace from the boot root never reaches the second engine. CLAUDE.md caps `orchestrator.py` edits to "the minimal seam call" and DharmaGraph non-goals forbid touching sibling surfaces — steering agents *away* from the two files holding the duplication.
- **Root cause:** No `dharma_swarm/execution/` module owns the ReAct loop + tool registry + gate as one consumable unit, and no track charters those files.
- **One-and-done fix:** Extract ONE tool registry + ONE gate invocation shared by both engines (no loop rewrite; bounded blast radius). This forces the governance question — *which track owns agent_runner.py* — to be answered. Do **not** hard-merge the two loops in one PR (the graph track's oracle/DST guardrails cover graph dispatch, not agent execution).
- **Risks/caveats:** `Orchestrator` vs `AgentOrchestrator` at the dispatch altitude is *legitimate layering*, not duplication — do not collapse. The message-shape difference (Anthropic blocks vs OpenAI tool_calls) requires an adapter layer even under the registry-sharing fix.

### 4.2 — Cross-subsystem "false success": un-provenanced scalars cross receipt boundaries (C2)

- **Severity:** High · **Confidence:** High (all 5 findings CONFIRMED)
- **What is happening:** The same shape recurs: a placeholder constant, typed identically to a real measurement, crosses an emit/report/fitness boundary. `economic_agent` sets `cost_usd=0.0` (TODO) so `profit_usd == revenue_usd` by construction (economic_agent.py:467-477), while a fully-built `cost_tracker.py` (43-160) has zero callers. `drift_triage._estimate_age_days` returns hardcoded `7.0` for every row (drift_triage.py:89-97), feeding `priority_score` and the operator-facing `make onboard` display (agent_onboard.py:1585). `jikoku with_span_metadata` documents attaching metadata but its enabled branch is a bare `pass`. The GraphQL stub resolvers all return `None/[]` but are **dead code** (unmounted; the wired `/graphql` is a separate REST router) — a landmine, not a live lie.
- **Evidence + lineage:** The history proves the class has no shared guard: `providers.py` content-collapse re-fixed ≥4× (abbe1db1 2026-04-06 → 6491e9bb 2026-06-12, whose body notes a prior fix "was never on main"); the "no provider" lie killed 3× in one day (873bf7d3/0bed9251/70b18674, 2026-06-23); CI `-x`/pipe-masking hid **46 failing tests** (c01f473f); evolution archive fabricated `gates_passed` (dbdd2416).
- **Why agents get stuck:** Each instance is a one-line "TODO: wire later" that passes local tests (the tests assert the placeholder). The fabrication is only visible tracing *who consumes the value across a module boundary* — which no single-file edit does.
- **Root cause:** No provenance type separating a subsystem's internal placeholder from a signal a downstream consumer trusts. `RVReading`, `LedgerEntry`, receipts all validate identically whether the number was measured or defaulted.
- **One-and-done fix:** Add one shared `assert_outcome_truthful` test helper to the existing receipt/closure surface; attach it to the 4 live emitters (economic ledger, drift triage, spine receipt, arena fitness). Per-instance: wire `cost_tracker.log_cost` into economic_agent; read a real timestamp (control-surface rows already carry `freshness`/`last_verified`) or return an `UNMEASURED` sentinel in drift_triage; delete the dead GraphQL package; make jikoku's docstring honest.
- **Risks/caveats:** economic_agent is currently **dormant** (no production consumer) — this is a latent landmine that arms the moment organism-rewire activates it, not a live corruption today. drift_triage's `7.0` is a uniform multiplier so it does *not* change ranking order — medium, not critical.

### 4.3 — Agent persona sourced from 4+ registries; the `skill.md` pipeline is dead (C1)

- **Severity:** High · **Confidence:** High
- **What is happening:** Role→persona text is materialized in `skill.md` files (8), `daemon_config.ROLE_BRIEFINGS` (5 PSMV roles), inline crew system_prompt strings, and `agent_constitution` roster (6 named agents), assembled by two `_build_system_prompt` functions plus a holon `active.txt` source. **Editing any `skill.md` persona body has zero runtime effect** — `agent_runner._build_system_prompt` (948-967) sources only `ROLE_BRIEFINGS` and never imports `skills.py`; every module that *does* import `SkillRegistry` consumes only metadata and discards `.system_prompt`.
- **Evidence:** `create_from_skill` (profiles.py:216-244) is the only skill→prompt bridge and has zero production callers; its output `AgentProfile.system_prompt_extra` is never converted to `AgentConfig.system_prompt`. `cartographer.skill.md`'s distinguishing manifest-verification protocol (`~/.dharma_manifest.json`) never reaches a prompt; the `ROLE_BRIEFINGS` cartographer text is unrelated generic prose. `AgentRole('builder')`/`AgentRole('jagat_kalyan')` empirically raise `ValueError` (no enum member).
- **Why agents get stuck:** `SkillRegistry` *is* imported in swarm/startup_crew/stage_executor, giving false confidence skills are wired; the break is that each consumer specifically discards the body. `ROLE_BRIEFINGS` always returns plausible text, so nothing errors — the pipeline is dead *silently*.
- **Root cause:** No `persona_resolver` boundary with a documented precedence chain; every spawn path re-derives the mapping and drops a different field.
- **One-and-done fix:** In `_build_system_prompt`, consult `SkillRegistry().get(config.role.value).system_prompt` before falling back to `ROLE_BRIEFINGS`; add a regression test asserting cartographer's manifest text reaches the built prompt. The role names already match skill basenames, so `.get()` resolves cleanly with a safe `None` fallback.
- **Risks/caveats:** The `role-persona-duplicated-4x` finding was **WEAKENED** — one cited site (`startup_crew.py:216-252`) is `CYBERNETICS_CREW`, not `DEFAULT_CREW`, and `DEFAULT_CREW` carries no inline system_prompt. The fragmentation is real (verification found *more* sites than claimed, incl. swarm.py:831), but the specific "4 registries" count under-counts and the fix scope is larger than stated.

### 4.4 — INTERFACE_MISMATCH_MAP.md, the designated #1 failure tracker, is itself unreliable (C3)

- **Severity:** Critical (of the tracking instrument) · **Confidence:** High
- **What is happening:** CLAUDE.md mandates this doc as the first thing to read before any bug/feature. Its header claims "Maintainer: Guardian Crew — auto-updates every 4 hours," but `guardian_crew.py` has **zero** references to the file — it is entirely hand-edited. The real executable guard (`mismatch_registry.py:109`) only fires on `status=open AND severity=BLOCKER`, but the YAML has zero open entries (5 of 25 migrated, all resolved) — a permanent no-op. Status is asserted in six unsynchronized places in one file.
- **Evidence:** Live self-contradiction at HEAD: header line 7 says "All BLOCKERs resolved" while table line 38 lists NEW-12 as a BLOCKER/HALF-OPEN — and NEW-12 is genuinely open (`_resolve_agent_model_override` still absent from autonomous_agent.py; 6 tests silently skip). Confirmed resolve→reopen cycles: MISMATCH-03 (message_bus) marked RESOLVED, re-listed DEGRADED, lived ~3 months, closed by a *different* fix (d4e982e); MM-13 (WorldModelAgent) marked RESOLVED on an *unmerged* branch while main crashed 147×/day, re-filed as NEW-14, fixed 2.5 months later (29e0e53f). The machine YAML is explicitly declared a "lagging projection" subordinate to the prose — so the only artifact a gate *can* enforce is definitionally stale.
- **Why agents get stuck:** Marking "RESOLVED" is a one-word prose edit with no truth-condition; a green test on the author's own branch feels safe (MM-13 was green on `organ/03-seat` while main crashed). The doc claims to be machine-maintained, so agents assume something else owns its accuracy.
- **Root cause:** No separation between DATA (which mismatches exist), VERIFIER (status = f(pinned test result, fixed_in ancestry)), and RENDERER (the .md). All three are fused into one hand-edited file.
- **One-and-done fix:** Three edits that stop the active lying: delete the false Guardian provenance; fix the header/table contradiction; add the 4 genuinely-open entries (NEW-05/07/08/12) to the YAML with `status=open` + a pinned test/SHA so `check_mismatch_adjacency` stops being a no-op. Larger: invert the artifact relationship — YAML canonical, .md generated, status computed from `git merge-base --is-ancestor <fixed_in> HEAD` or a pinned xfail test.
- **Risks/caveats:** Two substrate fixes *underneath* the map (message_bus act-then-mark; NEW-05 consistency_guard as a detector) are correct — relabel, don't rip out. Verification found the resolve-reopen finding's evidence had a wrong branch name and one anachronistic commit citation, but the cycles themselves are independently confirmed.

### 4.5 — Track-portfolio governance runs on a shared unlocked YAML with no merge-time invariant (C9)

- **Severity:** High · **Confidence:** High
- **What is happening:** `runtime-truth-reconciliation-2026-06` was closed SHIPPED on 2026-06-06 (c28951d), then **silently resurrected ACTIVE for ~21-24 days** when stale PR #555 (branched before the close) squash-merged and overwrote the whole file (dbbc4588). A 2026-06-24 re-verification pass (f017f753) even re-blessed it ACTIVE instead of noticing it was closed. Finally re-closed 2026-07-01 (dd02c1e0).
- **Evidence:** `check_track_status.py` builds `known_ids` as a silent union of active+closed (1542-1546) and never diffs against the merge base — the CI job checks out `fetch-depth: 0` (base available) but the checker never uses it. The regression baseline (`_load_prior_passed`:1811) reads only prior `active_tracks`, never `closed_tracks`, so resurrection evades even the diff-like mechanism.
- **Root cause:** A snapshot validator exists; a *transition* validator does not. The append-only rule for `closed_tracks` is asserted only in a YAML comment.
- **One-and-done fix:** ~30 lines: `_check_lifecycle_transition(base, head)` loading base via `git show ${GITHUB_BASE_REF:-origin/main}:...ACTIVE_TRACK.yaml` and ERRORing on append-only violations, active∩closed overlap, or resurrection without `reopened_at`. CI already blocks on ERROR — no workflow change.
- **Risks/caveats:** The resurrection window is already closed — this is preventive, not a live incident. The 7 pre-2026-06-30 closures are *deliberately* grandfathered (`FINAL_BOSS_EFFECTIVE_DATE`); do not retroactively hard-fail them — stamp an explicit `grandfathered_pre_rigor` flag instead.

### 4.6 — Instruction-file drift: per-agent docs restate CLAUDE.md rules ungated (C6)

- **Severity:** High (DEVIN.md finding) · **Confidence:** High
- **What is happening:** DEVIN.md §9 hand-copies 9 CLAUDE.md behavioral rules "for emphasis" with no renderer and no diff-gate. It has **already drifted**: it tells Devin files >500 lines are allowed "with grandfathering" (a permission CLAUDE.md:298 never grants) and omits the 2026-06-18 worktree-budget rule entirely. The ACTIVE_TRACK block is byte-identical across *three* files (CLAUDE.md, BUILD_SESSION_ENTRYPOINT.md, SOVEREIGN_MANIFEST.md) — this duplication is *governed* (YAML-sourced, rendered), but its sync CI gate is `continue-on-error` on the PR path and only hard-fails on the weekly schedule, so drift can merge and live up to 7 days.
- **Evidence:** git blame: DEVIN.md §9 authored 2026-05-23 (522a068d), predating the worktree rule by ~1 month — genuine temporal drift. `active-track.yml:79-83` carries `continue-on-error: ${{ github.event_name != 'schedule' }}`. QWEN.md is structurally allowlisted but absent from the ownership map, asserting a false "Current State" (branch `holon/spine-v1`, Mac path `/Users/dhyana/...`, a 2026-06-11 brief) ~1 month stale.
- **Root cause:** No "managed-block or link, never hand-copy" rule; per-agent files restate owned facts without a gate.
- **One-and-done fix:** Replace DEVIN.md's restated bullets with a pointer to CLAUDE.md §Behavioral Rules; remove `continue-on-error` from the sync step (one line — machinery exists); rewrite QWEN.md as a defers-to-CLAUDE.md stub + add an ownership-map row.
- **Risks/caveats:** The 3× ACTIVE_TRACK rendering is intentional (one-hop convenience) — do NOT de-duplicate by deleting copies. CLAUDE.md itself is operator-owned (DEVIN.md:323 "Never modify CLAUDE.md") — the layer-inversion sub-finding (~55% of CLAUDE.md is fast-changing Intent-layer state above the behavioral doctrine at line 268) must be *proposed*, not applied by a subagent.

### 4.7 — Vision-code alignment: dormant organs and metaphorical R_V (C5)

- **Severity:** Medium · **Confidence:** High (with one REJECTED sub-finding)
- **What is happening:** CLAUDE.md's Key Abstractions read as standing production reality, but several marquee organs are dormant-by-default flags. `Organism` ("the living system") is constructed only when `DHARMA_ORGANISM_ROOT=1`, which no shipped config sets (grep confirms it appears only in api/main.py + one test). `StrangeLoop`'s only constructor is inside that flag-gated Organism, so it fires in no shipped config — and its name collides with the live `StrangeLoopMemory`. `RVReading` has five producers but only `rv.py` does real transformer SVD geometry; four proxies (gaia_fitness `pr_early=1.0` hardcoded, dse_integration `1.0-archived*0.1`, swarm_rv word-frequency, living_map Jaccard) launder unrelated scalars into R_V vocabulary — and the production evolution/cockpit paths read the *proxies*, not rv.py.
- **Evidence:** ECONOMIC_VISION.md's own status notes admit the COLM 2026 publication the "Market-1 first-mover" thesis depended on never happened. `l4_rv_correlator.py` (the only importer of the real `RVMeasurer`) is itself imported nowhere.
- **Root cause:** No provenance discriminator on `RVReading`; no live/staged marker in Key Abstractions distinguishing an organ that runs in shipped configs from one behind an unset flag.
- **One-and-done fix:** Documentation-truthfulness pass (no behavior change): add live/staged markers to each dormant organ; add a "two meanings of R_V" note. Durable: add `measurement_kind` to `RVReading`, rename `colony_rv`/`rv_trend` out of R_V vocabulary.
- **Risks/caveats:** These are legitimately *staged* rollouts (organism-rewire D5/D2), not overstatements of intent — only the prose overstates them. Do NOT flip the flags as a "fix." **The MemoryKernel sub-finding was REJECTED** (§6, §10): MemoryKernel is *not* shadow-only — it is wired into live orchestrator dispatch.

---

## 5. Duplication and overlap ledger

| # | Concept | Materializations | Reconciled? | Owning issue |
|---|---|---|---|---|
| 1 | ReAct execution loop + tool registry + gate | 2 engines (agent_runner, autonomous_agent) | No | C4 §4.1 |
| 2 | Role→persona text | ≥4 registries + 2 assemblers + holon file | No | C1 §4.3 |
| 3 | `RVReading` producers | 5 (1 real, 4 proxy) | No (no discriminator) | C5 §4.7 |
| 4 | Interface-mismatch status | 6 places in 1 file + subordinate YAML | No | C3 §4.4 |
| 5 | ACTIVE_TRACK block | 3 byte-identical files | Yes (rendered) but PR sync gate advisory | C6 §4.6 |
| 6 | CLAUDE.md behavioral rules | CLAUDE.md + DEVIN.md hand-copy | No (drifted) | C6 §4.6 |
| 7 | "block a stale A2A row" | ~7 near-identical 480-523-line scripts (10 total a2a_*, ~5000 lines) sharing 7 copy-pasted helpers, differing only in a hardcoded DEFAULT_TASK_ID | No | **C8** |
| 8 | 4 kernel-*.yml workflows | identical triggers, 4 files | No | C8 |
| 9 | Live repo metrics (counts) | 5 materializations (checker, 2 docs, assertions.yaml, CLAUDE.md) | **Now reconciled** post-merge (#616) | C7 |
| 10 | Dual TUI | tui_legacy.py (1795) + tui/app.py (2543) | No (stale fallback) | C4 |
| 11 | Two checkpoint mechanisms | checkpoint.py (loop-shaped) vs graph/checkpoint.py (dispatch-shaped) | **Correct — NOT duplication** | C4 do-not-touch |
| 12 | "axiom" | DharmaKernel 25 signed axioms vs onboard A1-A8 hygiene axioms | No (name collision) | C6 |

**C8 (ops-tooling-sprawl)** in full: the 10 `a2a_block_*` scripts (all landed in one batch commit 532d61e5, 2026-07-03) have zero Makefile/CI callers and are exercised only by their own paired tests — they are *incident receipts masquerading as tools*. Fix: `git mv` to `scripts/governance/incidents/` (zero-risk, tests move with them); keep the Makefile-live `a2a_agent_onboard.py`. Two orphaned scripts confirmed dead: `worktree_second_pass_list.py` (hardcodes `/Users/dhyana/...`, zero callers) and `verify_quality_membrane.py` (superseded by separate CI workflows). `tests.yml:70-71` "Lint (ruff)" carries `|| true` — a **dead gate giving false assurance** (drop `|| true`).

---

## 6. Vision-to-code alignment

The Transcendence Principle (diverse competent agents, decorrelated errors, quality aggregation) is **genuinely implemented** in real code: `archive.py MAPElitesGrid` is load-bearing in the DarwinEngine pipeline; `diversity_archive.py` is a deprecated shim (the D6a consolidation actually happened); telos gates do SHA-256 signing and hard-reject proposals; VSM `AlgedonicChannel` persists and has real threshold checks. These are not misaligned.

What *is* misaligned is **NORTH_STAR §2's "measurable awareness" claim**, which the vision hangs on R_V mechanistic geometry. In production that claim is carried by proxies, not by `rv.py`'s transformer measurement (§4.7). And crucially, the fabricated-signal cluster (C2) attacks the *aggregation substrate itself*: `cost_usd=0.0` makes every agent look equally efficient, so quality-weighted selection cannot distinguish them — the Krogh-Vedelsby diversity term the repo says it optimizes would be computed over lies. Drifted per-agent instruction files (C6) and a lying mismatch map (C3) inject **correlated** misinformation into otherwise-decorrelated agents — the exact opposite of the mechanism. The C4 two-engine split produces *decorrelated capabilities by accident* (a 14-tool agent vs a 5-tool agent depending on which dispatcher woke it), which is capability variance masquerading as diversity.

`revenue-external-humans-served` has substantial scaffolding (`dharma_swarm/revenue/`, `VENTURE_CELL_PORTFOLIO.yaml`) but self-reports `revenue_usd: 0`, a HELD 28/100 gauntlet score, and one DORMANT cell — the yaml is honest if read in full. The house pattern: **scaffolding/vocabulary/governance-doc structure is over-produced relative to externally-verifiable outcomes.**

**Verification correction (important):** C5's claim that MemoryKernel is a read-only shadow was **REJECTED**. Grep found real non-shadow constructions (`build_orchestrator_memory_kernel` in orchestrator.py:1150-1162, last touched 2026-07-06 PR #799); `ContextCompiler.compile_bundle` calls `build_memory_kernel_default_context` unconditionally and appends a real `memory_kernel_section`, independent of the `memory_kernel_shadow` flag. The drift runs the *opposite* direction from the finding: code has already promoted MemoryKernel past shadow-only into a live default context source, contradicting the M3E intent doc. CLAUDE.md's "canonical front door" language is therefore *more* accurate than the finding credited.

---

## 7. Agent confusion map

Where a fresh agent predictably gets misled:

1. **"skills are wired"** — grep for `SkillRegistry` returns hits in 4+ files; the break is that each discards `.system_prompt`. Editing a `skill.md` looks effective; it is not (C1).
2. **"this is fixed"** — INTERFACE_MISMATCH_MAP header says "All BLOCKERs resolved"; the same file's table says otherwise, and the code confirms the table (C3).
3. **"the living system runs"** — Key Abstractions read Organism/StrangeLoop as standing behavior; they are behind an unset flag (C5).
4. **"an rv field is a geometry measurement"** — four of five producers are proxies (C5).
5. **"this track is active"** — could be a resurrected SHIPPED track (C9).
6. **"DEVIN.md restates the rules faithfully"** — it invented a 500-line exception and dropped the worktree rule (C6).
7. **"scripts/governance/a2a_* is a subsystem"** — 10 of 11 are spent one-off receipts (C8).
8. **"green CI = lint enforced"** — the ruff step is `|| true` (C8).
9. **"consolidate the executors = DharmaGraph's job"** — the spec's frame is graph-dispatch; the two ReAct engines are out of frame and unowned (C4).
10. **"touch-count ranks hot files"** — the top two are machine-generated (C7); exclude marker-bearing/gitignored files from any hotspot audit.

---

## 8. Wasted energy and bottlenecks

- **The docops counter cascade (C7) — now retired but historically the single largest energy sink:** 100 lifetime `fix(docops)` commits, an O(n²) merge-queue collision cascade, because two committed docs froze live metrics that a CI gate verified by exact string equality. **Structurally closed** 2026-06-16 (#616/#617: advisory-on-PR counts + post-merge reconcile). Do NOT re-tighten. Remaining hardening: name `active_track_evidence.*`/`track_portfolio.json` in CLAUDE.md's "runtime receipts never enter git" clause (doctrine currently lags the .gitignore); add a pre-commit staging guard. *(Verification note: the finding's "daily peak 52 on 2026-06-05" is inaccurate — actual peak 19 on 2026-05-24 — but the cascade itself and its resolution are confirmed.)*
- **Piecemeal honesty re-fixes (C2):** ~4 months of the same class re-fixed per-subsystem because no shared outcome-truthful contract exists.
- **Same-day bug-fix churn:** orchestrator settled-counter fixed 3× in 22h; providers content-collapse ≥4×; a real WorldModelAgent fix sat unmerged on a branch while main crashed on every boot.
- **VPS blocker restated 3× (C9):** one human action described near-verbatim in loop-closure, organism-rewire, dharmagraph — closing it requires editing three places in sync. Fix: an `ops_blockers:` node + `blocked_by: [OPS-VPS-001]`.
- **reports/ sprawl (C8):** 907 files, only 10 archived; a 2026-04-02 cleanup plan named quarantine targets that still sit unarchived — but its two headline dirs are **live-referenced** by `long_context_sidecar_eval.py`/`mission_garden.py`, so the plan's headline recommendation is *unsafe to execute mechanically*.
- **Onboarding attention tax:** every `grep`, `ls scripts/governance`, `make help` returns a surface fragmented between live and dead with no marker.

---

## 9. One-and-done roadmap (proposal for a future session)

**First 24 hours (safe, unilateral, high-leverage):**
1. Remove `continue-on-error` from `active-track.yml` sync step → *eliminates the ACTIVE_TRACK drift-merge window forever* (C6).
2. Drop `|| true` from `tests.yml` ruff step → *ends a permanently-false green lint gate* (C8).
3. Fix INTERFACE_MISMATCH_MAP header/table contradiction + delete false Guardian provenance → *stops the map actively lying* (C3).
4. `git mv` the 10 `a2a_block_*` scripts to `incidents/`; delete the 2 orphaned scripts → *de-fogs scripts/governance discovery* (C8).

**First week:**
5. Add `_check_lifecycle_transition` to `check_track_status.py` → *eliminates the entire track-resurrection class* (C9).
6. Add the 4 open mismatch entries to the YAML with pinned tests → *gives the pre-commit guard teeth; ends the no-op* (C3).
7. Replace DEVIN.md's hand-copied rules with a pointer; rewrite QWEN.md to a stub → *ends per-agent instruction drift* (C6).
8. Add `assert_outcome_truthful` helper + wire `cost_tracker` into economic_agent; fix drift_triage age → *ends the fabricated-signal class at 4 emitters* (C2).
9. Doc-truthfulness pass on Key Abstractions (live/staged markers, "two meanings of R_V") → *stops the dormant-organ/R_V confusion* (C5) — **propose CLAUDE.md edits to operator.**

**First month:**
10. Extract ONE shared agent tool registry + gate invocation used by both ReAct engines; open a track owning `agent_runner.py`/`autonomous_agent.py` → *ends the capability-drift-between-engines class and answers the governance-ownership gap* (C4).
11. Consolidate the 10 a2a scripts into one parameterized `a2a_block_row.py` + selector registry; merge the 4 kernel workflows → *ends the incident-script recurrence* (C8).
12. Invert INTERFACE_MISMATCH_MAP: YAML canonical, .md generated, status computed from test/SHA ancestry → *makes the tracker structurally unable to self-contradict* (C3).
13. Add `measurement_kind` to `RVReading`; rename proxy surfaces out of R_V vocabulary (C5). One-time re-verify the 7 grandfathered track closures with an explicit flag (C9).

---

## 10. Verification and uncertainty

Honest accounting across all nine clusters (verdicts from the fresh-context verifiers):

| Cluster | Findings | CONFIRMED | WEAKENED | REJECTED |
|---|---|---|---|---|
| C1 identity-fragmentation | 5 | 4 | 1 (role-persona-duplicated-4x: startup_crew cite was CYBERNETICS_CREW not DEFAULT_CREW; fragmentation real but count under-stated) | 0 |
| C2 false-success | 5 | 5 | 0 (honesty "5x" mildly oversold; core intact) | 0 |
| C3 mismatch-map-rot | 5 | 5 | 0 (resolve-reopen had a wrong branch name + 1 anachronistic commit cite; cycles independently confirmed) | 0 |
| C4 orchestration-fragmentation | 5 | 2 | 3 (agentrunner-vs-autonomousagent: tool-set enumeration wrong, bash not exclusive, "every dispatch" overstated, gate framing imprecise; thinkodynamic-fourth-tail: vision cascade uses a different function, cited bypass is fallback-only, a bigger instance was missed; dual-TUI: wrong date, mischaracterized the guard test) | 0 |
| C5 vision-code-alignment | 4 | 3 | 0 | **1 (memorykernel-shadow-only: MemoryKernel IS in the live orchestrator dispatch path; drift runs opposite to claim)** |
| C6 doc-ssot-inversion | 5 | 5 | 0 | 0 |
| C7 generated-state-in-git | 4 | 4 | 0 (one "daily peak 52" stat is fabricated; the fix-verification itself is sound) | 0 |
| C8 ops-tooling-sprawl | 5 | 4 | 1 (makefile-drift: `make help` covers ~63 of 94 targets, not ~15; the drift is real but 4× less severe than stated) | 0 |
| C9 track-portfolio-governance | 3 | 3 | 0 (vps-duplication had a misattributed commit hash; duplication independently confirmed) | 0 |

**What is solidly confirmed:** the dead skill pipeline (C1), all five false-success emitters (C2), the mismatch-map's no-op guard + live self-contradiction + resolve-reopen cycles (C3), the DharmaGraph scope-gap + god-files-hide-duplication (C4), the R_V-proxy laundering + Organism/StrangeLoop dormancy (C5), every C6 instruction-drift finding, the docops-cascade-closed verification (C7), the a2a one-off sprawl + dead ruff gate + unsafe reports-cleanup + orphaned scripts (C8), and the track resurrection + shallow closure gates (C9).

**What is disputed / must be qualified:**
- **C4's headline "two divergent ReAct engines" is WEAKENED, not rejected** — the duplication is real and the fix direction sound, but ~a third of the specific evidence (tool-set counts, bash exclusivity, "every Orchestrator dispatch," two-gate-batteries framing) is wrong. The precise defect is *unequal gate invocation scope of the same gate class* and divergent tool registries, not two whole gate systems. `AgentOrchestrator` is only instantiated in tests, not production.
- **C4's ThinkodynamicDirector fourth-tail and dual-TUI findings are WEAKENED** — both mischaracterize specifics (the vision cascade calls `invoke_claude_vision`, not `_run_raw_backend_prompt`; the cited council bypass is a fallback; the TUI guard test is a repo-wide raw-getenv scan, not a two-file parity check). The underlying "direct-CLI escape hatches + stale-but-live legacy fallback" observations survive, and verification found an *additional, larger* bypass (`execute_pending_tasks`/`spawn_agent`) the finding missed.

**What is REJECTED and must not be carried as confirmed:** C5's `memorykernel-canonical-front-door-is-read-only-shadow`. Its proposed "reword to shadow-only" fix would make CLAUDE.md *less* accurate. MemoryKernel already runs in live dispatch (default_context.py + orchestrator_context.py, wired in orchestrator.py, commits dated 2026-07-03/06). The genuine issue there is a code-vs-intent-doc drift (M3E boundary), a distinct and already-known concern.

**Still uncertain:** the true count of persona-source call sites (C1 found "more than 4"); whether the tests/ satellite-file sprawl (845 vs 813 files) is intentional pattern or debt (scouts found it's co-development, not orphaning); whether `reports/agentops/work_packets` (213 files) is still being written to.

---

## 11. Appendices

**A. Command-log highlights (representative, from scouts + verifiers):** `wc -l` on god-files (5255/3632/3402/3385/3284/3210); `grep -n "skills\|SkillRegistry" dharma_swarm/agent_runner.py` → 0; `AgentRole('builder')` → ValueError (live shell); `git show c28951d`/`git merge-base --is-ancestor c28951d dbbc4588` (resurrection proof); `git log --all --grep 'fix(docops)'` → 100; `render_active_track_includes.py --check` → exit 0 (no live divergence); repo-wide grep `api.graphql.schema` → 0 code importers; `python3 scripts/governance/check_track_status.py` (7 grandfathered closures pass silently).

**B. Subagent roster — all nine deep-dive clusters:**
- **C1** `agent-system-prompt-identity-fragmentation` — dead skill pipeline, 4+ persona registries
- **C2** `false-success-fabricated-signal` — un-provenanced scalars across receipt boundaries
- **C3** `interface-mismatch-map-metatracking-rot` — the #1-failure tracker is unreliable
- **C4** `orchestration-execution-fragmentation` — two ReAct engines, unowned
- **C5** `vision-code-alignment-living-organs-rv` — dormant organs, metaphorical R_V (1 sub-finding rejected)
- **C6** `doc-ssot-inversion-and-instruction-drift` — 3× duplicated block, drifted per-agent files
- **C7** `generated-state-in-git-churn` — docops cascade (now closed) + stray governance commits
- **C8** `ops-tooling-sprawl-governance-scripts` — one-off incident scripts, dead lint gate
- **C9** `track-portfolio-governance-integrity` — shared unlocked YAML, no merge invariant

Plus 16 scout-wave cartography + history-mining agents (cartography: toplevel, core-abstractions, vision-docs, tests, config-ci-scripts, todo-hack-deprecated, duplication-overlap, agent-prompt-infra, governance-reports-sprawl; history: churn-and-god-modules, commit-message-mining, track-portfolio-churn, interface-mismatch-lifecycle, test-chasing-implementation; agent-confusion: instructions-and-onboarding).

**C. Evidence summary:** ~110 distinct file:line citations and ~40 commit hashes across the nine clusters, each cluster independently fresh-context-verified finding-by-finding. Of ~41 total deep-dive findings: **35 CONFIRMED, 5 WEAKENED, 1 REJECTED**. The single rejection (C5 MemoryKernel) and the five weakenings (three in C4, one each in C1/C8) are reflected honestly above and must not be re-promoted to confirmed in any downstream use of this report.