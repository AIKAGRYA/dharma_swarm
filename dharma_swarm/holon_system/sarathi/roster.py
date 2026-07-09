"""Sarathi sub-holon roster helpers.

Two surfaces coexist here:

- ``load_roster``: simple newline/YAML-list roster loader (no runtime state).
- ``load_fleet_roster``/``load_seat``/``fleet_summary``: live heartbeat readers
  over ``~/.dharma/a2a_bus/`` — they report receipts (heartbeat files), never
  claims, and are the source of truth for "who is alive right now" consumed by
  the pulse and brief modules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ROSTER = ("hermes-m5", "codex_composer", "fugu_ultra", "fable_composer")

DHARMA_HOME = Path.home() / ".dharma"
BRIDGE_HEARTBEATS = DHARMA_HOME / "a2a_bus" / "bridge_heartbeats"
WORKER_HEARTBEATS = DHARMA_HOME / "a2a_bus" / "worker_heartbeats"
STATE_DIR = DHARMA_HOME / "a2a_bus" / "state"

# The known sub-holons + Hermes organ. This is the apex view of the fleet.
KNOWN_SEATS: tuple[str, ...] = (
    "codex_composer",
    "fable_composer",
    "fugu_ultra",
    "opus_composer",
    "hermes-m5",
    "sarathi",
    "palantir-pilot",
)


def load_roster(path: str | Path | None = None) -> tuple[str, ...]:
    """Load a simple newline/YAML-list roster without creating runtime state."""
    if path is None:
        return DEFAULT_ROSTER
    roster_path = Path(path).expanduser()
    if not roster_path.exists():
        return DEFAULT_ROSTER
    names: list[str] = []
    for raw in roster_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in {"sub_holons:", "agents:"}:
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            names.append(line)
    return tuple(names) or DEFAULT_ROSTER


@dataclass(frozen=True)
class SeatStatus:
    """Live status of one fleet seat, read from heartbeat files."""

    name: str
    status: str
    last_heartbeat: str
    messages_processed: int
    source_file: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        """A seat is alive if its bridge/worker has a non-dead heartbeat."""
        dead_states = {"NATS_CLIENT_MISSING", "PARSE_ERROR", "dead", "scaffolded_not_alive", "NOT_FOUND"}
        return self.status not in dead_states

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat,
            "messages_processed": self.messages_processed,
            "is_alive": self.is_alive,
            "source_file": self.source_file,
        }


def _read_heartbeat(path: Path) -> dict[str, Any] | None:
    """Read a heartbeat JSON file, returning None on any error."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_seat(name: str) -> SeatStatus:
    """Load the live status of a single seat from heartbeat files.

    Checks bridge heartbeats first, then worker heartbeats, then state files.
    Returns a SeatStatus with status='NOT_FOUND' if no file exists.
    """
    for hdir in (BRIDGE_HEARTBEATS, WORKER_HEARTBEATS):
        path = hdir / f"{name}.json"
        if path.exists():
            data = _read_heartbeat(path)
            if data:
                return SeatStatus(
                    name=name,
                    status=str(data.get("status", "UNKNOWN")),
                    last_heartbeat=str(data.get("last_heartbeat", "")),
                    messages_processed=int(
                        data.get("messages_processed", data.get("receipt_count", 0))
                    ),
                    source_file=str(path),
                    raw=data,
                )

    state_path = STATE_DIR / f"{name}.json"
    if state_path.exists():
        data = _read_heartbeat(state_path)
        if data:
            return SeatStatus(
                name=name,
                status=str(data.get("status", data.get("l4_status", "UNKNOWN"))),
                last_heartbeat=str(data.get("last_heartbeat", data.get("last_active", ""))),
                messages_processed=0,
                source_file=str(state_path),
                raw=data,
            )

    return SeatStatus(
        name=name,
        status="NOT_FOUND",
        last_heartbeat="",
        messages_processed=0,
        source_file="",
    )


def load_fleet_roster(seats: tuple[str, ...] | None = None) -> list[SeatStatus]:
    """Load the full live fleet roster from heartbeat files. Defaults to KNOWN_SEATS."""
    seat_names = seats or KNOWN_SEATS
    return [load_seat(name) for name in seat_names]


def fleet_summary() -> dict[str, Any]:
    """Produce a machine-readable fleet summary for pulse/brief consumption."""
    roster = load_fleet_roster()
    alive = [s for s in roster if s.is_alive]
    dead = [s for s in roster if not s.is_alive]
    return {
        "schema_version": "dharma.sarathi.roster.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_seats": len(roster),
        "alive_count": len(alive),
        "dead_count": len(dead),
        "alive_seats": [s.name for s in alive],
        "dead_seats": [s.name for s in dead],
        "seats": [s.to_dict() for s in roster],
    }


__all__ = [
    "DEFAULT_ROSTER",
    "KNOWN_SEATS",
    "SeatStatus",
    "fleet_summary",
    "load_fleet_roster",
    "load_roster",
    "load_seat",
]
