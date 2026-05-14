# Memory Surfaces Census v3

Date: 2026-05-11
Status: M0 implementation scaffold

## Purpose

MemoryKernel M0 establishes the registry and read-only census layer for every
known memory-like surface in the Dharma ecosystem.  It does not migrate data,
promote canon, rewrite vectors, or merge stores.

The boundary is:

```text
memory-like surfaces
  -> MemoryKernel surface registry
  -> bounded health/schema probes
  -> normalized MemorySurface records
  -> later read-only adapters
  -> KnowledgeOps and context consumers
```

## Core Rule

Everything that remembers must become one of:

1. registered in MemoryKernel,
2. readable through a MemoryKernel adapter,
3. declared dormant/snapshot,
4. or marked unsafe/unowned.

## Implemented Files

```text
dharma_swarm/memory_kernel/atoms.py
dharma_swarm/memory_kernel/surfaces.py
dharma_swarm/memory_kernel/census.py
dharma_swarm/memory_kernel/adapters/base.py
scripts/memory_surface_census.py
tests/test_memory_surface_census.py
```

## Surface Schema

Each surface record includes:

```text
surface_id
path
owner_module
role
category
authority_level
write_mode
adapter_mode
active_status
health.exists
health.path_type
health.size_bytes
health.last_modified
health.record_count
health.schema
health.probe_error
summary.discovered_count
summary.discovery_enabled
summary.discovery_truncated
summary.discovery_entries_visited
summary.discovery_roots_scanned
summary.discovery_roots_skipped
summary.discovery_roots_unscanned_due_to_truncation
summary.discovery_root_status
provenance_quality
promotion_path
canon_risk
pii_secrets_risk
latency_risk
known_writers
known_readers
feeds
source_of_truth_for
projection_of
migration_status
do_not_migrate_reason
```

## Registered Surface Families

M0 registers the high-impact families found in the hard audit:

```text
home.dharma_root
home.memory_plane
home.runtime_state
home.memory_db
home.bridges
home.ecosystem_index
home.router_audit_log
home.routing_memory
home.hibernation
home.algedonic_signals
home.smriti
home.conversation_log
home.knowledge_root
home.knowledge_staging
home.knowledge_wiki
home.knowledge_quarantine
home.knowledge_extracts
home.knowledge_store
home.state_knowledge
home.ontology
home.temporal_graph
home.dharma_graphs
home.semantic_concept_graph
home.vectors
home.lancedb
home.witness
home.telos
home.agent_memory
home.agent_memory_db
home.organism_memory
home.messages
home.interop
home.sessions
home.agent_interop
home.stigmergy
home.traces
home.evolution
home.conversations
home.quality_gates
home.evals
home.cost_log
home.costs
home.artifacts
home.kaizen_ops
home.ginko
home.meta
home.meta_concept_graph
home.distilled
home.shared
home.citations
home.subconscious
home.campaigns
home.workspace
home.active_inference
home.gaia_ledger
home.gaia_platform
home.control
home.cron
home.alerts
home.custodians
home.jikoku
home.terminal_supervisor
home.frontier_council
home.terminal_tui
home.terminal_tui_session_log
home.claude_root
home.claude_hooks
home.claude_projects
home.claude_cabinet
home.claude_agent_memory
home.codex_memory
home.psmv
home.m5_handoff
repo.dharma_root
repo.memory_plane
repo.runtime_state
repo.swarm_memory
repo.literal_tilde_dharma
```

Current dry-run snapshot:

```text
registered surfaces: 78
existing surfaces: 69
missing surfaces: 9
explicit discovery enabled by default: false
```

The census also has opt-in bounded discovery for additional SQLite files and
JSONL directories under selected roots.  Discovery is off by default, entry
capped, depth capped, and skips known huge directories such as LanceDB,
conversation logs, terminal TUI logs, and extract roots.

Discovery is not adapter planning.  Unknown discovered surfaces are treated as
metadata-only until manually classified.  Repo-local discoveries under `.dharma`
or `.swarm` are snapshot metadata and `do_not_migrate`.

## Authority Rules

MemoryKernel classifies authority; it does not grant authority by ingestion.

- `memory_plane.db` is raw memory substrate, not canon.
- `runtime.db` is high-authority operational runtime state.
- witness logs prove provenance, not truth.
- Chetana/KnowledgeOps surfaces are metabolism and promotion candidates.
- `ontology.db` and Telos surfaces are medium-authority gated substrates in M0;
  individual objects can only become higher authority through their existing
  approval paths.
- `vectors.db`, LanceDB, temporal graphs, semantic salience, summaries, and
  cards are projections.
- Smriti, Claude, Codex, and agent self-memory are external or agent-scoped
  evidence unless promoted.
- repo-local `.dharma` and `.swarm` stores are snapshots/fixtures, including
  discovered unknown repo-local stores.
- repo literal `~/.dharma` is unsafe fixture state, not the user's home.
- census report output is refused inside known memory roots unless explicitly
  overridden.
- SQLite probes use immutable read-only connections and `PRAGMA query_only=ON`.
- SQLite probes are safe snapshots.  If a `-wal` file exists, the surface gets
  `immutable_probe_may_ignore_live_wal` because immutable probing may not see
  uncheckpointed live WAL changes.

## Running The Census

Dry run:

```bash
python scripts/memory_surface_census.py --repo-root . --dry-run
```

Discovery is off by default.  To include bounded unknown-surface discovery:

```bash
python scripts/memory_surface_census.py \
  --repo-root . \
  --discover \
  --max-discovered 128 \
  --max-discovery-entries 2048 \
  --dry-run
```

The summary reports whether discovery hit its caps:

```text
discovered_count
discovery_truncated
discovery_entries_visited
discovery_roots_scanned
discovery_roots_skipped
```

If `discovery_truncated` is true, treat the result as incomplete.  Raise caps
or add explicit registry entries before relying on it for completeness claims.
The `discovery_root_status` map shows whether each configured discovery root
was scanned, missing, truncated inside the root, or never reached because an
earlier root hit a cap.

Write reports:

```bash
python scripts/memory_surface_census.py \
  --repo-root . \
  --output-json reports/memory_surface_census.json \
  --output-md reports/memory_surface_census.md
```

Include SQLite table counts for registered count tables:

```bash
python scripts/memory_surface_census.py \
  --repo-root . \
  --probe-counts \
  --output-json reports/memory_surface_census.json
```

Counts are opt-in because some stores are large.  Directory probes are bounded
by `--max-dir-entries` and `--max-dir-depth`.

Report writes are intended for repo reports or temporary directories.  Output
paths under known memory roots such as `~/.dharma`, `~/.smriti`, `.claude`,
`.codex/memories`, repo `.dharma`, or repo `.swarm` are rejected unless
`--allow-memory-surface-output` is provided.

## M1 Handoff

M1 should add read-only adapters behind the same registry.  The first consumer
cut should be:

```text
dharma_swarm/context.py:read_memory_context
```

That function should become a compatibility wrapper over:

```text
MemoryKernel.retrieve_context(...)
```

M1 should not introduce promoted writes.  Write gates and runtime bypass
sentinels belong in later milestones.

The narrow M1 read facade is documented in
`docs/architecture/memory_kernel_m1_read_facade.md`.
