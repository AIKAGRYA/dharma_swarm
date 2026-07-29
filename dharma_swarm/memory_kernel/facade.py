"""MemoryKernel read-only facade.

M1 exposes normalized atom streams over selected existing surfaces.  It is still
read-only: no ingestion, promotion, archive, migration, or write-through.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from dharma_swarm.memory_kernel.adapters.base import MemorySurfaceAdapter
from dharma_swarm.memory_kernel.adapters.generic import GenericSurfaceMetadataAdapter
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
from dharma_swarm.memory_kernel.atoms import (
    AdapterMode,
    MemoryAtom,
    MemoryAtomType,
    MemoryQuery,
    MemorySurface,
    ReadMode,
)
from dharma_swarm.memory_kernel.census import CensusConfig, CensusResult, MemorySurfaceCensus
from dharma_swarm.memory_kernel.context_admission import (
    MemoryContextBudget,
    MemoryContextPack,
    preview_memory_pack,
)
from dharma_swarm.memory_kernel.surfaces import default_surface_specs


AdapterFactory = Callable[[MemorySurface], MemorySurfaceAdapter]
RETRIEVAL_PROJECTION_SURFACE_ID = "home.vectors"
DEFAULT_REQUIRED_ADAPTER_SURFACE_IDS = (
    "home.codex_memory",
    "home.conversation_log",
    "home.knowledge_wiki",
    "home.memory_plane",
    "home.runtime_state",
    "home.smriti",
    "home.witness",
)


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
                degraded_atom = self._degraded_surface_atom(surface_id, resolved_query)
                if degraded_atom is not None:
                    yield degraded_atom
                    if remaining_total is not None:
                        remaining_total -= 1
                        if remaining_total <= 0:
                            return
                continue
            for atom in adapter.iter_atoms(query=adapter_query):
                if resolved_query.allows_atom(atom):
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

    def query(
        self,
        text: str,
        *,
        top_k: int = 10,
        include_content: bool = True,
        min_score: float = 0.01,
        enable_memory_kernel: bool = True,
        record_telemetry: bool = True,
    ):
        """Query the governed wiki/vector retrieval door for ranked context."""

        from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery

        state_dir = self.config.census.home / ".dharma"
        engine = GovernedRetrievalEngine(state_dir=state_dir, memory_kernel=self)
        return engine.retrieve(
            RetrievalQuery(
                text=text,
                top_k=max(1, top_k),
                include_content=include_content,
                min_score=min_score,
                enable_memory_kernel=enable_memory_kernel,
                record_telemetry=record_telemetry,
            )
        )

    def atoms_for_candidates(self, candidates: Iterable[object]) -> tuple[MemoryAtom, ...]:
        """Map ranked retrieval candidates onto MemoryAtoms for admission preview.

        Candidates come from the vector retrieval projection, so the atoms are
        stamped with the ``home.vectors`` surface (projection authority/risk
        posture preserved) and run through the same admission gates as any
        other atom — this helper never bypasses ``preview_memory_pack``.
        """

        surface = self.surfaces_by_id.get(RETRIEVAL_PROJECTION_SURFACE_ID)
        if surface is None:
            # Fail closed and loud: a silent () here would make shadow receipts
            # read admitted=0 with no stamped WHY, poisoning the flip decision.
            raise LookupError(
                "retrieval projection surface "
                f"{RETRIEVAL_PROJECTION_SURFACE_ID!r} missing from census"
            )
        atoms: list[MemoryAtom] = []
        for candidate in candidates:
            doc_id = str(getattr(candidate, "doc_id", "") or "")
            if not doc_id:
                continue
            source = str(getattr(candidate, "source", "") or "")
            content = getattr(candidate, "content", None) or None
            atoms.append(
                MemoryAtom.build(
                    surface=surface,
                    atom_type=MemoryAtomType.SOURCE_CHUNK,
                    content_ref=f"retrieval:{doc_id}",
                    content=content,
                    timestamp=(
                        getattr(candidate, "event_time", None)
                        or getattr(candidate, "ingestion_time", None)
                    ),
                    source_path=source or None,
                    adapter_name="governed_retrieval",
                    read_mode=ReadMode.READ_ONLY,
                    source_row_key=doc_id,
                    source_refs=(source,) if source else None,
                    metadata={
                        "retrieval_rank": getattr(candidate, "rank", None),
                        "retrieval_score": getattr(candidate, "score", None),
                        "retrieval_layer": str(getattr(candidate, "layer", "") or ""),
                        "retrieval_channels": [
                            str(channel)
                            for channel in (getattr(candidate, "channels", ()) or ())
                        ],
                    },
                )
            )
        return tuple(atoms)

    def search(
        self,
        text: str,
        *,
        top_k: int = 10,
        include_content: bool = True,
        min_score: float = 0.01,
    ):
        """Alias for query() for callers that expect a search-shaped API."""

        return self.query(
            text,
            top_k=top_k,
            include_content=include_content,
            min_score=min_score,
        )

    def adapter_readiness_report(
        self,
        *,
        required_surface_ids: Iterable[str] | None = None,
    ):
        from dharma_swarm.memory_kernel.readiness import (  # noqa: PLC0415
            build_adapter_readiness_report,
        )

        resolved_required_surface_ids = (
            tuple(required_surface_ids)
            if required_surface_ids is not None
            else DEFAULT_REQUIRED_ADAPTER_SURFACE_IDS
        )
        return build_adapter_readiness_report(
            surfaces=self.list_surfaces(),
            adapter_factories=self._adapter_factories,
            required_surface_ids=resolved_required_surface_ids,
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

    def _degraded_surface_atom(
        self,
        surface_id: str,
        query: MemoryQuery,
    ) -> MemoryAtom | None:
        if not query.include_degraded_metadata or not query.allows_atom_type(MemoryAtomType.METADATA):
            return None
        surface = self.surfaces_by_id.get(surface_id)
        if surface is None:
            return None
        warnings: list[str] = []
        if surface_id not in self._adapter_factories:
            warnings.append("adapter_not_registered")
        if not surface.health.exists:
            warnings.append("surface_missing")
        if surface.health.probe_error:
            warnings.append("surface_probe_error")
        if not warnings:
            warnings.append("adapter_unavailable")
        atom = MemoryAtom.build(
            surface=surface,
            atom_type=MemoryAtomType.METADATA,
            content_ref=f"{surface_id}:degraded_surface",
            content=None,
            timestamp=surface.health.last_modified,
            source_path=surface.path,
            adapter_name="memory_kernel_facade",
            read_mode=ReadMode.METADATA_ONLY,
            metadata={
                "degraded": True,
                "read_warnings": tuple(dict.fromkeys(warnings)),
                "surface_exists": surface.health.exists,
            },
            source_row_key=f"{surface_id}:degraded_surface",
        )
        if query.allows_atom(atom):
            return atom
        return None


def default_adapter_factories(
    config: ReadOnlyAdapterConfig | None = None,
) -> dict[str, AdapterFactory]:
    adapter_config = config or ReadOnlyAdapterConfig()

    factories: dict[str, AdapterFactory] = {
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
    for spec in default_surface_specs():
        if spec.surface_id in factories:
            continue
        if spec.adapter_mode not in {
            AdapterMode.READ_ONLY,
            AdapterMode.STREAMING,
            AdapterMode.METADATA_ONLY,
        }:
            continue
        factories[spec.surface_id] = _generic_metadata_factory(adapter_config)
    return factories


def _generic_metadata_factory(config: ReadOnlyAdapterConfig) -> AdapterFactory:
    return lambda surface: GenericSurfaceMetadataAdapter(surface, config=config)
