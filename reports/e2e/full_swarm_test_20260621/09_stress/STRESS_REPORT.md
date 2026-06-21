# Stress Report — Phase 9

## Result

- Backend restart: old PID(s) `[65249, 82846]` were terminated; new PID `82888` reached `/api/health`.
- Task count continuity: before restart `10`, after restart `10`.
- Malformed/bad input statuses: `{'commands_task_empty': 422, 'commands_task_bad_type': 422, 'opportunities_dispatch_missing_id': 200, 'opportunities_refill_missing_id': 422, 'control_surface_bad_lookup': 404}`.
- Concurrent probe statuses: `[200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200]`.

## Findings

- Restart recovery passed if `/api/health` is 200 in `after_restart_endpoints.json`.
- Bad input behavior is mixed: any HTTP 200 in `malformed_input_responses.json` for missing required fields is degraded/failure evidence.
- Concurrent probes returned within timeout; see `concurrent_probe_results.json`.
- Process table after stress is in `backend_pids_after_stress.json`.

## Raw evidence

- `backend_pids_before_restart.json`, `backend_pids_after_kill.json`, `backend_restart_pid.txt`, `backend_pids_after_stress.json`
- `before_restart_endpoints.json`, `after_restart_endpoints.json`
- `malformed_input_responses.json`
- `concurrent_probe_results.json`
- `restart_uvicorn.log`, `restart_log_first_last.txt`
