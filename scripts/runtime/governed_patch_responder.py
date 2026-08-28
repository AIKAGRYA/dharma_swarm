"""Restart-safe, non-authorizing responder for one governed patch candidate.

The A2A inbox bridge owns the NATS subscription and broker acknowledgement.
This process only reads the bridge's committed ``semantic_jobs`` row and its
exact delivery record.  Its separate SQLite database owns candidate-authoring
leases and checkpoints; it never mutates Mission Control, the TaskBoard, the
bridge database, or a repository checkout.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import math
import os
import re
import sqlite3
import stat
import subprocess
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Final, Protocol
from urllib.parse import quote


DELIVERY_SCHEMA: Final[str] = "dharma.a2a.inbox_delivery.v1"
SEND_SCHEMA: Final[str] = "dharma.a2a.send.v1"
INTENT_SCHEMA: Final[str] = "dharma.a2a.governed_patch_intent.v1"
LEDGER_SCHEMA: Final[str] = "dharma.governed_patch.responder_ledger.v1"
JOB_SCHEMA: Final[str] = "dharma.governed_patch.responder_job.v1"

INPUT_COMMITTED: Final[str] = "INPUT_COMMITTED"
PROVIDER_CALL_STARTED: Final[str] = "PROVIDER_CALL_STARTED"
TERMINAL_COMMITTED: Final[str] = "TERMINAL_COMMITTED"
PENDING_AUTHORSHIP: Final[str] = "PENDING_AUTHORSHIP"
CANDIDATE_DURABLE: Final[str] = "CANDIDATE_DURABLE"
PROVIDER_REFUSED: Final[str] = "PROVIDER_REFUSED"

_PHASES = frozenset({INPUT_COMMITTED, PROVIDER_CALL_STARTED, TERMINAL_COMMITTED})
_STATUSES = frozenset({PENDING_AUTHORSHIP, CANDIDATE_DURABLE, PROVIDER_REFUSED})
_TERMINAL_STATUSES = frozenset({CANDIDATE_DURABLE, PROVIDER_REFUSED})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,255}$")
_DELIVERY_ID = re.compile(r"^[0-9a-f]{24}$")
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_DATABASE_BYTES = 256 * 1024 * 1024
_MAX_SQLITE_SIDECAR_BYTES = 256 * 1024 * 1024
_SQLITE_QUERY_SECONDS = 2.0
_SQLITE_VM_STEPS = 250_000
_LEDGER_APPLICATION_ID = 0x44504752
_LEDGER_USER_VERSION = 1

_DELIVERY_KEYS = frozenset(
    {
        "schema_version",
        "delivered_at",
        "agent_uid",
        "bridge_kind",
        "source_subject",
        "stream",
        "consumer",
        "envelope_sha256",
        "envelope",
        "semantic_reply_claim",
        "peer_model_processed_claim",
    }
)
_INTENT_KEYS = frozenset(
    {
        "schema_version",
        "mission_id",
        "task_id",
        "proposal_id",
        "base_sha",
        "authorized_source_path",
        "oracle_argv",
        "semantic_intent",
    }
)
_BRIDGE_COLUMNS = (
    "event_id",
    "envelope_sha256",
    "envelope_json",
    "status",
    "created_at",
    "updated_at",
)
_BRIDGE_TABLE_INFO = (
    ("event_id", "TEXT", 0, None, 1),
    ("envelope_sha256", "TEXT", 1, None, 0),
    ("envelope_json", "TEXT", 1, None, 0),
    ("status", "TEXT", 1, None, 0),
    ("created_at", "TEXT", 1, None, 0),
    ("updated_at", "TEXT", 1, None, 0),
)
_LEDGER_COLUMNS = (
    "event_id",
    "schema_version",
    "packet_id",
    "phase",
    "status",
    "envelope_sha256",
    "envelope_json",
    "delivery_record_path",
    "delivery_record_sha256",
    "semantic_artifact_sha256",
    "projection_json",
    "projection_sha256",
    "request_checkpoint_json",
    "request_checkpoint_sha256",
    "input_sha256",
    "lease_owner",
    "lease_boot_id",
    "lease_token",
    "lease_generation",
    "lease_acquired_at",
    "lease_expires_at",
    "provider_call_id",
    "author_owner",
    "author_boot_id",
    "provider_started_at",
    "provider_receipt_json",
    "provider_receipt_sha256",
    "candidate_checkpoint_json",
    "candidate_checkpoint_sha256",
    "outcome_sha256",
    "terminal_at",
    "created_at",
    "updated_at",
    "checkpoint_sha256",
)
_LEDGER_REAL_COLUMNS = frozenset(
    {
        "lease_acquired_at",
        "lease_expires_at",
        "provider_started_at",
        "terminal_at",
        "created_at",
        "updated_at",
    }
)
_LEDGER_REQUIRED_COLUMNS = frozenset(
    {
        "schema_version",
        "packet_id",
        "phase",
        "status",
        "envelope_sha256",
        "envelope_json",
        "delivery_record_path",
        "delivery_record_sha256",
        "semantic_artifact_sha256",
        "projection_json",
        "projection_sha256",
        "request_checkpoint_json",
        "request_checkpoint_sha256",
        "input_sha256",
        "lease_generation",
        "created_at",
        "updated_at",
        "checkpoint_sha256",
    }
)
_LEDGER_TABLE_INFO = tuple(
    (
        name,
        (
            "INTEGER"
            if name == "lease_generation"
            else "REAL"
            if name in _LEDGER_REAL_COLUMNS
            else "TEXT"
        ),
        int(name in _LEDGER_REQUIRED_COLUMNS),
        None,
        int(name == "event_id"),
    )
    for name in _LEDGER_COLUMNS
)
_CHECKPOINT_FIELDS = tuple(
    name for name in _LEDGER_COLUMNS if name != "checkpoint_sha256"
)


class GovernedPatchResponderError(RuntimeError):
    """The responder cannot safely advance the requested packet."""


class BridgeEvidenceError(GovernedPatchResponderError):
    """The bridge row or delivery record is absent, ambiguous, or corrupt."""


class LedgerCorruptionError(GovernedPatchResponderError):
    """A durable responder checkpoint contradicts its own digest or shape."""


class InputDriftError(GovernedPatchResponderError):
    """Current owner evidence differs from the packet's committed input."""


class LeaseUnavailableError(GovernedPatchResponderError):
    """Another live process owns the exact packet lease."""


class ProviderCallUncertainError(GovernedPatchResponderError):
    """A prior process may have called the provider and no result is recoverable."""


@dataclass(frozen=True, slots=True)
class BridgeDelivery:
    event_id: str
    packet_id: str
    delivery_record_path: Path
    delivery_record_sha256: str
    delivery_id: str
    envelope_sha256: str
    envelope_json: str
    envelope: dict[str, Any]
    delivery_record: dict[str, Any]
    content: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class SemanticProjection:
    """Exact semantic-execution proof plus the observer-native object."""

    semantic_artifact_sha256: str
    checkpoint: Mapping[str, Any]
    native: object | None = None


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    """Provider request and a closed, JSON-only restart checkpoint."""

    request: object
    checkpoint: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AuthorshipOutcome:
    """Normalized immutable provider receipt and optional candidate locator."""

    receipt: Mapping[str, Any]
    candidate: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class ResponderObservation:
    event_id: str
    status: str
    phase: str
    provider_call_id: str
    provider_receipt: dict[str, Any]
    candidate_checkpoint: dict[str, Any] | None
    input_sha256: str
    authored_by_owner: str
    authored_by_boot_id: str
    observed_by_boot_id: str
    provider_called: bool
    recovered: bool
    repository_effect_authorized: bool = False
    mission_control_completion_authorized: bool = False

    @property
    def authored_in_this_boot(self) -> bool:
        return (
            self.provider_called
            and self.authored_by_boot_id == self.observed_by_boot_id
        )


class DeliveryLoader(Protocol):
    def __call__(
        self,
        bridge_db: Path,
        event_id: str,
        delivery_record_path: Path,
    ) -> BridgeDelivery: ...


class ProjectionValidator(Protocol):
    def __call__(
        self,
        delivery: BridgeDelivery,
    ) -> SemanticProjection | Awaitable[SemanticProjection]: ...


class RequestParser(Protocol):
    def __call__(
        self,
        delivery: BridgeDelivery,
        projection: SemanticProjection,
        prior_checkpoint: Mapping[str, Any] | None,
    ) -> ParsedRequest | Awaitable[ParsedRequest]: ...


class CandidateAuthor(Protocol):
    def __call__(
        self,
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> object | Awaitable[object]: ...


class CandidateRecoverer(Protocol):
    def __call__(
        self,
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> object | Awaitable[object | None] | None: ...


class ProviderCallInspector(Protocol):
    def __call__(
        self,
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> str | Awaitable[str]: ...


class AuthorshipOutcomeVerifier(Protocol):
    def __call__(
        self,
        value: object,
        *,
        request: object,
        call_id: str,
        semantic_artifact_sha256: str,
        request_checkpoint: Mapping[str, Any],
    ) -> AuthorshipOutcome: ...


CheckpointHook = Callable[[str, Mapping[str, Any]], None]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_json(raw: str, *, label: str) -> Any:
    if type(raw) is not str:
        raise BridgeEvidenceError(f"{label} must be an exact JSON string")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BridgeEvidenceError(f"{label} is not valid UTF-8") from exc
    if len(encoded) > _MAX_JSON_BYTES:
        raise BridgeEvidenceError(f"{label} exceeds its read bound")

    def reject_constant(value: str) -> None:
        raise BridgeEvidenceError(f"{label} contains non-finite JSON {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BridgeEvidenceError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except BridgeEvidenceError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise BridgeEvidenceError(f"{label} is malformed JSON") from exc


def _json_value(value: Any, *, label: str) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise GovernedPatchResponderError(f"{label} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if type(key) is not str or key in result:
                raise GovernedPatchResponderError(f"{label} is not a JSON object")
            result[key] = _json_value(child, label=f"{label}.{key}")
        return result
    if type(value) in {list, tuple}:
        return [_json_value(child, label=label) for child in value]
    raise GovernedPatchResponderError(
        f"{label} contains unsupported {type(value).__name__}"
    )


def _canonical_bytes(value: Any, *, label: str) -> bytes:
    return json.dumps(
        _json_value(value, label=label),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_text(value: Any, *, label: str) -> str:
    return _canonical_bytes(value, label=label).decode("ascii")


def _read_regular(path: Path, *, label: str, limit: int) -> tuple[Path, bytes]:
    candidate = path.expanduser()
    try:
        before = candidate.lstat()
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise BridgeEvidenceError(f"{label} is unavailable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise BridgeEvidenceError(f"{label} is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise BridgeEvidenceError(f"{label} is unreadable") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > limit:
            raise BridgeEvidenceError(f"{label} exceeds its read bound")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    data = b"".join(chunks)
    if len(data) > limit or (
        opened.st_dev,
        opened.st_ino,
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise BridgeEvidenceError(f"{label} changed while it was read")
    return resolved, data


def _regular_identity(
    path: Path,
    *,
    label: str,
    limit: int,
) -> tuple[Path, tuple[int, int]]:
    candidate = path.expanduser()
    try:
        lexical = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        opened = resolved.stat()
    except OSError as exc:
        raise BridgeEvidenceError(f"{label} is unavailable") from exc
    if (
        stat.S_ISLNK(lexical.st_mode)
        or not stat.S_ISREG(lexical.st_mode)
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_size > limit
    ):
        raise BridgeEvidenceError(f"{label} is not a bounded regular file")
    return resolved, (opened.st_dev, opened.st_ino)


def _optional_sidecar_identity(path: Path) -> tuple[int, int] | None:
    if not os.path.lexists(path):
        return None
    _, identity = _regular_identity(
        path,
        label=f"SQLite sidecar {path.name}",
        limit=_MAX_SQLITE_SIDECAR_BYTES,
    )
    return identity


def _require_table(
    connection: sqlite3.Connection,
    *,
    name: str,
    expected_info: Sequence[tuple[str, str, int, object, int]],
    error_type: type[GovernedPatchResponderError],
) -> None:
    objects = connection.execute(
        "SELECT type, tbl_name, rootpage FROM main.sqlite_master "
        "WHERE name = ? LIMIT 2",
        (name,),
    ).fetchall()
    if (
        len(objects) != 1
        or str(objects[0][0]) != "table"
        or str(objects[0][1]) != name
        or int(objects[0][2]) <= 0
    ):
        raise error_type(f"{name} is not one exact SQLite table")
    info = tuple(
        (str(row[1]), str(row[2]).upper(), int(row[3]), row[4], int(row[5]))
        for row in connection.execute(f"PRAGMA main.table_info({name})").fetchall()
    )
    if info != tuple(expected_info):
        raise error_type(f"{name} has an unexpected schema")
    triggers = connection.execute(
        "SELECT 1 FROM main.sqlite_master "
        "WHERE type = 'trigger' AND tbl_name = ? LIMIT 1",
        (name,),
    ).fetchone()
    if triggers is not None:
        raise error_type(f"{name} must not have triggers")


def _bounded_fetchall(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object],
    *,
    error_type: type[GovernedPatchResponderError],
    label: str,
) -> list[sqlite3.Row]:
    deadline = time.monotonic() + _SQLITE_QUERY_SECONDS
    calls_remaining = max(1, _SQLITE_VM_STEPS // 1_000)

    def interrupt() -> int:
        nonlocal calls_remaining
        calls_remaining -= 1
        return int(calls_remaining <= 0 or time.monotonic() >= deadline)

    connection.set_progress_handler(interrupt, 1_000)
    try:
        return connection.execute(sql, tuple(parameters)).fetchall()
    except sqlite3.Error as exc:
        raise error_type(f"{label} exceeded its bounded SQLite read") from exc
    finally:
        connection.set_progress_handler(None, 0)


def _connect_bridge(
    path: Path,
) -> tuple[sqlite3.Connection, Path, tuple[int, int], dict[str, tuple[int, int] | None]]:
    resolved, identity = _regular_identity(
        path, label="semantic job database", limit=_MAX_DATABASE_BYTES
    )
    sidecars = {
        suffix: _optional_sidecar_identity(Path(f"{resolved}{suffix}"))
        for suffix in ("-wal", "-shm", "-journal")
    }
    if sidecars["-journal"] is not None:
        raise BridgeEvidenceError("semantic job database has a rollback journal")
    uri = f"file:{quote(str(resolved))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA busy_timeout=2000")
    journal = str(connection.execute("PRAGMA main.journal_mode").fetchone()[0]).lower()
    if journal != "wal":
        connection.close()
        raise BridgeEvidenceError("semantic job database is not in WAL mode")
    _require_table(
        connection,
        name="semantic_jobs",
        expected_info=_BRIDGE_TABLE_INFO,
        error_type=BridgeEvidenceError,
    )
    return connection, resolved, identity, sidecars


def _delivery_id(
    path: Path,
    delivery: Mapping[str, Any],
    envelope: Mapping[str, Any],
) -> str:
    stable = {
        "path": str(path),
        "packet_id": str(envelope.get("packet_id") or ""),
        "reply_subject": str(envelope.get("reply_subject") or ""),
        "envelope_sha256": str(delivery.get("envelope_sha256") or ""),
    }
    return _sha256(json.dumps(stable, sort_keys=True).encode("utf-8"))[:24]


def load_bridge_delivery(
    bridge_db: Path,
    event_id: str,
    delivery_record_path: Path,
) -> BridgeDelivery:
    """Read one exact PENDING bridge row and matching immutable delivery JSON."""

    if type(event_id) is not str or _TOKEN.fullmatch(event_id) is None:
        raise BridgeEvidenceError("event_id is malformed")
    connection, database_path, database_identity, sidecars = _connect_bridge(
        Path(bridge_db)
    )
    try:
        connection.execute("BEGIN")
        rows = _bounded_fetchall(
            connection,
            "SELECT event_id, envelope_sha256, envelope_json, status "
            "FROM semantic_jobs WHERE event_id = ? LIMIT 2",
            (event_id,),
            error_type=BridgeEvidenceError,
            label="semantic job lookup",
        )
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    _, after_identity = _regular_identity(
        database_path,
        label="semantic job database",
        limit=_MAX_DATABASE_BYTES,
    )
    if after_identity != database_identity:
        raise BridgeEvidenceError("semantic job database custody changed")
    for suffix, before_identity in sidecars.items():
        sidecar_path = Path(f"{database_path}{suffix}")
        after_sidecar = _optional_sidecar_identity(sidecar_path)
        if suffix == "-journal" and after_sidecar is not None:
            raise BridgeEvidenceError("semantic job rollback journal appeared")
        if before_identity is not None and after_sidecar != before_identity:
            raise BridgeEvidenceError(
                f"semantic job database {suffix} custody changed"
            )
    if len(rows) != 1:
        raise BridgeEvidenceError("expected exactly one semantic job for event_id")
    row = rows[0]
    if str(row["event_id"]) != event_id or str(row["status"]) != "PENDING":
        raise BridgeEvidenceError("semantic job is not the exact committed PENDING row")
    envelope_json = str(row["envelope_json"])
    envelope = _strict_json(envelope_json, label="semantic job envelope_json")
    if type(envelope) is not dict:
        raise BridgeEvidenceError("semantic job envelope_json must be an object")
    canonical_bridge_json = json.dumps(envelope, ensure_ascii=True, sort_keys=True)
    envelope_sha = str(row["envelope_sha256"])
    if (
        envelope_json != canonical_bridge_json
        or _SHA256.fullmatch(envelope_sha) is None
        or _sha256(envelope_json.encode("utf-8")) != envelope_sha
    ):
        raise BridgeEvidenceError("semantic job envelope digest is not canonical")

    delivery_path, delivery_bytes = _read_regular(
        Path(delivery_record_path),
        label="delivery record",
        limit=_MAX_JSON_BYTES,
    )
    try:
        delivery_text = delivery_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BridgeEvidenceError("delivery record is not UTF-8") from exc
    delivery = _strict_json(delivery_text, label="delivery record")
    if type(delivery) is not dict or frozenset(delivery) != _DELIVERY_KEYS:
        raise BridgeEvidenceError(
            "delivery record does not have the closed bridge shape"
        )
    delivered_envelope = delivery.get("envelope")
    if (
        delivery.get("schema_version") != DELIVERY_SCHEMA
        or delivery.get("bridge_kind") != "filesystem_delivery_handler"
        or delivery.get("semantic_reply_claim") is not False
        or delivery.get("peer_model_processed_claim") is not False
        or type(delivered_envelope) is not dict
        or delivered_envelope != envelope
        or delivery.get("envelope_sha256") != envelope_sha
    ):
        raise BridgeEvidenceError("delivery record disagrees with semantic job")
    subject = envelope.get("subject")
    packet_id = envelope.get("packet_id")
    agent_uid = delivery.get("agent_uid")
    content = envelope.get("content")
    content_sha = envelope.get("sha256")
    if (
        envelope.get("schema_version") != SEND_SCHEMA
        or type(subject) is not str
        or not subject
        or type(packet_id) is not str
        or packet_id != event_id
        or type(agent_uid) is not str
        or envelope.get("to") != agent_uid
        or envelope.get("target_uid") != agent_uid
        or delivery.get("source_subject") != subject
        or envelope.get("ack_subject") != f"{subject}.ack.{event_id}"
        or envelope.get("reply_subject") != f"{subject}.reply.{event_id}"
        or type(content) is not str
        or type(content_sha) is not str
        or _sha256(content.encode("utf-8")) != content_sha
    ):
        raise BridgeEvidenceError("delivery envelope identity is malformed")
    derived_delivery_id = _delivery_id(delivery_path, delivery, envelope)
    if _DELIVERY_ID.fullmatch(derived_delivery_id) is None:
        raise AssertionError("derived delivery_id is malformed")
    return BridgeDelivery(
        event_id=event_id,
        packet_id=event_id,
        delivery_record_path=delivery_path,
        delivery_record_sha256=_sha256(delivery_bytes),
        delivery_id=derived_delivery_id,
        envelope_sha256=envelope_sha,
        envelope_json=envelope_json,
        envelope=envelope,
        delivery_record=delivery,
        content=content,
        content_sha256=content_sha,
    )


def _ledger_connection(path: Path, *, repo_root: Path) -> sqlite3.Connection:
    repo = repo_root.expanduser().resolve(strict=True)
    lexical = path.expanduser().absolute()
    target = lexical.resolve(strict=False)
    if target == repo or target.is_relative_to(repo):
        raise GovernedPatchResponderError(
            "responder ledger must be outside the canonical repository"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        descriptor = os.open(
            target,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        pass
    except OSError as exc:
        raise GovernedPatchResponderError(
            "responder ledger cannot be exclusively admitted"
        ) from exc
    else:
        os.close(descriptor)
        created = True

    def existing_identity() -> tuple[int, int]:
        try:
            info = target.lstat()
        except OSError as exc:
            raise GovernedPatchResponderError(
                "responder ledger is unavailable"
            ) from exc
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_size > _MAX_DATABASE_BYTES
            or info.st_mode & 0o077
        ):
            raise GovernedPatchResponderError(
                "responder ledger must be one owner-only bounded regular file"
            )
        return info.st_dev, info.st_ino

    identity = existing_identity()
    for suffix in ("-wal", "-shm", "-journal"):
        _optional_sidecar_identity(Path(f"{target}{suffix}"))

    if not created:
        readonly = sqlite3.connect(
            f"file:{quote(str(target))}?mode=ro",
            uri=True,
            timeout=2.0,
            isolation_level=None,
        )
        try:
            readonly.execute("PRAGMA query_only=ON")
            readonly.execute("PRAGMA trusted_schema=OFF")
            if (
                int(readonly.execute("PRAGMA application_id").fetchone()[0])
                != _LEDGER_APPLICATION_ID
                or int(readonly.execute("PRAGMA user_version").fetchone()[0])
                != _LEDGER_USER_VERSION
                or str(readonly.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                != "wal"
            ):
                raise LedgerCorruptionError(
                    "existing responder ledger lacks its custody marker"
                )
            _require_table(
                readonly,
                name="governed_patch_jobs",
                expected_info=_LEDGER_TABLE_INFO,
                error_type=LedgerCorruptionError,
            )
            objects = readonly.execute(
                "SELECT type, name FROM main.sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name LIMIT 3"
            ).fetchall()
            if [(str(row[0]), str(row[1])) for row in objects] != [
                ("table", "governed_patch_jobs")
            ]:
                raise LedgerCorruptionError(
                    "existing responder ledger contains foreign schema objects"
                )
        finally:
            readonly.close()
        if existing_identity() != identity:
            raise LedgerCorruptionError(
                "responder ledger custody changed during read-only admission"
            )

    connection = sqlite3.connect(target, timeout=30.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA trusted_schema=OFF")
    journal = str(connection.execute("PRAGMA main.journal_mode=WAL").fetchone()[0]).lower()
    connection.execute("PRAGMA main.synchronous=FULL")
    connection.execute("PRAGMA busy_timeout=30000")
    synchronous = int(connection.execute("PRAGMA main.synchronous").fetchone()[0])
    if journal != "wal" or synchronous != 2:
        connection.close()
        raise GovernedPatchResponderError("responder ledger could not enable WAL/FULL")
    if created:
        connection.execute(f"PRAGMA application_id={_LEDGER_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={_LEDGER_USER_VERSION}")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS governed_patch_jobs (
            event_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            packet_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            status TEXT NOT NULL,
            envelope_sha256 TEXT NOT NULL,
            envelope_json TEXT NOT NULL,
            delivery_record_path TEXT NOT NULL,
            delivery_record_sha256 TEXT NOT NULL,
            semantic_artifact_sha256 TEXT NOT NULL,
            projection_json TEXT NOT NULL,
            projection_sha256 TEXT NOT NULL,
            request_checkpoint_json TEXT NOT NULL,
            request_checkpoint_sha256 TEXT NOT NULL,
            input_sha256 TEXT NOT NULL,
            lease_owner TEXT,
            lease_boot_id TEXT,
            lease_token TEXT,
            lease_generation INTEGER NOT NULL,
            lease_acquired_at REAL,
            lease_expires_at REAL,
            provider_call_id TEXT,
            author_owner TEXT,
            author_boot_id TEXT,
            provider_started_at REAL,
            provider_receipt_json TEXT,
            provider_receipt_sha256 TEXT,
            candidate_checkpoint_json TEXT,
            candidate_checkpoint_sha256 TEXT,
            outcome_sha256 TEXT,
            terminal_at REAL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            checkpoint_sha256 TEXT NOT NULL,
            CHECK (phase IN ('INPUT_COMMITTED','PROVIDER_CALL_STARTED','TERMINAL_COMMITTED')),
            CHECK (status IN ('PENDING_AUTHORSHIP','CANDIDATE_DURABLE','PROVIDER_REFUSED'))
        )
        """
    )
    _require_table(
        connection,
        name="governed_patch_jobs",
        expected_info=_LEDGER_TABLE_INFO,
        error_type=LedgerCorruptionError,
    )
    if existing_identity() != identity:
        connection.close()
        raise LedgerCorruptionError("responder ledger custody changed before use")
    return connection


def _row_dict(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    return {name: row[name] for name in _LEDGER_COLUMNS}


def _checkpoint_digest(values: Mapping[str, Any]) -> str:
    payload = {field: values.get(field) for field in _CHECKPOINT_FIELDS}
    return _sha256(_canonical_bytes(payload, label="ledger checkpoint"))


def _validate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    values = _row_dict(row)
    if (
        values["schema_version"] != JOB_SCHEMA
        or values["phase"] not in _PHASES
        or values["status"] not in _STATUSES
        or values["event_id"] != values["packet_id"]
        or _SHA256.fullmatch(str(values["checkpoint_sha256"] or "")) is None
        or _checkpoint_digest(values) != values["checkpoint_sha256"]
    ):
        raise LedgerCorruptionError(
            "responder checkpoint digest or identity is corrupt"
        )
    for field in (
        "envelope_sha256",
        "delivery_record_sha256",
        "semantic_artifact_sha256",
        "projection_sha256",
        "request_checkpoint_sha256",
        "input_sha256",
    ):
        if _SHA256.fullmatch(str(values[field] or "")) is None:
            raise LedgerCorruptionError(f"responder checkpoint has invalid {field}")
    json_digests = (
        ("projection_json", "projection_sha256"),
        ("request_checkpoint_json", "request_checkpoint_sha256"),
    )
    for json_field, digest_field in json_digests:
        raw = str(values[json_field] or "")
        parsed = _strict_json(raw, label=json_field)
        if (
            _canonical_text(parsed, label=json_field) != raw
            or _sha256(raw.encode()) != values[digest_field]
        ):
            raise LedgerCorruptionError(
                f"responder checkpoint has corrupt {json_field}"
            )
    lease_fields = (
        values["lease_owner"],
        values["lease_boot_id"],
        values["lease_token"],
        values["lease_acquired_at"],
        values["lease_expires_at"],
    )
    has_lease = all(value is not None for value in lease_fields)
    if any(value is not None for value in lease_fields) and not has_lease:
        raise LedgerCorruptionError("responder checkpoint has a partial lease")
    if has_lease and float(values["lease_expires_at"]) <= float(
        values["lease_acquired_at"]
    ):
        raise LedgerCorruptionError("responder checkpoint lease chronology is corrupt")
    if values["phase"] == INPUT_COMMITTED:
        if (
            values["status"] != PENDING_AUTHORSHIP
            or values["provider_call_id"] is not None
            or not has_lease
        ):
            raise LedgerCorruptionError("INPUT_COMMITTED checkpoint is contradictory")
    elif values["phase"] == PROVIDER_CALL_STARTED:
        if (
            values["status"] != PENDING_AUTHORSHIP
            or not has_lease
            or not values["provider_call_id"]
            or not values["author_owner"]
            or not values["author_boot_id"]
            or values["provider_started_at"] is None
        ):
            raise LedgerCorruptionError(
                "PROVIDER_CALL_STARTED checkpoint is contradictory"
            )
    else:
        if (
            values["status"] not in _TERMINAL_STATUSES
            or has_lease
            or values["provider_receipt_json"] is None
            or values["provider_receipt_sha256"] is None
            or values["outcome_sha256"] is None
            or values["terminal_at"] is None
        ):
            raise LedgerCorruptionError(
                "terminal responder checkpoint is contradictory"
            )
        receipt_raw = str(values["provider_receipt_json"])
        receipt = _strict_json(receipt_raw, label="provider_receipt_json")
        if (
            type(receipt) is not dict
            or _canonical_text(receipt, label="provider receipt") != receipt_raw
            or _sha256(receipt_raw.encode()) != values["provider_receipt_sha256"]
        ):
            raise LedgerCorruptionError("provider receipt checkpoint is corrupt")
        candidate_raw = values["candidate_checkpoint_json"]
        candidate_sha = values["candidate_checkpoint_sha256"]
        if values["status"] == CANDIDATE_DURABLE:
            if candidate_raw is None or candidate_sha is None:
                raise LedgerCorruptionError(
                    "candidate terminal lacks candidate checkpoint"
                )
            candidate = _strict_json(str(candidate_raw), label="candidate checkpoint")
            if (
                type(candidate) is not dict
                or _canonical_text(candidate, label="candidate checkpoint")
                != candidate_raw
                or _sha256(str(candidate_raw).encode()) != candidate_sha
            ):
                raise LedgerCorruptionError("candidate checkpoint is corrupt")
        elif candidate_raw is not None or candidate_sha is not None:
            raise LedgerCorruptionError(
                "provider refusal carries a candidate checkpoint"
            )
    return values


def _input_values(
    delivery: BridgeDelivery,
    projection: SemanticProjection,
    parsed: ParsedRequest,
) -> dict[str, Any]:
    if _SHA256.fullmatch(projection.semantic_artifact_sha256) is None:
        raise GovernedPatchResponderError(
            "semantic projection lacks exact artifact sha256"
        )
    projection_json = _canonical_text(
        projection.checkpoint, label="semantic projection"
    )
    projection_sha = _sha256(projection_json.encode())
    request_json = _canonical_text(parsed.checkpoint, label="request checkpoint")
    request_sha = _sha256(request_json.encode())
    body = {
        "schema_version": JOB_SCHEMA,
        "event_id": delivery.event_id,
        "packet_id": delivery.packet_id,
        "envelope_sha256": delivery.envelope_sha256,
        "envelope_json": delivery.envelope_json,
        "delivery_record_path": str(delivery.delivery_record_path),
        "delivery_record_sha256": delivery.delivery_record_sha256,
        "semantic_artifact_sha256": projection.semantic_artifact_sha256,
        "projection_json": projection_json,
        "projection_sha256": projection_sha,
        "request_checkpoint_json": request_json,
        "request_checkpoint_sha256": request_sha,
    }
    body["input_sha256"] = _sha256(_canonical_bytes(body, label="responder input"))
    return body


def _same_input(row: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    fields = (
        "event_id",
        "packet_id",
        "envelope_sha256",
        "envelope_json",
        "delivery_record_path",
        "delivery_record_sha256",
        "semantic_artifact_sha256",
        "projection_json",
        "projection_sha256",
        "request_checkpoint_json",
        "request_checkpoint_sha256",
        "input_sha256",
    )
    if any(row[field] != expected[field] for field in fields):
        raise InputDriftError("current packet evidence differs from INPUT_COMMITTED")


def _same_pre_author_input(row: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    """Allow only the uncalled executor identity to rotate after lease expiry."""

    fields = (
        "event_id",
        "packet_id",
        "envelope_sha256",
        "envelope_json",
        "delivery_record_path",
        "delivery_record_sha256",
        "semantic_artifact_sha256",
        "projection_json",
        "projection_sha256",
    )
    if any(row[field] != expected[field] for field in fields):
        raise InputDriftError("current owner evidence differs from INPUT_COMMITTED")
    old_request = _strict_json(
        str(row["request_checkpoint_json"]), label="prior pre-author request"
    )
    new_request = _strict_json(
        str(expected["request_checkpoint_json"]), label="current pre-author request"
    )
    if not isinstance(old_request, dict) or not isinstance(new_request, dict):
        raise LedgerCorruptionError("pre-author request checkpoint is not an object")
    old_bindings = old_request.get("native_bindings")
    new_bindings = new_request.get("native_bindings")
    if not isinstance(old_bindings, dict) or not isinstance(new_bindings, dict):
        raise LedgerCorruptionError("pre-author request lacks native bindings")
    rotated = dict(old_request)
    rotated_bindings = dict(old_bindings)
    for field in ("executor_run_id", "executor_process_boot_id"):
        rotated_bindings[field] = new_bindings.get(field)
    rotated["native_bindings"] = rotated_bindings
    rotated["request_content_sha256"] = new_request.get("request_content_sha256")
    if rotated != new_request:
        raise InputDriftError("pre-author request changed beyond executor rotation")


def _insert_input(
    connection: sqlite3.Connection,
    expected: Mapping[str, Any],
    *,
    owner_id: str,
    boot_id: str,
    lease_token: str,
    now: float,
    lease_seconds: float,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        **expected,
        "phase": INPUT_COMMITTED,
        "status": PENDING_AUTHORSHIP,
        "lease_owner": owner_id,
        "lease_boot_id": boot_id,
        "lease_token": lease_token,
        "lease_generation": 1,
        "lease_acquired_at": now,
        "lease_expires_at": now + lease_seconds,
        "provider_call_id": None,
        "author_owner": None,
        "author_boot_id": None,
        "provider_started_at": None,
        "provider_receipt_json": None,
        "provider_receipt_sha256": None,
        "candidate_checkpoint_json": None,
        "candidate_checkpoint_sha256": None,
        "outcome_sha256": None,
        "terminal_at": None,
        "created_at": now,
        "updated_at": now,
    }
    values["checkpoint_sha256"] = _checkpoint_digest(values)
    placeholders = ",".join("?" for _ in _LEDGER_COLUMNS)
    connection.execute(
        f"INSERT INTO governed_patch_jobs ({','.join(_LEDGER_COLUMNS)}) VALUES ({placeholders})",
        tuple(values[name] for name in _LEDGER_COLUMNS),
    )
    return values


def _update_row(
    connection: sqlite3.Connection, values: dict[str, Any]
) -> dict[str, Any]:
    values["checkpoint_sha256"] = _checkpoint_digest(values)
    assignments = ",".join(f"{name} = ?" for name in _LEDGER_COLUMNS[1:])
    cursor = connection.execute(
        f"UPDATE governed_patch_jobs SET {assignments} WHERE event_id = ? AND checkpoint_sha256 = ?",
        tuple(values[name] for name in _LEDGER_COLUMNS[1:])
        + (values["event_id"], values.get("_prior_checkpoint")),
    )
    values.pop("_prior_checkpoint", None)
    if cursor.rowcount != 1:
        raise LedgerCorruptionError("responder checkpoint CAS lost")
    return values


def _fetch_row(connection: sqlite3.Connection, event_id: str) -> dict[str, Any] | None:
    rows = connection.execute(
        "SELECT * FROM governed_patch_jobs WHERE event_id = ? LIMIT 2",
        (event_id,),
    ).fetchall()
    if len(rows) > 1:
        raise LedgerCorruptionError("responder ledger contains ambiguous packet rows")
    return _validate_row(rows[0]) if rows else None


def _claim_input(
    connection: sqlite3.Connection,
    expected: Mapping[str, Any],
    *,
    owner_id: str,
    boot_id: str,
    now: float,
    lease_seconds: float,
) -> tuple[dict[str, Any], str, bool]:
    token = uuid.uuid4().hex
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _fetch_row(connection, str(expected["event_id"]))
        if row is None:
            row = _insert_input(
                connection,
                expected,
                owner_id=owner_id,
                boot_id=boot_id,
                lease_token=token,
                now=now,
                lease_seconds=lease_seconds,
            )
            connection.execute("COMMIT")
            return row, token, True
        if row["phase"] == TERMINAL_COMMITTED:
            _same_input(row, expected)
            connection.execute("COMMIT")
            return row, "", False
        if row["phase"] == PROVIDER_CALL_STARTED:
            _same_input(row, expected)
            connection.execute("COMMIT")
            return row, "", False
        expires = float(row["lease_expires_at"])
        if expires > now:
            raise LeaseUnavailableError(
                f"packet lease is active for {row['lease_owner']} boot {row['lease_boot_id']}"
            )
        _same_pre_author_input(row, expected)
        row["_prior_checkpoint"] = row["checkpoint_sha256"]
        row.update(
            {
                "request_checkpoint_json": expected["request_checkpoint_json"],
                "request_checkpoint_sha256": expected["request_checkpoint_sha256"],
                "input_sha256": expected["input_sha256"],
                "lease_owner": owner_id,
                "lease_boot_id": boot_id,
                "lease_token": token,
                "lease_generation": int(row["lease_generation"]) + 1,
                "lease_acquired_at": now,
                "lease_expires_at": now + lease_seconds,
                "updated_at": now,
            }
        )
        row = _update_row(connection, row)
        connection.execute("COMMIT")
        return row, token, True
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _provider_call_id(expected: Mapping[str, Any]) -> str:
    return "gpr_" + _sha256(
        _canonical_bytes(
            {
                "schema_version": JOB_SCHEMA,
                "event_id": expected["event_id"],
                "input_sha256": expected["input_sha256"],
            },
            label="provider call identity",
        )
    )


def _start_provider_call(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    lease_token: str,
    owner_id: str,
    boot_id: str,
    call_id: str,
    now: float,
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _fetch_row(connection, event_id)
        if row is None or row["phase"] != INPUT_COMMITTED:
            raise LedgerCorruptionError("provider call cannot start from current phase")
        if (
            row["lease_token"] != lease_token
            or row["lease_owner"] != owner_id
            or row["lease_boot_id"] != boot_id
            or float(row["lease_expires_at"]) <= now
        ):
            raise LeaseUnavailableError(
                "provider call lease is not owned by this process"
            )
        row["_prior_checkpoint"] = row["checkpoint_sha256"]
        row.update(
            {
                "phase": PROVIDER_CALL_STARTED,
                "provider_call_id": call_id,
                "author_owner": owner_id,
                "author_boot_id": boot_id,
                "provider_started_at": now,
                "updated_at": now,
            }
        )
        row = _update_row(connection, row)
        connection.execute("COMMIT")
        return row
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _claim_provider_recovery(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    owner_id: str,
    boot_id: str,
    now: float,
    lease_seconds: float,
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _fetch_row(connection, event_id)
        if row is None or row["phase"] != PROVIDER_CALL_STARTED:
            raise LedgerCorruptionError("provider recovery has no started call")
        if float(row["lease_expires_at"]) > now:
            raise LeaseUnavailableError(
                f"provider call lease is active for {row['lease_owner']} "
                f"boot {row['lease_boot_id']}"
            )
        row["_prior_checkpoint"] = row["checkpoint_sha256"]
        row.update(
            {
                "lease_owner": owner_id,
                "lease_boot_id": boot_id,
                "lease_token": uuid.uuid4().hex,
                "lease_generation": int(row["lease_generation"]) + 1,
                "lease_acquired_at": now,
                "lease_expires_at": now + lease_seconds,
                "updated_at": now,
            }
        )
        row = _update_row(connection, row)
        connection.execute("COMMIT")
        return row
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _rebind_unclaimed_provider_author(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    owner_id: str,
    boot_id: str,
    now: float,
) -> dict[str, Any]:
    """Move authorship identity only while external evidence proves no call claim."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _fetch_row(connection, event_id)
        if (
            row is None
            or row["phase"] != PROVIDER_CALL_STARTED
            or row["lease_owner"] != owner_id
            or row["lease_boot_id"] != boot_id
            or float(row["lease_expires_at"]) <= now
        ):
            raise LeaseUnavailableError(
                "safe provider restart lease is not owned by this process"
            )
        row["_prior_checkpoint"] = row["checkpoint_sha256"]
        row.update(
            {
                "author_owner": owner_id,
                "author_boot_id": boot_id,
                "provider_started_at": now,
                "updated_at": now,
            }
        )
        row = _update_row(connection, row)
        connection.execute("COMMIT")
        return row
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _candidate_checkpoint(candidate: object) -> dict[str, Any]:
    if isinstance(candidate, Mapping):
        payload = dict(candidate)
    elif hasattr(candidate, "bundle_sha256"):
        fields = (
            "bundle_root",
            "repo_root",
            "relative_dir",
            "bundle_sha256",
            "candidate_digest",
            "diff_sha256",
            "request_content_sha256",
            "source_sha256",
            "authorized_source_path",
            "semantic_artifact_sha256",
            "semantic_intent_sha256",
            "task_snapshot_sha256",
            "executor_agent_uid",
            "executor_run_id",
            "executor_process_boot_id",
        )
        payload = {
            field: getattr(candidate, field)
            for field in fields
            if hasattr(candidate, field)
        }
    elif is_dataclass(candidate):
        payload = asdict(candidate)
    else:
        raise GovernedPatchResponderError("provider candidate has no durable locator")
    for field in ("bundle_root", "repo_root"):
        if field in payload:
            payload[field] = str(payload[field])
    for field in (
        "repository_effect_authorized",
        "repository_effect_performed",
        "mission_control_completion_authorized",
    ):
        if field in payload and payload[field] is not False:
            raise GovernedPatchResponderError("provider candidate is authorizing")
    payload["repository_effect_authorized"] = False
    payload["repository_effect_performed"] = False
    payload["mission_control_completion_authorized"] = False
    return _json_value(payload, label="candidate checkpoint")


def _normalize_outcome(
    value: object,
    *,
    request: object,
    call_id: str,
    semantic_artifact_sha256: str,
    request_checkpoint: Mapping[str, Any],
) -> AuthorshipOutcome:
    from dharma_swarm.governed_patch_candidate_bundle import (
        CandidateBundle,
        load_candidate_bundle_artifact,
    )
    from dharma_swarm.governed_patch_evidence import (
        GovernedPatchEvidenceError,
        GovernedPatchRequest,
    )
    from dharma_swarm.governed_patch_provider_authorship import (
        ProviderAuthorshipResult,
        verify_provider_authorship_receipt,
    )

    if type(request) is not GovernedPatchRequest:
        raise GovernedPatchResponderError(
            "production outcome verification requires GovernedPatchRequest"
        )
    if type(value) is not ProviderAuthorshipResult:
        raise GovernedPatchResponderError(
            "provider must return an exact ProviderAuthorshipResult"
        )
    if dict(request_checkpoint) != _request_checkpoint(request):
        raise GovernedPatchResponderError(
            "provider outcome request checkpoint is not exact"
        )
    try:
        receipt_object = verify_provider_authorship_receipt(
            value.receipt,
            request=request,
            semantic_artifact_sha256=semantic_artifact_sha256,
        )
        if receipt_object.provider_call_id != call_id:
            raise GovernedPatchResponderError(
                "provider receipt call identity is misbound"
            )
        candidate_object = value.candidate_bundle
        if receipt_object.status == "authored":
            if type(candidate_object) is not CandidateBundle:
                raise GovernedPatchResponderError(
                    "authored provider result lacks exact CandidateBundle"
                )
            verified_candidate = load_candidate_bundle_artifact(
                receipt_object.evidence_root,
                receipt_object.candidate_bundle_sha256 or "",
                repo_root=request.repo_root,
                expected=request.bindings,
                accepted_base_sha=request.bindings.base_sha,
            )
            if (
                verified_candidate != candidate_object
                or verified_candidate.authorized_source_path
                != request.authorized_source_path
                or verified_candidate.semantic_artifact_sha256
                != semantic_artifact_sha256
                or verified_candidate.semantic_intent_sha256
                != request.semantic_intent_sha256
                or verified_candidate.task_snapshot_sha256
                != request.task_snapshot_sha256
                or verified_candidate.diff_sha256 != receipt_object.diff_sha256
            ):
                raise GovernedPatchResponderError(
                    "provider candidate artifact is not exactly request-bound"
                )
        elif receipt_object.status == "refused":
            if candidate_object is not None:
                raise GovernedPatchResponderError(
                    "provider refusal unexpectedly carries a candidate"
                )
            verified_candidate = None
        else:
            raise GovernedPatchResponderError(
                "provider returned an unsupported terminal status"
            )
    except GovernedPatchEvidenceError as exc:
        raise GovernedPatchResponderError(
            f"provider outcome evidence is invalid: {exc}"
        ) from exc
    return AuthorshipOutcome(
        receipt=_json_value(receipt_object.to_dict(), label="provider receipt"),
        candidate=(
            _candidate_checkpoint(verified_candidate)
            if verified_candidate is not None
            else None
        ),
    )


def _commit_outcome(
    connection: sqlite3.Connection,
    *,
    event_id: str,
    expected: Mapping[str, Any],
    call_id: str,
    outcome: AuthorshipOutcome,
    now: float,
) -> dict[str, Any]:
    receipt_json = _canonical_text(outcome.receipt, label="provider receipt")
    candidate_json = (
        _canonical_text(outcome.candidate, label="candidate checkpoint")
        if outcome.candidate is not None
        else None
    )
    terminal_status = (
        CANDIDATE_DURABLE if candidate_json is not None else PROVIDER_REFUSED
    )
    outcome_payload = {
        "status": terminal_status,
        "provider_receipt_sha256": _sha256(receipt_json.encode()),
        "candidate_checkpoint_sha256": (
            _sha256(candidate_json.encode()) if candidate_json is not None else None
        ),
    }
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = _fetch_row(connection, event_id)
        if row is None:
            raise LedgerCorruptionError("provider outcome has no responder job")
        _same_input(row, expected)
        if row["phase"] == TERMINAL_COMMITTED:
            if (
                row["status"] != terminal_status
                or row["provider_receipt_json"] != receipt_json
                or row["candidate_checkpoint_json"] != candidate_json
            ):
                raise InputDriftError(
                    "recovered provider outcome contradicts terminal row"
                )
            connection.execute("COMMIT")
            return row
        if row["phase"] != PROVIDER_CALL_STARTED or row["provider_call_id"] != call_id:
            raise LedgerCorruptionError("provider outcome does not match started call")
        row["_prior_checkpoint"] = row["checkpoint_sha256"]
        row.update(
            {
                "phase": TERMINAL_COMMITTED,
                "status": terminal_status,
                "lease_owner": None,
                "lease_boot_id": None,
                "lease_token": None,
                "lease_acquired_at": None,
                "lease_expires_at": None,
                "provider_receipt_json": receipt_json,
                "provider_receipt_sha256": outcome_payload["provider_receipt_sha256"],
                "candidate_checkpoint_json": candidate_json,
                "candidate_checkpoint_sha256": outcome_payload[
                    "candidate_checkpoint_sha256"
                ],
                "outcome_sha256": _sha256(
                    _canonical_bytes(outcome_payload, label="provider outcome")
                ),
                "terminal_at": now,
                "updated_at": now,
            }
        )
        row = _update_row(connection, row)
        connection.execute("COMMIT")
        return row
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _observation(
    row: Mapping[str, Any],
    *,
    boot_id: str,
    provider_called: bool,
    recovered: bool,
) -> ResponderObservation:
    validated = _validate_row(row)
    if validated["phase"] != TERMINAL_COMMITTED:
        raise LedgerCorruptionError("nonterminal row cannot mint terminal observation")
    receipt = _strict_json(
        str(validated["provider_receipt_json"]), label="provider receipt"
    )
    candidate = (
        _strict_json(
            str(validated["candidate_checkpoint_json"]), label="candidate checkpoint"
        )
        if validated["candidate_checkpoint_json"] is not None
        else None
    )
    return ResponderObservation(
        event_id=str(validated["event_id"]),
        status=str(validated["status"]),
        phase=str(validated["phase"]),
        provider_call_id=str(validated["provider_call_id"]),
        provider_receipt=receipt,
        candidate_checkpoint=candidate,
        input_sha256=str(validated["input_sha256"]),
        authored_by_owner=str(validated["author_owner"]),
        authored_by_boot_id=str(validated["author_boot_id"]),
        observed_by_boot_id=boot_id,
        provider_called=provider_called,
        recovered=recovered,
    )


async def _resolve(value: object | Awaitable[object]) -> object:
    return await value if inspect.isawaitable(value) else value


async def process_once(
    *,
    bridge_db: Path,
    delivery_record_path: Path,
    ledger_db: Path,
    repo_root: Path,
    event_id: str,
    owner_id: str,
    boot_id: str,
    validate_semantic_projection: ProjectionValidator,
    parse_delivery: RequestParser,
    author_candidate: CandidateAuthor,
    recover_candidate: CandidateRecoverer | None = None,
    inspect_provider_call: ProviderCallInspector | None = None,
    verify_authorship_outcome: AuthorshipOutcomeVerifier | None = None,
    delivery_loader: DeliveryLoader = load_bridge_delivery,
    lease_seconds: float = 60.0,
    clock: Callable[[], float] = time.time,
    checkpoint_hook: CheckpointHook | None = None,
) -> ResponderObservation:
    """Advance exactly one packet without subscribing, ACKing, or authorizing effects."""

    if _TOKEN.fullmatch(owner_id) is None or _TOKEN.fullmatch(boot_id) is None:
        raise GovernedPatchResponderError("owner_id and boot_id must be stable tokens")
    if not math.isfinite(lease_seconds) or lease_seconds <= 0:
        raise GovernedPatchResponderError("lease_seconds must be positive and finite")
    outcome_verifier = verify_authorship_outcome or _normalize_outcome
    delivery = delivery_loader(Path(bridge_db), event_id, Path(delivery_record_path))
    projection_value = await _resolve(validate_semantic_projection(delivery))
    if type(projection_value) is not SemanticProjection:
        raise GovernedPatchResponderError(
            "semantic validator did not return SemanticProjection"
        )
    connection = _ledger_connection(Path(ledger_db), repo_root=Path(repo_root))
    try:
        prior = _fetch_row(connection, event_id)
        prior_checkpoint = None
        if prior is not None and prior["phase"] != INPUT_COMMITTED:
            parsed_prior = _strict_json(
                str(prior["request_checkpoint_json"]),
                label="prior request checkpoint",
            )
            if type(parsed_prior) is not dict:
                raise LedgerCorruptionError("prior request checkpoint is not an object")
            prior_checkpoint = parsed_prior
        parsed_value = await _resolve(
            parse_delivery(delivery, projection_value, prior_checkpoint)
        )
        if type(parsed_value) is not ParsedRequest:
            raise GovernedPatchResponderError(
                "delivery parser did not return ParsedRequest"
            )
        expected = _input_values(delivery, projection_value, parsed_value)
        now = float(clock())
        row, token, claimed = _claim_input(
            connection,
            expected,
            owner_id=owner_id,
            boot_id=boot_id,
            now=now,
            lease_seconds=lease_seconds,
        )
        if row["phase"] == TERMINAL_COMMITTED:
            if recover_candidate is not None:
                recovered_value = await _resolve(
                    recover_candidate(
                        parsed_value.request,
                        semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
                        provider_call_id=str(row["provider_call_id"]),
                    )
                )
                if recovered_value is None:
                    raise LedgerCorruptionError(
                        "terminal provider evidence is no longer recoverable"
                    )
                recovered_outcome = outcome_verifier(
                    recovered_value,
                    request=parsed_value.request,
                    call_id=str(row["provider_call_id"]),
                    semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
                    request_checkpoint=parsed_value.checkpoint,
                )
                row = _commit_outcome(
                    connection,
                    event_id=event_id,
                    expected=expected,
                    call_id=str(row["provider_call_id"]),
                    outcome=recovered_outcome,
                    now=float(clock()),
                )
            return _observation(
                row,
                boot_id=boot_id,
                provider_called=False,
                recovered=False,
            )
        call_id = str(row.get("provider_call_id") or _provider_call_id(expected))
        if row["phase"] == PROVIDER_CALL_STARTED:
            _claim_provider_recovery(
                connection,
                event_id=event_id,
                owner_id=owner_id,
                boot_id=boot_id,
                now=float(clock()),
                lease_seconds=lease_seconds,
            )
            provider_state = None
            if inspect_provider_call is not None:
                provider_state = await _resolve(
                    inspect_provider_call(
                        parsed_value.request,
                        semantic_artifact_sha256=(
                            projection_value.semantic_artifact_sha256
                        ),
                        provider_call_id=call_id,
                    )
                )
                if provider_state not in {"absent", "claimed", "terminal"}:
                    raise GovernedPatchResponderError(
                        "provider evidence inspector returned an invalid state"
                    )
            if provider_state == "absent":
                rebound = _rebind_unclaimed_provider_author(
                    connection,
                    event_id=event_id,
                    owner_id=owner_id,
                    boot_id=boot_id,
                    now=float(clock()),
                )
                if checkpoint_hook:
                    checkpoint_hook("PROVIDER_CALL_SAFE_REENTRY", dict(rebound))
                authored = await _resolve(
                    author_candidate(
                        parsed_value.request,
                        semantic_artifact_sha256=(
                            projection_value.semantic_artifact_sha256
                        ),
                        provider_call_id=call_id,
                    )
                )
                outcome = outcome_verifier(
                    authored,
                    request=parsed_value.request,
                    call_id=call_id,
                    semantic_artifact_sha256=(
                        projection_value.semantic_artifact_sha256
                    ),
                    request_checkpoint=parsed_value.checkpoint,
                )
                terminal = _commit_outcome(
                    connection,
                    event_id=event_id,
                    expected=expected,
                    call_id=call_id,
                    outcome=outcome,
                    now=float(clock()),
                )
                if checkpoint_hook:
                    checkpoint_hook(TERMINAL_COMMITTED, dict(terminal))
                return _observation(
                    terminal,
                    boot_id=boot_id,
                    provider_called=True,
                    recovered=False,
                )
            if provider_state == "claimed":
                raise ProviderCallUncertainError(
                    "provider claim exists without a terminal locator; redrive forbidden"
                )
            if recover_candidate is None:
                raise ProviderCallUncertainError(
                    "provider call was checkpointed; recovery is required before retry"
                )
            recovered_value = await _resolve(
                recover_candidate(
                    parsed_value.request,
                    semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
                    provider_call_id=call_id,
                )
            )
            if recovered_value is None:
                raise ProviderCallUncertainError(
                    "provider call may have happened; no immutable outcome was recovered"
                )
            outcome = outcome_verifier(
                recovered_value,
                request=parsed_value.request,
                call_id=call_id,
                semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
                request_checkpoint=parsed_value.checkpoint,
            )
            terminal = _commit_outcome(
                connection,
                event_id=event_id,
                expected=expected,
                call_id=call_id,
                outcome=outcome,
                now=float(clock()),
            )
            if checkpoint_hook:
                checkpoint_hook(TERMINAL_COMMITTED, dict(terminal))
            return _observation(
                terminal,
                boot_id=boot_id,
                provider_called=False,
                recovered=True,
            )
        if not claimed or not token:
            raise LedgerCorruptionError("INPUT_COMMITTED lease was not claimed")
        if checkpoint_hook:
            checkpoint_hook(INPUT_COMMITTED, dict(row))
        started = _start_provider_call(
            connection,
            event_id=event_id,
            lease_token=token,
            owner_id=owner_id,
            boot_id=boot_id,
            call_id=call_id,
            now=float(clock()),
        )
        if checkpoint_hook:
            checkpoint_hook(PROVIDER_CALL_STARTED, dict(started))
        authored = await _resolve(
            author_candidate(
                parsed_value.request,
                semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
                provider_call_id=call_id,
            )
        )
        outcome = outcome_verifier(
            authored,
            request=parsed_value.request,
            call_id=call_id,
            semantic_artifact_sha256=projection_value.semantic_artifact_sha256,
            request_checkpoint=parsed_value.checkpoint,
        )
        if checkpoint_hook:
            checkpoint_hook("PROVIDER_OUTCOME_READY", {"provider_call_id": call_id})
        terminal = _commit_outcome(
            connection,
            event_id=event_id,
            expected=expected,
            call_id=call_id,
            outcome=outcome,
            now=float(clock()),
        )
        if checkpoint_hook:
            checkpoint_hook(TERMINAL_COMMITTED, dict(terminal))
        return _observation(
            terminal,
            boot_id=boot_id,
            provider_called=True,
            recovered=False,
        )
    finally:
        connection.close()


def _intent(delivery: BridgeDelivery) -> dict[str, Any]:
    value = _strict_json(delivery.content, label="governed patch intent")
    if type(value) is not dict or frozenset(value) != _INTENT_KEYS:
        raise GovernedPatchResponderError(
            "governed patch intent has a non-closed shape"
        )
    if value.get("schema_version") != INTENT_SCHEMA:
        raise GovernedPatchResponderError("governed patch intent schema is unsupported")
    return value


def _trusted_git() -> tuple[Path, dict[str, str]]:
    git = Path("/usr/bin/git")
    if not git.is_file() or not os.access(git, os.X_OK):
        raise GovernedPatchResponderError("trusted Git executable is unavailable")
    return git, {
        "HOME": "/nonexistent",
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }


def _git_head(repo_root: Path) -> str:
    repo = repo_root.expanduser().resolve(strict=True)
    git, environment = _trusted_git()
    result = subprocess.run(
        [str(git), "-c", "core.fsmonitor=false", "rev-parse", "--show-toplevel", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
        env=environment,
    )
    lines = result.stdout.splitlines()
    if (
        result.returncode != 0
        or len(lines) != 2
        or Path(lines[0]).resolve(strict=True) != repo
        or re.fullmatch(r"[0-9a-f]{40}", lines[1]) is None
    ):
        raise GovernedPatchResponderError("canonical repository HEAD is unavailable")
    status = subprocess.run(
        [
            str(git),
            "-c",
            "core.fsmonitor=false",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=none",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
        env=environment,
    )
    if status.returncode != 0 or status.stdout:
        raise GovernedPatchResponderError(
            "canonical repository must be clean before candidate authorship"
        )
    return lines[1]


def _git_blob_at_head(repo_root: Path, head: str, relative_path: str) -> bytes:
    from dharma_swarm.governed_patch_evidence import MAX_SOURCE_BYTES

    repo = repo_root.expanduser().resolve(strict=True)
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GovernedPatchResponderError("Git blob lookup has an invalid HEAD")
    git, environment = _trusted_git()
    object_name = f"{head}:{relative_path}"
    size = subprocess.run(
        [str(git), "-c", "core.fsmonitor=false", "cat-file", "-s", object_name],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=10.0,
        env=environment,
    )
    try:
        blob_size = int(size.stdout.strip())
    except ValueError as exc:
        raise GovernedPatchResponderError(
            "authorized source is not an exact Git blob"
        ) from exc
    if size.returncode != 0 or blob_size < 0 or blob_size > MAX_SOURCE_BYTES:
        raise GovernedPatchResponderError(
            "authorized Git blob is unavailable or exceeds its bound"
        )
    blob = subprocess.run(
        [str(git), "-c", "core.fsmonitor=false", "cat-file", "blob", object_name],
        cwd=repo,
        check=False,
        capture_output=True,
        timeout=10.0,
        env=environment,
    )
    if blob.returncode != 0 or len(blob.stdout) != blob_size:
        raise GovernedPatchResponderError("authorized Git blob changed during read")
    return blob.stdout


def _request_checkpoint(request: object) -> dict[str, Any]:
    bindings = getattr(request, "bindings", None)
    to_dict = getattr(bindings, "to_dict", None)
    if not callable(to_dict):
        raise GovernedPatchResponderError(
            "governed patch request lacks native bindings"
        )
    fields = {
        "schema_version": getattr(request, "schema_version", None),
        "native_bindings": to_dict(),
        "authorized_source_path": getattr(request, "authorized_source_path", None),
        "oracle_argv": list(getattr(request, "oracle_argv", ())),
        "request_content_sha256": getattr(request, "request_content_sha256", None),
        "source_sha256": getattr(request, "source_sha256", None),
        "semantic_intent_sha256": getattr(request, "semantic_intent_sha256", None),
        "task_snapshot_sha256": getattr(request, "task_snapshot_sha256", None),
    }
    return _json_value(fields, label="governed patch request checkpoint")


def _semantic_approval_checkpoint(
    *,
    outbox_root: Path,
    trusted_receipt_roots: Sequence[Path],
    agent_uid: str,
    packet_id: str,
    expected_artifact_sha256: str,
) -> dict[str, Any]:
    """Refine semantic execution into an exact authoring-approval claim.

    Canonical A2A ``EXECUTED`` is a liveness/evidence-chain type.  Provider
    authorship additionally requires a passing verdict, explicit intent
    acknowledgement, and explicit request understanding from that same
    content-addressed semantic artifact.
    """
    from dharma_swarm.mission_control_a2a_io import (
        _trusted_link,
        read_json,
        safe_file,
    )
    from dharma_swarm.mission_control_contract import MissionControlError
    from dharma_swarm.operator_core.semantic_receipt import (
        PASSING_VERDICTS,
        SemanticReceiptValidationError,
        validate_semantic_receipt,
    )

    try:
        artifact_path = safe_file(
            outbox_root,
            agent_uid,
            f"{packet_id}-domain-reply.json",
        )
        artifact, artifact_raw = read_json(artifact_path, limit=_MAX_JSON_BYTES)
        if _sha256(artifact_raw) != expected_artifact_sha256:
            raise GovernedPatchResponderError(
                "semantic approval artifact changed after canonical projection"
            )
        semantic_path = _trusted_link(
            artifact.get("semantic_receipt_path"),
            tuple(trusted_receipt_roots),
            "semantic receipt path",
        )
        semantic, semantic_raw = read_json(semantic_path, limit=_MAX_JSON_BYTES)
        validated = validate_semantic_receipt(semantic)
    except GovernedPatchResponderError:
        raise
    except (MissionControlError, SemanticReceiptValidationError) as exc:
        raise GovernedPatchResponderError(
            "semantic authoring approval evidence is invalid"
        ) from exc
    if validated != semantic:
        raise GovernedPatchResponderError(
            "semantic authoring approval is not canonically normalized"
        )
    if (
        semantic.get("verdict") not in PASSING_VERDICTS
        or semantic.get("intent_ack") is not True
        or semantic.get("understood_request") is not True
        or semantic.get("authored_by_model") is not True
        or semantic.get("failure_type") != ""
        or semantic.get("semantic_reply_claim") is not True
        or semantic.get("peer_model_processed_claim") is not True
    ):
        raise GovernedPatchResponderError(
            "semantic execution does not carry authoring approval"
        )
    return {
        "schema_version": "dharma.governed_patch.semantic_approval.v1",
        "semantic_receipt_sha256": _sha256(semantic_raw),
        "semantic_receipt_id": semantic.get("receipt_id"),
        "verdict": semantic.get("verdict"),
        "intent_ack": True,
        "understood_request": True,
        "authored_by_model": True,
        "failure_type": "",
    }


def _build_default_projection_validator(
    *,
    mission_id: str,
    task_id: str,
    task_db: Path,
    runtime_db: Path,
    inbox_root: Path,
    semantic_job_root: Path,
    responder_state_root: Path,
    outbox_root: Path,
    trusted_receipt_roots: Sequence[Path],
) -> ProjectionValidator:
    async def validate(delivery: BridgeDelivery) -> SemanticProjection:
        from dharma_swarm.mission_control_a2a import A2AEvidencePhase
        from dharma_swarm.mission_control_a2a_projection import (
            MissionControlA2AProjection,
        )
        from dharma_swarm.runtime_state import RuntimeStateStore
        from dharma_swarm.task_board import TaskBoard

        projection = MissionControlA2AProjection(
            TaskBoard(task_db),
            RuntimeStateStore(runtime_db, include_memory_plane=False),
            inbox_root=inbox_root,
            semantic_job_root=semantic_job_root,
            responder_state_root=responder_state_root,
            outbox_root=outbox_root,
            trusted_receipt_roots=tuple(trusted_receipt_roots),
        )
        observation = await projection.observe(mission_id, task_id)
        if not observation:
            raise GovernedPatchResponderError(
                "canonical semantic projection did not mint an observation"
            )
        ref = observation.native_ref
        if (
            observation.phase != A2AEvidencePhase.EXECUTED
            or observation.semantic_job_status != "PENDING"
            or _SHA256.fullmatch(observation.artifact_sha256) is None
            or ref.packet_id != delivery.event_id
            or ref.delivery_id != delivery.delivery_id
            or ref.content_sha256 != delivery.content_sha256
            or observation.envelope_sha256 != delivery.envelope_sha256
        ):
            raise GovernedPatchResponderError(
                "canonical semantic projection does not prove exact execution"
            )
        checkpoint = observation.to_dict()
        checkpoint["governed_patch_semantic_approval"] = (
            _semantic_approval_checkpoint(
                outbox_root=outbox_root,
                trusted_receipt_roots=trusted_receipt_roots,
                agent_uid=ref.agent_uid,
                packet_id=ref.packet_id,
                expected_artifact_sha256=observation.artifact_sha256,
            )
        )
        return SemanticProjection(
            semantic_artifact_sha256=observation.artifact_sha256,
            checkpoint=checkpoint,
            native=observation,
        )

    return validate


def _build_default_request_parser(
    *,
    repo_root: Path,
    task_db: Path,
    owner_id: str,
    executor_run_id: str,
    boot_id: str,
) -> RequestParser:
    async def parse(
        delivery: BridgeDelivery,
        projection: SemanticProjection,
        prior_checkpoint: Mapping[str, Any] | None,
    ) -> ParsedRequest:
        from dharma_swarm.governed_patch_evidence import (
            NativePatchBindings,
            build_governed_patch_request_v2_content,
            governed_patch_task_snapshot_sha256,
            parse_governed_patch_request,
        )
        from dharma_swarm.mission_control_a2a_candidate import (
            require_task_native_ref,
        )
        from dharma_swarm.mission_control_a2a_io import read_task
        from dharma_swarm.mission_control_contract import (
            GOVERNED_PATCH_COMPLETION_CONTRACT,
            SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
            MissionControlError,
            completion_contract_from_metadata,
        )
        from dharma_swarm.models import TaskStatus

        intent = _intent(delivery)
        observation = projection.native
        ref = getattr(observation, "native_ref", None)
        if ref is None:
            raise GovernedPatchResponderError("semantic projection lacks native ref")
        if (
            intent.get("mission_id") != ref.mission_id
            or intent.get("task_id") != ref.task_id
            or intent.get("proposal_id") != ref.proposal_id
            or owner_id != ref.agent_uid
        ):
            raise GovernedPatchResponderError("intent disagrees with Mission Control")
        task = read_task(task_db, ref.task_id)
        if (
            task is None
            or task.metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
            or task.metadata.get("mission_id") != ref.mission_id
        ):
            raise GovernedPatchResponderError("canonical task snapshot is unavailable")
        try:
            require_task_native_ref(task.metadata, ref)
        except MissionControlError as exc:
            raise GovernedPatchResponderError(
                "canonical task A2A binding changed after semantic projection"
            ) from exc
        if (
            task.status is not TaskStatus.PENDING
            or task.assigned_to is not None
            or task.result is not None
        ):
            raise GovernedPatchResponderError(
                "canonical task is not pending, unassigned, and result-free"
            )
        contract = completion_contract_from_metadata(task.metadata)
        if contract != GOVERNED_PATCH_COMPLETION_CONTRACT:
            raise GovernedPatchResponderError(
                "task lacks governed patch completion contract"
            )
        creation_hash = task.metadata.get("mission_task_creation_hash")
        if type(creation_hash) is not str or _SHA256.fullmatch(creation_hash) is None:
            raise GovernedPatchResponderError("task creation hash is malformed")
        task_snapshot_sha = governed_patch_task_snapshot_sha256(
            mission_id=ref.mission_id,
            task_id=ref.task_id,
            title=task.title,
            description=task.description,
            mission_task_creation_hash=creation_hash,
            completion_contract=contract,
            status=task.status.value,
            assigned_to=task.assigned_to,
            result=task.result,
        )
        accepted_base_sha = _git_head(repo_root)
        if intent.get("base_sha") != accepted_base_sha:
            raise GovernedPatchResponderError("intent base_sha is not release HEAD")
        semantic_intent = intent.get("semantic_intent")
        if type(semantic_intent) is not str or not semantic_intent.strip():
            raise GovernedPatchResponderError("semantic_intent is empty")
        binding_values: dict[str, Any] = {
            "mission_id": ref.mission_id,
            "task_id": ref.task_id,
            "attempt_id": ref.packet_id,
            "lease_id": ref.delivery_id,
            "packet_id": ref.packet_id,
            "correlation_id": ref.correlation_id,
            "delivery_id": ref.delivery_id,
            "proposal_id": ref.proposal_id,
            "base_sha": accepted_base_sha,
            "executor_agent_uid": owner_id,
            "executor_run_id": executor_run_id,
            "executor_process_boot_id": boot_id,
        }
        if prior_checkpoint is not None:
            prior_bindings = prior_checkpoint.get("native_bindings")
            if not isinstance(prior_bindings, Mapping):
                raise LedgerCorruptionError("prior request lacks native bindings")
            fixed_fields = tuple(binding_values)[:-2]
            if any(
                prior_bindings.get(field) != binding_values[field]
                for field in fixed_fields
            ):
                raise InputDriftError("prior request native bindings drifted")
            if prior_bindings.get("executor_agent_uid") != owner_id:
                raise InputDriftError("prior request executor owner drifted")
            binding_values["executor_run_id"] = prior_bindings.get("executor_run_id")
            binding_values["executor_process_boot_id"] = prior_bindings.get(
                "executor_process_boot_id"
            )
        bindings = NativePatchBindings(**binding_values)
        content = build_governed_patch_request_v2_content(
            bindings,
            authorized_source_path=intent.get("authorized_source_path"),
            oracle_argv=intent.get("oracle_argv"),
            semantic_intent=semantic_intent,
            task_snapshot_sha256=task_snapshot_sha,
        )
        request = parse_governed_patch_request(
            content,
            repo_root=repo_root,
            expected=bindings,
            accepted_base_sha=accepted_base_sha,
            expected_semantic_intent=semantic_intent,
            expected_task_snapshot_sha256=task_snapshot_sha,
        )
        if request.source_bytes != _git_blob_at_head(
            repo_root,
            accepted_base_sha,
            request.authorized_source_path,
        ):
            raise GovernedPatchResponderError(
                "captured source is not the authorized release HEAD blob"
            )
        if _git_head(repo_root) != accepted_base_sha:
            raise GovernedPatchResponderError(
                "canonical repository changed while request source was captured"
            )
        return ParsedRequest(request=request, checkpoint=_request_checkpoint(request))

    return parse


def _build_default_author(
    *, evidence_root: Path, timeout_seconds: float
) -> CandidateAuthor:
    async def author(
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> object:
        from dharma_swarm.governed_patch_evidence import GovernedPatchEvidenceError
        from dharma_swarm.governed_patch_provider_authorship import (
            ProviderCallIndeterminateError,
            author_governed_patch,
        )

        try:
            return await author_governed_patch(
                request,
                evidence_root=evidence_root,
                semantic_artifact_sha256=semantic_artifact_sha256,
                provider_call_id=provider_call_id,
                timeout_seconds=timeout_seconds,
            )
        except ProviderCallIndeterminateError as exc:
            raise ProviderCallUncertainError(str(exc)) from exc
        except GovernedPatchEvidenceError as exc:
            raise GovernedPatchResponderError(
                f"provider authorship refused before terminal evidence: {exc}"
            ) from exc

    return author


def _build_default_recoverer(*, evidence_root: Path) -> CandidateRecoverer:
    def recover(
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> object | None:
        from dharma_swarm.governed_patch_evidence import GovernedPatchEvidenceError
        from dharma_swarm.governed_patch_provider_authorship import (
            ProviderCallIndeterminateError,
            recover_provider_authorship_result,
        )

        try:
            return recover_provider_authorship_result(
                request,
                evidence_root=evidence_root,
                semantic_artifact_sha256=semantic_artifact_sha256,
                provider_call_id=provider_call_id,
            )
        except ProviderCallIndeterminateError as exc:
            raise ProviderCallUncertainError(str(exc)) from exc
        except GovernedPatchEvidenceError as exc:
            raise GovernedPatchResponderError(
                f"provider recovery evidence is invalid: {exc}"
            ) from exc

    return recover


def _build_default_provider_inspector(
    *, evidence_root: Path
) -> ProviderCallInspector:
    def inspect_call(
        request: object,
        *,
        semantic_artifact_sha256: str,
        provider_call_id: str,
    ) -> str:
        from dharma_swarm.governed_patch_evidence import GovernedPatchEvidenceError
        from dharma_swarm.governed_patch_provider_authorship import (
            inspect_provider_call_evidence,
        )

        try:
            return inspect_provider_call_evidence(
                request,
                evidence_root=evidence_root,
                semantic_artifact_sha256=semantic_artifact_sha256,
                provider_call_id=provider_call_id,
            ).value
        except GovernedPatchEvidenceError as exc:
            raise GovernedPatchResponderError(
                f"provider call evidence is invalid: {exc}"
            ) from exc

    return inspect_call


def _canonical_custody_paths(
    *,
    bridge_db: Path,
    semantic_job_root: Path,
    repo_root: Path,
    owner_id: str,
) -> tuple[Path, Path]:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", owner_id) is None:
        raise GovernedPatchResponderError("owner_id is not a canonical custody token")
    from dharma_swarm.mission_control_a2a_io import safe_file
    from dharma_swarm.mission_control_contract import MissionControlError

    bridge = bridge_db.expanduser().resolve(strict=True)
    try:
        canonical_bridge = safe_file(
            semantic_job_root,
            f"{owner_id}.sqlite3",
        )
    except MissionControlError as exc:
        raise GovernedPatchResponderError(
            "canonical semantic-job database is unavailable"
        ) from exc
    if bridge != canonical_bridge:
        raise GovernedPatchResponderError(
            "bridge database is not the canonical semantic-job database"
        )
    repo = repo_root.expanduser().resolve(strict=True)
    custody = (bridge.parent / "governed_patch_custody" / owner_id).resolve(
        strict=False
    )
    if custody == repo or custody.is_relative_to(repo) or repo.is_relative_to(custody):
        raise GovernedPatchResponderError(
            "bridge-derived custody must be disjoint from the release repository"
        )
    return custody / "responder.sqlite3", custody / "evidence"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        allow_abbrev=False,
    )
    parser.add_argument("mode", choices=("once", "serve"), nargs="?", default="once")
    parser.add_argument("--bridge-db", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--task-db", required=True)
    parser.add_argument("--runtime-db", required=True)
    parser.add_argument("--inbox-root", required=True)
    parser.add_argument("--semantic-job-root", required=True)
    parser.add_argument("--responder-state-root", required=True)
    parser.add_argument("--outbox-root", required=True)
    parser.add_argument("--trusted-receipt-root", action="append", default=[])
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--executor-run-id", required=True)
    parser.add_argument("--boot-id", default="")
    parser.add_argument("--packet-id", default="")
    parser.add_argument("--delivery-record", default="")
    parser.add_argument("--lease-seconds", type=float, default=60.0)
    parser.add_argument("--provider-timeout", type=float, default=180.0)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    return parser


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


async def _main_async(args: argparse.Namespace) -> int:
    if not args.packet_id or not args.delivery_record:
        raise GovernedPatchResponderError(
            f"{args.mode} mode requires one exact --packet-id and --delivery-record"
        )
    for value, label in (
        (args.lease_seconds, "lease-seconds"),
        (args.provider_timeout, "provider-timeout"),
        (args.interval_seconds, "interval-seconds"),
    ):
        if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
            raise GovernedPatchResponderError(
                f"--{label} must be positive and finite"
            )
    repo_root = _path(args.repo_root)
    boot_id = args.boot_id or f"boot-{uuid.uuid4().hex}"
    bridge_db = _path(args.bridge_db)
    semantic_job_root = _path(args.semantic_job_root)
    ledger_db, evidence_root = _canonical_custody_paths(
        bridge_db=bridge_db,
        semantic_job_root=semantic_job_root,
        repo_root=repo_root,
        owner_id=args.owner_id,
    )
    inbox_root = _path(args.inbox_root)
    validator = _build_default_projection_validator(
        mission_id=args.mission_id,
        task_id=args.task_id,
        task_db=_path(args.task_db),
        runtime_db=_path(args.runtime_db),
        inbox_root=inbox_root,
        semantic_job_root=semantic_job_root,
        responder_state_root=_path(args.responder_state_root),
        outbox_root=_path(args.outbox_root),
        trusted_receipt_roots=tuple(_path(item) for item in args.trusted_receipt_root),
    )
    request_parser = _build_default_request_parser(
        repo_root=repo_root,
        task_db=_path(args.task_db),
        owner_id=args.owner_id,
        executor_run_id=args.executor_run_id,
        boot_id=boot_id,
    )
    author = _build_default_author(
        evidence_root=evidence_root,
        timeout_seconds=args.provider_timeout,
    )
    recover = _build_default_recoverer(evidence_root=evidence_root)
    inspector = _build_default_provider_inspector(evidence_root=evidence_root)

    async def run(event_id: str, delivery_path: Path) -> ResponderObservation:
        return await process_once(
            bridge_db=bridge_db,
            delivery_record_path=delivery_path,
            ledger_db=ledger_db,
            repo_root=repo_root,
            event_id=event_id,
            owner_id=args.owner_id,
            boot_id=boot_id,
            validate_semantic_projection=validator,
            parse_delivery=request_parser,
            author_candidate=author,
            recover_candidate=recover,
            inspect_provider_call=inspector,
            lease_seconds=args.lease_seconds,
        )

    while True:
        try:
            observations = [await run(args.packet_id, _path(args.delivery_record))]
        except (LeaseUnavailableError, ProviderCallUncertainError) as exc:
            if args.mode == "once":
                raise
            print(f"governed patch responder waiting: {exc}", file=os.sys.stderr)
            await asyncio.sleep(max(0.1, args.interval_seconds))
            continue
        payload = [asdict(observation) for observation in observations]
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            for observation in observations:
                print(
                    f"{observation.status} event_id={observation.event_id} "
                    f"provider_call_id={observation.provider_call_id}"
                )
        return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except GovernedPatchResponderError as exc:
        print(f"governed patch responder refused: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
