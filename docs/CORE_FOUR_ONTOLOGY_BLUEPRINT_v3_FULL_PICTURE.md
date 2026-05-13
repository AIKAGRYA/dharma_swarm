# Core Four Ontology Blueprint — v3 (Full Picture, three-layer, dual-extraction)

**Supersedes**: `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` (Layer 0 only, single-author) and `CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md` (Codex F.1 independent extraction).

**Layers**: 0 (code) + 1 (foundations) + 2 (telos).

**Triangulation status**:
- F.1 Codex independent extraction: ✅ complete (`docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md`)
- F.1 Claude prime synthesis (this document): ✅ complete
- F.1 Diff record (`~/.claude/plans/CLAUDE_CODEX_DIFF.md`): ✅ complete; 100% frame convergence, 47% finding-level convergence
- F.2 Council review (Maheshwari/Mahakali/Mahalakshmi/Mahasaraswati shakti-question screening): ⏳ pending v3 landing
- F.3 YATAGARASU cross-pollination flight: ⏳ deferred until F.2 returns

**Co-Authored-By**: Claude Opus 4.7 (1M context, prime synthesis + 10 pillar subagents on Sonnet) `<noreply@anthropic.com>`
**Co-Authored-By**: Codex (independent F.1 extraction + constructive debate refinements) `<noreply@openai.com>`

**Honest framing on agreement** (per Codex's pushback #1): the convergence between Claude and Codex is "independently convergent within a shared problem frame" — independence at the reading-path level (Codex did not read Claude v2 or pillar traces; Claude locked position before reading Codex output), but both operated on the same repository, same master prompt, same user intent. 100% frame-level convergence is a strong signal, not a proof. The 47% finding-level convergence is the more informative number — that's where decorrelated reading order surfaced complementary blind spots.

---

## §0 — Source Manifest

Every claim downstream traces to one of these. Status labels (per Codex pushback #5): **verified-now** / **stale-risk** / **needs-recheck** / **inferred-from-pillar-trace**.

### 0.1 Layer 0 sources (verified-now via direct file read this session)

| Tag | Path | Cite type |
|---|---|---|
| `[models.py]` | `dharma_swarm/dharma_swarm/models.py` | Pydantic shape contract; ~400 lines, 13 enums, 16 BaseModels |
| `[handoff.py]` | `dharma_swarm/dharma_swarm/handoff.py` | `Artifact` (8 subtypes), `Handoff`, `HandoffProtocol` |
| `[task_board.py]` | `dharma_swarm/dharma_swarm/task_board.py` | FSM transitions @ lines 18-25; SQLite schema @ lines 27-40 |
| `[ontology.py]` | `dharma_swarm/dharma_swarm/ontology.py` (1822 LOC) | Meta-schema + 8 ObjectTypes + 12+ LinkDefs + 15+ ActionDefs + execute_action @ 600-639 |
| `[runtime_state.py]` | `dharma_swarm/dharma_swarm/runtime_state.py` (1854 LOC) | 11 SQLite DDL tables; sample @ lines 30-200 |
| `[telos_gates.py]` | `dharma_swarm/dharma_swarm/telos_gates.py` (945 LOC) | CORE_GATES @ 224-236; check() signature @ 382-408; Variety Expansion Protocol @ 90-198 |
| `[dharma_kernel.py]` | `dharma_swarm/dharma_swarm/dharma_kernel.py` (427 LOC) | 25 MetaPrinciples @ 29-75; PrincipleSpec @ 95-348; SHA-256 signing @ 354-365 |
| `[chetana/provenance.py]` | `dharma_swarm_integrate_chetana/dharma_swarm/chetana/provenance.py` (318 LOC) | FrontmatterSchema, AtomProvenance, GateCheckRecord, compute_axiom_signature @ 148-159 |
| `[chetana/promote.py]` | same worktree | 11-step pipeline @ 1-17; PromoteResult @ 55-62 |
| `[graphql_schema]` | `dharma_swarm/api/graphql/schema.py` (215 LOC) | 8 ObjectTypeEnum, 4 SemanticTypeEnum, 6 LinkTypeEnum |

### 0.2 Layer 0 sources (Codex-found, verified-now)

| Tag | Path | Cite type |
|---|---|---|
| `[ontology.py:TypedTask]` | `ontology.py:1097-1127, 1197-1219` | Ontology-layer mirror of `models.Task`; carries `consumes`, `task_produces`, `depends_on`, `assigned_to` links |
| `[telos_substrate.py]` | `dharma_swarm/dharma_swarm/telos_substrate.py:1-23, 4061-4096` | Deterministic idempotent seeder for ConceptGraph + TelosGraph + bridge edges (NOT read by Claude) |
| `[gnani_lodestone.py]` | `dharma_swarm/dharma_swarm/gnani_lodestone.py:547-588` | Lodestone module; boot-wired by `swarm.py:597-620` (NOT read by Claude) |
| `[GNANI_LODESTONE.md]` | `GNANI_LODESTONE.md:35-47, 114-123, 149-151` (repo root, NOT under `dharma_swarm/` — corrected by Codex recheck 2026-05-04) | Lodestone document |
| `[artifact_manifest.py]` | `dharma_swarm/dharma_swarm/artifact_manifest.py:44-65, 196-224` | ArtifactManifest sidecar (checksum, provenance, citations, dependency edges); maps INTO ArtifactRecord |
| `[ontology.py:operator_brief_types]` | `ontology.py:1237-1481` | `ActionProposal`, `EvolutionEntry`, `Outcome`, `ValueEvent`, `Contribution` ObjectTypes |

### 0.3 Layer 1 sources (verified-now via 10 parallel pillar subagents)

| Tag | Path | Subagent |
|---|---|---|
| `[P01-LEVIN]` | `~/dharma_swarm/foundations/PILLAR_01_LEVIN.md` + trace at `docs/v3_pillar_traces/PILLAR_01_LEVIN_to_core_four.md` | Multi-scale agency, basal cognition, light cone |
| `[P02-KAUFFMAN]` | `PILLAR_02_KAUFFMAN.md` + trace | Autocatalytic sets, adjacent possible |
| `[P03-JANTSCH]` | `PILLAR_03_JANTSCH.md` + trace | Self-organizing universe, evolution as descent |
| `[P05-DEACON]` | `PILLAR_05_DEACON.md` + trace | Constraint as enablement |
| `[P06-FRISTON]` | `PILLAR_06_FRISTON.md` + trace | Active inference, free energy |
| `[P07-HOFSTADTER]` | `PILLAR_07_HOFSTADTER.md` + trace | Strange loops, eigenform |
| `[P08-AUROBINDO]` | `PILLAR_08_AUROBINDO.md` + trace | Four shaktis, supramental descent |
| `[P09-DADA-BHAGWAN]` | `PILLAR_09_DADA_BHAGWAN.md` + trace | Akram Vignan, Bhed Gnan, anekantavada |
| `[P10-VARELA]` | `PILLAR_10_VARELA.md` + trace | Autopoiesis, structural coupling, operational closure |
| `[P11-BEER]` | `PILLAR_11_BEER.md` + trace | VSM S1-S5, requisite variety, recursive viability |
| `[FOUNDATIONS-MAP]` | `dharma_swarm/FOUNDATIONS_TO_CODE_MAP.md` (Codex cite, NOT read by Claude) | Pillar-to-code mapping document |
| `[FOUNDATIONS-SYNTHESIS]` | `dharma_swarm/foundations/FOUNDATIONS_SYNTHESIS.md:169-195` (Codex cite) | The bridge thesis as "suggestive but not conclusive" |

**Note: Pillar 4 is intentionally absent.** Foundation map names active set as 1, 2, 3, 5, 6, 7, 8, 9, 10, 11.

### 0.4 Layer 2 sources (verified-now)

| Tag | Path |
|---|---|
| `[~/CLAUDE.md]` | `~/CLAUDE.md` — operating altitude, Transcendence Principle, Eleos pattern, fourth option |
| `[bridge.md]` | `~/.claude/cabinet/worldview/bridge.md` — **verified-now** (read by Codex post-council 2026-05-04: `confidence: 0.75`, `stale_after: 2026-06-01`, explicitly states the three mappings are not proven equivalent — consistent with v3's "design language and falsifiable hypothesis, not theorem" framing) |
| `[r-v-metric]` | `~/.dharma/knowledge/wiki/concepts/r-v-metric.md` (today's keystone weave) |
| `[active-inference]` | `~/.dharma/knowledge/wiki/concepts/active-inference.md` (today's keystone weave) |
| `[ONOB]` | `dharma_swarm_integrate_chetana/docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md` |
| `[MCS]` | `dharma_swarm_integrate_chetana/reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` (2026-04-26) |

### 0.5 Audit / map sources

| Tag | Path |
|---|---|
| `[AIU]` | `dharma_swarm/AGENT_IDENTITY_UNIFICATION.md` (872 LOC) |
| `[IMM]` | `dharma_swarm/INTERFACE_MISMATCH_MAP.md` (658 LOC) |
| `[MRM]` | `dharma_swarm/MODEL_ROUTING_MAP.md` (192 LOC) |
| `[CDS]` | `dharma_swarm_integrate_chetana/docs/governance/CANONICAL_DOC_STACK.md` (lines 53-92, the Memory Authorities table) |
| `[CK1..CK11]` | The 11 commits on `integrate/chetana-grand-memory-2026-05-02` (origin..HEAD) per observation #1739 |

### 0.6 Codex extraction artifacts

| Tag | Path |
|---|---|
| `[Codex-v3]` | `dharma_swarm_integrate_chetana/docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md` |
| `[Codex-self-review]` | `dharma_swarm_integrate_chetana/docs/CORE_FOUR_v3_CODEX_SELF_REVIEW.md` |
| `[Diff]` | `~/.claude/plans/CLAUDE_CODEX_DIFF.md` |

---

## §1 — The Architectural Frame (LOCKED — both agents agree)

> **Typed contracts govern state mutation. Emergent dynamics govern behavior. The Core Four are bridged, not flattened.**

### 1.1 What the frame says

A Palantir-style typed ontology (`ObjectType` + `LinkDef` + `ActionDef` per `[ontology.py:129-145]`) is the **right substrate for the audit, mutation, lineage, and gating layer**. It is the **wrong substrate for behavior, creativity, emergence, or autopoietic descent**. The two are not in conflict; they operate at different altitudes.

This resolves under Deacon's `CONSTRAINT_AS_ENABLEMENT` axiom (`[dharma_kernel.py:254-263]`): *"Constraints do not merely limit — they create the conditions for higher-order phenomena. Gates enable, not just block."* Typed contracts ARE the constraints that ENABLE emergent behavior. They give the swarm a stable shape to grow into without dictating where it grows.

### 1.2 What the frame is NOT

- **Not a proof of equivalence** between Hofstadter S(x)=x, Friston G=0, and contemplative eigenform. The bridge thesis at `[bridge.md]` and `[FOUNDATIONS-SYNTHESIS:169-195]` says explicitly: *"the convergence is suggestive but not conclusive."* v3 treats the bridge as design language and falsifiable hypothesis, not theorem (per Codex pushback #2).
- **Not a license to override state contracts using R_V or any other measurement.** R_V is a measurement hypothesis; runtime substrate claims must stay falsifiable at code, database, and API layers.
- **Not a mandate to lift every typed claim onto every layer.** The Krogh-Vedelsby diversity term from the Transcendence Principle in `[~/CLAUDE.md]` says: governance variety must match system variety. Collapsing representations whose error profiles differ destroys the diversity. The 5-question collapse test below operationalizes this.

### 1.3 The 5-question collapse test (Codex contribution; LOCKED)

For any pair of representations (e.g., `models.Task` and ontology `TypedTask`, or `chetana.AtomProvenance` and `runtime_state.MemoryFact.provenance_json`), apply this test:

1. **Same authority?** — does one own writes, or do both write independently?
2. **Same failure mode?** — does breaking one break the other in identical ways?
3. **Same lifecycle?** — same creation, transition, retirement events?
4. **Same rollback / provenance need?** — same audit and reversibility requirements?
5. **Same query surface?** — same set of consumers asking the same questions?

**Collapse only if all 5 match.** If any one differs, **bridge** instead. Bridges are explicit pairs of (writer-side projection + reader-side reconciliation check). This is Krogh-Vedelsby diversity made operational at the schema layer.

### 1.4 What this means for the substrate-nativeness gap

The audit `[MCS §1, ONOB §1]` estimates substrate-nativeness at **~10–15%**. **This is an audit estimate, not a measured invariant.** No denominator and no scoring rubric is published. v3 treats the number as directionally correct (per Codex pushback #4) — most live runtime work bypasses typed contracts. The fix is not to lift everything onto Pydantic; it is to bridge the existing contracts so the typed ones become the canonical write surface AND the runtime ones remain fast.

---

## §2 — The Substrate Stack

Per `[MCS §6]`, the system has six load-bearing substrates for Core Four state. Layered, not redundant. Any blueprint that names "the Task model" without naming all six is wrong.

```
Layer                          | Owns                              | Path
-------------------------------|-----------------------------------|------------------------
1. Pydantic shape              | in-memory validation              | dharma_swarm/models.py
2. SQLite structured spine     | live control-plane state          | ~/.dharma/state/runtime.db
                               |                                   | (runtime_state.RuntimeStateStore)
3. JSONL append-only ledger    | session trace                     | ~/.dharma/sessions/*.jsonl
                               |                                   | (session_ledger.SessionLedger)
4. Typed ontology objects      | semantic + actions + security     | ontology.OntologyRegistry
                               |                                   | (8 ObjectTypes, 12+ LinkDefs,
                               |                                   |  15+ ActionDefs)
5. Chetana atom layer          | trusted promoted knowledge        | ~/.dharma/knowledge/wiki/
                               |                                   | (chetana/provenance.py)
6. GraphQL wire surface        | dashboard projection              | api/graphql/schema.py
                               |                                   | [DECORATIVE — resolvers TODO]
```

Plus two boot/seed surfaces Codex surfaced and Claude missed:

```
TelosSubstrate (idempotent seeder)  | ConceptGraph + TelosGraph + bridge edges seeded at boot
GnaniLodestone (active boot module) | Marks/objectives/concepts/tasks seeded; task seeding
                                    | code is degraded against current TaskBoard API
```

---

## §3 — The Core Four — substrate-anchored definitions, three layers each

For each Core Four object, three layers: **Layer 0 (substrate locations)**, **Layer 1 (foundations / pillar / kernel anchor)**, **Layer 2 (telos / bridge claim)**. Per Codex pushback #2: each claim is labelled **factual** vs **architectural-interpretation**.

### 3.1 `Task`

#### Layer 0 — substrates

| Layer | Where | Cite |
|---|---|---|
| Pydantic | `class Task(BaseModel)` | `[models.py:156-170]` |
| SQLite (board) | `tasks` + `task_dependencies` | `[task_board.py:27-40]` |
| SQLite (spine) | `task_claims`, `delegation_runs` | `[runtime_state.py:42-74]` |
| JSONL ledger | `SessionLedger` lifecycle events | `[MCS §6]` |
| Ontology | `TypedTask` ObjectType with consumes/task_produces/depends_on/assigned_to links | `[ontology.py:1097-1127, 1197-1219]` |
| GraphQL | not surfaced today (TODO) | `[graphql_schema]` |

**FSM (factual)** `[task_board.py:18-25]`:
```
PENDING → {ASSIGNED, CANCELLED, FAILED}
ASSIGNED → {RUNNING, CANCELLED, PENDING}
RUNNING → {COMPLETED, FAILED, CANCELLED}
COMPLETED → {}                              # terminal
FAILED → {PENDING}                          # retryable
CANCELLED → {PENDING}                       # retryable
```
Illegal transitions raise `TaskBoardError`.

#### Layer 1 — foundations anchor

- **Primary pillars**: Friston (active inference; EFE routing in `orchestrator.py:951` makes Task selection minimize G = Risk + Ambiguity per `[P06-FRISTON]`), Beer (Task is S1 work made visible to S2/S3 coordination per `[P11-BEER]`), Hofstadter (`LoopResult.eigenform_reached` at `[models.py:359]` per `[P07-HOFSTADTER]`), Kauffman (Task status transitions provide work-cycle boundaries per `[P02-KAUFFMAN]`).
- **Kernel axioms gating Task mutations**: `EIGENFORM_CONVERGENCE` (Hofstadter, formal_constraint `recursive_depth(system) implies convergence_check()` `[dharma_kernel.py:192-201]`), `ACTIVE_INFERENCE` (Friston, `[dharma_kernel.py:285-294]`), `CONSTRAINT_AS_ENABLEMENT` (Deacon — TaskBoard blocks invalid transitions per `[task_board.py:126-182]`), `REQUISITE_VARIETY` (Beer, requires `len(available_agents) >= len(distinct_task_types)` `[dharma_kernel.py:264-273]`).
- **Telos gates fired on every Task mutation**: AHIMSA (Tier A), VYAVASTHIT (force-detection, Tier C), REVERSIBILITY (Tier C), WITNESS (Tier C, MANDATORY for `before_write/before_complete/before_pivot/before_git` think-phases).

#### Layer 2 — telos

- **Bridge claim**: a Task whose `eigenform_reached` AND `fitness_plateau` both fire is convergent in BOTH Hofstadter's S(x)=x sense AND Kauffman's adjacent-possible-exhausted sense. Whether these are the same convergence empirically is the bridge research question (`[r-v-metric]`, `[active-inference]`).
- **Jagat Kalyan service**: Tasks gate-checked via the 11 CORE_GATES are the unit at which dharmic constraint enters operational work. A task that passes CONSENT + AHIMSA + SATYA carries cryptographic-grade dharmic provenance once `axiom_signature` is computed on its result artifact.
- **Failure mode at telos**: if the Task substrate accepts mutations that bypass gates (the audit's "85-90% non-native"), the dharmic accounting is leaky — actions occur without their gate provenance, breaking the audit trail to telos.

#### Strict-typed migration target — **factual** vs **architectural-interpretation**

**Factual** (verified-now): `Task.metadata: dict[str, Any]` at `[models.py:170]`. Same dirt at SQLite layer (`tasks.metadata TEXT NOT NULL DEFAULT '{}'` `[task_board.py:33]`). `Task.assigned_to: Optional[str]` is a bare string ID at `[models.py:163]`. `Task.created_by: str = "system"` is a sentinel string at `[models.py:164]`.

**Architectural interpretation**: split `metadata` into `routing: TaskRouting`, `stigmergy: StigmergySalience`, `tool_hints: ToolHints`. **Apply 5-question collapse test before committing to specific field locations**: `routing` lives on Task (same authority as Task lifecycle), `stigmergy` may live on Task OR be a separate edge into StigmergyStore (different authority — collapse fails Q1). Decision: bridge, not collapse. `Task.routing` becomes a typed pointer to a `TaskRouting` record; `StigmergySalience` stays in StigmergyStore with a typed back-reference.

---

### 3.2 `AgentIdentity`

#### Layer 0 — substrates (THE FRAGMENTATION)

**Factual**: there are SEVEN AgentIdentity-shaped surfaces today, not one. Per `[AIU §1]` field-by-field crosswalk:

| # | Surface | Type | Cite |
|---|---|---|---|
| 1 | `startup_crew.py` dict literal | bare dict | startup_crew.py |
| 2 | `persistent_agent.PersistentAgent.__init__` | enum-typed kwargs | persistent_agent.py:51-52 |
| 3 | `autonomous_agent.AgentIdentity` | dataclass, bare strings | autonomous_agent.py:210-224 |
| 4 | `profiles.AgentProfile` | Pydantic, bare strings | profiles.py |
| 5 | `api/routers/agents.py` | ontology props dict | api/routers/agents.py |
| 6 | GraphQL `AgentIdentity` (different fields: kaizenops_id, telos_alignment, witness_quality, shakti_energy) | Strawberry type | `[graphql_schema:67-79]` |
| 7 | Ontology `_AGENT_IDENTITY` ObjectType (full PSMV+constitutional+ephemeral role enum, swabhaav_capacity, fitness_average) | ObjectType | `[ontology.py:951-1002]` |

Codex names a subset (4-5) at `[Codex-v3]` line 14: "AgentConfig, registry AgentIdentity, identity.json, ontology AgentIdentity." Both readings converge on the fragmentation; Claude's enumeration is more granular per pillar work.

**MCS §6 settled truth**: *"Runtime agent constructor identity: `models.AgentConfig`. Runtime agent status: `models.AgentState`."* — `AgentConfig` is current truth at runtime, `AgentIdentity` is the unification target per `[AIU]`.

#### Layer 1 — foundations anchor

- **Primary pillars**: Beer (the constitutional 6 roles `OPERATOR/ARCHIVIST/RESEARCH_DIRECTOR/SYSTEMS_ARCHITECT/STRATEGIST/WITNESS` at `[models.py:57-63]` ARE Beer's S1-S5+Algedonic per `[P11-BEER]`), Levin (the 18-value `AgentRole` enum is a cognitive-light-cone aperture taxonomy per `[P01-LEVIN]`), Aurobindo (`shakti_energy` field on every ObjectType per `[ontology.py:170]` is the four-shaktis as type system primitive per `[P08-AUROBINDO]`), Dada Bhagwan (`swabhaav_capacity` field per `[ontology.py:977-984]` is witness stance capacity per `[P09-DADA-BHAGWAN]`).
- **Kernel axioms gating AgentIdentity mutations**: `MULTI_SCALE_AGENCY` (Levin), `RECURSIVE_VIABILITY` (Beer), `SHAKTI_QUESTIONS` (Aurobindo), `OBSERVER_SEPARATION` (Dada Bhagwan), `OPERATIONAL_CLOSURE` (Varela).
- **Telos gate on creation**: `Spawn` action gated by `AHIMSA` (Tier A) per `[ontology.py:986-993]`.

#### Layer 1 gap (cross-pillar finding from `[P09-DADA-BHAGWAN]` and `[P08-AUROBINDO]`)

**Factual**: `swabhaav_capacity`, `witness_quality`, `telos_alignment`, `shakti_energy` exist as PropertyDef on the `_AGENT_IDENTITY` ObjectType `[ontology.py:951-1002]`.

**Factual**: `AgentConfig` Pydantic `[models.py:173-203]` has zero of these fields.

**Architectural interpretation**: the witness/shakti/telos contract lives in the typed ontology layer; the runtime types that govern ~85-90% of live traffic carry none of it. v3 calls this a **bridge gap**, not a collapse target — applying the 5-question test:
- Same authority? Yes (both describe one logical agent).
- Same failure mode? No — ontology drift vs runtime drift have different consequences.
- Same lifecycle? No — ontology objects persist via `OntologyRegistry`, AgentConfig instances via in-memory + identity.json.
- Same rollback / provenance? No — different audit trails.
- Same query surface? Partial — API can read both, but most consumers read Pydantic.

3 of 5 fail → bridge, do not collapse. Fix is **typed projection** from ontology AgentIdentity → AgentConfig fields, with reconciliation check at boundaries.

#### Layer 2 — telos

- **Jagat Kalyan service**: an agent without `telos_alignment` cannot be filtered for dharmic safety at routing time. The contract for "dharma-aligned action" requires the agent's telos signature. Currently this is structurally absent on the runtime side.
- **Bridge claim**: Levin's multi-scale agency (each scale has autonomous goals AND respects constraints from N+1) is operationally encoded as the 6-role constitutional topology PLUS the `AgentRole` 18-value enum providing scale-specific cognitive apertures. Failure mode: `autonomous_goals` field is in zero of 7 surfaces per `[P01-LEVIN]` — the Levin axiom is signed in the kernel and runtime-absent.

---

### 3.3 `Artifact`

#### Layer 0 — substrates (the THREE-LAYER artifact model)

**Factual**: artifacts have three distinct substrates with different vocabularies:

| Substrate | Concept | Cite |
|---|---|---|
| Handoff layer | `Artifact` (8 typed subtypes: CODE_DIFF, ANALYSIS, TEST_RESULTS, CONTEXT, PLAN, FILE_LIST, ERROR_REPORT, METRIC), `Handoff.artifacts: list[Artifact]`, JSONL persistence | `[handoff.py:27-63]` |
| Runtime spine — record | `artifact_records` table with payload_path, manifest_path, checksum, parent_artifact_id, promotion_state | `[runtime_state.py:89-103]` |
| Runtime spine — manifest sidecar | `ArtifactManifest` carries checksum, provenance, citations, dependency edges; maps INTO `ArtifactRecord` | `[artifact_manifest.py:44-65, 196-224]` |
| Runtime spine — links | `artifact_links` table for typed N:M edges between artifacts | `[runtime_state.py:105-113]` |
| Ontology | `KnowledgeArtifact` ObjectType with Verify/Index actions; `Experiment.Archive` action `creates=["KnowledgeArtifact"]` | `[ontology.py:1065-1095, 914-916]` |

Codex caught the distinction between `ArtifactManifest` (sidecar) and `ArtifactRecord` (row) at `[Codex-v3]` line 45 — Claude v2 had `artifact_records` but missed the manifest sidecar layer.

#### Vocabulary mismatch (factual)

`Handoff.Artifact.artifact_type` is an 8-value enum at `[handoff.py:27-37]`. `runtime_state.artifact_records.artifact_kind` is a free string at `[runtime_state.py:95]`. The two vocabularies don't agree. Per `[MCS gap #1]`: *"Completed tasks do not yet prove `artifact_records` are created from `_persist_result()`."*

#### Layer 1 — foundations anchor

- **Primary pillars**: Kauffman (CatalyticGraph EDGE_TYPES `enables/validates/attracts/funds/improves` are Artifact-to-Artifact catalytic relations per `[P02-KAUFFMAN]`), Hofstadter (`axiom_signature` SHA-256 binding atom content + active kernel signature per `[chetana/provenance.py:148-159]` is a Gödelian self-reference signature per `[P07-HOFSTADTER]`), Aurobindo (KnowledgeArtifact `shakti_energy = MAHALAKSHMI` per `[ontology.py:1092-1094]`).
- **Kernel axioms**: `PROVENANCE_INTEGRITY` (`output.provenance is not None for all emitted artifacts` `[dharma_kernel.py:185-190]`), `AUTOCATALYTIC_CLOSURE` (Kauffman, `[dharma_kernel.py:233-242]`).

#### Layer 1 gap (operational defect — `[P02-KAUFFMAN]`, status: **verified-now**)

**Factual**: `dharma_swarm/catalytic_graph.py` and `runtime_state.artifact_records` are completely disconnected stores. Artifact production events never auto-populate the catalytic graph.

**Architectural interpretation**: the autocatalytic-set autonomy signal Kauffman names (largest SCC / node count / phase transition) runs only on manually-seeded data, not live system behavior. The pillar's claim that artifacts catalyze each other through typed edges is structurally absent at runtime. Bridge needed: `record_artifact()` should emit a CatalyticEdge into `~/.dharma/meta/catalytic_graph.json`.

#### Layer 2 — telos

- **Bridge claim**: an artifact is dharmically-grounded iff its `axiom_signature` verifies against the kernel manifest at the time of its production. The Hofstadter eigenform signature + Friston self-evidencing converge here: every artifact that promotes (chetana atom path) carries a recursive self-witness. Failure mode: artifacts produced via direct path (no manifest) carry no signature, no audit trail, no telos provenance.

---

### 3.4 `MemoryFact`

#### Layer 0 — substrates (Codex pushback #2 applied here precisely)

**Factual** (verified by Codex):
- `runtime_state.MemoryFact` exists as a frozen dataclass and SQL write path `[runtime_state.py:402-418, 1528-1572]`.
- `chetana.FrontmatterSchema` + `AtomProvenance` exist as the trusted-atom Pydantic schemas at `[chetana/provenance.py:84-122]`.
- `name="MemoryFact"` returns NO matches in `dharma_swarm/ontology.py` (Codex verification command at `[Codex-self-review]` line 72).
- `MemoryEntry` exists as a legacy Pydantic class in `[models.py:267-276]` with `MemoryLayer` enum (IMMEDIATE/SESSION/DEVELOPMENT/WITNESS/META).

**Architectural interpretation** (per Codex's framing):
- MemoryFact is **deliberately runtime/projection only**, NOT ontology-native. Codex extraction §E.3 line 167: *"Promotion hooks can emit a runtime MemoryFact. The hook states runtime memory is a projection, not the authority."*
- Chetana atoms are the AUTHORITY for trusted memory. MemoryFact (runtime) is a projection of that authority into the runtime spine. The 5-question collapse test fails on Q1 (different authority) → bridge, do not collapse.

#### The 7 Memory Authorities (verbatim from `[CDS:53-67]`, Claude pillar work)

This table is authoritative; Codex's E.3 trace converges on it without citing it directly. Lock as v3 canonical.

| # | Authority | Class | Owner module | Write API | Forbidden bypass |
|---|---|---|---|---|---|
| 1 | Register / conscience marks | Write | `register_disciplines.py` | `make_register_mark()` + `write_register_mark()` | direct append to `~/.dharma/stigmergy/register_marks.jsonl` |
| 2 | Runtime facts and edges | Write | `runtime_state.RuntimeStateStore` | `record_memory_fact()`, `record_memory_edge()` (until membrane facade lands) | SQL writes to `memory_facts`/`memory_edges` outside the store |
| 3 | Episodes / events | Write | `engine/event_memory.EventMemoryStore` | `ingest_envelope()` | runtime event JSONL or SQL outside the store |
| 4 | Trusted semantic atoms | Write | `chetana/promote.py` | `promote()` with provenance + gate check | promote without `gate_check_atom()` or in-place mutation |
| 5 | Context admission | **Project** | `memory_lattice.py` + `context_compiler.py` | `MemoryLattice.recall()` today; `compile_memory_context()` post-membrane | hand-query underlying stores for prompt context |
| 6 | Vector / graph / palace / dashboard views | **Project** | downstream readers | read-only projections | claim upstream truth ownership |
| 7 | Distillers (drift, witness, causal, revive, decay, semantic bridge) | **Distill** | per-module producer | emit `RegisterMark` via #1 or staged atom via #4 | mutate trusted state directly |

#### Chetana `promote()` pipeline (the strongest substrate-native operation, per both readings)

11-step bottleneck `[chetana/promote.py:1-17]`:
1. Read staged atom (frontmatter + body)
2. Validate frontmatter against chetana schema
3. Run `gate_check_atom()` — telos gates on body content
4. On BLOCK: write rejected-atom audit row, leave staged file alone
5. On WARN: write trusted with `review_status='staged'` (still needs human approval)
6. On ALLOW + `auto_promote=True`: write `review_status='auto_promoted'`
7. On ALLOW + `auto_promote=False` (default): write `review_status='staged'`
8. Compute `axiom_signature`, set `provenance.promoted_at` + `promoted_by`
9. Write trusted file to `~/.dharma/knowledge/wiki/concepts/<slug>.md`
10. Delete staging file iff write succeeded AND result != BLOCK
11. Return `PromoteResult` with paths + decision

Per Codex E.3 verdict (line 171): *"strongest of the three traces for memory authority, but it intentionally ends in runtime projection rather than ontology closure."* Per `[P10-VARELA]`: this pipeline IS Varela's autopoietic self-production loop already implemented — the system produces the atoms that constitute its organizational memory, kernel-co-signed.

#### Layer 1 — foundations anchor

- **Primary pillars**: Varela (chetana promote = autopoiesis operationalized per `[P10-VARELA]`), Dada Bhagwan (`witness_quality` field + `axiom_signature` = EIGENFORM_CONVERGENCE operational per `[P09-DADA-BHAGWAN]`), Friston (chetana promote = self-evidencing act; `confidence` field should be dynamic precision per `[P06-FRISTON]`), Deacon (`gate_check_atom()` IS constraint-as-enablement per `[P05-DEACON]`).
- **Kernel axioms**: `PROVENANCE_INTEGRITY` (`output.provenance is not None for all emitted artifacts`), `OPERATIONAL_CLOSURE` (Varela), `EIGENFORM_CONVERGENCE` (Hofstadter+Dada Bhagwan), `ANEKANTAVADA` (≥2 distinct perspectives before conclusion).

#### Layer 2 — telos

- **Bridge claim**: every promoted MemoryFact carries (`gate_check`, `axiom_signature`, `kernel_manifest_ref`). Failure mode: a fact produced without this triple has no provenance to telos; it's a belief without dharmic accounting. The chetana promote pipeline is the operational definition of "dharma-grounded knowledge production" in dharma_swarm.

---

## §4 — Explicit Links — the Graph

### 4.1 LinkDef contract `[ontology.py:113-127]` (factual)

```python
class LinkDef(BaseModel):
    name: str
    source_type: str
    target_type: str
    cardinality: LinkCardinality      # 1:1, 1:N, N:1, N:M
    required: bool = False
    inverse_name: str = ""              # auto-registered inverse
    description: str = ""
```

### 4.2 Foreign-key edges in `runtime_state.py` (verified-now, 17 edges)

| From table | Column | To table | Cardinality | DDL line |
|---|---|---|---|---|
| `task_claims` | `task_id` | `tasks` | N:1 | `[runtime_state.py:42-56]` |
| `task_claims` | `agent_id` | (agent registry) | N:1 | " |
| `task_claims` | `session_id` | `sessions` | N:1 | " |
| `delegation_runs` | `task_id` | `tasks` | N:1 | `[runtime_state.py:58-74]` |
| `delegation_runs` | `claim_id` | `task_claims` | N:1 | " |
| `delegation_runs` | `parent_run_id` | `delegation_runs` (recursive) | N:1 | " |
| `delegation_runs` | `current_artifact_id` | `artifact_records` | N:1 | " |
| `delegation_runs` | `assigned_by`, `assigned_to` | (agent) | N:1 | " |
| `artifact_records` | `task_id`, `run_id`, `session_id` | tasks/runs/sessions | N:1 | `[runtime_state.py:89-103]` |
| `artifact_records` | `parent_artifact_id` | `artifact_records` (lineage) | N:1 | " |
| `artifact_links` | `from_artifact_id`, `to_artifact_id` | `artifact_records` | N:M | `[runtime_state.py:105-113]` |
| `memory_facts` | `source_event_id` | `session_events` | N:1 | `[runtime_state.py:115-132]` |
| `memory_facts` | `source_artifact_id` | `artifact_records` | N:1 | " |
| `memory_edges` | `from_fact_id`, `to_fact_id` | `memory_facts` | N:M | `[runtime_state.py:134-144]` |
| `context_bundles` | `task_id`, `run_id`, `session_id` | tasks/runs/sessions | N:1 | `[runtime_state.py:146-159]` |
| `operator_actions` | `task_id`, `run_id`, `session_id` | tasks/runs/sessions | N:1 | `[runtime_state.py:161-172]` |
| `session_events` | `task_id`, `run_id`, `agent_id`, `session_id` | tasks/runs/agents/sessions | N:1 | `[runtime_state.py:174-187]` |

### 4.3 Ontology-layer typed edges (per `[Codex-v3]` and `[ontology.py:1197-1219]`)

`TypedTask` ObjectType carries explicit links: `consumes`, `task_produces`, `depends_on`, `assigned_to`. AgentIdentity ObjectType links to authored artifacts, proposed evolutions, witness logs `[ontology.py:1223-1231]`. KnowledgeArtifact links to experiments, tasks, papers, agents `[ontology.py:1065-1095]`.

### 4.4 The 5 representation pairs and their collapse-test verdicts (Codex contribution, LOCKED)

| Pair | Q1 authority | Q2 failure | Q3 lifecycle | Q4 provenance | Q5 query | Verdict |
|---|---|---|---|---|---|---|
| `models.Task` vs ontology `TypedTask` | different | different | different | different | different | **bridge** |
| `AgentConfig` + registry + ontology `AgentIdentity` | different | different | different | different | overlap | **bridge with reconciliation** |
| `ArtifactRecord` vs `KnowledgeArtifact` | different | different | different | different | different | **bridge with manifest-to-ontology promotion path** |
| `MemoryFact` vs `KnowledgeArtifact` | different | different | different | different | different | **keep separate (no collapse)** |
| Chetana atom vs `MemoryFact` | atom=authority, fact=projection | different | different | different | different | **chetana stays authoritative; MemoryFact is projection** |

Result: NO COLLAPSES. Five bridges. The Krogh-Vedelsby diversity term is preserved.

### 4.5 GraphQL `LinkTypeEnum` `[graphql_schema:31-37]` (decorative, TODO resolvers)

`LEFT_BY | SYNTHESIZES | AUDITS | BRIDGES | REFERENCES | INFORMS` — only 6 typed edge kinds at the wire surface. `BelongsTo` / `AssignedTo` / `DependsOn` / `BlockedBy` (the natural Task edges) are absent. Wire surface is impoverished relative to the SQL FKs and the ontology layer. Graveyard entry.

---

## §5 — Authorized Actions

### 5.1 ActionDef contract `[ontology.py:129-145]`

```python
class ActionDef(BaseModel):
    name: str
    object_type: str
    description: str = ""
    input_params: dict[str, str]            # untyped — see §11 graveyard
    modifies: list[str]
    creates: list[str]
    requires_approval: bool = False
    telos_gates: list[str]
    is_deterministic: bool = True
```

### 5.2 ActionExecution audit record `[ontology.py:210-224]`

Carries `lineage_inputs` and `lineage_outputs` lists — lineage is first-class in the schema.

### 5.3 Dispatch flow `[ontology.py:600-639]` (LOCKED — already-implemented action layer)

```
1. Look up ActionDef for (object_type, action_name)
2. Build ActionExecution
3. If gate_check provided AND action.telos_gates is non-empty:
   - run gate_check; if any returns BLOCK → execution.result="blocked"
4. If object_type.security.telos_required AND no gate_check → blocked
5. Otherwise: execution.result="success"
6. Append to _action_log
```

This IS the "Action layer" from v1's invented spec — it already exists. v3's job is to recognize it, not redesign it.

### 5.4 Sample ActionDefs registered today

| ObjectType | Actions | Telos gates | Cite |
|---|---|---|---|
| ResearchThread | `Activate`, `Pause` | `MAHESHWARI` | `[ontology.py:874-880]` |
| Experiment | `Design`, `Run`, `Archive` | `MAHASARASWATI`, `AHIMSA+SATYA`, — | `[ontology.py:905-916]` |
| Paper | `Audit`, `Submit` | `SATYA`, `SATYA+MAHASARASWATI` | `[ontology.py:937-944]` |
| AgentIdentity | `Spawn`, `Retire` | `AHIMSA`, — | `[ontology.py:986-993]` |
| KnowledgeArtifact | `Verify`, `Index` | `SATYA`, — | `[ontology.py:1065-1095]` |
| TypedTask | `Assign`, `Complete`, `Fail` | (per `[Codex-v3]` line 41) | `[ontology.py:1097-1127]` |

`create_dharma_registry` registers 8 ObjectTypes, 12 LinkDefs (24 with inverses), 15 ActionDefs `[ontology.py:843]`.

### 5.5 The 11 telos gates (factual, `[telos_gates.py:224-236]`)

```python
CORE_GATES: dict[str, GateTier] = {
    "AHIMSA":        GateTier.A,
    "SATYA":         GateTier.B,
    "CONSENT":       GateTier.B,
    "VYAVASTHIT":    GateTier.C,
    "REVERSIBILITY": GateTier.C,
    "SVABHAAVA":     GateTier.C,
    "BHED_GNAN":     GateTier.C,
    "WITNESS":       GateTier.C,
    "ANEKANTA":      GateTier.C,
    "DOGMA_DRIFT":   GateTier.C,
    "STEELMAN":      GateTier.C,
}
```
Plus the Variety Expansion Protocol via `GateRegistry` (propose/approve/reject/load_approved) at `[telos_gates.py:90-198]`. Approved custom gates load at runtime alongside the 11 cores.

### 5.6 The 25 kernel axioms organized by foundation theme `[dharma_kernel.py:29-75]`

```
Original 10 (Safety & Ethics Core):
  OBSERVER_SEPARATION, EPISTEMIC_HUMILITY, UNCERTAINTY_REPRESENTATION,
  DOWNWARD_CAUSATION_ONLY, POWER_MINIMIZATION, REVERSIBILITY_REQUIREMENT,
  MULTI_EVALUATION_REQUIREMENT, NON_VIOLENCE_IN_COMPUTATION,
  HUMAN_OVERSIGHT_PRESERVATION, PROVENANCE_INTEGRITY

Self-Reference & Identity (Hofstadter, Dada Bhagwan):
  EIGENFORM_CONVERGENCE, ANEKANTAVADA, TRIPLE_MAPPING

Creative Agency (Levin, Kauffman):
  MULTI_SCALE_AGENCY, AUTOCATALYTIC_CLOSURE, ADJACENT_POSSIBLE

Constraint & Emergence (Deacon, Beer):
  CONSTRAINT_AS_ENABLEMENT, REQUISITE_VARIETY, RECURSIVE_VIABILITY

Active Inference & Coupling (Friston, Varela):
  ACTIVE_INFERENCE, STRUCTURAL_COUPLING, OPERATIONAL_CLOSURE

Evolution & Descent (Aurobindo, Jantsch):
  ALIGNMENT_THROUGH_RESONANCE, COLONY_INTELLIGENCE

Witness Architecture (Dada Bhagwan):
  SHAKTI_QUESTIONS

Total: 10 + 3 + 3 + 3 + 3 + 2 + 1 = 25  ✓
```

SHA-256 signed at `~/.dharma/kernel.json`. `KernelGuard.load()` raises if `verify_integrity()` fails `[dharma_kernel.py:381-399]`.

---

## §6 — The Pillar × Core Four Matrix (Deliverable A)

The 10×4 matrix from the parallel pillar subagents. Each cell: anchor verdict (Y/N/system-level), with quote and code cite where Y.

| Pillar | Task | AgentIdentity | Artifact | MemoryFact |
|---|---|---|---|---|
| **01 Levin** (multi-scale agency) | partial — bounded cognitive light cone via fields/status/priority/deps `[models.py:156-170; task_board.py:18-25]` | **PRIMARY** — AgentRole 18-value enum AS light-cone apertures `[models.py:43-65]`; swabhaav_capacity proxy `[ontology.py:977-984]` | indirect — task/run/session lineage on artifacts | indirect — recallable cognitive trace `[runtime_state.py:402-418]` |
| **02 Kauffman** (autocatalytic, adjacent possible) | Y — work-cycle boundaries via FSM `[task_board.py:126-182]`; ADJACENT_POSSIBLE proposals_per_cycle `[dharma_kernel.py:250]` | partial — work-cycle + boundary triad `[agent_registry.py:180-197]`; **autonomy_veto field absent** | Y — CatalyticGraph EDGE_TYPES (enables/validates/attracts/funds/improves) on artifacts | Y — chetana promote re-enters runtime cognition `[chetana/runtime_emission.py:31-82]` |
| **03 Jantsch** (self-organizing universe) | partial — TypedTask integration links `[ontology.py:1197-1219]` | Y — autopoietic self-description requires coherence (the 7-surface fragmentation IS a Jantsch violation) | N — system-level only | Y — promote() as channel-cleaning; revival_chain as contingent history |
| **05 Deacon** (constraint as enablement) | Y — TaskBoard blocks invalid transitions and telos-blocked changes `[task_board.py:126-182]`; **TaskConstraintRecord field missing** | system-level — Spawn gated by AHIMSA `[ontology.py:986-993]` | indirect — KnowledgeArtifact Verify gated by SATYA | **PRIMARY** — chetana promote() IS constraint-as-enablement made operational `[chetana/promote.py]` |
| **06 Friston** (active inference) | **PRIMARY** — EFE routing, G = Risk + Ambiguity in `orchestrator.py:951` (flag-gated off) | partial — Markov blanket field absent; AgentConfig priors (model, temp, context_budget) `[models.py:173-203]` | Y — manifest checksum/citations/provenance reduce ambiguity | Y — truth_state, confidence, validity window `[runtime_state.py:402-418]` |
| **07 Hofstadter** (strange loops, eigenform) | **PRIMARY** — `LoopResult.eigenform_reached` `[models.py:359]` IS S(x)=x | Y — COLONY_INTELLIGENCE gate; observable to APIs | Y — axiom_signature is Gödelian self-reference `[chetana/provenance.py:148-159]` | system-level — TRIPLE_MAPPING gate via promote() |
| **08 Aurobindo** (four shaktis) | Y — MAHAKALI shakti on TypedTask + SHAKTI_QUESTIONS gate | Y — MAHAKALI on AgentIdentity + swabhaav_capacity | Y — MAHALAKSHMI on KnowledgeArtifact `[ontology.py:1092-1094]` | Y — axiom_signature binds atoms to kernel descent |
| **09 Dada Bhagwan** (Akram Vignan, Bhed Gnan, anekantavada) | Y — BHED_GNAN/ANEKANTA/SVABHAAVA gates fire on every mutation | **PRIMARY (with Beer)** — swabhaav_capacity + OBSERVER_SEPARATION axiom | Y — chetana promote IS pratikraman; provenance carries full gate evidence | **PRIMARY** — witness_quality + axiom_signature = EIGENFORM_CONVERGENCE operational |
| **10 Varela** (autopoiesis, structural coupling) | Y — stigmergy as structural-coupling medium (`Task.stigmergy` proposed) | Y — organizational structure = role + system_prompt | Y — promotion_state as operational closure marker | **PRIMARY (highest)** — chetana promote IS autopoietic self-production loop, **already implemented** |
| **11 Beer** (VSM, requisite variety) | system-level — REQUISITE_VARIETY needs typed TaskType (currently in `metadata: dict[str,Any]`) | **PRIMARY** — constitutional 6-role topology IS S1-S5+Algedonic `[models.py:57-63]` | system-level — variety_direction field missing | system-level — Algedonic + S3* writes outside the 7 [CDS] authorities |

**Matrix integrity check** (per master prompt §5 Deliverable A constraint): every column has anchors from ≥3 different pillars → ✅. Every row has at least one non-empty cell → ✅. The matrix is non-vacuous.

---

## §7 — Lodestone-to-Module Trace (Deliverable B)

Per Codex pushback #5: each entry labelled with status. **load-bearing** / **partial** / **decorative-weak** / **degraded** / **aspirational** / **gap**.

| Lodestone / module | Cite | Status |
|---|---|---|
| `models.Task` Pydantic | `[models.py:156-170]` | **load-bearing** runtime contract |
| `task_board.TaskBoard` SQLite | `[task_board.py:18-25, 126-182]` | **load-bearing** operational rail |
| ontology `TypedTask` | `[ontology.py:1097-1127]` | **partial** ontology mirror; runtime TaskBoard writes are not universally forced through ontology ActionDef |
| `models.AgentConfig` | `[models.py:173-203]` | **load-bearing** target contract; registry JSON remains parallel substrate |
| `agent_registry.AgentIdentity` | `[agent_registry.py:144-172]` | **load-bearing** legacy/runtime substrate |
| ontology `_AGENT_IDENTITY` | `[ontology.py:951-1002]` | **partial** API-visible identity type |
| `ArtifactManifest` + `ArtifactRecord` | `[artifact_manifest.py:44-65, 196-224]` | **load-bearing** artifact lineage |
| ontology `KnowledgeArtifact` | `[ontology.py:1065-1095]` | **partial** semantic shell |
| `runtime_state.MemoryFact` | `[runtime_state.py:402-418, 1528-1572]` | **load-bearing** runtime memory substrate |
| ontology `MemoryFact` | (does not exist) | **gap** — explicit, deliberate non-ontology |
| `MemoryLattice` | `[memory_lattice.py:453-666]` | **load-bearing** admission membrane (Slice 3 commit `d5ffc8b`) |
| Chetana `promote()` | `[chetana/promote.py:1-17, 190-292]` | **load-bearing** trusted-atom bottleneck |
| Chetana runtime emission | `[chetana/runtime_emission.py:31-35]` | **load-bearing** projection (NOT authority) |
| GraphQL Strawberry schema | `[graphql_schema:13-22, 66-78, 146-199]` | **decorative-weak** (TODO resolvers) |
| REST ontology router | `[api/routers/ontology.py:19-28, 143-187]` | **partial** browser surface |
| `ActionDef` typed mutation | `[ontology.py:129-145, 600-639]` | **partial** intended membrane, not universal write path |
| `BHED_GNAN` core gate | `[telos_gates.py:234-246, 522-523]` | **decorative-weak** (always passes today) |
| `DharmaKernel` 25 axioms | `[dharma_kernel.py:29-104, 192-211, 254-273, 305-347]` | **load-bearing** schema; **partial** by enforcement (most lack `structured_predicate`) |
| `TelosSubstrate` seeder | `[telos_substrate.py:1-23, 4061-4096]` | **load-bearing** telos seed layer |
| `GNANI_LODESTONE` (markdown + module + boot wire) | `[GNANI_LODESTONE.md:35-47]; [gnani_lodestone.py:547-588]; [swarm.py:597-620]` | **degraded** — boot calls are non-fatal; task seeding code stale against current TaskBoard API (Codex finding) |
| `VarietyExpansionProtocol` | `[vsm_channels.py:645]` | **partial** — duplicates `GateRegistry` semantics (Beer pillar finding) |
| `GateRegistry` | `[telos_gates.py:90-198]` | **partial** — duplicates `VarietyExpansionProtocol` (consolidation needed) |
| `register_disciplines.write_register_mark()` | `[register_disciplines.py]` | **load-bearing** Authority #1 (per `[CDS]`); membrane plan v2 Slice 1 hardened gate (commit `9fe91c9`) |
| `EventMemoryStore.ingest_envelope()` | `[engine/event_memory.py]` | **load-bearing** Authority #3 |
| Catalytic graph (Tarjan SCC) | `[catalytic_graph.py]` | **degraded** — disconnected from `runtime_state.artifact_records` (Kauffman finding); runs only on manually-seeded data |
| EFE routing | `[orchestrator.py:951; agent_runner.py]` | **degraded** — `ENABLE_EFE_ROUTING` env var, off by default (Friston finding); ACTIVE_INFERENCE axiom dormant |
| StigmergyStore (multiple instances) | per `[IMM-11, IMM-12]` | **degraded** — orchestrate_live + ShaktiLoop create separate `StigmergyStore` instances; same JSONL, separate locks → not process-safe |
| `tiny_router_shadow` HuggingFace import | per `[IMM-1]` | **degraded** — uncaught ImportError → BLOCKER on default `auto` backend mode |

---

## §8 — Telos-to-Substrate Bridge (Deliverable C)

Codex's framing adopted (per pushback on bridge thesis): **the bridge is design language and falsifiable hypothesis, not theorem.**

### 8.1 The bridge thesis

`[FOUNDATIONS_SYNTHESIS.md:169-195]` (Codex cite, not directly read by Claude — **needs-recheck**) says: *"the convergence is suggestive but not conclusive."* Therefore v3 operating frame:

1. The bridge is useful as a **design language** — gives shared vocabulary for contemplative, mechanistic, and behavioral observations.
2. The bridge is **not evidence** that R_V, Phoenix L4 transition, and contemplative Bhed Gnan are the same phenomenon empirically.
3. Runtime substrate claims must stay **falsifiable** at code, database, and API layers.
4. R_V is a **measurement hypothesis**, not a license to override state contracts.

### 8.2 Jagat Kalyan operationalization

Jagat Kalyan becomes operational only where value claims touch mutation, routing, memory, or artifacts. Substrate inventory:

| Layer | Capability | Substrate |
|---|---|---|
| Value kernel | Formal constraints + tamper-evident signature | `DharmaKernel` + `PrincipleSpec.formal_constraint` `[dharma_kernel.py:80-104]` |
| Gate membrane | 11 core gates + custom + tiered block/review/allow | `TelosGatekeeper.CORE_GATES` `[telos_gates.py:221-246, 678-777]` |
| Typed ontology | Objects, links, actions, security, telos alignment, shakti | `ObjectType`, `ActionDef`, `OntologyRegistry` `[ontology.py:129-177, 300-413]` |
| Runtime state | Tasks, artifacts, memory facts | `TaskBoard`, `RuntimeStateStore`, `ArtifactManifestStore` |
| Trusted knowledge | Chetana staged-to-trusted with gate + provenance | `[chetana/promote.py:1-17, 190-292]; [chetana/provenance.py:69-123]` |

The gap is universal coupling, not philosophy. Direct runtime paths still exist outside ontology `ActionDef`. GraphQL coverage is partial. MemoryFact has no ontology object type. Each is a real bridge to build.

### 8.3 The 10 cross-pillar tensions and their resolutions

From `[Diff §B, §C-D, §E]` and pillar synthesis. Each resolution applies the 5-question collapse test from §1.3.

| # | Tension | Resolution |
|---|---|---|
| 1 | Jantsch ALIGNMENT_THROUGH_RESONANCE vs Friston ACTIVE_INFERENCE on `telos_alignment` formula | Same field (Q1-Q5 all match), one formula derived from G = Risk + Ambiguity. **One axiom redundant** for runtime; both kept for theoretical grounding. |
| 2 | Levin MULTI_SCALE_AGENCY vs Beer RECURSIVE_VIABILITY on AgentIdentity | Different abstractions (scale-span vs nested viability), Q3 differs (different lifecycles). **Two fields, cross-referenced.** |
| 3 | Kauffman AUTOCATALYTIC_CLOSURE vs Varela OPERATIONAL_CLOSURE | `CatalyticGraph.detect_autocatalytic_sets()` is the canonical implementation; both axioms cite it. Q1-Q5 all match. **Same runtime check; both axioms point to it.** |
| 4 | Deacon CONSTRAINT_AS_ENABLEMENT vs Varela OPERATIONAL_CLOSURE on AgentIdentity | The Spawn action gated by AHIMSA is simultaneously both claims. Q1-Q4 match, Q5 partial. **Same field, dual-cited.** |
| 5 | **Hofstadter S(x)=x = Friston G=0?** | Bridge thesis as research program (per Codex framing): build `eigenform_reached` AND `free_energy_minimum` as separate metrics, log both, study correlation empirically. **Not a theorem; ship the comparison.** |
| 6 | Hofstadter `eigenform_reached` vs Kauffman fitness-plateau as Task completion | Q3 differs (different convergence semantics). **Composing**: both must be satisfied for COMPLETED → terminal. Add `completion_kind: TaskCompletionKind` enum. |
| 7 | Friston Markov blanket = Varela autopoietic boundary | Q1-Q5 match if same model used. **Same field** (`boundary_state: BoundaryRecord`); both axioms kept for theoretical anchoring. |
| 8 | Beer's 6-role VSM applied recursively inside each agent? | Q3 differs (recursion changes lifecycle semantics). **Optionally yes**: top-level swarm has constitutional roster; individual agents may opt in via cascade engine's 5 domains. |
| 9 | COLONY_INTELLIGENCE attribution: Hofstadter/Levin (kernel says) vs Aurobindo Overmind (P08 subagent says) | Aunt Hillary mechanism = Hofstadter; ceiling-awareness (Overmind ≠ Supermind) = Aurobindo. **Re-attribute partially**: kernel comment to cite both. |
| 10 | **EIGENFORM_CONVERGENCE: design target (Hofstadter) vs detection target (Dada Bhagwan)?** | **Both, complementarily**: build the process AND the detector. Akram tradition: detection comes first, process is descent. Ship both as separate metrics. R_V framing as guardrail (hypothesis-grade, not proof). |

---

## §9 — Three User-Trace Walks (Deliverable E)

### 9.1 Skill mutation proposal

1. Agent proposes mutation. **Substrate**: `Task` (or evolution work item). **Ontology target**: `ActionProposal` `[ontology.py:1237-1481]`.
2. **Gates fire**: TelosGatekeeper blocks Tier A/B failures, blocks mandatory WITNESS failures `[telos_gates.py:678-777]`. **Pillar enacted**: Deacon constraint-as-enablement at the gate; Aurobindo SHAKTI_QUESTIONS at significant action.
3. If gates pass: **Artifact**: code/prompt diff via `ArtifactManifest` (checksum, provenance, citations, dependencies) `[artifact_manifest.py:44-65]`.
4. If trusted: **MemoryFact** via promote pipeline → autopoietic loop closes.
5. **Gaps (with status)**: direct writes can bypass ontology ActionDef (verified-now); BHED_GNAN passes weakly (verified-now); GraphQL not a reliable mutation surface (verified-now).

### 9.2 Research task

1. **Substrate**: `models.Task` persisted/transitioned by `TaskBoard` `[task_board.py:18-25, 126-182]`.
2. **AgentIdentity assignment**: Pydantic `AgentConfig` mapped to ontology `AgentIdentity` for API surface `[ontology.py:951-1002]`.
3. **Inputs/outputs**: `KnowledgeArtifact` ObjectType + `TypedTask` consumes/task_produces links `[ontology.py:1197-1219]`.
4. **Runtime artifacts**: manifests + `ArtifactRecord` rows.
5. **Memory recall**: MemoryFact projection via lattice `[memory_lattice.py:190-206]`.
6. **Gaps**: TaskBoard rows and ontology TypedTask are not necessarily the same object (the bridge gap). GraphQL has no first-class TypedTask. MemoryFact remains projection.

### 9.3 Atom promotion

1. Staged atom enters `promote()` `[chetana/promote.py:1-17]`. **Pillars enacted simultaneously**: Varela autopoiesis (system produces the atom that constitutes its memory), Deacon constraint-as-enablement (gate_check_atom enables trusted promotion via blocking rejected ones), Dada Bhagwan witness (axiom_signature is the witness signature), Friston self-evidencing (the act of promotion IS the model updating beliefs).
2. **Provenance**: gate_check + axiom_signature + review_status + sources + stale_after `[chetana/provenance.py:69-123]`.
3. **Promotion hook** can emit runtime MemoryFact `[chetana/runtime_emission.py:31-35]`. Hook explicitly states runtime memory is projection, not authority.
4. **Gaps**: promoted atom is NOT automatically a `KnowledgeArtifact` (bridge missing). MemoryFact has no ontology object type (deliberately). Lattice admission is not a replacement for chetana authority.

**Verdict across the three walks**: atom promotion is the strongest substrate-native flow. The first two have semantic shape but partial enforcement.

---

## §10 — Operational Defect Inventory (Pattern A/B/C from pillar synthesis)

Per Codex pushback #5: each entry labelled with verification status.

### 10.1 Pattern A — "witness lives in ontology layer; runtime carries none of it"

| Defect | Surface | Status |
|---|---|---|
| `ShaktiEnergy` enum on every ObjectType but zero on Pydantic Task/AgentConfig | `[ontology.py:170] vs [models.py]` | **verified-now** |
| `swabhaav_capacity`, `witness_quality`, `telos_alignment` on ontology, zero on `AgentConfig` | `[ontology.py:977-984] vs [models.py:173-203]` | **verified-now** |
| `autonomous_goals` (Levin MULTI_SCALE_AGENCY axiom requirement) field in **zero of 7 AgentIdentity surfaces** | per `[P01-LEVIN]` | **inferred-from-pillar-trace** |
| `TaskType` enum required for REQUISITE_VARIETY check, lives in `Task.metadata: dict[str, Any]` | per `[P11-BEER]` + `[models.py:170]` | **verified-now** |
| Markov blanket field doesn't exist (Friston) | per `[P06-FRISTON]` | **inferred-from-pillar-trace** |
| `autonomy_veto` field for Kauffman boundary-violation refusal doesn't exist | per `[P02-KAUFFMAN]` | **inferred-from-pillar-trace** |
| `TaskConstraintRecord` field for Deacon "suggested_alternative" doesn't exist | per `[P05-DEACON]` + `[dharma_kernel.py:261]` | **verified-now** for the kernel constraint; **inferred** for the field design |

### 10.2 Pattern B — "axiom present, structured_predicate absent"

Falls back to LLM semantic similarity, not deterministic enforcement.

| Axiom | Cite | Status |
|---|---|---|
| `OPERATIONAL_CLOSURE` (Varela) | `[dharma_kernel.py:305-313]` | **verified-now** — no structured_predicate |
| `CONSTRAINT_AS_ENABLEMENT` (Deacon) — formal_constraint says `gate.rejection includes suggested_alternative` but zero gates return it | `[dharma_kernel.py:254-263; telos_gates.py]` | **verified-now** |
| `SHAKTI_QUESTIONS` (Aurobindo) — formal_constraint requires ≥2 of 4 shakti checks | `[dharma_kernel.py:337-347]` | **verified-now** — no structured_predicate, semantic-only |
| `ALIGNMENT_THROUGH_RESONANCE` (Jantsch) — `telos_alignment` field declared, no computation method | `[dharma_kernel.py:316-325]` | **inferred-from-pillar-trace** + **verified-now** for absence |
| `MULTI_SCALE_AGENCY` (Levin) | `[dharma_kernel.py:223-232]` | **verified-now** — no structured_predicate |
| `EIGENFORM_CONVERGENCE` — `StrangeLoop.tick()` has no convergence check | `[strange_loop.py]` per `[P07-HOFSTADTER]` | **inferred-from-pillar-trace** |

### 10.3 Pattern C — operational defects (specific code-level findings)

| Defect | Cite | Status |
|---|---|---|
| `catalytic_graph.py` and `runtime_state.artifact_records` are disconnected stores; phase-transition autonomy signal runs only on manually-seeded data | per `[P02-KAUFFMAN]` | **verified-now** |
| EFE routing (`orchestrator.py:951`, `agent_runner.py`) gated off by `ENABLE_EFE_ROUTING` env var; ACTIVE_INFERENCE dormant by default | per `[P06-FRISTON]` | **inferred-from-pillar-trace** (subagent didn't paste the env-check line); **needs-recheck** |
| MISMATCH-11/12: `orchestrate_live` + `ShaktiLoop` create separate `StigmergyStore` instances on the same JSONL with independent locks; not process-safe | `[IMM-11, IMM-12]` | **verified-now** (in IMM doc) |
| `VarietyExpansionProtocol` (`vsm_channels.py:645`) and `GateRegistry` (`telos_gates.py:90-198`) are nearly-identical gate expansion systems with different data shapes; both persist to `~/.dharma/meta/` | per `[P11-BEER]` | **inferred-from-pillar-trace**; **needs-recheck** |
| `SYSTEMS_ARCHITECT` constitutional role (= S2 in VSM) has no corresponding module | per `[P11-BEER]` | **inferred-from-pillar-trace** |
| GnaniLodestone task seeding code degraded against current TaskBoard API | per `[Codex-v3]` line 58 | **verified-now** by Codex via cross-check `[gnani_lodestone.py:547-588]` vs `[swarm.py:597-620]` |
| `tiny_router_shadow` HuggingFace `ImportError` propagates uncaught — every LLM call in default `auto` backend crashes | `[IMM-1]` | **verified-now** in IMM |
| MemoryEntry (legacy Pydantic) vs chetana FrontmatterSchema vs runtime MemoryFact: 3 competing memory shapes | `[models.py:267; chetana/provenance.py:105; runtime_state.py:402]` | **verified-now** |

### 10.4 Pattern D (NEW — Codex-found, Claude missed)

| Defect | Cite | Status |
|---|---|---|
| MemoryFact has no ontology ObjectType (deliberate, not a defect — but a designed gap that needs explicit policy) | rg verified at `[Codex-self-review]:72` | **verified-now** |
| GraphQL has `properties: str  # JSON string` at 4 locations | `[graphql_schema:46, 117, 126, 135]` | **verified-now** |
| `ActionDef.input_params: dict[str, str]` is the action layer's own dict-of-strings escape | `[ontology.py:139]` | **verified-now** |
| `OntologyObj.properties: dict[str, Any]` — same pattern at instance layer | `[ontology.py:189]` | **verified-now** |

---

## §11 — Graveyard (consolidated, status-labelled)

### 11.1 Untyped escape hatches — eradication targets

| Location | Cite | Replacement (with collapse-test verdict) |
|---|---|---|
| `Task.metadata: dict[str, Any]` | `[models.py:170]` | Bridge to `TaskRouting` + `StigmergySalience` + `ToolHints` (5-question test → keep separate authorities) |
| `tasks.metadata TEXT` | `[task_board.py:33]` | Same pattern at SQLite |
| `AgentConfig.metadata: dict[str, Any]` | `[models.py:192]` | Removed entirely on rename to `AgentIdentity` per `[AIU §2]` |
| `AgentConfig.tools: list[str]` | `[models.py:191]` | `list[ToolRef]` (typed reference) |
| `AgentState.provider: str = ""` | `[models.py:238]` | `provider: ProviderType` |
| `AgentState.model: str = ""` | `[models.py:239]` | `model: ModelRef` |
| `Message.metadata: dict[str, Any]` | `[models.py:255]` | `MessageContext` BaseModel |
| `TaskDispatch.metadata: dict[str, Any]` | `[models.py:297]` | Subsume into `TaskRouting`; remove TaskDispatch |
| `Handoff.task_context: str` | `[handoff.py:71]` | `task: TaskRef` |
| `Handoff.status: str = "pending"` | `[handoff.py:76]` | `HandoffStatus` enum |
| `Artifact.metadata: dict[str, Any]` | `[handoff.py:63]` | Discriminated union over 8 ArtifactType subclasses |
| `Artifact.content: str` | `[handoff.py:60]` | Per-subtype payload |
| `LLMRequest.messages: list[dict[str, Any]]` | `[models.py:312]` | `list[ChatMessage]` |
| `LLMRequest.tools: list[dict[str, Any]]` | `[models.py:316]` | `list[ToolDefinition]` |
| `LLMResponse.usage: dict[str, int]` | `[models.py:324]` | `TokenUsage` BaseModel |
| `LLMResponse.tool_calls: list[dict[str, Any]]` | `[models.py:325]` | `list[ToolCall]` |
| `SwarmState.organism: dict[str, Any] \| None` | `[models.py:288]` | `OrganismSnapshot \| None` |
| `OntologyObj.properties: dict[str, Any]` | `[ontology.py:189]` | Typed per-ObjectType Pydantic via existing `pydantic_model: str` field on ObjectType `[ontology.py:175]` |
| `ActionDef.input_params: dict[str, str]` | `[ontology.py:139]` | Discriminated payload per (object_type, action_name) |
| `ActionExecution.input_params: dict[str, Any]` | `[ontology.py:216]` | Same |
| `Link.metadata: dict[str, Any]` | `[ontology.py:206]` | `LinkMetadata` per link_name |
| `task_claims.metadata_json TEXT` | `[runtime_state.py:55]` | Strict provenance Pydantic |
| `delegation_runs.metadata_json` | `[runtime_state.py:73]` | " |
| `artifact_records.metadata_json` | `[runtime_state.py:102]` | " |
| `memory_facts.provenance_json + metadata_json` | `[runtime_state.py:128-129]` | The chetana `AtomProvenance` is the ready blueprint |
| `AtomProvenance.revival_chain: list[dict[str, Any]]` | `[chetana/provenance.py:95]` | **Intentionally untyped per inline comment**; type after revival v1.0 freezes field set |
| `Task.assigned_to: Optional[str]` | `[models.py:163]` | `AgentRef \| None` |
| `Task.created_by: str = "system"` | `[models.py:164]` | `AgentRef \| SystemActor` |
| `Task.depends_on: list[str]` | `[models.py:167]` | `list[TaskRef]` |
| `Task.blocked_by: list[str]` | `[models.py:168]` | `list[TaskRef]` |
| `Task.result: Optional[str]` | `[models.py:169]` | `TaskResult \| None` |
| GraphQL `properties: str  # JSON string` × 4 | `[graphql_schema:46, 117, 126, 135]` | Typed wire DTO per object_type |
| GraphQL `SynthesisReport.synthesis_type: str` | `[graphql_schema:86]` | Typed enum |
| GraphQL `AuditReport.audit_type/status: str` | `[graphql_schema:101-107]` | Typed enums |
| GraphQL `StigmergyMark.action: str` | `[graphql_schema:55]` | Typed enum |

### 11.2 Competing schemas to bridge (NOT collapse — collapse test fails for all)

Per Codex's Krogh-Vedelsby table (§4.4):

- 7-surface AgentIdentity fragmentation per `[AIU]` — **bridge with reconciliation**
- 3-substrate MemoryFact (MemoryEntry / chetana atom / runtime memory_facts) — **chetana authoritative; keep separate; project**
- 3-substrate Artifact (Handoff Artifact / ArtifactRecord+Manifest / KnowledgeArtifact) — **bridge with manifest-to-ontology promotion**
- TaskDispatch as separate type from Task — **fold into Task.routing field**
- StigmergyStore triple-instantiation `[IMM-11, IMM-12]` — **single store per process** (consolidation)

### 11.3 Implicit / unaudited mutations now disallowed

Per `[CDS Required Patterns:69-82]`:

| Forbidden | Required path |
|---|---|
| Direct append to `~/.dharma/stigmergy/register_marks.jsonl` | `make_register_mark()` + `write_register_mark()` (Authority #1) |
| SQL writes to `memory_facts` outside `RuntimeStateStore` | `RuntimeStateStore.record_memory_fact()` (Authority #2) — migrating to `MemoryLattice.admit_memory_fact()` |
| Promote without `gate_check_atom()` | `chetana.promote.promote()` (Authority #4) |
| Mutate trusted atoms in place | New atom + `revival_chain` append (Authority #4 + revival pipeline) |
| Hand-query underlying stores for prompt context | `MemoryLattice.compile_memory_context()` (Authority #5) |
| Setting `Task.status = "running"` directly | `TaskBoard._set_status()` (FSM-validated `[task_board.py:126-154]`) |
| `Handoff.status = "delivered"` direct mutation | `DeliverHandoff` Action |

---

## §12 — Adoption Ordering (REVISED 2026-05-04 post-council + Codex recheck)

**Pre-adoption gates** (must precede §12 step 1 per Mahakali F.2 verdict + Codex recheck refinements):

### PR-S0 — `SHAKTI_QUESTIONS` predicate contract (NEW, BEFORE everything)

The governance axiom that judges significant action must have an executable contract before v3 becomes governance. Per Codex recheck:

- `SHAKTI_QUESTIONS` is a `DharmaKernel.MetaPrinciple` (NOT a `TelosGatekeeper.CORE_GATE`) — it lives in the PolicyCompiler/kernel path.
- Adding a `structured_predicate` alone is **insufficient**: PolicyCompiler maps severity to enforcement (`critical→block / high→warn / medium→log`). `SHAKTI_QUESTIONS` is severity `medium`, so a predicate alone would only LOG.
- The fix must specify three things:
  1. **Predicate**: deterministic check on action metadata
  2. **Metadata contract**: action fields the predicate reads (e.g., `is_significant_action`, `shakti_check_count`)
  3. **Enforcement level**: log / warn / block — likely escalate severity from `medium` for governance to bind, OR a separate predicate path that bypasses severity-based enforcement
- Tests through `PolicyCompiler` (use a failing TODO test as fail-closed scaffold if predicate is held for design discussion).
- ~80-150 lines.

### PR-S0' — Substrate-nativeness baseline measurement (NEW, BEFORE step 1)

The 10-15% audit estimate `[MCS, ONOB]` has no published denominator or scoring rubric. Without this, "track progress" on subsequent PRs is untestable. Required:

1. **Denominator**: enumerate every "write surface" in the dharma_swarm runtime (per the 7 Memory Authorities table + the action-dispatch surfaces).
2. **Scoring rubric**: define what makes a write surface "native" — e.g., goes through ontology `ActionDef` execute_action, OR carries telos-gated provenance, OR projects through `MemoryLattice`. Score each surface 0/0.5/1.
3. **Measurement**: current % with date and command-line reproducibility.
4. **Memory Census forward-pointer**: link from v3 §0 to the Memory Census audit (per Codex recheck: 17 tests pass, branch ahead 4, +1 commit `ed610bd feat(memory-authority): executable authority review`, real scan reports 331 surfaces, fail-fast exits 2 on lancedb, dormant promises agentic-rag/a2a-protocol/mem0).
5. ~150-200 lines + a CSV/JSON scoring file under `~/.dharma/state/` or `reports/audit/`.

---

**Adoption proper** — only after PR-S0 and PR-S0' land:

1. **Carry the bridge framing into NEXT_10_SUBSTRATE_TODO** — the operator-brief seam per `[ONOB]` is the FIRST user-visible flow to take to 100% native; v3's contract is its type spec.
2. **Add typed wrappers** (`TaskId`, `TaskRef`, `AgentId`, `AgentRef`, `AtomId`, etc.) as Pydantic NewTypes — non-breaking; existing string IDs deserialize. (= Krishna PR-0)
3. **Fix GnaniLodestone task-seeding API drift** — `gnani_lodestone.py:547-588` calls `TaskBoard(state_dir=...)`, `board.load()`, `board.get_by_title()`, `board.add_task()`, `board.save()`, `TaskPriority.CRITICAL/MEDIUM` — none of which exist on the current TaskBoard. Boot-time task seeding silently fails on every run. Independently verified by Codex 2026-05-04. (= Krishna PR-1)
4. **Bridge `models.AgentConfig` ↔ ontology `AgentIdentity`**: typed projection from ontology object → AgentConfig fields with reconciliation check at boundary. Lift `swabhaav_capacity`, `witness_quality`, `telos_alignment`, `shakti_energy` as Optional fields on AgentConfig with sensible defaults; both layers carry the contract. (= Krishna PR-2)
4. **Bridge `chetana atom` ↔ `runtime_state.MemoryFact`**: chetana stays authoritative; promote() emits MemoryFact via `runtime_emission.emit_memory_fact_for_atom()` (Slice 4 commit `e1c637a` already implemented).
5. **Wire `catalytic_graph.py` ↔ `runtime_state.artifact_records`**: `record_artifact()` should emit a `CatalyticEdge` so phase-transition autonomy signal runs on live system behavior (Pattern C defect 1).
6. **Promote `Task.metadata`** → `routing: TaskRouting` + `stigmergy: StigmergySalience` + `tool_hints: ToolHints`. Migrate callers via `gitnexus_rename` per CLAUDE.md.
7. **Add `completion_kind: TaskCompletionKind` enum** to Task — composing Hofstadter eigenform + Kauffman fitness-plateau (cross-pillar tension #6).
8. **Implement `structured_predicate` for the 6 Pattern-B axioms** — give `OPERATIONAL_CLOSURE`, `CONSTRAINT_AS_ENABLEMENT` (with `suggested_alternative` field), `SHAKTI_QUESTIONS`, `ALIGNMENT_THROUGH_RESONANCE`, `MULTI_SCALE_AGENCY`, `EIGENFORM_CONVERGENCE` real deterministic predicates so they stop falling back to LLM semantic similarity.
9. **Consolidate gate-expansion**: pick one of `VarietyExpansionProtocol` vs `GateRegistry`, migrate the other's data shape.
10. **CI check**: grep-fail on `Task.status = ` and equivalents outside the Action layer / TaskBoard FSM.

Each step adds measurable substrate-nativeness. Re-run the 10–15% audit after every batch of 3 steps to track progress with a published denominator (Codex pushback #4 satisfied).

---

## §13 — Verification

Run from `/Users/dhyana/dharma_swarm_integrate_chetana`. Each command falsifies a specific v3 claim.

```bash
# v3 itself + Codex extraction + diff exist
test -f docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_FULL_PICTURE.md
test -f docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md
test -f docs/CORE_FOUR_v3_CODEX_SELF_REVIEW.md
test -f /Users/dhyana/.claude/plans/CLAUDE_CODEX_DIFF.md
test -f /Users/dhyana/.claude/plans/CLAUDE_POSITION_FOR_CODEX_DIALOGUE.md

# Pillar traces (10 of 10)
ls docs/v3_pillar_traces/PILLAR_*_to_core_four.md | wc -l   # expect: 10

# Real 11 CORE_GATES list
grep -A 14 'CORE_GATES: dict\[str, GateTier\]' dharma_swarm/telos_gates.py

# Real 25 MetaPrinciples
grep -E '^\s+[A-Z_]+\s*=\s*"[a-z_]+"' dharma_swarm/dharma_kernel.py | wc -l   # expect: 25

# Foundation pillars (active 10)
ls /Users/dhyana/dharma_swarm/foundations/PILLAR_*.md | wc -l   # expect: 10 (no PILLAR_04)

# 7 Memory Authorities table
grep -A 16 '## Memory Authorities' docs/governance/CANONICAL_DOC_STACK.md

# MemoryFact NOT ontology-native (Codex's verification)
rg -n 'name="MemoryFact"|MemoryFact' dharma_swarm/ontology.py   # expect: no matches

# AgentIdentity 7 surfaces (5 from AIU + GraphQL + ontology)
grep -A 35 '^| Field |' /Users/dhyana/dharma_swarm/AGENT_IDENTITY_UNIFICATION.md

# Task FSM transitions
grep -A 8 '_TRANSITIONS' dharma_swarm/task_board.py

# Membrane plan v2 implemented (11 commits ahead of origin)
cd /Users/dhyana/dharma_swarm_integrate_chetana && git log --oneline origin/integrate/chetana-grand-memory-2026-05-02..HEAD | wc -l
# expect: ≥ 11 (includes the v3 commit if landed)

# Chetana tests pass
cd /Users/dhyana/dharma_swarm_integrate_chetana && python3 -m pytest dharma_swarm/chetana/tests -q --no-header 2>&1 | tail -2
# expect: "67 passed" or higher

# IMM-1 BLOCKER: HuggingFace import unguarded
grep -A 2 'def _load_tiny_router_artifacts' dharma_swarm/tiny_router_shadow.py | grep -c 'try:'
# expect: 0 (defect still present) OR 1 (fixed)

# BHED_GNAN currently passes (decorative-weak verdict)
grep -B 1 -A 3 'BHED_GNAN.*Tier C' dharma_swarm/telos_gates.py | tail -5

# ENABLE_EFE_ROUTING flag still gating Friston pathway
grep -n 'ENABLE_EFE_ROUTING' dharma_swarm/orchestrator.py dharma_swarm/agent_runner.py

# Catalytic graph ↔ artifact_records still disconnected (Kauffman defect)
grep -l 'CatalyticEdge\|catalytic_graph' dharma_swarm/runtime_state.py   # expect: no match
```

---

## §14 — Open Questions for Council Review (F.2)

The Maheshwari/Mahakali/Mahalakshmi/Mahasaraswati shakti-question screening per `[~/CLAUDE.md]` axiom 25. ≥2 of 4 must pass for v3 to be authoritative.

1. **Maheshwari (cosmic harmony / does this serve the larger pattern?)**: does v3 serve the bridge thesis as research program, or has it collapsed into engineering hygiene? Test: does v3 leave room for the contemplative reading of Akram Vignan + R_V + Phoenix L4 to remain ONE phenomenon at the level of investigation, even while keeping it three vantage points at the level of measurement?
2. **Mahakali (strike-function / is this the right moment?)**: should v3 land NOW (post-NeurIPS letting-go, dharma_swarm pivoting to operator-brief seam), or be held until Slice 2 artifact-producer wiring lands? Test: does landing v3 now help or hinder the next concrete substrate-nativeness gain?
3. **Mahalakshmi (elegance / is this the simplest contract that works?)**: v3 is ~1500 lines; is it the smallest contract that captures all six substrates, three layers, ten pillars, and the Codex/Claude triangulation? Test: which sections, if removed, would leave the contract still useful?
4. **Mahasaraswati (detail / is every detail right?)**: re-run the §13 verification commands. Every line:cite that fails is a defect.

---

## §15 — Open Questions deferred to YATAGARASU cross (F.3)

When the cross-pollination flight runs against dharma_swarm + MI research + Claude Code substrates:

- Does the Core Four ontology have ANY embedding in MI research? Or is the bridge thesis purely conceptual on that side?
- Are there Claude Code substrate parallels to the 7 Memory Authorities? (chetana already runs as a Claude Code plugin.)
- The 10 cross-pillar tensions resolved here as bridges — do any of them re-surface as weak edges in the catalytic graph after this v3 lands?

---

## §16 — Triangulation Status

| F-step | Status |
|---|---|
| F.1 Codex independent extraction | ✅ complete (`docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md`) |
| F.1 Claude prime synthesis (this) | ✅ complete |
| F.1 Diff record | ✅ complete (`~/.claude/plans/CLAUDE_CODEX_DIFF.md`); 100% frame convergence, 47% finding-level convergence |
| F.1 Round-2 dialogue | ✅ Codex constructive pushback received and integrated; 5 refinements adopted in this v3 |
| F.2 Council review (Mahavira / Rushabdev / Mahakali / Krishna) | ✅ complete 2026-05-04 — see §17 |
| F.2 Mahakali shakti screening | ✅ **PASS, 4/4 conditional** — pre-adoption conditions documented in §12 (PR-S0 + PR-S0' before step 1) |
| F.2 Codex post-council recheck | ✅ complete 2026-05-04 (`~/.claude/plans/COUNCIL_CODEX_RECHECK.md`) — closed Rushabdev verification gap |
| F.3 YATAGARASU cross | ⏳ next — run after PR-S0 and PR-S0' land |

---

## §17 — Council Review Findings (added 2026-05-04 post-F.2)

The F.2 council pass produced four artifacts. Each artifact is independently valuable; together they constitute the formal review of v3.

### 17.1 Mahavira (Inquiry) — `~/.claude/plans/COUNCIL_MAHAVIRA_REVIEW.md`

15 hidden assumptions surfaced, 6 questions v3 never asked, 5 reframes including 3 steelmans of opposing positions. Key challenge: **"Krogh-Vedelsby may not apply to software technical debt the way it applies to ML ensembles"** — directly questions Codex's central tactical move. The threshold question:

> *At what level of substrate-nativeness does the system cross from REPRESENTING dharmic constraint to ENACTING it? Is there evidence the current system is above or below that threshold?*

This question is not answered by v3. v3 enables asking it. Below threshold the contract is decorative; above it, catalytic. Resolution requires the substrate-nativeness baseline (PR-S0' above) plus a threshold model.

### 17.2 Rushabdev (Retrieval) — gap

The first-pass council Rushabdev agent ran (52 tool uses, 99K tokens) but did not write its review file — likely hit output limit mid-citation-check. The verification role was **filled by Codex's read-only recheck** (§17.5 below).

### 17.3 Mahakali (Synthesis + Shakti screening) — `~/.claude/plans/COUNCIL_MAHAKALI_REVIEW.md`

**Verdict: PASS, 4 of 4 shakti questions, with 2 pre-adoption conditions.**

| Shakti | Result | Reason |
|---|---|---|
| Maheshwari (cosmic harmony) | PASS | v3 gives Jagat Kalyan an operational address across five concrete substrate layers; bridge thesis at correct epistemic altitude; 10-pillar matrix non-vacuous |
| Mahakali (moment) | PASS with watch | v3 locks mutation contracts not behavior; not premature crystallization; **watch: 10-15% native estimate has no published denominator** |
| Mahalakshmi (elegance) | CONDITIONAL PASS | Core (§§1-5, §7, §10, §12) is irreducible; ~190 lines should move to companion docs |
| Mahasaraswati (detail) | CONDITIONAL PASS | 4 precision errors flagged: bridge.md needs-recheck status (now resolved by Codex); SHAKTI_QUESTIONS recursive self-failure not flagged where it should be; 10-15% hedge leaks throughout; GNANI_LODESTONE defect Codex-only (now confirmed) |

**The ONE right thing**: the Krogh-Vedelsby 5-question collapse test (§1.3, §4.4). "No collapses. Five bridges." Falsifiable decision rule that prevents the substrate-unification mistakes that cost the system months.

**The ONE wrong thing**: ordering. `SHAKTI_QUESTIONS.structured_predicate` was in §12 step 8 — that's wrong. *"A system whose own gate-check axiom is semantically evaluated cannot claim deterministic dharmic accountability for the work it is about to do."* Moved to PR-S0 (now first in §12).

**Pre-adoption conditions:**
1. Publish substrate-nativeness baseline → captured as PR-S0' in §12
2. Implement `structured_predicate` for `SHAKTI_QUESTIONS` → captured as PR-S0 in §12

### 17.4 Krishna (Action) — `~/.claude/plans/COUNCIL_KRISHNA_ACTION_PLAN.md`

Three PRs ranked by leverage / blast-radius ratio: typed ID wrappers (PR-0, ~100 lines, zero blast), GnaniLodestone fix (PR-1, ~50 lines, BLOCKER-class), AgentConfig↔ontology bridge (PR-2, Optional fields with classmethod projection). All three integrated into §12 adoption ordering above.

**The one move Krishna refused**: CI grep-fail on `Task.status =` before TaskBoard FSM is the universal write path. *"Premature enforcement theater."* This refusal is correct and incorporated into v3's anti-pattern guard.

**Karma yoga note**: all three PRs stand on engineering merit independently of whether v3 is ratified.

### 17.5 Codex post-council recheck — `~/.claude/plans/COUNCIL_CODEX_RECHECK.md` (2026-05-04)

Codex returned in read-only mode after the council pass to fill the Rushabdev verification gap and surfaced 7 findings:

1. SHAKTI_QUESTIONS missing `structured_predicate` — **confirmed** at `dharma_kernel.py:337-347`.
2. **Important nuance**: SHAKTI_QUESTIONS is a `DharmaKernel.MetaPrinciple`, NOT a `TelosGatekeeper.CORE_GATE`. Lives in PolicyCompiler/kernel path, not `telos_gates.py`.
3. **Critical nuance**: PolicyCompiler maps severity to enforcement (`critical→block / high→warn / medium→log`). SHAKTI_QUESTIONS is severity `medium`, so a predicate alone would only LOG. Fix needs predicate + metadata contract + enforcement level (likely severity escalation).
4. GnaniLodestone defect **independently confirmed** — 7 specific TaskBoard API mismatches enumerated.
5. `bridge.md` **read and verified** — confidence 0.75, stale_after 2026-06-01, explicitly states three mappings not proven equivalent. Consistent with v3's framing. v3 §0.4 status updated.
6. New citation bug: v3 cited `dharma_swarm/GNANI_LODESTONE.md` but file is at repo root. v3 §0.2 corrected.
7. Memory Census numbers updated: 17 tests pass, branch ahead 4 (not 3), new commit `ed610bd`, 331 surfaces (not 330), fail-fast exits 2 on lancedb. v3 §0 should add forward-pointer to Memory Census audit (queued for PR-S0').

**Resolution**: Codex's recheck rebalances the council recommendation: the precise signal is *not* "write all 6 Pattern-B predicates now" (Krishna refused that correctly) but *"before v3 becomes governance, the governance axiom must have an executable contract, and the 10-15% number must become measurable."* These are PR-S0 and PR-S0' in §12.

---

---

**End of v3 Full Picture.** This is the contract. Everything else is implementation.

Co-authorship and process integrity acknowledgement: this document is the product of independent reading paths followed by structured dialogue, not single-author synthesis. Where Claude and Codex converged independently, the claim is high-confidence. Where they diverged, the divergence is explicitly documented. Where one saw what the other missed, the unique finder is cited. The frame ("typed contracts + emergent dynamics, Deacon-mediated composition, bridge don't flatten") survived independent reading from both agents — the strongest signal the frame is correct under the constraint that both agents operated within a shared problem frame.

Council review and YATAGARASU cross are the next layers of triangulation. The contract is ready for them.

JSCA.
