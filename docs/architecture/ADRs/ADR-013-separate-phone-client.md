# ADR-013: Separate Lightweight Phone Client

> **Date:** 2026-08-07
> **Status:** PROPOSED (operator decision recorded; ratification by merge pending)
> **Decision:** Build Fleet Command as a separate lightweight phone client over the shared API and canonical runtime surfaces. Do not extend DHARMA COMMAND for the first phone iteration.

---

## Context

The Fleet Command design accepts the thin-client reframe: the operator surface renders and commands existing A2A, TaskBoard, roster, presence, governance, and receipt owners rather than creating parallel state (`docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:42-57`). The architecture document records the accepted reframe and live topology.

DHARMA COMMAND already provides the cockpit and broad operator panels (`docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:70-71`). The phone surface has different interaction and layout constraints. Keeping it separate allows phone iteration without destabilizing the cockpit while preserving a shared API and canonical owners.

## Decision

The first Fleet Command client is a separate lightweight phone client. It:

- uses the shared authenticated API (`api/main.py:234-239`);
- renders TaskBoard/BoardStore projections and runtime evidence (`api/main.py:188-203`);
- issues consequential changes through TaskBoard command paths (`docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md`);
- consumes canonical A2A, presence, governance, and receipt surfaces (`docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:154-242`);
- does not create a phone-owned roster, board, envelope, or authority layer.

DHARMA COMMAND remains the cockpit and is not refactored into the phone client as part of this decision.

## Consequences

### Positive

- Phone interaction can iterate without destabilizing the cockpit.
- The client remains thin because state and authority stay in existing owners.
- A separate surface can optimize for objectives, exceptions, and background/mobile delivery.

### Negative

- Some presentation code is duplicated.
- Shared API contracts and evidence semantics must remain compatible across two clients.
- Authentication, reply visibility, and JetStream metadata permissions remain hard dependencies for a useful phone surface.

### Neutral

- ADR-011 still governs consequential work-state mutations.
- ADR-012 still governs identity and routing ownership.

## Enforcement

- `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md` records the separate-client choice and the remaining open decisions.
- `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md` governs consequential work-state mutations.
- `docs/architecture/ADRs/ADR-012-canonical-fleet-roster.md` governs identity and routing ownership.

## Options considered

| Option | Verdict |
|---|---|
| Extend DHARMA COMMAND for the first phone surface | ✗ risks destabilizing the cockpit while phone interaction iterates |
| **Separate lightweight phone client over shared API (CHOSEN)** | ✓ isolates phone iteration while preserving canonical owners |
| Build a parallel phone-owned board, roster, or message protocol | ✗ violates the thin-client boundary and creates competing authority |

## Related decisions

- `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md`
- `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md`
- `docs/architecture/ADRs/ADR-012-canonical-fleet-roster.md`
- `dashboard/src/app/dashboard/cockpit/page.tsx`

## Status history

- **2026-08-07** — Proposed with the operator's separate-client decision recorded; ratification by merge remains pending.
