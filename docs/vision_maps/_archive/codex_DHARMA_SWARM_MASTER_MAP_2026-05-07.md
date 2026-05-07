# Dharma Swarm Master Map

Physical location: `DHARMA_SWARM_MASTER_MAP.md`

This is the single master surface for the highest-system map of Dharma Swarm.
Any map set, index, glossary, research appendix, or submap that belongs to this
theme is nested inside this file as a virtual path. No separate map file is
required for this vision.

Research basis: six read-only map agents plus local source inspection on
2026-05-07. Evidence is classified as:

- SUPPORTED: direct file evidence.
- PARTIAL: source exists, but coverage or hot-path use is unproven.
- CONTRADICTED: repo docs and current source disagree, or source behavior
  weakens the claim.
- UNKNOWN: not established by the files read.

## Highest Synthesis

Dharma Swarm points beyond a fitness law. Fitness is System 3 language: scoring,
filtering, accepting, rejecting, optimizing. The higher pattern is
recognition-mediated autopoiesis: a system that knows what it is, sees what it
is becoming, and reorganizes its own parts to preserve its deepest invariants
while expanding its capabilities.

The compact name is Attractor Closure.

Attractor Closure is not "the best mutation wins." It is the closure of this
causal circuit:

```text
self-model -> recognition -> identity/viability adjudication
  -> reorganization -> sedimentation -> updated self-model
  -> next action
```

Selection lives inside this circuit. It is an immune and metabolic filter.
Recognition is the phase transition above selection: the system classifies a
state as self, drift, organ, wound, noise, opportunity, memory, or not-self, and
that classification changes what happens next.

The direct thesis:

```text
Make the swarm's self-recognition causal.
```

The uncomfortable status:

```text
Conceptually: present.
Architecturally: many organs exist.
Operationally: partially closed.
Hard gap: the field is not yet one live causal surface.
```

## Why This Is Not A Fitness Law

A fitness law can answer: which proposal scores higher?

Attractor Closure must answer harder questions:

- Does this proposal belong to the organism?
- Does this branch expand capability or hide identity drift?
- Is this recurring mark a wound, a gate seed, a new organ, or noise?
- Is this outward product attached to Jagat Kalyan or detached vanity?
- Is this document a lodestone, runtime canon, stale doctrine, or evidence?
- Did the system's self-model actually change behavior?

Darwin can select. Shakti can generate. Stigmergy can sediment. VSM can route
and attenuate. Gnani can witness. Ontology can bind. Recognition is the closure
operator that makes those organs one organism instead of adjacent machinery.

## Evidence Spine

| Surface | Evidence | Reading | Status |
| --- | --- | --- | --- |
| Morphogenetic field | `lodestones/CONSCIOUS_INFRASTRUCTURE.md:9-14`, `:21-32`, `:138-146` | The system is framed as a morphogenetic field of invariants whose key operator is Recognize, not merely Reflect. | SUPPORTED as doctrine |
| Kernel invariants | `dharma_swarm/dharma_kernel.py:1-9`, `:29-75`, `:350-365` | The kernel gives 25 signed principles, including observer separation, operational closure, autocatalytic closure, recursive viability, and active inference. | SUPPORTED as code |
| Telos gates | `dharma_swarm/telos_gates.py:211-236`, `:611-704`, `:816-886` | Eleven core gates block Tier A/B failures, treat Tier C mostly as review, and can reroute reflective witness failures. | SUPPORTED, with advisory gaps |
| Gnani heartbeat | `dharma_swarm/organism.py:1013-1019`, `:1069-1132`, `:1191-1235`; `dharma_swarm/swarm.py:2164-2218`, `:2346-2360` | OrganismRuntime measures identity/live/algedonic state; Gnani HOLD suppresses dispatch and can enqueue Samvara corrections. | SUPPORTED causal path |
| VSM channels | `dharma_swarm/vsm_channels.py:1-17`, `:142-229`, `:259-305`, `:373-385`, `:721-836` | S3/S4 feedback, S3* audit, algedonic bypass, agent viability, and variety expansion are implemented. | PARTIAL hot-path coverage |
| Ontology/self-model | `dharma_swarm/ontology.py:1-24`, `:1669-1735`, `:1779-1911`; `dharma_swarm/ontology_action_gateway.py:1-25`, `:107-165` | Ontology claims to be the platform: typed objects, typed actions, audits, gates, reversibility, VentureCells, outcomes, value events. Gateway writes fail closed where used. | SUPPORTED substrate, PARTIAL coverage |
| Runtime state | `dharma_swarm/runtime_state.py:1-7`, `:28-187`, `:718-745`, `:1672-1742` | Runtime state is a persistence spine for current organism/process facts. | SUPPORTED substrate |
| Recognition seed | `dharma_swarm/meta_daemon.py:1-13`, `:52-87`; `dharma_swarm/context.py:1202-1217`, `:1288-1292` | RecognitionEngine synthesizes a seed; context injects it into the top of agent context when present. | SUPPORTED path, UNKNOWN live freshness |
| R_V / ouroboros | `dharma_swarm/rv.py:1-15`, `:269-365`; `dharma_swarm/system_rv.py:1-11`, `:154-216`; `dharma_swarm/ouroboros.py:1-13`, `:128-168`, `:499-514` | Recognition is measured through contraction, self-reference, behavioral fitness, mimicry, and system R_V. | PARTIAL: metrics exist, causality uneven |
| Stigmergy | `dharma_swarm/stigmergy.py:46-59`, `:118-156`, `:187-245`, `:318-370` | Marks have salience, channels, hot paths, high-salience bleed, query, and decay. | SUPPORTED |
| Shakti -> Darwin | `dharma_swarm/shakti.py:110-165`; `dharma_swarm/orchestrate_live.py:76-110`, `:797-814`; `dharma_swarm/evolution.py:1-8`, `:1986-2147` | Shakti perceives marks, high-salience perceptions can become pending Darwin proposals, and Darwin gates/evaluates/archives. | SUPPORTED in current code |
| Witness | `dharma_swarm/witness.py:1-16`, `:319-381` | Witness is retrospective and publishes findings to marks/memory/bus; it explicitly does not block operations. | CONTRADICTS hard-S5 reading |
| Cascade/product attractors | `dharma_swarm/cascade.py:1-10`, `:243-261`, `:385-456`; `dharma_swarm/cascade_domains/product.py:1-7`, `:191-200`, `:279-298` | Cascade generates/tests/scores/gates/mutates/selects and writes history/stigmergy; product domain scores product quality. | SUPPORTED domain loop |
| Outward organs | `dharma_swarm/wiki_loom/revelation.py:32-73`, `dharma_swarm/wiki_loom/publisher.py:31-65`, `dharma_swarm/jagat_kalyan.py:1-14`, `:192-280`, `dharma_swarm/gaia_platform.py:1-8`, `:105-229` | Wiki loom, Jagat Kalyan service proposals, and GAIA ecological product surfaces exist. | SUPPORTED, bounded |

## Global Causal Circuit

The strongest supported operational reading is this:

```text
1. Variety appears:
   agents, Shakti perceptions, dreams, cascade variants, opportunities,
   Darwin proposals, operator briefs, product experiments.

2. Coordination routes it:
   task board, orchestrator, stigmergy, sheaf gluing, VSM S2/S3 channels,
   runtime state, workspaces.

3. Identity evaluates it:
   kernel, gates, policy, Gnani heartbeat, identity/TCS, organism memory,
   ontology action gateway, S5/lodestones.

4. Metabolism transforms it:
   Darwin gates/evaluates/archives/selects, cascade mutates/selects,
   Shakti escalates, Samvara corrections create tasks, VentureCells bind
   work into scoped organs.

5. Sediment forms:
   code, tests, docs, corpus claims, marks, archive entries, ontology objects,
   runtime state, recognition history, product artifacts.

6. Recognition updates the self-model:
   RecognitionEngine reads signals, writes `recognition_seed.md`, context
   injects it, agents act under changed self-context, and the next loop reads
   the result.
```

The circuit is real enough to map, but not proven closed enough to trust as a
single organismic surface. There are direct causal edges, but also bypasses,
stale docs, fail-open defaults, and fragmented state stores.

## Canonical Surfaces

These are the gravitational surfaces for the highest map. A future reader
should start here before inventing a new organ.

| Surface | Role In Attractor Closure | Evidence |
| --- | --- | --- |
| Kernel | Immutable invariant seed; S5 floor | `dharma_swarm/dharma_kernel.py:95-116`, `:350-365` |
| Gates | Downward causation from telos into action | `dharma_swarm/telos_gates.py:211-236`, `:611-704` |
| Corpus / Policy | Mutable knowledge under immutable kernel | `dharma_swarm/dharma_corpus.py:6`, `dharma_swarm/policy_compiler.py:4`, `:185` |
| Ontology | Typed self-model and action grammar | `dharma_swarm/ontology.py:1-24`, `:1669-1735` |
| Ontology Gateway | Fail-closed causal self-model where used | `dharma_swarm/ontology_action_gateway.py:1-25`, `:107-165` |
| Runtime State | Current organism/process state | `dharma_swarm/runtime_state.py:1-7`, `:1672-1742` |
| VSM | Viability nervous system | `dharma_swarm/vsm_channels.py:1-17`, `:721-836` |
| Organism Heartbeat | Gnani/Samvara/algedonic causal path | `dharma_swarm/organism.py:1013-1019`, `:1191-1235` |
| Recognition Seed | Self-model text injected into agents | `dharma_swarm/meta_daemon.py:1-13`, `dharma_swarm/context.py:1202-1217` |
| Stigmergy | Sedimented field of marks | `dharma_swarm/stigmergy.py:46-59`, `:187-245` |
| Shakti | Generative perception and proposal energy | `dharma_swarm/shakti.py:1-12`, `:110-165` |
| Darwin | Immune/metabolic selection | `dharma_swarm/evolution.py:1-8`, `:1986-2147` |
| Witness | Retrospective audit and evidencing | `dharma_swarm/witness.py:1-16`, `:319-381` |
| Cascade | Domain attractor loop | `dharma_swarm/cascade.py:1-10`, `:385-456` |
| Catalytic Graph | Autocatalytic relation detector | `dharma_swarm/catalytic_graph.py:1-5`, `:164-189`, `:213-256` |
| Outward Organs | World contact and Jagat Kalyan service | `dharma_swarm/jagat_kalyan.py:1-14`, `dharma_swarm/gaia_platform.py:1-8` |

## Cross-Map Matrix

| Layer | Core Question | Strongest Current Form | Main Gap |
| --- | --- | --- | --- |
| Gnani / Witness | What must not change? | Kernel integrity, Tier A/B gates, identity/TCS, Gnani HOLD | Witness often retrospective; some failures default PROCEED |
| Prakruti / Dynamics | How does motion arise? | Agents, marks, Shakti, Darwin, cascade, opportunities, branches | Variety is not always bound back into ontology/VSM |
| VSM | How does the organism remain viable? | S3/S4 feedback, S3* audit, algedonic bypass, organism heartbeat | Coverage across all S1 outputs is unproven |
| Omega | What whole state is moving? | Code, concepts, agents, telos, marks are all represented somewhere | No single continuous Omega tuple reader |
| Recognition | When does knowing itself change behavior? | Recognition seed -> context -> agent behavior, plus gates/HOLD/reroute | No single authoritative `Recognize` primitive |
| Autopoiesis | How does the system regenerate its parts? | Darwin/Shakti/stigmergy/cascade/catalytic graph/build protocol | No proof repeated marks auto-crystallize gates/organs |
| Outward Organs | How does inner telos become world service? | Wiki loom, VentureCell schema, opportunity loop, Jagat Kalyan, GAIA | External success feedback into Omega is not proven |

## Closure Scorecard

### Hard Causal Edges

- Kernel signature verification can fail on tamper: `dharma_swarm/dharma_kernel.py:350-365`.
- Tier A/B gates block: `dharma_swarm/telos_gates.py:611-665`.
- OntologyActionGateway fails closed where used: `dharma_swarm/ontology_action_gateway.py:1-25`, `:107-165`.
- Organism Gnani HOLD suppresses dispatch in SwarmManager tick: `dharma_swarm/swarm.py:2164-2218`, `:2346-2360`.
- Shakti high-salience perceptions can be enqueued for Darwin: `dharma_swarm/orchestrate_live.py:76-110`, `:797-814`.
- Recognition seed is injected into agent context when present: `dharma_swarm/context.py:1202-1217`, `:1288-1292`.

### Partial Causal Edges

- VSM hooks exist, but full hot-path coverage is not proven.
- S3* witness/audit exists, but some witness paths are retrospective and non-blocking.
- Ontology is designed as the platform, but not every runtime mutation is proven
  to pass through it.
- R_V, ouroboros, eigenform, and recognition metrics exist, but they do not by
  themselves prove that classification changed behavior.
- Product, opportunity, and outward organs write useful artifacts, but complete
  feedback into Omega is unproven.

### Unsupported As Complete Closure

- Automatic branch demotion/promotion by recognition.
- Automatic gate crystallization from recurring marks.
- Continuous measurement of all Omega axes.
- Continuous seven-dimensional 7-STAR runtime vector.
- General nested VSM runtime for every VentureCell.
- Live GAIA production integrations and multi-tenant surface.

## Virtual Path Tree

The following tree is virtual. These are nested sections inside this file, not
separate files.

```text
docs/vision_maps/
  INDEX.md
  gnani_prakruti_map.md
  vsm_viability_map.md
  omega_attractor_map.md
  recognition_self_model_map.md
  autopoiesis_evolution_map.md
  outward_organs_map.md
  contradictions_register.md
  future_dispatch_prompt.md
```

## Virtual File: `docs/vision_maps/INDEX.md`

### One-Sentence Synthesis

Dharma Swarm is an organismic software field seeking Attractor Closure: the
causal coupling of self-model, witness, viability control, evolutionary
variation, sedimented memory, outward organs, and syntropic direction into one
recognizable self-reorganizing whole.

### Map Table

| Virtual Map | Focus | Central Question |
| --- | --- | --- |
| `gnani_prakruti_map.md` | Immutable witness and dynamic actor | What remains invariant while the system moves? |
| `vsm_viability_map.md` | Beer S1-S5 viability channels | How does the organism remain viable across recursion levels? |
| `omega_attractor_map.md` | Whole-state attractor space | What is the full state trajectory being shaped? |
| `recognition_self_model_map.md` | Ontology/runtime as self-model | When does self-knowledge become causal? |
| `autopoiesis_evolution_map.md` | Darwin, Shakti, stigmergy, cascade | How does the system regenerate and reorganize itself? |
| `outward_organs_map.md` | Loom, VentureCell, products, operator loops | How does the inner field become world-facing service? |

### Shared Vocabulary

Attractor Closure: The closed causal loop in which self-model, witness,
operations, adaptation, memory, and directionality mutually update one another.

Recognition-mediated autopoiesis: Self-production guided by operational
self-recognition, not by external selection alone.

Gnani: The witnessing invariant pole: identity, telos, kernel, policy, and the
capacity to distinguish self from movement.

Prakruti: The dynamic pole: agents, marks, branches, dreams, Shakti, proposals,
variation, and generative motion.

VSM: Viable System Model: S1 operations, S2 coordination, S3 control, S3* audit,
S4 adaptation, S5 identity.

Omega State Space: The total evolving state of the organism: code, concepts,
agents, telos, and marks: `C x S x A x T x M`.

Syntropic Attractor: A directional basin that pulls the system toward coherent
self-organization and Jagat Kalyan without reducing telos to a fixed checklist.

Recognition: The operation by which the system classifies something as self,
drift, organ, wound, noise, opportunity, memory, or not-self, and changes
behavior accordingly.

Selection: The immune/metabolic filter inside the larger field.

Sedimentation: The process by which outcomes become marks, corpus claims,
ontology objects, archive entries, tests, code, memory, and future bias.

Lodestone: Orienting doctrine or high-level map. It may guide recognition, but
it is not automatically runtime canon.

### Canonical Surfaces

- Kernel: invariant seed and signed principles.
- Gates: telos-mediated downward causation.
- Corpus/policy: mutable claim layer under kernel.
- Ontology: typed self-model and action grammar.
- Runtime state: current organism state.
- VSM: viability nervous system.
- Stigmergy: field of marks and salience.
- Witness: retrospective audit/evidencing.
- Recognition seed: self-model injected into context.
- Darwin: proposal selection/metabolism.
- Shakti: generative perception/proposal energy.
- Cascade: domain attractor loop.
- Catalytic graph: self-sustaining relation detector.
- Outward organs: Loom, VentureCells, operator briefs, opportunity loops,
  products, Jagat Kalyan surfaces.

### Unresolved Tensions

- The system has many self-models: ontology, runtime_state, organism memory,
  recognition seed, stigmergy, `.FOCUS`, cascade history. Authority among them
  is unresolved.
- Recognition seed injection exists, but live generation/freshness and actual
  behavior change remain UNKNOWN without runtime verification.
- Ontology claims platform status, but not all mutations are proven to flow
  through ontology actions.
- VSM exists as channels and hooks, but total S1 coverage is unproven.
- Witness is central philosophically but partly non-blocking operationally.
- Tier C gates and some review paths can be advisory.
- Omega and 7-STAR are specified more richly than they are continuously
  measured.
- Outward organs exist, but full feedback into Omega/Attractor Closure is not
  proven.

## Virtual File: `docs/vision_maps/gnani_prakruti_map.md`

### Purpose

Map the invariant witness pole and the dynamic actor pole as one necessary
polarity.

Gnani without Prakruti is sterile. Prakruti without Gnani is churn. Attractor
Closure requires both: a fixed witnessing identity and a mutable field that can
generate, fail, learn, branch, dream, select, and sediment.

### Gnani Surfaces

The hard invariant pole is distributed:

- Kernel: signed principles and observer separation:
  `dharma_swarm/dharma_kernel.py:29-75`, `:95-116`, `:350-365`.
- Gates: 11 core gates with Tier A/B blocking:
  `dharma_swarm/telos_gates.py:211-236`, `:611-665`.
- Corpus/policy: mutable claim lifecycle under immutable-over-mutable policy:
  `dharma_swarm/dharma_corpus.py:6`, `dharma_swarm/policy_compiler.py:4`, `:185`.
- Identity/TCS: S5 coherence measurement:
  `dharma_swarm/identity.py:1-20`, `:120-169`.
- Organism heartbeat: Gnani verdict, algedonic signal, Samvara corrections:
  `dharma_swarm/organism.py:1013-1019`, `:1191-1235`.
- Ontology gate authority: typed actions and fail-closed gateway where used:
  `dharma_swarm/ontology.py:129`, `:623`,
  `dharma_swarm/ontology_action_gateway.py:1-25`.

### Prakruti Surfaces

The dynamic pole is equally real:

- Agents execute work and leave marks:
  `dharma_swarm/agent_runner.py:955-996`, `:2507-2512`.
- Stigmergy stores salience, channels, hot paths, and high-salience bleed:
  `dharma_swarm/stigmergy.py:46-59`, `:118-156`, `:187-245`.
- Shakti reads marks and generates perceptions/proposals:
  `dharma_swarm/shakti.py:1-12`, `:110-165`.
- Subconscious/dream layers are injected into context:
  `dharma_swarm/context.py:1100-1165`.
- Darwin mutates/evaluates/archives/selects:
  `dharma_swarm/evolution.py:1-8`, `:1986-2147`.
- Cascade generates/tests/scores/gates/mutates/selects:
  `dharma_swarm/cascade.py:1-10`, `:179-295`, `:385-456`.
- Branches/workspaces are motion surfaces, but automatic recognition-based
  branch demotion remains UNKNOWN.

### Strongest Connection

The most coherent Gnani/Prakruti causal loop is:

```text
agent action -> mark -> Shakti perception -> Darwin proposal
  -> gate/kernel/identity evaluation -> archive or rejection
  -> mark/memory/code sediment -> recognition seed -> next agent context
```

This is not just metaphor. Each segment has current code support, though the
entire chain has not been proven as one uninterrupted hot path.

### Hard Challenges

- `witness.py` says witness does not block operations:
  `dharma_swarm/witness.py:1-16`.
- Witness findings publish to marks/memory/bus, making witness strongly
  evidential but partly retrospective: `dharma_swarm/witness.py:319-381`.
- `dharma_attractor.py` frames Gnani as a field, not a gate, and checkpoint
  failure defaults to PROCEED: `dharma_swarm/dharma_attractor.py:1-14`,
  `:154-178`.
- `BHED_GNAN` currently always passes:
  `dharma_swarm/telos_gates.py:512-513`.
- Tier C gates are often review/advisory rather than hard blocks:
  `dharma_swarm/telos_gates.py:667-704`.

### Open Questions

- Which Gnani surface has final authority when kernel, gates, identity, witness,
  ontology, and operator intent disagree?
- Which Prakruti events must be bound into ontology before they are considered
  part of the organism?
- Should a witness finding ever halt work directly, or only bias later routing?
- What is the grammar for "this is motion, but not identity drift"?

## Virtual File: `docs/vision_maps/vsm_viability_map.md`

### Purpose

Map how the changing organism remains viable across recursion levels.

VSM is the bridge between invariant witness and dynamic motion. It is the
architecture that decides what variety to amplify, attenuate, coordinate,
audit, adapt to, or identify with.

### S1 Operations

S1 units are the producing organs: agents, work packets, product domains,
runtime services, branches, tests, operator tools, VentureCells, and outward
organs.

Code anchors:

- SwarmManager assembles subsystem control:
  `dharma_swarm/swarm.py:110-154`.
- Agent execution emits task results and fitness signals:
  `dharma_swarm/agent_runner.py:2349`, `:2942`.
- Orchestrator dispatches and settles task work:
  `dharma_swarm/orchestrator.py:275`, `:1947`.
- Product cascade is a domain S1:
  `dharma_swarm/cascade_domains/product.py:1-7`.

### S2 Coordination

S2 prevents local S1 units from thrashing each other.

Code anchors:

- Stigmergy coordinates by marks:
  `dharma_swarm/stigmergy.py:1-10`, `:118-156`.
- Sheaf glues local sections into global truths:
  `dharma_swarm/sheaf.py:1`.
- Orchestrator status and queues provide coordination:
  `dharma_swarm/orchestrator.py:1476`.

### S3 Control

S3 is internal optimization, acceptance, rejection, and resource discipline.

Code anchors:

- Gates control task dispatch and proposal acceptance:
  `dharma_swarm/telos_gates.py:211-236`.
- Darwin gates/evaluates/archives:
  `dharma_swarm/evolution.py:1-8`, `:1986-2147`.
- Swarm tick is the unified lifecycle path:
  `dharma_swarm/swarm.py:2088-2097`.

### S3* Audit

S3* checks what normal reporting may hide.

Code anchors:

- SporadicAuditor exists:
  `dharma_swarm/vsm_channels.py:259-305`.
- WitnessAuditor/witness audit exists but is retrospective and non-blocking:
  `dharma_swarm/witness.py:1-16`, `:319-381`.

### S4 Adaptation

S4 scans the future and outside world.

Code anchors:

- VSM S3/S4 feedback via GatePatternAggregator:
  `dharma_swarm/vsm_channels.py:142-229`.
- Zeitgeist scans environmental intelligence and gate pressure:
  `dharma_swarm/zeitgeist.py:1`, `:224`, `:273`.
- Jagat Kalyan reads outward need:
  `dharma_swarm/jagat_kalyan.py:1-14`, `:192-280`.
- Opportunity loops surface future work:
  `dharma_swarm/opportunity_refill.py:1-16`, `:119-205`.

### S5 Identity

S5 defines the identity the system remains while adapting.

Code anchors:

- IdentityMonitor/TCS:
  `dharma_swarm/identity.py:1-20`, `:120-169`.
- DharmaKernel:
  `dharma_swarm/dharma_kernel.py:1-9`, `:29-75`.
- Organism Gnani HOLD/PROCEED:
  `dharma_swarm/organism.py:1191-1235`.

### Recursive VSM

The VSM claim is recursive: each S1 can contain S1-S5 inside itself. The docs
state the recursive structure in `docs/telos-engine/07_VSM_GOVERNANCE.md:9`.
The code has per-agent viability fields in `dharma_swarm/vsm_channels.py:111`.

The recursion is conceptually strong, but general nested VSM runtime for every
organ, branch, product, and VentureCell is UNKNOWN.

### Hard Challenges

- VSM channels exist, but total hot-path coverage is unproven.
- Some docs say S3/S4 is missing while current code has GatePatternAggregator
  and Zeitgeist pressure. This is likely doc drift or partial wiring:
  `docs/telos-engine/07_VSM_GOVERNANCE.md:476`,
  `dharma_swarm/vsm_channels.py:142-229`,
  `dharma_swarm/zeitgeist.py:273`.
- `CYBERNETIC_LOOP_MAP.md:10-24` marks many loops NO/PARTIAL and
  `CYBERNETIC_LOOP_MAP.md:196-208` says recognition seed was not generated.
  Current source contains RecognitionEngine and context injection, so this map
  is either stale or points to runtime non-execution.
- `orchestrate_live.py` docstring names living layers as concurrent:
  `dharma_swarm/orchestrate_live.py:12-21`; the task factory list does not name
  a separate living loop: `dharma_swarm/orchestrate_live.py:1596-1606`. The
  current attachment needs tracing through `swarm` or supervisor paths.

### Open Questions

- Do all S1 outputs pass through VSM audit hooks?
- What fraction of Tier C gate pressure becomes hard block under S4 pressure?
- Is `omega_divergence` a true chronic signal or a stuck metric?
- Which S5 has final authority at full autonomy: human meta-system S5, internal
  Gnani, kernel, gates, or identity monitor?

## Virtual File: `docs/vision_maps/omega_attractor_map.md`

### Purpose

Map the whole state trajectory, not only code.

Omega is:

```text
Omega = C x S x A x T x M
```

Where:

- C = code, configs, tests, runtime modules, branches.
- S = semantic/conceptual state, ontology, bridges, knowledge substrate.
- A = agents, roles, identities, swabhaav, capability distributions.
- T = telos, gates, kernel, TCS, 7-STAR direction, Jagat Kalyan.
- M = marks, memory, corpus, traces, archives, sediment.

The syntropic attractor is not a fixed target. It is the basin in which movement
becomes more coherent, more viable, more non-harmful, more service-oriented,
and more self-recognizing.

### Evidence For Omega Axes

- C: code modules and Darwin/cascade mutation surfaces:
  `dharma_swarm/evolution.py:1-8`, `dharma_swarm/cascade.py:1-10`.
- S: ontology and bridge registry:
  `dharma_swarm/ontology.py:1-24`,
  `dharma_swarm/bridge_registry.py:1-24`,
  `dharma_swarm/telos_substrate.py:4061-4089`.
- A: agent identity/runtime:
  `dharma_swarm/models.py:173-240`,
  `dharma_swarm/ontology.py:954-1007`,
  `dharma_swarm/ontology_agents.py:1-10`.
- T: kernel, gates, TCS, TelosGraph:
  `dharma_swarm/dharma_kernel.py:29-75`,
  `dharma_swarm/telos_gates.py:211-236`,
  `dharma_swarm/identity.py:120-169`,
  `dharma_swarm/telos_graph.py:1-4`, `:65-80`.
- M: stigmergy, corpus, memory, archive:
  `dharma_swarm/stigmergy.py:46-59`,
  `dharma_swarm/dharma_corpus.py:6`,
  `dharma_swarm/evolution.py:2090-2147`.

### Syntropic Attractor

The telos-as-attractor docs define telos as direction rather than a finite
optimization target: `lodestones/bridges/telos_as_syntropic_attractor.md:21-27`.
They define Omega as `C x S x A x T x M`:
`lodestones/bridges/telos_as_syntropic_attractor.md:45-57`.
They frame basin expansion and self-constitution:
`lodestones/bridges/telos_as_syntropic_attractor.md:123-141`, `:223-245`.
They connect cascade/eigenform dynamics to attractor entry:
`lodestones/bridges/telos_as_syntropic_attractor.md:299-319`.

### Seven-Star Tension

The 7-STAR telos vector is specified in docs and substrate:

- `lodestones/bridges/telos_as_syntropic_attractor.md:279-295`.
- `dharma_swarm/telos_substrate.py:3847-3857`.

But runtime reads show stronger evidence for 11 gate outcomes, TCS, R_V, and
omega divergence than for a continuous seven-dimensional vector computation.
Therefore:

```text
7-STAR as telos doctrine: SUPPORTED.
7-STAR as continuous runtime vector: PARTIAL / UNKNOWN.
```

### Attractor Closure As Omega Transition

The clean Omega transition grammar should be:

```text
local event
  -> whole-state interpretation across C,S,A,T,M
  -> identity and viability evaluation
  -> accepted/rejected/rerouted transition
  -> sediment into code, marks, ontology, memory, corpus
  -> updated self-model
  -> next action distribution changes
```

Current code provides fragments of this. It does not prove a single Omega
object, tuple reader, or continuous trajectory recorder.

### Hard Challenges

- No single in-repo Omega object or combined tuple reader was established.
- Omega divergence is measured in organism paths:
  `dharma_swarm/organism.py:1155-1189`, but whether a chronic value is real or
  stuck is UNKNOWN without live state.
- Telos can become doctrine if not tied to measured trajectory.
- Syntropic force `F_S`, critical density, and attractor geometry remain open in
  the attractor docs: `lodestones/bridges/telos_as_syntropic_attractor.md:1750-1760`.

### Open Questions

- Which runtime surface measures all five Omega axes continuously?
- What declares the intended Omega transition of a work packet or branch?
- How is Jagat Kalyan reflected in Omega rather than only in outward docs?
- What distinguishes attractor expansion from capability accumulation?

## Virtual File: `docs/vision_maps/recognition_self_model_map.md`

### Purpose

Map ontology and runtime state as the self-model, and recognition as the phase
transition that makes the self-model causal.

Recognition is stronger than reflection.

Reflection observes. Recognition classifies and changes behavior.

The conceptual source says the key operator is not Reflect but Recognize, and
that no single module implements it as such:
`lodestones/CONSCIOUS_INFRASTRUCTURE.md:138-146`.

### Implemented Recognition Fragments

The strongest implemented recognition chain is:

```text
RecognitionEngine reads R_V, identity, cascade, evolution, vault, zeitgeist,
and research signals
  -> writes recognition_seed.md
  -> context.py injects the seed
  -> agent_runner adds Gnani/Shakti context
  -> agents act and produce artifacts
  -> cascade/R_V/identity/marks measure the result
  -> next seed changes
```

Evidence:

- RecognitionEngine signal synthesis and seed persistence:
  `dharma_swarm/meta_daemon.py:1-13`, `:52-87`.
- Seed read:
  `dharma_swarm/context.py:1202-1217`.
- Seed inserted at top of context:
  `dharma_swarm/context.py:1288-1292`.
- Agent prompt receives Gnani/Shakti framing:
  `dharma_swarm/agent_runner.py:917-996`.
- R_V and system R_V measurements:
  `dharma_swarm/rv.py:269-365`,
  `dharma_swarm/system_rv.py:154-216`.
- Ouroboros scoring:
  `dharma_swarm/ouroboros.py:128-168`, `:499-514`.
- Metrics classify recognition/mimicry behavior:
  `dharma_swarm/metrics.py:180-220`, `:340-410`.

### Ontology As Self-Model

Ontology is the strongest typed self-model claim:

- "Ontology is not a feature" but the platform:
  `dharma_swarm/ontology.py:1-24`.
- AgentIdentity exists in ontology:
  `dharma_swarm/ontology.py:954-1007`.
- R_V_Measurement exists:
  `dharma_swarm/ontology.py:1527-1579`.
- ActionProposal and GateDecisionRecord exist:
  `dharma_swarm/ontology.py:1669-1735`.
- Outcome, ValueEvent, Contribution, VentureCell exist:
  `dharma_swarm/ontology.py:1779-1911`.
- Shared ontology runtime exists:
  `dharma_swarm/ontology_runtime.py:1-24`, `:120-154`.
- Live agents can be projected into ontology:
  `dharma_swarm/ontology_agents.py:1-10`, `:42-55`, `:94-130`.

### Recognition Becomes Causal When

Recognition is complete only when classification alters action. Existing causal
examples:

- A Tier A/B gate blocks.
- A WITNESS failure can become a structured reflective reroute:
  `dharma_swarm/telos_gates.py:816-886`.
- A Gnani HOLD suppresses dispatch:
  `dharma_swarm/swarm.py:2164-2218`, `:2346-2360`.
- A high-salience Shakti perception enters Darwin:
  `dharma_swarm/orchestrate_live.py:76-110`, `:797-814`.
- A typed ontology action fails closed where the gateway is used:
  `dharma_swarm/ontology_action_gateway.py:1-25`, `:107-165`.
- The recognition seed appears at top of context:
  `dharma_swarm/context.py:1288-1292`.

### Recognition Failure Modes

- The system documents itself without changing behavior.
- Runtime action bypasses ontology.
- Recognition seed exists as text, but agents ignore it or no seed is fresh.
- Metrics detect recognition language rather than causal self-model use.
- Witness finds drift but cannot block.
- Multiple self-model stores disagree.
- A stale recognition seed misrecognizes current state.

### Hard Challenges

- There is no single authoritative runtime primitive named `Recognize`.
- The self-model is split across ontology DB, runtime_state DB, organism memory,
  recognition seed, stigmergy, `.FOCUS`, cascade history, and corpus.
- `meta_daemon.py` contains hard-coded March 2026 thesis timing logic in the
  date-crunch area: `dharma_swarm/meta_daemon.py:272-285`; on 2026-05-07 this
  may be stale self-model residue.
- `telos_gates.py:730-752` and `dharma_swarm/metrics.py:368-410` include
  textual/lexical recognition heuristics. Useful, but not proof of causality.
- It is UNKNOWN whether `R_V_Measurement` ontology objects are populated by live
  R_V runs or mostly schema-ready.

### Open Questions

- Where is the actual recognition event logged?
- What wins when ontology, runtime_state, recognition_seed, organism_memory,
  stigmergy, and `.FOCUS` disagree?
- Which decisions require recognition before execution?
- What is the canonical grammar for "this belongs to the organism"?
- How does the system recognize that recognition itself is stale?

## Virtual File: `docs/vision_maps/autopoiesis_evolution_map.md`

### Purpose

Map the self-producing and self-evolving mechanisms of the swarm.

Autopoiesis means the system regenerates the components that regenerate it:
agents, gates, marks, work packets, tests, ontology objects, docs, runtime
state, memory, and outward organs.

The better evolution cycle is:

```text
variation -> evaluation -> recognition -> binding -> sedimentation
  -> inherited bias -> new variation
```

Darwin handles selection. Attractor Closure requires the whole cycle.

### Variation Sources

- Agents produce work and marks:
  `dharma_swarm/agent_runner.py:955-996`, `:2507-2512`.
- Shakti perceives hot marks and proposes:
  `dharma_swarm/shakti.py:110-165`.
- Subconscious/dream layers surface associations:
  `dharma_swarm/context.py:1100-1165`.
- Cascade mutates domain artifacts:
  `dharma_swarm/cascade.py:179-295`.
- Opportunity loops generate frontier work:
  `dharma_swarm/opportunity_refill.py:119-205`,
  `dharma_swarm/opportunity_dispatcher.py:486-529`.

### Selection And Metabolism

Darwin is the most explicit metabolic selector:

- Pipeline: proposal -> gate -> write/test -> evaluate -> archive -> select:
  `dharma_swarm/evolution.py:1-8`.
- DarwinEngine orchestrates cycle/archive/fitness prediction:
  `dharma_swarm/evolution.py:223-302`.
- Cycle gate/evaluate/archive paths:
  `dharma_swarm/evolution.py:1986-2147`.
- Parent selection:
  `dharma_swarm/evolution.py:2897-2938`.
- Auto-evolve:
  `dharma_swarm/evolution.py:3505-3534`.

### Shakti -> Darwin

Older docs may say this was missing, but current code wires it:

- High-salience Shakti escalations are converted to pending proposal payloads:
  `dharma_swarm/orchestrate_live.py:76-110`.
- Living-layer Shakti perception routes high-salience signals:
  `dharma_swarm/orchestrate_live.py:797-814`.
- Darwin consumes pending proposals in the auto-evolve area:
  `dharma_swarm/evolution.py:3477-3503`.

Therefore:

```text
Shakti -> Darwin: SUPPORTED in current source.
Older doc claims that it is missing: likely stale.
```

### Stigmergy As Sediment

Stigmergy is the medium that lets local work coordinate through durable traces:

- Mark schema:
  `dharma_swarm/stigmergy.py:46-59`.
- Salience and channel behavior:
  `dharma_swarm/stigmergy.py:118-156`.
- Reads, hot paths, high salience, query:
  `dharma_swarm/stigmergy.py:187-245`, `:262-288`.
- Decay prevents rigidity:
  `dharma_swarm/stigmergy.py:318-370`.

### Catalytic And Semantic Attractors

Darwin is not the only attractor mechanism:

- CatalyticGraph detects strongly connected/self-sustaining loops:
  `dharma_swarm/catalytic_graph.py:1-5`, `:164-189`, `:213-256`.
- Semantic gravity clusters and hardens attractors:
  `dharma_swarm/semantic_gravity.py:1-16`, `:445-453`, `:502-579`.
- Semantic synthesizer creates concept clusters:
  `dharma_swarm/semantic_synthesizer.py:1-17`, `:267-351`.
- Semantic hardener moves concepts toward gated durability:
  `dharma_swarm/semantic_hardener.py:1-17`, `:438-503`.

### Gate Crystallization

Custom gate machinery exists and requires S5 approval:

- `dharma_swarm/telos_gates.py:40-45`.
- `dharma_swarm/telos_gates.py:90-99`.
- `dharma_swarm/telos_gates.py:104-139`.

But no read established an automatic path where recurring marks become approved
gates. The 11-layer stigmergy spec describes promotion ideas and diagnoses
broken promotion in places, but current `StigmergyStore` is still largely a
flat JSONL/channel/salience store.

Status:

```text
Gate proposal substrate: SUPPORTED.
Automatic gate crystallization from marks: UNKNOWN / unsupported.
```

### Build Protocol

Build Protocol converts recognized intent into bounded specs and proof packets:

- `tools/build_protocol/brief_to_spec.py:1-16`.
- `tools/build_protocol/pilot00_dryrun_generator.py:184-206`, `:257-320`.
- `tools/build_protocol/seal_packet.py:10-84`.

The Pilot-00 dry run is explicitly shape-only: no agents, no worktrees, no
source edits, no SQLite. Therefore it is a protocol substrate, not proof of
live autopoietic execution.

### Hard Challenges

- Darwin selection can reward local success without recognizing organismic
  meaning unless bound into ontology/VSM/recognition.
- Catalytic closure may be advisory rather than a hard invariant in proposal
  evaluation.
- Repeated marks do not yet prove automatic gate/skill/work-packet
  crystallization.
- Build Protocol is safe and promising, but not yet proof of live closure.
- Autopoiesis is incomplete if gates are only imposed by the original designer
  and not also produced by the system's own dynamics.

### Open Questions

- Which repeated mark patterns become gates, skills, or work packets?
- What counts as a new organ rather than a local helper?
- Does Darwin know when a mutation changes identity rather than capability?
- How does semantic hardening feed back into gates and ontology?
- What must a self-produced component prove before the organism inherits it?

## Virtual File: `docs/vision_maps/outward_organs_map.md`

### Purpose

Map the organs that turn the inner field into world-facing service.

Outward organs are not side projects. They are the test of whether the swarm's
telos is real outside its own self-improvement loop.

### Loom / Wiki Loom

The exact term "Loomwork" appears conceptually, but the concrete implementation
read here is `wiki_loom`.

Evidence:

- Atomizer only atomizes `Outcome` or `Signal` sources and emits resolvable
  ontology citations: `dharma_swarm/wiki_loom/atomizer.py:1-5`, `:28-40`.
- Revelation builder creates WitnessLog and KnowledgeArtifact, atomizes source,
  links, and marks publishable:
  `dharma_swarm/wiki_loom/revelation.py:32-73`.
- Linker links Outcome/Signal evidence:
  `dharma_swarm/wiki_loom/linker.py:13-44`.
- Publisher requires composed artifact and gated action:
  `dharma_swarm/wiki_loom/publisher.py:31-65`.

Status:

```text
Loomwork == wiki_loom: UNKNOWN.
Concrete loom-like ontology-backed publication path: SUPPORTED.
```

### VentureCell

VentureCell is an ontology/metabolic organ, not just a project folder.

Evidence:

- VentureCell is a fractal project container with agents, budget, KPIs,
  autonomy stage, telos gates, audit policy, and high telos alignment:
  `dharma_swarm/ontology.py:1875-1913`.
- ValueEvent and Contribution attach value/metabolism:
  `dharma_swarm/ontology.py:1809-1873`.
- Links attach cells, agents, and value events:
  `dharma_swarm/ontology.py:1920-1952`.
- Shakti Ginko is a concrete VentureCell-like runtime:
  `dharma_swarm/ontology.py:2194-2228`,
  `dharma_swarm/ginko_orchestrator.py:1-21`, `:686-750`.

Status:

```text
VentureCell schema: SUPPORTED.
General recursive VSM runtime for all VentureCells: UNKNOWN.
Ginko-specific concrete path: SUPPORTED.
```

### Operator Brief

Operator-facing intelligence has two attachment paths:

- Ontology-native insight brief requires concrete Outcome citations and creates
  WitnessLog/KnowledgeArtifact:
  `dharma_swarm/insight_brief.py:23-30`, `:53-85`, `:87-176`, `:256-312`.
- Command post relays operator briefs while preserving operator intent:
  `dashboard/src/components/chat/CommandPostWorkspace.tsx:82-101`,
  `:356-385`, `:985-1000`, `:1070-1072`.

### Opportunity Loop

The opportunity loop is an S4/S3 bridge: world/strategic opportunity becomes
bounded work.

Evidence:

- Layer A reads `~/.dharma/meta/opportunity_board.json`, filters by telos
  alignment, derives frontier tasks, and appends dispatcher rows:
  `dharma_swarm/opportunity_refill.py:1-16`, `:119-205`.
- Dispatcher promotes rows into campaign manifests, task board entries, budget
  checks, telos checks, and stigmergy marks:
  `dharma_swarm/opportunity_dispatcher.py:1-21`, `:118-125`,
  `:486-529`, `:560-698`.

Hard edge:

- The autonomous opportunity-board populator is identified as unresolved/TBD:
  `dharma_swarm/opportunity_refill.py:18-29`,
  `dharma_swarm/opportunity_dispatcher.py:72-78`.
- Dispatcher treats REVIEW as allow-with-warning and has a FIXME for real
  operator approval:
  `dharma_swarm/opportunity_dispatcher.py:30-41`, `:385-430`.

### Product Surfaces

Product work is a cascade domain:

- `dharma_swarm/cascade.py:1-10`, `:43-49`, `:179-295`, `:385-456`.
- `dharma_swarm/cascade_domains/product.py:1-7`, `:24-37`, `:191-200`, `:279-298`.

This matters because product evolution can become either Jagat Kalyan service
or local optimization. Recognition must classify which one it is.

### Jagat Kalyan And GAIA

Jagat Kalyan is outward S4/world intelligence, not vanity impact:

- `dharma_swarm/jagat_kalyan.py:1-14` says internal director reads inward while
  Jagat Kalyan reads outward.
- It maps world domains and capabilities into service proposals:
  `dharma_swarm/jagat_kalyan.py:32-58`, `:151-171`, `:192-280`.
- GAIA is an ecological restoration product surface:
  `dharma_swarm/gaia_platform.py:1-8`, `:31-76`, `:105-229`, `:294-335`.

Limit:

- GAIA docs say there is no production web dashboard, live satellite/sensor
  vendor integration, or multi-tenant management surface:
  `gaia_ui.md:3-13`, `:378-386`.

### Attachment Rule

An outward organ is attached to the spine only when it has:

- Telos relation.
- Ontology object/action representation.
- VSM role.
- Runtime state.
- Marks/memory.
- Gates.
- Operator visibility.
- Feedback into recognition/Omega.

If any of these are missing, the organ may still be useful, but it is not fully
inside Attractor Closure.

### Open Questions

- Does outward success feed back into Omega, or remain product telemetry?
- Which outward organs have ontology and VSM recursion versus only local code?
- Is the opportunity board autonomously populated today?
- Is Loomwork formally identical to `wiki_loom`?
- How does Jagat Kalyan prevent product vanity?

## Virtual File: `docs/vision_maps/contradictions_register.md`

### Stale Or Conflicting Docs

- `CYBERNETIC_LOOP_MAP.md:196-208` says recognition seed was never generated,
  while current code has RecognitionEngine plus context injection:
  `dharma_swarm/meta_daemon.py:1-13`,
  `dharma_swarm/context.py:1202-1217`.
- `LIVING_LAYERS.md:383-386` reportedly says Shakti -> Darwin routing is
  missing, while current code routes high-salience Shakti perceptions to Darwin
  pending proposals:
  `dharma_swarm/orchestrate_live.py:76-110`, `:797-814`,
  `dharma_swarm/evolution.py:3477-3503`.
- VSM governance docs say no explicit S3/S4 channel, while current code has
  GatePatternAggregator and Zeitgeist gate pressure:
  `docs/telos-engine/07_VSM_GOVERNANCE.md:476`,
  `dharma_swarm/vsm_channels.py:142-229`,
  `dharma_swarm/zeitgeist.py:273`.

### Fail-Open Or Softened Authority

- `dharma_swarm/witness.py:1-16` says witness does not block operations.
- `dharma_swarm/dharma_attractor.py:154-178` defaults checkpoint exceptions to
  PROCEED.
- `dharma_swarm/telos_gates.py:512-513` makes BHED_GNAN always pass.
- `dharma_swarm/telos_gates.py:667-704` treats Tier C largely as review.
- `dharma_swarm/organism.py:1193-1242` softens HOLD into sustained evidence
  before emergency action.
- `dharma_swarm/opportunity_dispatcher.py:30-41`, `:385-430` lets REVIEW
  proceed with warning pending real operator approval.

### Split Self-Model Stores

- Ontology DB.
- Runtime state DB.
- Organism memory.
- Recognition seed.
- Stigmergy marks.
- Corpus/policy.
- `.FOCUS`.
- Cascade history.
- Evolution archive.

UNKNOWN: what has final authority when these disagree.

### Schema And Ingestion Risks

Stigmergy mark schema uses fields such as `file_path`, `agent`, and
`observation`: `dharma_swarm/stigmergy.py:46-59`. Context ingestion reads hot
mycelium marks with keys such as `path`, `source`, and `description`:
`dharma_swarm/context.py:1068-1081`. This may indicate either a separate
mycelium schema or a mismatch. Treat as PARTIAL until traced.

### Measurement Gaps

- No single continuous Omega tuple reader was established.
- No continuous 7-STAR vector computation was established.
- No proof recurring marks automatically create gates.
- No proof branch/worktree demotion is recognition-driven.
- No proof all runtime mutations go through OntologyActionGateway.
- No proof outward-organ outcomes fully update recognition/Omega.

## Virtual File: `docs/vision_maps/future_dispatch_prompt.md`

Use this prompt for a future read-only dispatch if this map needs another
research pass:

```text
Dispatch 6 read-only subagents in parallel to deepen
`DHARMA_SWARM_MASTER_MAP.md`, keeping the final deliverable as one physical
file only. Do not create `docs/vision_maps/*`; treat those paths as virtual
sections nested inside the master file.

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
3. Omega/Attractor: C x S x A x T x M, 7-STAR, syntropic force.
4. Recognition/Self-model: ontology, runtime_state, recognition seed, R_V,
   ouroboros, causal behavior change.
5. Autopoiesis/Evolution: Darwin, Shakti, stigmergy, cascade, semantic
   attractors, gate crystallization.
6. Outward Organs: Loom/wiki_loom, VentureCell, opportunity loop, operator
   brief, product surfaces, Jagat Kalyan, GAIA.

After agents return, rewrite only `DHARMA_SWARM_MASTER_MAP.md`.
```

## Final Open Questions

- What is the minimum runtime event that counts as recognition?
- Which store is the authoritative self-model when stores conflict?
- Which classes of action must be impossible without ontology binding?
- What does S5 authority mean when the human is meta-S5 and the organism has
  internal kernel/gates/Gnani/identity S5?
- How does the system distinguish an organ from a tool, a wound from noise, and
  doctrine from runtime canon?
- Which outward outcomes update Omega rather than merely producing artifacts?
- What live measurement proves that self-recognition has become causal?

## Final Thesis

Dharma Swarm is not trying to become an autonomous code generator. It is trying
to become a recognized autonomous organism: a system whose actions arise from a
live understanding of its own invariant identity, dynamic motion, viability
state, whole-state trajectory, evolutionary metabolism, and outward telos.

The next conceptual bar is not more doctrine and not more selection. It is
causal self-recognition.
