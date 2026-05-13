"""Read-only writer inventory for MemoryKernel M2A.

The sentinel does not intercept, redirect, or block writes.  It records the
known memory-like write paths so bypasses become visible before any write gate
exists.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from dharma_swarm.memory_kernel.atoms import RiskLevel, WriteMode
from dharma_swarm.memory_kernel.surfaces import default_surface_specs


class WriterClassification(StrEnum):
    APPROVED = "approved"
    LEGACY_TOLERATED = "legacy_tolerated"
    REVIEW_REQUIRED = "review_required"
    UNSAFE = "unsafe"
    DORMANT = "dormant"


class WriterStatus(StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNREGISTERED_SURFACE = "unregistered_surface"
    ERROR = "error"


class DiscoveredWriteStatus(StrEnum):
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    IGNORED = "ignored"


class DiscoveryTriageCategory(StrEnum):
    REGISTERED_MEMORY_WRITER = "registered_memory_writer"
    MEMORY_WRITER_NEEDS_SPEC = "memory_writer_needs_spec"
    SURFACE_NEEDS_REGISTRY = "surface_needs_registry"
    READ_WRITE_HELPER = "read_write_helper"
    OPERATIONAL_STATE = "operational_state"
    GENERATED_ARTIFACT = "generated_artifact"
    TEST_OR_EXPERIMENT = "test_or_experiment"
    FALSE_POSITIVE = "false_positive"


@dataclass(frozen=True)
class MemoryWriterSpec:
    writer_id: str
    owner_module: str
    symbol: str
    writes_to: tuple[str, ...]
    write_mode: WriteMode
    classification: WriterClassification
    risk: RiskLevel
    notes: str = ""

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["write_mode"] = self.write_mode.value
        payload["classification"] = self.classification.value
        payload["risk"] = self.risk.value
        return payload


@dataclass(frozen=True)
class DiscoveredMemoryWrite:
    source_path: str
    symbol: str
    line: int
    operation: str
    target: str
    mode: str
    reason: str
    status: DiscoveredWriteStatus
    triage_category: DiscoveryTriageCategory
    triage_reason: str
    matched_writer_ids: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["triage_category"] = self.triage_category.value
        return payload


@dataclass(frozen=True)
class MemoryWriterObservation:
    spec: MemoryWriterSpec
    source_path: str
    present: bool
    status: WriterStatus
    unregistered_surfaces: tuple[str, ...] = ()
    error: str | None = None

    def to_json(self) -> dict[str, object]:
        payload = {
            "writer": self.spec.to_json(),
            "source_path": self.source_path,
            "present": self.present,
            "status": self.status.value,
            "unregistered_surfaces": self.unregistered_surfaces,
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class WriterSentinelSummary:
    writer_count: int
    present_count: int
    missing_count: int
    unregistered_surface_count: int
    error_count: int
    by_classification: dict[str, int]
    by_status: dict[str, int]

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WriterDiscoverySummary:
    scanned_file_count: int
    parse_error_count: int
    discovered_write_count: int
    registered_discovery_count: int
    unregistered_discovery_count: int
    action_required_count: int
    top_unregistered_sources: tuple[dict[str, object], ...]
    by_operation: dict[str, int]
    by_status: dict[str, int]
    by_triage: dict[str, int]

    def to_json(self) -> dict[str, object]:
        return asdict(self)


class MemoryWriterSentinel:
    """Inventory registered memory-like write paths."""

    def __init__(
        self,
        *,
        repo_root: Path | str,
        specs: Iterable[MemoryWriterSpec] | None = None,
        known_surface_ids: Iterable[str] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.specs = tuple(specs or default_writer_specs())
        self.known_surface_ids = set(
            known_surface_ids
            if known_surface_ids is not None
            else (surface.surface_id for surface in default_surface_specs())
        )

    def run(self) -> tuple[MemoryWriterObservation, ...]:
        return tuple(self._observe(spec) for spec in self.specs)

    def summarize(self, observations: Iterable[MemoryWriterObservation]) -> WriterSentinelSummary:
        rows = tuple(observations)
        by_classification: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for row in rows:
            by_classification[row.spec.classification.value] = (
                by_classification.get(row.spec.classification.value, 0) + 1
            )
            by_status[row.status.value] = by_status.get(row.status.value, 0) + 1
        return WriterSentinelSummary(
            writer_count=len(rows),
            present_count=sum(1 for row in rows if row.present),
            missing_count=sum(1 for row in rows if row.status == WriterStatus.MISSING),
            unregistered_surface_count=sum(
                len(row.unregistered_surfaces) for row in rows
            ),
            error_count=sum(1 for row in rows if row.status == WriterStatus.ERROR),
            by_classification=by_classification,
            by_status=by_status,
        )

    def discover_write_paths(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> tuple[DiscoveredMemoryWrite, ...]:
        files = tuple(self._iter_scan_files(scan_roots=scan_roots, max_files=max_files))
        registered = self._registered_symbol_index()
        discovered: list[DiscoveredMemoryWrite] = []
        for source_path in files:
            try:
                tree = ast.parse(source_path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            visitor = _MemoryWriteVisitor(source_path=source_path, repo_root=self.repo_root)
            visitor.visit(tree)
            for candidate in visitor.discovered:
                matches = _matching_writer_ids(candidate, registered)
                status = (
                    DiscoveredWriteStatus.REGISTERED
                    if matches
                    else DiscoveredWriteStatus.UNREGISTERED
                )
                triage_category, triage_reason = _triage_discovered_write(
                    candidate,
                    status=status,
                )
                discovered.append(
                    DiscoveredMemoryWrite(
                        source_path=candidate.source_path,
                        symbol=candidate.symbol,
                        line=candidate.line,
                        operation=candidate.operation,
                        target=candidate.target,
                        mode=candidate.mode,
                        reason=candidate.reason,
                        status=status,
                        triage_category=triage_category,
                        triage_reason=triage_reason,
                        matched_writer_ids=matches,
                    )
                )
        return tuple(discovered)

    def summarize_discoveries(
        self,
        discoveries: Iterable[DiscoveredMemoryWrite],
        *,
        scanned_file_count: int | None = None,
        parse_error_count: int = 0,
    ) -> WriterDiscoverySummary:
        rows = tuple(discoveries)
        by_operation: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_triage: dict[str, int] = {}
        by_unregistered_source: dict[str, int] = {}
        for row in rows:
            by_operation[row.operation] = by_operation.get(row.operation, 0) + 1
            by_status[row.status.value] = by_status.get(row.status.value, 0) + 1
            by_triage[row.triage_category.value] = by_triage.get(row.triage_category.value, 0) + 1
            if row.status == DiscoveredWriteStatus.UNREGISTERED:
                by_unregistered_source[row.source_path] = (
                    by_unregistered_source.get(row.source_path, 0) + 1
                )
        top_unregistered_sources = tuple(
            {"source_path": source_path, "count": count}
            for source_path, count in sorted(
                by_unregistered_source.items(),
                key=lambda item: (-item[1], item[0]),
            )[:10]
        )
        return WriterDiscoverySummary(
            scanned_file_count=scanned_file_count if scanned_file_count is not None else 0,
            parse_error_count=parse_error_count,
            discovered_write_count=len(rows),
            registered_discovery_count=sum(
                1 for row in rows if row.status == DiscoveredWriteStatus.REGISTERED
            ),
            unregistered_discovery_count=sum(
                1 for row in rows if row.status == DiscoveredWriteStatus.UNREGISTERED
            ),
            action_required_count=sum(
                1
                for row in rows
                if row.triage_category
                in {
                    DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
                    DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
                }
            ),
            top_unregistered_sources=top_unregistered_sources,
            by_operation=by_operation,
            by_status=by_status,
            by_triage=by_triage,
        )

    def _observe(self, spec: MemoryWriterSpec) -> MemoryWriterObservation:
        source_path = self._module_path(spec.owner_module)
        unregistered = tuple(
            surface_id for surface_id in spec.writes_to if surface_id not in self.known_surface_ids
        )
        if source_path is None or not source_path.exists():
            return MemoryWriterObservation(
                spec=spec,
                source_path=str(source_path or ""),
                present=False,
                status=WriterStatus.MISSING,
                unregistered_surfaces=unregistered,
            )
        try:
            present = _symbol_exists(source_path, spec.symbol)
        except (OSError, SyntaxError) as exc:
            return MemoryWriterObservation(
                spec=spec,
                source_path=source_path.as_posix(),
                present=False,
                status=WriterStatus.ERROR,
                unregistered_surfaces=unregistered,
                error=str(exc),
            )
        if not present:
            return MemoryWriterObservation(
                spec=spec,
                source_path=source_path.as_posix(),
                present=False,
                status=WriterStatus.MISSING,
                unregistered_surfaces=unregistered,
            )
        status = WriterStatus.UNREGISTERED_SURFACE if unregistered else WriterStatus.PRESENT
        return MemoryWriterObservation(
            spec=spec,
            source_path=source_path.as_posix(),
            present=True,
            status=status,
            unregistered_surfaces=unregistered,
        )

    def _module_path(self, owner_module: str) -> Path | None:
        if owner_module.endswith(".py") or "/" in owner_module:
            return self.repo_root / owner_module
        return self.repo_root / Path(*owner_module.split(".")).with_suffix(".py")

    def _iter_scan_files(
        self,
        *,
        scan_roots: Iterable[Path | str] | None,
        max_files: int,
    ) -> Iterable[Path]:
        roots = tuple(scan_roots or ("dharma_swarm", "scripts"))
        emitted = 0
        for root in roots:
            root_path = Path(root)
            if not root_path.is_absolute():
                root_path = self.repo_root / root_path
            if root_path.is_file() and root_path.suffix == ".py":
                yield root_path
                emitted += 1
                if emitted >= max_files:
                    return
                continue
            if not root_path.is_dir():
                continue
            for path in sorted(root_path.rglob("*.py")):
                if _skip_scan_path(path):
                    continue
                yield path
                emitted += 1
                if emitted >= max_files:
                    return

    def count_scan_files(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> int:
        return sum(1 for _ in self._iter_scan_files(scan_roots=scan_roots, max_files=max_files))

    def count_parse_errors(
        self,
        *,
        scan_roots: Iterable[Path | str] | None = None,
        max_files: int = 2000,
    ) -> int:
        errors = 0
        for path in self._iter_scan_files(scan_roots=scan_roots, max_files=max_files):
            try:
                ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                errors += 1
        return errors

    def _registered_symbol_index(self) -> dict[str, tuple[MemoryWriterSpec, ...]]:
        by_path: dict[str, list[MemoryWriterSpec]] = {}
        for spec in self.specs:
            source_path = self._module_path(spec.owner_module)
            if source_path is None:
                continue
            key = _relative_path(source_path, self.repo_root)
            by_path.setdefault(key, []).append(spec)
        return {path: tuple(specs) for path, specs in by_path.items()}


def default_writer_specs() -> tuple[MemoryWriterSpec, ...]:
    return (
        MemoryWriterSpec(
            "memory_lattice.ingest_runtime_envelope",
            "dharma_swarm.memory_lattice",
            "MemoryLattice.ingest_runtime_envelope",
            ("home.runtime_state",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Coordinates event ingestion and optional JSONL event log append.",
        ),
        MemoryWriterSpec(
            "memory_lattice.remember",
            "dharma_swarm.memory_lattice",
            "MemoryLattice.remember",
            ("home.runtime_state", "home.vectors"),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Writes strange-loop memory and projection index entries.",
        ),
        MemoryWriterSpec(
            "memory_lattice.record_fact",
            "dharma_swarm.memory_lattice",
            "MemoryLattice.record_fact",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Fact writes must remain non-canonical until KnowledgeOps promotion gates exist.",
        ),
        MemoryWriterSpec(
            "runtime_state.record_memory_fact",
            "dharma_swarm.runtime_state",
            "RuntimeStateStore.record_memory_fact",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.APPROVED,
            RiskLevel.MEDIUM,
            "Control-plane fact store; authority is runtime, not semantic canon.",
        ),
        MemoryWriterSpec(
            "runtime_state.record_memory_edge",
            "dharma_swarm.runtime_state",
            "RuntimeStateStore.record_memory_edge",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.APPROVED,
            RiskLevel.MEDIUM,
            "Control-plane edge store; authority is runtime, not semantic canon.",
        ),
        MemoryWriterSpec(
            "conversation_memory.record_turn",
            "dharma_swarm.engine.conversation_memory",
            "ConversationMemoryStore.record_turn",
            ("home.memory_plane",),
            WriteMode.APPEND_ONLY,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "Raw conversation and shard harvesting path; keep provenance labels attached.",
        ),
        MemoryWriterSpec(
            "retrieval_feedback.log_hits",
            "dharma_swarm.engine.retrieval_feedback",
            "RetrievalFeedbackStore.log_hits",
            ("home.memory_plane",),
            WriteMode.APPEND_ONLY,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.MEDIUM,
            "Retrieval telemetry is feedback evidence, not truth.",
        ),
        MemoryWriterSpec(
            "providers.routing_audit",
            "dharma_swarm.providers",
            "ModelRouter._append_routing_audit",
            ("home.router_audit_log",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Provider router audit JSONL is route evidence, not semantic truth.",
        ),
        MemoryWriterSpec(
            "providers.route_retrospective",
            "dharma_swarm.providers",
            "ModelRouter._append_route_retrospective",
            ("home.router_audit_log",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Route retrospective JSONL is provider-learning evidence, not canon.",
        ),
        MemoryWriterSpec(
            "routing_memory.store",
            "dharma_swarm.routing_memory",
            "RoutingMemoryStore",
            ("home.routing_memory",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Provider-learning SQLite store is memory-like runtime telemetry, not semantic truth.",
        ),
        MemoryWriterSpec(
            "runtime_state.store",
            "dharma_swarm.runtime_state",
            "RuntimeStateStore",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.APPROVED,
            RiskLevel.MEDIUM,
            "RuntimeStateStore is the runtime/control-plane writer boundary, not semantic canon.",
        ),
        MemoryWriterSpec(
            "telemetry_plane.store",
            "dharma_swarm.telemetry_plane",
            "TelemetryPlaneStore",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Telemetry plane writes company-state records into runtime.db.",
        ),
        MemoryWriterSpec(
            "event_memory.store",
            "dharma_swarm.engine.event_memory",
            "EventMemoryStore",
            ("home.memory_plane",),
            WriteMode.APPEND_ONLY,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.MEDIUM,
            "Event memory is raw runtime evidence in memory_plane.db.",
        ),
        MemoryWriterSpec(
            "conversation_memory.store",
            "dharma_swarm.engine.conversation_memory",
            "ConversationMemoryStore",
            ("home.memory_plane",),
            WriteMode.READ_WRITE,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "Conversation turns, idea shards, uptake, and follow-ups are raw evidence.",
        ),
        MemoryWriterSpec(
            "retrieval_feedback.store",
            "dharma_swarm.engine.retrieval_feedback",
            "RetrievalFeedbackStore",
            ("home.memory_plane",),
            WriteMode.READ_WRITE,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.MEDIUM,
            "Retrieval feedback is usefulness evidence, not truth.",
        ),
        MemoryWriterSpec(
            "unified_index.store",
            "dharma_swarm.engine.unified_index",
            "UnifiedIndex",
            ("home.memory_plane",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Unified index writes documents/chunks into memory_plane as retrieval projection state.",
        ),
        MemoryWriterSpec(
            "vector_store.store",
            "dharma_swarm.vector_store",
            "VectorStore",
            ("home.vectors",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "VectorStore writes retrieval projections; never authority.",
        ),
        MemoryWriterSpec(
            "vector_store.tfidf_state",
            "dharma_swarm.vector_store",
            "TFIDFEmbedder",
            ("home.vectors",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "TF-IDF model state is retrieval projection sidecar state.",
        ),
        MemoryWriterSpec(
            "agent_memory_manager.store",
            "dharma_swarm.agent_memory_manager",
            "AgentMemoryManager",
            ("home.agent_memory_db",),
            WriteMode.READ_WRITE,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "SQLite-backed agent memories remain raw agent evidence.",
        ),
        MemoryWriterSpec(
            "organism_memory.store",
            "dharma_swarm.organism_memory",
            "OrganismMemory",
            ("home.organism_memory",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Organism self-model events and relationships are reflections, not canon.",
        ),
        MemoryWriterSpec(
            "swarm.manager_memory_writers",
            "dharma_swarm.swarm",
            "SwarmManager",
            (
                "home.memory_db",
                "home.memory_plane",
                "home.runtime_state",
                "home.agent_memory",
            ),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Top-level coordinator delegates to multiple memory stores; keep boundary visible.",
        ),
        MemoryWriterSpec(
            "intelligence_adapters.memory_plane",
            "dharma_swarm.contracts.intelligence_adapters",
            "SovereignMemoryPlaneAdapter",
            ("home.memory_plane",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Contract adapter writes to the memory plane; provenance must stay attached.",
        ),
        MemoryWriterSpec(
            "intelligence_adapters.skill_store",
            "dharma_swarm.contracts.intelligence_adapters",
            "SovereignSkillStoreAdapter",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Skill-store contract state is runtime/control evidence.",
        ),
        MemoryWriterSpec(
            "intelligence_adapters.evaluation_sink",
            "dharma_swarm.contracts.intelligence_adapters",
            "SovereignEvaluationSinkAdapter",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Evaluation sink writes runtime evaluation telemetry.",
        ),
        MemoryWriterSpec(
            "intelligence_adapters.learning_engine",
            "dharma_swarm.contracts.intelligence_adapters",
            "SovereignLearningEngineAdapter",
            ("home.runtime_state",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Learning-engine contract writes runtime learning records.",
        ),
        MemoryWriterSpec(
            "bridge_registry.store",
            "dharma_swarm.bridge_registry",
            "BridgeRegistry",
            ("home.bridges",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Cross-graph bridge edges are linking evidence, not canon.",
        ),
        MemoryWriterSpec(
            "ecosystem_index.store",
            "dharma_swarm.ecosystem_index",
            "EcosystemIndex",
            ("home.ecosystem_index",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "FTS ecosystem index is a projection over source files.",
        ),
        MemoryWriterSpec(
            "graph_store.sqlite",
            "dharma_swarm.graph_store",
            "SQLiteGraphStore",
            ("home.dharma_graphs",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Generic graph-store writes derived graph state.",
        ),
        MemoryWriterSpec(
            "hibernation.store",
            "dharma_swarm.hibernation",
            "HibernationManager",
            ("home.hibernation",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Hibernate-and-wake state is runtime control memory.",
        ),
        MemoryWriterSpec(
            "kaizen_ops_local.store",
            "dharma_swarm.kaizen_ops_local",
            "KaizenOpsLocal",
            ("home.kaizen_ops",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Kaizen ops database is operational telemetry.",
        ),
        MemoryWriterSpec(
            "knowledge_units.store",
            "dharma_swarm.knowledge_units",
            "KnowledgeStore",
            ("home.state_knowledge",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Structured knowledge units are candidates until KnowledgeOps promotion gates exist.",
        ),
        MemoryWriterSpec(
            "lineage.graph",
            "dharma_swarm.lineage",
            "LineageGraph",
            ("home.ontology",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Lineage graph writes provenance edges into the ontology runtime store.",
        ),
        MemoryWriterSpec(
            "ontology_hub.store",
            "dharma_swarm.ontology_hub",
            "OntologyHub",
            ("home.ontology",),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Ontology hub is semantic graph state but not M0 canonical by default.",
        ),
        MemoryWriterSpec(
            "temporal_graph.store",
            "dharma_swarm.temporal_graph",
            "TemporalKnowledgeGraph",
            ("home.temporal_graph",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Temporal co-occurrence graph is temporal evidence/projection.",
        ),
        MemoryWriterSpec(
            "pruner.store",
            "dharma_swarm.pruner",
            "Pruner",
            ("home.stigmergy", "home.bridges"),
            WriteMode.READ_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Pruner mutates coordination marks and bridge edges; retain audit visibility.",
        ),
        MemoryWriterSpec(
            "observability.local_trace_store",
            "dharma_swarm.observability",
            "LocalTraceStore",
            ("home.traces",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Local traces and cost ledger entries are telemetry evidence.",
        ),
        MemoryWriterSpec(
            "agent_memory.remember",
            "dharma_swarm.agent_memory",
            "AgentMemoryBank.remember",
            ("home.agent_memory",),
            WriteMode.READ_WRITE,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "Agent self-memory remains raw evidence until gated.",
        ),
        MemoryWriterSpec(
            "agent_memory.save",
            "dharma_swarm.agent_memory",
            "AgentMemoryBank.save",
            ("home.agent_memory",),
            WriteMode.READ_WRITE,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "JSON persistence for agent self-memory.",
        ),
        MemoryWriterSpec(
            "conversation_log.log_exchange",
            "dharma_swarm.conversation_log",
            "log_exchange",
            ("home.conversation_log",),
            WriteMode.APPEND_ONLY,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "High-volume raw episodic log; must stay streaming/metadata-first.",
        ),
        MemoryWriterSpec(
            "conversation_log.log_agent_turn",
            "dharma_swarm.conversation_log",
            "log_agent_turn",
            ("home.conversation_log",),
            WriteMode.APPEND_ONLY,
            WriterClassification.LEGACY_TOLERATED,
            RiskLevel.HIGH,
            "High-volume raw episodic log; must stay streaming/metadata-first.",
        ),
        MemoryWriterSpec(
            "semantic_memory_bridge.index_concepts",
            "dharma_swarm.semantic_memory_bridge",
            "index_concepts_into_memory",
            ("home.runtime_state",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Semantic concepts are indexed into retrieval; they are derived, not canon.",
        ),
        MemoryWriterSpec(
            "semantic_memory_bridge.sleep_phase",
            "dharma_swarm.semantic_memory_bridge",
            "run_semantic_sleep_phase",
            ("home.semantic_concept_graph",),
            WriteMode.PROJECTION_WRITE,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.HIGH,
            "Semantic sleep graph is a projection and should not be cited as authority.",
        ),
        MemoryWriterSpec(
            "algedonic_bridge.write_witness",
            "dharma_swarm.algedonic_bridge",
            "_write_witness",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Algedonic bridge writer is planned or branch-local on current main.",
        ),
        MemoryWriterSpec(
            "bhed_gnan_monitor.write_witness",
            "dharma_swarm.bhed_gnan_monitor",
            "BhedGnanMonitor.write_witness",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Bhed/Gnani monitor writer is planned or branch-local on current main.",
        ),
        MemoryWriterSpec(
            "persistent_agent.write_witness",
            "dharma_swarm.persistent_agent",
            "PersistentAgent._write_witness",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Persistent-agent witness append path.",
        ),
        MemoryWriterSpec(
            "replication_protocol.write_witness",
            "dharma_swarm.replication_protocol",
            "ReplicationProtocol._write_witness",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Replication witness append path.",
        ),
        MemoryWriterSpec(
            "telos_gates.write_witness",
            "dharma_swarm.telos_gates",
            "TelosGatekeeper._log_witness",
            ("home.telos", "home.witness"),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Telos witness logs are intent/provenance evidence.",
        ),
        MemoryWriterSpec(
            "telos_gates.coupling_feedback",
            "dharma_swarm.telos_gates",
            "check_action",
            ("home.meta",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Gate feedback coupling is meta-control evidence.",
        ),
        MemoryWriterSpec(
            "opportunity_dispatcher.review_warn",
            "dharma_swarm.opportunity_dispatcher",
            "_write_review_warn",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Opportunity dispatcher writer is planned or branch-local on current main.",
        ),
        MemoryWriterSpec(
            "orchestrator.task_failure_algedonic",
            "dharma_swarm.orchestrator",
            "Orchestrator._handle_task_failure",
            ("home.algedonic_signals",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Task failure algedonic signal append path.",
        ),
        MemoryWriterSpec(
            "consume_review_marks.append_witness",
            "scripts.consume_review_marks",
            "append_witness",
            ("home.control",),
            WriteMode.APPEND_ONLY,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Review mark consumer script is not present on current main.",
        ),
        MemoryWriterSpec(
            "consume_review_marks.escalate_to_taskboard",
            "scripts.consume_review_marks",
            "escalate_to_taskboard",
            ("home.control",),
            WriteMode.READ_WRITE,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Review mark consumer script is not present on current main.",
        ),
        MemoryWriterSpec(
            "check_packet_provenance.append_witness",
            "scripts.governance.check_packet_provenance",
            "append_witness",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.DORMANT,
            RiskLevel.MEDIUM,
            "Packet provenance checker script is not present on current main.",
        ),
        MemoryWriterSpec(
            "orchestrate_live.revenue_intel_signal",
            "dharma_swarm.orchestrate_live",
            "_on_revenue_intel",
            ("home.revenue_intel",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Signal-bus revenue intel JSONL is telemetry evidence, not canon.",
        ),
        MemoryWriterSpec(
            "population_control.record_fitness_signal",
            "dharma_swarm.population_control",
            "record_fitness_signal",
            ("home.population",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Fitness signal JSONL is operational learning evidence.",
        ),
        MemoryWriterSpec(
            "training_flywheel.record_trajectory_from_signal",
            "dharma_swarm.training_flywheel",
            "record_trajectory_from_signal",
            ("home.training",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Training trajectory JSONL is learning telemetry.",
        ),
        MemoryWriterSpec(
            "witness.record_anomaly_signal",
            "dharma_swarm.witness",
            "record_anomaly_signal",
            ("home.witness",),
            WriteMode.APPEND_ONLY,
            WriterClassification.REVIEW_REQUIRED,
            RiskLevel.MEDIUM,
            "Anomaly signal JSONL is witness evidence.",
        ),
    )


def _symbol_exists(source_path: Path, symbol: str) -> bool:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    parts = symbol.split(".")
    if len(parts) == 1:
        return any(_node_name(node) == parts[0] for node in ast.walk(tree))
    class_name, member_name = parts[0], parts[1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(_node_name(child) == member_name for child in node.body)
    return False


def _node_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    return None


@dataclass(frozen=True)
class _DiscoveredWriteCandidate:
    source_path: str
    symbol: str
    line: int
    operation: str
    target: str
    mode: str
    reason: str


class _MemoryWriteVisitor(ast.NodeVisitor):
    def __init__(self, *, source_path: Path, repo_root: Path) -> None:
        self.source_path = source_path
        self.repo_root = repo_root
        self.discovered: list[_DiscoveredWriteCandidate] = []
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []
        self._memory_var_stack: list[dict[str, str]] = []
        self._sql_write_stack: list[bool] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_stack.append(node.name)
        self._memory_var_stack.append({})
        self._sql_write_stack.append(_contains_sql_write(node))
        self.generic_visit(node)
        self._sql_write_stack.pop()
        self._memory_var_stack.pop()
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function_stack.append(node.name)
        self._memory_var_stack.append({})
        self._sql_write_stack.append(_contains_sql_write(node))
        self.generic_visit(node)
        self._sql_write_stack.pop()
        self._memory_var_stack.pop()
        self._function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        value_expr = _safe_unparse(node.value)
        if self._memory_var_stack and _is_memory_like_expr(value_expr):
            for target in node.targets:
                for name in _assigned_names(target):
                    self._memory_var_stack[-1][name] = value_expr
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            self._memory_var_stack
            and node.value is not None
            and _is_memory_like_expr(_safe_unparse(node.value))
        ):
            value_expr = _safe_unparse(node.value)
            for name in _assigned_names(node.target):
                self._memory_var_stack[-1][name] = value_expr
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        detected = _detect_memory_write_call(
            node,
            memory_vars=self._memory_vars(),
            sql_write_context=any(self._sql_write_stack),
        )
        if detected is not None:
            operation, mode, target, reason = detected
            self.discovered.append(
                _DiscoveredWriteCandidate(
                    source_path=_relative_path(self.source_path, self.repo_root),
                    symbol=self._symbol(),
                    line=int(getattr(node, "lineno", 0)),
                    operation=operation,
                    target=target,
                    mode=mode,
                    reason=reason,
                )
            )
        self.generic_visit(node)

    def _symbol(self) -> str:
        class_name = self._class_stack[-1] if self._class_stack else ""
        function_name = self._function_stack[-1] if self._function_stack else ""
        if class_name and function_name:
            return f"{class_name}.{function_name}"
        if function_name:
            return function_name
        if class_name:
            return class_name
        return "<module>"

    def _memory_vars(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for scope in self._memory_var_stack:
            merged.update(scope)
        return merged


def _detect_memory_write_call(
    node: ast.Call,
    *,
    memory_vars: dict[str, str],
    sql_write_context: bool,
) -> tuple[str, str, str, str] | None:
    call_name = _call_name(node.func)
    target = _safe_unparse(node)
    origin = _memory_var_origin(target, memory_vars)
    effective_target = f"{target} [origin: {origin}]" if origin else target
    mode = _call_mode(node, path_open=call_name.endswith(".open") and call_name != "open")
    memory_like = _is_memory_like_expr(target) or origin is not None
    if call_name in {"sqlite3.connect", "aiosqlite.connect"} and memory_like and sql_write_context:
        return (
            "sqlite_connect",
            "read_write",
            effective_target,
            "sqlite connection in function containing schema/write SQL",
        )
    if call_name in {"open", "aiofiles.open"} and _is_write_mode(mode) and memory_like:
        return (
            "file_open_write",
            mode or "unknown_write",
            effective_target,
            "file open with write/append mode on memory-like path expression",
        )
    if call_name.endswith(".open") and _is_write_mode(mode) and memory_like:
        return (
            "path_open_write",
            mode or "unknown_write",
            effective_target,
            "Path.open with write/append mode on memory-like path expression",
        )
    if (
        (call_name.endswith(".write_text") or call_name.endswith(".write_bytes"))
        and memory_like
    ):
        return (
            "path_write",
            "write",
            effective_target,
            "Path write helper on memory-like path expression",
        )
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _call_mode(node: ast.Call, *, path_open: bool = False) -> str:
    if path_open and node.args:
        value = _constant_string(node.args[0])
        if value:
            return value
    if len(node.args) >= 2:
        value = _constant_string(node.args[1])
        if value:
            return value
    for keyword in node.keywords:
        if keyword.arg == "mode":
            value = _constant_string(keyword.value)
            if value:
                return value
    return ""


def _constant_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in ("a", "w", "x", "+"))


def _is_memory_like_expr(expr: str) -> bool:
    lowered = expr.lower()
    tokens = (
        ".dharma",
        "agent_memory",
        "codex",
        "conversation",
        "db_path",
        "default_",
        "knowledge",
        "log_dir",
        "memory",
        "ontology",
        "routing",
        "semantic",
        "smriti",
        "state",
        "telos",
        "vector",
        "witness",
        ".jsonl",
        ".sqlite",
        ".sqlite3",
        ".db",
    )
    return any(token in lowered for token in tokens)


def _contains_sql_write(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        call_name = _call_name(child.func)
        if not (
            call_name.endswith(".execute")
            or call_name.endswith(".executescript")
            or call_name in {"execute", "executescript"}
        ):
            continue
        sql = _first_sql_literal(child)
        if _is_sql_write(sql):
            return True
    return False


def _first_sql_literal(node: ast.Call) -> str:
    if not node.args:
        return ""
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        return "".join(
            value.value for value in arg.values if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return ""


def _is_sql_write(sql: str) -> bool:
    normalized = " ".join(sql.lower().split())
    if not normalized:
        return False
    prefixes = (
        "alter ",
        "create ",
        "delete ",
        "drop ",
        "insert ",
        "pragma journal_mode",
        "replace ",
        "update ",
    )
    return normalized.startswith(prefixes) or any(
        token in normalized
        for token in (
            " insert into ",
            " create table ",
            " update ",
            " delete from ",
            " replace into ",
        )
    )


def _memory_var_origin(expr: str, memory_vars: dict[str, str]) -> str | None:
    for name, origin in memory_vars.items():
        if expr == name or expr.startswith(f"{name}."):
            return origin
    return None


def _assigned_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names.update(_assigned_names(element))
        return names
    return set()


def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _matching_writer_ids(
    candidate: _DiscoveredWriteCandidate,
    registered: dict[str, tuple[MemoryWriterSpec, ...]],
) -> tuple[str, ...]:
    specs = registered.get(candidate.source_path, ())
    matches: list[str] = []
    for spec in specs:
        if _symbol_matches(candidate.symbol, spec.symbol):
            matches.append(spec.writer_id)
    return tuple(matches)


def _triage_discovered_write(
    candidate: _DiscoveredWriteCandidate,
    *,
    status: DiscoveredWriteStatus,
) -> tuple[DiscoveryTriageCategory, str]:
    source = candidate.source_path.lower()
    symbol = candidate.symbol.lower()
    target = candidate.target.lower()
    if status == DiscoveredWriteStatus.REGISTERED:
        return (
            DiscoveryTriageCategory.REGISTERED_MEMORY_WRITER,
            "matched an explicit MemoryWriterSpec",
        )
    if _is_test_or_experiment_source(source):
        return (
            DiscoveryTriageCategory.TEST_OR_EXPERIMENT,
            "test, smoke, experiment, or one-off validation surface",
        )
    if source.endswith("db_utils.py"):
        return (
            DiscoveryTriageCategory.READ_WRITE_HELPER,
            "shared database helper; classify callers rather than this helper alone",
        )
    if _is_generated_artifact_source(source, target):
        return (
            DiscoveryTriageCategory.GENERATED_ARTIFACT,
            "writes generated reports, manifests, handoffs, or derived files",
        )
    if _is_operational_state_source(source, symbol, target):
        return (
            DiscoveryTriageCategory.OPERATIONAL_STATE,
            "writes operational runtime/control state rather than semantic memory",
        )
    if _is_known_memory_writer_cluster(source, symbol, target):
        return (
            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
            "known memory/projection/witness writer cluster needs explicit writer spec",
        )
    if candidate.operation == "sqlite_connect":
        return (
            DiscoveryTriageCategory.SURFACE_NEEDS_REGISTRY,
            "SQLite write path needs surface classification or explicit exclusion",
        )
    if "witness" in target or "witness" in symbol or "jsonl" in target:
        return (
            DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC,
            "append-style evidence/witness path needs explicit writer spec",
        )
    return (
        DiscoveryTriageCategory.OPERATIONAL_STATE,
        "file write looks operational/generated; review before excluding",
    )


def _is_test_or_experiment_source(source: str) -> bool:
    filename = source.rsplit("/", 1)[-1]
    return (
        source.startswith("tests/")
        or "/tests/" in source
        or source.startswith("scripts/experiments/")
        or "test" in filename
        or "smoke" in filename
        or "probe" in filename
        or "experiment" in filename
    )


def _is_generated_artifact_source(source: str, target: str) -> bool:
    generated_markers = (
        "artifact",
        "audit",
        "distill",
        "handoff",
        "authority_map",
        "gap_map",
        "manifest",
        "morning",
        "report",
        "review",
        "risk_map",
        "snapshot",
        "synthesis",
        "xray",
    )
    generated_sources = (
        "codex_overnight.py",
        "conversation_distiller.py",
        "dual_audit.py",
        "artifact_manifest.py",
        "immune_mission_xray.py",
        "knowledge_ops/cli.py",
        "merge_snapshot.py",
        "organism_council.py",
        "offline_training_bridge.py",
        "allout_autopilot.py",
        "scout_audit.py",
        "strange_loop.py",
    )
    return source.endswith(generated_sources) or any(marker in target for marker in generated_markers)


def _is_operational_state_source(source: str, symbol: str, target: str) -> bool:
    operational_sources = (
        "active_inference.py",
        "custodians.py",
        "economic_spine.py",
        "thread_manager.py",
        "tui/",
        "tui_legacy.py",
        "zeitgeist.py",
        "cron",
        "terminal",
    )
    operational_markers = (
        "focus_file",
        "pid",
        "state_file",
        "trust_mode",
        "launchd",
        "prediction_error",
    )
    return any(part in source for part in operational_sources) or any(
        marker in target or marker in symbol for marker in operational_markers
    )


def _is_known_memory_writer_cluster(source: str, symbol: str, target: str) -> bool:
    writer_sources = (
        "agent_memory_manager.py",
        "algedonic_bridge.py",
        "bhed_gnan_monitor.py",
        "contracts/intelligence_adapters.py",
        "engine/conversation_memory.py",
        "engine/event_memory.py",
        "engine/retrieval_feedback.py",
        "engine/unified_index.py",
        "memory.py",
        "organism_memory.py",
        "runtime_state.py",
        "semantic_memory_bridge.py",
        "swarm.py",
        "telemetry_plane.py",
        "telos_gates.py",
        "vector_store.py",
    )
    writer_markers = (
        "memory",
        "retrieval",
        "runtime_state",
        "semantic",
        "telemetry",
        "vector",
        "witness",
    )
    return source.endswith(writer_sources) or any(
        marker in source or marker in symbol or marker in target for marker in writer_markers
    )


def _symbol_matches(candidate_symbol: str, registered_symbol: str) -> bool:
    if candidate_symbol == registered_symbol:
        return True
    return candidate_symbol.startswith(f"{registered_symbol}.")


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _skip_scan_path(path: Path) -> bool:
    skip_parts = {".git", ".venv", "__pycache__", "node_modules", "site-packages"}
    return any(part in skip_parts for part in path.parts)
