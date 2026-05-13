# MemoryKernel M1 Read Facade

Date: 2026-05-11
Status: M1.1 hardened read-only implementation

## Purpose

M1 adds read-only adapters and normalized `MemoryAtom` streams over selected
registered surfaces.  It does not add a memory database, write-through path,
promotion flow, archive flow, deduper, vector rebuild, or context rewiring.

The boundary remains:

```text
registered surfaces
  -> read-only adapters
  -> normalized MemoryAtom records
  -> later KnowledgeOps / ContextCompiler consumers
```

## Implemented Components

```text
dharma_swarm/memory_kernel/atoms.py
  MemoryAtom
  MemoryAtomType
  MemoryQuery
  MemoryOrder
  MemoryLane
  MemoryScope
  TruthState
  ReadMode

dharma_swarm/memory_kernel/adapters/base.py
  MemorySurfaceAdapter
  SurfaceProbe

dharma_swarm/memory_kernel/adapters/read_only.py
  MemoryPlaneAdapter
  RuntimeStateAdapter
  SmritiAdapter
  WitnessJsonlAdapter
  KnowledgeWikiAdapter
  CodexMemoryAdapter
  ConversationLogMetadataAdapter

dharma_swarm/memory_kernel/facade.py
  MemoryKernel
  MemoryKernelConfig
```

## Adapter Scope

M1 intentionally starts with the clearest surfaces:

```text
home.memory_plane
home.runtime_state
home.smriti
home.witness
home.knowledge_wiki
home.codex_memory
home.conversation_log
```

The first six expose bounded atoms.  `home.conversation_log` is metadata-only
in M1 because raw conversation logs are large and private.  A later streaming
adapter can add line-level access with stronger filters.

## Atom Contract

Each `MemoryAtom` carries:

```text
atom_id
surface_id
atom_type
content_ref
content
timestamp
source_path
authority_level
provenance_quality
projection_of
canon_risk
pii_risk
adapter_name
read_mode
surface_category
surface_role
memory_lane
scope
truth_state
confidence
freshness
valid_from
valid_until
source_refs
supersedes
promotion_allowed
context_admissible
metadata
```

The authority and risk labels are inherited from the surface.  This is the main
M1 safety property: adapters do not launder raw evidence or projections into
truth.

Defaults are conservative:

```text
promotion_allowed = false
context_admissible = false
truth_state != canonical
include_content = false
include_metadata_payloads = false
```

Consumers must ask explicitly for bounded content or metadata payloads.

## Query Contract

`MemoryQuery` controls read budgets and disclosure:

```text
limit_total
limit_per_surface
order_by = stable_id | newest | oldest
since
cursor
include_content
include_metadata_payloads
atom_types
```

`limit_total` is enforced by the facade across all selected surfaces.
`limit_per_surface` is enforced per surface, including SQLite surfaces with
multiple tables.  SQLite adapters no longer apply the limit independently per
table.  Atom-type filters are pushed into adapters before per-surface limits are
applied, so type-specific consumers are not starved by unrelated atom types.

`cursor` resumes after a previously returned `atom_id` within the adapter's
deterministic ordering.  In M1.1 this is a bounded continuation cursor:
cursored reads may scan past the page size up to `max_cursor_scan_atoms`, but it
is not a full unbounded export contract.

## Facade Methods

```text
list_surfaces()
summarize_surface_health()
list_adapter_ids()
get_adapter(surface_id)
iter_memory_atoms(...)
iter_episodes(...)
iter_memory_facts(...)
iter_source_chunks(...)
iter_retrieval_feedback(...)
iter_witness_events(...)
iter_external_memory_atoms(...)
```

These methods are read-only.  They are intended for KnowledgeOps and future
context integration, not for canonical promotion.

## Safety Rules

- SQLite adapters use immutable read-only snapshots and `PRAGMA query_only=ON`.
- SQLite WAL snapshot caveats are propagated onto emitted atoms.
- JSONL adapters stream bounded line counts.
- Markdown wiki reads are bounded by configured content size.
- Conversation logs expose metadata only.
- Atom ordering is deterministic: stable ID by default, with newest/oldest when
  timestamps exist and a metadata warning when a stable fallback is used.
- Cursor pagination is bounded; full traversal/export remains a later streaming
  adapter concern.
- Metadata payloads are omitted by default.  If included, content-like and
  private fields are redacted and serialized metadata is capped.
- Missing surfaces yield no atoms.
- Adapter limits default to conservative caps.
- No M1 adapter writes to any memory surface.
- No M1 adapter changes authority, promotes canon, archives stale memory, or
  rebuilds projections.

## Next Move

M2A writer inventory now exists and the action-required discovery queue is zero
for the current repo scan.  M2B adds the first KnowledgeOps read-only intake:

```text
MemoryKernel atoms -> evidence records -> KnowledgeOps/Chetana staging
```

The bridge should preserve source atom IDs, authority labels, truth state,
projection flags, and risk metadata.  It must not promote, dedupe canon, archive
sources, or route hot runtime context yet.  ContextCompiler integration should
wait until KnowledgeOps intake proves that evidence can be carried without
laundering raw memory into truth.
