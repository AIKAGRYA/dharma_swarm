"""Exact, immutable execution-identity persistence for RuntimeState."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Callable, Mapping
from typing import Any

from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity

EXACT_EXECUTION_IDENTITY_SOURCE_PREFIX = "exact:"

EXECUTION_IDENTITY_CONFLICT_FIELDS = (
    "trace_id",
    "correlation_id",
    "task_id",
    "claim_id",
    "idempotency_key",
    "causation_id",
    "parent_run_id",
    "agent_id",
    "session_id",
    "external_a2a_task_id",
    "message_id",
    "event_id",
    "artifact_id",
    "proposal_id",
)


def canonical_finite_json_value(value: Any, *, surface: str) -> Any:
    """Return the one JSON value accepted by exact evidence writers."""

    active_containers: set[int] = set()

    def normalize(inner: Any, path: str) -> Any:
        if inner is None or type(inner) in (bool, str, int):
            return inner
        if type(inner) is float:
            if not math.isfinite(inner):
                raise ValueError(f"{surface} contains a non-finite number at {path}")
            return inner
        if isinstance(inner, Mapping):
            marker = id(inner)
            if marker in active_containers:
                raise ValueError(f"{surface} contains a recursive object at {path}")
            active_containers.add(marker)
            try:
                normalized: dict[str, Any] = {}
                for key, child in inner.items():
                    if type(key) is not str:
                        raise ValueError(
                            f"{surface} requires string object keys at {path}"
                        )
                    if key in normalized:
                        raise ValueError(
                            f"{surface} contains duplicate key {key!r} at {path}"
                        )
                    normalized[key] = normalize(child, f"{path}.{key}")
                return normalized
            finally:
                active_containers.remove(marker)
        if isinstance(inner, (list, tuple)):
            marker = id(inner)
            if marker in active_containers:
                raise ValueError(f"{surface} contains a recursive array at {path}")
            active_containers.add(marker)
            try:
                return [
                    normalize(child, f"{path}[{index}]")
                    for index, child in enumerate(inner)
                ]
            finally:
                active_containers.remove(marker)
        raise ValueError(
            f"{surface} contains a non-JSON value {type(inner).__name__} at {path}"
        )

    return normalize(value, "$")


def canonical_finite_json_dump(value: Any, *, surface: str) -> str:
    normalized = canonical_finite_json_value(value, surface=surface)
    return json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def canonical_finite_json_load(raw: str, *, surface: str) -> Any:
    def reject_constant(constant: str) -> None:
        raise ValueError(f"{surface} contains non-finite JSON constant {constant}")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise ValueError(f"{surface} contains duplicate JSON key {key!r}")
            value[key] = child
        return value

    try:
        value = json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{surface} is malformed JSON") from exc
    return canonical_finite_json_value(value, surface=surface)


def record_execution_identity_exact_sync(
    identity: ExecutionIdentity,
    *,
    source: str,
    init_db_sync: Callable[[], None],
    connect_sync: Callable[..., sqlite3.Connection],
    apply_connection_pragmas_sync: Callable[[sqlite3.Connection], None],
    row_to_execution_identity: Callable[[sqlite3.Row], ExecutionIdentity],
    now_iso: Callable[[], str],
    busy_timeout_seconds: float,
) -> ExecutionIdentity:
    """Insert or exactly replay one immutable execution-identity assertion."""

    if type(identity) is not ExecutionIdentity:
        raise MissingExecutionIdentity(
            "exact execution identity requires exact ExecutionIdentity"
        )
    if type(source) is not str or not source.strip():
        raise ValueError("source is required for exact execution identity")
    if source != source.strip():
        raise ValueError(
            "exact execution identity source must not contain surrounding whitespace"
        )
    if source.startswith(EXACT_EXECUTION_IDENTITY_SOURCE_PREFIX):
        raise ValueError("exact execution identity source must not use its marker")
    durable_source = EXACT_EXECUTION_IDENTITY_SOURCE_PREFIX + source
    identity.require_for_dispatch()
    field_names = ("run_id", *EXECUTION_IDENTITY_CONFLICT_FIELDS)
    fields = {name: getattr(identity, name) for name in field_names}
    for name, value in fields.items():
        if type(value) is not str:
            raise MissingExecutionIdentity(
                f"ExecutionIdentity field {name} must be a string"
            )
        if value != value.strip():
            raise MissingExecutionIdentity(
                f"ExecutionIdentity field {name} must not contain surrounding whitespace"
            )
    if type(identity.metadata) is not dict:
        raise MissingExecutionIdentity(
            "ExecutionIdentity metadata must be an exact JSON object"
        )
    normalized_metadata = canonical_finite_json_value(
        identity.metadata,
        surface="exact ExecutionIdentity metadata",
    )
    assert isinstance(normalized_metadata, dict)
    normalized_identity = {**fields, "metadata": normalized_metadata}
    identity_json = canonical_finite_json_dump(
        normalized_identity,
        surface="exact ExecutionIdentity",
    )
    metadata_json = canonical_finite_json_dump(
        normalized_metadata,
        surface="exact ExecutionIdentity metadata",
    )
    # Input validation deliberately completes before schema initialization.
    init_db_sync()
    columns = (
        "run_id, trace_id, correlation_id, task_id, claim_id,"
        " idempotency_key, causation_id, parent_run_id, agent_id,"
        " session_id, external_a2a_task_id, message_id, event_id,"
        " artifact_id, proposal_id, source, metadata_json"
    )
    with connect_sync(timeout=busy_timeout_seconds) as db:
        apply_connection_pragmas_sync(db)
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        try:

            def load_row() -> sqlite3.Row | None:
                return db.execute(
                    f"SELECT {columns} FROM execution_identities WHERE run_id = ?",
                    (fields["run_id"],),
                ).fetchone()

            def require_exact(row: sqlite3.Row) -> ExecutionIdentity:
                try:
                    durable_metadata = canonical_finite_json_load(
                        str(row["metadata_json"]),
                        surface="durable exact ExecutionIdentity metadata",
                    )
                except ValueError as exc:
                    raise ValueError(
                        "conflicting exact execution identity metadata"
                    ) from exc
                durable_identity = {
                    **{name: str(row[name] or "") for name in field_names},
                    "metadata": durable_metadata,
                }
                durable_json = canonical_finite_json_dump(
                    durable_identity,
                    surface="durable exact ExecutionIdentity",
                )
                if (
                    durable_json != identity_json
                    or str(row["source"]) != durable_source
                ):
                    raise ValueError("conflicting exact execution identity")
                return row_to_execution_identity(row)

            existing = load_row()
            if existing is not None:
                replay = require_exact(existing)
                db.commit()
                return replay

            now = now_iso()
            cursor = db.execute(
                "INSERT INTO execution_identities (run_id, trace_id, correlation_id,"
                " task_id, claim_id, idempotency_key, causation_id, parent_run_id,"
                " agent_id, session_id, external_a2a_task_id, message_id, event_id,"
                " artifact_id, proposal_id, source, metadata_json, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(run_id) DO NOTHING",
                (
                    *(fields[name] for name in field_names),
                    durable_source,
                    metadata_json,
                    now,
                    now,
                ),
            )
            if int(cursor.rowcount or 0) != 1:
                raise RuntimeError("exact execution identity insertion lost its slot")
            inserted = load_row()
            if inserted is None:
                raise RuntimeError("exact execution identity was not durably inserted")
            stored = require_exact(inserted)
            db.commit()
            return stored
        except BaseException:
            db.rollback()
            raise


__all__ = [
    "EXACT_EXECUTION_IDENTITY_SOURCE_PREFIX",
    "EXECUTION_IDENTITY_CONFLICT_FIELDS",
    "canonical_finite_json_dump",
    "canonical_finite_json_load",
    "canonical_finite_json_value",
    "record_execution_identity_exact_sync",
]
