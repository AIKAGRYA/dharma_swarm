"""Episode Ledger — versioned, validated lifecycle events (THE_KEEL §6).

The ledger is an append-only event family with stable episode/attempt IDs.
This module is the schema slice: a validated event type, a PURE projector
(side-effect-free — ordering, dedup, visible conflicts, fail-closed closure),
and a thin persistence wrapper that owns the writes (redaction, append-only
JSONL, write-side dedup). Producers (session ledger, packet closeout) wire in
as separate slices.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterator
from uuid import uuid4

logger = logging.getLogger(__name__)

EPISODE_EVENT_SCHEMA_VERSION = "episode_event.v1"
LOGICAL_DELIVERY_KEY_FIELD = "logical_delivery_key"

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

_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


class LedgerValidationError(ValueError):
    """A ledger event failed schema validation — always fail closed."""


def new_episode_id() -> str:
    return f"ep_{uuid4().hex[:16]}"


def new_attempt_id() -> str:
    return f"at_{uuid4().hex[:16]}"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Mask secret-like keys recursively; persistence never sees raw secrets.

    Lists are containers, not leaves: a secret inside e.g.
    ``{"messages": [{"api_key": ...}]}`` is masked at any depth.
    """
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if any(marker in key.lower() for marker in _REDACT_KEY_MARKERS):
            redacted[key] = _REDACTED
        else:
            redacted[key] = _redact_value(value)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_payload(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(item) for item in value]
    return value


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
        if not stored_id:
            raise LedgerValidationError(
                "event_id is required; refusing to mint a fresh identity for a "
                "stored record"
            )
        if stored_id != rebuilt.event_id:
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
    # Strict integer check: int() would silently truncate 1.9 to 1 and misorder
    # a malformed event instead of failing the validated schema closed.
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise LedgerValidationError("sequence must be a non-negative integer")
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
    episode_ids = sorted({e.episode_id for e in events})
    if len(episode_ids) > 1:
        raise LedgerValidationError(
            f"project_episode projects ONE episode but got events from "
            f"{len(episode_ids)}: {episode_ids}"
        )
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
    # Closure validity is decided by the evidence present AT each close, in
    # sequence order — evidence appended after a close cannot retroactively
    # validate it, and any close without prior evidence fails the episode.
    closes_valid: list[bool] = []
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
            closes_valid.append(bool(state.observations or state.reviews))
    state.closure_valid = state.closed and all(closes_valid)
    return state


def _thread_lock_for(path: Path) -> threading.RLock:
    key = str(path.expanduser().resolve(strict=False))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def _logical_key_from_event(event: EpisodeEvent) -> str:
    explicit = str(event.payload.get(LOGICAL_DELIVERY_KEY_FIELD, "")).strip()
    if explicit:
        return explicit
    if event.event_type == "episode_opened":
        return f"episode:{event.episode_id}:opened"
    if event.event_type == "attempt_started" and event.attempt_id:
        return f"attempt:{event.attempt_id}:started"
    if event.event_type == "observation_recorded":
        session_event_id = str(event.payload.get("session_event_id", "")).strip()
        if session_event_id:
            return f"session-event:{session_event_id}:observation"
    return ""


class EpisodeLedgerWriter:
    """Thin persistence wrapper — owns the writes the pure core never makes.

    Append-only JSONL; payloads are redacted before persistence; duplicate
    event IDs, logical delivery keys, and episode sequences are refused across
    threads, processes, and restarts. Rehydration streams the history once to
    recover all three indexes; later appends only ingest bytes written since
    this instance's last offset while holding the interprocess file lock.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        self._logical_events: dict[str, EpisodeEvent] = {}
        self._high_water: dict[str, int] = {}
        self._sequences: dict[str, set[int]] = {}
        self._scan_offset = 0
        self._rehydration_passes = 0
        self._thread_lock = _thread_lock_for(self.path)
        # A torn tail has no trailing newline; the next append must start on
        # a fresh line or the new event is absorbed INTO the garbage line and
        # silently lost on the following rehydration.
        self._tail_unterminated = False
        self._rehydrate()

    @property
    def rehydration_passes(self) -> int:
        return self._rehydration_passes

    @contextmanager
    def _locked_stream(self) -> Iterator[BinaryIO]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with open(self.path, "a+b") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                try:
                    yield stream
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _rehydrate(self) -> None:
        if not self.path.exists():
            return
        with self._locked_stream() as stream:
            self._rehydration_passes += 1
            self._sync_from_disk_locked(stream)

    def _sync_from_disk_locked(self, stream: BinaryIO) -> None:
        stream.seek(0, os.SEEK_END)
        end = stream.tell()
        if end < self._scan_offset:
            self._seen.clear()
            self._logical_events.clear()
            self._high_water.clear()
            self._sequences.clear()
            self._scan_offset = 0
            self._rehydration_passes += 1
        stream.seek(self._scan_offset)
        while stream.tell() < end:
            raw_line = stream.readline()
            if not raw_line:
                break
            self._observe_line(raw_line)
        self._scan_offset = end
        if end:
            stream.seek(end - 1)
            self._tail_unterminated = stream.read(1) != b"\n"
        else:
            self._tail_unterminated = False

    def _observe_line(self, raw_line: bytes) -> None:
        if not raw_line.strip():
            return
        # Tolerant decode: a torn multi-byte UTF-8 tail from a crashed write
        # must degrade to a corrupt LINE, not disable the writer.
        try:
            record = json.loads(raw_line.decode("utf-8", errors="replace"))
        except (TypeError, ValueError):
            logger.warning(
                "episode_ledger: skipping corrupt line in %s during rehydrate",
                self.path,
            )
            return
        if not isinstance(record, dict):
            logger.warning(
                "episode_ledger: skipping non-object line in %s during rehydrate",
                self.path,
            )
            return
        try:
            event = EpisodeEvent.from_dict(record)
        except LedgerValidationError:
            logger.warning(
                "episode_ledger: skipping invalid record in %s during rehydrate",
                self.path,
            )
            return
        self._observe_event(event)

    def _observe_event(self, event: EpisodeEvent) -> None:
        self._seen.add(event.event_id)
        self._high_water[event.episode_id] = max(
            self._high_water.get(event.episode_id, 0),
            event.sequence,
        )
        self._sequences.setdefault(event.episode_id, set()).add(event.sequence)
        logical_key = _logical_key_from_event(event)
        if logical_key:
            self._logical_events.setdefault(logical_key, event)

    def _append_event_locked(self, stream: BinaryIO, event: EpisodeEvent) -> bool:
        if event.event_id in self._seen:
            return False
        logical_key = _logical_key_from_event(event)
        if logical_key and logical_key in self._logical_events:
            return False
        if event.sequence in self._sequences.get(event.episode_id, set()):
            return False
        record = event.to_dict()
        record["payload"] = redact_payload(event.payload)
        EpisodeEvent.from_dict(record)
        prefix = b"\n" if self._tail_unterminated else b""
        encoded = (
            json.dumps(record, ensure_ascii=True, default=str).encode("utf-8")
            + b"\n"
        )
        stream.seek(0, os.SEEK_END)
        stream.write(prefix + encoded)
        stream.flush()
        os.fsync(stream.fileno())
        self._scan_offset = stream.tell()
        self._tail_unterminated = False
        self._observe_event(event)
        return True

    def append(self, event: EpisodeEvent) -> bool:
        """Append one event; returns False when the event_id was already
        persisted or its logical key/sequence is already occupied."""
        record = event.to_dict()
        record["payload"] = redact_payload(event.payload)
        EpisodeEvent.from_dict(record)
        with self._locked_stream() as stream:
            self._sync_from_disk_locked(stream)
            return self._append_event_locked(stream, event)

    def append_delivery(
        self,
        *,
        delivery_key: str,
        event_type: str,
        episode_id: str,
        attempt_id: str,
        payload: dict[str, Any],
        fixed_sequence: int | None = None,
    ) -> EpisodeEvent:
        """Append one logical delivery under the file lock and return its event.

        A replay after file append but before outbox ack returns the already
        persisted event for ``delivery_key``. New non-fixed sequences are
        allocated only after ingesting bytes from competing writers.
        """

        delivery_key = str(delivery_key).strip()
        if not delivery_key:
            raise LedgerValidationError("delivery_key is required")
        with self._locked_stream() as stream:
            self._sync_from_disk_locked(stream)
            existing = self._logical_events.get(delivery_key)
            if existing is not None:
                return existing
            sequence = (
                int(fixed_sequence)
                if fixed_sequence is not None
                else max(1, self._high_water.get(episode_id, 0) + 1)
            )
            event_payload = dict(payload)
            supplied_key = str(
                event_payload.get(LOGICAL_DELIVERY_KEY_FIELD, delivery_key)
            ).strip()
            if supplied_key != delivery_key:
                raise LedgerValidationError(
                    "payload logical_delivery_key conflicts with delivery_key"
                )
            event_payload[LOGICAL_DELIVERY_KEY_FIELD] = delivery_key
            event = EpisodeEvent.new(
                event_type=event_type,
                episode_id=episode_id,
                attempt_id=attempt_id,
                sequence=sequence,
                payload=event_payload,
            )
            if not self._append_event_locked(stream, event):
                replay = self._logical_events.get(delivery_key)
                if replay is not None:
                    return replay
                raise LedgerValidationError(
                    f"sequence {sequence} for episode {episode_id!r} is occupied"
                )
            return event
