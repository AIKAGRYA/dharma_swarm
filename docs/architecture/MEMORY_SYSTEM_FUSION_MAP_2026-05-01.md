# Dharma Swarm Memory Fusion Map

Date: 2026-05-01

Scope: dharma_swarm runtime memory systems, the Chetana atom/governance worktree, Claude session preamble memory injection, and current external agent-memory patterns. I did not bulk-read every generated JSONL/history row; I mapped the code-level memory systems, their storage, write/read paths, and how they should be fused.

## Executive Verdict

Do not build a twelfth memory system. Do not radically delete systems just because their names overlap. The highest-leverage move is to make one authoritative memory protocol and demote the existing systems into clean roles:

- Canonical substrate: one append-only episode/event ledger plus one atom/edge/use schema.
- Admission controller: one retrieval controller that decides what enters context.
- Projections: vector, graph, palace, working-memory, agent-local, and dashboards generated from the canonical substrate.
- Distillers: sleep, Chetana revive, persistent evolution lessons, mem actions, experiment memory, and semantic bridge convert raw episodes into atoms and edges.
- Operational stores: routing EWMA and latency/cost telemetry remain separate, but can emit summarized lessons into canonical memory.

The monster memory system is not a bigger vector DB. It is an event-sourced, bitemporal, truth-stateful, graph-linked, vector-indexed, utility-trained, contradiction-aware memory plane with one admission policy.

## First Principles

Memory is controlled state transition, not storage. A memory system must answer five questions for every item: where did it come from, what scope owns it, how true is it, when was it true, and did using it improve action?

Context is an actuator. Injecting memory into a prompt changes behavior. Therefore retrieval must be governed like action, not treated like decoration.

Specialized memory forms are valid only as projections. A vector index, graph store, palace canvas, agent working buffer, and Chetana wiki can all exist, but only one layer should decide authoritative truth and context admission.

Forgetting is part of memory. The right operation is usually soft invalidation, supersession, demotion, or compression, not deletion. Hard deletion is for secrets, legal constraints, corruption, or obviously generated trash.

## Current Local Memory Map

### Core Runtime Spine

| System | Local file | Storage | Current role | Future role |
|---|---|---|---|---|
| EventMemoryStore | `dharma_swarm/engine/event_memory.py` | `~/.dharma/db/memory_plane.db` | Canonical runtime envelope ledger. Creates `event_log`, `source_documents`, `source_chunks`, `retrieval_log`, `conversation_turns`, `idea_shards`, `idea_links`, `idea_uptake`. | Keep. This is the episode ledger. |
| UnifiedIndex | `dharma_swarm/engine/unified_index.py` | same `memory_plane.db` | Search surface over source chunks plus runtime events. | Keep as FTS/document projection, but make it consume canonical atoms too. |
| HybridRetriever | `dharma_swarm/engine/hybrid_retriever.py` | reads UnifiedIndex and feedback | Fuses lexical, overlap, hash-semantic, temporal, structural, and feedback signals. | Keep as retrieval lane engine. Replace hash embeddings when available; add contradiction lane and lane quotas. |
| RetrievalFeedbackStore | `dharma_swarm/engine/retrieval_feedback.py` | `retrieval_log` | Logs retrieval hits, outcome, citation uptake, and bounded feedback boosts. | Keep. This is the use-telemetry kernel most systems lack. |
| MemoryLattice | `dharma_swarm/memory_lattice.py` | memory_plane, runtime_state, event JSONL, StrangeLoopMemory | Facade over events, facts, retrieval, always-on context, and StrangeLoop memory. | Promote into or wrap with `MemoryKernel`. |
| RuntimeStateStore | `dharma_swarm/runtime_state.py` | runtime DB | Has `MemoryFact`, `MemoryEdge`, `ContextBundleRecord`, sessions, artifacts, leases. | Reuse schema ideas for canonical atoms/edges. |
| ContextCompiler | `dharma_swarm/context_compiler.py` | runtime state + memory systems | Builds budgeted context bundles from lattice, palace, graph, knowledge store, facts, artifacts. | This is already a pre-inference controller inside dharma_swarm. Needs one unified memory kernel input. |

### Agent, Session, and Conversation Memory

| System | Local file | Storage | Current role | Future role |
|---|---|---|---|---|
| StrangeLoopMemory | `dharma_swarm/memory.py` | SQLite `memories` table | Five-layer immediate/session/development/witness/meta memory. Used by swarm/pulse/review/lattice. | Adapter over atom scopes. Keep API, stop independent authority. |
| AgentMemoryBank | `dharma_swarm/agent_memory.py` | JSON files under `~/.dharma/agent_memory/{agent}/` | Older per-agent working/archival/persona memory. | Compatibility adapter. Backfill then read through kernel. |
| AgentMemoryManager | `dharma_swarm/agent_memory_manager.py` | `~/.dharma/agent_memory/memories.db` | Newer Letta-style working/short/long/shared memory with TTL and explicit tools. | Keep API as agent-local projection over kernel scopes. |
| ConversationMemoryStore | `dharma_swarm/engine/conversation_memory.py` | `conversation_turns`, `idea_shards`, `idea_links`, `idea_uptake` | Records turns, harvests latent ideas, tracks uptake and follow-up outcomes. | Keep. This is branch/latent-opportunity memory. Its shards become atoms. |
| Terminal bridge working memory | `dharma_swarm/terminal_bridge_context.py` | `working_memory.json` | Recent terminal turns/actions, active mission, preferred route. | Keep as hot working projection; write summarized turns to kernel. |
| Claude preamble hook | `~/.claude/hooks/dharma_session_preamble.py` | reads files/digests | Injects routing, altitude, MCP, wiki extracts, register digest. | Add real retrieval controller. Static digest is not enough. |

### Projection and Search Systems

| System | Local file | Storage | Current role | Future role |
|---|---|---|---|---|
| VectorStore | `dharma_swarm/vector_store.py` | `vectors.db` | Bitemporal vector/FTS store with confidence decay and GC. Uses TF-IDF/SVD default, sentence transformers optional. | Projection fed from canonical atoms/episodes. Excellent bitemporal ideas should be reused. |
| GraphStore | `dharma_swarm/graph_store.py` | graph DB/tables | Code, semantic, runtime, telos graph with bridge edges. | Graph projection of canonical edges plus code graph. |
| MemoryPalace | `dharma_swarm/memory_palace.py` | lattice + VectorStore + optional LanceDB/graph | Merges lattice/vector/graph/Lance hits, reranks by semantic/lexical/recency/salience. | Query orchestrator and UI projection, not a writer of independent truth. |
| KnowledgeStore | `dharma_swarm/engine/knowledge_store.py` | in-memory or Qdrant | Lightweight concept retrieval with hash embeddings. | Keep as plug-in projection for artifacts/knowledge; feed from atoms. |
| Graph unifier | `dharma_chetana/dharma_swarm/chetana/graph_unifier.py` | external graph backends | Unified query surface over memory MCP, gitnexus, contextplus, catalytic graph. | Keep as external graph adapter. Do not make it another graph of truth. |

### Distillers, Governance, and Specialized Memory

| System | Local file | Storage | Current role | Future role |
|---|---|---|---|---|
| Chetana provenance/staging | `dharma_chetana/dharma_swarm/chetana/provenance.py`, `staging.py` | frontmattered markdown under `~/.dharma/knowledge` | Staged/trusted atom lifecycle with source, chain, gate check, SHA-256 axiom signature, stale_after, review_status. | Trusted atom ingress. Map frontmatter to canonical atom fields. |
| Chetana governance | `dharma_chetana/dharma_swarm/chetana/governance.py` | witness logs | Fails closed if gates/kernel unavailable, signs promoted atoms. | Governance adapter for atom promotion. |
| Chetana revive/decay | `dharma_chetana/dharma_swarm/chetana/revival.py`, `decay.py` | trusted wiki/quarantine | Stale atom revival, neighbor scan, confidence delta, revival_chain. | Nightly consolidation/reverification distiller. |
| OrganismMemory | `dharma_swarm/organism_memory.py` | JSONL entities/relationships | Autonoetic self-model of mutations, decisions, capabilities, algedonic events, etc. | Self-model projection over atom/edge graph. |
| PersistentMemory | `dharma_swarm/persistent_memory.py` | evolution JSONL | Distills experiment histories into ideation and strategy lessons. | Distiller emitting `evolution_lesson` atoms. |
| ExperimentMemory | `dharma_swarm/experiment_memory.py` | analyzer over experiment records | Produces mutation bias, failure signatures, caution components, lessons. | Distiller, not store. |
| SemanticMemoryBridge | `dharma_swarm/semantic_memory_bridge.py` | memory_plane plus concept graph | Bridges concept evolution, retrieval uptake, idea shards, experiment lessons. | Consolidation job. |
| MemAction | `dharma_swarm/mem_action.py` | parsed from `<mem>` blocks | Captures step summaries, key facts, key skills, and MemPO-style truncation. | Excellent procedural/factual distiller. Convert facts and skills into atoms. |
| RoutingMemory | `dharma_swarm/routing_memory.py` | router SQLite | EWMA quality/latency/tokens and provider pheromones. | Keep separate operational telemetry. Emit periodic route lessons only. |

## Current Connectivity

```text
RuntimeEnvelope
  -> EventMemoryStore.ingest_envelope()
  -> memory_plane.event_log
  -> EventLog JSONL export

UnifiedIndex.records()
  -> source_documents/source_chunks
  -> event_log rows

HybridRetriever.search()
  -> UnifiedIndex.search/records
  -> RetrievalFeedbackStore.feedback_profile()
  -> RetrievalFeedbackStore.log_hits()/record_outcome()/record_citation_uptake()

AgentRunner
  -> AgentMemoryBank JSON writes
  -> AgentMemoryManager SQLite writes
  -> ConversationMemoryStore turn/shard/uptake writes
  -> RetrievalFeedbackStore outcome writes

ContextCompiler
  -> RuntimeStateStore
  -> MemoryLattice.replay_session/recall/always_on_context
  -> MemoryPalace.search
  -> GraphStore semantic search
  -> KnowledgeStore search
  -> ContextBundleRecord

Chetana
  -> ingest staged markdown
  -> promote through TelosGatekeeper + KernelGuard
  -> trusted atom markdown with provenance
  -> decay/revive/gap/palace/query surfaces

Claude SessionStart preamble
  -> static routing/altitude/MCP/register/wiki sections
  -> missing: measured retrieval/admission controller
```

## Main Diagnosis

The system does not primarily need pruning. It needs authority collapse.

Today, several systems can write memory, retrieve memory, and shape context without passing through the same admission policy. That makes the swarm complicated rather than integrated. It also makes future self-modification dangerous: a mutation can improve one memory path while silently bypassing another.

The strongest existing spine is:

```text
EventMemoryStore
  + RuntimeStateStore.MemoryFact/MemoryEdge
  + UnifiedIndex
  + HybridRetriever
  + RetrievalFeedbackStore
  + ConversationMemoryStore
  + Chetana provenance
```

Everything else should plug into that spine.

The most important missing component is a `MemoryKernel`: a small facade that owns canonical writes, retrieval admission, truth-state transitions, and use feedback. It should not replace existing stores in one sweep. It should sit above them, then progressively absorb authority.

## External Research Pattern Map

| Source | Pattern | What to absorb |
|---|---|---|
| Letta/MemGPT | Stateful agents persist messages and memory blocks; important blocks stay in context while external memory is retrieved on demand. | Separate always-visible core memory from searchable archival memory. Make memory editing explicit through tools. |
| LangGraph | Short-term thread checkpoints plus long-term memories in namespace/key stores. | Add namespace discipline: agent, user, project, repo, task, global, governance. |
| AutoGen | A simple `Memory` protocol with `add`, `query`, `update_context`, `clear`, `close`. | Define a tiny compatibility protocol so every agent runner can consume one memory surface. |
| LlamaIndex Memory | FIFO short-term memory flushes into long-term memory blocks; blocks have priorities under token pressure. | Use priority and token pressure as first-class admission controls. |
| Zep/Graphiti | Episodic ingestion, temporal edges, hybrid semantic/BM25/graph search, temporal invalidation. | This is closest to your needs: episodes -> facts/edges with historical truth. |
| Mem0 April 2026 | Add-only extraction, agent-generated facts as first-class, entity linking, multi-signal retrieval. | Do not overwrite memories. Add superseding atoms/edges. Fuse semantic, BM25, and entity lanes. |
| Microsoft GraphRAG | Local search for entity-specific questions, global/community search for corpus-wide questions, DRIFT mixes both. | Your retrieval controller should classify query altitude and select local/global/DRIFT-like lanes. |
| HippoRAG | Knowledge graph plus Personalized PageRank for single-step multi-hop retrieval. | Add graph-neighborhood expansion after the first candidate set. |
| LightRAG | Dual low-level/high-level graph/vector retrieval. | Retrieve both precise path-local facts and abstract concept summaries. |
| RAPTOR | Recursive summary tree over chunks. | Build hierarchical summaries during sleep, not at SessionStart. |
| Generative Agents | Memory stream plus reflection plus planning. | Preserve ConversationMemoryStore latent ideas and nightly reflection, but connect them to action outcomes. |
| Cognee | Relational provenance, vector search, graph relationships. | Your architecture already matches this. The missing piece is one write contract across the three. |

## Unified Architecture: Dharma Memory Plane v2

### Canonical Objects

```python
@dataclass(frozen=True)
class MemoryEpisode:
    episode_id: str
    source_kind: str       # session, tool, runtime_event, chetana_atom, experiment, route_event
    source_uri: str
    actor_id: str
    event_time: datetime
    ingestion_time: datetime
    payload: dict
    checksum: str

@dataclass(frozen=True)
class MemoryAtom:
    atom_id: str
    kind: str              # fact, procedure, preference, lesson, warning, identity,
                           # capability, latent_branch, governance, register_mark
    scope: str             # turn, session, agent, task, repo, project, swarm, global
    owner_id: str
    text: str
    summary: str
    truth_state: str       # observed, candidate, promoted, contradicted,
                           # superseded, deprecated, refused
    confidence: float
    salience: float
    utility_score: float
    stability_class: str   # volatile, working, durable, axiom
    valid_from: datetime | None
    valid_to: datetime | None
    source_episode_id: str
    provenance: dict
    access_policy: dict
    metadata: dict

@dataclass(frozen=True)
class MemoryEdge:
    edge_id: str
    from_atom_id: str
    to_atom_id: str
    relation: str          # supports, contradicts, supersedes, caused,
                           # predicts, corrects, derived_from, enables,
                           # same_as, part_of
    weight: float
    evidence_uri: str
    valid_from: datetime | None
    valid_to: datetime | None

@dataclass(frozen=True)
class MemoryUse:
    use_id: str
    task_id: str
    query: str
    admitted_atom_ids: list[str]
    rejected_atom_ids: list[str]
    consumer: str
    outcome: str | None
    citation_uptake: dict
    created_at: datetime
```

### Minimal Kernel API

```python
class MemoryKernel:
    async def observe_episode(self, episode: MemoryEpisode) -> str: ...

    async def promote_atom(
        self,
        *,
        episode_id: str,
        kind: str,
        text: str,
        scope: str,
        confidence: float,
        provenance: dict,
        links: list[MemoryEdge] | None = None,
    ) -> str: ...

    async def link_atoms(self, edge: MemoryEdge) -> str: ...

    async def recall(
        self,
        query: str,
        *,
        scope: list[str],
        active_paths: list[str] = (),
        token_budget: int = 1200,
        consumer: str,
        task_id: str = "",
        require_admission_log: bool = True,
    ) -> "MemoryContext": ...

    async def record_use_outcome(
        self,
        use_id: str,
        *,
        outcome: str,
        citations: list[str] = (),
        notes: str = "",
    ) -> None: ...

    async def consolidate(self, mode: str = "nightly") -> "ConsolidationReport": ...
```

This API is deliberately small. It maps cleanly onto AutoGen's memory protocol, LangGraph stores, Letta-style core/archival blocks, and your current ContextCompiler.

## Retrieval Controller

Fixed `K=5-10` is too crude. Use a token budget with lane quotas. Default SessionStart can admit 8 items, but the controller should reserve slots:

| Lane | Default quota | Purpose |
|---|---:|---|
| Hot working state | 1-2 | active mission, recent edits, failing tests |
| Path-local memory | 2 | same repo/file/module |
| Semantic/vector memory | 2 | concept similarity |
| Graph neighborhood | 1-2 | related entities, superseding edges, causal links |
| Contradiction warnings | 1 required if present | known conflicts or stale claims |
| Latent branch/idea shards | 1 | high-salience orphaned ideas |
| Governance/register/kernel | 1 | relevant telos, register mark, axiom, refusal |

Scoring should be additive but bounded:

```python
score = (
    0.28 * semantic_score
    + 0.22 * lexical_score
    + 0.16 * path_overlap
    + 0.12 * graph_proximity
    + 0.10 * salience
    + 0.08 * utility_score
    + 0.04 * recency_score
)

if atom.truth_state in {"contradicted", "superseded", "deprecated"}:
    score *= 0.25

if atom.kind in {"governance", "warning", "register_mark"} and path_overlap > 0:
    score += 0.10

score = min(score, lane_cap(atom.kind, atom.source_kind))
```

Admission is not just top-K:

```python
candidates = gather_lanes(query, active_paths, scope)
clusters = cluster_duplicates(candidates)
conflicts = find_conflict_clusters(clusters)

selected = []
selected += required_guardrails(conflicts, active_paths)
selected += mmr_diverse_pick(clusters, lane_quotas, remaining_budget)

context = render_with_truth_state(selected, conflicts)
use_id = log_memory_use(query, candidates, selected, rejected)
return MemoryContext(text=context, use_id=use_id)
```

Contradictions should be rendered explicitly:

```text
<memory_conflict>
Claim A: "daemon runs from worktree X" [promoted, 2026-04-29, source=observer]
Claim B: "daemon runs from worktree Y" [observed, 2026-04-29, source=audit]
Resolution: unresolved. Before editing daemon startup, verify live process cwd.
</memory_conflict>
```

Never silently choose the newer claim when the older claim has higher utility or stronger provenance.

## Consolidation and Forgetting

Nightly consolidation:

```text
episodes -> candidate atoms -> duplicate clusters -> contradiction edges
         -> promoted atoms -> projection refresh -> utility decay -> report
```

Weekly consolidation:

- Merge near-duplicate atoms using `same_as` or `supersedes` edges.
- Convert successful task traces into procedure atoms.
- Convert failed traces into warning atoms with concrete preconditions.
- Promote high-uptake idea shards into latent branches.
- Demote unused working memories back to archival scope.
- Refresh Chetana stale atoms through revive, not automatic trust.

Homeostasis rule:

```text
Every new pinned/core memory must either:
1. replace or supersede an existing pinned memory,
2. be scoped narrower than global, or
3. expire automatically.
```

This preserves the thought behind each existing memory system without letting total context weight grow without bound.

## Sublation Map

Keep as kernel core:

- `EventMemoryStore`
- `RuntimeStateStore.MemoryFact` / `MemoryEdge`
- `UnifiedIndex`
- `HybridRetriever`
- `RetrievalFeedbackStore`
- `ConversationMemoryStore`
- Chetana provenance schema

Convert to adapters:

- `AgentMemoryBank`
- `AgentMemoryManager`
- `StrangeLoopMemory`
- terminal bridge `working_memory.json`
- Claude preamble hook

Convert to projections:

- `VectorStore`
- `GraphStore`
- `MemoryPalace`
- `OrganismMemory`
- dashboards and memory palace canvas

Convert to distillers:

- `PersistentMemory`
- `ExperimentMemory`
- `SemanticMemoryBridge`
- `MemAction`
- Chetana revive/decay/gap scan

Keep separate but summarize into memory:

- `RoutingMemory`
- cost/latency telemetry
- daemon health probes

## Execution Plan

### Phase 1: Introduce the Kernel Facade

Add `dharma_swarm/engine/memory_kernel.py` with the small API above. For the first patch, do not migrate storage. Back it with existing `EventMemoryStore`, `RuntimeStateStore`, `UnifiedIndex`, `HybridRetriever`, and `RetrievalFeedbackStore`.

Acceptance:

- `observe_episode()` writes to `event_log`.
- `promote_atom()` writes to `RuntimeStateStore.record_memory_fact()`.
- `link_atoms()` writes to `RuntimeStateStore.record_memory_edge()`.
- `recall()` calls HybridRetriever and logs admission to RetrievalFeedbackStore.
- Unit tests prove the old stores still work.

### Phase 2: Add Atom/Edge Tables to memory_plane

Add tables to `engine/event_memory.py` schema sync:

```sql
CREATE TABLE IF NOT EXISTS memory_atoms (...);
CREATE TABLE IF NOT EXISTS memory_edges (...);
CREATE TABLE IF NOT EXISTS memory_uses (...);
CREATE TABLE IF NOT EXISTS memory_projection_runs (...);
```

Do not remove `memory_facts` yet. Dual-write promoted atoms to both until tests prove parity.

### Phase 3: Adapterize Existing Writers

Change these paths to write through `MemoryKernel` while preserving their public APIs:

- `AgentMemoryManager.remember`
- `AgentMemoryBank.remember`
- `StrangeLoopMemory.remember`
- `MemoryLattice.remember/record_fact`
- `ConversationMemoryStore.harvest_turn`
- `PersistentMemory.distill_from_experiments`
- `MemAction` extraction path
- Chetana `promote` and `revive --apply`

Acceptance:

- No direct new writes to legacy memory stores except inside adapters.
- Legacy reads still work through read-through fallback.
- Scanner flags direct memory writes outside approved adapter files.

### Phase 4: Real SessionStart Prior Retrieval

Add a `PriorRetrievalController` used by `~/.claude/hooks/dharma_session_preamble.py` and by dharma_swarm `ContextCompiler`.

Inputs:

- cwd
- last prompts if available
- active git diff paths
- recent file edits
- failing tests or hot items
- register digest categories

Outputs:

- `<prior_relevant>` block with source, truth state, confidence, and use ID.
- retrieval attempt log even on zero hits.
- conflict block when contradictions are found.

Trigger it at SessionStart and before hot-path edits. SessionStart alone is insufficient because the query changes after the agent opens files and discovers the real task boundary.

### Phase 5: Projection Refresh and Sleep

Nightly:

- Backfill/refresh VectorStore from canonical atoms.
- Refresh GraphStore from canonical edges.
- Run Chetana revive proposals for stale trusted atoms.
- Convert high-uptake retrievals into higher utility scores.
- Decay low-utility, low-confidence, never-used atoms.
- Emit a memory health report.

Weekly:

- Run hierarchical summaries in RAPTOR style for long document/session clusters.
- Run graph-neighborhood compression in HippoRAG/LightRAG style.
- Review top contradictions and unresolved stale governance atoms.

## What Not To Build

Do not make Chroma or any vector DB authoritative. Vector DBs are projections.

Do not increase K as a substitute for better admission. More context can reduce agency by adding stale attractors.

Do not let LLM summarization promote truth by itself. Promotion needs provenance, source episode, truth state, and ideally outcome feedback.

Do not collapse routing telemetry into general memory. Routing is a control policy store. Only distilled route lessons belong in canonical memory.

Do not delete all legacy memory files now. Wrap them first, log read/write parity, then freeze direct writes. Deletion without parity is amnesia.

Do not build a new memory palace before the kernel. The palace should render the memory plane; it should not become a parallel mind.

## Highest Leverage Next Patch

Implement `MemoryKernel` and make only one integration change: route `MemoryLattice.record_fact()` and `MemoryLattice.recall()` through it. That creates the authority point without destabilizing agent runner, terminal, Chetana, or the swarm daemon.

Second patch: add `PriorRetrievalController` and make `dharma_session_preamble.py` call it in read-only mode. Log results but do not yet change behavior aggressively.

Third patch: adapterize `AgentMemoryManager` because it is the cleanest Letta-style API already exposed as agent tools.

This sequence gives immediate loop closure and avoids both theatrical pruning and another layer of complexity.

## Source Links

- Letta stateful agents and memory blocks: https://docs.letta.com/guides/core-concepts/stateful-agents
- Graphiti/Zep temporal knowledge graphs: https://help.getzep.com/graphiti/getting-started/overview
- Mem0 repository and April 2026 memory algorithm notes: https://github.com/mem0ai/mem0
- LangGraph memory concepts: https://docs.langchain.com/oss/javascript/concepts/memory
- AutoGen memory protocol: https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/memory.html
- LlamaIndex memory: https://developers.llamaindex.ai/python/examples/memory/memory/
- Microsoft GraphRAG query engine: https://microsoft.github.io/graphrag/query/overview/
- Cognee core concepts: https://docs.cognee.ai/core-concepts/overview
- Generative Agents paper page: https://huggingface.co/papers/2304.03442
- HippoRAG paper page: https://huggingface.co/papers/2405.14831
- LightRAG project page: https://lightrag.github.io/
- RAPTOR paper page: https://arxiv.org/abs/2401.18059
