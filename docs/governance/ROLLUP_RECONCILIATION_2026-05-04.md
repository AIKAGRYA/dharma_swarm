# Phase 2 Rollup Reconciliation

Date: 2026-05-04
Worktree: `/Users/dhyana/dharma_swarm_governance_truth`
Branch: `chore/governance-truth-repairs`
Base checkpoint: `3e5b8d9 fix(governance): restore uplift guard runner`

## Current Brake Truth

- The rollup checkpoint is locally clean and the scheduled brake matrix is green.
- Latest recorded rollup brake exits: collection `0`, semgrep `0`, contract hook `0`, uplift hook `0`, module budget `0`, compileall `0`, diff check `0`, `dgc --help` `0`.
- Pytest collection at the checkpoint is `9192` tests.
- Module budget is passing because known large files are explicitly grandfathered by policy.

## Integration Topology

- `chore/phase2-governance-rollup` is not based on current `origin/main`.
- `git rev-list --left-right --count origin/main...HEAD`: `71 89`.
- Merge base: `45e4700c4e19eecb7c595096ff1a8f6cba5e9f3c`.
- Interpretation: rollup is 89 commits ahead and 71 commits behind `origin/main`; local green is not promotion-ready by itself.

## Brief Seam Conflict

`origin/main` added the Operator Brief seam in PR #57:

- `dharma_swarm/operator_brief/insight_brief.py`
- `dharma_swarm/operator_brief/persistence.py`
- `dharma_swarm/operator_brief/types.py`
- `tests/test_operator_brief_insight_brief.py`

The rollup branch independently carries Daily Insight/Telic seam work:

- `dharma_swarm/insight_brief.py`
- `dharma_swarm/telic_seam.py`
- `tests/test_daily_insight_invariant_chain.py`
- `tests/test_insight_brief.py`
- `tests/test_telic_seam_inquiry.py`

This is the highest-risk semantic fork. Do not add new brief behavior until the project has one canonical brief entrypoint and one persistence/provenance contract.

## Governance Layer Truth

After scanner hardening in this worktree, assurance no longer reports provider-contract noise from adjacent provider/model records or Groq-hosted Llama models.

Current assurance summary:

- `route_contract`: 23 high findings.
- `provider_contract`: 0 findings.
- `storage_path`: 3 medium findings.
- `ownership_audit`: 1 medium finding.
- all other assurance scanners: 0 findings.

The remaining route findings are real contract drift: dashboard API helpers call VSM, catalytic, strange-loop, gates, and cascade endpoints that are not registered in `api/main.py`.

Given the current strategic constraint against dashboard/API expansion, the next move is to classify or fail-close unsupported helpers/surfaces rather than adding backend endpoints.

## Highest ROI Order

1. Reconcile rollup with `origin/main` before new feature work.
2. Choose the canonical Operator Brief/Daily Insight entrypoint and preserve TelicSeam proposal, gate, outcome, value-event, and citation linkage.
3. Keep assurance scanners truthful; treat route findings as contract drift, not parser noise.
4. Classify unsupported dashboard/API projections as inactive or fail-closed instead of expanding product surface.
5. Keep module budget as a reporting brake; do not split `opportunity_dispatcher.py` or `telic_seam.py` during reconciliation.
6. Review `feat/memory-census` only after the rollup/main seam decision is made.

## Non-Goals

- No dashboard/API/product expansion.
- No Operator Brief feature additions before seam reconciliation.
- No memory authority consolidation.
- No ontology/provider/routing consolidation.
- No module splitting.
- No AgentRunner, `telos_gates.py`, or `dharma_kernel.py` changes.
