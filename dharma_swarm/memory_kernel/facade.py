"""MemoryKernel read-only facade.

M1 exposes normalized atom streams over selected existing surfaces.  It is still
read-only: no ingestion, promotion, archive, migration, or write-through.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from dharma_swarm.memory_kernel.adapters.base import MemorySurfaceAdapter
from dharma_swarm.memory_kernel.adapters.read_only import (
    CodexMemoryAdapter,
    ConversationLogMetadataAdapter,
    KnowledgeWikiAdapter,
    MemoryPlaneAdapter,
    ReadOnlyAdapterConfig,
    RuntimeStateAdapter,
    SmritiAdapter,
    WitnessJsonlAdapter,
)
from dharma_swarm.memory_kernel.atoms import MemoryAtom, MemoryAtomType, MemoryQuery, MemorySurface
from dharma_swarm.memory_kernel.census import CensusConfig, CensusResult, MemorySurfaceCensus
from dharma_swarm.memory_kernel.context_admission import (
    MemoryContextBudget,
    MemoryContextPack,
    preview_memory_pack,
)


AdapterFactory = Callable[[MemorySurface], MemorySurfaceAdapter]


@dataclass(frozen=True)
class MemoryKernelConfig:
    census: CensusConfig
    adapter: ReadOnlyAdapterConfig = ReadOnlyAdapterConfig()


class MemoryKernel:
    """Read-only coordination facade over registered memory surfaces."""

    def __init__(
        self,
        config: MemoryKernelConfig | None = None,
        *,
        census_result: CensusResult | None = None,
    ) -> None:
        self.config = config or MemoryKernelConfig(census=CensusConfig())
        self.census = MemorySurfaceCensus(self.config.census)
        self.census_result = census_result or self.census.run_result()
        self.surfaces_by_id = {
            surface.surface_id: surface for surface in self.census_result.surfaces
        }
        self._adapter_factories = default_adapter_factories(self.config.adapter)

    def list_surfaces(self) -> tuple[MemorySurface, ...]:
        return self.census_result.surfaces

    def summarize_surface_health(self) -> dict[str, object]:
        return self.census.summarize_surface_health(self.census_result)

    def list_adapter_ids(self) -> tuple[str, ...]:
        return tuple(
            surface_id
            for surface_id in sorted(self._adapter_factories)
            if surface_id in self.surfaces_by_id and self.surfaces_by_id[surface_id].health.exists
        )

    def get_adapter(self, surface_id: str) -> MemorySurfaceAdapter | None:
        surface = self.surfaces_by_id.get(surface_id)
        factory = self._adapter_factories.get(surface_id)
        if surface is None or factory is None or not surface.health.exists:
            return None
        return factory(surface)

    def iter_memory_atoms(
        self,
        *,
        surface_ids: Iterable[str] | None = None,
        atom_types: set[MemoryAtomType] | None = None,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
        limit_total: int | None = None,
    ) -> Iterable[MemoryAtom]:
        resolved_query = self._resolve_query(
            query,
            atom_types=atom_types,
            limit_per_surface=limit_per_surface,
            limit_total=limit_total,
        )
        remaining_total = resolved_query.total_limit()
        if remaining_total == 0:
            return
        selected_ids = tuple(surface_ids) if surface_ids is not None else self.list_adapter_ids()
        adapter_query = replace(resolved_query, limit_total=None)
        for surface_id in selected_ids:
            adapter = self.get_adapter(surface_id)
            if adapter is None:
                continue
            for atom in adapter.iter_atoms(query=adapter_query):
                if atom_types is None or atom.atom_type in atom_types:
                    yield atom
                    if remaining_total is not None:
                        remaining_total -= 1
                        if remaining_total <= 0:
                            return

    def iter_episodes(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.EPISODE, MemoryAtomType.EXTERNAL_MEMORY},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def iter_memory_facts(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.FACT, MemoryAtomType.EDGE},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def iter_source_chunks(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.SOURCE_CHUNK},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def iter_retrieval_feedback(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.RETRIEVAL_FEEDBACK},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def iter_witness_events(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.WITNESS_EVENT},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def iter_external_memory_atoms(
        self,
        *,
        query: MemoryQuery | None = None,
        limit_per_surface: int | None = None,
    ) -> Iterable[MemoryAtom]:
        return self.iter_memory_atoms(
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=query,
            limit_per_surface=limit_per_surface,
        )

    def preview_memory_pack(
        self,
        *,
        surface_ids: Iterable[str] | None = None,
        atom_types: set[MemoryAtomType] | None = None,
        query: MemoryQuery | None = None,
        budget: MemoryContextBudget | None = None,
    ) -> MemoryContextPack:
        resolved_budget = budget or MemoryContextBudget()
        resolved_query = (
            MemoryQuery(
                limit_total=resolved_budget.max_candidate_atoms,
                limit_per_surface=resolved_budget.max_candidate_atoms,
                include_content=resolved_budget.include_content,
            )
            if query is None
            else replace(
                query,
                include_content=query.include_content or resolved_budget.include_content,
            )
        )
        return preview_memory_pack(
            self.iter_memory_atoms(
                surface_ids=surface_ids,
                atom_types=atom_types,
                query=resolved_query,
            ),
            budget=resolved_budget,
        )

    def _resolve_query(
        self,
        query: MemoryQuery | None,
        *,
        atom_types: set[MemoryAtomType] | None,
        limit_per_surface: int | None,
        limit_total: int | None,
    ) -> MemoryQuery:
        resolved = query or MemoryQuery()
        if atom_types is not None:
            resolved = replace(
                resolved,
                atom_types=tuple(sorted(atom_types, key=lambda atom_type: atom_type.value)),
            )
        if limit_per_surface is not None:
            resolved = replace(resolved, limit_per_surface=limit_per_surface)
        if limit_total is not None:
            resolved = replace(resolved, limit_total=limit_total)
        return resolved


def default_adapter_factories(
    config: ReadOnlyAdapterConfig | None = None,
) -> dict[str, AdapterFactory]:
    adapter_config = config or ReadOnlyAdapterConfig()

    return {
        "home.memory_plane": lambda surface: MemoryPlaneAdapter(surface, config=adapter_config),
        "home.runtime_state": lambda surface: RuntimeStateAdapter(surface, config=adapter_config),
        "home.smriti": lambda surface: SmritiAdapter(surface, config=adapter_config),
        "home.witness": lambda surface: WitnessJsonlAdapter(surface, config=adapter_config),
        "home.knowledge_wiki": lambda surface: KnowledgeWikiAdapter(surface, config=adapter_config),
        "home.codex_memory": lambda surface: CodexMemoryAdapter(surface, config=adapter_config),
        "home.conversation_log": lambda surface: ConversationLogMetadataAdapter(
            surface,
            config=adapter_config,
        ),
    }
