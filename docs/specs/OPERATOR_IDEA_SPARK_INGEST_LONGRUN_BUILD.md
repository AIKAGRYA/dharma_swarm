# Operator Idea Spark Ingest Long-Run Build Spec

Status: controlling long-run build spec
Created: 2026-06-26
Owner surface: operator input, Idea Spark, Chetana, MemoryKernel, Semantic Commons, TaskBoard, Verified Experiment Loop
Primary distinction: this is not SAB/Spark social canon. SAB remains an adjacent public protocol surface.
Delivery: ds-goal mission plus PR stack, not one mega PR.

## 1. Mission

Build the reliable path for this operator promise:

```text
idea / inspiration / transcript / public signal
  -> immutable source receipt
  -> normalized Idea Spark candidate
  -> deterministic triage tuple
  -> Chetana staged atom
  -> governed MemoryKernel / KnowledgeOps receipt
  -> trusted wiki synthesis only after promotion
  -> Semantic Commons route and owner surface
  -> proposal, task, or BetCard
  -> implementation / experiment evidence
  -> retrieval proof by correlation_id
```

The current system saves a lot of material, but the chain is fragmented. The
mission is not more capture. The mission is one correlation spine from fired-in
input to routed action and later recall.

## 2. Current Truth From The Deep Pass

### Working

- Go Idea Spark exists as a real, separate-from-SAB spine:
  `docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md`,
  `dharma_swarm/world_radar/analysis.py::_idea_spark_triage`,
  `dharma_swarm/world_radar/go_bridge.py`, and Go receipt modules.
- `make go-ci` passes for the Go ingest family.
- Chetana can ingest, promote, and query:
  `python -m dharma_swarm.chetana.cli status/query`.
- Conversation memory stores operator turns and harvests `idea_shards`; tests
  cover latent-gold recall and follow-up outcomes.
- `thinkodynamic_director.py` and `orchestrator.py` can use latent-gold shards
  as context signals.
- `insight_evolution_bridge.py` can turn world/Shakti insight rows into Darwin
  pending proposals with `dispatch_authority=False`.
- `opportunity_refill.py` can move qualified opportunities into
  `frontier_tasks_pending.jsonl`, then the existing runtime can drain that into
  TaskBoard.
- MemoryKernel promotion receipts exist and are human-gated.

### Not Yet Trustworthy

- The Karpathy-style wiki is alive as a capture substrate but stale as trusted
  synthesis: recent atom writes exist, but trusted concept promotion is lagging
  and the staging backlog is huge.
- Hermes wiki distillation can bypass the stronger Chetana promotion path by
  writing directly into live atoms.
- The advertised `wiki search/show` command is not installed in PATH; Chetana
  CLI is the executable path.
- Operator idea shards, world radar Idea Sparks, Chetana atoms, MemoryKernel
  receipts, Semantic Commons routes, TaskBoard rows, and Verified Experiment
  Loop BetCards are not connected by one required schema or one required
  `correlation_id`.
- No executable test proves: local idea or transcript fixture -> staged atom ->
  trusted wiki concept -> MemoryKernel receipt -> route -> owner task ->
  implementation receipt -> retrieval.
- YouTube transcript ingest is not a proven runtime path. Treat it as local
  transcript-shaped input until a source-rights-safe fetcher is built.
- Go archive wiring has drift risk: Python can construct archive flags for
  `world_scout_go`; the Go CLI must be kept in lockstep by an unmocked smoke
  test.
- `world_scout_health` and world signal identity need schema/dedupe hardening.

## 3. Non-Goals

- Do not merge this with SAB. SAB Spark/canon/challenge is a separate public
  protocol and can bridge in later.
- Do not scrape or store full copyrighted pages, videos, transcripts, labs, or
  course bodies automatically.
- Do not let Go write ontology, runtime authority, trusted memory, Chetana
  trusted wiki, or TaskBoard directly.
- Do not create a standalone BetCard class. Reuse the Verified Experiment Loop
  rule: BetCard is an extension/wrapper of existing `self_research.Hypothesis`.
- Do not promote an Idea Spark to runtime-changing action without human or
  existing policy approval.
- Do not make vector/LanceDB projections canonical authority.

## 4. Canonical Objects

### OperatorInputReceipt

One immutable receipt for the fired-in thing.

Required fields:

```text
schema_version       operator_input_receipt.v0
input_id             stable hash-derived id
correlation_id       shared join key for the full lifecycle
source_kind          note | transcript | youtube_transcript | session | url | file | world_signal | go_receipt | idea_shard
source_ref           local path, URL, receipt id, session id, or inline ref
source_rights        owned | operator_supplied | public_excerpt | link_only | unknown
content_hash         sha256 of raw supplied content or allowed extract
captured_at          UTC
captured_by          CLI/API/daemon/agent id
raw_storage_ref      file path or receipt ref; may be empty for link-only
redaction_policy     none | pii_redacted | summary_only | link_only
```

Rules:

- Raw content is kept only when source rights allow it.
- For YouTube or public web input, default to metadata, hash, short operator
  summary, source URL, and bounded excerpts unless the operator provides an
  owned transcript file.
- This receipt never mutates trusted memory.

### IdeaSparkCandidate

The normalized middle object shared by operator input, latent idea shards, and
world radar.

Required fields:

```text
schema_version       idea_spark_candidate.v0
candidate_id         stable hash over source receipt + normalized claim
correlation_id       inherited from OperatorInputReceipt or Go receipt
title
claim
why_now
domain
source_refs
evidence_refs
triage               idea_spark_triage.v0 tuple
promotion_status     rejected | watchlist | incubating | promotion_ready
routing_status       unrouted | routed | proposal_queued | task_queued | bet_opened | implemented | blocked
owner_surface        Semantic Commons owner/module path
authority_level      observation | proposal | task_candidate | experiment_candidate | trusted_memory
created_at
```

Rules:

- The existing world-radar `idea_spark_triage.v0` is the seed triage contract.
- Operator input and idea shards must be normalized into this object before they
  reach proposal or task queues.
- `promotion_ready` means "eligible for routed proposal/task review", not
  "allowed to mutate runtime".

### OperatorInputLifecycleReceipt

The closure receipt for the chain.

Required fields:

```text
schema_version             operator_input_lifecycle_receipt.v0
correlation_id
input_id
candidate_id
chetana_staged_atom_id
chetana_trusted_atom_id
memory_write_receipt_id
memory_canonical_receipt_id
semantic_route
owner_surface
proposal_id
task_id
bet_id
implementation_receipt_id
retrieval_probe_id
status                     captured | staged | routed | tasked | implemented | blocked | archived
blockers
evidence_paths
created_at
updated_at
```

At v0, many fields may be empty. The build is done only when the e2e fixture
fills the expected fields for each route class.

## 5. Target State Paths

Use existing roots and append-only files:

```text
~/.dharma/meta/idea_spark/input_receipts/*.json
~/.dharma/meta/idea_spark/candidates.jsonl
~/.dharma/meta/idea_spark/routing_receipts/*.json
~/.dharma/meta/idea_spark/lifecycle_receipts/*.json
~/.dharma/knowledge/staging/...
~/.dharma/knowledge/wiki/concepts/...
~/.dharma/evolution/pending_proposals.jsonl
~/.dharma/meta/frontier_tasks_pending.jsonl
reports/memory_kernel/*.jsonl
```

Do not add a new database in the first milestone. Use existing stores and add
receipted projections.

## 6. Routing Rules

Use the same candidate object across these entry lanes:

| Source lane | Existing owner | v0 route |
| --- | --- | --- |
| Operator note/idea | new thin CLI/API wrapper | OperatorInputReceipt -> IdeaSparkCandidate -> Chetana staging |
| Local transcript file | Chetana session/note ingest | source receipt -> chunked candidates -> staging |
| YouTube transcript-shaped file | same as local transcript | local file only in v0; no network fetch |
| Conversation idea shards | `ConversationMemoryStore.idea_shards` | candidate projection; keep original shard id |
| World radar | `world_radar` + Go receipts | reuse existing `idea_spark_triage.v0` |
| Go archive/public source | `world_radar.go_bridge` | candidate projection with source-rights guard |
| GitHub/repo events | `github_ingestor_go` | evidence candidate, not direct task |
| Shakti opportunity | `insight_evolution_bridge` / `opportunity_refill` | route through candidate first |

Routing destinations:

- Chetana staging for knowledge capture.
- MemoryKernel write receipt for governed memory review.
- Semantic Commons owner surface for domain routing.
- Darwin pending proposal when the idea is an experiment candidate.
- Frontier task queue when it is a bounded implementation task.
- Verified Experiment Loop BetCard when it is a falsifiable improvement claim.

## 7. PR Stack

### PR 0 - Spec Drift And Health Baseline

Goal: make the build start honest.

Work:

- Add an ingest health command or report that prints counts for input receipts,
  candidates, staged atoms, trusted promotions, routes, queued tasks, BetCards,
  lifecycle receipts, and stale concepts.
- Reconcile doc drift: the Go Idea Spark spec says `world_scout_go` was not in
  `make go-ci`; current Makefile already includes it.
- Add an executable check for the missing `wiki` command claim or replace docs
  with the Chetana CLI path.

Verifier:

```bash
make onboard
make go-ci
./.venv/bin/python -m dharma_swarm.chetana.cli status
```

### PR 1 - OperatorInputReceipt Schema And Fixtures

Goal: define source receipts without mutating trusted state.

Work:

- Add schema helpers for `operator_input_receipt.v0` and
  `operator_input_lifecycle_receipt.v0`.
- Add deterministic fixtures for note, local transcript-shaped text, URL
  metadata, Go receipt, and idea shard.
- Enforce source-rights fields.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_operator_input_receipts.py
```

### PR 2 - IdeaSparkCandidate Projection

Goal: normalize all lanes into one candidate object.

Work:

- Extract world-radar `idea_spark_triage.v0` into a reusable module or adapter
  without breaking existing tests.
- Project operator receipts, conversation idea shards, and world radar rows into
  `idea_spark_candidate.v0`.
- Keep candidates append-only and idempotent by `candidate_id`.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_idea_spark_candidate_projection.py tests/test_world_signal_analysis.py
```

### PR 3 - Chetana Staging Adapter

Goal: every candidate can become a staged atom, but not trusted memory.

Work:

- Add a candidate -> Chetana staged atom adapter.
- Stop or quarantine direct live writes from Hermes distillation into trusted
  context paths; route them to staging or mark them untrusted.
- Store candidate id and correlation id in frontmatter/source metadata.

Verifier:

```bash
./.venv/bin/python -m pytest -q dharma_swarm/chetana/tests tests/test_idea_spark_chetana_adapter.py
```

### PR 4 - MemoryKernel / KnowledgeOps Bridge

Goal: candidates can request memory promotion without silent memory mutation.

Work:

- Emit MemoryKernel write receipts for candidate summaries.
- Connect reviewed canonical receipt ids back to lifecycle receipts.
- Preserve privacy/redaction policy before writing projection content.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_memory_kernel_knowledgeops_bridge.py tests/test_idea_spark_memory_bridge.py
```

### PR 5 - Semantic Route And Owner Assignment

Goal: every promoted or promotion-ready candidate has an owner.

Work:

- Route candidates through Semantic Commons aliases and owner surfaces.
- Persist `owner_surface`, `authority_level`, and `semantic_route`.
- Fail closed when a candidate cannot be routed.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_semantic_commons.py tests/test_idea_spark_semantic_routing.py
```

### PR 6 - Proposal, Task, And BetCard Bridges

Goal: make routed candidates actionable without bypassing gates.

Work:

- Candidate -> Darwin pending proposal for experiment/evolution claims.
- Candidate -> `frontier_tasks_pending.jsonl` for bounded implementation work.
- Candidate -> Verified Experiment Loop BetCard by extending/wrapping
  `self_research.Hypothesis`, not by creating a new BetCard class.
- Require `dispatch_authority=False` unless an existing owner gate explicitly
  grants authority.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_idea_spark_action_routing.py tests/test_insight_evolution_bridge.py tests/test_conversation_memory.py
```

### PR 7 - Retrieval Round Trip

Goal: prove the input is findable later with its action chain.

Work:

- Add retrieval probe by `correlation_id`, source text, candidate title, and
  semantic route.
- Return input receipt, candidate, staged/trusted atom refs, memory receipt,
  proposal/task/bet refs, implementation receipt, and blockers.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_operator_input_retrieval_roundtrip.py tests/test_vector_store.py tests/test_engine_knowledge_store.py
```

### PR 8 - Long-Run Health And Backlog Discipline

Goal: make drift visible before trust claims go stale.

Work:

- Add daily health receipt: candidate count, staged backlog, trusted promotion
  freshness, zero-review-mark warning, lifecycle completion rate, unrouted
  candidates, unimplemented tasks, stale concepts, and query success.
- Do not bulk-promote the existing staging backlog. Sample, classify, dedupe,
  and route only through gates.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_idea_spark_health.py tests/test_live_ops_receipt_freshness_gate.py
```

### PR 9 - End-To-End Operator Fixture

Goal: close the trust claim.

Work:

- Build one deterministic no-network fixture:
  local idea text + transcript-shaped file -> source receipts -> candidates ->
  Chetana staging -> MemoryKernel receipt -> semantic route -> task/proposal or
  BetCard -> mock implementation/experiment receipt -> retrieval proof.
- Run in temp roots, not against live `~/.dharma`.

Verifier:

```bash
./.venv/bin/python -m pytest -q tests/test_operator_idea_spark_ingest_e2e.py
make go-ci
```

## 8. Definition Of Done

The build is not done until:

- `operator_input_receipt.v0`, `idea_spark_candidate.v0`, and
  `operator_input_lifecycle_receipt.v0` exist and have tests.
- A note, transcript-shaped file, conversation idea shard, and world radar
  signal all project into IdeaSparkCandidate.
- Candidate -> Chetana staging is proven.
- Candidate -> MemoryKernel write/promotion receipt is proven without direct
  protected memory mutation.
- Candidate -> Semantic Commons route is proven.
- Candidate -> proposal/task/BetCard bridge is proven with authority flags.
- Retrieval can reconstruct the whole chain by `correlation_id`.
- The e2e fixture runs in temp roots with no network and passes.
- Health output reports stale wiki concepts, staged backlog, unrouted
  candidates, and lifecycle completion rate.
- The old SAB Spark surface remains separate and explicitly out of the default
  path.

## 9. Long-Run Instantiation

Use the repo-native goal front door:

```bash
ds-goal init --goal "Wire operator input, transcripts, Idea Spark, Chetana, MemoryKernel, Semantic Commons, TaskBoard, and Verified Experiment Loop into one receipt-backed ingest lifecycle. Controlling spec: docs/specs/OPERATOR_IDEA_SPARK_INGEST_LONGRUN_BUILD.md"
ds-goal run --mission-id <mission-id> --duration-hours 10 --dispatch-mode tmux
ds-goal status --mission-id <mission-id>
```

Attach a long harness:

```bash
make long-harness-init GOAL="Operator Idea Spark Ingest Lifecycle" MODE=brownfield
make context-quorum-check AGENT=codex_planner RISK=Q3 QUESTION="Operator Idea Spark ingest authority boundaries, source-rights policy, and owner-routing design"
```

Use local verification loops inside each PR:

```bash
make codex-loop-init GOAL="<PR verifier goal>" MODE=verification NAME="idea-spark-pr<N>"
make codex-loop-validate LOOP_ID=<id> PHASE=ready
make codex-loop-record LOOP_ID=<id> STATUS=pass EVIDENCE="<command summary and receipt path>"
```

## 10. Slash Goal Prompt

```text
/goal Read docs/specs/OPERATOR_IDEA_SPARK_INGEST_LONGRUN_BUILD.md completely and execute it as the controlling build spec.

This is the non-SAB Operator Idea Spark ingest lifecycle. Keep SAB Spark/canon/challenge out of the default path. Preserve the language and authority boundaries: Go collects, normalizes, hashes, spools, and emits receipts; Python owns policy, triage, memory governance, Semantic Commons routing, TaskBoard/proposal/BetCard bridges, and promotion.

Start with make onboard and toolbelt status. Build as a PR stack, not a mega PR. For each PR, declare file scope, implement narrowly, add deterministic no-network tests, run the narrowest meaningful verifier, record receipt evidence, and require a separate evaluator pass before closure.

The mission is complete only when a local operator idea and transcript-shaped fixture prove the full chain: source receipt -> IdeaSparkCandidate -> Chetana staged atom -> MemoryKernel receipt -> Semantic Commons owner route -> proposal/task/BetCard -> implementation or experiment receipt -> retrieval proof by correlation_id.

Do not claim done from code inspection. Do not bulk-promote the existing wiki backlog. Do not store full copyrighted transcripts or pages unless operator-supplied/owned. Do not create a new canonical database in v0. If blocked, write the exact blocker, command output, and missing owner surface.
```

