# Final Sitrep

Mission ID: `20260618T020138Z`

## Status

Offline hardening and surface alignment are implemented and verified in the
pinned worktree `/Users/dhyana/ds_model_pool` on branch
`model-routing/consolidation-2026-06`.

Actual live model-call proof is not complete. The direct live verifier is
implemented and intentionally fail-closed unless `DHARMA_LIVE_MODEL_E2E=1` is
set; this run produced a dry-run plan but did not make live model calls.

## Implemented

- Added canonical model-status projection in `dharma_swarm.model_status`.
- Added dashboard API routes for `/api/pool/top10/status`,
  `/api/pool/top10/verify`, and profile patching.
- Updated dashboard model types and `/dashboard/models` copy/state handling.
- Added fail-closed direct live probe in
  `scripts/verify/model_routing_live_probe.py` and kept
  `scripts/verify/model_pool_e2e.py` as a secondary TUI consumer check.
- Added fail-closed A2A model-council harness in
  `scripts/verify/model_council_e2e.py`; it plans draft, critique, and
  synthesis stages through `CardRegistry` -> `A2AServer` -> `A2AClient`.
- Added hermetic routing decision matrix in
  `dharma_swarm.routing_decision_matrix` plus receipt script.
- Hardened router failure handling for empty responses and long structured
  quota/billing/access/rate-limit errors.
- Aligned Terminal/Bun `/models` bridge payloads with `dharma_swarm.model_status`
  and rendered target rows directly from the structured contract.
- Diversified multi-role swarm planning across available providers before
  reusing a provider.

## Receipts

- `TARGET_WORKTREE_RECEIPT.md`: target worktree and branch pin.
- `COMPLETION_AUDIT.md`: requirement-by-requirement status and remaining
  completion gates.
- `model_inventory.json`: model/provider inventory and debt census.
- `naming_drift_report.md`: Semantic Commons alignment, hardcoded debt, and
  guard status.
- `live_call_matrix.json`: refreshed from
  `reports/model_pool/e2e_20260618T113124.json`; `9` floor operable, `12`
  grunt-only, `9` unroutable; actual live calls are `not_run`.
- `direct_live_probe.json`: direct runtime-provider dry-run plan; `9` floor
  models planned, `3` floor models skipped as `provider_dead`, `0` live calls.
- `routing_decision_matrix.json`: hermetic matrix, `8` passed, `0` failed.
- `model_council_transcript.json`: A2A council dry-run plan; `3` planned
  agents, `3` distinct providers, `0` live calls.
- `models_surface_contract.md`: surface contract and verification log.

## Verification

- `pytest -q tests/test_model_status_projection.py tests/test_model_pool_api.py tests/test_model_pool_e2e_live_gate.py tests/test_key_oracle_live_filter.py tests/test_model_pool.py tests/test_routing_decision_matrix.py tests/test_provider_failure_classes.py tests/test_provider_matrix.py tests/test_provider_policy.py tests/test_router_v1.py tests/test_swarm_router.py tests/test_runtime_provider.py tests/test_provider_smoke.py tests/test_terminal_bridge.py tests/test_operator_core_adapters.py tests/test_model_key_routing_guard.py`
  - Result: `201 passed, 1 warning`.
- `pytest -q tests/test_model_council_e2e.py tests/test_model_routing_live_probe.py tests/test_model_pool_e2e_live_gate.py tests/test_model_status_projection.py tests/test_runtime_provider.py tests/test_model_key_routing_guard.py`
  - Result: `49 passed`.
- `cd terminal && bun test tests/routePolicy.test.ts tests/protocol.test.ts`
  - Result: `122 pass`.
- `python3 scripts/verify/model_pool_e2e.py --dry-run --no-refresh`
  - Result: fresh-key dry-run wrote `reports/model_pool/e2e_20260618T113124.json`.
- `env DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --dry-run --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json`
  - Result: direct probe plan wrote `9` planned, `3` skipped, `0` attempted.
- `python3 scripts/verify/model_routing_live_probe.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `env DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_council_e2e.py --dry-run --output reports/model_routing/e2e/20260618T020138Z/model_council_transcript.json`
  - Result: A2A council plan wrote `3` planned agents, `3` distinct providers,
    `0` attempted.
- `python3 scripts/verify/model_council_e2e.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `python3 scripts/verify/model_pool_e2e.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `python3 scripts/verify/routing_decision_matrix.py --output reports/model_routing/e2e/20260618T020138Z/routing_decision_matrix.json`
  - Result: `8 passed, 0 failed`.

## Blockers

- Live model-call verification requires explicit operator opt-in:
  `DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --live --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json`.
- Multi-model council E2E remains blocked for the same live opt-in plus a real
  live execution of the new DharmaSwarm/A2A receipt-producing path.
- Terminal app reducer test is blocked by missing local `react` dependency.
- Terminal `bun run typecheck` is blocked by missing local `tsc`.
- The documented `scripts/terminal_guardian_preflight.sh` does not exist in this
  checkout; terminal changes were verified through Python bridge tests and Bun
  route-policy/protocol tests instead.
- Dashboard browser rendering still needs a running API/dashboard server for
  visual verification.
