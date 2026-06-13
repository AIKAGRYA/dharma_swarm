# Interface Mismatch Map — dharma_swarm

**Last X-Ray:** 2026-05-20 (verified against current HEAD on main)
**Previous version:** 2026-05-04 (provenance-completion audit against `74d015c`)
**Maintainer:** Guardian Crew (`guardian_crew.py`) — auto-updates every 4 hours
**How to read this:** Severity = BLOCKER (crashes at runtime), DEGRADED (silent failure / wrong behavior), WARNING (structural smell).
**Status:** All BLOCKERs resolved. 3 items remain (NEW-05 GUARDED, NEW-07/08 PARTIAL+) — actively monitored, not stale.

---

## What Changed Since Last Audit

| Mismatch | Old Status | New Status | Resolution |
|----------|-----------|-----------|-----------|
| MM-01: huggingface_hub ImportError | BLOCKER | ✅ RESOLVED | `try/except ImportError` added; heuristic fallback path confirmed |
| MM-02/03: PersistentAgent enum coercion | BLOCKER | ✅ RESOLVED | `orchestrate_live.py:1363` wraps with `AgentRole()` and `PT()`. Conductor path uses enum values from config. |
| MM-04: AgentPool None guard | DEGRADED | ✅ RESOLVED | `SubsystemNotReady` raised at line 870, `_agent_pool` guard present |
| MM-06: Dual StigmergyStore | DEGRADED | ✅ RESOLVED | `run_living_layers_loop` now accepts `stigmergy_store` param; passes swarm's store |
| MM-08: ECC_INSTINCT_SIGNAL constant | DEGRADED | ✅ RESOLVED | `SIGNAL_ECC_INSTINCT` defined in `signal_bus.py:40`, used in `instinct_bridge.py` |
| MM-09: samvara.current_power None chain | DEGRADED | ✅ RESOLVED | Double guard present at `swarm.py:2182-2184` |
| MM-10: AutoProposer stigmergy guard | DEGRADED | ✅ RESOLVED | `auto_proposer.py:297` has `if self._stigmergy is None: return` |
| MM-11: WitnessAuditor ModelRouter provider | DEGRADED | ✅ RESOLVED | `swarm.py:456-457` now uses `OpenRouterFreeProvider()` |
| MM-07: MetaEvolutionEngine cadence mismatch | DEGRADED | ✅ RESOLVED | `run_evolution_loop()` now feeds `observe_cycle_result()` at most once per outer cycle, preferring real `auto_evolve()` results over synthetic observed-fitness estimates. |
| NEW-01: archaeology_ingestion palace.query | BLOCKER | ✅ FIXED THIS SESSION | Replaced with `palace.recall(PalaceQuery(...))` + correct `max_results=` |
| NEW-02: dgm_loop _provider attr | DEGRADED | ✅ FIXED THIS SESSION | Removed nonexistent `hasattr(engine, '_provider')` check |

| MM-17: gnani → TaskBoard.get_by_title | DEGRADED | ✅RESOLVED | `TaskBoard.get_by_title()` added — SQL WHERE on title column |
| MM-18: gnani → TelosGraph.get_by_name | DEGRADED | ✅RESOLVED | `TelosGraph.get_by_name()` added — linear scan on name field |
| NEW-04: agent_runner → telic_seam dispatch gap | DEGRADED | ✅RESOLVED | `record_dispatch` + `record_gate_decision` added at task start in agent_runner |
| NEW-05: task_board ↔ runtime_state split lifecycle | — | ⚠️ GUARDED | `run_task_consistency_guard` added to guardian_crew — detects COMPLETED tasks with still-OPEN claims |
| NEW-07: 54 stores lack common trace_id | — | ⚠️ PARTIAL+ | `trace_id` column added to task_board, runtime_state, telemetry_plane, stigmergy, traces, artifact_manifest, handoff. CorrelationContext auto-populates memory_palace.ingest(), economic_engine transactions, and ai_reciprocity_ledger entries. |
| NEW-08: 12 independent record_outcome() | ⚠️ PARTIAL | ⚠️ PARTIAL+ | TelicSeam emits signals + SignalBus subscriber pattern added for automatic fanout |
| NEW-09: orchestrator → TelicSeam registry_path kwarg | — | ✅ FIXED | `TelicSeam.__init__()` now accepts `registry_path=` as an alias for `path=`, and uses the same path for lineage persistence. |
| NEW-10: lineage edges lack delegation chain | — | ✅ FIXED | `LineageEdge.delegated_by` + `trace_id` fields added; `agent_runner.spawn_worker` records delegation lineage |
| NEW-11: TelicSeam singleton missing signal_bus | — | ✅ FIXED | `get_seam()` now passes `signal_bus=SignalBus.get()` to singleton |
| BR-007: runtime.db path drift + store split | BLOCKER | ✅ RESOLVED | `_record_memory_fact()` now writes `state/runtime.db`; `engine/store_sync.py` materializes ontology Outcomes into runtime ArtifactRecords; cron + room-health guards wired. |
| BR-008: VentureCell room/ontology split | BLOCKER | ✅ RESOLVED | `fractal/room_bridge.py` uses deterministic room IDs for ontology objects, updates through `put_object()`, preserves `room_status`, and room-health persists ontology sync. |
| NEW-12: cross-lane test↔module drift broke suite collection | BLOCKER | ⚠️ GUARDED (2026-06-12) | `tests/test_a2a_readiness_gate.py` (untracked) imports `operator_core.a2a_task_lifecycle` and `tests/test_autonomous_agent.py` (modified) imports `_resolve_agent_model_override` — both exist only on the holon/spine-v1 lane (`946e876e9`/`6b9b51e1b`), not this branch. Collection of the entire suite hard-failed. Guarded with `pytest.importorskip`/`skipif` so they activate when the lane lands. |
| NEW-13: cli_wake mutates shared PRESET_AGENTS | DEGRADED | ✅ FIXED (2026-06-12) | `cli_wake(model=...)` set `identity.model` directly on the shared preset object, corrupting every later wake of that preset in-process (runtime-proven: reviewer preset became `model="gemini"`). Now copies via `dataclasses.replace`. |
| NEW-14: world-model loop ↔ WorldModelAgent total API mismatch | BLOCKER (loop dead) | 🔴 OPEN | `orchestrate_live.py:1657` calls `WorldModelAgent(state_dir=...)` / `.initialize()` / `.run_cycle()`; `world_model.py:265` actually takes `(store, search_tool, arxiv_tool)` with `.boot()` / `.run_loop()`. Runtime-proven 2026-06-12 02:07 swarm.log: `TypeError: unexpected keyword argument 'state_dir'` → 5 restarts → "exceeded max restarts, abandoning" on every daemon boot. Fix needs a tool-injection decision (which search/arxiv tools to wire) — left to the loop owner. Abandoned loops are now visible via `dgc status` "Daemon loops" line (loop_liveness.json projection). |
| NEW-15: F821 sweep — 17 undefined names, all fixed | DEGRADED (silent failures) | ✅ FIXED (2026-06-12) | All 16 `dharma_swarm/` F821s + 1 in `scripts/` fixed and runtime-verified. Notable: `archaeology_ingestion.py` missing `PalaceQuery` import meant ALL 5 lessons-learned palace queries silently failed since NEW-01 (anti-amnesia dead); `orchestrate_live.py` `_evo_allowed` was used 38 lines before its definition (meta-evolution feed NameError'd every cycle, swallowed); `orchestrator.py:2567` `agent_name` → catalytic graph never recorded completion edges; `semantic.py` `_DEFAULT_GRAPH_PATH` lost in the dgc_cli extraction (8a5a8cd52, restored from d7af817ac); `verify_holon_harness_prod.py` called unaliased `holon_wake_cycle`. Guard: `make lint-blockers` (F821, blocking) wired into `make verifier-selfcheck` and `agent-build-preflight`. |

**Net change:** 12 resolved, 5 fixed prior sessions, 6 new entries (NEW-05 guarded, NEW-07/NEW-08 partially resolved, NEW-09/10/11 fixed), plus BR-007/BR-008 closure notes from PR #187. 0 open BLOCKERs, 1 structural degraded remains (message_bus semantics).

---

## Current Live Mismatches

### MM-02/03 — RESOLVED: PersistentAgent enum deserialization

**File:** `orchestrate_live.py:1361-1366`
**Status:** ✅ RESOLVED — replication path wraps with `AgentRole()` and `PT()` at line 1363-1365. Conductor path at line 1471 uses already-constructed enum values from `CONDUCTOR_CONFIGS` (`AgentRole.CONDUCTOR`).

---

### MM-05 — RESOLVED: Private Orchestrator method coupling

**File:** `orchestrator.py:730`, `swarm.py:1978`
**Status:** ✅ RESOLVED — `Orchestrator.retry_policy_for_failure(task, error, source, meta)` added as public API. `swarm.py` now calls this single method instead of 3 private methods. Internal refactors of orchestrator retry logic won't break swarm.py.

---

### MM-07 — RESOLVED: MetaEvolutionEngine cadence mismatch

**File:** `orchestrate_live.py`
**Status:** ✅ RESOLVED — `run_evolution_loop()` now stores a single per-cycle meta input and calls `observe_cycle_result()` once after the auto-evolve branch. Real `auto_evolve()` output wins when present; synthetic observed-fitness output is only the fallback. Additionally guarded: synthetic result only fires on non-auto_evolve cycles.

---

### MM-12 — RESOLVED: Same as MM-02/03 (second call site)

**File:** `orchestrate_live.py:1471` (conductor configs path)
**Status:** ✅ RESOLVED — uses `AgentRole.CONDUCTOR` from `CONDUCTOR_CONFIGS`. No bare string coercion.

---

## New Module Contracts (Added This Sprint)

These contracts must be maintained by any future changes:

| Module | Class | Method | Signature | Notes |
|--------|-------|--------|-----------|-------|
| `memory_palace.py` | `MemoryPalace` | `recall(query)` | `query: PalaceQuery` → `PalaceResponse` | Use `PalaceQuery(text=..., max_results=...)` NOT `query()` |
| `memory_palace.py` | `MemoryPalace` | `ingest(content, source, *, layer, tags, metadata)` | Returns `str` doc_id | All keyword-only after `source` |
| `memory_palace.py` | `PalaceQuery` | `__init__` | `text: str, max_results: int = 10` | NOT `top_k=` |
| `memory_palace.py` | `PalaceResult` | attrs | `.content`, `.source`, `.score`, `.layer` | NOT `.relevance_score` |
| `evolution.py` | `DarwinEngine` | `auto_evolve(provider, source_files, shadow, timeout, context)` | `provider` is required | No `_provider` instance attr |
| `archaeology_ingestion.py` | `ArchaeologyIngestionDaemon` | `run_once()` | async, returns `dict[str, int]` | |
| `dgm_loop.py` | `DGMLoop` | `run_one_generation(source_file, fitness_context, timeout)` | Returns `DGMResult` | |
| `world_actions.py` | `WorldActionResult` | `to_json()` | Returns JSON string | |
| `gnani_lodestone.py` | `GnaniLodestone` | `seed_all()` | async, returns `dict[str, int]` | idempotent |
| `guardian_crew.py` | `GuardianFinding` | attrs | `.severity`, `.check`, `.title`, `.detail`, `.file`, `.line`, `.fix_hint` | |

---

## Cross-Repo Tool Contracts (not guardian-cycled — maintained by hand)

### IMM-26 — MITIGATED: dkeys ↔ api_keys.py key-name contract

**Caller:** `~/.dharma/bin/dkeys` (`cmd_add`, `PROVIDERS[*].env`) — vendor-habit names
**Callee:** `dharma_swarm/api_keys.py` (canonical runtime names, the only sanctioned key reader)
**Mismatch:** the same physical key has two legitimate env names — `GEMINI_API_KEY` (dkeys/vendor) vs `GOOGLE_AI_API_KEY` (api_keys.py:26 canonical), and `NVIDIA_API_KEY` (dkeys/vendor, api_keys.py:32) vs `NVIDIA_NIM_API_KEY` (api_keys.py:19, used by `PROVIDER_API_KEY_ENV_KEYS["nvidia_nim"]`). A key added under one name was invisible to the other side ("replayed dozens of times" per operator; acute failure 2026-06-06). Old `dkeys add` also wrote non-export `VAR=value` lines and its `^VAR=` regex missed existing `export VAR=` lines, appending duplicates.
**Mitigation (2026-06-11, system-evolution change 25):** `dkeys add` now (a) always upserts `export VAR=value` (normalizing legacy non-export lines in place), and (b) auto-writes both names of each alias pair via `ALIAS_PAIRS` in `~/.dharma/bin/dkeys`. Verified by sandboxed-HOME tests: pair-write, legacy-line normalization, idempotent re-add, mode 600 preserved.
**Residual risk:** the contract is duplicated knowledge — `ALIAS_PAIRS` (dkeys) must stay in sync with canonical names in `api_keys.py`. New provider with a vendor-name/runtime-name split ⇒ add the pair to `ALIAS_PAIRS` AND update this entry. Fully resolving would mean api_keys.py accepting fallback aliases (e.g. `GEMINI_API_KEY` for `GOOGLE_AI_API_KEY`); deliberately not done here to keep one canonical reader.
**Status:** ⚠️ MITIGATED (tool-side). Flip to RESOLVED only if api_keys.py grows alias fallback or the vendor names are retired.

---

## The Guardian Crew (Future-Proofing)

The old approach was: audit manually every few days, miss things, fix them under fire.

The new approach: `guardian_crew.py` runs as a 15th concurrent loop in `orchestrate_live`.

**Three agents, one cycle (every 4 hours):**

```
AUDITOR        — Scans all .py files for syntax errors
               — Checks method existence for all contracts in _METHOD_EXISTENCE_CHECKS
               — Verifies import chains for all critical modules
               — O(n) scan, no imports executed, safe to run always

LOOP_WATCHER   — Checks that evolution archive, stigmergy, telos, gnani are alive
               — Measures freshness (stale > 24h = DEGRADED)
               — Checks evolution archive for zero applied entries (shadow mode stuck)
               — Reads circuit_breakers.json for open breakers

ROUTER_PROBE   — Reads circuit_breakers.json for open providers
               — Scans last 1000 log lines for repeated provider error patterns
               — Checks env vars for missing API keys
```

**Output:**
- `~/.dharma/guardian/GUARDIAN_REPORT.md` — full report, overwritten each cycle
- `GUARDIAN_REPORT.md` in repo root — version-controlled visibility
- GitHub issues for BLOCKER findings (deduped via `issues_created.json`)

**How to add a new check:** Add one `async def run_*_check()` function, one line in the relevant `run_auditor/run_loop_watcher/run_router_probe` function, one entry in `_METHOD_EXISTENCE_CHECKS` or `_IMPORT_CHECKS`. The report synthesizer handles everything else.

**How to extend the contract registry:**
```python
# Add to _METHOD_EXISTENCE_CHECKS in guardian_crew.py:
("dharma_swarm.your_new_module", "YourClass", "your_method", "BLOCKER"),

# Add to _IMPORT_CHECKS:
("dharma_swarm.your_new_module", "BLOCKER"),
```

---

## Module Pair Status (Refreshed)

| # | Module Pair | Status |
|---|-------------|--------|
| 1 | `orchestrate_live` → `swarm.SwarmManager` | ✅ |
| 2 | `swarm` → `orchestrator.Orchestrator` (public API) | ✅ |
| 3 | `swarm` → `orchestrator.retry_policy_for_failure` (public) | ✅ |
| 4 | `swarm` → `agent_runner.AgentPool` | ✅ |
| 5 | `swarm` → `evolution.DarwinEngine` | ✅ |
| 6 | `swarm` → `meta_evolution.MetaEvolutionEngine` | ✅ |
| 7 | `swarm` → `auto_proposer.AutoProposer` (stigmergy) | ✅ |
| 8 | `swarm` → `organism.OrganismRuntime.samvara` | ✅ |
| 9 | `swarm` → `witness.WitnessAuditor` | ✅ |
| 10 | `swarm` → `stigmergy.StigmergyStore` | ✅ |
| 11 | `orchestrate_live` → `persistent_agent.PersistentAgent` (replication) | ✅ |
| 12 | `orchestrate_live` → `message_bus.receive()` semantics | ⚠️ DEGRADED |
| 13 | `orchestrate_live` → `meta_evolution.observe_cycle_result` cadence | ✅ |
| 14 | `orchestrate_live` → `living_layers` (dual StigmergyStore) | ✅ |
| 15 | `archaeology_ingestion` → `memory_palace.recall()` | ✅ (fixed this session) |
| 16 | `dgm_loop` → `evolution.DarwinEngine.auto_evolve()` | ✅ (fixed this session) |
| 17 | `gnani_lodestone` → `task_board.get_by_title()` | ✅ (method added this session) |
| 18 | `gnani_lodestone` → `telos_graph.get_by_name()` | ✅ (method added this session) |
| 21 | `agent_runner` → `telic_seam.record_dispatch()` (provenance) | ✅ (dispatch+gate wired this session) |
| 22 | `task_board` ↔ `runtime_state` (lifecycle consistency) | ⚠️ GUARDED (NEW-05) |
| 23 | `telic_seam` → `signal_bus` (outcome fanout) | ✅ (NEW-08: SIGNAL_OUTCOME_RECORDED emitted) |
| 24 | `task_board` / `runtime_state` / `telemetry_plane` (trace_id) | ⚠️ PARTIAL (NEW-07) |
| 19 | `guardian_crew` → `world_actions.github_create_issue()` | ✅ |
| 20 | `orchestrate_live` → `guardian_crew.start_guardian_loop()` | ✅ |

---

*This document is maintained by the Guardian Crew. Do not edit the "Current Live Mismatches" section manually — it will be overwritten on the next guardian cycle. Add new contracts to `guardian_crew.py:_METHOD_EXISTENCE_CHECKS` to ensure they are continuously monitored.*
