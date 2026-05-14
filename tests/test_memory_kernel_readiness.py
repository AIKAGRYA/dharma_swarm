from __future__ import annotations

import json
import sqlite3
from pathlib import Path

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
from scripts.memory_kernel_readiness import main as readiness_cli_main


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


def test_readiness_report_is_deterministic_and_warns_on_degraded_reads(
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
    assert report_one["status"] == "degraded"
    assert "home.memory_plane:immutable_probe_may_ignore_live_wal" in report_one["warnings"]
    assert "home.witness:jsonl_trailing_partial_line_skipped" in report_one["warnings"]


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
    assert payload["status"] == "degraded"

    assert (
        readiness_cli_main(
            [
                "--repo-root",
                str(repo),
                "--home",
                str(home),
                "--require-surface",
                "home.memory_plane",
                "--strict",
                "--dry-run",
            ]
        )
        == 5
    )


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


def test_jsonl_adapter_skips_trailing_partial_line_and_reports_metadata(
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
    assert len(metadata) == 1
    assert "jsonl_trailing_partial_line_skipped" in metadata[0].metadata["read_warnings"]


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
