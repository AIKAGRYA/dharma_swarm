---
name: testing-opportunity-loop
description: Test the Authority and Revenue Loop Gauntlet end-to-end. Use when verifying opportunity dispatch/refill API endpoints, durable runtime state, telic provenance, economic telemetry, or governance checks.
---

# Testing the Opportunity Dispatch/Refill Pipeline

## Prerequisites

- Python venv at `.venv/` with `pip install -e ".[dev]" pre-commit`
- No API key needed for local dev (auth middleware skips when `DASHBOARD_API_KEY` is unset)
- `sqlite3` CLI may not be installed — use Python's `sqlite3` module instead

## Devin Secrets Needed

- None for local testing (dev mode has no auth)
- `DASHBOARD_API_KEY` only needed if testing authenticated API access

## Running the Pytest Suite

```bash
cd /home/ubuntu/dharma_swarm && source .venv/bin/activate
python -m pytest tests/test_authority_revenue_loop.py -v
```

Expected: 22 passed, 1 skipped (orphan ValueEvent test may skip if ontology schema doesn't support direct creation).

## Starting the API Server

```bash
cd /home/ubuntu/dharma_swarm && source .venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8420
```

Startup warnings about GnaniLodestone seeding failures are expected and non-blocking.
The server prints `Application startup complete` when ready.

## API Endpoints to Test

### GET /api/opportunities/stages
Returns the 6 canonical stages: `scope, validate, deep_research, capability, mvp, first_artifact`

```bash
curl -s http://127.0.0.1:8420/api/opportunities/stages | python3 -m json.tool
```

### POST /api/opportunities/dispatch
Dispatches an opportunity through all 6 stages, creating durable task claims and delegation runs.

```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"id":"test-1","title":"Test Opp","type":"external_revenue"}' | python3 -m json.tool
```

Expect: `results` array with 6 entries, each with `success: true` and non-empty `task_id`, `claim_id`, `run_id`.
Note: `proposal_id` will be empty unless the dispatcher is wired with a TelicSeam instance.

### POST /api/opportunities/refill
Refills an opportunity through all stages, produces a revenue packet.

```bash
curl -s -X POST http://127.0.0.1:8420/api/opportunities/refill \
  -H 'Content-Type: application/json' \
  -d '{"id":"test-2","title":"Test Refill","type":"external_revenue","estimated_value_usd":1000.0}' | python3 -m json.tool
```

Expect: `success: true`, 6 stages, `total_provider_cost_usd: 0.23`, revenue_packet written to `~/.dharma/revenue_packets/`.

## Verifying Durable SQLite State

After dispatch/refill, verify claims persist in SQLite:

```python
import sqlite3
db = sqlite3.connect('/home/ubuntu/.dharma/state/runtime.db')
cur = db.cursor()
cur.execute('SELECT COUNT(*) FROM task_claims WHERE status="claimed"')
print('claims:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM delegation_runs WHERE status="running"')
print('runs:', cur.fetchone()[0])
```

Expect: counts >= 6 per dispatch call.

## Testing Quarantine Mode

Set `DHARMA_RESEARCH_BACKEND=quarantine` on the **server process** (not the curl client):

```bash
DHARMA_RESEARCH_BACKEND=quarantine uvicorn api.main:app --host 127.0.0.1 --port 8420
```

Then POST to `/api/opportunities/refill`. The `deep_research` stage should show:
- `status: "quarantined"`
- `quarantined: true`
- Other stages: `status: "completed"`
- Overall: `success: true`

## Testing Pre-commit Governance

```bash
cd /home/ubuntu/dharma_swarm && source .venv/bin/activate
pre-commit run --all-files
```

All 11 hooks should pass. Semgrep gracefully skips if not installed. Uplift guards handle ImportError for missing pydantic.

## Key Environment Variables

- `DHARMA_STATE_DIR` — override state directory (default: `~/.dharma/state`)
- `DHARMA_RESEARCH_BACKEND` — `stub` (default), `quarantine`, or `auto`
- `DHARMA_WORLD_MODEL_TIMEOUT` — timeout in seconds (default: 900, was hard-coded 300)
- `DHARMA_UPLIFT_ACK=impact-checked` — required for hot-path commits
- `DASHBOARD_API_KEY` — set to enable Bearer auth (unset = dev mode, no auth)

## Common Gotchas

- The `sqlite3` CLI may not be available — always use Python's sqlite3 module for DB inspection
- Quarantine env var must be set on the server process, not the curl client
- GnaniLodestone startup warnings are expected and don't affect opportunity endpoints
- The API endpoint doesn't wire TelicSeam by default, so `proposal_id` will be empty in API responses (telic provenance works when seam is explicitly provided, as proven by pytest)
