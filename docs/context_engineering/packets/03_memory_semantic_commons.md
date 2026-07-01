# Packet 03: Memory, Semantic Commons, Wiki, And Vector Retrieval

Packet ID: `ctx.memory-semantic-commons`

Use when touching memory retrieval, semantic aliases/objects, wiki-vector ingest,
context compilation, knowledge promotion, or retrieval quality gates.

Do not use for generic documentation cleanup. Use `ctx.docops-hygiene-repo-governance`
for doc ownership and hygiene.

## Authority Model

- Intent owners: agent-admission-semantic-commons and memory-related tracks
- Surface owners: `docs/ontology/**`, `dharma_swarm/memory_retrieval.py`,
  `dharma_swarm/wiki_vector_ingest.py`, `dharma_swarm/vector_store.py`,
  `dharma_swarm/memory_kernel/**`
- State owners: `~/.dharma/knowledge/**`, `~/.dharma/state/runtime.db`, vector
  projection databases, memory reports
- Proof owners: memory live gates, retrieval benchmark reports, wiki ingest
  receipts, tests

Core invariant: retrieval is a projection and admission policy, not a new source
of truth.

## Mission

Make the repo's memory useful on purpose. Agents should know when to use exact
owner files, when to retrieve from wiki/vector space, when to ask graph-shaped
questions, and when to reject retrieved material as stale, unauthoritative, or
secret-bearing.

## First Reads

L0 Safety:

- `make onboard`
- `docs/ontology/session_orientation.yaml`

L1 Route:

- agent-admission-semantic-commons track in `ACTIVE_TRACK.yaml`
- `docs/ontology/SEMANTIC_COMMONS.md`
- `docs/ontology/retrieval_scope.yaml`

L2 Owners:

- `docs/ontology/semantic_objects.yaml`
- `docs/ontology/semantic_aliases.yaml`
- `dharma_swarm/memory_retrieval.py`
- `dharma_swarm/wiki_vector_ingest.py`
- `dharma_swarm/vector_store.py`

L3 Evidence:

- `reports/memory_kernel/**`
- `reports/governance/semantic_commons_projection_manifest.json`
- tests named `test_memory_*`, `test_vector_store_*`, and
  `test_wiki_vector_live_gate.py`

L4 Search:

- `rg -n "RetrievalQuery|GovernedRetrievalEngine|semantic_aliases|retrieval_scope" dharma_swarm docs tests scripts`
- wiki search terms: "semantic commons", "memory retrieval", "context compiler",
  "wiki vector"

L5 Seat:

- `context_librarian`, `strategy_librarian`, or `cybernetics_codex` only when
  their current seat files are relevant and fresh.

## Live Probes

```bash
make onboard
python3 scripts/memory_retrieval_system_gate.py
python3 scripts/wiki_vector_live_gate.py
python3 scripts/vector_store_live_gate.py
```

For code changes:

```bash
pytest tests/test_memory_retrieval.py tests/test_memory_retrieval_system_gate.py
pytest tests/test_wiki_vector_live_gate.py tests/test_vector_store_live_gate.py
```

## Retrieval Contract

Use adaptive retrieval:

- If the task names a canonical file or schema, read that file first.
- If the task asks "what happened" or "what did prior agents find", search
  reports and memory.
- If the task asks cross-organ "how are these related", use semantic aliases,
  orientation graph, and graph-style searches before broad vector search.
- If retrieval returns secrets, private text, or low-provenance snippets, reject
  or summarize only with source boundaries.

Suggested queries:

- "agent admission semantic commons retrieval scope"
- "memory retrieval system gate final top1 source diversity"
- "wiki vector ingest receipt discovered files reembed"
- "context compiler shadow parity memory kernel"

## Operating Loop

1. Identify whether the question is owner lookup, recall, relation traversal, or
   evidence search.
2. Read owner files for owner lookup.
3. Run retrieval only for recall/relation/evidence.
4. Check diagnostics and source family.
5. Use retrieved context only if provenance is clear.
6. Verify with memory gates or tests.
7. Write a handoff that lists accepted and rejected context.

## Guardrails

- Do not bulk-promote wiki/vector results into canonical docs.
- Do not treat vector similarity as authority.
- Do not import raw private notes into repo docs.
- Do not hide retrieval degradation.
- Do not skip exact owner files because retrieval returned a plausible answer.
- Do not add another memory substrate unless a track explicitly owns it.

## Context Budget

- Tiny: `make onboard`, semantic commons doc, this packet.
- Standard: tiny plus semantic aliases/objects, retrieval scope, memory gate
  report, relevant owner module.
- Deep: standard plus benchmark reports, wiki ingest receipts, tests, and graph
  projections.

## Done Criteria

Complete means:

- task type is classified;
- authoritative owners are read before retrieval claims;
- accepted context includes provenance;
- rejected context/degradation is named;
- retrieval gate or targeted tests are run for code changes.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.memory-semantic-commons.
Classify the task as owner lookup, recall, relation traversal, or evidence search.
Read canonical owners before retrieval. Use wiki/vector/graph only as projections
with provenance. Reject stale, secret-bearing, or unauthoritative context. Verify
with memory/vector/wiki gates or targeted tests, and leave accepted/rejected
context in the handoff.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.memory-semantic-commons",
  "task_type": "owner_lookup|recall|relation_traversal|evidence_search",
  "owner_files_read": [],
  "retrieval_queries": [],
  "accepted_context": [],
  "rejected_context": [],
  "diagnostics": [],
  "commands_run": [],
  "next_index_or_ingest_action": ""
}
```
