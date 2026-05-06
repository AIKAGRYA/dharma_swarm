# Hypernode — Empty Quadrant Revenue Cell

## Problem

The `governance × welfare` quadrant of the dharma ontology had no concrete revenue
hypothesis attached to it. Every other quadrant pointed to a candidate cell
(research, infra, content, ops); this one was empty. That gap meant the system
could not propose a coherent revenue path that simultaneously honored governance
constraints (telos gates, axioms) and the welfare telos (Jagat Kalyan).

## Architecture

The hypernode is a deterministic, gate-checked seed of one revenue cell:

- `dharma_swarm/hypernode.py` — `HypernodePayload`, `RevenueCellPayload`,
  `CouncilVerdictPayload`, `FitnessVectorPayload`. Builds the empty-quadrant
  payload from frozen quorum participants, scores it through `AutoGradeEngine`,
  and runs the result through `TelosGatekeeper` + `evaluate_anekanta`.
- `dharma_swarm/hypernode_ontology.py` — typed link specs binding the hypernode
  into the ontology graph (revenue cell → council verdict → fitness vector →
  contribution chain).
- `dharma_swarm/hypernode_seed.py` — `ensure_empty_quadrant_hypernode(registry)`
  idempotently inserts all hypernode objects + typed links into the ontology
  registry. Re-runs are no-ops.
- `dharma_swarm/opportunity_dispatcher_observer.py` — observer extracted from
  `opportunity_dispatcher` so the hypernode payload can be rendered without
  triggering dispatch side effects.
- `api/routers/hypernodes.py` — `GET /api/hypernodes/empty-quadrant`. Calls the
  seed function on first hit and returns the canonical payload.
- `dashboard/src/app/dashboard/hypernodes/` — read-only Next.js page rendering
  `HypernodePayload` (quadrants, provenance, council verdict, fitness vector,
  revenue cell, typed links).
- `dashboard/src/hooks/useEmptyQuadrantHypernode.ts` — typed client hook.

## API Contract

```
GET /api/hypernodes/empty-quadrant → ApiResponse[HypernodePayload]
```

`HypernodePayload` keys: `hypernode_id`, `slug`, `quadrants`, `provenance`,
`council`, `fitness`, `revenue_cell`, `typed_links`. Schema lives in
`dharma_swarm/hypernode.py:119` and is mirrored in
`dashboard/src/lib/types.ts`.

## Status

- 6/6 tests passing in `tests/test_hypernode.py` — covers payload determinism,
  council verdict gate, fitness scoring, ontology seed idempotency, router
  contract, and opportunity-dispatcher-observer extraction.
- Ontology registry tests (60/60) green with hypernode integration.
- Dashboard page renders against fixture data.

## Next Gate

Hook the empty-quadrant payload into a live revenue surface (consulting page,
carbon-credit landing, geometric_lens artifact). The hypernode currently models
the cell; the next commit shipping a public artifact moves it from
`proposed` → `executing`.
