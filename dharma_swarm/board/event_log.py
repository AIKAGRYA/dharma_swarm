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

import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from dharma_swarm.correlation_context import get_correlation
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


def _current_trace_id() -> str:
    return get_correlation().trace_id


def _current_trace_id_source() -> str:
    return "correlation_context" if get_correlation().trace_id else ""


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
    trace_id: str = Field(default_factory=_current_trace_id)
    trace_id_source: str = Field(default_factory=_current_trace_id_source)
    detail: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Event log persistence
# ---------------------------------------------------------------------------

_DEFAULT_LOG_PATH = Path.home() / ".dharma" / "board" / "event_log.sqlite3"


class BoardEventLog:
    """Append-only event log for board operations.

    Writes to a local-first SQLite database. Each row stores one complete
    BoardEvent JSON payload plus queryable routing columns. The log never
    modifies or deletes past entries.

    Usage:
        log = BoardEventLog()
        log.append(BoardEvent(kind="card_created", card_id=CardId("card_001")))
        events = log.read_all()
        recent = log.read_since("2026-05-20T00:00:00+00:00")
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _DEFAULT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS board_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    card_id TEXT,
                    actor_id TEXT NOT NULL,
                    actor_kind TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    card_version INTEGER,
                    from_status TEXT,
                    to_status TEXT,
                    idempotency_key TEXT NOT NULL,
                    governance_snapshot_hash TEXT NOT NULL,
                    trace_id TEXT NOT NULL DEFAULT '',
                    trace_id_source TEXT NOT NULL DEFAULT '',
                    event_json TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(board_events)")
            }
            if "trace_id" not in columns:
                conn.execute(
                    "ALTER TABLE board_events "
                    "ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''"
                )
            if "trace_id_source" not in columns:
                conn.execute(
                    "ALTER TABLE board_events "
                    "ADD COLUMN trace_id_source TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_board_events_card_sequence
                ON board_events(card_id, sequence)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_board_events_timestamp_sequence
                ON board_events(timestamp, sequence)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_board_events_trace_sequence
                ON board_events(trace_id, sequence)
                """
            )

    def append(self, event: BoardEvent) -> EventId:
        """Append an event to the log. Returns the event ID."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO board_events (
                    event_id,
                    kind,
                    card_id,
                    actor_id,
                    actor_kind,
                    timestamp,
                    card_version,
                    from_status,
                    to_status,
                    idempotency_key,
                    governance_snapshot_hash,
                    trace_id,
                    trace_id_source,
                    event_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.event_id),
                    event.kind,
                    str(event.card_id) if event.card_id is not None else None,
                    event.actor_id,
                    event.actor_kind,
                    str(event.timestamp),
                    int(event.card_version) if event.card_version is not None else None,
                    event.from_status,
                    event.to_status,
                    event.idempotency_key,
                    event.governance_snapshot_hash,
                    event.trace_id,
                    event.trace_id_source,
                    event.model_dump_json(),
                ),
            )
        logger.debug("board_event: %s %s %s", event.kind, event.card_id, event.event_id)
        return event.event_id

    def read_all(self) -> list[BoardEvent]:
        """Read all events from the log."""
        if not self._path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_json FROM board_events ORDER BY sequence ASC"
            ).fetchall()
        return [BoardEvent.model_validate_json(row["event_json"]) for row in rows]

    def read_for_trace(self, trace_id: str) -> list[BoardEvent]:
        """Read all events associated with a trace_id."""
        if not self._path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM board_events
                WHERE trace_id = ?
                ORDER BY sequence ASC
                """,
                (trace_id,),
            ).fetchall()
        return [BoardEvent.model_validate_json(row["event_json"]) for row in rows]

    def read_since(self, after: str) -> list[BoardEvent]:
        """Read events with timestamp > after (ISO string comparison)."""
        if not self._path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM board_events
                WHERE timestamp > ?
                ORDER BY sequence ASC
                """,
                (after,),
            ).fetchall()
        return [BoardEvent.model_validate_json(row["event_json"]) for row in rows]

    def read_for_card(self, card_id: CardId) -> list[BoardEvent]:
        """Read all events for a specific card."""
        if not self._path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM board_events
                WHERE card_id = ?
                ORDER BY sequence ASC
                """,
                (str(card_id),),
            ).fetchall()
        return [BoardEvent.model_validate_json(row["event_json"]) for row in rows]

    def count(self) -> int:
        """Count total events in the log."""
        if not self._path.exists():
            return 0
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM board_events").fetchone()
        return int(row["count"])

    def tail(self, n: int = 10) -> list[BoardEvent]:
        """Read the last N events."""
        if not self._path.exists():
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_json FROM board_events
                ORDER BY sequence DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
        return [
            BoardEvent.model_validate_json(row["event_json"])
            for row in reversed(rows)
        ]
