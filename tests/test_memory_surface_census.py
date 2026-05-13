from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.memory_kernel import AdapterMode, CensusConfig, MemorySurfaceCensus
from dharma_swarm.memory_kernel.surfaces import default_surface_specs
from scripts.memory_surface_census import main as census_cli_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sqlite_db(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def test_census_classifies_known_surfaces_and_counts_opt_in_tables(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(
        home / ".dharma/db/memory_plane.db",
        [
            "CREATE TABLE event_log(id INTEGER PRIMARY KEY, payload TEXT)",
            "CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY, payload TEXT)",
            "INSERT INTO event_log(payload) VALUES ('a')",
            "INSERT INTO event_log(payload) VALUES ('b')",
            "INSERT INTO conversation_turns(payload) VALUES ('c')",
        ],
    )
    _sqlite_db(
        home / ".smriti/smriti.db",
        [
            "CREATE TABLE memories(id INTEGER PRIMARY KEY, text TEXT)",
            "CREATE TABLE entities(id INTEGER PRIMARY KEY, name TEXT)",
            "CREATE TABLE relations(id INTEGER PRIMARY KEY, name TEXT)",
            "INSERT INTO memories(text) VALUES ('remembered')",
        ],
    )
    _write(home / ".dharma/conversation_log/2026-05-11.jsonl", '{"a": 1}\n')
    _write(home / ".dharma/lancedb/palace_docs.lance/manifest.json", "{}\n")

    census = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=False,
            probe_sqlite_counts=True,
        )
    )

    surfaces = {surface.surface_id: surface for surface in census.run()}

    memory_plane = surfaces["home.memory_plane"]
    assert memory_plane.health.record_count == 3
    assert memory_plane.health.schema["table_counts"] == {
        "event_log": 2,
        "conversation_turns": 1,
    }
    assert memory_plane.feeds == (
        "episodes",
        "source_chunks",
        "retrieval_feedback",
        "idea_shards",
    )

    smriti = surfaces["home.smriti"]
    assert smriti.authority_level.value == "low"
    assert smriti.health.record_count == 1
    assert smriti.canon_risk.value == "high"

    conversation_log = surfaces["home.conversation_log"]
    assert conversation_log.adapter_mode is AdapterMode.STREAMING
    assert conversation_log.health.path_type == "directory"

    json.dumps([surface.to_json() for surface in surfaces.values()])


def test_census_discovers_bounded_sqlite_and_jsonl_surfaces(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(
        repo / ".dharma/custom/unknown.sqlite",
        ["CREATE TABLE observations(id INTEGER PRIMARY KEY, body TEXT)"],
    )
    _write(repo / ".dharma/custom/logs/events.jsonl", '{"event": "x"}\n')

    surfaces = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=True,
            max_discovered=10,
        )
    ).run()
    surface_map = {surface.surface_id: surface for surface in surfaces}

    sqlite_surface = surface_map["discovered.repo.dharma.custom.unknown.sqlite"]
    jsonl_surface = surface_map["discovered.repo.dharma.custom.logs"]
    assert sqlite_surface.category.value == "repo_local"
    assert sqlite_surface.active_status.value == "snapshot"
    assert sqlite_surface.adapter_mode.value == "metadata_only"
    assert sqlite_surface.feeds == ("snapshot_metadata",)
    assert sqlite_surface.migration_status.value == "do_not_migrate"
    assert jsonl_surface.category.value == "repo_local"
    assert jsonl_surface.active_status.value == "snapshot"
    assert jsonl_surface.adapter_mode.value == "metadata_only"
    assert jsonl_surface.feeds == ("snapshot_metadata",)


def test_directory_probe_is_bounded_for_large_projection_roots(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    for index in range(5):
        _write(home / f".dharma/lancedb/palace_docs.lance/chunk-{index}.bin", "x")

    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(
                repo_root=repo,
                home=home,
                include_discovered=False,
                max_dir_entries=2,
                max_dir_depth=1,
            )
        ).run()
    }

    lancedb = surfaces["home.lancedb"]
    assert lancedb.adapter_mode is AdapterMode.METADATA_ONLY
    assert lancedb.health.probe_truncated is True
    assert lancedb.migration_status.value == "do_not_migrate"


def test_census_writes_machine_and_markdown_reports(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _write(home / ".codex/memories/mcp-memory.jsonl", '{"memory": "x"}\n')
    output_json = tmp_path / "reports/census.json"
    output_md = tmp_path / "reports/census.md"

    census = MemorySurfaceCensus(
        CensusConfig(repo_root=repo, home=home, include_discovered=False)
    )
    surfaces = census.run()
    census.write_json(output_json, surfaces)
    census.write_markdown(output_md, surfaces)

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")

    assert payload["summary"]["surface_count"] == len(surfaces)
    assert "home.codex_memory" in markdown
    assert "This is a read-only MemoryKernel M0 census" in markdown


def test_sqlite_probe_does_not_create_wal_or_shm_sidecars(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    db_path = home / ".dharma/db/memory_plane.db"
    _sqlite_db(
        db_path,
        [
            "PRAGMA journal_mode=WAL",
            "CREATE TABLE event_log(id INTEGER PRIMARY KEY, payload TEXT)",
            "INSERT INTO event_log(payload) VALUES ('a')",
        ],
    )
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")
    wal_path.unlink(missing_ok=True)
    shm_path.unlink(missing_ok=True)

    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(
                repo_root=repo,
                home=home,
                include_discovered=False,
                probe_sqlite_counts=True,
            )
        ).run()
    }

    assert surfaces["home.memory_plane"].health.probe_error is None
    assert not wal_path.exists()
    assert not shm_path.exists()


def test_existing_wal_sidecar_adds_immutable_snapshot_note(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    db_path = home / ".dharma/db/memory_plane.db"
    _sqlite_db(
        db_path,
        [
            "CREATE TABLE event_log(id INTEGER PRIMARY KEY, payload TEXT)",
            "INSERT INTO event_log(payload) VALUES ('a')",
        ],
    )
    Path(str(db_path) + "-wal").write_bytes(b"")

    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=repo, home=home, include_discovered=False)
        ).run()
    }

    assert "immutable_probe_may_ignore_live_wal" in surfaces["home.memory_plane"].health.notes


def test_missing_literal_tilde_surface_remains_unsafe_not_missing(tmp_path: Path) -> None:
    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(
            CensusConfig(repo_root=tmp_path / "repo", home=tmp_path / "home")
        ).run()
    }

    literal_tilde = surfaces["repo.literal_tilde_dharma"]
    assert literal_tilde.health.exists is False
    assert literal_tilde.active_status.value == "unsafe"
    assert literal_tilde.category.value == "unsafe"


def test_discovery_honors_depth_and_entry_caps(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(repo / ".dharma/a.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(repo / ".dharma/b.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _write(repo / ".dharma/deep/level/events.jsonl", '{"event": "too-deep"}\n')

    surfaces = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=True,
            max_discovered=10,
            max_discovery_entries=1,
            max_dir_depth=1,
        )
    ).run()
    discovered_ids = {
        surface.surface_id for surface in surfaces if surface.surface_id.startswith("discovered.")
    }

    assert discovered_ids == {"discovered.repo.dharma.a.sqlite"}
    assert "discovered.repo.dharma.deep.level" not in discovered_ids


def test_discovery_truncation_is_reported_when_cap_saturates(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(home / ".dharma/a.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(home / ".dharma/b.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(home / ".smriti/smriti.db", ["CREATE TABLE memories(id INTEGER)"])
    _write(home / ".codex/memories/mcp-memory.jsonl", '{"memory": "x"}\n')
    _sqlite_db(repo / ".dharma/repo.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(repo / ".swarm/memory.db", ["CREATE TABLE observations(id INTEGER)"])

    census = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=True,
            max_discovered=1,
            max_discovery_entries=100,
        )
    )
    surfaces = census.run()
    summary = census.summarize_surface_health(surfaces)

    assert summary["discovered_count"] == 1
    assert summary["discovery_truncated"] is True
    assert summary["discovery_entries_visited"] >= 1
    assert str(home / ".dharma") in summary["discovery_roots_scanned"]
    assert summary["discovery_root_status"][str(home / ".dharma")] == "truncated_inside_root"
    assert summary["discovery_root_status"][str(home / ".smriti")] == "truncated_before_scan"
    assert summary["discovery_root_status"][str(repo / ".dharma")] == "truncated_before_scan"
    assert str(repo / ".swarm") in summary["discovery_roots_unscanned_due_to_truncation"]


def test_markdown_report_includes_discovery_truncation_warning(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(home / ".dharma/a.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(home / ".dharma/b.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    census = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=True,
            max_discovered=1,
        )
    )
    surfaces = census.run()
    output_md = tmp_path / "reports/census.md"

    census.write_markdown(output_md, surfaces)
    markdown = output_md.read_text(encoding="utf-8")

    assert "## Discovery" in markdown
    assert "Discovery incomplete: cap reached." in markdown
    assert "Discovered surfaces" in markdown
    assert str(home / ".smriti") in markdown


def test_external_surface_summary_does_not_reuse_stale_discovery_stats(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(home / ".dharma/a.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    _sqlite_db(home / ".dharma/b.sqlite", ["CREATE TABLE observations(id INTEGER)"])
    census = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            include_discovered=True,
            max_discovered=1,
        )
    )
    census.run()

    summary = census.summarize_surface_health(tuple())

    assert summary["surface_count"] == 0
    assert summary["discovery_truncated"] is False
    assert summary["discovery_stats_source"] == "external_surfaces"


def test_cli_default_does_not_enable_discovery(tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(repo / ".dharma/custom/unknown.sqlite", ["CREATE TABLE observations(id INTEGER)"])

    assert census_cli_main(["--repo-root", str(repo), "--home", str(home), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)

    assert summary["surface_count"] == len(default_surface_specs())


def test_census_config_accepts_string_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"

    census = MemorySurfaceCensus(CensusConfig(repo_root=str(repo), home=str(home)))

    assert census.run()


def test_report_output_inside_memory_roots_is_rejected(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    census = MemorySurfaceCensus(CensusConfig(repo_root=repo, home=home))
    surfaces = census.run()

    with pytest.raises(ValueError, match="Refusing to write census output"):
        census.write_json(home / ".dharma/reports/census.json", surfaces)

    with pytest.raises(ValueError, match="Refusing to write census output"):
        census.write_markdown(repo / ".swarm/reports/census.md", surfaces)


def test_report_output_override_allows_memory_root_when_explicit(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    output_path = repo / ".dharma/reports/census.json"
    census = MemorySurfaceCensus(
        CensusConfig(
            repo_root=repo,
            home=home,
            allow_memory_surface_output=True,
        )
    )

    census.write_json(output_path, census.run())

    assert output_path.exists()


def test_probe_errors_are_recorded_without_crashing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _write(home / ".dharma/db/memory_plane.db", "not sqlite")

    surfaces = {
        surface.surface_id: surface
        for surface in MemorySurfaceCensus(CensusConfig(repo_root=repo, home=home)).run()
    }

    memory_plane = surfaces["home.memory_plane"]
    assert memory_plane.health.exists is True
    assert memory_plane.health.probe_error


def test_known_audit_surfaces_are_explicitly_registered() -> None:
    surface_ids = {spec.surface_id for spec in default_surface_specs()}

    assert {
        "home.traces",
        "home.evolution",
        "home.conversations",
        "home.state_knowledge",
        "home.dharma_graphs",
        "home.quality_gates",
        "home.evals",
        "home.cost_log",
        "home.costs",
        "home.artifacts",
        "home.terminal_tui",
        "home.bridges",
        "home.ecosystem_index",
        "home.hibernation",
        "home.algedonic_signals",
        "home.semantic_concept_graph",
        "home.meta_concept_graph",
        "home.distilled",
        "home.shared",
        "home.citations",
        "home.subconscious",
        "home.campaigns",
        "home.workspace",
        "home.active_inference",
        "home.gaia_ledger",
        "home.gaia_platform",
        "home.organism_memory",
        "home.control",
        "home.cron",
        "home.alerts",
        "home.custodians",
        "home.jikoku",
        "home.terminal_supervisor",
    } <= surface_ids
