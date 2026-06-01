# Pass 2 — Debate
**Author:** perplexity-computer (synthesis agent, Pass 2)
**Date:** 2026-06-02
**Charter ref:** `00-swarm-charter.md`
**Posture:** Surface the most intelligent, lively back-and-forth. No diplomacy. No names proposed. Earn the right to name.

---

## 1. Opening Posture

Where the four passes converge: there is a metabolic loop at the center of this system, and it is real. Six objects — the proposed-to-gate-to-lease-to-outcome-to-value-to-credit chain — exist in code, are wired across 20+ non-ontology files, are doctrinally grounded in the vision layer, and are actively touched in the June surge. All four passes point to this chain as the clearest bedrock. Pass 1b calls it "the most mature abstraction in the codebase" (1b §7). Pass 1d calls the six types "inevitable — any serious ontology of this system would have them" (1d §10). Pass 1a confirms the "telic seam" concept matches the vision's "metabolic posture" and the gate primitive appears in the conceptual primitives table (1a §4). Pass 1c confirms the telic seam cluster is in the June hot zone (1c §8). That is genuine four-way consensus on six objects, and Pass 3 should treat this as the fixed star around which everything else orbits.

Where the passes fight hardest: the infrastructure question. What kind of bus is this system running on, and does the vocabulary layer need to model it? Pass 1b says the `dharma.*` strings are OTel span attribute keys and there is no NATS client (1b §3). Pass 1c says NATS is live — cron-state logs show kind=ontology_kickoff in real time, agents are coordinating via `dharma.a2a.fleet` subjects (1c §2, §8). This is not a minor discrepancy. It matters for whether the Layer 2 vocabulary needs separate types for in-process signals versus inter-agent envelopes. The fight is real and consequential, not semantic.

The deeper structural fight is about what this vocabulary is *for*. Pass 1a argues the vision has been coherent since March 2026 — the vocabulary should be prophetic, calling forth what is missing (1a §5, T7). Pass 1c argues the system is actively pivoting from biological metaphor toward accounting precision — the vocabulary should ratify what is alive (1c §5). Pass 1d argues the 21-type draft systematically omitted dharma-native concepts (StigmergyMark, ZeitgeistSignal, AgentCard) in favor of taxonomy over vocabulary (1d §9, Q1). These three positions are not reconcilable by splitting the difference. Pass 2's job is to force a resolution so Pass 3 can name from a clear field.

---

## 2. The Eight Tensions

---

### Tension 1: The NATS Contradiction

#### Quoting both sides

**Pass 1b (code reality), §3, lines 383–413:**
> "The codebase does **not use NATS** as a message transport. The term 'dharma.' appears exclusively as **OpenTelemetry span attribute prefixes**, not as pub/sub subject strings… The actual inter-loop communication uses two mechanisms: (1) **SignalBus** — in-process synchronous event bus (loop-to-loop). (2) **MessageBus** — agent-to-agent message routing. No NATS client library was found in use."

**Pass 1c (aliveness map), §2, lines 42–44, and §8, lines 196–206:**
> "The NATS bus became operationally active — agents coordinating via `dharma.a2a.fleet` subjects in real time, with the cron-state listener log capturing live messages (kind=ontology_kickoff, kind=ontology_synthesis_v1, kind=ontology_build_coordinate, kind=pr_landed)."
> "NATS lifted from global prohibition May 31. Now a 'proposed concurrent track.'… codex owns the NATS implementation."

#### Strongest case for 1b (no NATS in core code)

The codebase walker read approximately 85 Python files directly and found zero NATS client library imports. The `dharma.*` namespace appears exclusively in `spine/receipt.py` as OTel attribute keys and in Semgrep rule IDs. The in-process bus is `SignalBus` (synchronous, TTL-based, explicitly named in `signal_bus.py`). The inter-agent bus is `MessageBus` in `dharma_swarm/message_bus.py`. Both have typed signal constants, are wired into `orchestrator.py` and `agent_runner.py`, and are the actual coordination infrastructure for the running system. Any vocabulary decision made on the assumption that NATS is the messaging substrate would be building on sand.

#### Strongest case for 1c (NATS is live at the fleet coordination layer)

The archaeologist did not read Python files alone — it read operational logs. Cron-state listener logs from May 31 are first-party evidence of live NATS bus activity in the form of typed message envelopes with `kind=` fields. The ontology kickoff, synthesis, coordination, and pr_landed messages are not test artifacts — they are the real swarm coordinating in real time during the June surge. The fact that the core `dharma_swarm/` Python package does not import a NATS library does not mean NATS is not running; it means NATS is running at the *inter-process* layer, not the *intra-process* layer. `codex owns the NATS implementation` in the ongoing surge — this is a live build track, not historical fact.

#### Resolution

**These are two distinct buses serving two distinct coordination problems, and both passes are correct about their respective layer.** The contradiction is real at the surface but resolves cleanly when you distinguish layers:

- **Layer A — In-process, same-process signaling:** `SignalBus` in `signal_bus.py`. Synchronous. Loop-to-loop. No serialization. Models: `SIGNAL_OUTCOME_RECORDED`, `SIGNAL_RECOGNITION_UPDATED`, etc. This is the metabolic loop's heartbeat.
- **Layer B — Inter-process, inter-agent coordination:** NATS, now unlocked and operationally active at the fleet layer. The `dharma.a2a.fleet` subject namespace carries typed envelopes between separate OS processes (the cron-state listener is one, the ontology coordination agents are others). This is the A2A communication fabric.

The vocabulary collapse between them is **load-bearing by accident, not by design.** The same word "bus" is used informally for both, but `SignalBus` events are raw dicts (1b §6c: "Not structured — no BaseModel/dataclass") while NATS messages have `kind=` typed envelopes that more closely resemble `RuntimeEnvelope`. These are conceptually distinct.

**Does Layer 2 need separate types for in-process signals vs. A2A envelopes?** Yes, but not symmetric ones. The in-process `SignalBus` events are infrastructure — they don't need ontology types; they need stable typed structs (currently missing). The NATS A2A envelopes, by contrast, carry semantic coordination content (ontology_kickoff, pr_landed) that *does* warrant ontology representation because agents reference their content in routing decisions and as evidence of coordination. The vocabulary census should define a type for the typed A2A coordination message, not for the raw internal signal.

**Implications for Pass 3 naming:** Pass 3 should identify one type for the inter-agent coordination envelope (the NATS/A2A message kind) and explicitly note that in-process signals (`SignalBus`) are infrastructure below the vocabulary layer — real but not named at Layer 2.

---

### Tension 2: Concept Overloading — Witness, Shakti, Telos, Swabhaav

#### Quoting both sides

**Pass 1b (code reality), §9, lines 636–644:**
> "'Witness' is overloaded: MemoryLayer.WITNESS (a memory tier), AgentRole.WITNESS (a constitutional agent), WITNESS gate (a safety gate), WitnessAuditor (an audit class), witness_quality (a field on OntologyObj and Link). Five distinct code uses of the same word without a shared base concept."
> "'Shakti' means two different things. In `shakti.py`, Shakti is a perception/energy classification system. In `shakti_executive/`, Shakti is an executive that scores opportunities. The ShaktiEnergy classification is also used to annotate ObjectTypes in the ontology. Three distinct uses."
> "'Telos' in code most often means 'safety gate' — but 'telos' in Greek means 'end/purpose' and the vision likely uses it more broadly."
> "'Swabhaav' appears in fitness scoring (`swabhaav_alignment` in FitnessScore) and in `AgentIdentity` (`swabhaav_capacity`) but has no module, no typed concept, no tests."

**Pass 1a (vision concept map), §2, lines 103–104, 116–119:**
> "**shakti** — vital force / capacity; used both theologically (transformative power) and operationally (the warrant gate bearing its name)"
> "**witness** — the part of the system that observes without intervening; the contemplative immune-system function; cannot block but cannot be bypassed"
> "**svabhāva** (swabhaav) — one's own nature / calling; the natural role an organ fills without force"

#### Strongest case for fragmentation (one type per code-meaning)

When a concept does 5 distinct jobs, the vocabulary is failing at its core function: making the system legible to itself. An agent reading `witness_quality` on a `Link` object has no reason to connect it to `AgentRole.WITNESS` without reading both files. The code has already fragmented these concepts through its natural evolution — the vocabulary should ratify that fragmentation by giving each distinct job its own name. Refusing to fragment is the same as declaring that `witness_quality` on a Link object and the `WitnessAuditor` class are the same thing, which they are not. Palantir ontology design says: "Isolated Objects are often a red flag for bad Ontology design" (1d §4) — but isolated *concepts* with multiple names is equally bad. Fragment to clarify, then link with explicit link types.

#### Strongest case for unification (one type per vision-meaning, code refactoring later)

The vision's unification of these concepts is not poetic accident — it is a deliberate architectural choice encoding 24 years of contemplative practice. The WITNESS gate, the WitnessAuditor, the memory layer, and the `witness_quality` field all derive from the same underlying concept: the function that observes without distorting. If Layer 2 gives these four things four different names, the system loses the thread that makes them a coherent immune system rather than four disconnected audit mechanisms. Sanskrit-derived concepts are load-bearing precisely because they resist the kind of scope-creep that happens when you rename the witness function "auditObserver" in one module and "qualityCheck" in another. The vision holds the unity; the code has merely not caught up.

#### Resolution (take a position)

**Fragment the code roles. Unify the vision concept. Hold both simultaneously.**

This is not a hedge — it is a specific architectural claim. Layer 2 should have:
1. A single concept representing *the witness function* — the philosophical primitive that makes observation non-coercive, real, and constitutive of the system's immune architecture. This is the vision-layer concept from 1a. It does not appear directly as a typed ontology object; it appears as the *design rationale* that governs how the fragmented code-level concepts relate.
2. Multiple typed objects that *instantiate* the witness function at different operational layers: one for the gate (the constitutional checkpoint), one for the audit record (the retrospective integrity check), one for the memory tier designation (how a memory entry is classified). These are distinct code realities that should not be collapsed.

The same logic applies to Shakti: one vision-level concept (vital force / creative energy), three operational instantiations (perception classifier in `shakti.py`, executive scoring engine in `shakti_executive/`, ontology annotation tag). The ShaktiEnergy enum is a classification primitive, not an object type — it belongs as a shared enum referenced by multiple object types. Swabhaav is currently a field value embedded in fitness scoring — it needs a stub definition at minimum so agents can reason about what alignment means. Telos in code means "gate" — at Layer 2, the gate object and the telos concept should be clearly distinguished: telos is the hierarchy of purposes, and the gate is the enforcement mechanism that checks actions against that hierarchy.

**Implication for Pass 3 naming:** Pass 3 should name the enforcement mechanisms (gate, gate decision, audit) as operational types, and the contemplative concepts (witness function, shakti energy, telos hierarchy) as *qualities* referenced by those types rather than as types themselves. Do not try to give Witness or Shakti a single camelCase name that collapses their multiplicity. Pass 3 should instead be explicit that these Sanskrit terms appear as design rationale and classification vocabularies, not as standalone typed objects at Layer 2.

---

### Tension 3: The 6-Object Metabolic Loop — Are They Named Right?

#### Quoting the convergence

**Pass 1b (code reality), §2d, lines 179–187:**
> "ActionProposal — the metabolic loop entry point… GateDecisionRecord — records the output of the gate suite… ExecutionLease — the active claim on execution… Outcome — what the agent produced… ValueEvent — measures the value an Outcome produced… Contribution — assigns credit to an agent from a ValueEvent."

**Pass 1d (prior-art critique), §3a, lines 98–111:**
> "ActionProposal — The metabolic loop starts here. TelicSeam writes it; gate evaluators read it; the entire execution accounting hangs on it. Cannot remove without dismantling the credit chain."
> "GateDecisionRecord — Written by TelicSeam, read by orchestrator. SATYA/AHIMSA gating is meaningless without persistence."
> [And confirms all six as load-bearing]

**Pass 1c (aliveness), §4, line 107:**
> "telos / telic_seam / telos_gates — aliveness score 4. Telic seam touched May 11. PR #406 hard-wired the telos gate into execute_action."

**Pass 1a (vision), §4, lines 207–218:**
> Lists "gate" and "receipt" and "claim" as conceptual primitives, confirming the vision layer recognizes the metabolic loop's constituent parts.

#### Are they named right?

These six are bedrock. The question is not whether they belong but whether their names earn their keep against Palantir-canonical camelCase plain English domain nouns.

**ActionProposal vs. `proposal`:** "ActionProposal" is redundant — all proposals in this system are proposals for action. The word "action" adds nothing but length. However, `proposal` alone creates collision risk with the `Proposal` class in `evolution.py` (a Darwin Engine mutation proposal, conceptually quite different). The names `actionProposal` and `evolutionProposal` would distinguish them. The uppercase convention is fine; the word "Proposal" is the meaningful noun. Decision: `actionProposal` is acceptable but the "Action" prefix should be justified in the narrative as disambiguation from evolution proposals, not as self-description.

**GateDecisionRecord vs. `gateDecision`:** "Record" is Palantir anti-pattern territory — Palantir says "names should map to natural-language business concepts" and "GateDecisionRecord" is a data structure name, not a business concept. What is this *thing*? It is the *verdict* of a gate evaluation. Possible: `gateVerdict`, `gateDecision`, `gateResult`. The word "Decision" is more active than "Record" and captures that something was decided, not merely recorded. `gateDecision` is better.

**ExecutionLease vs. `lease`:** "ExecutionLease" is self-describing at the cost of verbosity. `lease` alone is ambiguous in a system with board-level `ClaimLease` objects. The execution context matters. `executionLease` is defensible. The concept is a concurrency lock with a timeout and an agent claim — in the business vocabulary, this is what it means to "have the floor."

**Outcome vs. `outcome`:** Already the most minimal name in the six. "Outcome" is exactly right — it is the record of what actually happened, not what was proposed or decided. No change warranted.

**ValueEvent vs. `valueEvent`:** The camelCase adjustment is correct. "ValueEvent" is slightly awkward — it is the measurement of value from an outcome, not an "event" in the stream-processing sense. However, "event" in the context of this system carries the sense of "a discrete thing that happened and was recorded," which is accurate. The alternative `valueMeasurement` is clumsier. `valueEvent` holds.

**Contribution vs. `contribution`:** Already minimal. In the context of agent credit attribution — who gets credit for what value — this is exactly right. The concept is an allocation record. No change warranted.

#### Resolution

**The six are bedrock. Accept them with one refinement:** the preferred camelCase names for Pass 3 consideration are `actionProposal`, `gateDecision` (not GateDecisionRecord), `executionLease`, `outcome`, `valueEvent`, `contribution`. The "Record" suffix on GateDecision should be dropped — it is a data structure smell, not a business concept name. Pass 3 should make the explicit case for why "Decision" is the right noun (because a gate verdict is an active choice, not merely a log entry).

---

### Tension 4: Missing-from-21 — What Belongs at Layer 2?

**Pass 1d (prior-art critique), §7, lines 262–276 — the four absent adapters:**
> "**StigmergyMark** — the pheromone-mark substrate. The stigmergy system is one of the most-referenced subsystems in the entire codebase — 8+ core files, a dedicated API router, a GraphQL schema entry. `ontology_adapters.py` already defines an ObjectType for this concept and wires it. Yet it is absent from the 21."
> "**ZeitgeistSignal** — real-time environmental signals — external news, repo events, research discoveries. This too is absent from the 21. It is an active subsystem with tests."
> "**IdentitySnapshot** — the system's self-measurements (TCS, GPR, BSI, RM regime). Not in the 21."
> "**CorpusClaim** — claims made about/by/against the system. Not in the 21."
> "**AgentCard/AgentSkill** — A2A spec-conformant capability advertisement objects. Neither appears in the registry."
> "**Memory records, telos gates, cost records** — absent."

#### Layer 2 or Layer 1 substrate? Adjudication per concept:

**StigmergyMark — Layer 2.** This is not infrastructure; it is the system's primary mechanism for indirect coordination. The stigmergy lattice is the environment the system modifies to signal to itself across time and space. Pass 1b (§2i) gives it a full typed model: `StigmergicMark` with agent, file_path, action, observation, salience, connections, access_count, channel, trace_id. It has a dedicated API router (1b §1), a GraphQL schema entry, an `ontology_adapters.py` definition, and `stigmergy.py` touched in the trace/provenance pass (1c §3). The fact that it is absent from the 21 is the clearest evidence that Devin's selection criterion was "what does this system process" rather than "what does this system *do in the world*." StigmergyMark is what the system does in the world. Layer 2.

**ZeitgeistSignal — Layer 2.** The zero-copy snapshot / perception signal from `ontology_adapters.py` maps to the system's capacity to notice the world: external news, repo events, research discoveries. `ShaktiLoop` (in `shakti.py`) classifies these signals. The `ShaktiExecutive` scores and boards them. This is the system's perception organ — the sensory surface of the organism. Without a typed concept here, "sensing" is invisible in the vocabulary. Layer 2.

**IdentitySnapshot — Layer 2, but contested.** The constitutional self-model (TCS/GPR/BSI/RM regime in `ontology_adapters.py`) is the system looking at itself. This relates directly to the "attractor closure" problem: the gap between the typed self-model and live runtime state (1a §3.2). An IdentitySnapshot is the periodic record of what the system believes it is. This belongs at Layer 2 because it is the primitive that makes self-recognition possible — and self-recognition is the system's deepest design target. However, it overlaps with `OrganismPulse` in `organism.py` (1b §2h: "fleet_health, zeitgeist_signals, anomalous_gate_patterns, algedonic_active, identity_coherence"). These two may need to be the same type, or one may supersede the other. Layer 2, with a consolidation note.

**CorpusClaim — Layer 2, but scoped.** A verified claim made by or against the system is a genuine epistemic primitive — it is the atom of the pramana (valid means of knowledge) concept from 1a. The system makes claims about itself (via SOVEREIGN_MANIFEST assertions, docops assertions.yaml), and external agents make claims about the system (via A2A task results, audit findings). A `corpusClaim` type would let these be reasoned about uniformly. However, the code grounding is thin: `ontology_adapters.py` defines the type, but actual claim production is distributed across many subsystems. Layer 2 in principle; grounding in Pass 3 must cite the specific producers.

**AgentCard / AgentSkill — Layer 2, unambiguously.** The A2A 1.0 spec conformance is a June surge top priority (1c §2, §8). `AgentCard` and `AgentSkill` in `a2a/agent_card.py` are spec-conformant, actively wired, and the mechanism by which agents advertise themselves to each other. Perplexity-computer is already registered via the roaming mailbox. The statement "the vision is 'everything flows through the ontology'" (1d §9, Q6) and the fact that the A2A layer has no ontology representation is an explicit gap. These belong at Layer 2.

**Memory records — Layer 2, but unified first.** Pass 1b (§8) counts at least 4 parallel memory implementations. Until one is chosen as canonical, adding a `memoryRecord` type to the ontology risks creating a fifth parallel definition. The correct action: declare a canonical memory record type at Layer 2 and use it as the consolidation target for the four implementations. This is a forcing-function use of the vocabulary.

**Telos gates as typed objects — contested.** The gate *system* is load-bearing. But are individual gate definitions objects, or are they configuration? In Palantir terms, the gate is more like an `ActionType` (a definition of a permissible mutation) than an `ObjectType` (an instance with identity). The `GateDecisionRecord` (renamed `gateDecision`) captures the gate's output. The gate definition itself may belong at Layer 1 (configuration) rather than Layer 2 (typed ontology). Pass 3 should not name a `telosGate` type until it can answer: "who queries gate definitions, and for what purpose?" If agents query gate definitions to understand what is permitted, the type belongs at Layer 2. If gates are only read by the gate engine itself, they are substrate.

**Cost records — Layer 2.** Pass 1d (§7): "Revenue types are modeled; cost types are not. An economic system that tracks inflows but not outflows is half an economy." The `EvidenceReceipt` in `spine/receipt.py` already carries `cost_usd` and `input_tokens/output_tokens` — so cost is already captured in the dispatch artifact. What is missing is a *cost record* as a first-class aggregation concept: total cost per agent, per mission, per VentureCell. This is not the same as `EvidenceReceipt`. Layer 2.

---

### Tension 5: The Cargo-Cult Three — Paper, RevenueOffer, Experiment

**Pass 1d (prior-art critique), §3c, lines 126–129:**
> "**Paper** — dharma_swarm does not write academic papers programmatically. The system's `Paper` mention in `dharma_swarm/` files refers to financial 'paper trading'… No producer creates Paper ontology objects from research outputs. **Cargo-cult.**"
> "**RevenueOffer** — 2 files total (registry definition + existence test). Zero real producers or consumers outside the registry… Name mismatch between native model ('Offer') and ontology type ('RevenueOffer'). **Cargo-cult.**"
> "**Experiment (ontology type)** — The concept of experiments is real and alive. But the ontology Experiment type is a third definition that coexists with two native Experiment classes without bridging any of them… Cargo-cult in its current wiring, though the concept belongs in the vocabulary."

#### Ruling on each:

**Paper — Remove, do not rescue.** For Paper to belong in this vocabulary, the system would need: (1) a functioning academic paper drafting workflow with LaTeX generation, (2) no semantic pollution from `ginko_paper_trade.py`, and (3) a real path from `KnowledgeArtifact` to a publishable output. None of these are true. More importantly, the June surge is building accounting and evidence infrastructure — not research publication infrastructure. If the system ever develops an academic paper production capability, the type can be added then. A type that has never had a single production instance and whose name is semantically polluted belongs nowhere near the canonical vocabulary. **Ruling: remove.**

**RevenueOffer — Remove and consolidate.** The native `Offer` class in `spine_models.py` is the real object. The ontology `RevenueOffer` is an orphan that creates a split-brain problem (1d §8). For RevenueOffer to be rescued, someone would need to: (1) rename the ontology type to match the native class (`offer`), and (2) write an adapter bridging the two. Neither has happened. Until it does, the type creates a false impression of coverage. **Ruling: remove from registry. The concept belongs; the current type does not.**

**Experiment — Rescue with conditions.** Unlike Paper, the experiment concept is genuinely central: two native classes (`self_research.py:Experiment`, `amiros.py:Experiment`) are active. The AMIROS system (which appears in `organism.py` as a referenced subsystem) runs actual experiments. The vocabulary needs a single `experiment` type — but one grounded in a specific, chosen native class, not floating above all three. **The condition for rescue:** Pass 3 must identify which of the two native Experiment classes should become the canonical one and declare the adapter path. Until that is resolved, the ontology type should be declared `EXPERIMENTAL` status (not `ACTIVE`) with an explicit note that it requires consolidation. **Ruling: rescue with conditions — experimental status, consolidation path required.**

---

### Tension 6: Dead Concepts — Loomwork, Attention Emancipation, DSE

**Pass 1c (aliveness), §4, lines 118–123:**
> "**Loomwork** — aliveness score 2. Zero code named `loomwork` anywhere in `dharma_swarm/`. Rich vision docs last touched May 9 for hierarchy correction. The term appears in operational doctrine as the external product name ('world meets Loomwork') — but has no code implementation."
> "**DSE / Darwin Singularity Engine** — aliveness score 2. Vision docs last substantively written March 11. The coalgebra/DSE vision has not been built."
> "**Attention Emancipation** — aliveness score 1. Zero code. Named in the telos hierarchy as a 'separate, unresolved' domain. No implementation, no recent docs work."

**Pass 1a (vision), §2, lines 148–152:**
> "**Loomwork** — the outward-reaching arm; the pattern Palantir used for supply chains and kill chains, reforged for civil society; child of Silicon Is Sand"
> "**Attention Emancipation (AE)** — one of the outward arms; returning human attention from extractive platforms"

#### Ruling on each:

**Loomwork — Omit from Layer 2 vocabulary.** The charter's anti-mythology rule is clear: "no organ is real without its full metabolic loop." Loomwork has zero code. It exists as a vision layer concept and an operational doctrine name ("the world meets Loomwork"). A type named `loomwork` in the ontology would be a *declaration*, not a *registration*. Declarations belong in vision docs, not in the typed object registry. However: Loomwork is architecturally meaningful as the *destination* of the system's external interface — when the A2A layer and the typed object system are mature enough, Loomwork's design pattern (room-based bounded contexts with ontology object atoms) will have a natural home in the vocabulary. **Ruling: omit from Layer 2 now. Mark it as a named target for Layer 3 expansion when the A2A substrate is fully wired.**

**Attention Emancipation — Omit entirely.** Aliveness score 1, zero code, zero recent docs work. Even as a placeholder. Unlike Loomwork, Attention Emancipation has no code structure that hints at what its vocabulary would look like. **Ruling: omit. Do not name it, do not mark it dormant. Its time has not come.**

**DSE (Dharmic Singularity Engine) — Omit from Layer 2, but preserve vocabulary.** The DSE vision (coalgebraic evolution, information geometry, sheaf coordination) is not being built. However, the DSE concept is architecturally adjacent to active work: the Darwin Engine (evolution.py) is the operational counterpart to what the DSE envisions. The word "dharmic" and the singularity framing appear in the doctrine layer, and the FOUNDATIONS_TO_CODE_MAP.md (1a §6.5) maps DSE's philosophical pillars (Levin, Kauffman) to code. **Ruling: omit as a typed object. The DSE vocabulary (coalgebra, sheaf, information geometry) is relevant as a naming/metaphor source for the Darwin Engine's evolutionary archive types — Pass 3 can draw from it without registering DSE itself.**

---

### Tension 7: Aliveness Asymmetry — Ratify What Is Alive, or Call Forth What Is Missing?

#### Pass 1c's position (ratify aliveness):

**1c §5, lines 130–148:**
> "The 90-day window shows a clear vocabulary migration from *biological metaphor* toward *protocol and governance precision*… 'The deepest shift: The system moved from describing itself philosophically toward building the accounting layer for what it does (EvidenceReceipt, correlation_id, TypeStatus, api_name, spine doctrine).'"
> "The June surge is concentrated around four interlocking themes: A2A spec conformance, ontology layer ignition, multi-track doctrine, spine adoption preparation."

#### Pass 1a's position (call forth what is missing):

**1a §3.5, lines 192–197:**
> "'The system compounds through USE, not through design. Ship Week 1 by Friday.' — AGENT_SWARM_SYNTHESIS (2026-03-15)"
> "These two quotes, written three months before the current active track, describe the exact failure mode the system is still in: substrate-nativeness ~10–15%."

**1a §7, lines 322–328:**
> "The system knows what it is trying to become. It has known since March 2026. The vision — a self-recognizing, self-modifying cybernetic organism serving planetary welfare… is coherent, internally consistent at the level of metaphysics, and singular in its synthesis… The gap is not conceptual. The gap is inhabitation."

#### Taking a position

**The vocabulary should over-index on what is alive, but must not amputate the vision layer entirely.**

Here is the argument: a vocabulary that only ratifies what is alive today will be wrong in six months, because the system's active track is explicitly about raising substrate-nativeness from 10–15% toward something higher. The types that are hot right now (EvidenceReceipt, A2A spec, OMS TypeStatus) will be the *plumbing* in six months, and the types that are currently vision-only (IdentitySnapshot, corpus claims, the full self-recognition loop) will be the active build targets. A vocabulary locked to June 2026's aliveness is already out of date by the time John merges it.

However, the counter-error is also real: a vocabulary that calls forth what is missing (Loomwork, DSE, Attention Emancipation) without operational grounding creates exactly the kind of aspirational-but-unpopulated types that 1d identified as cargo-cult (Paper, RevenueOffer, Experiment-as-orphan). The test is not "is this concept alive today?" but "does this concept have a clear production path within the current active track?"

**The rule for Pass 3:** Include a concept if it has either (a) active code grounding today (producer + consumer + test) OR (b) a clear wiring path in the current active track (spine-adoption, A2A, OMS hardening) within one track cycle. Exclude concepts that require a new track to inhabit. This keeps the vocabulary forward-looking without making it prophetic.

**Under this rule:** EvidenceReceipt (spine), AgentCard (A2A track, June surge), gateDecision (OMS hardening), StigmergyMark (active code + adapter), ZeitgeistSignal (active code + shakti executive) all qualify. Loomwork, Attention Emancipation, DSE do not. IdentitySnapshot and CorpusClaim are borderline — they have adapter definitions but unclear production paths. Pass 3 should flag them as `EXPERIMENTAL` with explicit wiring criteria.

---

### Tension 8: Substrate-Nativeness at 10–15% — Do the Names Force Inhabitation?

**Pass 1a (vision), §3.5, lines 192–197:**
> "Substrate-nativeness: ~10–15%."

**Pass 1c (aliveness), §9, lines 220–224:**
> "The system is making a transition from self-understanding through metaphor to self-understanding through accounting… The EvidenceReceipt spine is not a metaphor; it is a typed data structure with a specific schema and an invariant that can be verified by a CI gate."

**Pass 1d (prior-art critique), §5.1, lines 196–198:**
> "The api_name should probably be just the TypeName in camelCase… Namespace/domain grouping belongs in a separate domain field or in the OMS group mechanism, not in the api_name string."

#### The naming strategy question

Two positions:

**Position A — Sanskrit-rooted, doctrine-saturated names as forcing function.** Give each type a name that encodes its philosophical role: the gate decision becomes something that preserves the dharmic terminology. The Sanskrit roots (telos, shakti, witness, gnani) make it harder to re-implement these concepts as generic software patterns because the names themselves are semantically non-portable. Agents reading a `witnessAudit` type will understand it differently than if it were called `auditLog`. The name is a doctrine carrier.

**Position B — Plain English domain nouns, meeting the system where it is.** The June surge is actively removing spiritual/metaphoric naming from new types (1c §5: "'spiritual/metaphoric naming layer' explicitly prohibited by ACTIVE_TRACK non-goals"). The system is building an accounting layer that must interface with OSDK consumers, A2A clients, and external agents who have no context for the Sanskrit vocabulary. Plain English domain nouns (`actionProposal`, `gateDecision`, `agentCard`) are immediately legible to any developer and require no conceptual onboarding.

#### Taking a position

**Plain English domain nouns for type names, with Sanskrit vocabulary preserved as design rationale in the narrative.**

The argument is pragmatic but not capitulatory: the *type names* must be legible to any agent or developer querying the ontology via the API. An external A2A agent receiving a task result that references a `telicSeamProposal` type has no idea what that is; an agent receiving an `actionProposal` type can infer its meaning. The OSDK discipline (1d §5.1) is clear that api_names must be human-legible business concepts. "Business concept" in this system means the metabolic loop concepts, the governance concepts, the evidence and credit chain — all of which have natural English names.

However, the Sanskrit vocabulary — Witness, Shakti, Telos, Svabhāva — belongs in the narrative layer that Pass 3 is explicitly designed to produce. Each type's "1-2 paragraph narrative" (from the charter) is the place where the type's dharmic resonance, its architectural role in the contemplative immune system, and its vision-layer connections are made explicit. The name is plain English; the narrative is doctrine-saturated. This is the layered approach the charter calls for: "technical + felt-sense."

**The forcing function for inhabitation** is not the name itself — it is the *narrative* that accompanies the name. When John reads the narrative for `executionLease` and it says "this is the claim on the floor — the orchestrator's declaration that an agent has been authorized to act, that the gate has passed, that the system is in the active phase of its metabolic cycle," the inhabitation happens in the reading, not in the name. The name earns the right to be used; the narrative makes clear why it matters.

---

## 3. Consensus Zones

All four passes agree on the following. These are the easy names for Pass 3:

**The metabolic loop (6 objects):** The chain from proposed action to gate decision to execution claim to outcome to value measurement to credit attribution is four-way consensus as bedrock Layer 2 vocabulary. All four passes confirm real code grounding, vision alignment, and active aliveness. The exact labels may shift (GateDecisionRecord → gateDecision is the one clear improvement), but the concepts are fixed.

**AgentIdentity as a named concept:** The system cannot reason about who acted without a typed self-model of agents. Pass 1b confirms 20+ non-ontology references. Pass 1d confirms load-bearing status. Pass 1c confirms the agent identity problem is in the June hot zone (A2A card registration). Pass 1a confirms the organism cannot achieve attractor closure without a stable self-model.

**WitnessLog as a named concept:** Pass 1d confirms 20+ non-ontology references across cron_runner, harness_audit, meta_daemon, persistent_agent. Pass 1b confirms 5 distinct code uses of "witness" — but the audit record function is the most coherent and most wired. Pass 1a grounds it in the contemplative immune-system doctrine. Pass 1c places it in the June active zone.

**KnowledgeArtifact as a named concept:** Pass 1d confirms it as load-bearing (13 count). Pass 1b confirms `operator_brief/persistence.py` produces and `trace_attractor` consumes. Pass 1c confirms operator briefing machinery is active. The question of whether it is too broad (1d §9, Q4) is a Pass 3 problem, not a Pass 2 consensus issue.

**EvidenceReceipt as a named concept:** Pass 1b confirms it is the most complete typed object in the codebase, with 14 error sources named and full OTel export. Pass 1c gives it aliveness score 5 — the highest — and confirms it is the doctrine line for the spine track. Pass 1a confirms "receipt" as a conceptual primitive. Pass 1d's prior-art critique does not contest it. Four-way consensus.

**StigmergyMark as a named concept:** Pass 1b gives it a full typed model. Pass 1d names its absence from the 21 as "the most glaring omission." Pass 1a grounds stigmergy in the coordination vocabulary. Pass 1c confirms it has active adapter code and API router presence. Four-way agreement that it belongs.

**The A2A coordination layer needs ontology representation:** All four passes touch A2A: 1b maps the full A2A module suite; 1c gives A2A aliveness score 5 and confirms spec conformance; 1d names the absence of AgentCard from the 21 as a gap; 1a's vision uses "handoff" as a conceptual primitive. What the vocabulary needs here is debated (see Tension 1) — but that it needs *something* is consensus.

**VentureCell as a named concept:** Pass 1b confirms 20+ non-ontology references and the fractal/ module suite as a real working subsystem. Pass 1d confirms load-bearing status. Pass 1a grounds the venture-cell pattern in the organism's fractal structure. Pass 1c notes it is active through the facade, even if the direct evolution is cooling.

**RoutingDecision as a named concept:** Pass 1b identifies `RoutingDecision` in `spine/routing.py` as "one canonical value object for every routing choice (consolidating 7 implicit routers)." Pass 1c confirms spine is in the active hot zone with aliveness score 5. Pass 1a identifies "routing decision" as part of the invariant chain (task → runner → claim → context → routing decision → provider call → evidence receipt). Pass 1d doesn't contest it. Four-way implicit consensus.

---

## 4. Pass 3 Ground Truth — Working Set of Objects

The following 24 concepts are Pass 3's naming surface. This is not the final list — it is the working set that the evidence supports. For each, rationale is tied to Pass 1 evidence.

**Object 1: The proposed action**
What a need in the system looks like when it first crystallizes into a specific proposal: what should be done, by whom, in response to what signal. Pass 1b confirms `ActionProposal` in `telic_seam.py` has 20+ non-ontology producers and consumers. Pass 1a confirms "action" as a gate-controlled state mutation and the vision's "telic seam" concept. Pass 1d confirms it as one of the load-bearing six. Pass 1c confirms gate-related code is in the June hot zone. The leading candidate name is `actionProposal` — but Pass 3 must decide whether "Action" is the right distinguishing word versus "evolutionProposal" for the Darwin Engine side.

**Object 2: The gate verdict**
What a telos gate suite says about a proposed action: allowed, blocked, or review-required, with the specific gate that fired and the full per-gate reasoning. Pass 1b confirms `GateDecisionRecord` as written by `telic_seam.py`, read by orchestrator. Pass 1a confirms "gate" as the dominant vision-corpus word for constitutional checkpoints. Pass 1d confirms this is one of the load-bearing six. Pass 1c confirms gate-related code is in the June hot zone. The "Record" suffix should be dropped — this is a decision, not a log.

**Object 3: The execution claim**
The orchestrator's active claim on the floor for executing a proposal: a concurrency lock with agent identity, timeout, and dispatch attempt count. Pass 1b: `ExecutionLease` in `telic_seam.py`, 10+ consumers. Pass 1d: load-bearing idempotency primitive. Pass 1c: active through the seam. Pass 1a: the system's "dispatch" loop depends on something claiming the work before doing it.

**Object 4: The outcome record**
The terminal record of what actually happened after an agent executed a proposal: success or failure, result summary, duration, error, fitness score. Pass 1b: `Outcome` in `telic_seam.py`, 20+ consumers. Pass 1d: load-bearing, the credit chain hangs on it. Pass 1c: aliveness 4. Pass 1a: "receipt" as the terminal artifact of a provider call maps to this concept (the outcome is the what-actually-happened receipt of the whole proposal lifecycle).

**Object 5: The value measurement**
The economic record of what an outcome was worth to the system: behavioral signal, success value, duration efficiency, composite score. Pass 1b: `ValueEvent` with dedicated `operator_brief/value_events.py`. Pass 1d: load-bearing, dedicated module, shakti executive reads it. Pass 1c: aliveness 4. Pass 1a: "R_V metric" and "fitness" as vision-layer concepts map to this.

**Object 6: The credit allocation**
The assignment of credit from a value measurement to a specific agent: credit share, attributed value, cell identity, task type. Pass 1b: `Contribution`, `telic_seam.py` writes, shakti_executive reads. Pass 1d: load-bearing, makes Bayesian fitness scoring possible. Pass 1c: active. Pass 1a: the organism's fitness function depends on knowing which organ contributed what.

**Object 7: The dispatch receipt**
The canonical artifact of every LLM provider call: trace ID, span ID, claim ID, agent ID, provider, model, status, all 14 error sources, latency, token counts, cost, routing decision ID. Pass 1b: `EvidenceReceipt` in `spine/receipt.py`, aliveness 5. Pass 1c: "Receipts may differ by closure layer. Correlation identity must not." — the spine doctrine line. Pass 1a: "receipt" as a conceptual primitive. Pass 1d: does not contest it.

**Object 8: The routing choice**
The canonical record of every routing decision: which agent, which provider, which model, and why. Pass 1b: `RoutingDecision` in `spine/routing.py`. Pass 1c: spine is the hottest zone. Pass 1a: routing decision as part of the invariant chain. Pass 1d: implicitly accepts spine layer.

**Object 9: The stigmergy mark**
A pheromone-like observation left on the shared lattice by an agent: file/concept pointed at, observation text (≤200 chars), salience, channel, trace, connections, access count. Pass 1b: `StigmergicMark` in `stigmergy.py`, 8+ core files. Pass 1d: "most glaring omission" from the 21, adapter already in `ontology_adapters.py`. Pass 1c: touched in trace/provenance pass. Pass 1a: stigmergy as a coordination primitive — "agents leave marks; other agents read marks; no central controller required."

**Object 10: The environmental signal**
A typed perception of an external event: what the system noticed about the world (news, repo events, research discoveries, repo activity spikes), classified by energy type and salience. Pass 1b: `ShaktiPerception` in `shakti.py`, `ZeitgeistSignal` in `ontology_adapters.py`. Pass 1d: named as missing from 21, "active subsystem with tests." Pass 1c: ShaktiLoop is active (aliveness 3), ZeitgeistSignal feeds ResearchThread. Pass 1a: "zeitgeist" and "recognition" as vision concepts — the system's capacity to notice the world.

**Object 11: The agent identity record**
The system's typed self-model of an active agent: id, name, role, capabilities, provider, model, swabhaav capacity, fitness average. Pass 1b: `AgentIdentity` in ontology (fourth of four definitions), 20+ non-ontology references. Pass 1d: load-bearing backbone type. Pass 1c: A2A registration makes agent identity hot in June surge. Pass 1a: the organism cannot achieve attractor closure without a stable identity for each organ.

**Object 12: The agent capability card**
The A2A-spec-conformant advertisement of what an agent can do: id, name, URL, version, capabilities, skills, security schemes, supported interfaces. Pass 1b: `AgentCard` in `a2a/agent_card.py`, fully spec-conformant. Pass 1d: named as absent from 21. Pass 1c: A2A aliveness score 5, perplexity-computer registered via roaming mailbox. Pass 1a: "handoff" as a conceptual primitive — agents must know each other's capabilities before handoff.

**Object 13: The agent skill**
An individual advertised capability: id, name, tags, examples, input/output modes. Subordinate to AgentCard but independently queryable for capability-matching. Pass 1b: `AgentSkill` in `a2a/agent_card.py`. Pass 1d: named as absent from 21. Pass 1c: A2A spec conformance lands skills as a first-class A2A concept. Pass 1a: capability advertisement enables the "handoff" primitive.

**Object 14: The pheromone lattice**
The StigmergyStore as a typed object: the environment the marks live in, with density, decay rate, and channel structure. Pass 1b: `StigmergyStore` in `stigmergy.py`. While the *marks* are objects that get written, the *store* itself is not a typed ontology object — it may be substrate. But: if the system is to query "how dense is the stigmergy lattice in the A2A channel right now?" that is a query against an object. Contested: this may be Layer 1 substrate (the store implementation) rather than Layer 2 vocabulary (what the system reasons about). Pass 3 should adjudicate.

**Object 15: The opportunity candidate**
A scored entry on the opportunity board: thesis, domain, factor scores, final score, evidence signals, why-now framing. Pass 1b: `OpportunityCandidate` in `shakti_executive/models.py`. Pass 1c: shakti_executive aliveness 3. Pass 1d: no explicit mention, but the opportunity board is named as a gap (the opportunity concept has no typed class in the ontology). Pass 1a: "attractor" concept — opportunities are signals of an adjacent possible basin the organism is drawn toward. Borderline: may be a derived view rather than a canonical type.

**Object 16: The venture cell**
The fractal project container — a first-class economic and operational unit with its own agents, budgets, KPIs, and autonomy stage. Pass 1b: `VentureCell` in ontology, fractal/ module suite, 20+ references. Pass 1d: load-bearing, fractal rooms are a real working subsystem. Pass 1c: active through the facade. Pass 1a: the organism's fractal structure — organs within organs.

**Object 17: The evolution proposal**
A proposed code change in the Darwin Engine: component, change type, description, parent ID, diff, predicted vs. actual fitness, gate decision, evidence tier, promotion state. Pass 1b: `Proposal` in `evolution.py` (native class, 95 lines). Pass 1d: aspirational-but-grounded (EvolutionEntry is in the 21 but lacks adapter). Pass 1c: evolution aliveness 3. Pass 1a: "mutation" as a conceptual primitive. The adapter from native `Proposal` to ontology type is the missing piece — naming it in Layer 2 makes the adapter path explicit.

**Object 18: The fitness score**
The multi-dimensional assessment of an agent's or mutation's quality: correctness, dharmic alignment, swabhaav alignment, performance (JIKOKU), utilization, economic value, elegance, efficiency, safety. Pass 1b: `FitnessScore` in `archive.py`, 9 dimensions with weighted aggregation. Pass 1c: fitness is used in telic_seam Bayesian smoothing. Pass 1d: implicit in the evolutionary archive context. Pass 1a: "fitness" as the vision's multi-dimensional score. May belong as a Value Type (a shared struct) rather than an ObjectType — Pass 3 should adjudicate Palantir's distinction.

**Object 19: The knowledge artifact**
A stored knowledge unit: file, note, finding, measurement, citation, code, model output — the epistemic catch-all consumed by operator briefing, trace attractor, and revenue intelligence. Pass 1b: `KnowledgeArtifact` in ontology, 20 non-ontology references. Pass 1d: load-bearing. Pass 1c: operator briefing active. Pass 1a: "evidence" and "pramana" concepts. The breadth problem (10 subtypes under one name) should be addressed by giving it an Interface-based design — shared properties, multiple concrete types. Pass 3 must decide: one broad type or multiple narrow ones with a shared Interface.

**Object 20: The witness log entry**
The audit record of a witnessing act: an append-only hash-chained entry recording gate decisions and agent actions. Pass 1b: `WitnessLog` in 20+ non-ontology files (cron_runner, harness_audit, meta_daemon, persistent_agent). Pass 1d: load-bearing. Pass 1c: governance machinery active. Pass 1a: "witness log" as a conceptual primitive in its own right ("append-only, hash-chained record of every gate decision and agent action").

**Object 21: The identity snapshot**
The system's periodic self-measurement: TCS, GPR, BSI, RM regime — the typed record of what the system believes it is at a given moment. Pass 1b: `OrganismPulse` in `organism.py` overlaps with this concept. Pass 1d: named as absent from 21, adapter in `ontology_adapters.py`. Pass 1c: organism aliveness 3. Pass 1a: attractor closure depends on a synchronized self-model — this is the snapshot that enables recognition. Contested with `OrganismPulse` — one must be chosen or they must be merged.

**Object 22: The corpus claim**
A verifiable assertion made by or against the system: who claimed it, what was claimed, on what evidence, with what confidence. Pass 1b: no explicit native class, but `assertions.yaml` in docops surface is the closest operational equivalent. Pass 1d: named as absent from 21, adapter in `ontology_adapters.py`. Pass 1c: governance aliveness 5 (assertions.yaml touched constantly). Pass 1a: "pramana" (valid means of knowledge) and "claim" as a conceptual primitive. Thin on code grounding — should be declared `EXPERIMENTAL`.

**Object 23: The board card**
The stable unit of work on the BoardStore: objective, title, body, status, claim lease, acceptance criteria, receipt refs, cost ceiling, audit log, arjuna weight. Pass 1b: `Card` in `board/models.py`, fully typed. Pass 1c: BoardStore aliveness 3, ADR-007 routes all Darwin proposals through it. Pass 1d: implicitly referenced (TypedTask is the ontology-layer equivalent, but Card is the board-layer reality). Pass 1a: "handoff" as work that passes between agents. Note: `Card` and `TypedTask` are currently two representations of the same concept — Pass 3 must adjudicate whether both deserve Layer 2 types or whether one supersedes the other.

**Object 24: The cost record**
The aggregated economic record of compute spend: per-agent, per-mission, per-VentureCell. Pass 1b: `EvidenceReceipt` carries per-call cost; `AgentBudget`/`MissionRecord` in `economic_spine.py` carry aggregated cost. Pass 1d: "an economic system that tracks inflows but not outflows is half an economy." Pass 1c: economic spine aliveness 3. Pass 1a: the five metabolisms include "compute" as an energy transformation — compute cost is what flows in that metabolism. This type exists in fragments and needs consolidation into one typed concept.

---

## 5. Open Tensions Pass 3 Cannot Resolve

**Discernment question 1 — Which bus is the system's native communication medium?**
The SignalBus (in-process, raw dicts, synchronous) and the NATS A2A bus (inter-process, typed envelopes, async) serve different purposes but both carry semantic content that agents act on. The vocabulary census recommends naming typed A2A coordination messages as Layer 2 objects. But: should the SignalBus event types (`SIGNAL_OUTCOME_RECORDED`, `SIGNAL_RECOGNITION_UPDATED`) also be typed at Layer 2, or are they below the vocabulary floor? If they stay untyped dicts, agents cannot reason about them through the ontology. If they become typed objects, the in-process bus becomes an ontology traffic lane. What is John's intended architecture for the boundary between infrastructure signaling and vocabulary-layer coordination?

**Discernment question 2 — Is the "opportunity" layer a first-class organ or a derived view?**
The `opportunity_board.json` is produced by `ShaktiExecutive` and consumed by the curriculum engine. `OpportunityCandidate` has full scoring infrastructure. But: is an "opportunity" a typed ontology object (with its own identity, lifecycle, and link types), or is it a *derived view* — a ranking of `ZeitgeistSignal` + `StigmergyMark` + `KnowledgeArtifact` combinations that the ShaktiExecutive surfaces? Palantir's design guide says derived views should not be made into objects. But if opportunities are the system's primary attention-direction mechanism, they arguably deserve object-level identity. John's voice is needed: is ShaktiExecutive's output an ontology citizen or an ephemeral scoring surface?

**Discernment question 3 — Does `KnowledgeArtifact` become an Interface with multiple subtypes, or does it stay as one broad object?**
Pass 1d (§9, Q4) names this explicitly: KnowledgeArtifact encompasses 10 subtypes under one name. Palantir's design principle is that a union type masquerading as an object is bad design — it should be an Interface shared by multiple concrete types. But: splitting KnowledgeArtifact into 10 subtypes multiplies the registry complexity by 10 immediately. Is there a natural partition (e.g., `evidenceArtifact` + `knowledgeNote` + `codeArtifact`) that would serve the system better than one broad catch-all? This requires John's feel for how operators actually use knowledge artifacts in practice.

**Discernment question 4 — Where does the gate itself live?**
The individual telos gate (`AHIMSA`, `SATYA`, `REVERSIBILITY`, `SVABHAAVA`, `WITNESS`) is the constitutional backbone of the system. The `GateDecisionRecord` captures the gate's output per proposal. But the gate definition itself — its tier, its trigger patterns, its justification, its historical pass/fail statistics — has no ontology representation. Should a `telosGate` type be added to Layer 2 (making gates queryable as objects), or should gate definitions remain as system configuration (Layer 1 substrate)? The `GateProposal` type in `telos_gates.py` suggests the gate variety expansion protocol already treats new gate proposals as structured objects — which implies existing gates should be objects too. John's architectural intent for the gate system as an object or as configuration is the deciding voice.

**Discernment question 5 — What is the canonical unit of agent memory?**
Four parallel implementations (`StrangeLoopMemory`, `AgentMemoryBank`, `AgentMemoryManager`, `MemoryPalace`) plus the contracts layer `MemoryPlane` protocol. Pass 1d names this as a gap. Pass 1b documents it as a parallel-implementation problem. A Layer 2 vocabulary with a `memoryRecord` type would force one of these to be chosen as canonical and the others to be deprecated. But choosing the wrong one sets the consolidation path wrong. Does John have a view on which memory implementation is the intended architecture, or is the intended answer "these merge into one in the spine-adoption track"?

---

## 6. Recommended Pass 3 Posture

**Plain English domain nouns as type names. Sanskrit and dharmic vocabulary as the narrative layer that earns each name's right to exist.**

The argument is both pragmatic and principled. On the pragmatic side: the June surge's non-goals explicitly prohibit "spiritual/metaphoric naming layer" in new types (1c §5). The A2A spec conformance means external agents will query these types without context for Sanskrit roots. The OSDK discipline means developers consuming the API should read `actionProposal` and immediately understand what it is. Sanskrit names in the api_name slot create exactly the kind of long-term technical debt that Palantir's naming guide warns against: "This results in production ontologies with APIs such as `demoCustomer` four years into deployment" (1d §5.1) — except the equivalent here would be `witnessAuditShaktiMark` four years in. The test is: could a skilled developer who knows nothing about dharma_swarm's doctrine read the type name and infer its purpose? If yes, it is a good name. If no, the doctrine is being used to obscure rather than illuminate.

On the principled side: the Sanskrit vocabulary earns its place in the *narrative*, not the name. Every type in Pass 3 gets a 1-2 paragraph narrative that situates it in the life of the system. That narrative is where `actionProposal` becomes the system's metabolic intake breath — where the witness gate becomes the contemplative perceptual organ that cannot be bypassed — where the evidence receipt becomes the proof that this organism compounded through *use*, not through design. The narrative is doctrine-saturated. The name is plain. This is not a compromise between the two postures — it is the correct layering of two distinct audiences: the narrative is for John and for agents building dharmic alignment; the api_name is for developers, OSDK consumers, and A2A clients. The vocabulary should speak fluently to both, and it can only do that if the two registers are held in their proper relationship: name first, meaning second. The charter says to "earn the names" — and names are earned by being right, not by being sacred.

---

*This debate document was written by Pass 2 synthesis agent under 00-swarm-charter.md protocol.*
*All Pass 1 files read in full: 1a (340 lines), 1b (667 lines), 1c (229 lines), 1d (325 lines).*
*No type names proposed. Debate complete. Pass 3 has a clear field.*
*Active track: runtime-truth-spine-2026-06. Kill condition: 2026-08-07.*
