"""Episode Ledger — versioned, validated lifecycle events (THE_KEEL §6).

The ledger is an append-only event family with stable episode/attempt IDs.
This module is the schema slice: a validated event type, a PURE projector
(side-effect-free — ordering, dedup, visible conflicts, fail-closed closure),
and a thin persistence wrapper that owns the writes (redaction, append-only
JSONL, write-side dedup). Producers (session ledger, packet closeout) wire in
as separate slices.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

EPISODE_EVENT_SCHEMA_VERSION = "episode_event.v1"

# The lifecycle vocabulary each producer appends at the transition it owns.
EVENT_TYPES = (
    "episode_opened",
    "attempt_started",
    "observation_recorded",
    "effect_requested",
    "effect_resolved",
    "review_recorded",
    "episode_closed",
    "post_merge_observation",
)

# Effect events carry the idempotency fence key — mandatory, never implied.
_EFFECT_EVENT_TYPES = ("effect_requested", "effect_resolved")

_REDACT_KEY_MARKERS = ("secret", "token", "password", "api_key", "authorization", "credential")
_REDACTED = "[REDACTED]"


class LedgerValidationError(ValueError):
    """A ledger event failed schema validation — always fail closed."""


def new_episode_id() -> str:
    return f"ep_{uuid4().hex[:16]}"


def new_attempt_id() -> str:
    return f"at_{uuid4().hex[:16]}"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Mask secret-like keys recursively; persistence never sees raw secrets."""
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if any(marker in key.lower() for marker in _REDACT_KEY_MARKERS):
            redacted[key] = _REDACTED
        elif isinstance(value, dict):
            redacted[key] = redact_payload(value)
        else:
            redacted[key] = value
    return redacted


@dataclass(frozen=True)
class EpisodeEvent:
    """One immutable lifecycle event; identity is deterministic over content."""

    schema_version: str
    event_type: str
    episode_id: str
    attempt_id: str
    sequence: int
    payload: dict[str, Any]
    event_id: str

    @classmethod
    def new(
        cls,
        *,
        event_type: str,
        episode_id: str,
        attempt_id: str = "",
        sequence: int,
        payload: dict[str, Any] | None = None,
    ) -> "EpisodeEvent":
        # Redact at CONSTRUCTION: secrets never enter the event, and event
        # identity is computed over exactly what persistence will write, so
        # the from_dict tamper check holds across the disk round-trip.
        payload = redact_payload(dict(payload or {}))
        _validate(
            schema_version=EPISODE_EVENT_SCHEMA_VERSION,
            event_type=event_type,
            episode_id=episode_id,
            sequence=sequence,
            payload=payload,
        )
        event_id = hashlib.sha256(
            "\n".join(
                (
                    EPISODE_EVENT_SCHEMA_VERSION,
                    event_type,
                    episode_id,
                    attempt_id,
                    str(int(sequence)),
                    _canonical(payload),
                )
            ).encode("utf-8")
        ).hexdigest()
        return cls(
            schema_version=EPISODE_EVENT_SCHEMA_VERSION,
            event_type=event_type,
            episode_id=episode_id,
            attempt_id=attempt_id,
            sequence=int(sequence),
            payload=payload,
            event_id=f"ev_{event_id[:32]}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "episode_id": self.episode_id,
            "attempt_id": self.attempt_id,
            "sequence": self.sequence,
            "payload": self.payload,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodeEvent":
        schema_version = str(data.get("schema_version", ""))
        if schema_version != EPISODE_EVENT_SCHEMA_VERSION:
            raise LedgerValidationError(
                f"unknown schema_version {schema_version!r}; refusing to guess"
            )
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise LedgerValidationError("payload must be a dict")
        _validate(
            schema_version=schema_version,
            event_type=str(data.get("event_type", "")),
            episode_id=str(data.get("episode_id", "")),
            sequence=data.get("sequence", -1),
            payload=payload,
        )
        rebuilt = cls.new(
            event_type=str(data["event_type"]),
            episode_id=str(data["episode_id"]),
            attempt_id=str(data.get("attempt_id", "")),
            sequence=int(data["sequence"]),
            payload=payload,
        )
        stored_id = str(data.get("event_id", ""))
        if stored_id and stored_id != rebuilt.event_id:
            raise LedgerValidationError(
                f"event_id mismatch for {data.get('event_type')!r}: content was altered"
            )
        return rebuilt


def _validate(
    *,
    schema_version: str,
    event_type: str,
    episode_id: str,
    sequence: Any,
    payload: dict[str, Any],
) -> None:
    if schema_version != EPISODE_EVENT_SCHEMA_VERSION:
        raise LedgerValidationError(f"unknown schema_version {schema_version!r}")
    if event_type not in EVENT_TYPES:
        raise LedgerValidationError(
            f"unknown event_type {event_type!r}; the lifecycle vocabulary is {EVENT_TYPES}"
        )
    if not str(episode_id).strip():
        raise LedgerValidationError("episode_id is required")
    try:
        if int(sequence) < 0:
            raise LedgerValidationError("sequence must be a non-negative integer")
    except (TypeError, ValueError) as exc:
        raise LedgerValidationError("sequence must be a non-negative integer") from exc
    if event_type in _EFFECT_EVENT_TYPES and not str(payload.get("idempotency_key", "")).strip():
        raise LedgerValidationError(f"{event_type} requires payload.idempotency_key")


@dataclass
class EpisodeState:
    """Pure projection of one episode's events. Regenerable; never authoritative
    over the raw events it was projected from."""

    episode_id: str = ""
    events: list[EpisodeEvent] = field(default_factory=list)
    observations: list[EpisodeEvent] = field(default_factory=list)
    reviews: list[EpisodeEvent] = field(default_factory=list)
    effects: list[EpisodeEvent] = field(default_factory=list)
    duplicate_event_ids: list[str] = field(default_factory=list)
    closed: bool = False
    closure_valid: bool = False


def project_episode(events: list[EpisodeEvent]) -> EpisodeState:
    """SIDE-EFFECT-FREE projector: explicit ordering (sequence, then event_id),
    dedup by event_id, conflicting observations kept visible (never
    last-write-wins), and fail-closed closure — an episode_closed with zero
    observations AND zero reviews is closed but NOT valid (missing evidence)."""
    state = EpisodeState()
    seen: set[str] = set()
    ordered: list[EpisodeEvent] = []
    for event in sorted(events, key=lambda e: (e.sequence, e.event_id)):
        if event.event_id in seen:
            state.duplicate_event_ids.append(event.event_id)
            continue
        seen.add(event.event_id)
        ordered.append(event)
    state.events = ordered
    for event in ordered:
        state.episode_id = state.episode_id or event.episode_id
        if event.event_type == "observation_recorded":
            state.observations.append(event)
        elif event.event_type == "review_recorded":
            state.reviews.append(event)
        elif event.event_type in _EFFECT_EVENT_TYPES:
            state.effects.append(event)
        elif event.event_type == "episode_closed":
            state.closed = True
    state.closure_valid = state.closed and bool(state.observations or state.reviews)
    return state


class EpisodeLedgerWriter:
    """Thin persistence wrapper — owns the writes the pure core never makes.

    Append-only JSONL; payloads are redacted before persistence; duplicate
    event_ids are refused, including across restarts (seen-IDs rehydrate from
    disk, skipping torn/corrupt lines so one bad write cannot poison the file).
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        self._rehydrate()

    def _rehydrate(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except (TypeError, ValueError):
                logger.warning(
                    "episode_ledger: skipping corrupt line in %s during rehydrate",
                    self.path,
                )
                continue
            event_id = str(record.get("event_id", ""))
            if event_id:
                self._seen.add(event_id)

    def append(self, event: EpisodeEvent) -> bool:
        """Append one event; returns False when the event_id was already
        persisted (write-side dedup)."""
        if event.event_id in self._seen:
            return False
        record = event.to_dict()
        record["payload"] = redact_payload(event.payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")
        self._seen.add(event.event_id)
        return True
