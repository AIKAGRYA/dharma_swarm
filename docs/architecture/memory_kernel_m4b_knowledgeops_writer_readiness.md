# MemoryKernel M4B KnowledgeOps And Writer Readiness

Date: 2026-05-14
Status: read-only readiness hardening

## Purpose

M4B restores the missing KnowledgeOps source path that earlier architecture docs
already described.  MemoryKernel atoms can now become bounded, JSONable
KnowledgeOps evidence artifacts without scraping memory stores directly and
without writing canon.

The same cut strengthens writer visibility: the writer sentinel now scans
`dharma_swarm`, `scripts`, and `api`, tracks module constants and instance
attributes, and registers the API/stigmergy/session/evolution writer families
that were invisible to the earlier pass.

## Implemented Source

```text
dharma_swarm/knowledge_ops/
  __init__.py
  cli.py
  memory_intake.py
  memory_conflict_review.py
  memory_promotion_queue.py
  memory_decision_ledger.py
  memory_promotion_executor.py
```

## Safety Contract

M4B does not:

- write to MemoryKernel, Chetana, wiki, ontology, runtime state, vectors, or logs
- mark any atom as canon
- copy raw atom content into KnowledgeOps reports
- expose local paths or secret-like refs in output artifacts
- route MemoryKernel atoms into prompts
- apply accepted decisions to live governance surfaces
- implement Chetana, canon, vector, or runtime mutations

M4B may write explicit JSON/Markdown review artifacts, but the CLI rejects
outputs under `.dharma`, `.smriti`, `.codex/memories`, repo-local `.dharma`,
and repo-local `.swarm`.

The promotion executor is deliberately a dry-run artifact emitter.  It consumes
valid `accept` decisions only, creates stable idempotency keys, records reviewer
and rationale fields after redaction, preserves source atom IDs, names the
intended governed target surface, and includes append-only rollback/tombstone
metadata.  Rejected, deferred, invalid, duplicate, projection, high-risk, and
superseded paths do not produce promotion requests.

## Writer Sentinel Upgrade

The current CI profile reports:

```text
registered writer specs: 58
present writers: 52
dormant missing writers: 6
unregistered surfaces: 0
action-required discoveries: 0
discovered write sites: 137
discovery roots: dharma_swarm, scripts
```

Unregistered discoveries remain visible as generated artifacts, operational
state, or test/experiment writes.  They are not promoted into governance truth.

Exact writer counts may drift as other agents land code.  The release-facing
claim is narrower: no unreviewed/action-required write discoveries and no
MemoryKernel writer surface that lacks an explicit triage classification.

## Operational 100% Definition

Operational 100% means accounted safe readiness, not unconstrained live memory.
The release gate is scoped to the seven required read-only MemoryKernel adapter
surfaces:

```text
home.memory_plane
home.runtime_state
home.smriti
home.witness
home.knowledge_wiki
home.codex_memory
home.conversation_log
```

A final ready run must satisfy:

- `make memory-kernel-readiness` exits 0.
- The adapter report uses `memory_kernel_readiness.v1` and
  `required_surface_count=7`.
- Every required surface has a registered adapter and no required surface is
  `unavailable` or `missing_adapter`.
- A required `degraded` row is not 100% until the warning is either removed or
  explicitly counted by code/tests as reviewed safe degradation.
- Non-required `missing_adapter` rows are allowed only as an accounted census
  backlog.  They must remain `required=false` and must not be read into live
  prompts or treated as a mandate to adapterize every home-state directory.
- Writer sentinel output has zero action-required discoveries and zero
  untriaged MemoryKernel writer surfaces.
- Context eval and shadow-sweep reports have zero hard failures; warnings are
  acceptable only when they preserve the shadow/no-write/no-prompt-injection
  contract.

The latest local dry run reports `status=ready`, `adapter_registered_count=81`,
`required_adapter_registered_count=7`, `required_ready_count=7`,
`required_surface_count=7`, `accounted_optional_count=74`,
`missing_adapter_count=0`, and `warning_count=0`.  That is the intended
operational 100% shape: all required surfaces are ready, and optional surfaces
are accounted without being promoted into unconstrained live memory.

This is ready for read-only KnowledgeOps review, governed dry-run promotion
artifacts, and shadow reporting. It is not approval for live prompt injection,
MemoryKernel write-through, canon promotion, vector rebuilds, or Chetana
mutation.  This also avoids the current `#191` supersession risk: older
KnowledgeOps seed material may remain useful as evidence, but this lane does
not treat it as live governance input without a fresh accepted request artifact.
