from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    CensusConfig,
    MemoryAtomType,
    MemoryKernel,
    MemoryKernelConfig,
    MemoryQuery,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    MigrationStatus,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    WriteMode,
    default_surface_specs,
)
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig
from dharma_swarm.memory_kernel.adapters.generic import GenericSurfaceMetadataAdapter
from dharma_swarm.memory_kernel.facade import default_adapter_factories


def test_default_factories_cover_all_adapter_expected_surface_specs(
    tmp_path: Path,
) -> None:
    expected_surface_ids = {
        spec.surface_id
        for spec in default_surface_specs()
        if spec.adapter_mode
        in {AdapterMode.READ_ONLY, AdapterMode.STREAMING, AdapterMode.METADATA_ONLY}
    }
    factories = default_adapter_factories(ReadOnlyAdapterConfig(default_limit=1))

    assert expected_surface_ids <= set(factories)

    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(
                repo_root=tmp_path / "repo",
                home=tmp_path / "home",
                include_discovered=False,
            ),
            adapter=ReadOnlyAdapterConfig(default_limit=1),
        )
    )
    summary = kernel.adapter_readiness_report().to_json()["summary"]

    assert summary["required_surface_count"] == 7
    assert summary["adapter_registered_count"] == len(expected_surface_ids)
    assert summary["missing_adapter_count"] == 0
    assert summary.get("optional_missing_adapter_count", 0) == 0
    assert summary.get("total_missing_adapter_count", 0) == 0


def test_generic_adapter_emits_metadata_without_ingesting_content(
    tmp_path: Path,
) -> None:
    surface_dir = tmp_path / "active_inference"
    surface_dir.mkdir()
    (surface_dir / "secret-token-notes.jsonl").write_text(
        '{"content": "do not ingest"}\n',
        encoding="utf-8",
    )
    surface = _surface(
        surface_id="home.active_inference",
        path=surface_dir,
        adapter_mode=AdapterMode.METADATA_ONLY,
        category=SurfaceCategory.KNOWLEDGE_METABOLISM,
        role=MemorySurfaceRole.RUNTIME_STATE,
        canon_risk=RiskLevel.HIGH,
        pii_risk=RiskLevel.HIGH,
    )
    adapter = GenericSurfaceMetadataAdapter(
        surface,
        config=ReadOnlyAdapterConfig(default_limit=5, max_metadata_chars=4000),
    )

    atoms = list(
        adapter.iter_atoms(
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=5,
                include_content=True,
                include_metadata_payloads=True,
            )
        )
    )

    assert len(atoms) == 1
    assert atoms[0].atom_type is MemoryAtomType.METADATA
    assert atoms[0].content is None
    assert atoms[0].metadata["content_ingestion"] == "suppressed"
    assert atoms[0].metadata["metadata_policy"] == "surface_health_only_no_content_ingestion"
    assert atoms[0].metadata["risk_policy"] == "high_risk_metadata_only"
    assert "secret-token-notes" not in json.dumps(atoms[0].to_json(), sort_keys=True)
    assert "do not ingest" not in json.dumps(atoms[0].to_json(), sort_keys=True)


def test_generic_adapter_suppresses_unsafe_surface_atoms(tmp_path: Path) -> None:
    unsafe_dir = tmp_path / "unsafe"
    unsafe_dir.mkdir()
    surface = _surface(
        surface_id="repo.literal_tilde_dharma",
        path=unsafe_dir,
        adapter_mode=AdapterMode.METADATA_ONLY,
        category=SurfaceCategory.UNSAFE,
        role=MemorySurfaceRole.UNSAFE_FIXTURE,
        active_status=SurfaceStatus.UNSAFE,
        canon_risk=RiskLevel.CRITICAL,
        pii_risk=RiskLevel.CRITICAL,
    )
    adapter = GenericSurfaceMetadataAdapter(
        surface,
        config=ReadOnlyAdapterConfig(default_limit=5),
    )

    atoms = list(
        adapter.iter_atoms(
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=5,
                include_unsafe=True,
            )
        )
    )

    assert atoms == []


def _surface(
    *,
    surface_id: str,
    path: Path,
    adapter_mode: AdapterMode,
    category: SurfaceCategory,
    role: MemorySurfaceRole,
    active_status: SurfaceStatus = SurfaceStatus.ACTIVE,
    canon_risk: RiskLevel = RiskLevel.MEDIUM,
    pii_risk: RiskLevel = RiskLevel.MEDIUM,
) -> MemorySurface:
    return MemorySurface(
        surface_id=surface_id,
        path=str(path),
        owner_module="tests",
        role=role,
        category=category,
        authority_level=AuthorityLevel.LOW,
        write_mode=WriteMode.READ_ONLY,
        adapter_mode=adapter_mode,
        active_status=active_status,
        health=MemorySurfaceHealth(
            exists=True,
            path_type="directory",
            size_bytes=0,
            last_modified="2026-05-14T00:00:00+00:00",
        ),
        provenance_quality="synthetic",
        canon_risk=canon_risk,
        pii_secrets_risk=pii_risk,
        migration_status=MigrationStatus.ADAPTER_NEEDED,
    )
