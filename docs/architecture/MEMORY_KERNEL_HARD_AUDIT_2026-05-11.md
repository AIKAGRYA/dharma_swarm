# MemoryKernel Hard Audit

Date: 2026-05-11

Scope: dharma_swarm repo memory code, existing architecture docs, high-volume
local memory stores under `~/.dharma`, Smriti, Claude hooks/cabinet/session data,
Codex memories, m5-handoff Smriti hooks, and the Persistent Semantic Memory
Vault. This audit intentionally sampled schemas, counts, paths, and code-level
writers. It did not bulk-read private conversation rows or vector payloads.

## Executive Verdict

The MemoryKernel direction is correct, but only if it becomes the one governed
coordination organ for memory. It should not become another giant database and
it should not compete with MemoryLattice, RuntimeStateStore, EventMemoryStore,
UnifiedIndex, MemoryPalace, or KnowledgeOps.

The highest build is:

```text
all memory surfaces
  -> MemoryKernel surface registry
  -> read/write adapters
  -> normalized episodes, facts, edges, chunks, retrieval uses, witness events
  -> authority/provenance/time/decay labeling
  -> retrieval compiler and context admission
  -> KnowledgeOps feed
  -> concepts, claims, evidence, decisions, cards, promotion queues
```

MemoryKernel owns memory coordination. KnowledgeOps owns semantic metabolism and
promotion. Chetana, Smriti, Sakshi/Witness, vector stores, conversation logs,
Telos, and external vaults are sensed sources, substrates, projections, or
consumers. None should be swallowed as truth.

Confidence after this audit:

- Architecture boundary: high, about 0.91.
- Local surface coverage: strong, about 0.86.
- Entire ecosystem coverage: not complete, about 0.72, because Claude/App
  Support stores, MCP server internals, external worktrees, and private app
  stores can still hide memory paths.

## Correction To The Previous Plan

The earlier plan was directionally right but still too small. The missing point
is that MemoryKernel cannot just be a facade over "memory.py plus friends." It
must coordinate every thing that remembers or influences future context:

- raw episode logs
- runtime state
- routing decisions
- conversation transcripts
- witness/provenance
- agent-local memory
- Chetana lifecycle stores
- semantic/ontology graphs
- vector and LanceDB indexes
- external vaults/cabinets
- Claude hooks and session data
- Codex/MCP memory
- telemetry ledgers that produce operational lessons

The correct stance is:

```text
MemoryKernel does mechanical metabolism:
  sense, normalize, label authority, dedupe, age, route, retrieve, record use.

KnowledgeOps does semantic metabolism:
  extract concepts/claims/evidence, critique, link, promote, archive.
```

## Existing De Facto Kernels

There are already partial kernels. The new organ must wrap them, not duplicate
them.

| Component | Evidence | Current role | Future role |
|---|---|---|---|
| MemoryLattice | `dharma_swarm/memory_lattice.py:31` | Facade over runtime state, event memory, index, retriever, StrangeLoop memory, JSONL event log. | Inner adapter or first implementation of MemoryKernel facade. |
| EventMemoryStore | `dharma_swarm/engine/event_memory.py:15` | `~/.dharma/db/memory_plane.db` event/conversation/retrieval schema. | Episode ledger substrate. |
| RuntimeStateStore | `dharma_swarm/runtime_state.py:28`, `:718` | `~/.dharma/state/runtime.db` sessions, artifacts, context bundles, facts/edges schema. | Runtime/control-plane truth plus candidate fact/edge tables. |
| UnifiedIndex | `dharma_swarm/engine/unified_index.py:153` | Indexes source docs/chunks and runtime events. | Projection/index adapter, never authority. |
| ContextCompiler | `dharma_swarm/context_compiler.py:84` | Builds prompt context from lattice, palace, graph, knowledge, facts, artifacts. | Primary MemoryKernel consumer. |
| read_memory_context | `dharma_swarm/context.py:600` | Legacy/simple context retrieval path used by prompts, pulse, cron, TUI. | Compatibility consumer through kernel. |
| MemoryPalace | `dharma_swarm/memory_palace.py:205` | Merges lattice, vector, graph, and LanceDB search. | Search/UI projection, not source of truth. |
| KnowledgeOps | `dharma_swarm/knowledge_ops/extractor.py:76`, `schema.py:207` | Read-only graph extraction and projection cards. | First-class KnowledgeOps consumer of MemoryKernel atoms. |

## High-Volume Memory Surfaces

| Surface | Path | Observed size/counts | Classification | Authority |
|---|---|---:|---|---|
| LanceDB | `~/.dharma/lancedb` | 243 GB, `palace_docs.lance` | vector/projection index | none, projection only |
| Conversation log | `~/.dharma/conversation_log` | 24 GB JSONL, including large daily/all rotations | raw episodic transcript source | low raw evidence |
| Chetana knowledge | `~/.dharma/knowledge` | 1.9 GB, 43,505 staging files, 308 wiki files | KnowledgeOps lifecycle/staging/canon surface | mixed; wiki may be curated, staging is not |
| Memory plane | `~/.dharma/db/memory_plane.db` | 992 MB | strongest runtime memory substrate | raw event/idea/retrieval substrate |
| Vector SQLite | `~/.dharma/vectors.db` | 1.6 GB, 677,403 docs/FTS/embeddings rows | vector/FTS projection | none, projection only |
| Runtime DB | `~/.dharma/state/runtime.db` | 80 MB | control-plane/runtime state | high for runtime observations |
| Ontology DB | `~/.dharma/ontology.db` | 5,788 objects, 3,943 links, 7,773 lineage edges | semantic graph | medium, depends on source |
| Witness logs | `~/.dharma/witness` | 35 MB, 1,880 JSONL files | provenance/audit stream | high as witness evidence, not semantic truth |
| Terminal TUI state | `~/.dharma/terminal_tui` | 5.1 GB | operator/runtime transcript surface | raw/operational |
| Traces | `~/.dharma/traces` | 208 MB, many history files | runtime trace surface | raw evidence |
| Agent memory | `~/.dharma/agent_memory` | JSON plus `memories.db` | agent-local memory | low/agent-scoped |
| Smriti | `~/.smriti/smriti.db` | 6,660 memories | Claude/session memory | low, episodic import source |
| Claude home | `~/.claude` | 40 GB | hooks, cabinet, session data, agent memories | mixed external exocortex |
| PSMV | `~/Persistent-Semantic-Memory-Vault` | 979 MB | external semantic vault | external curated/raw mix |
| Codex memories | `~/.codex/memories/mcp-memory.jsonl` | 16 KB | Codex/MCP memory | low/agent-scoped |
| m5-handoff Smriti | `~/m5-handoff/smriti/smriti.db` | 2.9 MB repo area | alternate Smriti source | low import source |

## SQLite Substrate Census

### `~/.dharma/db/memory_plane.db`

This is the most important existing storage substrate.

| Table | Count |
|---|---:|
| `event_log` | 11,301 |
| `conversation_turns` | 3,838 |
| `idea_shards` | 102,695 |
| `idea_links` | 2,838,491 |
| `idea_uptake` | 54,930 |
| `retrieval_log` | 6,853 |
| `source_documents` | 0 |
| `source_chunks` | 0 |
| `index_runs` | 0 |

Interpretation: memory_plane is alive for events, conversations, idea shards,
links, uptake, and retrieval feedback. It is not currently populated as a
document chunk index.

### `~/.dharma/state/runtime.db`

| Table | Count |
|---|---:|
| `session_events` | 39,476 |
| `routing_decisions` | 3,263 |
| `context_bundles` | 82 |
| `artifact_records` | 2 |
| `memory_facts` | 0 |
| `memory_edges` | 0 |
| `retrieval_log` | 0 |
| `conversation_turns` | 0 |
| `idea_shards` | 0 |
| `source_documents` | 0 |
| `source_chunks` | 0 |
| `event_log` | 0 |

Interpretation: runtime.db is the live control-plane store. Its memory fact and
edge schema exists but is not populated in this observed DB. That makes it a
good target for controlled fact/edge admission, not the only current memory
source.

### Other Databases

| Path | Counts | Role |
|---|---:|---|
| `~/.dharma/vectors.db` | 677,403 documents/embeddings/FTS rows | projection index |
| `~/.dharma/ontology.db` | 5,788 objects, 3,943 links, 7,773 lineage edges | semantic graph |
| `~/.smriti/smriti.db` | 6,305 episodic, 230 working, 120 procedural, 5 semantic memories | session memory import source |
| `~/.dharma/agent_memory/memories.db` | 16 memories | agent-local memory |
| `~/.dharma/db/memory.db` | 3,944 memories | StrangeLoop memory |
| `~/.dharma/db/knowledge_store.db` | 1,623 propositions, 666 prescriptions, 8,620 concept_index rows | concept retrieval/distillation |
| `~/.dharma/state/knowledge.db` | 68 propositions, 24 prescriptions, 369 concept_index rows | smaller state knowledge projection |
| `~/.dharma/db/messages.db` | 196,912 messages, 3,592 events, 44 subscriptions | message bus/history |
| `~/.dharma/db/temporal_graph.db` | 1,752 concepts, 158,935 co-occurrences, 5,301 sources | temporal semantic projection |
| `~/.dharma/data/dharma_graphs.db` | 83 semantic nodes, 489 semantic edges | multi-graph projection |

## Hidden Write Paths

These are the paths MemoryKernel must either own, wrap, or explicitly mark as
legacy.

| Writer | Storage | Risk |
|---|---|---|
| `dharma_swarm/conversation_log.py:73` | daily/master/promises JSONL under `~/.dharma/conversation_log` | huge raw transcript store; must stream, never eager load |
| `dharma_swarm/engine/conversation_memory.py:176` | `conversation_turns`, `idea_shards`, `idea_links`, `idea_uptake` | valuable atom source; currently direct write |
| `dharma_swarm/engine/event_memory.py:15` | `memory_plane.db` event log and memory-plane schema | good substrate, but multiple callers can bypass kernel |
| `dharma_swarm/engine/unified_index.py:153` | `source_documents`, `source_chunks`, `index_runs` | projection writes must not imply truth |
| `dharma_swarm/engine/retrieval_feedback.py:254` | `retrieval_log` | use feedback is core kernel input |
| `dharma_swarm/memory_lattice.py:31` | runtime state, memory_plane, event JSONL, StrangeLoop memory | closest current facade; should be wrapped/promoted |
| `dharma_swarm/memory.py:77` | `~/.dharma/db/memory.db` StrangeLoop memory | independent authority unless adapterized |
| `dharma_swarm/agent_memory.py:69` | per-agent JSON memory | agents can self-edit memory |
| `dharma_swarm/agent_memory_manager.py:148` | `~/.dharma/agent_memory/memories.db` | cleaner API, still outside kernel |
| `dharma_swarm/route_witness.py:481` | runtime telemetry plus router JSONL audit | witness/audit, not memory truth |
| `dharma_swarm/telemetry_plane.py:795` | runtime telemetry tables | operational source for route lessons |
| `dharma_swarm/routing_memory.py:68` | default `~/.dharma/logs/router/routing_memory.sqlite3` | code path exists but observed DB was absent |
| `dharma_swarm/inquiry_substrate_chew.py:481` | inquiry witness JSONL | witness family surface |
| `dharma_swarm/telos_gates.py` | witness logs and gate feedback JSONL | gate/audit writes, can silently swallow failures |
| `api/routers/chat.py` | `~/.dharma/conversations/dashboard_*.jsonl` | dashboard transcript path separate from conversation_log |
| `api/routers/stigmergy.py` | `~/.dharma/stigmergy/marks.jsonl` | coordination blackboard, direct rewrites |
| `hooks/telos_gate.py` | `~/.dharma/witness` | hook-level witness write |
| `~/.claude/hooks/smriti_session_start.py` | reads Smriti into session context | external context injector |
| `~/.claude/hooks/smriti_session_end.py` | writes Smriti memories from session end | external memory writer |
| `~/.claude/hooks/dharma_session_preamble.py` | reads wiki/extracts/Smriti/register/GitNexus signals | external prior-context injector |

## Main Context Consumers

These consumers must stop scraping random stores directly over time. They
should call MemoryKernel or a compatibility facade.

| Consumer | Current behavior | Kernel target |
|---|---|---|
| `ContextCompiler` | Reads runtime state, MemoryLattice, MemoryPalace, graph store, KnowledgeStore. Persists `context_bundles`. | Primary `retrieve_context_bundle()` consumer. |
| `read_memory_context` | Reads StrangeLoop DB, memory_plane, KnowledgeStore, MemoryPalace. | Legacy compatibility wrapper. |
| `AgentRunner` | Exposes remember tools, records conversation turns, retrieval outcomes, and agent memory. | Agent tool facade over kernel. |
| `SwarmManager` / `swarm.py` | Calls remember/recall and records runtime facts. | Kernel write/read facade. |
| `MemoryPalace` | Searches lattice/vector/graph/LanceDB. Also writes/indexes in places. | Query orchestrator/projection only. |
| `Claude hooks` | Inject Smriti/wiki/register context at SessionStart and write Smriti on Stop. | External adapter plus prior retrieval controller. |
| `KnowledgeOpsExtractor` | Reads repo/docs/wiki/code surfaces into graph projection. | Consume MemoryKernel atom feed plus repo docs. |
| `TUI`, `pulse`, `prompt_builder`, `cron_runner` | Use `read_memory_context`. | Compatibility wrapper to kernel. |
| MCP server | Exposes remember/recall. | Tool surface over kernel only. |

## Authority Map

MemoryKernel must label authority explicitly. Suggested tiers:

| Tier | Meaning | Examples |
|---|---|---|
| `raw_observation` | append-only event or transcript; true only as "this was observed" | memory_plane event_log, conversation logs, traces |
| `witness_evidence` | audit/provenance/gate record; strong evidence of a system decision | witness JSONL, route_witness, telos_gate logs |
| `agent_claim` | generated or agent-edited memory | Smriti auto-extracts, agent_memory, StrangeLoop |
| `system_state` | live runtime/control-plane state | runtime.db sessions/routing/context bundles |
| `projection` | derived index; never authority | LanceDB, vectors.db, UnifiedIndex chunks, MemoryPalace |
| `semantic_graph` | derived/curated links with provenance | ontology.db, temporal_graph.db, graph_store |
| `human_curated` | manually reviewed docs/wiki/canon | curated wiki/docs, selected PSMV nodes |
| `canonical` | promoted through review/gates | future KnowledgeOps/Chetana promoted atoms |
| `intent_graph` | objectives/strategies/hypotheses | Telos JSONL/graph |
| `dormant_or_unsafe` | discovered but not trusted/adapted | unknown external app stores, stale worktrees |

Hard rule: vector stores and search indexes can only point to authority; they
cannot become authority.

## Risks And Blockers

1. Duplicate kernel risk: MemoryLattice, ContextCompiler, read_memory_context,
   MemoryPalace, and Claude hooks all currently shape memory/context.
2. Authority confusion: Smriti, conversation logs, Chetana staging, vector
   indexes, and agent memory can look like truth but are mostly raw or
   generated memory.
3. Write bypass: many modules write directly to memory-like stores.
4. Scale risk: 243 GB LanceDB and 24 GB conversation logs make naive scanning
   unacceptable. Adapters need streaming, sampling, watermarks, and health
   summaries.
5. Empty schema risk: runtime.db has `memory_facts` and `memory_edges`, but the
   observed DB has zero rows. Do not assume those tables represent current
   memory coverage.
6. Chetana backlog risk: 43,505 staged files versus 308 wiki files means most
   Chetana material is not canon.
7. External context risk: Claude hooks inject and write memory outside the repo.
   MemoryKernel must account for them even if it cannot own them immediately.
8. Privacy/secrets risk: raw home logs and transcripts likely contain sensitive
   material. Census should record path/schema/count/health, not dump content.
9. Routing memory ambiguity: `RoutingMemoryStore` exists, but its default SQLite
   file was not present in the observed location. Routing learning may be
   living in telemetry and JSONL instead.

## Recommended MemoryKernel Organ

```text
dharma_swarm/memory_kernel/
  __init__.py
  atoms.py                 # MemoryEpisode, MemoryFact, MemoryEdge, MemoryChunk, MemoryUse
  surfaces.py              # MemorySurface, authority, role, health, risk
  registry.py              # mandatory roots and discovered surfaces
  facade.py                # MemoryKernel public API
  authority.py             # authority labels, truth states, promotion eligibility
  retrieval_compiler.py    # lane quotas, context admission, conflict rendering
  use_feedback.py          # retrieval/use outcome bridge
  bypass_sentinel.py       # scans/warnings for direct memory writes
  knowledge_ops_feed.py    # normalized feed into KnowledgeOps
  adapters/
    base.py
    memory_plane.py
    runtime_state.py
    smriti.py
    conversation_log.py
    witness.py
    chetana_knowledge.py
    ontology.py
    vectors.py
    lancedb_metadata.py
    agent_memory.py
    strange_loop.py
    telos.py
    stigmergy.py
    claude_home.py
    codex_memory.py
    psmv.py
```

The public API should start read-first:

```python
class MemoryKernel:
    def list_surfaces(self) -> list[MemorySurface]: ...
    def summarize_surface_health(self) -> MemoryHealthReport: ...

    def iter_episodes(self, query: MemoryQuery | None = None) -> Iterator[MemoryEpisode]: ...
    def iter_memory_facts(self, query: MemoryQuery | None = None) -> Iterator[MemoryFact]: ...
    def iter_edges(self, query: MemoryQuery | None = None) -> Iterator[MemoryEdge]: ...
    def iter_source_chunks(self, query: MemoryQuery | None = None) -> Iterator[MemoryChunk]: ...
    def iter_retrieval_feedback(self, query: MemoryQuery | None = None) -> Iterator[MemoryUse]: ...
    def iter_witness_events(self, query: MemoryQuery | None = None) -> Iterator[WitnessEvent]: ...
    def iter_external_memory_atoms(self, query: MemoryQuery | None = None) -> Iterator[MemoryAtom]: ...

    def retrieve_context(self, request: MemoryContextRequest) -> MemoryContextBundle: ...
    def feed_knowledge_ops(self, request: KnowledgeOpsFeedRequest) -> KnowledgeOpsFeed: ...

    def record_use_feedback(self, feedback: MemoryUseFeedback) -> None: ...
    def propose_promotion(self, atom_id: str, reason: str) -> PromotionCandidate: ...
    def propose_archive(self, atom_id: str, reason: str) -> ArchiveCandidate: ...
```

In M1, all writes except retrieval/use feedback and maybe append-only observation
records should be disabled or routed to existing stores through explicit
adapters.

## M0 PR: Surface Census v3

Purpose: prove the map, expose hidden writers, and create the data contract for
future MemoryKernel adapters.

Add:

- `dharma_swarm/memory_kernel/atoms.py`
- `dharma_swarm/memory_kernel/surfaces.py`
- `dharma_swarm/memory_kernel/census.py`
- `dharma_swarm/memory_kernel/adapters/base.py`
- `scripts/memory_surface_census.py`
- `docs/architecture/memory_surfaces_census_v3.md`
- `tests/test_memory_surface_census.py`

Required census fields:

- `surface_id`
- `path`
- `owner_module`
- `role`
- `category`
- `authority_level`
- `write_mode`
- `adapter_mode`
- `active_status`
- `last_modified`
- `size_bytes`
- `record_count`
- `schema`
- `tables`
- `provenance_quality`
- `promotion_path`
- `canon_risk`
- `pii_secrets_risk`
- `latency_risk`
- `known_writers`
- `known_readers`
- `feeds`
- `source_of_truth_for`
- `projection_of`
- `migration_status`
- `do_not_migrate_reason`

Acceptance:

- Census includes all mandatory surfaces listed in this audit.
- Large surfaces are summarized without full content scans.
- Vector/LanceDB surfaces are labeled projections.
- Chetana staging is not labeled canon.
- Smriti is labeled low-authority session memory.
- Witness is labeled provenance/audit evidence.
- Hidden write paths are reported.
- Tests use synthetic temp stores, not local private data.

## M1 PR: Read-Only MemoryKernel Facade

Purpose: make one callable organ without changing authority yet.

Read-only adapters first:

- `memory_plane.db`: events, turns, idea shards, idea links, idea uptake, retrieval feedback
- `runtime.db`: session events, routing decisions, context bundles, memory facts/edges
- `~/.smriti/smriti.db`: episodic/session/procedural candidates
- `~/.dharma/conversation_log/*.jsonl`: streaming adapter only
- `~/.dharma/witness/**/*.jsonl`: witness atoms
- `~/.dharma/knowledge/{staging,wiki,quarantine}`: Chetana lifecycle atoms
- `~/.dharma/ontology.db`: semantic graph atoms
- `~/.dharma/vectors.db` and `~/.dharma/lancedb`: metadata/pointer adapters only
- `~/.dharma/agent_memory`: agent scoped memory
- `~/.dharma/db/memory.db`: StrangeLoop compatibility
- `~/.dharma/db/messages.db`: message/event adapter
- `~/.dharma/telos`: intent graph adapter
- `~/.dharma/stigmergy`: coordination blackboard adapter
- `~/.claude`: hooks/cabinet/session-data adapter with content caps
- `~/.codex/memories`: Codex/MCP memory adapter
- `~/Persistent-Semantic-Memory-Vault`: external vault adapter, excluding virtualenv/vendor dirs

Do not migrate in M1:

- LanceDB payloads
- vector embeddings
- Chetana wiki/canon
- Telos objectives/strategies
- ontology graph authority
- raw conversation logs
- PSMV documents

## M2-M4: Enforcement Sequence

M2: KnowledgeOps bridge

- `KnowledgeOpsExtractor` consumes MemoryKernel feed in addition to repo docs.
- Generated concept cards keep source refs and authority tiers.
- No KnowledgeOps promotion without human/gate review.

M3: Retrieval compiler

- `ContextCompiler` asks MemoryKernel for context bundles.
- `read_memory_context` becomes a compatibility wrapper.
- Claude preamble hook gets a prior retrieval controller in read-only/log-only
  mode.

M4: Write gate and bypass sentinel

- New memory-like writes must be through MemoryKernel or through an approved
  legacy adapter.
- CI/test scanner flags direct writes to known memory roots.
- Existing direct writers get one of three statuses: adapter-owned, legacy
  tolerated, or unsafe.

## Non-Negotiable Rules

1. Everything that remembers must be registered.
2. Every surface must be classified as truth, raw evidence, projection,
   telemetry, lifecycle, external exocortex, or dormant/unsafe.
3. Projection stores cannot be promoted to authority.
4. Chetana staging, Smriti auto-extracts, and agent self-memory are not canon.
5. Witness proves provenance, not truth.
6. KnowledgeOps consumes normalized MemoryKernel atoms; it should not scrape
   random memory stores directly.
7. Context consumers should receive admitted bundles with source refs, truth
   state, confidence, and conflict warnings.
8. Raw stores over 1 GB require streaming adapters, watermarks, and size caps.
9. No migration or deletion before adapter parity is proven.
10. Human-reviewed gates are required for canonical promotion.

## Elephant Interpretation

"Elephant memory" is not a separate store found in this audit. It is the mature
system-level behavior once MemoryKernel, RetrievalCompiler, KnowledgeOps, and
promotion/forgetting gates operate together.

In concrete terms:

```text
Elephant = MemoryKernel organ + KnowledgeOps metabolism + governed retrieval
           + long-range external exocortex adapters + feedback-driven recall
```

Do not create a new Elephant database. Make MemoryKernel strong enough that the
whole ecosystem behaves like one long-range memory system.

## Build Recommendation

Proceed with MemoryKernel, but build it as an organ:

```text
SurfaceRegistry
  -> AdapterBus
  -> NormalizedAtoms
  -> AuthorityEngine
  -> RetrievalCompiler
  -> UseFeedback
  -> KnowledgeOpsFeed
  -> BypassSentinel
```

The first PR should be M0 census only. The second should be M1 read-only facade.
Only after those two are proven should writes, migrations, canonical promotion,
or retirement of old memory modules begin.

This is the highest-confidence build because it respects the existing working
substrates, catches the missing external surfaces, prevents another duplicate
kernel, and gives KnowledgeOps one clean feed without pretending projections or
raw transcripts are truth.

## Six-Agent Full-Pass Addendum

This addendum folds in the six-agent audit pass plus a local mechanical scan of
repo files, home memory roots, SQLite stores, JSONL roots, hidden writers,
consumer call flows, KnowledgeOps boundaries, and cross-worktree drift.

The conclusion did not change: MemoryKernel should be the single memory organ
contract, not a new storage monopoly. What changed is the surface area. The
ecosystem is larger than the first pass captured.

### Updated Confidence

No honest audit can claim 100 percent completeness for a live multi-worktree,
hook-driven, daemon-backed system without runtime write tracing. The six-agent
pass gets the map close enough to build M0/M1, but the final few percent require
a sentinel that observes actual writes while the system runs.

| Scope | Confidence | Reason |
|---|---:|---|
| Architecture direction | 0.95 | Multiple independent passes agree on facade/adapter/kernel, not one DB. |
| Primary repo memory modules | 0.96 | Filename, semantic, and source scans converge on the same core modules. |
| Static write paths in live worktree | 0.94 | Main writes are mapped; dynamic/env-selected paths remain possible. |
| Direct context consumers | 0.95 | `read_memory_context`, `build_agent_context`, prompts, TUI, MCP, and cron are mapped. |
| Local home-store inventory under targeted roots | 0.96 | Major DBs, JSONL roots, and bulk stores were counted. |
| KnowledgeOps/Chetana authority boundary | 0.94 | Existing docs/code clearly separate evidence, proposals, canon, and human approval. |
| Cross-worktree divergence awareness | 0.88 | Major divergent modules are known, but 100+ worktrees cannot be exhaustively reasoned by static summary alone. |
| External hooks/exocortex surfaces | 0.90 | `.claude`, `.smriti`, PSMV, Codex memory, and m5-handoff are mapped; cloud/network stores remain outside this pass. |
| Runtime-only/daemon-active writes | 0.78 | Needs live tracing of file opens, SQLite writes, launchd/cron, and active daemon behavior. |
| "Nothing important missing" claim | 0.82 | Good enough to start M0/M1, not good enough to claim final closure. |

The practical target is:

```text
M0 static census confidence: 0.95+
M1 read facade confidence: 0.90+
M2 runtime bypass sentinel confidence: 0.98+
Only after M2 should "all memory writes are known" be treated as operationally true.
```

### New High-Impact Surfaces

The full pass added these surfaces to the mandatory MemoryKernel registry:

| Surface | Role | Authority |
|---|---|---|
| `~/.dharma/lancedb/palace_docs.lance` | Huge vector/projection index; 243 GB | Projection only |
| `~/.dharma/conversation_log` | Raw conversation JSONL; 24 GB | Raw episodic evidence |
| `~/.dharma/knowledge/extracts` | Extracted knowledge JSONL; 1.73 GB | Candidate evidence/projection |
| `~/.dharma/terminal_tui/session.log` | Terminal telemetry log; 5.18 GB | Telemetry/raw evidence |
| `~/.dharma/vectors.db` | SQLite vector/FTS projection | Projection only |
| `~/.dharma/db/memory_plane.db` | Main event, turn, shard, retrieval substrate | Raw memory substrate |
| `~/.dharma/state/runtime.db` | Runtime/control-plane state | Runtime state, high operational authority |
| `~/.dharma/db/knowledge_store.db` | Concepts, propositions, prescriptions | Knowledge substrate, not canon by itself |
| `~/.dharma/db/temporal_graph.db` | Co-occurrence and temporal concept graph | Projection/evidence |
| `~/.dharma/ontology.db` | Semantic/ontology graph | Higher authority, gated by ontology rules |
| `~/.dharma/db/messages.db` | Message bus/event/subscription state | Runtime communications substrate |
| `~/.dharma/interop/message_bus.sqlite` | Interop messages/artifacts | Interop runtime evidence |
| `~/.dharma/sessions` | Operator session stores | Raw/session evidence |
| `~/.dharma/agent_interop` | Agent interop JSONL | Coordination evidence |
| `~/.dharma/kaizen/ops.db` | Kaizen/ops health events | Ops telemetry |
| `~/.dharma/stigmergy*` | Agent blackboard marks | Coordination evidence, not truth |
| `~/.dharma/ginko` | Ginko JSONL notes/logs | External/lifecycle evidence |
| `~/.dharma/meta` | Memory inventories, catalytic/concept graphs, histories | Mixed registry/projection/staging |
| `~/.dharma/frontier_council` | Snapshot DB replicas | Dormant/snapshot evidence |
| `~/.claude/projects` | Huge Claude transcript/exocortex root | External raw exocortex |
| `~/.claude/hooks` | Prompt/session memory injectors and writers | Active external write/read policy surface |
| `~/.claude/cabinet` | Cabinet documents | External curated-ish exocortex |
| `~/.claude/agent-memory` | Agent memory logs | External agent-scoped memory |
| `~/.codex/memories/mcp-memory.jsonl` | Codex MCP memory | External agent-scoped memory |
| `~/Persistent-Semantic-Memory-Vault` | PSMV external semantic vault | External exocortex/canon candidates |
| `~/m5-handoff` | Handoff bundle with Smriti and hooks | Dormant/snapshot evidence |
| Repo `.dharma/*` | Embedded project-local state | Repo-local state/snapshot |
| Repo `.swarm/memory.db` | Swarm-local memory DB | Repo-local dormant/empty substrate |
| Repo literal `~/.dharma/*` | Accidental fixture/snapshot path | Unsafe/dormant, must not be treated as home |

### Updated Store Counts

The most important home-store counts from the full pass:

| Store | Key counts |
|---|---|
| `~/.dharma` | 279 GB, 283,994 files, 2,788 dirs, 4,197 JSONL, 56 SQLite-ish DBs |
| `~/.claude` | 40 GB, 35,822 files, 22,988 dirs, 12,689 JSONL |
| `~/Persistent-Semantic-Memory-Vault` | 979 MB, 24,282 files, 1,421 dirs |
| `~/.smriti` | 7.2 MB, 1 SQLite DB |
| `~/.dharma/vectors.db` | `vec_documents=746712`, `vec_embeddings_fallback=746712`, `vec_fts=746712` |
| `~/.dharma/db/memory_plane.db` | `idea_links=2888130`, `idea_shards=103584`, `idea_uptake=55478`, `event_log=11381`, `conversation_turns=3867` |
| `~/.dharma/ontology.db` | `objects=5827`, `links=3968`, `lineage_edges=7792`, `lineage_inputs=7800`, `lineage_outputs=7792` |
| `~/.dharma/db/messages.db` | `messages=198249`, `events=3610`, `subscriptions=44`, `heartbeats=22` |
| `~/.dharma/state/runtime.db` | `session_events=39563`, `sessions=549`, `routing_decisions=3264`, `delegation_runs=923`, `task_claims=923` |
| `~/.dharma/db/knowledge_store.db` | `concept_index=8620`, `propositions=1623`, `prescriptions=666` |
| `~/.dharma/db/temporal_graph.db` | `co_occurrences=158935`, `concept_sources=5301`, `concepts=1752` |
| `~/.dharma/db/memory.db` | `memories=3981` |
| `~/.dharma/agent_memory/memories.db` | `memories=123`, `shared_memories=0` |
| `~/.smriti/smriti.db` | `memories=6660`, `entities=8`, `relations=5`, FTS rows=6660 |
| `~/m5-handoff/smriti/smriti.db` | `memories=361`, `entities=0`, `relations=0`, FTS rows=361 |
| `~/.dharma/db/tasks.db` | `tasks=2411` |
| `~/.dharma/kaizen/ops.db` | `events=2129`, `cron_health=15` |
| `~/.dharma/data/dharma_graphs.db` | `semantic_nodes=83`, `semantic_edges=489` |

Project-local embedded state also exists and must be separated from home state:

| Repo-local store | Key counts |
|---|---|
| `dharma_swarm/.dharma/db/memory_plane.db` | `event_log=240`, `conversation_turns=1757`, `idea_shards=5476`, `idea_links=78688`, `idea_uptake=1170`, `retrieval_log=1375` |
| `dharma_swarm/.dharma/state/runtime.db` | `session_events=343`, most other runtime tables empty |
| `dharma_swarm/.dharma/ontology.db` | `objects=3604`, `links=2414`, `lineage_edges=6072` |
| `dharma_swarm/.dharma/db/messages.db` | `messages=5605`, `events=20`, `heartbeats=25`, `subscriptions=50` |
| `dharma_swarm/.dharma/db/memory.db` | `memories=3988` |
| `dharma_swarm/.swarm/memory.db` | Schema exists; core memory tables are effectively empty |

### Updated Writer Map

MemoryKernel must register these write families before claiming write control:

| Writer family | Existing paths | Kernel status |
|---|---|---|
| Memory plane events | `engine/event_memory.py`, `memory_lattice.py` | Adapter-owned raw event writes |
| Conversation memory | `engine/conversation_memory.py` | Adapter-owned turns, shards, uptake, links |
| Runtime state | `runtime_state.py`, `telemetry_plane.py` | High-authority runtime adapter |
| Unified index | `engine/unified_index.py`, `semantic_memory_bridge.py` | Projection writer only |
| Retrieval feedback | `engine/retrieval_feedback.py`, `agent_runner.py` | Kernel feedback service |
| Routing memory/witness | `routing_memory.py`, `route_witness.py`, `providers.py` | Telemetry/provenance adapter |
| Agent self-memory | `agent_memory.py`, `agent_memory_manager.py` | Legacy write path; gate and label untrusted until mediated |
| Conversation log | `conversation_log.py`, `api/routers/chat.py`, Claude `conversation_logger.py` | Raw episodic ingest source |
| Stigmergy | `stigmergy.py`, `api/routers/stigmergy.py`, Claude stigmergy hooks | Coordination adapter, not truth |
| Telos | `telos_graph.py`, `telos_gates.py`, `hooks/telos_gate.py` | Intent substrate; no kernel mutation of approved objectives |
| Inquiry/witness | `inquiry_substrate_chew.py`, witness logs | Witness adapter |
| Knowledge units/store | `knowledge_units.py`, `engine/knowledge_store.py`, `knowledge_ops/schema.py` | Candidate/projection adapter; canon gates remain separate |
| Temporal/ontology/lineage | `temporal_graph.py`, `ontology_hub.py`, `lineage.py` | Semantic evidence/gated ontology adapter |
| Bridge/ecosystem index | `bridge_registry.py`, `ecosystem_index.py` | Registry/projection adapter |
| Operator sessions | `operator_core/session_store.py`, `operator_core/permissions.py` | Session/audit adapter |
| Interop/message bus | `operator_core/interop.py`, `message_bus.py` | Interop runtime adapter |
| Hibernation | `hibernation.py` | Dormancy/state adapter |
| Scripts and probes | `scripts/compact_stigmergy.py`, `scripts/strange_loop.py`, `scripts/allout_autopilot.py`, `scripts/review_readiness_probe.py`, `scripts/tcs_history_writer.py`, `scripts/mimo_explorer.py` | Legacy/ad hoc; bypass sentinel must flag |
| Claude hooks | `~/.claude/hooks/*.py`, `.claude/settings.json`, `.claude/hooks.json` | External active writer/injector surface |

The audit also found duplicate GitNexus hook definitions in `.claude/settings.json`
and `.claude/hooks.json` with different commands/timeouts. MemoryKernel should
not fix that directly, but M0 should classify it as an external policy/context
surface with duplicate-hook risk.

### Updated Consumer Map

The most important cut point remains:

```text
dharma_swarm/context.py:600 read_memory_context
```

That function is the shared legacy throat for prompt memory. M1 should keep the
function name but make it a compatibility wrapper over:

```text
MemoryKernel.retrieve_context(...)
```

Then move consumers in this order:

1. `context.py:600 read_memory_context`
2. `context.py:1249 build_agent_context`
3. `agent_runner.py` prompt and system-prompt builders
4. `prompt_builder.py` TUI/director context snapshots
5. `context_compiler.py` bundle compilation
6. Pulse/cron context injection
7. `mcp_server.py` memory tools
8. `terminal_bridge.py` and `terminal_bridge_context.py`
9. Dashboard agent-memory APIs
10. Claude SessionStart/UserPromptSubmit hooks, via exported kernel context

Retrieval feedback is already a real loop:

```text
retrieve -> cite/use -> record outcome -> bias future retrieval
```

MemoryKernel should preserve this loop and own the query/session IDs, source
refs, and feedback writes.

### KnowledgeOps Boundary Tightening

The full pass confirms that KnowledgeOps/Chetana must not be treated as ordinary
memory storage.

MemoryKernel may feed KnowledgeOps:

- episodes
- facts
- source chunks
- retrieval feedback
- witness events
- graph atoms
- lifecycle state
- confidence and authority metadata

KnowledgeOps may produce:

- concepts
- claims
- evidence bundles
- critiques
- decisions
- promotion candidates
- archive candidates
- generated projections/cards

KnowledgeOps must not silently mutate:

- human canon
- signed doctrine
- approved Telos objectives
- gate approval state
- curated wiki/public knowledge
- ontology authority rows

Authority precedence remains:

1. Current user/system instructions.
2. Canonical governance docs.
3. Typed ontology and signed doctrine.
4. Approved Telos/gate state.
5. Runtime evidence and witness logs.
6. Projections, candidates, summaries, and agent memories.

Chetana staging, generated KnowledgeOps cards, route witness records, temporal
co-occurrence, semantic salience, bridge confidence, routing scores, proposed
Telos objectives, and Smriti/Codex/Claude auto-memories are evidence or
candidates. They are not canon without promotion.

### Cross-Worktree Drift

The canonical worktree is not the whole system. M0 must include a worktree-aware
surface pass.

Important drift found:

- `dharma_swarm/knowledge_ops/*` is untracked in the canonical worktree but
  tracked in `promotion_worktrees/dharma_swarm_knowledge_ops_seed`.
- `dharma_swarm/correlation_context.py` exists as a tracked surface in 13
  worktree variants but not as a canonical tracked file in the main tree.
- `memory_palace.py`, `meta_daemon.py`, and `cron_runner.py` have 22 variants
  across worktrees.
- `daemon_config.py` has 18 variants.
- `context.py`, `context_agent.py`, `knowledge_extractor.py`,
  `cron_scheduler.py`, and several dashboard hooks/pages have 15 variants.
- `dharma_context_mcp.py`, `overnight_evaluator.py`, and
  `overnight_task_stager.py` have 12 variants.
- LF5/cutover/runtime branches contain divergent memory-adjacent modules,
  including `engine/conversation_memory.py`, `knowledge_units.py`,
  `session_ledger.py`, `mcp_server.py`, and daemon/dashboard surfaces.

MemoryKernel M0 should not try to merge these. It should register drift:

```text
surface_id
canonical_path
worktree_path
branch
tracked_status
hash
role
write_risk
migration_status
```

### Adapter Set After Full Pass

M1's adapter list should expand beyond the original obvious stores:

```text
memory_plane_adapter
runtime_state_adapter
memory_db_adapter
smriti_adapter
conversation_log_adapter
witness_jsonl_adapter
knowledge_lifecycle_adapter
knowledge_store_adapter
ontology_adapter
temporal_graph_adapter
vectors_metadata_adapter
lancedb_metadata_adapter
message_bus_adapter
interop_adapter
agent_memory_adapter
operator_session_adapter
stigmergy_adapter
telos_adapter
lineage_adapter
bridge_registry_adapter
ecosystem_index_adapter
kaizen_ops_adapter
ginko_adapter
meta_inventory_adapter
frontier_council_snapshot_adapter
repo_local_state_adapter
literal_tilde_snapshot_adapter
claude_hooks_adapter
claude_projects_adapter
claude_cabinet_adapter
codex_memory_adapter
psmv_adapter
m5_handoff_adapter
```

Vector/LanceDB adapters must expose metadata and pointers only. They must not
become authority.

### Remaining Blind Spots

To move from high-confidence static audit to operational near-certainty, add
these checks after M0:

1. Runtime write sentinel for `~/.dharma`, `~/.smriti`, `.claude`,
   `.codex/memories`, PSMV, repo `.dharma`, and repo `.swarm`.
2. SQLite write wrapper or trace for known DB paths.
3. Launchd, cron, tmux, and long-running daemon inventory.
4. Env-var path resolver audit for dynamic memory roots.
5. Cloud/network/MCP remote memory store audit.
6. CI scanner that rejects new direct memory writes unless registered.
7. Worktree drift scanner for memory-adjacent module variants.

This is the path to the user's requested "everything coordinated by
MemoryKernel" outcome:

```text
M0: Know every surface and writer.
M1: Read everything through adapters.
M2: Detect bypasses at runtime.
M3: Route context consumers through MemoryKernel.
M4: Enforce write gates and promotion policy.
```

Until M2 exists, the honest answer is: the picture is now comprehensive enough
to build the right MemoryKernel, but not comprehensive enough to claim that
every live write path has been captured.
