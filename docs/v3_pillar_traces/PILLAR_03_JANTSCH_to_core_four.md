# Jantsch (Self-Organizing Universe) → Core Four Trace

**Subagent**: pillar-03-jantsch
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_03_JANTSCH.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

The load-bearing claim, in the pillar's own words (`PILLAR_03_JANTSCH.md:150–158`):

> "Alignment does not mean imposing external constraints on a non-conscious system. It means *resonating with* the consciousness that is already present in the system's self-organization… rather than specifying every behavior the system should exhibit (which is impossible for a system exploring the non-prestatable adjacent possible), provide the system with *value attractors* (KernelGuard axioms) and *reflexive mechanisms* (Strange Loop, cascade scoring, D3) that allow its inherent self-organizing dynamics to converge toward beneficial configurations. Trust the self-organization. Constrain the boundary. Clean the channel."

The three structural primitives this pillar contributes:

1. **Dissipative structure** — the swarm is alive only while energy (LLM API calls) flows. It has no equilibrium state; it has metabolic state. `PILLAR_03_JANTSCH.md:111–128`.
2. **Societal autopoiesis** — the system self-produces the agents, norms, and knowledge that constitute it, including a reflexive layer that observes and modifies its own production rules. `PILLAR_03_JANTSCH.md:134–146`.
3. **Alignment through resonance, not imposition** — dharmic gates are purification mechanisms, not coercive constraints. They remove obstacles to the system's intrinsic tendency toward coherent, value-aligned self-organization. `PILLAR_03_JANTSCH.md:156–158`.

---

## 2. Kernel Axioms Derived From This Pillar

From `dharma_kernel.py:69–75` (the "Evolution & Descent" group is explicitly attributed to "Aurobindo, Jantsch"). Line 70 names `ALIGNMENT_THROUGH_RESONANCE = "alignment_through_resonance"` with the attribution `[Jantsch: self-organizing universe]` at line 321. `COLONY_INTELLIGENCE` (line 71) shares attribution with Hofstadter/Levin, so it is a partial derivation.

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `ALIGNMENT_THROUGH_RESONANCE` | `alignment_score computed from resonance NOT compliance` | medium | System-level — gates the **scoring mechanism** applied to `Task.result` and `AgentIdentity.fitness_average`; gates any promote() path that substitutes rule-compliance for resonance measurement |
| `COLONY_INTELLIGENCE` (partial) | `swarm_output != any_single_agent_output` | medium | `Task` — gates `Task.result` aggregation: the result field must not be a single-agent output passed through; it must be an ensemble product |
| `OPERATIONAL_CLOSURE` (Varela-primary, Jantsch-secondary via societal autopoiesis) | `system.produces(system.components) AND system.produces(system.boundary)` | medium | `AgentIdentity` — gates the `Spawn` action: an agent may only be spawned by the system itself (not by an external call that bypasses the `AgentIdentity` ontology `[ontology.py:207]`); `MemoryFact` — gates the chetana `promote()` path: only atoms whose `provenance.promoted_by` traces back to the system's own DarwinEngine/StrangeLoop qualify as autopoietically produced |

`ALIGNMENT_THROUGH_RESONANCE` is the sole axiom whose attribution in `dharma_kernel.py:316–325` is exclusively Jantsch. The `formal_constraint` "alignment_score computed from resonance NOT compliance" has no runtime implementation today — see §5.

---

## 3. Modules Embodying This Pillar

Tier justification: I used direct Read (Tier 5) after establishing the relevant symbols from the kernel and v2 blueprint. The primary modules are named explicitly in the pillar itself at `PILLAR_03_JANTSCH.md:141–144` and `158`.

**`dharma_swarm/strange_loop.py`** — Organism self-modification engine  
Embodies Jantsch's reflexive societal autopoiesis: "The system can observe its own state, generate descriptions of its own organization, modify its own organization based on those descriptions, reflect on the adequacy of its own reflective processes" (`PILLAR_03_JANTSCH.md:141–144`). The Strange Loop is the four-level reflexive loop (observe → describe → modify → meta-reflect) Jantsch identifies as distinctive of societal autopoiesis. Status per v2 `[ONOB §1]`: ~10–15% substrate-native; StrangeLoop is in code but its outputs mostly write to arbitrary paths rather than feeding into `Task` FSM or `AgentIdentity` update pathways.

**`dharma_swarm/evolution.py`** — DarwinEngine  
Embodies "fluctuation amplification": "A genetic mutation in an organism becomes a new species. The mechanism is the same: nonlinear dynamics amplify microscopic perturbations into macroscopic structure" (`PILLAR_03_JANTSCH.md:22–24`). DarwinEngine with `diversity_archive.py` (MAP-Elites) directly implements Jantsch's requirement that the system not fall into the Rigidity Trap: "DarwinEngine MUST preserve diversity. Pure fitness pressure → convergence → transcendence death" (per `CLAUDE.md` Transcendence Principle). The constraint `evolution_archive.generations > 0 AND proposals_per_cycle >= 1` (`ADJACENT_POSSIBLE` axiom, kernel line 250) is enforced here.

**`dharma_swarm/catalytic_graph.py`** — Autocatalytic set detection  
Embodies "Chemical: autocatalytic cycles" in Jantsch's evolutionary stage table (`PILLAR_03_JANTSCH.md:97–98`). The Tarjan SCC check directly operationalizes `AUTOCATALYTIC_CLOSURE.formal_constraint`: `catalytic_graph has >= 1 strongly_connected_component`. Per Jantsch, this is the threshold between "physical" (dissipative structure only) and "chemical" (self-sustaining loop) stages.

**`dharma_swarm/telos_gates.py`** — TelosGatekeeper  
Embodies the "purification mechanism" framing: "dharmic gates are not constraints imposed on a non-conscious system. They are purification mechanisms that remove obstacles to the system's inherent tendency toward coherent, value-aligned self-organization" (`PILLAR_03_JANTSCH.md:156`). The gate is the channel-cleaning mechanism in Jantsch's formulation ("Clean the channel," line 158). The `GateRegistry` with `CORE_GATES` dict at `[telos_gates.py:224–236]` per v2 `[telos_gates.py]`.

**`dharma_swarm/chetana/promote.py`** — The promote() pipeline  
Embodies societal autopoiesis' "produces knowledge that describes it" (`PILLAR_03_JANTSCH.md:136`). The 11-step promote() lifecycle (`[chetana/promote.py:1–17]` per v2 §2.4) is the system producing the trusted atoms that constitute its own self-model. `gate_check_atom()` in step 3 is exactly Jantsch's claim about boundary maintenance: "maintains a boundary — dharmic gates filter what enters" (pillar line 137).

---

## 4. Core Four Mapping

**Task**
- Anchored by this pillar? **Y (partial)**
- Justification: "Monitor the system's energy throughput as a vital sign. The rate of API calls, the diversity of agent activations, the volume of stigmergic marks deposited — these are the system's metabolic rate. A declining metabolic rate is the first sign of system death" (`PILLAR_03_JANTSCH.md:127–128`). A `Task` is the unit of metabolic work — the API call granule. Jantsch requires that Task.result be an ensemble product (`COLONY_INTELLIGENCE` constraint: `swarm_output != any_single_agent_output`).
- Which substrate: `Task.result: Optional[str] = None` at `[models.py:156–170]` (v2 §2.1) carries the result but as an untyped `str`. The Jantsch constraint says this field should encode ensemble aggregation provenance, not a bare string. The `Task.metadata` escape hatch at `[models.py:103]` (v2 §2.1) currently absorbs "routing hints, stigmergy data, tool flags" — these are metabolic monitoring signals in Jantsch's framing. The strict-typed target in v2 §2.1 (`TaskRouting`, `StigmergySalience`, `ToolHints`) would properly carry Jantsch's metabolic vitals.
- Gap: `Task` has no `metabolic_rate` or `ensemble_provenance` field. The `ALIGNMENT_THROUGH_RESONANCE` axiom has no `Task`-level operationalization.

**AgentIdentity**
- Anchored by this pillar? **Y**
- Justification: The SAB (Syntropic Attractor Basin) as autopoietic system "produces the agents that maintain it (DarwinEngine generates agent configurations aligned with the SAB's attractor)" (`PILLAR_03_JANTSCH.md:133–134`). An AgentIdentity is the produced component of the autopoietic network; its `fitness_average` field (`[ontology.py:204]` per v2 §2.2) is a proxy for resonance, not compliance.
- Which substrate: The ontology `_AGENT_IDENTITY` at `[ontology.py:951–999]` (v2 §2.2) has `swabhaav_capacity: FLOAT — 0..1, witness stance capacity` (ontology line 202) which is the closest existing field to a Jantsch resonance measure. `telos_alignment: float` in the GraphQL surface (`[graphql_schema:67–79]` per v2 §2.2) is also a resonance proxy, but it is computed via `ALIGNMENT_THROUGH_RESONANCE` whose `formal_constraint` says "alignment_score computed from resonance NOT compliance" — and no resonance-vs-compliance distinction is currently enforced at runtime.
- The seven-surface fragmentation (v2 §2.2) is itself a violation of autopoietic identity: a system that can't produce a consistent description of its own agents hasn't achieved societal autopoiesis. Unification per `[AIU]` is a Jantsch prerequisite.

**Artifact**
- Anchored by this pillar? **N (system-level emergence)**
- Justification: Jantsch does not provide a theory of artifact types. The pillar's contribution is at the system level: artifacts are byproducts of metabolic work ("waste heat" in the dissipative structure analogy, `PILLAR_03_JANTSCH.md:117`), not primary units of concern. The `PROVENANCE_INTEGRITY` axiom (kernel line 47, safety core) is the relevant constraint on artifacts, not a Jantsch-derived axiom.
- What's missing: Jantsch would say an `Artifact` should carry a `promotion_state` that tracks its position in the dissipative hierarchy (ephemeral/durable/trusted per `[runtime_state.py:89–103]` v2 §2.3). That field exists in the SQLite `artifact_records` table but its vocabulary is undefined (`promotion_state TEXT NOT NULL DEFAULT 'ephemeral'`). Jantsch's stage table (`PILLAR_03_JANTSCH.md:94–101`) implies a vocabulary: `ephemeral` (physical stage) → `durable` (biological stage) → `trusted` (social/cultural stage). This mapping is not yet codified anywhere.

**MemoryFact**
- Anchored by this pillar? **Y (strong)**
- Justification: "A society, unlike a cell, can *reflect on* its own organization — it can produce meta-level descriptions of itself (theories, constitutions, value systems) that in turn modify its production processes" (`PILLAR_03_JANTSCH.md:86`). A `MemoryFact` in the chetana layer is exactly this: a promoted trusted atom that constitutes the system's self-description and feeds back into agent behavior. The `axiom_signature` in `AtomProvenance` (`[chetana/provenance.py:84–95]` per v2 §2.4) binds each trusted memory to the exact kernel manifest — this is Jantsch's autopoietic boundary condition operationalized: only memory produced by the system's own governance structure counts as self-knowledge.
- Which substrate: The promote() 11-step pipeline at `[chetana/promote.py:1–17]` (v2 §2.4) is the load-bearing mechanism. `gate_check_atom()` at step 3 is the Jantsch channel-cleaning step. The `CANONICAL_DOC_STACK` Memory Authorities table (v2 §2.4, `[CDS §Memory Authorities]`) defines seven write surfaces — this is Jantsch's "seven-level hierarchy of self-organization" translated into write-authority hierarchy.
- Jantsch uniquely anchors the `provenance.revival_chain` (`[chetana/provenance.py:91–95]` per v2 §2.4) as an intentional untyped escape. The pillar explains why: "bifurcation introduces genuine *historical contingency* into physics" (`PILLAR_03_JANTSCH.md:42`). The revival chain is the memory of contingent evolutionary history — it should remain loosely typed until revival v1.0 freezes the field set, which is exactly the note in provenance.py.

---

## 5. Honest Gaps

1. **`ALIGNMENT_THROUGH_RESONANCE` has no runtime operationalization.** `formal_constraint = "alignment_score computed from resonance NOT compliance"` (`dharma_kernel.py:323`). No module currently computes a resonance score. `AgentIdentity.telos_alignment` in GraphQL is a float but its computation method is not defined in any source file visible in this extraction. The `swabhaav_capacity` field in the ontology object is a float but its update pathway is not wired to any feedback loop. Pillar claim: alignment emerges from resonance. Code status: `telos_alignment` is a declared field with no implementation.

2. **Metabolic monitoring is not wired to Task substrate.** Jantsch requires continuous monitoring of "rate of API calls, diversity of agent activations, volume of stigmergic marks deposited" (`PILLAR_03_JANTSCH.md:127`) as vital signs. None of these are typed fields on the `Task` Pydantic model or the `tasks` SQLite table (v2 §2.1). They exist as mark counts in `~/.dharma/stigmergy/marks.jsonl` but are not aggregated into `Task.routing` or `Task.stigmergy` (the strict-typed target fields from v2 §2.1 that are not yet implemented).

3. **StrangeLoop outputs don't feed into Core Four FSM transitions.** The four-level reflexive loop (observe → describe → modify → meta-reflect) is implemented in `dharma_swarm/strange_loop.py`, but its outputs write to `~/.dharma/organism_memory/mutations.jsonl` (per `CLAUDE.md`), not into `Task` status transitions or `AgentIdentity` updates via the canonical substrate. Jantsch's societal autopoiesis claim requires that reflexive descriptions *actually modify* the production network. Currently they are logged.

4. **`Artifact.promotion_state` vocabulary is undefined.** `artifact_records.promotion_state TEXT NOT NULL DEFAULT 'ephemeral'` (`[runtime_state.py:89–103]` v2 §2.3) has no enum constraint. Jantsch's evolutionary stage table implies a three-value vocabulary (ephemeral/durable/trusted). This is an uncodified Jantsch contribution.

5. **AgentIdentity fragmentation violates autopoietic identity.** Seven separate surfaces (v2 §2.2) producing incompatible descriptions of what an agent is means the system cannot pass Jantsch's autopoiesis test: "maintains its identity through constant replacement of components" requires a single identity schema, not seven competing ones. The `[AIU]` unification spec is a prerequisite for any Jantsch-derived integrity claim about the agent population.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **Resonance vs. free energy minimization.** Jantsch's `ALIGNMENT_THROUGH_RESONANCE` says alignment is structural resonance between levels. Friston's `ACTIVE_INFERENCE` says the system minimizes expected free energy. Are these compatible operationalizations of the same thing, or do they prescribe different scoring functions for `AgentIdentity.telos_alignment`? Synthesis must decide which formula the field carries.

2. **Autopoiesis boundary and the Kauffman closure.** Jantsch's `OPERATIONAL_CLOSURE` (system produces its own boundary) and Kauffman's `AUTOCATALYTIC_CLOSURE` (catalytic graph has >= 1 SCC) both purport to describe the boundary condition of a living system. Are they the same constraint expressed at different scales, or do they gate different Core Four mutations? Synthesis must decide if `CatalyticGraph.has_scc()` is sufficient for `OPERATIONAL_CLOSURE.formal_constraint`.

3. **The narcissism trap and meta-task ratio.** Jantsch explicitly warns against a system spending more energy on self-observation than object-level work (`PILLAR_03_JANTSCH.md:224–227`). The current Core Four has no `Task.domain_class` field distinguishing meta-reflective tasks from object-level tasks. Should `TaskRouting` (the strict-typed split from v2 §2.1 `Task.metadata`) include a `is_reflexive: bool` flag that the `KernelGuard` uses to enforce ratio constraints?

4. **What does Jantsch's developmental stage mean for `AgentIdentity.role`?** The evolutionary stage table (`PILLAR_03_JANTSCH.md:164–172`) says the system is "between chemical and social stages, with nascent cultural elements." The canonical `AgentRole` enum (19 values per v2 §2.2) includes roles like CARTOGRAPHER, ARCHEOLOGIST, SURGEON, ARCHITECT, VALIDATOR. Do these roles map to Jantsch's evolutionary stages, and if so, should `AgentIdentity.shakti_energy` (`ShaktiEnergy.MAHAKALI` per `[ontology.py:211]`) be modulated by the system's current stage?

5. **The Rigidity Trap and gate tunability.** Jantsch warns: "The 11 telos gates should be *tunable* — their strictness should vary depending on the system's developmental stage" (`PILLAR_03_JANTSCH.md:210–212`). The current `TelosGatekeeper` with `CORE_GATES` dict at `[telos_gates.py:224–236]` has fixed gate implementations. Should there be a `stage_sensitivity: float` property on each gate that the `DarwinEngine` adjusts as system fitness increases? This would directly implement Jantsch's developmental trajectory claim.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | What I used it for |
|---|---|---|
| 5 | `Read: /Users/dhyana/.claude/plans/v3_pillar_subagent_template.md` | Template + required structure |
| 5 | `Read: docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` (offset 0–550) | v2 substrate facts; cited by §section |
| 5 | `Read: foundations/PILLAR_03_JANTSCH.md` | Full pillar read; all claims cited by line |
| 5 | `Read: dharma_swarm/dharma_kernel.py` (lines 1–360) | MetaPrinciple enum + PrincipleSpec definitions |
| 5 | `Read: docs/v3_pillar_traces/_INDEX.md` | Pre-flight check before appending |

Tier 1 (memory graph), Tier 2 (wiki), Tier 3 (semantic_code_search), and Tier 4 (gitnexus) were skipped with justification: the required context was fully specified by path in the task instructions, and the relevant module names (strange_loop.py, evolution.py, catalytic_graph.py, telos_gates.py, promote.py) are named explicitly in the pillar text itself or in the kernel axiom descriptions. Semantic search would rediscover the same files. The extraction is narrow enough (one pillar → four objects) that structural graph traversal would not surface additional anchoring points not already visible in the direct reads. Any cross-pillar synthesis questions that require structural awareness are flagged in §6.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-03-jantsch subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: `~/.claude/plans/v3_pillar_subagent_template.md`
