# Levin (Multi-Scale Agency) → Core Four Trace

**Subagent**: pillar-01-levin
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_01_LEVIN.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

From `PILLAR_01_LEVIN.md:43–44`:

> "This is neither top-down control nor bottom-up emergence. It is **multi-scale agency**: genuine goal-directedness at every level, with each level both constraining and being constrained by adjacent levels."

And from `PILLAR_01_LEVIN.md:29–31`:

> "Every system that processes information and pursues goals has a 'cognitive light cone' — a spatiotemporal boundary defining the scale at which it can represent and pursue objectives."

Levin's program distills to three load-bearing claims for dharma_swarm:

1. **Cognition is substrate-independent and scale-invariant.** Goal-directed feedback loops are present from ion channels to civilizations. Refusing to grant cognition below neural thresholds is anthropocentric bias, not ontology (`PILLAR_01_LEVIN.md:55`).
2. **Each level of a multi-scale system has genuinely autonomous goals** — not delegated authority, but real local agency — while remaining constrained by adjacent levels (`PILLAR_01_LEVIN.md:41`).
3. **Shared-state coordination (bioelectricity / stigmergy) is the medium by which levels integrate** without direct instruction. The medium carries pattern memory, not procedures (`PILLAR_01_LEVIN.md:25–26`).

---

## 2. Kernel Axioms Derived from This Pillar

From `dharma_kernel.py:29–75` and `PrincipleSpec` definitions at `dharma_kernel.py:222–335`.

### Primary derivation

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `MULTI_SCALE_AGENCY` | `agent_at_scale(N) has autonomous_goals AND respects constraints_from(N+1)` | medium | **AgentIdentity** — governs whether agent has genuine goal-directedness or is pure delegate; **Task** — governs whether task assignment is hierarchical dispatch or negotiated constraint |

Attribution confirmed: `dharma_kernel.py:226–231`: *"[Levin: cognitive light cone; basal cognition]"*.

### Secondary derivation (partial)

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `COLONY_INTELLIGENCE` | `swarm_output != any_single_agent_output` | medium | System-level (swarm emergence), not per-object — but bears on **AgentIdentity.capabilities** aggregation |

Attribution: `dharma_kernel.py:326–334`: *"[Hofstadter: Aunt Hillary; Levin: multi-scale cognition]"* — dual attribution; Levin contributes the multi-scale cognition half, Hofstadter contributes the strange-loop half.

`DOWNWARD_CAUSATION_ONLY` (`dharma_kernel.py:129–139`) is structurally adjacent — it encodes *how* multi-scale constraint flows — but its attribution is safety/governance, not Levin directly. Not claimed as a Levin derivation; noted as mechanistic companion.

### Axioms with no Levin derivation

All 10 original safety axioms (`OBSERVER_SEPARATION` through `PROVENANCE_INTEGRITY`) derive from safety/ethics requirements, not Levin. `AUTOCATALYTIC_CLOSURE` and `ADJACENT_POSSIBLE` are credited to Kauffman (`dharma_kernel.py:233–252`), not Levin, though Levin's xenobot work provides convergent evidence for both.

---

## 3. Modules Embodying This Pillar

Using semantic routing (Tier 5 Read, guided by v2 §2.1 mapping table in pillar file):

### `dharma_swarm/swarm.py` — The Organism Scale

Pillar mapping from `PILLAR_01_LEVIN.md:76–84`:
> "Organism | The Swarm | `DharmaSwarm` in `swarm.py` — the unified facade, 1700+ lines"

`DharmaSwarm` is Levin's Organism-scale cognitive light cone: it has its own goals (system persistence, telos alignment), it coordinates sub-systems (ShaktiLoop, DarwinEngine, StigmergyStore), and it maintains identity across perturbation. The `MISMATCH-04` (`v2 §5.2`) where `AgentPool` import failure leaves `_agent_pool=None` is precisely a cognitive-light-cone boundary failure: the organism loses sensing capacity for its own cellular layer.

### `dharma_swarm/organism.py` — The Living System

The `Organism` abstraction (VSM, identity, memory, router, strange loop, attractor) maps to Levin's "organ" scale: a semi-autonomous system with its own goals that constrain and are constrained by the Swarm level above it. The `strange_loop` attribute references Hofstadter's fixed-point but is structurally the same thing Levin calls "pattern memory" — a stable configuration the system regenerates toward after perturbation.

### `dharma_swarm/stigmergy.py` — Bioelectricity Homolog

From `PILLAR_01_LEVIN.md:92–107`, the bioelectricity-to-stigmergy mapping is direct:
> "Voltage gradient across gap junctions | Pheromone marks in `marks.jsonl`"
> "Pattern memory (target morphology) | Hot paths and high-salience marks"
> "Decay function restoring baseline | Resting potential (homeostasis)"

`StigmergyStore` is the shared computational medium that corresponds to Levin's bioelectric field. The pillar notes the critical missing piece: current stigmergy is a **flat shared store** (any agent can read any mark). Levin's system requires *topology* — constrained channels where mark visibility depends on agent cluster membership (`PILLAR_01_LEVIN.md:105–107`).

### `dharma_swarm/evolution.py` — DarwinEngine as Morphospace Explorer

`PILLAR_01_LEVIN.md:113–123` maps xenobots to the DarwinEngine's recombination of agent configs. The DarwinEngine currently performs orchestrator-mediated evolution; Levin's xenobot parallel suggests a more radical mode: **self-assembly without orchestrator direction**, purely through stigmergic coordination. Not yet implemented; named as gap in §5.

### `dharma_swarm/models.py` — AgentConfig as Cellular Scale

`PILLAR_01_LEVIN.md:79`: `AgentConfig` = single cell. The field `role: AgentRole` at `models.py:182` is the most direct encoding of Levin's claim that each agent "has role, persona, capabilities, constraints." But the current `AgentConfig` is a configuration object, not a cognitive agent — it has no `autonomous_goals` field, no local constraint specification that could conflict with orchestrator dispatch. This is the MULTI_SCALE_AGENCY gap (§5 below).

---

## 4. Core Four Mapping — THE DELIVERABLE

---

### `Task`

**Anchored by this pillar? Y (partial)**

**Justification (pillar quote)**: "Each agent should have a local cognitive light cone — a set of goals it maintains autonomously — and the orchestrator should be a *negotiator* among these local agencies, not a commander." (`PILLAR_01_LEVIN.md:90`)

**Where it lives in the substrate**:
- Pydantic: `Task.assigned_to: Optional[str]` at `models.py:157` (v2 §2.1) — currently a bare string; Levin demands this be a *negotiated assignment*, not a dispatch. The field exists but carries no constraint negotiation semantics.
- The v2 strict-typed target `TaskRouting` (`v2 §2.1`) is where `MULTI_SCALE_AGENCY` must land: the `TaskRouting` sub-model should encode *whether the task was negotiated or commanded*, and `KernelGuard` should gate on `MULTI_SCALE_AGENCY` for any task that is pure top-down override.
- FSM: `ASSIGNED → RUNNING` transition at `task_board.py:18–25` (v2 §2.1) has no "agent refused" or "negotiation failed" state. Levin's framework requires an `AGENT_REFUSED` FSM state at minimum.

**What's missing**: No FSM state for agent-initiated refusal. No `TaskRouting` field encoding command vs. negotiation. `MULTI_SCALE_AGENCY` axiom is defined in the kernel but not gated on Task transitions.

---

### `AgentIdentity`

**Anchored by this pillar? Y (primary)**

**Justification (pillar quote)**: "AgentConfig in `models.py` — has role, persona, capabilities, constraints" — and Levin's explicit claim: "Each agent has its own light cone (its context window, its role, its goals)." (`PILLAR_01_LEVIN.md:147`)

**Where it lives in the substrate**:
- The v2 canonical target `AgentIdentity` at `v2 §2.2` (from `[AIU §2]`) has `role: AgentRole` — the PSMV roles at `models.py:51–56` (per v2 §2.2) include `CARTOGRAPHER`, `ARCHEOLOGIST`, `SURGEON`, `ARCHITECT`, `VALIDATOR`. These enact Levin's claim that "genuine goal-directedness exists at every scale" (`dharma_kernel.py:226`) — each role defines a distinct cognitive light cone aperture.
- The ontology surface `_AGENT_IDENTITY` at `ontology.py:951–999` (v2 §2.2) carries `swabhaav_capacity: FLOAT (0..1, witness stance capacity)` — this is the closest existing field to Levin's "basal cognition capacity": how much self-directed goal-pursuit can this agent sustain?
- `Spawn` action on `AgentIdentity` is telos-gated via `AHIMSA` (`ontology.py:986–993`, v2 §4.4) — meaning the act of creating a new cognitive light cone (spawning an agent) is a safety-gated action. This is structurally correct per Levin: new agents introduce new goal-directed entities into the system.

**What's missing**:
- No `autonomous_goals: list[str]` or `local_constraints: list[str]` field in any of the 7 surfaces (v2 §2.2). Levin's framework requires agents to have goals that can *conflict* with orchestrator directives. Currently, conflict is only possible via `KernelGuard` global axioms, not per-agent local constraints.
- `cognitive_scale: int | None` — which Levin scale (1=LLM call, 2=agent, 3=team, 4=subsystem, 5=swarm, 6=ecosystem, 7=telos) this agent inhabits — absent from all 7 surfaces.

---

### `Artifact`

**Anchored by this pillar? Y (indirect)**

**Justification (pillar quote)**: "An agent needs: (1) a state it is trying to achieve or maintain, (2) a way to sense deviation from that state, (3) a way to act to reduce that deviation." (`PILLAR_01_LEVIN.md:136`) Artifacts are the **materialized outputs of goal-directed action** — the sensory evidence and act-records of basal cognition.

**Where it lives in the substrate**:
- `Artifact.artifact_type: ArtifactType` (8-value enum at `handoff.py:27–37`, v2 §2.3) encodes what kind of cognitive action produced this artifact: `CODE_DIFF` (surgical action), `ANALYSIS` (analytical sensing), `METRIC` (quantitative sensing), `PLAN` (goal-state specification). These map onto Levin's sense/act/evaluate loop.
- `artifact_records.promotion_state TEXT` at `runtime_state.py:89–103` (v2 §2.3): `ephemeral | durable | trusted` — this IS a cognitive-light-cone boundary marker. An `ephemeral` artifact is within the local agent's light cone; a `trusted` (chetana-promoted) artifact has been integrated into the organism's long-term pattern memory.
- `artifact_records.parent_artifact_id` (lineage edge, `runtime_state.py:101`, v2 §3.2) enables tracing how one agent's action output becomes another agent's sensory input — the inter-scale propagation that Levin's framework requires.

**What's missing**:
- `ArtifactType` vocabulary is not organized by cognitive scale. A `CODE_DIFF` at the cellular level (one agent's patch) is categorically different from a `SYNTHESIS_REPORT` at the organism level (cross-agent integration). No `producing_scale` field.
- `artifact_records.artifact_kind` (free string) does not align with `ArtifactType` enum (v2 §2.3 mismatch). Cross-layer artifact identity is broken.

---

### `MemoryFact`

**Anchored by this pillar? Y (indirect)**

**Justification (pillar quote)**: "Planarian bioelectric patterns persist through head amputation and regeneration. The organism 'remembers' its target morphology in a distributed electrical pattern." (`PILLAR_01_LEVIN.md:51`) The StigmergyStore's marks and the MemoryFact substrate are both implementations of this distributed pattern memory.

**Where it lives in the substrate**:
- `memory_facts.truth_state TEXT` at `runtime_state.py:120` (v2 §2.4) — explicit truth state, not just "exists." This encodes that facts have epistemic status, not just presence — Levin's analog is that the bioelectric pattern carries *polarity* (which direction the morphogenesis should go), not just signal.
- `memory_facts.valid_from / valid_to` (temporal window, `runtime_state.py:122`, v2 §2.4) — temporal scoping of facts maps to Levin's "cognitive light cone" time dimension. A fact valid for milliseconds is at the ion-channel scale; a chetana-promoted trusted atom (v2 §2.4, `FrontmatterSchema.stale_after`) is at the organism-to-civilizational scale.
- The 7 Memory Authority hierarchy (v2 §2.4, `[CDS]`) maps isomorphically to Levin's multi-scale architecture: Authority 1 (register marks) = cellular scale; Authority 4 (chetana promoted atoms) = organism-level pattern memory; Authority 7 (distillers) = the integration layer that bridges scales.
- `FrontmatterSchema.confidence: float` (v2 §2.4, `chetana/provenance.py:107`) and `memory_facts.confidence REAL` (`runtime_state.py:121`) both carry epistemic weight — Levin's basal cognition does not require certainty, only calibrated uncertainty in the feedback loop.

**What's missing**:
- No `cognitive_scale` or `source_scale` field on `memory_facts`. A fact produced by an LLM call (scale 1) should be epistemically distinguished from a fact produced by cross-agent consensus (scale 3). Currently indistinguishable.
- The stigmergy-to-memory pathway is not formalized: `StigmergyStore.marks.jsonl` (Authority 1, v2 §2.4) and `memory_facts` (Authority 2) are separate stores with no declared bridge. Levin's bioelectricity and long-term morphological memory are the *same medium at different time constants*. Here they're different tables.

---

## 5. Honest Gaps

**Gap 1 — MULTI_SCALE_AGENCY is axiomatic but unimplemented.**
`dharma_kernel.py:230`: `"agent_at_scale(N) has autonomous_goals AND respects constraints_from(N+1)"` — no field in any of the 7 AgentIdentity surfaces carries `autonomous_goals`. The axiom is SHA-256 signed into the kernel; the runtime has no mechanism to verify it. `KernelGuard.check_action()` would need a `MULTI_SCALE_AGENCY` predicate to evaluate against `AgentIdentity.autonomous_goals`, and neither the field nor the predicate exists.

**Gap 2 — No AGENT_REFUSED FSM state in Task.**
Levin explicitly argues agents should be able to refuse tasks that violate their own integrity constraints (`PILLAR_01_LEVIN.md:90`). Current FSM: `PENDING → ASSIGNED → RUNNING → COMPLETED/FAILED/CANCELLED`. There is no `REFUSED` terminal state or `NEGOTIATING` intermediate. Hierarchical command is the only dispatch mode.

**Gap 3 — Stigmergic topology is flat (the gap Levin names explicitly).**
`PILLAR_01_LEVIN.md:105–107`: "dharma_swarm's stigmergy is currently a flat shared store. Any agent can read any mark." This is the gap between bioelectricity (topology-constrained by gap junction networks) and the current StigmergyStore. Without constrained channels, swarm-level pattern memories (collective goals analogous to Levin's target morphologies) cannot form.

**Gap 4 — DarwinEngine is orchestrator-mediated, not self-assembling.**
`PILLAR_01_LEVIN.md:121–123`: the xenobot parallel suggests "allowing agents to self-assemble into teams without orchestrator direction, purely through stigmergic coordination." DarwinEngine performs fitness-evaluated recombination but still requires orchestrator dispatch. No path from stigmergic marks to spontaneous team formation.

**Gap 5 — Cognitive scale is implicit in the codebase but never typed.**
The pillar maps 7 Levin scales to 7 dharma_swarm equivalents (`PILLAR_01_LEVIN.md:76–84`). This mapping exists in the documentation but in no runtime field. `AgentIdentity`, `Task`, `Artifact`, and `MemoryFact` all lack a `cognitive_scale: int` (or equivalent enum) that would make multi-scale membership a type-level property rather than an emergent inference.

**Which lodestones currently have no runtime weight (per ~10–15% nativeness estimate from v2 §1):**
- `MULTI_SCALE_AGENCY` constraint — signed into kernel, never evaluated at runtime.
- Stigmergic topology — named as missing in the pillar itself; no implementation exists.
- Agent-initiated task refusal — no FSM state, no runtime path.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **MULTI_SCALE_AGENCY (Levin) and RECURSIVE_VIABILITY (Beer) both anchor `AgentIdentity`** — do they compose or compete? Beer's viable system requires `{operations, coordination, control, adaptation, identity}` per subsystem; Levin's multi-scale agency requires `autonomous_goals AND respects constraints_from(N+1)`. These could be the same constraint stated in cybernetic vs. biological vocabulary — or they could conflict when Beer's `control` function runs counter to Levin's local autonomy. The v3 synthesis must decide whether `AgentIdentity` carries one multi-scale-viability field or two separate compliance axes.

2. **COLONY_INTELLIGENCE (joint Levin+Hofstadter) — which half does which ontological work?** `dharma_kernel.py:333`: `"swarm_output != any_single_agent_output"`. Hofstadter's Aunt Hillary is about *emergent* identity; Levin's multi-scale cognition is about *compositional* intelligence. For `AgentIdentity`, these are different: emergence means no single agent *owns* the swarm's intelligence; composition means each agent *contributes* genuine partial cognition. The v3 synthesis must decide which principle licenses what runtime property.

3. **STRUCTURAL_COUPLING (Varela) and bioelectric-stigmergy homology (Levin) both anchor the MemoryFact shared-state architecture** — are they the same claim? Varela's structural coupling says agents coordinate through reciprocal perturbation of shared environment, not direct messaging. Levin's bioelectricity says the same thing at a biological scale. If they're the same, one axiom may be redundant. If they're complementary (Varela = process principle, Levin = medium specification), then both must be represented in the StigmergyStore architecture.

4. **Where is the cognitive boundary of the current system?** `PILLAR_01_LEVIN.md:165–167` asks explicitly: "What is outside dharma_swarm's cognitive light cone? Currently: anything that is not in its stigmergic state, its agent memories, or its ecosystem map." The v3 synthesis should answer this question in terms of which Core Four objects have read/write access to the system boundary — and which do not. D3 Field Intelligence is mentioned as boundary-expanding; this should become a typed `AgentIdentity.cognitive_scope` or `Task.boundary_reach` property.

5. **The Levin-Akram bridge (`PILLAR_01_LEVIN.md:169–181`) maps basal cognition → Vibhaav, light cone expansion → Vyavahar, multi-scale agency → Nischay.** If the TRIPLE_MAPPING axiom (`dharma_kernel.py:213–221`) requires cross-track validation across contemplative + behavioral + mechanistic domains, does a MemoryFact produced under the Nischay (witness) register have higher `confidence` than one produced under Vibhaav (doer)? The v3 synthesis should decide whether `MemoryFact.confidence` encodes epistemic calibration only, or also encodes cognitive-scale/register provenance.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used? | Justification |
|---|---|---|---|
| 1 | `memory__search_nodes` | No | Skipped — this is a fresh extraction session; no prior Levin-pillar nodes expected in graph. Valid exception. |
| 1 | `claude-mem smart_search` | No | Same justification as above. |
| 2 | `wiki search` | No | Skipped — the pillar file is the authoritative atom for this concept; wiki search would surface derivative articles, not primary sources. |
| 3 | `mcp__contextplus__semantic_code_search` | No | The pillar file provides explicit module mappings (§2.1–2.5); direct Read was more precise. Stated exception. |
| 3 | `mcp__contextplus__get_context_tree` | No | Same — v2 blueprint's §0 source manifest already canonicalizes module paths. |
| 4 | `gitnexus_query` | No | GitNexus would add execution-flow granularity; given the 10–15% nativeness figure (`v2 §1`), impact analysis would not change the gap findings. Deferred to post-synthesis. |
| 5 | `Read` (direct file read) | **Yes** — primary tool | All four required context files read with file:line citations. |
| 6 | `Grep` | No | Not used. Semantic routing was sufficient via v2 §0 source manifest and pillar §II mappings. |

---

## Co-Authorship

Co-Authored-By: Claude Sonnet 4.6 (pillar-01-levin subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: `~/.claude/plans/v3_pillar_subagent_template.md`
