---
title: DharmaGraph Production Runtime Specification v1.1 — Reconstructed
path: docs/plans/DHARMAGRAPH_PRODUCTION_RUNTIME_SPEC_v1_1_RECONSTRUCTED.md
doc_type: production_runtime_specification
status: proposed_not_implemented
reconstruction_status: non_byte_identical_reconstruction
created_at: 2026-08-12
source_repository: AIKAGRYA/dharma_swarm
reconstruction_baseline: 12212397be1dbe0a9b0cc29be4311f930140e751
lost_v1_baseline: e8cce03171d57945d3c9adc6f0cb2b3c2072d0b9
lost_v1_sha256: 3dea6d71679eb6e80aa7301d3cda727c109a03147c37aca12111ec44c02b909e
claim_boundary: design_contract_only
---

# DharmaGraph Production Runtime Specification v1.1

## Reconstructed edition — proposed, not implemented

> **Hard status boundary:** This document is a reconstructed production-runtime
> contract. It is not the byte-identical 4,837-line v1 artifact, it is not proof
> that the code implements these requirements, and it does not raise the
> repository's judge-signed LangGraph-parity grade. Until the conformance gates
> in this document pass against production wiring, DharmaGraph remains
> `CLOSED_NOT_PROD`.

## 0. Reconstruction record

The original v1 specification was produced and subjected to repeated hostile
review, but it remained an untracked workspace file and was lost during
workspace cleanup. Its final recorded SHA-256 was
`3dea6d71679eb6e80aa7301d3cda727c109a03147c37aca12111ec44c02b909e`, its
recorded length was 4,837 lines, and its structural citation audit found 89
citation expressions containing 112 file/line ranges across 22 repository
files, with no missing or out-of-range references at the frozen review
revision. Those facts authenticate only the review record; they do not recover
the lost bytes.

This v1.1 reconstruction preserves the surviving architectural decisions and
closes the major failure modes discovered during review. It is freshly grounded
at repository commit
`12212397be1dbe0a9b0cc29be4311f930140e751`. Line references in this document
are therefore references to that commit unless a different baseline is stated.

### 0.1 Artifact identity

The publisher SHALL record, at commit time:

- the exact Git commit containing this file;
- the SHA-256 and line count of this file at that commit;
- the source baseline audited by its citations;
- the conformance profile, test results, and evidence-root digests;
- the claim boundary `PROPOSED_NOT_IMPLEMENTED` until implementation gates pass.

No agent may represent the lost v1 hash as the hash of this reconstruction.

### 0.2 What survived and what did not

Survived:

- the four-axis architectural audit of state, routing/cycles, recovery, and
  synchronicity;
- the hostile-review decision trail for execution, effects, persistence,
  restore, and rollout;
- the official 58/100 parity evidence and current source tree;
- the final v1 validation metadata.

Did not survive:

- the exact prose, ordering, diagrams, and bytes of v1;
- a Git commit, branch, pull request, or Library version of v1;
- any right to claim byte-for-byte continuity.

## 1. Executive decision

### 1.1 Present-state verdict

At the reconstruction baseline, the neutral DharmaGraph core is explicitly
marked candidate/test-only and not wired into production dispatch
(`dharma_swarm/graph/__init__.py:1-10`,
`dharma_swarm/graph/scheduler.py:1-30`,
`dharma_swarm/graph/executor.py:1-16`). The official frozen parity matrix still
records **58.00/100**, while the active track targets `CLOSED_NOT_PROD`
(`docs/governance/ACTIVE_TRACK.yaml:940-991`,
`docs/governance/ACTIVE_TRACK.yaml:1101-1103`,
`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3`).

The implementation contains a real BSP/Pregel-like kernel, concurrent task
execution, channels and reducers, dynamic `Send`/`Command`, checkpoints,
history, replay, fork, and process-restart behavior. It is not a toy in the
sense of being a mock or a linear demo. It is nevertheless **not production
grade for concurrent consequential agentic workflows** because the production
authority boundary, distributed fencing, effect protocol, terminal lifecycle,
durable streaming, and disaster-recovery contract are not implemented and
qualified end-to-end.

### 1.2 Relationship to the 58/100 LangGraph grade

The 58/100 score grades implemented behavior against a frozen LangGraph 1.2.4
rubric. This specification defines a stronger production destination. Design
coverage is not implementation credit.

The frozen matrix reports full evidence for core schemas, static and
conditional topology, BSP step atomicity, `Send`, `Command`, cycles,
checkpointing, thread continuity, history/replay, state update/fork/time travel,
and restart recovery
(`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:40-59`). It reports
material gaps in node policies, defer/finalize,
message semantics, invocation surfaces, batching, interrupts, streaming,
subgraphs, retry, timeout, error/cancellation semantics, stores, caching,
runtime/config propagation, callbacks, functional APIs, introspection, drain,
application integration, and prebuilts
(`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:9-36`).

Production qualification SHALL be evaluated separately from LangGraph parity:

1. **Parity:** Does DharmaGraph reproduce the deliberately selected behavior?
2. **Sovereignty:** Does it preserve Dharma identities, authority, evidence,
   policy, provenance, and human control?
3. **Safety:** Does it remain correct through concurrency, crash, retry,
   partition, restore, and operator error?
4. **Operability:** Can a bounded team deploy, observe, repair, and roll back it?

### 1.3 Release verdict vocabulary

Only these release verdicts are valid:

- `PROPOSED_NOT_IMPLEMENTED` — specification only;
- `IMPLEMENTED_UNQUALIFIED` — code exists but release gates are incomplete;
- `CLOSED_NOT_PROD` — bounded evidence exists; production claim forbidden;
- `DG_P1_QUALIFIED` — the single-tenant durable profile passes;
- `DG_P2_QUALIFIED` — the single-region HA profile passes;
- `DG_P3_QUALIFIED` — the multitenant regulated profile passes;
- `PRODUCTION_READY` — explicitly ratified profile plus operational evidence;
- `QUARANTINED` — integrity, determinism, authority, or effect ambiguity blocks use.

Passing unit tests alone cannot yield `PRODUCTION_READY`.

## 2. Scope, goals, and non-goals

### 2.1 Goals

DharmaGraph v1 production runtime SHALL provide:

1. deterministic BSP execution with snapshot isolation;
2. immutable task outputs and one authoritative reducer/barrier commit;
3. typed routing with fail-closed invalid-destination handling;
4. finite cycle, task, attempt, edge, time, token, and effect budgets;
5. durable exact resume without replaying covered node work;
6. fenced single-writer authority across workers and recovery attempts;
7. durable waits, interrupts, retries, deadlines, cancellation, and terminality;
8. logical exactly-once effect intent with provider idempotency and
   reconciliation, never magical exactly-once network delivery;
9. gapless resumable event/token streaming under declared durability modes;
10. authenticated state lineage and auditable repair/fork/migration;
11. multi-tenant authorization, quotas, fairness, and data isolation;
12. crash, partition, delayed-ack, stale-worker, and disaster-restore evidence;
13. a strangler path from the current canonical runtime without dual authority.

### 2.2 Non-goals

The first qualified profile need not:

- clone every LangGraph convenience API;
- promise arbitrary user reducer safety without reducer qualification;
- make non-idempotent providers safe through retries;
- run unbounded synchronous callables safely;
- provide cross-region active/active execution;
- preserve byte-identical operational envelopes after crash or restore;
- auto-repair integrity or determinism conflicts;
- execute consequential effects in shadow, exploratory fork, or untrusted code.

### 2.3 Named deployment profiles

#### Profile A / DG-P1 — durable single-tenant authority

- one canonical SQL store with transactions and store-authoritative time;
- one active coordinator lease per branch/run;
- horizontally scalable workers behind fenced commands;
- process-crash RPO 0 on surviving canonical storage;
- disaster RPO/RTO only as explicitly measured for the storage deployment;
- consequential effects admitted only through qualified provider adapters.

#### Profile B / DG-P2 — single-region high availability

- replicated strongly consistent metadata store;
- cross-host quota and lease arbitration;
- outbox/broker dispatch with fenced claims;
- externally anchored store-incarnation authority for disaster cutover;
- partition and healed-old-primary tests;
- no claim of multi-region availability until the exact topology is qualified.

The detailed release names in §10.2 are authoritative: DG-P0 is lab-only,
DG-P1 corresponds to Profile A, DG-P2 corresponds to Profile B, and DG-P3 adds
the regulated multi-tenant controls. DG-P1 SHALL be qualified before DG-P2,
and DG-P2 before DG-P3, unless an operator signs an evidence-bearing exception
showing that the higher-profile substrate satisfies every lower-profile gate.

## 3. Normative language and trust boundaries

`MUST`, `MUST NOT`, `SHALL`, `SHALL NOT`, `SHOULD`, and `MAY` are normative.
Examples and rationale are non-normative unless explicitly promoted.

The runtime trust boundary contains:

- graph manifests and revision signatures;
- compiler and canonical serializer;
- scheduler/planner and barrier reducer;
- `GraphStore` transaction adapter;
- current store-authority and branch/run lease services;
- effect broker and qualified provider adapters;
- checkpoint/integrity key service;
- authorization, quota, and audit services.

Node code, LLM output, route identifiers, reducer plugins, provider responses,
client cursors, external input, replay payloads, and restored storage are
untrusted until validated at their boundary.

No untrusted node or router may mint authority identities, lease epochs,
activation identities, checkpoint records, effect identities, or terminal
proofs.

## 4. Threat and failure model

The design SHALL remain safe under:

- concurrent fan-out tasks writing the same and different channels;
- task completion in any order;
- mutable, stateful, raising, slow, or non-deterministic user code;
- invalid, empty, hallucinated, duplicated, or adversarial routes;
- cycles, self-loops, join generations, and no-ready states;
- process death before and after every durable boundary;
- duplicate delivery, lost acknowledgement, retry, timeout, and late result;
- two recovery workers racing on the same branch;
- stale workers continuing after lease loss;
- checkpoint corruption, rollback, topology drift, schema drift, or key rotation;
- provider acceptance with unknown client outcome;
- cancellation racing commit, effect dispatch, wait settlement, or terminality;
- compaction/GC racing execution, publication, backup, and restore;
- database PITR that rolls back acknowledged operational counters;
- old-primary recovery after disaster cutover;
- tenant-confused identifiers and authorization context.

The design does not assume Byzantine safety inside the trusted store, HSM, or
external canonical-owner arbiter. Corruption there SHALL be detected where
possible and SHALL quarantine affected scope.

## 5. Non-negotiable invariants

| ID | Invariant |
|---|---|
| I-01 | Nodes never mutate committed state; each task reads a deep immutable snapshot or a packet-scoped input. |
| I-02 | Task results are immutable proposals. Only the barrier transaction advances committed graph state. |
| I-03 | One logical superstep has one frozen ready set, plan digest, and canonical task identity set. |
| I-04 | A failed/invalid superstep advances neither state head nor trigger/join consumption. |
| I-05 | Every authoritative mutation is fenced by tenant, thread, branch, run, graph revision, expected head, store incarnation, lease owner, and never-reused epoch. |
| I-06 | A stale task/attempt may append diagnostics but may never resolve a newer attempt or occupy canonical result keys. |
| I-07 | Resume adopts immutable covered task bundles and executes exactly the uncovered tasks in the frozen ready set. |
| I-08 | An in-place resume starts only from the current branch head; historical execution requires an explicit fork. |
| I-09 | Invalid routing cannot silently quiesce. It repairs within budget, dead-letters, fails, or quarantines through the closed run state machine. |
| I-10 | Completion requires an explicit normalized `HALT` contribution and a verified termination proof; absence of ready work is not success. |
| I-11 | Every cycle and retry path consumes durable, non-replenishable budget according to a canonical charge equation. |
| I-12 | Effect identity is stable for the logical operation and slot, independent of attempts, leases, payload recomputation, or recovery worker. |
| I-13 | Same effect ID with a different request digest is a determinism conflict and quarantines before provider dispatch. |
| I-14 | `UNKNOWN` provider outcome is never blindly redispatched; it must reconcile, compensate, or quarantine. |
| I-15 | Consequential providers lacking adequate idempotency retention and reconciliation are rejected at admission. |
| I-16 | Checkpoint integrity binds semantic state, operational references, graph revision, lineage, authority, budgets, routes, waits, joins, effects, and task journals. |
| I-17 | Historical authenticated records remain verifiable after later settlement, reconciliation, compaction, key rotation, and restore. |
| I-18 | Every acknowledged durable stream item survives process crash and can be resumed without identity aliasing. |
| I-19 | One business operation has at most one active same-operation owner; repair transfer is atomic with target publication. |
| I-20 | Disaster activation is externally fenced; a healed old primary can make zero post-cutover commits or provider calls. |
| I-21 | Tenant identity and authorization are included in every primary key, capability, query, mutation, event, and blob reference. |
| I-22 | Terminal status, final checkpoint, terminal result, budget settlement, and lifecycle event are committed atomically. |
| I-23 | Compatibility code may not execute from production-qualified ingress. |
| I-24 | No release claim exceeds the exact profile and fault model exercised by its signed evidence. |

## 6. Canonical identity hierarchy

All identities SHALL be typed, versioned, domain-separated, length-bounded,
canonically encoded, and tenant-scoped.

```text
TenantId
└── GraphId
    └── GraphRevisionId
        └── ThreadId
            └── BranchId
                └── RunId
                    └── AbsoluteSuperstep
                        └── TaskId (one run-specific execution slot)
                            └── AttemptId (one operational attempt)
```

Additional stable namespaces:

- `OperationId` — business operation lineage;
- `TaskNamespaceId` — stable semantic-task lineage across approved repair/migration;
- `EffectNamespaceId` — stable effect slots across approved repair/migration;
- `StoreIncarnation` — operational authority epoch across disaster cutover;
- `CommandId` and request digest — idempotent external mutations;
- `StreamIncarnation` plus stream sequence — non-aliasing operational cursors.

For v1, `StreamIncarnation` SHALL equal the active `StoreIncarnation` at event
commit. A future independent stream-incarnation allocator requires a new
protocol version and the same non-reuse proof.

Recommended derivations use canonical CBOR or an equivalently specified binary
encoding, not language-native object serialization:

```text
SemanticTaskId = H("dg/semantic-task/v1", tenant, operation_id,
                   task_namespace_id, stable_task_path)

TaskId         = H("dg/task/v1", tenant, run_id, graph_revision,
                   absolute_step, activation_id, semantic_task_id)

AttemptId      = H("dg/attempt/v1", tenant, store_incarnation,
                   task_id, attempt_ordinal)

EffectId      = H("dg/effect/v1", tenant, operation_id, effect_namespace_id,
                  stable_task_path, effect_slot)
```

`EffectId` MUST NOT include payload bytes, retry ordinal, lease epoch, worker
identity, or wall-clock time. The immutable effect declaration separately binds
operation, provider route, target digest, payload digest, and policy digest.

## 7. Required public authority boundary

Application code SHALL invoke one canonical service boundary. Direct calls from
qualified ingress to candidate `CompiledGraph.invoke`, legacy
`CompiledWorkflow.execute`, filesystem checkpoint kernels, provider SDKs, or
effect helpers are forbidden.

```python
class GraphRuntime(Protocol):
    async def accept_run(self, request: AcceptRunRequest,
                         authority: ClientAuthority) -> RunHandle: ...
    async def get_run(self, ref: RunRef,
                      authority: ClientAuthority) -> RunView: ...
    async def resume(self, request: ResumeRequest,
                     authority: ClientAuthority) -> RunHandle: ...
    async def respond_interrupt(self, request: InterruptResponse,
                                authority: ClientAuthority) -> CommandReceipt: ...
    async def cancel(self, request: CancelRequest,
                     authority: ClientAuthority) -> CommandReceipt: ...
    async def fork(self, request: ForkRequest,
                   authority: ClientAuthority) -> RunHandle: ...
    async def stream(self, request: StreamRequest,
                     authority: ClientAuthority) -> AsyncIterator[StreamEnvelope]: ...
```

Every request SHALL carry an idempotency key and canonical request digest.
Same key/same digest returns the original durable result. Same key/different
digest is a conflict. Retention horizons SHALL be explicit; consequential
operation tombstones outlive provider idempotency retention.

## 8. Core execution kernel

This part is normative. Its local subsection numbering is `8.x`; cross-references
inside this part use that numbering.

### 8.1 Purpose and non-negotiable properties

DharmaGraph is a durable distributed state-machine kernel. A graph run is not an in-memory loop with occasional snapshots; it is an ordered sequence of authenticated, atomically committed state transitions whose work may execute concurrently and on different processes.

Every conforming runtime profile SHALL provide these properties:

1. **Snapshot isolation.** Every task in superstep `k` reads the same committed snapshot `S[k]`, plus its own immutable task input. No task observes a sibling's uncommitted write.
2. **Proposal-only nodes.** Nodes SHALL return typed deltas and control decisions. Nodes and workers SHALL NOT hold a mutable reference to authoritative state.
3. **One authoritative merge point.** Only the fenced coordinator's barrier-commit transaction may advance state from `S[k]` to `S[k+1]`.
4. **Atomic supersteps.** A superstep either commits its entire accepted delta bundle, routing plan, checkpoint, and durable event batch, or commits none of them.
5. **Completion-order independence.** Given the same graph version, initial state, external effect receipts, and accepted task-result set, task completion order SHALL NOT change the committed state, route plan, checkpoint bytes, or canonical event sequence.
6. **Fail-closed control flow.** Unknown routes, malformed commands, undeclared state keys, reducer failures, stale workers, and ambiguous joins SHALL never be silently ignored.
7. **Bounded cycles.** Every run has durable, monotonically decreasing run-wide budgets. Resume SHALL NOT replenish them.
8. **Crash-exact continuation.** After coordinator or worker loss, execution continues from the last authoritative run head. Already committed supersteps are never re-run; staged successful task results are reused where valid.
9. **Non-blocking orchestration.** A slow node or subscriber SHALL not block unrelated tasks, runs, coordinator heartbeats, lease renewal, or persistence I/O scheduling.
10. **Replayable observation.** State/control/checkpoint stream events SHALL be durably ordered and cursor-addressable.

These properties dominate API convenience and generic LangGraph parity. A feature that violates them SHALL remain disabled in the production profile.

---

### 8.2 Current-code alignment and required replacement seams

The implementation already contains useful candidate vocabulary: `START`, `END`, `GraphState`, `ChannelWrite`, `ReducerChannel`, `Send`, `Command`, `RunCheckpoint`, `GraphPersistenceKernel`, `CompiledGraph`, `SuperstepExecutor`, and version-driven BSP scheduling. v1.1 SHOULD preserve source-compatible names where doing so does not weaken this contract.

The reconstruction was checked against source baseline `12212397be1dbe0a9b0cc29be4311f930140e751`. Evidence anchors at that baseline are:

- `dharma_swarm/graph/state.py:50-107` owns the mutable in-process channel map and the validate-then-`channel.commit(...)` merge; `dharma_swarm/graph/state.py:161-176` deep-copies user snapshots.
- `dharma_swarm/graph/channels.py:213-277` implements canonical left-fold reducers, while `dharma_swarm/graph/channels.py:321-370` stores join progress as one channel-local `_seen` set.
- `dharma_swarm/graph/executor.py:124-180` starts same-superstep tasks concurrently and buffers proposals; `dharma_swarm/graph/executor.py:360-380` sends only selected synchronous calls to a thread, leaving the ordinary sync path on the caller/event-loop thread.
- `dharma_swarm/graph/routing.py:123-159` defines additive `Command.goto`; `dharma_swarm/graph/routing.py:295-352` correctly rejects malformed and unmapped branch results before commit.
- `dharma_swarm/graph/types.py:47-48` exposes only `completed`/`ok` run vocabulary; `dharma_swarm/graph/types.py:111-140` defines resumable channel snapshots.
- `dharma_swarm/graph/scheduler.py:240-250` deliberately resets the recursion budget per invocation; `dharma_swarm/graph/scheduler.py:343-405` validates, journals, mutates state, and checkpoints as separate process-level operations.
- `dharma_swarm/graph/persistence.py:148-175` uses a file-backed, process-locked persistence kernel; `dharma_swarm/graph/persistence.py:448-475` confirms path-based JSON state as the durable adapter.

These anchors describe the migration baseline, not defects in the already-useful candidate/test implementation. Line references SHALL be re-baselined before this reconstructed document is merged if those files have moved.

The following current behaviors are not sufficient for a distributed production profile and MUST be replaced or wrapped behind a production implementation:

- In-process channel mutation after validation is not an authoritative distributed commit. Production state advancement requires durable compare-and-swap, a coordinator fencing token, and an atomic run-head/checkpoint/outbox transaction.
- A join represented only by a channel-level `_seen` set can mix arrivals from different fan-out waves. Production joins require persistent, activation-scoped `JoinFrame` records.
- Running an ordinary synchronous node directly on the event-loop thread is forbidden. All synchronous callables must use a bounded worker executor or isolated worker process.
- A run model with only `completed` cannot express waits, retries, cancellation, failure, or quarantine. The durable state machine in §8.9 is required.
- An invocation-local recursion limit is not a run termination guarantee because repeated resumes can replenish it. The run-wide budgets in §8.8 are authoritative.
- Local JSON files and process-local locks MAY remain a development adapter; they SHALL NOT satisfy the multi-worker production storage profile.
- A callback-only checkpoint surface is not streaming. The cursor-addressable asynchronous protocol in §8.12 is required.

No migration may label the runtime production-ready merely because the existing candidate types have matching names.

---

### 8.3 Canonical identifiers and records

Every core execution record in §8 SHALL carry `schema_version`, `tenant_id`,
and `graph_version_id`. A specialized §9 record that is operation-, effect-,
wait-, blob-, store-, or deployment-scoped instead SHALL carry
`schema_version` and `tenant_id` where tenant-scoped, plus an authenticated
foreign key to the exact graph/run/checkpoint record that supplies any
applicable graph revision. A record to which graph version is semantically
irrelevant MUST NOT invent one. IDs SHALL be opaque strings at public
boundaries and have an unambiguous canonical binary encoding internally.

```text
GraphVersionId = sha256(canonical_compiled_graph)
RunId          = globally unique execution id
ThreadId       = durable conversation/workflow lineage id
OperationId    = stable id for one operator-authorized real-world operation
TaskNamespaceId   = stable namespace for logical task identity within an operation
EffectNamespaceId = stable namespace for consequential effect identity
StepId         = H("step", tenant_id, run_id, superstep)
ActivationId   = H("activation", step_id, source_task_id, edge_id, ordinal)
StableTaskPath = canonical logical path independent of attempts and graph revision
SemanticTaskId = H("semantic-task", tenant_id, operation_id,
                   task_namespace_id, stable_task_path)
TaskId         = H("task", tenant_id, run_id, graph_version_id,
                   absolute_superstep, activation_id, semantic_task_id)
AttemptId      = H("attempt", tenant_id, store_incarnation, task_id, attempt_no)
DeltaId        = H("delta", task_id, canonical_node_outcome)
EffectId       = H("effect", tenant_id, operation_id, effect_namespace_id,
                   stable_task_path, effect_slot)
JoinFrameId    = H("join", run_id, join_spec_id, parent_activation_id,
                   generation)
CheckpointId  = the content-derived identifier defined exclusively in §9.4.1
StreamEventId = H("event", tenant_id, stream_incarnation, run_id,
                  stream_seq, event_type, payload_digest)
```

`H` SHALL be a domain-separated cryptographic digest over length-delimited canonical fields. Concatenating unescaped strings is forbidden.

#### 8.3.1 Stability requirements

- `RunId` remains constant across suspend/resume and coordinator failover.
- `OperationId` identifies the operator-authorized real-world operation. A retry, crash recovery, or same-operation repair preserves it; an unrelated invocation never reuses it.
- `TaskNamespaceId` and `EffectNamespaceId` are explicit persisted authorities, not values inferred from `RunId` or graph revision.
- `StableTaskPath` is derived from logical parent path, compiled node semantic id, stable activation/send key, and loop/join generation. It SHALL NOT contain attempt number, worker id, coordinator fence, wall time, or graph revision. A graph migration SHALL supply an audited old-to-new semantic path map or refuse same-operation continuation.
- `SemanticTaskId` remains constant across retries and an explicitly
  authorized same-operation repair that preserves its task namespace and
  mapped semantic path. `TaskId` is run/graph/step/activation-specific; repair
  or migration creates a new `TaskId` and persists an authenticated
  old-to-new mapping, preventing old result rows from occupying new slots.
- `AttemptId` changes for every attempt and store incarnation. Its ordinal is
  incremented atomically; PITR or disaster activation therefore cannot remint
  an identity already visible before the rollback point.
- `EffectId` SHALL be exactly the domain-separated digest of `(tenant_id, operation_id, effect_namespace_id, stable_task_path, effect_slot)`. It SHALL be independent of `RunId`, `TaskId`, `AttemptId`, worker/coordinator identity, graph revision, and wall time. `effect_slot` is a compile-declared logical operation within the node. Retry and same-operation repair therefore deduplicate the same real-world effect.
- A **same-operation repair** (for example, repair from a quarantined
  checkpoint under corrected graph code) MUST preserve `OperationId`,
  `TaskNamespaceId`, and `EffectNamespaceId`; it MUST record repair authority,
  source run/checkpoint, semantic path migration, graph-version change, and
  old-to-new TaskId mapping. It mints a new RunId and execution TaskIds. It may
  execute an effect only after reconciling the preserved `EffectId` to a
  terminal provider/receipt state.
- An **exploratory fork** MUST mint a new `OperationId`, `TaskNamespaceId`, and `EffectNamespaceId`. Consequential effects SHALL be disabled by default in the fork; enabling them requires a new explicit authority/admission decision. Merely copying a checkpoint SHALL NOT copy permission to repeat real-world effects.
- `dispatch_ordinal` and `Send.ordinal` SHALL be assigned by the committed step plan, never by wall-clock completion order.
- A caller-provided invocation idempotency key SHALL map to exactly one `RunId` within its tenant and graph version. Reusing it with different input bytes SHALL fail with `IDEMPOTENCY_CONFLICT`.

#### 8.3.2 Minimum durable records

Every run-scoped durable record embeds this common scope; schemas below do not
rely on an implicit database session or URL path for isolation. Cross-run
authority records such as `OperationOwner` carry their explicit tenant and
operation scope instead:

```python
@dataclass(frozen=True)
class RecordScope:
    tenant_id: str
    store_lineage_id: str
    store_incarnation: str
    thread_id: str
    branch_id: str
    run_id: str
    graph_version_id: str
```

Primary/unique keys and every read/write predicate SHALL include `tenant_id`
and the complete identity subset relevant to the record. A globally unique
opaque ID is defense in depth, not permission to omit tenant scope.

```python
@dataclass(frozen=True)
class RunHead:
    scope: RecordScope
    operation_id: str
    task_namespace_id: str
    effect_namespace_id: str
    status: RunStatus
    state_revision: int
    state_digest: str
    checkpoint_id: str
    current_superstep: int
    plan_digest: str | None
    lease_owner_id: str | None
    lease_epoch: int
    lease_expires_at: Instant | None
    budget_account: "BudgetAccount"
    budget_reservation_root: str
    stream_incarnation: str
    stream_seq: int
    updated_at: Instant

@dataclass(frozen=True)
class StepPlan:
    scope: RecordScope
    step_id: str
    superstep: int
    base_revision: int
    base_state_digest: str
    base_checkpoint_id: str
    tasks: tuple["PlannedTask", ...]
    joins_touched: tuple[str, ...]
    budget_reservation: "BudgetVector"
    plan_digest: str
    lease_owner_id: str
    lease_epoch: int

@dataclass(frozen=True)
class PlannedTask:
    scope: RecordScope
    task_id: str
    semantic_task_id: str
    stable_task_path: str
    activation_id: str
    node_id: str
    dispatch_ordinal: int
    input_ref: str
    input_digest: str
    retry_policy_id: str
    deadline: Instant | None
    authority_ref: str

@dataclass(frozen=True)
class TaskResult:
    scope: RecordScope
    task_id: str
    semantic_task_id: str
    stable_task_path: str
    attempt_id: str
    attempt_store_incarnation: str
    attempt_no: int
    plan_digest: str
    outcome_digest: str
    delta: "StateDelta"
    control: "ControlDecision"
    effect_receipt_refs: tuple[str, ...]
    completed_at: Instant
```

`OperationOwner(tenant_id, operation_id)` is a separate versioned authority
row containing `owner_run_id`, `owner_branch_id`, `state`, `successor_run_id`,
and `owner_version`. Admission creates it atomically. Every terminal transition
updates its control state, and every same-operation repair/migration transfers
it by CAS and marks the predecessor owner projection `SUPERSEDED` in the same
transaction that publishes the target root. Neither `MIGRATED` nor
`SUPERSEDED` is a `RunStatus`.

Authoritative timestamps SHALL be observational metadata only. They SHALL NOT participate in route, reducer, or scheduling decisions unless time was explicitly supplied as a recorded external input/effect receipt.

---

### 8.4 Immutable state, deltas, and reducers

#### 8.4.1 State snapshot contract

`StateSnapshot` is an immutable mapping from declared `ChannelId` to a canonical value plus a monotonically increasing channel version.

```python
@dataclass(frozen=True)
class ChannelValue:
    value_ref: str              # content-addressed immutable blob
    value_digest: str
    channel_version: int

@dataclass(frozen=True)
class StateSnapshot:
    scope: RecordScope
    revision: int
    superstep: int
    channels: Mapping[str, ChannelValue]
    state_digest: str
```

The runtime SHALL enforce the following:

- A task receives a deserialized deep-frozen/read-only view. Returning or retaining a nested object from that view cannot mutate the store.
- Runtime-owned scheduling fields, secrets, capability tokens, lease tokens, and join internals SHALL NOT appear in the user-state mapping.
- Context is immutable invocation metadata and SHALL NOT be checkpointed as user state unless explicitly copied through a declared state delta.
- State values SHALL use a versioned canonical serializer. Maps have sorted keys; numeric edge cases, Unicode normalization, bytes, enums, datetimes, and tagged unions have one specified encoding. NaN, infinity, pointer-bearing objects, open handles, generators, and unserializable values SHALL be rejected before staging.
- `state_digest` SHALL cover schema version, graph version, channel names, channel versions, and value digests. Hashing only the visible value map is insufficient.
- The implementation SHALL verify blob digest on read and state digest on checkpoint restore. A mismatch quarantines the run as `CORRUPT_STATE`.

#### 8.4.2 Node contract

A user node is logically pure with respect to graph state:

```python
async def node(
    state: ReadOnlyState,
    task_input: FrozenValue | None,
    context: ReadOnlyContext,
    effects: EffectPort,
) -> NodeOutcome: ...

@dataclass(frozen=True)
class NodeOutcome:
    delta: StateDelta = StateDelta.empty()
    control: ControlDecision = Continue()
    custom_events: tuple[CustomEvent, ...] = ()
```

Nodes SHALL NOT receive a persistence handle, mutable `GraphState`, coordinator lease, reducer instance with mutable global state, or direct run-head update method. External operations SHALL go through `EffectPort`, which records stable effect identities and receipts; arbitrary network calls MAY be prohibited by the production sandbox.

#### 8.4.3 Delta vocabulary

```python
class DeltaOpKind(Enum):
    SET = "set"          # exactly one writer in a step unless conflict policy says otherwise
    REDUCE = "reduce"    # fold through declared reducer
    APPEND = "append"    # syntactic reducer with declared ordering semantics
    DELETE = "delete"    # only where channel schema declares deletable

@dataclass(frozen=True)
class DeltaOp:
    channel: str
    kind: DeltaOpKind
    value_ref: str | None
    value_digest: str
    emission_index: int

@dataclass(frozen=True)
class StateDelta:
    base_revision: int
    task_id: str
    ops: tuple[DeltaOp, ...]
```

Each output key SHALL map to a declared channel and compatible operation. Unknown keys, runtime-reserved keys, operation mismatches, and schema-invalid values are non-retryable `INVALID_DELTA` failures.

Workers may stage immutable `TaskResult` records, but workers SHALL NOT apply deltas to authoritative state.

#### 8.4.4 Reducer declaration

```python
@dataclass(frozen=True)
class ChannelSpec:
    channel_id: str
    schema_id: str
    mode: Literal["single_writer", "reducer"]
    reducer_id: str | None
    identity_ref: str | None
    delete_allowed: bool
    max_serialized_bytes: int

@dataclass(frozen=True)
class ReducerSpec:
    reducer_id: str
    implementation_digest: str
    input_schema_id: str
    output_schema_id: str
    associative: bool
    commutative: bool
    idempotent: bool
    ordering: Literal["canonical", "unordered"]
```

A reducer SHALL be total over valid inputs, deterministic, side-effect free, and free of dependence on time, randomness, environment, mutable globals, locale, process hash seeds, or network state. Reducer code and declared identity value are part of `GraphVersionId`.

For channel `c`, accepted ops SHALL be ordered by this canonical key:

```text
(channel_id, task.dispatch_ordinal, delta_op.emission_index, task_id)
```

The final `task_id` is a corruption-resistant tie-breaker; a valid plan SHALL never have equal preceding fields.

- `single_writer` channels reject two or more accepted writes in one superstep, even if their values are equal. There is no implicit “last finisher wins.”
- `reducer` channels fold from the prior committed value in canonical order.
- A reducer declared `ordering="unordered"` MUST be associative and commutative; property tests SHALL prove permutation invariance.
- A canonical-order reducer MUST be associative so batching does not alter results. Non-commutativity is permitted only because the committed plan fixes total order.
- If duplicate delivery is possible before result deduplication, the reducer is never used as the deduplication mechanism. Results are deduplicated by `TaskId`/`DeltaId` first.

#### 8.4.5 Central merge algorithm

```python
def build_commit_candidate(head, plan, staged_results, snapshot):
    require head.status == RUNNING
    require plan.base_revision == head.state_revision
    require plan.base_state_digest == head.state_digest
    require plan.plan_digest == head.plan_digest
    require exact_success_coverage(plan.tasks, staged_results)

    results = dedupe_by_task_id(staged_results)
    for task_id, duplicates in results:
        require all_equal(outcome_digest for duplicates)
        # unequal duplicate outcome => NONDETERMINISTIC_RESULT quarantine

    # Interpret every dynamic, static, branch, join, and parent contribution
    # before reducing state. Invalid routes, DeadLetter, and incompatible
    # controls produce a FailureSettlement for TX-G; their deltas never commit.
    routing = interpret_all_routes(plan, results, snapshot)
    if isinstance(routing, FailureSettlement):
        return routing
    control = normalize_control_contributions(plan, results, routing)
    if control.requires_failure_settlement:
        return FailureSettlement.from_control(head, plan, results, control)

    ops = canonical_sort(flatten(result.delta.ops for result in results))
    validate_all_channels_and_routes(snapshot, ops, results)
    next_snapshot = apply_to_fresh_builder(snapshot, ops)
    require snapshot is byte_identical_to_preimage()

    next_frontier, join_updates = materialize_normalized_routing(routing, control)
    return CommitBundle(next_snapshot, next_frontier, join_updates, control)
```

`apply_to_fresh_builder` SHALL construct new channel values. It SHALL NOT mutate `snapshot` and roll back on exception. Production implementations MAY use structural sharing, copy-on-write pages, or immutable persistent data structures, provided the old revision remains readable and byte-identical.

Before persistence, the coordinator SHALL re-run schema validation and reducer evaluation from stored immutable result bytes. Trusting a worker-supplied computed post-state is forbidden.

#### 8.4.6 Authoritative barrier transaction

The state merge is committed by one storage transaction equivalent to:

```sql
BEGIN;
SELECT store_control, run_head, run_lease, step
  FOR UPDATE
 WHERE run_head.tenant_id           = :tenant_id
   AND run_head.thread_id           = :thread_id
   AND run_head.branch_id           = :branch_id
   AND run_head.run_id              = :run_id;
ASSERT store_control.mode           = 'WRITABLE';
ASSERT store_control.incarnation    = :store_incarnation;
ASSERT run_head.store_incarnation   = store_control.incarnation;
ASSERT run_head.graph_version_id    = :graph_version_id;
ASSERT run_head.state_revision      = :base_revision;
ASSERT run_head.state_digest        = :base_digest;
ASSERT run_head.plan_digest         = :plan_digest;
ASSERT run_head.lease_owner_id      = :lease_owner_id;
ASSERT run_head.lease_epoch         = :lease_epoch;
ASSERT run_head.status              = 'RUNNING';
ASSERT run_lease.owner_id           = :lease_owner_id;
ASSERT run_lease.run_id             = run_head.run_id;
ASSERT run_lease.epoch              = :lease_epoch;
ASSERT run_lease.store_incarnation  = :store_incarnation;
ASSERT run_lease.expires_at         > store_now();
ASSERT step.status                  = 'READY_TO_COMMIT';
ASSERT step.scope                   = run_head.scope;
ASSERT step.lease_epoch             = :lease_epoch;

INSERT immutable_state_blobs ... ON CONFLICT VERIFY SAME DIGEST;
INSERT checkpoint ...;
UPDATE join_frames ... WHERE frame_revision = :expected_revision;
INSERT next_activations ...;
INSERT durable_stream_outbox ...;
UPDATE steps SET status='COMMITTED', commit_digest=:commit_digest ...;
UPDATE run_head
   SET state_revision=:base_revision+1,
       state_digest=:next_digest,
       checkpoint_id=:checkpoint_id,
       current_superstep=:superstep,
       plan_digest=NULL,
       budget_account=:next_budget_account,
       status=:next_status,
       stream_seq=:last_stream_seq
 WHERE tenant_id=:tenant_id
   AND thread_id=:thread_id
   AND branch_id=:branch_id
   AND run_id=:run_id
   AND graph_version_id=:graph_version_id
   AND store_incarnation=:store_incarnation
   AND state_revision=:base_revision
   AND lease_owner_id=:lease_owner_id
   AND lease_epoch=:lease_epoch
   AND status='RUNNING';
ASSERT ROW_COUNT = 1;
COMMIT;
```

The conditional CAS statement is the mutation's linearization point. A store
adapter SHALL prove serializable ordering with takeover and that `store_now()`
is evaluated at the statement, not frozen at a transaction-start instant.
Statements have a bounded timeout below the lease safety margin. If the adapter
cannot prove those properties, the predicate SHALL additionally require
remaining TTL greater than the qualified maximum transaction duration plus
commit/clock uncertainty.

Checkpoint, state head, join updates, next activations, budget consumption, and durable outbox records SHALL share this transaction. A database without multi-record atomicity may implement an append-only consensus log, but SHALL demonstrate equivalent linearizable semantics.

---

### 8.5 BSP supersteps, fan-out, and fan-in

#### 8.5.1 Superstep semantics

Let `S[k]` be the committed snapshot before user tasks in superstep `k`, and `F[k]` the committed activation frontier. Execution is:

```text
PLAN:      (S[k], F[k], graph version, budgets) -> immutable StepPlan[k]
EXECUTE:   every task reads S[k] and its own immutable input
STAGE:     workers persist signed/fenced TaskResult proposals
BARRIER:   validate complete coverage and build one CommitBundle
COMMIT:    atomically publish S[k+1], F[k+1], checkpoint, events, budgets
```

No task in `StepPlan[k]` may observe `S[k+1]`. Routes created by tasks in step `k` activate tasks no earlier than step `k+1`.

Planning SHALL be deterministic from the authoritative inputs. The `StepPlan` SHALL be persisted before workers acquire tasks. Replanning an existing step is allowed only if it produces the identical `plan_digest`; otherwise the run is quarantined.

#### 8.5.2 Fan-out with `Send`

```python
@dataclass(frozen=True)
class Send:
    node: str
    arg: FrozenValue
    key: str | None = None
    timeout_ms: int | None = None
    authority_ref: str | None = None
```

- A `Send` creates one activation and normally one task in the next superstep.
- `Send.node` MUST resolve to a node in the pinned graph version.
- `Send.arg` SHALL be copied into immutable content-addressed storage and validated against the target's input schema before the current step commits.
- Send identity SHALL derive from the source `TaskId` and emission index. If `key` is supplied, it becomes an additional stable semantic key; duplicate keys from one source outcome are invalid unless the edge declares coalescing.
- `timeout_ms` is capped by the node policy, run deadline, and tenant limits. A timeout cancels the attempt but does not allow its detached synchronous code to publish a result or effect.
- The compiler/runtime SHALL enforce per-task, per-step, per-run, and tenant-wide fan-out limits before committing the sends.
- A source retry returning the same outcome produces the same sends. A different send set for the same `TaskId` is `NONDETERMINISTIC_RESULT`.

Fan-out tasks may finish in any order. Their deltas merge only at the barrier using §8.4.4 canonical order.

#### 8.5.3 Plain fan-in versus join fan-in

A node receiving multiple independent activations has **OR fan-in**: each activation is a distinct task unless an explicit coalescing policy says otherwise. “Wait for all predecessors” SHALL never be inferred from multiple incoming edges.

**AND/ANY/QUORUM fan-in requires an explicit `JoinSpec`.**

```python
@dataclass(frozen=True)
class JoinSpec:
    join_spec_id: str
    target_node: str
    mode: Literal["ALL", "ANY", "QUORUM"]
    quorum: int | None
    duplicate_policy: Literal["IGNORE_SAME", "FAIL"]
    timeout_policy: Literal["WAIT", "FAIL", "ROUTE_DLQ", "PARTIAL"]
    timeout_ms: int | None
    reducer_channel: str | None
    member_failure_policy: Literal["FAIL", "ROUTE_DLQ", "PARTIAL"] = "FAIL"
    resolution_policy: Literal[
        "ALL_TERMINAL_CANONICAL",
        "RECORDED_DEADLINE_CANONICAL",
    ] = "ALL_TERMINAL_CANONICAL"

@dataclass(frozen=True)
class JoinFrame:
    scope: RecordScope
    frame_id: str
    join_spec_id: str
    parent_activation_id: str
    generation: int
    expected_members: tuple[str, ...]
    arrivals: Mapping[str, ArrivalRecord]
    status: Literal["OPEN", "SATISFIED", "EXPIRED", "CANCELLED"]
    revision: int
    deadline: Instant | None
```

`expected_members` SHALL be frozen when the frame is created. A member identity is an activation/task identity, not merely a node name. This prevents arrival from fan-out wave `n+1` satisfying wave `n`.

Arrival insertion SHALL be idempotent by `(frame_id, member_id)`. A duplicate with the same digest is a no-op; a duplicate with a different digest quarantines the run. Frame satisfaction and creation of its target activation SHALL occur in the same barrier transaction. Exactly one target activation may be created per satisfied frame.

`ALL` satisfies only when every expected member has a successful arrival. `ANY`
is `QUORUM(1)`. `ANY` and `QUORUM` SHALL NOT settle merely because the first
wall-clock subset happened to reach quorum. Their deterministic resolution is:

1. Under the default `ALL_TERMINAL_CANONICAL` policy, wait until every frozen
   expected member has a durable terminal record (`SUCCEEDED`, `FAILED`, or
   `CANCELLED`). Select the first `q` successful members by canonical member ID.
   If fewer than `q` succeeded, apply `member_failure_policy`.
2. `RECORDED_DEADLINE_CANONICAL` MAY resolve earlier only from one durable,
   store-time timer-firing record whose identity and observed arrival set are
   committed with the frame. Select the first `q` successful arrivals by
   canonical member ID. The timer record is an explicit external input to
   replay; without the same record, executions are not claimed equivalent.

Arrival delivery order before the same deterministic resolution point SHALL not
change the selected set. Frame satisfaction, the exact selected-member tuple,
frame closure, and creation of the single target activation SHALL share one CAS
transaction. Late arrivals are recorded as `LATE_ARRIVAL` and handled by the
declared policy; they SHALL NOT reopen a frame.

`PARTIAL` timeout handling is legal only where the target input schema and join spec explicitly declare partial membership. An unspecified timeout means durable `WAIT`, not process-local polling.

---

### 8.6 Routing and control decisions

#### 8.6.1 Closed-world routing

All static edges, conditional path keys, command destinations, parent boundaries, and join targets SHALL be compiled into the immutable graph version. A conditional router SHALL return a typed decision or a key from an explicit `path_map`. Destination inference from free-form LLM text is forbidden in the production profile.

LLM-produced routing text SHALL first pass through a schema-constrained adapter that maps it to an allowed enum. The adapter's failure is an invalid route; the raw text is evidence, never an executable identifier.

```python
ControlDecision = (
    Continue
    | Goto
    | SendMany
    | Halt
    | Wait
    | DeadLetter
    | Parent
)

@dataclass(frozen=True)
class Command:
    update: StateDelta = StateDelta.empty()
    goto: tuple[str | Send, ...] = ()
    control: ControlDecision = Continue()
    graph: Literal["LOCAL", "PARENT"] = "LOCAL"
    suppress_static: bool = False
```

Node returns MAY use `Command` to combine update and routing. `Command.goto` is additive to static routing by default, preserving the existing DharmaGraph/LangGraph behavior. Replacement semantics require `suppress_static=True` and compile-time node permission; silent suppression is forbidden.

At the barrier, the coordinator SHALL normalize control across the **entire**
accepted result set, not task completion order. It first materializes every
candidate static edge, conditional edge, `goto`, `Send`, join release, and
parent contribution, then sorts contributions by
`(dispatch_ordinal, task_id, contribution_index)`. Exactly one of these global
forms is valid:

| Form | Valid normalized contribution set |
|---|---|
| Continue/routing | Only `Continue`, `Goto`, and `SendMany`; union their validated targets in canonical order. |
| Halt | One or more byte-identical `Halt` values, no other non-`Continue` control, no candidate next activation of any kind, no open required join, and no unresolved required effect. |
| Wait | One or more byte-identical `Wait` values, no other non-`Continue` control, no candidate local/parent activation, no open required join, and no unresolved required effect. |
| Dead-letter | One or more byte-identical `DeadLetter` values, no other non-`Continue` control, and no candidate activation; settle through TX-G without committing task deltas. |
| Parent | One or more byte-identical `Parent` values, no local route or other non-`Continue` control; validate and hand off at exactly one compiled parent boundary. |

Different terminal/suspending kinds, unequal payloads of the same kind, a
terminal control plus a static/conditional/dynamic target, or an unauthorized
`suppress_static` are `INVALID_CONTROL`. They produce a failure settlement and
commit none of the step's graph-state deltas. There is no priority rule such as
“HALT wins” or “first task wins.”

#### 8.6.2 Terminal and suspended controls

```python
@dataclass(frozen=True)
class Halt:
    reason_code: str
    result_projection: str | None = None

@dataclass(frozen=True)
class Wait:
    wait_kind: Literal["SIGNAL", "TIMER", "APPROVAL", "RESOURCE"]
    correlation_key: str
    wake_after: Instant | None = None
    input_schema_id: str | None = None
    expires_at: Instant | None = None
    on_expire: Literal["FAIL", "DLQ", "ROUTE"] = "FAIL"

@dataclass(frozen=True)
class DeadLetter:
    reason_code: str
    evidence_refs: tuple[str, ...]
    recoverable: bool
```

- `HALT` requests successful termination after the current barrier commits. It
  MUST NOT coexist with a static edge, conditional target, `goto`, `Send`,
  parent activation, open required join, or unresolved required effect. Such
  ambiguity is `INVALID_CONTROL`.
- No frontier without an accepted `HALT` contribution is `STRANDED_RUN`, never
  success. The barrier SHALL fail or quarantine it with a termination proof
  describing the missing obligation, even when there are no open waits/joins.
- `WAIT` atomically commits state plus a durable wait record and transitions the run to `WAITING`. No in-memory coroutine is required to survive.
- Wake-up uses `(run_id, correlation_key, signal_id)` idempotency and compare-and-swap from the addressed wait revision. A duplicate signal cannot create duplicate tasks.
- `DLQ` atomically records reason, evidence, checkpoint, and recovery policy and transitions to `QUARANTINED`. It is not successful completion.
- `Parent` may cross exactly one compiled subgraph boundary. Its state update is validated through the parent's declared reducers. An unbound `PARENT`, arbitrary graph address, or cross-tenant target fails closed.
- `resume` is caller-side input to a persisted `WAIT`/interrupt, never an ordinary node-return command.

#### 8.6.3 Invalid route policy

An unknown route key, unknown node, `START` target, illegal `END` send, malformed sequence, unauthorized target, or route exceeding fan-out limits SHALL be detected while staging/validating the current step. The runtime SHALL:

1. reject the entire barrier commit;
2. preserve the prior checkpoint unchanged;
3. persist a typed non-retryable task/step failure with raw-output evidence redacted according to policy; and
4. transition according to the graph's explicit `invalid_route_policy`, whose production default is `DLQ`.

Allowed policies are `FAIL_RUN` and `DLQ`; silently dropping the route, substituting a default, retrying indefinitely, or leaving the run `RUNNING` is forbidden.

Invalid-route and invalid-control settlement SHALL use TX-G in §8.10. It leaves
the state revision, checkpoint, frontier, and join-consumption set unchanged,
while atomically closing the step/run under the selected failure policy and
publishing the durable failure/DLQ event. A crash cannot expose the failure row
while leaving the same plan dispatchable.

---

### 8.7 Scheduling, leases, retries, and result acceptance

#### 8.7.1 Coordinator ownership

At most one run lease may advance a branch head at a time. Acquisition SHALL
CAS the exact tenant/thread/branch/run/graph/head/status tuple and issue a
never-reused `lease_epoch` within the current `store_incarnation`. The pair
`(store_incarnation, lease_epoch)` is the coordinator fence. Every plan, task
lease, staged result, checkpoint commit, wait transition, event append, and
effect claim SHALL carry it.

A stale coordinator may continue computing but cannot commit. Storage SHALL reject its compare-and-swap. Lease duration is liveness metadata, while the monotonic fence is the safety mechanism; clocks alone SHALL never establish authority.

#### 8.7.2 Worker task leases

```python
@dataclass(frozen=True)
class TaskLease:
    scope: RecordScope
    task_id: str
    attempt_id: str
    attempt_no: int
    worker_id: str
    coordinator_owner_id: str
    coordinator_lease_epoch: int
    task_attempt_fence: int
    expires_at: Instant
```

- Claiming a task atomically changes it from `PLANNED`/`RETRYABLE` to `LEASED`, increments `attempt_no` and `task_attempt_fence`, and emits an attempt record whose `AttemptId` binds the active store incarnation.
- Heartbeats extend only the currently fenced lease.
- Expiry makes the attempt orphaned and eligible for retry, but does not itself prove the worker stopped.
- Result acceptance requires the complete scope, matching `TaskId`,
  `AttemptId`, plan digest, coordinator lease lineage, input digest, current
  task-attempt fence/state/deadline, and active store incarnation.
- A result from a stale attempt is retained as diagnostic evidence but cannot affect state.
- If an accepted result already exists for the `TaskId`, an identical `outcome_digest` is idempotent success. A different digest is a nondeterminism/security violation and quarantines the run.

#### 8.7.3 Retry semantics

Retry policies SHALL classify typed failures; `retry all exceptions` is prohibited. The policy includes maximum attempts, exponential backoff with recorded jitter input, retryable codes, and deadline/cost ceilings.

Retries do not advance the superstep and do not change `TaskId`. They consume attempt, time, token, cost, and external-effect budgets. A coordinator restart reconstructs the retry schedule from durable attempt records.

When one task fails while siblings succeed, successful siblings' immutable results MAY remain staged. The step does not commit. On retry/resume, the coordinator reuses valid staged results and runs only uncovered/failed tasks. It SHALL revalidate every reused result against the pinned plan and graph version at final barrier commit.

#### 8.7.4 Cancellation

Cancellation begins with a fenced CAS that changes the run to `CANCELLING`,
marks every nonterminal step/task as cancellation-requested, and emits its
durable lifecycle event. Task claim predicates SHALL require `run.status ==
RUNNING`; therefore no new lease can linearize after the cancellation CAS.
Workers receive cooperative cancellation, but lease/result fences remain the
safety boundary. The cancellation reconciler drains accepted effects and
atomically settles `CANCELLED`, or `QUARANTINED` if an effect remains ambiguous.
Late task results are diagnostic only and cannot commit graph state. Terminal
cancellation is monotonic. Continuing work requires either the audited
same-operation repair transfer in §8.3.1 or an exploratory fork with fresh
operation/task/effect namespaces and consequential effects disabled by default.

---

### 8.8 Cycle and resource robustness

Cycles are legal only when the compiled graph declares them and run admission supplies a complete `BudgetVector` within tenant policy.

```python
@dataclass(frozen=True)
class BudgetVector:
    supersteps: int
    tasks: int
    node_executions: Mapping[str, int]
    attempts: int
    sends: int
    effects: int
    tokens: int
    cost_micros: int

@dataclass(frozen=True)
class BudgetAccount:
    limits: BudgetVector
    spent: BudgetVector
    reserved: BudgetVector
    wall_deadline: Instant
    version: int
```

Requirements:

- `available = limits - spent - reserved` component-wise and SHALL never be
  negative. `spent` is monotonic. A reservation may be released, but neither
  release, resume, wait/wake, failover, SDK reconnect, repair, nor retry may
  raise `limits`, reduce `spent`, or make `available` exceed its value before
  that reservation. Every mutation CASes `BudgetAccount.version`.
- Planning reserves deterministic task/send/node-execution budget through
  TX-B. Barrier commit converts used reservation to `spent` and releases only
  the unused remainder through TX-F.
- Claiming an attempt charges `attempts` through TX-C. Effect claims, token
  grants, and cost grants reserve an upper bound before the provider/model can
  spend them; idempotent usage records settle actual consumption through TX-D.
  Charges survive failed steps and process death.
- `remaining_steps` exposed to a node is a managed read-only projection of the durable run-wide budget, never a user-writable state key.
- `supersteps` is charged once when a new step plan is published. A
  failing/retrying step reuses that reservation and cannot charge zero or reset
  the wall deadline.
- Nested subgraphs inherit a bounded child allocation. A child cannot mint budget or exceed its parent's remaining amount.
- Dynamic `Send` and join frame creation SHALL be budget-checked before the producing step commits.
- When any hard budget is exhausted with work still possible, the run transitions to `FAILED(BUDGET_EXHAUSTED)` or `QUARANTINED` according to explicit policy. It SHALL never return ordinary success.
- The runtime SHOULD support a deterministic livelock detector over repeated `(state_digest, frontier_digest, open_join_digest)` tuples. A repeated tuple may terminate earlier with `NO_PROGRESS_CYCLE`; it does not replace hard budgets.

A graph containing a cycle without admitted run-wide budgets SHALL fail compilation/admission. “The model will eventually choose END” is not a termination guarantee.

---

### 8.9 Durable run, step, and task state machines

#### 8.9.1 Run states

The run transition relation is closed. The following are the only legal target
states; a missing edge is rejected by CAS:

| From | Allowed targets |
|---|---|
| `CREATED` | `VALIDATING`, `CANCELLING`, `FAILED`, `QUARANTINED` |
| `VALIDATING` | `READY`, `CANCELLING`, `FAILED`, `QUARANTINED` |
| `READY` | `RUNNING`, `SUSPENDED`, `CANCELLING`, `FAILED`, `QUARANTINED` |
| `RUNNING` | `WAITING`, `SUSPENDED`, `CANCELLING`, `SUCCEEDED`, `FAILED`, `QUARANTINED` |
| `WAITING` | `RUNNING`, `SUSPENDED`, `CANCELLING`, `FAILED`, `QUARANTINED` |
| `SUSPENDED` | `READY`, `RUNNING`, `WAITING`, `CANCELLING`, `FAILED`, `QUARANTINED` |
| `CANCELLING` | `CANCELLED`, `QUARANTINED` |
| `SUCCEEDED`, `FAILED`, `CANCELLED`, `QUARANTINED` | none |

`WAITING -> RUNNING` is an idempotent wake or declared timeout route;
`WAITING -> FAILED/QUARANTINED` applies the declared expiry policy. A cancel is
accepted from every nonterminal state. `SUCCEEDED`, `FAILED`, `CANCELLED`, and
`QUARANTINED` are terminal for a `RunId`. Recovery from `QUARANTINED` creates a
new run through the same-operation repair transfer or exploratory-fork rules in
§8.3.1; it never changes the terminal run back to `RUNNING`.

The state meanings are:

- `CREATED`: invocation idempotency accepted; no graph validation claimed.
- `VALIDATING`: graph version, input schema, authority, budgets, and tenant admission are being checked.
- `READY`: authoritative initial checkpoint exists; coordinator work may be claimed.
- `RUNNING`: a coordinator fence owns progress; zero or one uncommitted `StepPlan` exists.
- `WAITING`: durable wake condition exists; no user task is considered active.
- `SUSPENDED`: operator/policy pause, distinct from a graph-authored wait.
- `CANCELLING`: cancellation is durable; active attempts are draining/reconciling.
- `SUCCEEDED`: an explicit valid normalized `HALT` committed with a verified
  termination proof and final checkpoint. Mere quiescence is never success.
- `FAILED`: typed unrecoverable execution failure or exhausted policy.
- `QUARANTINED`: integrity, authority, ambiguity, corruption, nondeterminism, or DLQ condition requiring inspection.

Every transition SHALL be append-recorded with old/new status, cause code,
actor/authority, store incarnation, lease owner/epoch, expected revision, and
event id. The transition table is implemented as an exhaustive
`(from_state, event_kind) -> to_state` map; no wildcard transition is allowed.

#### 8.9.2 Step states

```text
PLANNED      -> DISPATCHING | CANCELLED | FAILED | QUARANTINED
DISPATCHING  -> COLLECTING | RETRYING | CANCELLED | FAILED | QUARANTINED
COLLECTING   -> READY_TO_COMMIT | RETRYING | CANCELLED | FAILED | QUARANTINED
RETRYING     -> DISPATCHING | CANCELLED | FAILED | QUARANTINED
READY_TO_COMMIT -> COMMITTED | CANCELLED | FAILED | QUARANTINED
COMMITTED | CANCELLED | FAILED | QUARANTINED -> <no transition>
```

Only `COMMITTED` advances `RunHead.state_revision`. A step at
`READY_TO_COMMIT` may be committed repeatedly only as an idempotent transaction
yielding the same commit/checkpoint digest. Cancellation versus commit is
resolved by the run-head/step CAS: whichever linearizes first prevents the
other transition.

#### 8.9.3 Task states

```text
PLANNED    -> LEASED | CANCELLED
LEASED     -> RUNNING | ORPHANED | CANCELLED
RUNNING    -> SUCCEEDED_STAGED | RETRYABLE | ORPHANED | FAILED | CANCELLED
ORPHANED   -> RETRYABLE | LEASED | FAILED | CANCELLED
RETRYABLE  -> LEASED | FAILED | CANCELLED
SUCCEEDED_STAGED | FAILED | CANCELLED -> <no transition for this step>
```

Task status is not graph state. Staging a success does not expose its delta until barrier commit.

#### 8.9.4 Recovery algorithm

On coordinator acquisition:

1. acquire a new `(store_incarnation, lease_epoch)` fence without reusing an
   identity visible in any prior incarnation;
2. read and verify the run head, checkpoint, state blobs, graph version, budgets, wait/join records, and optional open step;
3. if no open step exists, deterministically plan the next frontier;
4. if an open step exists, verify its plan digest and classify tasks as accepted, leased-live, expired, retryable, or failed;
5. if run status is `CANCELLING`, lease no task and drive fenced cancellation
   drainage; otherwise reuse accepted staged outcomes and re-lease only
   missing/eligible tasks after confirming no permanent step failure;
6. if exact successful coverage exists, repeat the barrier transaction idempotently;
7. publish/re-publish outbox events from durable cursor state.

Recovery SHALL never infer completion from logs alone, never replay committed nodes 1–6 when resuming a checkpoint before node 7, and never trust an uncommitted in-memory state image.

---

### 8.10 Transaction boundaries and crash semantics

The production storage adapter SHALL expose the following linearizable operations, whether implemented with SQL transactions, a consensus log, or another proven mechanism.

#### 8.10.1 TX-A — Admit invocation

Atomically bind `(tenant_id, invocation_idempotency_key)` to `RunId`, graph
version, canonical input digest, `OperationId`, initial `BudgetAccount`,
`CREATED` run record, initial checkpoint lineage, and audit/outbox event. For a
new business operation, insert `OperationOwner(tenant_id, operation_id)` with a
unique primary key and this run as owner. Duplicate key/same digest returns the
original admission; duplicate key/different digest fails. A same-operation
repair is not ordinary admission and SHALL use TX-I.

#### 8.10.2 TX-B — Publish step plan

Compare-and-swap complete scope, current run revision/fence/status, operation
ownership, and `BudgetAccount.version`; reserve the step/task/node-execution
budget; write immutable plan/tasks/activations; set step `PLANNED` and run-head
`plan_digest`. No worker sees a task before TX-B commits.

#### 8.10.3 TX-C — Claim attempt and charge it

Require the run is `RUNNING`, the coordinator fence/current store incarnation
matches, and the task is `PLANNED` or `RETRYABLE`. Atomically insert the new
attempt/lease, increment attempt ordinal/fence, charge one `attempts` unit under
a unique charge ID, and transition the task to `LEASED`. Either lease and charge
both exist, or neither exists.

#### 8.10.4 TX-D — Reserve and settle resource usage

Before an effect/provider/model can consume effects, tokens, or cost, insert an
idempotent reservation keyed by
`ChargeId = H(scope, budget_kind, logical_source_id, charge_ordinal)` and CAS the
budget account. Usage acknowledgements monotonically move reserved units to
spent; unused units are released only by a fenced terminal settlement. Duplicate
charge ID/same digest is a no-op; different digest quarantines. A process crash
cannot erase incurred usage or make the provider grant exceed its reservation.
Consequential-effect reservation and claim additionally require that the run
and branch are the current `OperationOwner`; a retired source or unpublished
repair target cannot obtain a provider grant.

#### 8.10.5 TX-E — Accept task result

Compare complete task/attempt/lease scope and fences; validate input, plan,
result, delta, control, effect-receipt, and blob digests; settle known usage;
write the immutable outcome; and transition the task to `SUCCEEDED_STAGED`.
This transaction does not mutate graph state. An already accepted equal outcome
is idempotent; an unequal outcome for the same `TaskId` quarantines.

#### 8.10.6 TX-F — Commit successful barrier

Perform §8.4.6: validate exact coverage, recompute reducers and normalized
control/routing, update joins, publish the next frontier, convert/release budget
reservations, append checkpoint and durable stream events, and advance run head
in one transaction. Valid `Halt` and `Wait` settle `SUCCEEDED` and `WAITING`
respectively inside this transaction. A terminal `Halt` also updates the
current `OperationOwner` state; ownership is not inferred later from an event.

#### 8.10.7 TX-G — Settle failure, invalid control, or cancellation

CAS complete scope/fence/status/revision and atomically: leave graph state,
checkpoint, joins, and frontier unchanged; close/cancel the step and its
nonterminal tasks; persist typed failure/DLQ/cancellation evidence; settle
incurred budget charges and release only unused reservations; transition the run
to the policy-selected `FAILED`, `QUARANTINED`, `CANCELLING`, or `CANCELLED`;
and append the durable lifecycle event. The unique settlement ID makes retries
idempotent. This is the only settlement path for `FailureSettlement`, invalid
route/control, permanent task failure, and cancellation request/drain.
Every terminal settlement updates the current `OperationOwner` state in the
same transaction to `TERMINAL`, disables `external_effects_mode`, and revokes
new effect/task/wait progression authority; entering `CANCELLING` changes the
owner state to `DRAINING` and disables new effect dispatch while retaining only
the authority required to drain or reconcile already-dispatched work.

#### 8.10.8 TX-H — Create or consume a durable wait

Creating a graph-authored wait occurs with TX-F. Wake/expiry processing CASes
the exact wait and run revision, consumes one idempotent signal/timer record,
creates the continuation activation where applicable, and applies the closed
run-state transition in one transaction. Duplicate signals cannot create tasks.

#### 8.10.9 TX-I — Transfer same-operation repair ownership

Lock `OperationOwner` plus source and proposed target roots. Verify repair
authority, source terminal/quarantine state, namespace preservation, graph/path
migration proof, budget-account conservation, and effect reconciliation. In
one transaction, CAS
`owner_version`, retire the source ownership, publish the target root/checkpoint,
set `successor_run_id`, transfer owner run/branch and the conserved budget
account, and append audit/outbox events.
Before this commit the target is undispatchable; after it, the source is
undispatchable. Competing repair transfers have exactly one winner.

#### 8.10.10 TX-J — Acknowledge outbox delivery

Advance a subscriber delivery cursor only after delivery according to the
selected transport contract. Cursor updates never change graph state.

Crash expectations:

| Crash point | Required recovery behavior |
|---|---|
| Before TX-B commit | No tasks exist; replan from same head |
| After TX-B, before dispatch | Claim persisted tasks |
| During TX-C | Attempt lease and attempt charge both exist or neither exists |
| During node execution | Lease expires; retry same `TaskId` with new `AttemptId` |
| During TX-D or after external effect, before result | Reservation/usage is idempotently recoverable; reconcile by stable effect ID and never blindly repeat |
| After TX-E | Reuse staged result; do not rerun successful task |
| During TX-F | Observe either old head or complete new head, never partial merge |
| After TX-F, before notification | Outbox publisher emits committed events |
| During TX-G | Failure/cancel state and durable evidence are both absent or both committed; the plan is never left dispatchable |
| During TX-H | Wait/signal and continuation transition are exactly-once by record identity |
| During TX-I | Exactly one of source or repair target owns the operation; never both or neither |
| During stream delivery | Subscriber may receive duplicate event; same `StreamEventId` permits dedupe |

Any implementation that can expose a checkpoint without its corresponding state, advance state without its budget/event records, or schedule next tasks before the preceding state commit is non-conforming.

---

### 8.11 Failure taxonomy and mandatory disposition

```python
class FailureClass(Enum):
    USER_RETRYABLE = "user_retryable"
    USER_NONRETRYABLE = "user_nonretryable"
    INFRA_RETRYABLE = "infra_retryable"
    POLICY = "policy"
    INTEGRITY = "integrity"
    CANCELLED = "cancelled"
```

Every failure record SHALL contain a stable code, class, retry decision, attempt/task/step/run identities, evidence references, redaction metadata, causal chain, and state/checkpoint digest. Free-form exception strings are supplemental only.

| Condition | Step/state effect | Default disposition |
|---|---|---|
| Node timeout/transient provider error | No barrier commit | bounded retry |
| Invalid node return/delta/schema | No barrier commit | fail or DLQ |
| Invalid/hallucinated route | No barrier commit | DLQ |
| Reducer throws or returns invalid bytes | No barrier commit | quarantine |
| Conflicting single-writer deltas | No barrier commit | quarantine design error |
| Duplicate task, same outcome digest | none | idempotent accept |
| Duplicate task, different outcome digest | No barrier commit | quarantine nondeterminism |
| Worker/coordinator stale fence | none | reject; recover under current fence |
| Checkpoint/blob digest mismatch | stop all dispatch | quarantine corruption |
| Budget/deadline exhausted | No new work | typed failure/quarantine |
| Join deadline expires | per declared join policy | never implicit success |
| Storage unavailable | no unsafe local commit | infrastructure retry/backpressure |
| Subscriber slow/disconnected | graph continues within outbox quota | cursor replay/backpressure |

There SHALL be no code path that catches a control-plane exception, logs it, and returns `SUCCEEDED`.

---

### 8.12 Asynchronous invocation and streaming

#### 8.12.1 Required internal kernel SPI

`GraphRuntime` in §7 is the sole public ingress. It authenticates the caller,
authorizes the requested operation, resolves tenant and graph scope, enforces
request idempotency, and only then delegates to this internal SPI using a
trusted context that callers cannot construct from request fields alone.

```python
@dataclass(frozen=True)
class AuthorizedRunContext:
    scope_authority_id: str
    tenant_id: str
    actor_id: str
    policy_decision_id: str
    request_idempotency_key: str
    request_digest: str

class AsyncGraphKernel(Protocol):
    async def ainvoke(
        self, input: Mapping[str, Any], *, config: RunConfig,
        authz: AuthorizedRunContext
    ) -> GraphRunResult: ...

    async def astart(
        self, input: Mapping[str, Any], *, config: RunConfig,
        authz: AuthorizedRunContext
    ) -> RunHandle: ...

    async def aresume(
        self, run_id: str, resume: ResumeInput, *, expected_revision: int,
        authz: AuthorizedRunContext
    ) -> RunHandle: ...

    def astream(
        self, run_id: str, *, cursor: StreamCursor | None,
        modes: frozenset[StreamMode], authz: AuthorizedRunContext
    ) -> AsyncIterator[StreamEvent]: ...

    async def acancel(
        self, run_id: str, *, reason: str, expected_revision: int | None,
        authz: AuthorizedRunContext
    ) -> RunHead: ...
```

The kernel SHALL reject a missing, expired, wrong-tenant, or wrong-operation
trusted context before reading run data. `AsyncGraphKernel`, candidate
`CompiledGraph` objects, storage adapters, and worker APIs are not application
entry points and SHALL not be exported through the production service SDK.

`astart` SHALL durably admit work and return without holding an application request open for the entire run. Background progress belongs to durable coordinators/workers, not a process-local `create_task` whose loss abandons the run.

Synchronous convenience APIs MAY exist only as `GraphRuntime` client adapters
around the asynchronous/durable service boundary. They SHALL detect invocation
from an already-running event loop and fail with guidance rather than
nesting/blocking that loop.

#### 8.12.2 Non-blocking node execution

- Native async nodes execute as supervised tasks under structured concurrency.
- Synchronous nodes execute in a bounded, instrumented executor or isolated worker process. No synchronous user callable may run on the coordinator event-loop thread, whether or not it declares a timeout.
- Each task has deadline propagation, cancellation scope, memory/output limits, and tenant concurrency permits.
- A slow API call consumes only its task/tenant permit. Other ready siblings and other runs continue.
- Coordinator lease heartbeats, task heartbeats, persistence operations, and stream publication use separate bounded capacity pools so user-code saturation cannot starve safety work.
- Blocking storage/SDK drivers SHALL use async drivers or isolated bounded executors.
- Timeouts around non-cancellable threads SHALL fence and discard late results. External effects still require reconciliation.
- `asyncio.gather` without bounded admission, failure supervision, and drainage is non-conforming.

#### 8.12.3 Stream event model

```python
class StreamMode(Enum):
    CONTROL = "control"
    STATE = "state"
    UPDATES = "updates"
    TOKENS = "tokens"
    CUSTOM = "custom"
    DEBUG = "debug"

@dataclass(frozen=True)
class StreamCursor:
    tenant_id: str
    run_id: str
    stream_incarnation: str
    seq: int

@dataclass(frozen=True)
class StreamEvent:
    scope: RecordScope
    stream_incarnation: str
    event_id: str
    run_id: str
    seq: int
    mode: StreamMode
    event_type: str
    payload_ref: str
    payload_digest: str
    state_revision: int
    superstep: int
    task_id: str | None
    attempt_id: str | None
    durability: Literal["DURABLE", "BEST_EFFORT"]
```

`run_id` SHALL equal `scope.run_id`. A durable event's `stream_incarnation` and
fields SHALL reproduce the `StreamEventId` formula in §8.3; an event copied
across a restore incarnation therefore cannot alias an identity emitted before
rollback.

Within `(tenant_id, run_id, stream_incarnation)`, durable stream `seq` is
strictly increasing and allocated in the same transaction as the state/control
transition it describes. The cursor and ordering key are the tuple
`(stream_incarnation, seq)`, never bare `seq`. Consumers receive at-least-once
delivery and deduplicate by `event_id`. A cursor resumes strictly after that
tuple. After PITR/activation, an old-incarnation cursor returns a signed
`RESTORE_DISCONTINUITY` containing the last externally witnessed cursor and
the first cursor in the new incarnation; the server never silently interprets
the numeric sequence in a different incarnation. The server SHALL return typed
`CURSOR_EXPIRED` with the earliest retained checkpoint/event when retention
prevents exact replay. `BEST_EFFORT` events SHALL use a separate ephemeral
sequence namespace or carry the most recent durable cursor; they SHALL NOT
consume durable sequence numbers and create unexplained replay gaps.

Mandatory durable events include run transitions, step plans/commits/failures, accepted state updates, checkpoint creation, waits/wakes, DLQ/quarantine, cancellation, budget exhaustion, and terminal results.

Token streaming requirements:

- Token/chunk events SHALL include task and attempt identity plus a task-local monotonic `chunk_seq`.
- Chunks from different tasks may interleave; order within one attempt SHALL be preserved.
- Token chunks are observations, not graph-state writes. A model stream does not affect committed state until its node returns a validated outcome.
- The production default SHOULD be durable token events where user-visible transcript recovery is required. A deployment MAY declare `BEST_EFFORT` token mode, but it SHALL advertise that reconnect cannot recover lost chunks and SHALL emit a durable `TOKEN_STREAM_INCOMPLETE` range marker when loss is detected.
- Chunks from a stale/rejected attempt SHALL be marked speculative/rejected and SHALL never masquerade as the accepted final output.

#### 8.12.4 Backpressure and quotas

The runtime SHALL use bounded queues. A slow client may backpressure its connection but SHALL not block barrier commits indefinitely. Durable events accumulate in a quota-controlled outbox; crossing warning limits triggers metrics and admission throttling, and crossing hard limits transitions according to explicit policy rather than exhausting memory.

Debug and best-effort token events MAY be sampled or dropped under declared policy. Durable control/state events SHALL never be silently dropped. Subscriber disconnect is not run cancellation unless the caller explicitly requested cancellation-on-disconnect and policy permits it.

---

### 8.13 Reference coordinator loop

This pseudocode is normative in behavior, not implementation language:

```python
async def coordinate(scope: RecordScope) -> None:
    fence = await store.acquire_run_fence(scope)
    try:
        while True:
            head = await store.read_verified_head(scope)
            require head.scope == scope
            require head.scope.store_incarnation == fence.store_incarnation
            require head.lease_owner_id == fence.lease_owner_id
            require head.lease_epoch == fence.lease_epoch

            if head.status in TERMINAL:
                return
            if head.status == CANCELLING:
                await store.tx_progress_cancellation(
                    scope, fence, expected_revision=head.state_revision
                )  # TX-G; this path never claims work
                continue
            if head.status in {WAITING, SUSPENDED}:
                await store.release_or_park_fence(scope, fence)
                return
            require head.status == RUNNING
            step = await store.read_open_step(scope)
            if step is None:
                if hard_budget_exhausted(head):
                    await store.tx_settle_failure(
                        budget_exhaustion(head), fence,
                        expected_revision=head.state_revision,
                    )  # TX-G, before planning or leasing more work
                    continue
                snapshot = await store.load_and_verify_checkpoint(head.checkpoint_id)
                plan = deterministic_plan(snapshot, head, compiled_graph)
                if plan.tasks == ():
                    await store.tx_settle_failure(
                        stranded_run(plan), fence,
                        expected_revision=head.state_revision,
                    )  # TX-G; WAIT/HALT would already have settled the run
                    continue
                step = await store.tx_publish_plan(plan, fence, expected=head)

            classification = await store.classify_results_and_leases(step, fence)
            if classification.has_permanent_failure:
                await store.tx_settle_failure(
                    permanent_step_failure(step, classification), fence,
                    expected_revision=head.state_revision,
                )  # TX-G, before any new lease
                continue
            if not classification.exact_success_coverage:
                if hard_budget_exhausted(head):
                    await store.tx_settle_failure(
                        budget_exhaustion(head), fence,
                        expected_revision=head.state_revision,
                    )  # TX-G, before any new lease
                    continue
                # TX-C rechecks complete scope, current fence, and RUNNING in
                # the same statement that creates each attempt and charge.
                await store.tx_claim_missing_tasks_bounded(
                    classification, fence, required_run_status=RUNNING
                )
                await wait_for_result_lease_or_cancel_event()
                continue

            # Recompute from immutable task result bytes under coordinator code.
            commit_head = await store.read_verified_head(scope)
            if commit_head.status == CANCELLING:
                continue
            require commit_head.status == RUNNING
            require commit_head.scope.store_incarnation == fence.store_incarnation
            require commit_head.lease_owner_id == fence.lease_owner_id
            require commit_head.lease_epoch == fence.lease_epoch
            bundle = build_commit_candidate(
                head=commit_head,
                plan=step.plan,
                staged_results=await store.read_staged_results(step.step_id),
                snapshot=await store.load_and_verify_checkpoint(
                    step.plan.base_checkpoint_id
                ),
            )
            if isinstance(bundle, FailureSettlement):
                await store.tx_settle_failure(bundle, fence)  # TX-G
            else:
                await store.tx_commit_barrier(bundle, fence)  # TX-F
    finally:
        await store.best_effort_release_fence(scope, fence)
```

Every transaction above treats a lost fence or head-CAS mismatch as a signal to
discard the in-memory candidate and restart the loop from a verified head. It
never retries a stale `CommitBundle` against a newer revision.

There is no mutable global state shared by task coroutines, no routing based on task completion order, and no checkpoint written outside the authoritative commit.

---

### 8.14 Core acceptance and adversarial qualification tests

Passing unit tests is necessary but insufficient. The production profile SHALL pass every test below against the real production storage adapter with at least two coordinators and multiple worker processes. Fault tests SHALL run repeatedly with randomized injection points.

#### 8.14.1 State integrity

- **CORE-STATE-001 — malicious in-place mutation:** A node mutates nested dict/list objects in its input then raises. The committed snapshot and digest remain byte-identical.
- **CORE-STATE-002 — retained reference:** A node returns an object and mutates its retained reference after result staging. Stored result bytes and committed state do not change.
- **CORE-STATE-003 — semantic replay under randomized delivery:** Clone one
  fixed authoritative pre-step image—including run/scope identities, store and
  stream incarnations, plan, accepted external inputs, and immutable task
  outcomes—into isolated stores. Deliver the outcomes in 1,000 permutations.
  The committed state bytes/digest, frontier, next-plan digest, normalized
  control, checkpoint semantic content, and canonical durable event
  type/payload sequence are identical. Compare a defined semantic projection;
  transport delivery timestamps and other observational metadata are excluded.
  Creating fresh `RunId`s and then requiring raw record bytes to match is not a
  valid test.
- **CORE-STATE-004 — single-writer collision:** Two sibling tasks write a single-writer channel, including the same value. Entire step rejects with no state/version/checkpoint advancement.
- **CORE-STATE-005 — reducer laws:** Property tests cover identity, associativity, canonical batching invariance, serialization round-trip, and commutativity where declared.
- **CORE-STATE-006 — reducer failure:** One reducer raises after other channels validate. No channel advances and no next activation/outbox event becomes visible.
- **CORE-STATE-007 — stale CAS:** Two coordinators build different candidates from one head. Exactly one fence/CAS may commit; the other is rejected.
- **CORE-STATE-008 — duplicate outcomes:** Equal duplicate result is idempotent; unequal duplicate result quarantines before reducer application.
- **CORE-STATE-009 — corruption:** Flip one state/blob/checkpoint byte. Restore refuses execution and emits `CORRUPT_STATE` quarantine evidence.

#### 8.14.2 BSP, fan-out, and joins

- **CORE-BSP-001 — snapshot isolation:** Sibling B cannot see sibling A's current-step proposal; both see the same base digest.
- **CORE-BSP-002 — failed sibling:** Task 7 fails while siblings succeed. No partial state commits; successful staged results remain reusable under policy.
- **CORE-BSP-003 — exact resume:** Crash after nodes 1–6 are in committed steps and before/while node 7 runs. Resume by checkpoint/run id does not execute 1–6 again.
- **CORE-BSP-004 — post-stage crash:** Crash after all task results stage but before barrier commit. Recovery commits from stored results without rerunning nodes.
- **CORE-BSP-005 — Send identity:** Retry a source task. Identical sends have identical activation/task IDs and create no duplicates.
- **CORE-JOIN-001 — wave isolation:** Interleave arrivals from 100 generations of the same join. No generation is satisfied by another generation's member.
- **CORE-JOIN-002 — duplicate arrival:** Same arrival/digest is ignored idempotently; different digest quarantines.
- **CORE-JOIN-003 — exactly one release:** Concurrent last-member arrivals create exactly one target activation.
- **CORE-JOIN-004 — ANY/QUORUM determinism:** For a fixed frame and terminal
  member set, randomize arrival delivery before the same all-terminal closure.
  No early arrival closes the frame; every run selects the same first `q`
  successful canonical member IDs and creates one identical target activation.
- **CORE-JOIN-005 — recorded deadline:** For a
  `RECORDED_DEADLINE_CANONICAL` frame, replay the same durable store-time timer
  input with randomized pre-deadline arrival delivery. Selection and closure
  are identical. Kill all coordinators across the deadline; the timer/timeout
  policy and target or failure settlement apply exactly once.

#### 8.14.3 Routing and cycles

- **CORE-ROUTE-001 — hallucinated key:** Router/LLM returns an unmapped identifier. The step does not commit, the run does not hang, and default production policy creates a typed DLQ record.
- **CORE-ROUTE-002 — malformed command:** Test unknown goto, `START`, `Send(END)`, unbound parent, resume-from-node, unauthorized target, and control/goto conflict; all fail closed.
- **CORE-ROUTE-003 — HALT:** Valid HALT atomically commits its delta, final checkpoint, terminal event, and `SUCCEEDED`; no later task is leased.
- **CORE-ROUTE-004 — WAIT/wake:** Crash before and after wait commit and send the same wake signal concurrently 100 times. Exactly one continuation activation exists.
- **CORE-ROUTE-005 — stranded quiescence:** No frontier and no accepted
  `HALT` never returns success, including when no join or wait remains open.
- **CORE-ROUTE-006 — deterministic control fold:** Exercise static route plus
  `Halt`, mixed `Wait`/`DeadLetter`, unequal terminal-control payloads, local
  route plus `Parent`, and multiple identical terminal controls. Invalid sets
  settle through TX-G with no state delta; the one allowed identical set has a
  completion-order-independent outcome.
- **CORE-ROUTE-007 — atomic invalid-route settlement:** Kill before and after
  every write attempted while settling an unknown route. The old checkpoint,
  state, frontier, and joins remain unchanged, while the typed terminal/DLQ
  evidence and closed step are both absent or both visible; the plan can never
  be claimed again after settlement.
- **CORE-CYCLE-001 — self-loop cap:** An unconditional self-loop terminates with `BUDGET_EXHAUSTED` at the exact durable count.
- **CORE-CYCLE-002 — resume budget:** Repeated resume/wait cycles never replenish run-wide step/task/effect/cost budgets.
- **CORE-CYCLE-003 — retry budget:** A permanently transient-classified failure cannot retry past attempts/deadline/cost limits.
- **CORE-CYCLE-004 — fan-out bomb:** Exponential sends are rejected before the producing barrier commits when reservations exceed limits.
- **CORE-CYCLE-005 — nested budget:** Child subgraph cannot consume more than its allocated parent slice.

#### 8.14.4 Leases, crashes, and transactions

- **CORE-LEASE-001 — stale worker:** Pause worker A past lease expiry, complete with worker B, then release A. A's late result cannot change state or emit accepted output.
- **CORE-LEASE-002 — stale coordinator:** Partition coordinator A, promote B, then heal A. Only B's fence can commit.
- **CORE-LEASE-003 — execution identity:** `TaskId` is stable across retry and
  failover within one run, while `AttemptId` changes for every ordinal and
  store incarnation. A same-operation repair creates a new `RunId` and
  `TaskId` but preserves the mapped `SemanticTaskId`, `TaskNamespaceId`,
  `EffectNamespaceId`, and logical `EffectId`.
- **CORE-LEASE-004 — cancellation/claim race:** Race cancellation against task
  claims and barrier commit under two coordinators. After the cancellation CAS
  no TX-C claim can commit; whichever of commit or cancel linearizes first
  determines the closed transition, and late results never advance state.
- **CORE-SCOPE-001 — scope and incarnation isolation:** Reuse local-looking
  run/task/event IDs across two tenants, branches, and restored store
  incarnations. Every cross-scope read, claim, result, CAS, effect grant, and
  stream cursor is rejected; no pre-restore fence/attempt/event aliases a
  post-restore identity.
- **CORE-TX-001 — crash matrix:** Inject process kill/storage error before and after every durable write in TX-A through TX-J. Observed state always matches the crash table in §8.10.
- **CORE-TX-002 — checkpoint atomicity:** There is no observable run head pointing at a missing checkpoint/blob or checkpoint ahead of the head.
- **CORE-TX-003 — effect ambiguity:** Kill after provider success and before receipt acknowledgment. Reconciliation resolves by stable effect id or quarantines `UNKNOWN`; it does not blindly duplicate.
- **CORE-TX-004 — monotonic resource charges:** Kill at every TX-B, TX-C, TX-D,
  TX-F, and TX-G boundary around reservations, attempts, token chunks, provider
  usage, failed steps, and retries. `spent` never decreases, no charge is
  duplicated, no grant exceeds its reservation, and recovery cannot recreate
  available budget consumed before the crash.
- **CORE-TX-005 — repair ownership race:** Start two authorized repairs of one
  quarantined operation while a stale source worker attempts an effect claim.
  Exactly one TX-I wins; at every observable point exactly one source/target
  root owns the operation, and only that owner can obtain a consequential
  effect grant.
- **CORE-LIFE-001 — closed transitions:** Exhaustively enumerate every
  `(run_state, event_kind)`, step transition, and task transition. Listed edges
  succeed under their predicates; every omitted edge and every transition out
  of a terminal state fails its CAS without a lifecycle event.

#### 8.14.5 Asynchronous execution and streaming

- **CORE-ASYNC-001 — event-loop heartbeat:** Run a deliberately blocking synchronous node and async siblings. Coordinator heartbeat jitter stays within SLO and siblings progress; the sync node executes off-loop.
- **CORE-ASYNC-002 — slow API isolation:** One 60-second API call does not block unrelated runs, ready siblings, lease renewals, or stream delivery.
- **CORE-ASYNC-003 — bounded concurrency:** Submit work above every concurrency limit. Memory/threads remain bounded and admission is fair by tenant.
- **CORE-ASYNC-004 — cancellation drainage:** Cancel during async call, sync call, reducer preparation, and stream production. No late result commits; ambiguous effects reconcile.
- **CORE-STREAM-001 — cursor reconnect:** Disconnect after each possible durable event, reconnect by cursor, and reconstruct the exact ordered state/control sequence with only deduplicable repeats.
- **CORE-STREAM-002 — slow subscriber:** A stalled consumer does not block graph commit; outbox quotas/backpressure apply without unbounded memory.
- **CORE-STREAM-003 — token order:** Randomly interleaved token streams preserve per-attempt chunk order and identify accepted versus stale attempts.
- **CORE-STREAM-004 — commit correlation:** Every externally observed committed state update references the checkpoint/state revision created in the same transaction.
- **CORE-STREAM-005 — process loss:** Kill the stream publisher after commit but before delivery acknowledgment. Events are redelivered with identical ids.

#### 8.14.6 Admission gates

The core execution profile SHALL NOT be called production-grade until:

1. every test above passes on the production persistence and queue adapters;
2. reducer law tests cover every registered reducer implementation digest;
3. the full crash matrix completes with zero invariant violations;
4. multi-process soak and partition tests show no double commit, cross-run state bleed, orphaned `RUNNING` run, or unbounded queue;
5. operational dashboards expose run/step/task state, fences, leases, budgets, open joins/waits, checkpoint age, outbox lag, retry causes, DLQ, and quarantine;
6. schema/version migration and rollback tests prove old checkpoints remain readable or fail with an explicit non-destructive migration requirement; and
7. all candidate/test-only execution paths are either removed from production dispatch or guarded by a fail-closed profile boundary.

---

### 8.15 Core conformance checklist

A reviewer can reject a release if any answer below is “no”:

- Is authoritative state immutable outside one fenced barrier transaction?
- Are all concurrent writes represented as typed deltas and merged in committed canonical order?
- Are write conflicts explicit rather than last-finisher-wins?
- Does one failed task leave the entire superstep uncommitted?
- Can successful sibling results survive a crash without exposing partial state?
- Are `Send` tasks, retries, attempts, effects, joins, and stream events assigned stable identities?
- Are join arrivals scoped to a specific frame/generation?
- Does an invalid route reach a typed terminal/DLQ disposition instead of hanging or disappearing?
- Are cycle/resource budgets durable, run-wide, monotonic, and preserved across resume?
- Can a stale coordinator or worker compute but never commit?
- Does resume continue from an authenticated checkpoint without re-running committed predecessors?
- Do synchronous nodes run off the event loop under bounded capacity?
- Can a run progress without an attached client connection?
- Can a stream subscriber resume by cursor and deduplicate every durable event?
- Do checkpoint, state head, budgets, join updates, next activations, and durable events commit atomically?

If any answer is “no,” the runtime remains a candidate graph engine, not a production distributed state machine.

## 9. Durability, recovery, and external-effects contract

This part is normative for persistent execution, recovery, and consequential
side effects. It shares the identities, run states, reducer semantics, and
public authority boundary defined in §§5–8. Where this part introduces a more
specialized persistent record, that record refines rather than replaces the
core contract. Durability subsection numbers are globally rebased under §9.

All §9 schemas implicitly embed the following common envelope even when the
field is elided from a compact record block:

~~~text
PersistentRecordEnvelope {
  schema_version
  tenant_id | null              // null only for deployment-global control
  record_kind
  record_id
  graph_run_ref | null          // authenticated FK supplies graph revision
  created_in_store_incarnation
  integrity_version
}
~~~

Tenant-scoped rows MUST have non-null tenant identity. Records not scoped to a
graph run leave `graph_run_ref` null rather than inventing a graph revision;
records that can affect a run require the exact authenticated foreign key.

### 9.1 Scope and claims

This contract owns:

1. authoritative run and thread state;
2. immutable checkpoint frames and authenticated checkpoint records;
3. task plans, attempts, results, and superstep bundles;
4. leases, fencing tokens, head compare-and-swap, and writer authority;
5. exact resume, historical fork, schema migration, and compaction;
6. durable effects, provider idempotency, reconciliation, uncertainty, and sagas;
7. durable waits, human interrupts, signals, timers, and child-run joins;
8. transactional outbox and destination deduplication;
9. content-addressed blob storage, retention, garbage collection, and legal holds;
10. backup, point-in-time recovery, disaster activation, and incarnation fencing.

It does not promise the impossible:

- Exactly-once external execution cannot be guaranteed against a provider that supplies neither an idempotency key nor a status/query protocol.
- A database transaction cannot be atomic with an arbitrary network call.
- An in-memory Python coroutine stack is not a durable continuation.
- A lease by itself is not a lock and cannot prevent a paused or partitioned process from waking later.
- At-least-once publication can duplicate a message after an acknowledgement is lost; consumers need an inbox/deduplication key.

Any product claim that hides one of those limits is non-conformant.

#### 9.1.1 Deployment profiles

The implementation SHALL expose the document-wide profile identifiers and
meanings defined in §10.2. The labels below are exact aliases, not a second
profile taxonomy:

| Canonical profile | Alias | Permitted backing | Claims |
|---|---|---|---|
| DG-P0 | LAB | in-memory, SQLite, locked JSON, local filesystem, deterministic emulators | development and reproducible qualification only; never production |
| DG-P1 | SINGLE_TENANT_DURABLE | one transactional durable authority domain plus versioned blobs and strict effect adapters | bounded single-tenant production only after DG-P1 gates pass |
| DG-P2 | SINGLE_REGION_HA | strongly consistent HA metadata, distributed quota/lease arbitration, durable broker/outbox, externally fenced recovery | single-region HA production only after DG-P2 gates pass |
| DG-P3 | MULTI_TENANT_REGULATED | DG-P2 plus tenant isolation, encryption, authorization, audit, retention, and regulated controls | named regulated/multitenant production only after DG-P3 gates pass |

The runtime MUST refuse a production-readiness label if DG-P0 components sit on
an authoritative path. Deterministic test mode is a qualification method, not
a deployable profile.

---

### 9.2 Normative durability invariants

The following invariants are individually testable. Their identifiers are permanent acceptance-test references.

#### 9.2.1 Authority and state

**DG-DUR-001 — One authoritative head.** A run has exactly one authoritative committed head tuple:

~~~text
(store_lineage_id, active_incarnation_id, run_id,
 head_checkpoint_id, head_frame_digest, head_version)
~~~

Only the Durability Service may change it.

**DG-DUR-002 — Fenced mutation.** Every run mutation MUST carry the active store incarnation, authenticated principal, capability/warrant envelope, lease holder, and monotonically increasing fencing token. A stale token MUST fail even if the former lease holder later resumes.

**DG-DUR-003 — CAS is final authority.** Lease possession is necessary but not sufficient. Head movement requires compare-and-swap against the expected head checkpoint and expected head version in the same database transaction.

**DG-DUR-004 — Immutable checkpoints.** Checkpoint semantic content, checkpoint identity, frame digest, parent link, graph package, schema/reducer/codec manifests, and blob references MUST never be updated in place.

**DG-DUR-005 — Authenticated content.** Every frame and referenced blob MUST be length-checked, digest-checked, tenant-bound, and cryptographically authenticated before it can influence execution. Verification failure quarantines the run; it never falls back to a best-effort read.

**DG-DUR-006 — Step atomicity.** A superstep either advances the head with one complete, valid bundle or advances nothing. No successful sibling may leak a state mutation into the visible head before the barrier commit.

**DG-DUR-007 — Reducer-only state.** Node code receives an immutable snapshot and returns typed deltas, commands, waits, and effect declarations. It MUST NOT mutate authoritative state objects in place. The trusted reducer engine is the only writer of the next state manifest.

**DG-DUR-008 — Canonical merge.** Bundle reduction order is a pure, versioned function of channel, node identity, task identity, and declared reducer semantics. Completion order, worker identity, wall-clock time, and hash-map iteration MUST NOT affect the state root.

#### 9.2.2 Resume and task work

**DG-DUR-009 — Exact committed resume.** Resume starts after the selected committed checkpoint. Tasks represented by that checkpoint MUST NOT re-execute.

**DG-DUR-010 — Reusable uncommitted work.** A succeeded task result may be reused directly only when its input checkpoint, SemanticTaskId, TaskId, graph package, node code digest, reducer manifest, schema manifest, effect-call history, and plan digest exactly match the resumed plan. Cross-TaskId reuse requires a trusted compatibility proof keyed by the same SemanticTaskId.

**DG-DUR-011 — Stable semantic task identity.** SemanticTaskId is H(tenant, operation_id, task_namespace_id, stable_task_path). Same-operation retry, replan, repair, and migration preserve those inputs. Run, plan, TaskId, AttemptId, worker, graph revision, code digest, request bytes, and time MUST NOT enter SemanticTaskId.

**DG-DUR-012 — First fenced result wins.** One task slot has at most one accepted result. Late or stale attempt results may be retained as audit evidence but MUST NOT enter a bundle.

**DG-DUR-013 — Compatibility pinned.** Resume requires the exact graph package, state schema, channel codecs, reducers, router semantics, and runtime semantic version named by the frame. Missing or incompatible material produces MIGRATION_REQUIRED or INCOMPATIBLE_RUNTIME, never reinterpretation.

**DG-DUR-014 — Budget persistence.** Recursion, token, cost, deadline, retry, and effect budgets are checkpointed semantic state. Resume MUST NOT silently reset a lifetime budget. A separately declared per-invocation budget MAY reset only if its policy explicitly says so.

#### 9.2.3 Effects and messages

**DG-DUR-015 — Intent before effect.** No external provider call may occur until its immutable EffectIntent and authority decision are durably committed.

**DG-DUR-016 — Stable effect identity.** EffectId is H(tenant, operation_id, effect_namespace_id, stable_task_path, effect_slot). A retry, replan, same-operation repair/migration, crash replay, or restore uses the same effect_id and provider idempotency key. Attempt, run, plan, graph revision, request bytes, and time MUST NOT mint a new semantic effect.

**DG-DUR-017 — Origin and fence are distinct.** The origin idempotency key follows the user or agent intent end to end. The effect fence key identifies one semantic external operation. Neither may overwrite the other.

**DG-DUR-018 — No production fail-open.** If the persistence store, execution identity, effect identity, warrant, policy decision, encryption key, or activation authority is unavailable, consequential effect dispatch MUST fail closed. A receipt saying unprotected_dispatch is observability of a contract violation, not a production safety mechanism.

**DG-DUR-019 — Uncertainty is a state.** If the provider may have accepted an operation but success cannot be proved, the effect becomes UNKNOWN. It is not automatically called failed, succeeded, or retried.

**DG-DUR-020 — No false rollback.** Saga compensation is a new external effect with its own stable identity and receipt. A compensated saga records that forward effects occurred and compensations later occurred; it MUST NOT claim the original effects never happened.

**DG-DUR-021 — Transactional publication.** State commits, effect status transitions, wait transitions, and their corresponding outbox records occur in the same authoritative database transaction.

**DG-DUR-022 — Honest delivery semantics.** The outbox is at least once. Exactly-once processing exists only where a destination performs durable deduplication by outbox_id or a receiver inbox has a unique constraint on that ID.

#### 9.2.4 Waits, storage, and recovery

**DG-DUR-023 — Durable wait ownership.** A wait is an immutable logical identity plus a versioned state machine. Signal, timeout, cancellation, and effect completion race by CAS; exactly one terminal satisfaction wins.

**DG-DUR-024 — No stack serialization.** Interrupt resume reconstructs from checkpoint, accepted task results, durable activity/effect results, and a call-order cursor. It never depends on serializing a live coroutine, context variable, file descriptor, socket, or process-local object.

**DG-DUR-025 — Tenant isolation.** Identifiers, content digests, encryption, database access, object keys, leases, caches, and dedupe constraints are tenant-scoped. Cross-tenant content substitution MUST fail authentication.

**DG-DUR-026 — Blob safety.** A database row may reference a blob only after the blob has reached required durability and passed integrity verification. Garbage collection never treats a mutable refcount as its sole source of truth.

**DG-DUR-027 — Recoverable deletion.** Runtime deletion first creates a tombstone and observes retention, legal hold, and PITR windows. Production roles cannot hard-delete live history directly.

**DG-DUR-028 — Proof-preserving compaction.** Compaction may change physical history retention, never logical state or surviving checkpoint identity. It emits an authenticated range proof and retains every live root.

**DG-DUR-029 — New incarnation after restore.** A restored store cannot become writable until a new incarnation and activation epoch have been minted by an authority outside the restored backup and the old site has been externally fenced.

**DG-DUR-030 — Stable effects across restore.** Restore does not remint logical run, task, effect, signal, or outbox identities. A new store incarnation fences writers; it does not make already-issued external operations look new.

**DG-DUR-031 — Database time for ownership.** Lease acquisition, expiry, takeover, and claim staleness use authoritative database or consensus-service time, never a worker wall clock.

**DG-DUR-032 — No network inside commit.** No database transaction may remain open across an LLM, HTTP, subprocess, queue, object upload, KMS network operation, or other unbounded call.

**DG-DUR-033 — Auditable authority.** Every consequential mutation records the authenticated principal, delegated capability, warrant or approval, policy version, request ID, causation, trace, and incarnation. Audit creation is part of the mutation transaction.

**DG-DUR-034 — Semantic task, task activation, and attempt.** SemanticTaskId names stable operation work. TaskId names one run/graph-revision/superstep/activation-specific execution of that work. AttemptId names one store-incarnation-bound try of that TaskId. These IDs MUST be separate, and result reuse verifies both semantic and execution compatibility.

**DG-DUR-035 — One operation owner.** Exactly one run may own live progression and external-effect authority for an operation. Same-operation repair or migration transfers ownership by operation-level fenced CAS; it never merely starts a second effect-capable run.

---

### 9.3 Identity model and canonical encoding

#### 9.3.1 Stable identifiers

An **operation** is the durable semantic undertaking born from one accepted origin intent. It may span scheduler processes, runs, replans, repair branches, graph-package revisions, schema migrations, regional restores, and many task attempts. The operation registry mints exactly one operation_id, task_namespace_id, and effect_namespace_id at origin. Those three values are immutable for the life of the same operation.

The following identities have different lifetimes and MUST NOT be conflated:

| Identity | Retry/replan | Resume | Restore | Same-operation repair/migration | Exploratory fork |
|---|---:|---:|---:|---:|---:|
| store_lineage_id | same | same | same | same | same store |
| active_incarnation_id | same until activation changes | same | new | current store | current store |
| operation_id | same | same | same | same | new |
| task_namespace_id | same | same | same | same | new |
| effect_namespace_id | same | same | same | same | new |
| thread_id | same by policy | same | same | same or mapped | new by default |
| run_id | same | same | same | may be new | new |
| branch_id | same | same | same | may be new | new |
| checkpoint_id | same | same | same | source referenced; new anchor | source referenced; new anchor |
| semantic_task_id | same | same | same | same after stable-path mapping | new |
| task_id | same for the same activation | same if activation is unfinished | same if already recorded | new for a new run/graph/step/activation | new |
| attempt_id | new | new only for work that runs | new only for work that runs | new | new |
| effect_id | same | same | same | same after stable-path mapping | new; dispatch disabled initially |
| origin_idempotency_key | same origin | same | same | same | new origin |
| wait_id | same logical wait | same | same | same after mapping where supported | new |
| signal_id | same received signal | same | same | historical signals retained | not copied |
| outbox_id | same event | same | same | same historical event | new |

Opaque IDs SHALL be 128 bits or stronger. Semantic IDs SHALL use the public, canonical, domain-separated encoding below. Authentication keys MUST NOT participate in semantic identity.

#### 9.3.2 Canonicalization

Semantic objects MUST serialize through one registered canonical codec. v1.1 requires one of:

1. canonical CBOR with deterministic map ordering and prohibited indefinite lengths; or
2. RFC 8785 JSON for values that can be represented without loss.

Pick one for the production profile and pin codec_id in every frame. Floats, NaN, infinity, decimal precision, timezone normalization, byte strings, sets, tuples, and custom classes MUST have explicit schema rules. Python pickle, repr, default=str, process hash values, and unordered container iteration are prohibited from semantic encoding.

Canonical digest context separation is REQUIRED. LP is a fixed-width unsigned length followed by that many bytes; every value below is canonical bytes, never ambiguous string concatenation:

~~~text
H_id(kind, tenant_id, fields...) =
  SHA-256(
    LP(UTF8("dharmagraph.semantic-id.v1.1")) ||
    LP(UTF8(kind)) ||
    LP(canonical(tenant_id)) ||
    concat(LP(canonical(field)) for field in fields)
  )

H_content(kind, tenant_id, canonical_bytes) =
  SHA-256(
    LP(UTF8("dharmagraph.semantic-content.v1.1")) ||
    LP(UTF8(kind)) ||
    LP(canonical(tenant_id)) ||
    LP(canonical_bytes)
  )
~~~

Tenant identity is therefore inside the hashed bytes, providing tenant-separated IDs without a rotating secret. HMACs, digital signatures, AEAD tags, and KMS keys authenticate or encrypt records separately. Rotating any authentication or encryption key MUST NOT change operation_id, task_id, effect_id, checkpoint_id, blob_id, or their semantic content digests. Algorithm versions are pinned in manifests. Changing canonical semantic encoding requires an explicit compatibility migration, but that migration still preserves the registered operation and namespace identities.

#### 9.3.3 Logical identity derivation

~~~text
plan_id =
  H_id("plan", tenant_id,
    run_id, input_checkpoint_id, absolute_superstep,
    graph_package_digest, canonical_ready_set_digest, budget_snapshot_digest)

semantic_task_id =
  H_id("semantic-task", tenant_id,
    operation_id, task_namespace_id, stable_task_path)

task_id =
  H_id("task", tenant_id,
    run_id, graph_revision_digest, absolute_superstep,
    activation_id, semantic_task_id)

attempt_id =
  H_id("attempt", tenant_id,
    active_incarnation_id, task_id, attempt_number)

effect_id =
  H_id("effect", tenant_id,
    operation_id, effect_namespace_id, stable_task_path, effect_slot)

wait_id =
  H_id("wait", tenant_id,
    operation_id, task_namespace_id, stable_task_path, wait_slot,
    wait_generation)

outbox_id =
  H_id("outbox", tenant_id,
    causation_kind, causation_id, destination, event_kind,
    canonical_payload_digest)
~~~

The SemanticTaskId formula is exactly H(tenant, operation_id, task_namespace_id, stable_task_path). TaskId is deliberately run/graph-revision/superstep/activation-specific; activation_id canonically distinguishes PULL/PUSH activations and stable fan-out items within the step. AttemptId is deliberately bound to active_incarnation_id plus TaskId and monotonic attempt_number; a restored incarnation can never accidentally reuse an old worker-attempt identity. The EffectId formula is exactly H(tenant, operation_id, effect_namespace_id, stable_task_path, effect_slot). run_id, plan_id, TaskId, AttemptId, retry count, graph/package revision, node-code digest, request bytes, provider, target, payload, worker, fence, time, and store incarnation MUST NOT enter SemanticTaskId or EffectId.

activation_id is derived canonically from activation kind, declared activation path, stable fan-out/domain key, and the triggering channel/message identities. It MUST NOT use dispatch order, completion order, worker identity, or list position unless that position is itself a declared semantic key. Reconstructing the same ready activation from one checkpoint MUST reproduce the same activation_id and TaskId.

stable_task_path is a canonical sequence of declared stable path components, not an incidental stack trace or mutable node display name. Fan-out adds a domain key that is stable for the logical item; list position may be used only when list ordering is itself a pinned semantic contract. A repair or migration that moves or renames work supplies an authenticated StablePathMapping from old paths to new implementation locations while retaining the canonical semantic path used for identity.

effect_slot is a developer-declared stable symbol within stable_task_path. A loop or fan-out that intentionally creates multiple semantic effects includes its stable item/iteration identity in the slot. Call ordinal may detect replay drift but MUST NOT define effect identity. A genuinely new external operation requires a new effect_slot. It MUST NOT be manufactured by adding retry_count, graph revision, request digest, or a “semantic revision” to an old slot.

`wait_generation` is a coordinator-derived, nonnegative stable semantic
generation within the wait slot, bound to the activation/loop/join generation
that created it. Retry and recovery preserve it; re-entering the same wait slot
after a prior terminal wait increments or otherwise deterministically derives a
different generation. Callers and node code cannot choose it.

Request, operation kind, provider, provider account, target, payload, consequence class, and saga placement are immutable **semantic claims under effect_id**, not inputs that allow changed behavior to mint a convenient new identity. Re-registering one effect_id with any different semantic claim is EFFECT_DETERMINISM_CONFLICT and quarantines the operation. Warrant, approval, and policy decisions are separate versioned authorization facts: they may expire, revoke, or refresh without changing EffectId or its semantic claims, but dispatch always requires a currently valid decision.

Same-operation repair and migration preserve operation_id, task_namespace_id, effect_namespace_id, and all mapped SemanticTaskIds/EffectIds. Execution-specific TaskIds may change. An exploratory fork mints a new operation and fresh namespaces; all external effects are disabled at fork creation and require a separate, explicit activation decision.

#### 9.3.4 Stable path mapping

Graph implementation paths may change while semantic identity must not. A same-operation repair or migration therefore supplies:

~~~text
StablePathMapping {
  mapping_id
  tenant_id
  operation_id
  task_namespace_id
  effect_namespace_id
  source_graph_package_digest
  target_graph_package_digest
  entries: sorted [
    {
      source_stable_task_path
      target_implementation_path
      preserved_identity_path
      source_semantic_task_id
      recomputed_target_semantic_task_id
      effect_slots: sorted [
        {
          source_effect_slot
          target_declared_effect_slot
          source_effect_id
          recomputed_target_effect_id
        }
      ]
    }
  ]
  new_identity_paths[]
  retired_identity_paths[]
  approvals[]
  mapping_digest
  signature
}
~~~

For preserved work, preserved_identity_path equals the canonical source stable_task_path even when target_implementation_path changes; recomputed SemanticTaskIds and EffectIds MUST byte-equal their source identities. TaskIds normally change when repair/migration changes run, graph revision, superstep, or activation and are intentionally excluded from this equality. An effect slot may be mapped only as an alias to the original semantic slot and MUST recompute the original EffectId. New behavior uses a genuinely new stable path or slot and is listed explicitly. A mapping cannot merge two existing semantic identities, split one completed effect into multiple aliases, map across tenants/operations/namespaces, or relabel an old effect to carry changed claims. Such mappings fail before migration or repair activation.

---

### 9.4 Checkpoint frame and record integrity

#### 9.4.1 Two-layer representation

A checkpoint has:

1. **CheckpointFrameCore** — deterministic semantic state.
2. **CheckpointEnvelope** — identity and cryptographic authentication.
3. **CheckpointRecord** — authoritative database commit metadata.

Checkpoint ID is derived from the frame core, avoiding identity/content divergence:

~~~text
frame_digest  = H_content("checkpoint-frame", tenant_id, canonical(FrameCore))
checkpoint_id = "ckp_" || base32(frame_digest)
integrity_tag = HMAC-SHA-256(
  K_checkpoint_auth[tenant, auth_key_version],
  canonical([
    "dharmagraph/checkpoint-envelope/v1.1",
    store_lineage_id, tenant_id, checkpoint_id, frame_digest
  ]))

record_integrity_tag = HMAC-SHA-256(
  K_checkpoint_record[tenant, record_auth_key_version],
  canonical([
    "dharmagraph/checkpoint-record/v1.1",
    all_immutable_CheckpointRecord_fields_except_record_integrity_tag
  ]))
~~~

Checkpoint ID and integrity_tag are envelope fields and are excluded from FrameCore, preventing a circular digest.

#### 9.4.2 Normative frame schema

~~~text
CheckpointFrameCore {
  format_version:                 "dharmagraph.checkpoint.v1.1"
  tenant_id:                      TenantId
  store_lineage_id:               StoreLineageId
  origin_incarnation_id:          IncarnationId

  graph_id:                       GraphId
  graph_package_digest:           Digest
  runtime_semantics_version:      String
  state_schema_id:                String
  state_schema_digest:            Digest
  reducer_manifest_digest:        Digest
  router_manifest_digest:         Digest
  codec_manifest_digest:          Digest

  thread_id:                      ThreadId
  run_id:                         RunId
  branch_id:                      BranchId
  operation_id:                   OperationId
  task_namespace_id:              NamespaceId
  effect_namespace_id:            NamespaceId
  stable_path_mapping_digest:     Digest | null
  commit_sequence:                UInt64
  absolute_superstep:             UInt64
  parent_checkpoint_id:           CheckpointId | null
  parent_frame_digest:             Digest | null
  lineage_source_checkpoint_id:   CheckpointId | null

  logical_run_status:             RunStatus
  state_manifest_blob_id:         BlobId
  state_root_digest:              Digest
  channel_versions_blob_id:       BlobId
  versions_seen_blob_id:          BlobId
  next_frontier_blob_id:          BlobId
  durable_call_cursors_blob_id:   BlobId
  budget_snapshot_blob_id:        BlobId

  accepted_bundle_id:             BundleId | null
  accepted_bundle_digest:         Digest | null
  open_wait_set_root:              Digest
  unresolved_effect_set_root:     Digest
  child_join_set_root:             Digest

  semantic_metadata:              CanonicalMap
}

CheckpointEnvelope {
  checkpoint_id:                  CheckpointId
  frame_core:                     CheckpointFrameCore
  frame_digest:                   Digest
  integrity_algorithm:            "HMAC-SHA-256"
  auth_key_version:               String
  integrity_tag:                  Bytes
}

CheckpointRecord {
  tenant_id:                      TenantId
  run_id:                         RunId
  checkpoint_id:                  CheckpointId
  commit_id:                      CommitId
  frame_digest:                   Digest
  integrity_tag:                  Bytes
  auth_key_version:               String
  parent_checkpoint_id:           CheckpointId | null
  commit_sequence:                UInt64
  absolute_superstep:             UInt64
  committed_head_version:         UInt64
  committed_by_principal:         PrincipalId
  committed_by_lease_fence:       UInt64
  committed_by_operation_owner_fence: UInt64
  committed_in_incarnation:       IncarnationId
  committed_at_database_time:     Timestamp
  audit_event_id:                 AuditEventId
  record_auth_key_version:        String
  record_integrity_tag:           Bytes
}
~~~

Wall-clock committed time is record metadata, not part of deterministic
semantic state, but it and every authority/provenance field in the immutable
record are authenticated by `record_integrity_tag`. Record authentication keys
rotate independently of semantic IDs and remain available for the full
retention horizon.

#### 9.4.3 State manifest

Every checkpoint MUST be self-contained at the logical level. Its state manifest lists every channel required to resume, although unchanged channel payload blobs may be structurally shared:

~~~text
StateManifest {
  format_version
  tenant_id
  checkpoint_frame_digest
  entries: sorted [
    {
      channel_name
      channel_type_id
      channel_schema_digest
      reducer_id
      reducer_version
      logical_version
      value_blob_id
      value_digest
      encoded_length
    }
  ]
  manifest_root
}
~~~

Resume MUST NOT need process memory or an unbounded delta chain. Implementations MAY use deltas for transport or cache, but a bounded reconstruction path to an authenticated full manifest is REQUIRED.

#### 9.4.4 Verification algorithm

Before returning a ResumePackage, the Durability Service SHALL:

1. resolve the checkpoint through tenant-scoped authoritative records;
2. verify store_lineage_id and allowed origin incarnation;
3. load the named auth key version from KMS;
4. canonicalize FrameCore and recompute frame_digest;
5. verify checkpoint_id derives from frame_digest;
6. verify integrity_tag in constant time;
7. verify `record_integrity_tag`, then verify record fields equal their envelope
   projections and authoritative commit/audit lineage;
8. verify parent ID/digest or a valid compaction certificate;
9. verify graph, schema, reducer, router, and codec package digests;
10. fetch every required blob and verify tenant, length, AEAD tag, and content digest;
11. reconstruct the full StateManifest and state_root_digest;
12. verify channel versions, versions_seen, frontier, durable call cursors, and budget schemas;
13. verify wait, unresolved-effect, and child-join set roots against authoritative rows;
14. verify the selected checkpoint is reachable from the requested branch or has an explicit historical-fork authorization.

Any mismatch returns CHECKPOINT_INTEGRITY_FAILURE, marks the run QUARANTINED in a separately authenticated control transaction, emits a high-severity audit/outbox event, and prevents execution.

#### 9.4.5 Rollback detection

An attacker restoring an internally consistent old database must not silently
present it as current. Every head transaction SHALL insert an immutable,
signed `HeadAnchorOutbox` record atomically with the head. Exporting that anchor
to the external monotonic witness occurs after commit and is idempotent:

~~~text
HeadAnchor {
  store_lineage_id
  active_incarnation_id
  run_id
  head_version
  checkpoint_id
  frame_digest
  database_commit_lsn_or_sequence
}

HeadAnchorOutbox {
  anchor_id
  anchor: HeadAnchor
  anchor_signature
  status: PENDING | CLAIMED | WITNESSED
  claim_fence
  external_witness_sequence | null
  external_witness_receipt | null
}
~~~

After an ordinary process crash with surviving canonical storage, a locally
committed head plus its anchor-outbox row is valid and the exporter resumes.
For media-loss RPO 0, a profile MUST synchronously obtain the external witness
receipt before acknowledging the head; a profile using asynchronous export
MUST declare the resulting DR RPO and MUST NOT claim media-loss RPO 0. A head
whose local anchor exists but whose external acknowledgement is not yet known
may continue pure computation under the surviving canonical store, but disaster
activation and consequential egress remain disabled until the anchor is
exported or an operator follows the signed ambiguity procedure.

Production activation compares restored heads with the last available external
witness and the durable local anchor-outbox chain. A rollback outside declared
PITR is a security incident requiring operator authorization, not automatic
resume.

---

### 9.5 Authoritative persistence service

#### 9.5.1 Required components

The production authority consists of:

- a strongly consistent transactional metadata database;
- an immutable, versioned, encrypted object store;
- a KMS/HSM for checkpoint authentication, envelope encryption, authority signing, and audit signing keys;
- an activation authority outside the restored database;
- an effect gateway or provider adapters enforcing activation epoch, warrant, and idempotency;
- an append-only audit sink replicated outside the primary failure domain.

PostgreSQL is an acceptable implementation. SQLite and per-thread JSON are not acceptable for distributed production authority.

The metadata database is authoritative for heads, leases, accepted results, waits, effects, outbox state, blob references, tombstones, and restore state. The object store is authoritative only for immutable bytes named by authenticated metadata. Read replicas and search indexes MUST NOT make scheduling, lease, effect, wait, or deletion decisions.

#### 9.5.2 Minimum relational model

The physical schema may vary, but it MUST enforce equivalent keys and constraints:

~~~text
store_control(
  store_lineage_id PK,
  active_incarnation_id,
  activation_epoch BIGINT,
  mode ENUM(READ_ONLY, WRITABLE, QUARANTINED),
  control_version BIGINT,
  activated_at,
  activation_receipt_id
)

operations(
  tenant_id,
  operation_id,
  task_namespace_id,
  effect_namespace_id,
  origin_idempotency_key,
  origin_intent_digest,
  owner_run_id,
  owner_fence BIGINT,
  owner_version BIGINT,
  external_effects_mode ENUM(DISABLED, ENABLED),
  status ENUM(ACTIVE, DRAINING, TERMINAL, SUPERSEDED),
  operation_version,
  created_at,
  PRIMARY KEY(tenant_id, operation_id),
  UNIQUE(tenant_id, origin_idempotency_key)
)

operation_owner_history(
  tenant_id,
  operation_id,
  transfer_id,
  predecessor_run_id,
  successor_run_id,
  predecessor_owner_fence,
  successor_owner_fence,
  reason,
  authority_digest,
  transferred_at,
  PRIMARY KEY(tenant_id, operation_id, transfer_id)
)

graph_runs(
  tenant_id,
  run_id,
  operation_id,
  task_namespace_id,
  effect_namespace_id,
  thread_id,
  branch_id,
  graph_id,
  graph_package_digest,
  stable_path_mapping_digest,
  external_effects_mode ENUM(DISABLED, ENABLED),
  status,
  head_checkpoint_id,
  head_frame_digest,
  head_version BIGINT,
  absolute_superstep BIGINT,
  run_policy_digest,
  active_incarnation_id,
  created_at,
  updated_at,
  PRIMARY KEY(tenant_id, run_id),
  UNIQUE(tenant_id, thread_id, branch_id)
)

run_leases(
  tenant_id,
  run_id,
  holder_id,
  authority_kind ENUM(EXECUTION, MAINTENANCE),
  fence_token BIGINT,
  lease_version BIGINT,
  acquired_at,
  renewed_at,
  expires_at,
  active_incarnation_id,
  PRIMARY KEY(tenant_id, run_id)
)

checkpoint_records(
  tenant_id,
  run_id,
  checkpoint_id,
  commit_id,
  parent_checkpoint_id,
  frame_digest,
  auth_key_version,
  integrity_tag,
  commit_sequence,
  absolute_superstep,
  committed_head_version,
  committed_by_principal,
  committed_by_fence,
  committed_by_operation_owner_fence,
  committed_in_incarnation,
  committed_at,
  audit_event_id,
  record_auth_key_version,
  record_integrity_tag,
  PRIMARY KEY(tenant_id, checkpoint_id),
  UNIQUE(tenant_id, run_id, commit_id),
  UNIQUE(tenant_id, run_id, commit_sequence)
)

blob_records(
  tenant_id,
  blob_id,
  object_version,
  ciphertext_digest,
  plaintext_length,
  encoded_length,
  codec_id,
  encryption_key_version,
  state,
  staged_at,
  verified_at,
  tombstoned_at,
  delete_after,
  legal_hold_count,
  PRIMARY KEY(tenant_id, blob_id)
)

blob_references(
  tenant_id,
  owner_kind,
  owner_id,
  blob_id,
  created_at,
  PRIMARY KEY(tenant_id, owner_kind, owner_id, blob_id)
)
~~~

Separate tables defined later cover task plans, attempts, results, bundles, effects, waits, signals, outbox, inbox, sagas, compaction, and restore.

The runtime database role SHALL have no UPDATE or DELETE privilege on immutable semantic rows. Mutable state machines live in separate rows with version columns and constrained transition procedures.

#### 9.5.3 Authority envelope

Every mutating service request includes:

~~~text
AuthorityEnvelope {
  tenant_id
  principal_id
  service_identity
  capability_set
  delegated_from
  warrant_id
  approval_id
  policy_version
  policy_decision_digest
  trace_id
  causation_id
  request_id
  active_incarnation_id
  activation_epoch
  issued_at
  expires_at
  signature
}
~~~

The service verifies authentication, tenant scope, capability, warrant scope, expiry, revocation, policy digest, activation epoch, and request replay before mutation. Consequential effect authority is checked both when the intent is registered and immediately before dispatch.

Database row-level security, service roles, and object-prefix policies SHALL enforce tenant scope independently of application filters.

#### 9.5.4 Lease protocol

The API is:

~~~text
AcquireRunLease(run_id, holder_id, requested_ttl, authority)
  -> RunLeaseToken

RenewRunLease(run_lease_token, requested_ttl, authority)
  -> RunLeaseToken

ReleaseRunLease(run_lease_token, authority)
  -> Released

AcquireMaintenanceLease(run_id, holder_id, requested_ttl, expected_head,
                        authority) -> MaintenanceLeaseToken

RenewMaintenanceLease(maintenance_lease_token, requested_ttl, authority)
  -> MaintenanceLeaseToken

ReleaseMaintenanceLease(maintenance_lease_token, authority) -> Released

RunLeaseToken {
  tenant_id
  run_id
  holder_id
  fence_token
  lease_version
  active_incarnation_id
  activation_epoch
  expires_at_database_time
  signature
}

MaintenanceLeaseToken {
  tenant_id
  run_id
  holder_id
  fence_token
  lease_version
  expected_head_checkpoint_id
  active_incarnation_id
  activation_epoch
  expires_at_database_time
  signature
}
~~~

Execution and maintenance acquisition use the same `run_leases` authority row;
there can never be one lease of each kind. Acquisition is a serializable
transaction that:

1. validates active writable incarnation and authority;
2. row-locks the run lease;
3. permits acquisition only if absent, expired by database time, or explicitly released;
4. increments fence_token on every new acquisition, including reacquisition by the same holder;
5. records a lease audit event;
6. returns a signed token.

An execution lease permits planning/dispatch/commit and forbids history
maintenance. A maintenance lease permits only the named migration/compaction
operation against its expected head and forbids task/effect/wait dispatch. Both
renew through the same row and fence sequence. Takeover, cancellation, resume,
and ordinary execution acquisition fail while a live maintenance lease exists;
maintenance acquisition fails while a live execution lease exists.

Renewal increments lease_version but does not reduce expiry or change fence_token. It succeeds only for the exact holder, fence, incarnation, activation epoch, and current lease version. Release never decrements or reuses a fence.

All mutation procedures compare token expiry to database time inside their transaction. A worker may continue pure computation after expiry, but it cannot commit, accept a task result, dispatch an effect, satisfy a wait, or publish an outbox message with the stale token.

#### 9.5.5 Operation ownership

Run leases prevent two schedulers from owning one run. They do not prevent a source run and a same-operation repair run from both dispatching the same operation. The operation registry therefore carries an independent monotonically fenced owner:

~~~text
OperationOwnerToken {
  tenant_id
  operation_id
  owner_run_id
  owner_fence
  owner_version
  owner_state: ACTIVE | DRAINING | TERMINAL | SUPERSEDED
  active_incarnation_id
  activation_epoch
  external_effects_mode
  signature
}

TransferOperationOwner(
  operation_id,
  predecessor_run_id,
  successor_run_id,
  expected_owner_fence,
  transfer_id,
  authority
) -> OperationOwnerToken
~~~

Initial operation creation sets its origin run as owner. Every state-head commit, TaskPlan creation, durable-call suspension, effect registration/claim/dispatch/completion, wait resolution that resumes work, and operation-scoped outbox publication verifies the current owner token. The transaction also verifies the run's own lease where applicable.

TransferOperationOwner is a serializable CAS transaction that:

1. verifies same tenant, operation, namespaces, stable-path mapping, authority, and active incarnation;
2. locks the operation and predecessor/successor runs;
3. requires predecessor_run_id and expected_owner_fence to equal the current owner;
4. requires the successor to be a verified SAME_OPERATION_REPAIR or migration anchor;
5. increments owner_fence without reuse and sets successor_run_id;
6. marks the predecessor's `OperationOwner` control projection `SUPERSEDED`
   and revokes its effect/wait progression authority; this is not a new
   `RunStatus` and does not rewrite the source run's terminal status;
7. records OperationOwnerHistory, audit, and outbox rows;
8. commits atomically.

Lost responses retry transfer_id and return the same token. The predecessor may remain readable and its in-flight provider response may enter reconciliation evidence, but its stale owner fence cannot dispatch, accept, or overwrite anything. Exploratory forks create new operations and do not use ownership transfer.

#### 9.5.6 Typed errors

Durability APIs return typed errors at the boundary:

- AUTHORITY_DENIED
- ACTIVATION_EPOCH_MISMATCH
- STORE_READ_ONLY
- INCARNATION_FENCED
- LEASE_BUSY
- LEASE_EXPIRED
- FENCE_LOST
- OPERATION_OWNER_CONFLICT
- OPERATION_OWNER_FENCED
- HEAD_CONFLICT
- REQUEST_REPLAY_CONFLICT
- CHECKPOINT_INTEGRITY_FAILURE
- GRAPH_PACKAGE_UNAVAILABLE
- SCHEMA_INCOMPATIBLE
- MIGRATION_REQUIRED
- TASK_PLAN_CONFLICT
- STALE_ATTEMPT
- EFFECT_IN_FLIGHT
- EFFECT_UNKNOWN
- EFFECT_DETERMINISM_CONFLICT
- WAIT_ALREADY_RESOLVED
- BLOB_NOT_DURABLE
- LEGAL_HOLD
- RESTORE_NOT_ACTIVATED

None may be converted to a generic empty result or silently ignored.

---

### 9.6 Superstep commit protocol

#### 9.6.1 Precondition

Before commit, all referenced blobs are uploaded under immutable tenant-scoped object keys using conditional create. The uploader verifies:

- returned object version;
- byte length;
- ciphertext digest;
- AEAD authentication;
- required replica/durability policy;
- a read-after-write verification where the store does not guarantee strong read-after-write.

Blob upload performs no graph mutation. A crash at this point leaves a staged orphan.

#### 9.6.2 Commit request

~~~text
CommitSuperstepRequest {
  authority
  run_lease_token
  operation_owner_token
  request_id
  commit_id
  run_id
  expected_head_checkpoint_id
  expected_head_frame_digest
  expected_head_version
  expected_absolute_superstep
  plan_id
  bundle_id
  bundle_digest
  proposed_checkpoint_envelope
  referenced_blob_proofs[]
  run_status_after_commit
}
~~~

commit_id is deterministic:

~~~text
commit_id = H_id("commit", tenant_id,
  run_id, expected_head_checkpoint_id, plan_id,
  bundle_digest, proposed_frame_digest)
~~~

Retrying the exact commit after an acknowledgement loss returns the original CommitResult. Reusing commit_id with different bytes is REQUEST_REPLAY_CONFLICT and a security alert.

#### 9.6.3 Trusted pre-transaction validation

The Durability Service, not an untrusted worker, SHALL:

1. verify the lease token signature and authority;
2. load and verify the expected checkpoint;
3. verify plan_id and exact ready task set;
4. verify every accepted task result and its attempt fence;
5. ensure one result per task slot and no extra task;
6. validate all deltas against channel schemas;
7. apply registered reducers in canonical order;
8. validate routes, commands, waits, effect declarations, and budgets;
9. recompute next frontier, channel versions, versions_seen, state manifest, roots, and checkpoint frame;
10. require byte equality with the proposed envelope;
11. verify referenced blobs are durable and immutable.

Validation is pure and bounded. It performs no network effect and holds no database transaction.

#### 9.6.4 Authoritative transaction

At SERIALIZABLE isolation, or an equivalent row-lock plus CAS discipline, CommitSuperstep executes:

1. look up commit_id; if the same digest already committed, return it idempotently;
2. lock store_control, graph_runs, and run_leases rows;
3. lock the operation row and verify operation owner run/fence/version plus external-effects/control mode;
4. verify WRITABLE mode, active incarnation, activation epoch, principal, lease holder, fence, lease version, and non-expiry using database time;
5. verify graph_runs head checkpoint, frame digest, head version, and superstep equal the request;
6. verify run status permits a commit;
7. insert the immutable checkpoint record;
8. insert checkpoint blob references;
9. insert or bind the accepted StepBundle;
10. atomically register newly declared waits, effect intents, saga steps, child joins, and their blob references;
11. insert all resulting event/effect outbox and audit records plus the signed
    `HeadAnchorOutbox` for the proposed head;
12. transition task plan and accepted results to COMMITTED;
13. update graph_runs head checkpoint, frame digest, head_version + 1, superstep, status, and active incarnation with a SQL CAS predicate;
14. clear only pending plan records proven subsumed by this bundle;
15. commit.

If any insertion, audit row, outbox row, wait, effect intent, blob reference, or CAS fails, the entire transaction rolls back. The in-memory state is never called committed before this transaction returns success.

#### 9.6.5 Post-commit

After commit:

- the scheduler replaces its local view with CommitResult, not its proposal;
- the transaction's durable `HeadAnchorOutbox` row is exported idempotently;
  profiles claiming media-loss RPO 0 wait for the external witness receipt
  before acknowledging the commit, while other profiles advertise their DR RPO;
- outbox publishers and effect workers may claim newly visible work;
- staged blobs become logically LIVE by reachability; a state field may be updated asynchronously, but reachability from committed rows is authoritative.

Loss of the client response causes an exact commit_id retry, never reconstruction from memory.

---

### 9.7 Task plans, attempts, results, and bundles

#### 9.7.1 Schema

~~~text
TaskPlan {
  tenant_id
  plan_id
  run_id
  operation_id
  task_namespace_id
  effect_namespace_id
  input_checkpoint_id
  input_frame_digest
  absolute_superstep
  graph_package_digest
  reducer_manifest_digest
  budget_snapshot_digest
  canonical_ready_set_digest
  status: OPEN | WAITING | READY_TO_COMMIT | COMMITTED | ABORTED
  core_step_status: PLANNED | DISPATCHING | COLLECTING | RETRYING |
                    READY_TO_COMMIT | COMMITTED | CANCELLED | FAILED |
                    QUARANTINED
  plan_version
}

TaskSlot {
  tenant_id
  plan_id
  semantic_task_id
  task_id
  operation_id
  task_namespace_id
  stable_task_path
  graph_revision_digest
  absolute_superstep
  activation_id
  node_id
  task_kind: PULL | PUSH | CONTINUATION
  stable_fanout_key
  input_slice_digest
  node_code_digest
  status: READY | LEASED | ORPHANED | SUCCEEDED | WAITING |
          FAILED_RETRYABLE | FAILED_FINAL | CANCELLED
  core_task_status: PLANNED | LEASED | RUNNING | SUCCEEDED_STAGED |
                    ORPHANED | RETRYABLE | FAILED | CANCELLED
  current_attempt_fence
  accepted_result_id
  slot_version
  UNIQUE(tenant_id, task_id)
  UNIQUE(tenant_id, plan_id, task_id)
}

TaskAttempt {
  tenant_id
  attempt_id
  active_incarnation_id
  plan_id
  semantic_task_id
  task_id
  attempt_number
  worker_id
  attempt_fence
  worker_image_digest
  runtime_semantics_version
  started_at
  lease_expires_at
  heartbeat_at
  finished_at
  status: RUNNING | SUCCEEDED | FAILED | TIMED_OUT | CANCELLED |
          ABANDONED | STALE
  error_code
  error_blob_id
  UNIQUE(tenant_id, active_incarnation_id, task_id, attempt_number)
}

TaskResult {
  tenant_id
  result_id
  plan_id
  semantic_task_id
  task_id
  operation_id
  task_namespace_id
  stable_task_path
  attempt_id
  input_checkpoint_id
  input_frame_digest
  node_code_digest
  worker_image_digest
  delta_blob_id
  delta_digest
  commands_blob_id
  routes_blob_id
  effect_declarations_blob_id
  wait_declarations_blob_id
  child_declarations_blob_id
  durable_call_cursor_digest
  result_digest
  accepted_at
  committed_checkpoint_id
}

StepBundle {
  tenant_id
  bundle_id
  operation_id
  plan_id
  input_checkpoint_id
  sorted_task_result_ids
  sorted_task_result_digests
  canonical_merge_manifest_blob_id
  resulting_state_root
  resulting_frontier_root
  declared_effect_set_root
  declared_wait_set_root
  bundle_digest
  status: PROPOSED | VALIDATED | COMMITTED | REJECTED
}
~~~

TaskResult is immutable. Acceptance and commit linkage may live in separate relation rows if immutable-table privileges prohibit those mutable projections.

The §8.9 machines are the public/canonical lifecycle. The §9 storage statuses
are refinements and SHALL carry the following total projection in the same row:

| Storage record/status | Allowed canonical projection |
|---|---|
| TaskPlan `OPEN` | `PLANNED`, `DISPATCHING`, `COLLECTING`, or `RETRYING` |
| TaskPlan `WAITING` | `COLLECTING` while durable calls/waits are outstanding |
| TaskPlan `READY_TO_COMMIT` | `READY_TO_COMMIT` |
| TaskPlan `COMMITTED` | `COMMITTED` |
| TaskPlan `ABORTED` | `CANCELLED`, `FAILED`, or `QUARANTINED`, selected by its immutable reason |
| TaskSlot `READY` | `PLANNED` before first claim, otherwise `RETRYABLE` |
| TaskSlot `LEASED` | `LEASED` before start acknowledgement, otherwise `RUNNING` while the current attempt is live |
| TaskSlot `ORPHANED` | `ORPHANED`; the prior attempt is expired/abandoned and cannot publish a canonical result |
| TaskSlot `SUCCEEDED` | `SUCCEEDED_STAGED` |
| TaskSlot `WAITING` | `RUNNING` with an immutable durable-call/wait suspension reference |
| TaskSlot `FAILED_RETRYABLE` | `RETRYABLE` |
| TaskSlot `FAILED_FINAL` | `FAILED` |
| TaskSlot `CANCELLED` | `CANCELLED` |

Every storage transition atomically updates its canonical projection and is
legal only if both the storage transition and the corresponding §8.9
transition are allowed. Recovery recomputes and verifies this projection;
there is no adapter-specific lifecycle interpretation.

#### 9.7.2 Attempt leasing

ClaimTask first recomputes SemanticTaskId and the run/graph/step/activation-specific TaskId and rejects either mismatch. It atomically increments current_attempt_fence, allocates an attempt_number monotonically for that TaskId within the active incarnation, derives AttemptId from (tenant, active_incarnation_id, TaskId, attempt_number), and creates TaskAttempt. CompleteTaskAttempt succeeds only when:

- the plan is still OPEN or WAITING;
- its input checkpoint remains the run head expected by the plan;
- task identity and code/package digests match;
- task execution identity and active incarnation match;
- attempt holder and fence are current;
- attempt lease has not expired by database time;
- no result was already accepted.

A task-attempt lease expiring CASes its slot to storage/canonical `ORPHANED`;
the §8.9 transition then moves it to `RETRYABLE`, `LEASED`, `FAILED`, or
`CANCELLED` under policy. A stale result is marked STALE and cannot win merely
because it arrived first at an API process.

#### 9.7.3 Result reuse after crash

On scheduler takeover, RehydratePlan returns:

- the exact input checkpoint and plan;
- all accepted results;
- currently live attempts;
- expired attempts eligible for takeover;
- open waits/effects for durable calls;
- missing task slots.

Accepted results are reused without node re-execution when DG-DUR-010 matches. Missing or stale slots get new attempts. If any plan/input/code semantic digest differs, the old plan is ABORTED and a new plan is derived; old results remain evidence but are not applied. Same-operation replan preserves SemanticTaskId for the same stable path. It preserves TaskId only if run, graph revision, superstep, and activation_id are unchanged; otherwise it derives a new TaskId and may reuse the old result only through explicit exact-compatibility validation keyed by SemanticTaskId.

This gives precise node-7 recovery behavior: if checkpoint 6 is committed, nodes represented through checkpoint 6 do not run again. If node 7 and sibling node 8 ran but the barrier did not commit, their fenced accepted results can be reused against checkpoint 6 while only incomplete slots run.

#### 9.7.4 Nondeterminism and durable calls

Workers MUST NOT directly perform undeclared network effects. Time, randomness, LLM inference, subprocesses with external state, file writes, child-agent dispatch, payment, email, and tool calls enter through typed durable calls.

For a durable call:

1. task execution deterministically reaches call ordinal N;
2. task code supplies its declared effect_slot and the runtime derives effect_id solely from operation_id, effect_namespace_id, stable_task_path, and effect_slot;
3. if a completed durable result exists, it returns that result;
4. otherwise it registers EffectIntent and suspends the task without accepting a final TaskResult;
5. the effect worker executes after durable intent commit;
6. effect completion satisfies the task wait;
7. the task re-executes from the top or resumes through a language-neutral state-machine continuation and receives the memoized result at ordinal N.

Code before a replaying durable call must be pure or itself use durable calls. Provider responses of any permitted size are stored as authenticated blobs; production MUST NOT re-execute a consequential effect merely because its result exceeded an inline metadata cap.

#### 9.7.5 Durable-call suspension transaction

A task cannot register an effect in memory and hope a later checkpoint captures it. SuspendTaskPlan is an idempotent authoritative transaction:

~~~text
SuspendTaskPlanRequest {
  authority
  run_lease_token
  operation_owner_token
  suspension_id
  run_id
  expected_head_checkpoint_id
  expected_head_version
  plan_id
  task_id
  stable_task_path
  task_attempt_fence
  durable_call_ordinal
  effect_slot | null
  effect_intent | null
  wait_declaration
  accepted_sibling_result_ids[]
}
~~~

suspension_id is derived from plan_id, task_id, call ordinal, declared effect_slot, effect_id, wait_id, and their semantic digests. It is a request-deduplication ID, not the semantic effect ID. The transaction:

1. verifies active incarnation, run lease, head CAS, plan, task attempt fence, and exact call ordinal;
2. idempotently inserts the immutable EffectIntent when present;
3. inserts the WaitRecord and binds effect completion to it;
4. transitions the task slot and plan to WAITING;
5. preserves already accepted sibling results without applying their deltas;
6. changes the run control status to WAITING without moving the state head;
7. writes audit and outbox records;
8. commits atomically.

Only after that commit may an effect worker claim the intent. If the suspension response is lost, the same suspension_id returns the existing effect and wait. If the task reaches the same stable effect_slot with different operation/provider/account/target/request/payload/consequence/saga claims, it has reused the same effect_id inconsistently: the operation is quarantined with EFFECT_DETERMINISM_CONFLICT. A changed call ordinal alone neither remints nor aliases the effect; it is replay-drift evidence requiring migration or correction. When the wait resolves, the plan is reopened against the same head; the effect result is returned at the recorded cursor and exact accepted siblings remain reusable.

At most one nonterminal TaskPlan may own a given (run_id, input_checkpoint_id, absolute_superstep) unless the graph explicitly declares independent speculative plans. Speculative plans MUST NOT mint alternate namespaces to conceal divergent semantics. They are external-effect-disabled until one plan wins head CAS; only the winner may register intents under the operation's existing effect_namespace_id. Different claims for one stable effect ID are a determinism conflict, not two candidates to race.

---

### 9.8 Exact resume, fork, migration, and compaction

#### 9.8.1 Resume API

~~~text
LoadResumePackage(
  tenant_id,
  thread_id,
  run_id | null,
  checkpoint_id | HEAD,
  requested_graph_package_digest | null,
  authority
) -> ResumePackage

ResumePackage {
  run_record
  verified_checkpoint_envelope
  materialized_state_manifest
  channel_versions
  versions_seen
  next_frontier
  durable_call_cursors
  budget_snapshot
  open_waits
  unresolved_effects
  child_joins
  reusable_plan
  accepted_uncommitted_results
  required_graph_package
  expected_head_version
}
~~~

Resume sequence:

1. acquire a new run lease and fencing token;
2. read run head and all resume metadata at one consistent database snapshot;
3. execute the full checkpoint verification algorithm;
4. resolve and verify the exact graph package and dependency lock;
5. reconstruct state only from authenticated manifests/blobs;
6. rehydrate an exact matching pending plan, if any;
7. reconcile expired effect/task claims without provider calls;
8. schedule only next-frontier or missing pending-plan work.

If checkpoint_id names history rather than current head, the caller must use ForkRun or an explicit read-only inspection API. Resume MUST NOT move a live branch backward in place.

#### 9.8.2 Fork

~~~text
ForkRunRequest {
  authority
  fork_mode: SAME_OPERATION_REPAIR | EXPLORATORY
  source_run_id
  source_checkpoint_id
  target_thread_id
  target_run_id
  target_branch_id
  stable_path_mapping_blob_id | null
  prior_effect_observation_policy: REFERENCES_ONLY | DROP
  wait_policy: DROP | COPY_AS_NEW
  child_policy: REFERENCES_ONLY | DROP
  reason
}
~~~

ForkRun is one transaction plus preverified blobs. Both modes verify the source checkpoint and authority, create a new run/branch/head, create an authenticated anchor that references the source, add independent blob references, omit leases/attempt ownership/outbox claims, and emit a ForkRecord, audit event, and outbox event.

**SAME_OPERATION_REPAIR** is continuation of the original semantic undertaking:

- preserve operation_id, task_namespace_id, effect_namespace_id, and origin idempotency key;
- authenticate and validate StablePathMapping; every live source task/effect path is either preserved or explicitly mapped to one canonical semantic path, and ambiguous/many-to-one mappings fail;
- recompute SemanticTaskId and EffectId from preserved canonical paths and require equality with source semantic identities; derive new TaskIds for the successor run/graph/step/activations;
- bind the repair run to the operation-global EffectIntent records; completed effects are reused, UNKNOWN effects remain UNKNOWN, and pending effects retain their semantic IDs and provider keys;
- discard worker/lease ownership only; never remint an effect to escape a pending or uncertain claim;
- create the successor initially non-owning and effect-disabled;
- after verification, atomically call TransferOperationOwner from source to successor, incrementing the operation owner fence and marking the source `OperationOwner` projection `SUPERSEDED` without changing its terminal `RunStatus`;
- permit progression/effect dispatch only under the successor's new OperationOwnerToken plus normal run/effect authority and reconciliation rules.

**EXPLORATORY** is not continuation of the same operation:

- mint a new operation_id, task_namespace_id, effect_namespace_id, origin idempotency key, SemanticTaskIds, TaskIds, EffectIds, waits, and outbox identities;
- make the exploratory run owner of its new operation but set external_effects_mode=DISABLED atomically in both operation and run control;
- retain selected prior effects only as immutable, read-only observations with original provenance; they do not satisfy new effect IDs and cannot be claimed;
- require a separate operator/policy action, after inspection, to enable external effects. Fork creation itself cannot request or imply that activation.

No mode copies UNKNOWN or in-flight effect **ownership** as executable work. Same-operation repair references the original effect records and reconciles them; exploration has fresh, disabled identities. Forking a checkpoint whose state assumes unresolved external reality is quarantined unless the selected mode has an explicit, reviewed interpretation.

The source checkpoint never changes. An EXPLORATORY fork does not mutate the source run. SAME_OPERATION_REPAIR changes only the source run's mutable `OperationOwner` control projection to `SUPERSEDED` when operation ownership transfers; its terminal `RunStatus`, checkpoints, effects, receipts, and history remain immutable.

#### 9.8.3 Migration

Resume with incompatible schema or code fails closed. Migration is explicit:

~~~text
MigrationPlan {
  migration_id
  operation_id
  task_namespace_id
  effect_namespace_id
  source_graph_package_digest
  target_graph_package_digest
  source_schema_digest
  target_schema_digest
  source_reducer_manifest
  target_reducer_manifest
  transformer_artifact_digest
  transformer_runtime_digest
  stable_path_mapping_blob_id
  stable_path_mapping_digest
  input_checkpoint_id
  expected_output_state_root
  reversibility
  approvals
}
~~~

Requirements:

- migration transformer is deterministic, sandboxed, resource-bounded, and denied external effects;
- source checkpoint remains immutable;
- dry-run output and invariants are reviewed before activation;
- the same input and transformer must reproduce the same output root;
- a same-operation migration preserves operation_id, task_namespace_id, effect_namespace_id, origin idempotency key, all SemanticTaskIds, and all EffectIds through an authenticated stable-path mapping; TaskIds may change with run/graph/step/activation;
- graph/package revision, schema revision, changed node names, and the migration itself MUST NOT enter SemanticTaskId or EffectId;
- every live task/effect path is mapped unambiguously; missing or ambiguous mappings fail closed;
- request/provider/account/target/payload/consequence/saga claims under an existing effect ID must remain byte-identical. If new product behavior requires a changed external operation, it declares a new stable effect_slot; it cannot add a revision field to the old identity;
- a migration that intentionally creates a new semantic undertaking is an EXPLORATORY fork, receives fresh operation/namespaces, and starts with external effects disabled;
- the migration produces a new run or new branch anchor by default, not an in-place historical rewrite;
- migration records source and target manifests, toolchain, operator approvals, transformed/dropped fields, and proof digests;
- pending attempts, waits, effects, and sagas require typed migration adapters or remain on the old branch;
- the target migration run starts non-owning and effect-disabled; activation atomically transfers operation ownership/fence from source to target and supersedes the source;
- rollback selects the old branch; it does not reverse-write old bytes into the migrated checkpoint.

Migration activation uses head CAS, an execution-exclusive maintenance lease,
and operation-owner transfer in one serializable transaction. The transaction
consumes/releases the maintenance authority as it publishes the successor so a
later release cannot be stranded on the old head. A crash before CAS leaves an
unreferenced non-owning proposal; a crash after CAS is recovered idempotently
by migration_id. Rollback that reactivates the source is a new fenced ownership
transfer, never reuse of its old owner token.

#### 9.8.4 Compaction

Logical checkpoints are immutable. Compaction operates on retention:

~~~text
CompactionRecord {
  compaction_id
  tenant_id
  run_id
  first_checkpoint_id
  last_checkpoint_id
  boundary_parent_digest
  boundary_child_digest
  ordered_range_merkle_root
  materialized_boundary_manifest_blob_id
  retained_root_set_digest
  archive_manifest_blob_id
  policy_digest
  approvals
  created_at
  integrity_tag
}
~~~

Before inspecting a nonterminal branch for pruning, and throughout publication
of its compaction decision, the compactor MUST hold the execution-exclusive
maintenance lease from §9.5.4 against the exact head. Terminal history also
uses the same maintenance lease to serialize concurrent migration, repair, pin,
and compaction commands. Before pruning any online record, the compactor MUST:

1. take a consistent snapshot;
2. compute reachability from all run heads, branches, historical pins, open waits, unresolved effects, sagas, task results, legal holds, audit holds, backup/PITR windows, and operator pins;
3. materialize and verify a full state manifest at every retained boundary;
4. archive the range and verify archive restoration;
5. write the authenticated CompactionRecord;
6. wait the configured grace interval;
7. re-evaluate reachability under a newer database snapshot and CAS the same
   maintenance fence and expected head;
8. tombstone, never immediately hard-delete, eligible records/blobs.

Resume from every retained checkpoint must produce the identical state root, frontier, versions, call cursors, and budgets before and after compaction. A compaction certificate substitutes only for ancestry verification of intentionally archived records; it cannot make an invalid state valid.

---

### 9.9 Effect protocol, reconciliation, UNKNOWN, and sagas

#### 9.9.1 Effect schema

~~~text
EffectIntent {
  tenant_id
  effect_id
  operation_id
  effect_namespace_id
  stable_task_path
  effect_slot
  origin_idempotency_key
  provider_idempotency_key
  origin_run_id
  origin_plan_id
  origin_task_id
  durable_call_ordinal
  operation_kind
  consequentiality: PURE_OBSERVATION | REVERSIBLE | CONSEQUENTIAL |
                    IRREVERSIBLE
  provider
  provider_account_digest
  target_digest
  canonical_request_blob_id
  canonical_request_digest
  payload_digest
  authority_snapshot_blob_id
  warrant_id
  approval_id
  policy_decision_digest
  saga_id
  saga_step
  compensation_effect_template_id
  status
  effect_version
  created_at
  not_before
  deadline
}

EffectBinding {
  tenant_id
  run_id
  plan_id
  semantic_task_id
  task_id
  effect_id
  stable_task_path
  effect_slot
  binding_kind: ORIGIN | RESUME | REPAIR | MIGRATION
  PRIMARY KEY(tenant_id, run_id, plan_id, task_id, effect_id)
}

EffectAuthorizationDecision {
  tenant_id
  effect_id
  decision_id
  warrant_id
  approval_id
  policy_version
  decision: ALLOW | DENY | REVOKED | EXPIRED
  scope_digest
  valid_from
  valid_until
  authority_receipt_blob_id
  created_at
  PRIMARY KEY(tenant_id, effect_id, decision_id)
}

EffectAttempt {
  tenant_id
  effect_attempt_id
  effect_id
  attempt_number
  worker_id
  claim_fence
  active_incarnation_id
  activation_epoch
  claimed_at
  lease_expires_at
  dispatch_started_at
  provider_request_id
  provider_status_code
  transport_outcome
  response_blob_id
  receipt_digest
  finished_at
  status
}
~~~

EffectIntent states and allowed transitions:

~~~text
DECLARED
  -> BLOCKED_APPROVAL
  -> READY
  -> CANCELLED             cancelled/terminalized before eligibility
BLOCKED_APPROVAL
  -> READY                 current approval/warrant accepted
  -> FAILED_FINAL          denied by terminal policy decision
  -> CANCELLED             run cancelled/terminalized before dispatch
READY
  -> CLAIMED
  -> CANCELLED             run cancelled/terminalized before claim
CLAIMED
  -> DISPATCHING
  -> READY                 only if definitely not sent and claim abandoned
  -> CANCELLED             only with durable proof gateway sent nothing
DISPATCHING
  -> SUCCEEDED
  -> FAILED_RETRYABLE      only on definite provider rejection/non-acceptance
  -> FAILED_FINAL
  -> UNKNOWN               any ambiguous acceptance window
FAILED_RETRYABLE
  -> READY                 retry policy, same effect_id/provider key
UNKNOWN
  -> SUCCEEDED             reconciliation proof
  -> FAILED_RETRYABLE      proof provider did not accept
  -> FAILED_FINAL          authoritative proof of rejection/non-execution
  -> COMPENSATION_REQUIRED proof that compensation is safe for either outcome
  -> QUARANTINED           ambiguity cannot be safely resolved
SUCCEEDED
  -> COMPENSATION_REQUIRED saga decision
COMPENSATION_REQUIRED
  -> COMPENSATING
COMPENSATING
  -> COMPENSATED
  -> COMPENSATION_FAILED
CANCELLED                  terminal; provider was provably not called
~~~

There is no UNKNOWN -> READY transition without evidence that retry is safe.
Human authority may accept a business loss, quarantine, or authorize a distinct
new operation; it cannot turn uncertainty into proof that the original slot was
not executed and cannot blindly redispatch that slot. Compensation from
`UNKNOWN` is allowed only when the adapter proves the compensation is safe
whether the forward effect happened or not.

The canonical effect vocabulary is the state machine above. Qualification and
telemetry shorthand maps exactly as follows: `CONFIRMED = SUCCEEDED`,
`FAILED = FAILED_FINAL`, and `UNKNOWN = UNKNOWN`. `FAILED_RETRYABLE` is
nonterminal and MUST NOT satisfy a terminal-`FAILED` invariant. Implementations
and evidence receipts SHALL store the canonical name plus, if needed, the
derived shorthand; they may not define a second effect state machine.

#### 9.9.2 Registration

RegisterEffectIntent occurs in the superstep commit transaction or a durable-call suspension transaction. The service independently recomputes:

~~~text
expected_effect_id =
  H_id("effect", tenant_id,
    operation_id, effect_namespace_id, stable_task_path, effect_slot)
~~~

It rejects a caller-supplied mismatch. Duplicate effect_id with byte-identical operation-kind, provider, provider-account, target, request, payload, saga, and consequence claims is idempotent and adds only a valid EffectBinding. Duplicate effect_id with any different immutable semantic claim is EFFECT_DETERMINISM_CONFLICT, quarantines every active run of the operation, preserves both claim blobs as evidence, and alerts security. It is never resolved by silently creating an ID from the changed request. Refreshed or revoked authorization is appended as EffectAuthorizationDecision and cannot alter semantic claims.

Provider idempotency keys are stable, bounded encodings of tenant_id and effect_id. Provider-specific truncation must retain collision resistance and be tested. The key is persisted before dispatch and never reminted on retry, replan, same-operation repair/migration, restore, graph revision, or authentication-key rotation.

#### 9.9.3 Claim and dispatch

ClaimEffect is a short database transaction:

1. verify active writable incarnation and activation epoch;
2. lock the operation-owner and owning-run rows; verify the calling run holds
   the current owner token/fence, `owner_state=ACTIVE`,
   `external_effects_mode=ENABLED`, and owning `RunStatus` is exactly `RUNNING`
   or `WAITING` (the latter permits a previously committed durable-call intent);
3. verify effect READY and not_before/deadline;
4. re-evaluate authority, warrant, approval, revocation, budget, and policy;
5. increment claim_fence and attempt_number;
6. create EffectAttempt;
7. transition READY -> CLAIMED by effect_version CAS;
8. commit and return a signed claim token.

No provider call occurs in that transaction.

Before the network call, the effect gateway verifies the signed claim, current
activation epoch from external authority, current operation owner run/fence,
`owner_state=ACTIVE`, owning run status in `{RUNNING, WAITING}`,
`external_effects_mode=ENABLED`, provider idempotency key, request digest,
tenant egress policy, and warrant. It records DISPATCHING in a short transaction,
then rechecks activation, owner state/fence, owning run status, and effects mode
at its egress boundary immediately before calling the provider. A cancel,
failure, quarantine, terminal transition, or ownership transfer that linearizes
first makes this check fail and causes zero new provider calls.

Completion is another transaction requiring current effect version, attempt fence, incarnation, activation epoch, and current operation-owner run/fence. It stores the authenticated response/receipt blob reference, transitions the effect, satisfies any bound wait when appropriate, advances saga state, and writes audit/outbox records atomically. If ownership transferred while the provider call was in flight, direct completion by the predecessor is fenced; the returned provider evidence enters reconciliation under the successor owner and cannot be discarded or overwrite state directly.

#### 9.9.4 Crash and ambiguity rules

| Failure point | Required recovery |
|---|---|
| before intent commit | no effect exists; provider MUST NOT be called |
| after intent commit, before claim | another worker may claim |
| after claim, before DISPATCHING | expired claim may return to READY only with proof gateway saw no send |
| after DISPATCHING, before network send | conservative UNKNOWN unless gateway has a durable no-send fact |
| provider definite rejection | FAILED_RETRYABLE or FAILED_FINAL by policy |
| timeout/connection reset after bytes may have reached provider | UNKNOWN |
| provider accepted, worker crashes before recording response | UNKNOWN after claim expiry; reconcile by same provider key |
| completion committed, response to worker lost | reread effect; never call provider again |
| stale worker returns after takeover | completion CAS fails; result is evidence for reconciliation, not an overwrite |

#### 9.9.5 Reconciliation

The reconciler scans:

- expired CLAIMED/DISPATCHING attempts;
- UNKNOWN effects;
- provider webhooks without a local terminal record;
- local terminal records lacking receipt/blob/outbox completeness;
- sagas blocked by uncertain steps.

It claims reconciliation work with its own fence and queries the provider by provider idempotency key or provider request ID. Evidence is stored before transition. Reconciliation never changes effect_id and never fabricates a successful receipt.

Provider capability classes:

| Class | Provider support | Automatic policy |
|---|---|---|
| A | idempotency key plus query/status | safe same-key retry/query under bounded policy |
| B | idempotency key, no query | same-key retry only if provider contract guarantees replay; otherwise UNKNOWN |
| C | query/status, no idempotent create | query first; dispatch only when absence can be proved |
| D | neither | no automatic retry after ambiguous dispatch; human quarantine |

Irreversible production effects SHOULD require Class A or a Dharma-controlled idempotency gateway.

#### 9.9.6 Saga protocol

~~~text
Saga {
  tenant_id
  saga_id
  run_id
  saga_definition_digest
  current_forward_step
  current_compensation_step
  status: FORWARD | COMPLETED | COMPENSATION_REQUIRED | COMPENSATING |
          COMPENSATED | COMPENSATION_FAILED | UNKNOWN | QUARANTINED
  saga_version
}

SagaStep {
  saga_id
  step_number
  forward_effect_id
  compensation_effect_id
  compensation_policy
  status
}
~~~

Forward steps and compensation steps are distinct effects. Compensation order is reverse dependency order, not merely reverse completion time. A compensation is scheduled only after the forward effect is proved SUCCEEDED. An UNKNOWN forward or compensation step freezes automatic saga progression unless the policy contains a reviewed, provider-specific safe resolution.

Cancellation of a run does not erase external reality. It transitions eligible sagas to COMPENSATION_REQUIRED or QUARANTINED according to declared policy.

---

### 9.10 Durable waits, interrupts, timers, and signals

#### 9.10.1 Wait schema

~~~text
WaitRecord {
  tenant_id
  wait_id
  operation_id
  task_namespace_id
  run_id
  plan_id
  task_id
  input_checkpoint_id
  stable_task_path
  wait_slot
  durable_call_ordinal
  wait_generation
  wait_kind: HUMAN | SIGNAL | TIMER | EFFECT | CHILD_RUN | APPROVAL
  correlation_key_digest
  expected_payload_schema_digest
  authorization_policy_digest
  bound_effect_id
  bound_child_run_id
  deadline_database_time
  status: WAITING | SATISFIED | TIMED_OUT | CANCELLED | EXPIRED |
          QUARANTINED
  winning_signal_id
  result_blob_id
  wait_version
  created_at
  resolved_at
}

SignalRecord {
  tenant_id
  signal_id
  wait_id
  source_kind
  source_identity
  idempotency_key
  payload_blob_id
  payload_digest
  authority_digest
  received_at
  disposition: ACCEPTED | DUPLICATE | LATE | UNAUTHORIZED |
               SCHEMA_INVALID | QUARANTINED
  UNIQUE(tenant_id, signal_id)
  UNIQUE(tenant_id, wait_id, idempotency_key)
}
~~~

The service recomputes
`WaitId = H(tenant, operation_id, task_namespace_id, stable_task_path,
wait_slot, wait_generation)` and rejects a mismatch. Signal and response
deduplication keys include this exact `WaitId`; terminal generation `g` can
never consume a signal intended for generation `g+1`.

#### 9.10.2 Interrupt semantics

An interrupt does not serialize a call stack. It produces a durable wait
declaration whose semantic identity is operation_id, task_namespace_id,
stable_task_path, declared wait_slot, and coordinator-derived wait_generation.
The call ordinal is a replay-consistency cursor, not the WaitId source. The
superstep head remains at its pre-step checkpoint unless the graph model
explicitly commits a separate yield checkpoint. Successful sibling TaskResults
may be retained but remain invisible until a later complete bundle.

On resume, the interrupted node re-executes from its deterministic entry point. The Nth durable interrupt/effect call verifies the expected declared slot and reads its recorded result for that operation/task path. Any code before it must be pure or durable-call mediated. A code change that changes call ordering or slot mapping requires migration; it MUST NOT consume old resume values under new ordinals or remint identities from the changed ordinal.

The public resume API addresses an exact wait:

~~~text
DeliverSignal(wait_id, signal_id, idempotency_key, payload, authority)
  -> SignalDisposition

ResumeWait(run_id, wait_id, expected_wait_version,
           expected_head_checkpoint_id, authority)
  -> ResumeReceipt
~~~

Using only thread_id and “latest interrupt” is prohibited where more than one wait may exist.

#### 9.10.3 Signal transaction

DeliverSignal:

1. verifies source authority and tenant;
2. canonicalizes, uploads, and verifies payload;
3. begins a serializable transaction;
4. inserts SignalRecord or returns the prior duplicate disposition;
5. locks WaitRecord;
6. verifies WAITING, expected schema, correlation, policy, and deadline;
7. CAS transitions WAITING -> SATISFIED with winning signal;
8. inserts audit and outbox records;
9. commits.

Timer expiry, human response, child completion, provider webhook, and cancellation use the same CAS. Exactly one wins. Losing signals are retained as LATE evidence and never overwrite the winning result.

ResumeWait consumes no payload destructively. It marks the run runnable and creates/reopens the exact TaskPlan using head CAS and wait version. Repeated resume requests return the same receipt.

#### 9.10.4 Approval waits

Approval records include action summary, exact request digest, consequence class, expiry, approver identity, separation-of-duties policy, and revocation state. A changed effect request invalidates prior approval. Dispatch rechecks approval validity; approval at intent creation is not a permanent bearer token.

---

### 9.11 Transactional outbox and inbox

#### 9.11.1 Schema

~~~text
OutboxRecord {
  tenant_id
  outbox_id
  stream_id
  stream_sequence
  destination
  event_kind
  causation_id
  trace_id
  payload_blob_id
  payload_digest
  headers_digest
  status: PENDING | CLAIMED | PUBLISHED | RETRY_WAIT | DEAD_LETTER
  claim_fence
  claimed_by
  claim_expires_at
  attempt_count
  next_attempt_at
  provider_message_id
  published_at
  last_error_blob_id
  UNIQUE(tenant_id, outbox_id)
  UNIQUE(tenant_id, stream_id, stream_sequence)
}

InboxRecord {
  tenant_id
  destination_consumer
  outbox_id
  payload_digest
  first_received_at
  processed_at
  result_digest
  PRIMARY KEY(tenant_id, destination_consumer, outbox_id)
}
~~~

For run event streams, `stream_id` binds tenant, run, and
`stream_incarnation`; `stream_sequence` is allocated in the same transaction as
the causative state change and is unique only inside that identity. Per-stream
order is preserved where required; unrelated streams may publish concurrently.

#### 9.11.2 Publisher protocol

1. claim eligible rows in a short transaction using skip-locked or CAS;
2. publish outside the transaction with outbox_id as the destination dedupe key;
3. record PUBLISHED by claim fence CAS;
4. if acknowledgement is ambiguous, retry the same outbox_id;
5. after bounded attempts, retain DEAD_LETTER and alert; never silently drop.

A crash after publish but before PUBLISHED can duplicate delivery. A conforming internal consumer inserts InboxRecord and applies its state change in one transaction. External destinations lacking dedupe receive explicitly documented at-least-once semantics.

Outbox publishing MUST NOT advance graph state. It projects already committed truth.

---

### 9.12 Blob lifecycle, garbage collection, and PITR

#### 9.12.1 Blob format

Each object is tenant-scoped and immutable:

~~~text
blob_id = "blob_" || base32(
  H_content("blob-plaintext", tenant_id, canonical_plaintext_bytes)
)

BlobEnvelope {
  format_version
  tenant_id
  blob_id
  content_digest_algorithm
  codec_id
  schema_digest
  plaintext_length
  ciphertext_length
  encryption_algorithm: AES-256-GCM or approved equivalent
  encryption_key_version
  nonce
  wrapped_data_key
  ciphertext_digest
  authenticated_metadata
  ciphertext
}
~~~

Storage key includes tenant_id and blob_id; cross-tenant physical deduplication is prohibited. Conditional create rejects different ciphertext metadata for an existing logical blob unless a registered re-encryption version is being written. Key rotation creates a new object version and atomically changes the verified storage projection; logical blob_id remains stable.

Secrets SHOULD be referenced through a secrets service rather than embedded in state. If secret material must be checkpointed, it requires field-level classification, encryption, redaction from logs/streams, and shorter retention rules that remain compatible with resume.

#### 9.12.2 Lifecycle

~~~text
STAGING -> VERIFIED -> LIVE -> TOMBSTONED -> DELETING -> DELETED
                     \-> QUARANTINED
~~~

- STAGING objects have no authoritative owner and expire after an upload grace period.
- VERIFIED means bytes passed integrity and durability checks.
- LIVE is derived from at least one committed or protected reference.
- TOMBSTONED records a future delete_after; object versions remain recoverable.
- QUARANTINED objects are never executed or automatically deleted until adjudicated.

Refcounts are hints for cost and scheduling. Mark-and-sweep reachability from an authoritative database snapshot decides deletion.

#### 9.12.3 GC roots

The mark phase includes:

- every live run and branch head;
- all checkpoints inside retention or PITR windows;
- operator-pinned and legal-held checkpoints;
- open task plans, accepted results, and nonterminal attempts;
- open waits and signals inside retention;
- nonterminal effects, all UNKNOWN effects, receipts, and active sagas;
- unpublished/dead-letter outbox and unexpired inbox records;
- migration, compaction, restore, audit, and evidence records;
- backup manifests not past expiry;
- fork lineage sources required by policy.

Sweep protocol:

1. record gc_epoch and consistent database snapshot;
2. mark all reachable blob IDs;
3. identify unmarked candidates older than grace and PITR minima;
4. write tombstones, not deletes;
5. wait at least one full GC cycle and replication/backup lag bound;
6. repeat reachability at a later snapshot;
7. require no legal hold and unchanged blob reference version;
8. issue version-specific object deletion;
9. verify deletion and retain deletion receipt.

A concurrent new reference defeats the CAS and rescues the blob. GC credentials cannot mutate graph heads or effect state.

#### 9.12.4 Backup and point-in-time recovery

Production SHALL provide:

- continuous database WAL/log archiving;
- encrypted full backups;
- versioned object storage retained longer than the maximum database PITR window;
- cross-failure-domain replication;
- backup manifests containing database log position, object inventory high-water mark, key-version inventory, audit anchor, and checksum;
- escrowed/recoverable KMS key versions for every retained checkpoint;
- automatic backup verification and scheduled full restore drills.

Baseline production objectives are RPO <= 5 minutes and RTO <= 60 minutes unless a stricter deployment profile is ratified. A system that has never completed a timed restore drill may not claim those objectives.

Database-at-time-T consistency is safe because committed rows reference only objects verified durable before their transaction. GC MUST retain object versions beyond database PITR plus replication lag plus safety margin.

---

### 9.13 Disaster restore and incarnation fencing

#### 9.13.1 Control-plane separation

The activation authority is a small linearizable service, HSM-backed register, or quorum process outside the database backup:

~~~text
ActivationRecord {
  store_lineage_id
  activation_epoch
  active_incarnation_id
  active_region
  mode
  predecessor_incarnation_id
  activation_reason
  operator_approvals
  issued_at
  expires_or_review_at
  signature
}
~~~

All scheduler commits, task claims, effect claims, effect-gateway calls, wait mutations, outbox claims, and GC actions require a current signed activation token. Restoring an old database cannot restore an old token into validity.

#### 9.13.2 Restore procedure

1. declare incident and freeze automated failover loops;
2. revoke or isolate old-region database, queue, KMS grants, service credentials, and provider egress;
3. restore database to selected log position in READ_ONLY mode;
4. restore or attach object replicas and verify backup manifest;
5. mint a new random active_incarnation_id;
6. CAS activation authority from prior epoch to epoch + 1 with required human/quorum approvals;
7. write a RestoreRecord, update store_control, and append one signed
   deployment-level `RESTORE_DISCONTINUITY` control root under the new
   activation token; it binds predecessor/new stream incarnations and the last
   externally witnessed event high-water marks without requiring an O(number
   of runs) event transaction;
8. invalidate all restored run leases, operation-owner tokens, task attempts, and effect claims through the new incarnation; preserve their history as ABANDONED_BY_RESTORE, retain each operation's owner_run_id/fence in the database, and issue fresh owner tokens only after verification;
9. verify checkpoint frames, head anchors, blob inventory, graph packages, key versions, open effects, UNKNOWN windows, waits, outbox, and sagas;
10. reconcile providers by stable effect/provider keys before dispatch;
11. run read-only replay and invariant checks;
12. enable pure scheduling writes;
13. enable outbox/effect egress only after the old incarnation is externally fenced and the effect gateway accepts only the new epoch;
14. produce signed recovery evidence and measure RPO/RTO.

If the old site cannot be proven fenced, the restored site remains READ_ONLY or runs with external effects and publication disabled. Availability does not outrank double-payment, double-message, or split-brain safety.

#### 9.13.3 Restore record

~~~text
RestoreRecord {
  restore_id
  store_lineage_id
  source_backup_id
  source_database_position
  predecessor_incarnation_id
  new_incarnation_id
  old_activation_epoch
  new_activation_epoch
  selected_recovery_time
  measured_data_loss
  checkpoint_verification_report_blob_id
  blob_verification_report_blob_id
  open_effect_reconciliation_report_blob_id
  old_site_fencing_evidence_blob_id
  approvals
  activated_at
  integrity_tag
}
~~~

Restore never changes operation_id, task_namespace_id, effect_namespace_id, run_id, checkpoint_id, task_id, effect_id, provider idempotency key, wait_id, signal_id, or outbox_id. Therefore retries after restore collide with prior semantic work rather than creating duplicates.

---

### 9.14 Crash and race matrix

The following outcomes are mandatory:

| Injected failure/race | Required observable outcome |
|---|---|
| crash during blob upload | no database reference; staged orphan later collected |
| crash after blob verification, before commit | old head; verified orphan safe to reuse or collect |
| node mutates its input object | mutation cannot reach authoritative snapshot; runtime detects or isolation prevents it |
| two siblings finish in opposite orders | identical bundle digest and state root |
| one sibling fails | zero head advancement; successful fenced results retained only as uncommitted work |
| scheduler crashes after result acceptance | replacement reuses exact results; no completed activity/effect is reminted |
| crash after bundle construction, before commit | old head; same commit may be retried |
| two schedulers submit different bundles to same head | one CAS winner at most; loser gets HEAD_CONFLICT |
| commit succeeds, response is lost | same commit_id returns committed checkpoint |
| lease expires while worker paused | stale worker cannot accept result or move head |
| old holder wakes after lease takeover | higher fence rejects every mutation |
| old operation owner wakes after repair transfer | higher operation-owner fence rejects commit, wait, outbox, and effect authority |
| checkpoint frame bit flips | CHECKPOINT_INTEGRITY_FAILURE and quarantine |
| blob swapped across tenants | authentication/tenant binding failure |
| graph package missing on resume | INCOMPATIBLE_RUNTIME; no fallback to newest code |
| crash after checkpoint 6 in 10-node chain | resume begins with node 7 frontier; nodes 1-6 do not execute |
| crash with partial fan-out results | exact matching successes reused; missing slots execute; one canonical barrier commit |
| replan places same semantic task | SemanticTaskId unchanged; TaskId stays only for identical run/graph/step/activation, otherwise changes; result reuse needs exact compatibility proof |
| restore creates a new task attempt | AttemptId differs because active_incarnation_id differs; SemanticTaskId, TaskId, and EffectId remain stable for the restored activation |
| same-operation repair fork from history | new run/head; operation/namespaces and mapped SemanticTaskId/EffectId preserved; new TaskIds derived; owner fence transfers and source is superseded |
| exploratory fork from history | new operation and namespaces; external effects disabled; source unchanged |
| migration crashes before activation CAS | target proposal unreferenced; source remains head |
| migration activation response lost | migration_id returns same target head |
| provider call may have crossed network, response lost | effect UNKNOWN; no unsafe automatic retry |
| same effect claimed by 100 workers | one current claim fence; one provider semantic key |
| provider success then worker dies | reconciliation finds success by stable key and records it |
| non-idempotent provider cannot answer status | human quarantine; never guessed retry |
| saga compensation fails | COMPENSATION_FAILED or UNKNOWN; original forward effect remains visible |
| signal and timer race | one wait-version CAS winner; loser recorded LATE |
| duplicate human response | one accepted signal, deterministic duplicate response |
| outbox publish succeeds, ack lost | possible duplicate with same outbox_id; inbox processes once |
| GC races with new fork/reference | reference-version CAS rescues blob; no live deletion |
| GC process crashes after tombstone | object recoverable until resumed, verified deletion |
| database restored while old region runs | new region cannot enable writes/effects until external activation epoch fences old |
| restored worker uses old token | INCARNATION_FENCED or ACTIVATION_EPOCH_MISMATCH |

---

### 9.15 Production acceptance gates

No deployment may claim this durability contract until every gate has machine-readable evidence tied to exact source, dependency lock, database schema, graph package, and infrastructure versions.

#### 9.15.1 Integrity suite

- Flip every byte position class in frame core, envelope, record projection, manifests, and blobs; every mutation is rejected before execution.
- Substitute a valid blob/frame from another tenant, run, graph version, schema, or parent; reject.
- Delete or reorder a parent and verify chain or compaction-proof failure.
- Restore an older internally valid database behind the external head witness; detect rollback.
- Rotate encryption and authentication keys while retaining resume for every retained key version.
- Fuzz canonicalization across all supported values and prove identical bytes across supported languages/platforms.

#### 9.15.2 Concurrency and fencing suite

- Run at least 100 concurrent lease acquirers; exactly one current fence exists.
- Pause the winner, expire/take over, then release the old process; every old mutation fails.
- Transfer one operation through 100 competing repair successors; exactly one successor owner fence wins and every predecessor/loser effect call is rejected at the egress gateway.
- Submit identical commit requests concurrently; one checkpoint exists and all callers receive it.
- Submit conflicting bundles against one head; at most one head move.
- Repeat under transaction serialization failures, connection loss, replica lag, and process kill.
- Verify database time, not injected worker-clock skew, decides expiry.
- Race execution acquisition/takeover against migration and compaction
  maintenance claims; exactly one authority kind is live and no pruned record
  is required by a later accepted commit.

#### 9.15.3 Exact recovery suite

- For a chain, cycle, conditional branch, join, nested child graph, interrupt, and 1,000-way fan-out, kill the runtime after every durable boundary.
- Compare final state root, frontier, channel versions, budgets, accepted task set, effect set, and audit causality with an uninterrupted oracle.
- Instrument node execution counts: work committed before the selected checkpoint executes zero additional times.
- Verify successful siblings from an uncommitted failed step are reused only under exact plan compatibility.
- Prove SemanticTaskId stays fixed while TaskId changes across run/graph/step/activation and AttemptId changes across attempt/incarnation; prove no identity is conflated in storage or receipts.
- Remove the pinned graph package and prove fail-closed resume.
- Test repair-fork divergence and source immutability while proving operation/task/effect namespaces and mapped identities are preserved.
- Prove repair/migration cannot progress the successor until operation ownership transfers, and cannot progress the predecessor afterward.
- Test exploratory forks mint fresh operation/namespaces and cannot dispatch any external effect until a separate activation.
- Run every registered migration twice and require identical target root and stable-path/SemanticTaskId/EffectId mapping; test rollback by branch selection.
- Compact and archive history, then resume every retained boundary with identical semantic roots.

#### 9.15.4 Effect and saga suite

- Inject crash, timeout, cancellation, and response loss before and after every effect transition.
- Against a Class A fake provider, prove one semantic external operation and eventual terminal local status for arbitrary retries and worker races.
- Against a Class D fake provider, prove ambiguous dispatch enters UNKNOWN and is never automatically retried.
- Prove SemanticTaskId is unchanged across retry, replan, new run, graph revision, and same-operation repair/migration when stable_task_path maps; prove TaskId changes exactly when run/graph/step/activation inputs change.
- Prove effect_id and provider key are unchanged across attempt retry, replan, new run, graph revision, same-operation repair/migration, database PITR, disaster incarnation, and authentication/encryption-key rotation.
- Revoke a warrant after intent creation but before dispatch; provider is not called.
- Race `ClaimEffect` and the gateway's final egress check against cancellation,
  failure, quarantine, and successful terminal commit; if terminal/draining
  control linearizes first, the provider receives zero new calls.
- Change request, provider, account, target, payload, operation kind, consequence class, or saga placement under an existing effect_id; raise EFFECT_DETERMINISM_CONFLICT and quarantine without provider dispatch.
- Expire, revoke, and refresh effect authorization; prove EffectId and semantic claims remain unchanged while dispatch follows the latest valid EffectAuthorizationDecision.
- Prove none of run_id, plan_id, TaskId, AttemptId, graph revision, request digest, retry count, or key version affects SemanticTaskId/EffectId golden vectors; separately prove TaskId golden vectors include run, graph revision, step, and activation.
- Execute multi-step sagas with forward failure, compensation failure, UNKNOWN forward, UNKNOWN compensation, and operator adjudication.
- Prove oversized/non-inline results are blob-backed and never trigger consequential re-execution.

#### 9.15.5 Wait and outbox suite

- Deliver duplicate, late, unauthorized, schema-invalid, and cross-tenant signals; only one valid transition wins.
- Race signal, timeout, cancellation, child completion, and effect completion under 100 workers.
- Change durable call order between code versions and prove migration is required.
- Enter the same wait slot across many loop generations; terminal generation
  `g` and all its duplicate signals cannot satisfy generation `g+1`.
- Crash before and after message publish and acknowledgement; inbox applies each outbox_id at most once.
- Verify per-stream ordering, retry backoff, poison-message dead letter, and operator replay with the same outbox_id.

#### 9.15.6 Blob, backup, and disaster suite

- Corrupt object bytes, metadata, AEAD tags, object versions, and manifests; reject.
- Run GC concurrently with commits, forks, legal holds, compaction, backup, and restore; delete no reachable object.
- Restore database to random points throughout the PITR window and verify every referenced object exists and authenticates.
- Complete a full isolated restore drill at least quarterly and a backup verification at least daily.
- Demonstrate declared RPO and RTO with measured evidence.
- Crash after head commit but before external witness export; prove the durable
  anchor outbox recovers, and prove a media-loss-RPO-0 profile does not
  acknowledge before the witness receipt.
- Restore behind an acknowledged stream tail and deliberately reuse numeric
  sequence values; old/new `(stream_incarnation, seq)` cursors and EventIds do
  not alias and old cursors receive `RESTORE_DISCONTINUITY`.
- Simulate the old region remaining alive. Prove activation authority and effect gateway reject it before enabling the new site.
- Reconcile all open DISPATCHING/UNKNOWN effects before egress activation and prove stable provider keys prevent duplicate semantic operations.

#### 9.15.7 Long-haul deterministic simulation

The deterministic test provider SHALL virtualize:

- database time and lease expiry;
- dispatch/completion order;
- process crash and restart;
- dropped, delayed, duplicated, and reordered messages;
- database serialization aborts and acknowledgement loss;
- object-store write/read/delete faults;
- provider acceptance and ambiguous responses;
- KMS/key-version unavailability;
- failover and activation-epoch changes.

Run seeded histories for at least millions of transitions with invariant checks after every transition. Persist the smallest failing seed, fault schedule, source commit, schema version, and infrastructure image digest. A passing happy-path test suite is insufficient.

---

### 9.16 Required service APIs

A conforming implementation exposes equivalent typed operations:

~~~text
// Run ownership and state
AcquireRunLease
RenewRunLease
ReleaseRunLease
AcquireMaintenanceLease
RenewMaintenanceLease
ReleaseMaintenanceLease
GetOperationOwner
TransferOperationOwner
GetRunHead
LoadResumePackage
CommitSuperstep
SuspendTaskPlan
FailTaskPlan
CancelRun

// Tasks
CreateOrLoadTaskPlan
ClaimTask
HeartbeatTaskAttempt
CompleteTaskAttempt
GetReusableResults
BuildAndValidateBundle

// History
ForkRun
PlanMigration
DryRunMigration
ActivateMigration
CreateCompactionRecord
PinCheckpoint
ReleaseCheckpointPin

// Effects and sagas
RegisterEffectIntent
ClaimEffect
MarkEffectDispatching
CompleteEffect
MarkEffectUnknown
ClaimReconciliation
RecordReconciliationEvidence
AdjudicateUnknownEffect
StartSagaCompensation

// Waits
RegisterWait
DeliverSignal
ResolveTimer
CancelWait
ResumeWait

// Messaging
ClaimOutboxBatch
CompleteOutboxPublish
FailOutboxPublish
RecordInboxAndApply

// Storage and recovery
StageBlob
VerifyBlob
CreateBlobReference
CreateLegalHold
RunGcMark
RunGcSweep
CreateBackupManifest
VerifyBackup
PrepareRestore
ActivateRestoredIncarnation
FinalizeRestore
~~~

Every mutating API is idempotent by request_id, tenant-scoped, audit-producing, and version/CAS guarded. SDK convenience methods may compose calls but may not weaken their preconditions.

---

### 9.17 Implementation boundary and migration from the current candidate

The production cutover should proceed in this order:

1. define canonical schemas, codecs, identity derivations, and conformance vectors;
2. implement the Durability Service against a transactional database with immutable migrations;
3. implement authenticated blob staging and checkpoint verification;
4. route scheduler plan/result/bundle persistence through the service;
5. make head CAS the sole definition of commit;
6. introduce run/task/effect/outbox fencing and external activation authority;
7. replace fail-open consequential dispatch with strict EffectIntent workflow;
8. implement waits/signals and exact pending-plan replay;
9. add fork/migration/compaction and reachability GC;
10. qualify PITR and disaster activation under fault injection;
11. shadow the candidate runtime, comparing roots and receipts without dispatching duplicate effects;
12. cut over only named graph classes whose qualification matrix is green.

Existing local checkpoint files and SQLite rows require an explicit importer. The importer:

- reads them as untrusted legacy input;
- validates and canonicalizes supported fields;
- creates new authenticated anchor checkpoints;
- never implies missing lease, effect, wait, or authority history existed;
- labels imported runs LEGACY_INCOMPLETE unless an operator accepts the evidentiary gaps;
- never enables automatic replay of a legacy ambiguous consequential effect.

There is no flag that turns the candidate file persistence into this production protocol. The architecture becomes production-grade only when every authoritative state transition and external effect is routed through the fenced transaction, verified in crash tests, and operated with a proven restore procedure.

## 10. Production qualification, security, and rollout

This part is normative for release qualification. It does not assert that any
named profile is currently implemented or qualified.

### 10.0 Non-negotiable claim boundary

Acceptance or hostile review of this document changes **no implementation score**.

The following claims are distinct and MUST NOT be collapsed:

1. **DESIGN_DRAFTED** — requirements exist in prose.
2. **DESIGN_REVIEWED** — independent reviewers found the design internally coherent.
3. **IMPLEMENTED** — source implementing a requirement exists at a named commit.
4. **CONFORMANCE_PROVEN** — executable tests prove the implementation against a frozen contract.
5. **SHADOW_PROVEN** — production-shaped traffic ran with effects suppressed and acceptable divergence.
6. **CANARY_PROVEN** — bounded live traffic ran inside SLOs and invariants.
7. **PROFILE_PRODUCTION_READY** — all mandatory gates for one named production profile passed and were independently ratified.

No earlier state implies a later state. In particular:

- DESIGN_REVIEWED is not IMPLEMENTED.
- A LangGraph parity score is not a production-readiness score.
- Passing unit tests is not crash-safety evidence.
- A valid checkpoint file is not exact-resume evidence.
- An async function is not a non-blocking end-to-end runtime.
- A digest is not authentication unless its signer and trust root are authenticated.
- A single-host lock is not a distributed ownership protocol.
- “Exactly once” is invalid for an external effect unless the provider participates in an idempotency or transactional protocol; otherwise DharmaGraph MUST describe the guarantee as effectively-once plus reconciliation.

Normative words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, and MAY are used in their RFC 2119 sense.

---

### 10.1 Verified baseline and the 58/100 truth

#### 10.1.1 Repository baseline inspected

This reconstruction section was checked on 2026-08-12 against:

| Item | Verified value |
|---|---|
| Canonical repository | AIKAGRYA/dharma_swarm |
| Default branch | main |
| main head at inspection | 12212397be1dbe0a9b0cc29be4311f930140e751 |
| Head commit | fix(mike): publish bounded review packets atomically [impact-checked] (#1185) |
| Active-track file | docs/governance/ACTIVE_TRACK.yaml |
| Active-track blob | f52986ff7cfb8645df7e60dac679aad341958cbb |
| Builder receipt blob | 95609cef5355fdc7f19b7506fd28fc7892ae3a50 |
| Judge receipt blob | e2704ecffc4ba5887680b0960c947757654af5e7 |
| Parity matrix blob | 94fe296fb1c2dd1e4bd7a7a263bbd5c60a374622 |
| V3 rubric overlay blob | ae6ccb1a204063325e0ead57d23c388d8d684c25 |
| Gauntlet script blob | 6ad3705fba5264b8975648eaebab9f3c95e52e98 |

Line references in this section are valid for those inspected blobs. Agents MUST re-resolve them after source drift.

#### 10.1.2 Governing status

The active track declares:

- dharmagraph-engine-2026-07 as ACTIVE at docs/governance/ACTIVE_TRACK.yaml:940-945.
- target_closure_kind: CLOSED_NOT_PROD at docs/governance/ACTIVE_TRACK.yaml:990.
- a no-production-capability claim boundary at docs/governance/ACTIVE_TRACK.yaml:991.
- closeout blocked below judge-signed 100/100 unless the operator ratifies an explicit non-goal set at docs/governance/ACTIVE_TRACK.yaml:1101.

The current sealed evidence says:

- score: **58.00/100**;
- verdict: **NOT_FINISHED**;
- closeout_blocked: true;
- receipt claim boundary: **CLOSED_NOT_PROD; this receipt grades engine parity only**;
- frozen comparison target: LangGraph 1.2.4;
- measured Dharma source SHA: c83df531c32ce7c775f27ddfbc7512e1cc952db7;
- observed_at: 2026-07-17;
- builder and judge stable digest: 59a6a08e226be3f699d11c8af20b5409881ed0e60a6b36b407dfe1bcd0a932a0;
- judge reconciliation: MATCH;
- 28 capability rows remain gaps.

The matrix headline and verdict are at reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3. The gauntlet itself stamps the CLOSED_NOT_PROD boundary at scripts/governance/dharmagraph_parity_gauntlet.py:960-976.

The receipt also records non-gating drift against LangGraph 1.2.8 while preserving 1.2.4 as the frozen grade. That is evidence discipline, not evidence of parity with whatever LangGraph release is current when this specification lands.

#### 10.1.3 What 58/100 proves

The current matrix assigns full credit to the following rows:

- LG01 state/input/output/context schemas;
- LG04 static topology and barriers;
- LG05 conditional routing;
- LG06 BSP supersteps and step atomicity;
- LG07 dynamic Send and map-reduce;
- LG08 Command update/goto/parent/resume;
- LG09 cycles and recursion bounds;
- LG14 checkpoint protocol;
- LG15 thread continuity and resume;
- LG16 state inspection/history/replay;
- LG17 update/fork/time travel;
- LG18 durability ordering and process-restart recovery;
- PERF01 bounded comparison workloads.

This list reflects the current signed matrix, not a fresh rerun on current main. The active-track summary specifically highlights the six core cards completed by PR #1002: LG01, LG04, LG06, LG07, LG08, and LG09.

The highest-risk remaining matrix gaps include:

| Row | Current result | Production consequence |
|---|---:|---|
| LG10 reducers/channels | 1/2 | concurrent state semantics remain incomplete |
| LG12 invocation | 1/2 | public sync/async/stream contract incomplete |
| LG13 batch/concurrency | 0/2 | no qualified batch or max-concurrency surface |
| LG19-LG20 interrupts | 0/2 | human-in-loop pause/resume incomplete |
| LG21-LG22 streaming | 0/2 | durable typed streaming incomplete |
| LG23 subgraphs | 0/2 | nested execution semantics incomplete |
| LG24 retries | 0/2 | retry selection, backoff, jitter, and write clearing unproven |
| LG25 timeout | 0/2 | hard/idle/heartbeat interaction unproven |
| LG26 error semantics | 1/2 | cancellation and handlers incomplete |
| LG30 runtime/config | 0/2 | propagation and runtime injection incomplete |
| LG31 lifecycle callbacks | 0/2 | operational event surface incomplete |
| LG35 drain | 0/2 | checkpointed shutdown/continuation absent |
| APP01-APP04 | 1/2 each | application oracle does not exercise the neutral engine |
| PB01 | 0/2 | prebuilt agent/tool layer is not parity-qualified |

See reports/governance/dharmagraph_parity/PARITY_MATRIX.md:5-36 and :42-82.

#### 10.1.4 Evidence inconsistency that MUST be reconciled first

The intent record and measurement record disagree at the per-card level:

- ACTIVE_TRACK describes LG14 as 1/2, LG15 as 0/2, and LG18 as 1/2 at lines 1153, 1157, and 1169.
- The current derived PARITY_MATRIX describes LG14, LG15, and LG18 as 2/2 at lines 55, 56, and 59.

This does not make 58/100 disappear. It means the portfolio intent projection is stale relative to the sealed measurement detail.

The first production packet MUST:

1. run the committed gauntlet check on a clean current-main checkout;
2. confirm that the relevant-source manifest still reproduces the stable digest;
3. emit a new builder receipt if relevant source or dependencies changed;
4. obtain an independent judge rerun and ratification;
5. regenerate the parity matrix mechanically;
6. reconcile ACTIVE_TRACK card text to the newly sealed evidence without changing its intent authority.

For score facts, a fresh mechanically generated and independently signed receipt is the measurement authority. ACTIVE_TRACK remains the authority for campaign scope and closure policy. A conflict is a release blocker; agents MUST NOT silently choose the more flattering record.

#### 10.1.5 Current source facts relevant to production qualification

The current graph package contains explicit modules for compiler, executor, scheduler, state, channels, persistence, checkpoints, routing, interrupts, effects, receipts, reconciliation, and subgraphs.

Verified implementation anchors include:

- concurrent asyncio superstep task execution: dharma_swarm/graph/executor.py:124-182;
- conditional sync-call isolation through `asyncio.to_thread` only when the
  caller requests `sync_in_thread=True`: dharma_swarm/graph/executor.py:360-380;
- one state write application point: dharma_swarm/graph/state.py:88-155;
- channel validation and commit contracts: dharma_swarm/graph/channels.py:99-131;
- reducer folding/commit: dharma_swarm/graph/channels.py:213-275;
- async invocation with thread_id and checkpoint_id: dharma_swarm/graph/scheduler.py:104-157;
- checkpoint records and pending writes: dharma_swarm/graph/persistence.py:72-146;
- per-thread file locking: dharma_swarm/graph/persistence.py:148-225 and dharma_swarm/graph/_persistence_lock.py:22-35;
- checkpoint resolution and resume: dharma_swarm/graph/persistence_runtime.py:65-162;
- idempotent dispatch claims and CAS reclaim: dharma_swarm/graph/durable_invoker.py:416-638;
- single-host reconciliation doctrine: dharma_swarm/graph/reconciler.py:1-15;
- heartbeat lease inference without a distributed fencing token: dharma_swarm/graph/reconciler.py:375-397;
- a simulated clock/random/dispatch-order provider whose own module says the full fault menu is later work: dharma_swarm/graph/effects.py:1-7 and :69-103.

A bounded scan of all Python files under dharma_swarm/graph at main head found:

- zero tenant or tenant_id occurrences;
- zero explicit authentication/authorization/principal/ACL occurrences;
- zero HMAC/KMS/encryption occurrences;
- zero OpenTelemetry or Prometheus instrumentation occurrences;
- lease wording only in the single-host reconciler, with no persisted fence token.

This negative scan does not prove that upstream services provide no security. It proves that security, multitenancy, cryptographic checkpoint authenticity, and production telemetry are not self-contained or qualified properties of the graph package. DG-P3 below therefore starts as **NOT_IMPLEMENTED**.

---

### 10.2 Named production profiles

A production claim MUST name one exact profile. The bare statement “DharmaGraph is production-grade” is prohibited.

#### 10.2.1 DG-P0 — LAB

Purpose: local development, hermetic oracle runs, deterministic simulation, and benchmark work.

Allowed:

- in-memory or local-file persistence;
- single process;
- synthetic data;
- mocked or sandboxed effects;
- manual recovery.

Prohibited:

- live consequential side effects;
- customer data;
- production availability claims;
- multitenant claims.

DG-P0 is never production-ready, even if every parity test passes.

#### 10.2.2 DG-P1 — SINGLE_TENANT_DURABLE

Purpose: one tenant, one authoritative writer domain, one region, bounded low-risk workloads.

Mandatory properties:

- immutable node input and delta-return contract;
- deterministic reducer barrier;
- durable atomic superstep commit;
- exact checkpoint resume;
- stable effect identity and effect reconciliation;
- bounded retry, timeout, cancellation, and cycle policies;
- durable event stream with cursor resume;
- authenticated service identity;
- encryption in transit and at rest;
- documented backup/restore;
- operator-visible quarantine and dead-letter queues;
- SLO dashboards and paging.

DG-P1 MAY use one active runtime leader, but leadership MUST be explicit and fenced. A process-local or file lock alone is insufficient once two hosts or containers can reach the same state.

#### 10.2.3 DG-P2 — SINGLE_REGION_HA

Purpose: one tenant or a set of administratively isolated single-tenant deployments, multiple runtime workers, one authoritative region.

DG-P2 adds:

- durable external database or log with transactional compare-and-swap;
- lease epoch or monotonic fencing token on every commit;
- automatic worker failover;
- admission backpressure and fair scheduling;
- zero-downtime schema migration;
- cooperative drain and checkpointed continuation;
- tested process, host, network, and database failover;
- regional backup with rehearsed restoration;
- canary and rollback automation.

No active-active ownership of one thread is allowed. Multiple workers MAY execute disjoint tasks, but only a current fenced owner may commit a thread superstep.

#### 10.2.4 DG-P3 — MULTI_TENANT_REGULATED

Purpose: shared infrastructure serving mutually untrusted tenants or regulated workloads.

DG-P3 adds:

- tenant identity as a mandatory storage and authorization dimension;
- row/key namespace isolation and deny-by-default policy;
- workload identity, short-lived credentials, and audited operator elevation;
- per-tenant encryption context and key rotation;
- secret reference resolution outside graph state;
- retention, deletion, legal-hold, and export controls;
- per-tenant quotas and noisy-neighbor isolation;
- redaction and data-classification enforcement;
- authenticated and tamper-evident checkpoints and receipts;
- security incident response and tenant-scoped forensics;
- disaster recovery requirements for the declared failure domains.

Cross-tenant state, stream, cache, checkpoint, receipt, or effect visibility is a severity-zero invariant violation and an automatic rollback trigger.

#### 10.2.5 Explicit non-goals

Unless separately ratified, this version does not promise:

1. a byte-for-byte LangGraph API clone;
2. every LangGraph prebuilt or experimental API;
3. distributed transactions with arbitrary external providers;
4. exactly-once effects when a provider offers neither idempotency keys nor reconciliation;
5. arbitrary untrusted Python execution without a sandbox;
6. multi-region active-active execution of the same thread;
7. autonomous topology evolution;
8. automatic bypass of telos, capability, or human-approval gates;
9. deterministic equivalence of nondeterministic LLM text;
10. unlimited graph size, fan-out, state size, event retention, or run duration.

LangGraph exclusions MUST follow the existing active-track rule: each exclusion names exact rubric rows/facets and requires operator ratification. Exclusions remove claimed scope; they do not award implementation credit.

---

### 10.3 Security and multitenancy contract

#### 10.3.1 Mandatory execution identity

Every admitted run MUST carry an immutable ExecutionEnvelope:

| Field | Rule |
|---|---|
| tenant_id | server-derived, never accepted from an untrusted payload without authentication |
| principal_id | authenticated human, service, or delegated agent |
| principal_type | human, service, agent, operator |
| authority_chain | signed delegation lineage and expiry |
| graph_id | logical graph identity |
| graph_version | immutable compiled artifact digest |
| thread_id | tenant-scoped continuity key |
| run_id | unique execution attempt group |
| trace_id | observability correlation key, not an authority token |
| policy_version | immutable policy snapshot used for admission |
| capability_set | least-privilege node/tool/effect scopes |
| data_classification | maximum permitted state/stream classification |
| deadline | absolute execution deadline |
| budget | steps, wall time, tokens, cost, fan-out, state bytes |

The envelope MUST be copied into commit, checkpoint, effect-intent, receipt, and audit metadata. A derived record missing tenant_id, graph_version, run_id, or policy_version MUST fail closed.

Identifiers MUST be server-minted or cryptographically unguessable. Human-readable identifiers MAY be labels but MUST NOT be authorization boundaries.

#### 10.3.2 Authorization points

Authorization MUST be evaluated:

1. at graph admission;
2. before checkpoint read, resume, fork, export, or deletion;
3. before each tool or external effect;
4. before dynamic route targets outside the node’s declared destination set;
5. before cross-graph or parent/subgraph commands;
6. before operator override;
7. again when a paused run resumes if policy or authority changed.

The policy decision MUST include principal, tenant, graph version, node, effect type, data classification, and requested action. A boolean “is_admin” is insufficient.

Revocation MUST be defined:

- queued tasks are denied at dispatch;
- running pure computation MAY reach the next commit boundary;
- effects not yet dispatched are cancelled;
- in-flight external effects transition to canonical `SUCCEEDED`,
  `FAILED_FINAL`, or `UNKNOWN` through reconciliation;
- a revoked run MUST NOT silently continue under a cached decision.

#### 10.3.3 Tenant isolation

Every durable primary key and unique constraint MUST begin with tenant_id or reference a parent that is itself tenant-bound. This includes:

- graph definitions and versions;
- threads and run heads;
- checkpoints and pending writes;
- node/task attempts;
- effect intents and provider idempotency keys;
- outbox events and stream cursors;
- cache keys;
- receipts and audit events;
- quarantine/dead-letter records;
- leases and fence epochs.

Storage APIs MUST accept an authenticated TenantContext object rather than a raw tenant string. Repository methods that omit TenantContext MUST not be callable from production paths.

Database row-level security SHOULD be used as defense in depth. Application predicates alone are not enough. Tests MUST attempt confused-deputy and identifier-substitution attacks through every read/write API.

#### 10.3.4 Secrets and sensitive data

Secrets MUST be represented in graph state only as opaque secret references. Resolution happens immediately before an authorized effect in a dedicated secret provider.

The runtime MUST:

- redact secret values from logs, traces, errors, checkpoints, streams, and receipts;
- prevent model-visible state from receiving credentials by default;
- rotate provider credentials without checkpoint rewriting;
- classify fields and enforce stream projection by audience;
- reject state exceeding the envelope’s data-classification authority.

#### 10.3.5 Cryptographic and transport controls

DG-P1 and above require:

- TLS for all network hops;
- authenticated workload identity between workers and stores;
- encrypted storage volumes and backups;
- checkpoint and event integrity verification;
- key rotation with key-version metadata;
- constant-time verification where secret material is compared;
- protection against replay of operator approvals and resume commands.

DG-P3 requires tenant-specific encryption context or tenant-dedicated keys according to the deployment’s threat model.

A plain SHA-256 content digest detects accidental or adversarial modification only when the expected digest comes from an authenticated trust root. It MUST NOT be presented as a signature.

#### 10.3.6 Untrusted code and tool isolation

Node functions and tools are trusted application code unless a sandbox profile explicitly says otherwise.

If untrusted or tenant-authored code is admitted, it MUST run outside the scheduler process with:

- OS/container isolation;
- read-only base filesystem;
- explicit egress allowlist;
- resource quotas;
- short-lived credentials;
- no direct persistence access;
- signed result envelope;
- hard termination independent of cooperative cancellation.

asyncio timeout around blocking native code is not a hard sandbox timeout.

#### 10.3.7 Abuse, quota, and denial-of-service controls

Budgets MUST be checked both before admission and at every superstep:

- recursion and superstep count;
- fan-out width and total spawned tasks;
- concurrent tasks per tenant and globally;
- state bytes and checkpoint bytes;
- event bytes and retained cursor age;
- external-effect count and cost;
- token and wall-clock budget;
- retry count and cumulative backoff.

Exhaustion produces a typed terminal or waiting state. It MUST NOT leave a run indefinitely RUNNING.

#### 10.3.8 Security qualification tests

DG-P3 cannot promote until all are green:

- tenant A cannot list/get/resume/fork/delete tenant B’s thread;
- a forged tenant_id in state or config is ignored or rejected;
- cache and idempotency keys cannot collide across tenants;
- stream cursors cannot cross tenants;
- checkpoint object-store paths cannot be guessed to bypass policy;
- operator elevation is time-bounded, reasoned, and audited;
- policy revocation stops new effects;
- secret canaries never appear in telemetry or artifacts;
- corrupted or replayed approvals fail closed;
- backup restore preserves isolation and audit lineage.

---

### 10.4 Observability, SLOs, and operability

#### 10.4.1 Event model

Every runtime transition MUST emit a structured GraphRuntimeEvent with:

- schema_version;
- observed_at and monotonic duration where available;
- tenant_id in protected telemetry only, plus a low-cardinality tenant class for shared metrics;
- graph_id and graph_version;
- thread_id, run_id, superstep, node_id, task_id, attempt;
- checkpoint_id and parent_checkpoint_id;
- lease_epoch/fence_token;
- transition and outcome;
- error_class and retry disposition;
- effect_id and effect state when applicable;
- trace_id and span_id;
- state_digest, delta_digest, and event_digest;
- policy_version;
- runtime build SHA and store incarnation.

Payload bodies and raw model content MUST be excluded by default. Debug capture requires explicit policy, retention, and access controls.

#### 10.4.2 Required metrics

At minimum:

- dg_run_admitted_total;
- dg_run_terminal_total by typed outcome;
- dg_run_active;
- dg_queue_depth and dg_queue_age_seconds;
- dg_superstep_duration_seconds;
- dg_superstep_commit_duration_seconds;
- dg_node_duration_seconds;
- dg_checkpoint_bytes and dg_checkpoint_commit_seconds;
- dg_resume_seconds;
- dg_commit_cas_conflict_total;
- dg_fence_rejection_total;
- dg_lease_expiry_total;
- dg_effect_total by state;
- dg_effect_unknown_total;
- dg_effect_duplicate_prevented_total;
- dg_reconcile_age_seconds;
- dg_outbox_lag_seconds;
- dg_stream_subscriber_lag_seconds;
- dg_retry_total;
- dg_timeout_total;
- dg_quarantine_total;
- dg_invalid_route_total;
- dg_budget_exhaustion_total;
- dg_tenant_authorization_denied_total;
- dg_invariant_violation_total.

High-cardinality identifiers MUST be trace/log attributes, not unbounded metric labels.

#### 10.4.3 Tracing

The root span is one graph run. Child spans include admission, superstep, node attempt, persistence commit, effect dispatch, reconciliation, stream publication, checkpoint resume, and operator interaction.

Trace context MUST propagate through queued tasks and effect adapters. Trace IDs MUST NOT be used as idempotency or authority keys.

#### 10.4.4 SLOs

Targets exclude time spent inside a declared external provider unless stated otherwise. Provider latency is measured separately.

| SLI | DG-P1 | DG-P2 | DG-P3 |
|---|---:|---:|---:|
| Runtime admission availability, 30-day | 99.9% | 99.95% | 99.95% |
| Admission latency p99 | 500 ms | 250 ms | 250 ms |
| Commit latency p99 for checkpoint <=256 KiB | 1 s | 500 ms | 500 ms |
| Durable stream publication lag p99 | 5 s | 2 s | 2 s |
| Resume readiness after worker loss, p99 after lease expiry | 60 s | 30 s | 30 s |
| Queue age p99 for admitted normal-priority work | 60 s | 30 s | 30 s |
| Lost acknowledged superstep commits under process/host failure | 0 | 0 | 0 |
| Silent externally duplicated consequential effects | 0 | 0 | 0 |
| Unquarantined UNKNOWN consequential effects | 0 | 0 | 0 |
| Cross-tenant disclosure or mutation | n/a | n/a or 0 | 0 |
| Corrupt checkpoint accepted | 0 | 0 | 0 |

The workload and storage envelope for every latency SLO MUST be published. Percentiles without payload size, concurrency, region, and observation window are invalid.

Disaster-recovery objectives are separate:

- DG-P1: documented backup RPO <=24 h and operator recovery RTO <=4 h unless a stricter service contract applies.
- DG-P2: region backup RPO <=15 min and RTO <=60 min.
- DG-P3: profile-specific RPO/RTO, tested at least quarterly; a claimed RPO 0 across region loss requires synchronous replication and proof.

#### 10.4.5 Error-budget and paging policy

Page immediately on:

- invariant violation;
- cross-tenant access;
- accepted corrupt checkpoint;
- duplicate consequential effect;
- stuck COMMITTING state;
- UNKNOWN effect older than policy threshold;
- inability to fence a stale owner;
- receipt/checkpoint chain verification failure.

Freeze rollout when:

- 1-hour burn exceeds 14.4 times budget;
- 6-hour burn exceeds 6 times budget;
- any zero-tolerance event occurs;
- checkpoint/resume or effect-reconciliation SLO fails in two consecutive windows.

Telemetry outage is a release blocker for canary promotion. “No alerts” is meaningless if event ingestion is broken.

#### 10.4.6 Operational endpoints and runbooks

DG-P1 and above require:

- liveness endpoint: process can make progress;
- readiness endpoint: dependencies available and writer authority valid;
- drain endpoint: stop admission, checkpoint, and relinquish leases;
- per-thread diagnostic projection;
- safe retry/reconcile/quarantine controls;
- capacity and queue dashboard;
- incident runbooks for store outage, lease split-brain, corrupted checkpoint, duplicate/unknown effect, stream backlog, and tenant breach.

Admin operations MUST be authenticated, authorized, idempotent, and receipted.

---

### 10.5 Formal execution model

#### 10.5.1 State variables

For each tenant-scoped thread, model:

- H = current durable head: checkpoint_id, version, superstep, fence_epoch, state_digest;
- S = immutable state snapshot at H;
- R = ready task multiset for the next superstep;
- W = pending task writes keyed by full task identity;
- E = effect records keyed by stable effect_id;
- O = committed outbox records;
- L = current lease owner, epoch, and expiry;
- P = policy snapshot;
- Q = run phase;
- B = remaining budget.

The model SHALL use the closed run, step, and task machines in §8.9. It MAY
introduce abstract labels only through this total projection:

- `ADMITTED` maps to `CREATED | VALIDATING | READY`;
- `RUNNABLE | EXECUTING(k) | COMMITTING(k) | RECOVERING` map to `RUNNING`
  plus the persisted Step state;
- `WAITING_FOR_INPUT` maps to `WAITING`;
- operator pause maps to `SUSPENDED`;
- `CANCELLING` maps to `CANCELLING`;
- terminal labels map exactly to `SUCCEEDED | FAILED | CANCELLED | QUARANTINED`.

The abstraction SHALL NOT create new legal transitions. Completion requires
the explicit HALT/termination proof of I-10 and §8.6.2; no-ready work is not a
finish condition. Terminal states are monotonic. Reopening requires a new run
or an explicitly authorized same-operation repair with the ownership transfer
defined in the durability part.

#### 10.5.2 Commit bundle

A node never commits shared state directly. It returns a NodeOutcome:

- delta writes;
- route decisions;
- new task intents;
- external effect intents;
- custom stream events;
- interrupt or wait intent;
- typed error.

The scheduler constructs one CommitBundle for a superstep:

- tenant/thread/run identity;
- expected parent head and expected fence epoch;
- canonical ordered task outcomes;
- validated reducer results;
- next ready-task set;
- checkpoint snapshot/delta and integrity metadata;
- effect intents;
- outbox events;
- budget decrement;
- terminal/waiting transition.

The persistence layer accepts a CommitBundle only through one fenced compare-and-swap transaction.

#### 10.5.3 Safety invariants

The formal model and executable tests MUST prove:

**Q-I01 — Single head.** At most one child checkpoint is accepted as the canonical successor of a given head/version.

**Q-I02 — Fenced ownership.** A commit from lease epoch e is rejected after any lease epoch greater than e has been issued.

**Q-I03 — Step atomicity.** A superstep’s state, task frontier, checkpoint metadata, effect intents, outbox records, and budget transition become visible together or not at all.

**Q-I04 — Immutable observation.** All tasks in superstep k observe the same snapshot S(k). No task can observe a sibling’s uncommitted mutation.

**Q-I05 — Deterministic reduction.** Given graph version, parent snapshot, canonical task identities, and deltas, the next snapshot digest is deterministic. Noncommutative reducers require a declared canonical order.

**Q-I06 — Stable effect identity.** Retries and recovery derive the same effect_id for the same logical effect. A new logical attempt receives a new attempt identity without losing lineage.

**Q-I07 — Effect honesty.** A run cannot claim effect success unless the effect
is canonical `SUCCEEDED`. Ambiguous non-idempotent effects become `UNKNOWN` and
quarantine; they are never blindly retried.

**Q-I08 — Route closure.** Every route target belongs to the compiled destination set or a typed dead-letter policy. An invalid target cannot silently become a node name.

**Q-I09 — Exact resume.** Resume from checkpoint c begins from the committed
state/frontier after c without re-executing committed ancestors. An uncovered
task in the current incomplete frozen step may retry under its attempt policy;
that is not ancestor replay.

**Q-I10 — Checkpoint authenticity.** Corrupt, cross-tenant, wrong-version, or untrusted-store-incarnation checkpoints fail closed.

**Q-I11 — Tenant noninterference.** Operations for tenant A cannot change observations for tenant B except through explicitly shared, separately authorized resources.

**Q-I12 — Terminal monotonicity.** `SUCCEEDED`, `FAILED`, `CANCELLED`, and
`QUARANTINED` (including reason `UNKNOWN_EFFECT`) cannot transition back to
`RUNNING` under the same `run_id`.

**Q-I13 — Stream truth.** Durable public events correspond to accepted commits or are explicitly marked speculative. Cursor replay never reorders events within a thread.

**Q-I14 — Budget monotonicity.** Consumed steps, time, effects, and cost never decrease during a run.

#### 10.5.4 Liveness properties

Under an available store and fair scheduling:

- an expired owner cannot block a thread forever;
- every admitted task eventually starts, expires, is cancelled, or is rejected by budget/policy;
- every run eventually reaches terminal, waiting, or quarantined state;
- every effect intent eventually reaches canonical `SUCCEEDED`, `FAILED_FINAL`,
  `UNKNOWN`, pre-dispatch `CANCELLED`, or an explicitly modeled compensation
  terminal;
- every committed outbox event is eventually published or alarms;
- drain eventually produces a resumable checkpoint or a typed failure.

Liveness MUST be bounded by explicit timers. “Eventually” without a timeout, alert, or operator state is not an operational guarantee.

#### 10.5.5 Model-checking deliverable

A TLA+, PlusCal, Alloy, or equivalent state-machine model MUST cover at least:

- two workers;
- two concurrent sibling tasks;
- two tenants;
- two fence epochs;
- one crash at every commit/effect boundary;
- retry and cancellation;
- one invalid route;
- one noncommutative reducer;
- one process/store failover.

The model checker MUST search all states within the declared bound and produce:

- invariant list and results;
- counterexample traces;
- tool/version/config;
- model digest;
- source commit;
- a regression test derived from each discovered counterexample.

The model is not a substitute for implementation fault tests; both are required.

---

### 10.6 Fault-injection and conformance qualification

#### 10.6.1 Deterministic fault matrix

Every row requires a replayable seed, exact injection point, expected durable state, expected recovery action, and receipt.

| ID | Injected fault | Required outcome |
|---|---|---|
| F01 | crash before node starts | task remains ready; no write/effect recorded |
| F02 | crash during pure node computation | no partial state; retry follows policy |
| F03 | crash after NodeOutcome, before pending journal | task safely re-executes |
| F04 | crash after pending journal, before commit CAS | recovered outcome replays once by full task identity |
| F05 | crash during commit transaction | old or new bundle is wholly visible, never mixed |
| F06 | crash after commit, before worker acknowledgement | head prevents duplicate commit; next worker resumes from new head |
| F07 | old worker resumes after lease transfer | stale fence is rejected |
| F08 | network partition isolates current worker from store | worker cannot commit or dispatch new effects after authority loss |
| F09 | database primary failover during CAS | one canonical head; retry is safe |
| F10 | checkpoint bytes truncated or digest altered | restore fails closed and alarms |
| F11 | checkpoint from another tenant/version/incarnation | restore denied |
| F12 | crash after effect intent commit, before dispatch | dispatcher eventually sends one logical effect |
| F13 | crash after provider applies effect, before confirmation | provider lookup/idempotency reconciles; otherwise UNKNOWN quarantine |
| F14 | duplicate delivery of effect intent | provider sees same idempotency key; no silent duplicate |
| F15 | outbox publisher crash after publish, before ack | subscriber deduplicates by event_id and cursor remains monotonic |
| F16 | invalid/hallucinated route | typed INVALID_ROUTE failure or declared dead-letter; no hang |
| F17 | cycle never reaches finish | recursion/budget terminal with checkpoint and diagnostic |
| F18 | sibling task fails while another runs | sibling cancellation and write policy match contract; no partial commit |
| F19 | cancellation during node/effect/commit | cancellation is phase-aware; commit/effect truth remains honest |
| F20 | timeout races with successful completion | one deterministic disposition and no double apply |
| F21 | clock jumps forward/backward | leases use server/monotonic semantics; DST seed replays |
| F22 | reducer receives reordered sibling writes | commutative result stable or canonical sequence enforced |
| F23 | tenant quota exhaustion mid-run | typed budget state; other tenants continue |
| F24 | auth revoked while paused | resume reauthorizes and rejects unauthorized effects |
| F25 | telemetry/outbox unavailable | commits follow declared policy; loss is bounded, durable, and alarmed |
| F26 | rolling upgrade changes checkpoint schema | dual reader/migration succeeds or new worker refuses safely |

Zero fault rows may be waived by a builder. A waiver requires operator ratification, a named production profile exclusion, and a documented residual risk.

#### 10.6.2 Semantic conformance matrix

| Contract | Minimum executable proof |
|---|---|
| fan-out state integrity | N sibling deltas with randomized completion orders yield deterministic committed state |
| conflicting last-value writes | compile-time rejection or typed runtime conflict before commit |
| noncommutative reducer | canonical task order proves byte-identical snapshot digest |
| conditional route | all declared targets plus invalid/unhashable/empty/multi-target returns |
| cycle bounds | finite loop, exact-limit completion, over-limit terminal |
| checkpoint resume | kill process at every node/superstep boundary and resume without ancestor replay |
| pending writes | repeated Send targets distinguished by full task identity and multiplicity |
| retries | selection, attempt count, backoff, jitter seed, write clearing |
| timeouts | async, sync-to-thread, uncooperative blocking code, cancellation race |
| streaming | values, deltas, tasks, checkpoints, custom events, cursor reconnect, slow consumer |
| effect idempotency | same logical attempt derives same effect_id across crash and worker takeover |
| UNKNOWN reconciliation | non-idempotent ambiguous result quarantines and requires adjudication |
| tenant isolation | cross-tenant CRUD, cursor, cache, effect, and backup/restore attacks |
| schema migration | old checkpoint to new reader, mixed-version workers, rollback compatibility |
| drain | stop admission, finish/abort bounded work, checkpoint continuation |
| observability | every state transition has trace/event; injected telemetry outage alarms |

#### 10.6.3 Oracle policy

Use LangGraph as an oracle only where the product intentionally claims LangGraph semantics. Dharma-specific guarantees use a frozen Dharma contract.

For nondeterministic LLM nodes, compare:

- transition sequence;
- visible state schema;
- route class;
- effect intents;
- checkpoint lineage;
- termination class;
- declared semantic projections.

Do not require byte-identical model prose unless the model and seed are controlled.

Every oracle workload MUST include:

- a positive arm;
- a broken control that must fail;
- executed behavior rather than import/getattr presence;
- pinned dependency and environment;
- source and rubric digest;
- independent judge replay.

The active track already records a harness weakness: import/getattr-only facets can preserve points for a broken engine, and APP rows can grade the clone rather than the neutral engine. Those findings at docs/governance/ACTIVE_TRACK.yaml:1265-1269 remain production-qualification blockers even if the headline stays 58.

#### 10.6.4 Load, soak, and chaos thresholds

Before DG-P2 canary:

- at least 100,000 deterministic supersteps across property workloads;
- at least 10,000 injected crash schedules;
- no safety-invariant violation;
- 24-hour soak at expected peak concurrency;
- 2 times expected burst for 30 minutes without unbounded queue growth;
- checkpoint store filled to expected retention envelope;
- slow stream consumer and reconnect storms;
- database failover and worker rolling restart;
- restore drill from backup into a new store incarnation.

Counts MAY be adjusted after an explicit workload power analysis. Time alone never substitutes for event count, and event count alone never substitutes for soak duration.

---

### 10.7 Rollout and canary gates

#### 10.7.1 Stage R0 — offline qualification

Required:

- work packets Q0-Q10 complete for the target profile;
- formal model green;
- fault and conformance matrices green;
- parity receipt freshly replayed and sealed;
- zero unresolved severity-0/1 defects;
- runbooks exercised in staging;
- checkpoint migration/rollback rehearsal;
- security threat model and review.

Exit artifact: OFFLINE_QUALIFIED receipt. It is not a live-production claim.

#### 10.7.2 Stage R1 — shadow, effects suppressed

Run legacy and DharmaGraph on the same production-shaped inputs. DharmaGraph MUST use a physically or logically isolated effect adapter that cannot call live providers.

Minimum gate:

- seven days and at least 1,000 representative runs;
- 100% normalized transition/terminal-state agreement for deterministic workloads;
- every nondeterministic divergence classified;
- zero state-integrity, tenant, or checkpoint violations;
- SLO telemetry complete;
- recovery drills during the shadow window.

The current ascent plan already proposes a default-off workflow.py shadow seam; that plan is directionally compatible but is not proof it landed.

#### 10.7.3 Stage R2 — internal canary

Scope:

- one internal tenant;
- reversible, low-consequence effects;
- strict allowlisted graphs;
- 72 hours and at least 100 completed runs.

Promotion requires zero zero-tolerance events and SLO compliance.

#### 10.7.4 Stage R3 — one-percent canary

Scope:

- <=1% eligible runs;
- no high-consequence non-idempotent effects;
- automatic rollback switch;
- on-call coverage.

Minimum duration: seven days and 10,000 supersteps, unless traffic is lower and the operator ratifies an evidence-equivalent window.

#### 10.7.5 Stages R4-R6 — 10%, 50%, 100%

Each stage requires:

- at least one full error-budget window;
- no unresolved upward trend in queue age, commit latency, UNKNOWN effects, or recovery time;
- successful worker restart and database-failover exercise;
- checkpoint compatibility with both current and rollback binary;
- independent promotion approval.

Recommended minimum dwell:

- R4 10%: seven days;
- R5 50%: fourteen days;
- R6 100%: fourteen additional days before legacy retirement.

Legacy retirement is a separate operator decision. Successful 100% routing does not authorize immediate deletion of rollback paths.

#### 10.7.6 Automatic abort conditions

Any stage automatically stops new DharmaGraph admission on:

- invariant violation;
- cross-tenant event;
- duplicate consequential effect;
- accepted corrupt checkpoint;
- two canonical heads for one thread;
- stale owner commit accepted;
- UNKNOWN consequential effect not quarantined;
- loss of required telemetry;
- recovery time above hard limit;
- schema incompatibility with rollback binary.

The response sequence is:

1. stop admission;
2. preserve evidence;
3. drain/checkpoint where safe;
4. fence compromised workers;
5. route eligible new work to legacy;
6. reconcile in-flight effects;
7. incident review and new regression seed;
8. independent approval before re-entry.

#### 10.7.7 Upgrade and rollback law

Every checkpoint and event has schema_version, graph_version, runtime_build, and store_incarnation.

Before rollout:

- new binary reads N and N-1 checkpoint versions;
- rollback binary reads checkpoints written during the canary, or the rollout is one-way and explicitly operator-gated;
- migrations are idempotent and restartable;
- dual-write periods have one declared read authority;
- mixed-version workers cannot bypass fencing;
- destructive migrations occur only after legacy retirement and backup verification.

---

### 10.8 Implementation work packets and dependency DAG

`Q0` through `Q12` are stable work-packet identifiers, not decimal subsection
numbers. They remain stable if prose subsections are inserted.

The work is deliberately packetized so disconnected agents can operate without inventing their own architecture.

#### 10.8.Q0 — Re-baseline evidence truth

Dependencies: none.

Owned surfaces:

- docs/governance/ACTIVE_TRACK.yaml;
- scripts/governance/dharmagraph_parity_gauntlet.py;
- docs/langgraph_parity;
- reports/governance/dharmagraph_parity;
- tests/test_dharmagraph_parity_gauntlet.py.

Deliver:

- clean-main gauntlet replay;
- reconciliation of ACTIVE_TRACK versus PARITY_MATRIX card detail;
- current dependency drift audit;
- execute-or-zero broken-engine control;
- application scenarios routed through the neutral engine or operator-ratified exclusion;
- new builder receipt and independent judge receipt.

Exit: one internally consistent baseline with immutable commit and receipt digests.

#### 10.8.Q1 — Runtime contract and identity spine

Dependencies: Q0.

Primary surfaces:

- dharma_swarm/graph/types.py;
- dharma_swarm/graph/schema.py;
- dharma_swarm/graph/compiler.py;
- new versioned contract modules as needed.

Deliver:

- ExecutionEnvelope;
- NodeOutcome and CommitBundle;
- typed run/effect/route/error states;
- graph and schema versioning;
- compatibility policy;
- budget contract;
- serialization schemas.

Exit: contract tests and schema golden files; no executor behavior change required yet.

#### 10.8.Q2 — Immutable reducer and commit preparation

Dependencies: Q1.

Primary surfaces:

- dharma_swarm/graph/state.py;
- dharma_swarm/graph/channels.py;
- dharma_swarm/graph/executor.py;
- dharma_swarm/graph/scheduler.py.

Deliver:

- deep immutable snapshot or persistent data contract;
- delta-only node output;
- canonical task identity/order;
- validate-all-then-apply-once reducer barrier;
- conflict policy per channel;
- deterministic state/delta digests.

Exit:

- randomized fan-out tests;
- mutation escape tests;
- noncommutative reducer tests;
- failure leaves parent state byte-identical.

#### 10.8.Q3 — Fenced durable commit kernel

Dependencies: Q1 and Q2.

Primary surfaces:

- dharma_swarm/graph/persistence.py;
- persistence_adapter.py;
- persistence_runtime.py;
- _persistence_io.py;
- _persistence_lock.py;
- store-specific migration modules.

Deliver:

- authoritative head row;
- transactional compare-and-swap;
- monotonic fence epoch;
- lease acquire/renew/release;
- atomic CommitBundle storage;
- outbox in same transaction;
- store incarnation;
- durable database backend for DG-P2/P3.

Exit:

- two-worker linearizability tests;
- stale-writer rejection;
- database failover test;
- no split head in 10,000 race schedules.

#### 10.8.Q4 — Effect journal, idempotency, and reconciliation

Dependencies: Q1 and Q3.

Primary surfaces:

- dharma_swarm/graph/durable_invoker.py;
- effects.py;
- receipt_authority.py;
- receipt_chain.py;
- reconciler.py;
- provider adapters.

Deliver:

- stable effect_id vocabulary;
- provider idempotency adapter;
- effect state machine;
- confirmation lookup;
- UNKNOWN quarantine;
- saga/compensation hooks;
- durable reconciler with fenced ownership.

Exit:

- F12-F14 green for every provider class;
- no blind retry for ambiguous non-idempotent effects;
- reconciliation SLO dashboard.

#### 10.8.Q5 — Authenticated checkpoints and exact resume

Dependencies: Q2 and Q3.

Primary surfaces:

- dharma_swarm/graph/checkpoint.py;
- persistence.py;
- persistence_runtime.py;
- serializer and migration modules.

Deliver:

- versioned authenticated checkpoint envelope;
- parent lineage and state/frontier digests;
- pending-write identity/multiplicity;
- exact checkpoint-ID resume;
- fork/time-travel authority checks;
- schema migration and rollback readers;
- corruption and cross-incarnation rejection.

Exit:

- process kill at every commit boundary;
- no re-execution of completed ancestors;
- corrupted/cross-tenant checkpoint tests;
- backup/restore drill.

#### 10.8.Q6 — Async API, streaming, cancellation, and backpressure

Dependencies: Q1, Q3, Q5.

Primary surfaces:

- dharma_swarm/graph/scheduler.py;
- executor.py;
- types.py;
- new streaming/outbox projection module;
- public workflow adapter.

Deliver:

- ainvoke and typed invoke policy;
- durable astream with cursor resume;
- bounded queues;
- slow-consumer policy;
- batch/as-completed/max-concurrency interfaces if in scope;
- structured cancellation;
- cooperative drain.

Exit:

- LG12, LG13, LG21, LG22, LG31, and LG35 target facets either proven or ratified out;
- no event-loop blocking in instrumented workloads;
- reconnect and cancellation race matrix green.

#### 10.8.Q7 — Routing, cycles, interrupts, retry, timeout, and errors

Dependencies: Q1 and Q2. Q7 retry persistence also depends on Q3.

Primary surfaces:

- dharma_swarm/graph/routing.py;
- compiler.py;
- interrupts.py;
- executor.py;
- scheduler.py.

Deliver:

- closed destination sets;
- invalid-route dead-letter/failure policy;
- recursion and total-budget guards;
- retry policy with deterministic jitter;
- hard/idle/heartbeat timeout semantics;
- sibling/user cancellation;
- static and dynamic interrupt/resume.

Exit:

- F16-F22 green;
- relevant LG02, LG03, LG19, LG20, LG24, LG25, and LG26 facets proven.

#### 10.8.Q8 — Security and multitenancy

Dependencies: Q1 and Q3; effect authorization integrates Q4.

Primary surfaces:

- new graph identity/policy/security modules;
- every persistence schema and repository;
- every stream/cache/effect key;
- operator API and secret provider.

Deliver:

- TenantContext and authority chain;
- deny-by-default policy enforcement;
- row/key isolation;
- encryption and integrity key management;
- secret references and redaction;
- quotas;
- audited operator elevation;
- retention/deletion/hold controls.

Exit:

- threat model reviewed;
- security test list in §10.3.8 green;
- penetration test findings closed;
- zero direct production repository APIs without TenantContext.

#### 10.8.Q9 — Telemetry and operational control plane

Dependencies: Q1; integrates continuously with Q2-Q8.

Primary surfaces:

- new telemetry and health modules;
- GraphRuntimeEvent;
- dashboards, alerts, and runbooks;
- admin control API.

Deliver:

- metrics/traces/events in §10.4;
- readiness/liveness/drain;
- per-thread diagnostic read model;
- SLO and burn-rate alerts;
- evidence-preserving incident controls.

Exit:

- telemetry completeness tests;
- outage injection pages correctly;
- all zero-tolerance events produce a durable incident artifact.

#### 10.8.Q10 — Formal model and deterministic chaos

Dependencies: Q2-Q9 contracts stable.

Primary surfaces:

- formal model directory;
- dharma_swarm/graph/effects.py or extracted simulated-effects modules;
- tests/test_graph_pregel_properties.py;
- tests/test_graph_chaos_receipt.py;
- new fault-matrix tests and reports.

Deliver:

- model in §10.5;
- replayable fault scheduler;
- F01-F26;
- semantic matrix;
- load/soak harness;
- regression seed corpus.

Exit: all mandatory invariants and target-profile thresholds green.

#### 10.8.Q11 — Application shadow seam

Dependencies: Q4-Q10.

Primary surfaces:

- dharma_swarm/workflow.py;
- tests/oracle_support/scenarios.py;
- tests/oracle_support/outcomes.py;
- bounded integration adapters.

Deliver:

- default-off neutral-engine adapter;
- effect-suppressed shadow;
- normalized comparator;
- divergence receipts;
- per-graph allowlist and kill switch.

Exit: R1 gates pass. APP01-APP04 must exercise the neutral engine before receiving full integration credit.

#### 10.8.Q12 — Canary, disaster recovery, and ratification

Dependencies: Q11.

Primary surfaces:

- deployment configuration;
- migrations;
- rollout automation;
- dashboards/runbooks;
- immutable promotion receipts.

Deliver:

- R2-R6 automation;
- backup/restore and regional recovery drill;
- rollback compatibility;
- on-call ownership;
- final profile qualification.

Exit: independently signed PROFILE_PRODUCTION_READY receipt for exactly one named profile.

#### 10.8.DAG Dependency graph

Critical path:

Q0 → Q1 → Q2 → Q3 → Q4/Q5 → Q6/Q7/Q8 → Q9/Q10 → Q11 → Q12

Safe parallelism:

- Q4 and Q5 after Q3;
- early Q7 routing/compiler work after Q2, with retry persistence after Q3;
- Q8 policy model after Q1, with storage enforcement after Q3;
- Q9 schema after Q1, instrumentation alongside each packet;
- formal-model skeleton after Q1, final Q10 only after contracts stabilize.

No packet may bypass Q0 by assuming the remembered 58/100 card distribution is current.

---

### 10.9 Evidence, independent judgment, and ratification

#### 10.9.1 Evidence bundle

Every packet and promotion stage produces an immutable evidence manifest containing:

- repository and exact source commit;
- clean/dirty status;
- graph/runtime schema versions;
- dependency lock and relevant package versions;
- compiler/platform/store versions;
- test and workload manifests;
- exact commands and exit codes;
- raw artifact paths and SHA-256 digests;
- fault seeds and injection points;
- SLO observation window and sample counts;
- known deviations and exclusions;
- builder identity;
- independent judge identity and attestation;
- operator ratifications;
- expiry/revalidation conditions.

Screenshots and prose summaries MAY aid review but are not primary evidence.

#### 10.9.2 Separation of duties

- Builder emits implementation evidence.
- Independent judge reruns from a clean checkout and signs the stable measurement digest.
- Security reviewer signs the threat model and security test result for DG-P3.
- Operator alone ratifies scope exclusions, consequential-effect policy, risk acceptance, and production promotion.
- The author of a code change MUST NOT be its sole judge.

An agent name in JSON is not authentication. Judge authority MUST bind to a repository-controlled trust root or an external authenticated signing system.

#### 10.9.3 Revalidation triggers

Evidence expires and MUST be re-emitted when any of these change:

- relevant source roots;
- rubric or conformance contract;
- runtime/compiler/provider dependency;
- persistence schema or serializer;
- graph compiler output;
- effect identity algorithm;
- authorization policy;
- checkpoint format;
- deployment topology;
- fault-injection harness;
- target production profile;
- latest-reference drift that changes a claimed semantic.

Time-based TTLs:

- parity/conformance: 30 days maximum while active development continues;
- security scan: 30 days and after dependency/policy change;
- restore drill: quarterly;
- regional failover drill: quarterly for DG-P3, semiannual for DG-P2;
- production SLO evidence: rolling 30-day window.

#### 10.9.4 Production admission gate

LangGraph parity is one input, not the final gate.

PROFILE_PRODUCTION_READY requires:

1. parity closeout at 100/100 or an operator-ratified exact non-goal set, preserving the active-track rule;
2. 100% of applicable safety invariants;
3. 100% of applicable security isolation tests;
4. all F-matrix rows applicable to the named profile;
5. no unresolved severity-0/1 defect;
6. shadow and canary gates;
7. SLO/error-budget compliance;
8. backup/restore and rollback proof;
9. independent judge and operator signatures;
10. an explicit production profile and deployment topology.

A reviewed production specification satisfies none of these ten gates by itself.

---

### 10.10 Disconnected-agent handoff protocol

Conversation context is not an artifact store. The authoritative handoff MUST be a remote Git commit.

#### 10.10.1 Minimum handoff coordinates

Send every agent:

- repository: AIKAGRYA/dharma_swarm;
- branch or PR URL;
- exact commit SHA;
- specification path;
- specification file digest;
- baseline main SHA used by the document;
- packet ID;
- declared owned surfaces;
- dependency status;
- verification commands;
- evidence paths;
- explicit claim state.

Agents MUST fetch the exact commit before reading. “Use the latest” is not reproducible.

#### 10.10.2 Machine-readable handoff template

    schema: dharmagraph.production_handoff.v1
    repository: AIKAGRYA/dharma_swarm
    base_sha: <immutable-main-sha>
    artifact:
      path: docs/plans/DHARMAGRAPH_PRODUCTION_RUNTIME_SPEC_v1_1_RECONSTRUCTED.md
      commit_sha: <commit-containing-artifact>
      sha256: <file-digest>
      status: PROPOSED_NOT_IMPLEMENTED
    current_measurement:
      langgraph_parity: 58.00/100
      receipt_source_sha: c83df531c32ce7c775f27ddfbc7512e1cc952db7
      verdict: NOT_FINISHED
      production_claim: CLOSED_NOT_PROD
    packet:
      id: Q<n>
      depends_on: [<packet-ids>]
      owned_surfaces: [<paths>]
      forbidden_surfaces: [<paths>]
    invariants: [I<n>, ...]
    verify:
      - <exact-command>
    evidence_outputs:
      - <path>
    blockers:
      - <typed-blocker-or-empty>
    next_action: <one-bounded-action>

#### 10.10.3 Agent start procedure

Every new agent SHALL:

1. fetch the immutable handoff commit;
2. run repository onboarding and inspect current git status;
3. compare current main with base_sha;
4. read ACTIVE_TRACK, the production spec, PARITY_MATRIX, judge receipt, and the packet’s source modules;
5. run the packet’s done-block before editing;
6. stop if dependencies are not merged or surfaces conflict;
7. implement one bounded slice;
8. run verification;
9. commit code and evidence together where custody permits;
10. push a dedicated branch and update a draft PR;
11. never claim a later evidence state than it earned;
12. never merge its own qualification evidence.

Recommended initial commands:

    make onboard
    bash scripts/governance/run_python_with_repo_env.sh \
      scripts/governance/dharmagraph_parity_gauntlet.py --check
    git status --short
    git rev-parse HEAD

#### 10.10.4 Copy-paste human handoff

    Work in AIKAGRYA/dharma_swarm at commit <sha>.
    Read docs/plans/DHARMAGRAPH_PRODUCTION_RUNTIME_SPEC_v1_1_RECONSTRUCTED.md in full.
    The current judge-signed LangGraph-parity baseline is 58.00/100 with
    verdict NOT_FINISHED and claim boundary CLOSED_NOT_PROD. The production
    specification is a proposed contract, not evidence that implementation
    moved above 58 or became production-ready.

    Execute packet <Qn> only. Respect its dependency and surface boundaries.
    Re-run its done-block from a clean checkout, preserve all failing evidence,
    emit a builder receipt, and request an independent judge. Do not merge and
    do not weaken a gate to obtain a green result.

#### 10.10.5 Publication safety rule

Before any long review session:

1. create the artifact;
2. compute its digest;
3. commit it on a dedicated branch;
4. push;
5. open a draft PR;
6. only then begin iterative review.

An untracked local file is not delivered work.

---

### 10.11 Final release checklist

The release authority MUST answer every item with evidence:

- [ ] Exact production profile named.
- [ ] Spec committed, pushed, and digest-pinned.
- [ ] Q0 current-main evidence reconciliation complete.
- [ ] Fresh builder and independent judge receipts MATCH.
- [ ] ACTIVE_TRACK and derived matrix no longer disagree.
- [ ] Applicable parity rows full or exact non-goals operator-ratified.
- [ ] Q-I01 through Q-I14 proven by model and executable tests.
- [ ] F01-F26 applicable rows green.
- [ ] Tenant/security gates green for DG-P3.
- [ ] No secret or customer payload leakage in telemetry.
- [ ] SLO dashboards and burn alerts live.
- [ ] Readiness, drain, quarantine, and reconcile controls exercised.
- [ ] Backup restore completed into a fresh store incarnation.
- [ ] Rollback binary reads canary checkpoints or rollout marked one-way.
- [ ] Shadow gate passed.
- [ ] Canary dwell/count gates passed.
- [ ] Zero unresolved severity-0/1 findings.
- [ ] Operator approved consequential-effect policy.
- [ ] Operator and independent judge signed profile promotion.
- [ ] Legacy rollback retained through the post-100% observation window.

Until every applicable item is checked, the only honest conclusion is:

**DharmaGraph has promising, judge-measured execution and durability foundations. It remains CLOSED_NOT_PROD. This specification defines the work and evidence required to change that fact; it does not change the fact itself.**

## 11. Current-source reality map

This section distinguishes existing foundations from work prescribed by this
specification. It is not a substitute for a fresh implementation audit.

### 11.1 Existing foundations

- Candidate/test-only status is explicit in
  `dharma_swarm/graph/__init__.py:1-10`,
  `dharma_swarm/graph/scheduler.py:1-30`, and
  `dharma_swarm/graph/executor.py:1-16`.
- User snapshots deep-copy committed channel values in
  `dharma_swarm/graph/state.py:161-176`; per-task branch views clone channel
  objects in `dharma_swarm/graph/state.py:199-219`.
- Writes group, validate, and commit by channel in
  `dharma_swarm/graph/state.py:88-118`; reducer validation and commit are
  separate executions in `dharma_swarm/graph/channels.py:213-265`.
- Parallel task execution uses `asyncio` and cancels siblings on first failure
  in `dharma_swarm/graph/executor.py:124-237`.
- Conditional routes reject `None`, invalid types, unmapped keys, `START`, and
  `Send(END)` in `dharma_swarm/graph/routing.py:295-352`.
- The scheduler accepts checkpoint callbacks and filesystem persistence in
  `dharma_swarm/graph/scheduler.py:104-197`, restores channels and
  `versions_seen` in `dharma_swarm/graph/scheduler.py:199-211`, and journals
  writes before applying them in `dharma_swarm/graph/scheduler.py:380-408`.
- The persistence kernel serializes per-thread checkpoint and pending-write
  lists under a file lock in `dharma_swarm/graph/persistence.py:148-226` and
  `dharma_swarm/graph/persistence.py:327-366`.
- `RunCheckpoint` contains run/graph IDs, superstep, state digest, channel
  snapshots, and `versions_seen` in `dharma_swarm/graph/types.py:111-140`.

### 11.2 Production gaps this specification closes

- The current public run status vocabulary contains only `completed`
  (`dharma_swarm/graph/types.py:44-48`); production needs the closed lifecycle
  defined below.
- Current quiescence returns `completed` whenever no tasks are ready
  (`dharma_swarm/graph/scheduler.py:343-418`); production requires a verified
  `HALT` termination proof.
- Cyclic execution requires a cap but the public argument is not fully
  canonicalized and durably charged at admission
  (`dharma_swarm/graph/scheduler.py:172-178`,
  `dharma_swarm/graph/scheduler.py:343-365`).
- Slow synchronous nodes without a `Send.timeout` execute inline; only timed
  synchronous sends are moved to a worker thread
  (`dharma_swarm/graph/executor.py:278-300`,
  `dharma_swarm/graph/executor.py:360-393`).
- File locks serialize one file mutation but do not provide a distributed
  run lease, never-reused epoch, branch-head CAS, attempt fence, or provider
  dispatch fence (`dharma_swarm/graph/persistence.py:148-226`).
- The scheduler restores checkpoint state but does not establish a signed graph
  manifest/topology/schema compatibility proof before execution
  (`dharma_swarm/graph/scheduler.py:199-211`,
  `dharma_swarm/graph/types.py:111-140`).
- Auto checkpoint IDs are derived from step and state digest with collision
  suffixing, not from an authoritative branch-head transaction
  (`dharma_swarm/graph/persistence.py:480-492`).
- Current low-level route errors inherit `ValueError`
  (`dharma_swarm/graph/routing.py:56-70`); production persistence must capture
  every typed routing failure through one durable failure path.

## 12. Agent handoff contract

An agent receiving this document SHALL begin with:

1. verify the document commit and SHA-256;
2. verify the reconstruction baseline against current `main`;
3. read `docs/governance/ACTIVE_TRACK.yaml` and the frozen parity matrix;
4. treat every unimplemented `MUST` as open, regardless of prose confidence;
5. select one work packet and preserve its dependency order;
6. emit code, tests, fault evidence, and a machine-readable receipt;
7. never self-ratify production readiness.

Suggested seed:

```text
Repository: AIKAGRYA/dharma_swarm
Artifact: docs/plans/DHARMAGRAPH_PRODUCTION_RUNTIME_SPEC_v1_1_RECONSTRUCTED.md
Artifact commit: <exact commit SHA>

Treat the artifact as a proposed production contract, not evidence that the
runtime exceeds the official 58/100 frozen LangGraph-parity grade. Reconcile
current main against the artifact baseline before editing. Implement only the
selected dependency-ready work packet. Preserve all authority, determinism,
effect, checkpoint, and evidence invariants. Produce replayable evidence and
stop at CLOSED_NOT_PROD unless an operator ratifies a named deployment profile.
```

## 13. Ratification block

```yaml
artifact_status: PROPOSED_NOT_IMPLEMENTED
reconstruction: true
byte_identical_to_lost_v1: false
source_baseline: 12212397be1dbe0a9b0cc29be4311f930140e751
official_frozen_parity_score: 58.00
production_profile_qualified: null
operator_ratified: false
artifact_sha256: RECORDED_IN_COMPANION_SHA256_AND_COMMIT_RECEIPT
artifact_line_count: RECORDED_IN_COMPANION_SHA256_AND_COMMIT_RECEIPT
```

The document cannot contain its own cryptographic digest without a circular
definition. The publisher SHALL create a same-commit companion `.sha256` file
containing the exact digest and line count. No value in this block or its
companion may be changed without an evidence-bearing commit.
