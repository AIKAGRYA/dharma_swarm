# LivingAgentKernel v1 Final Report

Mission: `living-agent-kernel-20260605`
Status: completed for durable runtime, append-only wake ledger, source-normalizer, source-closeback, operator-inspection, bounded-mutation, control-tick, restart-snapshot, subagent-wake lifecycle, daemon-control-cycle, external-service-runner, supervisor-dry-run-plan, external-worker-lifecycle, reviewed activation, provider-free worker wake execution, reviewed launch artifact install, launch start/status, crash-resume snapshot/bounded-recovery, promotion gate, provider-worker boundary, provider tool-delegation boundary, and OS status slices

## Built

Implemented the first durable executable kernel slice:

```text
AgentRunEnvelope
  -> evaluate_governed_work_admission
  -> ToolPlan
  -> KernelReadOnlyToolRegistry.dispatch(optional read-only tool calls)
  -> KernelRunStore.append_event / append_tool_result / append_proof_entry
  -> KernelRunResult
  -> KernelRunStore.replay_run(run_id)

AgentRunEnvelope
  -> KernelRunStore.enqueue_wake
  -> KernelRunStore.lease_next_wake
  -> LivingAgentKernel.run
  -> KernelRunStore.complete_wake
  -> KernelRunStore.verify_wake_ledger

manual/A2A/ds-goal/self-wake/external-fleet payload
  -> LivingAgentKernel.normalize_wake_source
  -> AgentRunEnvelope
  -> LivingAgentKernel.enqueue_source_wake

terminal KernelWakeRecord + KernelRunResult
  -> LivingAgentKernel.closeback_source_wake
  -> A2A receipt close | ds-goal kernel result ref | self-wake witness receipt | external-fleet refusal
  -> KernelRunStore.record_wake_closeback

wake_ledger.jsonl
  -> LivingAgentKernel.latest_wake_status

code-write AgentRunEnvelope + unified diff
  -> ToolPlan(apply_patch visible only under code-write authority)
  -> LivingAgentKernel._dispatch_apply_patch
  -> DiffApplier.apply(dry_run by default, live apply only with sandbox flags)
  -> KernelToolResult rollback refs + RuntimeTruthPacket mutation truth

control-plane tick
  -> LivingAgentKernel.recover_expired_wakes
  -> LivingAgentKernel.run_next_wake(max_wakes bounded)
  -> LivingAgentKernel.closeback_source_wake
  -> LivingAgentKernel.latest_wake_status

restart snapshot
  -> KernelRunStore.control_snapshot
  -> queued/leased/expired/terminal wake classification
  -> wake-ledger integrity state

parent AgentRunEnvelope
  -> LivingAgentKernel.spawn_subagent_wake
  -> inherited authority and subagent limits
  -> child AgentRunEnvelope(source=subagent)
  -> wake_ledger.jsonl
  -> run_control_tick
  -> subagent delivery closeback receipt

operator pause/resume/stop request
  -> LivingAgentKernel.request_daemon_control
  -> daemon_control.jsonl
  -> LivingAgentKernel.run_daemon_cycle
  -> skip while paused/stopped | run_control_tick while running
  -> daemon_cycles.jsonl heartbeat receipt

external service invocation
  -> run_kernel_daemon_service
  -> daemon_service.lock
  -> bounded repeated run_daemon_cycle calls
  -> scripts/runtime/living_agent_kernel_service.py --json

supervisor planning/status
  -> build_supervisor_plan
  -> default-off launchd/tmux dry-run artifacts
  -> supervisor_status
  -> recent/stale/never-ran state from daemon-cycle receipts
  -> scripts/runtime/living_agent_kernel_supervisor.py plan|status

external worker lifecycle
  -> KernelExternalWorkerStore.register_worker
  -> KernelExternalWorkerStore.heartbeat_worker
  -> KernelExternalWorkerStore.lease_worker_wake(existing wake_ledger.jsonl)
  -> KernelExternalWorkerStore.complete_worker_wake
  -> KernelRunStore.complete_external_wake
  -> KernelExternalWorkerStore.recover_stale_worker_leases
  -> scripts/runtime/living_agent_kernel_worker.py register|heartbeat|status|lease|complete|recover|verify

reviewed activation and launch surface
  -> KernelActivationStore.append_activation
  -> activate_supervisor_plan / activate_worker_process
  -> scripts/runtime/living_agent_kernel_worker_process.py --execute
  -> install_supervisor_plan
  -> start_installed_supervisor_artifact
  -> launch_artifact_status
  -> activation_receipts.jsonl hash-chain verification

crash-resume projection
  -> build_kernel_crash_resume_snapshot
  -> wake/daemon/worker/activation/launch/result ledger replay
  -> recover_kernel_after_crash
  -> stale-worker expired lease recovery
  -> scripts/runtime/living_agent_kernel_recovery.py snapshot|recover

promotion and provider-worker boundary
  -> KernelPromotionStore.append_promotion / revoke_promotion
  -> KernelPromotionStore.evaluate_worker_admission
  -> KernelExternalWorkerStore.register_worker / heartbeat / lease_worker_wake
  -> build_provider_request
  -> evaluate_provider_tool_boundary(context-only requested tool visibility)
  -> fixture, injected, or explicit live provider completion boundary
  -> KernelProviderWorkerStore.append_receipt
  -> KernelExternalWorkerStore.complete_worker_wake(provider_execution=true)
  -> scripts/runtime/living_agent_kernel_promotion.py
  -> scripts/runtime/living_agent_kernel_provider_worker.py
  -> scripts/runtime/living_agent_kernel_status.py
```

The kernel lives at `dharma_swarm/operator_core/living_agent_kernel.py`.
The external runner lives at
`dharma_swarm/operator_core/living_agent_kernel_service.py` and
`scripts/runtime/living_agent_kernel_service.py`.
The supervisor planner lives at
`dharma_swarm/operator_core/living_agent_kernel_supervisor.py` and
`scripts/runtime/living_agent_kernel_supervisor.py`.
The external worker lifecycle lives at
`dharma_swarm/operator_core/living_agent_kernel_workers.py` and
`scripts/runtime/living_agent_kernel_worker.py`.
The promotion/provider/status slice lives at
`dharma_swarm/operator_core/living_agent_kernel_promotion.py`,
`dharma_swarm/operator_core/living_agent_kernel_provider_worker.py`,
`dharma_swarm/operator_core/living_agent_kernel_status.py`, and their matching
runtime CLIs.

## What It Does

- normalizes task, trigger, authority, memory, tool, and proof inputs into one
  `AgentRunEnvelope`;
- reduces authority through existing `evaluate_governed_work_admission`;
- compiles a deterministic `ToolPlan` with visible tools, denied tools, denial
  reasons, read-only tool schemas, sandbox policy, inherited subagent limits,
  diagnostics, and stable policy hash;
- dispatches kernel-owned read-only tools: `session_status`, `memory_read`,
  `read_file`, and `search_files`;
- intercepts bounded `apply_patch` execution under code-write authority, explicit
  mission contract, workspace lease, allowed-file scope, sandbox policy, and
  rollback-backup checks;
- enforces explicit allowed-file authority at the `read_file` boundary;
- records canonical runtime events in `kernel_events.jsonl`;
- records tool lifecycle receipts in `tool_results.jsonl`;
- records hash-chained proof rows in `proof_ledger.jsonl`;
- records append-only wake state in `wake_ledger.jsonl`;
- leases queued wakes, executes them through `LivingAgentKernel.run`, and
  records terminal wake state;
- requeues expired leased wakes by appending recovery rows;
- maps manual operator, A2A queue, ds-goal task, persistent self-wake, and
  external fleet payloads into one `AgentRunEnvelope` shape;
- preserves source identity fields: mission id, task id, correlation id,
  return address, lease metadata, and source payload hash;
- closes A2A source queue rows with validated kernel proof receipts;
- records kernel result refs onto ds-goal task rows without falsely closing them;
- appends persistent self-wake witness receipts with replay/proof refs;
- refuses external-fleet source mutation while still recording the refusal in the
  wake ledger;
- projects compact latest-wake status for operator inspection;
- runs a bounded control-plane tick that recovers expired leases, executes queued
  wakes, performs source closeback, and returns latest wake status;
- replays persisted wake state through `control_snapshot`, including restart
  recovery visibility for expired leases and terminal wake state;
- spawns bounded subagent child wakes over the same append-only wake ledger with
  inherited authority, parent-run lineage, allowed-agent/max-depth/max-child
  limits, and non-elevating file scope;
- records subagent delivery closeback receipts after child wake execution;
- records operator pause/resume/stop controls in `daemon_control.jsonl`;
- runs a bounded daemon-control cycle that checks active controls, skips work
  while paused or stopped, delegates to `run_control_tick` while running, and
  records heartbeat receipts in `daemon_cycles.jsonl`;
- verifies daemon control and cycle ledger hash chains, including tamper
  detection;
- runs bounded repeated daemon cycles under a non-blocking file lock through
  `run_kernel_daemon_service`;
- exposes a runtime CLI that can print structured JSON service-run receipts;
- stops repeated service cycles on durable stop controls without losing queued
  wakes;
- renders default-off launchd/tmux supervisor plans for operator review without
  invoking launchctl, tmux, cron, or process start;
- writes reviewable supervisor artifacts under the kernel store with stable
  receipt hashes;
- derives supervisor freshness from daemon-cycle receipts;
- registers external workers with allowed-source filters and max lease seconds;
- records external worker heartbeats and classifies workers as registered,
  online, stale, or offline;
- denies wake leases to unregistered workers and registered workers without
  fresh heartbeats;
- leases eligible queued wakes to fresh workers through the existing wake
  ledger, without creating another queue;
- records external worker result receipts and marks leased wakes terminal with
  `external_worker_result` refs;
- requeues expired wake leases owned by stale/offline external workers while
  leaving fresh-worker leases alone;
- verifies hash chains across worker registry, heartbeat, lease, result, and
  recovery ledgers;
- exposes a worker lifecycle CLI with JSON register, heartbeat, status, lease,
  complete, recover, and verify commands;
- records reviewed activation receipts for supervisor service commands, worker
  process commands, installed launch artifacts, and launch-start actions;
- executes provider-free worker wakes only under explicit worker-process
  `--execute`, using the existing `LivingAgentKernel.run` path;
- installs exact hash-approved launchd/tmux artifacts into explicit
  operator-owned directories without starting them;
- verifies installed launch artifact content hashes before reviewing or
  activating a start command;
- records dry-run launch start reviews as `target_kind=launch_start`,
  `status=reviewed`, with `launch_started=false`;
- projects launch artifact status as unknown, missing, changed, installed, or
  started from activation receipts and artifact content hashes;
- reconstructs cross-ledger crash-resume state from wake, daemon, worker,
  activation, launch, and worker-result receipts;
- verifies wake, daemon-control, daemon-cycle, worker, activation, and optional
  proof ledgers before recovery;
- blocks crash recovery when ledger integrity fails;
- explicitly recovers already-expired stale/offline worker leases without
  stealing fresh-worker leases;
- records hash-chained promotion, denial, and revocation receipts for
  persistent agent identities;
- blocks provider-worker admission when promotion is missing, expired, revoked,
  source-mismatched, missing provider evidence, or missing promoted tool/work
  kind authority;
- clamps provider-worker lease authority through promotion receipts;
- builds provider requests from leased wake envelopes without mutating the
  shared provider/router policy;
- records provider tool boundaries where requested wake tools/tool calls are
  context only, `provider_complete` is the sole delegated provider tool, and
  `provider_may_execute_tools=false`;
- runs provider-worker completion through fixture responses, injected provider
  clients, or an explicit live-provider boundary;
- records provider-worker result receipts with request/response hashes,
  response content, promotion refs, and lease refs;
- completes promoted provider-worker wakes through the existing external-worker
  terminal result path with `provider_execution=true`;
- leaves queued wakes untouched when provider-worker promotion is absent;
- projects a combined OS status packet over wake snapshot, worker states, latest
  promotions, activation count, provider-worker receipt count, and per-ledger
  integrity;
- keeps external fleet workers evidence-only and denies action tools;
- replays a run by `run_id` with event/proof/tool-result integrity checks;
- verifies wake-ledger hash-chain integrity;
- emits a `RuntimeTruthPacket` projection;
- performs no shell execution, network calls, browser calls, `pytest`, or
  `compileall` execution inside the kernel in v1. Provider execution is limited
  to the promoted provider-worker boundary and does not grant unrestricted tool
  execution.

## Files Changed

- `dharma_swarm/operator_core/governed_work_admission.py`
- `dharma_swarm/operator_core/runtime_truth.py`
- `dharma_swarm/operator_core/living_agent_kernel.py`
- `dharma_swarm/operator_core/living_agent_kernel_service.py`
- `dharma_swarm/operator_core/living_agent_kernel_supervisor.py`
- `dharma_swarm/operator_core/living_agent_kernel_workers.py`
- `dharma_swarm/operator_core/living_agent_kernel_activation.py`
- `dharma_swarm/operator_core/living_agent_kernel_recovery.py`
- `dharma_swarm/operator_core/living_agent_kernel_promotion.py`
- `dharma_swarm/operator_core/living_agent_kernel_provider_worker.py`
- `dharma_swarm/operator_core/living_agent_kernel_status.py`
- `scripts/runtime/living_agent_kernel_activation.py`
- `scripts/runtime/living_agent_kernel_promotion.py`
- `scripts/runtime/living_agent_kernel_provider_worker.py`
- `scripts/runtime/living_agent_kernel_recovery.py`
- `scripts/runtime/living_agent_kernel_service.py`
- `scripts/runtime/living_agent_kernel_status.py`
- `scripts/runtime/living_agent_kernel_supervisor.py`
- `scripts/runtime/living_agent_kernel_worker.py`
- `scripts/runtime/living_agent_kernel_worker_process.py`
- `tests/test_governed_work_admission.py`
- `tests/test_living_agent_kernel.py`
- `tests/test_living_agent_kernel_activation.py`
- `tests/test_living_agent_kernel_promotion_provider.py`
- `tests/test_living_agent_kernel_recovery.py`
- `tests/test_living_agent_kernel_service.py`
- `tests/test_living_agent_kernel_supervisor.py`
- `tests/test_living_agent_kernel_workers.py`
- `spec-forge/living-agent-kernel/MASTER_SPEC.md`
- `reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md`
- `reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md`
- `reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md`
- `reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md`

## Verification

- `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_governed_work_admission.py -q --tb=short`
  - pass: `25 passed in 0.49s`
- `pytest -q tests/test_living_agent_kernel.py --tb=short`
  - latest continuation pass: `39 passed, 1 warning in 0.68s`
- `pytest -q tests/test_living_agent_kernel.py --tb=short`
  - latest subagent continuation pass: `42 passed, 1 warning in 0.70s`
- `pytest -q tests/test_living_agent_kernel.py --tb=short`
  - latest daemon-control continuation pass: `46 passed, 1 warning in 0.69s`
- `pytest -q tests/test_living_agent_kernel_service.py --tb=short`
  - service-runner continuation pass: `4 passed, 1 warning in 0.89s`
- `pytest -q tests/test_living_agent_kernel_supervisor.py --tb=short`
  - supervisor-plan continuation pass: `5 passed, 1 warning in 1.89s`
- `pytest -q tests/test_living_agent_kernel_workers.py --tb=short`
  - external-worker-lifecycle continuation pass: `6 passed, 1 warning in 1.96s`
- `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`
  - launch start/status continuation pass: `17 passed, 1 warning in 3.19s`
- `pytest -q tests/test_living_agent_kernel_recovery.py --tb=short`
  - crash-resume continuation pass: `4 passed, 1 warning in 0.86s`
- `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py -q --tb=short`
  - pass: `104 passed in 1.07s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short`
  - latest continuation pass: `115 passed, 1 warning in 0.75s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - latest continuation pass: `138 passed, 1 warning in 1.33s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - latest subagent continuation pass: `141 passed, 1 warning in 1.40s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - latest daemon-control continuation pass: `145 passed, 1 warning in 1.40s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - service-runner continuation pass: `149 passed, 1 warning in 1.93s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - supervisor-plan continuation pass: `154 passed, 1 warning in 3.17s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - external-worker-lifecycle continuation pass: `160 passed, 1 warning in 4.35s`
- `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - launch start/status continuation pass: `177 passed, 1 warning in 6.16s`
- `./.venv/bin/python -m pytest tests/test_living_agent_kernel_promotion_provider.py -q --tb=short`
  - promotion/provider/status focused pass: `7 passed in 2.42s`
- `rg -n "<<<<<<<|=======|>>>>>>>" dharma_swarm/operator_core/living_agent_kernel_provider_worker.py tests/test_living_agent_kernel_promotion_provider.py scripts/runtime/living_agent_kernel_provider_worker.py`
  - provider tool-boundary continuation pass: no unresolved conflict markers
- `./.venv/bin/python -m compileall -q dharma_swarm/operator_core/living_agent_kernel_provider_worker.py tests/test_living_agent_kernel_promotion_provider.py scripts/runtime/living_agent_kernel_provider_worker.py`
  - provider tool-boundary continuation compile pass
- `./.venv/bin/python -m ruff check dharma_swarm/operator_core/living_agent_kernel_provider_worker.py tests/test_living_agent_kernel_promotion_provider.py`
  - provider tool-boundary continuation static pass: `All checks passed!`
- `./.venv/bin/python -m pytest tests/test_living_agent_kernel_promotion_provider.py -q --tb=short`
  - provider tool-boundary continuation focused pass: `7 passed in 2.42s`
- `./.venv/bin/python scripts/runtime/living_agent_kernel_provider_worker.py --store-dir /private/tmp/lak_provider_tool_boundary_5ygHsj --workspace-root /Users/dhyana/dharma_swarm --worker-id cli-provider-boundary --agent-uid promoted_agent --provider openrouter_free --model fixture-model --allowed-source manual --fixture-response 'Provider boundary fixture completed.' --now 2026-06-06T00:00:01Z`
  - provider tool-boundary CLI smoke pass: completed `wake-provider-tool-boundary`
    and wrote a provider-worker receipt under
    `/private/tmp/lak_provider_tool_boundary_5ygHsj/provider_worker_results.jsonl`
- provider tool-boundary receipt inspection
  - pass: `provider_may_execute_tools=false`, delegated tools
    `["provider_complete"]`, denied delegated tools `["read_file",
    "session_status"]`, and terminal wake status `completed`
- `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_promotion_provider.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py -q --tb=short`
  - promotion/provider/status broad bundle pass: `184 passed in 9.84s`
- `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_recovery.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_living_agent_kernel_promotion_provider.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py -q --tb=short`
  - provider tool-boundary broad bundle pass: `188 passed in 12.47s`
- `./.venv/bin/python scripts/runtime/context_quorum.py check ... --task-id living-agent-kernel-provider-tool-boundary-v1`
  - provider tool-boundary Q3 pass: `allowed_next_action=bounded_action_allowed`,
    `missing_families=[]`; `tests/test_living_agent_kernel_promotion_provider.py`
    flagged as measurement-protected and covered by focused/broad verifier
- `./.venv/bin/python -m ruff check dharma_swarm/operator_core/living_agent_kernel_promotion.py dharma_swarm/operator_core/living_agent_kernel_provider_worker.py dharma_swarm/operator_core/living_agent_kernel_status.py scripts/runtime/living_agent_kernel_promotion.py scripts/runtime/living_agent_kernel_provider_worker.py scripts/runtime/living_agent_kernel_status.py tests/test_living_agent_kernel_promotion_provider.py`
  - promotion/provider/status static pass: `All checks passed!`
- `./.venv/bin/python -m compileall dharma_swarm/operator_core/living_agent_kernel_promotion.py dharma_swarm/operator_core/living_agent_kernel_provider_worker.py dharma_swarm/operator_core/living_agent_kernel_status.py scripts/runtime/living_agent_kernel_promotion.py scripts/runtime/living_agent_kernel_provider_worker.py scripts/runtime/living_agent_kernel_status.py tests/test_living_agent_kernel_promotion_provider.py`
  - promotion/provider/status compile pass
- `./.venv/bin/python scripts/runtime/context_quorum.py check ... --task-id living-agent-kernel-promotion-provider-worker-v1`
  - Q3 context quorum pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`
- `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_recovery.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
  - crash-resume continuation pass: `181 passed, 1 warning in 7.59s`
- `python3 scripts/runtime/living_agent_kernel_service.py --store-dir /private/tmp/lak_service_probe --workspace-root /Users/dhyana/dharma_swarm --cycles 1 --interval-seconds 1 --json`
  - service-runner smoke pass: one completed service run, one idle daemon
    cycle, and daemon cycle receipt at
    `/private/tmp/lak_service_probe/daemon_cycles.jsonl`
- `python3 scripts/runtime/living_agent_kernel_supervisor.py plan --mode launchd --repo-root /Users/dhyana/dharma_swarm --store-dir /private/tmp/lak_supervisor_probe --workspace-root /Users/dhyana/dharma_swarm --label com.dharma.lak.probe --write`
  - supervisor-plan smoke pass: dry-run plan and launchd plist written under
    `/private/tmp/lak_supervisor_probe/supervisor/`
- `python3 scripts/runtime/living_agent_kernel_supervisor.py status --store-dir /private/tmp/lak_supervisor_probe --daemon-id living-agent-kernel --now 2026-06-05T00:00:00Z`
  - supervisor-status smoke pass: `never_ran` from absence of daemon-cycle
    receipts
- `python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe register --worker-id probe-worker --role verifier --allowed-source manual --now 2026-06-05T00:00:00Z`
  - worker-register smoke pass: wrote `worker_registry.jsonl` row with
    `record_hash=sha256:f435bd48332953418530de16f752b77b440884cf7cd965ece573ca27a06d65fc`
- `python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe heartbeat --worker-id probe-worker --now 2026-06-05T00:00:01Z`
  - worker-heartbeat smoke pass: wrote `worker_heartbeats.jsonl` row with
    `record_hash=sha256:d55e4b17bf5ca02496bb9ec3671147da4993a635a0db874f2457bb0305e001b3`
- `python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe status --now 2026-06-05T00:00:02Z`
  - worker-status smoke pass: `online`, `heartbeat_age_seconds=1.0`
- `python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe verify`
  - worker-ledger smoke pass: `{"errors": [], "ok": true}`
- `python3 scripts/runtime/living_agent_kernel_activation.py supervisor-start --store-dir /private/tmp/lak_launch_start_probe_8aVkbb --install-receipt-hash sha256:42489d67e5538d851834867f3dafbc31345b74d568f2d0f6438df3e00e8e3c04 --launchd-domain gui/501 --now 2026-06-06T00:00:01Z`
  - launch start review smoke pass: wrote `target_kind=launch_start`,
    `status=reviewed`, command
    `launchctl bootstrap gui/501 /private/tmp/lak_launch_start_probe_8aVkbb/LaunchAgents/com.dharma.lak.start-probe.plist`,
    and `launch_started=false`
- `python3 scripts/runtime/living_agent_kernel_activation.py supervisor-launch-status --store-dir /private/tmp/lak_launch_start_probe_8aVkbb --install-receipt-hash sha256:42489d67e5538d851834867f3dafbc31345b74d568f2d0f6438df3e00e8e3c04 --now 2026-06-06T00:00:02Z`
  - launch status smoke pass: `status=installed` because the start receipt was
    reviewed only, not activated
- `python3 -c 'from dharma_swarm.operator_core.living_agent_kernel_activation import KernelActivationStore; import json; ok, errors = KernelActivationStore("/private/tmp/lak_launch_start_probe_8aVkbb").verify_activation_ledger(); print(json.dumps({"ok": ok, "errors": errors}, sort_keys=True))'`
  - activation ledger smoke pass: `{"errors": [], "ok": true}`
- `python3 scripts/runtime/living_agent_kernel_recovery.py snapshot --store-dir /private/tmp/lak_crash_resume_probe_h91JNm --now 2026-06-06T00:00:03Z --stale-after-seconds 1`
  - crash-resume snapshot smoke pass: `status=needs_recovery`,
    `expired_worker_lease_wake_ids=["wake-crash-probe"]`, ledger integrity OK
- `python3 scripts/runtime/living_agent_kernel_recovery.py recover --store-dir /private/tmp/lak_crash_resume_probe_h91JNm --now 2026-06-06T00:00:03Z --stale-after-seconds 1`
  - crash recovery smoke pass: `status=completed`,
    worker recovery receipt recovered `wake-crash-probe`, after snapshot
    requeued it
- `python3 -c 'from dharma_swarm.operator_core.living_agent_kernel import KernelRunStore; from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore; import json; store=KernelRunStore("/private/tmp/lak_crash_resume_probe_h91JNm"); workers=KernelExternalWorkerStore("/private/tmp/lak_crash_resume_probe_h91JNm"); wake_ok,wake_errors=store.verify_wake_ledger(); worker_ok,worker_errors=workers.verify_worker_ledgers(); latest=store.latest_wake_records()["wake-crash-probe"]; print(json.dumps({"wake_ok":wake_ok,"wake_errors":wake_errors,"worker_ok":worker_ok,"worker_errors":worker_errors,"wake_status":latest.status,"lease_owner":latest.lease_owner}, sort_keys=True))'`
  - crash recovery ledger smoke pass:
    `{"lease_owner": "", "wake_errors": [], "wake_ok": true, "wake_status": "queued", "worker_errors": [], "worker_ok": true}`
- `python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py tests/test_living_agent_kernel.py`
  - pass
- `./.venv/bin/python -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/governed_work_admission.py dharma_swarm/operator_core/runtime_truth.py tests/test_living_agent_kernel.py tests/test_governed_work_admission.py`
  - pass
- Context+ static analysis on `dharma_swarm/operator_core/living_agent_kernel.py`
  - pass: no issues found
- Latest Context+ static analysis attempt after subagent continuation
  - not counted as evidence: timed out after 600 seconds
- Latest Context+ static analysis attempt after service-runner continuation
  - not counted as evidence: timed out after 600 seconds
- Latest Context+ static analysis attempt after external-worker continuation
  - not counted as evidence: timed out after 600 seconds
- Q3 context quorum
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`
- Q3 context quorum continuation for wake ledger
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for source normalizers
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for source closeback
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for bounded mutation
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for control tick
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for restart snapshot
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for subagent wake lifecycle
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for daemon-control cycle
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel.py` remains a measurement-protected surface
    and was changed only with focused verifier coverage
- Q3 context quorum continuation for service runner
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_service.py` is a measurement-protected
    surface and was added with focused verifier coverage
- Q3 context quorum continuation for supervisor dry-run plans
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_supervisor.py` is a measurement-protected
    surface and was added with focused verifier coverage
- Q3 context quorum continuation for external-worker lifecycle
  - pass: `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_workers.py` is a measurement-protected
    surface and was added with focused verifier coverage
- Q3 context quorum continuation for launch start/status
  - pass: `task_id=living-agent-kernel-launch-start-status-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_activation.py` is a measurement-protected
    surface and was covered by focused/broad verifier runs
- Q3 context quorum continuation for crash-resume
  - pass: `task_id=living-agent-kernel-crash-resume-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_recovery.py` is a measurement-protected
    surface and was covered by focused/broad verifier runs
- 2026-06-06 reorientation after terminal timeout
  - located interrupted point: latest pasted run was waiting in Context+
    `run_static_analysis` after the service-runner smoke; current report/spec
    already contained later supervisor dry-run and external-worker lifecycle
    receipts
  - active process check: no `run_static_analysis` or
    `living_agent_kernel_service` command was still running; only Context+
    node servers were present
  - deterministic static replacement:
    `./.venv/bin/ruff check dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_service.py dharma_swarm/operator_core/living_agent_kernel_supervisor.py dharma_swarm/operator_core/living_agent_kernel_workers.py scripts/runtime/living_agent_kernel_service.py scripts/runtime/living_agent_kernel_supervisor.py scripts/runtime/living_agent_kernel_worker.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py`
    -> `All checks passed!`
  - lint-only cleanup applied: two `is not False` boolean identity fixes and
    intentional `E402` suppressions for runtime scripts that prepend the repo
    root before local imports
  - compile pass:
    `python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_service.py dharma_swarm/operator_core/living_agent_kernel_supervisor.py dharma_swarm/operator_core/living_agent_kernel_workers.py scripts/runtime/living_agent_kernel_service.py scripts/runtime/living_agent_kernel_supervisor.py scripts/runtime/living_agent_kernel_worker.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py`
  - focused frontier tests:
    `pytest -q tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py --tb=short`
    -> `15 passed, 1 warning in 2.69s`
  - broad bundle:
    `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
    -> `160 passed, 1 warning in 4.34s`
  - fresh CLI smokes:
    service runner wrote a daemon-cycle receipt under
    `/private/tmp/lak_service_reorient_zuRTYj`; supervisor dry-run plan/status
    wrote artifacts under `/private/tmp/lak_supervisor_reorient_mWx4Tw` and
    returned `never_ran`; worker register/heartbeat/status/verify succeeded
    under `/private/tmp/lak_worker_reorient_DOVY7D`
  - Q3 context quorum:
    `task_id=living-agent-kernel-reorient-static-clean-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`
- Reviewed activation + bounded worker heartbeat process continuation
  - implemented `dharma_swarm/operator_core/living_agent_kernel_activation.py`
    with `KernelActivationStore`, hash-gated supervisor activation,
    hash-gated worker process activation, command hashes, injected launchers,
    and hash-chain verification for `activation_receipts.jsonl`
  - implemented `scripts/runtime/living_agent_kernel_worker_process.py` as a
    bounded real worker heartbeat process that registers an external worker and
    emits heartbeat receipts without provider-backed wake work
  - implemented `scripts/runtime/living_agent_kernel_activation.py` for
    `worker-plan`, `worker-launch`, and `supervisor-activate` JSON commands
  - found and fixed a real activation-ledger race: parallel CLI receipt writes
    could corrupt `previous_record_hash`; `_append_hashed` now takes a file
    lock and `test_activation_ledger_survives_concurrent_review_receipts`
    covers the regression
  - focused activation tests:
    `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`
    -> `7 passed, 1 warning in 1.77s`
  - broad bundle with activation:
    `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
    -> `167 passed, 1 warning in 7.43s`
  - static/compile checks:
    `./.venv/bin/ruff check ...` -> `All checks passed!`;
    `python3 -m compileall -q ...` passed for LivingAgentKernel
    modules/scripts/tests including activation
  - fresh CLI smoke:
    worker process wrote registration and heartbeat receipts under
    `/private/tmp/lak_activation_probe2_id7PwT`; activation CLI recorded
    reviewed worker command and supervisor plan receipts; worker status returned
    `online`; activation ledger verify returned `{"errors": [], "ok": true}`
  - Q3 context quorum:
    `task_id=living-agent-kernel-reviewed-activation-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_activation.py` flagged as
    measurement-protected and covered by focused/broad verifier
- Provider-free worker wake execution continuation
  - updated `scripts/runtime/living_agent_kernel_worker_process.py` with an
    explicit `--execute` mode that heartbeats, leases an eligible wake, runs the
    original `AgentRunEnvelope` through `LivingAgentKernel.run`, and completes
    the existing leased wake through `KernelExternalWorkerStore`
  - updated activation command planning so reviewed worker command hashes cover
    `--workspace-root` and `--execute`
  - focused activation tests:
    `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`
    -> `8 passed, 1 warning in 2.07s`
  - broad bundle:
    `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
    -> `168 passed, 1 warning in 5.17s`
  - fresh CLI smoke:
    `/private/tmp/lak_worker_execute_probe_IOZ3m2` was seeded with
    `wake-cli-execute`; worker process `--execute --json` leased and completed
    it; terminal wake row points to `external_worker_result`, kernel replay hash
    `sha256:1ea2a1e8977075669c54849801b75ed32bdad8955017d48ea6c1e0b1d94d7711`,
    proof entry hash
    `sha256:b7000345aee0a2383229a31a393732e05a9205de090a1c13acfbb354c032712b`,
    and `provider_execution=false`; worker and wake ledgers verified clean
  - Q3 context quorum:
    `task_id=living-agent-kernel-worker-wake-execution-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_activation.py` flagged as
    measurement-protected and covered by focused/broad verifier
- Reviewed launch artifact install continuation
  - added `install_supervisor_plan(...)` and `supervisor-install` to install
    exact hash-approved launchd/tmux artifacts into an explicit operator-owned
    install directory without starting the service
  - focused activation tests:
    `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`
    -> `12 passed, 1 warning in 2.61s`
  - broad bundle:
    `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`
    -> `172 passed, 1 warning in 6.02s`
  - fresh CLI smoke:
    `supervisor-install` wrote
    `/private/tmp/lak_launch_install_probe_KKH59U/LaunchAgents/com.dharma.lak.install-probe.plist`;
    the file exists, preserves `RunAtLoad=false`, contains no `launchctl`,
    records `launch_started=false`, and activation ledger verify returned
    `{"errors": [], "ok": true}`
  - Q3 context quorum:
    `task_id=living-agent-kernel-launch-install-v1`,
    `allowed_next_action=bounded_action_allowed`, `missing_families=[]`;
    `tests/test_living_agent_kernel_activation.py` flagged as
    measurement-protected and covered by focused/broad verifier

## Unsupported Claims

- This does not execute unrestricted provider tools. Provider execution is
  limited to the promoted provider-worker wake-completion boundary with
  promotion, lease, request/response, and terminal wake receipts.
  Requested wake tools are visible to providers as context only and are denied
  for provider-side delegated execution unless a separate kernel receipt
  executes them.
- This does not execute subprocesses, network calls, browser calls, payment,
  deploy, publish, push/merge, or external outreach.
- This does not provide general write-tool execution. The only write-capable
  adapter is bounded `apply_patch` over unified diffs with allowed-file,
  sandbox-policy, and rollback-backup checks.
- This does not mutate persistent memory.
- External workers can now register, heartbeat, lease eligible wakes, record
  terminal worker-result receipts, recover stale leases, execute eligible wakes
  through the provider-free `LivingAgentKernel.run` path, and complete promoted
  provider-worker wakes through the new provider boundary. They still do not get
  broad action-tool authority.
- This does not implicitly install or start a launchd/systemd/tmux-managed
  persistent service. The service runner is an invokable CLI/function with a
  split-brain lock and durable daemon-cycle receipts.
- Supervisor activation, artifact installation, and launch-start review are
  hash-gated and receipt-backed. The smoke path did not call launchctl, start
  tmux, install cron, or activate the forever service; live start is available
  only through an explicit launcher boundary and is covered by injected tests.
- This does not provide a full tool-using provider subagent, real
  launchctl/tmux supervision smoke, provider-backed crash replay, live provider
  smoke with credentials, or full persistent-agent integration.
- Crash-resume support is limited to receipt-backed snapshot projection and
  explicit expired-lease recovery. It does not restart providers, rehydrate model
  sessions, or prove benchmarked unattended autonomy.
- Source closeback exists only for A2A queue close receipts, ds-goal kernel
  result refs, persistent self-wake witness receipts, subagent delivery
  receipts, and external-fleet refusal; it is not a general source mutation
  engine.

## Next Slice

Add live provider smoke and full tool-call boundaries: operator-approved live
provider execution, explicit tool/provider deny/allow receipts, write-tool
delegation gates, and real service supervision evidence under operator approval.
