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
- mark any atom canonical
- copy raw atom content into KnowledgeOps reports
- expose local paths or secret-like refs in output artifacts
- route MemoryKernel atoms into prompts
- apply accepted decisions to live authority surfaces
- implement Chetana, canon, vector, or runtime mutations

M4B may write explicit JSON/Markdown review artifacts, but the CLI rejects
outputs under `.dharma`, `.smriti`, `.codex/memories`, repo-local `.dharma`,
and repo-local `.swarm`.

The promotion executor is deliberately a dry-run artifact emitter.  It consumes
valid `accept` decisions only, creates stable idempotency keys, records reviewer
and rationale fields after redaction, preserves source atom IDs, names the
intended target authority surface, and includes append-only rollback/tombstone
metadata.  Rejected, deferred, invalid, duplicate, projection, high-risk, and
superseded paths do not produce promotion requests.

## Writer Sentinel Upgrade

The CI profile now reports:

```text
registered writer specs: 97
present writers: 91
dormant missing writers: 6
unregistered surfaces: 0
action-required discoveries: 0
discovery roots: dharma_swarm, scripts, api
```

Unregistered discoveries remain visible as generated artifacts, operational
state, or test/experiment writes.  They are not promoted to authority.

## Readiness Meaning

This is ready for read-only KnowledgeOps review, governed dry-run promotion
artifacts, and shadow reporting. It is not yet approval for live prompt
injection, MemoryKernel write-through, canon promotion, vector rebuilds, or
Chetana mutation.  This also avoids the current `#191` supersession risk: older
KnowledgeOps seed material may remain useful as evidence, but this lane does
not treat it as live authority without a fresh accepted request artifact.
