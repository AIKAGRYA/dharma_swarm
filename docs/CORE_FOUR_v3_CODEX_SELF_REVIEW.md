# CORE FOUR v3 Codex Self-Review

Date: 2026-05-03  
Reviewed artifact: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_codex_extraction.md`  
Review stance: independent Codex self-review, not council consensus.

## Scope and Compliance

I wrote the v3 extraction without reading:

- `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT.md`
- `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

Those files exist in the worktree, but they were not opened or cited. Evidence in the extraction comes from source modules, non-forbidden docs, shell line checks, contextplus semantic search, memory graph search, and chetana wiki gap scans.

One caveat: a broad `.dharma` search in the prior working context surfaced staging observations from other agents. I did not use those notes as evidence in the extraction; the written claims cite source code, docs, gates, lodestones, or explicit verification commands.

## Deliverable Coverage

| Required item | Status | Notes |
|---|---|---|
| A. 10 x 4 Pillar x Core Four matrix | Complete | Uses the repo's ten active foundation pillars and cites code for Task, AgentIdentity, Artifact, and MemoryFact. |
| B. Lodestone/module trace | Complete | Marks components as load-bearing, partially wired, decorative/weak, degraded, aspirational, or gap. |
| C. Telos-to-substrate bridge | Complete | Includes bridge thesis, Jagat Kalyan capability, Shakti, telos failure mode, R_V, eigenform, anekantavada, constraint-as-enablement, requisite variety, and operational closure. |
| D. Tension resolution | Complete | States the firm composability decision: typed contracts govern mutation; emergent dynamics govern behavior. |
| E. Three trace walks | Complete | Covers skill mutation, research task, and atom promotion with explicit gaps. |
| F. Independent extraction status | Complete | F.1 complete; F.2 council review and F.3 YATAGARASU cross deferred. |

## Evidence Quality

Strong:

- Core Four runtime substrate: `Task`, `AgentConfig`, `ArtifactRecord`, and `MemoryFact` are directly present in source.
- Ontology substrate: `AgentIdentity`, `KnowledgeArtifact`, and `TypedTask` are directly present as ObjectTypes.
- MemoryFact ontology gap: `ontology.py` has no `MemoryFact` object type.
- Gate/kernel extraction: `CORE_GATES`, `BHED_GNAN`, and `MetaPrinciple` are directly line-cited.
- Chetana atom promotion: promotion, provenance, and runtime projection are directly line-cited.

Moderate:

- Trace walks for skill mutation and research task are architecturally supported, but not all steps are enforced by a single runtime transaction.
- REST ontology browser is real, while GraphQL is partial and should not be treated as authoritative.
- Gnani Lodestone is boot-wired, but task seeding appears degraded against the current TaskBoard API.

Weak or aspirational:

- Philosophical bridge claims are design-language support, not proof.
- Jagat Kalyan capability is only operational where it affects gates, tasks, artifacts, memory, or ontology actions.
- Shakti is present in schema/kernel language, but enforcement is partial.

## Risk Register

| Risk | Review verdict |
|---|---|
| Accidentally treating ontology `ActionDef` as universal write authority | Explicitly avoided. The extraction calls it an intended membrane, not current universal path. |
| Accidentally making MemoryFact ontology-native | Explicitly avoided. The extraction says MemoryFact is runtime/chetana projection only. |
| Over-crediting GraphQL | Explicitly avoided. Strawberry GraphQL is marked decorative/partial because resolvers are TODO. |
| Over-crediting `BHED_GNAN` | Explicitly avoided. It is marked decorative/weak because the current predicate always passes. |
| Confusing chetana authority with runtime memory | Explicitly avoided. Runtime MemoryFact emission is cited as projection, not authority. |
| Treating Palantir ontology as behavioral lock | Explicitly avoided. The extraction frames it as Deacon-style enabling constraint. |

## Verification Performed

Commands and checks performed during this run included:

```bash
git -C /Users/dhyana/dharma_swarm_integrate_chetana status --short
rg -n 'class Task|class AgentConfig|class ArtifactRecord|class MemoryFact|name="TypedTask"|name="AgentIdentity"|name="KnowledgeArtifact"' \
  dharma_swarm/models.py dharma_swarm/runtime_state.py dharma_swarm/ontology.py
rg -n 'CORE_GATES|BHED_GNAN|class MetaPrinciple|EIGENFORM_CONVERGENCE|ANEKANTAVADA|CONSTRAINT_AS_ENABLEMENT|REQUISITE_VARIETY|OPERATIONAL_CLOSURE|SHAKTI_QUESTIONS' \
  dharma_swarm/telos_gates.py dharma_swarm/dharma_kernel.py
rg -n 'name="MemoryFact"|MemoryFact' dharma_swarm/ontology.py
python -m dharma_swarm.chetana.cli gap-scan --focus eigenform --min-occurrences 2
python -m dharma_swarm.chetana.cli gap-scan --focus anekantavada --min-occurrences 2
```

MCP checks performed:

- `mcp__contextplus__.semantic_code_search`
- `mcp__contextplus__.search_memory_graph`
- `mcp__memory__.search_nodes`

The GitNexus MCP resource path was unavailable in this environment, so GitNexus-specific graph verification was not used.

## Final Self-Assessment

This is an acceptable independent Codex extraction for F.1. It is source-grounded, names the major gaps, and does not claim final consensus. The most important architectural conclusion is stable:

Typed contracts should govern state mutation; emergent dynamics should govern behavior. The Core Four should be bridged, not flattened.
