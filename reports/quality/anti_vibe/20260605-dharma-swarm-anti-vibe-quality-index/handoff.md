# Anti-Vibe Quality Cleanup Handoff

Generated: 2026-06-05

## Outcome

The six highest-priority cleanup categories now have executable gates rather than narrative claims:

- strict runtime-name gate: `ruff F821,F811`
- deterministic fast test lane: `make test-fast`
- generated/cache quarantine in X-Ray and bounded source scanners
- DocOps count assertions refreshed and auto inventory regenerated
- source-only module coherence inventory
- strict A2A readiness gate that fails closed on live degraded state

## Verification

Passed:

- `./.venv/bin/python -m ruff check --select F821,F811 dharma_swarm api scripts tests`
- `make module-coherence`
  - `status=pass`
  - `scanned_files=839`
  - `family_counts={"adapter": 10, "bridge": 24, "gateway": 1, "orchestrator": 2, "router": 9}`
- `make docops-integrity`
  - DocOps integrity checks passed
  - current key counts: 680 dharma modules, 608 test files, 10,537 test defs, 858 markdown files
- `make verify-quality-membrane`
  - runtime names passed
  - module coherence passed
  - A2A/module contract tests: 17 passed
  - DocOps integrity passed
- `make test-fast`
  - 10,674 passed
  - 32 skipped
  - 23 deselected
  - 7 xfailed
  - 14 xpassed
  - 3 warnings
  - runtime: 264.44s

Strict fail-closed behavior verified:

- `make a2a-score-strict`
  - exit code 2
  - JSON emitted `gate_status: DEGRADED`
  - reason: `open_or_claimed_tasks_present`
  - live pending task: `forge-v0.1-001`

## Main Changes

- Added governance scripts:
  - `scripts/governance/check_a2a_readiness.py`
  - `scripts/governance/check_module_coherence.py`
  - `scripts/governance/verify_quality_membrane.py`
- Added contract tests:
  - `tests/test_a2a_readiness_gate.py`
  - `tests/test_module_coherence_gate.py`
- Wired Make targets:
  - `module-coherence`
  - `a2a-score-strict`
  - `verify-quality-membrane`
- Fixed remaining `F821/F811` runtime-name and duplicate-definition failures across production and tests.
- Hardened X-Ray defaults to skip generated/cache/report surfaces and moved the live full-repo X-Ray smoke out of `test-fast` with `slow`.
- Regenerated DocOps inventory and refreshed `SOVEREIGN_MANIFEST.md` count assertions to 2026-06-05 measured values.
- Kept the large pre-existing dirty/untracked worktree intact; no unrelated cleanup or revert was performed.

## Residual Risk

- `make test-fast` still emits an existing `aiosqlite` event-loop thread warning in `tests/test_verify_api.py`; it does not fail the suite but should be cleaned in a follow-up.
- `tests/test_living_agent_kernel_workers.py::test_stale_worker_recovery_only_requeues_expired_stale_leases` failed once during a full-suite run, then passed isolated, file-level, and on the final full `make test-fast` rerun. Treat as a watch-list flake.
- Live A2A readiness is intentionally degraded until pending task `forge-v0.1-001` is completed, blocked with receipt, or removed through the governed queue lifecycle.

## Next Repair PRs

1. Close or receipt the live pending A2A task so `make a2a-score-strict` becomes green in live state.
2. Fix the `aiosqlite` event-loop shutdown warning in Verify API tests.
3. Convert the module-coherence inventory into an allowlisted consolidation plan for bridge/adapter/router naming, one family at a time.
4. Extend generated-artifact quarantine from X-Ray into GitNexus/retrieval/index tooling if those tools still scan `reports/` and runtime scratch trees.
