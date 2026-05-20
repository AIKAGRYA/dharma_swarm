# ADR-0001: Next Seam Candidate — BoardStore Facade

**Status:** Proposed  
**Date:** 2026-05-20  
**Deciders:** @AmitabhainArunachala  
**Track context:** Opened after `cockpit-control-surface-2026-05` reaches SHIPPABLE

---

## Context

The dharma_swarm substrate has two ontology-native seams shipped:

1. **Operator Brief seam** (track `operator-brief-seam-2026-04`, SHIPPED 2026-05-19)
   — The first substrate-native seam. Structured knowledge artifacts produced
   by cron, surfaced via the guardian crew.

2. **Operator Cockpit + Control Surface** (track `cockpit-control-surface-2026-05`)
   — Declared intent vs observed reality reconciliation. ControlSurfaceEnvelope,
   DisplayHints, SSE stream, agent handoff prompts, five-zone dashboard layout.

The next seam must unify the seven existing truth-bearing stores behind a
single facade before `dharma_swarm.client` (the public mutation boundary)
can be built. The spec for this is `docs/architecture/SWARM_BOARDSTORE_SPEC.md`.

## Candidates Evaluated

| Candidate | Benefit | Risk | Readiness |
|---|---|---|---|
| **BoardStore facade** | Unifies 7 stores, enables `dharma_swarm.client`, noticer/doer separation | Large surface area, migration complexity | Spec written (PR #316), all stores exist |
| Training flywheel | Closes the evolution loop (BR-003) | Requires live apply gate open, safety risk | Partial — shadow-apply exercised only |
| Identity unification | Resolves agent contract fragmentation (BR-013) | 8+ surfaces to consolidate | Low — no spec, no ADR |

## Decision

**BoardStore facade** is the next seam candidate.

### Rationale

1. **Spec already written.** `SWARM_BOARDSTORE_SPEC.md` defines the Card schema,
   event log, participation boundary, noticer/doer separation, cost-cap semantics,
   and 5-step migration plan. No other candidate has an implementation contract.

2. **Unblocks the most downstream work.** `dharma_swarm.client`, the kanban view,
   Telegram push, cost-cap enforcement, and multi-agent task coordination all
   require the board facade to exist.

3. **Lowest safety risk.** The facade wraps existing stores behind compatibility
   adapters with rollback semantics. Unlike the training flywheel, it does not
   require opening the live evolution gate.

4. **Seven stores already work.** TaskBoard, OperatorBridge, RuntimeStateStore,
   RoamingMailbox, ControlSurface, IntentRouter+MissionState, and
   AutoProposer+recursive_discovery are all tested and running. The facade
   adds a unified read/write surface, not new state.

## Consequences

- A new active track (`boardstore-facade-2026-05` or similar) will be opened
  once `cockpit-control-surface-2026-05` flips SHIPPABLE.
- Implementation follows the 5-step migration plan in the spec:
  1. Scaffold facade package (no call-path changes)
  2. Add Card + event-log schema behind adapters
  3. Adapt TaskBoard first, then remaining stores
  4. Add `dharma_swarm.client` after facade lifecycle tests pass
  5. Cut over one store at a time with compatibility wrappers
- The training flywheel (BR-003) and identity unification (BR-013) remain
  future candidates, addressed after the board facade ships.
- The noticer/doer boundary is a hard architectural constraint from day one —
  not a feature to be added later.

## Non-Goals of This ADR

- This ADR does not implement anything. It declares the next seam.
- It does not retire or close the cockpit track.
- It does not open a third concurrent seam.

## References

- `docs/architecture/SWARM_BOARDSTORE_SPEC.md` — full implementation contract
- `docs/state/BROKEN_REGISTER.md` — BR-003 (evolution gate), BR-013 (identity)
- `docs/governance/ACTIVE_TRACK.yaml` — track lifecycle
