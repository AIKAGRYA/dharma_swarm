---
name: testing-dashboard-runtime
description: Test DHARMA COMMAND dashboard and FastAPI runtime end-to-end. Use when verifying the app boots locally, dashboard telemetry is live, or opportunity dispatch/refill writes durable runtime state.
type: reference
---

# Testing Dashboard + Runtime Inside-Out

**Purpose:** an end-to-end smoke that proves the FastAPI runtime boots, the Next.js dashboard renders live telemetry from it, and opportunity dispatch/refill writes durable sqlite state. "Inside-out" means: assert at the API first, then confirm the UI shows the same numbers — a pretty dashboard over a dead API is a FAIL.

## Environment

No secrets needed in dev mode: when `DASHBOARD_API_KEY` is unset the API middleware opens `/api/*`. Set it only when intentionally testing Bearer auth. NATS credentials are only for live A2A substrate tests, never for this smoke.

Run from the repo root of the checkout under test:

```bash
cd "$(git rev-parse --show-toplevel)"
export PYTHONPATH="$PWD"
export PATH="$PWD/.venv/bin:$PATH"    # prefer THIS checkout's venv; only borrow a shared
                                      # venv after confirming it's the same repo + deps
[ -d dashboard/node_modules ] || npm --prefix dashboard install --legacy-peer-deps
```

## Procedure

### 1. Start the runtime with isolated state

Always use a throwaway state dir so sqlite assertions are repeatable and you never pollute `~/.dharma`:

```bash
export DHARMA_STATE_DIR="$PWD/.e2e_state/inside-out-state"
export DHARMA_SWARM_INIT_TIMEOUT_SECONDS=3
uvicorn api.main:app --host 127.0.0.1 --port 8420
```

Expected startup: `Application startup complete`, plus `Dashboard API bearer auth is disabled...` when the key is unset. GnaniLodestone seeding warnings are warnings only — escalate them to failures only if an endpoint then errors.

### 2. Start the dashboard

```bash
npm --prefix dashboard run dev -- --hostname 127.0.0.1 --port 3420
```

Open `http://127.0.0.1:3420/dashboard`. The dashboard makes relative `/api/...` calls that Next proxies to FastAPI on 8420 — keep `NEXT_PUBLIC_API_URL` unset unless you are deliberately bypassing the proxy.

### 3. Browser assertions (record browser testing for UI runs)

Pass criteria — all of:
- Page shows `System Overview`; `Connecting to swarm...` disappears.
- Metric cards render: `Agents`, `Tasks`, `Fitness`, `Health`.
- Card values match `GET http://127.0.0.1:8420/api/overview`: `agent_count`, `task_count`, `mean_fitness` (3 decimals), `health_status`.
- `health_status: "unknown"` is a warning, not a wiring failure, iff `/api/health` returns `status: "ok"` and no endpoint errored.

### 4. Opportunity loop checks

```bash
curl -s http://127.0.0.1:8420/api/opportunities/stages | python -m json.tool
```
Expected stages, in order: `scope, validate, deep_research, capability, mvp, first_artifact`.

Dispatch:
```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"id":"inside-out-dispatch","title":"Inside-out dispatch","type":"external_revenue","estimated_value_usd":1000}' \
  | python -m json.tool
```
Pass: exactly 6 results, every one `success: true` with non-empty `stage`, `task_id`, `claim_id`, `run_id`; and `$DHARMA_STATE_DIR/runtime.db` contains exactly 6 matching `task_claims` and 6 matching `delegation_runs` for the test opportunity id (inspect with Python's `sqlite3` module — the CLI may not be installed).

Refill:
```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/refill \
  -H 'Content-Type: application/json' \
  -d '{"id":"inside-out-refill","title":"Inside-out refill","type":"external_revenue","estimated_value_usd":1000}' \
  | python -m json.tool
```
Pass: `success: true`; exactly 6 stages; `total_provider_cost_usd` present and numeric; `total_net_value_usd` numeric and equal to `estimated_value_usd - total_provider_cost_usd`; `revenue_packet_path` non-empty, exists on disk, and contains the refill opportunity id.

### 5. Diagnostics (context for the report, not pass/fail)

```bash
make status        # open PRs / broken-register items → report as warnings
make spine-check   # should print "spine ownership clear"
```

## Output Format

```
DASHBOARD/RUNTIME SMOKE: PASS | FAIL
- runtime boot:        <ok | failed: first error line>
- dashboard render:    <ok | which card/value mismatched vs /api/overview>
- stages endpoint:     <ok | got: ...>
- dispatch:            <6/6 success, db rows 6+6 | what diverged>
- refill:              <ok, packet at <path> | what diverged>
- warnings:            <GnaniLodestone seeding, health_status unknown, make status items, ...>
```

## Do NOT

- Do not run against `~/.dharma/state` — always an isolated `DHARMA_STATE_DIR`, and don't commit `.e2e_state/` (runtime receipts never enter git).
- Do not call the UI "passing" without diffing its numbers against `/api/overview` — matching values are the test.
- Do not set `NEXT_PUBLIC_API_URL` casually; it silently bypasses the proxy path you're supposed to be testing.
- Do not promote startup warnings to failures unless an endpoint actually errors — and do not bury endpoint errors as "warnings" either.
- Do not leave uvicorn/next dev servers running after the smoke; kill them and note it.
