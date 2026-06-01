# Execution Identity Lineage and Blast-Radius Audit

Date: 2026-06-01

Audit target: `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2`

Branch: `codex/runtime-truth-spine-v2`

Base HEAD: `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859`

Verdict: the v2 branch has a real Canonical `ExecutionIdentity` spine for selected paths, but identity is not yet saturated. The repo still contains multiple parallel identity lineages, legacy run/claim writes, graph/workflow IDs, event envelope IDs, artifact IDs, A2A IDs, provider session IDs, and proposal/gate IDs that are not mechanically joined to the runtime ledger.

The shortest accurate summary: `ExecutionIdentity` is no longer vapor, but it is still optional infrastructure unless the remaining boundary surfaces are adapted or quarantined.

## 1. Clean Source Boundary

Evidence level: `code-enforced/staged-v2-candidate`, `test-backed`.

The intended clean branch exists, but the v2 spine changes are currently staged rather than committed. A checkpoint commit was attempted and blocked by repo governance hooks:

- `dharma-uplift-guards` required hot-path impact acknowledgement in the commit message.
- `dharma-docops-integrity` reported stale generated counts in manifest/inventory files.

I did not bypass those hooks.

Source boundary used for this audit:

| Field | Value |
| --- | --- |
| Worktree | `/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v2` |
| Branch | `codex/runtime-truth-spine-v2` |
| Base HEAD | `2737b26d7ed8dbee9c828ba64d5a6c9ec128b859` |
| Tracked/index file count | `2746` |
| Source status | staged v2 candidate, no unstaged diff observed |
| Staged scope | 20 files, 3710 insertions, 56 deletions |

Staged files in scope include:

- `dharma_swarm/spine/identity.py`
- `dharma_swarm/spine/adapters.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`
- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/message_bus.py`
- `tests/test_runtime_truth_spine_v1.py`
- `tests/test_runtime_truth_spine_v2_adapters.py`
- `tests/test_runtime_truth_spine_v2_evidence.py`

Important caveat: this is not a clean committed `AUDIT_SHA` yet. Implementation claims below are valid against the staged v2 worktree, not against a merged `origin/main` commit.

Search scope:

- Broad ID-like grep found `9540` references across `649` files.
- Top term counts: `session_id` 2404, `task_id` 2391, `agent_id` 1831, `run_id` 1209, `trace_id` 1085, `artifact_id` 571, `proposal_id` 506, `claim_id` 439, `event_id` 299, `correlation_id` 240, `idempotency_key` 207.
- Absence test: `promotion_id`, `revert_id`, `verification_id`, and `ontology_action_id` had zero implementation hits in tracked Python/docs/config search.

## 2. Identity Surface Inventory

Evidence level: mostly `code-enforced/staged-v2-candidate`; noted gaps are `absence-test-backed` or `inferred`.

| ID surface | Meaning found | Generator / owner | Required? | Durable surface | Maps to `ExecutionIdentity`? | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `ExecutionIdentity` | Canonical runtime identity bundle | `ExecutionIdentity.new` | Required only where invoked | `execution_identities` table | Canonical | `dharma_swarm/spine/identity.py:29`, `runtime_state.py:210` |
| `trace_id` | Cross-surface trace lineage | `CorrelationContext`, `ExecutionIdentity.new`, `RuntimeEnvelope.create` | Required on selected v2 paths | TaskBoard column, `execution_identities`, receipts | Yes, but also parallel | `identity.py:37`, `correlation_context.py:64`, `runtime_contract.py:49` |
| `correlation_id` | Correlates task/run/message lineage | Defaults to trace in `ExecutionIdentity.new` | Required in `from_metadata(require=True)` | `execution_identities`, receipts | Yes | `identity.py:38`, `identity.py:79`, `runtime_state.py:215` |
| `causation_id` | Causal predecessor | Caller-provided or blank | Optional | `execution_identities`, receipts | Yes | `identity.py:43`, `runtime_state.py:217` |
| `task_id` | Internal task identity | `TaskBoard._new_id`, A2A fallback, adapters | Required for `ExecutionIdentity` | TaskBoard, RuntimeStateStore, receipts | Yes, but many independent generators | `identity.py:39`, `task_board.py:207`, `a2a_server.py:407` |
| `run_id` | Runtime/work unit identity | `ExecutionIdentity.new`, `RuntimeStateStore.new_run_id`, workflow-local generators | Required for dispatch identity | `execution_identities`, `delegation_runs`, receipts | Yes, but legacy writes bypass it | `identity.py:40`, `runtime_state.py:210`, `opportunity_dispatcher.py:157` |
| `workflow_id` | Graph/durable workflow identity | `workflow.py`, `workflow_graph.py`, `durable_execution.py` | Required in workflow systems | Checkpoint/state files | No direct mapping found | `workflow.py:231`, `workflow_graph.py:240`, `durable_execution.py:99` |
| `thread_id` | Chat/provider thread identity | Gateway/provider adapters | Optional | Gateway/TUI/session metadata | No | `gateway/base.py:36`, `gateway/telegram.py:137`, `tui/engine/adapters/codex.py:383` |
| `session_id` | Operator/runtime/provider session | Multiple session stores and `RuntimeStateStore.new_session_id` | Often optional | TaskBoard metadata, runtime tables, TUI stores | Optional field on identity | `identity.py:46`, `runtime_state.py:3062`, `task_board.py:212` |
| `claim_id` | Work claim/lease-ish runtime claim | `ExecutionIdentity.new`, `RuntimeStateStore.new_claim_id`, legacy sync callers | Required for dispatch identity | `task_claims`, `execution_identities`, receipts | Yes, but legacy path bypasses identity row | `identity.py:41`, `runtime_state.py:3066`, `opportunity_dispatcher.py:156` |
| `lease_id` | Workspace lease ID | `RuntimeStateStore.new_lease_id` | Lease-specific | `workspace_leases` | No canonical mapping except holder run | `runtime_state.py:81`, `runtime_state.py:3074` |
| `lock_id` | File lock implementation identity | `file_lock.py` hash | Lock-specific | Lock files | No | `file_lock.py:79`, `file_lock.py:284` |
| `message_id` | Message transport ID | `Message.id`, adapter metadata | Optional | MessageBus `messages`, identity table optional | Optional field | `models.py:243`, `spine/identity.py:48`, `message_bus.py:33` |
| `event_id` | Event envelope / MessageBus event ID | `RuntimeEnvelope.create`, `MessageBus.emit_event` | Event-specific | `events`, `execution_identities` optional | Optional field | `runtime_contract.py:43`, `message_bus.py:603`, `identity.py:49` |
| `artifact_id` | Artifact object identity | Engine/runtime artifact stores | Optional | Artifact manifests, runtime artifact table | Optional field | `identity.py:50`, `artifact_store.py:151`, `engine/artifacts.py:111` |
| `receipt_id` | Runtime ledger receipt ID | `RuntimeStateStore.build_runtime_receipt` | Receipt-specific | `runtime_receipts` | Receipt links to identity fields | `runtime_state.py:233`, `runtime_state.py:2127` |
| `agent_id` | Agent identity / assignee | `AgentConfig.id`, callers, A2A `to_agent` | Optional | Agent config, receipts, runtime tables | Optional field | `models.py:173`, `identity.py:45`, `a2a_server.py:408` |
| `parent_run_id` | Parent runtime run | Caller-provided | Optional | `execution_identities`, `delegation_runs`, receipts | Yes | `identity.py:44`, `runtime_lifecycle.py:362` |
| `parent_task_id` | Parent task concept | Only one tracked hit | Not implemented | None found | No | absence count: 1 |
| `external_a2a_task_id` | External A2A task ID | `A2ATask.id` mapped in A2A server | Optional but important for A2A | `execution_identities` indexed | Yes | `identity.py:47`, `a2a_server.py:417`, `runtime_state.py:287` |
| `a2a_task_id` | Legacy A2A metadata field | A2A bridge/test | Not canonical | Message metadata only | No | `a2a_bridge.py:229`, `tests/test_a2a.py:639` |
| `idempotency_key` | Duplicate suppression key | `ExecutionIdentity.new`, MessageBus caller, A2A metadata | Required in v2 required identity | `idempotency_records`, receipts | Yes | `identity.py:42`, `runtime_state.py:251`, `message_bus.py:598` |
| `request_id` | Request-local identity | Scattered adapters/contracts | Not canonical | Varies | No direct mapping found | grep count: 171 |
| `operation_id` | Operation-local identity | Scattered | Not canonical | Varies | No direct mapping found | grep count: present in broad search |
| `checkpoint_id` | Checkpoint store identity | Contract/checkpoint modules | Checkpoint-specific | Checkpoint stores/files | No canonical mapping found | `contracts/runtime.py:63`, checkpoint search count: 31 |
| `action_id` | Operator action / generic action ID | `RuntimeStateStore.new_action_id`, ontology/action code uses action names | Action-specific | `operator_actions` | No ontology-specific canonical ID | `runtime_state.py:169`, `runtime_state.py:3094` |
| `ontology_action_id` | Expected ontology action ID | None found | Missing | None found | No | absence count: 0 |
| `proposal_id` | Self-mod/telos proposal lineage | Evolution/telic systems | Proposal-specific | Evolution/telic/proposal records | Optional field on identity, not wired broadly | `identity.py:51`, `evolution.py` grep, `runtime_state.py:224` |
| `gate_id` | Gate-decision record identity | Telic/operator brief | Gate-specific | Ontology/telic records | No direct runtime mapping | `operator_brief/insight_brief.py:161`, `tests/test_telic_seam.py:313` |
| `verification_id` | Expected self-mod verification ID | None found | Missing | None found | No | absence count: 0 |
| `promotion_id` | Expected self-mod promotion ID | None found | Missing | None found | No | absence count: 0 |
| `revert_id` | Expected self-mod revert ID | None found | Missing | None found | No | absence count: 0 |
| `swarm_id` | Swarm grouping identity | Rare/scattered | Not canonical | unclear | No direct mapping found | broad grep term included |
| `provider_session_id` | Provider/TUI external session | TUI/operator session stores | UI/provider-specific | TUI/operator stores | No | `tui/engine/session_store.py:62`, `operator_core/session_store.py:60` |
| `block_id` / `pipeline_id` | Logic/lineage graph block IDs | Logic/lineage modules | Graph-local | Lineage DB | No direct mapping found | `logic_layer.py:139`, `lineage.py:68` |
| `bundle_id` | Context bundle identity | RuntimeStateStore | Bundle-specific | `context_bundles` | Indirect via run/task/session | `runtime_state.py:152` |

## 3. Same-Name Collision Matrix

Evidence level: `code-enforced/staged-v2-candidate`, `absence-test-backed`.

| Name | Collision | Risk | Evidence | Recommendation |
| --- | --- | --- | --- | --- |
| `trace_id` | Created by `CorrelationContext`, `RuntimeEnvelope`, and `ExecutionIdentity` | Same field name can mean ambient trace, transport trace, or canonical runtime trace | `correlation_context.py:64`, `runtime_contract.py:67`, `identity.py:78` | Keep `trace_id`, but require it to be carried inside `ExecutionIdentity` at runtime boundaries. |
| `task_id` | TaskBoard task, A2A fallback task, RuntimeState task claim field, tests | Same name is close enough to be useful but not always ledger-backed | `task_board.py:207`, `a2a_server.py:407`, `runtime_state.py:44` | `TaskBoard.create` should emit/accept identity adapter metadata or be marked task-only projection. |
| `run_id` | Canonical runtime run, delegation run, workflow-adjacent run, operator action run | Legacy helpers can write run rows without identity | `identity.py:80`, `runtime_state.py:61`, `runtime_state.py:1686`, `opportunity_dispatcher.py:157` | Make `execution_identities.run_id` the FK-like owner for all runtime runs. |
| `claim_id` | Canonical claim in identity and direct task claim primary key | Legacy claim writes do not guarantee identity or receipt | `identity.py:81`, `runtime_state.py:44`, `runtime_state.py:1595` | Require `ExecutionIdentity` or quarantine legacy claim creation. |
| `event_id` | Runtime envelope event, MessageBus event, optional identity field | Event identity can be generated without run linkage | `runtime_contract.py:67`, `message_bus.py:603`, `identity.py:49` | Message/event envelopes should include canonical run mapping before handlers run. |
| `message_id` | MessageBus message ID and optional identity field | Raw message send is not ledger-backed | `models.py:243`, `message_bus.py:184`, `identity.py:48` | Add message-consumed receipt and run/trace mapping on receive. |
| `artifact_id` | Runtime artifact, engine artifact, optional identity field | Engine artifacts can exist without run/trace | `artifact_store.py:151`, `engine/artifacts.py:111`, `runtime_state.py:94` | Require runtime artifact adapter for selected surfaces. |
| `session_id` | Operator session, provider session, runtime session | Many meanings with different lifetimes | `identity.py:46`, `runtime_state.py:3062`, `tui/engine/session_store.py:62` | Treat session as context, not execution truth. |
| `agent_id` | Agent config identity, actor, assignee, A2A target | Agent identity is not the same as execution identity | `models.py:173`, `a2a_server.py:408`, `runtime_state.py:190` | Keep as participant field; do not use as run owner. |
| `workflow_id` | Graph/durable workflow ID, not runtime run ID | Cannot reconstruct runtime ledger by workflow ID without mapping | `workflow.py:231`, `workflow_graph.py:240`, `durable_execution.py:99` | Add workflow-to-run mapping receipt or quarantine graph workflow as graph-local. |
| `proposal_id` | Self-mod/telic proposal ID and optional identity field | Proposal can pass gates/apply without runtime run linkage | `identity.py:51`, `runtime_state.py:224`, `evolution.py` grep | Add proposal/gate/apply/verify receipts tied to run. |
| `a2a_task_id` vs `external_a2a_task_id` | Two names for external A2A task lineage | Legacy A2A metadata will not join to v2 lookup | `a2a_bridge.py:229`, `a2a_server.py:417`, `runtime_state.py:2110` | Migrate to `external_a2a_task_id`; adapter should read legacy alias. |

## 4. Lineage Map

Evidence level: `code-enforced/staged-v2-candidate`, `inferred` where call path is not fully wired.

### A2A Local Ingress

Path: `A2AServer.submit` -> `_ensure_execution_identity` -> `RuntimeStateStore.record_execution_identity_sync` -> idempotency -> dispatch -> runtime receipt.

Evidence:

- `A2AServer.__init__` accepts `runtime_state` and `require_execution_identity`, default false: `a2a/a2a_server.py:273`.
- `_ensure_execution_identity` creates an identity from A2A task metadata and maps `task.id` to `external_a2a_task_id`: `a2a/a2a_server.py:399`, `a2a/a2a_server.py:417`.
- It persists identity when runtime state exists: `a2a/a2a_server.py:335`.
- It checks idempotency before dispatch: `a2a/a2a_server.py:345`.
- It records a runtime receipt after dispatch: `a2a/a2a_server.py:367`.
- It completes the idempotent side effect: `a2a/a2a_server.py:390`.

Verdict: joined for the selected path, but not globally mandatory because `require_execution_identity=False` by default.

### TaskBoard

Path: `TaskBoard.create` -> task row with `trace_id` column and metadata.

Evidence:

- Tasks table has `trace_id`: `task_board.py:29`.
- `create` generates `task_id` with `_new_id`: `task_board.py:207`.
- It copies ambient `CorrelationContext.trace_id` to metadata/column: `task_board.py:212`.

Verdict: adapter-ready, not canonical. It stores trace, not full `ExecutionIdentity`.

### Orchestrator / RuntimeLifecycle Dispatch

Path: task/dispatch metadata -> `RuntimeLifecycle.ensure_execution_identity` -> task and dispatch metadata -> `RuntimeStateStore`.

Evidence:

- `ensure_runtime_run_id` writes `runtime_run_id`: `runtime_lifecycle.py:68`.
- `ensure_execution_identity` merges task and dispatch metadata: `runtime_lifecycle.py:83`.
- Required mode rejects missing trace/correlation/claim: `runtime_lifecycle.py:108`.
- It writes identity fields back to dispatch and task metadata: `runtime_lifecycle.py:137`.
- It records identity in `RuntimeStateStore`: `runtime_lifecycle.py:163`.

Verdict: strongest current canonical seam after A2A.

### MessageBus

Path A: `emit_event` with `idempotency_key` -> `ExecutionIdentity` -> idempotency table -> event insert -> idempotency completion.

Evidence:

- Optional `idempotency_key` parameter: `message_bus.py:598`.
- Deterministic event ID from idempotency key: `message_bus.py:603`.
- Requires runtime state when idempotency key is provided: `message_bus.py:612`.
- Constructs `ExecutionIdentity`: `message_bus.py:615`.
- Checks existing idempotency record before insert: `message_bus.py:625`.
- Begins idempotent side effect before insert: `message_bus.py:631`.
- Completes it after insert: `message_bus.py:675`.

Path B: raw message/artifact send -> no identity enforcement.

Evidence:

- `send` inserts message directly: `message_bus.py:184`.
- `attach_artifact` generates artifact IDs and inserts artifacts: `message_bus.py:373`.
- `consume_events` marks events consumed without `ExecutionIdentity` or receipt: `message_bus.py:683`.

Verdict: event emit with idempotency is joined; raw messages, artifacts, and consume path are not.

### Artifact Stores

Path A: `RuntimeArtifactStore` can write runtime artifact records if caller supplies run/trace.

Evidence:

- `create_text_artifact` accepts optional `run_id` and `trace_id`, default blank: `artifact_store.py:40`.
- `_record_ref` records into runtime state when present: `artifact_store.py:298`.

Path B: `engine/artifacts.py` creates artifacts independently.

Evidence:

- `ArtifactRef` only carries artifact/session/type/version/path: `engine/artifacts.py:15`.
- `create_artifact` generates `artifact_id` independently: `engine/artifacts.py:90`, `engine/artifacts.py:111`.

Verdict: runtime artifact path is adapter-ready; engine artifact path is a parallel artifact lineage.

### Workflow / Graph

Path: workflow ID -> checkpoint state files.

Evidence:

- `CompiledWorkflow` creates `workflow_id`: `workflow.py:231`.
- Checkpoint writes `workflow_id`: `workflow.py:377`.
- `WorkflowGraph.execute` defaults `workflow_id` to `wfg_<timestamp>`: `workflow_graph.py:240`.
- `DurableWorkflow` persists by `workflow_id`: `durable_execution.py:99`, `durable_execution.py:220`.

Verdict: graph/workflow has a separate lineage. No direct `workflow_id -> run_id` mapping was found in the audited search.

### Ontology Actions

Path: `OntologyRegistry.execute_action` -> telos check -> success log.

Evidence:

- `ActionDef.modifies` and `requires_approval` are declared: `ontology.py:161`, `ontology.py:172`, `ontology.py:174`.
- `execute_action` starts at `ontology.py:763`.
- Telos gate logic exists before success: `ontology.py:798`.
- The action logs success: `ontology.py:872`.
- `ontology_action_id` absence test returned zero hits.

Verdict: ontology action lineage is not currently joined to `ExecutionIdentity`; the C2 tollbooth fix remains queued.

### Tools

Path: `ToolRegistry.dispatch` -> handler call.

Evidence:

- Registry class: `tool_registry.py:58`.
- Dispatch method: `tool_registry.py:129`.
- No `ExecutionIdentity`, `run_id`, `trace_id`, or `idempotency` hits in the file-level search.

Verdict: tool dispatch is missing an identity boundary.

### Self-Modification

Path: proposal/gate/apply/test modules carry `proposal_id`, but runtime ledger receipts are not wired.

Evidence:

- `proposal_id` appears widely in evolution/telic code.
- `RuntimeStateStore` has self-mod receipt helpers: `runtime_state.py:2364`, `runtime_state.py:2385`.
- Absence tests found zero `verification_id`, `promotion_id`, and `revert_id`.

Verdict: self-mod identity is proposal-centric, not runtime-ledger-centric.

## 5. Durable Ledger Map

Evidence level: `code-enforced/staged-v2-candidate`, `test-backed`.

`RuntimeStateStore` is the durable ledger candidate.

Ledger tables:

- `execution_identities`: `runtime_state.py:210`
- `runtime_receipts`: `runtime_state.py:233`
- `idempotency_records`: `runtime_state.py:251`
- `task_claims`: `runtime_state.py:44`
- `delegation_runs`: `runtime_state.py:61`
- `artifact_records`: `runtime_state.py:94`
- `session_events`: `runtime_state.py:180`

Capabilities:

| Question | Can answer? | Evidence |
| --- | --- | --- |
| What happened to `run_id X`? | Yes, for joined paths | `describe_run`: `runtime_state.py:2734`; `get_run_ledger`: `runtime_state.py:2765` |
| Who spawned this child? | Yes, if `parent_run_id` is recorded | `list_child_runs`: `runtime_state.py:2718`; child receipts in `runtime_lifecycle.py:362` |
| Was this side effect already performed? | Yes, for side effects that use idempotency helpers | `was_side_effect_performed`: `runtime_state.py:2710`; `idempotency_records`: `runtime_state.py:251` |
| Which external A2A task maps to run? | Yes, for v2 A2A path | `get_execution_identity_by_external_a2a_task`: `runtime_state.py:2107` |
| Which workflow ID maps to run? | Not proven | no mapping found in workflow grep |
| Which proposal/gate maps to run? | Only possible via optional `proposal_id`; not wired broadly | `identity.py:51`, self-mod receipt helpers present |
| Which ontology action maps to run? | Not proven | `ontology_action_id` absence count 0 |

Critical caveat: the same store still exposes legacy sync methods that write runtime-looking rows without the canonical identity ledger.

Evidence:

- `create_task_claim_sync`: `runtime_state.py:1595`
- `create_delegation_run_sync`: `runtime_state.py:1686`
- Opportunity dispatcher uses both: `opportunity_dispatcher.py:184`, `opportunity_dispatcher.py:193`

## 6. Idempotency Map

Evidence level: `code-enforced/staged-v2-candidate`, `test-backed`.

Canonical idempotency implementation:

- Table: `idempotency_records` with primary key `(idempotency_key, side_effect_key)`: `runtime_state.py:251`.
- Begin-before-side-effect helper: `try_begin_idempotent_side_effect`: `runtime_state.py:2501`.
- Completion helper: `complete_idempotent_side_effect`: `runtime_state.py:2594`.
- Query helper: `was_side_effect_performed`: `runtime_state.py:2710`.

Proven joined users:

- A2A submit path uses `try_begin_idempotent_side_effect_sync` before dispatch: `a2a/a2a_server.py:345`.
- MessageBus `emit_event` uses begin-before-insert and completion: `message_bus.py:631`, `message_bus.py:675`.
- RuntimeState tests cover duplicate side-effect prevention: `tests/test_runtime_state.py:192`.

Unproven or missing users:

- MessageBus `consume_events`: no receiver-side `message_consumed` receipt or idempotency guard found: `message_bus.py:683`.
- `ToolRegistry.dispatch`: no identity/idempotency evidence: `tool_registry.py:129`.
- `OntologyRegistry.execute_action`: no `ontology_action_id` or idempotency guard found: `ontology.py:763`.
- Workflow/checkpoint execution: no `workflow_id -> run_id` idempotency mapping found.
- Engine artifact store: artifact writes can happen without idempotency or runtime receipt: `engine/artifacts.py:90`.

Verdict: idempotency is real where the new helpers are used; it is not a property of the repo yet.

## 7. Parent/Child Lineage Map

Evidence level: `code-enforced/staged-v2-candidate`.

Joined path:

- `ExecutionIdentity` includes `parent_run_id`: `identity.py:44`.
- `execution_identities` stores `parent_run_id`: `runtime_state.py:218`.
- `delegation_runs` stores `parent_run_id`: `runtime_state.py:66`.
- `RuntimeLifecycle.record_delegation_run` emits `child_spawned` for queued/claimed/running child state: `runtime_lifecycle.py:362`.
- It emits `child_completed` for completed/failed child state: `runtime_lifecycle.py:375`.
- `RuntimeStateStore.list_child_runs` queries children: `runtime_state.py:2718`.

Gaps:

- `parent_task_id` is effectively absent from implementation search.
- Opportunity dispatcher writes claim/run rows with no parent linkage: `opportunity_dispatcher.py:155`.
- Workflow graph dependencies use graph-local topology and `workflow_id`, not runtime parent/child run IDs: `workflow.py:653`.
- Swarm/delegation surfaces outside `RuntimeLifecycle` are not proven joined.

Verdict: parent/child lineage is real in `RuntimeLifecycle`; it is not saturated across all delegation/scheduler paths.

## 8. Artifact / Receipt / Message Linkage Map

Evidence level: `code-enforced/staged-v2-candidate`, `inferred` for missing enforcement.

| Surface | Carries run/trace/correlation? | Durable receipt? | Evidence | Verdict |
| --- | --- | --- | --- | --- |
| `RuntimeLifecycle.record_artifact` | Yes, via identity metadata | Yes: `artifact` and `artifact_written` | `runtime_lifecycle.py:416`, `runtime_lifecycle.py:453`, `runtime_lifecycle.py:474` | joined |
| `RuntimeArtifactStore` | Optional run/trace args | Runtime record if `runtime_state` exists | `artifact_store.py:40`, `artifact_store.py:298` | adapter-ready |
| `engine.ArtifactStore` | No run/trace | No runtime receipt | `engine/artifacts.py:15`, `engine/artifacts.py:90` | parallel lineage |
| MessageBus `emit_event` | Yes when idempotency path used | idempotency receipts | `message_bus.py:615`, `message_bus.py:631` | joined for emit |
| MessageBus `send` | No canonical identity | No runtime receipt | `message_bus.py:184` | missing |
| MessageBus `consume_events` | Reads task/agent only | No `message_consumed` receipt found on consume path | `message_bus.py:683` | missing |
| A2A completion receipt | Includes external A2A mapping | Yes | `a2a/a2a_server.py:367` | joined |
| RuntimeStateStore receipts | run/task/trace/correlation/idempotency fields | Yes | `runtime_state.py:233` | canonical |

## 9. Identity Drop / Fork Findings

Evidence level: `code-enforced/staged-v2-candidate`, `absence-test-backed`.

1. Legacy RuntimeStateStore sync helpers bypass the spine.
   - Evidence: `create_task_claim_sync` at `runtime_state.py:1595`; `create_delegation_run_sync` at `runtime_state.py:1686`.
   - Caller evidence: `opportunity_dispatcher.py:184`, `opportunity_dispatcher.py:193`.
   - Risk: runtime-looking rows exist without `execution_identities` or `runtime_receipts`.

2. `CorrelationContext` is a predecessor, not canonical execution identity.
   - Evidence: only trace/proposal/session/cell fields in `correlation_context.py:53`.
   - Risk: code can believe it is traced while missing run/claim/idempotency.

3. `RuntimeEnvelope` is an event envelope, not workflow identity.
   - Evidence: `RuntimeEnvelope` carries event/session/trace only: `runtime_contract.py:41`.
   - Risk: event trace can fork from runtime trace unless adapted.

4. Workflow and DurableWorkflow use `workflow_id` without a runtime run mapping.
   - Evidence: `workflow.py:231`, `workflow_graph.py:240`, `durable_execution.py:99`.
   - Risk: checkpoints cannot be reconstructed from `run_id` unless caller records a mapping.

5. Raw MessageBus send/consume paths do not enforce identity.
   - Evidence: direct `send`: `message_bus.py:184`; consume path: `message_bus.py:683`.
   - Risk: event delivery and handler execution can be unjoinable to run ledger.

6. Tool dispatch is identity-free.
   - Evidence: `tool_registry.py:129`.
   - Risk: side-effecting tools can bypass idempotency and receipts.

7. Ontology action execution has no ontology action ID lineage.
   - Evidence: `execute_action`: `ontology.py:763`; `ontology_action_id` absence count 0.
   - Risk: domain mutations or declared action successes cannot be joined to runtime run unless caller wraps them.

8. Artifact stores fork identity.
   - Evidence: runtime artifact path optional run/trace: `artifact_store.py:40`; engine artifact path generates independent artifact IDs: `engine/artifacts.py:111`.
   - Risk: artifacts can be real but unjoinable.

9. Self-mod lifecycle IDs are incomplete.
   - Evidence: `proposal_id` exists; `verification_id`, `promotion_id`, `revert_id` absence counts 0.
   - Risk: proposal/gate/apply/verify/promote/revert cannot be reconstructed as one runtime chain.

10. `a2a_task_id` is a legacy alias.
    - Evidence: `a2a_bridge.py:229`; v2 canonical mapping uses `external_a2a_task_id`: `a2a/a2a_server.py:417`.
    - Risk: old A2A paths may not be queryable via `get_execution_identity_by_external_a2a_task`.

## 10. Canonical / Adapt / Quarantine Recommendations

Evidence level: `code-enforced/staged-v2-candidate`, `inferred`.

| Surface | Classification | Reason | Action |
| --- | --- | --- | --- |
| `ExecutionIdentity` | canonical | Central bundle with required runtime fields | Keep and make mandatory at selected boundaries |
| `RuntimeStateStore.execution_identities` | canonical | Durable identity table keyed by run | Keep as runtime ledger root |
| `RuntimeStateStore.runtime_receipts` | canonical | Durable receipt table | Keep and extend coverage |
| `RuntimeStateStore.idempotency_records` | canonical | Pre-side-effect duplicate suppression | Keep and require before irreversible work |
| `RuntimeLifecycle` | canonical seam | Writes identity, claims, runs, artifacts, receipts | Expand into TaskBoard/orchestrator default path |
| A2A v2 local submit | canonical seam | Maps external A2A ID to runtime run and idempotency | Flip required mode once adapters land |
| `spine/adapters.py` | adapter-ready | Defines surface mappings but not widely invoked | Wire into boundary modules |
| TaskBoard | adapter-ready | Trace-only today | Add identity metadata adapter |
| MessageBus emit | partially canonical | Joined when idempotency key supplied | Require envelope/identity on selected event subjects |
| MessageBus send/consume | missing | No canonical identity receipt | Add consume receipt and receiver idempotency |
| RuntimeArtifactStore | adapter-ready | Optional run/trace | Require identity for selected write paths |
| Engine ArtifactStore | quarantine/projection | Independent artifact lineage | Wrap or mark graph/local artifact store |
| Workflow/DurableWorkflow | transitional | Uses workflow_id lineage | Add mapping receipt or quarantine as graph-local |
| Ontology execute_action | missing/tollbooth queued | Declares action contracts but no runtime identity/action ID | Queue C2 fix with identity receipt |
| ToolRegistry | missing | Dispatch has no identity | Add tool-call boundary adapter |
| Self-mod evolution | missing/transitional | Proposal IDs not joined to runtime receipts | Add self-mod lifecycle receipts |
| CorrelationContext | predecessor/context | Useful trace context, not execution truth | Keep as source for `trace_id`, never as ledger substitute |
| RuntimeEnvelope | transport envelope | Useful event validation, not workflow identity | Adapt to `ExecutionIdentity` at ingress/consume |
| TUI/provider session IDs | projection/external | Provider-local sessions | Do not force canonical semantics; map when launching work |
| File locks | local infrastructure | `lock_id` is lock-specific | Do not map unless locks guard runtime side effects |

## 11. Blast-Radius Map

Evidence level: `code-enforced/staged-v2-candidate`, `inferred`.

If `ExecutionIdentity` becomes mandatory everywhere, these files/classes/functions are in the direct blast radius:

Canonical spine:

- `dharma_swarm/spine/identity.py`
- `dharma_swarm/spine/adapters.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`

Ingress and external protocol:

- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/a2a/a2a_bridge.py`
- `dharma_swarm/a2a/node_gateway.py`
- `dharma_swarm/gateway/base.py`
- `dharma_swarm/gateway/telegram.py`

Dispatch and scheduling:

- `dharma_swarm/task_board.py`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/opportunity_dispatcher.py`
- `dharma_swarm/contracts/runtime.py`
- `dharma_swarm/contracts/runtime_adapters.py`

Messaging and events:

- `dharma_swarm/message_bus.py`
- `dharma_swarm/runtime_contract.py`

Artifacts:

- `dharma_swarm/artifact_store.py`
- `dharma_swarm/engine/artifacts.py`

Graph/checkpoint:

- `dharma_swarm/workflow.py`
- `dharma_swarm/workflow_graph.py`
- `dharma_swarm/durable_execution.py`
- `dharma_swarm/checkpoint.py`

Ontology/tools/governance:

- `dharma_swarm/ontology.py`
- `dharma_swarm/tool_registry.py`
- `dharma_swarm/telic_seam.py`
- `dharma_swarm/evolution.py`
- `dharma_swarm/self_improve.py`
- `dharma_swarm/sealed_packet_apply.py`

Operator/TUI/provider projections:

- `dharma_swarm/tui/engine/session_store.py`
- `dharma_swarm/operator_core/session_store.py`
- `dharma_swarm/tui/engine/adapters/codex.py`
- `dharma_swarm/tui/engine/adapters/claude.py`

Tests that must grow:

- `tests/test_runtime_truth_spine_v1.py`
- `tests/test_runtime_truth_spine_v2_adapters.py`
- `tests/test_runtime_truth_spine_v2_evidence.py`
- `tests/test_runtime_state.py`
- `tests/test_runtime_lifecycle.py`
- `tests/test_message_bus.py`
- New tests for TaskBoard, ToolRegistry, ontology action receipts, workflow mapping, and self-mod lifecycle receipts.

## 12. Tests and Falsification

Evidence level: `test-backed`.

Focused verification command:

```bash
env HOME=/private/tmp/dharma_spine_v2_identity_audit_home pytest -q \
  tests/test_runtime_truth_spine_v2_evidence.py \
  tests/test_runtime_truth_spine_v2_adapters.py \
  tests/test_runtime_truth_spine_v1.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py \
  tests/test_message_bus.py
```

Result:

```text
34 passed, 1 warning in 2.69s
```

Falsification attempts:

- Searched for every named identity field across Python/docs/config/test surfaces.
- Verified `ExecutionIdentity` import/use sites. Runtime use is limited to `message_bus.py`, `runtime_lifecycle.py`, `runtime_state.py`, `a2a/a2a_server.py`, exports, adapters, and tests.
- Searched for `create_task_claim_sync` and `create_delegation_run_sync`; found direct legacy callers in `opportunity_dispatcher.py`.
- Searched for self-mod lifecycle IDs; `verification_id`, `promotion_id`, and `revert_id` were absent.
- Searched for `ontology_action_id`; absent.
- Searched low-count transport/provider aliases (`thread_id`, `lock_id`, `gate_id`, `a2a_task_id`) and separated external/local meanings from canonical runtime identity.
- Verified adapter functions exist; usage search shows they are tested/exported but not yet broadly wired into runtime source.

What would disprove the major findings:

- A committed branch where `create_task_claim_sync` and `create_delegation_run_sync` require and persist `ExecutionIdentity`.
- A call path where TaskBoard, ToolRegistry, raw MessageBus consume, ontology actions, workflow checkpoints, and self-mod proposal/apply/verify all invoke `ExecutionIdentity` adapters before side effects.
- A runtime ledger query proving `workflow_id`, `proposal_id`, `ontology_action_id`, `message_id`, and `artifact_id` all map back to one `run_id`.

## 13. Top Risks

Evidence level: `code-enforced/staged-v2-candidate`, `test-backed` where noted.

1. Duplicate execution despite ID fields.
   - Cause: idempotency is enforced only on selected paths.
   - Evidence: idempotency helper exists at `runtime_state.py:2501`, but ToolRegistry and consume paths lack it.

2. Broken lineage from legacy RuntimeStateStore writes.
   - Cause: old sync methods can create claims/runs without `execution_identities`.
   - Evidence: `runtime_state.py:1595`, `runtime_state.py:1686`.

3. Unjoinable artifacts.
   - Cause: artifacts can be created with blank run/trace or through engine store only.
   - Evidence: `artifact_store.py:40`, `engine/artifacts.py:90`.

4. False idempotency.
   - Cause: presence of `idempotency_key` is not the same as pre-side-effect guard.
   - Evidence: pre-side-effect guard is proven only in A2A submit and MessageBus emit, not all consumers.

5. Orphan child runs.
   - Cause: parent-child receipts exist only through `RuntimeLifecycle.record_delegation_run`.
   - Evidence: `runtime_lifecycle.py:362`; legacy `opportunity_dispatcher.py:155` creates independent IDs.

6. Audit gaps around workflow/checkpoint lineage.
   - Cause: `workflow_id` is separate from `run_id`.
   - Evidence: `workflow.py:231`, `workflow_graph.py:240`, `durable_execution.py:99`.

7. Governance bypasses.
   - Cause: ontology action and tool dispatch are not identity/idempotency receipt boundaries.
   - Evidence: `ontology.py:763`, `tool_registry.py:129`.

8. Self-mod chain is not reconstructable as one runtime lineage.
   - Cause: missing verification/promotion/revert IDs and unused self-mod receipt helpers.
   - Evidence: absence counts 0 for `verification_id`, `promotion_id`, `revert_id`; helpers at `runtime_state.py:2364`.

## 14. Next Implementation Slices

Exactly three prioritized slices.

### Slice 1: Close the RuntimeStateStore Legacy Bypass

Problem:

`RuntimeStateStore` has canonical identity/receipt tables, but `create_task_claim_sync` and `create_delegation_run_sync` still write runtime-looking state without `ExecutionIdentity`.

Why first:

This is the deepest identity fork. If the ledger itself accepts non-spine rows, every downstream query can lie by omission.

Files:

- `dharma_swarm/runtime_state.py`
- `dharma_swarm/opportunity_dispatcher.py`
- `tests/test_runtime_state.py`
- New/updated tests for OpportunityDispatcher identity propagation.

Target architecture:

All claim/run creation either:

- receives an `ExecutionIdentity` and writes `execution_identities` plus `runtime_receipts`, or
- is explicitly named and marked legacy/quarantined with tests proving it is not used on canonical paths.

Migration steps:

1. Add optional `identity` parameter to legacy sync helpers.
2. If helper is used in canonical mode, require identity and record it before inserting claim/run rows.
3. Update `OpportunityDispatcher` to construct one identity and pass it through.
4. Add invariant test: every `delegation_runs.run_id` created by canonical helpers has an `execution_identities` row and at least one receipt.
5. Leave a deprecated compatibility shim only for tests that explicitly assert legacy behavior.

Success criteria:

- No selected runtime path can create a `run_id` without `ExecutionIdentity`.
- `get_run_ledger(run_id)` reconstructs claim, run, receipts, artifacts, idempotency, and child rows for OpportunityDispatcher-created work.

### Slice 2: Promote Adapters Into Boundary Tollbooths

Problem:

`spine/adapters.py` defines the right compatibility surface, but broad runtime modules do not call it yet.

Why second:

Once the ledger refuses bypasses, edge surfaces need cheap adapters rather than broad rewrites.

Files:

- `dharma_swarm/spine/adapters.py`
- `dharma_swarm/task_board.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/artifact_store.py`
- `dharma_swarm/tool_registry.py`
- `tests/test_runtime_truth_spine_v2_adapters.py`
- New tests for TaskBoard, MessageBus consume, artifact write, and tool dispatch identity requirements.

Target architecture:

Each boundary has a deterministic adapter:

- accept an existing `ExecutionIdentity`,
- derive only from approved fields,
- fail closed when required,
- emit a runtime receipt before side effects.

Migration steps:

1. Add `require_identity` toggles defaulting false for compatibility.
2. Wire adapters into TaskBoard create/update metadata, MessageBus consume, RuntimeArtifactStore writes, and ToolRegistry dispatch.
3. Add tests where missing identity fails when the toggle is true.
4. Add tests proving artifacts/messages/tool calls carry `run_id`, `trace_id`, `correlation_id`, and idempotency where required.

Success criteria:

- At least four more surfaces become adapter-ready or joined without broad rewrites.
- Field presence is no longer mistaken for enforcement.

### Slice 3: Add Explicit Mapping Receipts for Parallel Lineages

Problem:

Workflow IDs, event IDs, message IDs, artifact IDs, proposal IDs, gate IDs, provider session IDs, and A2A legacy IDs currently have independent meanings. Some are valid local identities, but they are not always joinable to a runtime run.

Why third:

These systems should not all be renamed. They need mapping receipts that preserve local meaning while making runtime reconstruction possible.

Files:

- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_contract.py`
- `dharma_swarm/workflow.py`
- `dharma_swarm/workflow_graph.py`
- `dharma_swarm/durable_execution.py`
- `dharma_swarm/message_bus.py`
- `dharma_swarm/ontology.py`
- `dharma_swarm/evolution.py`
- `dharma_swarm/sealed_packet_apply.py`
- `tests/test_runtime_truth_spine_v2_evidence.py`
- New tests for workflow/proposal/ontology mapping receipts.

Target architecture:

Runtime ledger can answer:

- which `run_id` owns `workflow_id X`,
- which `run_id` owns `proposal_id X`,
- which `run_id` emitted/consumed `event_id X`,
- which `run_id` wrote `artifact_id X`,
- which `run_id` requested/applied ontology action X.

Migration steps:

1. Add generic `identity_mapping` or typed receipt metadata for external/local IDs.
2. Record `workflow_started`, `workflow_checkpointed`, `proposal_created`, `gate_evaluated`, `ontology_action_requested`, and `ontology_action_applied` receipts.
3. Treat `a2a_task_id` as a read-only legacy alias mapping to `external_a2a_task_id`.
4. Add ledger query tests for every mapped ID type.

Success criteria:

- Parallel local IDs remain valid but become ledger-queryable.
- No major runtime artifact, event, proposal, workflow, or ontology action is unjoinable to `run_id` on selected paths.
