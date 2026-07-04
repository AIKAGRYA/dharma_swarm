# Related Work Magnetization Ledger

- UTC: 2026-07-01T15:08:33Z
- candidate_worktree: `/Users/dhyana/ds_langgraph_prod_candidate_20260702`
- candidate_branch: `codex/langgraph-prod-candidate-20260702`

## Included

### Current Main

- source: `origin/main`
- sha: `a4610e585d0cf92c4155e4e0ef417bdb4b82e866`
- reason: latest remote main, including PR #741 final-boss governance and the current repository baseline.

### LangGraph Orchestration Parity

- source: `codex/langgraph-orchestration-parity-20260701`
- sha: `0720fdfaccc4edd2ff756bf5fcbcb1e0f326ab9b`
- prior_pr: `https://github.com/AmitabhainArunachala/dharma_swarm/pull/732`
- merge_result: clean merge into candidate branch.
- essence: runtime-state-backed LangGraph parity, runtime cockpit/API surfaces, MemoryKernel hardening, provider-truth receipts, A2A readiness closure, dashboard runtime controls, and live cockpit proof.

Key proof:

- `scripts/verify/runtime_live_cockpit_probe.py`
- `tests/test_runtime_live_cockpit_probe.py`
- `reports/langgraph_parity/allnight/runtime_live_cockpit_probe_20260701T080204Z.json`
- `reports/langgraph_parity/allnight/SCOREBOARD.json`

## Related But Not Merged

### Runtime Truth NATS Live Evidence

- local_source: `codex/runtime-truth-nats-live-evidence-20260701`
- local_sha: `ca297f584f9d2aa77191098403b28eccc780bb98`
- remote_source: `origin/agent/magpie-seed`
- remote_sha: `44305a99e12bf3d20f6aa51ae7dfe3d6ce2e6964`
- reason_not_merged: cherry-pick conflicted with current main and the candidate branch.

Conflict paths observed:

- `Makefile`
- `docs/governance/ACTIVE_TRACK.yaml`
- `reports/governance/active_track_evidence.json`
- `reports/governance/track_portfolio.json`
- `scripts/runtime/a2a_send.py`
- `tests/test_nats_substrate_contract.py`
- `tests/test_nats_transport.py`

Decision needed:

Treat NATS live production evidence as one of:

1. dependency of `langgraph-runtime-prod-20260702`;
2. sibling active track under runtime truth;
3. out-of-scope proof lane that should not block LangGraph productionization.

### Whole Magpie Branch

- source: `origin/agent/magpie-seed`
- reason_not_merged: too broad for this consolidation. Diff against current main spans more than 1,200 files and includes Magpie, IdeaSpark, rescue, product, and holon work outside the LangGraph runtime parity lane.

### Other Open PRs

Open PR scan on 2026-07-01 showed PR #732 as the relevant LangGraph branch. Other open PRs were either unrelated, already separate product/governance tracks, or conflicting non-LangGraph lanes:

- #742 verifier-ranker spike: related to future verification but not runtime parity.
- #740 cybernetic ratchet evidence gates: governance-adjacent, not runtime parity.
- #738 agentic design patterns: research ingestion, not runtime parity.
- #737/#736 metabolization/vector guard: repo hygiene, not runtime parity.
- #734 forge production contracts: adjacent production harness, conflicting, separate lane.
- #723 routing canon: model-routing adjacent, conflicting, separate lane.

## Result

This worktree is the clearest single continuation point for LangGraph runtime parity. It contains current main plus the full PR #732 parity bundle. It deliberately does not hide the NATS conflict by choosing one governance projection over another.
