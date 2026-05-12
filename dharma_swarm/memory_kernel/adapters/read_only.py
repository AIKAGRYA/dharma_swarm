"""Read-only MemoryKernel M1 adapters.

These adapters normalize selected existing memory surfaces into MemoryAtom
records.  They do not write, migrate, promote, dedupe, rebuild indexes, or
claim canonical truth.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from dharma_swarm.memory_kernel.adapters.base import SurfaceProbe
from dharma_swarm.memory_kernel.atoms import (
    MemoryAtom,
    MemoryAtomType,
    MemoryOrder,
    MemoryQuery,
    MemorySurface,
    MemorySurfaceHealth,
    ReadMode,
)


DEFAULT_LIMIT = 100
MAX_CONTENT_CHARS = 2000
MAX_METADATA_CHARS = 2000
TIMESTAMP_KEYS = ("timestamp", "created_at", "updated_at", "ts", "time", "observed_at")
ID_KEYS = ("id", "rowid", "event_id", "turn_id", "shard_id", "fact_id", "memory_id")
CONTENT_LIKE_KEYS = {
    "body",
    "chunk_text",
    "content",
    "fact",
    "message",
    "payload",
    "query",
    "raw",
    "summary",
    "text",
    "value",
}
SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "access_key",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
STRUCTURAL_METADATA_KEYS = {
    "columns",
    "content_status",
    "line",
    "metadata_only",
    "ordering_warning",
    "path",
    "probe_error",
    "read_error",
    "reason",
    "size_bytes",
    "snapshot_warnings",
    "table",
}


@dataclass(frozen=True)
class ReadOnlyAdapterConfig:
    default_limit: int = DEFAULT_LIMIT
    max_content_chars: int = MAX_CONTENT_CHARS
    max_metadata_chars: int = MAX_METADATA_CHARS
    max_files: int = 100
    max_lines_per_file: int = 100
    max_cursor_scan_atoms: int = 1000


class BaseReadOnlyAdapter:
    adapter_name = "base_read_only"
    read_mode = ReadMode.READ_ONLY

    def __init__(
        self,
        surface: MemorySurface,
        *,
        config: ReadOnlyAdapterConfig | None = None,
    ) -> None:
        self.surface = surface
        self.surface_id = surface.surface_id
        self.path = Path(surface.path).expanduser()
        self.config = config or ReadOnlyAdapterConfig()

    def probe(self) -> SurfaceProbe:
        return SurfaceProbe(path=self.path, health=_probe_path_metadata(self.path))

    def _query(self, query: MemoryQuery | None, limit: int | None) -> MemoryQuery:
        if query is None:
            return MemoryQuery(limit_per_surface=self._bounded_limit(limit))
        if limit is None:
            return query
        return replace(query, limit_per_surface=self._bounded_limit(limit))

    def _surface_limit(self, query: MemoryQuery) -> int:
        limit = query.per_surface_limit(self.config.default_limit)
        if limit is None:
            return self.config.default_limit
        return min(limit, self.config.default_limit)

    def _scan_limit(self, query: MemoryQuery, surface_limit: int) -> int:
        if not query.cursor:
            return surface_limit
        return max(surface_limit, min(self.config.max_cursor_scan_atoms, max(surface_limit * 10, surface_limit + 1)))

    def _bounded_limit(self, limit: int | None) -> int:
        if limit is None:
            return self.config.default_limit
        return max(0, min(limit, self.config.default_limit))

    def _atom(
        self,
        atom_type: MemoryAtomType,
        *,
        query: MemoryQuery,
        content_ref: str,
        content: str | None = None,
        timestamp: str | None = None,
        source_path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryAtom:
        safe_metadata = _safe_metadata(
            metadata or {},
            include_payloads=query.include_metadata_payloads,
            max_chars=self.config.max_metadata_chars,
        )
        snapshot_warnings = _snapshot_warnings(self.surface)
        if snapshot_warnings:
            safe_metadata["snapshot_warnings"] = snapshot_warnings
        if content is not None and not query.include_content:
            safe_metadata["content_status"] = "omitted_by_query"
        bounded_content = _truncate(content, self.config.max_content_chars) if query.include_content else None
        return MemoryAtom.build(
            surface=self.surface,
            atom_type=atom_type,
            content_ref=content_ref,
            content=bounded_content,
            timestamp=timestamp,
            source_path=source_path,
            adapter_name=self.adapter_name,
            read_mode=self.read_mode,
            metadata=safe_metadata,
        )


class SQLiteReadOnlyAdapter(BaseReadOnlyAdapter):
    adapter_name = "sqlite_read_only"
    read_mode = ReadMode.IMMUTABLE_SNAPSHOT
    table_atom_types: dict[str, MemoryAtomType] = {}

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        if not self.path.exists():
            return
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if surface_limit <= 0:
            return
        scan_limit = self._scan_limit(resolved_query, surface_limit)
        try:
            atoms: list[MemoryAtom] = []
            with _connect_sqlite_immutable(self.path) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                tables = _sqlite_tables(conn)
                for table_index, (table, atom_type) in enumerate(self.table_atom_types.items()):
                    if not resolved_query.allows_atom_type(atom_type):
                        continue
                    if table not in tables:
                        continue
                    columns = _sqlite_table_columns(conn, table)
                    order_clause, ordering_warning = _sqlite_order_clause(columns, resolved_query.order_by)
                    where_clause, params = _sqlite_since_clause(columns, resolved_query)
                    sql = (
                        f"SELECT * FROM {_quote_identifier(table)}"
                        f"{where_clause}{order_clause} LIMIT ?"
                    )
                    rows = conn.execute(sql, (*params, scan_limit)).fetchall()
                    for row_index, row in enumerate(rows):
                        row_data = dict(row)
                        timestamp = _row_timestamp(row_data)
                        if not _passes_since(timestamp, resolved_query.since):
                            continue
                        content_ref = _row_ref(table, row_data, row_index)
                        metadata: dict[str, Any] = {
                            "table": table,
                            "columns": tuple(row_data.keys()),
                            "row": row_data,
                            "table_index": table_index,
                        }
                        if ordering_warning:
                            metadata["ordering_warning"] = ordering_warning
                        atoms.append(
                            self._atom(
                                atom_type,
                                query=resolved_query,
                                content_ref=content_ref,
                                content=_row_content(row_data),
                                timestamp=timestamp,
                                metadata=metadata,
                            )
                        )
            for atom in _after_cursor(_ordered_atoms(atoms, resolved_query.order_by), resolved_query.cursor)[
                :surface_limit
            ]:
                yield atom
        except sqlite3.Error as exc:
            if not resolved_query.allows_atom_type(MemoryAtomType.METADATA):
                return
            yield self._atom(
                MemoryAtomType.METADATA,
                query=resolved_query,
                content_ref=f"{self.surface_id}:sqlite_probe_error",
                content=None,
                metadata={"probe_error": str(exc), "path": self.path.as_posix()},
            )


class MemoryPlaneAdapter(SQLiteReadOnlyAdapter):
    adapter_name = "memory_plane_adapter"
    table_atom_types = {
        "event_log": MemoryAtomType.RUNTIME_EVENT,
        "conversation_turns": MemoryAtomType.EPISODE,
        "idea_shards": MemoryAtomType.FACT,
        "source_chunks": MemoryAtomType.SOURCE_CHUNK,
        "retrieval_log": MemoryAtomType.RETRIEVAL_FEEDBACK,
    }


class RuntimeStateAdapter(SQLiteReadOnlyAdapter):
    adapter_name = "runtime_state_adapter"
    table_atom_types = {
        "session_events": MemoryAtomType.RUNTIME_EVENT,
        "routing_decisions": MemoryAtomType.RUNTIME_EVENT,
        "context_bundles": MemoryAtomType.CONTEXT_BUNDLE,
        "memory_facts": MemoryAtomType.FACT,
        "memory_edges": MemoryAtomType.EDGE,
    }


class SmritiAdapter(SQLiteReadOnlyAdapter):
    adapter_name = "smriti_adapter"
    table_atom_types = {
        "memories": MemoryAtomType.EXTERNAL_MEMORY,
    }


class JsonlReadOnlyAdapter(BaseReadOnlyAdapter):
    adapter_name = "jsonl_read_only"
    read_mode = ReadMode.STREAMING
    atom_type = MemoryAtomType.EXTERNAL_MEMORY

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if surface_limit <= 0 or not self.path.exists():
            return
        if not resolved_query.allows_atom_type(self.atom_type):
            return
        scan_limit = self._scan_limit(resolved_query, surface_limit)
        atoms: list[MemoryAtom] = []
        for file_path in _jsonl_files(self.path, self.config.max_files):
            for line_number, payload in _iter_jsonl(file_path, self.config.max_lines_per_file):
                timestamp = _payload_timestamp(payload)
                if not _passes_since(timestamp, resolved_query.since):
                    continue
                atoms.append(
                    self._atom(
                        self.atom_type,
                        query=resolved_query,
                        content_ref=f"{file_path.as_posix()}:{line_number}",
                        content=_payload_content(payload),
                        timestamp=timestamp,
                        source_path=file_path.as_posix(),
                        metadata={"line": line_number, "payload": payload},
                    )
                )
                if resolved_query.order_by == MemoryOrder.STABLE_ID and len(atoms) >= scan_limit:
                    break
            if resolved_query.order_by == MemoryOrder.STABLE_ID and len(atoms) >= scan_limit:
                break
        for atom in _after_cursor(_ordered_atoms(atoms, resolved_query.order_by), resolved_query.cursor)[
            :surface_limit
        ]:
            yield atom


class WitnessJsonlAdapter(JsonlReadOnlyAdapter):
    adapter_name = "witness_jsonl_adapter"
    atom_type = MemoryAtomType.WITNESS_EVENT


class CodexMemoryAdapter(JsonlReadOnlyAdapter):
    adapter_name = "codex_memory_adapter"
    atom_type = MemoryAtomType.EXTERNAL_MEMORY


class KnowledgeWikiAdapter(BaseReadOnlyAdapter):
    adapter_name = "knowledge_wiki_adapter"
    read_mode = ReadMode.READ_ONLY

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if surface_limit <= 0 or not self.path.exists():
            return
        if not (
            resolved_query.allows_atom_type(MemoryAtomType.KNOWLEDGE_CARD)
            or resolved_query.allows_atom_type(MemoryAtomType.METADATA)
        ):
            return
        atoms: list[MemoryAtom] = []
        files = _ordered_paths(_markdown_files(self.path, self.config.max_files), resolved_query.order_by)
        for file_path in files:
            stat = file_path.stat()
            content: str | None = None
            if resolved_query.include_content:
                try:
                    content = _read_text_bounded(file_path, self.config.max_content_chars + 1)
                except OSError as exc:
                    if resolved_query.allows_atom_type(MemoryAtomType.METADATA):
                        atoms.append(
                            self._atom(
                                MemoryAtomType.METADATA,
                                query=resolved_query,
                                content_ref=file_path.as_posix(),
                                metadata={"read_error": str(exc)},
                            )
                        )
                    continue
            if not resolved_query.allows_atom_type(MemoryAtomType.KNOWLEDGE_CARD):
                continue
            atoms.append(
                self._atom(
                    MemoryAtomType.KNOWLEDGE_CARD,
                    query=resolved_query,
                    content_ref=file_path.as_posix(),
                    content=content,
                    timestamp=_format_mtime(stat.st_mtime),
                    source_path=file_path.as_posix(),
                    metadata={"size_bytes": stat.st_size},
                )
            )
        for atom in _after_cursor(_ordered_atoms(atoms, resolved_query.order_by), resolved_query.cursor)[
            :surface_limit
        ]:
            yield atom


class ConversationLogMetadataAdapter(BaseReadOnlyAdapter):
    adapter_name = "conversation_log_metadata_adapter"
    read_mode = ReadMode.METADATA_ONLY

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if surface_limit <= 0 or not self.path.exists():
            return
        if not resolved_query.allows_atom_type(MemoryAtomType.METADATA):
            return
        atoms: list[MemoryAtom] = []
        files = _ordered_paths(_jsonl_files(self.path, self.config.max_files), resolved_query.order_by)
        for file_path in files:
            stat = file_path.stat()
            atoms.append(
                self._atom(
                    MemoryAtomType.METADATA,
                    query=resolved_query,
                    content_ref=file_path.as_posix(),
                    content=None,
                    timestamp=_format_mtime(stat.st_mtime),
                    source_path=file_path.as_posix(),
                    metadata={
                        "size_bytes": stat.st_size,
                        "metadata_only": True,
                        "reason": "conversation logs are streamed later; M1 exposes file pointers only",
                    },
                )
            )
        for atom in _after_cursor(_ordered_atoms(atoms, resolved_query.order_by), resolved_query.cursor)[
            :surface_limit
        ]:
            yield atom


def _probe_path_metadata(path: Path) -> MemorySurfaceHealth:
    if not path.exists():
        return MemorySurfaceHealth(exists=False)
    try:
        stat = path.stat()
        path_type = "directory" if path.is_dir() else "file" if path.is_file() else "other"
        return MemorySurfaceHealth(
            exists=True,
            path_type=path_type,
            size_bytes=stat.st_size,
            last_modified=_format_mtime(stat.st_mtime),
        )
    except OSError as exc:
        return MemorySurfaceHealth(exists=True, probe_error=str(exc))


def _connect_sqlite_immutable(path: Path) -> sqlite3.Connection:
    uri_path = quote(path.resolve().as_posix(), safe="/:")
    return sqlite3.connect(f"file:{uri_path}?mode=ro&immutable=1", uri=True, timeout=1.0)


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _sqlite_table_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
    return tuple(str(row[1]) for row in rows)


def _sqlite_order_clause(columns: tuple[str, ...], order_by: MemoryOrder) -> tuple[str, str | None]:
    if order_by in {MemoryOrder.NEWEST, MemoryOrder.OLDEST}:
        timestamp_key = _first_present(columns, TIMESTAMP_KEYS)
        if timestamp_key:
            direction = "DESC" if order_by == MemoryOrder.NEWEST else "ASC"
            return f" ORDER BY {_quote_identifier(timestamp_key)} {direction}", None
        id_key = _first_present(columns, ID_KEYS)
        if id_key:
            return f" ORDER BY {_quote_identifier(id_key)} ASC", "timestamp_unavailable_stable_fallback"
        return "", "timestamp_unavailable_unordered"
    id_key = _first_present(columns, ID_KEYS)
    if id_key:
        return f" ORDER BY {_quote_identifier(id_key)} ASC", None
    return " ORDER BY rowid ASC", None


def _sqlite_since_clause(columns: tuple[str, ...], query: MemoryQuery) -> tuple[str, tuple[str, ...]]:
    if not query.since:
        return "", ()
    timestamp_key = _first_present(columns, TIMESTAMP_KEYS)
    if not timestamp_key:
        return "", ()
    return f" WHERE {_quote_identifier(timestamp_key)} >= ?", (query.since,)


def _first_present(columns: tuple[str, ...], keys: tuple[str, ...]) -> str | None:
    column_set = set(columns)
    for key in keys:
        if key in column_set:
            return key
    return None


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _row_ref(table: str, row_data: dict[str, Any], index: int) -> str:
    for key in ID_KEYS:
        value = row_data.get(key)
        if value is not None:
            return f"{table}:{value}"
    return f"{table}:row:{index}"


def _row_content(row_data: dict[str, Any]) -> str:
    for key in (
        "content",
        "text",
        "payload",
        "summary",
        "message",
        "body",
        "value",
        "fact",
        "chunk_text",
    ):
        value = row_data.get(key)
        if value not in (None, ""):
            return str(value)
    return json.dumps(_redacted_value("row", row_data)[0], sort_keys=True, default=str)


def _row_timestamp(row_data: dict[str, Any]) -> str | None:
    for key in TIMESTAMP_KEYS:
        value = row_data.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _jsonl_files(path: Path, max_files: int) -> tuple[Path, ...]:
    if path.is_file() and path.suffix == ".jsonl":
        return (path,)
    if not path.is_dir():
        return ()
    files: list[Path] = []
    for current, dirs, filenames in os.walk(path):
        dirs[:] = sorted(name for name in dirs if name not in {".git", "__pycache__"})
        for filename in sorted(filenames):
            if filename.endswith(".jsonl"):
                files.append(Path(current) / filename)
                if len(files) >= max_files:
                    return tuple(files)
    return tuple(files)


def _markdown_files(path: Path, max_files: int) -> tuple[Path, ...]:
    if path.is_file() and path.suffix.lower() in {".md", ".markdown"}:
        return (path,)
    if not path.is_dir():
        return ()
    files: list[Path] = []
    for current, dirs, filenames in os.walk(path):
        dirs[:] = sorted(name for name in dirs if name not in {".git", "__pycache__"})
        for filename in sorted(filenames):
            if Path(filename).suffix.lower() in {".md", ".markdown"}:
                files.append(Path(current) / filename)
                if len(files) >= max_files:
                    return tuple(files)
    return tuple(files)


def _iter_jsonl(path: Path, max_lines: int) -> Iterable[tuple[int, dict[str, Any]]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line_number > max_lines:
                    break
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    payload = {"raw": stripped, "parse_error": True}
                if not isinstance(payload, dict):
                    payload = {"value": payload}
                yield line_number, payload
    except OSError as exc:
        yield 0, {"read_error": str(exc)}


def _payload_content(payload: dict[str, Any]) -> str:
    for key in ("content", "text", "message", "summary", "body", "value", "raw"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return json.dumps(_redacted_value("payload", payload)[0], sort_keys=True, default=str)


def _payload_timestamp(payload: dict[str, Any]) -> str | None:
    for key in TIMESTAMP_KEYS:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _safe_metadata(
    metadata: dict[str, Any],
    *,
    include_payloads: bool,
    max_chars: int,
) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    redacted_keys: list[str] = []
    for key, value in metadata.items():
        if key in {"row", "payload"} and not include_payloads:
            redacted_keys.append(key)
            continue
        safe_value, child_redactions = _redacted_value(key, value)
        safe[key] = safe_value
        redacted_keys.extend(child_redactions)

    redacted_keys = sorted(set(redacted_keys))
    safe["redaction_status"] = "redacted" if redacted_keys else "clean"
    safe["redacted_keys"] = tuple(redacted_keys)
    safe["metadata_truncated"] = False

    serialized = json.dumps(safe, sort_keys=True, default=str)
    if len(serialized) <= max_chars:
        return safe

    compact = {
        key: value
        for key, value in safe.items()
        if key in STRUCTURAL_METADATA_KEYS or key.startswith("redaction_")
    }
    compact["metadata_truncated"] = True
    compact["redaction_status"] = safe["redaction_status"]
    compact["redacted_keys"] = safe["redacted_keys"]
    return compact


def _redacted_value(key: str, value: Any) -> tuple[Any, list[str]]:
    if _is_sensitive_key(key):
        return "<redacted>", [key]
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>", []
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        redacted: list[str] = []
        for child_key, child_value in value.items():
            child_safe, child_redactions = _redacted_value(str(child_key), child_value)
            safe[str(child_key)] = child_safe
            redacted.extend(child_redactions)
        return safe, redacted
    if isinstance(value, (list, tuple)):
        items: list[Any] = []
        redacted = []
        for index, item in enumerate(value):
            child_safe, child_redactions = _redacted_value(f"{key}.{index}", item)
            items.append(child_safe)
            redacted.extend(child_redactions)
        return tuple(items), redacted
    return value, []


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in CONTENT_LIKE_KEYS or any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS)


def _ordered_atoms(atoms: list[MemoryAtom], order_by: MemoryOrder) -> list[MemoryAtom]:
    if order_by == MemoryOrder.NEWEST:
        return sorted(atoms, key=lambda atom: (_timestamp_missing(atom), -_timestamp_epoch(atom), atom.atom_id))
    if order_by == MemoryOrder.OLDEST:
        return sorted(atoms, key=lambda atom: (_timestamp_missing(atom), _timestamp_epoch(atom), atom.atom_id))
    return sorted(atoms, key=lambda atom: atom.atom_id)


def _ordered_paths(paths: tuple[Path, ...], order_by: MemoryOrder) -> list[Path]:
    if order_by == MemoryOrder.NEWEST:
        return sorted(paths, key=lambda path: (-_path_mtime(path), path.as_posix()))
    if order_by == MemoryOrder.OLDEST:
        return sorted(paths, key=lambda path: (_path_mtime(path), path.as_posix()))
    return sorted(paths, key=lambda path: path.as_posix())


def _after_cursor(atoms: list[MemoryAtom], cursor: str | None) -> list[MemoryAtom]:
    if not cursor:
        return atoms
    for index, atom in enumerate(atoms):
        if atom.atom_id == cursor:
            return atoms[index + 1 :]
    return atoms


def _passes_since(timestamp: str | None, since: str | None) -> bool:
    if not since:
        return True
    if not timestamp:
        return False
    timestamp_dt = _parse_datetime(timestamp)
    since_dt = _parse_datetime(since)
    if timestamp_dt and since_dt:
        return timestamp_dt >= since_dt
    return timestamp >= since


def _timestamp_missing(atom: MemoryAtom) -> int:
    return 1 if _parse_datetime(atom.timestamp) is None else 0


def _timestamp_epoch(atom: MemoryAtom) -> float:
    parsed = _parse_datetime(atom.timestamp)
    if parsed is None:
        return 0.0
    return parsed.timestamp()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _snapshot_warnings(surface: MemorySurface) -> tuple[str, ...]:
    notes = tuple(
        note
        for note in surface.health.notes
        if "wal" in note.lower() or "immutable" in note.lower() or "snapshot" in note.lower()
    )
    path = Path(surface.path).expanduser()
    wal_path = path.with_name(path.name + "-wal")
    if wal_path.exists() and "immutable_probe_may_ignore_live_wal" not in notes:
        notes = (*notes, "immutable_probe_may_ignore_live_wal")
    return notes


def _truncate(value: str | None, max_chars: int) -> str | None:
    if value is None:
        return None
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "...[truncated]"


def _read_text_bounded(path: Path, max_chars: int) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(max_chars)


def _format_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
