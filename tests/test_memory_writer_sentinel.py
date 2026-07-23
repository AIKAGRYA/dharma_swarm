from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.memory_kernel import (
    DiscoveredWriteStatus,
    DiscoveryTriageCategory,
    MemoryWriterSentinel,
    MemoryWriterSpec,
    RiskLevel,
    WriteMode,
    WriterClassification,
    WriterStatus,
    default_writer_specs,
)
from scripts.memory_writer_sentinel import main as writer_sentinel_cli_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_default_writer_sentinel_finds_known_writer_symbols() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    observations = MemoryWriterSentinel(repo_root=repo_root).run()
    by_id = {observation.spec.writer_id: observation for observation in observations}

    assert by_id["memory_lattice.record_fact"].present is True
    assert by_id["conversation_memory.record_turn"].present is True
    assert by_id["retrieval_feedback.log_hits"].present is True
    assert by_id["providers.routing_audit"].status is WriterStatus.PRESENT
    assert by_id["providers.route_retrospective"].status is WriterStatus.PRESENT
    assert by_id["routing_memory.store"].status is WriterStatus.PRESENT
    assert {spec.writer_id for spec in default_writer_specs()} <= set(by_id)


def test_writer_sentinel_flags_unregistered_surfaces(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg/mod.py",
        "class Writer:\n    def write(self):\n        return None\n",
    )
    spec = MemoryWriterSpec(
        "fake.writer",
        "pkg.mod",
        "Writer.write",
        ("home.unknown_surface",),
        WriteMode.READ_WRITE,
        WriterClassification.REVIEW_REQUIRED,
        RiskLevel.HIGH,
    )

    observations = MemoryWriterSentinel(
        repo_root=tmp_path,
        specs=(spec,),
        known_surface_ids=("home.memory_plane",),
    ).run()

    assert observations[0].present is True
    assert observations[0].status is WriterStatus.UNREGISTERED_SURFACE
    assert observations[0].unregistered_surfaces == ("home.unknown_surface",)


def test_writer_sentinel_detects_missing_symbols(tmp_path: Path) -> None:
    _write(tmp_path / "pkg/mod.py", "class Writer:\n    pass\n")
    spec = MemoryWriterSpec(
        "fake.missing",
        "pkg.mod",
        "Writer.write",
        ("home.memory_plane",),
        WriteMode.READ_WRITE,
        WriterClassification.REVIEW_REQUIRED,
        RiskLevel.HIGH,
    )

    observations = MemoryWriterSentinel(
        repo_root=tmp_path,
        specs=(spec,),
        known_surface_ids=("home.memory_plane",),
    ).run()

    assert observations[0].present is False
    assert observations[0].status is WriterStatus.MISSING


def test_writer_discovery_marks_registered_and_unregistered_write_calls(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg/mod.py",
        "\n".join(
            [
                "import sqlite3",
                "from pathlib import Path",
                "",
                "class Writer:",
                "    def __init__(self):",
                "        self.db_path = Path.home() / '.dharma' / 'state' / 'runtime.db'",
                "",
                "    def write(self):",
                "        db = sqlite3.connect(str(self.db_path))",
                "        db.execute('INSERT INTO memory_facts(text) VALUES (?)', ('x',))",
                "",
                "def helper():",
                "    path = Path.home() / '.dharma' / 'witness' / 'x.jsonl'",
                "    with path.open('a', encoding='utf-8') as handle:",
                "        handle.write('{}\\n')",
            ]
        ),
    )
    spec = MemoryWriterSpec(
        "fake.writer",
        "pkg.mod",
        "Writer.write",
        ("home.memory_plane",),
        WriteMode.READ_WRITE,
        WriterClassification.REVIEW_REQUIRED,
        RiskLevel.HIGH,
    )

    sentinel = MemoryWriterSentinel(
        repo_root=tmp_path,
        specs=(spec,),
        known_surface_ids=("home.memory_plane",),
    )
    discoveries = sentinel.discover_write_paths(scan_roots=("pkg",))
    by_symbol = {discovery.symbol: discovery for discovery in discoveries}

    assert by_symbol["Writer.write"].status is DiscoveredWriteStatus.REGISTERED
    assert by_symbol["Writer.write"].triage_category is DiscoveryTriageCategory.REGISTERED_MEMORY_WRITER
    assert by_symbol["Writer.write"].matched_writer_ids == ("fake.writer",)
    assert by_symbol["helper"].status is DiscoveredWriteStatus.UNREGISTERED
    assert by_symbol["helper"].triage_category is DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC
    assert by_symbol["helper"].operation == "path_open_write"


def test_writer_discovery_triages_tests_and_helpers(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts/test_probe.py",
        "\n".join(
            [
                "from pathlib import Path",
                "def main():",
                "    out = Path.home() / '.dharma' / 'probe.jsonl'",
                "    out.write_text('{}')",
            ]
        ),
    )
    _write(
        tmp_path / "dharma_swarm/db_utils.py",
        "\n".join(
            [
                "import sqlite3",
                "def connect_sync(db_path):",
                "    db = sqlite3.connect(str(db_path))",
                "    db.execute('PRAGMA journal_mode=WAL')",
            ]
        ),
    )

    discoveries = MemoryWriterSentinel(repo_root=tmp_path, specs=()).discover_write_paths()
    by_path = {discovery.source_path: discovery for discovery in discoveries}

    assert by_path["scripts/test_probe.py"].triage_category is DiscoveryTriageCategory.TEST_OR_EXPERIMENT
    assert by_path["dharma_swarm/db_utils.py"].triage_category is DiscoveryTriageCategory.READ_WRITE_HELPER


def test_writer_sentinel_cli_reports_summary(capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert writer_sentinel_cli_main(["--repo-root", str(repo_root)]) == 0
    out = capsys.readouterr().out

    assert '"writer_count"' in out
    assert '"unregistered_surface_count"' in out


@pytest.mark.timeout(60)
def test_writer_sentinel_cli_reports_discovery_summary(capsys) -> None:
    """Same real repo-wide scan cost as the sibling test below (WP-0D)."""
    repo_root = Path(__file__).resolve().parents[1]

    assert writer_sentinel_cli_main(["--repo-root", str(repo_root), "--discover"]) == 0
    out = capsys.readouterr().out

    assert '"discovery_summary"' in out
    assert '"discovered_write_count"' in out
    assert '"by_triage"' in out


@pytest.mark.timeout(60)
def test_writer_sentinel_cli_action_required_gate_passes_for_triaged_repo(capsys) -> None:
    """discover_write_paths scans the whole real repo tree, so cost scales
    with repo size like the QL-R1 quality ratchet does; ~14s call time on
    this checkout already crosses test-fast's blanket 10s budget (WP-0D
    suite-context timeout). A per-test override, not a `slow` marker, since
    both required CI and `make test` filter -m "not slow"."""
    repo_root = Path(__file__).resolve().parents[1]

    assert (
        writer_sentinel_cli_main(
            [
                "--repo-root",
                str(repo_root),
                "--discover",
                "--fail-on-action-required-discovery",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out

    assert '"action_required_count": 0' in out


def test_loop4_10_state_sentinel_write_has_reviewed_baseline() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    discoveries = MemoryWriterSentinel(repo_root=repo_root).discover_write_paths(
        scan_roots=("scripts/loop4_10_memory_context_closure_run.py",),
    )
    sentinel_write = next(
        discovery
        for discovery in discoveries
        if discovery.source_path == "scripts/loop4_10_memory_context_closure_run.py"
        and discovery.symbol == "_prepare_state_dir"
        and "STATE_SENTINEL_CONTENT" in discovery.target
    )

    assert sentinel_write.triage_category is DiscoveryTriageCategory.MEMORY_WRITER_NEEDS_SPEC
    assert sentinel_write.write_decision is not None
    assert sentinel_write.write_decision["reviewed_baseline"] is True
    assert (
        sentinel_write.write_decision["reviewed_baseline_id"]
        == "scripts/loop4_10_memory_context_closure_run.py:_prepare_state_dir:"
        "path_write:fff3e82d4cdf"
    )
    assert sentinel_write.write_decision["decision"] == "warn"


def test_tfidf_embedder_move_keeps_registered_writer_spec() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    observations = MemoryWriterSentinel(repo_root=repo_root).run()
    by_id = {observation.spec.writer_id: observation for observation in observations}
    tfidf_spec = by_id["vector_store.tfidf_state"].spec

    assert tfidf_spec.owner_module == "dharma_swarm.embedders"
    assert by_id["vector_store.tfidf_state"].status is WriterStatus.PRESENT

    discoveries = MemoryWriterSentinel(repo_root=repo_root).discover_write_paths(
        scan_roots=("dharma_swarm/embedders.py",),
    )
    tfidf_write = next(
        discovery
        for discovery in discoveries
        if discovery.symbol == "TFIDFEmbedder._save_state"
        and discovery.operation == "file_open_write"
    )

    assert tfidf_write.status is DiscoveredWriteStatus.REGISTERED
    assert tfidf_write.matched_writer_ids == ("vector_store.tfidf_state",)


def test_writer_sentinel_cli_ci_profile_runs_discovery_and_gates(capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert writer_sentinel_cli_main(["--repo-root", str(repo_root), "--ci"]) == 0
    out = capsys.readouterr().out

    assert '"discovery_summary"' in out
    assert '"action_required_count": 0' in out
    assert '"unregistered_surface_count": 0' in out


def test_writer_sentinel_cli_writes_markdown_report(tmp_path: Path, capsys) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "writer_report.md"

    assert (
        writer_sentinel_cli_main(
            [
                "--repo-root",
                str(repo_root),
                "--discover",
                "--markdown-out",
                str(report_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    report = report_path.read_text(encoding="utf-8")

    assert "# Memory Writer Sentinel Report" in report
    assert "## Static Discovery" in report
    assert "## Gate Guidance" in report
