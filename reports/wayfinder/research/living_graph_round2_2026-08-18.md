# Living Graph — Round 2 — 2026-08-18

**Ticket:** [Research: living graph round 2 — living memory, DharmaGraph-native, streaming event↔graph](https://github.com/AIKAGRYA/dharma_swarm/issues/1388) (child of Wayfinder MAP #1277)
**Provenance:** operator held round 1's living-graph verdict ("not sure abou tth eliving graph... needs more reserach"); round 1 = §Lane D of `badass_terminal_frontier_scan_2026-08-18.md` (same branch). Three lanes: living-memory systems (web), streaming event↔graph engines (web), DharmaGraph-native sweep (internal, claims verified against origin/main). Web citations fetched 2026-08-18; UNVERIFIED markers preserved.

---

## §0 Synthesis — the verdict

1. **The substrate dichotomy was false. The estate is already SQLite-native — the ledger exists.** `~/.dharma/state/runtime.db` is a 529 MB WAL-mode SQLite database on the *live dispatch path* (written via canon wiring `orchestrator.py:2527` → `durable_invoker.persist_evidence_receipt`): 144,679 `runtime_receipts` (with trace/correlation/causation/parent ids in schema), 116,216 FTS5-indexed `session_events`, 10,757 `delegation_runs`. Beside it: a genuinely append-only, hash-chained, tamper-refusing receipt log (`spine/receipt.py:299-325` → `~/.dharma/witness/claim_evidence_receipts.jsonl`), receipts already serialized as OTel GenAI spans (`spine/receipt.py:81-127`). And the DharmaGraph track's own spec claims exactly this territory: *"the receipt log as side-effect journal"*, *"receipts get monotonic offsets"*, *"SQLite: WAL + synchronous=NORMAL … Litestream"*, and §5: *"we deliberately do NOT build a new truth store of any kind"* (`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md`). **Architect's Gate answer: build on the organ — round 1's "adopt SQLite" was right by accident; there is nothing to adopt.**
2. **But be precise which organ.** The living graph = `runtime_state.py` + the receipt chain — NOT `dharma_swarm/graph/` as it stands: the Pregel engine is 24-of-27 modules dormant with an **empty checkpoint directory** (`~/.dharma/graph/` — zero files ever written). Its persistence types are right (thread-addressed checkpoints, `parent_checkpoint_id` fork lineage) and unused.
3. **"Living" now has a technical definition, and the answer is two layers.** Convergent across ActiveGraph ("The Log is the Agent"), PROJECTMEM, event-sourcing practice, and Graphiti's own internals: **immutable log primary, living graph as a rebuildable projection.** Living = (1) incremental ingest with entity resolution, no batch rebuilds; (2) bi-temporal supersession — facts invalidated, never deleted; (3) background consolidation (sleep-time compute); (4) provenance from every fact to its source episode; (5) rebuildability — the graph is disposable, re-projectable from the log. Roles must never merge: ledger never mutated, graph never trusted over its log. The write-rate mismatch (mechanical appends ~50k/s vs LLM-bound extraction ~seconds/episode) makes coupling them on one hot path a swarm-throttler.
4. **The gap is wiring, not architecture.** 10-query scorecard: **1 EXISTS, 5 PARTIAL, 4 ABSENT** — and three of the four ABSENTs are "the table/module exists and nobody calls it" (`artifact_links`, `memory_edges`, `retrieval_log`: schemas present, **0 rows**). Six wiring items close it: monotonic offset + tail cursor; `execution_identities` backfill 18%→100% + recursive-CTE walker; cost/token population on the write path (0.4%→~100%); wire the three dead tables; turn on `graph/persistence.py`; DSSE signing + file-touch refs. All are DharmaGraph-track territory — coordinate, don't unilaterally edit.
5. **Streaming lane: round 1's SQLite+DuckDB verdict survives round 2.** For one operator, DuckDB-on-poll + trigger-maintained rollups covers ~90%. Exactly two real capability gaps: **standing pattern alerts** (push-on-pattern-completion — Quine is the only right-sized closer: single JAR, MIT+Commons-Clause, pilot as a disposable sidecar that holds no truth) and **bitemporality** (first a *schema* choice — `valid_from/valid_to` + `recorded_at` + AS-OF views; adopt XTDB v2 only if retroactive re-grading becomes routine). Feldera = IVM fallback if triggers buckle. Amendments to round 1: Kùzu-dead needs a rider (MIT fork **LadybugDB** is genuinely active); **CozoDB is unmaintained — exclude**; Materialize is structurally mis-sized for solo-local.
6. **Living layer candidate: the Graphiti pattern** (bi-temporal KG over episodes, hybrid vector+BM25+graph search with no query-time LLM, local via FalkorDB-Lite embedded + Ollama). Benchmark honesty: LoCoMo is compromised (full-context baseline beats Mem0; a filesystem-grep agent scored 74.0%); graph memory's *proven* wins are *latency/token cost and temporal reasoning*, not raw recall. Freeform text2cypher is fragile (execution accuracy as low as 0.21 under paraphrase) — NL→query belongs in a slow analytics lane only.
7. **⚠️ LIVE DEFECT found during the sweep:** `runtime_receipts` last wrote **2026-08-15** while `session_events` wrote 2026-08-18 — the receipt write path stalled three days ago. Repair precedes any Helm build against the ledger. (Also: `~/.dharma/witness/` is 1.5 GB / 351,722 files of mostly unstructured md/txt — not queryable; the JSONL chain is the usable part.)

**Decision returned to operator:** lock the two-layer shape (existing ledger repaired + rebuildable living projection, no new truth store), lock ledger-only for leg one, or hold with a named axis for round 3.

---

## Lane G — Living-memory systems for agents (web; agent-gathered 2026-08-18)

### Findings

**(a) Living-graph memory systems, 2025-26 state.** [Graphiti](https://github.com/getzep/graphiti) (Zep's engine, ~30k stars, MCP server v1.0 Nov 2025) is the reference implementation: data enters as immutable **episodes**; an LLM incrementally extracts entities/edges with entity resolution against existing nodes — no batch recomputation. Edges are **bi-temporal**: four timestamps (system created/expired, world valid/invalid); a contradiction writes `t_invalid` rather than deleting, so the graph answers "what was believed when" and never serves superseded facts as current ([Zep paper](https://arxiv.org/abs/2501.13956)). Vendor numbers: DMR 94.8% vs MemGPT 93.4%; LongMemEval up to +18.5% accuracy at −90% latency. Zep Community Edition deprecated Apr 2025 — Graphiti is the only OSS piece; backends: Neo4j, FalkorDB (incl. embedded "Lite"), Neptune; Kuzu deprecated. **Letta/MemGPT**: context-as-RAM; editable in-context memory blocks + archival vector store + full message history; a [sleep-time agent](https://www.letta.com/blog/sleep-time-compute/) rewrites memory asynchronously — consolidation as background compute. SQLite default, Ollama for offline. **Mem0** ([paper](https://arxiv.org/pdf/2504.19413), ECAI 2025): write-time LLM chooses ADD/UPDATE/DELETE/NOOP per fact; SQLite append-only history + pluggable vector store; optional entity-graph variant. Paper numbers: LoCoMo J=66.9% (68.4% graph); temporal questions 58.1% vs OpenAI memory 21.7%. **Cognee**: typed Extract–Cognify–Load into hybrid graph+vector; default graph engine was Kuzu (dead upstream) — backend churn risk. **LangMem**: semantic/episodic/procedural + background consolidation over LangGraph's store. Note: none implements literal time-decay; "decay" in practice = supersession (Graphiti/Mem0) or consolidation (Letta/LangMem).

**(b) One substrate or two?** Three independent designs converge on **log-primary, graph-as-projection**. [ActiveGraph — "The Log is the Agent"](https://arxiv.org/abs/2605.21997) (2026): append-only event log is source of truth, working graph is a deterministic projection; payoff = exact replay, cheap forking, end-to-end lineage. [PROJECTMEM](https://arxiv.org/abs/2606.12329) (2026): local-first append-only typed event log with deterministic projections over MCP. Graphiti itself keeps raw episodes as ground truth beneath derived entities/edges; Mem0 keeps an append-only SQLite history beside its mutating memories. What breaks in one store: (1) consolidation/decay destroys audit and replay if the mutating graph is authoritative; (2) write-rate mismatch — mechanical appends (SQLite 50k+ inserts/s in-transaction) vs LLM-bound extraction (seconds/episode; Graphiti ingestion throughput UNVERIFIED beyond "LLM-in-loop") — coupling serializes the hot path; (3) query-shape mismatch (columnar scans vs multi-hop traversal).

**(c) Benchmark reality.** [LongMemEval](https://arxiv.org/abs/2410.10813) (ICLR 2025): commercial assistants drop ~30%. LoCoMo is compromised: conversations only ~16–26k tokens; a **full-context baseline (~73%) beats Mem0 (~68%)**; Letta's plain filesystem-grep agent on gpt-4o-mini scored **74.0%**; ~6.4% of golden answers wrong; <5-point gaps statistically indistinguishable. Vendor war: Mem0 scored Zep 65.99%; [Zep reproduced 75.14%±0.17](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/) alleging misconfigurations. 2026 successors: BEAM (Mem0 64.1→48.6 at 10M tokens); [LongMemEval-V2](https://arxiv.org/html/2605.12493v1) (25M–115M-token trajectories): best memory system 72.5% vs 69.3% memoryless — thin margins. Honest read: graph memory's proven wins are **latency/token cost and temporal reasoning**, not raw recall.

**(d) Semantic query.** Production systems keep LLMs **off the query hot path**: Graphiti fuses cosine + BM25 + graph BFS with RRF/MMR/cross-encoder rerankers, "typically sub-second." Freeform text2cypher: execution accuracy as low as 0.21 under paraphrase/schema generalization ([2026 study](https://arxiv.org/pdf/2511.08274)). Verdict: hybrid vector+FTS+graph works; NL→graph-query = slow analytics lane only.

**(e) Local-first fit.** Fully local on a Mac: Graphiti (FalkorDB-Lite embedded or Neo4j Desktop; Ollama loop), Letta (SQLite+Ollama), Mem0 OSS (graph variant needs a server), Cognee (embedded defaults, dead default graph engine), LangMem (Postgres). All ingest episodes/messages — every one is architecturally shaped to sit downstream of an event stream via an async consumer with a cursor.

### The living-vs-ledger verdict

**Two logical layers; round 1's ledger stands as the base.** "Living" = (1) incremental ingest + entity resolution; (2) bi-temporal supersession; (3) background consolidation; (4) provenance to source episode; (5) rebuildability. At solo scale the layers may share one machine — the roles must never merge: ledger never mutated, graph never trusted over its log.

### Top candidates for a local-first living layer

| System | Architecture | Backend (local) | Maturity | Fits over ledger? |
|---|---|---|---|---|
| **Graphiti** | Bi-temporal KG; episodes → entities/edges; edge invalidation; hybrid search, no query-time LLM | FalkorDB-Lite embedded or Neo4j; Ollama | High (~30k stars, paper; release churn) | **Yes — best fit**: `add_episode` is a natural ledger consumer |
| Mem0 OSS | LLM ADD/UPDATE/DELETE/NOOP facts; optional entity graph | SQLite + Chroma/FAISS; graph tier needs server | High adoption; benchmark-war baggage | Yes for facts; graph tier heavier |
| Cognee | Typed ECL pipelines → graph+vector | Kuzu (dead) + LanceDB + SQLite | Medium; churn risk | Conceptually yes; risky substrate |
| Letta | Memory blocks + sleep-time consolidation | SQLite; Ollama | High (product) | Partial — per-agent memory, not a swarm graph |
| LangMem | Semantic/episodic/procedural + consolidation | LangGraph store (Postgres) | Medium; LangChain-coupled | Partial — no graph semantics |
| ActiveGraph / PROJECTMEM | Log primary, graph = deterministic projection | Python research code | Research-grade (2026) | They **are** the pattern — steal the shape, not the code |

---

## Lane H — Streaming event↔graph engines (web; agent-gathered 2026-08-18)

### Findings

**(a) Quine (thatDot)** [ACTIVE]. Actor-per-node streaming graph; *standing queries* live inside the graph, accumulate partial matches, fire the instant a pattern completes, push to outputs (https://thatdot.com/products/quine). OSS alive — pushed 2026-08-12, v2.1.0 2026-07-22; company small (~$2M seed + CrowdStrike Falcon Fund; 361 stars — single-vendor risk). Single executable JAR, JDK 17+; embedded RocksDB/MapDB persistors [persistor detail not re-verified today]. License **MIT + Commons Clause** — fine for internal cockpit, restricts resale. Fit: literally the product's design center.

**(b) XTDB v2 (JUXT)** [ACTIVE]. v2.2.0-rc1 2026-08-06; MPL-2.0. Bitemporal per SQL:2011 — **valid time** (retroactively correctable) vs **system time** (immutable); `SELECT … FOR VALID_TIME AS OF …` (https://xtdb.com/blog/launching-xtdb-v2). JVM server (Postgres wire protocol), not embedded. Gives what SQLite lacks: retroactive correction without destroying audit ("task later judged FAILED, effective as of dispatch time"); forensic joins across both axes.

**(c) Incremental view maintenance.** **Feldera** [ACTIVE, MIT]: DBSP incremental engine, v0.335.0 2026-08-18, single Docker container — most credible lightweight-local true-IVM. **Differential dataflow** [MAINTAINED]: Rust library substrate. **Materialize** [ACTIVE, mis-sized]: local Emulator non-production; self-managed needs license key + k8s. **pg_ivm** [ACTIVE]: trigger-based IMMVs, requires Postgres. **SQLite**: no in-core IVM — honest equivalent is AFTER-INSERT triggers maintaining rollup tables. **LiveStore** [ACTIVE, Apache-2.0]: event log → materializers → reactive SQLite, but a TypeScript app framework (relevant only if cockpit-TS). cr-sqlite = CRDT sync, not IVM.

**(d) Other engines.** **Memgraph** [ACTIVE]: in-memory C++ Cypher + stream ingestion; BSL; RAM-resident, Docker-only on macOS. **KurrentDB** (EventStoreDB rebrand) [ACTIVE]: v26.1 shipped new JS projection engine + SQL access; wholesale ledger replacement. **SurrealDB** [ACTIVE]: 3.0 GA 2026-02; `LIVE SELECT` standing queries; embedded LIVE-query support UNVERIFIED. **CozoDB** [STALLED]: last push 2024-12-04 — do not build on it. **Kùzu** [ARCHIVED 2025-10-10; Apple acquisition per EU DMA filing, via theregister.com 2025-10-14]. Credible fork: **LadybugDB** [ACTIVE, MIT, 1.6k stars, v0.19.1 2026-08-04, Arrow/DuckDB interop] (https://ladybugdb.com); Kineviz bighorn [ACTIVE, small]. **HelixDB** [ACTIVE, Apache-2.0] Rust graph-vector OLTP — young, watch. **Raphtory** [ACTIVE, GPL-3.0]: Rust temporal-graph embedded via Python — as-of/windowed graph views; sleeper fit for "replay the swarm graph at time T."

**(e) Synthesis.** Keep SQLite ledger as sole record of truth. DuckDB-on-poll (sqlite_scanner) + trigger-maintained rollups covers ~90% for one operator. Two real gaps: (1) **standing pattern alerts** — "fire when agent spawns 3 children that all fail within 10 min" is push-on-completion; Quine is the only right-sized closer; pilot as disposable sidecar (holds no truth → vendor risk contained). (2) **Bitemporal corrections** — emulate in schema first (`valid_from/valid_to` + `recorded_at` + AS-OF views in DuckDB); adopt XTDB only if retroactive re-grading becomes routine (it would *replace*, not accompany, SQLite). Feldera = fallback when triggers buckle. Memgraph/KurrentDB/SurrealDB want to *be* the database — unjustified migration. LadybugDB/Raphtory = poll-time analytics options, not live layers.

### Capability-gap table

| Candidate | Unique capability over SQLite+DuckDB | Cost/risk | Verdict |
|---|---|---|---|
| Quine | Standing graph-pattern queries that push on match | JVM; MIT+Commons-Clause; tiny community | **Pilot as sidecar** if push-alerts needed |
| XTDB v2 | True bitemporal SQL | JVM server; replaces ledger role | Emulate in schema first |
| Feldera | True IVM, always-fresh views | Docker service; young APIs | Fallback when triggers buckle |
| pg_ivm / Materialize | IVM | Postgres swap / k8s+BSL | No (mis-sized) |
| Memgraph / KurrentDB / SurrealDB | in-mem Cypher / ES projections / LIVE SELECT | each wants to be the DB | No |
| LadybugDB | Embedded Cypher, DuckDB/Arrow interop | young fork governance | Optional poll-time graph projection |
| Raphtory | As-of/windowed temporal graph views | GPL-3.0; batch | Optional replay analytics |
| CozoDB | — | unmaintained since 2024-12 | Dead — exclude |

### What round 1 got right/wrong

Right: SQLite+DuckDB survives; Kùzu-archived call correct (now explained). Wrong/missed: LadybugDB rider needed; standing-query category skipped entirely; bitemporality is first a schema choice; local IVM reduces to triggers-or-Feldera; CozoDB fails the liveness check round 1 said to run on everything.

---

## Lane I — DharmaGraph-native sweep (internal; verified against origin/main 2026-08-18)

### What exists (per organ)

Verification: `git ls-tree origin/main dharma_swarm/graph/` = 27 modules; wiring confirmed at `origin/main:dharma_swarm/swarm.py:56,1799-1807` and `orchestrator.py:2527`; local tree dirty but **zero modifications** under the cited files — local = canon for everything cited. Disk numbers local.

**1. DharmaGraph engine — a real Pregel core that has never persisted a byte.** `graph/executor.py:1-14,82-83` genuine superstep engine (ready-set, barrier commit, checkpoint emission, `(node_id, seq)` identity); `graph/persistence.py:72-80` thread-addressed checkpoints with `parent_checkpoint_id` fork lineage. **Storage `graph/checkpoint.py:31-34` → `~/.dharma/graph/checkpoints` — directory does not exist; 0 files ever.** Production wiring = 3 of 27 modules (`reconciler`, `durable_invoker`, `state`); `scheduler/compiler/persistence/executor/channels/world/subgraph/interrupts/routing/effects` = 0 production importers. What it DOES write via `durable_invoker.persist_evidence_receipt` (`durable_invoker.py:157-211`) lands in **`runtime_state.py:30` → `~/.dharma/state/runtime.db` (529 MB + WAL, live)**:

| table | rows |
|---|---|
| `runtime_receipts` (receipt_id, type, run/task/trace/correlation/causation/parent ids, agent, idempotency_key, status, payload_json) | **144,679** |
| `session_events` (+FTS5) | **116,216** |
| `idempotency_records` | 40,753 |
| `delegation_runs` (+receipt_json, quarantined_at) | 10,757 |
| `task_claims` / `routing_decisions` / `provider_attempts` / `artifact_records` / `economic_events` | 11,382 / 9,757 / 9,471 / 4,750 / 2,336 |
| `execution_identities` | **1,940 (18% of runs)** |
| `event_log`, `operator_actions`, `artifact_links`, `memory_edges`, `retrieval_log`, `conversation_turns` | **0** |

**2. Receipts/provenance.** `EvidenceReceipt` (`spine/receipt.py:41-77`) already the right shape (trace/span/parent_span, tokens, cost_usd, routing_decision_id), serialized as OTel GenAI spans (`:81-127`). **Hash chain** `spine/receipt.py:153-156` → `~/.dharma/witness/claim_evidence_receipts.jsonl` (786 K) — genuinely append-only, refuses to extend a broken chain (`:299-325`). `~/.dharma/witness/` overall: 1.5 GB / 351,722 files, mostly unstructured. Stigmergy (`marks.jsonl` 494 K + 19 M archive) NOT append-only (decay rewrites). Traces → 462 MB; `TraceEntry.parent_id` + `get_lineage()` (`traces.py:130-149`) already walks chains; `cost_ledger.jsonl` 1.2 M. Catalytic graph = mutable JSON snapshot, not a ledger. memory_kernel has no store of its own (reads others).

**3. The 10-query scorecard: 1 EXISTS, 5 PARTIAL, 4 ABSENT.**

| # | Query | Verdict | Gap |
|---|---|---|---|
| 1 | Live tail | PARTIAL | no monotonic offset/tail cursor — poll only; `runtime_receipts` stalled 08-15 |
| 2 | Causal chain of act N | PARTIAL | `execution_identities` 18% coverage; no CTE walker |
| 3 | Cost by agent×task×day | PARTIAL | only 634/144,679 receipts carry cost_usd (0.4%); truth split across 3 stores |
| 4 | Replay to step k + fork | ABSENT | checkpoint dir empty; persistence has 0 importers |
| 5 | Diff run A vs B | ABSENT | no snapshots to diff |
| 6 | Acts touching file R | PARTIAL | file refs only in stigmergy/traces, not on dispatch receipts |
| 7 | Lineage of output O | PARTIAL | `artifact_links` = 0 rows; traces lineage exists |
| 8 | Acts lacking valid signed receipt | PARTIAL | chain verifier exists; nothing SIGNED (DSSE = Phase 4 rung 1, unbuilt) |
| 9 | Failure/latency concentration | EXISTS | `provider_attempts` indexed by error_class; no p50/p99 rollup view |
| 10 | Who wrote E / read since | ABSENT | `memory_edges`, `retrieval_log`, `artifact_links` all 0 rows |

**4. DharmaGraph track intent (cited).** The track **claims this territory and forbids a new store**: `DHARMAGRAPH_PHASED_SPEC_2026-07-05.md` §2 — *"snapshot-per-superstep + the receipt log as side-effect journal"*; *"Streaming = tailing the receipt log … receipts get monotonic offsets"*; *"SQLite: WAL + synchronous=NORMAL … Litestream v0.5 on the VPS"*; §5 — *"[do NOT build] a new truth store of any kind."* Phase 4 = observability/compliance ladder: rung 0 unify receipts (done) → rung 1 in-toto/DSSE → rung 2 Merkle tlog-tiles → rung 3 signed tree heads → rung 4 witness cosigning.

**5. Terminal bridge emissions.** `terminal_bridge.py:106` → `~/.dharma/terminal/` persists only `working_memory.json` (3.1 K, rolling last-8 turns) — **no request/response log, no receipt, no correlation id. The Helm surface is currently the least-instrumented organ in the estate.**

### Honest verdict

There is nothing to "adopt" — the estate is already SQLite-native and the track's spec §5 forbids a new truth store. The living transaction graph = `runtime_state.py` + the receipt chain, NOT the dormant Pregel engine. Already there (do not rebuild): event stream, failure/latency surface, OTel-shaped receipts, hash-chained tamper-refusing log, reconciler, idempotency, FTS5. Must be built (six items, all small, none a new store): (1) monotonic offset + tail cursor; (2) `execution_identities` backfill + CTE walker; (3) cost/token population on the write path; (4) wire the three dead tables (highest leverage: two full queries for writer-wiring only); (5) turn on `graph/persistence.py`; (6) DSSE signing + file-touch refs on dispatch receipts. **⚠️ Caveat flagged to operator: `runtime_receipts` last wrote 2026-08-15 vs `session_events` 2026-08-18 — the receipt path stalled; check before building on it.**

---

*Report compiled by Fable (session 2026-08-18). Two web lanes agent-gathered with per-claim URLs fetched 2026-08-18; internal lane cites file:line with origin/main verification noted. Decision on the two-layer lock returns to the operator on the map.*
