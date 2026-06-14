# Runtime Spine Landing Closeout

Date: 2026-06-14 JST
Goal: `codex-goal:019ec1bc`
Mode: ramp down / clean landing
Commit: none

## Verdict

Runtime-spine hardening produced a real 70/100 landing candidate with measured
blockers and a clean, reviewable, self-metabolized worktree, not an 88/100
production-ready system.

Not production-ready unless 70→75 passes.

## Evidence Posture

Verified without expanding scope:

```text
65→70 dispatch gate: PASS
70→75 receipt-coverage gate: FAIL
runtime spine score posture: baseline=54/100, current=70/100, cap=70/100
```

Copied runtime DB gate evidence:

```text
db: /private/tmp/runtime-spine-landing-20260614/state/state/runtime.db
runtime_receipts: 8027
major_task_receipts: 3567
idempotency_records: 87
side_effect_key missing: 7026
major idempotency join: 44/3567
latest mission payload: 27/165
artifact evidence: artifact_record=966/3567; latest_artifact_or_no_artifact=27/165
active head windows: 5m=2/7|15m=4/14|60m=14/49
latest major provider/model proof/accounted: 58.79% / 58.79%
latest terminal provider/model proof/accounted: 97.0% / 97.0%
```

Production-readiness blockers preserved:

```text
latest major task receipts do not all carry provider/model payloads
latest major task receipts do not all carry provider/model provenance beyond probe-selected metadata
installed ds-goal wrapper default target does not match the audited checkout
installed ds-goal wrapper target lacks sync side-effect-key hardening
daemon health self-report missing runtime_dispatch
```

## L1/L2 Containment

Only the in-scope static read-only probe boundary was fixed.

Change:

- `scripts/runtime/live_ops_census.py` now comments the exact read-only NATS
  probe: `nats consumer info <stream> <consumer> --json`.
- `tests/test_live_ops_census.py` now allows only that exact NATS command shape
  in the static read-only command test.
- No publish, ack, consume, start, stop, mutate, or supervise command was added.

Focused proof:

```text
PYTEST_ADDOPTS="-p no:cacheprovider" pytest -q tests/test_live_ops_census.py::test_live_ops_census_only_uses_read_only_probe_commands_static_including_nats_consumer_info --tb=short
exit 0
1 passed
```

Two stale `next_action` assertions in `tests/test_live_ops_census.py` were also
aligned with the existing receipt-head-staleness priority after the requested
full slice exposed them. This did not change source behavior.

## L3 Verification

Passing:

```text
PYTEST_ADDOPTS="-p no:cacheprovider" pytest -q \
  tests/test_runtime_receipt_coverage_report.py \
  tests/test_spine_dispatch_mode_report.py \
  tests/test_live_ops_census.py \
  tests/test_runtime_lifecycle.py \
  tests/test_runtime_state_invariants.py \
  tests/test_orchestrator.py \
  tests/test_orchestrator_spine_dispatch.py \
  tests/test_spine_adoption_dispatch.py \
  tests/test_ds_goal_wrapper_receipt_probe.py \
  tests/test_ds_goal_longrun_preflight.py \
  tests/test_ds_goal_longrun_preflight_report.py \
  --tb=short
exit 0
192 passed, 1 warning

python3 scripts/governance/spine_bypass_report.py --json
exit 0

DHARMA_RUNTIME_DB=/private/tmp/runtime-spine-landing-20260614/state/state/runtime.db \
  python3 scripts/governance/spine_dispatch_mode_report.py --strict --json
exit 0

DHARMA_RUNTIME_DB=/private/tmp/runtime-spine-landing-20260614/state/state/runtime.db \
  python3 scripts/runtime/live_ops_census.py \
  --repo-root /Users/dhyana/dharma_swarm \
  --state-root /private/tmp/runtime-spine-landing-20260614/state \
  --output /private/tmp/runtime-spine-landing-20260614/out/live_ops_census.json \
  --write --no-probes
exit 0

python3 scripts/governance/check_track_status.py
exit 0

python3 scripts/governance/render_active_track_includes.py --check
exit 0

git diff --check
exit 0
```

Expected failing gate:

```text
python3 scripts/governance/runtime_receipt_coverage_report.py \
  --strict --json \
  --db /private/tmp/runtime-spine-landing-20260614/state/state/runtime.db
exit 1
70→75 score gate: FAIL
```

Temp evidence outputs:

```text
/private/tmp/runtime-spine-landing-20260614/out/spine_bypass_report.json
/private/tmp/runtime-spine-landing-20260614/out/spine_dispatch_mode_report.json
/private/tmp/runtime-spine-landing-20260614/out/runtime_receipt_coverage_report.json
/private/tmp/runtime-spine-landing-20260614/out/live_ops_census.json
```

Note: `live_ops_census --no-probes` intentionally reports process/port/tmux
surfaces as stopped or unknown because live probes were disabled. Use the
dispatch report for live process proof and the census output for copied DB/temp
projection shape.

## L4 Code-Quality Self-Review

Radon command:

```text
radon cc -s scripts/runtime/live_ops_census.py tests/test_live_ops_census.py scripts/governance/runtime_receipt_coverage_report.py tests/test_runtime_receipt_coverage_report.py dharma_swarm/operator_core/control_surface_live_ops.py scripts/governance/spine_dispatch_mode_report.py tests/test_spine_dispatch_mode_report.py scripts/governance/agent_onboard.py scripts/governance/orientation_graph.py
```

Too complex to merge as-is:

```text
scripts/runtime/live_ops_census.py
  build_live_ops_census F(132)
  _runtime_receipt_coverage_state F(56)
  _a2a_inbox_bridge_runtime_state D(29)
  _daemon_process_source_state D(26)

tests/test_live_ops_census.py
  3326 lines; highest tests E(33), D(23), many C/D scenario tests

scripts/governance/runtime_receipt_coverage_report.py
  _print_text F(144)
  build_report F(70)
  _live_census_ds_goal_context E(31)
  _major_field_gap_producer_groups D(30)

tests/test_runtime_receipt_coverage_report.py
  highest tests E(34), E(31), many C-class scenario tests

dharma_swarm/operator_core/control_surface_live_ops.py
  _rows_from_live_ops_census F(70)
  _runtime_receipt_coverage_evidence_source E(33)
  _live_ops_coherence D(30)

scripts/governance/spine_dispatch_mode_report.py
  _format_runtime_receipt_coverage E(40)
  _live_census_summary E(32)
  _print_text D(21)

scripts/governance/agent_onboard.py
  render_active_track F(41)
  render_live_ops_cockpit E(35)
  _runtime_truth_packets E(35)
  _live_ops_surface_proof_gaps E(31)

scripts/governance/orientation_graph.py
  _surface_proof_gaps E(31)
  _provider_model_coverage_line D(24)
  _ds_goal_wrapper_contract_line D(21)
  render D(21)
```

Split recommendations:

- `live_ops_census.py`: split into process probes, receipt DB read model,
  surface assembly, ds-goal contract projection, and A2A/NATS observation.
- `test_live_ops_census.py`: extract fixture builders and scenario groups by
  surface; keep static safety tests in a separate file.
- `runtime_receipt_coverage_report.py`: split SQL/read model, provider-model
  classification, field-gap action queue, gate components, and text renderer.
- `test_runtime_receipt_coverage_report.py`: split complete-fixture tests,
  provider/model taxonomy tests, field-gap/action-queue tests, and active-head
  window tests.
- `control_surface_live_ops.py`: split evidence-source builders from row
  projection and coherence summary.
- `spine_dispatch_mode_report.py`: split live-census formatting from dispatch
  mode collection and CLI text rendering.
- `agent_onboard.py` / `orientation_graph.py`: move shared receipt-head,
  provider/model, field-gap, and ds-goal formatting into a small projection
  helper after the landing review.

No large refactor was performed during landing.

## L5 Waste Metabolism

Artifacts added:

```text
reports/governance/_landing_compost/MANIFEST.md
reports/governance/WASTE_LEDGER.md
```

No repo file was composted. Clear scratch outputs are outside the repo under
`/private/tmp/runtime-spine-landing-20260614/`.

## L6 Reflection

Drift acknowledged:

- Scope expanded from runtime-spine audit into broad observability and projection
  hardening across census, dashboard helpers, onboard/orient, and governance
  reports.
- `live_ops_census.py` became a ballooning observation hub. It is useful, but
  it needs decomposition before merge.
- Several improvements are projection-only. They make truth visible but do not
  repair the runtime substrate.
- Scoped temp DB proofs are real but not live daemon/default proof.
- Dashboard/operator labels improved, but live dashboard reload/restart proof
  was intentionally not performed.

What is real:

- 65→70 dispatch gate passes.
- Score cap prevents narrative inflation past 70.
- Strict receipt coverage exposes concrete red components.
- ds-goal split-brain is measured and blocked by preflight.
- The read-only command boundary now explicitly permits only NATS consumer-info
  observation.

What remains unproven:

- global 70→75 receipt coverage;
- daemon/default runtime self-report;
- active-head side_effect_key cleanliness;
- provider/model production provenance;
- installed ds-goal default target convergence;
- semantic A2A/domain-reply lifecycle.

## L7 Segmentation Map

Review slice A, runtime core:

```text
dharma_swarm/orchestrator.py
dharma_swarm/agent_runner.py
dharma_swarm/runtime_lifecycle.py
dharma_swarm/runtime_state.py
dharma_swarm/runtime_provider.py
dharma_swarm/providers.py
dharma_swarm/thinkodynamic_director.py
dharma_swarm/swarm_health_api.py
dharma_swarm/spine/manual_runner.py
scripts/runtime/autonomy_spine.py
scripts/live_*.py
runtime core tests
```

Review slice B, receipt/provenance/idempotency:

```text
scripts/governance/runtime_receipt_coverage_report.py
scripts/runtime/runtime_lifecycle_receipt_probe.py
scripts/runtime/ds_goal_wrapper_receipt_probe.py
scripts/runtime/ds_goal_longrun_preflight.py
dharma_swarm/operator_core/ds_goal_wrapper_contract.py
receipt/provenance tests
```

Review slice C, live ops/control surface:

```text
scripts/runtime/live_ops_census.py
dharma_swarm/operator_core/control_surface_live_ops.py
dharma_swarm/operator_core/live_ops_census_contract.py
scripts/governance/agent_onboard.py
scripts/governance/orientation_graph.py
dashboard/src/components/cockpit/SystemTruthMatrix.tsx
dashboard/src/lib/controlSurfaceRuntimeEvidence.ts
status scripts and live-ops tests
```

Review slice D, A2A lifecycle truth:

```text
dharma_swarm/a2a/a2a_bridge.py
dharma_swarm/a2a/a2a_client.py
dharma_swarm/a2a/nats_transport.py
dharma_swarm/a2a/node_gateway.py
reports/a2a/send_receipts/20260614T035438Z-codex_composer-dd41828408dd.json
A2A/NATS tests
```

Review slice E, governance/rendered evidence:

```text
docs/governance/ACTIVE_TRACK.yaml
reports/governance/active_track_evidence.json
reports/governance/active_track_evidence.md
reports/governance/track_portfolio.json
reports/governance/runtime_spine_*_progress_2026-06-14.md
scripts/governance/check_track_status.py
scripts/governance/render_active_track_includes.py
scripts/governance/spine_bypass_report.py
scripts/governance/spine_dispatch_mode_report.py
docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md
```

Review slice F, excluded:

```text
Palantir files: excluded from this landing.
cybernetics_codex files: excluded from this landing.
```

Files to split before merge:

```text
scripts/runtime/live_ops_census.py
tests/test_live_ops_census.py
scripts/governance/runtime_receipt_coverage_report.py
tests/test_runtime_receipt_coverage_report.py
dharma_swarm/operator_core/control_surface_live_ops.py
scripts/governance/spine_dispatch_mode_report.py
scripts/governance/agent_onboard.py
scripts/governance/orientation_graph.py
```

## L8 Halt Condition

No edit is intentionally half-applied.
No commit was made.
No service was restarted.
No Palantir/cybernetics_codex fix was attempted.
Score remains capped at 70/100.

Landing-ready pending human review.

