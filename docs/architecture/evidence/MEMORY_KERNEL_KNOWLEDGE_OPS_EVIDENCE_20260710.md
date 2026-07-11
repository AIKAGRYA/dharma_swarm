# Memory Kernel + Knowledge Operations Evidence Receipt — 2026-07-10

Status: dated evidence receipt; v0.2 candidate byte-pinned; remedial council rerun pending

Target: docs/architecture/MEMORY_KERNEL_KNOWLEDGE_OPS_MASTER_SPEC_V0.md

Captured: 2026-07-10T15:41:27Z through 2026-07-10T15:43:13Z

Local time: 2026-07-11T00:41:27+0900 through 2026-07-11T00:43:13+0900

Master-spec version: v0.2 research-only candidate

Master-spec SHA-256: 00d30b6e700da89c883077562be579097ac2ca80f3978071581928cdb0adce76

This receipt records commands, outputs, mutable host observations, primary-source
identity checks, and council artifacts used to review the target specification.
It is evidence of what was checked, not proof that every proposition in the
specification is true. Hashes establish byte identity only. Test and council
results do not grant epistemic or implementation authority.

## 1. Repository and environment basis

Repository:

~~~text
/Users/dhyana/dharma_swarm
~~~

Command:

~~~bash
git rev-parse HEAD
git branch --show-current
git status --short
git status --porcelain=v1 | wc -l
~~~

Observed before this receipt was added:

~~~text
HEAD: db5da6d864006340d58f9dc389437825e5e3436f
branch: agent/magpie-seed
dirty entries: 11

 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/nats_live_production_matrix/latest.json
 M reports/governance/track_portfolio.json
?? docs/architecture/MEMORY_KERNEL_KNOWLEDGE_OPS_HANDOFF_PROMPT.md
?? docs/architecture/MEMORY_KERNEL_KNOWLEDGE_OPS_MASTER_SPEC_V0.md
?? docs/governance/REMOTE_HOLON_MESH_AND_SHARED_BOARD_V1.md
?? reports/governance/ONBOARD_META_NOTEBOOK.md
?? reports/governance/nats_live_production_matrix/nats-live-20260708T005030Z-23095df4/
?? reports/governance/nats_live_production_matrix/nats-live-20260709T144535Z-f434a78a/
?? scripts/runtime/sync_agent_keys_to_vps.sh
~~~

The target specification was untracked and the checkout was already dirty.
Therefore the Git commit alone did not identify the reviewed document. The byte
identity above was recomputed after all v0.2 architecture edits and three
independent remedial review rechecks returned PASS. This receipt itself remains
an additional untracked path until committed. No pre-existing dirty path was
modified by this receipt task.

Environment:

~~~text
Darwin arm64, kernel 25.5.0
macOS 26.5.1 (25F80)
uv 0.11.2
Python 3.13.12
pytest 9.0.2
SQLite 3.51.0
~~~

## 2. Memory-surface census

Observed at 2026-07-10T15:42:15Z.

Command:

~~~bash
uv run python scripts/memory_surface_census.py \
  --repo-root . \
  --home /Users/dhyana \
  --dry-run
~~~

Exit: 0.

Material result:

~~~json
{
  "surface_count": 81,
  "existing_surface_count": 70,
  "missing_surface_count": 11,
  "discovery_enabled": false,
  "discovered_count": 0,
  "discovery_truncated": false,
  "by_authority": {
    "high": 1,
    "low": 61,
    "medium": 14,
    "none": 5
  },
  "by_status": {
    "active": 62,
    "disabled": 3,
    "expected_unavailable": 5,
    "missing": 3,
    "retired": 1,
    "snapshot": 6,
    "unsafe": 1
  }
}
~~~

The command was a dry run. It did not enable optional discovery.

## 3. Adapter-readiness result

Observed at 2026-07-10T15:42:15Z.

Command:

~~~bash
uv run python scripts/memory_kernel_readiness.py \
  --repo-root . \
  --home /Users/dhyana \
  --summary-only \
  --dry-run
~~~

Exit: 0.

Material result:

~~~json
{
  "schema_version": "memory_kernel_readiness.v1",
  "status": "ready",
  "summary": {
    "surface_count": 81,
    "observed_surface_count": 81,
    "accounted_surface_count": 81,
    "adapter_registered_count": 81,
    "required_surface_count": 7,
    "required_adapter_registered_count": 7,
    "required_ready_count": 7,
    "required_failure_count": 0,
    "missing_required_surface_count": 0,
    "degraded_count": 0,
    "total_ready_count": 64,
    "total_unavailable_count": 3,
    "total_warning_count": 3,
    "warning_count": 0
  },
  "warnings": []
}
~~~

The readiness label is limited to the implemented adapter/readiness contract.
It does not establish query relevance, semantic convergence, canonical writes,
or cross-store consistency.

## 4. Focused Memory Kernel verification

Observed at 2026-07-10T15:42:15Z.

Command:

~~~bash
uv run pytest -q \
  tests/test_memory_kernel_adapters.py \
  tests/test_memory_kernel_generic_adapters.py \
  tests/test_memory_kernel_readiness.py \
  tests/test_memory_context_eval.py \
  tests/test_context_compiler_memory_kernel.py \
  tests/test_memory_retrieval.py
~~~

Result:

~~~text
exit: 0
56 passed, 14 warnings in 3.06s
warnings:
  tests/test_memory_kernel_generic_adapters.py: 1
  tests/test_memory_retrieval.py: 13
  sklearn TruncatedSVD RuntimeWarning: invalid value encountered in divide
~~~

## 5. Broader legacy-memory regression group

The broader group was run immediately before this receipt by the root review
lane against the same checkout:

~~~bash
uv run pytest -q -p no:cacheprovider \
  tests/test_agent_memory.py \
  tests/test_agent_memory_manager.py \
  tests/test_agent_runner_memory.py \
  tests/test_memory.py \
  tests/test_memory_integration.py
~~~

Result:

~~~text
exit: 1
104 passed, 1 failed in 249.49s
~~~

Failure:

~~~text
tests/test_memory_integration.py:397
TestBackwardCompatibility.test_build_sections_accepts_knowledge_block

TypeError:
ContextCompiler._build_sections() missing 1 required keyword-only argument:
'memory_kernel_section'
~~~

The exact failing node was independently rerun during receipt construction:

~~~bash
uv run pytest -q -p no:cacheprovider \
  tests/test_memory_integration.py::TestBackwardCompatibility::test_build_sections_accepts_knowledge_block
~~~

Result:

~~~text
exit: 1
1 failed in 0.17s
~~~

This is a real backward-compatibility regression. The 56-test focused pass must
not be generalized into a claim that the broader legacy memory suite is green.

## 6. Live SQLite snapshot

The following queries were read-only logical queries over mutable local stores.
They were observed at 2026-07-10T15:41:47Z. Sizes are exact bytes; GiB/MiB
labels in the master specification are rounded display values.

### 6.1 Commands

~~~bash
stat -f '%N|%z|%Sm' -t '%Y-%m-%dT%H:%M:%S%z' \
  ~/.dharma/db/memory_plane.db \
  ~/.dharma/db/memory_plane.db-wal \
  ~/.dharma/db/memory_plane.db-shm

sqlite3 -readonly ~/.dharma/db/memory_plane.db \
  "SELECT 'event_log',max(rowid) FROM event_log
   UNION ALL SELECT 'source_documents',max(rowid) FROM source_documents
   UNION ALL SELECT 'source_chunks',max(rowid) FROM source_chunks
   UNION ALL SELECT 'retrieval_log',max(rowid) FROM retrieval_log;"

stat -f '%N|%z|%Sm' -t '%Y-%m-%dT%H:%M:%S%z' \
  ~/.dharma/db/memory.db \
  ~/.dharma/db/memory.db-wal \
  ~/.dharma/db/memory.db-shm

sqlite3 -readonly ~/.dharma/db/memory.db \
  "SELECT 'memories',max(rowid) FROM memories;"

stat -f '%N|%z|%Sm' -t '%Y-%m-%dT%H:%M:%S%z' \
  ~/.dharma/state/runtime.db \
  ~/.dharma/state/runtime.db-wal \
  ~/.dharma/state/runtime.db-shm

sqlite3 -readonly ~/.dharma/state/runtime.db \
  "SELECT 'session_events_max_rowid',max(rowid) FROM session_events
   UNION ALL SELECT 'context_bundles_max_rowid',max(rowid) FROM context_bundles
   UNION ALL SELECT 'event_log_count',count(*) FROM event_log
   UNION ALL SELECT 'source_documents_count',count(*) FROM source_documents
   UNION ALL SELECT 'source_chunks_count',count(*) FROM source_chunks
   UNION ALL SELECT 'retrieval_log_count',count(*) FROM retrieval_log;"

stat -f '%N|%z|%Sm' -t '%Y-%m-%dT%H:%M:%S%z' \
  ~/.dharma/vectors.db \
  ~/.dharma/vectors.db-wal \
  ~/.dharma/vectors.db-shm

sqlite3 -readonly ~/.dharma/vectors.db \
  "SELECT 'vec_documents_sequence',seq
     FROM sqlite_sequence WHERE name='vec_documents';
   SELECT 'vec_documents_count',count(*) FROM vec_documents;
   SELECT 'content_hash_non_null',count(content_hash) FROM vec_documents;
   SELECT 'content_hash_distinct_non_null',count(distinct content_hash)
     FROM vec_documents;
   SELECT name,sql FROM sqlite_master
     WHERE type='index' AND tbl_name='vec_documents';"
~~~

The stat command reports absent optional WAL/SHM paths as no row because stderr
was suppressed in the capture command.

### 6.2 Results

| Store | Exact size | Main-file mtime | Read-only result |
|---|---:|---|---|
| /Users/dhyana/.dharma/db/memory_plane.db | 4,953,976,832 bytes | 2026-07-02T14:27:35+0900 | max rowids: event_log=40,347; source_documents=14,735; source_chunks=74,609; retrieval_log=27,172 |
| /Users/dhyana/.dharma/db/memory.db | 3,911,680 bytes | 2026-07-11T00:06:34+0900 | memories max rowid=11,026 |
| /Users/dhyana/.dharma/state/runtime.db | 439,205,888 bytes | 2026-07-11T00:06:34+0900 | session_events max rowid=101,327; context_bundles max rowid=8,010; duplicate event_log/source_documents/source_chunks/retrieval_log counts all zero |
| /Users/dhyana/.dharma/vectors.db | 61,244,141,568 bytes | 2026-07-10T01:53:30+0900 | vec_documents sequence=24,796,967; current rows=24,735,271; non-null content_hash rows=1 |

At capture time runtime.db and vectors.db each had a zero-byte WAL and a
32,768-byte SHM file. No WAL/SHM file was returned for memory_plane.db or
memory.db.

### 6.3 Snapshot caveats

- These databases are live mutable state, not immutable historical artifacts.
- The master specification's July 10 memories max-rowid observation of 11,003
  had already advanced to 11,026 by this receipt.
- max(rowid) is a high-water observation, not a row count.
- sqlite_sequence=24,796,967 is the committed AUTOINCREMENT high-water mark,
  not the current vec_documents count.
- sqlite3 -readonly prevents SQL writes, but a WAL-mode reader may still
  participate in SQLite connection coordination through SHM state.
- A zero-byte current WAL does not prove that no uncheckpointed or historical
  WAL state existed at an earlier observation.
- Host paths, file mtimes, and counts can drift immediately after capture.
- This receipt stores query outputs, not copies of the databases or their
  protected contents.

## 7. Vector schema drift

Repository source at dharma_swarm/vector_store.py:540-601 creates
vec_documents without a content_hash column or dedup index. The current
VectorStore.upsert() at dharma_swarm/vector_store.py:697-745 always inserts and
does not populate content_hash.

The live database instead contains:

~~~sql
CREATE INDEX idx_vec_documents_dedup
ON vec_documents(content_hash, source, layer)
~~~

The index is not UNIQUE. The live table has a content_hash column, but only one
of 24,735,271 current rows had a non-null value at capture time. A repository
search found no source definition for idx_vec_documents_dedup or an
ALTER/ADD-COLUMN migration for vec_documents.content_hash outside the target
report:

~~~bash
rg -n \
  'idx_vec_documents_dedup|ADD COLUMN content_hash|content_hash.*vec_documents' \
  . -g '*.py' -g '*.sql' -g '*.md' \
  -g '!docs/architecture/MEMORY_KERNEL_KNOWLEDGE_OPS_MASTER_SPEC_V0.md'
~~~

Result: no matches.

Interpretation: the live schema contains untracked schema drift, while the
current writer remains non-idempotent. The live index does not establish a
working deduplication contract.

## 8. World Radar source-capture health

Observed at 2026-07-10T15:41:58Z.

Primary live health artifact:

~~~text
path: /Users/dhyana/.dharma/meta/world_radar/world_scout_health.json
size: 455 bytes
mtime: 2026-07-11T00:00:15+0900
sha256: 0c8afe3759f0b47ab1042fbf80140cc5c6b7d2508e5cd9a72d17fbab036b0c58
archive_enabled: false
archive_count: 0
archive_total_bytes: 0
archive_error_count: 0
successful_sources: 0
failed_sources: 0
~~~

Related older aggregate artifact:

~~~text
path: /Users/dhyana/.dharma/meta/world_radar/world_radar_health.json
size: 2,041 bytes
mtime: 2026-07-06T16:38:33+0900
sha256: c0b7de50ec61c0a7c2735130833dcf69bc627aeea020b76a08966189389de716
~~~

The health artifact supports only the state of that run. The implementation
finding is separately grounded in:

- dharma_swarm/world_radar/go_bridge.py:75-103,515-559 — Python archive flags;
- tools/world_scout_go/main.go:19-27 — Go CLI has no archive flags;
- tools/world_scout_go/scout.go:42-61,144-160 — response bytes are parsed into
  observations and not passed to an archive writer;
- tests/test_world_radar_go_bridge.py:131-224,233-289 — Python plumbing and
  simulated archive output, not a real Go archive implementation.

## 9. Recent primary-source verification manifest

Retrieval window: 2026-07-10T15:40Z. Verification here means that the primary
publisher page opened and its identifier/title/version metadata matched the
specification. It does not independently reproduce experiments or certify the
paper's conclusions. Page bytes were not archived by this receipt.

| Work | Primary page | Verified identity/version metadata |
|---|---|---|
| EvoMemBench: Benchmarking Agent Memory from a Self-Evolving Perspective | https://arxiv.org/abs/2605.18421 | arXiv:2605.18421; v1 submitted 2026-05-18; current v2 revised 2026-06-15 |
| LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues | https://arxiv.org/abs/2605.12493 | arXiv:2605.12493v1; submitted 2026-05-12; page labels it Work in Progress |
| MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks | https://arxiv.org/abs/2602.16313 | arXiv:2602.16313v1; submitted 2026-02-18 |
| GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents | https://arxiv.org/abs/2606.18829 | arXiv:2606.18829v1; submitted 2026-06-17 |
| RecMem: Recurrence-based Memory Consolidation for Efficient and Effective Long-Running LLM Agents | https://aclanthology.org/2026.findings-acl.1619/ | ACL Anthology ID 2026.findings-acl.1619; Findings of ACL 2026; July 2026; DOI 10.18653/v1/2026.findings-acl.1619 |
| Useful Memories Become Faulty When Continuously Updated by LLMs | https://arxiv.org/abs/2605.12978 | arXiv:2605.12978v1; submitted 2026-05-13 |
| Are We Ready For An Agent-Native Memory System? | https://arxiv.org/abs/2606.24775 | arXiv:2606.24775v1; submitted 2026-06-23 |

These seven rows close only the existence/identity challenge raised by one
council critic. They do not turn recent 2026 results into settled engineering
law.

## 10. Decorrelated review council receipts

### 10.1 Initial sandbox/network-blocked attempt

Receipt paths:

~~~text
reports/agentops/decorrelated_review_council/20260710T151529Z-memory-kernel-knowledge-ops-v0_1-hold_blockers.md
reports/agentops/decorrelated_review_council/20260710T151529Z-memory-kernel-knowledge-ops-v0_1-hold_blockers.json
~~~

SHA-256:

~~~text
02fa46d22a59e147809227cf55b9b2f44d3a7716fcb77a48ceef4c3cfcdd8945  markdown
a2a25c585ea761c97b3a3201f8194dc56d76d5971e4bb7da5a2513546867b2bc  json
~~~

Result:

~~~text
conviction_gate: hold_blockers
critics: 6 required=6
score_min: 0
score_avg: 0.0
critic outcome: all blocked by sandbox/DNS/network failure
persistent witness: palantir-pilot stopped and stale
~~~

This attempt contains no substantive six-model review signal.

### 10.2 Network-real retry

Receipt paths:

~~~text
reports/agentops/decorrelated_review_council/20260710T151943Z-memory-kernel-knowledge-ops-v0_1-network-retry-hold_blockers.md
reports/agentops/decorrelated_review_council/20260710T151943Z-memory-kernel-knowledge-ops-v0_1-network-retry-hold_blockers.json
~~~

SHA-256:

~~~text
413e6bbeb5c8b85f866ea530197b6bbf49d72e836b1a115ab1dcf29191e7d0d3  markdown
cc176f3bc4426944834f394ecbf09864bf63f759f6d0b6564e6f1534a4dbebed  json
~~~

Scores:

| Critic lane | Verdict | Score |
|---|---|---:|
| ollama:glm-5.2:cloud | revise | 84 |
| ollama:kimi-k2.7-code:cloud | revise | 78 |
| ollama:qwen3-coder:480b-cloud | revise | 82 |
| ollama:deepseek-v4-pro:cloud | approve | 100 |
| ollama:minimax-m3:cloud | approve | 90 |
| openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free | approve | 92 |

Aggregate:

~~~text
critics: 6 required=6
score_min: 78
score_avg: 87.67
approve: 3
revise: 3
conviction_gate: hold_blockers
persistent witness in receipt: stopped and stale
~~~

Council scores are opinions from correlated model systems, not independent
primary evidence and not a truth vote.

### 10.3 Witness status after the retry

At 2026-07-10T15:43:13Z:

~~~text
tmux session: dharma_palantir_pilot_a2a_worker
pane pid: 91772
pane command: uv
pane dead: false
worker command:
  uv run --with nats-py python
  scripts/runtime/palantir_pilot_a2a_worker.py
  --subject dharma.a2a.palantir-pilot
  --consumer palantir_pilot_a2a
  --stream DHARMA_FLEET
  --loop

heartbeat path:
  /Users/dhyana/.dharma/a2a_bus/worker_heartbeats/palantir-pilot.json
heartbeat timestamp: 2026-07-10T15:43:09Z
status: IDLE
cycle: 41
receipt_count: 0
~~~

The witness was live and producing fresh heartbeat state after the network-real
retry, but no completed final council rerun receipt existed at this capture
boundary. The valid council status therefore remains preliminary
HOLD_BLOCKERS. A later finalizer must append or link the final rerun receipt
rather than rewriting these historical results.

### 10.4 Full six-lane v0.2 review with fresh witness

Receipt paths:

~~~text
reports/agentops/decorrelated_review_council/20260711T001737Z-memory-kernel-knowledge-ops-v0_2-hold_blockers.md
reports/agentops/decorrelated_review_council/20260711T001737Z-memory-kernel-knowledge-ops-v0_2-hold_blockers.json
~~~

SHA-256:

~~~text
efc09b4ebbe6dffc1c28e8640118b4fc68511c7a2b991a04efcde17f4beeb5f4  markdown
bc90a2a56d188682d0fd5f0ad47914bea6fc38d9ddb39e9a96f05b16bce6aa83  json
~~~

| Critic lane | Verdict | Score |
|---|---|---:|
| ollama:glm-5.2:cloud | revise | 89 |
| ollama:kimi-k2.7-code:cloud | revise | 78 |
| ollama:qwen3-coder:480b-cloud | revise | 82 |
| ollama:deepseek-v4-pro:cloud | approve | 95 |
| ollama:minimax-m3:cloud | revise | 68 |
| openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free | approve | 93 |

Aggregate:

~~~text
critics: 6 required=6
score_min: 68
score_avg: 84.17
conviction_gate: hold_blockers
persistent witness: running, fresh=true, heartbeat_age_seconds=4
~~~

Every requested lane returned its requested provider/model family; no fallback
satisfied a required lane. The repeated minimax lane is a repeated measurement
from a correlated model, not independent corroboration of its earlier v0.1
approve. Council scores remain advisory critique, never evidence of factual
truth or standing.

This round identified real artifact/process and contract gaps alongside several
out-of-scope demands to implement already disclosed Phase 0 defects. v0.2 was
then remediated with: matching version/changelog and research-only fence;
gateway-only DML plus executable constructor-emission constraints; sealed
genesis, signed/fenced commits, append-only security-event batches/folds;
outbox shadow-definition identity; closed contradiction vocabulary; CRDT/root
pressure fixtures; separable-axis composition; concrete retention/tamper
defaults; store neutrality; Phase 0 owners/exit criteria; and immediately
implementable golden fixture specifications. Three independent focused rechecks
returned PASS after those edits. The next council run is a remedial review of the
byte-pinned candidate above; this historical HOLD_BLOCKERS result is preserved.

### 10.5 v0.2 closeout diagnostics

Observed at approximately 2026-07-11T00:33Z against the byte-pinned master spec:

~~~text
memory surface census: exit 0; 81 registered, 70 existing, 11 missing
adapter readiness: exit 0; status ready; 7/7 required; 81 accounted
focused kernel/retrieval tests: exit 0; 56 passed, 14 warnings in 2.65s
known compatibility node: exit 1; 1 failed in 0.16s at test_memory_integration.py:397
embedded SQLite DDL: parsed/executed in-memory; 260 lines; exit 0
local backticked references: 103 checked; 0 missing/out-of-range
master Markdown: 3,854 lines; 234,613 bytes; 112 balanced backtick fences
git diff --check on task-owned architecture files: exit 0
~~~

The known failing node is deliberately unchanged and is now a named P0 blocker
to live integration with owner and Phase 0 exit evidence. That is compatible with
the document's research-only status and incompatible with any merge/rollout
claim.

## 11. Receipt boundary

This receipt establishes:

- the exact repository HEAD and dirty-worktree disclosure;
- reproducible census/readiness commands and outputs;
- the focused 56-test pass and broader 104-pass/1-fail boundary;
- dated read-only observations of the four principal live SQLite stores;
- the live/repo vector-schema mismatch;
- the World Radar health artifact and code-level archive seam;
- primary publisher identity/version checks for seven challenged recent works;
- the exact preliminary and full v0.2 council artifact paths, hashes, scores,
  and fresh-witness state;
- the exact v0.2 master-spec byte identity and closeout diagnostics.

It does not establish:

- a clean or committed repository state;
- immutable database snapshots or historical WAL completeness;
- implementation of EMIR;
- production readiness;
- correctness of every cited paper;
- consensus, truth, or authority from the council score;
- closure of the one legacy regression;
- passage of the remedial council rerun until that separate receipt exists.
