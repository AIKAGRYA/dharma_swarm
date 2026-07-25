# Consolidation Receipt

- UTC: 2026-07-01T15:08:33Z
- worktree: `/Users/dhyana/ds_langgraph_prod_candidate_20260702`
- branch: `codex/langgraph-prod-candidate-20260702`
- base: `origin/main` at `a4610e585d0cf92c4155e4e0ef417bdb4b82e866`
- merged_source: `codex/langgraph-orchestration-parity-20260701` at `0720fdfaccc4edd2ff756bf5fcbcb1e0f326ab9b`
- merge_commit_before_receipt: `9e3dcd8d79133cbc33810193193249fb24af844e`
- candidate_status: CANDIDATE_ACTIVE_TRACK

## What This Did

Created a new clean worktree from current `origin/main`, merged the full LangGraph parity lane, and recorded the candidate active-track package under:

`reports/langgraph_parity/prod_candidate_20260702/`

## What Was Not Merged

The NATS live production proof commit `ca297f584f9d2aa77191098403b28eccc780bb98` was tested as a cherry-pick and then aborted because it conflicted in governance/runtime surfaces. The worktree was returned to a clean non-conflicted state before this receipt was written.

Conflict paths:

- `Makefile`
- `docs/governance/ACTIVE_TRACK.yaml`
- `reports/governance/active_track_evidence.json`
- `reports/governance/track_portfolio.json`
- `scripts/runtime/a2a_send.py`
- `tests/test_nats_substrate_contract.py`
- `tests/test_nats_transport.py`

## Verification

Commands were run from this candidate worktree using the existing parity worktree venv because the new worktree does not have its own `.venv` yet.

```text
/Users/dhyana/ds_langgraph_parity_20260701/.venv/bin/python scripts/docops/check_docops_integrity.py --write-auto-sections --write-manifest-counts
DocOps integrity checks passed

/Users/dhyana/ds_langgraph_parity_20260701/.venv/bin/python -m pytest -q tests/test_runtime_live_cockpit_probe.py tests/test_runtime_graph_api.py --tb=short
9 passed in 6.03s

/Users/dhyana/ds_langgraph_parity_20260701/.venv/bin/ruff check scripts/verify/runtime_live_cockpit_probe.py tests/test_runtime_live_cockpit_probe.py
All checks passed

/Users/dhyana/ds_langgraph_parity_20260701/.venv/bin/python -m compileall -q scripts/verify/runtime_live_cockpit_probe.py tests/test_runtime_live_cockpit_probe.py
passed
```

## Residual Work

- Push this candidate branch.
- Open or update a PR that supersedes #732.
- Install/create a local `.venv` in this worktree or verify through CI.
- Decide whether the NATS proof is a dependency, sibling track, or out-of-scope.
- Add browser-driven dashboard proof before production-ready promotion.
