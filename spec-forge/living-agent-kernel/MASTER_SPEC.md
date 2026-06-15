---
title: LivingAgentKernel Master Build Spec
path: spec-forge/living-agent-kernel/MASTER_SPEC.md
slug: living-agent-kernel-master-build-spec
doc_type: master_spec
status: draft
created: 2026-06-05
owner: ds-goal / PGE / Codex verification loop
scope: spec-forge incubation, not normative specs truth
summary: Master build specification for unifying dharma_swarm persistent-agent, fleet, memory, authority, tool, wake, and receipt organs into one LivingAgentKernel contract.
---

# LivingAgentKernel Master Build Spec

Date: 2026-06-05
Status: draft in `spec-forge/`
Target repo: `/Users/dhyana/dharma_swarm`
Risk: Q3 until contracts and negative tests prove safe

## Implemented Slice: v1 Durable Runtime + Wake Ledger + Source Closeback + Bounded Mutation + Control Tick + Restart Snapshot + Subagent Wakes + Daemon Controls + Service Runner + Supervisor Plans + External Worker Lifecycle + Reviewed Activation + Worker Wake Execution + Reviewed Launch Install + Launch Start Status + Crash Resume Snapshot + Promotion Gate + Provider Worker Boundary + Provider Tool Boundary + OS Status

The first no-op contract slice has been superseded by a durable read-only
runtime slice in `dharma_swarm/operator_core/living_agent_kernel.py`.

Current implemented claims:

- `LivingAgentKernel.run(envelope)` reduces authority through
  `evaluate_governed_work_admission`;
- `ToolPlan` includes stable policy hashes, read-only tool schemas, and the
  bounded `apply_patch` schema under code-write authority;
- `KernelReadOnlyToolRegistry` dispatches `session_status`, `memory_read`,
  `read_file`, and `search_files`; `apply_patch` is intercepted by the kernel
  write adapter so it can see authority and sandbox policy;
- `read_file` enforces explicit `AuthorityPassport.allowed_files` at dispatch;
- `KernelRunStore` appends canonical runtime events, tool-result receipts, and
  hash-chained proof ledger rows;
- `KernelRunStore.replay_run(run_id)` returns events, proofs, tool results,
  replay hash, and integrity status;
- `KernelRunStore` owns an append-only `wake_ledger.jsonl` with queued,
  leased, terminal, and expired-lease recovery rows;
- `LivingAgentKernel.wake(...)` can enqueue one `AgentRunEnvelope`, lease it,
  execute it through `run(...)`, and append terminal wake state;
- `LivingAgentKernel.normalize_wake_source(...)` maps manual, A2A, ds-goal,
  persistent-self-wake, and external-fleet payloads into `AgentRunEnvelope`;
- `LivingAgentKernel.enqueue_source_wake(...)` persists normalized source wakes
  onto the existing append-only wake ledger;
- `LivingAgentKernel.closeback_source_wake(...)` can close A2A queue rows with
  kernel proof receipts, record kernel result refs on ds-goal task rows, append
  persistent self-wake witness receipts, and refuse external-fleet source
  mutation;
- `LivingAgentKernel.latest_wake_status(...)` projects compact operator state
  over the append-only wake ledger;
- bounded `apply_patch` execution validates unified diffs against
  `AuthorityPassport.allowed_files`/`forbidden_files`, dry-runs by default, and
  requires explicit sandbox flags plus rollback backup evidence for live apply;
- `LivingAgentKernel.run_control_tick(...)` recovers expired wake leases,
  executes a bounded number of queued wakes, automatically records source
  closeback, and returns latest operator-visible wake status;
- `LivingAgentKernel.control_snapshot(...)` replays persisted wake state after
  restart, classifies queued/leased/expired/terminal wakes, and reports wake
  ledger integrity;
- `LivingAgentKernel.spawn_subagent_wake(...)` creates bounded child wakes over
  the existing wake ledger with inherited authority, parent-run lineage,
  allowed-agent/max-depth/max-child limits, and non-elevating file scope;
- subagent wakes execute through `run_control_tick(...)` and record subagent
  delivery closeback receipts;
- `LivingAgentKernel.request_daemon_control(...)` records durable
  pause/resume/stop controls;
- `LivingAgentKernel.run_daemon_cycle(...)` checks daemon controls, skips work
  while paused/stopped, invokes `run_control_tick(...)` while running, and
  records daemon heartbeat receipts;
- `run_kernel_daemon_service(...)` repeatedly invokes `run_daemon_cycle(...)`
  under a non-blocking file lock;
- `scripts/runtime/living_agent_kernel_service.py` exposes the service runner
  as a bounded CLI with JSON output;
- `build_supervisor_plan(...)` renders default-off launchd/tmux supervisor
  plans for operator review without starting processes;
- `supervisor_status(...)` derives recent/stale/never-ran state from
  daemon-cycle receipts;
- `scripts/runtime/living_agent_kernel_supervisor.py` exposes dry-run plan and
  status JSON commands;
- `KernelExternalWorkerStore` records external worker registration,
  heartbeats, leases, terminal result receipts, and stale-worker recovery
  receipts over the existing kernel store;
- external workers must have fresh heartbeats before leasing wake rows;
- external worker leases can be source-filtered without creating another queue;
- external worker results mark leased wakes terminal through
  `KernelRunStore.complete_external_wake(...)` and reference immutable worker
  result hashes;
- stale/offline external workers can have expired wake leases requeued through
  the existing wake ledger;
- `scripts/runtime/living_agent_kernel_worker.py` exposes register, heartbeat,
  status, lease, complete, recover, and verify JSON commands;
- `KernelActivationStore` records hash-chained reviewed activation receipts for
  supervisor service commands and worker process commands;
- supervisor activation requires the exact `KernelSupervisorPlan.receipt_hash`
  before a service command can be reviewed or launched through an injected
  launcher;
- worker process activation requires the exact reviewed command hash before a
  bounded worker process can be reviewed or launched through an injected
  launcher;
- `scripts/runtime/living_agent_kernel_worker_process.py` provides a bounded
  live worker heartbeat process that registers, heartbeats, and optionally
  leases wakes;
- explicit worker `--execute` mode leases eligible wakes, runs the original
  `AgentRunEnvelope` through `LivingAgentKernel.run`, completes the leased wake
  with an external-worker result receipt, and points that receipt to real kernel
  replay/proof hashes;
- `scripts/runtime/living_agent_kernel_activation.py` exposes worker command
  planning, reviewed worker launch receipts, reviewed supervisor activation
  receipts, and reviewed supervisor artifact installation;
- `install_supervisor_plan(...)` installs the exact reviewed launchd plist or
  tmux script into an explicit operator-owned install directory and records
  `launch_started=false`;
- `start_installed_supervisor_artifact(...)` verifies an installed activation
  receipt and launch artifact content hash before recording a launch-start
  review receipt or invoking an explicit live launcher;
- `launch_artifact_status(...)` reports unknown, missing, changed, installed,
  or started state from activation receipts and installed artifact content
  hashes;
- `scripts/runtime/living_agent_kernel_activation.py` exposes
  `supervisor-start` and `supervisor-launch-status` JSON commands over installed
  launch artifact receipts;
- `build_kernel_crash_resume_snapshot(...)` reconstructs cross-ledger restart
  state from wake, daemon, worker, activation, launch, and worker-result
  receipts without mutation;
- `recover_kernel_after_crash(...)` refuses bad ledger integrity and explicitly
  requeues only already-expired wake leases owned by stale/offline workers or
  non-worker kernel owners;
- `scripts/runtime/living_agent_kernel_recovery.py` exposes `snapshot` and
  `recover` JSON commands for restart inspection and bounded recovery;
- `KernelPromotionStore` records hash-chained promotion, denial, and revocation
  receipts for persistent agent identities before provider work is admitted;
- promotion admission checks level, source, tool, work kind, expiry, revocation,
  lease limits, and provider-executor evidence before granting reduced worker
  authority;
- `KernelProviderWorkerStore` records hash-chained provider-worker execution
  receipts with request/response hashes and promotion refs;
- `KernelProviderToolBoundary` records requested wake tools, requested tool-call
  names, promoted provider tools, delegated provider tools, denied delegated
  tools, and `provider_may_execute_tools=false`;
- `execute_provider_worker_cycle(...)` registers a promoted provider worker,
  heartbeats, leases an eligible wake through the existing external-worker
  store, calls an injected/fixture/live provider boundary, and completes the
  wake with `provider_execution=true` receipt refs;
- provider workers fail closed: missing promotion leaves wakes queued, missing
  provider configuration records failure rather than success, and source
  mismatch blocks the leased wake;
- `living_agent_os_status(...)` combines wake snapshot, worker states, latest
  promotions, activation count, provider-worker receipt count, and per-ledger
  integrity into one operator-visible packet;
- `scripts/runtime/living_agent_kernel_promotion.py`,
  `scripts/runtime/living_agent_kernel_provider_worker.py`, and
  `scripts/runtime/living_agent_kernel_status.py` expose promotion management,
  bounded provider-worker cycles, and OS status JSON commands;
- general tool-calling provider agents, `pytest`/`compileall` subprocess
  execution inside the kernel, unreviewed launchd/systemd/tmux scheduling, real
  launchctl/tmux live smoke outside injected tests, memory mutation,
  provider-backed crash replay, and unbounded external action authority remain
  unsupported.

Next work should target operator-approved live provider smoke, full agent
tool-call delegation gates, and live service supervision receipts under explicit
operator approval, not another no-op facade.

## North Star

Powerful agents are not just model calls plus Python files. Their power comes
from a complete operating contract:

1. stable identity;
2. durable trigger and run state;
3. explicit authority and sandbox policy;
4. tool inventory compiled for the current run;
5. memory read/write plan with provenance;
6. subagent lifecycle and handoff rules;
7. proof ledger and runtime truth projection;
8. feedback loop for learning, skill evolution, and promotion;
9. operator-visible receipts and stop conditions.

The target remains Hermes-grade continuity, OpenClaw-grade authority routing,
LangGraph-grade durable state discipline, and dharma_swarm-grade receipt truth.

## Product Contract

```text
LivingAgentKernel.run(envelope: AgentRunEnvelope) -> KernelRunResult
LivingAgentKernel.wake(envelope: AgentRunEnvelope, ...) -> KernelWakeExecution
LivingAgentKernel.normalize_wake_source(source, payload, ...) -> AgentRunEnvelope
LivingAgentKernel.enqueue_source_wake(source, payload, ...) -> KernelWakeRecord
LivingAgentKernel.run_next_wake(...) -> KernelWakeExecution
LivingAgentKernel.run_control_tick(...) -> KernelControlTick
LivingAgentKernel.control_snapshot(...) -> KernelControlSnapshot
LivingAgentKernel.spawn_subagent_wake(parent_envelope, ...) -> KernelSubagentDispatch
LivingAgentKernel.request_daemon_control(action, ...) -> KernelDaemonControlReceipt
LivingAgentKernel.daemon_control_state(...) -> KernelDaemonState
LivingAgentKernel.run_daemon_cycle(...) -> KernelDaemonCycle
run_kernel_daemon_service(...) -> KernelDaemonServiceRun
scripts/runtime/living_agent_kernel_service.py --cycles N --json
build_supervisor_plan(...) -> KernelSupervisorPlan
supervisor_status(...) -> KernelSupervisorStatus
scripts/runtime/living_agent_kernel_supervisor.py plan|status
KernelExternalWorkerStore.register_worker(...) -> KernelExternalWorkerRecord
KernelExternalWorkerStore.heartbeat_worker(...) -> KernelExternalWorkerHeartbeat
KernelExternalWorkerStore.lease_worker_wake(...) -> KernelExternalWorkerLease
KernelExternalWorkerStore.complete_worker_wake(...) -> KernelExternalWorkerResult
KernelExternalWorkerStore.recover_stale_worker_leases(...) -> KernelExternalWorkerRecovery
KernelExternalWorkerStore.verify_worker_ledgers() -> tuple[bool, list[str]]
scripts/runtime/living_agent_kernel_worker.py register|heartbeat|status|lease|complete|recover|verify
activate_supervisor_plan(...) -> KernelActivationReceipt
install_supervisor_plan(...) -> KernelActivationReceipt
start_installed_supervisor_artifact(...) -> KernelActivationReceipt
launch_artifact_status(...) -> KernelLaunchArtifactStatus
build_kernel_crash_resume_snapshot(...) -> KernelCrashResumeSnapshot
recover_kernel_after_crash(...) -> KernelCrashRecoveryRun
build_worker_process_command(...) -> list[str]
activate_worker_process(...) -> KernelActivationReceipt
KernelActivationStore.verify_activation_ledger() -> tuple[bool, list[str]]
scripts/runtime/living_agent_kernel_worker_process.py --worker-id ID --cycles N --json
scripts/runtime/living_agent_kernel_worker_process.py --worker-id ID --execute --json
scripts/runtime/living_agent_kernel_activation.py worker-plan|worker-launch|supervisor-activate|supervisor-install
scripts/runtime/living_agent_kernel_activation.py supervisor-start|supervisor-launch-status
scripts/runtime/living_agent_kernel_recovery.py snapshot|recover
KernelPromotionStore.append_promotion(...) -> KernelPromotionReceipt
KernelPromotionStore.revoke_promotion(...) -> KernelPromotionReceipt
KernelPromotionStore.evaluate_worker_admission(...) -> KernelPromotionAdmission
KernelPromotionStore.verify_promotion_ledger() -> tuple[bool, list[str]]
KernelProviderWorkerStore.append_receipt(...) -> KernelProviderWorkerReceipt
KernelProviderWorkerStore.verify_provider_worker_ledger() -> tuple[bool, list[str]]
build_provider_request(...) -> LLMRequest
evaluate_provider_tool_boundary(...) -> KernelProviderToolBoundary
execute_provider_worker_cycle(...) -> KernelProviderWorkerCycleResult
living_agent_os_status(...) -> KernelOSStatus
scripts/runtime/living_agent_kernel_promotion.py promote|revoke|status|verify
scripts/runtime/living_agent_kernel_provider_worker.py --cycles N --fixture-response TEXT
scripts/runtime/living_agent_kernel_status.py --store-dir PATH
LivingAgentKernel.closeback_source_wake(wake_record, result, ...) -> KernelSourceCloseback
LivingAgentKernel.latest_wake_status(...) -> list[dict[str, Any]]
LivingAgentKernel.recover_expired_wakes(...) -> list[KernelWakeRecord]
LivingAgentKernel.compile_tool_plan(envelope) -> ToolPlan
LivingAgentKernel.evaluate_authority(envelope) -> GovernedWorkAdmission
LivingAgentKernel.record_proof(...) -> ProofLedgerEntry
KernelRunStore.replay_run(run_id: str) -> KernelRunReplay
KernelRunStore.verify_wake_ledger() -> tuple[bool, list[str]]
KernelRunStore.verify_daemon_control_ledger() -> tuple[bool, list[str]]
KernelRunStore.verify_daemon_cycle_ledger() -> tuple[bool, list[str]]
```

## Current Surface

- `AgentRunEnvelope`: task, trigger, authority, memory, tool request, proof;
- `AuthorityPassport`: work kind, risk tier, contracts, leases, scanner,
  context quorum, protected hits, mutation budget;
- `ToolPlan`: visible tools, denied tools, denial reasons, read-only schemas,
  sandbox projection, inherited limits, diagnostics, policy hash;
- bounded `apply_patch` adapter: unified-diff validation, allowed/forbidden
  target checks, dry-run and explicit live-apply modes, rollback backup refs;
- `KernelControlTick`: one bounded supervisor tick over recovery, wake
  execution, source closeback, and latest operator status projection;
- `KernelControlSnapshot`: persisted wake-ledger replay for queued, leased,
  expired, and terminal wake classes plus integrity state;
- `KernelSubagentDispatch`: child-wake spawn/deny result with parent-run,
  child-run, child-agent, wake id, reason, and inherited-authority projection;
- `KernelDaemonControlReceipt`: append-only pause/resume/stop operator control
  receipt;
- `KernelDaemonState`: derived running/paused/stopped state for a daemon id;
- `KernelDaemonCycle`: one callable service-cycle receipt with control state,
  optional control tick, heartbeat ref, and next-run timestamp;
- `KernelDaemonServiceRun`: external runner result with lock ref, requested
  cycles, completed cycles, and per-cycle receipts;
- `KernelSupervisorPlan`: default-off launchd/tmux supervisor artifact plan
  with service command, artifact refs, and receipt hash;
- `KernelSupervisorStatus`: never-ran/recent/stale status derived from daemon
  cycle receipts;
- `KernelExternalWorkerRecord`: registered worker id, role, allowed wake
  sources, max lease seconds, metadata, and hash-chain refs;
- `KernelExternalWorkerHeartbeat`: online/offline liveness receipt for worker
  freshness gates;
- `KernelExternalWorkerLease`: leased/idle/denied result for worker wake
  claims over the existing `wake_ledger.jsonl`;
- `KernelExternalWorkerResult`: worker terminal result receipt referenced by
  the terminal wake row;
- `KernelExternalWorkerRecovery`: stale/offline worker recovery receipt listing
  recovered expired wake ids;
- `KernelActivationReceipt`: hash-chained reviewed activation receipt for a
  supervisor service command, worker process command, installed launch
  artifact, or launch-start action;
- `KernelLaunchArtifactStatus`: receipt-derived installed-artifact status with
  content-hash preflight and latest activated start ref;
- `KernelCrashResumeSnapshot`: read-only cross-ledger restart packet over wake,
  daemon, worker, activation, launch, and result receipts;
- `KernelCrashRecoveryRun`: explicit bounded recovery receipt projection that
  records before/after snapshots and recovered expired wake ids;
- `KernelPromotionReceipt`: hash-chained agent promotion/denial/revocation row
  with level, allowed sources/tools/work kinds, lease cap, expiry, reviewer, and
  evidence refs;
- `KernelPromotionAdmission`: allow/block projection over requested source,
  work kind, tools, level, and reduced worker authority;
- `KernelProviderWorkerReceipt`: provider-worker execution result row with
  provider/model, request hash, response hash, response content, promotion ref,
  lease ref, and error field;
- `KernelProviderToolBoundary`: context-only provider tool boundary showing
  wake-requested tools, delegated provider tools, denied delegated tools, and
  `provider_may_execute_tools=false`;
- `KernelOSStatus`: operator packet over wake snapshot, worker states, latest
  promotions, activation count, provider-worker receipt count, and ledger
  integrity map;
- `KernelProcessLaunch`: bounded process launch observation returned by an
  injected launcher or local subprocess wrapper;
- `KernelWorkerProcessRun`: bounded worker process run receipt with heartbeat,
  lease, execution, and worker-result refs;
- `KernelRunStore`: `kernel_events.jsonl`, `tool_results.jsonl`,
  `proof_ledger.jsonl`, `wake_ledger.jsonl`, `daemon_control.jsonl`,
  `daemon_cycles.jsonl`, `worker_registry.jsonl`, `worker_heartbeats.jsonl`,
  `worker_leases.jsonl`, `worker_results.jsonl`, `worker_recoveries.jsonl`,
  `promotion_receipts.jsonl`, `provider_worker_results.jsonl`,
  source-closeback wake projection, replay and integrity checks;
- `KernelSourceCloseback`: source mutation/refusal receipt over A2A, ds-goal,
  persistent self-wake, external fleet, or manual wake sources;
- `RuntimeTruthPacket`: projection over authority, progress, completion, and
  source refs.

## Non-Negotiables

- Do not create a duplicate daemon, queue, generic router, dashboard substrate,
  memory plane, provider adapter, or agent framework.
- Do not claim agent OS, scheduler, sandbox, self-evolving agent, provider tool
  runtime, or benchmark-proven capability from this slice.
- Do not claim a general provider-agent runtime from the provider-worker slice:
  it is one promoted worker boundary for completing leased wakes with provider
  response receipts, not a full tool-using subagent.
- Do not claim general write-tool execution: only bounded unified-diff
  `apply_patch` has sandbox/rollback tests; subprocess gates still do not run.
- Do not upgrade external workers beyond receipt-backed wake leasing/completion
  without a human-approved contract and live worker/process tests.
- Rerun context quorum before expanding beyond the current file set.

## Completed Slice: Source Closeback + Operator Inspection

Terminal closeback and inspectability now exist for normalized source wakes:

- A2A queue rows can be closed with kernel proof receipts;
- ds-goal task rows can receive kernel result receipt refs;
- persistent self-wake receipts can point to kernel replay hashes;
- external fleet rows remain evidence-only and cannot mutate source queues;
- operator views can inspect latest wake state, source hash, lease owner,
  terminal result, and replay/proof refs.

Acceptance requirements:

- no source closeback without kernel result proof;
- no source queue mutation for external evidence-only workers;
- durable source refs for every closeback;
- no provider execution;
- no duplicate runner, daemon, or global queue;
- focused tests plus context quorum.

## Completed Slice: Bounded Sandboxed Mutation Adapter

Move from read-only operational closeback into bounded action execution:

- sandboxed `apply_patch` execution through a kernel-owned adapter;
- explicit write-set leases and rollback backup artifacts before live mutation;
- dry-run default for all patch calls;
- target validation against allowed and forbidden paths before dispatch;
- provider/tool invocation still gated behind authority and receipts;
- no subprocess format/test execution through the kernel yet.

Acceptance requirements:

- read-only envelopes cannot execute `apply_patch`;
- code-write envelopes without explicit sandbox live-apply flags cannot mutate;
- patch targets outside `allowed_files` are denied;
- live apply records rollback backup paths and truthful mutation state;
- no provider, shell, network, browser, git, `pytest`, or `compileall` execution.

## Completed Slice: Control Plane Tick

Move from one-off kernel calls into a bounded supervisor tick:

- control-plane tick that leases wakes, runs, closebacks, and reports
  latest status without inventing a second queue;
- expired leased wakes are recovered before execution;
- tick output carries executions, closebacks, recovered wake ids, and latest wake
  state;
- no daemon process is installed or started by this tick.

## Completed Slice: Restart Snapshot

Move from manually invoked ticks into restart-aware operation:

- persisted control snapshot classifies recoverable expired leases after a fresh
  kernel instance is created with the same store path;
- restart fixture proves an expired leased wake can be recovered and completed
  by `run_control_tick` after re-instantiation;
- empty stores report integrity-ok snapshots.

## Completed Slice: Subagent Wake Lifecycle

Move from single-agent ticks into bounded in-kernel delegation:

- subagent child wakes are spawned onto the existing append-only wake ledger;
- child envelopes inherit parent authority and carry parent-run lineage;
- allowed agents, max children, max depth, and allowed-file scope are enforced
  before the child wake is queued;
- control ticks execute child wakes and record subagent delivery closeback
  receipts.

Acceptance requirements:

- denied child agents do not enqueue wake rows;
- file-scope escalation does not enqueue wake rows;
- max-child limits are enforced over existing child wakes;
- child delivery is not claimed until the wake ledger records a closeback;
- no live worker process, provider call, subprocess, network, browser, git,
  `pytest`, or `compileall` execution occurs inside the kernel.

## Completed Slice: Daemon Control Cycle

Move from manually invoked ticks into operator-controlled service cycles:

- pause/resume/stop controls are persisted as append-only receipts;
- paused and stopped cycles skip wake execution without losing queued work;
- resumed cycles call `run_control_tick` and record daemon heartbeat receipts;
- daemon control and cycle ledgers are hash-chained and tamper-tested;
- cycle receipts include `next_run_after` so an external scheduler can invoke
  the next bounded cycle without owning kernel state.

Acceptance requirements:

- paused cycles do not lease or execute queued wakes;
- stopped cycles remain stopped until a resume control receipt is appended;
- queued wakes survive pause/stop and execute after resume;
- daemon control and cycle ledger tampering is detected;
- no external process installation, provider call, subprocess, network, browser,
  git, `pytest`, or `compileall` execution occurs inside the kernel.

## Completed Slice: External Service Runner

Move from one-shot daemon cycles into an externally invokable runner:

- `run_kernel_daemon_service` runs bounded repeated daemon cycles;
- a non-blocking file lock prevents split-brain concurrent runners;
- durable stop controls end the service loop without losing queued wakes;
- the runtime CLI emits JSON so launch agents, tmux supervisors, or cron-style
  wrappers can inspect receipt refs;
- focused tests cover multi-cycle execution, stop behavior, lock exclusion, and
  CLI JSON smoke.

Acceptance requirements:

- service runner does not create a second queue;
- lock-held runners do not append daemon-cycle receipts;
- stop controls prevent further cycles while queued wakes remain intact;
- CLI execution writes daemon-cycle receipts;
- no provider call, subprocess tool runtime, network, browser, git, payment,
  deploy, publish, or external outreach is performed by the kernel service.

## Completed Slice: Supervisor Dry-Run Plans

Move from an invokable service runner toward reviewable installation:

- launchd plans render absolute ProgramArguments and default `RunAtLoad=false`;
- tmux plans render a reviewable shell script rather than starting a session;
- plans are written under the kernel store as dry-run artifacts;
- status is derived from daemon-cycle receipts and reports never-ran, recent, or
  stale;
- CLI plan/status commands emit JSON for operator review and automation.

Acceptance requirements:

- no launchctl, tmux, cron, or process start is performed by plan/status;
- launchd artifacts use absolute paths;
- dry-run plan artifacts carry stable receipt hashes;
- status does not claim running without daemon-cycle receipts;
- recent/stale status is derived from receipt timestamps.

## Completed Slice: External Worker Lifecycle

Move from dry-run supervision into external worker participation over the
existing wake ledger:

- workers register with role, allowed wake sources, max lease seconds, and
  hash-chained receipts;
- workers must heartbeat before leasing queued wakes;
- leasing honors source filters and writes worker lease receipts;
- terminal worker results append worker-result receipts and terminal wake rows
  that reference worker result hashes;
- stale/offline worker recovery requeues only expired leases owned by stale or
  offline registered workers;
- worker CLI commands emit JSON for register, heartbeat, status, lease,
  complete, recover, and verify operations.

Acceptance requirements:

- registered workers without fresh heartbeats cannot lease wakes;
- source filters do not lease ineligible queued wakes;
- external worker completion does not fabricate `KernelRunResult`;
- terminal wake rows reference immutable external-worker result receipts;
- stale recovery does not recover leases owned by fresh workers;
- worker ledgers and wake ledgers remain hash-chain verifiable;

## Completed Slice: Reviewed Activation + Worker Heartbeat Process

Move from dry-run plans and receipt-only workers into hash-gated activation:

- supervisor service activation records reviewed receipts only when the
  operator-provided hash matches the exact `KernelSupervisorPlan.receipt_hash`;
- worker process activation records reviewed receipts only when the
  operator-provided hash matches the exact command hash;
- activation receipts are append-only, hash-chained, and file-lock protected
  against concurrent append races;
- injected launchers allow tests to prove the launch path without installing
  launchd/tmux or starting the forever service;
- the bounded worker process CLI runs as a real subprocess in smoke tests,
  registers a worker, emits heartbeat receipts, and reports online worker state.

Acceptance requirements:

- mismatched supervisor plan hashes deny activation and do not call launchers;
- matching supervisor plan hashes record reviewed or activated receipts;
- mismatched worker command hashes deny activation and do not register workers;
- bounded worker process subprocesses write registration and heartbeat receipts;
- concurrent activation receipt appends preserve hash-chain integrity;
- no provider execution, launchctl, tmux, cron, network, browser, git, payment,
  deploy, publish, push/merge, or external outreach is performed.

## Completed Slice: Provider-Free Worker Wake Execution

Move from heartbeat-only workers into bounded useful wake execution:

- explicit `--execute` mode leases one eligible wake per worker cycle;
- the worker process runs the leased wake envelope through the existing
  `LivingAgentKernel.run` path instead of fabricating a result;
- terminal wake rows reference an external-worker result receipt whose payload
  references the actual kernel replay hash and proof entry hash;
- worker, wake, proof, event, and tool-result ledgers remain independently
  verifiable;
- the execution path remains provider-free and uses only the kernel's current
  tool dispatch boundaries.

Acceptance requirements:

- worker execution must require an explicit `--execute` flag;
- leased wakes must complete through `KernelExternalWorkerStore.complete_worker_wake`;
- terminal wake result refs must include worker result hash, kernel replay ref,
  and kernel proof entry hash;
- no second queue, provider call, network, browser, git, payment, deploy,
  publish, push/merge, or external outreach is performed.

## Completed Slice: Reviewed Launch Artifact Install

Move from reviewed plans into an operator-owned launch surface:

- launchd supervisor plans can be installed into an explicit install directory
  only when the provided hash matches `KernelSupervisorPlan.receipt_hash`;
- tmux supervisor scripts can be installed into an explicit install directory
  only when the provided hash matches `KernelSupervisorPlan.receipt_hash`;
- install receipts are written to `activation_receipts.jsonl` with
  `target_kind=launch_artifact`, `status=installed`, install path, content
  hash, mode, and `launch_started=false`;
- mismatched hashes deny installation and write no launch artifact;
- the install path does not call `launchctl`, start tmux, install cron, or
  start the forever service.

Acceptance requirements:

- reviewed launchd install writes exactly the reviewed plist content;
- reviewed tmux install writes an executable reviewed script;
- mismatched supervisor plan hashes deny install and leave no target artifact;
- activation ledgers remain hash-chain verifiable;
- no service start, launchctl, tmux session start, cron install, provider call,
  network, browser, git, payment, deploy, publish, push/merge, or external
  outreach is performed.

## Completed Slice: Launch Start Review + Status

Move from installed artifacts into receipt-backed start review and status:

- start review requires an installed `launch_artifact` activation receipt hash;
- launchd/tmux start commands are derived from the installed artifact only after
  content hash verification passes;
- dry-run start appends a `target_kind=launch_start`, `status=reviewed`
  receipt and does not call launchctl or tmux;
- explicit live start is available only through a launcher boundary and records
  `status=activated` or `status=failed` with process refs;
- status reports unknown, missing, changed, installed, or started from
  activation receipts and installed artifact content hashes.

Acceptance requirements:

- unknown install receipt hashes are denied without launcher calls;
- changed or missing installed artifacts fail preflight before start;
- reviewed start receipts must leave `launch_started=false`;
- activated start receipts must be tied to the install receipt hash;
- status cannot report `started` from a dry-run review alone;
- CLI dry-run start/status smoke must verify the activation ledger;
- no implicit launchctl, tmux session start, cron install, provider call,
  network, browser, git, payment, deploy, publish, push/merge, or external
  outreach is performed.

## Completed Slice: Crash Resume Snapshot + Bounded Recovery

Move from isolated ledgers into restart reconstruction:

- crash-resume snapshot reads wake, daemon-cycle, worker, activation,
  launch-artifact, and worker-result receipts into one operator packet;
- ledger integrity is checked before any recovery mutation;
- expired wake leases owned by stale/offline workers are recovered through the
  existing external-worker recovery path;
- expired wake leases owned by non-worker kernel owners can be requeued through
  the existing wake-ledger recovery path;
- fresh-worker leases are not recovered even when their lease timestamp has
  expired;
- CLI `snapshot` is read-only, and CLI `recover` is explicit.

Acceptance requirements:

- snapshot must report queued, leased, expired, terminal, worker, supervisor,
  launch, activation, and worker-result refs from persisted ledgers;
- recovery must block on ledger-integrity failure;
- recovery must not recover leases owned by fresh workers;
- recovery must append verifiable wake/worker recovery receipts when it requeues
  stale-worker leases;
- CLI smoke must prove snapshot -> recover -> wake/worker ledger verify;
- no provider call, launchctl, tmux session start, cron install, network,
  browser, git, payment, deploy, publish, push/merge, or external outreach is
  performed.

## Completed Slice: Promotion Gate + Provider Worker Boundary + OS Status

Move from provider-free worker execution into promoted provider-backed wake
completion:

- persistent agent identities require hash-chained promotion receipts before
  provider workers can lease wakes;
- provider-executor admission checks current promotion status, level, source,
  tool, work kind, expiry, lease cap, and evidence refs;
- missing, expired, revoked, source-mismatched, or under-evidenced promotions
  block provider work;
- promoted provider workers register, heartbeat, lease from the existing wake
  ledger, build an `LLMRequest` from the wake envelope, and call only an
  injected, fixture, or explicit live provider boundary;
- requested wake tools and tool calls are recorded in a context-only provider
  tool boundary; only `provider_complete` is delegated, and the provider cannot
  execute kernel tools;
- completed provider responses write `provider_worker_results.jsonl`, then
  complete the leased wake through the existing external-worker result path
  with `provider_execution=true`;
- OS status projects wake state, worker state, promotions, activation count,
  provider receipt count, and ledger integrity in one JSON packet.

Acceptance requirements:

- unpromoted provider workers leave queued wakes untouched;
- provider-executor receipts require explicit source/tool/work-kind authority
  and evidence refs;
- terminal wake rows reference both external-worker and provider-worker result
  hashes;
- provider-worker receipts expose requested wake tools as context only and deny
  delegated execution for non-provider tools;
- injected/fixture provider tests prove execution without network credentials;
- CLI smoke covers promotion, provider-worker execution, and OS status;
- no shared provider router mutation, unrestricted tool-calling provider agent,
  live launchctl/tmux activation, subprocess tool runtime, network, browser,
  git, payment, deploy, publish, push/merge, or external outreach is performed.

## Completed Slice: Provider Tool Delegation Boundary Hardening

Move from generic provider-worker request receipts into explicit tool-boundary
proof:

- `KernelProviderToolBoundary` is attached to provider-worker receipts and
  terminal wake result refs;
- provider request payloads expose requested wake tools and tool-call names as
  context only;
- `provider_may_execute_tools=false` is recorded in both request payloads and
  durable receipts;
- `provider_complete` is the only delegated provider-side completion tool;
- wake-requested tools such as `read_file` and `session_status` are recorded as
  denied for provider-side delegated execution unless a separate kernel receipt
  executes them.

Acceptance evidence:

- conflict-marker scan over provider module, runtime script, and focused tests
  returned no unresolved markers;
- compileall and ruff passed over the provider worker, runtime script, and
  promotion/provider test;
- focused promotion/provider tests passed: `7 passed in 2.42s`;
- provider-boundary CLI smoke completed `wake-provider-tool-boundary` under
  `/private/tmp/lak_provider_tool_boundary_5ygHsj`;
- receipt inspection proved `provider_may_execute_tools=false`, delegated tools
  `["provider_complete"]`, denied delegated tools `["read_file",
  "session_status"]`, and terminal wake status `completed`;
- broad LivingAgentKernel regression bundle passed: `188 passed in 12.47s`.

## Next Slice: Live Provider Smoke + Full Agent Tool Boundary

Move from reviewed heartbeat/process receipts into useful unattended work:

- live provider smoke under an explicit operator-approved provider and budget;
- full tool-call delegation gates for read/write/tool-call execution without
  bypassing kernel authority, receipts, or sandbox policy;
- optional live service supervision receipts may be added under explicit
  operator approval, but should not block provider/tool boundary work.

## Required Evals

- unit tests for schema invariants;
- golden replay fixtures;
- adversarial denial tests;
- proof-ledger tamper tests;
- crash/resume tests before any resume claim;
- closeback source-mutation tests before any source-closure claim;
- sandbox rollback tests before any write-tool execution claim;
- external task harness before any swarm-advantage claim.
