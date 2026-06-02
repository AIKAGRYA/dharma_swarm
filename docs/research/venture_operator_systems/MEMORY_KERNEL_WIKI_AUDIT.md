# Memory Kernel / Karpathy-Style Wiki Audit

Date: 2026-06-02
Status: architecture audit

## Question

Are we using the Karpathy-style LLM wiki properly?

Short answer: partially. Dharma Swarm has the right organs, but this Operator OS mission is not yet in reliable agent-native recall.

## Current Receipts

Command:

```bash
./.venv/bin/python -m dharma_swarm.chetana.cli status
```

Observed on 2026-06-02:

```text
staged: 159357
trusted: 1318
quarantine: 11890
```

Command:

```bash
./.venv/bin/python -m dharma_swarm.chetana.cli query 'Polsia Cofounder VentureCell Operator OS Karpathy wiki MemoryKernel'
```

Observed:

```text
wiki: 0
catalytic: 0
gitnexus: 0
memory: 0
contextplus: 0
```

Notes:

- GitNexus CLI backend in Chetana currently calls an unavailable `gitnexus search` command.
- Memory and Context+ are only reachable through MCP/harness paths from the current Chetana Python process.
- Context+ direct MCP calls during this packet successfully mapped Darshan/operator_core/Chetana, but later semantic/memory graph calls hit transport closure.

## Existing Strengths

Chetana already has:

- staged, trusted, and quarantine tiers;
- provenance schema and axiom signatures;
- ingest/promote/revive/decay/gap-scan flows;
- graph unifier over wiki, catalytic graph, GitNexus, memory MCP, and Context+;
- MCP server skeleton;
- deterministic cross-update hooks after promotion;
- Darshan bundle ingest adapter.

Relevant files:

- `dharma_swarm/chetana/ingest.py`
- `dharma_swarm/chetana/promote.py`
- `dharma_swarm/chetana/provenance.py`
- `dharma_swarm/chetana/graph_unifier.py`
- `dharma_swarm/chetana/mcp_server.py`
- `dharma_swarm/chetana/wiki_log.py`
- `dharma_swarm/venture_cell/darshan/chetana_adapter.py`

## Gap

The memory kernel is not yet operating as "nanosecond grasp" for this mission because an agent cannot currently ask one question and reliably retrieve:

- Polsia funding, product claims, role model, risks, repo receipts;
- Cofounder departments, Canvas, tasks, Library, Plan/Execute, publishing, integrations;
- Darshan contact gate doctrine;
- Go receipt organ boundary;
- first-native-brick implementation spec;
- local DS surfaces and exact file owners;
- evaluation history and prior harness receipts.

The pieces exist, but the corpus is not linked into one trusted mission packet.

## Target Memory Architecture

Use Chetana as the canonical living wiki, not a side notebook.

Every serious Operator OS artifact should become:

1. Raw source receipt.
2. Staged Chetana atom.
3. Provenance-normalized frontmatter.
4. Trust decision.
5. Cross-update into index/related pages.
6. Query eval fixture.
7. Control-surface coverage row.

## Required Atom Classes

Create or stage atoms for:

- `Polsia company operator dossier`
- `Cofounder company OS shell dossier`
- `Dharma Swarm Operator OS consolidation spec`
- `Darshan external reader gate`
- `Go evidence receipt organ`
- `VentureCell lifecycle and autonomy ladder`
- `Chetana MemoryKernel retrieval evals`
- `External operator observation protocol`

Each atom must include:

- source URLs or local paths;
- captured date;
- trust tier;
- stale-after date;
- uncertainty notes;
- local related files;
- receipt references;
- query terms it is expected to satisfy.

## Retrieval Evals

Add a small eval file or script that asserts these queries return non-zero useful context:

- `Polsia Cofounder VentureCell Operator OS`
- `Darshan external reader gate Go evidence receipt`
- `Go evidence receipt source_url event_uid accepted`
- `Cofounder Canvas Library Plan Execute publishing`
- `Chetana wiki memory kernel staged trusted quarantine`
- `VentureCell autonomy ladder external action approval`

Passing means the query returns:

- at least one trusted/staged atom;
- at least one local source ref;
- at least one external source ref where relevant;
- freshness/trust metadata.

## Ingest Path For First Brick

When a Darshan external-reader event passes:

1. Gate validator returns accepted receipt refs.
2. Darshan Chetana adapter stages a receipt atom.
3. Atom links to bundle path, decision delta, Go receipt path, source pack, and control-surface row.
4. Atom remains staged until human review.
5. Promotion triggers cross-update into Operator OS and Darshan pages.

## Acceptance Criteria

The wiki is being used properly when future agents can retrieve the whole Operator OS context from Chetana before reading repo files or web sources.

Minimum first milestone:

- the six docs in this packet are ingested or staged;
- query coverage for the six eval queries is non-zero;
- every result includes provenance;
- stale external claims are marked for review;
- Chetana does not become an untrusted dump of marketing pages.

