# MemoryKernel M2A Writer Sentinel

Date: 2026-05-11
Status: read-only inventory

## Purpose

M2A makes memory-like write paths visible before any write gate exists.  It does
not intercept writes, redirect writes, migrate data, promote memories, or change
runtime behavior.

The rule is still:

```text
Every memory-like writer must be registered, classified, legacy-tolerated, or
called out as an unsafe/unowned bypass.
```

## Implemented Components

```text
dharma_swarm/memory_kernel/writers.py
  MemoryWriterSpec
  MemoryWriterObservation
  DiscoveredMemoryWrite
  DiscoveryTriageCategory
  MemoryWriterSentinel
  WriterClassification
  WriterStatus
  WriterDiscoverySummary

scripts/memory_writer_sentinel.py
  CLI summary, optional details, and optional AST write discovery
```

## Writer Registry

The registry now tracks the high-impact writer families by boundary, not only
individual methods:

```text
core stores:
  MemoryLattice
  RuntimeStateStore
  TelemetryPlaneStore
  EventMemoryStore
  ConversationMemoryStore
  RetrievalFeedbackStore
  UnifiedIndex
  VectorStore / TFIDFEmbedder
  RoutingMemoryStore

agent/session memory:
  AgentMemoryBank
  AgentMemoryManager
  conversation_log
  OrganismMemory
  SwarmManager delegated writes

semantic/graph/projection stores:
  SovereignMemoryPlaneAdapter
  SovereignSkillStoreAdapter
  SovereignEvaluationSinkAdapter
  SovereignLearningEngineAdapter
  BridgeRegistry
  EcosystemIndex
  SQLiteGraphStore
  KnowledgeStore
  LineageGraph
  OntologyHub
  TemporalKnowledgeGraph
  semantic_memory_bridge

runtime/control/witness writers:
  route_witness.emit_routing_decision
  HibernationManager
  KaizenOpsLocal
  Pruner
  LocalTraceStore
  algedonic_bridge._write_witness
  BhedGnanMonitor.write_witness
  PersistentAgent._write_witness
  ReplicationProtocol._write_witness
  TelosGatekeeper._log_witness
  telos_gates.check_action
  opportunity_dispatcher._write_review_warn
  Orchestrator._handle_task_failure
  consume_review_marks append/escalation writers
  check_packet_provenance.append_witness
```

Each writer declares target surface IDs, write mode, classification, risk, and a
short note.  The sentinel checks whether the code symbol exists and whether all
declared target surfaces are present in the MemoryKernel surface registry.

## Current Intent

This is pressure toward governance, not enforcement.  Present writers that
target unregistered surfaces are reported as `unregistered_surface` so the next
M0/M2 hardening pass can either add an explicit surface or mark the writer as
unsafe.

The first sentinel run surfaced two missing registry surfaces:

```text
home.router_audit_log
home.routing_memory
```

Both are now explicit M0 surfaces.  Future unregistered entries should be
treated as new memory bypasses until classified.

## Static Discovery

M2A.1 adds an AST discovery pass for likely memory-like writes.  It scans Python
files under `dharma_swarm/` and `scripts/` by default and detects:

```text
sqlite3.connect / aiosqlite.connect inside functions containing schema/write SQL
open(...) / aiofiles.open(...) with write or append modes
Path.open(...) with write or append modes
Path.write_text(...) / Path.write_bytes(...)
```

The scanner is intentionally heuristic.  It is a bypass detector, not proof of
semantic memory mutation.  SQLite read-only functions are filtered out unless
the enclosing function contains write/schema SQL.

Current repo snapshot:

```text
registered writer specs: 58
present registered writers: 52
registered writer targets missing from surface registry: 0
AST-scanned Python files: 935
likely memory-like writes discovered: 137
registered discoveries: 80
unregistered discoveries: 57
action-required discoveries: 0
```

The raw unregistered discovery count is no longer the only queue.  The current
triage split is:

```text
registered_memory_writer: 80
memory_writer_needs_spec: 0
surface_needs_registry: 0
read_write_helper: 0
operational_state: 30
generated_artifact: 19
test_or_experiment: 8
```

The immediate action queue is `memory_writer_needs_spec +
surface_needs_registry = 0`.  The other categories remain visible but should
not block gates until reviewed.

## Triage Categories

M2A.3/M2A.4 add automatic triage categories:

```text
registered_memory_writer
memory_writer_needs_spec
surface_needs_registry
read_write_helper
operational_state
generated_artifact
test_or_experiment
false_positive
```

This keeps discovery honest without pretending every hit is equally dangerous.
The highest-priority queues are `memory_writer_needs_spec` and
`surface_needs_registry`.  `read_write_helper`, `generated_artifact`,
`operational_state`, and `test_or_experiment` are still visible but should be
reviewed before becoming fail-gate blockers.

## CLI

```bash
python scripts/memory_writer_sentinel.py --repo-root .
python scripts/memory_writer_sentinel.py --repo-root . --details
python scripts/memory_writer_sentinel.py --repo-root . --fail-on-unregistered
python scripts/memory_writer_sentinel.py --repo-root . --discover
python scripts/memory_writer_sentinel.py --repo-root . --discover --discovery-details
python scripts/memory_writer_sentinel.py --repo-root . --discover --fail-on-action-required-discovery
python scripts/memory_writer_sentinel.py --repo-root . --discover --fail-on-unregistered-discovery
python scripts/memory_writer_sentinel.py --repo-root . --discover --markdown-out reports/memory_writer_sentinel.md
```

Registered-writer fail gates can pass today.  The action-required discovery gate
can also pass today because the current scan has no remaining
`memory_writer_needs_spec` or `surface_needs_registry` rows.  The stricter
unregistered-discovery gate should remain opt-in because generated artifacts,
operational state, read/write helpers, and tests remain intentionally visible
but non-blocking.

`--markdown-out` writes the human review artifact for M2A.2.  It includes
registered writer issues, discovery counts, triage category counts, top
unregistered source files, and the first unregistered discovery rows for triage.
