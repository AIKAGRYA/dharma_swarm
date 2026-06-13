# AI Company Operator — Grounding Citation Pack (2026-06-12)

**Role:** research artifact (spec-forge intake input for the ai-company-operator track).
**Method:** readonly explorer subagent over in-repo primary docs (lane_F world triangulation,
fractal venture cell research, portfolio YAML, wedge precedents, NORTH_STAR read-next chain,
fractal_room.py code surfaces). Operator directive: in-repo primary docs FIRST, before any long build.
**Authority:** none — citations project from their owners; figures from lane_F carry that doc's receipts.

---

# GROUNDING CITATION PACK — AI Company Operator (Meta-Cell / spec-forge intake)

**Scope:** Read-only synthesis from 13 mandatory primary docs + `fractal_room.py` code surfaces.  
**Date anchor:** Sources dated 2026-05-07 through 2026-06-11.  
**Honesty flag:** Polis (participatory deliberation platform) is **not** covered in `lane_F_world.md`; closest in-repo analog = `scripts/organism_council.py` multi-model deliberation.

---

## A. Per-Doc Load-Bearing Extractions (with citations)

### 1. `reports/anatomy_altitude_2026-06-10/lane_F_world.md`

- **Economic engine cluster = ASPIRATION:** $0 revenue across all surfaces; `venture_cell/` = only `darshan/` + `operator_os/` (`lane_F_world.md:25`, `:199`)
- **Cofounder mechanism:** org-chart departments, exception-based HITL, MCP extensibility, milestone scaffold incorporation→scale; URLs: `cofounder.co` (`:13-17`)
- **dharma captured vs Cofounder:** deeper orchestration + typed gates RUN; missed = customer-facing execution, billing, GTM state machine (`:20-27`)
- **EXCEED-VECTOR (Cofounder):** receipted economic actions via `EvidenceReceipt` + `telos_gates.py` — auditable vs vibes-based approval (`:28`)
- **Polsia mechanism:** $49/mo + 20% rev-share; ~$10M ARR claims vs $689K run-rate (4.4× gap per zilla.so); URLs in `:33-35`
- **EXCEED-VECTOR (Polsia):** "honest ARR" via signed receipt chains — incumbents cannot publish without exposing claims gap (`:44`)
- **Numerai:** stake-weighted meta-model + burn for wrong predictions; dharma has fitness archive but **no stake primitive** (`:46-60`)
- **Palantir ontology:** writeback = governance path; dharma ontology ~10–15% runtime-native, read-only mirror (`:84-100`)
- **SLSA/in-toto:** receipts exist but unsigned/mutable — "diary not attestation" (`:103-117`)
- **DGM/AlphaEvolve/SWE-agent:** lineage broken (0/11,095 parent_id), swarm_lift = −0.10 recorded honestly (`:122-172`)
- **EXCEED-VECTOR ladder (8 rows):** receipted revenue (scrappy) → attested cognition → staked agent market → publishable decision chains (strategic) (`:184-195`)
- **Clean negatives:** $0 revenue, no staking, no crypto signing, broken DGM lineage, swarm loses to best single agent (`:197-205`)

### 2. `docs/research/FRACTAL_VENTURE_CELL_RESEARCH.md`

- **Seven source models:** Beer VSM, Haier RenDanHeYi, Holacracy, Nonaka, De Florio, BAMAS, Venture Studio (`:8-220`)
- **VSM recursion gap:** Dharma VSM is flat — rooms don't yet recurse S1–S5 inside each cell (`:47`)
- **Haier key innovation:** autonomy **with survival pressure** — dissolution threshold; Cofounder/Holacracy lack this (`:84-86`, `:396-397`)
- **Five Laws:** recursive self-similarity, economic accountability, governed autonomy, knowledge compounding, dissolution-with-recycling (`:222-254`)
- **Existing primitives map:** VentureCell ontology `:1444-1482` (note: line drift — actual `_VENTURE_CELL` now at `ontology.py:1839-1879`), TelosGatekeeper, SignalBus, EconomicEngine, etc. (`:260-282`)
- **Gaps:** Room container, budget enforcement, spawn protocol, WorkPacket, KaizenReview per room (`:284-297`)
- **Does not exist:** persistence, orchestrator dispatch, inter-room routing, autonomous spawning (`:299-307`)
- **Cofounder mapping:** take skills/flows/approval modes; reject flat departments, no economic accountability (`:383-411`)
- **Open questions:** in-memory v0, max depth 3, hard budget for VCs, human-only room creation (`:447-459`)

### 3. `docs/research/FRACTAL_ROOM_SPEC_V0.md`

- **NOT a Cofounder clone** — Haier ME model, not flat departments (`:11-13`)
- **Room = recursive building block** (De Florio) (`:15-17`)
- **FractalRoom fields:** id, kind, parent_id, purpose, status, operator, agents, budget_tokens, forbidden_work, gates, etc. (`:43-74`)
- **VentureCellV1 extends:** customer_or_beneficiary, kill_conditions, spinout_conditions, jagat_kalyan_constraint, autonomy_stage (`:79-98`)
- **Spawn protocol:** CONSENT gate, budget deduction, forbidden_work inheritance, witness log (`:182-195`)
- **Kill evaluator:** pure function on KPI dict; archival requires operator approval in v0 (`:199-215`)
- **Ontology linkage:** `ontology.py:VentureCell` = identity record; `fractal_room.py:FractalRoom` = runtime container; linked by `cell_id` (`:303-313`)

### 4. `docs/research/BUILD_PLAN_FRACTAL_ROOM_V0.md`

- **Build 1 only (schema + tests):** `fractal_room.py`, 20+ tests, no runtime (`:11-151`)
- **Build 2–5:** cell_id in CorrelationContext, operator brief, KaizenReview, Revenue Wedge instance (`:155-205`)
- **Decisions:** VentureCell extends Room; max depth 3; hard budget for VCs; no autonomous spawn v0 (`:208-221`)
- **Success:** Five Laws machine-verified; file <500 lines (`:225-239`)

### 5. `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`

- **Owner:** cell index of growing organism, NOT active build track (`:3-4`, `:22-24`)
- **Schema maps to:** `VentureCellV1` (`fractal/fractal_room.py:163-200`) + `_VENTURE_CELL` ontology (`:26-28`)
- **Cells spawn via** `RoomRegistry.spawn_child`; dead cells recycle via `archive_room` (`:27-28`)
- **THE ONE LAW** (verbatim — see §D)
- **HOBBLING GUARD** (verbatim — see §D)
- **Live cells:** darshan-publication ACTIVE_SEASON_0; `external_operator: cofounder.co` supersedes Polsia (`:73-89`)
- **revenue-wedge:** INCUBATING (`:103-106`)
- **campaign-xray:** HELD 28/100, $0 revenue (`:91-101`)
- **envisioned:** `future-organs` mechanism = IdeationNoticer → operator approve → `spawn_child` (`:148-151`)
- **retired:** arjuna-ngo-target-roster — phantom fabrication, not ambition (`:158-176`)

### 6. `docs/architecture/VENTURE_CELL_LIFECYCLE.md`

- **VentureCell = bounded economic survival pressure** — ontology + `VentureCellV1` + declared instance (`:12-18`)
- **NOT:** microservice, startup, pure code module (`:20-24`)
- **State machine:** PROPOSED → INCUBATING → ACTIVE → MATURE → DIVESTING/ARCHIVED (`:39-63`)
- **Status enum drift:** `ontology.py:1483` vs `fractal_room.py:62-69` — must unify (`:65-70`) — **actual ontology status at `ontology.py:1852-1854`**
- **Kill:** OR-semantic; evaluators at `fractal_room.py:248-303` (`:86-88`, `:211-237`)
- **Spinout:** AND-semantic; operator approval always required (`:265-290`)
- **KPIs:** revenue_usd, burn_usd, days_active via noticers — cells never self-compute (`:154-186`)
- **BoardStore/TreasuryNoticer/RevenueSpine:** spec'd but largely **future** (Phase 1–3 PRs) (`:156-186`, `:298-323`)

### 7. Code: `dharma_swarm/fractal/fractal_room.py`

| Symbol | Signature / behavior | Lines |
|--------|---------------------|-------|
| `MAX_NESTING_DEPTH` | `= 3` | `:43` |
| `RoomKind` | `OPERATIONS \| GOVERNANCE \| VENTURE_CELL \| RESEARCH` | `:60-64` |
| `RoomStatus` | `PROPOSED \| INCUBATING \| ACTIVE \| GRADUATING \| ARCHIVED \| SPUN_OUT` | `:67-73` |
| `FractalRoom` | dataclass; S1–S5 mapped; `remaining_budget()` | `:96-157` |
| `VentureCellV1(FractalRoom)` | + customer, kill/spinout, welfare, autonomy_stage | `:160-192` |
| `WorkPacket` | scoped work unit with cost_ceiling, gate_requirements | `:195-221` |
| `evaluate_kill_conditions` | `(conditions, kpis) → bool` OR semantics | `:297-303` |
| `evaluate_spinout_conditions` | `(conditions, kpis) → bool` AND semantics | `:306-314` |
| `RoomRegistry.register` | validates; deducts child budget from parent `current_burn` | `:487-501` |
| `RoomRegistry.spawn_child` | `(parent_id, child, *, consent_gate_passed: bool)` | `:591-636` |
| `RoomRegistry.archive_room` | returns agents+budget; preserves knowledge; recursive | `:640-697` |
| `room_brief` | operator brief section generator | `:720-784` |

### 8. `dharma_swarm/fractal/room_bridge.py`

- **RoomBridge:** wires registry → SignalBus, EconomicEngine, KaizenOps, CostTracker (`:52-84`)
- **`spawn_child`:** delegates to registry; emits `SIGNAL_ROOM_SPAWNED_CHILD` (`:123-142`)
- **`archive_room`:** emits `SIGNAL_ROOM_ARCHIVED`; optional EconomicEngine adjustment tx (`:144-172`)
- **`evaluate_room_health`:** kill/spinout check; **does NOT auto-archive** — operator approval v0 (`:269-312`)
- **`venture_cell_to_ontology` / `sync_registry_to_ontology`:** BR-008 ontology ↔ room polymorphism (`:375-464`)
- **`correlation_context_for_room`:** sets `cell_id=room_id` (`:316-334`)

### 9. `dharma_swarm/fractal/room_health.py`

- **`room_runtime_kpis`:** builds KPI dict for evaluators (`:31-61`)
- **`run_room_health_watcher`:** Guardian integration; disabled without live registry (`:64-78`)
- **Kill/budget findings:** BLOCKER on budget depletion; DEGRADED on kill trigger (`:91-130`)

### 10. `dharma_swarm/fractal/room_configs.py`

- **`make_core_ops_room()`:** root, budget 100k tokens, approval for sub-cell spawn (`:23-59`)
- **`make_revenue_wedge_cell()`:** id `revenue-wedge`, budget 50k, revenue_target 10_000, kill conditions (`:62-132`)
- **`bootstrap_registry()`:** core-ops → revenue-wedge + agentops hierarchy (`:175-188`)

### 11. `docs/research/wedge_precedents_sub90day_revenue_2026-05-29.md`

- **Brutal prior:** 54% indie SaaS = $0; median solo AI at 3mo = $200–$800/mo (`:8`, `:219-228`)
- **30-day first dollar (cold):** bounties (2–5d), done-for-you services (14–30d), agent audit consulting (20–45d) (`:191-200`)
- **#1 wedge for dharma:** AI Agent Audit / Code Review as a Service — substrate fit very high (`:249-265`)
- **#2:** Productized 48h eval report ($500–$1.5k) using gauntlet/petri_dish (`:269-284`)
- **Anti-pattern:** mech-interp research is credentialing, not revenue surface (`:341-351`)
- **Scoring dimensions:** time-to-first-$, substrate fit, sales complexity, burn coverage (`:308-337`)

### 12. `foundations/FIVE_FOURTEEN_A.md`

- **Three-organ organism:** VIVEKA (witness), SHAKTI (agent OS), KALYAN (welfare router) (`:21-27`)
- **Safety = intelligence same mechanism** — witness enables right action (`:19`, `:39`)
- **Strange loop:** VIVEKA monitors SHAKTI; SHAKTI runs KALYAN; KALYAN routes revenue to welfare (`:41-43`)
- **Entry sequence:** COLM → R_V consulting → consultancy → VIVEKA API → SHAKTI open-source → … (`:62-64`)
- **Moat claim:** 118K lines + 4326 tests + contemplative depth — solo, moksha telos (`:55-60`)

### 13. `docs/vision_maps/2026-05-07_operating_company_kernel.md`

- **North star:** solo-operator AI company organism — senses, selects work, ships, earns, buys compute, improves (`:17-41`)
- **Core loop:** truth → WorkPacket → AgentOps → evidence → revenue → YDS → budget → Darwin → next packet (`:46-70`)
- **Five metabolisms:** Truth, Work, Learning, Revenue, Compute (`:104-196`)
- **First offer:** `AI Codebase Governance + AgentOps Audit` (`:167-174`)
- **Missing organs (reserved names):** OperatingCompanyKernel, MorningCockpit, OpportunityEngine, EvidenceLedger, RevenueLedger, ComputeTreasury (`:200-215`)
- **Anti-mythology:** organ real only with producer + schema + durable output + consumer + tests + real run (`:344-354`)
- **90-day plan:** Days 1–30 Morning Cockpit; 31–60 WorkPacket real; 61–90 Revenue + ComputeTreasury (`:241-321`)

### 14. `reports/swarm_genome/2026-06-11/SYNTHESIS.md`

- **10-second map:** Krishna-first organism; inward Sakshi, outward Arjuna; strength = operating canon; distortion = hides telos (`:7-12`)
- **Clean truth:** vision large, runtime partial, **revenue zero**, research unstaffed, self-evolution not metabolic (`:12`)
- **No active track** for `revenue-external-humans-served` or `research-depth` (`:43-44`, `:121-122`)
- **Organ health:** RevenueSpine semi-working no customers; CashClaw semi-live unpaid; Agentic Code Governance Sprint = best sellable wedge (`:56-58`)
- **Ranked weak spot #1:** no canonical SWARM_GENOME.md (`:120`)
- **Revenue agent next action:** open revenue track, fix scout, first paid external human (`:200-202`)

### 15. `docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md`

- **Binocular loop:** Drishti scans world → swarm acts → reality answers → Sakshi reorganizes (`:34-49`)
- **SAB:** platform-spawning organ; status DORMANT zero sparks (`:53-59`)
- **Web 4.0:** trust substrate for agentic web — gates + witness + A2A receipts (`:63-65`)
- **THE ONE LAW** (verbatim — see §D)
- **Hobbling test:** constraint enhances vs hobbles; five detectors (`:90-105`)
- **Growth = subtraction (wu wei), not pushing** (`:84-86`)

### 16. `LIVING_THREAD_2026-06-10.md` + `docs/evidence/2026-06-10_chat_fable_evidence.md`

- **Vision:** cofounder.co-style autonomous companies as **organ** in one substrate-body, not separate product (`:21`, `:39`)
- **Unit of product:** sovereign swarm instance; revenue + seeding same event — banyan not oak (`:19`)
- **$0 external receipts;** Campaign X-Ray HELD 28/100; Darshan only ACTIVE_SEASON_0 (`:57`)
- **Polsia "interview" was chatbot** — propagated as canon 6+ days; phantom postmortem (`evidence:21`, `:230`)
- **Handoff 02:** first dispatch since 2026-05-27; SeatedCheckpoint EXISTS; fail-closed (`:97-107`)
- **Evidence run:** 0 cybernetic loops closed prod; evolution archive vacuous; $0 revenue (`evidence:4-5`, `:109-115`)

### 17. `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`

- **First VentureCell instance;** status `proposed`; parent `core-ops` (`:3-16`)
- **Economy:** budget 50k tokens, revenue_target 10,000 (`:28-33`)
- **Kill:** no_revenue_after_60_days, budget_exceeded, operator_override (`:77-86`)
- **Spinout:** revenue_exceeds_burn (3mo), operator_approval, customer_validation (`:88-94`)
- **Jagat Kalyan:** "Revenue without welfare is extraction" (`:96-103`)
- **First work packets:** customer discovery, value prop, MVP scope, pricing (`:113-118`)

---

## B. Competitor Mechanism Table

| Competitor | Mechanism | Receipt URLs (from docs) | dharma captured | dharma missed | EXCEED-VECTOR |
|------------|-----------|------------------------|-----------------|---------------|---------------|
| **Cofounder.co** | Org-chart departments; exception-based HITL; MCP/skills extensibility; GTM milestone scaffold | `https://cofounder.co`; LinkedIn announce `https://www.linkedin.com/posts/andrewpignanelli_...` | Deep orchestration, typed telos gates, spine `invoke_agent`, agent roster (`lane_F:20-22`) | Customer-facing execution (inbox, Stripe, outbound); billing; GTM state machine (`:25-26`) | Receipted economic actions — every dollar witnessed via `EvidenceReceipt` (`:28`) |
| **Polsia** | 9 agents E2E; $49/mo + 20% rev-share alignment | `https://polsia.com/`; `https://www.contextstudios.ai/blog/polsia-how-a-solo-founder-hit-1m-arr-in-30-days-with-ai-agents`; `https://zilla.so/blog/polsia-review` (4.4× ARR gap) | Honest measurement culture (swarm_lift −0.10 recorded) (`:37-39`) | Revenue-share mechanism, distribution, pricing, retention, billing (`:41-42`) | **Honest ARR** — signed receipt chains third-party verifiable; incumbents can't publish (`:44`) |
| **Numerai** | Crowdsourced models; NMR stake; burn on wrong; stake-weighted meta-model | `https://docs.numer.ai/`; `https://gemini.com/cryptopedia/numerai-tournaments`; JPMorgan $500M | Fitness archive, gauntlet, island/meta evolution (`:53-54`) | Stake/burn primitive; stake-weighted aggregation (`:56-58`) | Staked agent market on receipt spine — stake *actions* not just predictions (`:60`) |
| **Agentic funds / AI-native hedge funds** | Hierarchical veto (Risk Manager > Portfolio Manager); traceable decision chains (regulatory) | `https://digiqt.com/blog/ai-agents-in-hedge-funds/`; `https://arxiv.org/html/2605.19337v1`; EU AI Act / SEC OCC Bulletin 2026-13 | Gate-above-generator; `EvidenceReceipt.to_otel_span()` lineage (`:70-72`) | Capital, market connectivity, backtest, PIT data (`:75-76`) | Publish post-settlement decision chains as trust asset (`:78`) |
| **Palantir Foundry/AIP** | Ontology writeback; action types as governance path; AIP Logic sandboxed in actions | `https://www.palantir.com/docs/foundry/ontology/overview`; action-types, object-backend docs | Palantir-shaped ontology schema (`ontology.py`); gate registry (`:92-94`) | Writeback (ontology not write path); dynamic security (`:96-98`) | Self-governing ontology — schema evolves only through witnessed gate (`:100`) |
| **SLSA/Sigstore** | Signed attestations; Rekor transparency log | `https://slsa.dev/spec/v1.0/`; `https://docs.sigstore.dev/logging/overview/` | EvidenceReceipt subject+predicate shape; witness logs (`:109-111`) | Crypto signing; append-only; third-party verify (`:113-115`) | **SLSA-for-decisions** — attested cognition (`:117`) |
| **Sakana DGM** | Archive + diverse parent selection; empirical eval; lineage safety | `https://sakana.ai/dgm/`; `https://arxiv.org/abs/2505.22954` | `dgm_loop.py`, 11k archive entries (`:131-132`) | Working lineage (0% parent_id); real diffs (`:133-137`) | Semantic pre-application gate — meaning not markers (`:139`) |
| **AlphaEvolve** | Evaluator-driven hill-climb; program database | DeepMind blog; OpenEvolve | Forge harness RUNS; honest −0.10 (`:147-149`) | Closed loop to evolution; Flash/Pro division (`:151-153`) | Two-axis: fitness + conscience gate veto (`:155`) |
| **Polis-style deliberation** | *(not in lane_F)* Participatory preference mapping / collective deliberation | — | Partial: `scripts/organism_council.py` multi-model deliberation + telos gates (`:1-24` of that file); `jagat_kalyan.py:87-89` multi-model deliberation as public tool concept | No Polis mechanism, no public deliberation UI/API productized | **Spec-forge gap:** must define if "Polis-style" = organism_council productized + receipted outcomes, or new surface |
| **Factory.ai Missions** | Milestone planning + hook enforcement | `docs.factory.ai` (cited in research `:413-434`) | Telos gates as Python hooks with witness | Their bash hook format | Planning-before-execution WorkPacket pattern (`FRACTAL_VENTURE_CELL_RESEARCH.md:417-420`) |

---

## C. Meta-Cell Architecture — Today vs Productization Gap

### What EXISTS today (code-verified)

| Capability | Implementation | Lines |
|------------|----------------|-------|
| Recursive room schema | `FractalRoom` + `VentureCellV1` | `fractal_room.py:96-192` |
| Spawn child | `RoomRegistry.spawn_child(parent_id, child, *, consent_gate_passed)` — inherits forbidden_work/approvals; deducts budget | `:591-636` |
| Budget conservation | Child `budget_tokens` deducted to parent `current_burn` on register | `:496-499` |
| Archive / kill recycle | `archive_room` → agents to parent, budget returned, knowledge in `_archived_knowledge`, recursive children | `:640-697` |
| Kill/spinout eval | Pure functions OR/AND on KPI dict | `:297-314` |
| Work packets | `WorkPacket` + validation against room roster/budget | `:195-221`, `:402-438` |
| Ontology linkage | `venture_cell_to_ontology`, `sync_registry_to_ontology` | `room_bridge.py:375-464` |
| Ontology type | `_VENTURE_CELL` ObjectType with Create/Advance actions | `ontology.py:1839-1879` |
| Signal constants | `SIGNAL_ROOM_SPAWNED_CHILD`, `SIGNAL_ROOM_KILL_CONDITION_MET`, etc. | `fractal_room.py:80-88` |
| Bridge wiring | SignalBus, EconomicEngine, CostTracker hooks (optional deps) | `room_bridge.py:52-247` |
| Health watcher | Guardian `run_room_health_watcher` — needs live registry | `room_health.py:64-138` |
| Canonical configs | `bootstrap_registry()` with core-ops / revenue-wedge / agentops | `room_configs.py:175-188` |
| Portfolio index | YAML cell registry + spawn/archive doctrine | `VENTURE_CELL_PORTFOLIO.yaml:26-28` |

### What is MISSING for "venture cell that spawns venture cells" product

| Gap | Source |
|-----|--------|
| **No persistence** — in-memory `RoomRegistry` only | `BUILD_PLAN_FRACTAL_ROOM_V0.md:213`; `FRACTAL_VENTURE_CELL_RESEARCH.md:303` |
| **No orchestrator room dispatch** — work doesn't route to rooms | `FRACTAL_VENTURE_CELL_RESEARCH.md:304` |
| **No autonomous spawn** — human/CONSENT gate only v0 | `FRACTAL_ROOM_SPEC_V0.md:457`; `spawn_child` requires `consent_gate_passed=True` |
| **No billing/customer/revenue ledger** — $0 across surfaces | `lane_F_world.md:25`, `:199` |
| **No honest ARR receipt publication** — unsigned receipts | `lane_F_world.md:113-115` |
| **Kill does not auto-execute** — evaluate only; operator approval | `room_bridge.py:274-275`; `FRACTAL_ROOM_SPEC_V0.md:215` |
| **KPI noticers not wired** — TreasuryNoticer, RevenueSpine spec'd not live on rooms | `VENTURE_CELL_LIFECYCLE.md:156-186` |
| **Status enum mismatch** ontology vs fractal_room | `VENTURE_CELL_LIFECYCLE.md:65-70` |
| **No BoardStore facade** — lifecycle spec assumes future substrate | `VENTURE_CELL_LIFECYCLE.md:416-425` |
| **No meta-cell product API** — schema exists; no "AI Company Operator" outward surface | `lane_F_world.md:41-42` |
| **No Polis-style deliberation product** — only `organism_council.py` script | repo search |
| **IdeationNoticer → spawn_child** envisioned but not implemented | `VENTURE_CELL_PORTFOLIO.yaml:148-151` |
| **cell_id not in CorrelationContext** (Build 2) | `BUILD_PLAN_FRACTAL_ROOM_V0.md:155-168` |
| **VSM recursion inside rooms** — flat VSM today | `FRACTAL_VENTURE_CELL_RESEARCH.md:47` |

---

## D. THE ONE LAW + Hobbling Guard + Canon-Metabolism (verbatim short quotes)

**THE ONE LAW** (`VENTURE_CELL_PORTFOLIO.yaml:13-16`):
> No cell spawns, grows, or claims status except by closing a strange loop on a real, gated, verifiable, diversity-preserving outcome. The gate is "the bank that gives the river its power" — it makes many wild tentacles SAFE; it is NOT a reason to have one. Honest status per cell, across MANY cells.

**North-star equivalent** (`binocular_witness_seer_northstar.md:71-73`):
> No node spawns, no agent acts, no fitness updates, and no memory promotes — except through a strange loop that closes on a real, gated, verifiable, diversity-preserving outcome.

**HOBBLING GUARD** (`VENTURE_CELL_PORTFOLIO.yaml:18-20`):
> do NOT read this index as a mandate to shrink. A constraint that removes a tentacle that would have been *chosen* is hobbling, not dharma. Subtract only dead wood (phantom / narration-without-contact); never amputate a live limb to fit one brick.

**Hobbling diagnostic** (`binocular_witness_seer_northstar.md:94`):
> a constraint ENHANCES when it removes moves that would have been *regretted*; it HOBBLES when it removes moves that would have been *chosen*

**Canon-metabolism** (`VENTURE_CELL_PORTFOLIO.yaml:154-156`, `:194-196`):
> metabolize the lessons, retire the targets (kill nothing; compost)  
> Subtract toward the Tao (compost dead wood); do not amputate live limbs.

---

## E. Operator Preferences / Decisions (Polsia / Cofounder)

| Decision / preference | Source | Citation |
|----------------------|--------|----------|
| **Paused Polsia subscription** — prospective customer, not competitor | `lane_F_world.md` | `:38` (memory 2026-05-26) |
| **Darshan external_operator = cofounder.co** — supersedes Polsia (2026-05-27) | `VENTURE_CELL_PORTFOLIO.yaml` | `:80` |
| **Polsia "interview" was chatbot** — phantom; do not treat as real contact | `2026-06-10_chat_fable_evidence.md` | `:21`, `:230` |
| **Admires cofounder.co-style** as organ in one body, not standalone clone | `LIVING_THREAD_2026-06-10.md` | `:21`, `:39` |
| **Rejects phantom NGO roster** — OCCRP/GFW narrated-as-sent; operator: "I still don't even know what OCCRP / GFW is" | `VENTURE_CELL_PORTFOLIO.yaml` | `:163-164` |
| **Campaign X-Ray HELD** — separate from Darshan; not one receipt loop | `VENTURE_CELL_PORTFOLIO.yaml` | `:88-89`, `:94-101` |
| **Darshan = only ACTIVE_SEASON_0** cell | `LIVING_THREAD_2026-06-10.md` | `:57` |
| **$0 revenue truthful** — gauntlet HOLD | `evidence:109-115`; `first_cash_receipt_status.md` cited |
| **Cofounder internals SPECULATIVE** — landing page only | `lane_F_world.md` | `:18`, `:204` |
| **Polsia 4.4× ARR gap admired as honesty opportunity** — honest ARR moat | `lane_F_world.md` | `:35`, `:44` |

---

## F. Feature Seeds (20 items → `features.json`)

| # | Feature seed | Source doc:line |
|---|--------------|-----------------|
| 1 | Meta-cell `spawn_child` with CONSENT gate + budget conservation | `fractal_room.py:591-636` |
| 2 | `archive_room` dissolution-with-recycling (agents, budget, knowledge) | `fractal_room.py:640-697` |
| 3 | VentureCellV1 required fields: customer, revenue_target, kill_conditions | `fractal_room.py:380-399` |
| 4 | Kill condition registry + `evaluate_kill_conditions` OR semantics | `fractal_room.py:250-303` |
| 5 | Spinout condition registry + AND semantics + operator_approval | `fractal_room.py:274-314` |
| 6 | Ontology ↔ room sync (`venture_cell_to_ontology`) | `room_bridge.py:375-464` |
| 7 | Room health Guardian watcher (budget depletion, kill trigger) | `room_health.py:64-130` |
| 8 | Honest ARR: EvidenceReceipt chain per revenue event | `lane_F_world.md:44`, `:117-118` |
| 9 | Receipted revenue on CashClaw loop (scrappy exceed #1) | `lane_F_world.md:188` |
| 10 | SLSA-for-decisions: hash-chain + optional Sigstore on witness | `lane_F_world.md:117-118` |
| 11 | WorkPacket as only autonomous unit with cost_ceiling | `fractal_room.py:195-221`; `operating_company_kernel.md:130-144` |
| 12 | AI Codebase Governance + AgentOps Audit first offer | `operating_company_kernel.md:167-174` |
| 13 | Revenue Wedge cell instance (50k budget, 60-day kill) | `VENTURE_CELL_REVENUE_WEDGE.md:28-86` |
| 14 | IdeationNoticer → operator approve → spawn_child for new cells | `VENTURE_CELL_PORTFOLIO.yaml:148-151` |
| 15 | Haier survival pressure: kill at milestone, not infinite tenure | `FRACTAL_VENTURE_CELL_RESEARCH.md:78-79` |
| 16 | Max nesting depth 3 for meta-cell trees | `fractal_room.py:43`; `FRACTAL_ROOM_SPEC_V0.md:144` |
| 17 | Forbidden_work + approval inheritance on spawn | `fractal_room.py:360-377`, `:620-629` |
| 18 | Multi-model deliberation layer (organism_council pattern) for Polis-style | `scripts/organism_council.py:1-24` |
| 19 | KPI noticers (RevenueSpine, TreasuryNoticer) feeding kill eval | `VENTURE_CELL_LIFECYCLE.md:158-176` |
| 20 | Operator brief room sections (budget, revenue, agents) | `fractal_room.py:720-784`; `BUILD_PLAN_FRACTAL_ROOM_V0.md:172-180` |

---

## G. Contradictions & Constraints (honest flags)

1. **$0 revenue everywhere** — economic engine ASPIRATION (`lane_F_world.md:199`; `SYNTHESIS.md:12`; `evidence:4-5`). Build cannot claim paying customers without new receipts.

2. **revenue_target unit inconsistency:** `VENTURE_CELL_REVENUE_WEDGE.md:31` = 10,000; `FRACTAL_ROOM_SPEC_V0.md:255` = 100,000 "tokens"; `VENTURE_CELL_LIFECYCLE.md:388` = 1,000,000 "USD cents". Spec-forge must pick one canonical unit.

3. **Ontology line citations stale:** Research/lifecycle cite `ontology.py:1444-1507` / `:1470-1507`; actual `_VENTURE_CELL` = `ontology.py:1839-1879`.

4. **RoomStatus vs ontology status enums differ** — PROPOSED/GRADUATING/SPUN_OUT vs incubating/active/mature/divesting/archived (`VENTURE_CELL_LIFECYCLE.md:65-70`).

5. **Build 1 = schema only** — no runtime dispatch, persistence, billing (`BUILD_PLAN_FRACTAL_ROOM_V0.md:11-151`). "AI Company Operator" product exceeds Build 1 scope unless explicitly sequenced.

6. **No autonomous room spawning v0** — human/CONSENT only (`FRACTAL_VENTURE_CELL_RESEARCH.md:457`; `spawn_child` gate).

7. **Kill evaluation does not auto-archive** — operator approval required (`room_bridge.py:274-275`; `FRACTAL_ROOM_SPEC_V0.md:215`).

8. **ACTIVE_TRACK mismatch:** Portfolio says build track = `goodworks-dgm-core-2026-05` (`VENTURE_CELL_PORTFOLIO.yaml:22-23`); current ACTIVE_TRACK.yaml (per CLAUDE.md) = 4 runtime-truth/holon tracks — **no revenue-external-humans-served track** (`SYNTHESIS.md:43-44`).

9. **Cofounder chosen over Polsia for Darshan shell** but Polsia subscription paused, not rejected (`PORTFOLIO.yaml:80`; `lane_F:38`).

10. **Polis-style deliberation not in competitor research** — product claim needs explicit design; only `organism_council.py` exists.

11. **Phantom immune system behavioral-only** — Polsia/OCCRP incidents; no code gate on `originSessionId` (`evidence:21`, `:497`).

12. **swarm_lift = −0.10** — multi-agent may lose to best single on measured task; transcendence not proven (`lane_F:39`, `:203`).

13. **DGM lineage broken** — 0% parent_id; evolution archive safety gap (`lane_F:133-134`, `:202-203`).

14. **Receipts unsigned** — honest ARR moat requires crypto/append-only layer not yet built (`lane_F:113-115`).

15. **Fractal rooms BRANCH-DEPENDENT in operating kernel doc** — verify before claiming shipped (`operating_company_kernel.md:89`).

16. **30-day first-dollar pressure vs Build 1 schema-only** — wedge research says consulting/audit fastest (`wedge_precedents:191-200`); meta-cell productization is longer horizon.

17. **"NOT a Cofounder clone"** explicit doctrine — product must show fractal nesting + economic accountability + telos gates (`FRACTAL_ROOM_SPEC_V0.md:11-13`).

18. **ONE LAW forbids spawn without closed loop** — meta-cell that spawns cells without external receipts violates canon (`PORTFOLIO.yaml:13-16`).

19. **Hobbling guard forbids shrinking to one cell** — AI Company Operator must enable many tentacles, not replace portfolio with monolith (`PORTFOLIO.yaml:18-20`).

20. **Handoff evidence: anatomy ≠ physiology** — all "shipped" claims need tree + PID-epoch + runtime trace (`LIVING_THREAD:122-123`).

---

## Spec-forge intake one-liner

**AI Company Operator** = productized meta-layer over `RoomRegistry.spawn_child` + `VentureCellV1`, exceeding Cofounder (fractal + gates + kill/spinout) + Polsia (honest ARR receipts) + optional Polis-style deliberation (`organism_council` pattern), moat = third-party-verifiable revenue/decision receipts on spine — **substrate today = Build 1 schema + bridge hooks; revenue/dispatch/persistence/deliberation-product = open**.

---

*Pack complete. No files modified. All claims trace to cited primary docs or code lines above.*

[REDACTED]
