# Interface Mismatch Map - dharma_swarm

**Last X-Ray:** 2026-05-04 (Repo Reality Gauntlet audit against HEAD `3919207`)
**Previous version:** 2026-04-08 (55 module pairs, 13 mismatches, 9 prioritized)
**Maintainer:** Guardian Crew (`guardian_crew.py`) - auto-updates every 4 hours
**How to read this:** Severity = BLOCKER (crashes at runtime), DEGRADED (silent failure / wrong behavior), WARNING (structural smell).

---

## What Changed Since Last Audit

| Mismatch | Old Status | New Status | Resolution |
|----------|------------|------------|------------|
| MM-01: huggingface_hub ImportError | BLOCKER | RESOLVED | `try/except ImportError` added; heuristic fallback path confirmed |
| MM-02/03: PersistentAgent enum coercion | BLOCKER | RESOLVED | `orchestrate_live.py:1363` now wraps in `AgentRole()` / `PT()`; verified 2026-05-04 |
| MM-04: AgentPool None guard | DEGRADED | RESOLVED | `SubsystemNotReady` raised at line 870, `_agent_pool` guard present |
| MM-06: Dual StigmergyStore | DEGRADED | RESOLVED | `run_living_layers_loop` now accepts `stigmergy_store` param; passes swarm's store |
| MM-08: ECC_INSTINCT_SIGNAL constant | DEGRADED | RESOLVED | `SIGNAL_ECC_INSTINCT` defined in `signal_bus.py:40`, used in `instinct_bridge.py` |
| MM-09: samvara.current_power None chain | DEGRADED | RESOLVED | Double guard present at `swarm.py:2182-2184` |
| MM-10: AutoProposer stigmergy guard | DEGRADED | RESOLVED | `auto_proposer.py:297` has `if self._stigmergy is None: return` |
| MM-11: WitnessAuditor ModelRouter provider | DEGRADED | RESOLVED | `swarm.py:456-457` now uses `OpenRouterFreeProvider()` |
| NEW-01: archaeology_ingestion palace.query | BLOCKER | RESOLVED | Replaced with `palace.recall(PalaceQuery(...))` plus correct `max_results=` |
| NEW-02: dgm_loop _provider attr | DEGRADED | RESOLVED | Removed nonexistent `hasattr(engine, '_provider')` check |
| NEW-03: TelicSeam constructor kwarg | BLOCKER | RESOLVED | `orchestrator.py` passed `registry_path=` but `TelicSeam.__init__` expects `path=` |
| MM-13: message_bus.receive semantics | DEGRADED | OPEN | `orchestrate_live` to `message_bus.receive()` semantics unclear |

**Net change:** 9 resolved, 2 new fixed, 0 open BLOCKERs, 3 structural DEGRADED items remain in this rollup branch.

---

## Current Live Mismatches

### MM-02/03 - RESOLVED: PersistentAgent enum deserialization

**File:** `orchestrate_live.py:1361-1366`
**Status:** Fixed. Both call sites now wrap bare strings in `AgentRole()` / `PT()`.
**Verified:** 2026-05-04 by grep and code inspection.
**Pinning test:** `tests/test_mismatch_blockers.py::test_mm02_persistent_agent_enum`

```python
from dharma_swarm.models import AgentRole, ProviderType as PT
child = PersistentAgent(
    role=AgentRole(outcome.child_spec.get("role", "general")),
    provider_type=PT(outcome.child_spec.get("default_provider", "openrouter_free")),
)
```

---

### MM-05 - DEGRADED: Private Orchestrator method coupling

**File:** `swarm.py:1883-1895`
**What is wrong:** `swarm.py` calls `self._orchestrator._classify_failure()`, `_resolve_retry_policy()`, and `_apply_failure_retry_defaults()`. All are single-underscore private methods. Any internal refactor of `orchestrator.py` can silently break `swarm.py` retry logic.

**Fix:** Add `Orchestrator.retry_policy_for_failure(task, error, source, meta)` as a public API method.

---

### MM-07 - DEGRADED: MetaEvolutionEngine cadence mismatch

**File:** `orchestrate_live.py:399,407`
**What is wrong:** `observe_cycle_result()` is called twice per cycle number: once with synthetic fitness and once with the `auto_evolve` result. With `n_object_cycles_per_meta=2`, meta-adaptation can trigger within one evolution cycle instead of after two separate cycles.

**Fix:** Call `observe_cycle_result` once per cycle, using the actual `CycleResult` from `auto_evolve`.

---

### MM-13 - DEGRADED: message_bus.receive semantics

**File:** `orchestrate_live.py`
**What is wrong:** `message_bus.receive()` semantics remain unclear across the orchestrator boundary. The risk is silent visibility loss when a caller expects lifecycle events to stay visible after read status changes.

**Fix:** Pin the intended lifecycle-event consumption contract and use a single idempotent event-consumption API on the orchestration path.

---

### MM-12 - RESOLVED: Second PersistentAgent call site

**File:** `orchestrate_live.py:1471` (conductor configs path)
**Status:** This path uses already-constructed enum values. The replication path is also fixed.

---

## New Module Contracts

These contracts must be maintained by future changes:

| Module | Class | Method | Signature | Notes |
|--------|-------|--------|-----------|-------|
| `memory_palace.py` | `MemoryPalace` | `recall(query)` | `query: PalaceQuery` to `PalaceResponse` | Use `PalaceQuery(text=..., max_results=...)`, not `query()` |
| `memory_palace.py` | `MemoryPalace` | `ingest(content, source, *, layer, tags, metadata)` | Returns `str` doc_id | All keyword-only after `source` |
| `memory_palace.py` | `PalaceQuery` | `__init__` | `text: str, max_results: int = 10` | Not `top_k=` |
| `memory_palace.py` | `PalaceResult` | attrs | `.content`, `.source`, `.score`, `.layer` | Not `.relevance_score` |
| `evolution.py` | `DarwinEngine` | `auto_evolve(provider, source_files, shadow, timeout, context)` | `provider` is required | No `_provider` instance attr |
| `archaeology_ingestion.py` | `ArchaeologyIngestionDaemon` | `run_once()` | async, returns `dict[str, int]` | |
| `dgm_loop.py` | `DGMLoop` | `run_one_generation(source_file, fitness_context, timeout)` | Returns `DGMResult` | |
| `world_actions.py` | `WorldActionResult` | `to_json()` | Returns JSON string | |
| `gnani_lodestone.py` | `GnaniLodestone` | `seed_all()` | async, returns `dict[str, int]` | idempotent |
| `guardian_crew.py` | `GuardianFinding` | attrs | `.severity`, `.check`, `.title`, `.detail`, `.file`, `.line`, `.fix_hint` | |

---

## Module Pair Status

| # | Module Pair | Status |
|---|-------------|--------|
| 1 | `orchestrate_live` to `swarm.SwarmManager` | OK |
| 2 | `swarm` to `orchestrator.Orchestrator` public API | OK |
| 3 | `swarm` to `orchestrator._classify_failure` private API | DEGRADED |
| 4 | `swarm` to `agent_runner.AgentPool` | OK |
| 5 | `swarm` to `evolution.DarwinEngine` | OK |
| 6 | `swarm` to `meta_evolution.MetaEvolutionEngine` | DEGRADED cadence |
| 7 | `swarm` to `auto_proposer.AutoProposer` stigmergy | OK |
| 8 | `swarm` to `organism.OrganismRuntime.samvara` | OK |
| 9 | `swarm` to `witness.WitnessAuditor` | OK |
| 10 | `swarm` to `stigmergy.StigmergyStore` | OK |
| 11 | `orchestrate_live` to `persistent_agent.PersistentAgent` replication | OK |
| 12 | `orchestrate_live` to `message_bus.receive()` semantics | DEGRADED |
| 13 | `orchestrate_live` to `meta_evolution.observe_cycle_result` cadence | DEGRADED |
| 14 | `orchestrate_live` to `living_layers` shared stigmergy | OK |
| 15 | `archaeology_ingestion` to `memory_palace.recall()` | OK |
| 16 | `dgm_loop` to `evolution.DarwinEngine.auto_evolve()` | OK |
| 19 | `guardian_crew` to `world_actions.github_create_issue()` | OK |
| 20 | `orchestrate_live` to `guardian_crew.start_guardian_loop()` | OK |

---

`docs/interface_mismatches.yaml` is the machine-readable source of truth for hooks and tests. Update both files together.
