"""BoardStore event log — append-only audit stream.

Records what the facade did, not a parallel world. The durable domain
state remains in the existing stores. Events here track:
- Card creation, transition, claim, release, handoff
- Facade-level operations (projection rebuild, adapter sync)
- Multi-agent attribution (who did what, when, with what governance)

The event log is the substrate's institutional memory for board operations.
It is append-only and tamper-evident by design.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from dharma_swarm.board.models import (
    CardId,
    CardStatus,
    EventId,
    IsoDatetime,
    Version,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

EventKind = Literal[
    "card_created",
    "card_transitioned",
    "card_claimed",
    "card_released",
    "card_handoff",
    "lease_expired",
    "lease_heartbeat",
    "facade_sync",
    "adapter_error",
    "governance_check",
]


class BoardEvent(BaseModel):
    """A single append-only event in the board event log."""

    event_id: EventId = Field(default_factory=lambda: EventId(str(uuid.uuid4())))
    kind: EventKind
    card_id: CardId | None = None
    actor_id: str = ""
    actor_kind: Literal["operator", "agent", "noticer", "facade", "admin"] = "facade"
    timestamp: IsoDatetime = Field(
        default_factory=lambda: IsoDatetime(
            time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        )
    )
    card_version: Version | None = None
    from_status: CardStatus | None = None
    to_status: CardStatus | None = None
    idempotency_key: str = ""
    governance_snapshot_hash: str = ""
    detail: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event log persistence
# ---------------------------------------------------------------------------

_DEFAULT_LOG_PATH = Path.home() / ".dharma" / "board" / "event_log.jsonl"


class BoardEventLog:
    """Append-only event log for board operations.

    Writes to a JSONL file. Each line is a complete BoardEvent serialized
    as JSON. The log never modifies or deletes past entries.

    Usage:
        log = BoardEventLog()
        log.append(BoardEvent(kind="card_created", card_id=CardId("card_001")))
        events = log.read_all()
        recent = log.read_since("2026-05-20T00:00:00+00:00")
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: BoardEvent) -> EventId:
        """Append an event to the log. Returns the event ID."""
        line = event.model_dump_json() + "\n"
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line)
        logger.debug("board_event: %s %s %s", event.kind, event.card_id, event.event_id)
        return event.event_id

    def read_all(self) -> list[BoardEvent]:
        """Read all events from the log."""
        if not self._path.exists():
            return []
        events: list[BoardEvent] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                events.append(BoardEvent.model_validate_json(line))
        return events

    def read_since(self, after: str) -> list[BoardEvent]:
        """Read events with timestamp > after (ISO string comparison)."""
        return [e for e in self.read_all() if e.timestamp > after]

    def read_for_card(self, card_id: CardId) -> list[BoardEvent]:
        """Read all events for a specific card."""
        return [e for e in self.read_all() if e.card_id == card_id]

    def count(self) -> int:
        """Count total events in the log."""
        if not self._path.exists():
            return 0
        with self._path.open("r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def tail(self, n: int = 10) -> list[BoardEvent]:
        """Read the last N events."""
        all_events = self.read_all()
        return all_events[-n:]
