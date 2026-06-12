# Runtime Truth Command Cutover Baseline Receipt

Generated: 2026-06-12
Worktree: `/Users/dhyana/dharma_swarm_main`

## Branch And HEAD

- Branch: `holon/spine-v1`
- HEAD: `f0d03ffaf4 fix(runtime): repair ds-goal entrypoint`
- Baseline divergence from `origin/main`: ahead 5, behind 3

## Dirty Worktree Truth

Baseline `make onboard` reported 63 dirty files before this cutover pass.
Dirty areas already included tests, `scripts/runtime`, operator-core, control
surface, and generated governance reports. This pass preserved unrelated dirty
work and only edited the files named in the after-action.

## Active Tracks

`make onboard` projected two active tracks:

- `runtime-truth-reconciliation-2026-06`: ACTIVE, SHIPPABLE
- `runtime-truth-nats-2026-06`: ACTIVE, SHIPPABLE

Projected spine coverage gaps:

- no active track for `revenue-external-humans-served`
- no active track for `research-depth`

## Runtime Truth Claims

Latest onboard runtime compact before edits:

- runtime DB: `/Users/dhyana/.dharma/state/runtime.db`
- latest receipt: `runtime_receipts:rr_b38bdcee9c944307`
- run id: `kernel_run_75b788dc28db44d8`
- task id: `codex-runtime-truth-smoke-20260611t090734z-t01`
- heartbeat/progress: stalled by artifact progress
- completion: completed by receipt
- retry: retry equivalent

## Spine Adoption Metric

Observed `reports/governance/spine_adoption_metric.json` baseline:

- joined count: 12
- adapter-ready count: 3
- joined or adapter-ready: 93.8 percent
- joined percent: 75.0 percent
- legacy count: 1
- missing count: 0
- non-joined targets: `tool_registry_dispatch`, `self_modification_loop`,
  `mcp_tool_access`, `legacy_no_identity_escape_hatch`

## AMBER And RED Claims

- AMBER: runtime saturation is partial until default command paths prove
  idempotency, runtime receipts, and dispatch evidence.
- AMBER: revenue and external-human proof are absent from active tracks.
- AMBER: research-depth proof is absent from active tracks.
- AMBER: AgentOps green gates without runtime refs must not project as bound.
- RED: live trading authority without explicit external/legal authority.
- RED: Forge/Hydra runnable claims without a fresh run receipt.

## Known Cutover Targets

- `scripts/runtime/autonomy_spine.py` (`ds-goal`)
- `scripts/runtime/a2a_send.py`
- `scripts/runtime/a2a_reply_capture.py`
- `dharma_swarm/board/adapters/a2a_send_adapter.py`
- `dharma_swarm/operator_core/operating_facts.py`
- onboarding runtime truth compact summary

## Substrate Track State

The active substrate tracks were already projected as shippable by onboarding.
This receipt does not upgrade that to full runtime saturation. It records the
starting point for a narrower command cutover enforcement pass.
