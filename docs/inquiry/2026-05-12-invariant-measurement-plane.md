# Invariant Measurement Plane Seed

Status: under_chew
Date: 2026-05-12

## Claim

The system should not introduce `gplot.py` as a new authority. The load-bearing
object is a read-only invariant measurement plane that asks whether Dharma
Swarm's recursive transition networks, gates, external outcomes, and evolution
signals are stable under perturbation.

Gplot is a projection of these measurements, not the control plane itself.

## Repo Anchors

- `dharma_swarm/operator_core/invariant_measurements.py` computes v0 readings.
- `dharma_swarm/telemetry_plane.py` owns `external_outcomes` and `workflow_scores`.
- `dharma_swarm/invariants.py` owns existing health invariants.
- `dharma_swarm/landscape.py`, `archive.py`, `selector.py`, and `rv.py` are future measurement inputs.
- `dharma_swarm/viz_projection.py` is the current read projection.
- `dharma_swarm/loop_supervisor.py` is the future warning consumer after evidence exists.

## V0 Boundary

V0 is deliberately modest:

- no new database
- no new dashboard island
- no new gate
- no task routing authority
- no arbitrary shell health checks

It reads existing telemetry and reports:

- recursive-transition anchor coverage
- external-outcome coverage
- external-outcome trend slopes
- workflow-score trend slopes

## Promotion Gate

The plane can become operationally consequential only after it predicts real
failures or improvements better than baseline. Before that, it is evidence, not
authority.

Minimum promotion evidence:

- enough externally-grounded outcome rows to avoid pure self-reference
- predeclared prediction windows
- false-positive review
- operator approval before any supervisor alert becomes blocking

