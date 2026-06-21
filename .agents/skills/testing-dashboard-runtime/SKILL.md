---
name: testing-dashboard-runtime
description: Test DHARMA COMMAND dashboard and FastAPI runtime end-to-end. Use when verifying the app boots locally, dashboard telemetry is live, or opportunity dispatch/refill writes durable runtime state.
---

# Testing Dashboard + Runtime Inside-Out

## Devin Secrets Needed

- None for local dev mode when `DASHBOARD_API_KEY` is unset; API middleware opens `/api/*` in dev mode.
- `DASHBOARD_API_KEY` only if intentionally testing authenticated dashboard API access.
- `DEVIN_NATS_URL`, `DEVIN_NATS_USER`, `DEVIN_NATS_PW` are only needed for live A2A/NATS substrate tests, not the local dashboard/opportunity smoke.

## Setup

Use the repo venv when present:

```bash
cd /home/ubuntu/repos/dharma-swarm
PATH="$PWD/.venv/bin:$PATH" make onboard
```

If testing from a separate worktree, reuse the canonical venv and set `PYTHONPATH` to the worktree:

```bash
cd /path/to/dharma-swarm-worktree
export PYTHONPATH="$PWD"
export PATH="/home/ubuntu/repos/dharma-swarm/.venv/bin:$PATH"
```

If `dashboard/node_modules` is missing, install dashboard dependencies incrementally:

```bash
npm --prefix dashboard install --legacy-peer-deps
```

## Start Local Runtime

Use an isolated state dir for repeatable sqlite assertions:

```bash
export DHARMA_STATE_DIR=/home/ubuntu/test-artifacts/inside-out-state
export DHARMA_SWARM_INIT_TIMEOUT_SECONDS=3
uvicorn api.main:app --host 127.0.0.1 --port 8420
```

Expected startup:

- `Application startup complete`
- `Dashboard API bearer auth is disabled...` when `DASHBOARD_API_KEY` is unset
- GnaniLodestone seeding warnings might appear; treat them as warnings unless API endpoints fail

Start the dashboard:

```bash
npm --prefix dashboard run dev -- --hostname 127.0.0.1 --port 3420
```

Open `http://127.0.0.1:3420/dashboard`. The dashboard uses relative `/api/...` calls; Next proxies these to FastAPI on `8420`. Keep `NEXT_PUBLIC_API_URL` unset unless intentionally bypassing the proxy.

## Browser Assertions

Record browser testing when using the dashboard UI.

Pass criteria:

- The page shows `System Overview`.
- Metric cards render with labels `Agents`, `Tasks`, `Fitness`, and `Health`.
- `Connecting to swarm...` disappears.
- Values shown in the cards match `GET http://127.0.0.1:8420/api/overview`:
  - `agent_count`
  - `task_count`
  - `mean_fitness` formatted to three decimals
  - `health_status`

`health_status: "unknown"` is a warning, not a dashboard wiring failure, if `/api/health` returns `status: "ok"` and no endpoint error.

## Opportunity Loop Assertions

Verify the canonical stages:

```bash
curl -s http://127.0.0.1:8420/api/opportunities/stages | python -m json.tool
```

Expected stages exactly:

```text
scope, validate, deep_research, capability, mvp, first_artifact
```

Dispatch an opportunity:

```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"id":"inside-out-dispatch","title":"Inside-out dispatch","type":"external_revenue","estimated_value_usd":1000}' \
  | python -m json.tool
```

Pass criteria:

- Exactly 6 results.
- Every result has `success: true`.
- Every result has non-empty `stage`, `task_id`, `claim_id`, and `run_id`.
- `runtime.db` contains exactly 6 matching `task_claims` and 6 matching `delegation_runs` for the test opportunity ID.

Refill an opportunity:

```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/refill \
  -H 'Content-Type: application/json' \
  -d '{"id":"inside-out-refill","title":"Inside-out refill","type":"external_revenue","estimated_value_usd":1000}' \
  | python -m json.tool
```

Pass criteria:

- `success: true`.
- Exactly 6 stages.
- `total_provider_cost_usd` is `0.23`.
- `total_net_value_usd` is `999.77` for a `$1000` estimated value.
- `revenue_packet_path` is non-empty, exists on disk, and the file contains the refill opportunity ID.

## Useful Diagnostics

```bash
PATH="$PWD/.venv/bin:$PATH" make status
PATH="$PWD/.venv/bin:$PATH" make spine-check
```

`make spine-check` should print `spine ownership clear`. `make status` may still show open PRs or broken-register items; report those as warnings rather than dashboard/runtime smoke failures unless they prevent startup or endpoint execution.
