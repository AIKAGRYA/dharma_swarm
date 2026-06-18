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
- dashboard labels from `~/.dharma/model_pool_profiles.json` or `DHARMA_MODEL_PROFILE_PATH`

It does not read key values, construct providers, or make live model calls.

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

- `live_routable`: at least one provider route is live by current key oracle.
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

Blocked terminal checks:

- `cd terminal && bun test tests/app.test.ts` failed before tests because local
  `react` is not installed.
- `cd terminal && bun run typecheck` failed because local `tsc` is not installed.

Direct live model calls remain opt-in only:

```bash
DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --live --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json
```

Without the env gate, the live verifier exits fail-closed.

Receipts:

- `reports/model_pool/e2e_20260618T113124.json`: fresh-key dry-run, `9` floor
  operable, `12` grunt-only, `9` unroutable.
- `reports/model_routing/e2e/20260618T020138Z/live_call_matrix.json`: refreshed
  from the fresh-key dry-run; actual live model calls remain `not_run`.
- `reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json`:
  direct runtime-provider dry-run plan, `9` planned, `3` skipped, `0` attempted.
- `reports/model_routing/e2e/20260618T020138Z/model_council_transcript.json`:
  A2A council dry-run plan, `3` planned agents, `3` distinct providers,
  `0` attempted.
- `reports/model_routing/e2e/20260618T020138Z/routing_decision_matrix.json`:
  hermetic router/fallback matrix, `8` passed, `0` failed.

## Remaining Gaps

- Dashboard page rendering still needs browser verification after the API server
  is run.
- `/api/pool/top10/verify` intentionally does not make implicit live calls; live
  proof belongs in receipt-producing scripts.
- Bun app reducer and TypeScript checks need local terminal dependencies
  installed before they can run in this worktree.
