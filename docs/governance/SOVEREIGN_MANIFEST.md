# SOVEREIGN MANIFEST: SYSTEM SOURCE OF TRUTH

**Purpose**: This document is the absolute ground truth for the dharma_swarm repository. All AI agents, regardless of model or tab, MUST ingest, comprehend, and adhere to this context before outputting a single line of code.

**Generated**: 2026-04-04 | Count refresh: 2026-05-06 filesystem verification
**Prior audit**: 2026-04-04 | 5-model convergent audit (Claude, DeepSeek, GPT-OSS, Codex, RUFLO)
**Authority**: This file + `CLAUDE.md` are the two canonical governance surfaces. When they conflict, `CLAUDE.md` wins on behavioral rules; this file wins on architectural truth.

**Verification method**: Count-sensitive claims below were refreshed against the filesystem on 2026-05-06. Architecture prose still reflects the 2026-04-04 audit unless specifically marked otherwise. Recheck counts before citing them in future work.

**Substrate-nativeness status**: The current runtime is ~10–15% ontology-native; ~85–90% of runtime work bypasses substrate. The current build track is the ontology-native Operator Brief seam ([`docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](../plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md)). Do not open additional tracks until that seam ships. See [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) for the audit that established this estimate.

---

## GLOBAL AXIOMS

These are immutable engineering laws for this repository. Violation = architectural regression.

### A1: NO FLAT-PACKAGE GROWTH
The `dharma_swarm/` package currently has **381 files at its top level (71.6% of 532 total Python modules)** (V). No new .py file may be added to the top level. New modules must go into an appropriate subdirectory. Existing top-level files will be organized over time.

### A2: NO DUPLICATE IMPLEMENTATIONS
Before creating a new file for routing, bridging, adapting, or orchestrating, check if one already exists. The repo currently has **21 bridge files** (V), **3 model_routing copies** (2 are identical, 1 is different) (V), **4 orchestrators** (V), **14 adapter files across 7 locations** (V), and **13 router files** (V). Do not add more without deprecating an existing one.

### A3: NO UNDOCUMENTED SEAMS
If your code creates a new interface between domains (a bridge, adapter, or protocol), you must update `NAVIGATION.md` with its purpose, entry point, and boundary constraints. Undocumented seams become invisible coupling.

### A4: NO VIBE-CODING
If a seam, type, protocol, state contract, or API is missing from your context, **STOP and find the exact file** before proceeding. Do not guess imports. Do not assume module locations. Do not infer API shapes from naming conventions.

### A5: NO GOD OBJECTS
No single file should exceed 3,000 lines. Current violations (V):
- `dgc_cli.py`: 6,979 lines
- `thinkodynamic_director.py`: 5,167 lines
- `telos_substrate.py`: 4,423 lines
- `evolution.py`: 3,227 lines
- `swarm.py`: 3,119 lines
- `agent_runner.py`: 3,023 lines
- `providers.py`: 2,938 lines (approaching limit)

**148 files exceed 500 lines; 39 exceed 1,000; 7 exceed 3,000** (V). These must be decomposed over time, not grown further.

### A6: DOCS DECAY -- CHECK BEFORE CITING
All numerical claims in docs become stale within weeks. Before citing module counts, test counts, or line counts from any doc (including this one), verify against the actual filesystem. See `REPO_GOVERNANCE_AUDIT.md` for the current staleness log. The current DocOps inventory reports **260 Markdown files containing at least one reserved trust-language term** (V). Treat these as authority-scope review candidates, not confirmed repo-wide authority.

### A7: NO CIRCULAR IMPORTS
The repo has **9 verified circular dependency chains** (V). The worst:
1. **6-module evolution cycle** (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) -- has direct module-level imports
2. **4-module routing cycle** (router_v1 → provider_policy → smart_router → router_v1) -- mitigated by TYPE_CHECKING
3. **api ↔ dharma_swarm bidirectional** -- api imports dharma_swarm at module level; dharma_swarm imports api lazily

All 9 cycles were independently confirmed with exact import lines. Most are mitigated by lazy imports but remain architectural debt. **New code must not create circular imports.**

### A8: FRONTMATTER DISCIPLINE
Do not inject machine-readable YAML frontmatter into governance or architecture docs unless explicitly requested. Current state: **214 of 629 Markdown files start with YAML frontmatter; 15 of 20 docs/architecture Markdown files do so** (V). Long frontmatter remains an authority/noise risk even when the prose is useful.

---

## VERIFIED NUMBERS (2026-05-06 COUNT REFRESH)

These are the ground-truth metrics. All other documents citing different numbers are stale.

| Metric | Value | Verification |
|--------|-------|-------------|
| Total Python modules | **532** | find dharma_swarm -name "*.py" -type f |
| Top-level (flat) modules | **381 (71.6%)** | find dharma_swarm -maxdepth 1 -name "*.py" -type f |
| Total Python LOC | **241,639** | wc -l across dharma_swarm Python modules |
| Test files | **535** | find tests -name "*.py" -type f |
| Test functions | **9,698 `def test_` occurrences under tests/** | rg "def test_" tests |
| Tests collected (pytest) | **Needs write-permitted refresh** | not run during this DocOps count pass |
| Collection errors | **Historical: 16 on 2026-04-04** | refresh before relying on this count |
| Markdown files | **629** | find . -name "*.md" -type f |
| Markdown total lines | **162,844** | wc -l across all .md |
| Bridge files | **17** | find dharma_swarm -name "*bridge*.py" |
| Adapter files | **14 across 7 locations** | find dharma_swarm -type f \| rg -i "adapter" |
| Orchestrator files | **4** (6,034 LOC total) | find dharma_swarm -name "*orchestrat*" |
| Router files | **13** (4,976 LOC total) | find dharma_swarm -type f \| rg -i "rout" |
| Memory modules | **11** (5,848 LOC) | find dharma_swarm -name "*memory*" |
| Context modules | **8** (5,828 LOC) | find dharma_swarm -name "*context*" |
| Provider types (enum) | **18** | models.py ProviderType enum |
| Provider classes | **19** (including LLMProvider base) | grep "class.*Provider" providers.py |
| Kernel axioms | **25** (10 original + 15 foundations) | dharma_kernel.py MetaPrinciple enum |
| Telos gates | **11** (2 Tier A, 1 Tier B, 8 Tier C) | telos_gates.py core gates |
| SQLite-using modules | **49** | grep aiosqlite/sqlite3 |
| JSONL-writing modules | **126** | grep .jsonl |
| ~/.dharma/ subdirectories | **74** | ls ~/.dharma/ |
| Circular dependency chains | **9 confirmed** | import tracing |
| Files >500 lines | **148** | wc -l + awk |
| Files >3000 lines | **7** | wc -l + awk |

---

## SYSTEM TOPOGRAPHY

### Domain 1: Schema & Configuration

- **Path**: `dharma_swarm/models.py`, `dharma_swarm/config.py`, `dharma_swarm/profiles.py`
- **Global Role**: All shared Pydantic types, enums, and configuration
- **Primary Entry Points**: `models.py` (types), `config.py` (settings), `profiles.py` (agent profiles)
- **State Management**: `config.py` reads env vars -> `DEFAULT_CONFIG` singleton
- **Volatility Level**: LOW
- **Boundary Constraints**:
  - ALLOWED: Everything may import from here
  - FORBIDDEN: These files must NOT import from any other dharma_swarm module
- **Boundary Status**: **PASS** (V) -- no violations found
- **Notes for Agents**: This is the foundation. Changes here ripple everywhere. ProviderType enum has 18 values (not 9 as some docs claim).

### Domain 2: Governance (S5 Identity + S3 Control)

- **Path**: `dharma_swarm/dharma_kernel.py`, `telos_gates.py`, `guardrails.py`, `identity.py`, `policy_compiler.py`, `agent_constitution.py`, `pramana.py`, `samvara.py`, `anekanta_gate.py`, `dogma_gate.py`, `steelman_gate.py`
- **Global Role**: Immutable axioms, safety gates, constitutional constraints, epistemology
- **Primary Entry Points**: `dharma_kernel.py` (axioms), `telos_gates.py` (gate checks)
- **State Management**: `~/.dharma/witness/` (gate check logs, JSONL append-only)
- **Key numbers**: 25 kernel axioms (SHA-256 signed) (V), 11 telos gates (V), 3 tiers (V)
- **Volatility Level**: LOW (kernel is immutable; gates change via proposal protocol only)
- **Boundary Constraints**:
  - ALLOWED: May import from Schema domain
  - FORBIDDEN: Must NOT import from Runtime, Intelligence, or Evolution domains
- **Boundary Status**: **PASS** (V) -- no violations found
- **Notes for Agents**: `dharma_kernel.py` is SHA-256 signed. Do not modify. Gates are added via `GateRegistry.propose()`, not by editing `telos_gates.py` directly. Parent `~/CLAUDE.md` says "10 axioms" -- this is WRONG; actual count is 25.

### Domain 3: Runtime Core (S1 Operations + S2 Coordination)

- **Path**: `dharma_swarm/swarm.py` (3,119 lines), `orchestrator.py` (2,272 lines), `agent_runner.py` (3,023 lines), `providers.py` (2,938 lines), `message_bus.py`, `signal_bus.py`, `task_board.py`, `handoff.py`
- **Global Role**: Agent lifecycle, task routing, LLM provider management, async messaging
- **Primary Entry Points**: `swarm.py` (facade), `orchestrator.py` (task->agent dispatch), `agent_runner.py` (execution + provider routing)
- **State Management**: `~/.dharma/` (SQLite via aiosqlite), in-memory task board
- **Volatility Level**: MEDIUM
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance (for gate checks)
  - FORBIDDEN: Must NOT import from TUI/Terminal domain directly. Use bridges.
- **Boundary Status**: **PASS** (V) -- no violations found
- **The Routing Call Chain** (V):
  ```
  SwarmManager.dispatch_next()
    -> Orchestrator.dispatch() [task->agent assignment]
      -> AgentRunner._invoke_provider()
        -> ModelRouter.complete_for_task() [providers.py:2535]
          -> ProviderPolicyRouter.route() [provider_policy.py]
            -> DecisionRouter.route() [REFLEX/DELIBERATIVE/ESCALATE]
          -> model_hierarchy.py [tier selection]
          -> SmartRouter [cost optimization]
          -> provider.complete() [actual LLM API call]
  ```
- **Notes for Agents**: Orchestrator does task->agent assignment, NOT provider selection. Provider routing happens in AgentRunner via ModelRouter. `orchestrate.py` has orchestration logic; `orchestrate_live.py` runs the 5-loop live system. `ginko_orchestrator.py` is Ginko-specific.

### Domain 4: Intelligence (S4)

- **Path**: `dharma_swarm/thinkodynamic_director.py` (5,167 lines), `telos_substrate.py` (4,423 lines), `context.py` (1,387 lines), `context_compiler.py`, `context_agent.py`, `zeitgeist.py`, `active_inference.py`, `decision_ontology.py`, `decision_router.py`, `intent_router.py`, `routing_memory.py`
- **Global Role**: Task scoring, context injection, routing decisions, environmental scanning
- **Primary Entry Points**: `thinkodynamic_director.py` (brain), `context.py` (orientation)
- **State Management**: `routing_memory.py` persists routing outcomes via EWMA scoring
- **Volatility Level**: HIGH (most active development area)
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance, Runtime Core
  - FORBIDDEN: Must NOT import from TUI/Terminal or Evolution directly
- **Notes for Agents**: `thinkodynamic_director.py` is 5,167 lines -- a god object. Be careful. `telos_substrate.py` (4,423 lines) is imported only by `swarm.py` (lazy) -- possibly a zombie god object. `decision_router.py` is called via ProviderPolicyRouter, not directly. `intent_router.py` is NOT in the main dispatch path -- only used for CLI skill composition.

### Domain 5: Evolution & Learning

- **Path**: `dharma_swarm/evolution.py` (3,227 lines), `cascade.py`, `meta_evolution.py`, `diversity_archive.py`, `selector.py`, `ucb_selector.py`, `smart_seed_selector.py`, `landscape.py`, `jikoku_fitness.py`, `dse_integration.py`
- **Global Role**: DarwinEngine, F(S)=S cascade, meta-evolution, diversity preservation
- **Primary Entry Points**: `evolution.py` (DarwinEngine), `cascade.py` (LoopEngine)
- **State Management**: `~/.dharma/evolution/archive.jsonl`, `~/.dharma/evolution/merkle_log.json`
- **Volatility Level**: MEDIUM
- **Circular Dependency WARNING**: 6-module cycle exists (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) with direct module-level imports (V)
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance (for gate checks), Runtime Core (for agent dispatch)
  - FORBIDDEN: Must NOT import from TUI/Terminal
- **Notes for Agents**: Evolution is gated by telos gates. `diversity_archive.py` implements MAP-Elites -- do not remove diversity pressure. The 6-module circular dependency is the highest-risk architectural debt in the codebase.

### Domain 6: Bridges (Integration Layer)

**21 bridge files** (V), **10,602 total LOC**:

| Bridge | Lines | Importers | Status |
|--------|-------|-----------|--------|
| terminal_bridge.py | 2,738 | 2 | ALIVE |
| operator_bridge.py | 1,819 | 15 | ALIVE |
| vault_bridge.py | 885 | 2 | ALIVE |
| bridge_registry.py | 842 | 15 | ALIVE (infra) |
| bridge.py | 583 | 78 | ALIVE (core) |
| semantic_memory_bridge.py | 518 | 2 | ALIVE |
| bridge_coordinator.py | 449 | 3 | ALIVE (infra) |
| instinct_bridge.py | 374 | 4 | ALIVE |
| trishula_bridge.py | 347 | 1 | STALE |
| session_event_bridge.py | 311 | 2 | ALIVE |
| a2a/a2a_bridge.py | 309 | 2 | ALIVE |
| review_bridge.py | 224 | 4 | ALIVE |
| roaming_operator_bridge.py | 202 | 3 | ALIVE (boundary violation) |
| skill_bridge.py | 201 | 2 | ALIVE |
| optimizer_bridge.py | 191 | 8 | ALIVE |
| ecosystem_bridge.py | 170 | 3 | ALIVE |
| verify/flywheel_bridge.py | 118 | 0 | **ZOMBIE** |
| offline_training_bridge.py | 111 | 0 | **ZOMBIE** |
| runtime_bridge.py | 98 | 0 | **ZOMBIE** |
| ginko_bridge.py | 94 | 1 | ALIVE |

- **Primary Entry Points**: `terminal_bridge.py` (Bun<->Python), `bridge.py` (core abstraction)
- **State Management**: Bridges are stateless translators (mostly)
- **Volatility Level**: HIGH (most duplication risk area)
- **Boundary Constraints**:
  - ALLOWED: May import from any domain they bridge between
  - FORBIDDEN: Bridges must NOT import from other bridges (no bridge chains)
- **Boundary Status**: **FAIL** (V) -- `roaming_operator_bridge.py:14` imports `operator_bridge` directly; `bridge_coordinator.py` imports `bridge_registry` via late imports (6 locations)
- **4 zombie bridges deleted** in PR #95: math_bridges, flywheel_bridge, offline_training_bridge, runtime_bridge

### Domain 7: Terminal / TUI

- **Path**: `dharma_swarm/tui/`, `dharma_swarm/terminal_adapters/`, `dharma_swarm/terminal_routing/`, `dharma_swarm/terminal_engine/`, `dharma_swarm/terminal_commands/`
- **Global Role**: Bun/Ink terminal UI and its Python backend
- **Primary Entry Points**: `terminal_bridge.py` (JSON stdio protocol), `tui/` (Bun app)
- **State Management**: Stateless (session state in terminal, not Python)
- **Volatility Level**: HIGH (recent Bun TUI rewrite)
- **Boundary Constraints**:
  - ALLOWED: Schema, bridges (terminal_bridge.py only)
  - FORBIDDEN: Must NOT import from Runtime Core, Intelligence, or Evolution directly
- **Boundary Status**: **PASS** (V) -- no violations found
- **Adapter duplication**: `terminal_adapters/` and `tui/engine/adapters/` have identical file structure (base.py, claude.py, codex.py, ollama.py, openrouter.py) but **different implementations** (V). All 5 corresponding files differ.
- **Dead routing copies**: `tui/model_routing.py` and `terminal_routing/model_routing.py` are **identical to each other but different from the original** `dharma_swarm/model_routing.py` (V). Neither is imported in the main dispatch path -- both are dead code.

### Domain 8: API / Backend

- **Path**: `api/`
- **Global Role**: FastAPI REST endpoints for dashboard and external access
- **Primary Entry Points**: `api/main.py`
- **State Management**: Delegates to Runtime Core
- **Volatility Level**: LOW
- **Boundary Constraints**:
  - ALLOWED: Schema, Runtime Core (via imports)
  - FORBIDDEN: Must NOT import from TUI/Terminal
- **Circular Dependency WARNING**: api ↔ dharma_swarm bidirectional imports exist (V). `api_key_audit.py` and `provider_smoke.py` import from `api.routers` lazily.
- **Notes for Agents**: The API is a thin layer over the Python core. Don't put business logic here.

### Domain 9: Dashboard / Frontend

- **Path**: `dashboard/`
- **Global Role**: Next.js web dashboard
- **Primary Entry Points**: `dashboard/src/app/page.tsx`
- **State Management**: React state + API calls to backend
- **Volatility Level**: LOW (underactive)
- **Boundary Constraints**:
  - ALLOWED: Communicates with API only (HTTP)
  - FORBIDDEN: No direct Python imports (it's JavaScript/TypeScript)
- **Notes for Agents**: The dashboard exists but is not the primary interface. The Bun TUI is the active frontend.

### Domain 10: Ontology

- **Path**: `dharma_swarm/ontology.py` (1,822 lines), `ontology_runtime.py`, `ontology_hub.py`, `ontology_agents.py`, `ontology_adapters.py`, `ontology_query.py`
- **Global Role**: Palantir-pattern typed object system (ObjectType, OntologyObj, Links, Actions)
- **Primary Entry Points**: `ontology.py` (1,822 lines -- the foundation)
- **State Management**: SQLite-backed (`~/.dharma/ontology.db`, 1.3 MB)
- **Volatility Level**: MEDIUM
- **Boundary Constraints**:
  - ALLOWED: Schema
  - FORBIDDEN: Should not import from Terminal or Evolution
- **Notes for Agents**: The ontology is positioned as "THE foundation" in NAVIGATION.md but its relationship to the simpler Pydantic models in `models.py` is unclear. Two competing type systems coexist.

### Domain 11: State & Memory (NEW -- not in prior manifest)

- **Path**: 11 memory modules (5,848 LOC), 8 context modules (5,828 LOC)
- **Global Role**: Persistent memory, context assembly, state management
- **Key numbers**: 49 modules use SQLite (V), 126 modules write JSONL (V), 113 modules write to filesystem (V)
- **State Directory**: `~/.dharma/` with 74 subdirectories, 10+ SQLite databases (V)
- **Key databases**: memory_plane.db (58 MB), messages.db (3.6 MB), runtime.db (3.1 MB), ontology.db (1.3 MB)
- **Volatility Level**: HIGH
- **Notes for Agents**: This is the highest-entropy zone for state. 126 modules write JSONL and 49 use SQLite with no unified data access layer. State writes are scattered across the codebase.

---

## SHARED INVARIANTS

### State Mutation Discipline
- All persistent state lives in `~/.dharma/` (SQLite, JSONL, JSON)
- No Python module may write to the filesystem outside `~/.dharma/` during runtime
- Gate check results must be witnessed to `~/.dharma/witness/` (append-only)
- Evolution archive is append-only (`~/.dharma/evolution/archive.jsonl`)
- Stigmergy marks are append-only (`~/.dharma/stigmergy/marks.jsonl`)
- **Reality check**: 113 modules write to filesystem, 126 write JSONL (V). Enforcement is cultural, not technical.

### Event / Schema Discipline
- All shared types in `models.py` (Pydantic 2)
- Message bus: `message_bus.py` (async SQLite pub/sub, for agent communication)
- Signal bus: `signal_bus.py` (in-process events, for loop-to-loop signaling)
- These are DIFFERENT systems. Do not confuse them.

### Routing / Model Selection Truth
- **Canonical routing hub**: `ModelRouter.complete_for_task()` in `providers.py:2535` (V)
- **Decision path**: ProviderPolicyRouter -> DecisionRouter (REFLEX/DELIBERATIVE/ESCALATE)
- **Provider hierarchy**: `model_hierarchy.py` (TIER_FREE -> TIER_CHEAP -> TIER_PAID)
- **Cost optimization**: `smart_router.py`
- **Signal generation**: `router_v1.py` (language detection, complexity, tokens) -- ACTIVE, not legacy (V)
- **Learning**: `routing_memory.py` (EWMA scores from ~100 events)
- **Dead copies**: `tui/model_routing.py` and `terminal_routing/model_routing.py` are unused (V)
- **18 provider types** in enum (V), **19 provider classes** including abstract base (V)

### Naming Conventions
- Python: snake_case everywhere, PEP 8
- Files: descriptive, no abbreviations except established ones (dgc, tui, vsm, a2a)
- Tests: `tests/test_<module_name>.py` mirrors `dharma_swarm/<module_name>.py`
- Config: environment variables override defaults in `config.py`
- **Known inconsistency**: "bridge" vs "adapter" vs "connector" all mean "interface between systems". "orchestrator" vs "orchestrate" vs "director" all mean "coordinate work". "routing" vs "router" vs "selector" all mean "choose where to send".

### Legacy Quarantine Rules
- Files in `docs/archive/` are dead. Do not reference them as current.
- `swarmlens_app.py` is the old TUI (zero importers) (V). The current TUI is Bun/Ink in `tui/`.
- `specs/DGC_TERMINAL_ARCHITECTURE.md` (v1.0) is superseded by v1.1.
- `router_v1.py` is **NOT legacy** -- it is actively used in the routing chain for signal generation (V). The manifest previously labeled it "legacy" incorrectly.
- **4 zombie bridges** deleted in PR #95: `math_bridges.py`, `verify/flywheel_bridge.py`, `offline_training_bridge.py`, `runtime_bridge.py`

### Test / Verification Expectations
- `python3 -m pytest tests/ -q` must pass before any commit
- **16 collection errors** are KNOWN (V): 10 missing numpy, 2 missing textual, 1 missing typer, 1 missing pytest_asyncio, 1 missing yaml, 1 missing tui.app module
- Test file naming: `tests/test_<module>.py`
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- **300-second timeout** per test (conftest.py)

---

## ACTIVE LEDGER

**COMMON OPERATING PICTURE: MULTI-TAB LOCKS**

*Human Orchestrator: Update this list before pasting into a new tab.*

- LOCKED DOMAINS (currently in-flux by other agents): *None*
- AVAILABLE DOMAINS: *All*

*Last updated: 2026-04-04 by fresh filesystem-verified re-audit*

---

## MANDATORY AGENT BOOT SEQUENCE

**PRE-FLIGHT CHECKLIST FOR ALL AGENTS:**

Before you begin your task, you must verify:

1. You have mapped your task to a specific domain in the Topography above.
2. You confirm your domain is NOT in the Active Ledger Locked list.
3. You have read the Boundary Constraints for your domain and will not generate imports or logic that violate them.
4. You will not rely on vibe coding. If a seam, type, protocol, state contract, or API is missing from context, you will STOP and find the exact file before proceeding.
5. You will treat this manifest as repo-wide canon, not model-specific suggestion.
6. You will check `REPO_GOVERNANCE_AUDIT.md` for known contradictions before relying on any doc's numerical claims.
7. You understand that parent `~/CLAUDE.md` has stale numbers (says "10 axioms", "9 providers", "370 modules") -- trust THIS manifest's verified numbers instead.

---

## CORRECTIONS TO PRIOR AUDIT (2026-04-04)

This re-audit found errors in the earlier 5-model audit:

| Error in prior audit | Corrected value |
|---------------------|----------------|
| "codex_overnight.py is 10K lines" | **1,008 lines** (V) |
| "17 bridge files" / "19 bridge files" (self-contradicting) | **21 bridge files** (V) |
| "16 TUI test errors" | **16 total errors: 10 numpy, 2 textual, 1 typer, 1 pytest_asyncio, 1 yaml, 1 tui.app** -- only 3 are TUI-specific (V) |
| "10 pillars" with "PILLAR_04 missing, PILLAR_11 present" | **10 pillar files exist** (PILLAR_01-03, 05-11; PILLAR_04 never created). Sparse numbering, not 11. (V) |
| "router_v1.py is LEGACY" | **router_v1.py is ALIVE** -- actively used by providers.py for signal generation (V) |
| "18 provider classes" (VIVEKA) | **19 classes** (including abstract LLMProvider base); **18 ProviderType enum values** (V) |
| "engine/ is legacy duplicate of tui/engine/" | **Both are ALIVE** -- engine/ has 41 importers, tui/engine/ has 31 importers. Different purposes. (V) |
| Bridge count of "30" (Phase 3A) | **20 actual bridge files** -- the "30" counted test files and non-bridge files with "bridge" in name (V) |

---

## GOVERNANCE FILE RELATIONSHIPS

```
SOVEREIGN_MANIFEST.md (this file)
    |- Defines: axioms, domains, invariants, boot sequence, verified numbers
    |- Enforced by: CLAUDE.md (behavioral rules)
    |- Audited by: REPO_GOVERNANCE_AUDIT.md (contradiction log)
    |- Organized by: CANONICAL_DOC_STACK.md (doc hierarchy)
    |- Detailed by: docs/architecture/NAVIGATION.md (module-level map)
```

---

## WHAT SHOULD HAPPEN TO CLAUDE.md?

**Recommendation: RETAIN and SHARPEN.**

`CLAUDE.md` is the most effective governance surface in the repo:
- Actually read by agents (loaded automatically by Claude Code)
- Actively maintained (last updated 2026-04-04)
- Contains real architectural truth (5-layer model, key abstractions, build commands)

**Stale numbers to fix**:
- "~1,700 lines" for swarm.py -> **3,119** (V)
- References NAVIGATION.md which claims "500 modules" -> current filesystem count **532 dharma_swarm Python modules** (V)
- No mention of the 17 bridges, 13 routers, 14 adapters, or their hierarchy
- Provider list says 9 -> should acknowledge **18 types** (V)

**Do NOT**:
- Rename to AGENTS.md (CLAUDE.md is the Claude Code standard)
- Split it (it's already the right size at 148 lines)
- Mirror it (one source of truth per topic)
- Add the full domain topography (that belongs here in the manifest)

**DO**:
- Add a pointer to this SOVEREIGN_MANIFEST.md for architectural truth
- Fix stale numbers
- Add a note that parent `~/CLAUDE.md` has different (stale) numbers
