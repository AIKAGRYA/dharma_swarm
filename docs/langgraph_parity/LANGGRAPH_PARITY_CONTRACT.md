# LangGraph Parity Contract

Status: planning contract only
Owner: Agent 1, Planner/Architect
Date: 2026-06-29
Write scope for this pass: this file and `docs/langgraph_parity/TASK_GRAPH.md`

## Purpose

This contract defines what it means for `dharma_swarm` to reach LangGraph swarm/supervisor parity without creating a new runtime authority, truth store, or receipt system.

Parity does not require wrapping all execution in LangGraph. Parity means the target LangGraph semantics can be mapped to explicit local owners, invariants, receipts, and acceptance gates that future implementation work can verify.

The current repository has LangGraph-inspired components, but direct LangGraph execution is not wired as the runtime owner. The local contract therefore treats LangGraph as the reference semantics and `dharma_swarm` as the authoritative implementation surface.

## Verified Target Semantics

Verified on 2026-06-29 from current primary LangGraph documentation available through Context7:

- LangGraph Swarm `create_swarm(...)` builds a multi-agent `StateGraph`. Agents require stable names. `SwarmState` carries `messages` plus `active_agent`; `default_active_agent` selects the starting agent when state has no active agent.
- LangGraph Swarm handoff tools return a `Command` targeting the destination agent, update `active_agent`, and append a `ToolMessage` to message history while preserving prior history.
- LangGraph Supervisor uses a central supervisor agent to route work to specialized agents through handoff tools and then synthesize the final answer.
- LangGraph Supervisor `output_mode="full_history"` preserves worker history in supervisor state. `output_mode="last_message"` keeps the worker's final message, with the documented terminal tool-message exception.
- Supervisor delegation and swarm handoff are separate contracts. Swarm handoff updates `active_agent`; supervisor final authority remains with the supervisor even while work is delegated to a specialist.
- LangGraph core `StateGraph` execution is node/edge based. `Command` can update state and route to another node. Checkpointers plus thread identity provide durable multi-turn continuity.

Primary references used:

- `langchain-ai/langgraph-swarm-py` API docs for swarm, handoff, and `SwarmState`
- `langchain-ai/langgraph-supervisor-py` architecture and `create_supervisor` docs
- `docs.langchain.com/oss/python/langgraph` workflow, agent, and checkpointer docs

## Local Parity Thesis

`dharma_swarm` should satisfy LangGraph parity through existing runtime owners:

- `Task`, `TaskDispatch`, `TaskBoard`, `Orchestrator`, and A2A lifecycle own task state.
- `ExecutionIdentity`, `EvidenceReceipt`, `RuntimeReceipt`, and `IdempotencyRecord` own runtime truth.
- `HandoffProtocol`, `MessageBus`, `ContextCompiler`, and memory context parity own context movement.
- `SwarmRouter`, `ProviderPolicyRouter`, `DecisionRouter`, and `ToolRegistry` own role, provider, and tool routing.
- `BenchmarkRegistry` and Forge benchmark docs own evaluation reporting.

Future implementation may add thin adapter modules, but those modules must not become independent truth owners. They must validate, translate, or enforce the existing owners listed above.

## Custody Map

| LangGraph semantic | Local current owners | Proposed future module | Gate |
| --- | --- | --- | --- |
| `active_agent` in swarm state | `Task.assigned_to`, `TaskDispatch.agent_id`, `metadata.active_claim.agent_id`, A2A `claimed_by`, `ExecutionIdentity.agent_id` | `dharma_swarm/langgraph_parity/state_contract.py` | A |
| Handoff as `Command(goto=agent, update={messages, active_agent})` | `HandoffProtocol`, `TaskBoard.assign/requeue`, `Orchestrator._assign_dispatch`, `MessageBus.send`, A2A `claim_task` | `dharma_swarm/langgraph_parity/handoff_adapter.py` | A, C, D |
| Supervisor delegates but keeps final answer authority | `Orchestrator`, `TaskBoard.complete/fail`, A2A `allow_supervisor_block`, `RuntimeLifecycle` | `dharma_swarm/langgraph_parity/supervisor_contract.py` | B |
| `full_history` and `last_message` worker message filtering | `MessageBus.receive`, `MessageBus.build_context_from_artifacts`, `HandoffProtocol.build_context_from_handoffs`, `ContextCompiler`, memory parity tests | `dharma_swarm/langgraph_parity/message_history_policy.py` | C |
| Agent-local tools and domain boundaries | `ToolRegistry.get_definitions`, `ToolRegistry.dispatch`, `ProviderPolicyRouter`, `DecisionRouter`, `SwarmRouter`, orchestrator cell resolution | `dharma_swarm/langgraph_parity/domain_policy.py` | D |
| Checkpointed graph continuity | `DurableWorkflow`, `CheckpointStore`, `RuntimeStateStore`, `ExecutionIdentity`, `IdempotencyRecord` | `dharma_swarm/langgraph_parity/checkpoint_bridge.py` | E |
| Receipted execution evidence | `EvidenceReceipt`, `RuntimeReceipt`, `spine.persistence`, `RuntimeLifecycle`, A2A task receipts | `dharma_swarm/langgraph_parity/parity_verifier.py` | E |
| Benchmark parity metrics | `BenchmarkRegistry`, Forge benchmark docs, eval harnesses | `dharma_swarm/langgraph_parity/benchmark.py` | E |

## Acceptance Gates

### Gate A: Active Agent State and Handoff Ownership

Target: match LangGraph Swarm's explicit `active_agent` and handoff state update semantics.

Current owners:

- `dharma_swarm/models.py`: `Task.assigned_to`, `TaskDispatch.agent_id`, task metadata.
- `dharma_swarm/orchestrator.py`: dispatch assignment, active dispatch map, active claim metadata, execution identity preparation.
- `dharma_swarm/task_board.py`: claim, assign, requeue, complete, and fail transitions.
- `dharma_swarm/operator_core/a2a_task_lifecycle.py`: queue claim ownership and task closure.
- `dharma_swarm/spine/identity.py`: `ExecutionIdentity.agent_id`, `claim_id`, `run_id`, `trace_id`, `correlation_id`.

Acceptance checks:

1. Every live dispatch has exactly one `active_agent`.
2. For assigned or running local tasks, `active_agent == Task.assigned_to == TaskDispatch.agent_id == metadata.active_claim.agent_id == ExecutionIdentity.agent_id`.
3. For A2A-owned tasks, `active_agent` also matches A2A `claimed_by` while the task is claimed.
4. A handoff is atomic from the contract perspective: preserve prior messages, append a handoff/tool-equivalent event, update `active_agent`, and record `previous_agent`.
5. `default_active_agent` is explicit in the swarm plan. It is never guessed from the last message.
6. Requeue, cancellation, failure, or completion clears live ownership or moves it to a terminal owner without leaving a stale `active_agent`.
7. No adapter module may become a second writer of assignment truth. It can only call or validate the current owners.

### Gate B: Supervisor Final Authority

Target: match LangGraph Supervisor's central coordinator semantics. Workers may perform specialist work, but the supervisor owns the final user-facing answer. A local swarm may still track the worker as `active_agent`; that does not make the worker the final authority.

Current owners:

- `dharma_swarm/orchestrator.py`: fan-out, result persistence, lifecycle emission, dispatch execution.
- `dharma_swarm/task_board.py`: terminal task transitions.
- `dharma_swarm/operator_core/a2a_task_lifecycle.py`: supervisor block path with authority and evidence.
- `dharma_swarm/runtime_lifecycle.py`: route truth and runtime receipt production.

Acceptance checks:

1. Worker agents can emit artifacts, messages, and receipts, but they cannot mark a supervisor-level final answer.
2. Supervisor finalization must cite worker evidence by receipt id, artifact id, or handoff id.
3. If a supervisor blocks a task claimed by another agent, the receipt must include explicit `authority` and non-empty `evidence`, consistent with the existing A2A lifecycle guard.
4. Delegation changes `active_agent`; it does not transfer final authority away from the supervisor.
5. Final output must distinguish acted provider evidence from pending, unproven, simulated, or projection-only claims.
6. Supervisor authority must not weaken telos, safety, consent, route-truth, or lifecycle gates.

### Gate C: Message History Filtering

Target: match LangGraph Supervisor's `full_history` and `last_message` output modes while preserving local secrecy, redaction, and context budget rules.

Current owners:

- `dharma_swarm/message_bus.py`: per-agent receive filtering and artifact context assembly.
- `dharma_swarm/handoff.py`: pending handoff selection and context budget truncation.
- `dharma_swarm/context_compiler.py`: memory/context compilation.
- `tests/test_memory_context_parity.py`: projection omission and redaction expectations.

Acceptance checks:

1. `full_history` includes relevant worker messages, handoff/tool-equivalent events, and selected artifacts after redaction.
2. `last_message` includes only the worker's final non-tool message, except when the terminal observation is a tool-equivalent message required to make the final message coherent.
3. Internal scratch, hidden deliberation, raw secrets, and unredacted local filesystem paths are never surfaced as parity history.
4. A worker receives only inbound direct messages, valid broadcasts, assigned handoffs, and explicitly selected artifacts within budget.
5. Projection atoms are omitted by default unless a caller explicitly opts into projection context.
6. Filtering policy is deterministic and auditable by ids, not by ad hoc string matching.

### Gate D: Tool and Domain Isolation

Target: match LangGraph's practical isolation model where each agent is bound to its own callable tools and routed domain.

Current owners:

- `dharma_swarm/tool_registry.py`: tool definition selection, dispatch, side-effect receipts.
- `dharma_swarm/provider_policy.py`: provider/model selection with tooling, frontier, and complexity inputs.
- `dharma_swarm/decision_router.py`: reflex, deliberative, escalation, and collaboration routing.
- `dharma_swarm/swarm_router.py`: role allocation, blackboard contract, handoff order, route request context.
- `dharma_swarm/orchestrator.py`: dispatch cell and room resolution.

Acceptance checks:

1. Each role or agent receives an explicit allowed tool-name set.
2. Tool definitions exposed to an agent are exactly the allowed set after environment checks.
3. Tool dispatch is tied to `ExecutionIdentity` or an equivalent idempotent receipt path when side effects are possible.
4. Handoff targets must be present in the planned agent roster. Unknown target handoffs are rejected before side effects.
5. Domain or cell ownership must be explicit or uniquely derivable. Ambiguous room/cell membership cannot be guessed for domain-scoped action.
6. Provider routing must respect `requires_tooling`, `requires_frontier_precision`, complexity tier, role, and domain context.
7. Tool and domain denial must emit auditable failure evidence without executing the denied action.

### Gate E: Receipts, Checkpoints, and Benchmark Metrics

Target: match LangGraph's durable thread/checkpoint semantics while preserving the repo's existing runtime truth spine.

Current owners:

- `dharma_swarm/spine/invoke.py`: blessed agent invocation path.
- `dharma_swarm/spine/receipt.py`: `EvidenceReceipt`.
- `dharma_swarm/spine/persistence.py`: delegation-run receipt persistence.
- `dharma_swarm/runtime_state.py`: `RuntimeReceipt` and idempotency records.
- `dharma_swarm/runtime_lifecycle.py`: runtime producer receipts and route truth.
- `dharma_swarm/durable_execution.py`: workflow checkpoints.
- `dharma_swarm/checkpoint.py`: loop checkpoints and interrupt gates.
- `dharma_swarm/benchmark_registry.py`: benchmark registration and threshold reporting.

Acceptance checks:

1. Every logical dispatch attempt emits exactly one `EvidenceReceipt`.
2. A2A task execution emits exactly one canonical task `RuntimeReceipt` and one completed `IdempotencyRecord`; it must not add a second synthetic receipt for the same logical task.
3. Non-A2A orchestrator execution persists the dispatch `EvidenceReceipt` through the existing delegation-run receipt path or an existing runtime receipt owner.
4. No parity work may add a new truth store, new receipt authority, or parallel task state owner.
5. LangGraph `thread_id` maps to local run continuity through `ExecutionIdentity.run_id` or an explicitly documented session id, while `trace_id`, `correlation_id`, `claim_id`, and `routing_decision_id` keep their existing meanings.
6. Checkpoints occur at graph/handoff/task boundaries before and after side-effecting work.
7. Benchmark reporting includes gate pass rate, receipt completeness, import/test health, eval pass rate, latency percentiles, throughput, tool-call count, token/cost where available, provider-route truth, handoff success rate, supervisor override/block count, and `swarm_lift`.
8. `swarm_lift` is computed as `full_live_dharma_swarm_score - max(best_single_full_budget_score, same_budget_self_moa_score)`.
9. Archive or evolutionary fitness cannot be updated from candidate-only metrics; it requires external acted receipt quorum from the existing truth spine.

## Global Invariants

These invariants apply across all gates:

1. `active_agent` is the live execution owner, not a display label.
2. Supervisor final authority remains with the supervisor/orchestrator even while `active_agent` points to a worker.
3. Message history policy is explicit, deterministic, redacted, and budgeted.
4. Tool and domain access is allowlisted per agent or role.
5. Every side-effect-capable operation has receipt and idempotency coverage before it is considered real.
6. Metrics distinguish local candidate performance from externally acted, receipted outcomes.
7. Adapters may translate semantics, but existing owners remain the only sources of truth.

## Non-Goals

- Do not import or require LangGraph in runtime code as part of this contract.
- Do not create new runtime code, tests, databases, receipt tables, or task state stores in this pass.
- Do not weaken telos, consent, route-truth, lifecycle, or governance gates.
- Do not treat documentation parity as evidence that runtime parity is already implemented.

## Contract Definition of Done

The contract is complete when future implementers can answer these questions from docs and code:

1. Where is `active_agent` derived, validated, and cleared?
2. Who is allowed to synthesize the final supervisor answer?
3. Which messages are visible under `full_history` and `last_message`?
4. Which tools and domains can each agent access?
5. Which receipts prove the task, handoff, side effect, and final answer happened?
6. Which benchmark metrics prove parity without confusing candidate scores for acted outcomes?

## Adjudicated Deviations (Differential Oracle, Phase 1)

Maintained by the dharmagraph-engine-2026-07 differential oracle
(`tests/test_langgraph_differential_oracle.py`, spec §3 Phase 1). The oracle
runs the parity scenario inventory through BOTH engines — the deterministic
clone under `dharma_swarm/langgraph_parity/` and real langgraph 1.2.4 (the
`test-oracle` extra) — and diffs semantic outcomes. Every entry below is a
divergence the oracle actually observes; if a future run shows parity where
a deviation is documented, the entry is stale and MUST be removed (the
oracle enforces this in `test_rejection_receipt_deviation_is_found_and_adjudicated`).

### DEV-1: Rejected handoffs produce durable receipts (deliberate deviation)

- **Observed in:** `swarm_rejected_transfer_tool_not_visible`,
  `swarm_rejected_transfer_unknown_agent`
- **dharma:** an invalid transfer (tool not visible to the active agent, or
  target agent unknown) records a durable `TransferReceipt` with
  `status="rejected"` and the reason; the turn continues and activation
  state is unchanged.
- **langgraph 1.2.4:** such a handoff tool is never bound to the agent, so
  the call surfaces as an unbound-tool error at the tool-dispatch layer —
  no durable record of the rejected attempt exists.
- **Adjudication:** deliberate deviation, dharma keeps its behavior. The
  receipts-first doctrine (every attempted state transition leaves an
  operator-witnessable record) outranks tool-surface fidelity here.
  Activation-state parity is preserved: the final active agent is identical
  in both engines, so the deviation is bounded to evidence, not behavior.
