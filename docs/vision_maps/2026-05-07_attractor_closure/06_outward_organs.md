# 06 — Outward Organs

**Read-only research, file:line cited. UNKNOWN where unmeasurable.**
**Anchor question:** Do new VentureCells inherit the spine, or run as siblings that bypass it?

---

## 1. Organ Inventory

| Organ | Code path | Status | External surface | First user |
|---|---|---|---|---|
| Loomwork (named arm) | `~/.claude/cabinet/strategy/LOOMWORK_v0_MASTER.md` (LOCKED 2026-05-07); design at `~/.claude/cabinet/strategy/2026-05-07-loomwork-design.md` | Aspirational — design only; target dir `dharma_swarm/loomwork/` does not exist (verified `ls dharma_swarm/loomwork → no such file`) | Planned local Astro at `localhost:4321`; public deferred to v1 (design.md:101-110) | None — Day 1 of 14-day ship not yet begun |
| `wiki_loom` package (vertical slice) | `dharma_swarm/dharma_swarm/wiki_loom/` (`atomizer.py` 138 LOC, `linker.py` 44 LOC, `publisher.py` 70 LOC, `revelation.py` 90 LOC) | Scaffolded (partial). 4 modules are real; `algedonic.py`, `pattern.py`, `scout.py`, `witness_gate.py` are 1-line stubs (Read returned "shorter than offset (1)" for all four) | Filesystem only via `LoomPublisher.publish` writes `.md` to caller-supplied `output_dir` (publisher.py:46-55). No HTTP/CLI/site. | None invoking from cron or API; only test harness (no caller in `api/`, no caller in `cron_runner.py` for wiki_loom verified by grep — only self-imports inside `wiki_loom/__init__.py`) |
| Operator Brief / Daily Insight Brief | `dharma_swarm/dharma_swarm/insight_brief.py` (384 LOC) | Live — cron `ontology_insight_brief` ran 2026-05-06 20:31 with `last_status: ok` (`~/.dharma/cron/jobs.json:122-145`) | Markdown files at `/Users/dhyana/dharma_briefs/<date>-brief.md` (8 dated briefs verified, latest 2026-05-07-brief.md) | Dhyana (read-only consumer); `audience: "dhyana"` hardcoded at insight_brief.py:109 |
| Shakti Ginko VentureCell (financial arm) | `dharma_swarm/dharma_swarm/ginko_orchestrator.py` (975 LOC); cell created via `ontology.py:2194-2227 create_ginko_cell` | Scaffolded — only 1 of 17 ginko modules touches ontology (prior observation 1113 May 1); orchestrator state file written but no cron job for ginko found in `~/.dharma/cron/jobs.json` | CLI/state at `~/.dharma/ginko/ginko_state.json` (ginko_orchestrator.py:57); dashboard route exists `dashboard/src/app/dashboard/` (no specific ginko route in tree) | None confirmed — autonomy_stage 1 (research-only); `revenue_usd: target=0, current=0` (ontology.py:2219) |
| Opportunity Loop (Refill→Dispatcher→Board) | `dharma_swarm/dharma_swarm/opportunity_refill.py` (245 LOC), `opportunity_dispatcher.py` (962 LOC), `opportunity_dispatcher_observer.py` (610 LOC), `shakti_executive/executive.py` (192 LOC), `curriculum_engine.py` (269 LOC) | Live — cron handlers `frontier_dispatcher` (30m) and `frontier_refill` (daily 04:30) registered (opportunity_refill.py:18-21); `cron_runner.py:455,491` imports `ShaktiExecutive` and dispatcher | None external — internal `~/.dharma/meta/opportunity_board.json`, `~/.dharma/meta/frontier_tasks_pending.jsonl`, `~/.dharma/db/tasks.db` | Internal swarm orchestrator only |
| Jagat Kalyan Engine | `dharma_swarm/dharma_swarm/jagat_kalyan.py` (281 LOC); + `jk_credibility_gates.py` (417 LOC), `jk_subteams.py` (237 LOC), `jk_stigmergy_seeds.py` (188 LOC) | Mostly scaffolded — `jk_stigmergy_seeds.py:11` self-declares "currently archived/unused. It is not imported by any other module"; `jagat_kalyan.py` is hard-coded `WORLD_DOMAINS` + prompt builder, no live consumer found | None external. Persists `jagat_kalyan_proposals.jsonl` (jagat_kalyan.py:236, 261) | UNKNOWN — observation 2173 May 4 says "core vision has zero importers" |
| Cron-driven outward pulses | `~/.dharma/cron/jobs.json` jobs `planetary-reciprocity-pulse`, `planetary-reciprocity-cultivation`, `telos-mission-scout` | Failing — all three `last_status: error`, error: `unattended Claude bare mode requires ANTHROPIC_API_KEY` (jobs.json: pulse, cultivation, telos-scout entries) | Writes to `~/.dharma/shared/planetary_reciprocity_pulse.md`, `planetary_reciprocity_garden.md`, `telos_mission_scout.md` | Not delivering — job count `completed: 64/16/32` runs but every recent run errored |
| API surface | `dharma_swarm/api/main.py:264-282` registers 16 routers | Live — `health, agents, evolution, ontology, lineage, stigmergy, commands, modules, dashboard_new, telemetry, routing, graphql, verify, hypernodes, chat, chat_ws` | localhost FastAPI on port 8000/8420 (CLAUDE.md says 8420). No `loomwork`, `jagat_kalyan`, `opportunity`, `gaia`, `insight_brief`, `wiki_loom` router (verified by grep — only `graphql_router.py:86,263-264` references `~/.dharma/ginko/agents`) | Dashboard frontend |
| Dashboard (Next.js) | `dharma_swarm/dashboard/src/app/dashboard/` | Live — 24 sub-routes (`agents/`, `audit/`, `blocks/`, `command-post/`, `ecosystem/`, `eval/`, `evolution/`, `gates/`, `glm5/`, `hypernodes/`, `lineage/`, `log/`, `models/`, `modules/`, `observatory/`, `ontology/`, `qwen35/`, `runtime/`, `stigmergy/`, `synthesizer/`, `tasks/`, `telemetry/`, `timeline/`, `workflows/`) | Browser at npm dev port | Operator (Dhyana). NO route for ginko/jagat/loomwork/insight_brief/opportunity. |
| `welfare_ton_mrv/` | `dharma_swarm/dharma_swarm/welfare_ton_mrv/` | Empty — `__pycache__` only, no `.py` source files (verified `ls`) | None | None |
| GAIA Platform | `dharma_swarm/dharma_swarm/gaia_platform.py` (1016 LOC), `gaia_ledger.py` (681 LOC), `gaia_fitness.py` (265 LOC) | Scaffolded — has CLI scaffold (`argparse` import gaia_platform.py:12); imported by `swarm.py:2764-65`, `evolution.py:1780-81`, `scripts/gaia_demo.py:25,36-37`. No cron job. | CLI render and ledger files. No web surface, no public API route. | UNKNOWN runtime user — only swarm/evolution/demo importers |

---

## 2. Spine-Attachment Audit

Legend: ✓ = file:line attachment found; ✗ BYPASS = no measurable attachment; ? = aspirational/declared in design but not in code.

| Organ | dharma_kernel | telos_gates | witness (~/.dharma/witness/) | ontology (ObjectDef) | VSM channels | identity TCS | stigmergy | signal_bus / message_bus |
|---|---|---|---|---|---|---|---|---|
| **wiki_loom** (code) | ✗ BYPASS — no kernel import in any of 4 real modules | ✗ BYPASS — no `telos_gates`/`check_action` import | ✗ BYPASS for filesystem witness; uses **ontology** `WitnessLog` object instead (revelation.py:35-45, linker.py:24-43, atomizer.py:122). No write to `~/.dharma/witness/loomwork/` (witness dir listing has no `loomwork/` subdir) | ✓ via `OntologyActionGateway` (revelation.py:10, linker.py:9-11, publisher.py:9-13). Uses existing types `KnowledgeArtifact`, `WitnessLog`, `Outcome`, `Signal`. No new `Revelation`/`Pattern`/`WorldEvent` ObjectDef registered. | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS — no `leave_stigmergic_mark` call | ✗ BYPASS — no `signal_bus` import; `algedonic.py` is empty stub |
| **Loomwork (design)** | ? declared "Boot-time kernel signature verify" (design.md:91, contract 1) — NOT IMPLEMENTED (no `dharma_swarm/loomwork/` dir) | ? declared "Register publication gates as GateProposals" (design.md:92, contract 2) — NOT IMPLEMENTED | ? declared "Witness every decision to `~/.dharma/witness/loomwork/<YYYY-MM-DD>.jsonl`" (design.md:93, contract 3) — `ls ~/.dharma/witness/` confirms NO `loomwork/` subdir | ? declared OntologyObj subtypes for each atom kind (design.md:71-83) — NOT IMPLEMENTED | ? declared "VSM S1-S5 per room" (design.md:96, contract 6) — NOT IMPLEMENTED | ? declared "Surface TCS to IdentityMonitor" (design.md:95, contract 5) — NOT IMPLEMENTED | ? not declared in 7 contracts | ? declared via `SIGNAL_LOOM_REVELATION_PROPOSED` (design.md:66) — NOT IMPLEMENTED |
| **insight_brief** | ✗ BYPASS | ✗ BYPASS — no direct gate check (delegates to OntologyActionGateway action gates only) | ✗ BYPASS for filesystem; uses ontology `WitnessLog` (insight_brief.py:88-98) | ✓ creates `WitnessLog` + `KnowledgeArtifact` via `gateway.create_object_or_fail` (insight_brief.py:88, 99) | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **Shakti Ginko (orchestrator)** | ✗ BYPASS | ✗ BYPASS — only doc-string mentions "AHIMSA, SATYA, REVERSIBILITY" (ginko_orchestrator.py:14); no `check_action` call grep-verified | ✗ BYPASS — no write to `~/.dharma/witness/`; only `~/.dharma/ginko/ginko_state.json` (ginko_orchestrator.py:56-57) | ✓ as ObjectDef VentureCell (ontology.py:1875-1913); ✓ instantiated via `create_ginko_cell` (ontology.py:2194-2227); orchestrator imports nothing from ontology.py beyond ginko_brier/ginko_data/ginko_regime/ginko_signals (ginko_orchestrator.py:33-52) — orchestrator does NOT touch the ontology obj | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **opportunity_dispatcher** | ✗ BYPASS | ✓ `from dharma_swarm.telos_gates import check_action` (opportunity_dispatcher.py:390) and `_gate_check` wraps it (opportunity_dispatcher.py:385-408) | ✓ writes `~/.dharma/witness/<date>/dispatcher_review_warn.jsonl` (opportunity_dispatcher.py:114, 411-430) | ✓ delegates Outcome+ValueEvent+Contribution to existing TelicSeam at `agent_runner.py:2680, 2810` (cited dispatcher.py:70). Does NOT create them itself — explicit "MUST NOT duplicate" (opportunity_dispatcher.py:16) | ✗ BYPASS | ✗ BYPASS | ✓ `from dharma_swarm.stigmergy import leave_stigmergic_mark` (opportunity_dispatcher.py:463); marks `channel="strategy"` (line 474) | ✗ BYPASS — uses `task_board.create` instead (opportunity_dispatcher.py:64, 116) |
| **opportunity_refill** | ✗ BYPASS | ✗ BYPASS (relies on dispatcher downstream) | ✗ BYPASS | ✓ via `CurriculumEngine` produces `FrontierTask` rows; metadata only, not ontology objects (curriculum_engine.py:25-36) | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **shakti_executive** | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS — writes JSON board, not ontology (executive.py:28, 133-141) | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **jagat_kalyan** | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS — persists `~/.dharma/jagat_kalyan_proposals.jsonl` only (jagat_kalyan.py:236, 261) | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **jk_credibility_gates** | ✗ BYPASS | ✗ BYPASS — comment "These are NOT telos gates" (jk_credibility_gates.py:6-9). Defines parallel gate enum `GateID` and `Verdict` | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **jk_subteams** | ✗ BYPASS | partial — `gate: str  # which telos gate governs` is a string label only, not an enforcement (jk_subteams.py:28); no `check_action` import | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✓ via `stigmergy_channel` field (jk_subteams.py:33, 62) — but data only, no caller wires it to StigmergyStore | ✗ BYPASS |
| **jk_stigmergy_seeds** | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✓ imports `from dharma_swarm.stigmergy import StigmergyStore, StigmergicMark` (jk_stigmergy_seeds.py:27); but module SELF-DECLARES "currently archived/unused. It is not imported by any other module" (line 11) | ✗ BYPASS |
| **gaia_ledger** | ✗ BYPASS | ✗ BYPASS — comment "Integrates with: telos_gates.py: AHIMSA (no harm), SATYA (no greenwashing)" (gaia_ledger.py:10-11) but no `import` of `telos_gates` in this file | ✗ BYPASS | ✗ BYPASS — uses Pydantic models, not ontology.ObjectDef | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **gaia_fitness** | ✗ BYPASS | ✓ `from dharma_swarm.telos_gates import GateDecision, TelosGatekeeper` (gaia_fitness.py:27) | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |
| **gaia_platform** | ✗ BYPASS | partial via gaia_fitness | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS | ✗ BYPASS |

**Tally:** 0 organs with full 8-surface attachment. 1 organ (`opportunity_dispatcher`) with 4-of-8 (telos_gates, witness, ontology-via-TelicSeam, stigmergy). All others 0–2 of 8.

---

## 3. VentureCell Pattern

ObjectDef quoted from `ontology.py:1875-1913`:

```python
_VENTURE_CELL = ObjectType(
    name="VentureCell",
    description="Fractal project container — first-class ontology object with its own agents, budgets, KPIs",
    properties={
        "name": ..., "description": ..., "domain": ENUM[research|engineering|product|infrastructure|governance|community|economic],
        "autonomy_stage": INTEGER (1=research-only → 5=mostly autonomous),
        "status": ENUM[incubating|active|mature|divesting|archived],
        "budget_tokens": INTEGER, "kpis": DICT,
    },
    actions=[
        ActionDef(name="Create", telos_gates=["AHIMSA", "SATYA", "REVERSIBILITY"]),
        ActionDef(name="Advance", modifies=["autonomy_stage"], telos_gates=["SVABHAAVA"]),
    ],
    security=SecurityPolicy(create_roles=["orchestrator", "system"], telos_required=True, audit_all=True),
    telos_alignment=0.95, shakti_energy=ShaktiEnergy.MAHALAKSHMI,
)
```

Shakti Ginko bootstrap `ontology.py:2194-2227`:

```python
def create_ginko_cell(registry: OntologyRegistry) -> OntologyObj:
    obj, errors = registry.create_object(
        "VentureCell",
        properties={
            "name": "Shakti Ginko",
            "description": "Autonomous economic engine — market intelligence, Brier-scored predictions, signal generation, paper trading. ...",
            "domain": "economic",
            "autonomy_stage": 1,
            "status": "incubating",
            "budget_tokens": 0,
            "kpis": {"brier_score": {"target": 0.125, ...}, "sharpe_ratio": {...}, "max_drawdown": {...},
                     "prediction_count": {"target": 500, "current": 0},
                     "revenue_usd": {"target": 0, "current": 0}},
        }, created_by="system")
```

**Verdict on "true generative pattern vs label":** Partial pattern, mostly label.

- **What is generative:** `VentureCell` ObjectDef declares `telos_required=True`, `audit_all=True`, gated `Create`/`Advance` actions, and metabolic-loop links (`belongs_to_cell`, `cell_has_agent`, `cell_has_thread`, `has_value_event`, `has_contribution`) at ontology.py:1937-1957. Any new cell created through the registry path inherits these constraints automatically.
- **What is label-only:** The orchestrator (`ginko_orchestrator.py`) does not `import` ontology — it operates on its own `GinkoState` dataclass and `~/.dharma/ginko/ginko_state.json`. The cell-as-ontology-object and the cell-as-running-process are not the same artifact. Creating a `LoomworkVentureCell` in the registry does NOT automatically create a Loomwork loop or a Loomwork agent pool — that wiring is per-organ bespoke (verified: no `register` or `subclass` mechanism in ontology.py:1875-1913 that emits running-code). 
- **Inheritance audit:** Prior observation 2373 (May 4) confirms "VentureCell IS Partially Implemented (Not Narrative-Only)." Yes for the type definition; no for the runtime polymorphism.

So when the design says "VentureCells deployed later should be more powerful than VentureCells deployed earlier," the **ontology object** does inherit invariants (telos gates, audit, links). The **running organ** does not — each new cell re-derives its own loop, state file, and adapters from scratch (Ginko's 17 modules vs Loomwork's planned 30+ modules).

---

## 4. Loomwork Spine Attachment

Loomwork is the **named primary outward arm** per `LOOMWORK_v0_MASTER.md:6,16`: "First autonomously-generated, witness-gated, cited, cross-pollinated revelation published to a public URL by 2026-05-21."

**Where wired (planned):**
- Branch `feat/loomwork-venture-cell` off `dharma_swarm_truth_spine` (design.md:113); CURRENT repo `~/dharma_swarm/` does NOT contain `dharma_swarm/loomwork/` (verified `ls`).
- `dharma_swarm/orchestrate_live.py` add `run_loomwork_loop` as 9th concurrent loop (LOOMWORK_v0_MASTER.md:41, design.md:180); current `orchestrate_live.py` shows zero `loomwork|venture_cell` references (grep returned empty).
- `dharma_swarm/telos_substrate.py` register `LoomworkVentureCell` (design.md:181); current `telos_substrate.py` only references "telos_substrate" itself (lines 30, 4148, 4351, 4460-4461) — no `LoomworkVentureCell` symbol.
- The vertical slice `dharma_swarm/wiki_loom/` exists but is partial (4 stub files, 4 real files) and does NOT attach to the spine in 6 of 8 audited surfaces (see Section 2).

**The 7 spine contracts (quoted from `2026-05-07-loomwork-design.md:87-97`):**

> 1. **Boot-time kernel signature verify** — Loomwork imports `DharmaKernel.verify()` at module load; refuses to start if any axiom signature is invalid.
> 2. **Register publication gates as GateProposals** — the 7 Loomwork-specific gates ... register with `TelosGatekeeper` as `GateProposal` instances for S5 approval before going live.
> 3. **Witness every decision** to `~/.dharma/witness/loomwork/<YYYY-MM-DD>.jsonl` — every promote, every retract, every self-modification, every revelation publication.
> 4. **Inject Foundations Corpus** into every agent via `context.read_foundations()` before LLM calls. Loomwork agents reason inside the 11-pillar frame, not raw.
> 5. **Surface TCS to IdentityMonitor** — Loomwork's Telos Coherence Score gets reported alongside Shakti Ginko's, visible in the daily_operating_brief.
> 6. **VSM S1-S5 per room** — each FractalRoom honors the Beer convention (operations, coordination, control, intelligence, identity).
> 7. **Multi-evaluator promotion** per the Transcendence Principle — promoting a `dot` to `revelation` requires ≥3 decorrelated evaluators ... Otherwise the Krogh-Vedelsby diversity term drops to zero and revelations become Brier-bad.

**Status:** All 7 contracts are non-implemented (no `dharma_swarm/loomwork/` directory exists; design itself notes "build base: `dharma_swarm_truth_spine` worktree, new branch `feat/loomwork-venture-cell`" — design.md:5, the work has not started in the inspected `~/dharma_swarm/` worktree).

---

## 5. Operator Brief Loop

**Path:** `insight_brief.py:72-80 propose()` reads `gateway.registry.get_objects_by_type("Outcome")`, sorts by `_outcome_score` (insight_brief.py:315-338) → `compose()` creates `WitnessLog` + `KnowledgeArtifact` ontology objects → `publish()` writes `<YYYY-MM-DD>-brief.md` to `output_dir` (default `~/dharma_briefs/`, insight_brief.py:67-68).

**Where the brief lands:** `/Users/dhyana/dharma_briefs/` — verified live: 8 files `2026-05-01-brief.md` through `2026-05-07-brief.md` plus `MASTER_SYNTHESIS_2026-05-01.md`.

**Who reads it:** `audience: "dhyana"` (insight_brief.py:109). No machine consumer found — grep shows no `import insight_brief` consumer downstream of brief publication; `cron_runner.py:240` only calls `build_and_publish_daily_brief` to generate it.

**Feedback loop:** **One-way emission, no closed loop.**
- Brief writes to filesystem and updates ontology object (`KnowledgeArtifact.published_path`, insight_brief.py:170-178). No row read by next-cycle behavior.
- Open Claims and Open Questions are surfaced (insight_brief.py:209-254) but are derived FROM ontology each run, not WRITTEN BACK based on brief consumption.
- No `signal_bus` emission, no `stigmergy` mark, no algedonic feedback.
- Prior observation 3680 (May 5): "AttractorPacket Not Yet Implemented — Prototype Already Exists in InsightBrief and Hypernode." The brief is shaped like an attractor packet but isn't wired as one.

**UNKNOWN:** whether Dhyana's reads cause behavior changes — that is human-in-the-loop, not measurable from code.

---

## 6. Opportunity Loop

**The chain (cited):**

1. **Shakti Executive** reads signals → produces ranked candidates (`shakti_executive/executive.py:42-46`: `signals = read_all_signals(...)` → `candidates = candidates_from_signals(signals)`).
2. Writes `~/.dharma/meta/opportunity_board.json` (executive.py:28, 133-141 atomic write).
3. **opportunity_refill** reads board (`opportunity_refill.py:79-95`), asks `CurriculumEngine.derive_from_opportunity_board` (curriculum_engine.py:41-66) to bootstrap each opportunity into 6 stages: `scope, validate, deep_research, capability, mvp, first_artifact` (curriculum_engine.py:15-22).
4. Appends rows to `~/.dharma/meta/frontier_tasks_pending.jsonl` (opportunity_refill.py:46, 98-100).
5. **opportunity_dispatcher** ticks every 30 min (opportunity_refill.py:19), reads pending JSONL, telos-gate-checks (opportunity_dispatcher.py:385-408), budget-checks (lines 438-451), creates `~/.dharma/campaigns/{opp_id}/manifest.json` (lines 56-59), and creates a row on `task_board.create` at `~/.dharma/db/tasks.db` (lines 63-64, 115-116).
6. Orchestrator + agent_runner pick up the row via the existing **Telic Seam** (cited at opportunity_dispatcher.py:68-70: `orchestrator.py:1722,1760` ActionProposal+GateDecision; `agent_runner.py:2680,2810` Outcome+ValueEvent+Contribution).
7. **The dispatcher_observer** scans campaign manifests for stage progress (opportunity_dispatcher_observer.py:42-48 stages, `update_stage` at line 22).

**Where the loop closes back to Shakti:**

- **It does not, in any direct read-Outcome-from-ontology path.** Grep of `shakti_executive/inputs.py` and `shakti_executive/scoring.py` for `Outcome|ValueEvent|opportunity_id|read_outcomes` returned only one hit: `scoring.py:97 opportunity_id=_stable_id(...)` (an outbound ID stamp, not an inbound feedback read).
- The executive `read_all_signals(self.state_dir)` reads from filesystem signal files (executive.py:42, defined in `shakti_executive/inputs.py`), not from `Outcome` rows produced by completed dispatched tasks.
- The dispatcher merges into `opportunity_board.json` via `_merge_board` (executive.py:110-130) which combines on `_entry_key` and re-sorts by `final_score` — but the score is computed from signals, not from outcome history.
- Prior observation 2701 (May 4): "Product-Revenue Loop Is Broken at Multiple Seams — opportunity_refill Calls Missing Method."

**Verdict:** The forward path Shakti→board→refill→dispatcher→TelicSeam→Outcome is wired. **The reverse path Outcome→Shakti is not wired** — Shakti always re-derives candidates from raw signals each run. Health/observer state is written (`opportunity_dispatcher.health.json`, opportunity_dispatcher_observer.py:28, 99-119), but Shakti does not read it.

---

## 7. Jagat Kalyan Surface

**Code presence:**
- `jagat_kalyan.py` (281 LOC): hardcoded `CAPABILITIES` block (lines 32-58), `WORLD_DOMAINS` 7-item list (lines 65-125), `PERPETUAL_QUESTION` template (lines 132-144), `JagatKalyanEngine.build_council_prompt` (lines 192-223), persists `~/.dharma/jagat_kalyan_proposals.jsonl` (lines 236, 261).
- `jk_credibility_gates.py` (417 LOC): parallel gate enum `GateID` with 13 gates across 5 layers (lines 32-54). Comment line 8: "These are NOT telos gates."
- `jk_subteams.py` (237 LOC): 6 named teams (`TRUTH_TEAM`, `STANDARDS_TEAM`, etc.) with `gate: str` and `stigmergy_channel: str` fields (data only, no caller).
- `jk_stigmergy_seeds.py` (188 LOC): `seed_critique_marks()` async function. Module SELF-declares "currently archived/unused. It is not imported by any other module in the codebase" (line 11).

**Live vs scaffolded:**
- LIVE: `jagat_kalyan.py` is importable; `JagatKalyanEngine` has filesystem persistence.
- SCAFFOLDED: subteams + credibility_gates + stigmergy_seeds are data structures and one-off seed scripts. Grep confirms no production caller.

**Cron job state (from `~/.dharma/cron/jobs.json`):**

| Job ID | Name | Schedule | last_run | last_status | completed |
|---|---|---|---|---|---|
| `791c3c31a434` | planetary-reciprocity-pulse | every 360m | 2026-05-06T23:14 | **error** ("unattended Claude bare mode requires ANTHROPIC_API_KEY") | 64 |
| `2ee814ca7584` | planetary-reciprocity-cultivation | every 1440m | 2026-05-06T09:02 | **error** (same) | 16 |
| `6bd981c18f7b` | telos-mission-scout | every 720m | 2026-05-06T15:29 | **error** (same) | 32 |
| `a2672f4bd0d1` | yatagarasu-flight | cron 0 */6 | 2026-05-07T00:00 | **error** (same) | 120 |
| `c14ac73e62bb` | doctor_assurance | every 360m | 2026-05-06T23:32 | **error** ("Doctor report status=FAIL") | 29 |
| `ontology_insight_brief` | Ontology-Native Insight Brief | cron 30 20 | 2026-05-06T20:31 | **ok** | 6 |

**Verdict on JK surface:** The only outward organ with a confirmed `ok` cron run today is `ontology_insight_brief`. The three explicitly Jagat-Kalyan-aligned jobs (planetary-reciprocity-pulse, planetary-reciprocity-cultivation, telos-mission-scout) have all been failing on every recent run with the same provider auth error. Per observation 2376 (May 4): "jagat_kalyan.py Has Hardcoded PERPETUAL_QUESTION Scanning 7 World Domains — System's Operational Telos Engine" — the engine exists at design level but is not delivering output through cron right now.

---

## 8. Where Organs Bypass Spine

Concrete cases observed:

1. **Shakti Ginko orchestrator → spine**: `ginko_orchestrator.py:33-52` imports `ginko_brier`, `ginko_data`, `ginko_regime`, `ginko_signals`, none of which import `dharma_kernel`, `telos_gates`, or `signal_bus`. State written to `~/.dharma/ginko/ginko_state.json` (line 57) bypasses both `ontology` and `~/.dharma/witness/`. **Bypassed:** kernel, telos_gates, witness-fs, vsm, identity, signal_bus, stigmergy. **Reason:** orchestrator was built standalone; the cell-as-ontology-object (created by `create_ginko_cell` ontology.py:2194) is never read or updated by the orchestrator.

2. **wiki_loom publish → public surface**: `publisher.py:48-55` calls `gateway.execute_action_or_fail("KnowledgeArtifact","Publish",...)` which goes through ontology gates, but writes the file unconditionally with no `~/.dharma/witness/loomwork/` JSONL companion. **Bypassed:** filesystem witness (covered partly by ontology WitnessLog, but the design.md:93 contract 3 explicitly requires the JSONL), VSM, identity, signal_bus, stigmergy.

3. **jagat_kalyan proposals**: `jagat_kalyan.py:259-274` `_persist()` appends directly to `~/.dharma/jagat_kalyan_proposals.jsonl` with no kernel verify, no telos gate, no ontology object, no witness. **Bypassed:** all 8 spine surfaces.

4. **jk_credibility_gates parallel ontology**: declares its own `GateID` enum and `Verdict` enum (jk_credibility_gates.py:25-54) explicitly distinct from `telos_gates.GateDecision`. **Bypassed:** telos_gates (intentionally — comment "These are NOT telos gates" at line 6).

5. **shakti_executive board write**: `executive.py:139-140` `tmp.write_text(json.dumps(rows...))` bypasses the ontology — the board is plain JSON, not `OpportunityCandidate` ObjectDef instances. **Bypassed:** ontology, witness, kernel, telos_gates, signal_bus, stigmergy.

6. **gaia_ledger**: doc-string at `gaia_ledger.py:10-11` claims "Integrates with: telos_gates.py: AHIMSA, SATYA" but the file imports zero telos_gates symbols (only the doc-string mentions them). **Bypassed:** telos_gates (docstring drift).

7. **Cron-driven outward pulses (planetary-reciprocity-*)**: jobs.json shows `handler: headless_prompt` writing markdown to `~/.dharma/shared/*.md`. No ontology object, no witness JSONL, no kernel verify in the path. **Bypassed:** kernel, telos_gates, ontology, witness JSONL (only writes a markdown).

8. **Dashboard/API surface**: `api/main.py:264-282` registers 16 routers, none of which expose `loomwork`, `jagat_kalyan`, `opportunity`, `gaia`, `insight_brief`, or `wiki_loom`. The outward organs are **not addressable from the operator surface** — they are reachable only via cron or CLI. **Bypassed:** the runtime nervous system that the dashboard is supposed to be.

---

## 9. Open Questions

1. **Cell-process polymorphism gap.** The `VentureCell` ObjectDef inherits ontology invariants (telos_gates, audit, links). The `VentureCell` running organ does not — Ginko orchestrator never imports the ontology object created by `create_ginko_cell`. How should a new cell's bootstrap function generate (or load) the running loop, agent pool, and state file from the ontology entry, so "VentureCells deployed later are more powerful" is mechanism rather than aspiration?

2. **Loomwork branch divergence.** Design says build on `dharma_swarm_truth_spine` worktree (design.md:5, 113-122) but the inspected `~/dharma_swarm/` has `wiki_loom/` already (partial). Is `wiki_loom/` the v0 vertical slice that will be replaced by `dharma_swarm/loomwork/` on the truth_spine branch, or is it the canonical implementation? Either way, the 7 spine contracts in design.md:87-97 are unmet by the current `wiki_loom/`.

3. **Spine contract enforcement absence.** No verifier asserts that a new organ implements all 7 contracts before going live. `opportunity_dispatcher` has 4-of-8 attachment; `wiki_loom` has 1-of-8; `jagat_kalyan` has 0-of-8. What is the gating mechanism that prevents a new organ from being merged with 0-of-8?

4. **Outcome→Shakti backflow.** The opportunity loop is forward-only: Shakti→board→tasks→Outcome. Shakti re-derives candidates from raw signals each run, never reading completed Outcome rows or success/failure history. Where does the closing edge live, or is this an explicit decision (Shakti is sense-organ-only, not learner)?

5. **Witness directory schema.** Insight brief uses ontology `WitnessLog` object; opportunity dispatcher uses `~/.dharma/witness/<date>/dispatcher_review_warn.jsonl`; Loomwork design specifies `~/.dharma/witness/loomwork/<YYYY-MM-DD>.jsonl`. Three patterns. Which is canonical, and is convergence required?

6. **JK credibility gates vs telos gates.** `jk_credibility_gates.py:6-9` explicitly says "These are NOT telos gates." But subteams have a `gate: str` field naming `SATYA`, `DHARMA`, etc. (jk_subteams.py:48, 74) — the named telos gates. Is JK using telos gates, evidence gates, or both, and how do they compose?

7. **Bare-mode cron failure mode.** Five cron jobs are in error state with `"unattended Claude bare mode requires ANTHROPIC_API_KEY"`. The system depends on these for outward organ execution but has no fallback to free-tier providers (despite `dharma_swarm/jagat_kalyan.py:33-49` capabilities claiming "free-first operation"). What is the recovery path?

8. **Welfare-ton MRV stub.** `dharma_swarm/welfare_ton_mrv/` contains `__pycache__/` only — no source. Is this an empty placeholder for a planned organ, or sources that were deleted? If planned, it would need to inherit spine attachment from day 1, not be retrofitted later.

---

*End of 06_outward_organs.md*
