# LivingAgentKernel Semantic Context Receipt

Mission: `living-agent-kernel-20260605`
Agent: `codex-living-agent-kernel`
Risk: `Q3`
Generated: 2026-06-05
Receipt family: `semantic_code`

## Tooling

- Primary semantic tool attempted: `mcp__codebase_retrieval.codebase_retrieval`
- Result: unavailable, `402 Payment Required`
- Fallback semantic/structural tools used: `mcp__filesystem` and
  `mcp__contextplus`
- Context+ calls included:
  - `get_file_skeleton("dharma_swarm/operator_core/living_agent_kernel.py")`
  - `get_file_skeleton("tests/test_living_agent_kernel.py")`
  - semantic searches for durable JSONL/replay/proof-ledger and tool registry
    patterns
  - `get_file_skeleton("dharma_swarm/event_log.py")`
  - `get_file_skeleton("dharma_swarm/runtime_contract.py")`
  - `get_blast_radius("LivingAgentKernel")`
  - `get_blast_radius("KernelRunResult")`
  - `run_static_analysis("dharma_swarm/operator_core/living_agent_kernel.py")`
- Bounded-mutation continuation:
  - `mcp__codebase_retrieval.codebase_retrieval` on repo was too large, and on
    `operator_core` returned `402 Payment Required`
  - `mcp__contextplus.semantic_code_search` and `get_blast_radius` timed out
  - fallback exact inspection used `dharma_swarm/diff_applier.py`,
    `tests/test_diff_applier.py`, and
    `scripts/governance/run_agent_work_packet.py`
- External-worker continuation:
  - `mcp__contextplus.get_context_tree("dharma_swarm/operator_core")` timed out
    after 600 seconds
  - `mcp__contextplus.run_static_analysis("dharma_swarm/operator_core/living_agent_kernel_workers.py")`
    timed out after 600 seconds
  - fallback exact inspection used `KernelRunStore`, wake-ledger tests,
    service/supervisor modules, and the persistent-agent worker readiness docs
- 2026-06-06 reorientation continuation:
  - current pasted timeout was traced to Context+
    `run_static_analysis` after the service-runner smoke
  - no `run_static_analysis` or `living_agent_kernel_service` process was still
    running during reorientation
  - bounded replacement evidence used `get_file_skeleton` for
    `dharma_swarm/operator_core/living_agent_kernel_service.py`, exact local
    inspection, `ruff check`, compileall, focused/broad pytest, CLI smokes, and
    Q3 context quorum
- Reviewed-activation continuation:
  - `mcp__contextplus.get_file_skeleton` inspected supervisor and worker
    modules before expansion
  - Q3 pre-edit quorum passed for the planned activation/worker-process file
    set with `allowed_next_action=bounded_action_allowed`
  - fallback exact inspection used supervisor plan/status tests, external worker
    lifecycle tests, service runner boundaries, and activation receipt symbols
  - a CLI smoke found an activation hash-chain race under parallel receipt
    appends; the activation appender now takes a file lock and focused tests
    cover concurrent review receipts
- Launch start/status continuation:
  - exact local inspection covered `launch_artifact_status(...)`,
    `start_installed_supervisor_artifact(...)`, activation CLI subcommands, and
    focused tests
  - deterministic evidence used compileall, ruff, focused/broad pytest, a
    dry-run start/status CLI smoke, and activation-ledger verification
  - final Q3 context quorum passed with
    `task_id=living-agent-kernel-launch-start-status-v1`,
    `allowed_next_action=bounded_action_allowed`, and `missing_families=[]`
  - no implicit launchctl, tmux session start, cron install, provider execution,
    network, browser, git, payment, deploy, publish, push/merge, or external
    outreach was authorized or performed
- Promotion/provider/status continuation:
  - GitNexus index was known stale from reorientation; impact lookup on
    provider core had previously shown high fanout, so the slice avoided
    modifying `providers.py`, router policy, or shared provider classes
  - exact local inspection covered `KernelExternalWorkerStore`,
    `LLMRequest`/`LLMResponse`, runtime provider factory boundaries, activation
    receipts, worker result completion, and status projection surfaces
  - deterministic evidence used focused provider-promotion tests, broad
    LivingAgentKernel bundle, ruff, compileall, `make onboard`, and Q3 context
    quorum
  - final Q3 context quorum passed with
    `task_id=living-agent-kernel-promotion-provider-worker-v1`,
    `allowed_next_action=bounded_action_allowed`, and `missing_families=[]`
  - no shared provider/router mutation, live network provider call, implicit
    launchctl/tmux activation, subprocess tool runtime, browser, git, payment,
    deploy, publish, push/merge, or external outreach was authorized or
    performed
- Provider tool-boundary continuation:
  - the interrupted state was rechecked against the live filesystem and
    unresolved conflict markers were absent from the provider worker, runtime
    script, and focused promotion/provider tests
  - exact local inspection covered `KernelProviderToolBoundary`,
    `evaluate_provider_tool_boundary(...)`, `build_provider_request(...)`,
    `execute_provider_worker_cycle(...)`, and terminal wake `tool_boundary`
    result refs
  - deterministic evidence used compileall, ruff, focused promotion/provider
    tests, a fixture-backed provider-worker CLI smoke, durable receipt
    inspection, and the broad LivingAgentKernel regression bundle
  - the CLI smoke completed `wake-provider-tool-boundary` under
    `/private/tmp/lak_provider_tool_boundary_5ygHsj`
  - receipt inspection showed requested wake tools remained context-only:
    `provider_may_execute_tools=false`, delegated tools
    `["provider_complete"]`, and denied delegated tools `["read_file",
    "session_status"]`
  - final Q3 context quorum passed with
    `task_id=living-agent-kernel-provider-tool-boundary-v1`,
    `allowed_next_action=bounded_action_allowed`, and `missing_families=[]`;
    `tests/test_living_agent_kernel_promotion_provider.py` was flagged as a
    measurement-protected surface and covered by focused/broad verifier runs
  - no live provider network call, provider-side tool execution, shared
    provider/router mutation, launchctl/tmux activation, subprocess tool
    runtime, browser, git, payment, deploy, publish, push/merge, or external
    outreach was authorized or performed
- Crash-resume continuation:
  - added `build_kernel_crash_resume_snapshot(...)` and
    `recover_kernel_after_crash(...)` in a separate recovery module to avoid
    expanding the kernel god object
  - snapshot reconstructs wake, daemon, supervisor, worker, activation,
    launch-artifact, and worker-result state without mutation
  - recovery blocks on ledger-integrity failures and requeues only expired
    stale/offline worker leases or non-worker kernel leases through existing
    recovery paths
  - focused tests prove cross-ledger reconstruction, fresh-worker lease
    preservation, tamper blocking, and CLI snapshot/recover behavior
  - CLI smoke under `/private/tmp/lak_crash_resume_probe_h91JNm` proved
    `snapshot -> recover -> wake/worker ledger verify` without provider or
    service activation
  - final Q3 context quorum passed with
    `task_id=living-agent-kernel-crash-resume-v1`,
    `allowed_next_action=bounded_action_allowed`, and `missing_families=[]`

## Relevant Surfaces

### Governed Work Admission

`dharma_swarm/operator_core/governed_work_admission.py`

- `WorkKind` covers read-only, code-write, long-running, A2A claim,
  self-evolution, and promotion work.
- `evaluate_governed_work_admission` emits allow/review/block with reasons and
  required receipts.

Kernel implication: the kernel must call this function rather than fork policy.

### Runtime Truth

`dharma_swarm/operator_core/runtime_truth.py`

- `RuntimeTruthPacket` is the shell-neutral projection contract.
- `stable_payload_hash`, `sha256_file`, and `file_ref` are the stable proof
  helpers.

Kernel implication: every `KernelRunResult` should include runtime truth and
stable source/proof references.

### Canonical Runtime Events

`dharma_swarm/event_log.py` and `dharma_swarm/runtime_contract.py`

- `EventLog` appends validated runtime envelopes to JSONL streams.
- `RuntimeEnvelope` validates action and audit event payloads with checksums.
- `EventLog.read_envelopes` and `verify_stream` provide replay and integrity.

Kernel implication: the v1 kernel should persist `run_started`, tool lifecycle,
and `run_finished` rows through `EventLog`.

### Tool Registry Pattern

`dharma_swarm/tool_registry.py`

- The shared registry has schemas, dispatch, availability checks, and wrapped
  errors.
- It is broad and import-mutable, so the v1 kernel keeps a small owned
  registry plus a kernel-intercepted `apply_patch` adapter so write authority
  and sandbox policy are evaluated from the full run envelope.

### Diff Rollback Primitive

`dharma_swarm/diff_applier.py`

- `parse_unified_diff` identifies file targets from standard unified diffs.
- `DiffApplier.apply(diff, dry_run=True)` validates targets without mutation.
- `DiffApplier.apply(diff, dry_run=False)` writes files and records adjacent
  `.bak` rollback paths for existing files.

Kernel implication: the kernel may use this only after its own allowed-file,
forbidden-file, sandbox-policy, and rollback-safety checks. It must not call
`DiffApplier.apply_and_test` yet because that runs subprocess shell commands.

## Implemented v1 Slice

```text
AgentRunEnvelope
  -> evaluate_governed_work_admission
  -> ToolPlan
  -> KernelReadOnlyToolRegistry.dispatch(optional read-only tool calls)
  -> KernelRunStore.append_event / append_tool_result / append_proof_entry
  -> KernelRunResult
  -> KernelRunStore.replay_run(run_id)

source payload
  -> LivingAgentKernel.normalize_wake_source
  -> LivingAgentKernel.enqueue_source_wake
  -> LivingAgentKernel.run_next_wake
  -> LivingAgentKernel.closeback_source_wake
  -> KernelRunStore.record_wake_closeback

code-write envelope + unified diff
  -> LivingAgentKernel._dispatch_apply_patch
  -> DiffApplier.apply(dry_run by default)
  -> KernelToolResult backup refs
  -> RuntimeTruthPacket.mutation_truth

control tick
  -> LivingAgentKernel.recover_expired_wakes
  -> LivingAgentKernel.run_next_wake
  -> LivingAgentKernel.closeback_source_wake
  -> LivingAgentKernel.latest_wake_status

restart snapshot
  -> KernelRunStore.control_snapshot
  -> LivingAgentKernel.control_snapshot
  -> queued/leased/expired/terminal wake classification

parent AgentRunEnvelope
  -> LivingAgentKernel.spawn_subagent_wake
  -> inherited authority and subagent limits
  -> child AgentRunEnvelope(source=subagent)
  -> KernelRunStore.enqueue_wake
  -> LivingAgentKernel.run_control_tick
  -> subagent delivery closeback receipt

operator daemon control request
  -> LivingAgentKernel.request_daemon_control
  -> KernelRunStore.append_daemon_control
  -> LivingAgentKernel.daemon_control_state
  -> LivingAgentKernel.run_daemon_cycle
  -> skipped paused/stopped cycle | run_control_tick
  -> KernelRunStore.append_daemon_cycle

external service runner
  -> run_kernel_daemon_service
  -> daemon_service.lock
  -> bounded repeated LivingAgentKernel.run_daemon_cycle calls
  -> scripts/runtime/living_agent_kernel_service.py --json

supervisor dry-run planner
  -> build_supervisor_plan
  -> write_supervisor_plan
  -> launchd/tmux review artifacts
  -> supervisor_status
  -> scripts/runtime/living_agent_kernel_supervisor.py plan|status

external worker lifecycle
  -> KernelExternalWorkerStore.register_worker
  -> KernelExternalWorkerStore.heartbeat_worker
  -> KernelExternalWorkerStore.lease_worker_wake
  -> existing KernelRunStore.lease_next_wake
  -> KernelExternalWorkerStore.complete_worker_wake
  -> KernelRunStore.complete_external_wake
  -> KernelExternalWorkerStore.recover_stale_worker_leases
  -> scripts/runtime/living_agent_kernel_worker.py

reviewed activation
  -> build_worker_process_command
  -> command_hash
  -> activate_worker_process | activate_supervisor_plan
  -> KernelActivationStore.append_activation
  -> activation_receipts.jsonl
  -> scripts/runtime/living_agent_kernel_worker_process.py
  -> worker registration and heartbeat receipts

launch start/status
  -> install_supervisor_plan
  -> activation_receipts.jsonl launch_artifact receipt
  -> launch_artifact_status content hash preflight
  -> start_installed_supervisor_artifact
  -> activation_receipts.jsonl launch_start receipt
  -> scripts/runtime/living_agent_kernel_activation.py supervisor-start|supervisor-launch-status

crash resume
  -> build_kernel_crash_resume_snapshot
  -> wake/daemon/worker/activation/launch/result receipt projection
  -> recover_kernel_after_crash
  -> existing worker/wake expired-lease recovery paths
  -> scripts/runtime/living_agent_kernel_recovery.py snapshot|recover

promotion/provider/status
  -> KernelPromotionStore.append_promotion / revoke_promotion
  -> KernelPromotionStore.evaluate_worker_admission
  -> KernelExternalWorkerStore.register_worker / heartbeat / lease_worker_wake
  -> evaluate_provider_tool_boundary(context-only requested tool visibility)
  -> build_provider_request
  -> injected, fixture, or explicit live provider completion boundary
  -> KernelProviderWorkerStore.append_receipt
  -> KernelExternalWorkerStore.complete_worker_wake(provider_execution=true)
  -> living_agent_os_status
  -> scripts/runtime/living_agent_kernel_promotion.py
  -> scripts/runtime/living_agent_kernel_provider_worker.py
  -> scripts/runtime/living_agent_kernel_status.py
```

## Required Negative Tests

- read-only manual envelope succeeds without provider credentials;
- code-write envelope without mission contract returns review;
- self-evolution envelope without mutation budget blocks;
- protected-file hits block;
- high-risk missing context quorum blocks;
- external-fleet wake rows remain evidence-only and cannot mutate source queues;
- external worker lifecycle remains receipt-backed and does not grant broad
  provider or action-tool execution authority;
- unpromoted provider workers cannot lease wakes and leave queued wakes intact;
- expired or revoked promotions block provider execution;
- provider workers require explicit promoted source/tool/work-kind authority;
- provider tool boundaries record requested wake tools as context only and keep
  `provider_may_execute_tools=false`;
- provider request payloads, provider-worker receipts, and terminal wake result
  refs must not grant provider-side execution of wake-requested tools unless a
  separate kernel receipt explicitly executes them;
- provider worker result rows are hash-chained and referenced by terminal wake
  rows;
- blocked authority records denied tool results without dispatch;
- `read_file` denies reads without explicit `allowed_files`;
- A2A source closeback closes only with persisted kernel proof and a validated
  A2A receipt;
- ds-goal source closeback records kernel result refs without falsely closing
  autonomy-spine tasks;
- persistent self-wake closeback writes witness receipts with kernel result refs;
- external-fleet closeback refuses source mutation;
- latest-wake status projects compact operator-visible state;
- read-only envelopes cannot execute `apply_patch`;
- dry-run `apply_patch` validates allowed unified diffs without mutation;
- live `apply_patch` requires explicit sandbox allowance and rollback receipt
  policy;
- live `apply_patch` records rollback backup paths and truthful mutation state;
- `apply_patch` denies targets outside `allowed_files`;
- no unrestricted provider, shell, network, browser, git, `pytest`, or
  `compileall` execution occurs;
- control tick recovers expired leases before execution;
- control tick executes bounded queued wakes and automatically records source
  closeback when source roots are provided;
- control snapshot reports empty stores as integrity-ok;
- a fresh kernel instance can open the same store, classify an expired lease,
  and recover it through `run_control_tick`;
- subagent child wakes inherit parent authority and parent-run lineage;
- subagent spawn denies disallowed agents and allowed-file escalation;
- subagent spawn respects max-child and max-depth limits;
- subagent closeback records delivery receipts without live worker-process
  spawning;
- daemon pause/stop controls block cycles without leasing queued wakes;
- daemon resume allows queued wakes to run through `run_control_tick`;
- daemon cycle receipts include heartbeat refs and next-run timestamps;
- daemon control and cycle hash ledgers detect tampering;
- service runner executes bounded repeated cycles without creating another
  queue;
- held service locks prevent split-brain and append no cycle receipts;
- durable stop controls end the service loop without dropping queued wakes;
- service CLI emits JSON and writes daemon-cycle receipts;
- supervisor plans render default-off launchd/tmux artifacts without starting
  processes;
- supervisor status derives never-ran/recent/stale from daemon-cycle receipts;
- supervisor CLI emits JSON plan/status receipts;
- external workers cannot lease wakes unless registered and freshly heartbeating;
- source-filtered external workers do not lease ineligible wake sources;
- external worker result receipts mark existing wake rows terminal without
  fabricating a `KernelRunResult`;
- stale/offline external worker recovery only requeues expired leases owned by
  stale/offline registered workers;
- external worker ledgers verify hash-chain continuity;
- supervisor activation denies mismatched plan hashes and does not call the
  launcher;
- worker process activation denies mismatched command hashes and does not
  register workers;
- bounded worker-process subprocesses write registration and heartbeat receipts;
- concurrent activation receipt appends preserve hash-chain continuity;
- activation CLI review commands do not start the forever service unless
  explicit live launch is requested;
- launch start review verifies the installed artifact content hash before
  recording a `launch_start` receipt;
- launch status reports `started` only after an activated start receipt, not
  after dry-run review alone;
- crash-resume recovery blocks on ledger-integrity failure;
- crash-resume recovery does not recover leases owned by fresh workers;
- crash-resume CLI recovery leaves wake and worker ledgers verifiable;
- external worker CLI emits JSON lifecycle receipts;
- proof-ledger hash-chain verification detects tampering.

## Receipt Conclusion

The durable v1 slice reuses existing runtime envelopes, stable payload hashes,
governed admission, A2A close receipts, autonomy-spine task rows,
`DiffApplier`, and runtime truth without creating a duplicate queue, router,
dashboard substrate, memory plane, active launchd/systemd process, or shell
executor. The worker lifecycle continuation adds
receipt-backed worker registration, heartbeats, source-filtered leases,
terminal result refs, and stale lease recovery. The reviewed-activation
continuation adds hash-gated activation receipts and a bounded worker heartbeat
process. The worker-execution continuation adds explicit `--execute` mode that
leases a wake, runs the original envelope through the provider-free kernel path,
and completes the wake with external-worker result refs pointing to real replay
and proof hashes. The reviewed-launch-install continuation writes exact
hash-approved launchd/tmux artifacts into an explicit operator-owned install
directory while recording `launch_started=false`. The launch start/status
continuation adds install-receipt lookup, content-hash preflight, dry-run start
reviews, injected live-launch tests, CLI status projection, and hash-chain
verification without implicitly calling launchctl or starting tmux. The next
crash-resume continuation adds a cross-ledger restart packet and explicit
expired-lease recovery while blocking on ledger tamper evidence. The
promotion/provider/status continuation adds hash-chained promotion receipts, a
fail-closed provider-worker boundary over existing wake leases, provider result
receipts, and an operator OS status packet. The provider tool-boundary
continuation hardens that boundary so requested wake tools are visible as
context only and provider-side delegated execution remains limited to
`provider_complete`. The next action is live provider smoke plus full
tool-call execution gates over the durable kernel store.
