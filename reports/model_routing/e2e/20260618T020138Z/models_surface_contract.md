# Models Surface Contract

Mission ID: `20260618T020138Z`

## Contract

The canonical model-status projection is:

`dharma_swarm.model_status`

It projects:

- logical model identity from `dharma_swarm.model_pool.MODEL_POOL`
- floor/grunt demarcation from `ModelEntry.below_floor`
- route liveness from `dharma_swarm.key_oracle.live_providers()`
- safe provider status rows from `~/.dharma/keys_status.json`
- optional live-call receipt overlay from
  `DHARMA_MODEL_LIVE_CALL_MATRIX_PATH`
- dashboard labels from `~/.dharma/model_pool_profiles.json` or `DHARMA_MODEL_PROFILE_PATH`

It does not read key values, construct providers, or make live model calls.
Live calls are made only by receipt-producing verifier scripts; the projection
only consumes their safe route-level result matrix.

## Surface Alignment

Dashboard `/dashboard/models` consumes:

- `GET /api/pool/top10/status`
- `POST /api/pool/top10/verify`
- `PATCH /api/pool/models/{model_id}/profile`

Those routes are implemented by `api.routers.model_pool` and return the
canonical projection from `dharma_swarm.model_status`.

TUI model selection already projects from `dharma_swarm.model_pool.floor_entries()`
and `dharma_swarm.key_oracle.live_providers()` in `dharma_swarm/tui/model_routing.py`.
Its rendering still uses local terminal strings, but the identity, floor
demarcation, and liveness owner match the canonical projection.

Terminal/Bun model policy is now aligned at the bridge contract:

- `dharma_swarm/terminal_bridge.py` builds `/models` payloads from
  `dharma_swarm.model_status.floor_model_status()` plus the existing TUI alias
  table.
- `dharma_swarm/terminal_bridge_text.py` renders `targets` and `fallback_chain`
  directly; it no longer depends on legacy `available_providers` rows.
- `terminal/src/routePolicy.ts` continues to normalize the same `targets`
  payload for the picker.
- A target is terminal-selectable only when the canonical model route is
  `live_routable` and the Bun terminal has an adapter for that bridge provider.
  Live floor models without a terminal adapter remain visible as constrained
  targets with `terminal_adapter_missing`.

## Machine States

Every model surface must represent one of these states:

- `live_routable`: at least one provider route is live by current key oracle
  and not contradicted by a failed route-level live receipt.
- `unverified`: key status is missing or stale; surface must not advertise the
  model as callable.
- `unavailable`: no route is live under the current key oracle.

Unavailable reasons are machine-readable and restricted to:

- `key_status_unknown`
- `key_missing`
- `provider_dead`
- `model_missing`
- `quota`
- `unsupported_route`
- `timeout`
- `schema_failure`
- `routing_bug`

## Verification

Hermetic tests added:

- `tests/test_model_status_projection.py`
- `tests/test_model_pool_api.py`
- `tests/test_model_pool_e2e_live_gate.py`
- `tests/test_model_council_e2e.py`
- `tests/test_model_routing_live_probe.py`
- `tests/test_routing_decision_matrix.py`

Focused verification run:

```bash
pytest -q tests/test_model_status_projection.py tests/test_model_pool_api.py tests/test_model_pool_e2e_live_gate.py tests/test_model_routing_live_probe.py tests/test_key_oracle_live_filter.py tests/test_model_pool.py tests/test_routing_decision_matrix.py tests/test_provider_failure_classes.py tests/test_provider_matrix.py tests/test_provider_policy.py tests/test_router_v1.py tests/test_swarm_router.py tests/test_runtime_provider.py tests/test_provider_smoke.py tests/test_terminal_bridge.py tests/test_operator_core_adapters.py tests/test_model_key_routing_guard.py
```

Previous full result before the direct verifier/council harness was added:
`201 passed, 1 warning`.
Focused direct-verifier/council/runtime result: `49 passed`.

Terminal contract checks:

```bash
cd terminal && bun test tests/routePolicy.test.ts tests/protocol.test.ts
```

Result: `122 pass`.

Dashboard browser/build verification:

```bash
npm --prefix dashboard ci --legacy-peer-deps
env DHARMA_API_PROXY_URL=http://127.0.0.1:18420 npm --prefix dashboard run build
npx --prefix dashboard playwright screenshot --full-page --viewport-size=1440,1000 http://127.0.0.1:13420/dashboard/models reports/model_routing/e2e/20260618T020138Z/dashboard_models_fullpage.png
```

Result: isolated current-build API returned `12` models with `9` live-routable
before the live overlay and the dashboard route returned `200` (`76259` bytes).
The final default-port launchd receipt supersedes this for operator-visible
state.

Terminal Guardian/app checks:

- `scripts/terminal_guardian_preflight.sh` passed bridge `py_compile`, terminal
  `tsc --noEmit`, protocol/route-policy tests, and an `80x24` compact smoke.
- `cd terminal && bun run verify:command-routing`: `325 pass, 0 fail`.
- `cd terminal && bun run verify:control-surface`: `77 pass, 0 fail`.
- `cd terminal && bun run verify:repo-pane`: `466 pass, 0 fail`.
- `cd terminal && bun test tests/persistence.test.ts`: `44 pass, 0 fail`.

Direct live model calls remain opt-in only:

```bash
DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --live --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json
```

Without the env gate, the live verifier exits fail-closed. With the explicit
env gate, this mission generated PONG and full-profile live receipts.

Receipts:

- `reports/model_pool/e2e_20260618T113124.json`: fresh-key dry-run, `9` floor
  operable, `12` grunt-only, `9` unroutable.
- `reports/model_routing/e2e/20260618T020138Z/live_call_matrix.json`: refreshed
  from the fresh-key dry-run and live receipts; key-oracle counts remain `9`
  floor operable, while live-overlay counts are `7` available and `5`
  unavailable.
- `reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json`:
  direct runtime-provider PONG receipts, `11` attempted, `9` ok, `2` quota
  failures.
- `reports/model_routing/e2e/20260618T020138Z/direct_live_probe_full.json`:
  direct runtime-provider full-profile receipts, `45` attempted, `44` ok,
  `1` timeout.
- `reports/model_routing/e2e/20260618T020138Z/direct_live_probe_minimax_m3_full_retry.json`:
  targeted MiniMax retry receipts, `10` attempted, `9` ok, `1` quota failure.
- `reports/model_routing/e2e/20260618T020138Z/model_council_transcript.json`:
  live A2A council transcript, `3` planned agents, `3` distinct providers,
  `3` attempted, `3` completed.
- `reports/model_routing/e2e/20260618T020138Z/routing_decision_matrix.json`:
  hermetic router/fallback matrix, `8` passed, `0` failed.
- `reports/model_routing/e2e/20260618T020138Z/dashboard_browser_verification.json`:
  isolated dashboard browser receipt plus screenshots:
  `dashboard_models_1440.png`, `dashboard_models_fullpage.png`,
  `dashboard_models_mobile.png`.
- `reports/model_routing/e2e/20260618T020138Z/dashboard_launchd_verification.json`:
  default launchd/API/dashboard receipt after repointing launch agents to
  `/Users/dhyana/ds_model_pool`; `dashboard_models_default_live_overlay_fullpage.png`
  captures the default `3420` `/dashboard/models` surface with live overlay.
- `reports/model_routing/e2e/20260618T020138Z/terminal_guardian_verification.json`:
  Terminal Guardian dependency restoration, preflight, and app verification
  receipt.
- `reports/model_routing/e2e/20260618T020138Z/semantic_commons_guard_verification.json`:
  branch-local Semantic Commons guard receipt; `pytest -q
  tests/test_model_key_routing_guard.py` passed `3` guard tests.

## Remaining Gaps

- `/api/pool/top10/verify` intentionally does not make implicit live calls; live
  proof belongs in receipt-producing scripts.
- The NVIDIA NIM MiniMax route has a full-profile JSON-schema timeout receipt
  and a targeted retry quota receipt. The surface safely marks that route
  unavailable while leaving MiniMax available through Ollama.
