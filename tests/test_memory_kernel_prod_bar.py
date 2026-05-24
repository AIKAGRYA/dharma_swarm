from __future__ import annotations

from pathlib import Path

from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    CensusConfig,
    MemoryAtom,
    MemoryAtomType,
    MemoryContextBudget,
    MemoryLane,
    MemoryQuery,
    MemorySurfaceCensus,
    MigrationStatus,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    TruthState,
    WriteMode,
    WriterClassification,
    default_surface_specs,
    default_writer_specs,
    preview_memory_pack,
)


def _specs_by_id():
    return {surface.surface_id: surface for surface in default_surface_specs()}


def test_memory_lattice_and_palace_are_subordinate_to_kernel_registry() -> None:
    specs = _specs_by_id()

    memory_plane = specs["home.memory_plane"]
    runtime_state = specs["home.runtime_state"]
    vectors = specs["home.vectors"]
    lancedb = specs["home.lancedb"]

    assert "memory_lattice.py" in memory_plane.known_writers
    assert "memory_lattice.py" in memory_plane.known_readers
    assert "memory_palace.py" in memory_plane.known_readers
    assert memory_plane.category is SurfaceCategory.RAW_EVIDENCE
    assert memory_plane.authority_level is AuthorityLevel.MEDIUM
    assert "raw_events" in memory_plane.source_of_truth_for

    assert runtime_state.category is SurfaceCategory.RUNTIME_CONTROL
    assert runtime_state.authority_level is AuthorityLevel.HIGH
    assert "context_bundles" in runtime_state.source_of_truth_for

    for projection in (vectors, lancedb):
        assert projection.category is SurfaceCategory.PROJECTION
        assert projection.authority_level is AuthorityLevel.NONE
        assert projection.write_mode is WriteMode.PROJECTION_WRITE
        assert projection.adapter_mode is AdapterMode.METADATA_ONLY
        assert projection.migration_status is MigrationStatus.DO_NOT_MIGRATE
        assert projection.canon_risk is RiskLevel.CRITICAL
        assert projection.source_of_truth_for == ()
        assert projection.do_not_migrate_reason

    palace_surfaces = [
        surface
        for surface in specs.values()
        if surface.owner_module == "dharma_swarm.memory_palace"
    ]
    assert palace_surfaces
    assert all(
        surface.authority_level is AuthorityLevel.NONE for surface in palace_surfaces
    )
    assert all(surface.category is SurfaceCategory.PROJECTION for surface in palace_surfaces)


def test_memory_lattice_writers_are_reviewed_not_canonical_authority() -> None:
    writers = {writer.writer_id: writer for writer in default_writer_specs()}

    record_fact = writers["memory_lattice.record_fact"]
    remember = writers["memory_lattice.remember"]
    ingest_envelope = writers["memory_lattice.ingest_runtime_envelope"]

    assert record_fact.classification is WriterClassification.REVIEW_REQUIRED
    assert record_fact.risk is RiskLevel.HIGH
    assert record_fact.writes_to == ("home.runtime_state",)
    assert "non-canonical" in record_fact.notes

    assert remember.classification is WriterClassification.REVIEW_REQUIRED
    assert remember.risk is RiskLevel.HIGH
    assert "home.vectors" in remember.writes_to

    assert ingest_envelope.classification is WriterClassification.REVIEW_REQUIRED
    assert ingest_envelope.writes_to == ("home.runtime_state",)


def test_projection_atoms_are_blocked_from_default_context_even_when_relevant(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    projection_path = home / ".dharma/lancedb/palace_docs.lance"
    projection_path.mkdir(parents=True)

    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=repo, home=home, include_discovered=False)
        ).run()
    }
    lancedb = surfaces["home.lancedb"]

    atom = MemoryAtom.build(
        surface=lancedb,
        atom_type=MemoryAtomType.METADATA,
        content_ref="palace-projection-row",
        adapter_name="test_projection_adapter",
        read_mode=ReadMode.METADATA_ONLY,
        content="Projected palace hit: Memory Kernel should be the canonical front door.",
        memory_lane=MemoryLane.PROJECTION,
        context_admissible=True,
    )

    assert atom.is_projection
    assert atom.truth_state is TruthState.DERIVED
    assert MemoryQuery.canary_context(include_content=True).allows_atom(atom) is False

    pack = preview_memory_pack(
        [atom],
        budget=MemoryContextBudget(
            include_content=True,
            require_context_admissible=True,
        ),
    )

    assert pack.admitted_count == 0
    assert pack.items[0].surface_category is SurfaceCategory.PROJECTION
    assert pack.items[0].authority_level is AuthorityLevel.NONE
    assert "truth_state_not_allowed" in pack.items[0].omission_reasons
    assert "projection_blocked" in pack.items[0].omission_reasons
    assert "high_risk_blocked" in pack.items[0].omission_reasons


def test_chetana_surfaces_define_metabolism_not_unreviewed_canon() -> None:
    specs = _specs_by_id()

    staging = specs["home.knowledge_staging"]
    wiki = specs["home.knowledge_wiki"]
    quarantine = specs["home.knowledge_quarantine"]

    assert staging.authority_level is AuthorityLevel.LOW
    assert staging.canon_risk is RiskLevel.HIGH
    assert "must not be treated as canon" in staging.do_not_migrate_reason

    assert wiki.authority_level is AuthorityLevel.MEDIUM
    assert wiki.feeds == ("curated_knowledge_atoms",)
    assert wiki.source_of_truth_for == ()

    assert quarantine.authority_level is AuthorityLevel.NONE
    assert quarantine.migration_status is MigrationStatus.DO_NOT_MIGRATE
    assert quarantine.canon_risk is RiskLevel.CRITICAL
