# Runtime Spine Hardening Progress - Receipt Coverage Gate

Date: 2026-06-14 JST
Track: `runtime-truth-spine-adoption-2026-06`
Starting hardening score: 70/100
Current hardening score: 70/100

## Latest Checkpoint - Orchestrator fan_out Success Fresh Field Proof

- `runtime_lifecycle_receipt_probe.py` now accepts `--topology fan-out` for
  the `orchestrator-spine` producer.
- Fresh temp proof `run-orchestrator-fanout-success-proof-rerun` in
  `/private/tmp/orchestrator-fanout-success-proof-rerun-20260614T1100Z/state/runtime.db`
  proves the current orchestrator fan_out success path passes the scoped
  70->75 field gate.
- The scoped run produced 16/16 runtime receipts with all core fields,
  2/2 major idempotency joins, 2/2 artifact joins, 2/2 latest mission payloads,
  2/2 latest artifact payloads, 100% delegation `receipt_json` fill, and clean
  5/15/60 minute active-head windows.
- The proof does not count as provider/model production readiness because the
  probe did not record an actual served provider/model route.
- The proof does not repair or quarantine the historical `fanout_success=2052`
  field debt in the global live DB.

Fresh scoped verifier:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --db /private/tmp/orchestrator-fanout-success-proof-rerun-20260614T1100Z/state/runtime.db \
  --run-id run-orchestrator-fanout-success-proof-rerun \
  --strict
exit 0
Runtime receipts: 16
Delegation receipt_json fill: 100.0%
Major task receipts: 2
Major receipt idempotency join: 100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload: 100.0%
Latest major artifact payload: 100.0%
Active head side_effect_key clean: PASS
70->75 score gate: PASS
Production-readiness blockers:
  - latest major task receipts do not all carry provider/model payloads
  - latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata
```

Score consequence:

- Keep runtime spine at 70/100.
- The fan_out success source path now has fresh scoped field proof.
- Global strict coverage remains red on active-head `ds_goal_cli` debt,
  historical orchestrator debt, unresolved quarantine decisions, and
  provider/model production blockers.

## Latest Verification Recheck - Global Receipt Gate Still Red

Fresh receipt-gate rerun:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1
Runtime receipts: 8027
Major task receipts: 3567
side_effect_key: 1001/8027 = 12.47%
Major receipt idempotency join: 1.23%
Major receipt artifact record join: 27.08%
Latest major mission payload: 16.36%
Latest major artifact payload: 16.36%
Latest major provider/model: 3.64%
Latest major provider/model proof/accounted: 58.79% / 58.79%
Latest terminal provider/model proof/accounted: 97.0% / 97.0%
Active head side_effect_key clean: FAIL
70->75 score gate: FAIL
Freshest current producer gap: ds_goal_cli/sync_receipt_side_effect_key_missing/cli_goal_run
```

Current 70->75 component vector remains fully red in the global live DB:

```text
core=FAIL
idempotency=FAIL
mission=FAIL
artifact=FAIL
active_head=FAIL
```

Fresh isolated long-timeout rerun:

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer runtime-lifecycle-long-timeout \
  --db /private/tmp/runtime-lifecycle-long-timeout-proof-rerun-20260614T1050Z/state/runtime.db \
  --ledger-dir /private/tmp/runtime-lifecycle-long-timeout-proof-rerun-20260614T1050Z/ledgers \
  --mission-id runtime-spine-long-timeout-proof-rerun \
  --run-id run-long-timeout-proof-rerun \
  --task-id task-long-timeout-proof-rerun \
  --claim-id claim-long-timeout-proof-rerun \
  --trace-id trace-long-timeout-proof-rerun \
  --correlation-id corr-long-timeout-proof-rerun \
  --session-id sess-long-timeout-proof-rerun
exit 0
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py \
  --db /private/tmp/runtime-lifecycle-long-timeout-proof-rerun-20260614T1050Z/state/runtime.db \
  --run-id run-long-timeout-proof-rerun \
  --strict
exit 0
Runtime receipts: 16
Major task receipts: 2
Major receipt idempotency join: 100.0%
Latest major mission payload: 100.0%
Latest major artifact payload: 100.0%
Active head side_effect_key clean: PASS
70->75 score gate: PASS
Latest provider/model payload classes: missing=1, pending_execution=1
Latest terminal provider/model payload classes: missing=1
Production-readiness blockers:
  - latest major task receipts do not all carry provider/model payloads
  - latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata
```

Score consequence:

- Keep runtime spine at 70/100.
- The scoped proof verifies long-timeout field coverage, idempotency, mission,
  no-artifact truth, and active-head cleanliness in an isolated DB.
- The global live DB still blocks 70->75, led by installed `ds-goal` default
  target rows at the active head plus historical orchestrator field debt.
- `long_timeout` remains provider/model-unknown unless actual served route
  truth is recorded.

## Latest Checkpoint - Long Timeout Fresh Field Proof

- `runtime_lifecycle_receipt_probe.py` now supports
  `--producer runtime-lifecycle-long-timeout` for isolated long-timeout
  receipt proofs.
- Fresh temp proof `run-long-timeout-proof` in
  `/private/tmp/runtime-lifecycle-long-timeout-proof/state/runtime.db` proves
  the long-timeout field gate for a scoped run: 16/16 runtime receipt fields,
  2/2 major idempotency joins, 2/2 mission payloads, 2/2 artifact-or-explicit
  no-artifact payloads, and clean 5/15/60 minute active-head windows.
- The proof intentionally leaves provider/model unaccounted because
  `long_timeout` can occur after worker/provider execution has started. The
  scoped strict report therefore passes the 70->75 field gate but still prints
  provider/model production-readiness blockers.
- This gives the `long_timeout_proof` action bucket fresh executable evidence
  without mutating the live DB, restarting services, editing the installed
  `ds-goal` wrapper, or raising the global score.

Fresh scoped verifier:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --db /private/tmp/runtime-lifecycle-long-timeout-proof/state/runtime.db \
  --run-id run-long-timeout-proof \
  --strict
exit 0
70->75 score gate: PASS
Production-readiness blockers:
  - latest major task receipts do not all carry provider/model payloads
  - latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata
```

## Gate Result

- 70 to 75: not passed.
- Fresh measurement now exists in
  `scripts/governance/runtime_receipt_coverage_report.py`.
- Future task-claim and delegation-run RuntimeReceipts now carry side-effect
  keys plus matching `idempotency_records`, mission payload hints, and
  artifact payload hints when available.
- The fresh writer fixture, a bounded live RuntimeLifecycle probe, and a
  bounded live RuntimeStateStore sync-producer probe pass the scoped coverage
  report.
- Bounded live orchestrator spine-dispatch probes now also pass scoped
  coverage, including persisted `delegation_runs.receipt_json` for the
  `DHARMA_SPINE_DISPATCH=1` `_execute_task` path and mission-bearing
  `artifact_written` receipts.
- A bounded live RuntimeLifecycle dispatch-dropoff probe now passes scoped
  coverage for the no-artifact failure path that previously appeared at the
  top of the live DB without side-effect keys.
- The live DB still does not pass the global 70 to 75 gate because historical
  and test-contaminated receipts remain missing side-effect/idempotency joins
  and mission/artifact payloads.
- The strict report now prints receipt-type side-effect gaps, latest missing
  side-effect samples, major-task type gaps, and top offender groups so the
  next hardening target is machine-readable.
- Pytest runtime state is now isolated: `tests/conftest.py` redirects
  `DHARMA_RUNTIME_DB`, `DGC_LEDGER_DIR`, and
  `runtime_state.DEFAULT_RUNTIME_DB` to per-test temp paths. Rerunning the
  `t-ready` Orchestrator test no longer changes the live runtime DB receipt
  count or latest timestamp.
- The last source-level test hygiene offender is also closed:
  `tests/test_full_loop.py` now passes an explicit temp runtime DB, and
  `scripts/governance/check_test_hygiene.py` no longer has a stale file-level
  known-offender allowance for that path.
- The Rule 3 scanner now parses tests with `ast`, so future default-state
  variants such as `RuntimeStateStore(None)`, `RuntimeStateStore(db_path=None)`,
  or keyword-only calls that omit `db_path` fail the gate too.
- `live_ops_census` now projects this same active-head failure into the live
  daemon surface. A fresh census write shows `substrate.dharma_daemon`
  `proof_gaps=daemon_dispatch_runtime_unproven,daemon_process_source_stale,daemon_runtime_receipts_active_head_dirty`
  and carries the 5/15/60 minute DB-head windows in
  `raw.runtime_receipt_active_head`.
- The control-surface live-ops adapter now carries those same DB-head numbers
  as structured `db_probe` evidence, so dashboard/API rows can show the active
  receipt-head failure directly instead of only exposing the proof-gap code.
- `spine_dispatch_mode_report.py --strict` also prints the compact
  `runtime_receipt_active_head` summary under live census proof gaps, so the
  dispatch-mode gate output itself carries the active receipt-head blocker.

## Fresh-Since Receipt Scope

`runtime_receipt_coverage_report.py` now supports `--since-created-at`. The
scope filters `runtime_receipts` by `created_at >= <timestamp>` and scopes
`delegation_runs` metrics to the run IDs present in that filtered receipt set.
This gives the hardening campaign a non-mutating way to separate fresh
post-boundary behavior from historical debt without hiding the global DB
failure.

Before writing a new proof run, the post-isolation freshness scope was empty:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --since-created-at 2026-06-13T20:38:24+00:00 --strict
Runtime receipts:                  0
Major task receipts:               0
70->75 score gate:                 FAIL
Blockers:
  - no major task receipts found for selected scope
```

A bounded fresh sync-store probe passes by `run_id`:

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer runtime-state-sync --allow-live \
  --run-id run_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --task-id task_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --claim-id claim_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --trace-id trace_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --correlation-id corr_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --session-id sess_runtime_state_sync_since_probe_live_20260613T210320Z_codex \
  --mission-id runtime-spine-hardening-since-scope-2026-06-14
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py \
  --run-id run_runtime_state_sync_since_probe_live_20260613T210320Z_codex --strict
Runtime receipts:                  16
Major task receipts:               2
Major receipt idempotency join:     100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload:       100.0%
Latest major artifact payload:      100.0%
70->75 score gate:                 PASS
```

The standing daemon still fails the same freshness window because it continues
to emit dispatch-dropoff rows with blank `side_effect_key`:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --since-created-at 2026-06-13T21:03:20+00:00 --strict
Runtime receipts:                  184
Delegation receipt_json fill:       0.0%
Major task receipts:               86
Major receipt idempotency join:     2.33%
Major receipt artifact record join: 2.33%
Latest major mission payload:       2.33%
Latest major artifact payload:      2.33%
70->75 score gate:                 FAIL

Runtime receipt field coverage:
  side_effect_key        16/184       8.7%

Latest side_effect_key gap sample:
  2026-06-13T21:04:54.327678+00:00 delegation_run status=failed agent=a1 task=t-ready run=run_1ed9dd2b0b0747ef
  2026-06-13T21:04:54.314612+00:00 task_claim status=failed agent=a1 task=t-ready run=run_1ed9dd2b0b0747ef

Major task blocker breakdown:
  delegation_run   total=86    idempotency_gap=84    artifact_gap=84
```

This is active daemon/default debt. It is no longer accurate to describe the
latest missing `side_effect_key` rows as only pre-isolation pytest
contamination. Pytest isolation is still correct and verified, but the running
daemon also needs a controlled restart/proof before the 70->75 gate can move.

## Orchestrator Dispatch-Dropoff Source Hardening

The source path that produced the fresh daemon dispatch-dropoff debt is now
fail-closed for the next daemon process:

- `Orchestrator._prepare_claim()` stamps `trace_id`, `correlation_id`,
  `runtime_run_id`, and `idempotency_key` before runtime lifecycle writes.
- All orchestrator `record_task_claim()` and `record_delegation_run()` calls
  now pass `require_identity=True`.
- `test_dispatch_dropoff_requeues_once_when_runner_missing` now queries the
  isolated runtime DB and proves dispatch-dropoff `task_claim` and
  `delegation_run` receipts have non-empty `side_effect_key` values plus
  matching `idempotency_records`.

Verifier:

```text
pytest -q tests/test_orchestrator.py::test_dispatch_dropoff_requeues_once_when_runner_missing --tb=short
1 passed

pytest -q tests/test_orchestrator.py --tb=short
35 passed, 1 warning

pytest -q tests/test_orchestrator_spine_dispatch.py tests/test_runtime_receipt_coverage_report.py --tb=short
11 passed
```

This hardens the code that the daemon should run after restart. It does not
prove the already-running daemon, which is still serving old code and still
keeps the global 70->75 receipt gate red.

## Live Process Source Freshness

`live_ops_census` now reconciles process identity from both command matching
and `lsof` listener ownership, reads Darwin process starts through `libproc`
when the Python subprocess `ps` probe is blocked, then compares starts to
governing source files. The latest written census proves both daemon and
dashboard are source-stale, and also marks stopped P0 desired-live surfaces as
proof gaps instead of bound surfaces:

```text
substrate.dharma_daemon
  proof_gaps: daemon_dispatch_runtime_unproven, daemon_process_source_stale, daemon_runtime_receipts_active_head_dirty
  pids: 93875
  process_source_state: source_changed_after_process_start
  process_start: 2026-06-13T13:55:10Z
  newest runtime source: dharma_swarm/orchestrator.py 2026-06-13T21:10:58Z

dashboard.local
  proof_gaps: dashboard_control_surface_rows_slow, dashboard_control_surface_source_stale
  pid: 70585
  process_source_state: source_changed_after_process_start
  process_start: 2026-06-13T16:58:24Z
  newest projector source: dashboard/src/lib/controlSurfaceRuntimeEvidence.ts 2026-06-13T23:40:08Z

transport.a2a_bridge
  proof_gaps: a2a_inbox_bridge_stopped
  status: stopped
  next_action: start governed inbox delivery bridge if live A2A delivery is required

substrate.dharma_cron
  proof_gaps: substrate_dharma_cron_stopped
  status: stopped

tmux.cockpit
  proof_gaps: tmux_cockpit_stopped
  status: stopped

mission.forge_reality_arena
  proof_gaps: mission_forge_reality_arena_stopped
  status: stopped

remote.agni
  proof_gaps: remote_agni_stale
  status: stale
```

This converts live-port ambiguity into machine-readable live debt: the code and
tests are hardened, listener owners are known, and the process age/source-age
comparison is explicit. No production-readiness score should increase until
controlled restarts are followed by daemon/default receipt coverage and
dashboard/API projection proof.

## Fresh Live DB Measurement

```text
python3 scripts/governance/runtime_receipt_coverage_report.py
Runtime receipts:                  6703
Delegation receipt_json fill:       11.04%
Major task receipts:               3033
Major receipt idempotency join:     0.1%
Major receipt artifact record join: 30.2%
Latest major mission payload:       0.0%
Latest major artifact payload:      0.0%
70->75 score gate:                 FAIL

Runtime receipt field coverage:
  run_id               6703/6703    100.0%
  task_id              6703/6703    100.0%
  trace_id             6703/6703    100.0%
  correlation_id       6703/6703    100.0%
  agent_id             6703/6703    100.0%
  idempotency_key      6703/6703    100.0%
  side_effect_key       663/6703     9.89%
```

Latest live DB measurement:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py
Runtime receipts:                  7769
Delegation receipt_json fill:       10.51%
Major task receipts:               3523
Major receipt idempotency join:     0.48%
Major receipt artifact record join: 26.28%
Latest major mission payload:       0.0%
Latest major artifact payload:      0.0%
Latest major provider/model:        0.0%
Active head side_effect_key clean: FAIL
70->75 score gate:                 FAIL

Runtime receipt field coverage:
  side_effect_key       777/7769    10.0%

Recent side_effect_key gap windows:
  last_5m  missing=56/56 (100.0%)
  last_15m missing=56/56 (100.0%)
  last_60m missing=224/224 (100.0%)

Production-readiness blockers:
  - latest major task receipts do not all carry provider/model payloads

The same production-readiness blocker is now preserved in live ops raw daemon
coverage and rendered by the dispatch gate:

```text
python3 scripts/governance/spine_dispatch_mode_report.py --strict
runtime_receipt_coverage: available=true; latest=0/250; provider=0/250; model=0/250; percent=0.0; complete=false; major_total=3523; readiness_blockers=latest major task receipts do not all carry provider/model payloads
```

Strict gate:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1; expected because 70->75 is still blocked
```

Latest global coverage measurement:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py
Runtime receipts:                  7769
Delegation receipt_json fill:       10.51%
Major task receipts:               3523
Major receipt idempotency join:     0.48%
Major receipt artifact record join: 26.28%
Latest major mission payload:       0.0%
Latest major artifact payload:      0.0%
Active head side_effect_key clean: FAIL
70->75 score gate:                 FAIL

Runtime side_effect_key gaps by receipt type:
  delegation_run   missing=3506   total=3523
  task_claim       missing=3486   total=3498

Latest side_effect_key gap sample:
  2026-06-13T23:13:37.937601+00:00 delegation_run status=failed agent=a1 task=t-ready run=run_94d37b1293e74f6d
  2026-06-13T23:13:37.925638+00:00 task_claim status=failed agent=a1 task=t-ready run=run_94d37b1293e74f6d
  2026-06-13T23:13:37.895734+00:00 delegation_run status=claimed agent=a1 task=t-ready run=run_94d37b1293e74f6d
  2026-06-13T23:13:37.883202+00:00 task_claim status=claimed agent=a1 task=t-ready run=run_94d37b1293e74f6d

Latest side_effect_key gap diagnostics:
  2026-06-13T23:13:37.937601+00:00 delegation_run status=failed agent=a1 task=t-ready run=run_94d37b1293e74f6d source=orchestrator failure=dispatch_dropoff shape=fixture_shaped session=20260613T231336Z topology=fan_out db=/Users/dhyana/.dharma/state/runtime.db
    error=Dispatch accepted but worker unavailable (runner=False task=True)

Top side_effect_key gap producer groups:
  task_claim       source=orchestrator   failure=execution_error    topology=fan_out    shape=ordinary       missing=1683  latest=2026-06-12T13:52:35.504243+00:00  sample=8a80af72c2b14167/e420592414304bcf
  delegation_run   source=orchestrator   failure=execution_error    topology=fan_out    shape=ordinary       missing=1681  latest=2026-06-12T13:52:35.521860+00:00  sample=8a80af72c2b14167/e420592414304bcf
  delegation_run   source=orchestrator   failure=<none>             topology=fan_out    shape=ordinary       missing=997   latest=2026-06-13T17:14:12.359732+00:00  sample=frontier_ollama_qwen3_coder_480b/bcb4593aed214209
  delegation_run   source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=660   latest=2026-06-13T23:13:37.937601+00:00  sample=a1/t-ready

Recent side_effect_key gap windows:
  last_5m anchor=2026-06-13T23:13:37.937601+00:00 missing=56/56 (100.0%)
    delegation_run   source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=22    sample=a1/t-ready
    task_claim       source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=22    sample=a1/t-ready
  last_15m anchor=2026-06-13T23:13:37.937601+00:00 missing=56/56 (100.0%)
    delegation_run   source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=22    sample=a1/t-ready
    task_claim       source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=22    sample=a1/t-ready
  last_60m anchor=2026-06-13T23:13:37.937601+00:00 missing=224/224 (100.0%)
    delegation_run   source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=88    sample=a1/t-ready
    task_claim       source=orchestrator   failure=dispatch_dropoff   topology=fan_out    shape=fixture_shaped missing=88    sample=a1/t-ready

Major task blocker breakdown:
  delegation_run   total=3523  idempotency_gap=3506  artifact_gap=2597

exit 0 here because this command was run without `--strict` to print the full
diagnostic. `--strict` still exits 1, expected because the global live DB is
not saturated. The latest sample rows still use fixture-shaped agent/task IDs,
the aggregate producer view shows old `execution_error` groups dominate
historical debt, the diagnostic join names `source=orchestrator` /
`failure=dispatch_dropoff` as the fresh head producer, and
`active_head_side_effect_key_clean=false` because DB-head windows show the
active write pattern is still 100% blank-side-effect in the last 5, 15, and
60 minutes of receipt time. Daemon/default dispatch remains unproven until a
controlled restart/proof is performed.
```

The live-ops surface now carries the same receipt-head truth:

```text
python3 scripts/runtime/live_ops_census.py --write
/Users/dhyana/.dharma/ops/live_process_census.json

substrate.dharma_daemon
  status: live
  proof_state: partial
  proof_gaps:
    - daemon_dispatch_runtime_unproven
    - daemon_process_source_stale
    - daemon_runtime_receipts_active_head_dirty
  active_head_side_effect_key_clean: false
  DB-head windows:
    last_5m  missing=56/56
    last_15m missing=56/56
    last_60m missing=224/224
```

The control-surface projection now renders the same state as row evidence:

```text
live_ops.substrate.dharma_daemon
  evidence.kind: db_probe
  evidence.source: runtime_receipt_active_head clean=false; total=7769; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:56/56,15m:56/56,60m:224/224
```

The dispatch-mode report now prints it too:

```text
python3 scripts/governance/spine_dispatch_mode_report.py --strict
Live census proof gaps:
  substrate.dharma_daemon: status=live; pids=93875; source_state=source_changed_after_process_start; proof_gaps=daemon_dispatch_runtime_unproven,daemon_process_source_stale,daemon_runtime_receipts_active_head_dirty
    runtime_receipt_active_head: clean=false; total=7769; latest=2026-06-13T23:13:37.937601+00:00; windows=5m:56/56,15m:56/56,60m:224/224
  substrate.dharma_cron: status=stopped; pids=none; source_state=unknown; proof_gaps=substrate_dharma_cron_stopped
  transport.a2a_bridge: status=stopped; pids=none; source_state=unknown; proof_gaps=a2a_inbox_bridge_stopped
  dashboard.local: status=live; pids=70585; source_state=source_changed_after_process_start; proof_gaps=dashboard_control_surface_rows_slow,dashboard_control_surface_source_stale
  tmux.cockpit: status=stopped; pids=none; source_state=unknown; proof_gaps=tmux_cockpit_stopped
  mission.forge_reality_arena: status=stopped; pids=none; source_state=unknown; proof_gaps=mission_forge_reality_arena_stopped
  remote.agni: status=stale; pids=none; source_state=unknown; proof_gaps=remote_agni_stale
```

## Pytest Runtime DB Isolation

Before isolation, the latest missing side-effect rows used fixture-looking
task/agent ids such as `t-ready`, `t1`, `t2`, `a1`, and `a2`. These map to
`tests/test_orchestrator.py`, proving tests were contaminating
`~/.dharma/state/runtime.db`.

```text
python3 - <<'PY'
import sqlite3
from pathlib import Path
conn = sqlite3.connect(Path.home() / ".dharma/state/runtime.db")
print(conn.execute("SELECT COUNT(*), MAX(created_at) FROM runtime_receipts").fetchone())
PY
7137 2026-06-13T20:38:23.541333+00:00

pytest -q tests/test_orchestrator.py::test_route_next_skips_retry_backoff_tasks \
  tests/test_runtime_state_invariants.py::test_pytest_runtime_defaults_are_isolated_from_live_db --tb=short
2 passed

pytest -q tests/test_orchestrator.py tests/test_runtime_state_invariants.py --tb=short
39 passed, 1 warning

python3 - <<'PY'
import sqlite3
from pathlib import Path
conn = sqlite3.connect(Path.home() / ".dharma/state/runtime.db")
print(conn.execute("SELECT COUNT(*), MAX(created_at) FROM runtime_receipts").fetchone())
PY
7137 2026-06-13T20:38:23.541333+00:00
```

## Fresh Scoped Live Probe

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py --allow-live \
  --run-id run_runtime_spine_probe_live_20260613T173713Z \
  --task-id task_runtime_spine_probe_live_20260613T173713Z \
  --claim-id claim_runtime_spine_probe_live_20260613T173713Z \
  --trace-id trace_runtime_spine_probe_live_20260613T173713Z \
  --correlation-id corr_runtime_spine_probe_live_20260613T173713Z \
  --session-id sess_runtime_spine_probe_live_20260613T173713Z
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py \
  --run-id run_runtime_spine_probe_live_20260613T173713Z --strict
Runtime receipts:                  18
Major task receipts:               2
Major receipt idempotency join:     100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload:       100.0%
Latest major artifact payload:      100.0%
70->75 score gate:                 PASS
```

This proves the current `RuntimeLifecycle` writer can emit coherent
receipt/idempotency/artifact evidence into the live DB for one bounded run. It
does not prove daemon/default dispatch, A2A ingress, or agent-runner saturation.

## Fresh Scoped Sync-Store Probe

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer runtime-state-sync --allow-live \
  --run-id run_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --task-id task_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --claim-id claim_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --trace-id trace_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --correlation-id corr_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --session-id sess_runtime_state_sync_probe_live_20260613T181000Z_codex \
  --mission-id runtime-spine-hardening-sync-store-2026-06-14
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py --strict \
  --run-id run_runtime_state_sync_probe_live_20260613T181000Z_codex
Runtime receipts:                  16
Major task receipts:               2
Major receipt idempotency join:     100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload:       100.0%
Latest major artifact payload:      100.0%
70->75 score gate:                 PASS
```

This proves the sync `RuntimeStateStore.create_task_claim_sync()` and
`create_delegation_run_sync()` producer path now emits coherent
receipt/idempotency/artifact evidence into the live DB for one bounded run.

## Fresh Scoped Orchestrator Spine Probe

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer orchestrator-spine --allow-live \
  --run-id run_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --task-id task_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --claim-id claim_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --trace-id trace_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --correlation-id corr_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --session-id sess_orchestrator_spine_probe_live_20260613T191500Z_codex \
  --mission-id runtime-spine-hardening-orchestrator-spine-2026-06-14
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py --strict \
  --run-id run_orchestrator_spine_probe_live_20260613T191500Z_codex
Runtime receipts:                  16
Delegation receipt_json fill:       100.0%
Major task receipts:               2
Major receipt idempotency join:     100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload:       100.0%
Latest major artifact payload:      100.0%
70->75 score gate:                 PASS

sqlite3 /Users/dhyana/.dharma/state/runtime.db \
  "SELECT run_id, status, length(receipt_json), current_artifact_id FROM delegation_runs WHERE run_id='run_orchestrator_spine_probe_live_20260613T191500Z_codex';"
run_orchestrator_spine_probe_live_20260613T191500Z_codex|completed|880|artifact_run_orchestrator_spine_probe_live_20260613T191500Z_codex

sqlite3 /Users/dhyana/.dharma/state/runtime.db \
  "SELECT receipt_type, json_extract(payload_json,'$.mission_id'), json_extract(payload_json,'$.artifact_refs[0]') FROM runtime_receipts WHERE run_id='run_orchestrator_spine_probe_live_20260613T191500Z_codex' AND receipt_type IN ('artifact','artifact_written') ORDER BY receipt_type;"
artifact|runtime-spine-hardening-orchestrator-spine-2026-06-14|artifact_records:artifact_run_orchestrator_spine_probe_live_20260613T191500Z_codex
artifact|runtime-spine-hardening-orchestrator-spine-2026-06-14|artifact_records:artifact_task_result_task_orchestrator_spine_probe_live_20260613T191500Z_codex
artifact_written|runtime-spine-hardening-orchestrator-spine-2026-06-14|artifact_records:artifact_run_orchestrator_spine_probe_live_20260613T191500Z_codex
artifact_written|runtime-spine-hardening-orchestrator-spine-2026-06-14|artifact_records:artifact_task_result_task_orchestrator_spine_probe_live_20260613T191500Z_codex
```

This proves the flagged orchestrator `_execute_task` path can produce a scoped
EvidenceReceipt, persist it into `delegation_runs.receipt_json`, and emit
coherent runtime receipt/idempotency/artifact evidence when
`DHARMA_SPINE_DISPATCH=1`. The LaunchAgent spec now declares that flag for the
next daemon start, but this does not prove the already-running daemon/default
path until it is safely restarted or self-reports a fresh daemon/default
EvidenceReceipt with scoped receipt coverage.

## Fresh Scoped Dispatch-Dropoff Probe

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer runtime-lifecycle-dropoff --allow-live \
  --run-id run_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --task-id task_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --claim-id claim_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --trace-id trace_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --correlation-id corr_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --session-id sess_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex \
  --mission-id runtime-spine-hardening-2026-06-14
70->75 gate: PASS

python3 scripts/governance/runtime_receipt_coverage_report.py --strict \
  --run-id run_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex
Runtime receipts:                  16
Major task receipts:               2
Major receipt idempotency join:     100.0%
Major receipt artifact record join: 0.0%
Latest major mission payload:       100.0%
Latest major artifact payload:      100.0%
70->75 score gate:                 PASS
```

The scoped DB rows for that run contain:

```text
delegation_run claimed delegation_run:run_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex:claimed runtime-spine-hardening-2026-06-14 [] delegation_run has no current_artifact_id
delegation_run failed delegation_run:run_runtime_lifecycle_dropoff_probe_live_20260613T202000Z_codex:failed runtime-spine-hardening-2026-06-14 [] delegation_run has no current_artifact_id
idempotency_records 4
```

This specifically protects the recent dispatch-dropoff/no-artifact failure
shape: future receipts must carry a deterministic side-effect key, matching
idempotency records, mission identity, and an explicit no-artifact reason. It
does not saturate historical rows and does not prove daemon/default dispatch.

## Code Hardening

- `dharma_swarm/runtime_lifecycle.py` now opens idempotency before task-claim
  and delegation-run row/receipt writes.
- `dharma_swarm/runtime_lifecycle.py` now completes the idempotency record with
  the deterministic RuntimeReceipt id after the row/receipt write succeeds.
- `dharma_swarm/runtime_state.py` now applies the same idempotency/receipt
  saturation pattern to identity-backed sync task-claim and delegation-run
  writers; legacy no-identity sync calls remain explicitly receiptless.
- `dharma_swarm/runtime_lifecycle.py` artifact and artifact-written receipts
  now carry `mission_id` and `artifact_refs`, so fresh runtime-truth projections
  no longer drop mission identity on artifact receipts.
- `scripts/runtime/runtime_lifecycle_receipt_probe.py` now has
  `--producer runtime-state-sync` and `--producer orchestrator-spine` to prove
  sync-store and flagged orchestrator dispatch paths independently of the
  generic `RuntimeLifecycle` fixture.
- `scripts/runtime/runtime_lifecycle_receipt_probe.py` now has
  `--producer runtime-lifecycle-dropoff` to prove dispatch-dropoff/no-artifact
  receipts independently of the artifact-bearing happy path.
- Task-claim receipts use
  `side_effect_key=task_claim:<claim_id>:<status>`.
- Delegation-run receipts use
  `side_effect_key=delegation_run:<run_id>:<status>`.
- Delegation-run receipt payloads include `mission_id`, `artifact_refs`, and
  `no_artifact_refs_reason` fields. This does not create a second receipt
  hierarchy.

## Verification

```text
python3 -m py_compile dharma_swarm/runtime_state.py \
  scripts/runtime/runtime_lifecycle_receipt_probe.py \
  scripts/governance/runtime_receipt_coverage_report.py
exit 0

pytest -q tests/test_runtime_receipt_coverage_report.py tests/test_runtime_lifecycle_receipt_probe.py tests/test_runtime_lifecycle.py --tb=short
12 passed, 1 warning

pytest -q tests/test_runtime_lifecycle_receipt_probe.py \
  tests/test_runtime_state_invariants.py::test_sync_helpers_record_identity_trace_and_receipts \
  tests/test_runtime_state_invariants.py::test_sync_legacy_helpers_fail_closed_without_identity_unless_flagged \
  tests/test_runtime_receipt_coverage_report.py --tb=short
10 passed

The lifecycle fixture asserts:

- completed task-claim receipt joins to a completed `idempotency_records` row;
- completed delegation-run receipt joins to a completed `idempotency_records`
  row;
- the same fixture passes `runtime_receipt_coverage_report.build_report()`.
- the probe script writes a fresh scoped run that passes
  `runtime_receipt_coverage_report.build_report(run_id=...)`.

pytest -q tests/test_runtime_lifecycle.py tests/test_runtime_receipt_coverage_report.py tests/test_runtime_truth_projection_fields.py tests/test_operator_core_contracts.py tests/test_spine_persistence_invariant.py tests/test_spine_dispatch_mode_report.py --tb=short
24 passed

pytest -q tests/test_runtime_lifecycle.py tests/test_runtime_receipt_coverage_report.py tests/test_runtime_truth_projection_fields.py tests/test_operator_core_contracts.py tests/test_spine_persistence_invariant.py tests/test_spine_dispatch_mode_report.py tests/test_runtime_state.py tests/test_runtime_state_recovery.py --tb=short
34 passed

pytest -q tests/test_runtime_lifecycle.py tests/test_runtime_receipt_coverage_report.py tests/test_spine_dispatch_mode_report.py tests/test_spine_adoption_dispatch.py tests/test_orchestrator_spine_dispatch.py tests/test_spine_persistence_invariant.py --tb=short
31 passed

Context+ static analysis: dharma_swarm/runtime_lifecycle.py
No issues found

python3 scripts/governance/check_track_status.py
exit 0; runtime-truth-spine-adoption-2026-06 all completion criteria pass; operator lifecycle review still required

python3 scripts/governance/render_active_track_includes.py --check
exit 0

make onboard
exit 0; active portfolio renders current=70/100

make hygiene-check
exit 0; Hygiene integrity OK

make test-hygiene
exit 0; No findings.

make uplift-guards
exit 0

make module-budget
exit 0; No target Python files changed. OK.

make nats-substrate-contract
54 passed

git diff --check
exit 0
```

## Still Blocked

- Live `runtime.db` still carries historical receipts without side-effect keys,
  and the standing daemon is actively adding more stale-shape
  dispatch-dropoff receipts while it runs old code.
- Latest global coverage measurement in this slice:
  7769 runtime receipts, 3523 major task receipts, 777/7769
  `side_effect_key` filled, 0.48% major idempotency join, 26.28% major
  artifact-record join, 0.0% latest major mission/artifact payload coverage,
  dominant historical `source=orchestrator` / `failure=execution_error`
  producer groups, and fresh `source=orchestrator` /
  `failure=dispatch_dropoff` fixture-shaped `a1/t-ready` gaps at
  `2026-06-13T23:13:37Z`.
- DB-head recency windows show active debt, not only historical debt: last
  5/15/60 minutes of receipt time have 56/56, 56/56, and 224/224 receipts
  missing `side_effect_key`, led by orchestrator dispatch-dropoff groups;
  `active_head_side_effect_key_clean=false`.
- A fresh-since scope at `2026-06-13T21:03:20+00:00` failed with 184 runtime
  receipts, 86 major task receipts, only 16/184 `side_effect_key` filled, and
  2.33% major idempotency/artifact joins.
- Scoped producer probes pass by `run_id`; the failure is daemon/default
  runtime saturation, not the isolated proof writers.
- The next score movement requires a controlled daemon restart/proof that
  stops fresh stale-shape receipts, returns a non-secret runtime-dispatch
  self-report, and writes enriched daemon/default receipts through the real
  runtime path.

## Scoped Proof: Orchestrator Fan-Out Execution Error

Status: score remains **70/100**. The global live DB still fails strict receipt
coverage, but the current orchestrator-spine `fan_out` execution-error producer
can now be proven clean in an isolated run.

Proof command:

```text
env HOME=/private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/home python3 scripts/runtime/runtime_lifecycle_receipt_probe.py --producer orchestrator-spine --topology fan-out --runner-error "synthetic execution error for receipt proof" --db /private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/state/runtime.db --ledger-dir /private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/ledgers --artifact-dir /private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/artifacts --mission-id runtime-spine-fanout-error-proof --run-id run-orchestrator-fanout-error-proof --task-id task-orchestrator-fanout-error-proof --claim-id claim-orchestrator-fanout-error-proof --trace-id trace-orchestrator-fanout-error-proof --correlation-id corr-orchestrator-fanout-error-proof --session-id sess-orchestrator-fanout-error-proof
exit 0
70->75 gate: PASS
```

Scoped strict verifier:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --db /private/tmp/orchestrator-fanout-error-proof-20260614T1112Z/state/runtime.db --run-id run-orchestrator-fanout-error-proof --strict
exit 0

Runtime receipts: 14
Delegation receipt_json fill: 100.0%
Major task receipts: 2
Major receipt idempotency join: 100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload: 100.0%
Latest major artifact payload: 100.0%
Active head side_effect_key clean: PASS
70->75 score gate: PASS
```

What this proves:

- failed `task_claim` receipts use
  `side_effect_key=task_claim:<claim_id>:failed`;
- failed `delegation_run` receipts use
  `side_effect_key=delegation_run:<run_id>:failed`;
- the failed delegation-run payload carries `mission_id`, `artifact_refs`, and
  `failure_code=execution_error`;
- the delegation-run metadata keeps `topology=fan_out`;
- the isolated run joins idempotency and artifact records.

What this does not prove:

- it does not repair or quarantine historical `orchestrator_error=5037` debt;
- it does not prove provider/model production readiness;
- it does not clean active-head ds-goal wrapper rows;
- it does not justify raising the active-track score above 70.

## Policy Surface: Fixture Quarantine Candidate

Status: score remains **70/100**. Fixture-shaped debt is now reported as a
machine-readable candidate policy, but it is not excluded from the score gate.

Fresh strict verifier:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1

Runtime receipts: 8027
Major task receipts: 3567
side_effect_key coverage: 1001/8027 = 12.47%
Major receipt idempotency join: 44/3567 = 1.23%
Major receipt artifact record join: 27.08%
Active head side_effect_key clean: FAIL
70->75 score gate: FAIL
```

Fixture policy output:

```text
Fixture quarantine policy:
  status=candidate_not_applied candidate_missing=2148 groups=6 active_head=0 recent=2148 older=0 eligible_after_operator_decision=true applies_to_score_gate=false
  test_isolation_enforced=true path=tests/conftest.py
  blockers=fixture-shaped debt is only a candidate and is not excluded | explicit operator quarantine acceptance is not recorded
```

What this proves:

- fixture-shaped rows are visible as a distinct candidate boundary;
- current test runtime DB isolation evidence is machine-checked from
  `tests/conftest.py`;
- the report will not silently subtract fixture-shaped rows from the 70->75
  score gate;
- operator acceptance and a documented production boundary are still required
  before any fixture quarantine can become score-relevant.

Verification:

```text
python3 -m py_compile scripts/governance/runtime_receipt_coverage_report.py tests/test_runtime_receipt_coverage_report.py
exit 0

pytest -q tests/test_runtime_receipt_coverage_report.py --tb=short
22 passed
```

## Provider/Model Proof Surface: Orchestrator Fan-Out Actual Served

Status: score remains **70/100**. The orchestrator fan-out success proof now
has an explicit served-provider terminal receipt proof, but the global receipt
gate remains red.

Fresh scoped CLI proof:

```text
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py \
  --producer orchestrator-spine \
  --topology fan-out \
  --actual-served-provider openrouter \
  --actual-served-model qwen3-coder-live \
  --provider-model-truth-source runtime_provider.actual_served \
  --db /private/tmp/orchestrator-fanout-served-provider-proof-20260614T1133Z/state/runtime.db \
  --ledger-dir /private/tmp/orchestrator-fanout-served-provider-proof-20260614T1133Z/ledgers \
  --artifact-dir /private/tmp/orchestrator-fanout-served-provider-proof-20260614T1133Z/artifacts \
  --mission-id runtime-spine-fanout-served-provider-proof \
  --run-id run-orchestrator-fanout-served-provider-proof \
  --task-id task-orchestrator-fanout-served-provider-proof \
  --claim-id claim-orchestrator-fanout-served-provider-proof \
  --trace-id trace-orchestrator-fanout-served-provider-proof \
  --correlation-id corr-orchestrator-fanout-served-provider-proof \
  --session-id sess-orchestrator-fanout-served-provider-proof
exit 0
70->75 gate: PASS
Terminal provider/model: 100.0% proof=100.0% accounted=100.0% terminal=1
Provider/model pending execution: 1
```

Scoped strict verifier:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --db /private/tmp/orchestrator-fanout-served-provider-proof-20260614T1133Z/state/runtime.db \
  --run-id run-orchestrator-fanout-served-provider-proof \
  --strict
exit 0

Runtime receipts: 16
Major task receipts: 2
Major receipt idempotency join: 100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload: 100.0%
Latest major artifact payload: 100.0%
Latest major provider/model: 50.0%
Latest major provider/model proof: 50.0%
Latest major provider/model accounted: 50.0%
Latest terminal provider/model: 100.0% (1 terminal, 1 pending)
Latest terminal provider/model proof: 100.0%
Latest terminal provider/model accounted: 100.0%
Active head side_effect_key clean: PASS
70->75 score gate: PASS
```

What this proves:

- the `fan_out` success terminal delegation receipt can preserve
  `actual_served_provider=openrouter`;
- the same terminal receipt can preserve
  `actual_served_model=qwen3-coder-live`;
- provenance is marked as `runtime_provider.actual_served`, not selected config
  or probe-selected metadata;
- the CLI proof output now makes terminal provider/model truth and remaining
  production blockers visible without requiring JSON inspection.

What this does not prove:

- it does not make the pending/running major receipt carry served provider/model
  truth before execution has completed;
- it does not repair or quarantine historical `fanout_success=2052` debt;
- it does not clean active-head `ds_goal_cli` rows;
- it does not fix the installed `ds-goal` wrapper target mismatch;
- it does not justify raising the active-track score above 70.

Verification:

```text
python3 -m py_compile scripts/runtime/runtime_lifecycle_receipt_probe.py tests/test_runtime_lifecycle_receipt_probe.py
exit 0

pytest -q tests/test_runtime_lifecycle_receipt_probe.py --tb=short
15 passed, 3 warnings

python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1
70->75 score gate: FAIL
```

## Checkpoint: Field-Gap Fresh-Proof Status In Action Queue

Date: 2026-06-14 20:41 JST

The receipt coverage report now distinguishes two facts that were previously
too easy to blur:

1. Fresh scoped proof may already exist for a producer path.
2. The global live DB can still fail because historical debt, default-wrapper
   debt, or missing quarantine decisions remain unresolved.

Implementation:

- `runtime_receipt_coverage_report.py` attaches `fresh_proof` metadata to each
  major field-gap action queue row.
- The text renderer prints the status and remaining action for each row.
- The queue keeps the same missing counts and the same red 70->75 gate.

Fresh strict evidence:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1

70->75 score gate: FAIL
ds_goal_wrapper:40
orchestrator_error:5037
fanout_success:2052
fixture_quarantine:2148
dropoff_fresh_proof:318
claim_timeout_proof:32
long_timeout_proof:12

fresh_proof statuses:
  ds_goal_wrapper -> pin_mitigation_proof_recorded_default_still_broken
  orchestrator_error -> fresh_scoped_proof_recorded
  fanout_success -> fresh_scoped_proof_recorded
  fixture_quarantine -> candidate_policy_recorded_not_applied
  dropoff_fresh_proof -> fresh_scoped_proof_recorded
  claim_timeout_proof -> fresh_scoped_proof_recorded
  long_timeout_proof -> fresh_scoped_proof_recorded
```

Verification:

```text
python3 -m py_compile scripts/governance/runtime_receipt_coverage_report.py tests/test_runtime_receipt_coverage_report.py
exit 0

pytest -q tests/test_runtime_receipt_coverage_report.py --tb=short
exit 0
23 passed
```

Score consequence:

- no score movement;
- no historical debt hidden;
- no fixture candidate excluded from score;
- no wrapper/default target changed;
- no live service restarted;
- global strict coverage still blocks 75.

## Checkpoint: Field-Gap Proofs Projected To Operator Front Doors

Date: 2026-06-14 20:46 JST

The receipt coverage action queue's `fresh_proof` statuses are now visible in
the normal operator orientation surfaces:

```text
make onboard
make orient
python3 scripts/governance/spine_dispatch_mode_report.py --strict
```

All three now render the compact line:

```text
field_gap_proofs=ds_goal_wrapper:pin_proved_default_dirty|orchestrator_error:fresh|fanout_success:fresh|fixture_quarantine:policy_candidate|dropoff_fresh_proof:fresh|claim_timeout_proof:fresh|long_timeout_proof:fresh
```

This line is intentionally paired with the unchanged red gate:

```text
gate_70_75=core:fail|idempotency:fail|mission:fail|artifact:fail|active_head:fail
```

Verification:

```text
python3 scripts/runtime/live_ops_census.py --write
exit 0

pytest -q tests/test_spine_dispatch_mode_report.py::test_dispatch_report_formats_active_head_gap_producers tests/test_agent_onboard.py tests/test_orientation_graph.py tests/test_runtime_receipt_coverage_report.py --tb=short
exit 0
58 passed

python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1
70->75 score gate: FAIL
```

Score consequence:

- fresh proof labels are now visible to operators;
- historical repair/quarantine work is still unresolved;
- installed-wrapper convergence is still unresolved;
- global strict receipt coverage still fails;
- score remains 70/100.

## Checkpoint: ds-goal Wrapper Decision Packet In Receipt Gate

Date: 2026-06-14 21:05 JST

The strict receipt gate now carries the installed `ds-goal` wrapper convergence
decision rather than only naming the mismatch.

What changed:

- `ds_goal_wrapper_contract.py` builds a read-only
  `convergence_decision_packet`.
- `ds_goal_wrapper_receipt_probe.py --json` includes the packet with the
  pinned-clean/default-dirty proof.
- `live_ops_census.py` embeds the packet in the `cli.ds_goal` surface.
- `runtime_receipt_coverage_report.py --strict` prints:

```text
convergence_decision=operator_approval_required
operator_options=converge_installed_wrapper_default_to_audited_checkout|harden_current_default_target_checkout|retain_default_with_mandatory_pin_or_quarantine
forbidden_without_approval=edit_installed_wrapper|patch_default_target_checkout|start_repo_native_longrun_from_unpinned_ds_goal|declare_75_plus_from_pin_mitigation_only
```

Fresh proof:

```text
python3 scripts/runtime/ds_goal_wrapper_receipt_probe.py --expect-split-brain --json
exit 0
proof_root=/var/folders/2n/h27kz83n6dn90pzkb_8v3pm80000gn/T/ds-goal-wrapper-receipt-probe-20260614T120344Z
pinned run run_ds_goal_540de53136590fe62083899b: clean
default run run_ds_goal_5a0f0446a692675ff30b1d5a: dirty
```

Score consequence:

- no wrapper/default-target mutation;
- no sibling checkout patch;
- no historical repair/quarantine;
- no active-head cleanup;
- strict global gate still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Longrun Preflight In Receipt Gate

Date: 2026-06-14 21:20 JST

The receipt gate now sees the installed `ds-goal` longrun preflight state
instead of only the wrapper mismatch.

What changed:

- `scripts/runtime/ds_goal_longrun_preflight.py --json` is a read-only
  no-start gate.
- `live_ops_census.py` writes `cli.ds_goal.raw.longrun_preflight_gate`.
- `runtime_receipt_coverage_report.py --strict` prints:

```text
preflight=blocked_unpinned_default_target
```

Fresh proof:

```text
python3 scripts/runtime/ds_goal_longrun_preflight.py --json
exit 1
status=blocked_unpinned_default_target

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm python3 scripts/runtime/ds_goal_longrun_preflight.py --json
exit 0
status=pass_explicit_audited_checkout_pin
operator_convergence_required=true
score_effect=no_score_movement_preflight_only

python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1
70->75 score gate: FAIL
```

Score consequence:

- future operator workflows have a pre-start guard against unpinned ds-goal;
- existing active-head ds-goal debt is not repaired by this guard;
- the installed wrapper default still targets `/Users/dhyana/dharma_swarm_main`;
- strict global coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Workflow Command Guard

Date: 2026-06-14 21:33 JST

The repo now has a strict scanner for operational `ds-goal init/run/status`
commands that would otherwise rely on the installed wrapper default target.

Fresh proof:

```text
python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict
exit 0
command-shaped ds-goal entries=3
pinned=3
unsafe_unpinned=0
```

Score consequence:

- Palantir Pilot's longrun handoff verifier is pinned to the audited checkout.
- The runtime spine hardening goal's Phase 4a safe checks include the scanner.
- This reduces future unpinned workflow drift but does not repair historical
  active-head ds-goal rows.
- strict global coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Workflow Guard In Governance Bundle

Date: 2026-06-14 21:40 JST

`make ds-goal-longrun-preflight-check` now runs
`scripts/governance/ds_goal_longrun_preflight_report.py --strict`, and
`governance-all` depends on that target. Because `agent-build-closeout`
delegates to `governance-all`, repo-owned unpinned `ds-goal init/run/status`
workflow commands now fail the normal closeout bundle.

Fresh proof:

```text
make ds-goal-longrun-preflight-check
exit 0
command-shaped ds-goal entries=3
pinned=3
unsafe_unpinned=0

pytest -q tests/test_ds_goal_longrun_preflight_report.py --tb=short
exit 0
3 passed
```

Score consequence:

- the scanner is now enforced through the normal governance bundle;
- future repo-owned unpinned workflow examples should fail closeout;
- the installed wrapper default still targets `/Users/dhyana/dharma_swarm_main`;
- existing active-head ds-goal receipt debt is not repaired;
- strict global coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Preflight Payloads Counted In Major Receipts

Date: 2026-06-14 22:31 JST

The receipt coverage report now counts latest major `task_claim` /
`delegation_run` receipts that carry the `ds_goal_longrun_preflight` payload.
This turns the installed-wrapper preflight decision into receipt-local
evidence for future ds-goal/autonomy-spine runs, while keeping the score
unchanged.

What changed:

- `autonomy_spine.py` computes the preflight verdict at ds-goal dispatch time.
- `runtime_state.py` passes `ds_goal_longrun_preflight`,
  `ds_goal_longrun_preflight_status`,
  `ds_goal_longrun_preflight_passed`, and
  `ds_goal_default_target_repo` into major runtime receipt payloads.
- `runtime_receipt_coverage_report.py` reports
  `latest_with_ds_goal_preflight_payload`,
  `latest_ds_goal_preflight_status_breakdown`, and sample receipt IDs with
  repo-pin source and score effect.

Fresh scoped proof:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --db /private/tmp/ds-goal-preflight-receipt-proof-20260614T2220JST/state/.runtime/runtime.db --strict
exit 0
Runtime receipts: 13
Major task receipts: 2
Major receipt idempotency join: 100.0%
Major receipt artifact record join: 100.0%
Latest major mission payload: 100.0%
Latest major artifact payload: 100.0%
Active head side_effect_key clean: PASS
70->75 score gate: PASS
Latest ds-goal preflight receipt payloads: 2/2
pass_explicit_audited_checkout_pin 2
sample delegation_run/rr_run_ds_goal_1fbedb025b471ac597eb127c_completed_run status=pass_explicit_audited_checkout_pin passed=true default=/Users/dhyana/dharma_swarm_main pin=DHARMA_SWARM_REPO score_effect=no_score_movement_preflight_only
```

Score consequence:

- this is scoped receipt-context evidence for a pinned audited-checkout run;
- it does not edit `/Users/dhyana/.dharma/bin/ds-goal`;
- it does not patch `/Users/dhyana/dharma_swarm_main`;
- it does not clean global active-head ds-goal rows;
- it does not repair or quarantine historical orchestrator receipt debt;
- global strict coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Preflight Blocks Unsafe Receipt Creation

Date: 2026-06-14 22:45 JST

The ds-goal/autonomy-spine run path now fails closed before creating runtime
receipt or idempotency state when the longrun preflight blocks the invocation.
This reduces future receipt-head contamination risk from this checkout, while
leaving the global live DB score gate unchanged.

Fresh blocked proof:

```text
env -u DHARMA_SWARM_REPO python3 scripts/runtime/autonomy_spine.py run --state-root /private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state --kernel-store /private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/kernel --mission-id ds-goal-preflight-block-proof --max-wakes 1 --json
exit 2
status=preflight_blocked
preflight=blocked_unpinned_default_target
repo_pin_source=none
```

Filesystem proof after the blocked run:

```text
/private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state/ds-goal-preflight-block-proof/mission.json
/private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state/ds-goal-preflight-block-proof/receipts.jsonl
/private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state/ds-goal-preflight-block-proof/tasks.jsonl
```

No `.runtime/runtime.db` and no kernel event ledger were created for the
blocked proof.

Fresh allowed proof:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --db /private/tmp/ds-goal-preflight-gate-pinned-proof-20260614T2245JST/state/.runtime/runtime.db --strict
exit 0
Runtime receipts: 13
Major task receipts: 2
side_effect_key: 13/13
Latest ds-goal preflight receipt payloads: 2/2
pass_explicit_audited_checkout_pin 2
```

Score consequence:

- future current-checkout unpinned ds-goal runs are blocked before dirty
  runtime receipt creation;
- pinned audited-checkout runs still create clean scoped receipts;
- installed wrapper default remains `/Users/dhyana/dharma_swarm_main`;
- existing global live DB receipt debt remains;
- global strict coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Prevention Receipts Are Machine-Inspectable

Date: 2026-06-14 22:47 JST

`ds_goal_longrun_preflight_report.py` can now scan ds-goal mission ledgers for
`preflight_blocked` receipts and report them as prevention evidence. This gives
the 70->75 receipt gate a stable companion verifier for the fail-closed path:
the unsafe start was blocked before runtime DB/idempotency/kernel side effects,
but that does not turn the global live DB green.

Fresh verifier evidence:

```text
python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict --prevention-receipt-root /private/tmp/ds-goal-preflight-block-proof-20260614T2245JST/state
exit 0
Preflight prevention receipts: 1
Valid preflight blocks: 1
runtime_db=runtime_db_absent_under_state_root
kernel=kernel_store_absent

pytest -q tests/test_ds_goal_longrun_preflight_report.py --tb=short
exit 0
5 passed
```

Score consequence:

- fail-closed prevention evidence is now repeatable;
- active-head global ds-goal rows are still dirty;
- installed wrapper default still targets `/Users/dhyana/dharma_swarm_main`;
- global strict coverage still exits 1;
- score remains 70/100.

## Checkpoint: ds-goal Action Queue Separates Prevention From Readiness

Date: 2026-06-14 22:47 JST

The 70->75 receipt gate now projects ds-goal prevention evidence inside the
field-gap action queue without treating it as wrapper convergence. This keeps
the action item honest: the audited checkout can block unsafe unpinned starts,
but the installed wrapper/default target still owns the active-head receipt
debt.

Fresh verifier evidence:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
exit 1
label=ds_goal_wrapper
active_head=40
fresh_proof=status=pin_mitigation_and_fail_closed_prevention_recorded_default_still_broken
prevention_evidence=valid_preflight_block=1; runtime_db_absent_under_state_root; kernel_store_absent
```

Score consequence:

- fail-closed prevention is visible in the receipt gate;
- active-head ds-goal rows are still dirty;
- installed wrapper default still targets `/Users/dhyana/dharma_swarm_main`;
- global strict coverage still exits 1;
- score remains 70/100.
