"""BoardStore facade — unified read/write surface over seven stores.

This is the entry point for all board operations. It coordinates:
- Card CRUD via store adapters
- Lease management (claim, heartbeat, release, expire)
- Event log recording
- Optimistic concurrency (version checks)
- Cost-cap enforcement
- Noticer/doer boundary (write path always goes through here)

The facade does NOT own domain truth. Each store adapter owns its truth.
The facade owns: coordination, audit, identity mapping, and the event log.
"""

from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal

from dharma_swarm.board.event_log import BoardEvent, BoardEventLog
from dharma_swarm.board.models import (
    AuditEntry,
    Card,
    CardId,
    CardStatus,
    EventId,
    IsoDatetime,
    ObjectiveId,
    SourceSurface,
    Version,
)

logger = logging.getLogger(__name__)


def _now() -> IsoDatetime:
    return IsoDatetime(time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))


def _new_id(prefix: str = "card") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _trace_kwargs(trace_id: str, trace_id_source: str) -> dict[str, str]:
    if not trace_id and not trace_id_source:
        return {}
    return {
        "trace_id": trace_id,
        "trace_id_source": trace_id_source or "operator_supplied",
    }


class VersionConflictError(Exception):
    """Raised when a write conflicts with the current card version."""


class CostCeilingExceededError(Exception):
    """Raised when an operation would exceed the card's cost ceiling."""


class BoardStoreFacade:
    """Unified facade over seven truth-bearing stores.

    In this initial scaffold, the facade manages an in-memory card registry
    and the append-only event log. Store adapters will be wired in Step 3
    of the migration plan.
    """

    def __init__(self, event_log: BoardEventLog | None = None) -> None:
        self._event_log = event_log or BoardEventLog()
        self._cards: dict[CardId, Card] = {}

    @property
    def event_log(self) -> BoardEventLog:
        return self._event_log

    def create_card(
        self,
        title: str,
        body: str,
        source_surface: SourceSurface,
        arjuna_weight: float,
        actor_id: str = "facade",
        parent_objective: ObjectiveId | None = None,
        cost_ceiling_usd: Decimal = Decimal("0.00"),
        capability_required: list[str] | None = None,
        initial_status: CardStatus = "inbox",
        trace_id: str = "",
        trace_id_source: str = "",
    ) -> Card:
        """Create a new card and record the event."""
        card_id = CardId(_new_id("card"))
        now = _now()
        idempotency_key = _new_id("idem")

        card = Card(
            id=card_id,
            parent_objective=parent_objective,
            title=title,
            body=body,
            status=initial_status,
            assignee_kind="unknown",
            capability_required=capability_required or [],
            cost_ceiling_usd=cost_ceiling_usd,
            version=Version(1),
            idempotency_key=idempotency_key,
            arjuna_weight=arjuna_weight,
            created_by=actor_id,
            created_at=now,
            updated_at=now,
            last_transitioned_at=now,
            source_surface=source_surface,
        )

        audit = AuditEntry(
            event_id=EventId(_new_id("evt")),
            actor_id=actor_id,
            actor_kind="facade",
            action="card_created",
            at=now,
            idempotency_key=idempotency_key,
            next_version=Version(1),
        )
        card.audit_log.append(audit)
        self._cards[card_id] = card

        self._event_log.append(
            BoardEvent(
                kind="card_created",
                card_id=card_id,
                actor_id=actor_id,
                actor_kind="facade",
                card_version=Version(1),
                to_status=initial_status,
                idempotency_key=idempotency_key,
                **_trace_kwargs(trace_id, trace_id_source),
            )
        )

        logger.info("card_created: %s '%s'", card_id, title[:60])
        return card

    def transition(
        self,
        card_id: CardId,
        to_status: CardStatus,
        expected_version: Version,
        actor_id: str = "facade",
        reason: str = "",
        trace_id: str = "",
        trace_id_source: str = "",
    ) -> Card:
        """Transition a card's status with optimistic concurrency."""
        card = self._cards.get(card_id)
        if card is None:
            raise KeyError(f"Card not found: {card_id}")

        if card.version != expected_version:
            raise VersionConflictError(
                f"Expected version {expected_version}, got {card.version}"
            )

        now = _now()
        from_status = card.status
        new_version = Version(card.version + 1)

        card.status = to_status
        card.version = new_version
        card.updated_at = now
        card.last_transitioned_at = now

        audit = AuditEntry(
            event_id=EventId(_new_id("evt")),
            actor_id=actor_id,
            actor_kind="agent",
            action=f"transition:{from_status}->{to_status}",
            at=now,
            idempotency_key=_new_id("idem"),
            previous_version=expected_version,
            next_version=new_version,
            reason=reason,
        )
        card.audit_log.append(audit)

        self._event_log.append(
            BoardEvent(
                kind="card_transitioned",
                card_id=card_id,
                actor_id=actor_id,
                actor_kind="agent",
                card_version=new_version,
                from_status=from_status,
                to_status=to_status,
                **_trace_kwargs(trace_id, trace_id_source),
            )
        )

        return card

    def get_card(self, card_id: CardId) -> Card | None:
        """Retrieve a card by ID."""
        return self._cards.get(card_id)

    def project_card(
        self,
        card: Card,
        *,
        operation: str,
        actor_id: str = "command_api",
    ) -> Card:
        """Import an adapter projection without changing its canonical mapping."""
        existing = self._cards.get(card.id)
        self._cards[card.id] = card
        kind = "card_created" if operation == "create" and existing is None else "card_transitioned"
        self._event_log.append(
            BoardEvent(
                kind=kind,
                card_id=card.id,
                actor_id=actor_id,
                actor_kind="facade",
                card_version=card.version,
                from_status=existing.status if existing else None,
                to_status=card.status,
                idempotency_key=f"shadow_{operation}_{card.id}_{card.version}",
                detail={"operation": operation, "mode": "shadow"},
            )
        )
        return card

    def list_cards(
        self,
        status: CardStatus | None = None,
        source_surface: SourceSurface | None = None,
        limit: int = 100,
    ) -> list[Card]:
        """List cards with optional filters."""
        results = list(self._cards.values())
        if status is not None:
            results = [c for c in results if c.status == status]
        if source_surface is not None:
            results = [c for c in results if c.source_surface == source_surface]
        return results[:limit]

    def card_count(self) -> int:
        """Total cards in the facade."""
        return len(self._cards)
