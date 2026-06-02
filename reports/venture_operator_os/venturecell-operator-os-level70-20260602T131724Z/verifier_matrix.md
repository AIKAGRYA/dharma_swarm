# VentureCell Operator OS Verifier Matrix

Run: `venturecell-operator-os-level70-20260602T131724Z`

| Gate | Command | Result |
|---|---|---|
| Opening ritual | `make onboard` | pass |
| Toolbelt | `bash scripts/runtime/codex_toolbelt_status.sh` | pass with optional credential warnings |
| Long harness scaffold | `make long-harness-init RUN_ID=venturecell-operator-os-level70-20260602T131724Z MODE=brownfield RISK=Q2 MAX_ROUNDS=4 ...` | pass |
| Projection package compile | `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os` | pass |
| Operator OS projection | `pytest -q tests/test_venture_cell_operator_os_projection.py` | pass, 5 tests |
| Quiet renderer | `./.venv/bin/python -m dharma_swarm.venture_cell.operator_os.cli --output-dir reports/venture_operator_os/venturecell-operator-os-level70-20260602T131724Z` | pass, wrote 3 artifacts with no warning |
| External-reader/control-surface gate | `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'` | pass, 11 tests |
| Governed/A2A/daily brief | `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py` | pass, 31 tests |
| Context+ static analysis | `run_static_analysis(target_path="dharma_swarm/venture_cell/operator_os")` | tool failed: eslint `--eslintrc` option and py_compile missing filename arguments |
| GitNexus impact | `impact(build_operator_projection/build_memory_kernel_snapshot/render_operator_daily_digest)` | index could not resolve active Operator OS symbols |
| GitNexus analyze | `npx gitnexus analyze` | nonzero, incremental summary only; active checkout still absent from `list_repos` |

Interpreter note: the task lane's broad command `python3 -m pytest tests -q --tb=short` was not used as acceptance evidence because this machine's `python3` lacks pytest. Focused verification used the repo's working `pytest` entrypoint and `./.venv/bin/python` for module execution.
