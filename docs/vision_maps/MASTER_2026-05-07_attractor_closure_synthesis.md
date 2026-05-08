# MASTER (SYNTHESIS) — Attractor Closure
**Date:** 2026-05-07
**Location:** `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md`
**Mode:** Read-only synthesis of two prior master attempts. No plans. No new code. Evidence classified SUPPORTED / PARTIAL / CONTRADICTED / UNKNOWN per the codex discipline. File:line citations throughout.

This file supersedes the two prior 2026-05-07 master attempts as the single point-of-entry for the highest-vision map. The two predecessors are preserved as upstream inputs and remain readable.

---

## 0. Provenance

**Predecessor A — Claude master (filesystem-recursive):**
- `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure.md` (241 lines)
- + 6 child maps in `dharma_swarm/docs/vision_maps/2026-05-07_attractor_closure/0{1..6}_*.md` (1,226 lines total)
- Strength: filesystem recursion, date-stamped naming convention, single-diagnosis collapse, named 6-agent provenance
- Weakness: lighter on stale-doc challenge, no explicit evidence-tier classification

**Predecessor B — Codex master (monolithic with virtual paths):**
- `dharma_swarm/DHARMA_SWARM_MASTER_MAP.md` (1,142 lines)
- Strength: explicit SUPPORTED/PARTIAL/CONTRADICTED/UNKNOWN classification, dedicated Contradictions Register, Closure Scorecard, future-dispatch prompt
- Weakness: violates `CLAUDE.md` "NEVER save to root"; no date stamp; no filesystem recursion for deeper drilldown

**This synthesis** keeps codex's empirical discipline + contradictions register, keeps Claude's filesystem recursion + date-stamping, reconciles factual disagreements between the two against current source, and adds explicit comparison points where the two prior masters diverged.

---

## 1. Convergent Thesis (where both prior masters agree)

> **Recognition-mediated autopoiesis is structurally present in dharma_swarm but is not yet a single live causal surface.**

The architecture is not missing parts. Every limb exists. The field — the single live causal surface where recognition is continuously causal rather than retrospective — has not closed. The compact name is **Attractor Closure**.

> "morphogenetic field of invariants … the key operator is Recognize, not merely Reflect: the system seeing itself as itself."
> — `lodestones/CONSCIOUS_INFRASTRUCTURE.md:9, :138` (SUPPORTED as doctrine)

The direct thesis: **Make the swarm's self-recognition causal.**

The status:
```
Conceptually: present.
Architecturally: many organs exist.
Operationally: partially closed.
Hard gap: the field is not yet one live causal surface.
```

---

## 2. Why This Is Not A Fitness Law

A fitness law answers: which proposal scores higher? Selection. System 3.

Attractor Closure must answer harder questions:

- Does this proposal belong to the organism?
- Does this branch expand capability or hide identity drift?
- Is this recurring mark a wound, a gate seed, a new organ, or noise?
- Is this outward product attached to Jagat Kalyan or detached vanity?
- Is this document a lodestone, runtime canon, stale doctrine, or evidence?
- Did the system's self-model actually change behavior?

Darwin selects. Shakti generates. Stigmergy sediments. VSM routes. Gnani witnesses. Ontology binds. **Recognition is the closure operator that makes those organs one organism instead of adjacent machinery.**

---

## 3. The Seven-Layer Hierarchy

| # | Layer | What It Is | Surface in Code | Status |
|---|---|---|---|---|
| 1 | **Gnani / Witness** | What does NOT change. Identity, kernel, telos, observer separation. | `dharma_kernel.py`, `telos_gates.py`, `witness.py`, `identity.py` | SUPPORTED (with advisory gaps; §6) |
| 2 | **Prakruti / Dynamics** | What changes. Marks, agents, dreams, Shakti, proposals. | `stigmergy.py`, `shakti.py`, `subconscious_v2.py`, `auto_proposer.py` | SUPPORTED |
| 3 | **VSM / Beer** | How the organism stays viable: S1/S2/S3/S3*/S4/S5 + algedonic. | `vsm_channels.py:1-17, :142-229, :721-836`; `algedonic_bridge.py`; `sheaf.py` | PARTIAL hot-path coverage |
| 4 | **Omega State Space** | The whole state: Ω = C × S × A × T × M (code, state, agents, telos, marks). | scattered across `dharma_corpus.py`, `runtime_state.py`, `agent_registry.py`, `telos_graph.py`, `stigmergy.py` | PARTIAL — projected per-axis, no combined-trajectory reader |
| 5 | **Syntropic Attractor** | Directionality. Basin toward Jagat Kalyan / Moksha / coherent self-organization. | `dharma_attractor.py`, `jagat_kalyan.py`, `info_geometry.distance_to_dharma`, `lodestones/bridges/telos_as_syntropic_attractor.md` | PARTIAL — doctrine SUPPORTED, continuous runtime measurement UNKNOWN |
| 6 | **Recognition** | Phase transition where the self-model becomes operationally entangled with behavior. | `meta_daemon.py:1-13, :52-87` → `context.py:1202-1217, :1288-1292`; `ontology.py`; `strange_loop.py`; `ouroboros.py` | PARTIAL — recognition seed path SUPPORTED; live freshness UNKNOWN |
| 7 | **Selection** | Metabolic immune filter inside the larger field. | `evolution.py:1-8, :1986-2147`; `auto_proposer.py`; `gate_check`; `apply_diff_and_test:2156` | SUPPORTED (apply gate `DHARMA_EVOLUTION_SHADOW=1` default — CLOSED; `self_evolution_trace_2026-05-07.md`) |

---

## 4. The Closure Circuit

```
1. Variety appears
   agents, Shakti perceptions, dreams, cascade variants, opportunities,
   Darwin proposals, operator briefs, product experiments
   ↓
2. Coordination routes it
   task board, orchestrator, stigmergy, sheaf gluing, VSM S2/S3, runtime state
   ↓
3. Identity evaluates it
   kernel, gates, policy, Gnani heartbeat, identity/TCS, ontology gateway, S5
   ↓
4. Metabolism transforms it
   Darwin, cascade, Shakti escalates, Samvara corrections, VentureCells bind
   ↓
5. Sediment forms
   code, tests, docs, corpus, marks, archive, ontology objects, runtime state
   ↓
6. Recognition updates the self-model
   RecognitionEngine reads signals → writes recognition_seed.md → context injects
   → agents act under changed self-context → next loop reads the result
```

The circuit is real enough to map, but **not proven closed enough to trust as a single organismic surface.** Direct causal edges exist. So do bypasses, stale docs, fail-open defaults, and fragmented state stores.

---

## 5. Evidence Spine

| Surface | Evidence | Reading | Status |
|---|---|---|---|
| Morphogenetic field | `lodestones/CONSCIOUS_INFRASTRUCTURE.md:9-14, :21-32, :138-146` | Frames system as morphogenetic field of invariants; key operator is Recognize. | SUPPORTED as doctrine |
| Kernel invariants | `dharma_kernel.py:1-9, :29-75, :350-365` | 25 signed principles incl. observer separation, operational closure, autocatalytic closure, recursive viability, active inference. | SUPPORTED as code |
| Telos gates | `telos_gates.py:211-236, :611-704, :816-886` | 11 core gates block Tier A/B; Tier C mostly review; reflective witness reroute exists. | SUPPORTED with advisory gaps |
| Gnani heartbeat | `organism.py:1013-1019, :1069-1132, :1191-1235`; `swarm.py:2164-2218, :2346-2360` | OrganismRuntime measures identity/live/algedonic; Gnani HOLD suppresses dispatch and enqueues Samvara corrections. | SUPPORTED causal path |
| VSM channels | `vsm_channels.py:1-17, :142-229, :259-305, :373-385, :721-836` | S3/S4 feedback (GatePatternAggregator), S3* audit, algedonic bypass, agent viability, variety expansion. | PARTIAL hot-path coverage |
| Ontology / self-model | `ontology.py:1-24, :1669-1735, :1779-1911`; `ontology_action_gateway.py:1-25, :107-165` | Typed objects/actions, audits, gates, reversibility, VentureCells, Outcomes, ValueEvents. Gateway fails closed where used. | SUPPORTED substrate, PARTIAL coverage |
| Runtime state | `runtime_state.py:1-7, :28-187, :718-745, :1672-1742` | Persistence spine for current organism/process facts. | SUPPORTED substrate |
| Recognition seed | `meta_daemon.py:1-13, :52-87`; `context.py:1202-1217, :1288-1292` | RecognitionEngine synthesizes seed; context injects into top of agent context when present. | SUPPORTED path, UNKNOWN live freshness |
| R_V / ouroboros | `rv.py:1-15, :269-365`; `system_rv.py:1-11, :154-216`; `ouroboros.py:1-13, :128-168, :499-514` | Recognition measured via contraction, self-reference, behavioral fitness, mimicry. | PARTIAL — metrics exist, causality uneven |
| Stigmergy | `stigmergy.py:46-59, :118-156, :187-245, :318-370` | Marks with salience, channels, hot paths, high-salience bleed, query, decay. | SUPPORTED |
| Shakti → Darwin | `shakti.py:110-165`; `orchestrate_live.py:76-110, :797-814`; `evolution.py:1-8, :1986-2147, :3477-3503` | Shakti perceives marks; high-salience perceptions become pending Darwin proposals; Darwin gates/evaluates/archives. | **SUPPORTED in current code** (resolves disagreement; see §10) |
| Witness | `witness.py:1-16, :319-381` | Retrospective; publishes findings to marks/memory/bus; explicitly does not block operations. | CONTRADICTS hard-S5 reading |
| Cascade / product | `cascade.py:1-10, :243-261, :385-456`; `cascade_domains/product.py:1-7, :191-200, :279-298` | Generates/tests/scores/gates/mutates/selects; writes history/stigmergy. | SUPPORTED domain loop |
| Outward organs | `wiki_loom/revelation.py:32-73`; `wiki_loom/publisher.py:31-65`; `jagat_kalyan.py:1-14, :192-280`; `gaia_platform.py:1-8, :105-229` | Wiki loom, Jagat Kalyan service proposals, GAIA ecological surfaces exist. | SUPPORTED, bounded |

---

## 6. Canonical Surfaces

The load-bearing surfaces. Bypassing any one of them is what produces a sibling instead of a descendant. Any new organ should attach here before being deployed.

| Surface | Role In Attractor Closure | Evidence |
|---|---|---|
| Kernel | Immutable invariant seed; S5 floor | `dharma_kernel.py:95-116, :350-365` |
| Gates | Downward causation from telos into action | `telos_gates.py:211-236, :611-704` |
| Corpus / Policy | Mutable knowledge under immutable kernel | `dharma_corpus.py:6`; `policy_compiler.py:4, :185` |
| Ontology | Typed self-model and action grammar | `ontology.py:1-24, :1669-1735` |
| Ontology Gateway | Fail-closed causal self-model where used | `ontology_action_gateway.py:1-25, :107-165` |
| Runtime State | Current organism / process state | `runtime_state.py:1-7, :1672-1742` |
| VSM | Viability nervous system | `vsm_channels.py:1-17, :721-836` |
| Organism Heartbeat | Gnani / Samvara / algedonic causal path | `organism.py:1013-1019, :1191-1235` |
| Recognition Seed | Self-model text injected into agents | `meta_daemon.py:1-13`; `context.py:1202-1217` |
| Stigmergy | Sedimented field of marks | `stigmergy.py:46-59, :187-245` |
| Shakti | Generative perception and proposal energy | `shakti.py:1-12, :110-165` |
| Darwin | Immune / metabolic selection | `evolution.py:1-8, :1986-2147` |
| Witness | Retrospective audit and evidencing | `witness.py:1-16, :319-381` |
| Cascade | Domain attractor loop | `cascade.py:1-10, :385-456` |
| Catalytic Graph | Autocatalytic relation detector | `catalytic_graph.py:1-5, :164-189, :213-256` |
| Outward Organs | World contact and Jagat Kalyan service | `jagat_kalyan.py:1-14`; `gaia_platform.py:1-8` |

---

## 7. Cross-Map Matrix

| Layer | Core Question | Strongest Current Form | Main Gap |
|---|---|---|---|
| Gnani / Witness | What must not change? | Kernel integrity, Tier A/B gates, identity/TCS, Gnani HOLD | Witness retrospective; some failures default PROCEED |
| Prakruti / Dynamics | How does motion arise? | Agents, marks, Shakti, Darwin, cascade, opportunities | Variety not always bound back into ontology/VSM |
| VSM | How does the organism remain viable? | S3/S4 feedback, S3* audit, algedonic, organism heartbeat | Coverage across all S1 outputs unproven |
| Omega | What whole state is moving? | C, S, A, T, M each represented somewhere | No single continuous Omega tuple reader |
| Recognition | When does knowing change behavior? | recognition_seed → context → agent behavior + gates/HOLD/reroute | No single authoritative `Recognize` primitive |
| Autopoiesis | How does the system regenerate its parts? | Darwin, Shakti, stigmergy, cascade, catalytic graph, Build Protocol | No proof recurring marks auto-crystallize gates / organs |
| Outward Organs | How does inner telos become world service? | Wiki loom, VentureCell schema, opportunity loop, Jagat Kalyan, GAIA | External success feedback into Omega unproven |

---

## 8. Closure Scorecard

### 8.1 Hard Causal Edges (proven by file:line)

- Kernel signature verification can fail on tamper: `dharma_kernel.py:350-365`.
- Tier A/B gates block: `telos_gates.py:611-665`.
- OntologyActionGateway fails closed where used: `ontology_action_gateway.py:1-25, :107-165`.
- Organism Gnani HOLD suppresses dispatch in SwarmManager tick: `swarm.py:2164-2218, :2346-2360`.
- Shakti high-salience perceptions enqueued for Darwin: `orchestrate_live.py:76-110, :797-814`.
- Recognition seed injected into agent context when present: `context.py:1202-1217, :1288-1292`.
- StrangeLoop apply/revert on `OrganismConfig`: `strange_loop.py:228-303`.
- Algedonic routing-bias mutation: `organism.py:332-346`.
- Algedonic Gnani checkpoint: `organism.py:347-367`.
- Pulse `is_healthy` gating on `identity_coherence > 0.3`: `organism.py:106`.

### 8.2 Partial Causal Edges (mechanism present, coverage / behavior change unproven)

- VSM hooks exist; full hot-path coverage not proven.
- S3* witness/audit exists; some witness paths retrospective and non-blocking.
- Ontology designed as platform, but not every runtime mutation proven to flow through it.
- R_V, ouroboros, eigenform metrics exist; do not by themselves prove classification changed behavior.
- Product, opportunity, outward-organ artifacts written; complete feedback into Omega unproven.
- Recognition seed pathway present; live freshness not measured continuously.

### 8.3 Unsupported As Complete Closure (asserted in docs, not in code)

- Automatic branch demotion / promotion by recognition.
- Automatic gate crystallization from recurring marks.
- Continuous measurement of all Ω axes as one trajectory.
- Continuous seven-dimensional 7-STAR runtime vector (concept-graph names 7 components; `thinkodynamic_scorer._score_telos_alignment` collapses to keyword count).
- General nested VSM runtime for every VentureCell.
- Live GAIA production integrations and multi-tenant surface (`gaia_ui.md:3-13, :378-386`).

---

## 9. Contradictions Register (stale docs vs current code)

This is the section that resolves doc-rot. Every entry: a doc claim from somewhere in the repo, contrasted with current source evidence.

### 9.1 Doc-vs-Code Drift (doc is stale)

- `CYBERNETIC_LOOP_MAP.md:196-208` says recognition seed was never generated.
  **Current code**: `meta_daemon.py:1-13` + `context.py:1202-1217` — RecognitionEngine present + context injection wired.
  → **Doc is stale OR points to live runtime non-execution.**

- `LIVING_LAYERS.md:383-386` says Shakti → Darwin routing is missing.
  **Current code**: `orchestrate_live.py:76-110, :797-814` + `evolution.py:3477-3503` — high-salience Shakti perceptions become pending Darwin proposals; Darwin consumes them.
  → **Doc is stale.** (This resolves a disagreement between the two prior masters: codex was correct.)

- `docs/telos-engine/07_VSM_GOVERNANCE.md:476` says no explicit S3/S4 channel.
  **Current code**: `vsm_channels.py:142-229` (GatePatternAggregator) + `zeitgeist.py:273` (gate pressure) — channel implemented.
  → **Doc is stale OR partial wiring.**

- Some docs frame VSM as fully recursive (each S1 contains S1-S5).
  **Current code**: `vsm_channels.py:111` per-agent viability fields exist. General nested VSM runtime for every VentureCell — UNKNOWN.
  → **Recursion conceptually strong, runtime unproven.**

### 9.2 Fail-Open / Softened Authority (code itself tells a different story than the headline)

- `witness.py:1-16` says explicitly: witness does not block operations.
- `dharma_attractor.py:154-178` defaults checkpoint exceptions to PROCEED.
- `telos_gates.py:512-513` makes BHED_GNAN always pass (literal hard-pass).
- `telos_gates.py:667-704` treats Tier C largely as review.
- `organism.py:1193-1242` requires 3 consecutive criticals before EMERGENCY_HOLD — softens HOLD into "sustained evidence" before action.
- `opportunity_dispatcher.py:30-41, :385-430` — REVIEW proceeds with warning pending real operator approval (FIXME).
- `identity._issue_correction` (`identity.py:329-373`) writes `.FOCUS` on TCS drift. **VERIFIED 2026-05-07 18:00:** `.FOCUS` IS read in `swarm.py:1514, 1533-1534, 2114, 2122, 2125` (Wire 3 routing governance — GPR routing-bias boost + RM research-priority flag). Drift IS consumed. (Prior claim "no reader" was a stale-research artifact corrected by Agent C convergence audit + direct grep; tracked in BR-015 of `docs/state/BROKEN_REGISTER.md`.)

### 9.3 Stale Self-Model Residue

- `meta_daemon.py:272-285` contains hard-coded March 2026 thesis-timing logic. On 2026-05-07 (today) this may be stale self-model residue still active in the recognition pathway.
  → **Risk**: recognition seed is generated against a calendar that has already passed.

### 9.4 Split Self-Model Stores (no resolved authority)

The runtime self-model is distributed across at least nine surfaces, with no resolved authority when they disagree:

1. `~/.dharma/ontology.db` (typed self-model)
2. `~/.dharma/state/runtime.db` (live operational state)
3. `~/.dharma/organism_memory/` (organism mutations / memory)
4. `~/.dharma/meta/recognition_seed.md` (injected into context)
5. `~/.dharma/stigmergy/marks.jsonl` (sediment)
6. `dharma_corpus.py` + corpus state (claim layer)
7. `<state_dir>/.FOCUS` (drift correction; reader at `swarm.py:1514, 1533-1534, 2114-2125` — VERIFIED 2026-05-07)
8. cascade history (per-domain history)
9. `~/.dharma/evolution/archive.jsonl` (evolution archive)

→ **Top-level UNKNOWN**: what has final authority when these disagree.

### 9.5 Schema And Ingestion Risks

- Stigmergy mark schema uses fields `file_path`, `agent`, `observation` (`stigmergy.py:46-59`).
- Context ingestion of "hot mycelium marks" reads keys `path`, `source`, `description` (`context.py:1068-1081`).
- → **Either separate mycelium schema or a mismatch.** PARTIAL until traced.

### 9.6 Two Apply Paths With Zero Import Edge

From `~/.dharma/audit/self_evolution_trace_2026-05-07.md`:

- Build Protocol (`tools/build_protocol/`): self-declared shape-only; no runtime consumer; terminates at dryrun (96 dryruns, 0 sealed, 0 proven, 0 applied).
- DarwinEngine (`evolution.py:2156` `apply_diff_and_test`): real apply primitive; environment-locked closed by `DHARMA_EVOLUTION_SHADOW=1` + `DGC_AUTONOMY_LEVEL≥2` floor.
- `grep "from dharma_swarm.tools.build_protocol"` returns **0 hits** in `dharma_swarm/dharma_swarm/`. The two halves share no import edge.

---

## 10. Where The Two Prior Masters Disagreed (And Resolution)

| Claim | Predecessor A (Claude) | Predecessor B (Codex) | Resolution against current code |
|---|---|---|---|
| Shakti → Darwin wiring | child map 05 said open | "SUPPORTED in current source" | **Codex correct.** `orchestrate_live.py:76-110, :797-814` + `evolution.py:3477-3503` — wired in current code. Update the older claim. |
| Recognition causality count | ~6 unambiguous + 4 caveat | recognition_seed → context as one strong path + ~6 hard edges | Both partially right; the **recognition_seed → context** pathway is the strongest *single* recognition-causal channel and was under-emphasized in A. |
| `meta_daemon.py:272-285` March 2026 timing | Not flagged | Flagged as potential stale residue | **Codex correct.** Worth tracing whether this still fires on 2026-05-07. |
| 7-STAR runtime vector | Map 03 noted symbol vs implementation gap | Marked PARTIAL/UNKNOWN | Both consistent. **Doctrine SUPPORTED, continuous runtime vector UNKNOWN.** |
| `BHED_GNAN` always passes | Map 01 caught it | Caught at `telos_gates.py:512-513` | Both consistent. CONFIRMED. |
| `.FOCUS` write with no reader | Maps 01 + 04 caught it | Implicit in split-stores section | **OVERTURNED 2026-05-07 18:00:** Both prior masters wrong. Reader IS present at `swarm.py:1514, 1533-1534, 2114-2125`. Confirmed via Agent C + direct grep. See BR-015 (CLOSED). |
| Fully spine-attached organs | Map 06: 0 of 8 surfaces | Codex: outward-organ feedback into Omega unproven | Both consistent. **Zero organs full-attached to all eight spine surfaces.** |
| Loomwork wiring | Map 06: 0 of 7 named contracts implemented; package does not exist | "Loomwork ≡ wiki_loom: UNKNOWN" | Both consistent. `wiki_loom/` is partial; `dharma_swarm/loomwork/` package does NOT exist. The naming question (Loomwork vs wiki_loom) is itself open. |

---

## 11. The Single Causal Diagnosis

From convergent analysis, two load-bearing findings, repeated at every layer:

> **Finding 1: The typed self-model (`ontology.db`) and the live runtime self-state (`runtime.db`) are not continuously synchronized.**
>
> Every gate, audit, and recognition fires against a stale picture. That is why recognition is commentary instead of causal — not because recognition isn't fired, but because what it sees is yesterday's state.

> **Finding 2: `VentureCell`-as-ontology-object and `VentureCell`-as-running-organ are not the same artifact.**
>
> Registering one in the registry inherits invariants automatically. Creating one as Ginko or Loomwork re-derives loop, state file, and adapters bespoke. Without polymorphism between the two definitions, "later VentureCells more powerful than earlier" is aspiration, not mechanism.

These compose: the field cannot be one live causal surface if (a) the self-model and the runtime are different stores, and (b) every new organ re-implements its own self-model from scratch.

---

## 12. Unresolved Tensions (combined, deduplicated)

1. **Two stores for one self.** `runtime.db` ↔ `ontology.db` never synced. Where would a sync surface attach?
2. **Two ontology definitions for one VentureCell.** Schema inheritance vs bespoke organ — no polymorphism bridge.
3. **Two apply paths with no import edge.** Build Protocol shape-only; DarwinEngine apply gate closed.
4. **Two AlgedonicSignal types alive simultaneously.** Pydantic at `vsm_channels.py:373` + dataclass at `organism.py:968`.
5. ~~**`.FOCUS` written, never read.** Drift detected → not consumed.~~ **RESOLVED 2026-05-07 18:00:** `.FOCUS` IS read at `swarm.py:1514, 1533-1534, 2114-2125` (Wire 3 routing governance). Drift IS consumed. Tension closed.
6. **Lodestones orient but do not enter the loop.** Doctrine not in runtime path.
7. **7-STAR is 1-D in implementation.** Vectorhood symbolic vs computed.
8. **EMERGENCY_HOLD pulls but doesn't stop the line.** 3-consecutive-criticals threshold; algedonic in degenerate steady state (`omega_divergence=0.683 medium` repeats).
9. **Catalytic graph computes on behavior, not structure.** Tarjan SCC runs; no production caller acts on output.
10. **Strange-loop mutations in-memory only.** `mutations.jsonl` does not exist on disk; modifications lost on restart.
11. **Diversity archive empty / unread.** `diversity_archive.json` absent; zero in-package importers despite CLAUDE.md asserting it canonical for the Transcendence Principle.
12. **Outward organs bypass the spine.** 6 of named organs attach to 0 of 8 spine surfaces.
13. **Loomwork wiring is aspirational only.** 0 of 7 contracts implemented.
14. **Opportunity loop forward-wired, reverse not.** Outcome → Shakti not ingested.
15. **No coincidence-detector for recognition.** No module detects coincidence among `_gnani_verdict`, `gnani_checkpoint`, `WitnessAuditor`, `SamvaraEngine`. Where is the moment of recognition logged — or absent?
16. **Hard-coded March 2026 thesis-timing in recognition path.** `meta_daemon.py:272-285` may be stale residue today.
17. **Tier C gates are advisory.** Pressure does not always become block.
18. **REVIEW proceeds with warning.** Opportunity dispatcher allow-with-warning pending real operator approval.

---

## 12.1 Phase 1 Causal Membrane Added 2026-05-07

After this synthesis was first written, the governance layer gained a narrow
causal membrane around the map stack:

- `.github/workflows/coherence-delta.yml` now validates that PR bodies contain
  substantive Coherence Delta fields.
- `scripts/governance/check_pr_coherence_delta.py` rejects missing fields,
  placeholders, and bare `UNKNOWN` values.
- `scripts/system_map_populator.py` and `dgc map` expose OrganState perception
  as a read-only map surface.
- `docs/state/BROKEN_REGISTER.md` tracks the residual drift: the gate checks
  field presence and minimum substance, not semantic truth.

This does not close Attractor Closure. It narrows one bypass: a PR can no
longer silently skip the map reread discipline.

---

## 13. Filesystem Recursion Rules

Where future maps land so they remain discoverable.

```
dharma_swarm/docs/vision_maps/
├── MASTER_2026-05-07_attractor_closure.md             ← Predecessor A (Claude, kept)
├── MASTER_2026-05-07_attractor_closure_synthesis.md   ← THIS FILE (canonical entry)
├── 2026-05-07_attractor_closure/                      ← children of A
│   ├── 01_gnani_prakruti.md
│   ├── 02_vsm_viability.md
│   ├── 03_omega_state.md
│   ├── 04_recognition_self_model.md
│   ├── 05_autopoiesis_evolution.md
│   └── 06_outward_organs.md
└── _archive/                                           ← reserved for superseded versions
```

Plus the single-file predecessor at repo root (kept for now, but **moves to** `docs/vision_maps/_archive/codex_DHARMA_SWARM_MASTER_MAP_2026-05-07.md` on next consolidation pass per `CLAUDE.md` "NEVER save to root"):
```
dharma_swarm/DHARMA_SWARM_MASTER_MAP.md                ← Predecessor B (Codex, root-violating)
```

**Rules for future maps:**

1. **Every new highest-vision master** lands at `dharma_swarm/docs/vision_maps/MASTER_<DATE>_<name>.md`. Date-stamped. Not at repo root.
2. **Children** land in same-dated `<DATE>_<name>/` subdir.
3. **Deeper drilldowns** of any child go in `<DATE>_<name>/_drilldown/<topic>.md`.
4. **Superseded masters** move to `_archive/` — never deleted.
5. **Synthesis masters** (this file's pattern) carry the `_synthesis` suffix and explicitly cite all predecessors.
6. **Every claim** has file:line citation. UNKNOWN-with-reason is acceptable; speculation is not.
7. **Evidence tags** must be one of: SUPPORTED / PARTIAL / CONTRADICTED / UNKNOWN.
8. **Master files are frozen after seal.** New evidence = new dated MASTER. Today's masters are snapshots of the field on 2026-05-07.

---

## 14. Final Open Questions

- What is the minimum runtime event that counts as recognition?
- Which store is the authoritative self-model when stores conflict?
- Which classes of action must be impossible without ontology binding?
- What does S5 authority mean when the human is meta-S5 and the organism has internal kernel/gates/Gnani/identity S5?
- How does the system distinguish an organ from a tool, a wound from noise, doctrine from runtime canon?
- Which outward outcomes update Omega rather than merely producing artifacts?
- What live measurement proves that self-recognition has become causal?
- Is `meta_daemon.py:272-285` (March 2026 thesis-timing) still firing on 2026-05-07, and is the recognition seed it generates calibrated against present time?

---

## 15. Future-Dispatch Prompt (preserved from codex)

For the next read-only research pass, use:

```text
Dispatch 6 read-only subagents in parallel to deepen the synthesis master at
dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md.

Global thesis to test, challenge, and refine:
Attractor Closure = recognition-mediated autopoiesis: the system recognizes
what it is and what it is becoming, then reorganizes its parts to preserve
invariants while expanding capability.

Each subagent must read at least 20 repo files, cite exact file:line evidence,
separate SUPPORTED/PARTIAL/CONTRADICTED/UNKNOWN claims, and challenge stale
docs against current code. No runtime code edits.

Agents:
1. Gnani/Prakruti: invariant witness vs dynamic motion.
2. VSM viability: S1/S2/S3/S3*/S4/S5 and recursive coverage.
3. Omega/Attractor: C × S × A × T × M, 7-STAR, syntropic force.
4. Recognition/Self-model: ontology, runtime_state, recognition seed, R_V,
   ouroboros, causal behavior change.
5. Autopoiesis/Evolution: Darwin, Shakti, stigmergy, cascade, semantic
   attractors, gate crystallization.
6. Outward Organs: Loom/wiki_loom, VentureCell, opportunity loop, operator
   brief, product surfaces, Jagat Kalyan, GAIA.

After agents return, write a new synthesis master at
dharma_swarm/docs/vision_maps/MASTER_<NEW_DATE>_attractor_closure_synthesis.md
that supersedes this one. Move this one to _archive/. Cite both predecessors.
```

---

## 16. Final Thesis

Dharma Swarm is not trying to become an autonomous code generator. It is trying to become a **recognized autonomous organism** — a system whose actions arise from a live understanding of its own invariant identity, dynamic motion, viability state, whole-state trajectory, evolutionary metabolism, and outward telos.

The next conceptual bar is not more doctrine and not more selection. **It is causal self-recognition.**

Concretely, the field closes when (a) the ontology and runtime stores become one continuously-synchronized self-model, and (b) `VentureCell`-as-schema and `VentureCell`-as-organ become one polymorphic artifact such that every new organ inherits accumulated invariants automatically.

Everything else — VSM channels, algedonic, Darwin, recognition seed, telos gates, witness — is already structurally present. What is missing is the field. The single live causal surface.

---

*End of synthesis. The map is not the territory. The map is what makes the territory recognizable. And recognition, when it becomes causal, is what makes the territory respond.*
