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
`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-40`).

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
and restart recovery. It reports material gaps in node policies, defer/finalize,
message semantics, invocation surfaces, batching, interrupts, streaming,
subgraphs, retry, timeout, error/cancellation semantics, stores, caching,
runtime/config propagation, callbacks, functional APIs, introspection, drain,
application integration, and prebuilts
(`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:5-38`).

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
- `PROFILE_A_QUALIFIED` — single-region/single-authority durable profile passes;
- `PROFILE_B_QUALIFIED` — distributed-authority profile passes;
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

#### Profile A — durable single-store authority

- one canonical SQL store with transactions and store-authoritative time;
- one active coordinator lease per branch/run;
- horizontally scalable workers behind fenced commands;
- process-crash RPO 0 on surviving canonical storage;
- disaster RPO/RTO only as explicitly measured for the storage deployment;
- consequential effects admitted only through qualified provider adapters.

#### Profile B — distributed authority

- replicated strongly consistent metadata store;
- cross-host quota and lease arbitration;
- outbox/broker dispatch with fenced claims;
- externally anchored store-incarnation authority for disaster cutover;
- partition and healed-old-primary tests;
- no claim of multi-region availability until the exact topology is qualified.

Profile A SHALL be qualified before Profile B unless an operator signs an
exception with evidence that the Profile B substrate already satisfies every
Profile A invariant.

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
                        └── LogicalTaskId
                            └── AttemptId
```

Additional stable namespaces:

- `OperationId` — business operation lineage;
- `TaskNamespaceId` — stable task lineage across approved repair/migration;
- `EffectNamespaceId` — stable effect slots across approved repair/migration;
- `StoreIncarnation` — operational authority epoch across disaster cutover;
- `CommandId` and request digest — idempotent external mutations;
- `StreamIncarnation` plus stream sequence — non-aliasing operational cursors.

Recommended derivations use canonical CBOR or an equivalently specified binary
encoding, not language-native object serialization:

```text
LogicalTaskId = H("dg/task/v1", tenant, task_namespace, graph_revision,
                  run_lineage, absolute_step, activation_id, node_id)

AttemptId     = H("dg/attempt/v1", logical_task_id, attempt_ordinal,
                  store_incarnation)

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

- `dharma_swarm/graph/state.py:50-107` owns the mutable in-process channel map and the validate-then-`channel.commit(...)` merge; `state.py:161-176` deep-copies user snapshots.
- `dharma_swarm/graph/channels.py:213-277` implements canonical left-fold reducers, while `channels.py:321-370` stores join progress as one channel-local `_seen` set.
- `dharma_swarm/graph/executor.py:124-180` starts same-superstep tasks concurrently and buffers proposals; `executor.py:360-380` sends only selected synchronous calls to a thread, leaving the ordinary sync path on the caller/event-loop thread.
- `dharma_swarm/graph/routing.py:123-159` defines additive `Command.goto`; `routing.py:295-352` correctly rejects malformed and unmapped branch results before commit.
- `dharma_swarm/graph/types.py:47-48` exposes only `completed`/`ok` run vocabulary; `types.py:111-140` defines resumable channel snapshots.
- `dharma_swarm/graph/scheduler.py:240-250` deliberately resets the recursion budget per invocation; `scheduler.py:343-405` validates, journals, mutates state, and checkpoints as separate process-level operations.
- `dharma_swarm/graph/persistence.py:148-175` uses a file-backed, process-locked persistence kernel; `persistence.py:448-475` confirms path-based JSON state as the durable adapter.

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

All persisted records SHALL carry `schema_version`, `tenant_id`, and `graph_version_id`. IDs SHALL be opaque strings at public boundaries and SHALL have an unambiguous canonical binary encoding internally.

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
TaskId         = H("task", tenant_id, operation_id, task_namespace_id,
                   stable_task_path)
AttemptId      = H("attempt", task_id, attempt_no)
DeltaId        = H("delta", task_id, canonical_node_outcome)
EffectId       = H("effect", tenant_id, operation_id, effect_namespace_id,
                   stable_task_path, effect_slot)
JoinFrameId    = H("join", run_id, join_spec_id, parent_activation_id,
                   generation)
CheckpointId  = H("checkpoint", run_id, state_revision, state_digest,
                   plan_digest)
StreamEventId = H("event", run_id, stream_seq, event_type, payload_digest)
```

`H` SHALL be a domain-separated cryptographic digest over length-delimited canonical fields. Concatenating unescaped strings is forbidden.

#### 8.3.1 Stability requirements

- `RunId` remains constant across suspend/resume and coordinator failover.
- `OperationId` identifies the operator-authorized real-world operation. A retry, crash recovery, or same-operation repair preserves it; an unrelated invocation never reuses it.
- `TaskNamespaceId` and `EffectNamespaceId` are explicit persisted authorities, not values inferred from `RunId` or graph revision.
- `StableTaskPath` is derived from logical parent path, compiled node semantic id, stable activation/send key, and loop/join generation. It SHALL NOT contain attempt number, worker id, coordinator fence, wall time, or graph revision. A graph migration SHALL supply an audited old-to-new semantic path map or refuse same-operation continuation.
- `TaskId` remains constant across retries, worker/coordinator failover, and an explicitly authorized same-operation repair that preserves its task namespace and semantic path.
- `AttemptId` changes for each execution attempt and only after an atomic attempt-number increment.
- `EffectId` SHALL be exactly the domain-separated digest of `(tenant_id, operation_id, effect_namespace_id, stable_task_path, effect_slot)`. It SHALL be independent of `RunId`, `TaskId`, `AttemptId`, worker/coordinator identity, graph revision, and wall time. `effect_slot` is a compile-declared logical operation within the node. Retry and same-operation repair therefore deduplicate the same real-world effect.
- A **same-operation repair** (for example, repair from a quarantined checkpoint under corrected graph code) MUST preserve `OperationId`, `TaskNamespaceId`, and `EffectNamespaceId`; it MUST record repair authority, source run/checkpoint, semantic path migration, and graph-version change. It may execute an effect only after reconciling the preserved `EffectId` to a terminal provider/receipt state.
- An **exploratory fork** MUST mint a new `OperationId`, `TaskNamespaceId`, and `EffectNamespaceId`. Consequential effects SHALL be disabled by default in the fork; enabling them requires a new explicit authority/admission decision. Merely copying a checkpoint SHALL NOT copy permission to repeat real-world effects.
- `dispatch_ordinal` and `Send.ordinal` SHALL be assigned by the committed step plan, never by wall-clock completion order.
- A caller-provided invocation idempotency key SHALL map to exactly one `RunId` within its tenant and graph version. Reusing it with different input bytes SHALL fail with `IDEMPOTENCY_CONFLICT`.

#### 8.3.2 Minimum durable records

```python
@dataclass(frozen=True)
class RunHead:
    tenant_id: str
    thread_id: str
    run_id: str
    operation_id: str
    task_namespace_id: str
    effect_namespace_id: str
    graph_version_id: str
    status: RunStatus
    state_revision: int
    state_digest: str
    checkpoint_id: str
    current_superstep: int
    plan_digest: str | None
    coordinator_fence: int
    budgets_remaining: "BudgetVector"
    stream_seq: int
    updated_at: Instant

@dataclass(frozen=True)
class StepPlan:
    step_id: str
    run_id: str
    superstep: int
    base_revision: int
    base_state_digest: str
    base_checkpoint_id: str
    graph_version_id: str
    tasks: tuple["PlannedTask", ...]
    joins_touched: tuple[str, ...]
    budget_reservation: "BudgetVector"
    plan_digest: str
    coordinator_fence: int

@dataclass(frozen=True)
class PlannedTask:
    task_id: str
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
    task_id: str
    attempt_id: str
    attempt_no: int
    plan_digest: str
    outcome_digest: str
    delta: "StateDelta"
    control: "ControlDecision"
    effect_receipt_refs: tuple[str, ...]
    completed_at: Instant
```

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
    run_id: str
    graph_version_id: str
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

    ops = canonical_sort(flatten(result.delta.ops for result in results))
    validate_all_channels_and_routes(snapshot, ops, results)
    next_snapshot = apply_to_fresh_builder(snapshot, ops)
    require snapshot is byte_identical_to_preimage()

    next_frontier, join_updates, control = route_all(plan, results)
    return CommitBundle(next_snapshot, next_frontier, join_updates, control)
```

`apply_to_fresh_builder` SHALL construct new channel values. It SHALL NOT mutate `snapshot` and roll back on exception. Production implementations MAY use structural sharing, copy-on-write pages, or immutable persistent data structures, provided the old revision remains readable and byte-identical.

Before persistence, the coordinator SHALL re-run schema validation and reducer evaluation from stored immutable result bytes. Trusting a worker-supplied computed post-state is forbidden.

#### 8.4.6 Authoritative barrier transaction

The state merge is committed by one storage transaction equivalent to:

```sql
BEGIN;
SELECT run_head FOR UPDATE;
ASSERT run_head.run_id              = :run_id;
ASSERT run_head.state_revision      = :base_revision;
ASSERT run_head.state_digest        = :base_digest;
ASSERT run_head.plan_digest         = :plan_digest;
ASSERT run_head.coordinator_fence   = :fence;
ASSERT step.status                  = 'READY_TO_COMMIT';

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
       budgets_remaining=:next_budgets,
       status=:next_status,
       stream_seq=:last_stream_seq
 WHERE state_revision=:base_revision
   AND coordinator_fence=:fence;
ASSERT ROW_COUNT = 1;
COMMIT;
```

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

@dataclass(frozen=True)
class JoinFrame:
    frame_id: str
    join_spec_id: str
    run_id: str
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

For `ANY` and `QUORUM`, the selected member set SHALL be derived by canonical member order from all arrivals accepted in the satisfying transaction, not by wall-clock race. Late arrivals are recorded as `LATE_ARRIVAL` and handled by declared policy; they SHALL NOT reopen a frame.

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

- `HALT` requests successful termination after the current barrier commits. It MUST NOT coexist with `goto`, `Send`, an open required join, or unresolved required effect. Such ambiguity is `INVALID_CONTROL`.
- Normal quiescence with no frontier is success only if the graph contract permits quiescent completion and there are no open required waits/joins. Otherwise it is `STRANDED_RUN` and SHALL be quarantined or failed.
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

---

### 8.7 Scheduling, leases, retries, and result acceptance

#### 8.7.1 Coordinator ownership

At most one coordinator fence may advance a run head at a time. Acquiring ownership SHALL atomically increment `coordinator_fence`. Every plan, task lease, staged result, checkpoint commit, wait transition, and event append SHALL carry that fence.

A stale coordinator may continue computing but cannot commit. Storage SHALL reject its compare-and-swap. Lease duration is liveness metadata, while the monotonic fence is the safety mechanism; clocks alone SHALL never establish authority.

#### 8.7.2 Worker task leases

```python
@dataclass(frozen=True)
class TaskLease:
    task_id: str
    attempt_id: str
    attempt_no: int
    worker_id: str
    coordinator_fence: int
    lease_fence: int
    expires_at: Instant
```

- Claiming a task atomically changes it from `PLANNED`/`RETRYABLE` to `LEASED`, increments `attempt_no` and `lease_fence`, and emits an attempt record.
- Heartbeats extend only the currently fenced lease.
- Expiry makes the attempt orphaned and eligible for retry, but does not itself prove the worker stopped.
- Result acceptance requires matching `TaskId`, `AttemptId`, plan digest, coordinator fence lineage, input digest, and active lease fence.
- A result from a stale attempt is retained as diagnostic evidence but cannot affect state.
- If an accepted result already exists for the `TaskId`, an identical `outcome_digest` is idempotent success. A different digest is a nondeterminism/security violation and quarantines the run.

#### 8.7.3 Retry semantics

Retry policies SHALL classify typed failures; `retry all exceptions` is prohibited. The policy includes maximum attempts, exponential backoff with recorded jitter input, retryable codes, and deadline/cost ceilings.

Retries do not advance the superstep and do not change `TaskId`. They consume attempt, time, token, cost, and external-effect budgets. A coordinator restart reconstructs the retry schedule from durable attempt records.

When one task fails while siblings succeed, successful siblings' immutable results MAY remain staged. The step does not commit. On retry/resume, the coordinator reuses valid staged results and runs only uncovered/failed tasks. It SHALL revalidate every reused result against the pinned plan and graph version at final barrier commit.

#### 8.7.4 Cancellation

Cancellation is a durable run-head transition request. The coordinator stops issuing new leases, asks active workers to cancel, waits for policy-bounded drainage, and atomically transitions to `CANCELLED`. Late task results and effects are reconciled but cannot commit graph state. Terminal cancellation is monotonic unless an explicit fork creates a new `RunId`.

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
    wall_deadline: Instant
```

Requirements:

- Run-wide budgets are stored in `RunHead` and may only decrease. Resume, wait/wake, failover, SDK reconnect, and retry SHALL NOT reset them.
- Planning reserves deterministic task/send/node-execution budget. Barrier commit consumes the reservation or releases unused portions under one documented rule.
- Attempts, external effects, tokens, and cost are charged when incurred, even if the superstep fails.
- `remaining_steps` exposed to a node is a managed read-only projection of the durable run-wide budget, never a user-writable state key.
- `max_supersteps` counts committed supersteps plus the currently planned step. A failing/retrying step does not evade attempt and wall-clock budgets.
- Nested subgraphs inherit a bounded child allocation. A child cannot mint budget or exceed its parent's remaining amount.
- Dynamic `Send` and join frame creation SHALL be budget-checked before the producing step commits.
- When any hard budget is exhausted with work still possible, the run transitions to `FAILED(BUDGET_EXHAUSTED)` or `QUARANTINED` according to explicit policy. It SHALL never return ordinary success.
- The runtime SHOULD support a deterministic livelock detector over repeated `(state_digest, frontier_digest, open_join_digest)` tuples. A repeated tuple may terminate earlier with `NO_PROGRESS_CYCLE`; it does not replace hard budgets.

A graph containing a cycle without admitted run-wide budgets SHALL fail compilation/admission. “The model will eventually choose END” is not a termination guarantee.

---

### 8.9 Durable run, step, and task state machines

#### 8.9.1 Run states

```text
CREATED -> VALIDATING -> READY -> RUNNING
                                  |  |
                                  |  +-> WAITING -> RUNNING
                                  |  +-> SUSPENDED -> RUNNING
                                  |  +-> CANCELLING -> CANCELLED
                                  +----> SUCCEEDED
                                  +----> FAILED
                                  +----> QUARANTINED
```

`SUCCEEDED`, `FAILED`, `CANCELLED`, and `QUARANTINED` are terminal for a `RunId`. Recovery from `QUARANTINED` SHALL create an audited repair transition only if policy explicitly permits it, or fork a new run. Direct terminal-to-`RUNNING` updates are forbidden.

The state meanings are:

- `CREATED`: invocation idempotency accepted; no graph validation claimed.
- `VALIDATING`: graph version, input schema, authority, budgets, and tenant admission are being checked.
- `READY`: authoritative initial checkpoint exists; coordinator work may be claimed.
- `RUNNING`: a coordinator fence owns progress; zero or one uncommitted `StepPlan` exists.
- `WAITING`: durable wake condition exists; no user task is considered active.
- `SUSPENDED`: operator/policy pause, distinct from a graph-authored wait.
- `CANCELLING`: cancellation is durable; active attempts are draining/reconciling.
- `SUCCEEDED`: explicit valid `HALT` or permitted quiescence committed with final checkpoint.
- `FAILED`: typed unrecoverable execution failure or exhausted policy.
- `QUARANTINED`: integrity, authority, ambiguity, corruption, nondeterminism, or DLQ condition requiring inspection.

Every transition SHALL be append-recorded with old/new status, cause code, actor/authority, fence, expected revision, and event id.

#### 8.9.2 Step states

```text
PLANNED -> DISPATCHING -> COLLECTING -> READY_TO_COMMIT -> COMMITTED
                         |     |               |
                         |     +-> RETRYING ---+
                         +--------> FAILED / CANCELLED / QUARANTINED
```

Only `COMMITTED` advances `RunHead.state_revision`. A step at `READY_TO_COMMIT` may be committed repeatedly only as an idempotent transaction yielding the same commit/checkpoint digest.

#### 8.9.3 Task states

```text
PLANNED -> LEASED -> RUNNING -> SUCCEEDED_STAGED
             |          +----> RETRYABLE
             |          +----> FAILED
             |          +----> CANCELLED
             +---------------> ORPHANED -> RETRYABLE
```

Task status is not graph state. Staging a success does not expose its delta until barrier commit.

#### 8.9.4 Recovery algorithm

On coordinator acquisition:

1. increment and persist a new coordinator fence;
2. read and verify the run head, checkpoint, state blobs, graph version, budgets, wait/join records, and optional open step;
3. if no open step exists, deterministically plan the next frontier;
4. if an open step exists, verify its plan digest and classify tasks as accepted, leased-live, expired, retryable, or failed;
5. reuse accepted staged outcomes; re-lease only missing/eligible tasks;
6. if exact successful coverage exists, repeat the barrier transaction idempotently;
7. publish/re-publish outbox events from durable cursor state.

Recovery SHALL never infer completion from logs alone, never replay committed nodes 1–6 when resuming a checkpoint before node 7, and never trust an uncommitted in-memory state image.

---

### 8.10 Transaction boundaries and crash semantics

The production storage adapter SHALL expose the following linearizable operations, whether implemented with SQL transactions, a consensus log, or another proven mechanism.

#### 8.10.1 TX-A — Admit invocation

Atomically bind `(tenant_id, invocation_idempotency_key)` to `RunId`, graph version, canonical input digest, initial budget, `CREATED` run record, and audit event. Duplicate identical admission returns the same run; duplicate differing admission fails.

#### 8.10.2 TX-B — Publish step plan

Compare-and-swap the current run revision/fence; reserve budgets; write immutable plan/tasks/activations; set step `PLANNED` and run-head `plan_digest`. No worker sees a task before TX-B commits.

#### 8.10.3 TX-C — Accept task result

Compare task/attempt/lease fence; validate result envelope and blob digests; write immutable outcome and effect receipt references; transition task to `SUCCEEDED_STAGED`. This transaction does not mutate graph state.

#### 8.10.4 TX-D — Commit barrier

Perform §8.4.6: validate exact coverage, recompute reducers/routes, update joins, publish next frontier, consume budgets, append checkpoint and durable stream events, and advance run head in one transaction.

#### 8.10.5 TX-E — Wait/wake or control transition

Create/consume a wait record and transition run state with revision/fence CAS. Wake signal idempotency and next activation creation share the same transaction.

#### 8.10.6 TX-F — Outbox delivery acknowledgment

Advance a subscriber delivery cursor only after delivery according to the selected transport contract. Cursor updates never change graph state.

Crash expectations:

| Crash point | Required recovery behavior |
|---|---|
| Before TX-B commit | No tasks exist; replan from same head |
| After TX-B, before dispatch | Claim persisted tasks |
| During node execution | Lease expires; retry same `TaskId` with new `AttemptId` |
| After external effect, before result | Reconcile by stable effect id; do not blindly repeat |
| After TX-C | Reuse staged result; do not rerun successful task |
| During TX-D | Observe either old head or complete new head, never partial merge |
| After TX-D, before notification | Outbox publisher emits committed events |
| After WAIT commit | Wake condition survives process loss |
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

#### 8.12.1 Required public interfaces

```python
class AsyncCompiledGraph(Protocol):
    async def ainvoke(
        self, input: Mapping[str, Any], *, config: RunConfig
    ) -> GraphRunResult: ...

    async def astart(
        self, input: Mapping[str, Any], *, config: RunConfig
    ) -> RunHandle: ...

    async def aresume(
        self, run_id: str, resume: ResumeInput, *, expected_revision: int
    ) -> RunHandle: ...

    def astream(
        self, run_id: str, *, cursor: StreamCursor | None,
        modes: frozenset[StreamMode]
    ) -> AsyncIterator[StreamEvent]: ...

    async def acancel(
        self, run_id: str, *, reason: str, expected_revision: int | None
    ) -> RunHead: ...
```

`astart` SHALL durably admit work and return without holding an application request open for the entire run. Background progress belongs to durable coordinators/workers, not a process-local `create_task` whose loss abandons the run.

Synchronous convenience APIs MAY exist but SHALL be adapters around the asynchronous/durable interface. They SHALL detect invocation from an already-running event loop and fail with guidance rather than nesting/blocking that loop.

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
class StreamEvent:
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

For each run, durable stream `seq` is strictly increasing and allocated in the same transaction as the state/control transition it describes. Consumers receive at-least-once delivery and deduplicate by `event_id`. `cursor=seq` resumes strictly after that sequence. The server SHALL return a typed `CURSOR_EXPIRED` with the earliest retained checkpoint/event when retention prevents exact replay. `BEST_EFFORT` events SHALL use a separate ephemeral sequence namespace or carry the most recent durable cursor; they SHALL NOT consume durable sequence numbers and create unexplained replay gaps.

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
async def coordinate(run_id: RunId) -> None:
    fence = await store.acquire_run_fence(run_id)
    try:
        while True:
            head = await store.read_verified_head(run_id)
            require head.coordinator_fence == fence

            if head.status in TERMINAL:
                return
            if head.status in {WAITING, SUSPENDED}:
                await store.release_or_park_fence(run_id, fence)
                return
            if hard_budget_exhausted(head):
                await store.fail_budget(run_id, fence, expected=head.state_revision)
                return

            step = await store.read_open_step(run_id)
            if step is None:
                snapshot = await store.load_and_verify_checkpoint(head.checkpoint_id)
                plan = deterministic_plan(snapshot, head, compiled_graph)
                if plan.tasks == ():
                    await store.commit_quiescence_or_stranded(plan, fence)
                    continue
                step = await store.tx_publish_plan(plan, fence, expected=head)

            classification = await store.classify_results_and_leases(step, fence)
            await lease_missing_tasks_bounded(classification, fence)

            if classification.has_permanent_failure:
                await apply_failure_policy(step, classification, fence)
                continue
            if not classification.exact_success_coverage:
                await wait_for_result_lease_or_cancel_event()
                continue

            # Recompute from immutable task result bytes under coordinator code.
            bundle = build_commit_candidate(
                head=await store.read_verified_head(run_id),
                plan=step.plan,
                staged_results=await store.read_staged_results(step.step_id),
                snapshot=await store.load_and_verify_checkpoint(
                    step.plan.base_checkpoint_id
                ),
            )
            await store.tx_commit_barrier(bundle, fence)
    finally:
        await store.best_effort_release_fence(run_id, fence)
```

There is no mutable global state shared by task coroutines, no routing based on task completion order, and no checkpoint written outside the authoritative commit.

---

### 8.14 Core acceptance and adversarial qualification tests

Passing unit tests is necessary but insufficient. The production profile SHALL pass every test below against the real production storage adapter with at least two coordinators and multiple worker processes. Fault tests SHALL run repeatedly with randomized injection points.

#### 8.14.1 State integrity

- **CORE-STATE-001 — malicious in-place mutation:** A node mutates nested dict/list objects in its input then raises. The committed snapshot and digest remain byte-identical.
- **CORE-STATE-002 — retained reference:** A node returns an object and mutates its retained reference after result staging. Stored result bytes and committed state do not change.
- **CORE-STATE-003 — randomized completion:** Execute 100-way fan-out with randomized latency and worker placement 1,000 times. State, checkpoint, next plan, and durable event digests are identical.
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
- **CORE-JOIN-004 — ANY/QUORUM determinism:** Random arrival orders produce the same canonically selected satisfying members.
- **CORE-JOIN-005 — timeout:** Kill all coordinators across a join deadline. Recovery applies the declared timeout policy exactly once.

#### 8.14.3 Routing and cycles

- **CORE-ROUTE-001 — hallucinated key:** Router/LLM returns an unmapped identifier. The step does not commit, the run does not hang, and default production policy creates a typed DLQ record.
- **CORE-ROUTE-002 — malformed command:** Test unknown goto, `START`, `Send(END)`, unbound parent, resume-from-node, unauthorized target, and control/goto conflict; all fail closed.
- **CORE-ROUTE-003 — HALT:** Valid HALT atomically commits its delta, final checkpoint, terminal event, and `SUCCEEDED`; no later task is leased.
- **CORE-ROUTE-004 — WAIT/wake:** Crash before and after wait commit and send the same wake signal concurrently 100 times. Exactly one continuation activation exists.
- **CORE-ROUTE-005 — stranded quiescence:** No frontier plus open required join/wait never returns success.
- **CORE-CYCLE-001 — self-loop cap:** An unconditional self-loop terminates with `BUDGET_EXHAUSTED` at the exact durable count.
- **CORE-CYCLE-002 — resume budget:** Repeated resume/wait cycles never replenish run-wide step/task/effect/cost budgets.
- **CORE-CYCLE-003 — retry budget:** A permanently transient-classified failure cannot retry past attempts/deadline/cost limits.
- **CORE-CYCLE-004 — fan-out bomb:** Exponential sends are rejected before the producing barrier commits when reservations exceed limits.
- **CORE-CYCLE-005 — nested budget:** Child subgraph cannot consume more than its allocated parent slice.

#### 8.14.4 Leases, crashes, and transactions

- **CORE-LEASE-001 — stale worker:** Pause worker A past lease expiry, complete with worker B, then release A. A's late result cannot change state or emit accepted output.
- **CORE-LEASE-002 — stale coordinator:** Partition coordinator A, promote B, then heal A. Only B's fence can commit.
- **CORE-LEASE-003 — attempt identity:** Task ID is stable and attempt IDs strictly change across retry/failover; logical effect IDs remain stable.
- **CORE-TX-001 — crash matrix:** Inject process kill/storage error before and after every durable write in TX-A through TX-F. Observed state always matches the crash table in §8.10.
- **CORE-TX-002 — checkpoint atomicity:** There is no observable run head pointing at a missing checkpoint/blob or checkpoint ahead of the head.
- **CORE-TX-003 — effect ambiguity:** Kill after provider success and before receipt acknowledgment. Reconciliation resolves by stable effect id or quarantines `UNKNOWN`; it does not blindly duplicate.

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

<!-- DURABILITY_SECTION -->

<!-- QUALIFICATION_SECTION -->

## 20. Current-source reality map

This section distinguishes existing foundations from work prescribed by this
specification. It is not a substitute for a fresh implementation audit.

### 20.1 Existing foundations

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

### 20.2 Production gaps this specification closes

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

## 21. Agent handoff contract

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

## 22. Ratification block

```yaml
artifact_status: PROPOSED_NOT_IMPLEMENTED
reconstruction: true
byte_identical_to_lost_v1: false
source_baseline: 12212397be1dbe0a9b0cc29be4311f930140e751
official_frozen_parity_score: 58.00
production_profile_qualified: null
operator_ratified: false
artifact_sha256: TO_BE_FILLED_AT_COMMIT
artifact_line_count: TO_BE_FILLED_AT_COMMIT
```

No value in this block may be changed without an evidence-bearing commit.
