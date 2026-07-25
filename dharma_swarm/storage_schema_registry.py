"""Storage schema registry — opt-in scaffold for unifying JSONL/JSON/SQLite stores.

Purpose
-------
The audit counted **526 JSONL files**, **56 SQLite files**, **159 raw JSON
files**, and **28** (post-PR-H2 budget) raw ``~/.dharma/...`` literals across
the repo. Each persistent record is written by a different module, with no
shared schema declaration, no version tag, no migration story.

This module introduces, purely additively, three things:

  1. ``SCHEMA_REGISTRY`` — a dict mapping a stable ``schema_id`` to a
     ``SchemaDescriptor`` (owner module, version, record dataclass, optional
     migration callable from version N-1 → N).
  2. ``register_schema(...)`` — a decorator dataclasses can adopt to register
     themselves at import time.
  3. ``read_jsonl_versioned`` / ``write_jsonl_versioned`` — helpers that wrap
     stdlib JSONL I/O, embed a ``__schema_id__`` and ``__schema_version__``
     marker into every record, and refuse to load records whose schema_id is
     unknown to the registry (configurable via ``strict=False`` for advisory
     mode).

Nothing in the repo is required to change to make this module work. Modules
that want versioned persistence opt in by decorating their dataclass and
calling the versioned helpers; modules that don't, keep their existing
``json.dump`` / ``aiosqlite.execute`` code untouched.

Why scaffold first
------------------
A real "unify storage" migration is multi-week work touching 600+ files and
the data on every operator's disk. The risky part isn't the package; it's
the cutover plan and the migrations. The registry contract gives every
future migration PR a stable target shape: opt one record type in, write
the migration callable from `v_{n-1}` to `v_n`, prove it round-trips,
move on.

Design constraints
------------------
- **Doctrine-safe:** zero new substrate. Zero meta-framework. One module,
  one dict, one decorator, two I/O helpers.
- **Frozen surfaces:** none touched. Pure stdlib (``json``, ``pathlib``,
  ``dataclasses``, ``typing``).
- **Backward compatibility:** records persisted by modules that have NOT
  adopted the registry remain readable by their own existing code paths.
- **Idempotent registration:** registering the same ``schema_id`` twice
  raises ``SchemaAlreadyRegisteredError`` rather than silently shadowing.
- **Migration is opt-in and explicit.** Auto-migration on read is OFF by
  default; modules may pass ``auto_migrate=True`` once they trust their
  migration callables.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

__all__ = [
    "SchemaRegistryError",
    "SchemaAlreadyRegisteredError",
    "SchemaVersionMismatchError",
    "UnknownSchemaError",
    "SchemaDescriptor",
    "SCHEMA_REGISTRY",
    "register_schema",
    "get_schema",
    "registered_schema_ids",
    "clear_registry_for_tests",
    "write_jsonl_versioned",
    "read_jsonl_versioned",
    "render_registry_summary",
]


# ─── Errors ──────────────────────────────────────────────────────────────────


class SchemaRegistryError(RuntimeError):
    """Base for schema-registry-specific errors."""


class SchemaAlreadyRegisteredError(SchemaRegistryError):
    """Raised when two schemas attempt to register the same schema_id."""


class SchemaVersionMismatchError(SchemaRegistryError):
    """Raised when a record's persisted version differs from the registered version
    and ``auto_migrate=False`` (the default)."""


class UnknownSchemaError(SchemaRegistryError):
    """Raised when a persisted record's schema_id is not in the registry and
    ``strict=True`` (the default for reads)."""


# ─── Descriptor ──────────────────────────────────────────────────────────────


# Migration signature: (record_dict_at_old_version) -> record_dict_at_new_version
Migration = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class SchemaDescriptor:
    """Descriptor for one registered persistent schema.

    Attributes
    ----------
    schema_id:
        Stable identifier. Convention: ``<owner_module>.<RecordName>``,
        e.g. ``"closure_v0.ClosureEvidenceReceipt"`` or ``"telemetry.RoutingDecisionRecord"``.
    version:
        Integer version. Bumped on any breaking field change.
    cls:
        The dataclass implementing the record.
    owner_module:
        Dotted module path that owns this schema.
    migrations:
        Dict mapping ``from_version -> Migration callable``. A migration
        registered at key ``N`` transforms a record at version ``N`` into a
        record at version ``N+1``. To migrate from version ``M`` to current
        version ``K``, the helpers compose ``migrations[M], migrations[M+1],
        ..., migrations[K-1]`` in order. Missing entries break the chain
        and raise ``SchemaVersionMismatchError``.
    notes:
        Free-form comment for the registry inspector — never load-bearing.
    """

    schema_id: str
    version: int
    cls: type
    owner_module: str
    migrations: dict[int, Migration] = field(default_factory=dict)
    notes: str = ""


# ─── Registry state ──────────────────────────────────────────────────────────


SCHEMA_REGISTRY: dict[str, SchemaDescriptor] = {}


_T = TypeVar("_T", bound=type)


def register_schema(
    schema_id: str,
    *,
    version: int,
    migrations: dict[int, Migration] | None = None,
    notes: str = "",
) -> Callable[[_T], _T]:
    """Class decorator that registers a dataclass into the schema registry.

    Usage::

        from dataclasses import dataclass
        from dharma_swarm.storage_schema_registry import register_schema

        @register_schema(
            "closure_v0.ClosureEvidenceReceipt",
            version=1,
        )
        @dataclass(frozen=True)
        class ClosureEvidenceReceipt:
            ...

    The decorator returns the class unchanged. Its only side effect is
    populating ``SCHEMA_REGISTRY``. Decorated classes remain importable
    and usable through every existing pathway.

    Raises
    ------
    SchemaAlreadyRegisteredError
        If ``schema_id`` is already in the registry.
    ValueError
        If ``schema_id`` is empty/whitespace, ``version < 1``, or the
        decorated class is not a dataclass.
    """
    if not schema_id or any(ch.isspace() for ch in schema_id):
        raise ValueError(
            f"schema_id must be a non-empty, whitespace-free string; "
            f"got {schema_id!r}"
        )
    if version < 1:
        raise ValueError(f"version must be >= 1; got {version}")

    def _decorator(cls: _T) -> _T:
        if not is_dataclass(cls):
            raise ValueError(
                f"@register_schema requires a dataclass; "
                f"{cls.__module__}.{cls.__qualname__} is not @dataclass-decorated"
            )
        if schema_id in SCHEMA_REGISTRY:
            existing = SCHEMA_REGISTRY[schema_id]
            raise SchemaAlreadyRegisteredError(
                f"schema_id {schema_id!r} already registered to "
                f"{existing.cls.__module__}.{existing.cls.__qualname__}"
            )
        SCHEMA_REGISTRY[schema_id] = SchemaDescriptor(
            schema_id=schema_id,
            version=version,
            cls=cls,
            owner_module=cls.__module__,
            migrations=dict(migrations or {}),
            notes=notes,
        )
        return cls

    return _decorator


def get_schema(schema_id: str) -> SchemaDescriptor:
    """Look up a registered schema by id. Raises KeyError if missing."""
    try:
        return SCHEMA_REGISTRY[schema_id]
    except KeyError as exc:
        raise KeyError(
            f"schema_id {schema_id!r} not in registry; "
            f"known: {sorted(SCHEMA_REGISTRY)}"
        ) from exc


def registered_schema_ids() -> list[str]:
    """Return the sorted list of currently registered schema ids."""
    return sorted(SCHEMA_REGISTRY)


def clear_registry_for_tests() -> None:
    """Clear the registry. Tests only. Production code must not call this."""
    SCHEMA_REGISTRY.clear()


# ─── Migration mechanics ─────────────────────────────────────────────────────


def _migrate_to_current(
    descriptor: SchemaDescriptor,
    record: dict[str, Any],
    persisted_version: int,
) -> dict[str, Any]:
    """Apply the chain of migrations from ``persisted_version`` to ``descriptor.version``."""
    current = persisted_version
    out = dict(record)
    while current < descriptor.version:
        if current not in descriptor.migrations:
            raise SchemaVersionMismatchError(
                f"no migration registered from version {current} to "
                f"{current + 1} for schema {descriptor.schema_id!r}; "
                f"persisted_version={persisted_version}, "
                f"target_version={descriptor.version}"
            )
        out = descriptor.migrations[current](out)
        current += 1
    return out


# ─── JSONL I/O helpers ───────────────────────────────────────────────────────


_SCHEMA_ID_KEY = "__schema_id__"
_SCHEMA_VERSION_KEY = "__schema_version__"


def _record_to_dict(record: Any) -> dict[str, Any]:
    if is_dataclass(record):
        return dataclasses.asdict(record)
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(
        f"versioned JSONL records must be dataclass instances or dicts; "
        f"got {type(record).__name__}"
    )


def write_jsonl_versioned(
    path: Path,
    records: Iterable[Any],
    *,
    schema_id: str,
    append: bool = False,
) -> int:
    """Write ``records`` as JSONL with embedded schema_id/version markers.

    Each line is a JSON object with the record's fields plus two reserved
    keys: ``__schema_id__`` and ``__schema_version__``. The schema must be
    registered; otherwise ``UnknownSchemaError`` is raised.

    Returns the number of records written.
    """
    if schema_id not in SCHEMA_REGISTRY:
        raise UnknownSchemaError(
            f"schema_id {schema_id!r} not registered; "
            f"known: {sorted(SCHEMA_REGISTRY)}"
        )
    descriptor = SCHEMA_REGISTRY[schema_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    count = 0
    with path.open(mode, encoding="utf-8") as fh:
        for record in records:
            data = _record_to_dict(record)
            if _SCHEMA_ID_KEY in data or _SCHEMA_VERSION_KEY in data:
                raise ValueError(
                    f"record contains reserved key {_SCHEMA_ID_KEY!r} or "
                    f"{_SCHEMA_VERSION_KEY!r}; pick a different field name"
                )
            data[_SCHEMA_ID_KEY] = schema_id
            data[_SCHEMA_VERSION_KEY] = descriptor.version
            fh.write(json.dumps(data, sort_keys=True))
            fh.write("\n")
            count += 1
    return count


def read_jsonl_versioned(
    path: Path,
    *,
    expected_schema_id: str | None = None,
    auto_migrate: bool = False,
    strict: bool = True,
) -> list[dict[str, Any]]:
    """Read a JSONL file written by ``write_jsonl_versioned``.

    Parameters
    ----------
    expected_schema_id:
        If given, every record must have this schema_id. Mismatches raise
        ``UnknownSchemaError`` regardless of ``strict``.
    auto_migrate:
        If True, records whose persisted version is less than the registered
        version are passed through the migration chain. If False (default),
        version mismatches raise ``SchemaVersionMismatchError``.
    strict:
        If True (default), records whose schema_id is not registered raise
        ``UnknownSchemaError``. If False, such records pass through with
        their reserved keys intact (advisory mode).

    Returns a list of dicts. Reserved keys (``__schema_id__``,
    ``__schema_version__``) are stripped from the returned records.
    """
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_no} is not valid JSON: {exc}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(
                    f"{path}:{line_no} is not a JSON object"
                )
            sid = record.get(_SCHEMA_ID_KEY)
            sver = record.get(_SCHEMA_VERSION_KEY)
            if sid is None or sver is None:
                raise ValueError(
                    f"{path}:{line_no} missing {_SCHEMA_ID_KEY} or "
                    f"{_SCHEMA_VERSION_KEY} markers; not a versioned record"
                )
            if expected_schema_id is not None and sid != expected_schema_id:
                raise UnknownSchemaError(
                    f"{path}:{line_no} schema_id {sid!r} != "
                    f"expected {expected_schema_id!r}"
                )
            if sid not in SCHEMA_REGISTRY:
                if strict:
                    raise UnknownSchemaError(
                        f"{path}:{line_no} schema_id {sid!r} not in registry"
                    )
            else:
                descriptor = SCHEMA_REGISTRY[sid]
                if sver != descriptor.version:
                    if auto_migrate:
                        record = _migrate_to_current(descriptor, record, sver)
                    else:
                        raise SchemaVersionMismatchError(
                            f"{path}:{line_no} schema {sid!r} persisted "
                            f"version={sver} != registered version="
                            f"{descriptor.version}; pass auto_migrate=True "
                            f"to apply the migration chain"
                        )
            record.pop(_SCHEMA_ID_KEY, None)
            record.pop(_SCHEMA_VERSION_KEY, None)
            out.append(record)
    return out


# ─── Inspector ───────────────────────────────────────────────────────────────


def render_registry_summary() -> str:
    """Return a human-readable single-string summary of the registry."""
    if not SCHEMA_REGISTRY:
        return "(empty schema registry — no records have opted in yet)"
    lines = []
    for sid in registered_schema_ids():
        d = SCHEMA_REGISTRY[sid]
        migs = ",".join(str(k) for k in sorted(d.migrations)) or "—"
        lines.append(
            f"  {sid:<48s}  v{d.version}  "
            f"{d.cls.__module__}.{d.cls.__qualname__}  "
            f"migrations_from={migs}"
        )
    return "\n".join(lines)
