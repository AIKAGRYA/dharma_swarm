"""Deterministic readiness reports for read-only MemoryKernel adapters."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.memory_kernel.adapters.base import MemorySurfaceAdapter
from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    MemoryAtomType,
    MemorySurface,
    ReadMode,
    SurfaceStatus,
)


READINESS_SCHEMA_VERSION = "memory_kernel_readiness.v1"
AdapterFactory = Callable[[MemorySurface], MemorySurfaceAdapter]


@dataclass(frozen=True)
class AdapterSurfaceReadiness:
    surface_id: str
    status: str
    required: bool
    adapter_registered: bool
    adapter_name: str | None
    adapter_version: str | None
    read_mode: str | None
    surface_exists: bool
    active_status: str
    adapter_mode: str
    path_type: str
    atom_types: tuple[str, ...]
    warnings: tuple[str, ...]
    record_count: int | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterReadinessReport:
    schema_version: str
    status: str
    summary: dict[str, int]
    surfaces: tuple[AdapterSurfaceReadiness, ...]
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "summary": dict(self.summary),
            "warnings": self.warnings,
            "surfaces": tuple(surface.to_json() for surface in self.surfaces),
        }


def build_adapter_readiness_report(
    *,
    surfaces: Iterable[MemorySurface],
    adapter_factories: dict[str, AdapterFactory],
    required_surface_ids: Iterable[str] | None = None,
) -> AdapterReadinessReport:
    required = set(required_surface_ids or adapter_factories)
    rows = tuple(
        _surface_readiness(surface, adapter_factories, required)
        for surface in sorted(surfaces, key=lambda item: item.surface_id)
    )
    counts = Counter(row.status for row in rows)
    summary = {
        "surface_count": len(rows),
        "required_surface_count": sum(1 for row in rows if row.required),
        "adapter_registered_count": sum(1 for row in rows if row.adapter_registered),
        "ready_count": counts["ready"],
        "degraded_count": counts["degraded"],
        "unavailable_count": counts["unavailable"],
        "missing_adapter_count": counts["missing_adapter"],
        "uncovered_count": counts["uncovered"],
        "warning_count": sum(len(row.warnings) for row in rows),
    }
    report_warnings = _report_warnings(rows)
    return AdapterReadinessReport(
        schema_version=READINESS_SCHEMA_VERSION,
        status=_report_status(rows),
        summary=summary,
        surfaces=rows,
        warnings=report_warnings,
    )


def _surface_readiness(
    surface: MemorySurface,
    adapter_factories: dict[str, AdapterFactory],
    required: set[str],
) -> AdapterSurfaceReadiness:
    factory = adapter_factories.get(surface.surface_id)
    adapter: MemorySurfaceAdapter | None = None
    warnings: list[str] = []
    adapter_name: str | None = None
    adapter_version: str | None = None
    read_mode: str | None = None
    atom_types: tuple[str, ...] = ()

    if factory is None:
        if _expects_adapter(surface):
            warnings.append("adapter_not_registered")
    else:
        try:
            adapter = factory(surface)
        except Exception as exc:  # pragma: no cover - defensive report surface
            warnings.append(f"adapter_factory_error:{type(exc).__name__}")
        if adapter is not None:
            adapter_name = getattr(adapter, "adapter_name", adapter.__class__.__name__)
            adapter_version = getattr(adapter, "adapter_version", None)
            read_mode_value = getattr(adapter, "read_mode", None)
            read_mode = (
                read_mode_value.value
                if isinstance(read_mode_value, ReadMode)
                else str(read_mode_value)
            )
            atom_types = _adapter_atom_types(adapter)

    if not surface.health.exists:
        warnings.append("surface_missing")
    if surface.health.probe_error:
        warnings.append("surface_probe_error")
    warnings.extend(_surface_read_warnings(surface))

    normalized_warnings = tuple(sorted(dict.fromkeys(warnings)))
    return AdapterSurfaceReadiness(
        surface_id=surface.surface_id,
        status=_surface_status(surface, factory, normalized_warnings),
        required=surface.surface_id in required,
        adapter_registered=factory is not None,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        read_mode=read_mode,
        surface_exists=surface.health.exists,
        active_status=surface.active_status.value,
        adapter_mode=surface.adapter_mode.value,
        path_type=surface.health.path_type,
        atom_types=atom_types,
        warnings=normalized_warnings,
        record_count=surface.health.record_count,
    )


def _surface_status(
    surface: MemorySurface,
    factory: AdapterFactory | None,
    warnings: tuple[str, ...],
) -> str:
    if factory is None:
        return "missing_adapter" if _expects_adapter(surface) else "uncovered"
    if not surface.health.exists or surface.active_status == SurfaceStatus.MISSING:
        return "unavailable"
    if warnings:
        return "degraded"
    return "ready"


def _expects_adapter(surface: MemorySurface) -> bool:
    return surface.adapter_mode in {
        AdapterMode.READ_ONLY,
        AdapterMode.STREAMING,
        AdapterMode.METADATA_ONLY,
    }


def _adapter_atom_types(adapter: MemorySurfaceAdapter) -> tuple[str, ...]:
    values: set[MemoryAtomType] = set()
    table_atom_types = getattr(adapter, "table_atom_types", {})
    if isinstance(table_atom_types, dict):
        values.update(
            value
            for value in table_atom_types.values()
            if isinstance(value, MemoryAtomType)
        )
    atom_type = getattr(adapter, "atom_type", None)
    if isinstance(atom_type, MemoryAtomType):
        values.add(atom_type)
    adapter_name = getattr(adapter, "adapter_name", "")
    if adapter_name == "knowledge_wiki_adapter":
        values.update({MemoryAtomType.KNOWLEDGE_CARD, MemoryAtomType.METADATA})
    if adapter_name == "conversation_log_metadata_adapter":
        values.add(MemoryAtomType.METADATA)
    read_mode = getattr(adapter, "read_mode", None)
    if read_mode == ReadMode.METADATA_ONLY:
        values.add(MemoryAtomType.METADATA)
    return tuple(sorted(value.value for value in values))


def _surface_read_warnings(surface: MemorySurface) -> tuple[str, ...]:
    path = Path(surface.path).expanduser()
    warnings: list[str] = []
    if _looks_like_sqlite(path):
        wal_path = path.with_name(path.name + "-wal")
        if wal_path.exists():
            warnings.append("immutable_probe_may_ignore_live_wal")
    if _looks_like_jsonl_surface(path, surface):
        warnings.extend(_jsonl_append_warnings(path))
    return tuple(sorted(dict.fromkeys(warnings)))


def _jsonl_append_warnings(path: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    for file_path in _jsonl_files(path, max_files=100):
        try:
            if file_path.stat().st_size == 0:
                continue
            with file_path.open("rb") as handle:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    warnings.append("jsonl_trailing_partial_line_skipped")
                    break
        except OSError:
            warnings.append("jsonl_read_error")
    return tuple(sorted(dict.fromkeys(warnings)))


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


def _looks_like_sqlite(path: Path) -> bool:
    return path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}


def _looks_like_jsonl_surface(path: Path, surface: MemorySurface) -> bool:
    return path.suffix == ".jsonl" or surface.adapter_mode == AdapterMode.STREAMING


def _report_status(rows: tuple[AdapterSurfaceReadiness, ...]) -> str:
    required_rows = [row for row in rows if row.required]
    if any(row.status in {"unavailable", "missing_adapter"} for row in required_rows):
        return "unavailable"
    if any(row.status == "degraded" for row in required_rows):
        return "degraded"
    return "ready"


def _report_warnings(rows: tuple[AdapterSurfaceReadiness, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    for row in rows:
        if not row.required:
            continue
        for warning in row.warnings:
            warnings.append(f"{row.surface_id}:{warning}")
    return tuple(sorted(dict.fromkeys(warnings)))
