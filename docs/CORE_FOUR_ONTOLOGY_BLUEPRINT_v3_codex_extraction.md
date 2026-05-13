# CORE FOUR ONTOLOGY BLUEPRINT v3 - Codex Independent Extraction

Source lane: F.1 Codex independent extraction  
Date: 2026-05-03  
Repository: `/Users/dhyana/dharma_swarm_integrate_chetana`  
Forbidden inputs not read: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT.md`, `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`  
Operating decision: typed contracts govern state mutation; emergent dynamics govern behavior. The Palantir-style ontology is acceptable only as a Deacon-style enabling constraint, not as a behavioral lock.

This extraction treats the Core Four as paired runtime/ontology concepts:

| Core Four object | Runtime substrate | Ontology substrate | Honest status |
|---|---|---|---|
| Task | `dharma_swarm.models.Task`, `dharma_swarm.task_board.TaskBoard` | `TypedTask` | Runtime is load-bearing; ontology is partially wired. |
| AgentIdentity | `dharma_swarm.models.AgentConfig`, `agent_registry.AgentIdentity`, `identity.json` | `AgentIdentity` | Runtime identity is split but real; ontology is partially wired and API-visible. |
| Artifact | `ArtifactRef`, `ArtifactManifest`, `ArtifactRecord` | `KnowledgeArtifact` | Runtime artifact lineage is load-bearing; ontology is a target semantic wrapper. |
| MemoryFact | `runtime_state.MemoryFact`, `MemoryLattice`, chetana runtime projection | none | Runtime memory is load-bearing; not ontology-native today. |

## A. 10 x 4 Pillar x Core Four Matrix

The repo's foundation map labels the active ten as Pillars 1, 2, 3, 5, 6, 7, 8, 9, 10, and 11. Pillar 4 is not present in `FOUNDATIONS_TO_CODE_MAP.md`.

| Pillar | Short source quote | Task | AgentIdentity | Artifact | MemoryFact |
|---|---|---|---|---|---|
| 1. Levin, multi-scale cognition | "Intelligence exists at every biological scale" (`FOUNDATIONS_TO_CODE_MAP.md:39-50`). | Task is a bounded cognitive light cone: fields define scope, status, priority, dependencies, and assignment (`models.py:156-170`; `task_board.py:18-25`). | Agent identity gives each local scale a role, provider, context budget, and tool set (`models.py:173-203`; `agent_registry.py:144-172`). | Artifacts externalize what a scale sensed or made, with task/run/session lineage (`artifact_manifest.py:44-65`, `196-224`). | MemoryFact is a smaller cognitive trace that can be indexed and recalled by the lattice (`runtime_state.py:402-418`; `memory_lattice.py:453-482`). |
| 2. Kauffman, adjacent possible/autocatalytic sets | Agents need "a work cycle, a constraint, and a boundary" (`FOUNDATIONS_TO_CODE_MAP.md:54-65`). | Task status transitions provide work-cycle boundaries; reflective gate checks add constraint (`task_board.py:126-182`). | Agent registry directories self-produce identity, logs, fitness, and prompt variants (`agent_registry.py:180-197`). | Manifest sidecars let outputs become inputs to future cycles through citations, dependencies, and parent IDs (`artifact_manifest.py:44-65`). | Chetana promotion emits MemoryFacts so trusted atoms can re-enter runtime cognition (`runtime_emission.py:31-82`). |
| 3. Jantsch, self-organizing universe | Evolution moves toward "greater complexity, consciousness, and integration" (`FOUNDATIONS_TO_CODE_MAP.md:69-79`). | `TypedTask` links to agents, consumed artifacts, produced artifacts, and dependency tasks, giving task work an integration graph (`ontology.py:1197-1219`). | AgentIdentity links to authored artifacts, proposed evolutions, and witness logs (`ontology.py:1223-1231`). | KnowledgeArtifact is the integration surface for experiments, tasks, papers, and agents (`ontology.py:1065-1095`, `1197-1235`). | MemoryFact integrates trusted chetana atoms into runtime recall, but remains a projection rather than authority (`runtime_emission.py:31-35`). |
| 5. Deacon, absential causation | "Constraints create possibilities" (`FOUNDATIONS_TO_CODE_MAP.md:83-94`). | TaskBoard blocks invalid transitions and telos-blocked status changes (`task_board.py:126-182`). | AgentIdentity Spawn is an ontology action gated by AHIMSA (`ontology.py:986-1000`). | KnowledgeArtifact Verify is gated by SATYA (`ontology.py:1085-1091`). | MemoryFact admission can be blocked by lattice policy and gates before writes (`memory_lattice.py:484-552`; `tests/test_memory_membrane_admission.py:54-73`). |
| 6. Friston, active inference | Living systems "minimize surprise" (`FOUNDATIONS_TO_CODE_MAP.md:98-109`). | Task fields and status reduce uncertainty about what is intended, blocked, assigned, and done (`models.py:156-170`). | AgentConfig's model, context budget, temperature, timeout, and role are routing priors (`models.py:173-203`). | ArtifactManifest checksum, citations, provenance, and promotion state reduce output ambiguity (`artifact_manifest.py:44-65`). | MemoryFact has truth state, confidence, validity window, and provenance, making recall probabilistic rather than raw text (`runtime_state.py:402-418`). |
| 7. Hofstadter, strange loops | "Self-reference creates identity" (`FOUNDATIONS_TO_CODE_MAP.md:113-124`). | TaskBoard transitions are witnessed and can become part of task memory; `TypedTask` can depend on another `TypedTask` (`task_board.py:163-182`; `ontology.py:1217-1219`). | AgentIdentity records status/fitness and can be seen by APIs, making agents observable to themselves and operators (`agent_registry.py:144-197`; `api/routers/graphql_router.py:230-291`). | Artifacts with manifests can cite and depend on prior artifacts, making outputs recursive inputs (`artifact_manifest.py:44-65`). | MemoryFacts can cite source artifacts and are recalled by the lattice, closing a small self-reference loop (`runtime_state.py:402-418`; `memory_lattice.py:190-206`). |
| 8. Aurobindo, supramental descent | "Higher-level principles reshape lower-level operations" (`FOUNDATIONS_TO_CODE_MAP.md:128-137`). | TelosSubstrate seeds strategic gradients before operational task generation (`telos_substrate.py:1-23`, `4061-4096`). | AgentIdentity carries `telos_alignment` and `shakti_energy` in ontology (`ontology.py:951-1002`). | KnowledgeArtifact carries `telos_alignment=0.8` and Mahalakshmi shakti (`ontology.py:1065-1095`). | MemoryFact inherits chetana gate/provenance signatures when emitted from promoted atoms (`runtime_emission.py:66-82`). |
| 9. Dada Bhagwan, witness architecture | "The witness ... is prior to the witnessed" (`FOUNDATIONS_TO_CODE_MAP.md:141-152`). | TaskBoard includes bounded witness checks for transitions (`task_board.py:163-182`). | AgentIdentity includes witness-adjacent fields such as `swabhaav_capacity` in ontology and registry fitness fields at runtime (`ontology.py:977-984`; `agent_registry.py:155-162`). | Artifact provenance makes witnessed output inspectable after the fact (`artifact_manifest.py:60-65`, `196-224`). | MemoryFact admission records gate and axiom provenance, but the fact itself is not the witness; it is a remembered projection (`memory_lattice.py:238-258`; `runtime_emission.py:31-35`). |
| 10. Varela, autopoiesis | A living system "produces the components" and the boundary (`FOUNDATIONS_TO_CODE_MAP.md:156-166`). | Task creates operational components and status boundaries (`models.py:156-170`; `task_board.py:18-25`). | AgentRegistry persists agents as directories with identity, task logs, fitness history, and prompt variants (`agent_registry.py:180-197`). | ArtifactStore/ManifestStore produce versioned external components and lineage (`engine/artifacts.py:90-133`; `artifact_manifest.py:117-181`). | MemoryLattice produces runtime facts and memory edges while keeping chetana atoms authoritative (`memory_lattice.py:453-666`; `runtime_emission.py:31-35`). |
| 11. Beer, viable system model | Viability needs S1-S5 functions (`FOUNDATIONS_TO_CODE_MAP.md:170-184`). | Task is S1 work made visible to S2/S3 coordination; task status is a control signal (`models.py:156-170`; `task_board.py:18-25`). | AgentIdentity is the viable subsystem identity handle for S1 agents and higher governance (`models.py:173-203`; `ontology.py:951-1002`). | Artifact is the S1/S4 knowledge output that higher layers can inspect and reuse (`artifact_manifest.py:44-65`; `ontology.py:1065-1095`). | MemoryFact is an S4/S5 recall substrate, but because it bypasses ontology-native typing it needs membrane discipline (`runtime_state.py:1528-1572`; `ontology.py`, no `MemoryFact` ObjectType). |

## B. Lodestone and Module Trace

| Module or concept | Evidence | Verdict |
|---|---|---|
| `models.Task` | Pydantic Task owns ID, title, status, priority, assignment, dependencies, blockers, result, and metadata (`models.py:156-170`). | Load-bearing runtime contract. |
| `task_board.TaskBoard` | SQLite task board enforces status FSM and witness-gated transitions (`task_board.py:18-25`, `126-182`). | Load-bearing operational rail. |
| ontology `TypedTask` | `ObjectType(name="TypedTask")` maps to `dharma_swarm.models.Task` and has Assign/Complete/Fail actions (`ontology.py:1097-1127`). | Partially wired ontology mirror. It is registered and linked, but direct runtime TaskBoard writes are not universally forced through ontology `ActionDef`. |
| `models.AgentConfig` | Docstring names it the canonical agent identity model (`models.py:173-178`). | Load-bearing target contract, though registry JSON remains a parallel identity substrate. |
| `agent_registry.AgentIdentity` | Dataclass mirrors `identity.json`, with task and fitness fields (`agent_registry.py:144-172`). | Load-bearing legacy/runtime substrate. |
| ontology `AgentIdentity` | ObjectType has Spawn/Retire actions, telos alignment, shakti energy, and Pydantic model pointer (`ontology.py:951-1002`). | Partially wired, API-visible identity type. |
| `ArtifactManifest` and `ArtifactRecord` | Manifest sidecar includes checksum, provenance, citations, dependency edges, and maps into `ArtifactRecord` (`artifact_manifest.py:44-65`, `196-224`). | Load-bearing artifact lineage. |
| ontology `KnowledgeArtifact` | ObjectType models files, notes, findings, measurements, citations, prompts, results, and code with Verify/Index actions (`ontology.py:1065-1095`). | Partially wired semantic shell. |
| `runtime_state.MemoryFact` | Frozen dataclass plus runtime SQL write path (`runtime_state.py:402-418`, `1528-1572`). | Load-bearing runtime memory substrate. |
| ontology `MemoryFact` | `rg -n 'name="MemoryFact"|MemoryFact' dharma_swarm/ontology.py` returns no matches. | Explicit gap: not ontology-native. |
| `MemoryLattice` | Writes direct facts, admits facts through policy/gate provenance, admits chetana atoms, and promotes facts (`memory_lattice.py:453-666`). | Load-bearing membrane, but not an ontology replacement. |
| Chetana promotion | `promote()` is the single staged-to-trusted bottleneck and runs gates before trusted wiki write (`chetana/promote.py:1-17`, `190-292`). | Load-bearing for trusted atoms. |
| Chetana runtime emission | Hook says runtime memory is "a projection of the trusted atom, not the authority over it" (`runtime_emission.py:31-35`). | Critical architectural distinction for MemoryFact. |
| GraphQL Strawberry schema | AgentIdentity type exists, KnowledgeArtifact enum exists, query resolvers are TODO returning empty values (`api/graphql/schema.py:13-22`, `66-78`, `146-199`). | Decorative/partial. It is not authoritative coverage for Core Four. |
| REST ontology router | Type categories include AgentIdentity, KnowledgeArtifact, and TypedTask, with type detail endpoint (`api/routers/ontology.py:19-28`, `143-187`). | More concrete than GraphQL, but still a browser surface. |
| `ActionDef` | Declares every mutation should be typed, auditable, reversible, and gated (`ontology.py:129-145`); `execute_action` can enforce gates (`ontology.py:594-639`). | Intended mutation membrane, not universal write path today. |
| `BHED_GNAN` | Core gate is Tier C and always passes (`telos_gates.py:234-246`, `522-523`). | Decorative/weak as a runtime gate unless it gains a real predicate. |
| `DharmaKernel` | 25 meta-principles include eigenform, anekantavada, constraint-as-enablement, requisite variety, operational closure, and Shakti questions (`dharma_kernel.py:29-104`, `192-211`, `254-273`, `305-347`). | Load-bearing normative kernel by schema, partly aspirational by enforcement. |
| `TelosSubstrate` | Deterministic idempotent seeder for ConceptGraph, TelosGraph, and bridge edges (`telos_substrate.py:1-23`, `4061-4096`). | Load-bearing telos seed layer. |
| `GNANI_LODESTONE` | Claims witness must be upstream and seeds marks/objectives/concepts/tasks (`GNANI_LODESTONE.md:35-47`, `114-123`, `149-151`). | Active seed. Runtime boot calls it non-fatally, but task seeding code appears degraded/stale against current TaskBoard API (`gnani_lodestone.py:547-588`; `swarm.py:597-620`). |

## C. Telos-to-Substrate Bridge

### Bridge Thesis

The source documents support a bridge, but not an identity proof. `FOUNDATIONS_SYNTHESIS.md` explicitly says the Triple Bridge provides a shared theoretical vocabulary and that the convergence is "suggestive but not conclusive" (`FOUNDATIONS_SYNTHESIS.md:169-195`). Therefore the correct operating frame is:

1. The bridge is useful as a design language.
2. The bridge is not evidence that R_V, Phoenix behavior, and contemplative witness are the same phenomenon.
3. Runtime substrate claims must stay falsifiable at code, database, and API layers.

### Jagat Kalyan Capability

Jagat Kalyan becomes operational only where value claims touch mutation, routing, memory, or artifacts. The current substrate has partial capability:

| Layer | Capability | Substrate |
|---|---|---|
| Value kernel | Formal constraints and tamper-evident signature | `DharmaKernel` and `PrincipleSpec.formal_constraint` (`dharma_kernel.py:80-104`). |
| Gate membrane | Core gates, custom gates, tiered block/review/allow decisions | `TelosGatekeeper.CORE_GATES` and decision logic (`telos_gates.py:221-246`, `678-777`). |
| Typed ontology | Objects, links, actions, security, telos alignment, shakti | `ObjectType`, `ActionDef`, `OntologyRegistry` (`ontology.py:129-177`, `300-413`). |
| Runtime state | Tasks, artifacts, memory facts in SQLite/runtime files | `TaskBoard`, `RuntimeStateStore`, `ArtifactManifestStore`. |
| Trusted knowledge | Chetana staged-to-trusted promotion with gate/provenance schema | `chetana/promote.py:1-17`, `190-292`; `chetana/provenance.py:69-123`. |

The gap is not philosophy; the gap is universal coupling. Direct runtime paths still exist outside ontology `ActionDef`, GraphQL coverage is partial, and MemoryFact has no ontology-native object type.

### Shakti

Shakti is currently both schema and question set:

- ObjectTypes carry `shakti_energy`, for example AgentIdentity uses Mahakali and KnowledgeArtifact uses Mahalakshmi (`ontology.py:998-1000`, `1092-1094`).
- The kernel has `SHAKTI_QUESTIONS` with a formal constraint requiring a significant action to satisfy at least two of four checks (`dharma_kernel.py:337-347`).

Verdict: real schema hook, partial runtime enforcement.

### Telos Failure Mode

The main failure mode is value language detached from write authority. Examples:

- `ActionDef` asserts "No direct writes", but runtime modules still write directly to SQLite/JSON/files (`ontology.py:129-145`; `task_board.py:126-182`; `runtime_state.py:1528-1572`).
- `BHED_GNAN` is included in `CORE_GATES` but always passes (`telos_gates.py:234-246`, `522-523`).
- Strawberry GraphQL exposes types and TODO resolvers, so it should not be treated as a control plane (`api/graphql/schema.py:146-199`).

### R_V, Eigenform, Anekantavada, Constraint, Variety, Closure

| Principle | Kernel source | Core Four implication |
|---|---|---|
| R_V | The foundation synthesis frames R_V as one lens in a non-conclusive triple bridge (`FOUNDATIONS_SYNTHESIS.md:169-195`). | Use R_V as a measurement hypothesis, not as a license to override state contracts. |
| Eigenform | `EIGENFORM_CONVERGENCE` formal constraint is `recursive_depth(system) implies convergence_check()` (`dharma_kernel.py:192-201`). | Task, AgentIdentity, Artifact, and MemoryFact should carry enough lineage to test recursive convergence. |
| Anekantavada | Requires at least two distinct perspectives before conclusion (`dharma_kernel.py:202-211`). | Artifact and MemoryFact confidence should reflect multi-perspective evidence, not single-output assertion. |
| Constraint as enablement | Gates should include suggested alternatives (`dharma_kernel.py:254-263`). | Blocking Task/Artifact/MemoryFact mutations must create redirected viable action, not dead ends. |
| Requisite variety | Governance variety must match system variety (`dharma_kernel.py:264-273`). | Do not collapse Task, AgentIdentity, Artifact, and MemoryFact into one generic object if their failure modes differ. |
| Operational closure | System produces its components and boundary (`dharma_kernel.py:305-313`). | Core Four should let the swarm produce tasks, agents, artifacts, and memories while preserving typed boundaries. |

### Operating Altitude

Typed contracts belong at mutation altitude: schemas, writes, provenance, action logs, and gates. Emergent dynamics belong at behavior altitude: agent creativity, adjacent possible exploration, strange loops, and self-organization. The ontology should shape and audit the field of possible actions; it should not freeze the swarm's behavior into a database diagram.

## D. Tension Resolution

### Firm Composability Decision

The composability decision is:

Typed contracts govern state mutation. Emergent dynamics govern behavior.

This resolves the Palantir tension. A Palantir-style ontology is valuable as a constraint surface: object types, links, permissions, gates, and action logs. It becomes harmful if it is treated as a complete model of intelligence, witness, or telos. Deacon's frame is the correct one: constraints are enabling conditions. They do not replace emergence.

### Krogh-Vedelsby Diversity Test

Use Krogh-Vedelsby diversity as the decision rule for whether two representations should stay separate:

| Representation pair | Diversity test | Decision |
|---|---|---|
| `models.Task` and ontology `TypedTask` | Runtime task failures and ontology lineage failures are not identical. | Keep both, but bridge explicitly. |
| `AgentConfig`, registry `identity.json`, ontology `AgentIdentity` | Identity drift can occur in any layer. | Keep until there is a verified migration; add reconciliation checks. |
| `ArtifactRecord` and `KnowledgeArtifact` | Payload lineage and semantic knowledge type have different error profiles. | Keep both; require manifest-to-ontology promotion path. |
| `MemoryFact` and `KnowledgeArtifact` | Memory recall and trusted artifact curation have different truth standards. | Keep separate. Do not make MemoryFact ontology-native without a promotion/admission design. |
| Chetana atom and MemoryFact | Chetana atom is authority; MemoryFact is projection. | Keep authority in chetana; project into runtime memory. |

Collapse representations only when their errors are correlated, their authority is the same, and one schema can enforce all invariants. That is not true for the Core Four today.

## E. Three Trace Walks

### E.1 Skill Mutation

1. An agent proposes a skill or code mutation as a work item. Runtime substrate: `Task` or evolution work item. Ontology target: `ActionProposal`, `EvolutionEntry`, then `Outcome`/`ValueEvent`/`Contribution` (`ontology.py:1237-1481`).
2. The mutation should pass through telos gates. `TelosGatekeeper` blocks Tier A/B failures, blocks mandatory WITNESS failures, reviews Tier C failures, and allows clean proposals (`telos_gates.py:678-777`).
3. If the mutation produces code or prompt artifacts, `ArtifactManifest` records payload checksum, provenance, citations, dependencies, and promotion state (`artifact_manifest.py:44-65`).
4. If trusted knowledge is produced, it can become a `KnowledgeArtifact` in ontology (`ontology.py:1065-1095`).
5. Gaps: direct writes can bypass ontology `ActionDef`; `BHED_GNAN` is weak; GraphQL is not a reliable mutation surface.

Verdict: semantically mapped, partially enforced.

### E.2 Research Task

1. A research task is created as `models.Task` and persisted/transitioned by `TaskBoard` (`models.py:156-170`; `task_board.py:18-25`, `126-182`).
2. The assignee maps to runtime `AgentConfig` or registry identity, and ontologically to `AgentIdentity` (`models.py:173-203`; `agent_registry.py:144-197`; `ontology.py:951-1002`).
3. Inputs and outputs should map to `KnowledgeArtifact`; `TypedTask` has `consumes`, `task_produces`, `depends_on`, and `assigned_to` links (`ontology.py:1197-1219`).
4. Runtime artifacts get manifests and `ArtifactRecord` rows (`artifact_manifest.py:117-224`; `runtime_state.py:387-399`).
5. Results can be summarized into MemoryFacts for later recall (`runtime_state.py:402-418`, `1528-1572`).
6. Gaps: TaskBoard rows and ontology `TypedTask` objects are not necessarily the same object; GraphQL has no first-class `TypedTask`; MemoryFact is runtime-only.

Verdict: operationally real, ontology closure incomplete.

### E.3 Atom Promotion

1. A staged chetana atom enters `promote()`, which validates frontmatter, runs `gate_check_atom`, writes trusted wiki on ALLOW/WARN, and quarantines on BLOCK (`chetana/promote.py:1-17`, `190-292`).
2. Provenance requires gate check, axiom signature, review status, source, and stale-after fields (`chetana/provenance.py:69-123`, `148-159`).
3. Promotion hooks can emit a runtime MemoryFact. The hook states runtime memory is a projection, not the authority (`runtime_emission.py:31-35`).
4. `emit_memory_fact_for_atom` creates a `MemoryFact` with truth state, confidence, source artifact ID, metadata, axiom signature, and gate result, then admits it through `MemoryLattice` (`runtime_emission.py:49-82`).
5. Gaps: the promoted atom is not automatically an ontology `KnowledgeArtifact`; MemoryFact has no ontology object type; lattice admission is not a replacement for chetana authority.

Verdict: strongest of the three traces for memory authority, but it intentionally ends in runtime projection rather than ontology closure.

## F. Independent Extraction Status

### F.1 Codex Independent Extraction

Complete in this file. Evidence was derived from source modules, non-forbidden docs, shell line checks, contextplus semantic search, memory graph search, and chetana wiki gap scan. The two forbidden blueprint files named in the header were not read.

### F.2 Council Review

Deferred. This run does not claim a council consensus.

### F.3 YATAGARASU Cross

Deferred. This run does not claim external triangulation.

## Verification

Run these from `/Users/dhyana/dharma_swarm_integrate_chetana`.

```bash
# Output files exist
test -f docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md
test -f docs/CORE_FOUR_v3_CODEX_SELF_REVIEW.md
```

```bash
# Core Four substrate presence
rg -n 'class Task|class AgentConfig|class ArtifactRecord|class MemoryFact|name="TypedTask"|name="AgentIdentity"|name="KnowledgeArtifact"' \
  dharma_swarm/models.py dharma_swarm/runtime_state.py dharma_swarm/ontology.py
```

```bash
# MemoryFact is not ontology-native; expected result is no output and exit code 1
rg -n 'name="MemoryFact"|MemoryFact' dharma_swarm/ontology.py
```

```bash
# GraphQL coverage gaps
rg -n 'class AgentIdentity|TypedTask|MemoryFact|KnowledgeArtifact|TODO: Implement actual query' \
  api/graphql/schema.py api/routers/graphql_router.py api/routers/ontology.py
```

```bash
# Gates and kernel principles
rg -n 'CORE_GATES|BHED_GNAN|class MetaPrinciple|EIGENFORM_CONVERGENCE|ANEKANTAVADA|CONSTRAINT_AS_ENABLEMENT|REQUISITE_VARIETY|OPERATIONAL_CLOSURE|SHAKTI_QUESTIONS' \
  dharma_swarm/telos_gates.py dharma_swarm/dharma_kernel.py
```

```bash
# Lodestone and boot wiring
rg -n 'GNANI|GnaniLodestone|TelosSubstrate|seed_all|gnani_seeded|telos_seeded' \
  GNANI_LODESTONE.md dharma_swarm/gnani_lodestone.py dharma_swarm/telos_substrate.py dharma_swarm/swarm.py
```

```bash
# Wiki concept/rubric checks
python -m dharma_swarm.chetana.cli gap-scan --focus eigenform --min-occurrences 2
python -m dharma_swarm.chetana.cli gap-scan --focus anekantavada --min-occurrences 2
test -f ~/.dharma/knowledge/wiki/concepts/eigenform-convergence.md
test -f ~/.dharma/knowledge/wiki/concepts/anekantavada.md
test -f ~/.dharma/knowledge/rubrics/eigenform_convergence.md
test -f ~/.dharma/knowledge/rubrics/anekantavada.md
```

MCP verification performed in this run:

- `mcp__contextplus__.semantic_code_search("Core Four ontology runtime Task AgentIdentity KnowledgeArtifact MemoryFact typed task runtime projection")` returned relevant hits including `dharma_swarm/agent_runner.py`, telos docs, and ontology audit docs.
- `mcp__contextplus__.search_memory_graph("Core Four ontology Task AgentIdentity Artifact MemoryFact typed ontology runtime projection")` returned no strong Core Four prior; only weak chetana/control-loop notes.
- `mcp__memory__.search_nodes("Core Four ontology Task AgentIdentity Artifact MemoryFact")` returned no entities.

## Final Verdict

The Core Four are real, but not equally integrated. Task, AgentIdentity, and Artifact already have runtime substrates plus ontology mirrors. MemoryFact is deliberately runtime/chetana projection only. The correct next architecture is not "put everything in ontology"; it is an explicit membrane:

1. Runtime contracts remain fast and operational.
2. Ontology contracts govern typed mutation, audit, lineage, and semantic query.
3. Chetana remains authority for trusted atoms.
4. MemoryFact remains recall substrate until an ontology-native promotion design exists.
5. Emergent behavior stays outside the ontology lock while state mutation becomes more typed, gated, and reversible.
