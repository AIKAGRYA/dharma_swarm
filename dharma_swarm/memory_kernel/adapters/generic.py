"""Generic read-only metadata adapters for accounted MemoryKernel surfaces.

These adapters make low-confidence or high-risk surfaces visible to readiness
without ingesting their content or claiming canonical memory authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.adapters.read_only import BaseReadOnlyAdapter
from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    MemoryAtom,
    MemoryAtomType,
    MemoryQuery,
    MemorySurface,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    stable_digest,
)


class GenericSurfaceMetadataAdapter(BaseReadOnlyAdapter):
    """Bounded metadata-only adapter for surfaces without bespoke readers."""

    adapter_name = "generic_surface_metadata_adapter"
    adapter_version = "generic_metadata.v1"
    atom_type = MemoryAtomType.METADATA

    def __init__(
        self,
        surface: MemorySurface,
        *,
        config=None,
    ) -> None:
        super().__init__(surface, config=config)
        self.read_mode = _read_mode_for(surface.adapter_mode)

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._query(query, limit)
        surface_limit = self._surface_limit(resolved_query)
        if (
            surface_limit <= 0
            or not self.path.exists()
            or not resolved_query.allows_atom_type(MemoryAtomType.METADATA)
        ):
            return
        if _suppresses_atoms(self.surface):
            return
        timestamp = self.surface.health.last_modified or _path_mtime(self.path)
        content_ref = f"{self.surface_id}:surface_metadata"
        metadata = {
            "metadata_only": True,
            "reason": "generic adapter records bounded surface metadata only",
            "metadata_policy": "surface_health_only_no_content_ingestion",
            "content_ingestion": "suppressed",
            "child_names_redacted": True,
            "payloads_redacted": True,
            "surface_id": self.surface_id,
            "path_type": self.surface.health.path_type,
            "adapter_mode": self.surface.adapter_mode.value,
            "active_status": self.surface.active_status.value,
            "authority_level": self.surface.authority_level.value,
            "write_mode": self.surface.write_mode.value,
            "canon_risk": self.surface.canon_risk.value,
            "pii_secrets_risk": self.surface.pii_secrets_risk.value,
            "size_bytes": self.surface.health.size_bytes,
            "record_count": self.surface.health.record_count,
            "notes": self.surface.health.notes,
        }
        if _is_high_risk_surface(self.surface):
            metadata["risk_policy"] = "high_risk_metadata_only"
        atom = self._atom(
            MemoryAtomType.METADATA,
            query=resolved_query,
            content_ref=content_ref,
            content=None,
            timestamp=timestamp,
            source_path=self.path.as_posix(),
            metadata=metadata,
            source_digest=stable_digest(
                {
                    "surface_id": self.surface_id,
                    "path": self.path.as_posix(),
                    "path_type": self.surface.health.path_type,
                    "size_bytes": self.surface.health.size_bytes,
                    "last_modified": self.surface.health.last_modified,
                    "active_status": self.surface.active_status.value,
                }
            ),
            source_row_key=content_ref,
            source_last_modified=timestamp,
        )
        if resolved_query.cursor == atom.atom_id:
            return
        if resolved_query.allows_atom(atom):
            yield atom


def _read_mode_for(adapter_mode: AdapterMode) -> ReadMode:
    if adapter_mode == AdapterMode.STREAMING:
        return ReadMode.STREAMING
    if adapter_mode == AdapterMode.METADATA_ONLY:
        return ReadMode.METADATA_ONLY
    return ReadMode.READ_ONLY


def _suppresses_atoms(surface: MemorySurface) -> bool:
    return (
        surface.category == SurfaceCategory.UNSAFE
        or surface.active_status == SurfaceStatus.UNSAFE
        or surface.role == MemorySurfaceRole.UNSAFE_FIXTURE
    )


def _is_high_risk_surface(surface: MemorySurface) -> bool:
    return (
        surface.canon_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        or surface.pii_secrets_risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    )


def _path_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


GenericMetadataAdapter = GenericSurfaceMetadataAdapter
