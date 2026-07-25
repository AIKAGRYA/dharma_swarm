---
name: testing-opportunity-loop
description: Test the Authority and Revenue Loop Gauntlet end-to-end. Use when verifying opportunity dispatch/refill API endpoints, durable runtime state, telic provenance, economic telemetry, or governance checks.
---

# Testing the Opportunity Dispatch/Refill Pipeline

**Purpose:** prove the Authority & Revenue loop end-to-end — dispatch and refill endpoints run all six stages, write durable task claims and delegation runs to sqlite, and emit a revenue packet with coherent economics. This is the loop that eventually touches real revenue, so "the endpoint returned 200" is never the bar: durable state and packet contents are.

## Prerequisites

- Repo-root working dir: `cd "$(git rev-parse --show-toplevel)"`, then `source .venv/bin/activate` (or `python3 -m pip install -e ".[dev]"` + `pre-commit`).
- No secrets in dev mode — auth middleware is open when `DASHBOARD_API_KEY` is unset; set it only to test Bearer auth deliberately.
- The `sqlite3` CLI is often not installed — use Python's `sqlite3` module for all DB inspection.
- Use an isolated state dir so assertions are exact and `~/.dharma` stays clean: `export DHARMA_STATE_DIR="$PWD/.e2e_state/opportunity-loop"`.

## Procedure

### 1. Pytest suite

```bash
python -m pytest tests/test_authority_revenue_loop.py -v
```

Expect all tests green except the documented pre-existing skip (orphan ValueEvent test skips when the ontology schema doesn't support direct creation). Any *new* failure or skip vs a clean-baseline run is a finding.

### 2. Start the API server

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8420
```

Ready when it prints `Application startup complete`. GnaniLodestone seeding warnings are expected and non-blocking.

### 3. Exercise the endpoints

```bash
# Stages — must be exactly, in order:
# scope, validate, deep_research, capability, mvp, first_artifact
curl -s http://127.0.0.1:8420/api/opportunities/stages | python3 -m json.tool

# Dispatch
curl -s -X POST http://127.0.0.1:8420/api/opportunities/dispatch \
  -H 'Content-Type: application/json' \
  -d '{"id":"test-1","title":"Test Opp","type":"external_revenue"}' | python3 -m json.tool

# Refill
curl -s -X POST http://127.0.0.1:8420/api/opportunities/refill \
  -H 'Content-Type: application/json' \
  -d '{"id":"test-2","title":"Test Refill","type":"external_revenue","estimated_value_usd":1000.0}' | python3 -m json.tool
```

Dispatch pass criteria: `results` array with exactly 6 entries, each `success: true` with non-empty `task_id`, `claim_id`, `run_id`. Known gap, not a bug: `proposal_id` is empty unless the dispatcher is wired with a TelicSeam instance (telic provenance is proven by the pytest suite, not the API path).

Refill pass criteria: `success: true`; 6 stages; `total_provider_cost_usd` present, numeric, > 0 (do NOT assert an exact figure — pricing constants change); `total_net_value_usd == estimated_value_usd - total_provider_cost_usd`; revenue packet written under `~/.dharma/revenue_packets/` (or the state-dir equivalent) containing the opportunity id.

### 4. Verify durable sqlite state

```python
import sqlite3, os
db = sqlite3.connect(os.path.expandvars("$DHARMA_STATE_DIR/runtime.db"))
cur = db.cursor()
cur.execute("SELECT COUNT(*) FROM task_claims WHERE task_id LIKE ?", ("%test-1%",))
cur.execute('SELECT COUNT(*) FROM task_claims WHERE status="claimed"'); print("claims:", cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM delegation_runs WHERE status="running"'); print("runs:", cur.fetchone()[0])
```

Expect ≥ 6 claims and ≥ 6 runs per dispatch call, and filter by your test opportunity id when the table has prior rows.

### 5. Quarantine mode

Set the env var on the **server process**, not the curl client:

```bash
DHARMA_RESEARCH_BACKEND=quarantine uvicorn api.main:app --host 127.0.0.1 --port 8420
```

POST a refill; expect the `deep_research` stage to show `status: "quarantined"`, `quarantined: true`, all other stages `completed`, overall `success: true`.

### 6. Pre-commit governance

```bash
pre-commit run --all-files
```

All hooks should pass; semgrep gracefully skips when not installed; uplift guards tolerate missing pydantic.

## Key Environment Variables

- `DHARMA_STATE_DIR` — state dir override (default `~/.dharma/state`); always override for tests
- `DHARMA_RESEARCH_BACKEND` — `stub` (default) / `quarantine` / `auto`
- `DHARMA_WORLD_MODEL_TIMEOUT` — seconds (default 900)
- `DHARMA_UPLIFT_ACK=impact-checked` — required for hot-path commits
- `DASHBOARD_API_KEY` — set ⇒ Bearer auth on; unset ⇒ dev mode

## Output Format

```
OPPORTUNITY LOOP VERDICT: PASS | FAIL
- pytest suite:      <N passed, M skipped> (delta vs baseline: <none | ...>)
- stages endpoint:   <ok | got ...>
- dispatch:          <6/6 success | what diverged>   sqlite: <claims/runs counts>
- refill:            <ok; cost=<x>, net=<y>, packet=<path> | what diverged>
- quarantine mode:   <ok | what diverged>
- pre-commit:        <all hooks pass | failures>
```

## Do NOT

- Do not assert exact cost constants (e.g. a remembered `0.23`) — assert presence, numeric type, and the net-value arithmetic instead.
- Do not run against the real `~/.dharma/state/runtime.db` — isolated `DHARMA_STATE_DIR` only, and never commit `.e2e_state/` or any runtime receipt.
- Do not set quarantine env vars on the curl side and conclude the feature is broken.
- Do not treat an HTTP 200 as pass without checking durable rows and packet contents.
- Do not leave the uvicorn server running when done.
