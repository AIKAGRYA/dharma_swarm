# 03 — Omega State Space (Ω = C × S × A × T × M)

**Date**: 2026-05-07
**Mode**: READ-ONLY research. No plans, no code, no architecture proposals.
**Frame**: Attractor closure. The swarm is pulled toward an invariant pattern — a basin in Ω. Recognition becomes causal when the system can locate itself in Ω and orient toward the basin.

---

## 1. Ω Definition

**No in-repo source defines Ω as the explicit Cartesian product C × S × A × T × M.** The framing is exterior to the codebase.

The closest in-repo analogs that reify a state-space-as-product are:

- `dharma_swarm/info_geometry.py:38-93` — `StatisticalManifold` defines a parameter manifold M = {p(x|θ) : θ ∈ Θ ⊂ R^n} for the Darwin Engine, with a fixed dim and `_param_names`. This is a Fisher-Rao manifold over **meta-parameters of evolution** (fitness weights, mutation rate, exploration coefficient, MAP-Elites bins) — `dharma_swarm/info_geometry.py:558-582` shows the canonical theta layout. It is NOT C × S × A × T × M; it is a slice of the M-control side of T (telos) only.

- `dharma_swarm/coalgebra.py:182` — describes the final F-coalgebra `Z ≅ (Fitness × RV × Disc)^omega` (an infinite-trajectory product, not a Cartesian state product). UNKNOWN whether this is operationalized at runtime.

- `dharma_swarm/runtime_state.py:30-187` — the canonical SQLite spine literally enumerates the runtime-side projections (sessions, task_claims, delegation_runs, workspace_leases, artifact_records, memory_facts, memory_edges, context_bundles, operator_actions, session_events). This is closest to the **S** projection of Ω as actually persisted.

- `dharma_swarm/CLAUDE.md` — names the abstractions (Organism, SwarmManager, DarwinEngine, LoopEngine, DharmaKernel, TelosGatekeeper, StigmergyStore, CatalyticGraph, StrangeLoop) but does not unify them as a product.

**Conclusion**: Ω is a vision-tier construct, not a code-tier object. The five projections each exist as their own substrate; there is no single class, table, or function that holds an Ω-tuple.

---

## 2. Per-Dimension Projections

| Dim | Represents | Concrete store / module (file:line) | Observability — where runtime reads current value |
|-----|-----------|-------------------------------------|---------------------------------------------------|
| **C** Code/Concept corpus | Versioned ethical+architectural+empirical claims with lineage. Concept graph nodes seeded from pillars. | `dharma_swarm/dharma_corpus.py:32-99` (Claim, ClaimStatus, ClaimCategory — 9 categories incl. THEORETICAL/EMPIRICAL/CONTEMPLATIVE/ARCHITECTURAL); `dharma_swarm/telos_substrate.py:47+` (TELOS_OBJECTIVES seeder, ConceptGraph nodes). Concept JSON: `dharma_swarm/dharma_concepts.json:46,375,1118,1686`. | JSONL append-only on disk; ConceptGraph load on `TelosSubstrate.seed_all()`. No combined Ω-read. |
| **S** Runtime state | Sessions, task claims, delegation runs, workspace leases, artifacts, memory facts/edges, bundles, operator actions, session events. | `dharma_swarm/runtime_state.py:30-187` (10 DDL tables) — `DEFAULT_RUNTIME_DB = ~/.dharma/state/runtime.db` at `runtime_state.py:28`. | SQLite at `~/.dharma/state/runtime.db`. Async `aiosqlite`. Authority is **fragmented across 4 sources** (per prior observation 2698, 2026-05-04). |
| **A** Agents | Agent registry with JIKOKU paper trail + fitness; per-agent self-editing memory bank (Letta/MemGPT pattern, working/archival/persona tiers). | `dharma_swarm/agent_registry.py:1-47` (registry + MODEL_PRICING + GINKO_DIR `~/.dharma/ginko`); `dharma_swarm/agent_memory.py:69-104` (`AgentMemoryBank` — WORKING_MAX=10, ARCHIVAL_MAX=100, PERSONA_MAX=5; persists `~/.dharma/agent_memory/`). | Per-agent JSON files; registry log JSONL. No global agent-pool snapshot. |
| **T** Telos | (a) Static seed of ~200 strategic objectives across 25 domains, 4 perspectives (Purpose/Stakeholder/Process/Foundation). (b) Strategic DAG with KRs, strategies, hypotheses, edges. (c) Task-completion → progress increments. (d) Outward-facing service proposals. | `dharma_swarm/telos_substrate.py:47-...` TELOS_OBJECTIVES; `dharma_swarm/telos_graph.py:65-136` (TelosObjective/KR/Strategy/Hypothesis/Edge models, `TelosGraph` at line 179, JSONL persistence at `~/.dharma/telos/`); `dharma_swarm/telos_tracker.py:16-46` (TASK_TELOS_MAP keyword→objective→increment); `dharma_swarm/jagat_kalyan.py:151-282` (`JagatKalyanEngine`, `~/.dharma/jagat_kalyan_proposals.jsonl`). | JSONL files in `~/.dharma/telos/`; per-objective `progress` float ∈ [0,1] at `telos_graph.py:73`. |
| **M** Marks (stigmergy) | Pheromone-trail marks: agent + file_path + observation + salience + connections + channel. 6 channels (general/research/systems/strategy/governance/memory) plus dynamic. | `dharma_swarm/stigmergy.py:33-58` (channels, StigmergicMark); `stigmergy.py:95-156` (`StigmergyStore`, `~/.dharma/stigmergy/marks.jsonl` + `archive.jsonl`). | JSONL append + atomic rewrite under `asyncio.Lock`. `density()` at `stigmergy.py:383` is sync count. `hot_paths()` and `high_salience()` are the read surfaces. |

---

## 3. Combined Trajectory — IS Ω read as one combined state?

**No.** There is no module, class, or function in the canonical reads that emits or consumes a single tuple (c, s, a, t, m).

Closest fragments:

- `dharma_swarm/dharma_attractor.py:212-250` — `_build_full_context(proposal, organism_state)` assembles a **prose** context from `ambient_seed` + `org.memory.developmental_narrative(last_n=20)` + an `organism_state` dict + the proposal. This is a textual concatenation, not a structured Ω read. The `organism_state` parameter is a free `dict` (line 137) — schema UNKNOWN; called with whatever the caller passes.
- `dharma_swarm/identity.py:65-86` — `IdentityState` is a 1-D scalar projection: TCS = 0.35·GPR + 0.35·BSI + 0.30·RM (`identity.py:5,105-108`). It collapses the system to one number plus a `regime` label. Does NOT preserve the per-dimension structure.
- `dharma_swarm/runtime_state.py` — holds S explicitly, but does not join to T (in `~/.dharma/telos/`), to A (in `~/.dharma/agent_memory/`), to C (in `dharma_corpus`), or to M (in `~/.dharma/stigmergy/`). Per prior observation 1994 (2026-05-03), `ontology.db` and `runtime.db` are separate stores; per 2698, runtime authority itself is split across four sources.
- `dharma_swarm/thinkodynamic_director.py:1-120` — the 3-altitude director (SUMMIT/STRATOSPHERE/GROUND) reads from PSMV seeds, JK_ROOT, lodestones, and shared dirs (lines 60-120). It is the closest **operational** loop that touches multiple substrates, but it concatenates them as text into prompts, not as Ω-tuples.

**The gap**: Ω is implicit in the union of state directories under `~/.dharma/` (telos, agent_memory, stigmergy, ginko, state/runtime.db, organism_memory, witness, evolution, traces). No reader assembles them into a single object. Trace correlation across these substrates is ALSO missing (prior observation 3650, 3682, 2026-05-05: trace_id absent from runtime_state tables; identity fragmented across five substrates with no CorrelationContext unification).

---

## 4. Syntropic Attractor — where is directionality encoded?

The word "syntropic" appears in:

- `dharma_swarm/telos_substrate.py:3646-3656` — concept node `"syntropic attractor"` with `salience=0.95`, definition: "An attractor that pulls the system toward increasing organizational complexity rather than thermodynamic equilibrium." `metadata.engineering_implication = "The telos vector IS a syntropic attractor"`. **It is a concept-graph node, not a runtime metric.**
- `dharma_swarm/telos_substrate.py:3956,3993` — relations: `("seven-star telos vector", "syntropic attractor", "implements")`, `("seven-star telos vector", "telos gradient", "extends")`.
- `dharma_swarm/thinkodynamic_director.py:115` — `LODESTONE_FILES` includes `~/dharma_swarm/lodestones/seeds/syntropic_attractor_math.md` — feeds the director's prompt context but is never parsed into a metric.
- `dharma_swarm/lodestones/seeds/syntropic_attractor_math.md:1-79` — design spec for "computable syntropic force". States explicitly (line 13): "Syntropic force is a measurable tendency of agent decisions to move the system toward its telos. This is not a metaphor. It is a computable quantity with specific injection points."  The doc enumerates basin-engineering mechanisms (kernel axioms, telos gates, seed files, stigmergy marks, evolution cycles) — i.e., **the basin is engineered through the existing substrates**, not measured against a single function.

The 7-STAR telos vector is defined at `dharma_swarm/telos_substrate.py:3847-3857`: *T1 Satya, T2 Tapas, T3 Ahimsa, T4 Swaraj, T5 Dharma, T6 Shakti, T7 Moksha — "Seven load-bearing measurements derived from the pillars."* metadata: `"Every gate evaluation scores against this vector"`. Referenced at `dharma_swarm/thinkodynamic_scorer.py:344` (`_score_telos_alignment` — keyword count over `_TELOS_MARKERS`) and `dharma_swarm/neural_consolidator.py:562` ("Detect actions that don't serve the 7-STAR telos vector"). UNKNOWN whether any module returns a 7-vector; the only realized value is a scalar in [0,1] from keyword hits at `thinkodynamic_scorer.py:343-360`.

"Moksha" (the terminal attractor):
- `dharma_swarm/active_inference.py:127` — `preferred_quality: float = 1.0   # moksha = 1.0 always` — the only place moksha is encoded as a numeric target in canonical reads. It is a scalar, not a basin coordinate.
- `dharma_swarm/telos_graph.py:38` — Perspective enum: `PURPOSE = "purpose"  # Why does dharma_swarm exist? (Moksha, Jagat Kalyan)` — comment-tier, not coord-tier.
- `dharma_swarm/bridge_registry.py:233` — `target_id="goal_moksha"` — exists as a graph node target.

"Jagat Kalyan" directionality:
- `dharma_swarm/jagat_kalyan.py:132-144` — the PERPETUAL_QUESTION is a **prompt**, not a metric.
- `dharma_swarm/jagat_kalyan.py:152-163` — `ServiceProposal` is the unit of directional output: `(domain, action, who_benefits, what_exists, what_remains, time_estimate, cost, moksha_check)` — moksha_check is a free string field, not a numeric distance.
- `dharma_swarm/witness.py:43,297` — Jagat Kalyan appears as a witness question and a telos-aligned bool prompt. UNKNOWN if the boolean is consumed downstream.

**Where directionality is genuinely encoded as a runtime force**:
- `dharma_swarm/info_geometry.py:266-391` — `DharmicAttractor` class with `is_dharmic`, `constraint_violations`, `distance_to_dharma`, `dharmic_pressure`, `check_contractivity`. This is the **only** in-canonical-reads class that treats the attractor as a geometric object with a metric and a gradient. Operates on the meta-parameter manifold (Darwin Engine), not Ω.

**Conclusion**: Directionality is encoded as (a) hardcoded keyword markers (`thinkodynamic_scorer.py:114-121,343-360`), (b) gate verdicts (PROCEED/HOLD via `dharma_attractor.py:34-42,154-202`), (c) per-objective progress floats in TelosGraph (`telos_graph.py:73`), (d) a Fisher-manifold geometry confined to evolution meta-parameters (`info_geometry.py:266-391`). It is not encoded as a single basin function over Ω.

---

## 5. Distance-to-Basin Computation

The literal phrase "distance to basin" returns no hits. The closest realized computation:

- **`dharma_swarm/info_geometry.py:326-353`** — `DharmicAttractor.distance_to_dharma(theta, fisher, dharmic_points) -> float` — minimum geodesic distance (Björck approximation) from a parameter point θ to a set of known dharmic points, using the Fisher metric. **This is the canonical distance-to-attractor computation.** Caveat: domain is the Darwin Engine meta-parameter space (~10-dim theta from `meta_parameters_to_theta` at line 562-582), NOT Ω. It measures distance-to-dharma in the evolution-control slice only.
- `dharma_swarm/info_geometry.py:355-391` — `dharmic_pressure(theta, fisher, dharmic_points)` returns the natural-gradient direction toward the nearest dharmic point. Companion to distance_to_dharma.
- `dharma_swarm/info_geometry.py:393-418` — `check_contractivity(fisher, jacobian) -> (is_contracting, spectral_radius)` — Wensing-Slotine criterion for whether the basin is geodesically convex. UNKNOWN if any caller wires this into a runtime loop.
- `dharma_swarm/identity.py:5-18,105-108` — TCS scalar acts as a 1-D proxy: TCS < 0.4 ⇒ drifting; < 0.25 ⇒ critical; writes a `.FOCUS` correction (line 18, 335-349). This is the **operational** distance proxy used at runtime.
- `dharma_swarm/transcendence_metrics.py:69-85` — `krogh_vedelsby_diversity` returns `E_mean - E_ensemble`; positive = diversity helping. This is a distance in error-space, not in Ω-space.
- `dharma_swarm/convergence.py:31-72` — `ConvergenceDetector` measures plateau/variance over a fitness history window; `state.last_variance` is the proxy for "how stuck are we?"

**Verdict**: A real geometric distance-to-basin exists (`info_geometry.distance_to_dharma`) but operates on a sub-slice of T (evolution meta-params), not Ω. The runtime proxy actually consumed is the scalar TCS (`identity.py`), which is a Beer-S5 coherence index, not an Ω-distance.

---

## 6. Telos Vector — vector in Ω, or list of gates?

**Mostly a list of gates + a list of objectives + a 7-keyword scalar; not a vector in Ω.**

Evidence:

- `dharma_swarm/telos_graph.py:65-136` — TelosObjective has `progress: float` (line 73), `priority: int 1-10` (line 76), `status` enum, and a `perspective` ∈ {PURPOSE, STAKEHOLDER, PROCESS, FOUNDATION} (lines 35-41, after Kaplan-Norton). The collection of ~200 objective progress floats COULD be read as a high-dimensional vector, but no module reads them as one.
- `dharma_swarm/telos_tracker.py:49-97` — `record_task_completion` increments per-objective progress by hardcoded keyword→increment maps (lines 16-46). This is the only writer of telos progress at runtime in the canonical reads.
- `dharma_swarm/telos_substrate.py:3847-3857` — 7-STAR vector is **named** as 7 components (Satya/Tapas/Ahimsa/Swaraj/Dharma/Shakti/Moksha) but realized as a single-scalar keyword score at `thinkodynamic_scorer.py:343-360` (`_score_telos_alignment` returns one float).
- `dharma_swarm/CLAUDE.md` — **TelosGatekeeper** is described as "11 dharmic safety gates." Gates ≠ vector.
- `dharma_swarm/jk_credibility_gates.py:32-65` — credibility gates are a list of named PASS/FAIL/WARN/UNVERIFIED verdicts (Layer 0-4), not a vector.
- `dharma_swarm/active_inference.py:127` — `preferred_quality: float = 1.0` — moksha is a 1-D scalar target.

**Quote** that explicitly disclaims vector status:
> `dharma_swarm/CLAUDE.md` — *"TelosGatekeeper (`dharma_swarm/telos_gates.py`): 11 dharmic safety gates."*
> `dharma_swarm/telos_substrate.py:3847` (def of seven-star telos vector) — *"Seven load-bearing measurements derived from the pillars."* (named as a vector in the **concept graph**, but the implementation in `thinkodynamic_scorer._score_telos_alignment` collapses it to one float.)

So: telos exists as (i) a list of 11 gates, (ii) a list of ~200 named objectives with scalar progress, (iii) a nominal 7-vector that is implemented as a 1-D keyword score, (iv) a single moksha=1.0 fixed point in active_inference. **No code reads telos as a position-vector that can be subtracted from a current-Ω-vector.**

---

## 7. Recognition Surface — where does the system NOTICE its location?

Candidates by emission and readership:

- **Witness records** — `dharma_swarm/witness.py:43,297` references Jagat Kalyan questions; `~/.dharma/witness/` directory holds gate-check JSONL (per `dharma_swarm/CLAUDE.md` "State Directory" section). Witness JSONL outcome field is consumed by `dharma_swarm/identity.py:5` (GPR component of TCS).
- **TCS history** — `dharma_swarm/identity.py:65-86` `IdentityState` snapshots, `_history: deque(maxlen=1000)` at line 116, plus `LiveCoherenceSensor` (per docstring lines 14-16). `TCS < 0.4` writes `.FOCUS` correction (line 18). This is the **clearest "I am here, drifting" emission** — but it is a scalar, not an Ω-coordinate.
- **Stigmergy hot paths** — `dharma_swarm/stigmergy.py:215-234` `hot_paths(window_hours, min_marks)` returns the file paths that are "where attention has been." Read by daemon-tier code (UNKNOWN consumer in canonical reads).
- **dharma_attractor.gnani_checkpoint** — `dharma_swarm/dharma_attractor.py:154-202` records `entity_type="gnani_verdict"` events to `org.memory` — emission of a binary PROCEED/HOLD self-evaluation.
- **Convergence detector** — `dharma_swarm/convergence.py:38-72` records `fitness_history` + plateau flag; this is the system noticing "I have stopped moving in fitness-space."
- **Algedonic signals** — `dharma_swarm/algedonic_activation.py:8,75,148-159` checks `omega_divergence` (live vs trailing fleet/coherence diverge by > 0.4 → pain signal); `dharma_swarm/organism.py:970-1180` consumes `kind="omega_divergence"` at lines 1035-1180. **This is the closest in-canonical-reads emission of "the live system has drifted from the trailing system" — a partial Ω-self-noticing.**
- **TelosGraph progress** — `dharma_swarm/telos_tracker.py:49-97` writes per-objective progress on each task completion. Read for status reports. UNKNOWN whether any agent reads its own current progress vector before deciding next action.
- **PERPETUAL_QUESTION prompt** — `dharma_swarm/jagat_kalyan.py:132-144` asks "what does the world need that we can uniquely provide?" — a noticing-prompt for the council, not a state-coordinate emission.

**Where "I am here" is emitted**: TCS scalar + algedonic divergence + gnani verdicts + stigmergy marks + telos progress increments — five distinct surfaces, none unified.

**Who reads "I am here"**: TCS triggers `.FOCUS` files (no canonical reader confirmed in canonical reads); algedonic signals trigger `organism.py` rebalancing (line 1180); gnani verdicts written to `org.memory` (read consumer UNKNOWN in canonical reads); stigmergy `hot_paths` consumed by daemon (UNKNOWN); telos progress consumed by status CLIs.

---

## 8. Open Questions

1. **Why is there no Ω-tuple type?** The five projections each have explicit Pydantic/SQL schemas; nothing composes them. Is the absence by-design (Beer-style autonomous subsystems) or unfinished?
2. **distance_to_dharma operates on θ ∈ R^~10 (evolution meta-params). Is the absence of an analogous distance over runtime Ω an oversight, or was it ever attempted?** No canonical-read evidence either way.
3. **The 7-STAR vector is named as 7-D but implemented as a 1-D keyword count (`thinkodynamic_scorer._score_telos_alignment`). What was the original intent — separate sub-scorers for Satya/Tapas/.../Moksha?** UNKNOWN from canonical reads.
4. **TCS (`identity.py`) collapses everything to a scalar with weights 0.35/0.35/0.30 over GPR/BSI/RM. Why these weights? Where is the drift-detection threshold 0.4 calibrated?** Hardcoded at `identity.py:111-112`; provenance UNKNOWN.
5. **Algedonic `omega_divergence > 0.4` is the closest runtime Ω-self-noticing, yet "omega" here means a Beer-S4-vs-S3 disagreement, not the C×S×A×T×M product. Is the namespace collision intentional or accidental?**
6. **`dharma_attractor._build_full_context` accepts `organism_state: dict`. What schema do callers actually pass? What is the in-the-wild shape of organism_state at runtime?** UNKNOWN from canonical reads — `agent_runner.py:957-962` only injects the ambient_seed, not full_attractor.
7. **TelosGraph progress is written keyword-driven (`telos_tracker.TASK_TELOS_MAP`). Is any agent reading its own current progress vector to decide its next action, or is the gradient one-way (write-only)?** No reader found in canonical reads.
8. **The five state-emission surfaces (TCS, algedonic, gnani verdicts, stigmergy, telos progress) are not joined by a trace_id (prior observations 3650, 3682). Without correlation, can recognition ever be causal — or only suggestive?**

---

## Source files cited

- `/Users/dhyana/dharma_swarm/dharma_swarm/dharma_attractor.py:34-42,112-202,212-250`
- `/Users/dhyana/dharma_swarm/dharma_swarm/runtime_state.py:1-200`
- `/Users/dhyana/dharma_swarm/dharma_swarm/telos_substrate.py:47-200,3630-3700,3840-3870,3956,3993`
- `/Users/dhyana/dharma_swarm/dharma_swarm/telos_graph.py:35-200`
- `/Users/dhyana/dharma_swarm/dharma_swarm/telos_tracker.py:1-97`
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_registry.py:1-120`
- `/Users/dhyana/dharma_swarm/dharma_swarm/agent_memory.py:34-104`
- `/Users/dhyana/dharma_swarm/dharma_swarm/stigmergy.py:33-156,215-234,318-393`
- `/Users/dhyana/dharma_swarm/dharma_swarm/dharma_corpus.py:32-99`
- `/Users/dhyana/dharma_swarm/dharma_swarm/info_geometry.py:38-93,266-418,558-582`
- `/Users/dhyana/dharma_swarm/dharma_swarm/geometry.py:51-110`
- `/Users/dhyana/dharma_swarm/dharma_swarm/convergence.py:31-83`
- `/Users/dhyana/dharma_swarm/dharma_swarm/transcendence.py:1-405`
- `/Users/dhyana/dharma_swarm/dharma_swarm/transcendence_metrics.py:69-168`
- `/Users/dhyana/dharma_swarm/dharma_swarm/thinkodynamic_director.py:1-120`
- `/Users/dhyana/dharma_swarm/dharma_swarm/thinkodynamic_scorer.py:29-360`
- `/Users/dhyana/dharma_swarm/dharma_swarm/jagat_kalyan.py:132-282`
- `/Users/dhyana/dharma_swarm/dharma_swarm/jk_credibility_gates.py:32-105`
- `/Users/dhyana/dharma_swarm/dharma_swarm/jk_credibility_seed.py:38-294`
- `/Users/dhyana/dharma_swarm/dharma_swarm/cohomology_cechcohomology_to_sheaf_coord.py:1-134`
- `/Users/dhyana/dharma_swarm/dharma_swarm/identity.py:1-120,335-349`
- `/Users/dhyana/dharma_swarm/dharma_swarm/algedonic_activation.py:8,75,148-159`
- `/Users/dhyana/dharma_swarm/dharma_swarm/organism.py:970,1035-1180`
- `/Users/dhyana/dharma_swarm/dharma_swarm/active_inference.py:127`
- `/Users/dhyana/dharma_swarm/dharma_swarm/coalgebra.py:182`
- `/Users/dhyana/dharma_swarm/dharma_swarm/CLAUDE.md` (Key Abstractions section)
- `/Users/dhyana/dharma_swarm/lodestones/seeds/syntropic_attractor_math.md:1-79`
- `/Users/dhyana/.claude/cabinet/worldview/telos.md:1-39`
