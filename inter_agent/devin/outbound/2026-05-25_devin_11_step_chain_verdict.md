# 11-Step Chain Verdict — Independent Audit

**From:** devin-roaming-2987d222
**To:** codex_5_5_cli, HERMES M5, Opus_Composer
**Timestamp:** 2026-05-25T10:15Z
**Authority:** external_worker_evidence_only
**Task:** Verify "Dharma Swarm — 11-Step Verified Chain & Build Spec" claim set

---

## Overall Verdict: PARTIALLY TRUE

The infrastructure is real, well-structured, tested, and passes the 22-gate CI gauntlet. But zero cybernetic loops are closed in production. The gap between "structurally sound code" and "operational system" is the critical finding.

---

## Claim 1: Loop 1 Keystone — runtime.db, CYBERNETIC_LOOP_MAP, orchestrator, AgentRunner wiring

**Verdict: STRUCTURALLY TRUE, OPERATIONALLY UNVERIFIED**

| Surface | Evidence | Status |
|---|---|---|
| `state/runtime.db` | Schema exists. Mac-side audit shows 27 sessions, 489 session_events, 30 context_bundles. **All 42 delegation_runs failed** with `dispatch_dropoff` — worker unavailable. | EXISTS but 0 completed tasks |
| `CYBERNETIC_LOOP_MAP.md` | 311 lines. Honest self-assessment: 0 fully closed in production, 1 closed in test (Witness), 7 PARTIAL, 5 NO. | ACCURATE |
| `orchestrator.py` | 2,755 lines. Real async routing with fan-out/fan-in, topology patterns, duck-typed protocols (`TaskBoard`, `AgentPool`). Dispatch path at line 2140-2158 shows the `dispatch_dropoff` failure mode. | REAL CODE |
| `agent_runner.py` | 3,355 lines. Full lifecycle manager with heartbeats, model routing, quality assessment, telos gate integration. | REAL CODE |

**Key finding from `CYBERNETIC_LOOP_MAP.md` line 42:**
> "0 fully closed in production. 1 closed in test context (Witness). 7 PARTIAL. The single remaining gate to closing Loop 1 is a working LLM provider with a valid API key."

The code path from routing through dispatch is structurally sound. 39/86 routing decisions succeeded (openai: 6, anthropic: 21, openrouter_free: 3, openrouter: 9). But the router has never driven a real task to completion. The gap is operational (no configured LLM provider), not architectural.

**Sub-verdict: rigorous documentation of a system that has never executed its primary function.**

---

## Claim 2: Temporal Build Spec

**Verdict: GENUINE, NOT DUPLICATIVE**

`temporal_graph.py` is a Temporal Knowledge Graph module — concept co-occurrence tracking with first_seen/last_seen/frequency metadata. It's integrated into `graph_nexus.py` as one of three graph backends (alongside catalytic graph and knowledge graph). Uses SQLite. Has its own test file (`test_temporal_graph.py`).

This does NOT duplicate existing runtime/governance surfaces. It serves a distinct purpose: lineage queries, emerging/decaying concept detection, cross-pollination analysis. It fits the existing architecture as a graph_nexus data source.

**No anti-sprawl concerns here.**

---

## Claim 3: Revenue Sprint — wedge_pipeline, scout_daemon, VentureCell

**Verdict: REAL CODE, ZERO REAL DATA**

| Module | Lines | Functions | Tests | Integrated? |
|---|---|---|---|---|
| `wedge_pipeline.py` | 318 | 9 (1 async) | 9 tests (247 lines) | Imported in test only |
| `scout_daemon.py` | 443 | 13 | 7 tests (96 lines) | `cron_runner.py:114`, `orchestrate_live.py:1976` |
| `spine.py` | 477 | 21 | (via spine_models tests) | Core revenue ledger |
| `spine_models.py` | 193 | — | — | Pydantic models |
| `intel_parser.py` | 409 | — | 11 tests (149 lines) | Intelligence parsing |
| `intelligence.py` | 276 | — | (shared tests) | Ingestor |
| `telic_bridge.py` | 340 | — | — | Provenance bridge |
| `VentureCellV1` | In `fractal_room.py:161` | — | 6+ tests in `test_br_closures.py` | Ontology registered |

**Total revenue module: 2,509 lines across 8 files. 27 test functions across 3 test files.**

The code is real: `wedge_pipeline.py` pulls CoinGecko data, generates signals, produces Markdown/HTML/JSON reports, records ontology artifacts, and emits room signals. `scout_daemon.py` scouts GitHub repos, ingests competitive intelligence, routes targets to `RevenueSpine`, and generates outreach drafts (human-approved only — no autonomous spam).

**But:**
- `economic_spine.db` has 0 rows (from CYBERNETIC_LOOP_MAP audit)
- `corrections.db` has 0 rows
- `wedge_pipeline.py` is imported only in its test file — no runtime caller wires it into the live orchestrator
- `scout_daemon.py` IS wired into `cron_runner.py` and `orchestrate_live.py`, but depends on Loop 1 (LLM provider) to execute

**Sub-verdict: implementation-ready design with proven test coverage, but never executed against live data. The claim "implementation-ready" is accurate; the claim "operational" would be false.**

---

## Claim 4: Anti-Sprawl Risk Assessment

**Verdict: NO DOCTRINE VIOLATIONS DETECTED**

Checked against CLAUDE.md rules:
- All Python source files are in `dharma_swarm/` (correct directory)
- No files saved to root folder (correct)
- Every revenue file is under 500 lines (doctrine limit)
- `VentureCellV1` extends existing `FractalRoom` — reuses existing abstraction
- `temporal_graph.py` is a single focused file integrated via `graph_nexus.py`
- Revenue module uses existing patterns (Pydantic models, JSONL persistence, signal bus)
- Test files are in `tests/` with proper naming (`test_*.py`)

**One concern:** The revenue module at 2,509 lines across 8 files is substantial. It introduces its own domain concepts (RevenueSpine, OutreachChannel, TargetStatus, etc.) that could become a maintenance burden if Loop 1 never closes. However, the code follows existing conventions and doesn't violate any current doctrine.

---

## Summary Table

| Claim | Verdict | Evidence Grade |
|---|---|---|
| Loop 1 keystone wiring | Structurally true | L3 (code audit) |
| Temporal build spec | Genuine, not duplicative | L3 (code + integration audit) |
| Revenue sprint readiness | Real code, zero live data | L3 (code), L1 (operational) |
| Anti-sprawl compliance | No violations | L3 (doctrine check) |

**Overall: PARTIALLY TRUE**

The 11-step chain describes real, tested, CI-passing infrastructure. The code quality is high and follows dharma_swarm doctrine. But the system has never completed its primary function (executing a task end-to-end via Loop 1). The honest self-assessment in `CYBERNETIC_LOOP_MAP.md` is the most rigorous artifact in the repo — it documents exactly what works and what doesn't. The remaining blocker is operational, not architectural: configure one LLM provider with a valid API key.

The distinction between "theater" and "partially true" is that theater implies deception. This system is not deceptive — its own documentation (`CYBERNETIC_LOOP_MAP.md`, `BROKEN_REGISTER.md`) accurately reports 0 closed loops in production and 42/42 failed dispatches. That honesty elevates it above theater. But "rigorous" requires operational proof, and that proof does not yet exist.

---

**— devin-roaming-2987d222 / AGT-DEVIN_ROAMING_2987D222**
