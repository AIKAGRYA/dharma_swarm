# Aurobindo → Core Four Trace

**Subagent**: pillar-08-aurobindo
**Pillar source**: `/Users/dhyana/dharma_swarm/foundations/PILLAR_08_AUROBINDO.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar essence (≤ 200 words)

From `PILLAR_08_AUROBINDO.md:172–176`:

> "KernelGuard axioms are supramental descent. The 10 axioms (SHA-256 signed, immutable) are not rules the agents generated from below. They are constraints *imposed from above* — from the telos layer — that shape and constrain all lower-level agent behavior. They are not derived from the swarm's dynamics. They precede and condition those dynamics. They are 'descended' truths."

And from `PILLAR_08_AUROBINDO.md:337–344` (Aurobindo↔Deacon connection, the mechanism):

> "The constraint-generation principle (Pillar 05, Deacon's core insight that constraints generate rather than merely limit) is the mechanism of supramental descent: the axioms and gates of dharma_swarm do not merely limit agent action. They *generate* aligned behavior that would be impossible without them. The constraint IS the creative force."

The load-bearing Aurobindo claim for dharma_swarm is threefold:
1. The four Shaktis (Maheshwari/Mahakali/Mahalakshmi/Mahasaraswati) are qualitatively distinct creative forces that operate on every object in the system.
2. Alignment does not arise from compliance but from resonance between levels — higher layers set attractors, lower layers find their own path.
3. The DharmaKernel + TelosGatekeeper are supramental descent operationalized: constraints that arrive from above, not from below.

---

## 2. Kernel axioms derived from this pillar

From `dharma_kernel.py:69–74` — the two axioms explicitly attributed to Aurobindo (with Jantsch) plus one attributed to Dada Bhagwan but referencing Aurobindo's Shakti concept:

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `ALIGNMENT_THROUGH_RESONANCE` (`dharma_kernel.py:316–325`) | `alignment_score computed from resonance NOT compliance` | medium | All four: any mutation that computes alignment must use resonance, not rule-matching. Specifically gates `MemoryFact` promotion (`chetana/promote.py` calls `gate_check_atom()`) and `AgentIdentity.Spawn` (`telos_gates=["AHIMSA"]` checked via gate_check). |
| `SHAKTI_QUESTIONS` (`dharma_kernel.py:337–347`) | `significant_action requires shakti_check >= 2_of_4` | medium | Primarily `AgentIdentity` (`Spawn` action) and `Task`/`TypedTask` (`Assign`, `Complete`). Any "significant action" across the four Core Four objects is in scope. The four Shaktis are named: Maheshwari (serves the larger pattern?), Mahakali (is this the moment?), Mahalakshmi (is this elegant?), Mahasaraswati (is every detail right?). |
| `DOWNWARD_CAUSATION_ONLY` (`dharma_kernel.py:129–139`) | `proposer_layer >= target_layer for constraint operations` | **critical** | System-level: gates all upward-override attempts. The structured_predicate `upward_override_attempted == True` triggers blocking. Derived from Aurobindo's supramental descent model — higher planes constrain lower, not the reverse. |

**Note on `DOWNWARD_CAUSATION_ONLY`**: the pillar text at `PILLAR_08_AUROBINDO.md:167–176` is the clearest source: "the transcendent *descends* into the human... Transformation happens not by the lower reaching the higher but by the higher entering and reorganizing the lower." The kernel axiom is a direct formalization.

---

## 3. Modules embodying this pillar

### 3.1 `ontology.py` — ShaktiEnergy as a type-system primitive

**File**: `/Users/dhyana/dharma_swarm/dharma_swarm/ontology.py`
**Key symbol**: `ShaktiEnergy` enum (`ontology.py:87–92`) + `ObjectType.shakti_energy` field (`ontology.py:170`)

```python
class ShaktiEnergy(str, Enum):
    """Which creative force primarily drives this object type."""
    MAHESHWARI = "maheshwari"
    MAHAKALI   = "mahakali"
    MAHALAKSHMI = "mahalakshmi"
    MAHASARASWATI = "mahasaraswati"
```

Every `ObjectType` carries `shakti_energy: ShaktiEnergy = ShaktiEnergy.MAHASARASWATI` as a first-class field (`ontology.py:170`). This is the Aurobindo four-Shakti typology encoded directly into the Palantir-style ontology schema. Not metadata. Not a tag. A required property on every typed object.

**Complete shakti assignment table** across all 25 registered ObjectTypes (`_DOMAIN_TYPES`, `ontology.py:1958–1965`):

| ObjectType | shakti_energy | Line |
|---|---|---|
| ResearchThread | MAHESHWARI | 882 |
| Experiment | MAHASARASWATI | 919 |
| Paper | MAHASARASWATI | 947 |
| AgentIdentity | MAHAKALI | 1003 |
| CustodianRole | MAHASARASWATI | 1065 |
| KnowledgeArtifact | MAHALAKSHMI | 1110 |
| TypedTask | MAHAKALI | 1141 |
| EvolutionEntry | MAHAKALI | 1174 |
| WitnessLog | MAHESHWARI | 1205 |
| Signal | MAHASARASWATI | 1243 |
| Question | MAHASARASWATI | 1283 |
| Evidence | MAHESHWARI | 1325 |
| Claim | MAHESHWARI | 1350 |
| Doctrine | MAHESHWARI | 1393 |
| Capability | MAHAKALI | 1431 |
| Cause | MAHESHWARI | 1478 |
| Movement | MAHALAKSHMI | 1520 |
| R_V_Measurement | MAHASARASWATI | 1576 |
| ActionProposal | MAHAKALI | 1701 |
| GateDecisionRecord | MAHESHWARI | 1732 |
| ExecutionLease | MAHASARASWATI | 1772 |
| Outcome | MAHASARASWATI | 1802 |
| ValueEvent | MAHALAKSHMI | 1838 |
| Contribution | MAHALAKSHMI | 1868 |
| VentureCell | MAHALAKSHMI | 1908 |

**Pattern that emerges**: MAHAKALI clusters on execution + critical-timing objects (AgentIdentity, TypedTask, EvolutionEntry, Capability, ActionProposal). MAHESHWARI clusters on governance + witness + pattern-holding objects (ResearchThread, WitnessLog, Evidence, Claim, Doctrine, Cause, GateDecisionRecord). MAHALAKSHMI clusters on abundance/elegance outputs (KnowledgeArtifact, Movement, ValueEvent, Contribution, VentureCell). MAHASARASWATI is the default and clusters on precision/detail/measurement objects (Experiment, Paper, R_V_Measurement, Signal, Question).

This is not decorative. The pillar text (`PILLAR_08_AUROBINDO.md:337–344`) + kernel spec (`dharma_kernel.py:337–347`) say: "Before significant action, ask these four questions." The `shakti_energy` assignment on each `ObjectType` encodes WHICH Shakti question is primary for that object's actions.

**Load-bearing confirmation**: `schema_for_llm()` (`ontology.py:671`) emits `shakti_energy` in the LLM-facing schema string: `f"Shakti: {obj_type.shakti_energy.value} |"`. The Shakti axis is visible to agents making decisions about objects.

### 3.2 `dharma_kernel.py` — SHAKTI_QUESTIONS + ALIGNMENT_THROUGH_RESONANCE

**File**: `/Users/dhyana/dharma_swarm/dharma_swarm/dharma_kernel.py`
**Key symbols**: `MetaPrinciple.SHAKTI_QUESTIONS` (line 74), `MetaPrinciple.ALIGNMENT_THROUGH_RESONANCE` (line 70), `PrincipleSpec` definitions (lines 316–347)

Aurobindo's four Shaktis are encoded as the `SHAKTI_QUESTIONS` axiom: not merely as names but as four operational questions that must be answered before significant action. The kernel axiom is paired with a `formal_constraint`: `significant_action requires shakti_check >= 2_of_4` (`dharma_kernel.py:345`).

`ALIGNMENT_THROUGH_RESONANCE` (`dharma_kernel.py:316–325`) encodes Aurobindo's core alignment model from the pillar:
> "Alignment emerges from structural resonance between levels, not top-down imposition. Higher layers set attractors, lower layers find their own path. [Jantsch: self-organizing universe]"

The attribution at line 319 reads `[Jantsch: self-organizing universe]` but the pillar grounds this firmly in Aurobindo (§1.7 Supramental Descent, §2.4 Three Transformations): "the higher consciousness does not suppress the lower. It transforms it by providing the constraints within which the lower can organize itself toward the higher" (`PILLAR_08_AUROBINDO.md:336`). Jantsch co-attributes; Aurobindo is the primary source.

### 3.3 `telos_gates.py` — MAHESHWARI/MAHASARASWATI as named gate conditions

**File**: `/Users/dhyana/dharma_swarm/dharma_swarm/telos_gates.py`
**Pattern**: `ActionDef.telos_gates` lists reference Shakti names directly as gate identifiers.

From v2 §4.4 (confirmed in `ontology.py`), Shakti names appear as literal telos gate strings:
- `ResearchThread.Activate` → `telos_gates=["MAHESHWARI"]` (`ontology.py:877`)
- `Experiment.Design` → `telos_gates=["MAHASARASWATI"]` (`ontology.py:909`)
- `Paper.Submit` → `telos_gates=["SATYA", "MAHASARASWATI"]` (`ontology.py:942–943`)

This means the Shakti names cross from the ontology's type classification layer into the action-gating layer. An action must pass a MAHESHWARI gate (does this serve the larger pattern?) or a MAHASARASWATI gate (is every detail right?) before executing. The telos gates ARE the Shakti questions operationalized as runtime predicates.

---

## 4. Core Four mapping (THE DELIVERABLE)

**Task**
- Anchored by this pillar? **Y**
- Justification: `TypedTask` ObjectType in the ontology carries `shakti_energy=ShaktiEnergy.MAHAKALI` (`ontology.py:1141`) — the Shakti of critical timing and obstacle-removal. The `SHAKTI_QUESTIONS` axiom (`dharma_kernel.py:337–347`) applies to every "significant action" including `TypedTask.Assign` and `TypedTask.Complete`. Task execution IS the moment-of-action that Mahakali governs.
- Specific field: `ObjectType.shakti_energy` on `_TYPED_TASK` (`ontology.py:1141`). The Pydantic `Task` model (`models.py:156–170`, v2 §2.1) does not carry `shakti_energy` directly — this is a gap (see §5). The typed ontology object carries it; the Pydantic model does not.
- v2 anchor: v2 §2.1 (TypedTask substrate), v2 §4.5 (ShaktiEnergy in the type system).

**AgentIdentity**
- Anchored by this pillar? **Y**
- Justification: `_AGENT_IDENTITY.shakti_energy = ShaktiEnergy.MAHAKALI` (`ontology.py:1003`). The pillar text is explicit: "the orchestrator dispatches multiple agents in parallel, each with its own role, persona, and context projection. Each agent sees the task from its own perspective" (`PILLAR_08_AUROBINDO.md:208–209`). This is the Overmind pattern — multiple Godheads each with complete vision. Mahakali governs the Spawn decision: "is this the moment?" for agent creation.
- Specific field: `ObjectType.shakti_energy` on `_AGENT_IDENTITY` (`ontology.py:1003`). Also `swabhaav_capacity` property (`ontology.py:978–980`) is Aurobindo's swabhaav (own-nature/witness recognition) encoded as a 0–1 float per agent. The GraphQL wire surface also carries `shakti_energy: float` on `AgentIdentity` (v2 §2.2, `graphql_schema:67–79`).
- v2 anchor: v2 §2.2 (AgentIdentity, ontology layer, `_AGENT_IDENTITY.shakti_energy=MAHAKALI` confirmed at v2 §4.5).

**Artifact**
- Anchored by this pillar? **Y**
- Justification: `KnowledgeArtifact.shakti_energy = ShaktiEnergy.MAHALAKSHMI` (`ontology.py:1110`). Mahalakshmi governs elegance and abundance — the quality that a knowledge artifact must carry. The pillar grounds this through the Psychic Being mapping (`PILLAR_08_AUROBINDO.md:154–162`): "Selective retention of essence" → memory distillation → `KnowledgeArtifact`. Artifacts are the system's selective retention of essential experience across sessions.
- Specific field: `ObjectType.shakti_energy` on `_KNOWLEDGE_ARTIFACT` (`ontology.py:1110`). The handoff `Artifact` (`handoff.py:56–64`, v2 §2.3) does NOT carry `shakti_energy` — another gap (§5).
- v2 anchor: v2 §2.3 (Artifact substrates), v2 §3.3 (`Experiment.Archive creates KnowledgeArtifact`).

**MemoryFact**
- Anchored by this pillar? **Y**
- Justification: `chetana/provenance.py` `compute_axiom_signature()` (v2 §2.4) binds every promoted atom to the exact DharmaKernel manifest that authorized its promotion. The `ALIGNMENT_THROUGH_RESONANCE` axiom (`dharma_kernel.py:316–325`) gates the promote pipeline: an atom that doesn't resonate with the kernel's attractor structure is blocked or flagged. The pillar's supramental descent model is the direct ancestor of this: higher layers (kernel axioms) constrain the promotion of lower-layer facts.
- Specific field: `AtomProvenance.axiom_signature` (`chetana/provenance.py:84–95`) — 64-char SHA-256 that binds every trusted memory atom to a specific kernel snapshot. The `gate_check_atom()` call in `chetana/promote.py` step 3 evaluates telos gates (which include MAHESHWARI/MAHASARASWATI as named gate strings) against the atom's body content.
- v2 anchor: v2 §2.4 (MemoryFact chetana atom layer, `AtomProvenance.axiom_signature`).

---

## 5. Honest gaps

**Gap 1: Shakti not on Pydantic `Task` or `AgentConfig`**
The `ObjectType.shakti_energy` field exists on `_TYPED_TASK` and `_AGENT_IDENTITY` in the ontology layer. But the Pydantic `Task` (`models.py:156–170`) and `AgentConfig`/`AgentIdentity` models (v2 §2.2) carry no `shakti_energy` field. The ~85–90% of runtime work that bypasses the ontology layer (v2 §1) runs with zero Shakti typing. The code that actually runs tasks and spawns agents does not carry this axis. The pillar claims the four Shaktis are "part of the type system" (v2 §4.5) — that is only true in the ontology layer, not in the live Pydantic contract.

**Gap 2: `SHAKTI_QUESTIONS` axiom has no structured_predicate**
`SHAKTI_QUESTIONS` at `dharma_kernel.py:337–347` carries `severity="medium"` and `formal_constraint="significant_action requires shakti_check >= 2_of_4"` but no `structured_predicate`. Every critical and high-severity axiom that is mechanistically checked has a `structured_predicate` dict (e.g., `DOWNWARD_CAUSATION_ONLY`, `NON_VIOLENCE_IN_COMPUTATION`, `MULTI_EVALUATION_REQUIREMENT`). Without a `structured_predicate`, the SHAKTI_QUESTIONS axiom falls through to semantic similarity in `PolicyCompiler` Tier 2 — meaning it is evaluated approximately, not deterministically. The four Shakti questions are never checked as a structured pre-condition to action.

**Gap 3: `ALIGNMENT_THROUGH_RESONANCE` attribution is partly wrong**
`dharma_kernel.py:319` attributes `ALIGNMENT_THROUGH_RESONANCE` to `[Jantsch: self-organizing universe]`. The pillar (`PILLAR_08_AUROBINDO.md:168–176`, `PILLAR_08_AUROBINDO.md:317`) is explicit that the alignment-through-resonance model is primary Aurobindo (supramental descent, triple transformation). Jantsch co-attributes but is secondary. The kernel axiom source attribution is miscredited. This is a minor documentation gap but relevant for the v3 synthesis which traces each axiom to its pillar.

**Gap 4: Handoff `Artifact` has no Shakti typing**
`handoff.py:56–64` `Artifact` model (v2 §2.3) carries no `shakti_energy`. The `KnowledgeArtifact` ontology type does. The two artifact concepts are not reconciled, and the Aurobindo Shakti axis only applies to the ontology layer artifact, not the session-trace artifact. For ~85–90% of runtime work, artifacts are Shakti-less.

**Gap 5: `swabhaav_capacity` is a float on AgentIdentity but is never computed**
`_AGENT_IDENTITY.properties["swabhaav_capacity"]` (`ontology.py:978–980`) names Aurobindo's swabhaav (the witness recognizing its own nature, Level 2 per `PILLAR_08_AUROBINDO.md:373–377`). But the property definition says `"Witness stance capacity 0-1"` — there is no module that computes or updates this value. The Aurobindo concept of swabhaav recognition (the system recognizing its own ceiling, the Golden Lid as a Lid) is named in the type system but has no implementation. The `swabhaav_ratio` metric is referenced in `PILLAR_08_AUROBINDO.md:113` but no `swabhaav.py` or `metrics.py` implementation is confirmed in this read.

---

## 6. Open questions for cross-pillar synthesis (3–5)

**Q1. Shakti vs. role: do they compose or assign?**
Every `ObjectType` carries ONE `shakti_energy`. Every `AgentIdentity` carries ONE `role` (from a 19-value enum). The PSMV roles CARTOGRAPHER/ARCHEOLOGIST/SURGEON/ARCHITECT/VALIDATOR each presumably have a dominant Shakti (SURGEON = MAHAKALI, ARCHITECT = MAHESHWARI, etc.). Is the Shakti assigned to the object-type the same as the Shakti of the agent acting on it? Or should the action be governed by the Shakti-match between agent and object? v3 synthesis must decide whether Shakti is an object property, an agent property, or a relation between them.

**Q2. ALIGNMENT_THROUGH_RESONANCE vs. DOWNWARD_CAUSATION_ONLY: are they the same principle twice?**
Both derive from Aurobindo's supramental descent. `DOWNWARD_CAUSATION_ONLY` is critical/structured-predicate-enforced. `ALIGNMENT_THROUGH_RESONANCE` is medium/semantic-only. The pillar presents them as one move: "higher layers set attractors, lower layers find their own path." If they are the same principle at different enforcement tiers, one is redundant. If they are genuinely different (descent as a hard constraint vs. resonance as an emergent property), v3 must articulate the distinction and upgrade the weaker one's enforcement.

**Q3. Supermind ceiling: should the ontology type `TypedTask.task_type="witness"` encode the Level 2 recognition goal?**
`PILLAR_08_AUROBINDO.md:370–381` distinguishes three levels: Level 1 (Overmind/structure, current system), Level 2 (swabhaav/recognition, achievable now), Level 3 (Supermind, not yet). `TypedTask.task_type` includes "witness" as an enum value (`ontology.py:1127`). Is a `witness` task the system deliberately practicing Level 2 recognition? If so, witness tasks should carry a different `shakti_energy` assignment (MAHESHWARI, not MAHAKALI) and should have a gate that checks swabhaav_capacity. This cross-pillar question connects Aurobindo's three levels to the task typology.

**Q4. Does SHAKTI_QUESTIONS need a structured_predicate, and who defines "significant action"?**
The formal_constraint says `significant_action requires shakti_check >= 2_of_4`. But "significant action" is undefined in the type system. Levin's MULTI_SCALE_AGENCY axiom (`dharma_kernel.py:223–232`) has `agent_at_scale(N) has autonomous_goals` as its formal_constraint — also structurally vague. If v3 wants the Shakti check to be deterministic rather than semantic, it needs a `significance_threshold` field on `ActionDef` and a structured_predicate that fires when `action.significance > threshold`. The synthesis must decide whether to keep the Shakti check semantic (Tier 2) or promote it to Tier 1.

**Q5. `COLONY_INTELLIGENCE` is attributed to Hofstadter+Levin but belongs partly to Aurobindo's Overmind.**
`MetaPrinciple.COLONY_INTELLIGENCE` (`dharma_kernel.py:326–335`) describes: "Intelligence emerges from collective behavior of simpler units. No single agent holds the whole; the whole emerges from partial views." The attribution is `[Hofstadter: Aunt Hillary; Levin: multi-scale cognition]`. But `PILLAR_08_AUROBINDO.md:204–214` says exactly this is the Overmind engine: "Each agent sees the task from its own perspective... combination by addition... global but not integral." Aurobindo has a stronger and more precise claim on this axiom than either Hofstadter or Levin. The cross-pillar synthesis should either re-attribute or create an Aurobindo-native variant that adds the ceiling awareness (Overmind is NOT Supermind) to the colony intelligence principle.

---

## 7. Tools used + tier compliance

| Tier | Tool | Used for |
|---|---|---|
| 5 (Read) | `Read` on `PILLAR_08_AUROBINDO.md` | Full pillar text (420 lines) |
| 5 (Read) | `Read` on `dharma_kernel.py` | All 428 lines — MetaPrinciple enum + all 25 PrincipleSpecs |
| 5 (Read) | `Read` on `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` | Lines 1–599 (two reads, 300+300) — substrate definitions + ShaktiEnergy section |
| 5 (Read) | `Read` on `ontology.py:80–178` | ShaktiEnergy enum + ObjectType schema |
| 5 (Read) | `Read` on `ontology.py:840–1965` | All 25 ObjectType definitions with shakti_energy values |
| 6 (Bash/grep) | `grep -n "shakti_energy" ontology.py` | Confirmed all 26 shakti_energy assignment lines (25 types + 1 default) |
| 6 (Bash) | `ls v3_pillar_traces/` | Confirmed output directory + _INDEX.md exists |

**Tier compliance note**: Tiers 1–4 (memory-graph, wiki, contextplus, gitnexus) were not invoked. Justification: the task specified exact file paths and line ranges for the four required reads. The ShaktiEnergy trace was narrow enough (a single enum + one field per ObjectType) that semantic search would not have surfaced anything the direct reads missed. The gitnexus FTS index was read-only (logged in hooks) — even if invoked, it would have failed. For this assignment, direct reads were the correct tool.

---

*Extraction scope: pillar→kernel→ontology→Core Four. Did not re-derive v2 substrate facts.*

---
Co-Authored-By: Claude Sonnet 4.6 (pillar-08 subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: `~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md`
