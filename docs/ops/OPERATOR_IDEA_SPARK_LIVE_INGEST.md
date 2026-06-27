# Operator Idea Spark Live Ingest

Operator Idea Spark is the receipt-backed front door for notes, transcript snippets, URLs, and idea shards.

Canonical command:

```bash
python -m dharma_swarm.idea_spark.cli ingest --text "Prototype governed memory retrieval for agent runtime." --domain "operator idea spark" --authority-level proposal
```

Common live drops:

```bash
python -m dharma_swarm.idea_spark.cli ingest --kind transcript --file screenshot-transcript.txt --source-ref screenshot://operator/drop
python -m dharma_swarm.idea_spark.cli ingest --url https://example.com/signal
python -m dharma_swarm.idea_spark.cli ingest --kind session --file session-snippet.jsonl
```

The CLI emits IDs and receipt paths, not raw input text. URL drops are `link_only` unless the operator supplies an excerpt with `--text`.

Lifecycle:

1. `OperatorInputReceipt` under `${DHARMA_STATE_DIR:-~/.dharma}/meta/idea_spark/input_receipts/`
2. `IdeaSparkCandidate` appended to `candidates.jsonl`
3. untrusted Chetana staged atom with `idea_spark_lifecycle`, `corr:<id>`, and `candidate:<id>` tags
4. governed MemoryKernel write and reviewed-canonical receipts under `memory_kernel/`
5. Semantic Commons owner route from `docs/ontology/semantic_objects.yaml`
6. proposal, task, or BetCard candidate, with dispatch authority off unless explicitly granted
7. retrieval proof by `correlation_id`

Health and retrieval:

```bash
python -m dharma_swarm.idea_spark.cli health --json
python -m dharma_swarm.idea_spark.cli retrieve --correlation-id <corr_id> --json
python -m dharma_swarm.chetana.cli query "idea spark"
gitnexus query -r dharma_swarm -l 5 "idea spark"
```

Memory MCP discovery for agent harnesses:

```text
mcp__memory.search_nodes({"query": "Operator Idea Spark ingest"})
```

Authority boundaries:

- Ingest never promotes Chetana atoms into trusted wiki by itself.
- MemoryKernel receipts are governed promotion requests by default, not protected-memory mutation.
- Raw content is retained only when source rights permit it.
- Supabase, pgvector, and hosted projection stores are future projection backends only; append-only receipts plus Chetana and MemoryKernel remain canon.
