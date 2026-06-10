from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from dharma_swarm.memory_kernel import (
    AdapterMode,
    AuthorityLevel,
    CensusConfig,
    MemoryAtom,
    MemoryAtomType,
    MemoryKernel,
    MemoryKernelConfig,
    MemoryQuery,
    MemorySurface,
    MemorySurfaceHealth,
    MemorySurfaceRole,
    ReadMode,
    RiskLevel,
    SurfaceCategory,
    SurfaceStatus,
    WriteMode,
)
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig
from scripts.memory_kernel_readiness import (
    _strict_gate_failed,
    main as readiness_cli_main,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sqlite_db(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def _fixture_memory_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(
        home / ".dharma/db/memory_plane.db",
        [
            "CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY, content TEXT, timestamp TEXT)",
            "CREATE TABLE source_chunks(id INTEGER PRIMARY KEY, chunk_text TEXT, source_path TEXT)",
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn one', '2026-05-11T01:01:00Z')",
            "INSERT INTO source_chunks(chunk_text, source_path) VALUES ('source chunk', 'doc.md')",
        ],
    )
    _sqlite_db(
        home / ".smriti/smriti.db",
        [
            "CREATE TABLE memories(id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)",
            "INSERT INTO memories(text, created_at) VALUES ('smriti memory', '2026-05-11T03:00:00Z')",
        ],
    )
    _write(
        home / ".dharma/witness/2026-05-11.jsonl",
        '{"content": "complete", "timestamp": "2026-05-11T04:00:00Z"}\n{"content": ',
    )
    _write(home / ".dharma/db/memory_plane.db-wal", "")
    return home, repo


def _kernel(home: Path, repo: Path) -> MemoryKernel:
    return MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home, include_discovered=False),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )


def test_readiness_report_tolerates_live_tail_and_empty_wal(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    report_one = kernel.adapter_readiness_report(
        required_surface_ids=("home.memory_plane", "home.witness")
    ).to_json()
    report_two = kernel.adapter_readiness_report(
        required_surface_ids=("home.memory_plane", "home.witness")
    ).to_json()

    assert report_one == report_two
    assert report_one["status"] == "ready"
    assert report_one["warnings"] == ()
    assert report_one["summary"]["required_surface_count"] == 2
    assert report_one["summary"]["required_ready_count"] == 2
    assert report_one["summary"]["required_failure_count"] == 0
    assert report_one["summary"]["degraded_count"] == 0
    assert report_one["summary"]["missing_adapter_count"] == 0
    assert report_one["summary"]["uncovered_count"] == 0


def test_readiness_cli_outputs_stable_json_and_strict_exit(
    capsys,
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)

    assert (
        readiness_cli_main(
            [
                "--repo-root",
                str(repo),
                "--home",
                str(home),
                "--require-surface",
                "home.memory_plane",
                "--require-surface",
                "home.witness",
                "--dry-run",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "memory_kernel_readiness.v1"
    assert payload["summary"]["required_surface_count"] == 2
    assert payload["status"] == "ready"

    _write(
        home / ".dharma/witness/2026-05-11.jsonl",
        '{"content": "complete", "timestamp": "2026-05-11T04:00:00Z"}\n{"content": \n',
    )

    assert (
        readiness_cli_main(
            [
                "--repo-root",
                str(repo),
                "--home",
                str(home),
                "--require-surface",
                "home.witness",
                "--strict",
                "--dry-run",
            ]
        )
        == 5
    )
    capsys.readouterr()

    assert (
        readiness_cli_main(
            [
                "--repo-root",
                str(repo),
                "--home",
                str(home),
                "--require-surface",
                "home.smriti",
                "--summary-only",
                "--dry-run",
            ]
        )
        == 0
    )
    summary_payload = json.loads(capsys.readouterr().out)
    assert "surfaces" not in summary_payload
    assert summary_payload["status"] == "ready"
    assert summary_payload["summary"]["required_ready_count"] == 1
    assert summary_payload["summary"]["degraded_count"] == 0


def test_readiness_cli_defaults_to_memory_home_env(
    capsys,
    tmp_path: Path,
    monkeypatch,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    monkeypatch.setenv("DHARMA_MEMORY_KERNEL_HOME", str(home))

    assert (
        readiness_cli_main(
            [
                "--repo-root",
                str(repo),
                "--require-surface",
                "home.memory_plane",
                "--dry-run",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "ready"
    assert payload["summary"]["required_ready_count"] == 1


def test_strict_cli_gate_requires_m2_warning_free_accounting() -> None:
    summary = {
        "surface_count": 81,
        "accounted_surface_count": 81,
        "required_surface_count": 7,
        "required_ready_count": 7,
        "degraded_count": 0,
        "missing_adapter_count": 0,
        "uncovered_count": 0,
        "total_missing_adapter_count": 0,
        "total_uncovered_count": 0,
        "total_warning_count": 0,
    }
    ready_report = SimpleNamespace(
        status="ready",
        max_ready_tier="m2_strict_read_only_warning_free",
        summary=summary,
    )
    warning_report = SimpleNamespace(
        status="ready",
        max_ready_tier="m1_required_semantic_adapters",
        summary={**summary, "total_warning_count": 1},
    )
    unaccounted_report = SimpleNamespace(
        status="ready",
        max_ready_tier="m1_required_semantic_adapters",
        summary={**summary, "accounted_surface_count": 80},
    )

    assert _strict_gate_failed(ready_report) is False
    assert _strict_gate_failed(warning_report) is True
    assert _strict_gate_failed(unaccounted_report) is True


def test_absent_optional_lifecycle_surfaces_are_accounted_separately(
    tmp_path: Path,
) -> None:
    kernel = _kernel(tmp_path / "home", tmp_path / "repo")

    payload = kernel.adapter_readiness_report().to_json()
    rows = {row["surface_id"]: row for row in payload["surfaces"]}

    expected_statuses = {
        "home.alerts": ("expected_unavailable", "expected_unavailable"),
        "home.custodians": ("expected_unavailable", "expected_unavailable"),
        "home.gaia_ledger": ("expected_unavailable", "expected_unavailable"),
        "home.gaia_platform": ("expected_unavailable", "expected_unavailable"),
        "home.hibernation": ("expected_unavailable", "expected_unavailable"),
        "home.routing_memory": ("retired", "retired"),
        "home.ecosystem_index": ("disabled", "disabled"),
        "home.distilled": ("disabled", "disabled"),
        "home.citations": ("disabled", "disabled"),
        "repo.literal_tilde_dharma": ("unsafe", "unsafe_disabled"),
    }

    for surface_id, (active_status, readiness_status) in expected_statuses.items():
        row = rows[surface_id]
        assert row["active_status"] == active_status
        assert row["status"] == readiness_status
        assert row["warnings"] == ()

    assert payload["summary"]["expected_unavailable_count"] == 5
    assert payload["summary"]["retired_count"] == 1
    assert payload["summary"]["disabled_count"] == 3
    assert payload["summary"]["unsafe_disabled_count"] == 1
    assert payload["summary"]["accounted_optional_absent_count"] >= 5
    assert payload["summary"]["accounted_optional_lifecycle_count"] >= 10


def test_readiness_report_exposes_tiers_without_claiming_full_power(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    payload = kernel.adapter_readiness_report(
        required_surface_ids=("home.memory_plane", "home.witness")
    ).to_json()
    tiers = {tier["tier_id"]: tier for tier in payload["readiness_tiers"]}

    assert payload["max_ready_tier"] == "m1_required_semantic_adapters"
    assert tiers["m0_accounted_read_only"]["status"] == "ready"
    assert tiers["m1_required_semantic_adapters"]["status"] == "ready"
    assert tiers["m2_strict_read_only_warning_free"]["status"] == "blocked"
    assert tiers["m3_safe_context_preview"]["status"] == "blocked"
    assert tiers["m4_governed_write_receipts"]["status"] == "blocked"
    assert tiers["m5_live_promotion_candidate"]["status"] == "blocked"


def test_required_lifecycle_surface_remains_strict(
    tmp_path: Path,
) -> None:
    kernel = _kernel(tmp_path / "home", tmp_path / "repo")

    payload = kernel.adapter_readiness_report(
        required_surface_ids=("home.alerts",)
    ).to_json()
    row = {
        surface["surface_id"]: surface
        for surface in payload["surfaces"]
    }["home.alerts"]

    assert payload["status"] == "unavailable"
    assert row["required"] is True
    assert row["adapter_registered"] is True
    assert row["active_status"] == "expected_unavailable"
    assert row["status"] == "unavailable"
    assert row["warnings"] == ("surface_missing",)


def test_explicit_missing_required_surface_is_uncovered_gate_failure(
    tmp_path: Path,
) -> None:
    kernel = _kernel(tmp_path / "home", tmp_path / "repo")

    payload = kernel.adapter_readiness_report(
        required_surface_ids=("missing.required",)
    ).to_json()

    assert payload["status"] == "unavailable"
    assert payload["summary"]["required_surface_count"] == 1
    assert payload["summary"]["required_ready_count"] == 0
    assert payload["summary"]["required_failure_count"] == 1
    assert payload["summary"]["missing_required_surface_count"] == 1
    assert payload["summary"]["uncovered_count"] == 1
    assert payload["warnings"] == ("missing.required:required_surface_not_found",)


def test_memory_atoms_carry_provenance_extensions_without_content(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.content is None
    assert atom.schema_version == "memory_atom.v2"
    assert atom.source_digest and atom.source_digest.startswith("sha256:")
    assert atom.payload_digest and atom.payload_digest.startswith("sha256:")
    assert atom.source_row_key == "conversation_turns:1"
    assert atom.adapter_version == "read_only.v2"
    assert atom.to_json()["schema_version"] == "memory_atom.v2"


def test_memory_query_filters_high_risk_projection_and_unsafe_atoms(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    high_risk_hidden = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.smriti",),
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                include_high_risk=False,
            ),
        )
    )
    high_risk_explicit = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.smriti",),
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )
    projection_hidden = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.SOURCE_CHUNK},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                include_projections=False,
            ),
        )
    )

    assert high_risk_hidden == []
    assert len(high_risk_explicit) == 1
    assert projection_hidden == []

    unsafe_atom = _unsafe_atom(tmp_path)
    assert not MemoryQuery.canary_context().allows_atom(unsafe_atom)
    assert MemoryQuery(include_unsafe=True).allows_atom(unsafe_atom)


def test_jsonl_adapter_skips_live_tail_without_metadata_warning(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    events = list(
        kernel.iter_witness_events(
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                include_content=True,
            )
        )
    )
    metadata = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.witness",),
            atom_types={MemoryAtomType.METADATA},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert len(events) == 1
    assert events[0].content == "complete"
    assert metadata == []


def test_explicit_missing_surface_returns_stable_degraded_metadata(
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = _kernel(home, repo)

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.METADATA},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                include_degraded_metadata=True,
            ),
        )
    )

    assert len(atoms) == 1
    assert atoms[0].content is None
    assert atoms[0].content_ref == "home.codex_memory:degraded_surface"
    assert atoms[0].metadata["read_warnings"] == ("surface_missing",)


def _unsafe_atom(tmp_path: Path) -> MemoryAtom:
    surface = MemorySurface(
        surface_id="test.unsafe",
        path=str(tmp_path / "unsafe.jsonl"),
        owner_module="tests",
        role=MemorySurfaceRole.UNSAFE_FIXTURE,
        category=SurfaceCategory.UNSAFE,
        authority_level=AuthorityLevel.LOW,
        write_mode=WriteMode.UNKNOWN,
        adapter_mode=AdapterMode.READ_ONLY,
        active_status=SurfaceStatus.UNSAFE,
        health=MemorySurfaceHealth(exists=True, path_type="file"),
        canon_risk=RiskLevel.LOW,
        pii_secrets_risk=RiskLevel.LOW,
    )
    return MemoryAtom.build(
        surface=surface,
        atom_type=MemoryAtomType.EPISODE,
        content_ref="unsafe:1",
        adapter_name="test",
        read_mode=ReadMode.READ_ONLY,
    )
