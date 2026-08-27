# SOVEREIGN MANIFEST: SYSTEM SOURCE OF TRUTH

**Purpose**: This document is the absolute ground truth for the dharma_swarm repository. All AI agents, regardless of model or tab, MUST ingest, comprehend, and adhere to this context before outputting a single line of code.

**Generated**: 2026-04-04 | Count refresh: 2026-06-09 filesystem verification
**Prior audit**: 2026-04-04 | 5-model convergent audit (Claude, DeepSeek, GPT-OSS, Codex, RUFLO)
**Authority**: This file + `CLAUDE.md` are the two canonical governance surfaces. When they conflict, `CLAUDE.md` wins on behavioral rules; this file wins on architectural truth.

**Verification method**: Count-sensitive claims below were refreshed against the filesystem on 2026-06-09. Architecture prose still reflects the 2026-04-04 audit unless specifically marked otherwise. Recheck counts before citing them in future work.

**Substrate-nativeness status**: The current runtime is ~10–15% ontology-native; ~85–90% of runtime work bypasses substrate. See [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) for the audit that established this estimate.

**Active build tracks**: declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. Do not duplicate track names in prose here — the YAML is the single source of intent. The repository-wide portfolio uses `track_policy.min_active..max_active` (current floor 1, ceiling 10); narrower authority is represented independently by `track_policy.scoped_wip_limits`. The operator's 2026-08-27 directive caps the `mac_build` admission scope at four lanes without freezing non-Mac work or claiming that a declared track is actually running on a host. Opening additional tracks beyond the floor is operator discretion, not automatic — each concurrent track must have a clear owner, distinct surfaces, and non-overlapping non-goals. A portfolio of one is fine — concurrency is authorized, not mandated — and equally, opening a second co-equal track when the operator proposes new work is the expected response, never a violation of an existing track. **To open a track** (e.g. when the operator proposes a new project — treat that as a new track, never a violation): add an entry under `active_tracks:` in `ACTIVE_TRACK.yaml` with `serves:` a spine objective, `owned_surfaces:`, acceptance criteria, and any applicable `admission_scopes`, then run `scripts/governance/render_active_track_includes.py`; `check_track_status.py` enforces global and scoped WIP limits, spine binding, surface non-overlap, and edge/cycle validity. Concurrency is gated on non-overlap and declared admission scope, not on agent count.

<!-- ACTIVE_TRACK:START -->

<!-- GENERATED — do not hand-edit.
     source-of-truth: docs/governance/ACTIVE_TRACK.yaml
     render: python3 scripts/governance/render_active_track_includes.py
     check:  python3 scripts/governance/render_active_track_includes.py --check
     checked by: .github/workflows/active-track.yml, make docops-integrity,
                 tests/test_active_track_governance.py
     newest track verified_at in source: 2026-08-27 -->

**Active portfolio — declared intent only:** 4 co-equal track(s) (WIP warn 5, max 10; scoped WIP: `mac_build` 4 active / max 4; model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned). This stamped digest carries track identity and surface ownership, NOT runtime truth and NOT full track detail (descriptions, next-items, non-goals stay in the YAML). Declared intent comes from `docs/governance/ACTIVE_TRACK.yaml`; evaluate it with `python3 scripts/governance/check_track_status.py`. Never answer runtime or liveness questions from this block or another prose copy. Admission scopes constrain declared build authority; they do not prove where a process is running.

**Spine objectives:** `substrate-nativeness`, `revenue-external-humans-served`, `research-depth` (each covered by at least one active track)

- **`fleet-advancement-2026-08`** — Fleet advancement — Fleet Hub, Mission Control, and HELM operator surfaces (ACTIVE, serves `substrate-nativeness`, verified 2026-08-27, open blocker items: 2)
  - owns: dharma_swarm/mission_control*.py, tests/test_mission_control.py, dashboard/src/app/dashboard/cockpit/**, dashboard/src/components/cockpit/**, dashboard/src/components/operator-coherence/v2/**, terminal/**, dharma_swarm/terminal_commands/surfaces.py, dharma_swarm/runtime_activity.py, dharma_swarm/operator_views.py, dharma_swarm/runtime_graph_views.py, dharma_swarm/runtime_platform_views.py, dharma_swarm/runtime_agent_server_views.py, dharma_swarm/operator_core/adapters.py, dharma_swarm/terminal_bridge.py, dharma_swarm/tui_helpers.py, tests/test_terminal_surfaces.py, tests/test_routing_surface_inventory.py, tests/test_runtime_activity.py, tests/test_operator_views.py, tests/test_runtime_graph_api.py, tests/test_operator_core_adapters.py, tests/test_tui_helpers.py, docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md, specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`sadhana-10-day-program-2026-08`** — SADHANA — governed 10-day program (ACTIVE, serves `revenue-external-humans-served`, verified 2026-08-27, open blocker items: 2)
  - owns: deploy/sadhana/**, scripts/runtime/sadhana_release.py, tests/test_sadhana_release.py, dashboard/src/app/dashboard/sadhana/**
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`rsi-lab-meghadharma-2026-08`** — RSI Lab — exact-code Mac and Meghadharma campaign lane (ACTIVE, serves `research-depth`, verified 2026-08-27, open blocker items: 1)
  - owns: dharma_swarm/forge_lab/**, scripts/forge_lab/**, tests/forge_lab_v1/**, docs/ops/RSI_LAB_SYNC.md
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`sublimation-forge-2026-08`** — Sublimation Forge — offline-first governed foundry (ACTIVE, serves `research-depth`, verified 2026-08-27, open blocker items: 2)
  - owns: dharma_swarm/foundry/**, scripts/foundry/**, tests/test_foundry_*.py, docs/foundry/**, dharma_swarm/rudra/**, dharma_swarm/terminal_commands/rudra.py, tests/test_rudra_*.py, tests/fixtures/rudra/**, reports/rudra/**, docs/plans/rudra_v0/**
  - admission scopes: mac_build (declared build authority; not runtime evidence)

Before editing any file, check it against the `owns:` globs above — a surface owned by a track you are not serving is off-limits except through that track's own next-items. Full track detail: `docs/governance/ACTIVE_TRACK.yaml`.

**Recently closed tracks:** `loop-closure-2026-06` (SUPERSEDED, closed 2026-08-27) · `orchestration-arena-v1-2026-06` (SUPERSEDED, closed 2026-08-27) · `merge-master-mike-d4-2026-06` (SUPERSEDED, closed 2026-08-27)

For machine-readable status, run `python3 scripts/governance/check_track_status.py` — it writes `reports/governance/active_track_evidence.md` (untracked; derived status is not committed). CI publishes the latest copy on the `generated/status` branch: `git show origin/generated/status:reports/governance/active_track_evidence.md`.

<!-- ACTIVE_TRACK:END -->

---

## Telos Hierarchy

This section is the registry-named owner of the highest invariant in the repository: **what the whole system is for, and how its objectives rank.** Per `docs/governance/CANONICAL_DOC_STACK.md`, this manifest owns axioms and invariants; the telos hierarchy is the invariant that every other doc's "why" is subordinate to. Downstream docs (`docs/vision_maps/NORTH_STAR.md`, `docs/doctrine/OPERATIONAL_DOCTRINE.md`, `docs/doctrine/LIVE_ROADMAP.md`, `docs/loomwork/**`, `docs/research/verified_nature_house/**`, `docs/MEGAFILE_INDEX.md`) carry the *why* and compressed pointers; when any of them disagrees with this section on the hierarchy, **this section wins.**

**Provenance:** this section was first landed 2026-05-08 (commit `7ecf285`, logged in `docs/governance/REPO_GOVERNANCE_AUDIT.md` §"2026-05-08 — Telos Hierarchy Correction", entries C1–C10). That commit's branch never merged to `main`, so the manifest lost the section it is registry-named to own while ~30 downstream docs kept deferring to it — a dangling top authority. The text below restores the section from its own authoritative downstream descriptions: the audit's C1–C10 resolutions and the compressed hierarchy carried in `docs/doctrine/OPERATIONAL_DOCTRINE.md:9-24`. No new doctrine is introduced here; this is a recovery of the ratified invariant into the file that owns it.

### The hierarchy

```
Jagat Kalyan (JK) — highest telos: welfare / salvation of the world on every level
│                    (mental, spiritual, ecological, economic, focus, health,
│                     people finding their highest calling, harmonizing AI,
│                     human spirit, and nature — JK at full resolution)
│
├── DOMAINS — what we work on
│   ├── Silicon Is Sand (SIS) — the material-body domain objective
│   │   ├── GAIA / Reciprocity — accounting kernel under SIS
│   │   └── Loomwork — evidence-weaving / media organ under SIS
│   └── Attention Emancipation (AE) — separate JK-level domain, UNRESOLVED / not yet typed
│
└── METABOLISM — how we sustain the work
    └── Shakti Ginko — wealth-metabolism organ under JK directly

Dharma Swarm = the self-evolving VSM/cybernetic organism (S1–S5 + Kaizen + DGM)
               that enacts all of the above. It is the body, not a layer of the telos.
```

### Layer definitions

- **Jagat Kalyan (JK)** — the highest telos: universal welfare, the salvation of the world on every level. Everything below is a means to JK; nothing outranks it. Stated at full resolution in `docs/vision_maps/NORTH_STAR.md:12-16`.

- **Dharma Swarm (the organism)** — the self-evolving VSM/cybernetic organism that *enacts* the hierarchy. It has S1–S5 anatomy (operations, coordination, control, intelligence, identity) plus Kaizen and DGM (Darwin–Gödel Machine) learning loops (`docs/doctrine/OPERATIONAL_DOCTRINE.md:30`). It is the body serving JK — **not** itself a domain or objective within the telos. Recursion, self-narration, and "papers about our own architecture" are the named anti-pattern (the Mirror Experiment / world-zero), not a telos (`docs/doctrine/OPERATIONAL_DOCTRINE.md:43`).

- **Silicon Is Sand (SIS)** — a JK-level **domain objective**: material-body recognition covering the full material cost of compute — **energy, water, chips, minerals, fabs, labor, land, emissions, e-waste** (audit C3). SIS is the parent objective layer between JK and its accounting/media organs; it is not merely an adjective.

- **GAIA / Reciprocity** — the **accounting kernel under SIS** (the welfare-ton ecological-restoration / carbon-attribution loop). GAIA is **not** a peer-level "deployment platform / operating system" alongside JK; it is a kernel *under* SIS that pays the material debt SIS names (audit C2, C10).

- **Loomwork** — the **evidence-weaving / media organ under SIS**: ecological/material pattern surfacing (casefiles, alerts, maps, briefs, action intelligence for journalists, NGOs, regulators, citizens). Loomwork is a **domain organ under SIS**, **not** a peer of Shakti Ginko (audit C4). Current build status is DESIGN_ONLY (`docs/vision_maps/NORTH_STAR.md` §7). Note the owner boundary: **noosphere propagation is assigned to Darshan / SAB** (`docs/vision_maps/NORTH_STAR.md` §6), not to Loomwork.

- **Attention Emancipation (AE)** — a **separate JK-level domain**, marked **UNRESOLVED / not yet typed** (audit C6). Anti-collapse guard: **AE is not SIS, not productivity tooling, and not generic focus work.** It is named here so it is not silently folded into another domain, but it carries no typed structure yet.

- **Shakti Ginko** — the **wealth-metabolism organ under JK directly**, at peer *priority* to SIS but in a categorically distinct *position* (metabolism vs. domain) (audit C7). Function: **wealth-generation by all means possible**, in service of funding every other domain. Discipline: **trustee, not possessor** — internal trustee discipline is gate-enforced (`shakti.py` quadrature); outward function is unconstrained. Source authority: Sri Aurobindo, *The Mother*, Ch. IV.

### Conditions of consistency (binding on downstream docs)

1. **JK is the ceiling.** No doc may position any domain, organ, or the organism itself as peer to or above Jagat Kalyan.
2. **SIS is a domain; Shakti Ginko is metabolism.** They may share priority but are never the same category. Do not collapse metabolism into domain or vice versa.
3. **Loomwork is a child of SIS**, not a peer of Shakti Ginko. Any doc framing them as peers is superseded by this section.
4. **GAIA is an accounting kernel under SIS**, not a peer-platform of JK.
5. **AE stays separate and unresolved** until explicitly typed; it must not be collapsed into SIS, productivity tooling, or generic focus work.
6. **Runtime scoring** (e.g. Loomwork's CompassRoom / `compass.py`) should score candidates against **SIS-fitness primarily, with JK as the ultimate telos** — not JK-fitness directly (audit C5, tracked as drift).
7. **The organism is the body, not the telos.** Self-referential work that no external human transacts through is the named anti-pattern, not an objective.

Operational grounding: `dharma_swarm/ontology.py:1-30` declares "Palantir built this pattern for supply chains and kill chains. We take the engineering and reforge it for Jagat Kalyan." This hierarchy is the constitutional statement of that reforging.

---

## GLOBAL AXIOMS

These are immutable engineering laws for this repository. Violation = architectural regression.

### A1: NO FLAT-PACKAGE GROWTH
The `dharma_swarm/` package currently has **389 files at its top level (58.7% of 663 total Python modules)** (V). No new .py file may be added to the top level. New modules must go into an appropriate subdirectory. Existing top-level files will be organized over time.

### A2: NO DUPLICATE IMPLEMENTATIONS
Before creating a new file for routing, bridging, adapting, or orchestrating, check if one already exists. The repo currently has **37 bridge files** (V), **3 model_routing copies** (2 are identical, 1 is different) (V), **4 orchestrators** (V), **29 adapter files** (V), and **19 router files** (V). Do not add more without deprecating an existing one.

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
All numerical claims in docs become stale within weeks. Before citing module counts, test counts, or line counts from any doc (including this one), verify against the actual filesystem. See `REPO_GOVERNANCE_AUDIT.md` for the current staleness log. The current DocOps inventory reports **405 Markdown files containing at least one reserved trust-language term** (V). Treat these as authority-scope review candidates, not confirmed repo-wide authority.

### A7: NO CIRCULAR IMPORTS
The repo has **9 verified circular dependency chains** (V). The worst:
1. **6-module evolution cycle** (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) -- has direct module-level imports
2. **4-module routing cycle** (router_v1 → provider_policy → smart_router → router_v1) -- mitigated by TYPE_CHECKING
3. **api ↔ dharma_swarm bidirectional** -- api imports dharma_swarm at module level; dharma_swarm imports api lazily

All 9 cycles were independently confirmed with exact import lines. Most are mitigated by lazy imports but remain architectural debt. **New code must not create circular imports.**

### A8: FRONTMATTER DISCIPLINE
Do not inject machine-readable YAML frontmatter into governance or architecture docs unless explicitly requested. Current state: **219 of 894 Markdown files start with YAML frontmatter; 15 of 43 docs/architecture Markdown files do so** (V). Long frontmatter remains an authority/noise risk even when the prose is useful.

---

## VERIFIED NUMBERS (2026-08-01 COUNT REFRESH)

These are the ground-truth metrics. All other documents citing different numbers are stale.
One row per metric — refreshes REPLACE this table (never append; the 2026-06/07
append-style refreshes quadruplicated rows and broke `make docops-integrity`).

| Metric | Value | Verification |
|--------|-------|-------------|
| Total Python modules | **1,129** | git ls-files dharma_swarm \| rg '\.py$' \| wc -l |
| Top-level (flat) modules | **491 (44.4%)** | git ls-files dharma_swarm \| rg '^dharma_swarm/[^/]+\.py$' \| wc -l |
| Total Python LOC | **398,860** | wc -l across dharma_swarm Python modules |
| Test files | **1020** | git ls-files tests \| rg '\.py$' \| wc -l |
| Test functions | **15,594 `def test_` occurrences under tests/** | rg "def test_" tests |
| Tests collected (pytest) | **12,885 (measured 2026-07-10, cloud checkout)** | python3 -m pytest tests/ --collect-only -q |
| Collection errors | **35 (measured 2026-07-10, cloud checkout — env-dependent optional extras; 0 on the operator host 2026-07-03)** | python3 -m pytest tests/ --collect-only -q |
| Markdown files | **1,534** | git ls-files \| rg '\.md$' \| wc -l (excl. AGENTS.md, reports/docops) |
| Markdown total lines | **320,594** | wc -l across all tracked .md |
| Bridge files | **37** | find dharma_swarm -name "*bridge*.py" -type f |
| Adapter files | **50** | find dharma_swarm -type f \| rg -i "adapter" |
| Router files | **23** | find dharma_swarm -type f \| rg -i "rout" |

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
- **Named operator role (merge authority)**: **Merge Master Mike (MMM)** is the registered conditional-merge coordinator agent for this domain. Charter: [`MMM_CHARTER.md`](MMM_CHARTER.md). Operational manual: [`../ops/PR_REVIEW_CONTROL.md`](../ops/PR_REVIEW_CONTROL.md). Registration: [`../../examples/agents/merge_master_mike.registration.json`](../../examples/agents/merge_master_mike.registration.json).

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

**37 bridge files** (V), **13,299 total LOC**:

| Bridge | Lines | Importers | Status |
|--------|-------|-----------|--------|
| terminal_bridge.py | 2,539 | 2 | ALIVE |
| operator_bridge.py | 1,819 | 15 | ALIVE |
| vault_bridge.py | 885 | 2 | ALIVE |
| bridge_registry.py | 842 | 15 | ALIVE (infra) |
| bridge.py | 583 | 78 | ALIVE (core) |
| semantic_memory_bridge.py | 518 | 2 | ALIVE |
| world_radar/go_bridge.py | 457 | 2 | ALIVE |
| bridge_coordinator.py | 450 | 3 | ALIVE (infra) |
| instinct_bridge.py | 377 | 4 | ALIVE |
| fractal/room_bridge.py | 490 | 2 | ALIVE |
| trishula_bridge.py | 347 | 1 | STALE |
| session_event_bridge.py | 311 | 2 | ALIVE |
| a2a/a2a_bridge.py | 310 | 2 | ALIVE |
| review_bridge.py | 224 | 4 | ALIVE |
| roaming_operator_bridge.py | 202 | 3 | ALIVE (boundary violation) |
| skill_bridge.py | 202 | 2 | ALIVE |
| optimizer_bridge.py | 191 | 8 | ALIVE |
| ecosystem_bridge.py | 170 | 3 | ALIVE |
| revenue/telic_bridge.py | 340 | 3 | ALIVE |
| operator_core/go_github_bridge.py | 198 | 1 | ALIVE |
| operator_core/go_evidence_bridge.py | 113 | 1 | ALIVE |
| operator_core/world_radar/receipt_bridge.py | 248 | 2 | INCUBATING |
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

### Forge / Pudgala Naming Boundary
- **Dharma Forge** names the whole-swarm evolution, benchmark, external-receipt,
  candidate-control, Hydra, and arena family.
- **Pudgala Autopoiesis Protostar** names the anti-slop governance mechanism for
  graded claim/evidence binding, `min_evidence_grade` floors,
  `VerifiedMachineReceipt` chains, oracle-independence downgrades, and advisory
  quality gates.
- Do not use Forge names for anti-slop governance mechanisms. Historical
  receipts may preserve old branch names, but live docs and tracked surfaces
  must use the boundary above.

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
| "17 bridge files" / "19 bridge files" (self-contradicting) | **37 bridge files** (V) |
| "16 TUI test errors" | **16 total errors: 10 numpy, 2 textual, 1 typer, 1 pytest_asyncio, 1 yaml, 1 tui.app** -- only 3 are TUI-specific (V) |
| "10 pillars" with "PILLAR_04 missing, PILLAR_11 present" | **10 pillar files exist** (PILLAR_01-03, 05-11; PILLAR_04 never created). Sparse numbering, not 11. (V) |
| "router_v1.py is LEGACY" | **router_v1.py is ALIVE** -- actively used by providers.py for signal generation (V) |
| "18 provider classes" (VIVEKA) | **19 classes** (including abstract LLMProvider base); **18 ProviderType enum values** (V) |
| "engine/ is legacy duplicate of tui/engine/" | **Both are ALIVE** -- engine/ has 41 importers, tui/engine/ has 31 importers. Different purposes. (V) |
| Bridge count of "30" (Phase 3A) | **37 actual bridge files** -- the "30" counted test files and non-bridge files with "bridge" in name (V) |

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
- No mention of the 17 bridges, 13 routers, 16 adapters, or their hierarchy
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
