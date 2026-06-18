# Final Sitrep

Mission ID: `20260618T020138Z`

## Status

Hardening, surface alignment, and live receipt overlay are implemented and
verified in the pinned worktree `/Users/dhyana/ds_model_pool` on branch
`model-routing/consolidation-2026-06`.

Live proof is no longer dry-run only. The direct PONG probe attempted `11`
route calls (`9` ok, `2` Claude Code quota failures). The direct full-profile
probe attempted `45` calls (`44` ok, `1` NVIDIA NIM MiniMax JSON-schema
timeout), and a targeted MiniMax retry reproduced the NVIDIA route failure as
429/quota. The default `/models` surfaces now advertise `7` available floor
models and explicitly demote failed routes/models.

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
- `live_call_matrix.json`: preserves key-oracle counts (`9` floor operable,
  `12` grunt-only, `9` unroutable) and adds live-overlay counts (`7` floor
  available, `5` unavailable).
- `direct_live_probe.json`: direct runtime-provider PONG probe; `11` route
  calls attempted, `9` ok, `2` quota failures.
- `direct_live_probe_full.json`: direct runtime-provider full-profile probe;
  `45` calls attempted, `44` ok, `1` timeout.
- `direct_live_probe_minimax_m3_full_retry.json`: targeted MiniMax retry;
  `10` calls attempted, `9` ok, `1` quota failure.
- `routing_decision_matrix.json`: hermetic matrix, `8` passed, `0` failed.
- `model_council_transcript.json`: live A2A council transcript; `3` planned
  agents, `3` distinct providers, `3` live calls, `3` completed stages.
- `models_surface_contract.md`: surface contract and verification log.
- `dashboard_browser_verification.json`: isolated current-build dashboard/API
  browser receipt; superseded for final default-port state by the launchd
  live-overlay receipt.
- `dashboard_models_1440.png`, `dashboard_models_fullpage.png`,
  `dashboard_models_mobile.png`: Playwright screenshots of `/dashboard/models`.
- `dashboard_launchd_verification.json` and
  `dashboard_models_default_live_overlay_fullpage.png`:
  default `3420`/`8420` launchd verification after repointing launch agents to
  `/Users/dhyana/ds_model_pool`; `12` floor models, `7` available after live
  receipt overlay.
- `terminal_guardian_verification.json`: Terminal Guardian preflight and terminal
  app verification receipt after restoring Bun dependencies.
- `semantic_commons_guard_verification.json`: branch-local Semantic Commons
  guard receipt for routing terms and forbidden aliases.

## Verification

- `pytest -q tests/test_model_status_projection.py tests/test_model_pool_api.py tests/test_model_pool_e2e_live_gate.py tests/test_key_oracle_live_filter.py tests/test_model_pool.py tests/test_routing_decision_matrix.py tests/test_provider_failure_classes.py tests/test_provider_matrix.py tests/test_provider_policy.py tests/test_router_v1.py tests/test_swarm_router.py tests/test_runtime_provider.py tests/test_provider_smoke.py tests/test_terminal_bridge.py tests/test_operator_core_adapters.py tests/test_model_key_routing_guard.py`
  - Result: `201 passed, 1 warning`.
- `pytest -q tests/test_model_council_e2e.py tests/test_model_routing_live_probe.py tests/test_model_pool_e2e_live_gate.py tests/test_model_status_projection.py tests/test_runtime_provider.py tests/test_model_key_routing_guard.py`
  - Result: `49 passed`.
- `cd terminal && bun test tests/routePolicy.test.ts tests/protocol.test.ts`
  - Result: `122 pass`.
- `python3 scripts/verify/model_pool_e2e.py --dry-run --no-refresh`
  - Result: fresh-key dry-run wrote `reports/model_pool/e2e_20260618T113124.json`.
- `env DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --live --profile pong --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe.json`
  - Result: PONG route receipts merged from per-model runs; `11` route calls
    attempted, `9` ok, `2` quota failures.
- `env DHARMA_LIVE_MODEL_E2E=1 DHARMA_MODEL_LIVE_CALL_MATRIX_PATH=/Users/dhyana/.dharma/model_live_call_matrix.json python3 scripts/verify/model_routing_live_probe.py --live --profile full --timeout 60 --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe_full.json`
  - Result: full-profile route receipts wrote `45` attempted calls, `44` ok,
    `1` timeout on `nvidia_nim:minimaxai/minimax-m3` JSON-schema.
- `env DHARMA_LIVE_MODEL_E2E=1 python3 scripts/verify/model_routing_live_probe.py --live --profile full --model minimax-m3 --timeout 90 --output reports/model_routing/e2e/20260618T020138Z/direct_live_probe_minimax_m3_full_retry.json`
  - Result: targeted MiniMax retry wrote `10` attempted calls, `9` ok,
    `1` quota failure on `nvidia_nim:minimaxai/minimax-m3` long-context.
- `python3 scripts/verify/model_routing_live_probe.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `env DHARMA_LIVE_MODEL_E2E=1 DHARMA_MODEL_LIVE_CALL_MATRIX_PATH=/Users/dhyana/.dharma/model_live_call_matrix.json python3 scripts/verify/model_council_e2e.py --live --output reports/model_routing/e2e/20260618T020138Z/model_council_transcript.json`
  - Result: live A2A council passed; `3` planned agents, `3` distinct
    providers, `3` attempted, `3` completed.
- `python3 scripts/verify/model_council_e2e.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `python3 scripts/verify/model_pool_e2e.py --live --no-refresh`
  - Result: refused with `DHARMA_LIVE_MODEL_E2E=1` required.
- `python3 scripts/verify/routing_decision_matrix.py --output reports/model_routing/e2e/20260618T020138Z/routing_decision_matrix.json`
  - Result: `8 passed, 0 failed`.
- `npm --prefix dashboard ci --legacy-peer-deps`
  - Result: dependency install passed; npm audit reported `8` vulnerabilities
    (`1` low, `4` moderate, `3` high), not remediated in this routing task.
- `env DHARMA_API_PROXY_URL=http://127.0.0.1:18420 npm --prefix dashboard run build`
  - Result: dashboard build passed against the current API proxy target.
- Isolated API/dashboard verification:
  - `GET http://127.0.0.1:18420/api/pool/top10/status`: original isolated
    receipt had `12` models, `9` available before live overlay; default-port
    launchd receipt is the final surface state.
  - `POST http://127.0.0.1:18420/api/pool/top10/verify`: fail-closed with
    `live_calls_attempted=false`, `skipped_count=12`.
  - `GET http://127.0.0.1:13420/dashboard/models`: `200`, `76259` bytes.
- Playwright browser screenshots:
  - `reports/model_routing/e2e/20260618T020138Z/dashboard_models_1440.png`
  - `reports/model_routing/e2e/20260618T020138Z/dashboard_models_fullpage.png`
  - `reports/model_routing/e2e/20260618T020138Z/dashboard_models_mobile.png`
- Launchd/default dashboard verification:
  - `env DHARMA_API_PROXY_URL=http://127.0.0.1:8420 npm --prefix dashboard run build`: passed.
  - `bash scripts/install_dashboard_launch_agents.sh restart`: passed with scoped escalation after sandbox launchctl bootstrap failed.
  - `dkeys test`: refreshed safe key-status cache; summary `10` live,
    `2` valid-but-no-funds, `3` auth-fail, `1` no-key-yet.
  - `GET http://127.0.0.1:8420/api/pool/top10/status`: `12` models,
    `7` available after live overlay; Claude Opus 4.8 and Claude Sonnet 4.6
    are `unavailable/quota`.
  - `GET http://127.0.0.1:3420/api/pool/top10/status`: `12` models,
    `7` available; MiniMax M3 remains available through
    `ollama:minimax-m3:cloud` while `nvidia_nim:minimaxai/minimax-m3` is
    `unavailable/quota`.
  - `GET http://127.0.0.1:3420/dashboard/models`: `200`, `76259` bytes.
  - Screenshot:
    `reports/model_routing/e2e/20260618T020138Z/dashboard_models_default_live_overlay_fullpage.png`.
- `scripts/terminal_guardian_preflight.sh`
  - Result: passed bridge `py_compile`, terminal `tsc --noEmit`,
    protocol/route-policy tests, and an `80x24` compact smoke.
- `cd terminal && bun run verify:command-routing`
  - Result: `325 pass, 0 fail`.
- `cd terminal && bun run verify:control-surface`
  - Result: `77 pass, 0 fail`.
- `cd terminal && bun run verify:repo-pane`
  - Result: `466 pass, 0 fail`.
- `cd terminal && bun test tests/persistence.test.ts`
  - Result: `44 pass, 0 fail`.
- `pytest -q tests/test_model_key_routing_guard.py`
  - Result: `3 passed`.
- `pytest -q tests/test_model_status_projection.py tests/test_model_pool_e2e_live_gate.py tests/test_model_routing_live_probe.py tests/test_model_council_e2e.py tests/test_runtime_provider.py tests/test_model_key_routing_guard.py`
  - Result: `50 passed`.
- `make agent-build-closeout`
  - Result: passed. The bundle generated `/tmp/dharma-hygiene-audit.txt`,
    ran Semgrep (`0` findings), gitleaks (`no leaks found`), contract tests
    (`22 passed`), NATS/A2A tests (`55 passed`), uplift guards, module budget
    (`OK`), DocOps integrity (`passed`), and hygiene integrity (`OK`).

## Remaining Risks

- The full-profile direct probe is not a clean all-route pass: the NVIDIA NIM
  MiniMax route timed out on the JSON-schema case, and a targeted retry hit
  429/quota on long-context. The `/models` surface handles this safely by
  marking that route unavailable while keeping MiniMax available through
  Ollama.
- Canonical Semantic Commons ontology files are still physically owned by the
  sibling `/Users/dhyana/dharma_swarm` worktree, but this branch now has an
  explicit guard document and CI test until those files are reconciled.
