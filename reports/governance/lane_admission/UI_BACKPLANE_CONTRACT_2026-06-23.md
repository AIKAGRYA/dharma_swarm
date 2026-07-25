# UI ⇄ Backplane Contract — 2026-06-23

## One rule

The UI lane (other Fugu) RENDERS truth labels; it does not DERIVE them. All canonicality, proof-state, and production verdicts come from the backplane.

## Lane boundary (non-overlap)

UI Fugu owns (do not let backplane edit without coordination):
- `dashboard/src/app/dashboard/cockpit/**`
- `dashboard/src/components/operator-coherence/**`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`

Backplane Fugu owns:
- truth/admission semantics + schemas (this folder, `reports/governance/lane_admission/**`)
- production-readiness integration (`reports/governance/prod_readiness/**`)
- the generator's *data contract* in `dharma_swarm/operator_core/operator_coherence_cockpit.py`, `scripts/runtime/operator_coherence_cockpit.py`, `api/routers/operator_coherence.py` (coordinate before editing — these currently sit in the same dirty lane as the UI)

## Fields the UI must be able to consume

Per card, the backplane will supply (extends current `operator_coherence_cockpit.v0.1` card):
- existing: `id, kind, lane, status, risk, decision_type, title, next_action, facets, evidence, branch, pr, track`
- added: `canonicality` (taxonomy label), `proof_state` (LIVE/STATIC/STALE/INFERRED/CONTRADICTED), and for track cards `{checker_status, production_verdict, closure_risk, blocking_followups[]}`

## Display defaults (severity mapping)

- `CANONICAL_ORIGIN_MAIN` -> neutral/green
- `DIRTY_LOCAL_CANDIDATE`, `LOCAL_ONLY_BRANCH`, `UNPUSHED_LOCAL_BRANCH`, `STASHED_PRESERVED`, `OFF_REPO_ARTIFACT` -> amber "candidate"
- `ORPHANED_UPSTREAM_GONE` -> red
- `UNAVAILABLE_UNCERTAIN` -> grey "uncertain", never coerced to pass/fail
- `CONTRADICTED` proof_state -> red conflict badge
- `STALE_RECEIPT` -> amber "stale"

## Mandatory self-labeling

The cockpit's own `track_portfolio` panel MUST show a banner: "generated from DIRTY checkout — local 11/max11, not canonical origin/main 7/max10" until the generator runs from a clean worktree. This prevents the dashboard from presenting dirty truth as canonical.

## Uncertainty rendering

`source_errors` (gh auth, tmux, ps, launchctl) MUST appear as explicit uncertainty cards/panels, not be silently dropped. Current run has 4 source_errors.
