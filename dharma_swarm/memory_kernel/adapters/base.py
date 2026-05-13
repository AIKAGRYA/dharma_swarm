"""Base interfaces for read-only MemoryKernel surface adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from dharma_swarm.memory_kernel.atoms import MemoryAtom, MemoryQuery, MemorySurfaceHealth


@dataclass(frozen=True)
class SurfaceProbe:
    """Bounded observation of a memory surface.

    M0 probes describe surfaces only.  They do not load memory bodies or make
    writes to the target store.
    """

    path: Path
    health: MemorySurfaceHealth
    metadata: dict[str, Any] = field(default_factory=dict)


class MemorySurfaceAdapter(Protocol):
    """Minimal read-only contract for MemoryKernel adapters."""

    surface_id: str

    def probe(self) -> SurfaceProbe:
        """Return bounded health/schema metadata for the surface."""

    def iter_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit: int | None = None,
    ) -> Iterable[MemoryAtom]:
        """Yield bounded normalized atoms without mutating the source surface."""
