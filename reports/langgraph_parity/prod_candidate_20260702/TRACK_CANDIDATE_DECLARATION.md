# LangGraph Runtime Production Candidate Declaration

- UTC: 2026-07-01T15:08:33Z
- status: CANDIDATE_ACTIVE_TRACK
- worktree: `/Users/dhyana/ds_langgraph_prod_candidate_20260702`
- branch: `codex/langgraph-prod-candidate-20260702`
- base: `origin/main` at `a4610e585d0cf92c4155e4e0ef417bdb4b82e866`
- parity_source: `codex/langgraph-orchestration-parity-20260701` at `0720fdfaccc4edd2ff756bf5fcbcb1e0f326ab9b`
- consolidation_head: `9e3dcd8d79133cbc33810193193249fb24af844e`
- prior_pr: `https://github.com/AmitabhainArunachala/dharma_swarm/pull/732`

## Answer

Before this consolidation, the latest LangGraph parity lane lived in one clean local worktree:

`/Users/dhyana/ds_langgraph_parity_20260701`

That worktree was clean and pushed, but its PR was no longer cleanly mergeable because `origin/main` advanced. GitHub reported PR #732 as `CONFLICTING`.

This new worktree is the current canonical local candidate:

`/Users/dhyana/ds_langgraph_prod_candidate_20260702`

It is based on current `origin/main` and contains the full parity branch merged on top of that newer main. The merge completed with no conflicts.

## Score Framing

- Local executable parity gate: 100/100, as recorded by the all-night scoreboard and proof receipts.
- Full production readiness: 0/100 until this candidate is pushed, reviewed, CI-verified, and either merged or superseded by an explicit operator decision.

The 0/100 production score is not a claim that the code has no value. It means it is not production truth until it is on a mergeable branch with CI signal, dashboard/browser proof, and resolved adjacent runtime/NATS evidence.

## Candidate Track

This branch intentionally does not edit `docs/governance/ACTIVE_TRACK.yaml` yet. It declares itself as a candidate active track because:

- it owns broad runtime, dashboard, API, MemoryKernel, provider-truth, and A2A readiness surfaces;
- the prior PR is draft and conflicting;
- adjacent NATS production evidence conflicts with current main and needs operator choice before being folded in;
- production readiness needs browser-driven and live-runtime hardening beyond the local API proof.

Suggested track id if promoted:

`langgraph-runtime-prod-20260702`

Suggested spine objective:

`substrate-nativeness`

Owned surfaces:

- `api/routers/runtime.py`
- `dashboard/src/app/dashboard/runtime/page.tsx`
- `dashboard/src/lib/runtimeControlPlane.ts`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_*`
- `dharma_swarm/memory_kernel/**`
- `dharma_swarm/model_status.py`
- `scripts/verify/runtime_live_cockpit_probe.py`
- `reports/langgraph_parity/**`

Promotion rule:

Promote to ACTIVE only after the operator accepts this worktree as the single continuation branch and decides whether the adjacent NATS production proof is a dependency, sibling track, or out-of-scope evidence lane.
