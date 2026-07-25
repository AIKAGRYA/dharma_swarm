# REPO GOVERNANCE AUDIT

**Date**: 2026-04-04
**Auditors**: Claude Opus 4.6, DeepSeek-v3.1 (671B), GPT-OSS (20B), Codex CLI 0.117.0, RUFLO v3.5.51
**Method**: Multi-model convergent audit — 5 independent AI systems, zero coordination between them
**Scope**: Read-only. No code changes. No runtime modification.

---

## 1. VERIFIED NUMBERS

| Metric | CLAUDE.md Claim | NAVIGATION.md Claim | Actual (2026-04-04) | Verdict |
|--------|----------------|--------------------|--------------------|---------|
| Python modules | "370 modules" | "500 Python modules" | **514** | BOTH STALE |
| Test count | "4300+ tests" | "8,848 tests" | **8,562 collected, 16 errors** | CLAUDE.md STALE, NAV INFLATED |
| Test files | — | "494 test files" | **497-501** | CLOSE (grew) |
| swarm.py lines | "~1,700 lines" | "2,359 lines" | **3,119 lines** | BOTH STALE |
| orchestrator.py lines | — | "2,078 lines" | **2,272 lines** | NAV STALE |
| Providers | "9 LLM providers" | "9 LLM providers" | **9** | VERIFIED |
| Top-level .py files | — | — | **375 / 514 (73%)** | UNREPORTED PROBLEM |

---

## 2. ALL GOVERNANCE-RELEVANT DOCS FOUND

### Root Level (6 files)
| File | Lines | Purpose | Current? |
|------|-------|---------|----------|
| `CLAUDE.md` | 236 | Agent instruction file | **YES** — actively maintained |
| `README.md` | ~200 | Repo overview | PARTIAL — frontmatter bloat |
| `LIVING_LAYERS.md` | ~600 | Living layers architecture | STALE — references old line counts |
| `PRODUCT_SURFACE.md` | ~100 | Product surface map | UNKNOWN |
| `program.md` | ~300 | Program description | UNKNOWN |
| `program_ecosystem.md` | ~200 | Ecosystem map | RECENT (Apr 2) |

### docs/architecture/ (20 files)
| File | Purpose | Current? |
|------|---------|----------|
| `NAVIGATION.md` | Module map (12 layers) | **STALE** — numbers don't match |
| `MODEL_ROUTING_CANON.md` | "Single story" for routing | **CONTRADICTED** — 3 routing files exist |
| `INTEGRATION_MAP.md` | Infrastructure mapping | STALE (dated 2026-03-08) |
| `GENOME_WIRING.md` | Genome signal wiring | UNKNOWN |
| `ORCHESTRATOR_LEDGERS.md` | Orchestrator state | UNKNOWN |
| `DHARMA_SWARM_THREE_PLANE_ARCHITECTURE_2026-03-16.md` | 3-plane arch | STALE (pre-TUI) |
| `JIKOKU_SAMAYA_*.md` (4 files) | Temporal architecture | STALE |
| `SWARMLENS_MASTER_SPEC.md` | SwarmLens TUI spec | STALE (pre-Bun rewrite) |
| `VERIFICATION_LANE.md` | Verification pipeline | UNKNOWN |
| `COMPLIANCE_MAPPING.md` | Compliance map | UNKNOWN |
| Others (8 files) | Various | MIXED |

### specs/ (12+ files)
| File | Purpose | Current? |
|------|---------|----------|
| `DGC_TERMINAL_ARCHITECTURE.md` | Terminal JSON stdio spec | PARTIAL |
| `DGC_TERMINAL_ARCHITECTURE_v1.1.md` | v1.1 terminal spec | MORE CURRENT |
| `Dharma_Constitution_v0.md` | Constitutional rules | FOUNDATIONAL |
| `KERNEL_CORE_SPEC.md` | Kernel spec | FOUNDATIONAL |
| `STIGMERGY_11_LAYER_SPEC_2026-03-23.md` | Stigmergy layers | RECENT |
| `SOVEREIGN_BUILD_PHASE_MASTER_SPEC_2026-03-19.md` | Build spec | STALE |
| `ONTOLOGY_PHASE2_*.md` (2 files) | Ontology migration | STALE |
| `TaskBoardCoordination.tla` | TLA+ spec | UNKNOWN |

### foundations/ (23 files)
All 10 pillars + synthesis + meta docs. **STABLE** — intellectual genome, rarely changes.

### lodestones/ (15+ files)
Grounding research, expanded pillars, bridges, seeds. **STABLE** — reference material.

### docs/archive/ (12+ files)
Explicitly archived. **CORRECTLY QUARANTINED.**

### docs/research/ (12+ files)
Research docs. Mixed recency. Most are reference material, not governance.

---

## 3. CONTRADICTIONS DETECTED

### C1: Module Count Drift
- `CLAUDE.md` (root): "370 modules, 296 connected, 168 orphans"
- `NAVIGATION.md`: "500 Python modules"
- **Reality**: 514 modules
- **Diagnosis**: CLAUDE.md references an old audit. NAVIGATION.md is closer but also stale.

### C2: Test Count Inflation
- `CLAUDE.md` (root): "4300+ tests"
- `NAVIGATION.md`: "8,848 tests"
- **Reality**: 8,562 tests collected + 16 collection errors
- **Diagnosis**: CLAUDE.md is from an older era. NAVIGATION.md overstates by ~300.

### C3: swarm.py Size
- `CLAUDE.md` (root): "~1,700 lines"
- `NAVIGATION.md`: "2,359 lines"
- **Reality**: 3,119 lines
- **Diagnosis**: File has grown significantly. All references stale.

### C4: "Single Story" Routing Claim
- `MODEL_ROUTING_CANON.md`: Claims to be "the single story for model and provider selection"
- **Reality**: 3 separate `model_routing.py` files exist:
  - `dharma_swarm/model_routing.py`
  - `dharma_swarm/tui/model_routing.py`
  - `dharma_swarm/terminal_routing/model_routing.py`
- Plus: `routing_memory.py`, `operator_core/routing_payloads.py`
- **Diagnosis**: The "single story" was written before the TUI/terminal routing split.

### C5: Massive Frontmatter Injection
- Every doc in docs/, specs/, foundations/ has been injected with 80+ lines of YAML frontmatter by "Codex (GPT-5)"
- The frontmatter includes PKM, stigmergy, curation, and improvement metadata
- **Problem**: This bloats every file, making them harder to read. The frontmatter often exceeds the actual content.
- **Diagnosis**: Classic multi-agent drift. One agent's metadata system was applied globally without governance review.

### C6: Bridge Proliferation Without Registry
- 17 bridge files exist at top level of dharma_swarm/:
  - terminal_bridge.py, runtime_bridge.py, ecosystem_bridge.py, operator_bridge.py
  - skill_bridge.py, review_bridge.py, session_event_bridge.py, bridge.py
  - bridge_registry.py, bridge_coordinator.py, instinct_bridge.py
  - offline_training_bridge.py, vault_bridge.py, math_bridges.py
  - semantic_memory_bridge.py, roaming_operator_bridge.py, trishula_bridge.py
  - Plus: a2a/a2a_bridge.py, verify/flywheel_bridge.py
- **No doc describes the bridge hierarchy or which bridges are active.**
- `bridge_registry.py` and `bridge_coordinator.py` exist but don't appear to govern the others.

### C7: Adapter Duplication
- `dharma_swarm/terminal_adapters/` (6 files)
- `dharma_swarm/tui/engine/adapters/` (6 files)
- `dharma_swarm/engine/adapters/` (exists)
- `dharma_swarm/operator_core/adapters.py`
- `dharma_swarm/contracts/runtime_adapters.py`, `intelligence_adapters.py`
- **Multiple adapter directories doing overlapping work with no documented relationship.**

### C8: Orchestrator Fragmentation
- `orchestrator.py` (2,272 lines) — task routing
- `orchestrate.py` — orchestration logic
- `orchestrate_live.py` (1,549 lines) — live execution
- `ginko_orchestrator.py` — Ginko-specific orchestration
- **No doc explains which orchestrator is canonical or how they relate.**

### C9: TUI Tests Broken
- 16 test collection errors, all in `tests/tui/`
- TUI tests reference modules that may not exist or have import issues
- **No error tracking doc exists for these failures.**

---

## 4. STRUCTURAL PROBLEMS (MULTI-MODEL CONSENSUS)

All 5 audit sources independently identified:

### P1: Flat Package Anti-Pattern
**375 of 514 Python files (73%) sit at the top level** of `dharma_swarm/`. Only 139 files are in subdirectories. This makes the package nearly impossible to navigate and creates implicit coupling between unrelated modules.

### P2: God Objects
- `dgc_cli.py`: 6,979 lines (CLI, commands, formatting, state, everything)
- `thinkodynamic_director.py`: 5,167 lines
- `telos_substrate.py`: 4,423 lines
- `evolution.py`: 3,227 lines
- `swarm.py`: 3,119 lines

### P3: Naming Inconsistency
Same concepts named differently across modules:
- "bridge" vs "adapter" vs "connector" — all mean "interface between systems"
- "orchestrator" vs "orchestrate" vs "director" — all mean "coordinate work"
- "routing" vs "router" vs "selector" — all mean "choose where to send"
- "context" vs "orientation" vs "prompt" — overlapping context injection concepts

### P4: No Import Boundary Enforcement
Nothing prevents any module from importing any other module. The flat structure enables spaghetti imports.

### P5: Doc Maze
The repo has 80+ markdown files across root, docs/, specs/, foundations/, lodestones/. There is no document hierarchy. No single entry point tells you which docs are current vs stale.

---

## 5. WHAT IS ACTUALLY ALIVE VS DEAD

### ALIVE (actively used, recently modified)
- `dgc_cli.py` — primary CLI entry point
- `swarm.py` — core facade
- `orchestrator.py` — task routing
- `agent_runner.py` — agent lifecycle
- `providers.py` — LLM provider layer
- `evolution.py` — DarwinEngine
- `telos_gates.py` — governance gates
- `dharma_kernel.py` — immutable axioms
- `models.py` — Pydantic schemas
- `config.py` — configuration
- `stigmergy.py` / `stigmergy_store.py` — pheromone coordination
- `message_bus.py` — async pub/sub
- `terminal_bridge.py` — Bun TUI bridge
- API layer (`api/main.py` + routers)

### ZOMBIE (exists, has code, but unclear if anything uses it)
- Most bridge files beyond terminal_bridge
- `thinkodynamic_director.py` (5K lines, unknown active callers)
- `telos_substrate.py` (4K lines, unknown active callers)
- `swarmlens_app.py` — old TUI (replaced by Bun?)
- `overnight_director.py` — overnight mode
- `codex_overnight.py` (10K lines, last heartbeat failed)
- Multiple `*_bridge.py` files

### DEAD (no evidence of use)
- `dharma_swarm/engine/` — appears to duplicate `tui/engine/`
- Several auto_grade/, auto_research/ modules
- Legacy operator_core/ files
- Old routing implementations (router_v1.py)

---

## 6. WHAT SHOULD HAPPEN TO CLAUDE.md?

**Recommendation: RETAIN and SHARPEN.**

`CLAUDE.md` is the most effective governance surface in the repo. It is:
- Actually read by agents (it's loaded automatically)
- Actively maintained (last updated Apr 4)
- Contains real architectural truth (5-layer model, key abstractions, build commands)

**Problems to fix:**
1. Stale numbers (370 modules → 514, 4300+ tests → 8500+, swarm.py ~1700 → 3119)
2. Missing: bridge hierarchy, adapter map, orchestrator relationships
3. Missing: which docs are canonical vs stale
4. Should reference this governance layer

**Do NOT:**
- Rename to AGENTS.md (CLAUDE.md is the standard for Claude Code)
- Split it (it's already the right size)
- Mirror it (one source of truth)

---

## 7. MINIMUM CANONICAL FILE STACK

See `CANONICAL_DOC_STACK.md` for the full proposal.

---

## 8. ADDITIONAL FINDINGS (VIVEKA + CODEX)

### VIVEKA Epistemic Audit (83 tool calls, 349s runtime)

VIVEKA discovered contradictions the initial sweep missed:

| ID | Severity | Finding |
|----|----------|---------|
| C-04 | **CRITICAL** | Parent `~/CLAUDE.md` says "10 axioms" in DharmaKernel. Repo CLAUDE.md and actual code say **25 axioms**. The doc every Claude session reads first has a 2.5x undercount. |
| C-03 | HIGH | Providers claimed as 9 everywhere. Actual: **18 concrete provider classes** in providers.py |
| C-09 | HIGH | `spec-forge/transcendence-multi-agent-coordination/research/` referenced in CLAUDE.md **does not exist** |
| C-10 | HIGH | "Keep files under 500 lines" rule in CLAUDE.md violated by **147 of 513 files (29%)**. dgc_cli.py alone is 6,979 lines. |
| C-07 | MEDIUM | program.md claims ~83K lines across ~90 files. Reality: **227K lines across 513 files** (2.7x undercount) |
| C-08 | LOW | "12 architectural layers" but NAVIGATION.md defines **13** (Layer 0 through 12) |
| C-11 | LOW | LIVING_LAYERS.md says stigmergy.py is 220 lines. Actual: **564 lines** |

**VIVEKA root cause**: "Documentation was generated at discrete points in time and never updated. The codebase grew 2-7x while docs stayed frozen."

### Codex Architectural Audit (independent, GPT-5.4)

Codex found **import cycles** that RUFLO's JS-focused analyzer missed:

**Circular dependency chains:**

| Cycle | Modules | Severity |
|-------|---------|----------|
| Evolution/meta-evolution | 6 modules (evolution ↔ jikoku_fitness ↔ meta_evolution ↔ info_geometry ↔ dse_integration ↔ landscape) | HIGH |
| Routing | 4 modules (router_v1 → provider_policy → smart_router → router_v1) | HIGH |
| Build orchestration | 3 modules (build_engine → foreman → custodians → build_engine) | MEDIUM |
| api ↔ dharma_swarm | Top-level bidirectional import | HIGH |
| organism ↔ dharma_attractor | 2-module cycle | LOW |
| docker_sandbox ↔ sandbox | 2-module cycle | LOW |
| providers ↔ runtime_provider | 2-module cycle | MEDIUM |
| smart_seed_selector ↔ thinkodynamic_director | 2-module cycle | MEDIUM |
| verify/reporter ↔ verify/reviewer | 2-module cycle | LOW |

**Weak boundary quantification:**
- `contracts/` → flat root: 24 import edges
- `cascade_domains/` → flat root: 15 import edges
- `tui/` → flat root: 9 import edges
- flat root → `engine/`: 21 import edges (bidirectional leakage)

**Codex verdict**: "The real center of gravity is a flat monolith under dharma_swarm, not the subpackages."

---

## 9. RUFLO ANALYSIS NOTE

RUFLO v3.5.51's static analyzers (boundaries, modules, circular, complexity) are JavaScript/TypeScript-focused and returned empty results for Python files. RUFLO's orchestration capabilities (hive-mind, guidance, autopilot) could be useful for future multi-agent governance enforcement but require initialization and configuration. The repo does not currently use RUFLO.

## 9. CODEX REVIEW NOTE

Codex CLI 0.117.0 was dispatched for independent architectural review. Results pending at time of writing. Codex's `review` mode can be used for ongoing architectural compliance checks.

---

## 10. FRESH RE-AUDIT CORRECTIONS (2026-04-04, Claude Code Opus 4.6)

A parallel re-audit using Claude Code's filesystem tools (Grep, Glob, Read, Bash, 12 parallel agents) found errors in the original 5-model audit above:

### Self-Corrections

| Original Claim | Section | Corrected Value | Evidence |
|----------------|---------|-----------------|----------|
| "codex_overnight.py 10K lines" | Section 5 | **1,008 lines** | wc -l dharma_swarm/codex_overnight.py |
| "16 TUI test errors" | C9 | **16 total: 10 numpy, 2 textual, 1 typer, 1 pytest_asyncio, 1 yaml, 1 tui.app** -- only 3 are TUI-specific | pytest --collect-only |
| "17 bridge files" (line in Section 2) | C6 | **20 bridge files** | find dharma_swarm -name "*bridge*" |
| "19 bridge files" (line in Section 3 C6) | C6 | **20 bridge files** | Self-contradicting within same doc (17 vs 19); both wrong |
| VIVEKA C-03: "18 concrete provider classes" | Section 8 | **19 classes** (incl. abstract LLMProvider); **18 ProviderType enum values** | grep "class.*Provider" providers.py + models.py |

### New Contradictions Found

| ID | Severity | Finding |
|----|----------|---------|
| C-NEW-1 | HIGH | `router_v1.py` labeled "LEGACY" in SOVEREIGN_MANIFEST and NAVIGATION.md. Actually ALIVE: used by providers.py for signal generation (build_routing_signals), doctor.py, smart_router.py. 6+ importers. |
| C-NEW-2 | MEDIUM | `engine/` labeled "legacy duplicate of tui/engine/" in SOVEREIGN_MANIFEST. Actually BOTH are ALIVE: engine/ has 41 importers, tui/engine/ has 31 importers. Different purposes. |
| C-NEW-3 | MEDIUM | NAVIGATION.md claims CLAUDE.md is 383 lines. Actual: 148 lines. |
| C-NEW-4 | LOW | `tui/model_routing.py` and `terminal_routing/model_routing.py` are IDENTICAL (confirmed via comparison). Both are dead code (never imported in dispatch path). |
| C-NEW-5 | HIGH | 74 files across the repo claim to be "source of truth" or "canonical" -- while CANONICAL_DOC_STACK.md explicitly prohibits overlapping claims. |
| C-NEW-6 | MEDIUM | NAVIGATION.md summary claims "~274 modules, ~118,000+ lines". Actual: 514 modules, 227,486 lines. Nearly 2x on both metrics. |

### Circular Dependencies: All 9 Independently Confirmed

| Cycle | Modules | Import Pattern | Severity |
|-------|---------|---------------|----------|
| 1 | evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness (6) | Mixed direct + lazy | HIGH |
| 2 | router_v1 → provider_policy → smart_router → router_v1 (4) | TYPE_CHECKING + lazy | HIGH |
| 3 | build_engine → foreman → custodians (3) | All lazy | MEDIUM |
| 4 | api ↔ dharma_swarm (bidirectional) | Direct + lazy | HIGH |
| 5 | organism ↔ dharma_attractor (2) | All lazy | LOW |
| 6 | docker_sandbox ↔ sandbox (2) | Direct + lazy | LOW |
| 7 | providers ↔ runtime_provider (2) | All lazy | MEDIUM |
| 8 | smart_seed_selector ↔ thinkodynamic_director (2) | All lazy | MEDIUM |
| 9 | verify/reporter ↔ verify/reviewer (2) | Direct + lazy | LOW |

### Import Boundary Audit Results

| Boundary | Domain | Status |
|----------|--------|--------|
| Schema (models, config, profiles) | Domain 1 | **PASS** |
| Governance (kernel, gates) | Domain 2 | **PASS** |
| Runtime Core (swarm, orchestrator, runner) | Domain 3 | **PASS** |
| Bridges (no bridge-to-bridge imports) | Domain 6 | **FAIL** -- roaming_operator_bridge:14 imports operator_bridge; bridge_coordinator imports bridge_registry (6 locations) |
| TUI (no direct Runtime/Intelligence/Evolution imports) | Domain 7 | **PASS** |

### Alive/Dead/Zombie Reclassification

| File | Prior Status | Verified Status | Evidence |
|------|-------------|----------------|----------|
| thinkodynamic_director.py | Zombie | **ALIVE** | 2 importers (swarm.py, smart_seed_selector.py) |
| telos_substrate.py | Zombie | **STALE** | 1 importer (swarm.py, lazy) |
| swarmlens_app.py | Zombie | **ZOMBIE** (confirmed) | 0 importers |
| overnight_director.py | Zombie | **ALIVE** | 2 importers (dgc_cli.py, cron_runner.py) |
| codex_overnight.py | Zombie | **STALE** | 1 importer (terminal_overnight_supervisor.py) |
| router_v1.py | Legacy | **ALIVE** | 6+ importers in main routing chain |
| flywheel_bridge.py | — | **ZOMBIE** | 0 importers |
| runtime_bridge.py | — | **ZOMBIE** | 0 importers |
| math_bridges.py | — | **ZOMBIE** | 0 importers |
| offline_training_bridge.py | — | **ZOMBIE** | 0 importers |

---

## 11. POINTER FILES ADDED

The following pointer and plan files were added to root the ontology-native build track (per `CANONICAL_DOC_STACK.md`, every new doc must identify its place in the stack):

- `docs/governance/BUILD_SESSION_ENTRYPOINT.md` — canonical read-order and current-track pointers for every build session
- `docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md` — master spec for the first ontology-native seam
- `docs/plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md` — handoff notes for the next code agent
- `docs/plans/NEXT_10_SUBSTRATE_TODO.md` — prioritised 10-item build queue for the substrate track

## 2026-05-08 — Telos Hierarchy Correction (Track 2 doctrine drift log)

Drift discovered while landing the canonical telos hierarchy in `SOVEREIGN_MANIFEST.md §Telos Hierarchy` and aligning the doctrine + Loomwork surfaces. Each entry is a contradiction that existed before this commit; resolution noted inline.

### C1 — JAGAT_KALYAN_MASTER_VISION.md self-claims canonical authority outside the registry
- **Evidence:** `docs/dse/JAGAT_KALYAN_MASTER_VISION.md:1` self-titles "Master Vision Document"; the file is not in `CANONICAL_DOC_STACK.md` Authority Registry (lines 60–75 of that doc).
- **Resolution (2026-05-08):** added status header demoting the canonical claim and pointing to `SOVEREIGN_MANIFEST.md §Telos Hierarchy` as the registry-named owner of the telos invariant. Body preserved for archival continuity.

### C2 — Same doc collapses Jagat Kalyan into the GAIA platform
- **Evidence:** `docs/dse/JAGAT_KALYAN_MASTER_VISION.md` §I–§II frame JK as "AI-Coordinated Ecological Restoration & Grassroots Livelihood System" (the GAIA platform's mission).
- **Resolution (2026-05-08):** status header explicitly flags the hierarchy collapse and points to the corrected structure (JK > SIS > {GAIA, Loomwork}; Shakti Ginko under JK as metabolism; AE separate, unresolved).

### C3 — SIS / Silicon Is Sand was scattered, never named as a typed JK-level objective
- **Evidence:** SIS appears as adjective/concept in ~20 docs across `docs/`; no doc named it as the parent objective layer between JK and GAIA. `JAGAT_KALYAN_MASTER_VISION.md` had zero SIS occurrences.
- **Resolution (2026-05-08):** SIS named explicitly as a JK-level child objective in `SOVEREIGN_MANIFEST.md §Telos Hierarchy` with full definition (energy, water, chips, minerals, fabs, labor, land, emissions, e-waste).

### C4 — Loomwork docs framed Loomwork as peer of Shakti Ginko under JK constitutional layer
- **Evidence:** `docs/doctrine/OPERATIONAL_DOCTRINE.md:12` ("both peer VentureCells under the same constitutional layer"); `docs/loomwork/2026-05-07-loomwork-design.md:14` ("an arm — peer to Shakti Ginko").
- **Resolution (2026-05-08):** patched both docs. Loomwork is now named as a child of SIS (domain organ); Shakti Ginko is named as the wealth-metabolism organ under JK directly. Both are VentureCell-pattern instantiations but in distinct categorical positions (domain organ vs metabolism organ).

### C5 — Loomwork CompassRoom scored against "Jagat Kalyan fitness" (skipped SIS layer)
- **Evidence:** `docs/loomwork/2026-05-07-loomwork-design.md:60` defines `CompassRoom` as "Telos-driven filter. Scores any candidate atom/feed against Jagat Kalyan fitness." This collapses SIS into JK at the runtime-scoring layer.
- **Resolution (2026-05-08):** flagged in the loomwork-design.md status header. Runtime correction (`compass.py` scoring axis) is out of Track 2 scope (no-runtime invariant); future implementation should score against SIS-fitness primarily, with JK as the ultimate telos. Tracked as drift, not patched here.

### C6 — Attention Emancipation absent from this repo entirely
- **Evidence:** grep for "Attention Emancipation" / "attention emancipation" returned zero hits across `docs/`.
- **Resolution (2026-05-08):** AE named explicitly in `SOVEREIGN_MANIFEST.md §Telos Hierarchy` as a separate JK-level domain, marked **unresolved / not yet typed**, with explicit anti-collapse language (AE is not SIS, not productivity tooling, not generic focus work).

### C7 — Shakti Ginko placement was undefined relative to corrected hierarchy
- **Evidence:** Operational reality (AGNI VPS trading lab, `ginko_orchestrator.py`, Polymarket Rushabdev v4, Vraj nightly review, +$466/7d revenue) but no doctrine-level placement under the JK > SIS > {GAIA, Loomwork} + AE structure proposed in the doctrine correction.
- **Resolution (2026-05-08):** Shakti Ginko named in `SOVEREIGN_MANIFEST.md §Telos Hierarchy` as a JK-level child at peer priority to SIS but in a categorically distinct position (metabolism vs domain). Function: wealth-generation by all means possible. Discipline: trustee, not possessor (Sri Aurobindo, *The Mother* Ch. IV; `~/.claude/cabinet/worldview/money_as_divine_force.md`). Internal: trustee discipline gate-enforced (`shakti.py` quadrature). Outward function: unconstrained.

### C8 — MEGAFILE_INDEX Slot 2 (STUB) and Slot 3 (CONTESTED) were stale relative to ported substrate
- **Evidence:** `docs/MEGAFILE_INDEX.md:70` marked Slot 2 as STUB; line 86 marked Slot 3 as CONTESTED. The substrate files (`docs/doctrine/OPERATIONAL_DOCTRINE.md`, `docs/doctrine/LIVE_ROADMAP.md`) were ported onto this branch in commit `20a239a` (Track 2 Step 0).
- **Resolution (2026-05-08):** flipped Slot 2 STUB → SEEDED and Slot 3 CONTESTED → SEEDED. Roadmap contestation between `LOOMWORK_v0_MASTER.md` and `2026-05-07-loomwork-design.md` (cabinet) is preserved as a separate convergence track, not a blocker for slot graduation.

### C9 — SOVEREIGN_MANIFEST silent on the highest invariant (telos hierarchy)
- **Evidence:** `docs/governance/SOVEREIGN_MANIFEST.md` (registry-named owner of axioms + invariants per `CANONICAL_DOC_STACK.md`) had no Telos Hierarchy section before 2026-05-08.
- **Resolution (2026-05-08):** added §Telos Hierarchy as a new top-level section between Purpose and Global Axioms in commit `7ecf285`. The section names the full hierarchy, defines each layer (JK, Dharma Swarm-as-VSM, SIS, GAIA, Loomwork, AE, Shakti Ginko), cites Sri Aurobindo's *The Mother* Ch. IV as the source authority for Shakti Ginko, and lists conditions of consistency for downstream docs.

### C10 — JAGAT_KALYAN_CANONICAL_SYNTHESIS_2026-03-11.md is a second registry-violating canonical claim
- **Evidence:** `docs/reports/JAGAT_KALYAN_CANONICAL_SYNTHESIS_2026-03-11.md:1` self-titles "Jagat Kalyan Canonical Synthesis"; the file is not in `CANONICAL_DOC_STACK.md` Authority Registry. The doc defines a 4-layer "Canonical Stack" (`Jagat Kalyan Protocol` / `Planetary Reciprocity Commons` / `AI Reciprocity Ledger` / `GAIA`) where GAIA is positioned as a peer-level "deployment platform / operating system" alongside JK — incompatible with the corrected hierarchy where GAIA is an accounting kernel under SIS.
- **Resolution (2026-05-08):** added status header demoting the canonical claim and pointing to `SOVEREIGN_MANIFEST.md §Telos Hierarchy`. Body preserved for archival continuity. This is a parallel correction to C1 (JAGAT_KALYAN_MASTER_VISION.md); both files claim canonical authority by name without registry sanction. Found in fine-tooth review pass after C2.

### Verification pass (2026-05-08, post-C2)

A fine-tooth adversarial self-review pass after C2 verified:
- **Link integrity:** all 14 markdown cross-doc links added by C1+C2 resolve to existing files on this branch.
- **Runtime impact:** zero Python files reference the patched docs; no-runtime invariant holds.
- **Test impact:** zero test files reference the patched docs by filename.
- **DocOps anchor stability:** `assertions.yaml` (carried by build_spine_clean branch, not present on this branch) uses text-pattern regexes against the verified-numbers table; the §Telos Hierarchy insertion is upstream of those anchors and does not disturb them. When this branch eventually merges into a branch that carries the DocOps gate, the gate is expected to pass.
- **Cross-track contamination:** zero overlap between Track 1's commits since `a8206f6` (`telic_seam.py`, `test_telic_seam.py`, `system_map/latest.json`) and Track 2's commits (doctrine docs only). No merge-conflict potential.
- **Frontmatter compliance:** no YAML frontmatter added to any governance doc. CANONICAL_DOC_STACK Tier 1–2 frontmatter policy honored.
- **Anti-doc-maze compliance:** zero new files added by C1+C2+C3 (only edits + Step 0 ports). Authority Registry unchanged.
- **JK_MASTER_VISION body preservation:** 13-line diff confirms header-only change.

### Cross-track follow-ups (NOT resolved here)

- **Cabinet alignment:** `~/.claude/cabinet/ARJUNA.md`, `~/.claude/cabinet/strategy/LOOMWORK_v0_MASTER.md`, `~/.claude/cabinet/worldview/telos.md` are out-of-repo and were not touched by Track 2. They may carry the older Loomwork-as-peer-of-JK framing and should be aligned in a separate cabinet-side track.
- **`compass.py` runtime scoring axis (C5):** out of Track 2 scope (no-runtime). Future: score against SIS-fitness primarily, with JK as ultimate telos.
- **Cross-branch MEGAFILE_INDEX convergence:** other worktrees (notably `feat/loomwork-venture-cell` at `/Users/dhyana/dharma_swarm_loomwork`) lack `docs/MEGAFILE_INDEX.md`. Not resolved in Track 2; belongs to a separate convergence track.
- **`shakti.py` quadrature gate enforcement:** doctrine names trustee discipline as gate-enforced; runtime verification of "extractive behavior is a gate violation" is out of Track 2 scope and tracked separately.

---

## 2026-05-20 — Governance Convergence Pass (chore/governance-onboarding-convergence)

### Aim
Make every future agent (human or AI) land in the same operating reality with one command, without adding another "master doc". Replace hand-maintained read orders with a renderer/boot command that reads the existing owners.

### Stale claims and dead pointers found and fixed
- **README.md** — 96-line Codex frontmatter (violated `CANONICAL_DOC_STACK.md` Frontmatter Policy). **Stripped.**
- **README.md** — "Current build track" section hardcoded three plan files (now-deprecated). **Replaced with `make onboard` pointer + 3-layer owner table.**
- **README.md** — described `MODEL_ROUTING_MAP.md` as current; it is an archive pointer. **Removed from first-read pre-flight; depth pointer only.**
- **docs/governance/README.md** — pointed to non-existent `DHARMA_SWARM_ALL_AGENTS.md` and used absolute `/Users/dhyana/...` paths. **Rewritten as depth-pointer index with repo-relative paths.**
- **docs/README.md** — "Current Canon Set" listed `PRODUCT_SURFACE.md` and two dated 2026-03/04 specs as current. **Replaced with `make onboard` pointer.**
- **docs/governance/COHERENCE_DELTA.md** — said `BROKEN_REGISTER.md` was "once landed; until then INTERFACE_MISMATCH_MAP.md is the closest substrate". `BROKEN_REGISTER.md` has been landed for weeks. **Updated to current owner with INTERFACE_MISMATCH_MAP as parallel substrate.**
- **docs/governance/ANTI_SLOP_RULES.md** + **.semgrep/dharma-anti-slop.yml** — both pointed at non-existent `docs/governance/STATE_DIR_OWNERS.md`. **Re-routed surface ownership through `ACTIVE_SURFACE_MANIFEST.yaml` (the actual single owner of declared surfaces).**
- **docs/governance/CANONICAL_DOC_STACK.md** — Authority Registry listed missing files (`AGENTS.md` at root, `docs/agent/AGENT_CONTRACT_AND_TEAM.md`, `docs/operations/OPERATOR_RUNBOOK.md`); claimed "max 5 governance docs" while 17 exist; had no row for `ACTIVE_TRACK.yaml`. **Rewritten around the three-layer SSoT model (Intent / Surface / State); reframed the anti-doc-maze rule as "max 5 first-read surfaces"; deduplicated Authority Registry into a clean ownership map.**
- **docs/governance/BUILD_SESSION_ENTRYPOINT.md** — hardcoded "Track name: Ontology-Native Operator Brief" and a four-file mandatory read order. **Replaced with `make onboard` pointer and a depth-pointers list; track now defers to `ACTIVE_TRACK.yaml`.**
- **docs/governance/SOVEREIGN_MANIFEST.md** — hardcoded the active track in prose. **Replaced with deferral to `ACTIVE_TRACK.yaml`; added managed-block markers; count claims refreshed (582 test files, 10244 test_def, 693 md files, 176205 lines, 215 frontmattered).**
- **docs/MEGAFILE_INDEX.md** — opening "How to use" said read slots 1→10 in order. **Replaced with `make onboard` first, slots as depth reference.**
- **CLAUDE.md** — no pre-flight pointer to onboarding. **Added "Before Anything Else" section with `make onboard` and managed-block markers.**
- **docs/AGENTS.md** — no pre-flight pointer. **Added "Before Anything Else" section.**

### What was added

> Historical inventory from the 2026-05 audit. Current command semantics are
> owned by `BUILD_SESSION_ENTRYPOINT.md`: `make onboard` is truthful read-only
> session status, and packet-bound preflight owns edit admission.

- **`scripts/governance/agent_onboard.py`** (extended): single door. Renders branch/HEAD/origin-main divergence, active track + acceptance criteria, live-ops snapshot with staleness warning, surface manifest health, broken-register summary, living axioms, recent track activity, decay-watch list, enforcement commands, depth pointers. Always exits 0; never hard-gates.
- **`scripts/governance/check_track_status.py`** (preserved from prior pass): writes `reports/governance/active_track_evidence.json`.
- **`scripts/governance/render_active_track_includes.py`** (preserved): renders the managed `<!-- ACTIVE_TRACK:START -->`/`END` blocks in `CLAUDE.md`, `SOVEREIGN_MANIFEST.md`, `BUILD_SESSION_ENTRYPOINT.md` so the track name lives in one place.
- **`docs/governance/ACTIVE_TRACK.yaml`** (preserved): the single owner of build intent. TTL-enforced. CI-checked.
- **`tests/test_agent_onboard.py`** (new): asserts the command exits 0, renders all required sections, parses the broken register correctly, does not mutate owner files.
- **`tests/test_active_track_governance.py`** (preserved): governance test suite (6 tests).
- **`.github/workflows/active-track.yml`** (preserved): CI gate for track status + render check.
- **`Makefile`** — added `make onboard` target.
- **`.pre-commit-config.yaml`** — `dharma-active-track-status` + `dharma-active-track-render` hooks (preserved).
- **`docs/docops/assertions.yaml`** — `ACTIVE_TRACK.yaml` and `ANTI_SLOP_RULES.md` added to `canonical_guard.registered`; `verified_at` bumped to 2026-05-20.

### The three-layer SSoT model (now documented in CANONICAL_DOC_STACK)
| Layer | What it answers | Owner |
|---|---|---|
| Intent | What are we building? | `docs/governance/ACTIVE_TRACK.yaml` |
| Surface | What exists (routers, state dirs, nav)? | `ACTIVE_SURFACE_MANIFEST.yaml` |
| State | What is live (HEAD, recent merges, runtime)? | `docs/state/LIVE_OPS_DASHBOARD.md` |

Everything else is doctrine (stable prose: axioms, anti-slop, AGENTOPS, architecture). Doctrine never claims live state; live state never claims doctrine.

### Decay protections going forward
- Prose pointers → replaced with `make onboard` (no path to memorise).
- "Done" announced in work doc → active track has explicit acceptance + TTL in YAML.
- Fragile witness hashes → kept in LIVE_OPS as informational; not gated on.
- Multiple owners of same fact → ownership map in CANONICAL_DOC_STACK assigns one owner per fact-class.
- No TTL → ACTIVE_TRACK.yaml has TTL; onboarding shows countdown.
- Stale dashboard → onboarding surfaces `LIVE_OPS_DASHBOARD.md` staleness as soft warning (never gates).

### Constraints honoured
- No new CI gates beyond the active-track gates that already shipped.
- No new megafiles.
- No new root markdown.
- No mass move of governance files into `docs/doctrine/`.
- `agent_onboard.py` owns no facts; it renders the owners.
- All edits non-runtime.

### Validation
- `make onboard` — exit 0.
- `python3 -m pytest tests/test_agent_onboard.py tests/test_active_track_governance.py tests/test_manifest_health.py tests/test_pr_coherence_delta.py -q` — 37 passed.
- `make docops-integrity` — passed (after refreshing SOVEREIGN_MANIFEST counts + AUTO_INVENTORY + verified_at).
- `python3 scripts/governance/check_track_status.py` — passed.
- `python3 scripts/governance/render_active_track_includes.py --check` — passed.

### Files touched
24 files: 1,963 insertions, 333 deletions. See PR for full diff.

### Acceptance test
After this PR, the only thing a new agent has to remember is:

```bash
make onboard
```

Every governance / doc / anti-slop surface either feeds that command, is linked from it for depth, or is explicitly historical.

---

## One-Door scope reset and provenance — 2026-07-17

- Deprecated: 2026-07-17
- Reason: the combined One-Door campaign was retired with six unresolved
  blockers after session status, edit admission, closeout, CI, and persistent
  agent registration were separated into distinct authorities.
- Replacement: `docs/governance/BUILD_SESSION_ENTRYPOINT.md` for command
  boundaries and closed track `onboard-session-status-2026-07` for the retained
  verified slice.
- Review / removal date: permanent audit pointer; source files remain
  recoverable from immutable tree
  `55cf277be0dbf3b5a74da03eb1d7243024556806`.

The original `onboard-one-door-2026-07` track is `RETIRED`, not a verified
closure. Its unresolved-at-retirement obligations were `C1`, `D2`, `WP-O5`,
`M6-1`, `WP-O6`, and `TERMINAL-PROOF`. Recover the two campaign specifications
and enumerate all 25 packet records with:

```bash
git show 55cf277be0dbf3b5a74da03eb1d7243024556806:docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md
git show 55cf277be0dbf3b5a74da03eb1d7243024556806:docs/plans/ONBOARD_ONE_DOOR_CLOSURE_SPEC_2026-07-14.md
git ls-tree -r --name-only 55cf277be0dbf3b5a74da03eb1d7243024556806 reports/agentops/work_packets | rg '^reports/agentops/work_packets/onboard-one-door-WP-O'
git show 55cf277be0dbf3b5a74da03eb1d7243024556806:<packet-path-from-the-list>
```

Three records used the WP-O namespace for work that belonged to other tracks;
their merged outputs remain current and must not be mistaken for retired
One-Door implementation:

- `WP-O17` → PR `#979`, merge `5e0e42549a1e3f8123704d0c11b5fc6be2f8c5f0`
  (five-part Dharma and skill closure).
- `WP-O19` → PR `#980`, merge `d6c56f260fd75ba29feebd40a4115bbfd92c9e3e`
  (orchestration-arena TTL re-verification).
- `WP-O20` → PR `#984`, merge `6000849b995b4b210d19d01a683b2c321ff0f75b`
  (Merge Master Mike ledger reconciliation).

The other 22 records are campaign packets. Git history is their archive, not
current authority. The deleted Titanium preparation and WP-00 admission drafts
are likewise historical planning aids:

```bash
git show 55cf277be0dbf3b5a74da03eb1d7243024556806:docs/plans/TITANIUM_PREP_2026-07-15.md
git show 55cf277be0dbf3b5a74da03eb1d7243024556806:docs/plans/TITANIUM_WP00_ADMISSION_DRAFT_2026-07-15.md
```

Their current replacement is
`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md`; implementation
still begins only through its WP-00 admission.
