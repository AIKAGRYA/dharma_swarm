"""Deterministic readiness reports for read-only MemoryKernel adapters."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.memory_kernel.adapters.base import MemorySurfaceAdapter
from dharma_swarm.memory_kernel.adapters.read_only import (
    jsonl_surface_read_warnings,
    sqlite_surface_read_warnings,
)
from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    MemoryAtomType,
    MemorySurface,
    ReadMode,
    SurfaceStatus,
)


READINESS_SCHEMA_VERSION = "memory_kernel_readiness.v1"
AdapterFactory = Callable[[MemorySurface], MemorySurfaceAdapter]
DEFAULT_REQUIRED_SURFACE_IDS = (
    "home.memory_plane",
    "home.runtime_state",
    "home.smriti",
    "home.witness",
    "home.knowledge_wiki",
    "home.codex_memory",
    "home.conversation_log",
)
OPTIONAL_LIFECYCLE_STATUSES = {
    "disabled",
    "dormant",
    "expected_unavailable",
    "external",
    "retired",
    "snapshot",
    "unsafe_disabled",
}
REQUIRED_FAILURE_STATUSES = {
    "degraded",
    "missing_adapter",
    "unavailable",
    "uncovered",
    *OPTIONAL_LIFECYCLE_STATUSES,
}
REQUIRED_UNAVAILABLE_STATUSES = REQUIRED_FAILURE_STATUSES - {"degraded"}


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
    required = set(required_surface_ids or DEFAULT_REQUIRED_SURFACE_IDS)
    surface_rows = tuple(
        _surface_readiness(surface, adapter_factories, required)
        for surface in sorted(surfaces, key=lambda item: item.surface_id)
    )
    observed_surface_ids = {row.surface_id for row in surface_rows}
    missing_required_rows = tuple(
        _missing_required_surface_readiness(surface_id)
        for surface_id in sorted(required - observed_surface_ids)
    )
    rows = tuple(
        sorted(
            (*surface_rows, *missing_required_rows),
            key=lambda row: row.surface_id,
        )
    )
    counts = Counter(row.status for row in rows)
    required_rows = tuple(row for row in rows if row.required)
    optional_rows = tuple(row for row in rows if not row.required)
    required_counts = Counter(row.status for row in required_rows)
    optional_counts = Counter(row.status for row in optional_rows)
    required_adapter_registered_count = sum(
        1 for row in required_rows if row.adapter_registered
    )
    summary = {
        "surface_count": len(rows),
        "observed_surface_count": len(surface_rows),
        "missing_required_surface_count": len(missing_required_rows),
        "required_surface_count": len(required_rows),
        "required_ready_count": required_counts["ready"],
        "required_failure_count": len(required_rows) - required_counts["ready"],
        "expected_adapter_surface_count": len(required_rows),
        "expected_adapter_registered_count": required_adapter_registered_count,
        "required_adapter_registered_count": required_adapter_registered_count,
        "optional_surface_count": len(optional_rows),
        "accounted_surface_count": sum(1 for row in rows if row.status != "uncovered"),
        "accounted_optional_count": sum(
            1 for row in optional_rows if row.status != "uncovered"
        ),
        "accounted_optional_absent_count": sum(
            1
            for row in optional_rows
            if row.status in OPTIONAL_LIFECYCLE_STATUSES and not row.surface_exists
        ),
        "accounted_optional_lifecycle_count": sum(
            1 for row in optional_rows if row.status in OPTIONAL_LIFECYCLE_STATUSES
        ),
        "adapter_registered_count": sum(1 for row in rows if row.adapter_registered),
        "ready_count": required_counts["ready"],
        "degraded_count": required_counts["degraded"],
        "unavailable_count": required_counts["unavailable"],
        "missing_adapter_count": required_counts["missing_adapter"],
        "uncovered_count": required_counts["uncovered"],
        "optional_missing_adapter_count": optional_counts["missing_adapter"],
        "optional_uncovered_count": optional_counts["uncovered"],
        "expected_unavailable_count": counts["expected_unavailable"],
        "retired_count": counts["retired"],
        "disabled_count": counts["disabled"],
        "unsafe_disabled_count": counts["unsafe_disabled"],
        "snapshot_count": counts["snapshot"],
        "dormant_count": counts["dormant"],
        "external_count": counts["external"],
        "total_ready_count": counts["ready"],
        "total_degraded_count": counts["degraded"],
        "total_unavailable_count": counts["unavailable"],
        "total_missing_adapter_count": counts["missing_adapter"],
        "total_uncovered_count": counts["uncovered"],
        "warning_count": sum(len(row.warnings) for row in required_rows),
        "optional_warning_count": sum(len(row.warnings) for row in optional_rows),
        "total_warning_count": sum(len(row.warnings) for row in rows),
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
    is_required = surface.surface_id in required
    optional_lifecycle_status = _optional_lifecycle_status(
        surface,
        required=is_required,
    )

    if factory is None:
        if optional_lifecycle_status is None and _expects_adapter(surface):
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

    if not surface.health.exists and optional_lifecycle_status is None:
        warnings.append("surface_missing")
    if surface.health.probe_error:
        warnings.append("surface_probe_error")
    if optional_lifecycle_status is None:
        warnings.extend(_surface_read_warnings(surface))

    normalized_warnings = tuple(sorted(dict.fromkeys(warnings)))
    return AdapterSurfaceReadiness(
        surface_id=surface.surface_id,
        status=_surface_status(
            surface,
            factory,
            normalized_warnings,
            required=is_required,
        ),
        required=is_required,
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


def _missing_required_surface_readiness(surface_id: str) -> AdapterSurfaceReadiness:
    return AdapterSurfaceReadiness(
        surface_id=surface_id,
        status="uncovered",
        required=True,
        adapter_registered=False,
        adapter_name=None,
        adapter_version=None,
        read_mode=None,
        surface_exists=False,
        active_status=SurfaceStatus.MISSING.value,
        adapter_mode="unknown",
        path_type="missing",
        atom_types=(),
        warnings=("required_surface_not_found",),
        record_count=None,
    )


def _surface_status(
    surface: MemorySurface,
    factory: AdapterFactory | None,
    warnings: tuple[str, ...],
    *,
    required: bool,
) -> str:
    optional_lifecycle_status = _optional_lifecycle_status(
        surface,
        required=required,
    )
    if optional_lifecycle_status is not None:
        return optional_lifecycle_status
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


def _optional_lifecycle_status(
    surface: MemorySurface,
    *,
    required: bool,
) -> str | None:
    if required:
        return None
    active_status = surface.active_status.value
    adapter_mode = surface.adapter_mode.value
    if active_status == "expected_unavailable":
        return "expected_unavailable" if not surface.health.exists else None
    if active_status == "retired":
        return "retired"
    if active_status == "disabled" or adapter_mode == AdapterMode.DISABLED.value:
        return "disabled"
    if surface.active_status == SurfaceStatus.UNSAFE:
        return "unsafe_disabled"
    if surface.active_status == SurfaceStatus.SNAPSHOT:
        return "snapshot"
    if surface.active_status == SurfaceStatus.DORMANT:
        return "dormant"
    if surface.active_status == SurfaceStatus.EXTERNAL:
        return "external"
    return None


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
        warnings.extend(sqlite_surface_read_warnings(path))
    if _looks_like_jsonl_surface(path, surface):
        warnings.extend(jsonl_surface_read_warnings(path, max_files=100))
    return tuple(sorted(dict.fromkeys(warnings)))


def _looks_like_sqlite(path: Path) -> bool:
    return path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}


def _looks_like_jsonl_surface(path: Path, surface: MemorySurface) -> bool:
    return path.suffix == ".jsonl" or surface.adapter_mode == AdapterMode.STREAMING


def _report_status(rows: tuple[AdapterSurfaceReadiness, ...]) -> str:
    required_rows = [row for row in rows if row.required]
    if any(row.status in REQUIRED_UNAVAILABLE_STATUSES for row in required_rows):
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
