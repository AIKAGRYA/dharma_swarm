# LangGraph Parity All-Night Log

## 2026-06-30T15:59:09Z - Phase 0 Baseline Start

- Worktree: `/Users/dhyana/ds_langgraph_parity_20260701`
- Branch: `codex/langgraph-orchestration-parity-20260701`
- Base: `origin/main` at `f84f40344cbdfab9d236239b0d3ec00718e10bf9`
- PR #727 merge `3c2e4a684` is an ancestor of this branch.
- Dirty `agent/magpie-seed` checkout was not used.
- Current target gate: Phase 0 clean baseline.
- Current blockers: baseline commands not yet run; `scripts/governance/spine_dispatch_mode_report.py` not found in initial file scan.
- Files touched this round: this log and `SCOREBOARD.json`.
- Tests run this round: pending.

## 2026-06-30T16:12:53Z - Rounds 1-2 Implementation Slice

- Target gates:
  - Phase 1 deterministic conformance oracle expansion.
  - Phase 2 runtime spine default-on slice.
  - Phase 3 live topology enum/metadata slice.
- Code changes landed:
  - Expanded `default_benchmark_tasks()` from 4 to 26 deterministic cases.
  - Added machine-readable benchmark `case_tags` and required coverage summary.
  - Added `SWARM`, `SUPERVISOR`, and `SUBAGENTS_AS_TOOLS` to `TopologyType`.
  - Wired those topology modes into `Orchestrator.dispatch()` with active-agent, handoff, delegation, checkpoint, and parent graph metadata.
  - Inverted orchestrator dispatch from `DHARMA_SPINE_DISPATCH=1` opt-in to default-on with explicit false-like opt-out values.
  - Added `scripts/governance/spine_dispatch_mode_report.py`; `--strict` now passes on this branch.
  - Stamped run/idempotency/side-effect/topology/planned-provider/actual-provider fields into orchestrator `EvidenceReceipt.attributes`.
- Generated artifacts:
  - `reports/langgraph_parity/benchmark/benchmark_report.json`
  - `reports/langgraph_parity/benchmark/benchmark_report.md`
  - `reports/langgraph_parity/benchmark/benchmark_receipt.json`
- Verification:
  - `make onboard` -> pass after `.venv` exists; first run failed under system `python3` 3.9 before `uv run` created a Python 3.12 venv.
  - `.venv/bin/python -m pytest -q tests/test_langgraph_parity_*.py` -> `20 passed in 0.37s`.
  - `.venv/bin/python -m pytest -q tests/test_orchestrator.py tests/test_orchestrator_spine_dispatch.py tests/test_topology_execution.py tests/test_langgraph_parity_*.py` -> `66 passed in 28.95s`.
  - `.venv/bin/python scripts/governance/spine_dispatch_mode_report.py --strict` -> pass; reports `orchestrator_mode: spine_default_on`.
  - `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=19`, `unknown_status_tasks=2`, `unverified_closed_tasks=19`.
- Current blockers:
  - A2A strict green is blocked by live queue state in `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl`.
  - Full LangGraph parity remains unproven: live restart/resume topology, MemoryKernel live retrieval isolation, full provider served-model truth, and cockpit/API graph inspection are not complete.
- Next target gate:
  - Build live restart/resume topology proof backed by `RuntimeStateStore`, then attack A2A blockers with receipts or operator-approved external closure.
