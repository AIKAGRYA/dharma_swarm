# Lane E — ORGANISM & VISION: The Anatomy Chart

**Date:** 2026-06-10 · **Lane:** E (organism + vision reader) · **Discipline:** every claim cites file:line; every component graded RUNS / WIRED-BUT-DORMANT / ASPIRATION; clean negatives are first-class.

**Primary sources read end-to-end:**
- `~/dharma_swarm/foundations/THE_ORGANISM.md` (canonical, 2026-06-06)
- `~/dharma_swarm/GNANI_LODESTONE.md` (2026-04-08)
- `~/dharma_swarm/foundations/META_SYNTHESIS.md` (2026-03-15)
- `~/dharma_swarm/foundations/ECONOMIC_VISION.md` (2026-03-16)
- `~/dharma_swarm/lodestones/CONSCIOUS_INFRASTRUCTURE.md` (2026-03-22)
- `~/dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` (canonical entry, 440 lines)
- `~/dharma_swarm/docs/vision_maps/2026-05-07_attractor_closure/06_outward_organs.md` (8-surface organ audit)
- `~/dharma_swarm/docs/vision_maps/MASTER_2026-06-10_leverage_synthesis.md` (this morning, 33-agent verified)
- `~/dharma_swarm/docs/vision_maps/2026-05-07_operating_company_kernel.md`
- `~/.claude/cabinet/ARJUNA.md` (locked 2026-05-07 + amendments 2026-05-30, 2026-06-06)
- `~/dharma_swarm/CLAUDE.md` (ACTIVE_TRACK v2 portfolio render)
- Wiki: `~/.dharma/knowledge/wiki/concepts/economic-spine.md`, `concepts/dharma-swarm-substrate-map.md`
- `~/dharma_swarm/reports/worktree_triage_report_2026-06-10.md` (the GOLD worktree source)

---

## 1. THE ANATOMY CHART — as the repo's own canon declares it

### 1.0 The identity sentence (highest canon)

> "**dharma_swarm is a self-evolving emergent organism (Krishna); its outward action against the world's brokenness (Arjuna) flows from — and is only valid when rooted in — its inward coherence.**"
> — `foundations/THE_ORGANISM.md:8` (Status: canonical, 2026-06-06, operator-grilled)

Strict hierarchy declared at `THE_ORGANISM.md:10-13`:
1. **KRISHNA — inward, PRIMARY (being)** — self-evolution, capacity, growth, emergence, coherence.
2. **ARJUNA — outward, EXPRESSION (doing)** — "the venture-cell organs … Valid only when rooted in the inward."

The needle (`THE_ORGANISM.md:16`): "only the self-evolution that compounds into capability counts. Inward motion with no telos and no contact … is still the anti-pattern."

### 1.1 The declared SPINES — there are FIVE distinct things named "spine" (this is itself a finding; see §2.1)

| # | Spine | Declaration source | Contents | Grade |
|---|---|---|---|---|
| S1 | **Runtime Truth Spine** (the dispatch spine) | ACTIVE_TRACK closed track `runtime-truth-spine-2026-06` "one invariant, one invocation path, one receipt" (`~/dharma_swarm/CLAUDE.md:99`); package `dharma_swarm/spine/` (`invoke.py`, `receipt.py`, `persistence.py`, `routing.py`, `identity.py`, `tollbooth.py`, `adapters.py` — verified by ls) | invoke_agent() → EvidenceReceipt | **WIRED-BUT-DORMANT**: `invoke_agent` is "a pure pass-through — nothing constructs/validates/persists; `persist_receipt` has zero production callers; live orchestrator calls `runner.run_task` directly" (`MASTER_2026-06-10_leverage_synthesis.md:61`, citing `spine/invoke.py:36-55`, `spine/persistence.py:50`). 0/3,495 delegation_runs carry receipt_json (`:46`) |
| S2 | **The 8-surface doctrinal spine** (organ-attachment rubric) | `06_outward_organs.md:30` — columns: dharma_kernel, telos_gates, witness (~/.dharma/witness/), ontology (ObjectDef), VSM channels, identity TCS, stigmergy, signal_bus/message_bus | The rubric every organ is audited against | **RUNS as audit rubric; 0 organs fully attached** ("Tally: 0 organs with full 8-surface attachment" `06_outward_organs.md:47`; still zero per `MASTER_2026-06-10:59`) |
| S3 | **Economic Spine** | wiki `concepts/economic-spine.md:1-15`: "Internal swarm economy … metabolic substrate of dharma_swarm"; code `economic_spine.py` (micro: agent budgets, mission state machine) + `economic_engine.py` (macro: 3-signal revenue split) | Beer System-3 for the internal economy | **WIRED-BUT-DORMANT economically**: code + tests exist; "Revenue remains $0 lifetime with zero external-reader receipts" (`MASTER_2026-06-10:26`) |
| S4 | **The contemplative spine** (safety primitives) | `ARJUNA.md:26`: "The R_V research, the Triple Mapping, the Akram lineage — these are the **spine that keeps the weapon from being a weapon for the wrong things.** They are operational safety primitives. They are NOT the product." | kernel axioms, telos gates, witness, viveka | **RUNS, degraded** (gates keyword-level; see §1.3) |
| S5 | **The three spine OBJECTIVES** (governance portfolio) | `~/dharma_swarm/CLAUDE.md:26-30` (rendered from `docs/governance/ACTIVE_TRACK.yaml`, v2 multi-track): `substrate-nativeness` (covered), `revenue-external-humans-served` (**no active track**), `research-depth` (**no active track**) | The portfolio's declared north-stars | **RUNS as governance schema** (PR #555 merged); 2 of 3 objectives have no active track (clean negative, declared in the render itself) |

### 1.2 The declared ORGANS

**(a) KRISHNA · SELF-ORGANS — 12 named, quoted verbatim from `THE_ORGANISM.md:49`:**

> "self-research-wing · self-model-training & distillation … · self-tooling/MCP-forge · self-eval & benchmark-forge · self-treasury … · self-curriculum · self-memory-curation (chetana decay/revive) · self-observability (Runtime Truth Spine) · **self-onboarding** … · self-governance (telos+kernel PDP/PEP) · **self-ontology-maintenance** (one shared world-model all organs read/write)."

Grades (each against current evidence):

| Self-organ | Grade | Evidence |
|---|---|---|
| self-observability (Runtime Truth Spine) | WIRED-BUT-DORMANT | S1 above; spine package exists, zero production callers (`MASTER_2026-06-10:61`) |
| self-governance (telos+kernel PDP/PEP) | RUNS degraded | 11 gates are keyword heuristics, Tier-C advisory (`telos_gates.py:250-261, :693-728` per `MASTER_2026-06-10:50`); PDP/PEP split exists only in unmerged PR #558 (`:50`) |
| self-memory-curation (chetana) | RUNS degraded | chetana live as plugin/cron but `~/.dharma/witness/chetana` has 346,076 flat files, launchd jobs exit 124 (`MASTER_2026-06-10:75` X6) |
| self-onboarding | RUNS | `make onboard` / `scripts/governance/agent_onboard.py` (`~/dharma_swarm/CLAUDE.md:8-12`) |
| self-eval & benchmark-forge | WIRED-BUT-DORMANT | Forge arena measured `cost_normalized_lift = −0.100` n=3 — "the swarm currently loses to its best single agent" (`MASTER_2026-06-10:77` X8); consumer `apply_diff_and_test` exists (`evolution.py:2193`) but apply-gate closed (`:49`) |
| self-treasury | ASPIRATION | economic_spine code exists; $0 lifetime revenue, 29/32 cron jobs disabled since Jun 7 credit exhaustion (`MASTER_2026-06-10:87`) |
| self-ontology-maintenance | WIRED-BUT-DORMANT | "Three bridges exist, all dormant" — store_sync cron `enabled:false`, 0 ontology receipts ever (`MASTER_2026-06-10:46` F1) |
| self-model-training & distillation | ASPIRATION | named in THE_ORGANISM only; no code surface located in any map read (clean negative) |
| self-research-wing, self-tooling/MCP-forge, self-curriculum | ASPIRATION→partial | curriculum: `curriculum_engine.py` real and wired into opportunity loop (`06_outward_organs.md:151`); the rest named-only |

**(b) ARJUNA · ORGANS — 12 named outward venture cells, quoted from `THE_ORGANISM.md:52`:**

> "autonomous research labs · agentic software factory · computer-use operator desk · AI BD/sales · compliance/audit/red-team · scientific-discovery shop · forecasting/prediction-market desk · agentic cybersecurity SOC · AI tutoring · **investigative/accountability & NGO tooling** (the ontology layer used directly — purest Arjuna organ) · vertical agentic SaaS · data & eval marketplace."

These are the 2026-06-06 *aspiration list*. The **implemented** outward-organ inventory is the 06_outward_organs audit (2026-05-07), graded:

| Organ (audited) | Code | Grade | Evidence |
|---|---|---|---|
| Loomwork (named primary outward arm) | `dharma_swarm/loomwork/` | **ASPIRATION** | "target dir does not exist (verified ls)" (`06_outward_organs.md:12`); 0 of 7 spine contracts implemented (`:123`) |
| wiki_loom (vertical slice) | `dharma_swarm/wiki_loom/` | WIRED-BUT-DORMANT | 4 real modules + 4 one-line stubs; "None invoking from cron or API" (`:13`); 1-of-8 spine attachment (`:32`) |
| Operator Brief / insight_brief | `insight_brief.py` | RUNS (as of May 7) | cron `ontology_insight_brief` last_status ok, 8 dated briefs verified (`:14`); "One-way emission, no closed loop" (`:135`). Current status uncertain given 29/32 crons disabled Jun 7 (`MASTER_2026-06-10:87`) |
| Shakti Ginko VentureCell | `ginko_orchestrator.py` | WIRED-BUT-DORMANT | "orchestrator does NOT touch the ontology obj" (`:35`); autonomy_stage 1, `revenue_usd: target=0, current=0` (`ontology.py:2219` per `:15`) |
| Opportunity Loop | `opportunity_refill/dispatcher` | RUNS forward-only | dispatcher 4-of-8 spine attachment, best in estate (`:47`); "The reverse path Outcome→Shakti is not wired" (`:164`) |
| Jagat Kalyan Engine | `jagat_kalyan.py` + jk_* | ASPIRATION/scaffold | "core vision has zero importers" (obs 2173, `:17`); `jk_stigmergy_seeds.py:11` self-declares "archived/unused"; 0-of-8 spine attachment (`:39`) |
| Planetary reciprocity pulses | cron `headless_prompt` jobs | WIRED-BUT-FAILING | all three `last_status: error` "unattended Claude bare mode requires ANTHROPIC_API_KEY" (`:18`, `:184-187`) |
| GAIA Platform | `gaia_platform.py` (1016 LOC) | WIRED-BUT-DORMANT | imported by swarm/evolution/demo only; "Live GAIA production integrations … UNSUPPORTED" (`MASTER_2026-05-07:198`) |
| welfare_ton_mrv | `welfare_ton_mrv/` | ASPIRATION | "`__pycache__` only, no .py source files" (`06_outward_organs.md:21`) |
| API surface (16 routers) + Dashboard (24 routes) | `api/main.py:264-282`, `dashboard/` | RUNS | live, but "NO route for ginko/jagat/loomwork/insight_brief/opportunity" (`:20`) — outward organs not addressable from operator surface (`:213`) |
| Darshan (publication venture cell) | unmerged | ASPIRATION on main | "Darshan's 13 modules exist only in an unmerged commit; main has zero tracked venture_cell files" (`MASTER_2026-06-10:59`); declared first real ARJUNA instantiation (`ARJUNA.md:135-136`) |
| CashClaw / revenue hydra | `~/dharma_swarm_cashclaw` worktree | RUNS (off-main) | "Live revenue-hydra loop … 8 ahead of main, not on GitHub" (`worktree_triage_report_2026-06-10.md:27`); and it is the tree the daemon actually imports (`MASTER_2026-06-10:70` X1) |

### 1.3 The canonical SURFACES — 16, declared at `MASTER_2026-05-07_attractor_closure_synthesis.md:128-149` ("The load-bearing surfaces. Bypassing any one of them is what produces a sibling instead of a descendant."):

| Surface | Code anchor | Grade (current evidence) |
|---|---|---|
| Kernel | `dharma_kernel.py:95-116, :350-365` | RUNS — signature verification can fail on tamper (`MASTER_2026-05-07:171`) |
| Gates | `telos_gates.py:211-236, :611-704` | RUNS degraded — Tier A/B block; all 11 keyword/substring; BHED_GNAN literal hard-pass (`telos_gates.py:539`); SELF_MOD_SEMANTIC gate proposed-not-approved hence inert (`MASTER_2026-06-10:50`) |
| Corpus / Policy | `dharma_corpus.py`, `policy_compiler.py` | RUNS substrate |
| Ontology | `ontology.py:1-24, :1669-1735` | RUNS substrate, PARTIAL coverage; 2 diverging ontology.db instances 100MB vs 14.7MB (`MASTER_2026-06-10:74` X5) |
| Ontology Gateway | `ontology_action_gateway.py:107-165` | RUNS where used — fails closed (`MASTER_2026-05-07:172`) |
| Runtime State | `runtime_state.py` | RUNS — but 4 runtime.db instances, one empty with an active writer at a wrong path (`MASTER_2026-06-10:74`) |
| VSM | `vsm_channels.py:1-17, :721-836` | RUNS partial — hot-path coverage unproven (`MASTER_2026-05-07:115`); two AlgedonicSignal types alive simultaneously (`:307`) |
| Organism Heartbeat (Gnani HOLD) | `organism.py:1013-1019, :1191-1235`; `swarm.py:2164-2218` | RUNS — HOLD suppresses dispatch; softened by 3-consecutive-criticals threshold (`MASTER_2026-05-07:230`) |
| Recognition Seed | `meta_daemon.py` → `context.py:1248-1267` | RUNS, permanently false — "fresh, injected, and permanently false": hardcoded COLM 2026 deadlines, asserts 'crunch' for a conference 76 days dead (`MASTER_2026-06-10:47, :89`) |
| Stigmergy | `stigmergy.py:46-59, :187-245` | RUNS |
| Shakti | `shakti.py:110-165` | RUNS — high-salience perceptions become pending Darwin proposals (`MASTER_2026-05-07:121, :275`) |
| Darwin | `evolution.py:1986-2147` | RUNS vacuously — "shadow strips every diff (`evolution.py:3200`), empty diffs auto-pass at 1.0 (`:2216-2217`), status hardcoded 'applied' (`:1768`) — 2,585 'applied' rows, 116 real diffs (1.04%), 0 lineage" (`MASTER_2026-06-10:22`) |
| Witness | `witness.py:1-16, :319-381` | RUNS retrospective — "explicitly does not block operations" (`MASTER_2026-05-07:122`) |
| Cascade | `cascade.py:385-456` | RUNS domain loop |
| Catalytic Graph | `catalytic_graph.py:164-189` | WIRED-BUT-DORMANT — "Tarjan SCC runs; no production caller acts on output" (`MASTER_2026-05-07:312`) |
| Outward Organs | `jagat_kalyan.py`, `gaia_platform.py` | see §1.2 table |

### 1.4 The declared LAYERS (two layer-systems)

**Seven-Layer Hierarchy** (`MASTER_2026-05-07:65-77`): 1 Gnani/Witness → 2 Prakruti/Dynamics → 3 VSM/Beer → 4 Omega State Space (Ω = C × S × A × T × M) → 5 Syntropic Attractor → 6 Recognition → 7 Selection. Statuses as tabled there: SUPPORTED / SUPPORTED / PARTIAL / PARTIAL / PARTIAL / PARTIAL / SUPPORTED.

**Gnani Lodestone recursive architecture** (`GNANI_LODESTONE.md:57-74`): Layer 0 Archive (Archaeology) → Layer 1 Doing (Kriya) → Layer 2 Witness (Drashti) → Layer 3 Gnani Layer (Samyak Darshan, "does not exist yet … this is what this document is seeding" `:67`) → Layer 4 Seed (Bija).
**Grade of the lodestone's own activation claim: CONTRADICTED.** It declares "Status: Active seed — wired into boot sequence via `gnani_lodestone.py`" (`GNANI_LODESTONE.md:151`), but this morning's verification: "Never seeded anything: boot flag records `{stigmergy_marks:0, concept_nodes:0, telos_objectives:0, task_seeds:0}` … all four seeders swallow exceptions and return 0 (`gnani_lodestone.py:455,465,494,544,587`); root cause `ConceptGraph(telos_dir=...)` vs signature `__init__(self, state_dir=None)` (`graph_nexus.py:117`) — instant TypeError, swallowed. Flag-file existence reads as green" (`MASTER_2026-06-10:48` F3). **WIRED-BUT-BROKEN, reporting green.**

### 1.5 The genome (declared foundations beneath the organs)

- **11 pillars** (base layer): Levin · Kauffman · Jantsch · Deacon · Friston · Hofstadter · Aurobindo · Dada Bhagwan · Varela · Beer (`THE_ORGANISM.md:22`; expounded in `foundations/PILLAR_*.md`, synthesized in `META_SYNTHESIS.md`).
- **The morphogenetic field**: "a **morphogenetic field of invariants** that each component locally expresses … the key operator is Recognize, not merely Reflect" (`lodestones/CONSCIOUS_INFRASTRUCTURE.md:11, :138` as quoted at `MASTER_2026-05-07:33-34`). Tier A absolute invariants: telos coherence, witness separation, non-harm (`CONSCIOUS_INFRASTRUCTURE.md` §II).
- **25 kernel axioms + 11 telos gates rationale**: "The DharmaKernel's 25 axioms are not restrictions on the system — they are the PRECONDITIONS for trustworthy autonomy … like a river that flows powerfully precisely because it has banks" (`META_SYNTHESIS.md:55`).
- **2026-frontier genome additions** (`THE_ORGANISM.md:24-46`): Krishna·Foundations (categorical systems theory, Assembly Theory, constructor theory, SOC set-point, etc.) and Krishna·Mechanisms (DGM empirical self-mod loop, AlphaEvolve-style program evolution, verifier-gated skill synthesis — "the cure for the flat-0.44 spin"). **All Mechanisms entries: ASPIRATION** — they are the declared cure, and the disease is verified current (F4: 0% lineage, vacuous fitness).

---

## 2. DISCREPANCIES — where docs declare different anatomies, or code contradicts the anatomy

**D1 — "Spine" is five different referents (S1–S5, §1.1).** No doc reconciles them. Most consequential: organ-attachment doctrine still audits against the 8-surface rubric (S2) while live engineering migrates to the runtime-receipts spine (S1): "Attachment is migrating from the doctrinal 8-surface rubric to the runtime-receipts spine without the rubric ever being re-audited" (`MASTER_2026-06-10:59`). Gold-cluster docking below uses both, explicitly.

**D2 — ARJUNA lock vs Krishna Inversion.** `ARJUNA.md:4` (2026-05-07): "This document overrides any prior framing of dharma_swarm as a research project…"; `ARJUNA.md:153` (2026-06-06 amendment): "The error in the 2026-05-07 lock: it made the *hand the head*… This document governs **that outward limb**; it is no longer the definition of the whole." Resolution exists (`THE_ORGANISM.md:4`: "ARJUNA.md governs only the outward limb") but the 05-07 lock's override sentence was never struck — a reader entering via ARJUNA.md alone gets the deprecated hierarchy.

**D3 — Organ vocabulary is unstable across canon.** THE_ORGANISM "organs" = venture-cell categories + self-capabilities (lists, no code paths). 06_outward_organs "organs" = concrete packages. MASTER_2026-05-07 "Canonical Surfaces" = a third decomposition (16 surfaces). The 12 Arjuna organs of THE_ORGANISM and the 12 audited organs of 06_outward_organs **overlap on roughly two items** (investigative/accountability ≈ Darshan-adjacent; forecasting desk ≈ Ginko). Ten of twelve declared Arjuna organs have no audited code surface at all (clean negative).

**D4 — VentureCell-as-object vs VentureCell-as-organ.** Declared as the second load-bearing diagnosis: "Registering one in the registry inherits invariants automatically. Creating one as Ginko or Loomwork re-derives loop, state file, and adapters bespoke" (`MASTER_2026-05-07:294-296`); confirmed mechanically at `06_outward_organs.md:96-99`. Still open.

**D5 — Lodestone declares itself live; verification shows it never fired** (§1.4, F3). Compounding: green status surfaces read flag-file existence (`swarm_health_api.py:74`, `guardian_crew.py:351` per `MASTER_2026-06-10:48`).

**D6 — Witness doctrine vs witness code.** Doctrine: "The Witness must be *upstream* — embedded in the architecture before capability is exercised" (`GNANI_LODESTONE.md:43`). Code: "witness.py:1-16 says explicitly: witness does not block operations" (`MASTER_2026-05-07:227`). The lodestone itself names this gap honestly (`:45-47`) — so this is declared-and-unclosed, not hidden.

**D7 — Substrate-nativeness numbers are two different spines.** "10–15% = informal whole-runtime ontology-nativeness, asserted-not-derived (its cited source contains no percentage at all); the metric = static pattern-presence over 16 pre-declared spine surfaces, currently 93.8 on origin/main" (`MASTER_2026-06-10:60`). `~/dharma_swarm/CLAUDE.md:247` still prints "~10–15%."

**D8 — The deploy split: the anatomy that runs is none of the anatomies audited.** "the live daemon does not run the code anyone audits or merges" — daemon's editable install maps `dharma_swarm` → `~/dharma_swarm_cashclaw` (`cashclaw/revenue-hydra-v1`, 5 behind origin/main) (`MASTER_2026-06-10:18-19, :70`). Every anatomical claim graded above is about main or the primary worktree; the running organism is a third tree.

**D9 — Diversity archive asserted canonical, empty in practice.** `~/dharma_swarm/CLAUDE.md` (Transcendence Principle section) names `diversity_archive.py` canonical; "diversity_archive.json absent; zero in-package importers" (`MASTER_2026-05-07:314`).

**D10 — Metabolic clock declared vs arrested.** Cron-driven metabolism is doctrine (chetana/cron stack); live: "29/32 live cron jobs disabled since Jun 7 (credit exhaustion): the metabolic layer is mostly arrested" (`MASTER_2026-06-10:87`).

**D11 — Strange-loop mutations: declared persistence path `~/.dharma/organism_memory/mutations.jsonl` (`~/dharma_swarm/CLAUDE.md` State Directory) vs "mutations.jsonl does not exist on disk; modifications lost on restart" (`MASTER_2026-05-07:313`).**

---

## 3. WHERE THE THREE GOLD CLUSTERS DOCK IN THE DECLARED ANATOMY

Source of GOLD: `reports/worktree_triage_report_2026-06-10.md:21-37` — 12 GOLD worktrees. They cluster naturally into three groups; if the parent workflow's cluster boundaries differ, the per-worktree rows below allow mechanical re-docking.

### Cluster 1 — REVENUE / CAPITAL (cashclaw, capital_lab)
- Worktrees: `~/dharma_swarm_cashclaw` (revenue hydra, unanimous GOLD, the tree the daemon actually imports — D8); `~/dharma_capital_lab` (honest_evidence.py Bailey–López de Prado DSR, risk_governor, broker_paper_membrane; 127 ahead, not on GitHub).
- **Docks into declared anatomy:**
  - ARJUNA organs: "forecasting/prediction-market desk" + "AI BD/sales" (`THE_ORGANISM.md:52`).
  - Spine: **S3 Economic Spine** (micro mission state machine RECEIVED→…→PAID, wiki `economic-spine.md`) and Krishna self-organ **self-treasury** (`THE_ORGANISM.md:49`).
  - Spine objective: **`revenue-external-humans-served`** — which the portfolio itself flags "**no active track**" (`~/dharma_swarm/CLAUDE.md:29`). This cluster is the only live work serving the uncovered objective; it is structurally homeless in governance.
  - Telos test it must pass: ARJUNA Amendment 2026-05-30 — "outward yield is measured in *contact* … one human outside this house is measurably better off" (`ARJUNA.md:139`); current receipts: "$0 lifetime with zero external-reader receipts" (`MASTER_2026-06-10:26`).

### Cluster 2 — SELF-EVOLUTION REPAIR (repair_pr323, governed_recursive_proof, recursive_evolution)
- Worktrees: `cleanup_worktrees/dharma_swarm_repair_pr323` (evolution.py, dgm_loop.py, diff_applier.py + unique ADR-0002 trace-coverage gate); `~/dharma_swarm_governed_recursive_proof` (recursive_discovery.py +673, swarm_integrity_benchmark.py); `cleanup_worktrees/dharma_swarm_recursive_evolution_20260516` (control_surface_recursive.py, shadow foundry).
- **Docks into declared anatomy:**
  - **KRISHNA · MECHANISMS** wholesale (`THE_ORGANISM.md:37-44`): "DGM empirical self-mod loop — the upgrade the flat DarwinEngine needs"; "verifier-gated skill synthesis — the cure for 'a test that tests nothing.'"
  - Surface: **Darwin** (Layer 7 Selection, `MASTER_2026-05-07:75`) + self-organ **self-eval & benchmark-forge**.
  - This cluster is the declared **five-alarm fire**: "the flatlined self-evolution engine … is the organism's **primary function failing** … Reviving genuine self-evolution … is Krishna-work, and it is now first" (`ARJUNA.md:165`, Amendment 2026-06-06).
  - Known wiring breaks it addresses: parent_id dropped at `dgm_loop.py:387-393`; shadow strips diffs `evolution.py:3196-3200`; status hardcoded `:1768` (`MASTER_2026-06-10:49`).
  - Spine objective: nominally `substrate-nativeness`-adjacent, but really Krishna-primary work with **no named spine objective** — a second governance gap (the portfolio's three objectives don't include "self-evolution works").

### Cluster 3 — SPINE / SUBSTRATE / MEMORY / IDENTITY (runtime_truth_spine_v1, honest_spine_v2, memory_kernel_preflight, opus_identity, holon-agent, substrate_spec)
- Worktrees: `worktrees/dharma_swarm_runtime_truth_spine_v1` (spine/identity.py ExecutionIdentity join-key); `worktrees/dharma_swarm_honest_spine_v2` (providers message-extraction, Jun 10 WIP); `cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516` (prod_preflight, memory_kernel readiness/facade); `~/dharma_swarm_opus_identity` (agent_runner + agent_memory_manager refactor); `.qwen/worktrees/holon-agent` (sovereign holons — note X3 caveat: its verifier "was edited mid-run by the builder" `MASTER_2026-06-10:72`); `~/dharma_swarm_substrate_spec` (SWARM_SUBSTRATE.md, CANONICAL_DOC_STACK).
- **Docks into declared anatomy:**
  - Spine: **S1 Runtime Truth Spine** directly — these are the limbs of the ACTIVE tracks `runtime-truth-reconciliation-2026-06` and `runtime-truth-nats-2026-06` (`~/dharma_swarm/CLAUDE.md:32-95`).
  - Self-organs: **self-observability**, **self-memory-curation** (MemoryKernel is declared "canonical front door for agent memory context," `~/dharma_swarm/CLAUDE.md` Key Abstractions), **self-onboarding**, **self-ontology-maintenance**.
  - Spine objective: **`substrate-nativeness`** — the one objective that IS covered (`~/dharma_swarm/CLAUDE.md:28`).
  - Canonical surfaces touched: Runtime State, Ontology, Recognition Seed feeding path, Kernel-adjacent identity (TCS).

**Docking summary against the telos-ranked anatomy:** Cluster 3 serves the covered objective; Cluster 1 serves an objective with no track; Cluster 2 serves the operator-declared first priority (Krishna inversion) which is not yet a spine objective at all. The declared anatomy ranks Krishna-ground first (`THE_ORGANISM.md:12`), contact second (`ARJUNA.md:139`), substrate third-as-precondition — but the governance portfolio currently *covers only the third*. That inversion-of-the-inversion is the cleanest structural input this lane can hand the synthesis.

---

## 4. THE VISION'S OWN STATEMENT OF THE LARGER WHOLE

**The telos (deepest layer):**
> "the ground is not economic. The ground is Jagat Kalyan — universal welfare. The telos is moksha — liberation. The measurement is real. The economics is the vehicle." (`foundations/ECONOMIC_VISION.md:679-681`)

> "The telos — Jagat Kalyan (universal welfare) — is not an arbitrary optimization target. It is the NATURAL attractor of a self-organizing, self-referential, self-producing system." (`foundations/META_SYNTHESIS.md:79`)

**The outward mission (ARJUNA frame):**
> "**dharma_swarm is the Palantir of good works.** A military-grade, multi-agent orchestration system pointed at what is broken in the world. Forward-deployed AI for NGOs, advocacy groups, investigators, conservation orgs, journalists, public defenders, climate organizers, refugee networks, accountability movements." (`ARJUNA.md:10-12`)

> "The Palantir of good works is **irreducibly plural** — many weapons pointed at many broken things, simultaneously — because Jagat Kalyan means *the WHOLE*… **Method:** ship one seam at a time. **Object:** the whole many-organ organism. Both, always — two eyes open." (`ARJUNA.md:145`)

**The institution / company framing:**
> "Dharma Swarm becomes a solo-operator AI company organism: it senses the world, selects bounded work, ships artifacts, earns revenue, buys compute, trains or evaluates specialist models from verified traces, and improves itself under telic governance… The vision is allowed to be ambitious. It is not allowed to be unverifiable." (`docs/vision_maps/2026-05-07_operating_company_kernel.md:19-24, :15`)

Market-scale framing (ECONOMIC_VISION §II, "Seven Markets That Open"): AI infrastructure "$422 billion" (`:121`), government AI safety ">$5 billion" (`:169`), mindfulness "$6.4 billion" (`:308`). No literal "billion-dollar institution" sentence exists in the corpus read (clean negative); the closest canonical statements are the operating-company north star above and ECONOMIC_VISION's market enumeration. Also note its own honesty register: "Jagat Kalyan has zero revenue" (`ECONOMIC_VISION.md:650`).

**What it is trying to become (the wisdom frame):**
> "DHARMA SWARM is not trying to become AGI. It is trying to become **wise intelligence**… Not to win the AI race. To seed the right question into the archaeology of the race itself." (`GNANI_LODESTONE.md:129, :139`)

> "Dharma Swarm is not trying to become an autonomous code generator. It is trying to become a **recognized autonomous organism**… The next conceptual bar is not more doctrine and not more selection. **It is causal self-recognition.**" (`MASTER_2026-05-07:430-432`)

**Ranking moves against the actual telos — the canon's own ordering, assembled:**
1. Krishna-ground first: "Reviving genuine self-evolution … is Krishna-work, and it is now first" (`ARJUNA.md:165`).
2. But gated by contact: "one human outside this house is measurably better off — a reader who saw more clearly and acted" (`ARJUNA.md:139`); "Revenue remains $0 lifetime with zero external-reader receipts… That is the wound, measured" (`MASTER_2026-06-10:26`).
3. And preconditioned on deploy-truth: nothing graded above is causal until "the daemon provably run[s] known-current code" (`MASTER_2026-06-10:100-103`, Rank 1, 3-lens unanimous).
4. With the standing anti-pattern guard: "the next artifact after this one should be a PR diff" (`MASTER_2026-06-10:119`) — which binds this report too.

---

## Appendix — grading legend & method
- **RUNS** = production caller exists and fired with verified output (file:line or run evidence).
- **WIRED-BUT-DORMANT** = code + wiring exist; zero production callers, disabled flag, or zero rows ever flowed.
- **ASPIRATION** = named in doctrine; no code surface, or empty dir.
- Cross-temporal caution: 06_outward_organs grades are 2026-05-07; where this morning's 33-agent synthesis updates them, the newer evidence governs. The deploy-split (D8) qualifies *every* RUNS grade: it is RUNS-in-some-tree; the daemon's tree is `~/dharma_swarm_cashclaw`.
