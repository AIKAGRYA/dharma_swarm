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

<!-- CORE_RUNTIME_SECTION -->

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
