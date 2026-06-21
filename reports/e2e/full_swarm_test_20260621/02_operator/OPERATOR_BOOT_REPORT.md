# Operator Boot Report — Phase 2

## Result

- Degraded/pass: FastAPI backend did boot and API endpoints responded, but canonical `run_operator.sh --background` reported failure because `lsof` is not installed in this environment.
- Evidence: `operator_start.txt` says `Operator failed to stay up`; `operator_readiness_bug_evidence.txt` shows `bash: lsof: command not found`, a live uvicorn PID, and successful `/api/health`.

## Endpoint assertions

- `/api/health`: HTTP 200, status `ok`, overall `unknown`.
- `/api/overview`: HTTP 200, agents `14`, tasks `4`, health `unknown`.
- `/api/control-surface/summary`: total `None`, bound `None`, partial `None`, drifted `None`, declared_only `None`, unknown `None`, human decisions `None`.
- `/api/control-surface/rows`: row payload captured; rows with inline `source_errors`: `0`.
- `/api/control-surface/stream`: bytes captured in `api_control_surface_stream.txt`.
- Card endpoints: ds-goal, agentops, a2a, semantic-receipts all returned HTTP 200.

## Task lifecycle assertion

- Created API task: `Deep E2E Darshan first-reader mission`; response status `ok` with id `95bdd3e3eeb143dd`.
- Dispatch response: `{'status': 'ok', 'data': {'dispatched': 5}, 'error': '', 'timestamp': '2026-06-21T13:52:02.469091'}`.
- `/api/commands/tasks` after create/dispatch returned `5` tasks.

## Restart assertion

- Before restart task count: `5`.
- After restart task count: `10`.
- Finding: task count doubled after restart, suggesting startup seeds/rehydrates tasks again instead of preserving a stable non-duplicated task view.

## Raw evidence files

- `operator_start.txt`
- `operator_boot_failure_log.txt`
- `operator_readiness_bug_evidence.txt`
- `operator_api_summary.json`
- `api_*` endpoint payloads
- `restart_*` payloads
- `operator_log_first200.txt`, `operator_log_last200.txt`, `operator_log_after_restart_tail200.txt`
