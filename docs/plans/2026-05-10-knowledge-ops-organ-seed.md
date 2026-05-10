# KnowledgeOps Organ Seed

Status: seed plan, 2026-05-10.

KnowledgeOps is the semantic metabolism organ for Dharma Swarm. It turns scattered documents, code surfaces, runtime facts, broken-register entries, wiki material, and outside signals into linked knowledge that agents can retrieve, compress, compare, and act on.

## Role

KnowledgeOps owns semantic flow and lifecycle. It does not own execution, routing, kernel identity, ontology storage, or runtime state. Those remain with their existing organs.

Its loop is:

```text
ingest -> atomize -> link -> densify -> retrieve -> reflect -> promote/archive proposal
```

## Inputs

- Governance and architecture documents
- MEGAFILE slot surfaces
- Broken-register entries
- Runtime organ facts and system-map projections
- Code surfaces and import-facing modules
- Wiki and cabinet-adjacent knowledge
- Future Go sense-organ receipts

## Outputs

- JSONL knowledge nodes and edges
- Summary counts and drift signals
- Dense concept cards
- Agent context bundles
- Mode schedules for wake, sense, work, learning, reflection, sleep, dream, immune, promotion, and forgetting

## Boundaries

- Read-only in v0
- No database migrations
- No cron installation
- No ontology writes
- No archive moves
- No changes to execution organs
- Human review required before promotion or forgetting actions

## First Acceptance Gate

The seed is acceptable when the CLI can project a knowledge graph from the current repo, the focused tests pass, and the branch contains only the organ seed, its test, this plan, and generated DocOps count refreshes required by the repo hooks.
