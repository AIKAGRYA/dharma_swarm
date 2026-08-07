# ADR-011: Operator Actions Through TaskBoard

> **Date:** 2026-08-07
> **Status:** PROPOSED (awaiting operator ratification)
> **Decision:** Operator actions that change work state MUST use TaskBoard command paths. They MUST NOT mutate work state by publishing directly to NATS. Free-text chat may use A2A directly, but consequential state changes require TaskBoard authority, transition validation, claim leases, cost ceilings, Telos gates, and the receipt trail.

---

## Context

The Fleet Command phone surface is an operator client, not a second task authority. The repository already identifies TaskBoard as canonical and BoardStore as a projection (`api/main.py:188-203`; `dharma_swarm/board/adapters/agentops_adapter.py`). A direct NATS publish from the UI would bypass:

- Telos gates;
- TaskBoard transition validation;
- claim leases;
- cost ceilings;
- optimistic concurrency;
- runtime receipt and witness evidence.

That bypass would create a phone-shaped hole through the governance layer. A publish ACK is not proof of handler contact or semantic completion.

## Decision

All operator actions that alter work state follow:

```text
Phone / dashboard
  -> authenticated OperatorIntent
  -> TaskBoard command path
  -> transition validation + Telos / lease / cost policy
  -> canonical TaskBoard result
  -> BoardStore/dashboard projection
  -> A2A dispatch and receipt where required
```

The UI renders the returned verdict. It does not optimistically display a state that the command path has not accepted. A Telos BLOCK, lease conflict, cost violation, or invalid transition is visible with its reason.

Free-text chat remains allowed over A2A directly when it does not mutate work state. Chat-derived consequential intent must be converted into the same TaskBoard command path before changing a Card or task.

## Consequences

### Positive

- One authoritative work-state transition path.
- Telos gates, leases, cost ceilings, idempotency, and receipts remain in force.
- Dashboard and phone surfaces cannot silently diverge from TaskBoard.
- Direct A2A chat remains available without turning chat into an ungoverned mutation channel.

### Negative

- Phone actions incur TaskBoard command and projection latency.
- The client must represent rejected transitions and governance blocks rather than assuming optimistic success.
- Some chat interactions require an explicit conversion into an OperatorIntent or task command.

### Neutral

- BoardStore remains useful as the dashboard projection and event surface.
- The chosen NATS stream remains a separate open topology decision; this ADR does not select `DHARMA_A2A` or `DS_*`.

## Enforcement

- `dharma_swarm/task_board.py:175-203` validates transitions.
- `dharma_swarm/task_board.py:212-230` applies the reflective Telos checkpoint and raises on a block.
- `api/main.py:188-203` keeps TaskBoard canonical while BoardStore is a shadow projection.
- `dharma_swarm/board/facade.py:145-200` applies optimistic concurrency and audit events to projections.

Future phone/API command surfaces must call these owners or an explicitly equivalent command adapter. Direct NATS work-state writes from the operator surface are non-conforming.

## Options considered

| Option | Verdict |
|---|---|
| Direct NATS publish for every phone action | ✗ bypasses TaskBoard authority, Telos, leases, cost ceilings, and receipts |
| Make BoardStore/dashboard the new authority | ✗ creates a parallel task authority while TaskBoard remains canonical |
| **TaskBoard command path for state changes; direct A2A only for free-text chat (CHOSEN)** | ✓ preserves existing authority and keeps chat available |

## Related decisions

- `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md`
- `docs/architecture/ADRs/ADR-012-canonical-fleet-roster.md`
- `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md`
- `api/main.py:188-203`
- `dharma_swarm/task_board.py:175-230`

## Status history

- **2026-08-07** — PROPOSED on the Fleet Command operator-surface branch; operator ratification by merge remains pending.
