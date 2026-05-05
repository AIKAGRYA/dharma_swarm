# Interface Mismatch Map — dharma_swarm

**Last X-Ray:** 2026-05-05 (deep consolidation scan — 509 modules, AST + import graph analysis)
**Previous version:** 2026-05-04 (provenance-wiring audit against HEAD `2fcd2cf`)
**Maintainer:** Guardian Crew (`guardian_crew.py`) — auto-updates every 4 hours
**How to read this:** Severity = BLOCKER (crashes at runtime), DEGRADED (silent failure / wrong behavior), WARNING (structural smell).

---

## What Changed Since Last Audit

| Mismatch | Old Status | New Status | Resolution |
|----------|-----------|-----------|-----------|
| MM-01: huggingface_hub ImportError | BLOCKER | ✅ RESOLVED | `try/except ImportError` added; heuristic fallback path confirmed |
| MM-02/03: PersistentAgent enum coercion | BLOCKER | ✅ RESOLVED | Both call sites now use `AgentRole()` / `PT()` enum constructors (lines 1363-1366) |
| MM-04: AgentPool None guard | DEGRADED | ✅ RESOLVED | `SubsystemNotReady` raised at line 870, `_agent_pool` guard present |
| MM-06: Dual StigmergyStore | DEGRADED | ✅ RESOLVED | `run_living_layers_loop` now accepts `stigmergy_store` param; passes swarm's store |
| MM-08: ECC_INSTINCT_SIGNAL constant | DEGRADED | ✅ RESOLVED | `SIGNAL_ECC_INSTINCT` defined in `signal_bus.py:40`, used in `instinct_bridge.py` |
| MM-09: samvara.current_power None chain | DEGRADED | ✅ RESOLVED | Double guard present at `swarm.py:2182-2184` |
| MM-10: AutoProposer stigmergy guard | DEGRADED | ✅ RESOLVED | `auto_proposer.py:297` has `if self._stigmergy is None: return` |
| MM-11: WitnessAuditor ModelRouter provider | DEGRADED | ✅ RESOLVED | `swarm.py:456-457` now uses `OpenRouterFreeProvider()` |
| NEW-01: archaeology_ingestion palace.query | BLOCKER | ✅ FIXED THIS SESSION | Replaced with `palace.recall(PalaceQuery(...))` + correct `max_results=` |
| NEW-02: dgm_loop _provider attr | DEGRADED | ✅ FIXED THIS SESSION | Removed nonexistent `hasattr(engine, '_provider')` check |

| MM-17: gnani → TaskBoard.get_by_title | DEGRADED | ✅RESOLVED | `TaskBoard.get_by_title()` added — SQL WHERE on title column |
| MM-18: gnani → TelosGraph.get_by_name | DEGRADED | ✅RESOLVED | `TelosGraph.get_by_name()` added — linear scan on name field |
| NEW-04: agent_runner → telic_seam dispatch gap | DEGRADED | ✅RESOLVED | `record_dispatch` + `record_gate_decision` added at task start in agent_runner |
| NEW-05: task_board ↔ runtime_state split lifecycle | — | ⚠️ GUARDED | `run_task_consistency_guard` added to guardian_crew — detects COMPLETED tasks with still-OPEN claims |
| NEW-07: 54 stores lack common trace_id | — | ⚠️ PARTIAL+ | `trace_id` column added to task_board, runtime_state, telemetry_plane, stigmergy, traces, artifact_manifest, handoff. CorrelationContext auto-populates memory_palace.ingest() and economic_engine transactions. |
| NEW-08: 12 independent record_outcome() | ⚠️ PARTIAL | ⚠️ PARTIAL+ | TelicSeam emits signals + SignalBus subscriber pattern added for automatic fanout |
| NEW-09: orchestrator → TelicSeam registry_path kwarg | — | ✅ FIXED | `orchestrator.py:154` used `registry_path=` but TelicSeam accepts `path=`. TypeError at runtime. |
| NEW-10: lineage edges lack delegation chain | — | ✅ FIXED | `LineageEdge.delegated_by` + `trace_id` fields added; `agent_runner.spawn_worker` records delegation lineage |
| NEW-11: TelicSeam singleton missing signal_bus | — | ✅ FIXED | `get_seam()` now passes `signal_bus=SignalBus.get()` to singleton |

**Net change:** 13 resolved, 5 fixed prior sessions, 6 new entries (NEW-05 guarded, NEW-07/NEW-08 partially resolved, NEW-09/10/11 fixed), 0 open BLOCKERs, 3 structural degraded remain.

### Consolidation Actions Completed (2026-05-05)

| Action | Status | Detail |
|--------|--------|--------|
| SessionStore merge | ✅ DONE | `tui/engine/session_store.py` → thin re-export of `operator_core/session_store.py` |
| ClaudeAdapter merge | ✅ DONE | `terminal_adapters/claude.py` confirmed dead code (broken `from .base` import, zero runtime importers); `__init__.py` deprecation marker added |
| Model routing facade | ✅ DONE | `routing_facade.py` created — single entry: `classify_and_route()`, `detect_language()`, `select_provider()` |
| dgc_cli.py decomposition | ✅ DONE | 7078→5784 LOC; extracted `cli/evolution_cmds.py`, `cli/integrations_cmds.py`, `cli/semantic_cmds.py` |
| Ginko subdirectory packaging | ✅ DONE | 17 `ginko_*` modules moved to `dharma_swarm/ginko/`; all imports updated |
| providers_extended.py cleanup | ✅ DONE | Marked deprecated with clear documentation; zero runtime imports confirmed |
| AutonomyLevel dedup | ✅ DONE (prior commit) | `profiles.py` now imports from `models.py` instead of redefining |

---

## Current Live Mismatches

### MM-02/03 — ✅ RESOLVED: PersistentAgent enum deserialization

**File:** `orchestrate_live.py:1359-1366`
**Resolution:** Both call sites now use `AgentRole(...)` and `PT(...)` enum constructors. The replication monitor path (line 1363) wraps `child_spec.get("role", "general")` in `AgentRole()`. The conductor path uses pre-constructed enum values from `CONDUCTOR_CONFIGS`.

---

### MM-05 — ✅ RESOLVED: Private Orchestrator method coupling

**File:** `orchestrator.py:730-752`, `swarm.py:1978-1985`
**Resolution:** Added `Orchestrator.retry_policy_for_failure(task, error, source, meta)` as a public API method that wraps `_classify_failure`, `_resolve_retry_policy`, and `_apply_failure_retry_defaults`. Updated `swarm.py` to call the public API instead of reaching into private methods.

---

### MM-07 — ✅ RESOLVED: MetaEvolutionEngine cadence mismatch

**File:** `orchestrate_live.py:448-634`
**Resolution:** Added `_meta_observed_this_cycle` flag. The synthetic `observe_cycle_result` call sets the flag; the `auto_evolve` path skips its call if the flag is already set. This ensures exactly one meta-observation per evolution cycle.

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

## New Mismatches Discovered (Deep Scan 2026-05-05)

### NEW-12 — WARNING: `providers_extended.py` dead duplicates

**Files:** `providers_extended.py` (223 LOC) vs `providers.py` (2,473 LOC)
**What's wrong:** `providers_extended.py` contains duplicate `OllamaProvider` and `NVIDIANIMProvider` classes that already exist in `providers.py`. The file is **never imported at runtime** — confirmed by `api_key_audit.py:141` which notes "not wired into runtime_provider.py." The unique `MoonshotProvider` class (lines 136-188) is also unreachable.

**Impact:** Low — no runtime failure. But developers may edit the wrong copy and wonder why changes have no effect.

**Metabolism decision:** Archive. Unique `MoonshotProvider` should be moved to `providers.py` if needed; the rest can be deleted.

---

### NEW-13 — STRUCTURAL: Duplicate type definitions (50+ class name collisions)

The deep scan found **50+ class names defined in multiple files**. Most are independent domains (different authority, different lifecycle) that collide by naming convention. The highest-risk collisions:

| Class | Files | Shared Methods | Metabolism Decision |
|-------|-------|---------------|-------------------|
| `SessionStore` | `operator_core/session_store.py`, `tui/engine/session_store.py` | 19 | MERGE (same authority, same lifecycle, same query surface) |
| `ClaudeAdapter` | `terminal_adapters/claude.py`, `tui/engine/adapters/claude.py` | 11 | MERGE (same authority, same failure mode) |
| `GovernanceFilter` | `operator_core/permissions.py`, `tui/engine/governance.py` | 3 | MERGE (same authority) |
| `ProviderAdapter` | `engine/adapters/base.py`, `tui/engine/adapters/base.py` | full | MERGE (identical interface) |
| `ProviderRunner` | `engine/provider_runner.py`, `tui/engine/provider_runner.py` | full | MERGE (identical interface) |
| `CycleResult` | `evolution.py`, `overnight_evaluator.py` | 1 (name only) | BRIDGE — different authority, different fields |
| `TaskStatus` | `models.py`, `economic_agent.py` | 0 | BRIDGE — `models.py` is canonical, `economic_agent.py` defines local enum |
| `AutonomyLevel` | `models.py`, `guardrails.py`, `profiles.py` | 0 | MERGE to `models.py` — 3 definitions, 0 cross-imports |
| `AgentIdentity` | `agent_registry.py`, `autonomous_agent.py` | 0 | See `AGENT_IDENTITY_UNIFICATION.md` |
| `AgentPool` | `orchestrator.py` (Protocol), `agent_runner.py` (impl) | 5 | KEEP — Protocol + Implementation is correct pattern |
| `TaskBoard` | `orchestrator.py` (Protocol), `task_board.py` (impl) | 3 | KEEP — Protocol + Implementation is correct pattern |

**Priority corridors for merge** (per MODULE_METABOLISM_STRATEGY.md §8):
1. **Session store** — `tui/engine/session_store.py` should become a thin subclass or re-export of `operator_core/session_store.py`
2. **Claude adapter** — `tui/engine/adapters/claude.py` should delegate to `terminal_adapters/claude.py`
3. **Provider base** — `tui/engine/adapters/base.py` is a copy of `engine/adapters/base.py`; one should import the other

---

### NEW-14 — WARNING: `providers.py` → `providers_extended.py` split creates dead code

**File:** `providers_extended.py`
**Status:** The entire module is dead — zero runtime imports. `api_key_audit.py` explicitly notes "not wired into runtime_provider.py."

**Fix:** Move unique `MoonshotProvider` to `providers.py`. Delete `providers_extended.py`.

---

### NEW-15 — WARNING: `hasattr(engine, '_entries')` pattern in `dgm_loop.py`

**File:** `dgm_loop.py:145,318,401,406`
**What's wrong:** Four calls to `hasattr(archive, '_entries')` — reaching into the private implementation detail of the evolution archive. If the archive changes its internal storage, these guards silently break.

**Fix:** Add a public `Archive.has_entries() -> bool` method or use `len(archive)`.

---

### NEW-16 — WARNING: `hasattr(engine, '_state_dir')` in `strange_loop.py`

**File:** `strange_loop.py:346`
**What's wrong:** Checks for a private attribute on another module's class to decide behavior.

**Fix:** Add a public property or method for state dir availability.

---

### NEW-17 — DEGRADED: Multiple `record_outcome()` signatures across modules

**Files:** 8 independent `record_outcome()` implementations with different signatures:
- `telic_seam.py:243` — `record_outcome(task, agent_id, *, success, result_summary, error, duration_ms, fitness_score)`
- `routing_memory.py:458` — `record_outcome(request_id, provider, model, *, success, latency_ms, error)`
- `fitness_predictor.py:105` — `record_outcome(features, actual_fitness)`
- `adaptive_autonomy.py:193` — `record_outcome(self, success: bool)`
- `ai_reciprocity_ledger.py:453` — `record_outcome(self, outcome: OutcomeRecord)`
- `strategy_reinforcer.py:363` — `record_outcome(...)`
- `engine/retrieval_feedback.py:306` — `record_outcome(query_id, outcome, consumer)`
- `provider_policy.py:550` — `routing_memory.record_outcome(...)`

**Impact:** Callers must know which `record_outcome` they're calling. The `operator_brief/insight_brief.py` has its own `_record_outcome` wrapper (4 call sites) that delegates to `telic_seam.record_outcome`. If a caller confuses which `record_outcome` to use, it will get a TypeError at runtime.

**Status:** Partially mitigated by NEW-08 (TelicSeam emits `SIGNAL_OUTCOME_RECORDED` for fanout). Full resolution requires a unified outcome recording facade.

---

## Corridor Analysis (Metabolism Report 2026-05-05)

Per MODULE_METABOLISM_STRATEGY.md §8, the 7 priority corridors were scanned with the metabolism report. Summary:

| Corridor | Modules | split-review | merge-review | facade | archive-review | Top Finding |
|----------|---------|-------------|-------------|--------|---------------|-------------|
| Session Store | 7 | 0 | 2 | 0 | 1 | Two `SessionStore` classes (402 + 369 LOC) — merge to `operator_core` |
| Permissions/Governance | 5 | 0 | 0 | 0 | 0 | `GovernanceFilter` duplicated in `tui/engine/governance.py` |
| Claude Adapters | 12 | 2 | 2 | 0 | 0 | `ClaudeAdapter` 11 shared methods; `runtime_adapters.py` at 1182 LOC |
| Model Routing | 7 | 0 | 0 | 3 | 0 | Three facade candidates: smart_router, router_v1, swarm_router |
| Runtime/Ontology | 9 | 2 | 2 | 0 | 0 | `runtime_state.py` (2049 LOC, 24 inbound) and `ontology.py` (1823 LOC) both split-review |
| Ginko | 17 | 4 | 3 | 0 | 1 | 4 files over 1000 LOC; `ginko_evolution.py` merge candidate with `ginko_brier.py` |
| CLI Inventory | 37 | 4 | 2 | 1 | 8 | `dgc_cli.py` at 7078 LOC (top split target); 8 tui widgets without test coverage |

**Key observations:**
- **Session store** — ✅ MERGED. `tui/engine/session_store.py` is now a thin re-export of `operator_core/session_store.py`.
- **Model routing** — ✅ FACADE. `routing_facade.py` provides `classify_and_route()`, `detect_language()`, `select_provider()` as single entry points.
- **CLI inventory** — ✅ DECOMPOSED. `dgc_cli.py` reduced from 7078→5784 LOC. 3 command groups extracted to `cli/` subpackage. 8 archive-review TUI widgets still pending.
- **Ginko** — ✅ PACKAGED. 17 modules moved from flat `dharma_swarm/ginko_*.py` to `dharma_swarm/ginko/` subdirectory. All imports updated.

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
| 3 | `swarm` → `orchestrator._classify_failure` (private) | ⚠️ DEGRADED |
| 4 | `swarm` → `agent_runner.AgentPool` | ✅ |
| 5 | `swarm` → `evolution.DarwinEngine` | ✅ |
| 6 | `swarm` → `meta_evolution.MetaEvolutionEngine` | ⚠️ DEGRADED (cadence) |
| 7 | `swarm` → `auto_proposer.AutoProposer` (stigmergy) | ✅ |
| 8 | `swarm` → `organism.OrganismRuntime.samvara` | ✅ |
| 9 | `swarm` → `witness.WitnessAuditor` | ✅ |
| 10 | `swarm` → `stigmergy.StigmergyStore` | ✅ |
| 11 | `orchestrate_live` → `persistent_agent.PersistentAgent` (replication) | ⚠️ BLOCKER |
| 12 | `orchestrate_live` → `message_bus.receive()` semantics | ⚠️ DEGRADED |
| 13 | `orchestrate_live` → `meta_evolution.observe_cycle_result` cadence | ⚠️ DEGRADED |
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
