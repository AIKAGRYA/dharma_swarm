# LivingAgentKernel v1 Verifier Matrix

Mission: `living-agent-kernel-20260605`
Slice: durable runtime plus append-only wake ledger plus source normalizers, source closeback, bounded mutation, control tick, restart snapshot, subagent-wake lifecycle, daemon-control cycle, external-service runner, supervisor dry-run plans, external-worker lifecycle, reviewed activation, provider-free worker wake execution, reviewed launch artifact install, launch start/status, crash-resume snapshot/bounded recovery, promotion gate, provider-worker boundary, provider tool-delegation boundary, and OS status
Status: pass

## Scope

The implementation persists canonical events/proofs and dispatches
kernel-owned read-only tools plus one bounded `apply_patch` unified-diff
adapter. It also persists an append-only wake ledger for bounded queue, lease,
execution, terminal state, and expired-lease recovery tests. It does not call
unrestricted providers, execute subprocess tools, start daemons, mutate live
memory, or contact external systems.
It also exposes one bounded control-plane tick that recovers expired wake leases,
executes queued wakes, performs source closeback, and returns latest operator
status without starting a daemon process.
Restart snapshots replay persisted wake state and classify queued, leased,
expired, and terminal wakes for a fresh kernel instance.
Subagent dispatch is implemented as bounded child wakes over the same ledger,
with inherited authority, parent-run lineage, max-child/max-depth/allowed-agent
limits, non-elevating file scope, control-tick execution, and delivery
closeback receipts. It does not spawn live worker processes or call providers.
Daemon control is implemented as a callable service-cycle wrapper, not an
installed process: pause/resume/stop controls are persisted, paused/stopped
cycles skip wake execution, running cycles delegate to `run_control_tick`, and
heartbeat receipts are recorded in a daemon cycle ledger.
The external service runner repeatedly invokes daemon cycles under a
non-blocking file lock and has a CLI smoke test. It still does not install a
launchd/systemd/tmux persistent service or call live providers.
Supervisor planning renders default-off launchd/tmux artifacts and derives
recent/stale/never-ran status from daemon-cycle receipts. It does not invoke
launchctl, tmux, cron, or start a process.
External worker lifecycle records worker registration, heartbeat, source-filtered
leasing, terminal worker result receipts, and stale/offline worker lease
recovery over the same kernel store. It does not spawn workers, call providers,
or create a second queue.
Reviewed activation records hash-gated supervisor service and worker process
activation receipts. The bounded worker heartbeat process can run as a real
subprocess and write registration/heartbeat receipts, but it still does not
perform provider-backed wake work or install launchd/tmux services.
Provider-free worker wake execution now leases eligible wakes under explicit
`--execute`, runs the original envelope through `LivingAgentKernel.run`, and
completes the leased wake with an external-worker result pointing to real
kernel replay/proof hashes.
Reviewed launch artifact install writes the exact hash-approved launchd plist or
tmux script into an explicit operator-owned install directory and records
`launch_started=false`; it does not call launchctl, start tmux, install cron, or
start the forever service.
Launch start/status is receipt-backed over installed artifact receipts: start
review verifies the install receipt and installed content hash, records a
`launch_start` review receipt without launching by default, live start is
available only through an explicit launcher boundary, and status reports
unknown/missing/changed/installed/started from receipts plus artifact content.
Crash-resume snapshot reconstructs restart state from persisted wake, daemon,
worker, activation, launch, and worker-result receipts. Recovery is explicit,
blocks on ledger-integrity failure, and requeues only already-expired stale or
offline worker leases plus non-worker kernel leases; it does not call providers
or start services.
Promotion/provider status adds hash-chained promotion receipts, provider-worker
admission checks, provider-worker result receipts, and a combined OS status
packet. It can complete leased wakes through a fixture, injected, or explicit
live provider boundary only after provider-executor promotion; it does not grant
general provider tool authority or mutate the shared provider/router policy.
Requested wake tools are visible to the provider as context only through
`KernelProviderToolBoundary`; `provider_may_execute_tools` remains false.
It normalizes manual, A2A, ds-goal, persistent-self-wake, and external-fleet
payloads into `AgentRunEnvelope`. It can close back to owned source surfaces
only after persisted kernel proof exists: A2A queue close receipts, ds-goal
kernel result refs, persistent self-wake witness receipts, external-fleet
mutation refusal, and latest-wake operator inspection.

## Checks

| Check | Result | Evidence |
|---|---:|---|
| Focused kernel tests | pass | latest daemon-control continuation: `46 passed, 1 warning in 0.69s` |
| Focused service tests | pass | service-runner continuation: `4 passed, 1 warning in 0.89s` |
| Focused supervisor tests | pass | supervisor-plan continuation: `5 passed, 1 warning in 1.89s` |
| Focused worker tests | pass | external-worker-lifecycle continuation: `6 passed, 1 warning in 1.96s` |
| Combined governed/admission/A2A/memory/profile tests | pass | latest continuation: `115 passed, 1 warning in 0.75s` |
| Combined plus DiffApplier/service/supervisor/worker tests | pass | external-worker-lifecycle continuation: `160 passed, 1 warning in 4.35s` |
| Compile check | pass | `python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_service.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py scripts/runtime/living_agent_kernel_service.py` |
| CLI smoke | pass | `python3 scripts/runtime/living_agent_kernel_service.py --store-dir /private/tmp/lak_service_probe --workspace-root /Users/dhyana/dharma_swarm --cycles 1 --interval-seconds 1 --json` wrote a daemon cycle receipt |
| Supervisor CLI smoke | pass | `python3 scripts/runtime/living_agent_kernel_supervisor.py plan ... --write` wrote a dry-run launchd plan; `status` returned `never_ran` |
| Worker CLI smoke | pass | register and heartbeat wrote hash-chained rows under `/private/tmp/lak_worker_probe`; status returned `online`; verify returned `{"errors": [], "ok": true}` |
| Static analysis | partial | Earlier Context+ `run_static_analysis`: no issues found; latest worker continuation attempt timed out after 600 seconds and is not counted |
| Q3 context quorum | pass | external-worker-lifecycle continuation: `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; worker test file flagged as measurement-protected and covered by focused verifier |
| 2026-06-06 reorientation static check | pass | `./.venv/bin/ruff check ...` over LivingAgentKernel kernel/service/supervisor/worker modules, scripts, and tests: `All checks passed!` after two boolean identity cleanups and intentional script bootstrap import suppressions |
| 2026-06-06 reorientation compile check | pass | `python3 -m compileall -q ...` over LivingAgentKernel kernel/service/supervisor/worker modules, scripts, and tests |
| 2026-06-06 reorientation focused frontier tests | pass | `pytest -q tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py --tb=short`: `15 passed, 1 warning in 2.69s` |
| 2026-06-06 reorientation broad bundle | pass | `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`: `160 passed, 1 warning in 4.34s` |
| 2026-06-06 reorientation CLI smokes | pass | service CLI wrote `/private/tmp/lak_service_reorient_zuRTYj/daemon_cycles.jsonl`; supervisor dry-run plan wrote `/private/tmp/lak_supervisor_reorient_mWx4Tw/supervisor/`; worker register/heartbeat/status/verify succeeded under `/private/tmp/lak_worker_reorient_DOVY7D` |
| 2026-06-06 reorientation Q3 context quorum | pass | `task_id=living-agent-kernel-reorient-static-clean-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; test files flagged as measurement-protected and covered by focused verifier |
| Focused activation tests | pass | `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`: `7 passed, 1 warning in 1.77s` |
| Activation plus service/supervisor/worker tests | pass | `pytest -q tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py --tb=short`: `21 passed, 1 warning in 4.08s` before the file-lock fix; focused activation rerun covers the added race regression |
| Broad bundle with activation | pass | `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`: `167 passed, 1 warning in 7.43s` |
| Activation static check | pass | `./.venv/bin/ruff check ...` over LivingAgentKernel modules/scripts/tests including activation: `All checks passed!` |
| Activation compile check | pass | `python3 -m compileall -q ...` over LivingAgentKernel modules/scripts/tests including activation |
| Activation CLI smoke | pass | worker process wrote registration/heartbeat receipts under `/private/tmp/lak_activation_probe2_id7PwT`; worker-plan and worker-launch recorded reviewed command receipt; supervisor-activate recorded reviewed plan receipt; worker status returned `online`; activation ledger verify returned `{"errors": [], "ok": true}` |
| Activation Q3 context quorum | pass | `task_id=living-agent-kernel-reviewed-activation-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_activation.py` flagged as measurement-protected and covered by focused/broad verifier |
| Worker wake execution tests | pass | `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`: `8 passed, 1 warning in 2.07s`; activation/worker/service/supervisor bundle: `23 passed, 1 warning in 5.47s` |
| Broad bundle with worker execution | pass | `pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short`: `168 passed, 1 warning in 5.17s` |
| Worker execution CLI smoke | pass | seeded `/private/tmp/lak_worker_execute_probe_IOZ3m2/wake_ledger.jsonl`; `living_agent_kernel_worker_process.py --execute --json` leased and completed `wake-cli-execute`; terminal wake row references `external_worker_result`, kernel replay hash `sha256:1ea2a1e8977075669c54849801b75ed32bdad8955017d48ea6c1e0b1d94d7711`, proof hash `sha256:b7000345aee0a2383229a31a393732e05a9205de090a1c13acfbb354c032712b`, and `provider_execution=false`; worker and wake ledgers verified clean |
| Worker execution Q3 context quorum | pass | `task_id=living-agent-kernel-worker-wake-execution-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_activation.py` flagged as measurement-protected and covered by focused/broad verifier |
| Launch install tests | pass | `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`: `12 passed, 1 warning in 2.61s`; activation/service/supervisor/worker bundle: `27 passed, 1 warning in 4.43s`; broad bundle: `172 passed, 1 warning in 6.02s` |
| Launch install CLI smoke | pass | `supervisor-install` installed `/private/tmp/lak_launch_install_probe_KKH59U/LaunchAgents/com.dharma.lak.install-probe.plist`; installed artifact exists, has `RunAtLoad=false`, does not contain `launchctl`, records `launch_started=false`, and activation ledger verify returned `{"errors": [], "ok": true}` |
| Launch install Q3 context quorum | pass | `task_id=living-agent-kernel-launch-install-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_activation.py` flagged as measurement-protected and covered by focused/broad verifier |
| Launch start/status tests | pass | `pytest -q tests/test_living_agent_kernel_activation.py --tb=short`: `17 passed, 1 warning in 3.19s`; activation/service/supervisor/worker bundle: `32 passed, 1 warning in 5.25s`; broad bundle: `177 passed, 1 warning in 6.16s` |
| Launch start/status static checks | pass | `python3 -m compileall -q ...` over activation module/script/test passed; `./.venv/bin/ruff check ...` over LivingAgentKernel modules/scripts/tests passed |
| Launch start/status CLI smoke | pass | `/private/tmp/lak_launch_start_probe_8aVkbb`: plan hash `sha256:a7837c8b61e2345b96de534635e3e31adb0c14abaf7c122ec9f03a380b932b0d`; install receipt `sha256:42489d67e5538d851834867f3dafbc31345b74d568f2d0f6438df3e00e8e3c04`; dry-run `supervisor-start` recorded `launch_start` `status=reviewed`; `supervisor-launch-status` returned `installed`; activation ledger verify returned `{"errors": [], "ok": true}` |
| Launch start/status Q3 context quorum | pass | `task_id=living-agent-kernel-launch-start-status-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_activation.py` flagged as measurement-protected and covered by focused/broad verifier |
| Crash-resume tests | pass | `pytest -q tests/test_living_agent_kernel_recovery.py --tb=short`: `4 passed, 1 warning in 0.86s`; recovery/activation/service/supervisor/worker bundle: `36 passed, 1 warning in 5.94s`; broad bundle: `181 passed, 1 warning in 7.59s` |
| Crash-resume static checks | pass | `python3 -m compileall -q ...` over LivingAgentKernel modules/scripts/tests including recovery passed; `./.venv/bin/ruff check ...` over LivingAgentKernel modules/scripts/tests including recovery passed |
| Crash-resume CLI smoke | pass | `/private/tmp/lak_crash_resume_probe_h91JNm`: `snapshot` returned `status=needs_recovery`, `expired_worker_lease_wake_ids=["wake-crash-probe"]`; `recover` returned `status=completed`, worker recovery receipt recovered `wake-crash-probe`; wake/worker ledger verify returned `wake_ok=true`, `worker_ok=true`, `wake_status=queued`, `lease_owner=""` |
| Crash-resume Q3 context quorum | pass | `task_id=living-agent-kernel-crash-resume-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_recovery.py` flagged as measurement-protected and covered by focused/broad verifier |
| Promotion/provider focused tests | pass | `./.venv/bin/python -m pytest tests/test_living_agent_kernel_promotion_provider.py -q --tb=short`: `7 passed in 2.42s` |
| Promotion/provider broad bundle | pass | `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_promotion_provider.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py -q --tb=short`: `184 passed in 9.84s` |
| Promotion/provider static checks | pass | `./.venv/bin/python -m ruff check ...` over promotion/provider/status modules, scripts, and tests: `All checks passed!`; compileall over the same files passed |
| Promotion/provider Q3 context quorum | pass | `task_id=living-agent-kernel-promotion-provider-worker-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_promotion_provider.py` flagged as measurement-protected and covered by focused/broad verifier |
| Provider tool-boundary marker scan | pass | `rg -n "<<<<<<<|=======|>>>>>>>" dharma_swarm/operator_core/living_agent_kernel_provider_worker.py tests/test_living_agent_kernel_promotion_provider.py scripts/runtime/living_agent_kernel_provider_worker.py`: no unresolved conflict markers |
| Provider tool-boundary compile/static/focused tests | pass | compileall over provider worker/test/CLI passed; `./.venv/bin/python -m ruff check dharma_swarm/operator_core/living_agent_kernel_provider_worker.py tests/test_living_agent_kernel_promotion_provider.py`: `All checks passed!`; focused tests: `7 passed in 2.42s` |
| Provider tool-boundary CLI smoke | pass | provider worker CLI completed `wake-provider-tool-boundary` under `/private/tmp/lak_provider_tool_boundary_5ygHsj`; receipt inspection showed `provider_may_execute_tools=false`, delegated tools `["provider_complete"]`, denied delegated tools `["read_file", "session_status"]`, and terminal wake status `completed` |
| Provider tool-boundary broad bundle | pass | `./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_living_agent_kernel_activation.py tests/test_living_agent_kernel_recovery.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_living_agent_kernel_promotion_provider.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py -q --tb=short`: `188 passed in 12.47s` |
| Provider tool-boundary Q3 context quorum | pass | `task_id=living-agent-kernel-provider-tool-boundary-v1`; `allowed_next_action=bounded_action_allowed`; `missing_families=[]`; `tests/test_living_agent_kernel_promotion_provider.py` flagged as measurement-protected and covered by focused/broad verifier |

## Verified Behaviors

- read-only manual envelope completes without provider execution;
- code-write envelope without mission contract returns review and denies write tools;
- code-write envelope with mission contract and workspace lease exposes bounded write-tool names;
- self-evolution without mutation budget blocks;
- high-risk missing context quorum blocks;
- protected file hits block and deny protected mutation;
- external evidence-only workers keep action tools denied;
- A2A/ds-goal correlation fields survive proof and runtime truth projection;
- tool-plan policy hashes are stable for the same envelope;
- `session_status` read-only tool dispatches and replays from durable rows;
- blocked authority records denied tool results;
- `read_file` denies reads without explicit allowed-file authority;
- `read_file` reads only explicitly allowed files;
- invalid read-only tool arguments fail the run with a durable tool receipt;
- unregistered/custom dispatch remains unsupported in v1;
- proof-ledger hash-chain verification detects tampering;
- `LivingAgentKernel.wake` queues, leases, runs, and records terminal wake state;
- `run_next_wake` returns idle without queued work;
- expired leased wakes can be requeued and executed with incremented attempts;
- wake-ledger hash-chain verification detects tampering;
- manual source payloads enqueue and execute through the wake ledger;
- A2A task rows preserve task id, return address, trace id, and claim authority;
- ds-goal task rows preserve mission/task ids, lease state, allowed-write roots, and verifier commands;
- persistent self-wake rows preserve agent identity and default memory namespaces;
- external fleet rows are evidence-only and deny action tools;
- A2A source closeback closes queue rows with validated kernel proof receipts;
- ds-goal source closeback records kernel result refs without terminally closing
  autonomy-spine tasks;
- persistent self-wake closeback writes witness receipts with kernel result refs;
- external-fleet closeback is refused without source mutation and is still
  recorded in the wake ledger;
- latest-wake status projects source, task, lease, result, replay, and source
  payload hash for operator inspection;
- source closeback is blocked if persisted kernel proof/replay integrity is
  missing;
- read-only envelopes cannot execute `apply_patch`;
- `apply_patch` dry-run validates allowed unified diffs without mutation;
- `apply_patch` denies targets outside `allowed_files`;
- live `apply_patch` is denied without explicit sandbox allowance and rollback
  receipt requirement;
- live `apply_patch` can mutate an allowed existing file and records rollback
  backup paths while updating runtime mutation truth;
- no provider, shell, network, browser, git, `pytest`, or `compileall` execution
  is performed by the kernel;
- control tick executes multiple queued wakes and automatically closes back A2A
  source rows when source roots are provided;
- control tick recovers expired leases before execution and returns recovered
  wake ids plus latest operator status;
- empty control snapshots report integrity-ok state;
- restart snapshots classify an expired leased wake after a fresh kernel
  instance opens the same store and prove the tick can recover it.
- subagent child wakes inherit parent authority and carry parent-run lineage;
- subagent spawn denies disallowed child agents and file-scope escalation;
- subagent spawn respects max-child limits;
- control tick executes subagent child wakes and records subagent delivery
  closeback receipts in the wake ledger.
- daemon cycles call `run_control_tick` while running and record heartbeat
  receipts;
- operator pause controls block daemon cycles without leasing queued wakes;
- operator stop controls block daemon cycles until resume without losing wakes;
- daemon control and cycle ledgers detect tampering.
- service runner executes bounded repeated daemon cycles under one lock;
- held service lock returns `lock_held` and appends no daemon-cycle receipts;
- service runner stops on durable stop controls without dropping queued wakes;
- service CLI emits JSON and writes daemon-cycle receipts.
- launchd supervisor plans use absolute paths and default `RunAtLoad=false`;
- tmux supervisor plans write review scripts without starting sessions;
- supervisor status reports never-ran/recent/stale from daemon-cycle receipts;
- supervisor CLI emits JSON plan/status receipts.
- external workers register with role, allowed source filters, max lease
  seconds, metadata, and hash-chained receipts;
- external worker heartbeat receipts project online/stale/offline status;
- registered workers without fresh heartbeats are denied wake leases;
- source-filtered workers do not lease ineligible queued wakes;
- fresh workers lease existing queued wakes through `wake_ledger.jsonl`;
- external worker completion writes worker-result receipts and terminal wake
  rows with `external_worker_result` refs;
- stale/offline worker recovery requeues only expired leases owned by stale or
  offline registered workers;
- worker ledgers detect hash-chain tampering through shared verification;
- worker CLI emits JSON lifecycle receipts and verification status.
- mismatched supervisor plan hashes deny activation without launcher calls;
- matching supervisor plan hashes record reviewed or activated receipts;
- mismatched worker command hashes deny activation without worker registration;
- bounded worker process subprocesses write registration and heartbeat receipts;
- concurrent activation appends preserve `activation_receipts.jsonl` hash-chain
  integrity through a file lock;
- worker process `--execute` leases eligible wakes and completes them with
  external-worker result receipts;
- executed worker wakes carry real kernel replay/proof refs and
  `provider_execution=false`;
- reviewed launch artifact install denies mismatched plan hashes without
  writing a target artifact;
- reviewed launch artifact install writes launchd/tmux artifacts with
  `launch_started=false`;
- launch artifact status reports installed artifacts only when content hash
  verification passes;
- launch artifact status reports changed artifacts when installed content no
  longer matches the install receipt hash;
- supervisor start review derives a launchd `launchctl bootstrap` command from
  the installed artifact receipt without calling a launcher;
- unknown install receipt hashes are denied without launcher calls;
- injected live start records `status=activated`, process refs, and
  `launch_started=true`;
- launch status reports `started` only after an activated `launch_start`
  receipt, not after dry-run review alone;
- launch start/status CLI review path leaves the service unstarted and keeps
  the activation ledger hash-chain verifiable;
- crash-resume snapshot reports queued, leased, expired, terminal, supervisor,
  worker, activation, launch, and worker-result refs from persisted ledgers;
- crash recovery blocks when wake-ledger integrity is tampered;
- crash recovery requeues stale-worker expired leases through worker recovery
  receipts;
- crash recovery does not recover expired leases owned by fresh workers;
- crash recovery CLI snapshot/recover path leaves wake and worker ledgers
  hash-chain verifiable;
- promotion admission allows provider execution only with current
  provider-executor receipts carrying explicit source/tool/work-kind authority
  and provider evidence;
- missing, expired, and revoked provider promotions block execution;
- provider workers denied for missing promotion leave queued wakes untouched;
- promoted provider workers complete eligible wakes with provider-worker receipt
  hashes and terminal wake `provider_execution=true` payload refs;
- provider tool boundaries record requested wake tools as context only,
  delegate only `provider_complete`, and deny non-provider tool execution;
- provider request payloads and terminal wake refs carry
  `provider_may_execute_tools=false` for requested wake tools such as
  `read_file` and `session_status`;
- injected async provider clients receive an `LLMRequest` built from the wake
  envelope and return hash-recorded responses;
- promotion/provider/status CLIs cover promotion, provider-worker execution, and
  OS status projection;
- OS status reports provider-worker receipt count, terminal wake ids, worker
  state, latest promotions, activation count, and per-ledger integrity;

## Commands

```bash
./.venv/bin/python -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/governed_work_admission.py dharma_swarm/operator_core/runtime_truth.py tests/test_living_agent_kernel.py tests/test_governed_work_admission.py
./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_governed_work_admission.py -q --tb=short
./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py -q --tb=short
pytest -q tests/test_living_agent_kernel.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py tests/test_living_agent_kernel.py
pytest -q tests/test_living_agent_kernel.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py tests/test_living_agent_kernel.py
pytest -q tests/test_living_agent_kernel.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py tests/test_living_agent_kernel.py
pytest -q tests/test_living_agent_kernel.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py tests/test_living_agent_kernel.py
pytest -q tests/test_living_agent_kernel.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_service.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py scripts/runtime/living_agent_kernel_service.py
pytest -q tests/test_living_agent_kernel_service.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 scripts/runtime/living_agent_kernel_service.py --store-dir /private/tmp/lak_service_probe --workspace-root /Users/dhyana/dharma_swarm --cycles 1 --interval-seconds 1 --json
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_service.py dharma_swarm/operator_core/living_agent_kernel_supervisor.py scripts/runtime/living_agent_kernel_service.py scripts/runtime/living_agent_kernel_supervisor.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py
pytest -q tests/test_living_agent_kernel_supervisor.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 scripts/runtime/living_agent_kernel_supervisor.py plan --mode launchd --repo-root /Users/dhyana/dharma_swarm --store-dir /private/tmp/lak_supervisor_probe --workspace-root /Users/dhyana/dharma_swarm --label com.dharma.lak.probe --write
python3 scripts/runtime/living_agent_kernel_supervisor.py status --store-dir /private/tmp/lak_supervisor_probe --daemon-id living-agent-kernel --now 2026-06-05T00:00:00Z
python3 -m compileall -q dharma_swarm/operator_core/living_agent_kernel.py dharma_swarm/operator_core/living_agent_kernel_workers.py dharma_swarm/operator_core/living_agent_kernel_service.py dharma_swarm/operator_core/living_agent_kernel_supervisor.py scripts/runtime/living_agent_kernel_worker.py scripts/runtime/living_agent_kernel_service.py scripts/runtime/living_agent_kernel_supervisor.py tests/test_living_agent_kernel.py tests/test_living_agent_kernel_workers.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py
pytest -q tests/test_living_agent_kernel_workers.py --tb=short
pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short
python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe register --worker-id probe-worker --role verifier --allowed-source manual --now 2026-06-05T00:00:00Z
python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe heartbeat --worker-id probe-worker --now 2026-06-05T00:00:01Z
python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe status --now 2026-06-05T00:00:02Z
python3 scripts/runtime/living_agent_kernel_worker.py --store-dir /private/tmp/lak_worker_probe verify
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-external-worker-lifecycle-v1 --risk Q3 --question "LivingAgentKernel external worker lifecycle implemented over the existing append-only wake ledger with worker registration heartbeat freshness checks source-filtered wake leasing external worker result receipts terminal wake completion stale worker expired lease recovery worker CLI JSON tests and smoke evidence without spawning worker processes calling providers creating a second queue or executing subprocess tool runtime network browser git payment deploy publish push merge or external outreach" --exact-query "KernelExternalWorkerStore KernelExternalWorkerRecord KernelExternalWorkerHeartbeat KernelExternalWorkerLease KernelExternalWorkerResult KernelExternalWorkerRecovery lease_worker_wake complete_worker_wake recover_stale_worker_leases complete_external_wake allowed_sources worker_heartbeats worker_results worker_recoveries living_agent_kernel_worker.py" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file dharma_swarm/operator_core/living_agent_kernel_workers.py --changed-file scripts/runtime/living_agent_kernel_worker.py --changed-file tests/test_living_agent_kernel_workers.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --receipt exact_local=reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_living_agent_kernel_workers.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel external worker lifecycle module, runtime CLI, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, worker process spawn, live service activation, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the worker lifecycle slice by reverting dharma_swarm/operator_core/living_agent_kernel_workers.py, scripts/runtime/living_agent_kernel_worker.py, tests/test_living_agent_kernel_workers.py, the small complete_external_wake and filtered lease/recovery store additions in dharma_swarm/operator_core/living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no worker process or external service was activated."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-supervisor-dry-run-plan-v1 --risk Q3 --question "LivingAgentKernel supervisor dry-run plans implemented with default-off launchd and tmux artifacts status from daemon-cycle receipts CLI plan and status JSON tests and smoke evidence without calling launchctl tmux cron provider subprocess tool runtime network browser git payment deploy publish or external outreach" --exact-query "KernelSupervisorPlan KernelSupervisorStatus build_supervisor_plan write_supervisor_plan supervisor_status living_agent_kernel_supervisor.py launchd plist tmux RunAtLoad false never_ran recent stale dry_run receipt_hash" --changed-file dharma_swarm/operator_core/living_agent_kernel_supervisor.py --changed-file scripts/runtime/living_agent_kernel_supervisor.py --changed-file tests/test_living_agent_kernel_supervisor.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --receipt exact_local=reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_living_agent_kernel_supervisor.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel supervisor dry-run plan module, runtime CLI, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon activation, launchctl/tmux invocation, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the supervisor dry-run slice by reverting dharma_swarm/operator_core/living_agent_kernel_supervisor.py, scripts/runtime/living_agent_kernel_supervisor.py, tests/test_living_agent_kernel_supervisor.py, and the living-agent-kernel spec/report artifacts; no daemon or external service was activated."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-service-runner-v1 --risk Q3 --question "LivingAgentKernel external service runner implemented as bounded repeated run_daemon_cycle invocations under a non-blocking file lock with CLI JSON output stop-control behavior split-brain prevention service tests CLI smoke and no duplicate queue provider subprocess tool runtime network browser git payment deploy publish or external outreach" --exact-query "run_kernel_daemon_service KernelDaemonServiceRun living_agent_kernel_service.py daemon_service.lock lock_held cycles completed_cycles run_daemon_cycle stop_on_stopped CLI --json service runner split brain" --changed-file dharma_swarm/operator_core/living_agent_kernel_service.py --changed-file scripts/runtime/living_agent_kernel_service.py --changed-file tests/test_living_agent_kernel_service.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --receipt exact_local=reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_living_agent_kernel_service.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel service-runner module, runtime CLI, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon install, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the service-runner slice by reverting dharma_swarm/operator_core/living_agent_kernel_service.py, scripts/runtime/living_agent_kernel_service.py, tests/test_living_agent_kernel_service.py, and the living-agent-kernel spec/report artifacts; no daemon or external service was installed."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-daemon-control-cycle-v1 --risk Q3 --question "LivingAgentKernel daemon control cycle implemented over existing wake ledger with durable pause resume stop controls daemon heartbeat receipts bounded run_daemon_cycle delegation to run_control_tick tamper-tested daemon ledgers and no installed daemon provider subprocess network browser git pytest or compileall execution inside the kernel" --exact-query "LivingAgentKernel KernelDaemonControlReceipt KernelDaemonCycle request_daemon_control daemon_control_state run_daemon_cycle daemon_control daemon_cycles pause resume stop heartbeat_ref next_run_after verify_daemon_control_ledger verify_daemon_cycle_ledger run_control_tick" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --receipt exact_local=reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel daemon-control cycle, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon install, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the daemon-control cycle slice by reverting edits to dharma_swarm/operator_core/living_agent_kernel.py, tests/test_living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no daemon or external service state was installed."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-subagent-wake-lifecycle-v1 --risk Q3 --question "LivingAgentKernel subagent wake lifecycle implemented over existing wake ledger with inherited authority parent-run lineage spawn limits control-tick execution subagent result closeback and no daemon provider subprocess network browser git pytest or compileall execution" --exact-query "LivingAgentKernel spawn_subagent_wake KernelSubagentDispatch subagent parent_run_id inherited_subagent_limits max_children allowed_agents max_depth allowed_files closeback_source_wake subagent_result_recorded run_control_tick wake_ledger" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel subagent wake lifecycle, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon install, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the subagent lifecycle slice by reverting edits to dharma_swarm/operator_core/living_agent_kernel.py, tests/test_living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no daemon or external service state was installed."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-restart-snapshot-v1 --risk Q3 --question "LivingAgentKernel restart snapshot implemented to replay persisted wake ledger state classify queued leased expired terminal wakes verify wake ledger integrity and prove a fresh kernel instance can recover an expired wake through run_control_tick without daemon provider subprocess network browser git pytest or compileall execution" --exact-query "LivingAgentKernel control_snapshot KernelControlSnapshot KernelRunStore control_snapshot expired_lease_wake_ids terminal_wake_ids integrity_ok restart run_control_tick recover_expired_wakes wake_ledger latest_wake_status" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel restart snapshot, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon install, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the restart snapshot slice by reverting edits to dharma_swarm/operator_core/living_agent_kernel.py, tests/test_living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no daemon or external service state was installed."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-control-tick-v1 --risk Q3 --question "LivingAgentKernel bounded control tick implemented to recover expired wakes run a limited number of queued wakes automatically close back source records and return latest wake status without starting a daemon provider subprocess network browser git pytest or compileall execution" --exact-query "LivingAgentKernel run_control_tick KernelControlTick recover_expired_wakes run_next_wake closeback_source_wake latest_wake_status recovered_wake_ids executions closebacks source_roots wake_ledger" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel control tick, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, daemon install, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the control tick slice by reverting edits to dharma_swarm/operator_core/living_agent_kernel.py, tests/test_living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no daemon or external service state was installed."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-bounded-mutation-v1 --risk Q3 --question "LivingAgentKernel bounded apply_patch adapter implemented with code-write authority allowed-file target checks explicit sandbox live-apply flags rollback backup receipts runtime mutation truth and no provider subprocess network browser git pytest or compileall execution" --exact-query "LivingAgentKernel apply_patch _dispatch_apply_patch DiffApplier parse_unified_diff mutation_mode allow_write_tool_execution rollback_receipt_required allowed_files forbidden_files backup_paths runtime_truth mutation_truth dry_run_only" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py tests/test_diff_applier.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel bounded apply_patch adapter, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, subprocess tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized." --rollback-plan "Rollback the bounded mutation slice by reverting edits to dharma_swarm/operator_core/living_agent_kernel.py, tests/test_living_agent_kernel.py, and the living-agent-kernel spec/report artifacts; no live repo mutation outside those paths is required."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-source-closeback-v1 --risk Q3 --question "LivingAgentKernel source closeback and latest wake inspection implemented over append-only wake ledger for A2A ds-goal persistent self-wake and external evidence-only refusal without provider or write-tool execution" --exact-query "LivingAgentKernel closeback_source_wake latest_wake_status KernelSourceCloseback record_wake_closeback build_task_receipt close_task a2a ds_goal persistent_self_wake external_fleet kernel_result_ref source_closeback wake_ledger" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel source-closeback implementation, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, write-tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-wake-ledger-v1 --risk Q3 --question "LivingAgentKernel append-only wake ledger implemented with queue lease execution expired-lease recovery run replay proof receipts and no provider or write-tool execution" --exact-query "LivingAgentKernel KernelRunStore KernelWakeRecord KernelWakeExecution wake_ledger enqueue_wake lease_next_wake recover_expired_wakes run_next_wake verify_wake_ledger KernelRunReplay ProofLedgerEntry RuntimeTruthPacket" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel wake-ledger implementation, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, write-tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-source-normalizers-v1 --risk Q3 --question "LivingAgentKernel source-specific wake normalizers implemented for manual A2A ds-goal persistent self-wake and external fleet rows over the append-only wake ledger without provider or write-tool execution" --exact-query "LivingAgentKernel normalize_wake_source enqueue_source_wake manual a2a ds_goal persistent_self_wake external_fleet AgentRunEnvelope AuthorityPassport KernelWakeRecord wake_ledger WorkKind A2A_CLAIM CODE_WRITE external_worker_evidence_only" --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --test-command "pytest -q tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py --tb=short" --test-timeout 120 --human-approval "Scoped continuation approval for LivingAgentKernel source-normalizer implementation, tests, spec-forge draft, and living-agent-kernel report artifacts only; no provider execution, write-tool runtime, protected governance mutation, CI, scorer, or unrelated test mutation authorized."
./.venv/bin/python scripts/runtime/context_quorum.py check --agent codex-living-agent-kernel --task-id living-agent-kernel-v1 --risk Q3 --question "LivingAgentKernel durable read-only runtime implemented with persisted events replay proof ledger governed admission runtime truth and read-only tool dispatch" --exact-query "LivingAgentKernel KernelRunStore KernelReadOnlyToolRegistry KernelRunReplay GovernedWorkAdmission RuntimeTruthPacket append_event append_proof_entry replay_run tool_results proof ledger EventLog RuntimeEnvelope" --changed-file dharma_swarm/operator_core/governed_work_admission.py --changed-file dharma_swarm/operator_core/runtime_truth.py --changed-file dharma_swarm/operator_core/living_agent_kernel.py --changed-file tests/test_governed_work_admission.py --changed-file tests/test_living_agent_kernel.py --changed-file spec-forge/living-agent-kernel/MASTER_SPEC.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/final_report.md --changed-file reports/living_agent_kernel/living-agent-kernel-20260605/verifier_matrix.md --receipt semantic_code=reports/living_agent_kernel/living-agent-kernel-20260605/semantic_context_receipt.md --receipt exact_local=reports/living_agent_kernel/living-agent-kernel-20260605/exact_local_receipt.md --test-command "./.venv/bin/python -m pytest tests/test_living_agent_kernel.py tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_agent_memory.py tests/test_profiles.py -q --tb=short" --test-timeout 120 --human-approval "Scoped operator approval for LivingAgentKernel v1 implementation, governed admission/runtime truth dependencies, tests, spec-forge draft, and living-agent-kernel report artifacts only; no protected governance, CI, scorer, or unrelated test mutation authorized."
```
