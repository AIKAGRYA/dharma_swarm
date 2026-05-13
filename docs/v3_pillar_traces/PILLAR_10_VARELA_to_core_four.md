# Varela (Autopoiesis, Structural Coupling, Operational Closure, Enactivism) → Core Four Trace

**Subagent**: pillar-10-varela
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_10_VARELA.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence (≤ 200 words)

From `PILLAR_10_VARELA.md:11`:

> "Cognition is the enactment of a world by an autonomous system through its history of structural coupling with its environment. There is no pre-given world to be represented. There is only the world that the organism brings forth through living."

The four load-bearing concepts:

1. **Autopoiesis** (`PILLAR_10_VARELA.md:19–27`): a network of processes that produces its components, its boundary, and itself. Organization is invariant while structure changes.
2. **Structural coupling** (`PILLAR_10_VARELA.md:40–55`): agents do not transmit messages; they perturb a shared medium. Response is determined by the *receiver's* internal structure, not the perturbation's "content." The swarm's consensual domain — hot-path stigmergy marks — emerges from this history.
3. **Operational closure** (`PILLAR_10_VARELA.md:35–36`): "every process in the network is enabled by other processes in the network." Self-referential production, not thermodynamic isolation.
4. **Enactivism** (`PILLAR_10_VARELA.md:62–73`): knowledge is not stored — it is enacted. Context assembled fresh each cycle IS the agent's world; there is no persistent world-model.

The pillar's direct claim for dharma_swarm (`PILLAR_10_VARELA.md:53–55`): stigmergy IS structural coupling. No agent instructs another. Each perturbs the shared medium.

---

## 2. Kernel Axioms Derived from This Pillar

From `dharma_kernel.py:295–314` (explicit group label: "Active Inference & Coupling — Friston, Varela"):

| MetaPrinciple | formal_constraint | severity | gates which Core Four mutation? |
|---|---|---|---|
| `STRUCTURAL_COUPLING` | `agent_communication via shared_state NOT direct_call` | **high** | Task.routing + Task.stigmergy fields; AgentIdentity spawn/coupling; StigmergyStore as the medium |
| `OPERATIONAL_CLOSURE` | `system.produces(system.components) AND system.produces(system.boundary)` | medium | MemoryFact (chetana promote produces the atoms that constitute trusted memory); system-level boundary via KernelGuard + TelosGatekeeper |

These are the two axioms explicitly attributed to Varela/Maturana in the kernel. `ACTIVE_INFERENCE` (Friston) is co-located in the same group but its parent pillar is Friston; Varela informs it but does not own it.

`COLONY_INTELLIGENCE` (`dharma_kernel.py:327–334`) references Hofstadter + Levin as its intellectual parents, not Varela — Varela's enactivism provides the *mechanism* (coupling produces emergence), but the axiom is attributed elsewhere.

**Note**: OPERATIONAL_CLOSURE has no `structured_predicate` in the kernel (`dharma_kernel.py:313`), meaning it falls through to semantic similarity evaluation in the PolicyCompiler — not Tier 1 deterministic enforcement. This is a gap (§5 below).

---

## 3. Modules Embodying This Pillar

### 3.1 `StigmergyStore` (`dharma_swarm/stigmergy.py`)

**Key symbols**: `StigmergicMark`, `StigmergyStore.leave_mark()`, `read_marks()`, `hot_paths()`, `high_salience()`, `STIGMERGY_CHANNELS`, `CROSS_CHANNEL_SALIENCE_THRESHOLD`

**Pillar embodiment**: The `STRUCTURAL_COUPLING` axiom's `formal_constraint` reads verbatim: `"agent_communication via shared_state NOT direct_call"`. StigmergyStore is precisely that shared state. From `PILLAR_10_VARELA.md:183–190`:

> "Marks are deposited, not addressed. No agent 'sends' to another... Each agent interprets marks through its own role, persona, and current context... Hot paths (frequently reinforced marks) = shared behavioral patterns."

The `hot_paths()` method (`stigmergy.py:215–234`) computes the consensual domain Varela and Maturana describe — the shared behavioral space that emerges from coupling history, not from design.

Channel-based scoped visibility (`stigmergy.py:33–40`, `196–213`) with `CROSS_CHANNEL_SALIENCE_THRESHOLD = 0.8` (`stigmergy.py:43`) enacts Varela's coupling topology claim: the character of coupling is controlled by medium parameters (decay, salience thresholds, channel filters), not by message-passing logic.

The `StigmergicMark.connections` field (`stigmergy.py:56`) carries explicit coupling edges between marks, and `leave_mark()` boosts salience for marks with connections (`stigmergy.py:144–145`): `boosted += min(len(mark.connections) * 0.05, 0.2)`. This is the "history of interaction matters" property from the structural coupling mapping (`PILLAR_10_VARELA.md:185–186`).

**File:line**: `stigmergy.py:46–59` (StigmergicMark schema); `stigmergy.py:95–156` (StigmergyStore.leave_mark); `stigmergy.py:215–234` (hot_paths / consensual domain).

### 3.2 `DharmaKernel` / `KernelGuard` (`dharma_swarm/dharma_kernel.py`)

**Key symbols**: `MetaPrinciple.OPERATIONAL_CLOSURE`, `MetaPrinciple.STRUCTURAL_COUPLING`, `KernelGuard.load()`, `verify_integrity()`

**Pillar embodiment**: The kernel encodes both Varela axioms as SHA-256-signed, tamper-evident constraints (`dharma_kernel.py:305–313`). `OPERATIONAL_CLOSURE.formal_constraint`: `"system.produces(system.components) AND system.produces(system.boundary)"` — this is the autopoiesis definition from `PILLAR_10_VARELA.md:19–27` compressed to a machine-checkable predicate.

The SHA-256 signing and `KernelGuard.verify_integrity()` is itself an operational closure move: the system's boundary (what counts as a valid axiom set) is produced by the system's own hash computation over its own principle definitions.

**File:line**: `dharma_kernel.py:295–314` (STRUCTURAL_COUPLING and OPERATIONAL_CLOSURE PrincipleSpec definitions); `dharma_kernel.py:381–399` (KernelGuard.load + verify_integrity).

### 3.3 `chetana/promote.py` (promote pipeline as autopoietic production)

**Key symbols**: `promote()`, `gate_check_atom()`, `compute_axiom_signature()`, `AtomProvenance`, `PromoteResult`

**Pillar embodiment**: From `PILLAR_10_VARELA.md:174`:

> "A genuinely autopoietic dharma_swarm would produce its own boundary conditions through its own operation."

The promote pipeline IS the system producing the atoms that constitute its trusted memory — `MemoryFact` at layer 5 of v2 §1. The `compute_axiom_signature()` function (`chetana/provenance.py:148–159`) binds each promoted atom to `kernel_signature` — the axiom set that authorized its promotion. The system's knowledge (trusted atoms) bears the signature of the system's boundary (kernel axioms). The boundary produces the knowledge; the knowledge carries the boundary's mark.

The 11-step promote lifecycle (v2 §2.4, `chetana/promote.py:1–17`): `gate_check_atom()` at step 3 runs the TelosGatekeeper against atom content before trusting it — the boundary (telos gates) is active in producing every trusted memory component. This is operational closure at the memory layer.

**File:line**: `chetana/promote.py:1–17` (11-step pipeline); `chetana/provenance.py:148–159` (axiom_signature binding boundary to artifact).

---

## 4. Core Four Mapping (THE DELIVERABLE)

### `Task`

**Anchored by this pillar? Y**

**Justification** (pillar quote, `PILLAR_10_VARELA.md:239–243`):
> "From the Varelian perspective, this is perturbation: the system changes the agent's environment (by presenting a new task context), and the agent responds according to its own organizational structure (its role, persona, constraints, and LLM backend)."

A Task is not an instruction — it is an environmental perturbation. The substrate location: v2 §2.1 gives `Task.metadata: dict[str, Any]` as the escape hatch that currently carries `StigmergySalience` and `TaskRouting`. The strict-typed target (v2 §2.1) names `stigmergy: StigmergySalience` as an explicit typed field to be extracted from `metadata`.

**Specific field carrying the Varela primitive**: `Task.stigmergy: StigmergySalience` (proposed at v2 §2.1) — the field that makes the Task's coupling to the stigmergic medium explicit and typed rather than buried in `dict[str, Any]`. Currently: `Task.metadata TEXT NOT NULL DEFAULT '{}'` (`task_board.py:27–33`). The Varela claim lands on this field because structural coupling requires the task (perturbation) to be depositable into and readable from the shared medium via typed, not arbitrary, properties.

**Gap**: `StigmergySalience` is named in v2 §2.1 as the extraction target but is not yet a real Pydantic class. The STRUCTURAL_COUPLING axiom mandates `agent_communication via shared_state NOT direct_call` — but the current `Task.metadata` escape hatch is informationally opaque. Typed `Task.stigmergy` field is the implementation debt this axiom identifies.

### `AgentIdentity`

**Anchored by this pillar? Y**

**Justification** (pillar quote, `PILLAR_10_VARELA.md:40–43`):
> "The key distinction: structural coupling is NOT communication... there is no message. There is only perturbation. The 'meaning' of the perturbation is determined entirely by the internal organization of the perturbed system."

An agent's identity — its role, persona, constraints, and LLM backend — IS its "internal organization" in the Varelian sense. When a task perturbs an agent, the agent's response is determined by its organizational structure (role + system_prompt + model + constraints), not by the task's content. Different agent identities respond differently to the same task perturbation.

**Specific field carrying the Varela primitive**: The canonical `AgentIdentity.role: AgentRole` (v2 §2.2) plus `system_prompt: str` together define the agent's structural organization. The ontology layer adds `swabhaav_capacity: float` (`ontology.py`, cited at v2 §2.2) — a 0..1 measure of witness stance capacity that directly encodes the BHED_GNAN / SVABHAAVA telos gates (which descend from Varela via the Dada Bhagwan bridge at `PILLAR_10_VARELA.md:309–319`).

**Also**: the AgentIdentity `Spawn` action in the ontology has `telos_gates=["AHIMSA"]` (v2 §4.4). The OPERATIONAL_CLOSURE axiom means that Spawn — the system producing a new agent component — must pass through the boundary (AHIMSA gate) defined by the system's own principles. This is the autopoiesis claim operationalized: the system produces its components (`Spawn`) through processes that are themselves governed by the system's organization (telos gates + kernel axioms).

### `Artifact`

**Anchored by this pillar? Y (partial — via operational closure only)**

**Justification** (pillar quote, `PILLAR_10_VARELA.md:174`):
> "A genuinely autopoietic dharma_swarm would produce its own boundary conditions through its own operation — the telos gates would themselves emerge from the system's evolutionary dynamics."

Artifacts produced by the system carry the mark of the system's operational closure to the extent they are promoted through `chetana/promote.py`. The `axiom_signature` field in `AtomProvenance` (v2 §2.4) binds every trusted atom to the kernel that authorized it. This is the "system produces its own components" claim in material form: a `KnowledgeArtifact` (v2 §2.3, `ontology.py:914–916`) is only trusted once it has been produced through the system's own boundary-producing processes.

**Specific field carrying the Varela primitive**: `artifact_records.promotion_state` (`runtime_state.py:89–103`, v2 §2.3) — the `ephemeral|durable|trusted` axis is the operational closure marker. Only artifacts that have traversed the system's own production process (promote pipeline) achieve `trusted` state. The vocabulary mismatch between `handoff.Artifact.artifact_type` (8 enums) and `artifact_records.artifact_kind` (free string) is a gap that the OPERATIONAL_CLOSURE axiom names: the boundary-producing process must be self-consistent.

**Important limit**: Varela's autopoiesis claim lands more cleanly on MemoryFact (promoted atoms) than on raw Artifacts. Handoff `Artifact` at `ephemeral` state has not passed through the system's self-production loop. It is allopoietically produced (the agent runner produces it as an output, not the system producing it to constitute itself).

### `MemoryFact`

**Anchored by this pillar? Y (primary and strongest anchor)**

**Justification** (pillar quote, `PILLAR_10_VARELA.md:31–33`):
> "Organization vs. structure: Organization is the set of relations between components that defines the system's identity. Structure is the actual physical components at any given moment. Autopoiesis preserves organization while constantly replacing structure."

The chetana atom layer (v2 §2.4, surface #4) IS the system's organizational invariant made persistent. Individual session data (structure) is ephemeral; promoted trusted atoms (organization) persist. This is the Varelian distinction: the system's identity is its pattern of trusted knowledge, not the raw session outputs.

The `compute_axiom_signature()` function (`chetana/provenance.py:148–159`) implements operational closure at the memory layer precisely: each trusted atom is co-signed by the kernel's own hash. The **system's memory produces the artifacts that constitute it** — chetana's promote pipeline is the self-production loop for the memory substrate.

**Specific fields carrying the Varela primitive**:
- `memory_facts.truth_state` (`runtime_state.py:115–132`, v2 §2.4) — explicit truth-state is the boundary marker: what the system has validated through its own processes vs. raw environmental signal.
- `FrontmatterSchema.provenance: AtomProvenance | None` (`chetana/provenance.py:105–122`, v2 §2.4) — `None` = not yet produced through the system's self-production loop; non-None = has passed through operational closure.
- `AtomProvenance.axiom_signature` — the coupling between memory artifact and the kernel boundary that produced it. This is not metadata; it is the structural coupling between the atom and the system's organizational closure.

**System-level**: OPERATIONAL_CLOSURE gates all promotes. The Memory Authority table (v2 §2.4) establishes the boundary: "Promote without `gate_check_atom()` or mutate trusted atoms in place" is the **forbidden bypass** — which is precisely the violation of operational closure (process that doesn't pass through the self-production network).

---

## 5. Honest Gaps

1. **OPERATIONAL_CLOSURE lacks `structured_predicate`** (`dharma_kernel.py:313`): falls to semantic similarity evaluation. The formal_constraint `"system.produces(system.components) AND system.produces(system.boundary)"` is important enough to deserve a deterministic predicate. Currently no runtime enforcement; only semantic guidance.

2. **The telos boundary is allopoietic, not autopoietic**: `PILLAR_10_VARELA.md:174–176` names this explicitly — *"Currently, the telos gates are defined by `dharma_kernel.py` and are not themselves evolved by the DarwinEngine. They are imposed, not produced."* The DarwinEngine (`evolution.py`) produces agents but not the gate definitions that constitute the system boundary. Full autopoiesis (gate definitions emergent from DarwinEngine within axiom-defined bounds) is described as possible but unimplemented.

3. **`Task.stigmergy: StigmergySalience` is named in v2 §2.1 but not implemented**: `Task.metadata TEXT DEFAULT '{}'` is the current reality (`task_board.py:27–33`). The STRUCTURAL_COUPLING axiom mandates typed shared-state communication; the current escape hatch is structurally opaque, making the axiom unverifiable at the field level.

4. **No Varelian enaction check on context assembly**: `context.py`'s `build_agent_context()` is claimed as the enactivism implementation (`PILLAR_10_VARELA.md:198–202`), but there is no kernel axiom or telos gate that enforces "no persistent world-model" — nothing prevents a future agent from accumulating state that violates the enactivist principle. The claim is architectural commentary, not enforced constraint.

5. **`artifact_records.promotion_state` vocabulary** (`ephemeral|durable|trusted`) is not aligned with the `FrontmatterSchema` `review_status` vocabulary (`staged|approved|rejected|auto_promoted`) — v2 §2.3 names this. The two layers represent the same Varelian status (has this artifact passed through the system's self-production loop?) using different words. OPERATIONAL_CLOSURE should be the bridge concept that forces alignment.

---

## 6. Open Questions for Cross-Pillar Synthesis (3–5)

1. **Varela's operational closure vs. Kauffman's autocatalytic closure**: `PILLAR_10_VARELA.md:267–272` says the `catalytic_graph.py` `autocatalytic_cycles()` method finds Kauffman sets that ARE Varela's autopoietic core. The kernel has both `OPERATIONAL_CLOSURE` (Varela) and `AUTOCATALYTIC_CLOSURE` (Kauffman). Are these the same gate evaluated twice, or do they impose distinct constraints on different system layers? Synthesis must decide whether to merge them or specify the layer partition.

2. **Varela's structural coupling and Friston's active inference as the same boundary condition**: `PILLAR_10_VARELA.md:289–298` argues Friston's Markov blanket = Varela's autopoietic boundary, active inference = structural coupling, generative model = system organization. The kernel places `ACTIVE_INFERENCE` and `STRUCTURAL_COUPLING` as sibling axioms in the same group. v3 synthesis must decide: do they compose additively (both enforced independently), or is one a refinement of the other that makes the other redundant?

3. **Natural drift vs. DarwinEngine fitness function**: `PILLAR_10_VARELA.md:226–235` reframes DarwinEngine selection as viability maintenance rather than optimization. But the kernel's `ADJACENT_POSSIBLE` axiom (`dharma_kernel.py:243–252`) mandates `"proposals_per_cycle >= 1"` — an optimization-flavored constraint. Beer's `REQUISITE_VARIETY` (which Varela-via-Santiago would also endorse) mandates diversity. Do natural drift (Varela) and adjacent possible (Kauffman) compose or compete when the DarwinEngine runs selection? Synthesis must specify which takes precedence when fitness pressure and diversity pressure conflict.

4. **The chetana promote pipeline is autopoietic, but promotion rate determines memory health**: From the autopoiesis perspective, if the system fails to promote (fails to produce its organizational components from its own operations), the memory substrate decays toward allopoiesis (external humans defining what's trusted). The chetana decay-revive cycle (`CLAUDE.md §chetana`) is the operational answer to this. But no kernel axiom enforces minimum promote throughput. Should OPERATIONAL_CLOSURE acquire a `structured_predicate` that checks `promotion_state` prevalence — "trusted atoms must constitute >= N% of facts consulted in context compilation"?

5. **The first-person gap in the Triple Mapping**: `PILLAR_10_VARELA.md:339–342` says: "The system has no unified first-person perspective. Each agent has a context (an enacted world), but no agent encompasses the whole swarm." The `TRIPLE_MAPPING` kernel axiom (`dharma_kernel.py:212–221`) requires `"cross_track_claims require evidence from >= 2 measurement domains"` — but says nothing about whether the system itself constitutes a first-person perspective. Varela's neurophenomenology demands a trained first-person report; dharma_swarm's first-person is Dhyana. When the system reports its own state (strange loop, witness logs), is that a first-person source or third-person measurement? Synthesis must classify `StrangeLoop.observe()` outputs within the Triple Mapping framework.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used |
|---|---|---|
| Tier 5 (Read) | `PILLAR_10_VARELA.md` full read | Yes |
| Tier 5 (Read) | `dharma_kernel.py:1–348` (two reads, lines 1–200 and 200–348) | Yes |
| Tier 5 (Read) | `stigmergy.py:1–249` (two reads) | Yes |
| Tier 5 (Read) | `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` sections (four reads, offset-paginated) | Yes |
| Tier 5 (Read) | `v3_pillar_subagent_template.md` | Yes |
| Tier 5 (Read) | `_INDEX.md` (current state) | Yes |
| Tier 1–4 | Memory graph, wiki search, contextplus, gitnexus | Not invoked |

**Tier skip justification**: The task has a precise scope (one pillar, two axioms, three modules). The pillar file itself provides exact file:module citations with enough specificity that semantic search would find the same results via a longer path. The two key modules (stigmergy.py, dharma_kernel.py) are named explicitly in the pillar file and the kernel axiom group header. Grep was not used. All citations are from direct file reads.

---

*Generated: 2026-05-02*

---
Co-Authored-By: Claude Sonnet 4.6 (pillar-10-varela subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: ~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md
