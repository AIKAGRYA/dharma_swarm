# L4 Holon Substrate Hygiene And Smoke Baseline - 2026-06-18

created_utc: 2026-06-18T08:35:00Z
operator: codex
scope: pre-build hygiene baseline plus fresh L4 supervised smoke and prod verifier receipt
status: build-ready after provider-chain accounting fix, orchestration proof wiring, SwarmManager-backed bounded execution proof, structured model-probe lease hardening, unattended L4 service-runner proof, review-only supervisor plan artifacts, governed supervisor activation receipts, bounded direct-activation heartbeat proof, and heartbeat-bound installed launch artifact proof

## Verdict

The repository is clean enough to start the L4 HOLON build phase without adding
avoidable identity-taxonomy drift or hidden hygiene debt.

The current substrate is not just a daemon. The fresh proof chain shows an
identity-bearing holon with runtime session, task claim, execution lease,
declared routing, memory receipt, artifact, outcome, persistence heartbeat,
service heartbeat, and transport reachability.

The run does not claim live model responsiveness. The model probe was
deliberately skipped. The latest verifier does prove bounded specialist
execution over a read-only `SwarmManager` stack with deterministic in-process
`AgentRunner`s, but the always-on holon's own live service still needs a
governed live model proof before it can be called fully Hermes/OpenClaw-class.

## Hygiene Gates

Observed from `/Users/dhyana/dharma_swarm` on 2026-06-18:

- `make agent-build-closeout`: PASS after regenerating docops auto sections.
- `make onboard`: PASS with live ops proof-gap surfaces absent or zero.
- `python3 scripts/governance/spine_dispatch_mode_report.py --strict`: PASS.
- `python3 scripts/governance/runtime_receipt_coverage_report.py --strict`: FAIL
  on historical/pre-fix receipt debt.
- `pytest tests/test_holon_l4_smoke.py tests/test_holon_service_liveness.py tests/test_holon_transport_liveness.py tests/test_holon_health.py tests/test_holon_bridge.py tests/test_holon_runtime.py -q`: 62 passed.
- `pytest tests/test_agent_runner.py tests/test_providers_quality_track.py tests/test_runtime_lifecycle.py tests/test_runtime_receipt_coverage_report.py tests/test_orchestrator_spine_dispatch.py -q`: 121 passed.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py tests/test_holon_service_liveness.py tests/test_holon_transport_liveness.py tests/test_holon_health.py tests/test_holon_bridge.py tests/test_holon_runtime.py -q`: 66 passed.
- `pytest tests/test_holon_l4_smoke.py tests/test_holon_orchestrate.py -q`: 12 passed.
- `pytest tests/test_holon_l4_smoke.py tests/test_holon_orchestrate.py tests/test_live_ops_census.py -q`: 107 passed.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py tests/test_live_ops_census.py -q`: 109 passed after bounded subtask execution mode.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py tests/test_live_ops_census.py -q`: 110 passed, 3 sklearn runtime warnings, after read-only `SwarmManager` bounded execution proof.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py tests/test_live_ops_census.py -q`: 112 passed, 3 sklearn runtime warnings, after subprocess model-probe lease gate.
- `pytest tests/test_holon_l4_smoke.py -q`: 13 passed, 1 sklearn runtime warning, after structured model-probe lease receipt hardening.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py tests/test_live_ops_census.py -q`: 113 passed, 3 sklearn runtime warnings, after structured model-probe lease receipt hardening.
- `pytest tests/test_holon_l4_service.py -q`: 4 passed after unattended
  service-runner proof.
- `pytest tests/test_holon_l4_service.py tests/test_holon_l4_smoke.py tests/test_holon_orchestrate.py tests/test_live_ops_census.py -q`: 117 passed, 3 sklearn runtime warnings, after service-runner live-ops evidence wiring.
- `pytest tests/test_holon_l4_supervisor.py -q`: 5 passed after review-only
  launchd/tmux supervisor plan rendering and path-like name refusal.
- `pytest tests/test_holon_l4_supervisor.py tests/test_holon_l4_service.py tests/test_holon_l4_smoke.py tests/test_holon_orchestrate.py tests/test_live_ops_census.py -q`: 122 passed, 3 sklearn runtime warnings, after supervisor plan wiring.
- `pytest tests/test_holon_l4_activation.py -q`: 8 passed after governed
  install/start activation receipt wiring, bounded direct service activation
  proof, and heartbeat-required installed tmux launch artifact proof.
- `pytest tests/test_holon_l4_activation.py tests/test_holon_l4_supervisor.py -q`: 11 passed after supervisor activation CLI coverage.
- `pytest tests/test_holon_l4_activation.py tests/test_holon_l4_supervisor.py tests/test_holon_l4_service.py tests/test_holon_l4_smoke.py tests/test_holon_orchestrate.py tests/test_live_ops_census.py -q`: 130 passed, 3 sklearn runtime warnings, after heartbeat-required launch artifact service smoke wiring.
- `pytest tests/test_holon_orchestrate.py tests/test_holon_l4_smoke.py -q`: 15 passed, 3 sklearn runtime warnings, after read-only `SwarmManager` bounded execution proof.
- `pytest tests/test_holon_l4_smoke.py -q`: 12 passed, 1 sklearn runtime warning, after subprocess model-probe lease gate.
- `ruff check scripts/verify_holon_harness_prod.py dharma_swarm/holon_l4_smoke.py tests/test_holon_l4_smoke.py dharma_swarm/holon_orchestrate.py tests/test_holon_orchestrate.py`: PASS.
- `ruff check dharma_swarm/holon_l4_smoke.py tests/test_holon_orchestrate.py scripts/verify_holon_harness_prod.py`: PASS after SwarmManager verifier gate.
- `ruff check dharma_swarm/holon_l4_smoke.py scripts/holon_l4_smoke.py scripts/verify_holon_harness_prod.py tests/test_holon_l4_smoke.py`: PASS after subprocess model-probe lease gate.
- `./.venv/bin/python -m ruff check dharma_swarm/holon_l4_smoke.py scripts/holon_l4_smoke.py scripts/verify_holon_harness_prod.py tests/test_holon_l4_smoke.py`: PASS after structured model-probe lease receipt hardening.
- `./.venv/bin/python -m ruff check dharma_swarm/holon_l4_service.py scripts/holon_l4_service.py tests/test_holon_l4_service.py scripts/verify_holon_harness_prod.py scripts/runtime/live_ops_census.py`: PASS after service-runner proof wiring.
- `./.venv/bin/python -m ruff check dharma_swarm/holon_l4_supervisor.py scripts/holon_l4_supervisor.py tests/test_holon_l4_supervisor.py scripts/verify_holon_harness_prod.py scripts/runtime/live_ops_census.py`: PASS after supervisor plan wiring.
- `./.venv/bin/python -m ruff check dharma_swarm/holon_l4_activation.py scripts/holon_l4_activation.py tests/test_holon_l4_activation.py scripts/verify_holon_harness_prod.py scripts/runtime/live_ops_census.py`: PASS after activation receipt wiring.
- `./.venv/bin/python -m ruff check dharma_swarm/holon_l4_activation.py scripts/holon_l4_activation.py tests/test_holon_l4_activation.py scripts/verify_holon_harness_prod.py`: PASS after heartbeat-required launch artifact service smoke wiring.
- `./.venv/bin/python -m py_compile scripts/verify_holon_harness_prod.py dharma_swarm/holon_l4_smoke.py dharma_swarm/holon_orchestrate.py`: PASS.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS,
  receipt `reports/sovereign_holons/verify_holon_harness_prod_20260618T085404Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after live-ops
  projection and persistence-order fix, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T090329Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  orchestration naming hardening, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T090825Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after bounded
  subtask execution mode, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T091618Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  read-only `SwarmManager` bounded specialist execution gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T092519Z.{json,md}`.
- `./.venv/bin/python scripts/holon_l4_smoke.py codex_composer --session-id l4-holon-swmanager-bounded-20260618T0930Z --require-transport-reachable --transport-agent-uid codex_composer --transport-heartbeat-path /Users/dhyana/.dharma/a2a_bus/bridge_heartbeats/codex_composer.json --enable-orchestration-probe --require-orchestration --orchestration-execution-mode bounded_subtask_execution --orchestration-timeout-seconds 10 --use-readonly-swarm-manager-orchestrator`: PASS, persisted cycle 10 with `live_specialist_execution=true` and `live_model_call=false`.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon.json --write`: PASS; `holon.codex_composer_l4` reports `status=live`, `proof_state=bound`, and no proof gaps.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  subprocess model-probe lease gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T093605Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  structured model-probe lease receipt hardening, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T094633Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  unattended service-runner proof, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T095821Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py --mode smoke`: PASS
  after supervisor plan artifact gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T100828Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  supervisor plan artifact gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T101409Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py --mode smoke`: PASS
  after supervisor activation receipt gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T102158Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  supervisor activation receipt gate, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T102334Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py --mode smoke`: PASS
  after bounded direct activation service smoke, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T102856Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  bounded direct activation service smoke, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T102959Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py --mode smoke`: PASS
  after heartbeat-required installed launch artifact service smoke, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T104223Z.{json,md}`.
- `./.venv/bin/python scripts/verify_holon_harness_prod.py`: PASS after
  heartbeat-required installed launch artifact service smoke, receipt
  `reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.{json,md}`.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon-launch-artifact.json --write`: PASS; `holon.codex_composer_l4` reports `status=live`, `proof_state=bound`, `proof_gaps=[]`, and points at `verify_holon_harness_prod_20260618T104301Z.json`.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon-service.json --write`: PASS; `holon.codex_composer_l4` still reports `status=live`, `proof_state=bound`, `proof_gaps=[]`, and now lists `dharma_swarm/holon_l4_service.py` plus `scripts/holon_l4_service.py` as evidence.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon-supervisor.json --write`: PASS; `holon.codex_composer_l4` reports `status=live`, `proof_state=bound`, `proof_gaps=[]`, and now lists `dharma_swarm/holon_l4_supervisor.py` plus `scripts/holon_l4_supervisor.py` as evidence.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon-activation.json --write`: PASS; `holon.codex_composer_l4` reports `status=live`, `proof_state=bound`, `proof_gaps=[]`, points at `verify_holon_harness_prod_20260618T102334Z.json`, and now lists `dharma_swarm/holon_l4_activation.py` plus `scripts/holon_l4_activation.py` as evidence.
- `./.venv/bin/python scripts/holon_l4_service.py codex_composer --session-id l4-direct-activation-refresh-20260618T1030Z --cycles 1 --interval-seconds 0 --json`: PASS; refreshed the real `codex_composer` service heartbeat and produced artifact `l4-direct-activation-refresh-20260618T1030Z.json` without a live model call.
- `./.venv/bin/python scripts/holon_l4_smoke.py codex_composer --session-id l4-direct-activation-orchestration-refresh-20260618T1031Z --require-transport-reachable --transport-agent-uid codex_composer --transport-heartbeat-path /Users/dhyana/.dharma/a2a_bus/bridge_heartbeats/codex_composer.json --enable-orchestration-probe --require-orchestration --orchestration-execution-mode bounded_subtask_execution --orchestration-timeout-seconds 10 --use-readonly-swarm-manager-orchestrator`: PASS; refreshed the real persisted L4 proof with orchestration, transport, service heartbeat, memory receipt, artifact, and `live_model_call=false`.
- `./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes --output /tmp/dharma-live-ops-holon-direct-activation.json --write`: PASS; `holon.codex_composer_l4` reports `status=live`, `proof_state=bound`, `proof_gaps=[]`, points at `verify_holon_harness_prod_20260618T102959Z.json`, and uses latest artifact `/Users/dhyana/.dharma/agents/codex_composer/artifacts/l4-direct-activation-orchestration-refresh-20260618T1031Z.json`.
- `./.venv/bin/python scripts/docops/check_docops_integrity.py --write-auto-sections`: PASS.
- `./.venv/bin/python scripts/docops/check_docops_integrity.py`: PASS after
  supervisor plan wiring.
- `make onboard`: PASS; branch remained ahead 8/behind 21 with a large
  pre-existing dirty tree.
- `make agent-build-closeout`: PASS; printed known/pre-existing local
  Semgrep warnings/findings under Palantir research scripts, but exited 0 and
  no new L4 harness findings were introduced.
- Governance vocabulary preflight make targets: PASS; Semantic Commons verifier
  available with objects=28, aliases=151, errors=0, warnings=0. The route hits
  are historical/existing governance artifacts, not the new L4 supervisor
  files. An earlier wording in this report self-triggered the scanner; the
  wording was fixed and the rerun stayed clean for this report.

The strict runtime receipt report remains useful and intentionally red:

- runtime receipts: 10964
- major task receipts: 4054
- side effect key coverage: 10524/10964, 95.99%
- latest major mission/artifact coverage: 100%
- latest terminal provider/model payload/proof/accounted: 90.0% / 95.0% / 95.0%
- active head side effect key cleanliness: PASS
- historical score gate gap: 440 core receipts missing side effect keys
- historical idempotency join coverage: 311/4054
- historical field coverage: 3834/4054

The fresh strict rerun found one pre-fix terminal `execution_error` receipt
from `2026-06-18T08:27:37Z` with provider-chain failure text but no structured
provider/model payload. That was a real code-path gap, not a reporting artifact.
The fix landed in the same baseline pass:

- `dharma_swarm/providers.py` raises structured `ProviderChainExecutionError`
  with chain, failure trace, selected provider, and selected model.
- `dharma_swarm/agent_runner.py` retains attempted selected route metadata on
  provider-chain failure without claiming a served model.
- `dharma_swarm/orchestrator.py` stamps attempted selected route metadata only
  on failure, while preserving served-route-only semantics on success.
- `tests/test_runtime_lifecycle.py` proves source-marked provider-chain
  execution errors are receipt-accounted and do not trip production readiness in
  an isolated runtime DB.

The remaining red strict report is therefore historical/pre-fix receipt debt,
not a current code-path blocker for starting the L4 substrate build. It must
stay visible, but it should not be hidden by rewriting live history.

## Drift Fixed Before Build

- `dharma_swarm/operator_core/ds_goal_wrapper_contract.py` now parses the
  installed `ds-goal` wrapper by executable semantics instead of treating any
  commented `dharma_swarm_main` fallback as proof that main is preferred.
- `tests/test_ds_goal_wrapper_receipt_probe.py` and
  `tests/test_live_ops_census.py` cover the converged wrapper case.
- `docs/governance/ACTIVE_TRACK.yaml` now uses the actual dispatch verifier for
  runtime-truth-spine adoption instead of a stale import-proxy criterion.
- Provider-chain failures now carry structured attempted provider/model
  provenance into runtime receipts.
- Docops auto-generated inventories were refreshed after the hygiene changes.

## L4 Build Slice Landed

The first build slice after hygiene is the missing thin orchestration adapter:

- `dharma_swarm/holon_orchestrate.py` loads the holon's identity, decomposes a
  mission, creates a structured subtask plan, dispatches through existing
  `Orchestrator.fan_out()`, aggregates through `fan_in()`, and delegates final
  synthesis to an injected holon-owned synthesizer.
- It does not create a second orchestrator, task store, model router, or receipt
  schema.
- It requires at least two subtasks and, by default, at least two model lanes
  before it will claim orchestration.
- It reports `live_model_call_claimed=false` unless a caller explicitly wires a
  live synthesizer under lease.
- `tests/test_holon_orchestrate.py` covers the successful fan-out/fan-in path,
  false model-tier diversity refusal, and under-decomposed work refusal.
- `dharma_swarm/holon_l4_smoke.py` now has an optional orchestration probe. It
  is disabled by default, but when `require_orchestration=true` the L4 proof
  must run the orchestration adapter and prove subtask planning, fan-out
  dispatch, model-tier diversity, fan-in aggregation, and synthesis.
- `tests/test_holon_l4_smoke.py::test_l4_supervised_smoke_can_require_orchestration_probe`
  proves the supervised L4 chain can require that orchestration proof without
  claiming a live model call.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_orchestration_probe_stub`, so the receipt-producing prod verifier checks
  the same required orchestration proof over the existing Orchestrator spine.
- The verifier header was corrected to match the executable check list and stop
  advertising older sleep-time/frontier/external reread gates that this script
  does not currently run.
- `scripts/runtime/live_ops_census.py` now publishes a read-only
  `holon.codex_composer_l4` surface. It folds existing HOLON service heartbeat,
  A2A transport heartbeat, persisted L4 event, latest L4 artifact, and prod
  verifier receipt into one operator-visible row without starting or supervising
  anything.
- The live-ops surface exposed a real persistence-order bug:
  `run_l4_supervised_smoke()` returned `overall_pass=true` but had persisted the
  event before final `overall_pass` and `claim_scope` were computed. The save now
  happens after final proof computation, and
  `tests/test_holon_l4_smoke.py` asserts the durable event stores the final pass
  state.
- The orchestration proof is now explicitly named as
  `execution_mode=dispatch_aggregation_probe` and
  `live_specialist_execution_claimed=false`. This prevents the deterministic
  harness from being mistaken for final live specialist execution.
- `dharma_swarm/holon_orchestrate.py` now also supports
  `execution_mode=bounded_subtask_execution`. In this mode it creates real
  subtask `Task` records, dispatches each selected specialist through the
  existing Orchestrator execution path, waits boundedly, and aggregates the
  task-board results. It serializes subtask execution to avoid SQLite runtime DB
  write contention in the proof path.
- `dharma_swarm/holon_l4_smoke.py` can pass the bounded execution mode through
  `L4SmokeConfig`, and `tests/test_holon_l4_smoke.py` proves the full L4 proof
  chain can require `live_specialist_execution=true` when an execution-capable
  orchestrator/pool is injected. It still does not claim a live model call.
- `tests/test_holon_orchestrate.py::test_holon_orchestration_executes_on_read_only_swarm_manager_stack`
  proves the same bounded path on a real read-only `SwarmManager` boot with its
  canonical SQLite `TaskBoard`, real `AgentPool`, real `Orchestrator`, real
  `MessageBus`, and deterministic in-process `AgentRunner`s. This closes the
  previous gap between injected test pools and the actual manager organs.
- `dharma_swarm/holon_l4_smoke.py` now exposes bounded `subtask_task_ids` in
  the orchestration probe receipt, allowing the verifier to cross-check actual
  task-board completion instead of relying only on summarized dispatch counts.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_swarm_manager_bounded_execution`. It boots `SwarmManager` in
  `DHARMA_READ_ONLY_BOOT=1`, isolates `HOME` to a temp directory, spawns
  deterministic no-provider runners into the real pool, runs the L4 bounded
  orchestration probe, and asserts two completed subtask records. The gate
  explicitly keeps `live_model_call_claimed=false`.
- `scripts/holon_l4_smoke.py` now exposes the same manager-backed path as a
  repeatable CLI option via `--use-readonly-swarm-manager-orchestrator`,
  `--require-orchestration`, and
  `--orchestration-execution-mode bounded_subtask_execution`. The default CLI
  behavior is unchanged when those flags are absent.
- Declared live model probes now require a structured
  `dharma.holon_model_probe_lease.v1` receipt. The lease is bound to the holon
  name, provider type, model, smoke session id, explicit allow flags, issue
  time, expiry time, and an embedded digest computed without trusting the
  digest field itself.
- Subprocess model probes for `codex`/`claude_code` additionally require both
  `--allow-subprocess-model-probe` and a lease receipt whose
  `allow_subprocess_provider=true`. Override without a receipt path refuses
  before provider construction and receipts `model_probe_lease_path_missing`;
  tampered receipts refuse with `model_probe_lease_invalid:<failed-checks>`.
- `scripts/holon_l4_smoke.py` now exposes `--model-probe-lease-path`, and
  `scripts/verify_holon_harness_prod.py` proves both branches: override
  without a receipt is refused, while a valid expiring digest-backed receipt
  allows a stubbed subprocess route.
- `dharma_swarm/holon_l4_service.py` adds the next pilot-to-prod slice: a
  launchd/tmux-ready service runner around the existing L4 smoke proof. It
  uses a non-blocking per-holon service lock to prevent split-brain runs,
  supports bounded or unbounded repeated cycles, writes only the existing
  service heartbeat ledger, and returns a compact
  `dharma.holon_l4_service_run.v1` receipt.
- `scripts/holon_l4_service.py` exposes that runner as an external supervisor
  entrypoint. By default it does not call a live model; if `--live-model-probe`
  is used, it inherits the structured lease controls from `L4SmokeConfig`.
- `tests/test_holon_l4_service.py` proves unattended one-cycle execution,
  multi-cycle session isolation, split-brain lock refusal before heartbeat
  writes, and CLI JSON output.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_service_runner_unattended_wake`, which proves both lock-held refusal and
  an unlocked unattended L4 cycle that writes a fresh `holon-l4-service`
  heartbeat.
- `dharma_swarm/holon_l4_supervisor.py` adds the review-only supervisor plan
  layer for that service runner. It renders deterministic launchd plist and
  tmux script artifacts for `scripts/holon_l4_service.py`, includes safety
  metadata proving no install/start side effect occurred, and writes only
  review artifacts under the planned supervisor directory.
- `scripts/holon_l4_supervisor.py` exposes the same renderer as a CLI. Passing
  `--output-dir` writes reviewable plan/plist/script artifacts; it does not call
  `launchctl`, start tmux, or spawn the L4 service.
- `tests/test_holon_l4_supervisor.py` proves launchd plans are default-off and
  absolute, tmux plans are script-only, artifact writing does not touch a
  LaunchAgents install directory, the CLI writes review artifacts, and
  path-like holon names are refused before artifact refs are built.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_supervisor_plan_artifacts`, proving both launchd and tmux supervisor
  artifacts are renderable, digest-backed, and review-only.
- `dharma_swarm/holon_l4_activation.py` adds the governed activation receipt
  layer for L4 supervisor artifacts. It stores an append-only
  `dharma.holon_l4_activation_receipt.v1` hash ledger beside the supervisor
  plan, denies hash-mismatched plans before writing install artifacts, installs
  reviewed launchd/tmux artifacts without starting them, records reviewed start
  commands without launch side effects, and supports explicit live execution
  only behind a caller-supplied `live=True` boundary.
- `scripts/holon_l4_activation.py` exposes that layer as a CLI with
  `supervisor-install`, `supervisor-start`, `supervisor-launch-status`, and
  `supervisor-activate`.
- `tests/test_holon_l4_activation.py` proves denied installs do not write
  artifacts, reviewed launchd/tmux installs do not start services, launch
  artifact status detects changed content and started receipts, start review
  does not execute, injected live start records `launch_started=true`, and the
  CLI install/start/status path stays review-only by default.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_supervisor_activation_receipts`, proving the hash-reviewed install/start
  receipt path with temp launch artifacts and an injected launcher instead of a
  real process manager call.
- `dharma_swarm/holon_l4_activation.py` can now require a fresh service
  heartbeat after direct live activation. When `require_service_heartbeat=true`,
  the activation receipt includes `service_state_ref`; if no fresh heartbeat is
  observed the activation status is `failed`.
- `tests/test_holon_l4_activation.py::test_direct_activation_can_require_service_heartbeat_after_bounded_run`
  proves an approved bounded L4 service command can run once in temp state and
  return an activation receipt with `service_alive=true`,
  `latest_service_id=holon-l4-service`, and the expected session id.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_direct_activation_service_smoke`, which runs the same bounded activation
  path in the prod verifier and requires the heartbeat-backed activation
  receipt.
- `dharma_swarm/holon_l4_activation.py` also binds installed launch artifact
  starts to service liveness. Install receipts now carry `agents_root`;
  `supervisor-start --live --require-service-heartbeat` records
  `service_state_ref` and fails if the installed artifact does not produce a
  fresh holon service heartbeat.
- `tests/test_holon_l4_activation.py::test_installed_tmux_launch_artifact_can_require_service_heartbeat_after_bounded_start`
  proves the installed tmux launch artifact itself can run a bounded service
  cycle and write a fresh heartbeat.
- `scripts/verify_holon_harness_prod.py` now includes
  `l4_launch_artifact_service_smoke`, proving the heartbeat-bound launch
  artifact start path inside the prod verifier without calling a real operator
  process manager.

This is not yet the full live Opus/flagship synthesis proof. It is the clean
wiring organ plus an L4 proof hook that the live proof can now use.

## Fresh Prod Verifier Receipt

Command:

```text
./.venv/bin/python scripts/verify_holon_harness_prod.py
```

Observed result:

```text
OVERALL_PASS: True
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.md
```

Machine receipt checks:

- tests: PASS
- live_smoke_free: PASS
- passk: PASS
- artifact_gate: PASS
- l4_supervised_chain: PASS
- l4_service_runner_unattended_wake: PASS
- l4_supervisor_plan_artifacts: PASS
- l4_supervisor_activation_receipts: PASS
- l4_direct_activation_service_smoke: PASS
- l4_launch_artifact_service_smoke: PASS
- l4_model_response_probe_stub: PASS
- l4_unsafe_subprocess_probe_refusal: PASS
- l4_subprocess_model_probe_lease_gate: PASS
- l4_transport_probe_stub: PASS
- l4_orchestration_probe_stub: PASS
- l4_swarm_manager_bounded_execution: PASS
- exportable: PASS
- structured model-probe lease proof: missing lease path refused; valid
  digest-backed expiring lease allowed a stubbed `codex` subprocess route
- service-runner proof: lock-held refusal before provider/runtime work; unlocked
  unattended L4 cycle completed, wrote artifact/proof digest, and left fresh
  `holon-l4-service` heartbeat

Latest receipt after the live-ops projection and persistence-order fix:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T090329Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T090329Z.md
```

Latest receipt after orchestration naming hardening:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T090825Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T090825Z.md
l4_orchestration_probe_stub: PASS
execution_mode: dispatch_aggregation_probe
live_specialist_execution_claimed: false
```

Latest receipt after read-only `SwarmManager` bounded execution:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T092519Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T092519Z.md
l4_swarm_manager_bounded_execution: PASS
execution_mode: bounded_subtask_execution
live_specialist_execution_claimed: true
live_model_call_claimed: false
completed_subtasks: 2
```

Latest receipt after subprocess model-probe lease gate:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T093605Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T093605Z.md
l4_subprocess_model_probe_lease_gate: PASS
overall_pass: true
```

Latest receipt after structured model-probe lease receipt hardening:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T094633Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T094633Z.md
l4_subprocess_model_probe_lease_gate: PASS
missing_path_reason: model_probe_lease_path_missing
valid_lease_schema: dharma.holon_model_probe_lease.v1
valid_lease_digest: sha256:407266791b8fced85305abb0cf6166654ab97082e8e881f42719e0e2050a67f0
allowed_subprocess_route_status: ok
allowed_subprocess_stub_model_call_accounted: true
overall_pass: true
```

Latest receipt after unattended service-runner proof:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T095821Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T095821Z.md
l4_service_runner_unattended_wake: PASS
locked_status: lock_held
unlocked_status: completed
completed_cycles: 1
cycle_status: passed
latest_service_id: holon-l4-service
latest_service_status: idle
overall_pass: true
```

Latest receipt after review-only supervisor plan artifacts:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T101409Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T101409Z.md
l4_supervisor_plan_artifacts: PASS
launchd_label: com.dharma.verify-holon-l4
launchd_run_at_load: false
launchd_keep_alive: true
launchd_program: scripts/holon_l4_service.py
tmux_session: verify_holon_l4
install_performed: false
service_started: false
launchctl_invoked: false
tmux_invoked: false
overall_pass: true
```

Latest receipt after governed supervisor activation receipts:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T102334Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T102334Z.md
l4_supervisor_activation_receipts: PASS
denied_install_status: denied
reviewed_install_status: installed
reviewed_start_status: reviewed
injected_start_status: activated
installed_artifact_status: started
ledger_ok: true
real_process_manager_called: false
overall_pass: true
```

Latest receipt after bounded direct activation service smoke:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T102959Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T102959Z.md
l4_direct_activation_service_smoke: PASS
direct_activation_status: activated
process_return_code: 0
service_alive: true
latest_service_id: holon-l4-service
latest_session_id: verifier-l4-direct-activation
ledger_ok: true
overall_pass: true
```

Latest receipt after heartbeat-required installed launch artifact service smoke:

```text
machine_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.json
human_receipt: reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.md
l4_launch_artifact_service_smoke: PASS
launch_artifact_kind: tmux_script
launch_start_status: activated
process_return_code: 0
service_alive: true
latest_service_id: holon-l4-service
latest_session_id: verifier-l4-launch-artifact
ledger_ok: true
overall_pass: true
```

## Live-Ops HOLON Surface

Command:

```text
./.venv/bin/python scripts/runtime/live_ops_census.py --no-probes | jq '.surfaces[] | select(.id=="holon.codex_composer_l4")'
```

Observed state after rerunning the manager-backed bounded L4 smoke:

```text
status: live
proof_state: bound
proof_gaps: []
service_alive: true
transport_reachable: true
persisted_overall_pass: true
persisted_orchestration: true
persisted_model_responsive: false
prod_verifier_orchestration: true
service_supervisor_activation_evidence: dharma_swarm/holon_l4_service.py, scripts/holon_l4_service.py, dharma_swarm/holon_l4_supervisor.py, scripts/holon_l4_supervisor.py, dharma_swarm/holon_l4_activation.py, scripts/holon_l4_activation.py
latest_service_id: holon-l4-smoke
latest_session_id: l4-direct-activation-orchestration-refresh-20260618T1031Z
latest_artifact: /Users/dhyana/.dharma/agents/codex_composer/artifacts/l4-direct-activation-orchestration-refresh-20260618T1031Z.json
prod_verifier: reports/sovereign_holons/verify_holon_harness_prod_20260618T104301Z.json
```

That is the correct updated boundary: the current live holon has identity,
service heartbeat, transport reachability, artifact, memory receipt, final
persisted body proof, bounded specialist execution proof, and now a
launchd/tmux-ready service-runner entrypoint plus review-only supervisor plan
artifacts, governed activation receipts, a bounded direct activation proof that
an approved service command can write a fresh heartbeat, and a heartbeat-bound
installed launch artifact proof. It still does not claim live model
responsiveness or an actually installed always-on launchd/tmux service on the
operator machine.

Additional architecture boundary found while designing the next live proof:

- `Orchestrator.fan_out()` creates dispatches but does not itself aggregate live
  `AgentRunner` outputs.
- The real `AgentPool.get_result()` intentionally returns `None`; live results
  are written through `_execute_task()` into task state and runtime receipts.
- `fan_out()` currently keys every dispatch to the same parent task id, which is
  not yet a true parallel subtask execution substrate for live specialists.

Therefore the system will not claim model responsiveness through the `codex`
subprocess route unless an explicit structured operator lease receipt allows
it. The bounded specialist adapter now exists as
`execution_mode=bounded_subtask_execution`, is verified against an actual
read-only `SwarmManager`/agent pool in the prod verifier, and has been persisted
into the live holon L4 surface. The remaining step is no longer "prove the
manager path exists" or "persist orchestration"; it is to add a governed live
model response proof by running a leased model probe.

## Fresh L4 Smoke

Command:

```text
./.venv/bin/python scripts/holon_l4_smoke.py codex_composer --session-id l4-holon-hygiene-bound-20260618T0828Z --lease-seconds 900
```

Observed result:

```text
overall_pass: true
holon_id: codex_composer
session_id: l4-holon-hygiene-bound-20260618T0828Z
artifact: /Users/dhyana/.dharma/agents/codex_composer/artifacts/l4-holon-hygiene-bound-20260618T0828Z.json
artifact_digest: sha256:957d892b8022a7bea519826d4bbba0c88a9d58b629bf0341010901ceab20ff06
proof_digest: sha256:5cfc6f9c870ed8850e82b175b11096a40e2d3fd43b462390c105b237fadcd2f9
memory_receipt: reports/sovereign_holons/l4_memory_write_receipts.jsonl
memory_receipt_id: memory_kernel_write_receipt:3c9a0d97eacc2bf2dcfa6e12
service_record_hash: sha256:1a8c03128895422b1db8349d7e03b54b07ca3124a2be4fa2b232d62fb212d3f9
transport_heartbeat: /Users/dhyana/.dharma/a2a_bus/bridge_heartbeats/codex_composer.json
transport_status: IDLE
transport_stream: DHARMA_FLEET
transport_consumer: codex_composer_inbox
```

Proof levels:

- identity_loaded: true
- runtime_session: true
- task_claim: true
- execution_lease: true
- routing_decision: true
- memory_receipt: true
- artifact: true
- outcome: true
- persistence: true
- service_heartbeat: true
- transport_reachable: true
- orchestration: true
- model_responsive: false

Routing evidence:

- holon model: `gpt-5.5`
- provider type: `codex`
- declared-first route: true
- live model call: false
- system prompt chars: 1209

Latest bounded orchestration smoke:

```text
session_id: l4-holon-swmanager-bounded-20260618T0930Z
overall_pass: true
persistence_cycle: 10
artifact: /Users/dhyana/.dharma/agents/codex_composer/artifacts/l4-holon-swmanager-bounded-20260618T0930Z.json
artifact_digest: sha256:45731909f97b7fa8c163baffcbc30f6d0a3f6f2119ec23f2f1bd5980fff1f978
proof_digest: sha256:571a257d6878c300d0ce5dbbc1f0e52aabeafa8175667f72fa38fa7a9393a5a0
execution_mode: bounded_subtask_execution
live_specialist_execution_claimed: true
live_model_call_claimed: false
subtask_task_ids: 5ae320bb6aac48e1, 6327bff5275d493d
transport_reachable: true
service_alive: true
model_responsive: false
```

## Build Boundary

The next build phase should treat this as the L4 body baseline:

- keep gateways as adapters over one identity, memory, state, and receipt spine;
- add governed live model responsiveness only with an explicit structured
  lease receipt and route;
- avoid a second receipt schema or separate truth store;
- wire orchestration to existing spine/holon modules instead of creating a new
  parallel substrate;
- keep supervisor plans as review artifacts until a separate governed
  install/start step writes an activation receipt; this receipt path now exists,
  can require a fresh heartbeat from the launched artifact, and the remaining
  production step is to run it against an operator-approved real install target;
- use bounded direct activation and heartbeat-bound launch artifact activation
  as proofs of service-command and launch-target viability, not as substitutes
  for an installed always-on supervisor;
- leave historical receipt remediation as a visible follow-on workstream unless
  it blocks a concrete current proof.
