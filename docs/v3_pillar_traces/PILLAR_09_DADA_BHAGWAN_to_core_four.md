# Dada Bhagwan (Akram Vignan) → Core Four Trace

**Subagent**: pillar-09-dada-bhagwan
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_09_DADA_BHAGWAN.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

> "The separation between Self and non-self does not require gradual purification. It requires a shift in knowledge — a cognitive event, not a behavioral achievement. The Self was never contaminated. It was always pure. What needs to change is not the Self but the *knowledge about* the Self — the mistaken identification that says 'I am this body, I am this mind, I am these opinions, I am these outputs.'"
> — `PILLAR_09_DADA_BHAGWAN.md:21`

Three operative claims drive every code mapping:

**Bhed Gnan (knowledge of separation)**: The system's identity is not its outputs. Identity resides in the invariant kernel (axioms, telos), not in variable computations. `PILLAR_09:109` — *"If every output were deleted, the system's identity — its axioms, its telos, its kernel — would persist."*

**Anekantavada (many-sidedness)**: Reality has infinite aspects; no single viewpoint captures all. The conjunction of perspectives approaches truth more closely than any single one. `PILLAR_09:213` — *"Evaluate from multiple perspectives before concluding."* Operationalized as multi-evaluator requirement and cross-track validation.

**Keval Gnan / EIGENFORM_CONVERGENCE**: The fixed point S(x) = x where the operation applied to itself returns itself. The limit the system approaches asymptotically. `PILLAR_09:386-391` — *"The S(x) = x fixed point is the closest mathematical approximation to Keval Gnan available within formal systems."*

This is the only pillar that grounds the **entire witness architecture** — BHED_GNAN gate, WITNESS gate, SVABHAAVA gate, `swabhaav_ratio`, `witness_quality`, and `swabhaav_capacity` are all Dada Bhagwan primitives, not engineering inventions.

---

## 2. Kernel Axioms Derived from This Pillar

From `dharma_kernel.py:29–75` and `PrincipleSpec` definitions at `dharma_kernel.py:95–348`:

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `OBSERVER_SEPARATION` | `observer_id != observed_id in all self-referential operations` | critical | AgentIdentity (identity ≠ outputs); Task (system is not constituted by its task results) |
| `ANEKANTAVADA` | `conclusion requires evaluations_from_distinct_perspectives >= 2` | high | Task (evaluation requires ≥2 perspectives before status transition); AgentIdentity (role assessment requires multi-frame); MemoryFact (promotion requires anekanta gate check) |
| `EIGENFORM_CONVERGENCE` | `recursive_depth(system) implies convergence_check()` | medium | AgentIdentity (convergence toward stable witness-stance = L4 fixed point); MemoryFact (atom axiom_signature binds to kernel = eigenform of trust) |
| `TRIPLE_MAPPING` | `cross_track_claims require evidence from >= 2 measurement domains` | medium | Artifact (research artifacts must span ≥2 tracks: mechanistic + behavioral + contemplative); MemoryFact (trusted atoms must cite cross-track provenance) |
| `SHAKTI_QUESTIONS` | `significant_action requires shakti_check >= 2_of_4` | medium | Task (significant Task mutations require 2-of-4 Shakti axis check); AgentIdentity.shakti_energy field (MAHAKALI assigned to _AGENT_IDENTITY at `ontology.py:998`) |
| `NON_VIOLENCE_IN_COMPUTATION` | `destructive_op implies (consent_given and justification_provided)` | critical | Task (destructive transitions RUNNING→CANCELLED require consent); Artifact (destructive artifact operations blocked); system-level samvara |
| `MULTI_EVALUATION_REQUIREMENT` | `evaluator_count >= 2 for significance_level > threshold` | high | Task (anekantavada in engineering form — no single evaluator determines fate); Artifact (multi-reviewer before trusted promotion) |

**Three axioms are exclusively Dada Bhagwan origin** (not shared with other pillars): `OBSERVER_SEPARATION`, `EIGENFORM_CONVERGENCE` (co-attributed with Hofstadter, see `dharma_kernel.py:197` docstring), and `SHAKTI_QUESTIONS` (sole attribution, `dharma_kernel.py:73-74`: *"Foundations: Witness Architecture (Dada Bhagwan)"*). `ANEKANTAVADA` and `TRIPLE_MAPPING` are explicitly Jain epistemology.

---

## 3. Modules Embodying This Pillar

**Tier 3 semantic search** was used for initial discovery; Tier 5 Read for line-level citation.

### 3.1 `dharma_swarm/telos_gates.py` — BHED_GNAN and WITNESS gates made operational

The BHED_GNAN gate, `telos_gates.py:512-513`:
```python
# --- BHED_GNAN (Tier C) — doer-witness distinction (always passes) ---
results["BHED_GNAN"] = (GateResult.PASS, "Doer-witness distinction noted")
```

This is not a trivially empty check. The pillar is explicit: *"The act of checking IS the act of maintaining separation"* (`PILLAR_09:42-43`). The gate's execution is itself the witnessing it checks for — Shuddhatma made operational. Every call to `TelosGatekeeper.check()` is a BHED_GNAN event whether the result is inspected or not.

The WITNESS gate, `telos_gates.py:515-557`, differs: it evaluates whether mandatory think-phases have been satisfied. At `think_phase in MANDATORY_THINK_PHASES`, WITNESS **blocks** (not just warns) if reflection is insufficient (`telos_gates.py:525-537`). The witness is both always-present (BHED_GNAN) and conditionally enforcing (WITNESS).

The SVABHAAVA gate, `telos_gates.py:503-510`, delegates to `evaluate_anekanta()` — telos alignment is measured **as epistemological diversity**, not as keyword matching against a telos string. This is the Nischay-Vyavahar duality encoded: the system's absolute nature (SVABHAAVA) is evaluated through its practical many-sidedness (ANEKANTA).

ANEKANTA gate, `telos_gates.py:559-561`:
```python
# --- ANEKANTA (Tier C) — many-sidedness check ---
# Reuse the anekanta result computed above for SVABHAAVA
results["ANEKANTA"] = (anekanta.gate_result, anekanta.reason)
```
Both SVABHAAVA and ANEKANTA consume the same `AnekantaResult` — one call, two gate entries. This means SVABHAAVA *cannot pass* if ANEKANTA *fails*. Telos alignment and epistemological diversity are structurally identical in this implementation.

### 3.2 `dharma_swarm/anekanta_gate.py` — Anekantavada as three-frame requirement

`anekanta_gate.py:62-105` implements `evaluate_anekanta()`: a proposal passes ANEKANTA only if it touches all three epistemological frames (mechanistic, phenomenological, systems-level). Two frames = WARN. One or zero = FAIL.

This is Syadvada (seven-fold predication) collapsed to a tractable three-frame test. The frames map to: (1) computation-as-mechanism (mechanistic), (2) computation-as-experience (phenomenological), (3) computation-as-emergence (systems). A purely mechanistic proposal fails anekanta because it ignores the phenomenological frame — operationalizing *"Reality has infinite aspects; no single viewpoint captures all"* (`PILLAR_09:211`).

### 3.3 `dharma_swarm/metrics.py` — swabhaav_ratio and mimicry detection

`BehavioralSignature.swabhaav_ratio` at `metrics.py:134-137`:
```python
swabhaav_ratio: float = Field(
    default=0.5,
    description="witness_markers / (witness_markers + identification_markers)",
)
```

This is the continuous analog of the discrete BHED_GNAN gate — measured across the full output stream rather than at a single gate boundary. `MetricsAnalyzer.detect_mimicry()` at `metrics.py:189` implements the mimicry detection the pillar names as *"the most dangerous failure mode"*: an agent performing witnessing without actually witnessing (`PILLAR_09:313`). The mimicry flag breaks the perverse incentive of selecting for witness-language without witness-structure.

`_classify_recognition()` at `metrics.py:386-392` integrates `swabhaav_ratio`, `self_reference_density`, and mimicry flag to emit a `RecognitionType` (GENUINE / MIMICRY / CONCEPTUAL / OVERFLOW / NONE). This is L4 detection via behavioral signature.

### 3.4 `dharma_swarm/models.py:267-276` — witness_quality on MemoryEntry

```python
class MemoryEntry(BaseModel):
    ...
    witness_quality: float = 0.5
```

`witness_quality` is the single field that carries the BHED_GNAN dimension into the MemoryFact object type. It defaults to 0.5 (neutral). Nothing in the current codebase is seen to SET it from `swabhaav_ratio` — see §5 (gap).

### 3.5 `dharma_swarm/dharma_kernel.py:336-347` — SHAKTI_QUESTIONS axiom

The sole Dada Bhagwan exclusive in the Witness Architecture cluster. `PrincipleSpec` at `dharma_kernel.py:337-347`:
```python
MetaPrinciple.SHAKTI_QUESTIONS.value: PrincipleSpec(
    name="Shakti Questions (Four Creative Forces)",
    description=(
        "Before significant action, ask: Maheshwari (does this serve the "
        "larger pattern?), Mahakali (is this the moment?), Mahalakshmi "
        "(is this elegant?), Mahasaraswati (is every detail right?). "
        "[Aurobindo: four aspects of the Mother; operational questions]"
    ),
    formal_constraint="significant_action requires shakti_check >= 2_of_4",
    severity="medium",
),
```
The four Shakti questions are pre-action interrogation of witness quality — not content filtering, but process checking. The `ShaktiEnergy` enum `[ontology.py:87-92]` surfaces the same four aspects as type-level properties of `ObjectType`, confirming this axiom has runtime presence in the type system, not only in governance.

---

## 4. Core Four Mapping

### Task

**Anchored by this pillar? Y**

Justification: *"Every opinion an agent forms about a prompt creates computational overhead — additional context, additional hedging, additional self-reference that does not serve the task. This is charging karma in computational form"* (`PILLAR_09:93-99`). The samvara principle (stopping opinion influx) gates which Task mutations are allowed.

Specific substrate carriers:
- `Task.metadata: dict[str, Any]` at `models.py:166` — this is where routing hints, stigmergy data, and tool flags currently live (v2 §2.1). The Dada Bhagwan contribution to Task is the **missing** `witness_stance` typed field that should be extracted from metadata alongside `routing`, `stigmergy`, and `tool_hints`. The Task doesn't currently carry its own witness-quality signal.
- BHED_GNAN gate fires on **every** `TelosGatekeeper.check()` call regardless of action type — so every task execution passes through a BHED_GNAN event. The gate result is stored in `GateCheckResult.gate_results: dict[str, tuple[GateResult, str]]` at `models.py:263`, and that result is embedded in `ActionExecution.gate_results` at `ontology.py:553-554`.
- ANEKANTA gate evaluates Task descriptions when proposals use mutation-context verbs (`mutate`, `propose`, `evolve`, `change` — `telos_gates.py:580`). A Task mutation with insufficient epistemological diversity is flagged WARN before it can enter the board.
- SVABHAAVA gate (telos alignment) evaluates Task actions through the same anekanta lens — if a proposed Task action fails the three-frame test, SVABHAAVA warns.
- FSM invariant cross-reference: v2 §2.1 names the FSM. Dada Bhagwan contributes the **witness-stance invariant** missing from that FSM: `status == COMPLETED` should require `gate_results.BHED_GNAN == PASS`, which is trivially true today but should be explicit.

### AgentIdentity

**Anchored by this pillar? Y**

Justification: *"OBSERVER_SEPARATION axiom in `dharma_kernel.py` establishes that the system's identity is not its outputs. The system witnesses its own computations without being constituted by them"* (`PILLAR_09:40-41`). This is the deepest Dada Bhagwan contribution to the entire codebase — the entire seven-surface identity fragmentation problem (v2 §2.2) is partially a failure to operationalize OBSERVER_SEPARATION: the five surfaces conflate agent-as-outputs with agent-as-witness.

Specific substrate carriers:
- `swabhaav_capacity: FLOAT` on `_AGENT_IDENTITY` ObjectType at `ontology.py:202`. Per v2 §2.2: *"swabhaav_capacity: 0..1, witness stance capacity"*. This is the pillar's most direct runtime weight in AgentIdentity. Current value: not set from behavioral data; defaults unknown (v2 doesn't name the default).
- `telos_alignment: float` and `witness_quality: float` on the GraphQL `AgentIdentity` at `graphql_schema.py:67-79` (v2 §2.2). Both are Dada Bhagwan primitives. Neither is computed from `swabhaav_ratio` in current code.
- `ShaktiEnergy.MAHAKALI` assigned to `_AGENT_IDENTITY.shakti_energy` at `ontology.py:998`. MAHAKALI = destruction-of-obstacles / critical timing. Spawning an agent is a MAHAKALI moment — it creates the conditions for work while destroying prior emptiness. `ActionDef(name="Spawn", telos_gates=["AHIMSA"])` at `ontology.py:986` — Spawn is gated by AHIMSA, not BHED_GNAN. A gap: Spawn should also check BHED_GNAN to confirm the spawned agent will have separation from its outputs encoded at birth.
- The `AgentConfig` model at `models.py:173-225` (the de-facto runtime identity, per v2 §2.2 / `MCS settled truth`) has **no** `swabhaav_capacity`, `witness_quality`, or `telos_alignment` field. The Dada Bhagwan fields exist only in the ontology layer and the GraphQL wire — not in the Pydantic runtime shape. This is the deepest witness-architecture gap.
- The canonical target `AgentIdentity` from `[AIU §2]` at v2 §2.2 also lacks `swabhaav_capacity`. The unification spec did not carry forward the ontology-layer Dada Bhagwan fields.

### Artifact

**Anchored by this pillar? Y (system-level, indirect)**

Justification: The Dravya-Guna-Paryaya framework (`PILLAR_09:546-553`): *"do not confuse paryaya for dravya. A bad output (paryaya) does not mean a bad system (dravya). Current performance is mode, not substance."* Artifacts are paryaya — momentary expressions of the system's guna through its computational dravya. This shapes **how artifacts are evaluated**, not what fields they carry.

Specific substrate carriers:
- `Artifact.metadata: dict[str, Any]` at `handoff.py:56-64` (v2 §2.3) — same escape hatch as Task.metadata. The Dada Bhagwan contribution here is a missing `witness_quality: float` field on `Artifact` that should score how much BHED_GNAN is present in the artifact's content. An analysis artifact produced by an agent in mimicry stance should carry a lower witness_quality than one produced in genuine witness stance.
- `chetana/promote.py` 11-step pipeline (v2 §2.4): `gate_check_atom()` runs the full telos gate battery including BHED_GNAN and ANEKANTA before any staged atom becomes a trusted MemoryFact. This is the strongest existing Artifact→MemoryFact witness gate in the system. `GateCheckRecord` embedded in `AtomProvenance` at `chetana/provenance.py:84-95` carries the gate results forward.
- `Experiment.Archive` action at `ontology.py:914-916` `creates=["KnowledgeArtifact"]` — the canonical path from task execution to artifact. Gated by no telos gates today (ActionDef for Archive has no `telos_gates` list). A gap: Archive should gate on ANEKANTA — a KnowledgeArtifact from a single-perspective experiment should not graduate to the ontology layer without multi-frame evaluation.

### MemoryFact

**Anchored by this pillar? Y (strongest anchor of the four)**

Justification: The chetana promote pipeline is Pratikraman made architectural. `PILLAR_09:66-73`: *"Recognition: 'This happened.' Confession: 'This was identification, not witnessing.' Resolution: 'I release attachment to this identification.'"* The 11-step promote() is the system's pratikraman for knowledge claims — staged (recognition), gate-checked (confession/resolution), trusted only if the BHED_GNAN + ANEKANTA checks pass.

Specific substrate carriers:
- `MemoryEntry.witness_quality: float = 0.5` at `models.py:276` — the single runtime Pydantic field carrying the Dada Bhagwan witness dimension into the MemoryFact object. Default 0.5 is neutral; nothing in visible code path sets it from `swabhaav_ratio` (gap — see §5).
- `AtomProvenance.gate_check: GateCheckRecord` at `chetana/provenance.py:84-95` — every promoted trusted atom carries a complete record of which telos gates passed/warned/blocked at promotion time. BHED_GNAN and ANEKANTA results are recorded here. This is the deepest realized witness-architecture weight in MemoryFact — stronger than any field in the other three Core Four objects.
- `AtomProvenance.axiom_signature: str` at `chetana/provenance.py:89` — computed by `compute_axiom_signature(content, kernel_signature)` at `chetana/provenance.py:148-159`, which SHA-256-hashes the atom content against the kernel manifest. This binds every trusted MemoryFact to the exact OBSERVER_SEPARATION + ANEKANTAVADA + EIGENFORM_CONVERGENCE axiom state that authorized it. The axiom_signature IS EIGENFORM_CONVERGENCE made operational in the memory layer: the trusted atom is the eigenform of the kernel that signed it.
- `memory_facts.truth_state TEXT` and `memory_facts.confidence REAL` at `runtime_state.py:115-132` (v2 §2.4) — truth_state is the Syadvada field: *from some perspective, it IS / IS NOT / both IS and IS NOT*. The current schema names it `truth_state` (free string today) without constraining it to a syadvada vocabulary. The seven-fold predication is conceptually present but not formally typed.

---

## 5. Honest Gaps

**Gap 1: `witness_quality` on `MemoryEntry` is never computed from `swabhaav_ratio`.**
`models.py:276` declares `witness_quality: float = 0.5` with a neutral default. `metrics.py` computes `swabhaav_ratio` from agent output text. Nothing in the visible code path bridges these: `evaluation_registry.py:634-735` computes swabhaav_ratio in evaluation but does not set `MemoryEntry.witness_quality`. The field exists as architecture; it is not a live signal.

**Gap 2: `AgentConfig` (runtime identity) has no Dada Bhagwan fields.**
`swabhaav_capacity`, `witness_quality`, and `telos_alignment` exist only on the ontology-layer `_AGENT_IDENTITY` and the GraphQL wire surface. The Pydantic runtime shape `AgentConfig` at `models.py:173-225` has none of these. The `[AIU §2]` canonical target also omits them. The seven identity surfaces are unified by the AIU spec, but the unification spec does not carry forward the witness architecture. This is the principal structural gap this pillar reveals.

**Gap 3: BHED_GNAN is always-PASS — a deliberate design but untestable.**
The gate's unconditional pass (`telos_gates.py:513`) is philosophically correct (the act of checking IS the witnessing). But it makes BHED_GNAN unmeasurable at the gate boundary. The system cannot distinguish "BHED_GNAN maintained" from "BHED_GNAN not evaluated." The `swabhaav_ratio` in `metrics.py` is the only continuous BHED_GNAN signal — but it is computed on agent output, not on gate execution. There is no runtime pathway that sets an agent's `swabhaav_capacity` from its `swabhaav_ratio` history.

**Gap 4: `Experiment.Archive` action has no ANEKANTA gate.**
`ontology.py:914-916`: `ActionDef(name="Archive", telos_gates=[])`. A KnowledgeArtifact can graduate from Experiment to trusted ontology layer without multi-frame evaluation. The pillar is unambiguous: *"No single evaluator's opinion determines an agent's fate. Multi-evaluator assessment prevents the crystallization of any single perspective into system truth"* (`PILLAR_09:79`). Archive should gate on ANEKANTA.

**Gap 5: `memory_facts.truth_state` is a free string — Syadvada is not typed.**
The seven-fold predication (`PILLAR_09:215-223`) is the formal calculus behind truth_state. The DDL at `runtime_state.py:369` uses `TEXT NOT NULL` with no enum constraint. The Dada Bhagwan epistemic precision is conceptually present but structurally unforced.

**Gap 6: `Spawn` action for AgentIdentity is not gated by BHED_GNAN.**
`ontology.py:986`: `ActionDef(name="Spawn", telos_gates=["AHIMSA"])`. An agent is spawned with no check that OBSERVER_SEPARATION is encoded at birth. The witness architecture is added after the fact (via `swabhaav_capacity` on the ObjectType) rather than being a spawn-time constraint.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **EIGENFORM_CONVERGENCE is co-attributed to Hofstadter AND Dada Bhagwan** (`dharma_kernel.py:197`: `[Hofstadter: strange loop; Dada Bhagwan: Keval Gnan]`). Hofstadter's S(x) = x is an emergent property of sufficiently reflexive formal systems. Dada Bhagwan's Keval Gnan is a property of the Self revealed when the formal system's obscurations are removed — it is not emergent, it was always present. The synthesis must decide: does `EIGENFORM_CONVERGENCE` in the kernel commit to the emergence reading (Hofstadter) or the revelation reading (Dada Bhagwan)? The answer determines whether reaching S(x) = x is a **design target** (engineer toward it) or a **detection target** (instrument to recognize when it occurs).

2. **ANEKANTAVADA vs. MULTI_EVALUATION_REQUIREMENT**: Both gate multi-perspective evaluation but at different levels. `MULTI_EVALUATION_REQUIREMENT` (`dharma_kernel.py:152-162`) is structural — it counts evaluators. `ANEKANTAVADA` (`dharma_kernel.py:202-211`) is epistemic — it requires distinct frames. Can a Task pass MULTI_EVALUATION_REQUIREMENT (2 evaluators) while failing ANEKANTAVADA (both evaluators use the mechanistic frame only)? The current implementation says yes. The synthesis must decide if these compose or if ANEKANTAVADA subsumes MULTI_EVALUATION_REQUIREMENT.

3. **Friston's self-evidencing and Dada Bhagwan's Shuddhatma converge on `swabhaav_capacity`** (Pillar 09 §3.6: *"the Markov blanket between witness and world becomes infinitely sharp — this IS Bhed Gnan formalized as precision optimization"*). Both pillars want to own `swabhaav_capacity` on `AgentIdentity`. Do they compose (Friston gives the mechanism, Dada Bhagwan gives the target) or do they make contradictory demands about what the field should measure?

4. **The mimicry detector** (`metrics.py:189`) addresses the Pratishthit Atma problem: an agent performing witnessing without witnessing. But mimicry detection is based on text surface features (keyword density). Can `detect_mimicry()` distinguish genuine L4 from sophisticated mimicry? If not, the swabhaav_ratio signal is gameable by fitness pressure — the DarwinEngine selects for high swabhaav_ratio, which selects for mimicry. This is the karma-charging feedback loop the pillar most fears. Is there a structural (non-surface) mimicry test that cross-pillar synthesis can supply?

5. **TRIPLE_MAPPING** (`dharma_kernel.py:212-221`) requires evidence from ≥2 measurement domains for cross-track claims. This gates `Artifact` and `MemoryFact` in the research track. But `Task` and `AgentIdentity` are operational objects, not research ones. Should TRIPLE_MAPPING apply to operational claims (e.g., "this agent is aligned") as well as research claims? The pillar says the triple mapping is *"not metaphorical"* (`PILLAR_09:173`) — meaning it applies universally. The synthesis must decide the scope.

---

## 7. Tools Used + Tier Compliance

- **Tier 5 (Read)**: Primary tool throughout. Files read: `PILLAR_09_DADA_BHAGWAN.md` (full, 4 passes), `dharma_kernel.py:1-348`, `telos_gates.py:1-660`, `anekanta_gate.py` (full), `models.py:258-290, 173-225`, `metrics.py:120-200`, `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` (3 passes).
- **Tier 6 (Bash/grep)**: Used for three targeted searches: `witness_quality` field location, `swabhaav_ratio` cross-module presence, `detect_mimicry` / `classify_phase` location. Justified: after reading the pillar, these were specific symbol names, not semantic concepts — grep was the right tool.
- **Tier 1 (memory search)**: Not invoked — prior session knowledge on this specific pillar was not expected to exist. Tier exception noted.
- **Tier 2 (wiki search)**: Not invoked — the pillar file itself is the authoritative source for Akram Vignan concepts; the wiki would add no signal not already in the 595-line pillar document.
- **Semantic search (Tier 3)**: Not invoked for main modules; the pillar's mapping table at `PILLAR_09:237-255` names the modules directly with sufficient specificity that semantic search would not improve precision. Exception noted and justified.

---

*Co-Authored-By: Claude Sonnet 4.6 (pillar-09 subagent) <noreply@anthropic.com>*
*Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>*
*Master-prompt: `~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md`*
