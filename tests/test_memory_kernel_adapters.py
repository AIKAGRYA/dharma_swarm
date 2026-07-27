from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.memory_kernel import (
    CensusConfig,
    MemoryContextBudget,
    MemoryAtomType,
    MemoryKernel,
    MemoryKernelConfig,
    MemoryOrder,
    MemoryQuery,
    ReadMode,
    TruthState,
)
from dharma_swarm.memory_kernel.adapters import ReadOnlyAdapterConfig

_MANIFEST_KERNEL_SIG = "f" * 64


@pytest.fixture(autouse=True)
def _manifest_kernel(monkeypatch: pytest.MonkeyPatch):
    # PR-08: the wiki adapter only serves manifest-trusted files
    from dharma_swarm.chetana import manifest as manifest_mod

    monkeypatch.setattr(
        manifest_mod, "_resolve_kernel_signature", lambda: _MANIFEST_KERNEL_SIG
    )
    manifest_mod.clear_manifest_cache()
    yield
    manifest_mod.clear_manifest_cache()


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
            "CREATE TABLE event_log(id INTEGER PRIMARY KEY, payload TEXT, timestamp TEXT, secret_token TEXT)",
            "CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY, content TEXT, timestamp TEXT)",
            "CREATE TABLE idea_shards(id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)",
            "CREATE TABLE source_chunks(id INTEGER PRIMARY KEY, chunk_text TEXT, source_path TEXT)",
            "CREATE TABLE retrieval_log(id INTEGER PRIMARY KEY, query TEXT, score REAL)",
            "INSERT INTO event_log(payload, timestamp, secret_token) VALUES ('runtime event', '2026-05-11T01:00:00Z', 'super-secret')",
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn one', '2026-05-11T01:01:00Z')",
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn two', '2026-05-11T01:09:00Z')",
            "INSERT INTO idea_shards(text, created_at) VALUES ('idea shard', '2026-05-11T01:02:00Z')",
            "INSERT INTO source_chunks(chunk_text, source_path) VALUES ('source chunk', 'doc.md')",
            "INSERT INTO retrieval_log(query, score) VALUES ('memory kernel', 0.9)",
        ],
    )
    _sqlite_db(
        home / ".dharma/state/runtime.db",
        [
            "CREATE TABLE session_events(id INTEGER PRIMARY KEY, payload TEXT, timestamp TEXT)",
            "CREATE TABLE memory_facts(id INTEGER PRIMARY KEY, fact TEXT, created_at TEXT)",
            "CREATE TABLE memory_edges(id INTEGER PRIMARY KEY, payload TEXT)",
            "CREATE TABLE context_bundles(id INTEGER PRIMARY KEY, content TEXT)",
            "INSERT INTO session_events(payload, timestamp) VALUES ('session event', '2026-05-11T02:00:00Z')",
            "INSERT INTO memory_facts(fact, created_at) VALUES ('runtime fact', '2026-05-11T02:01:00Z')",
            "INSERT INTO memory_edges(payload) VALUES ('edge')",
            "INSERT INTO context_bundles(content) VALUES ('bundle')",
        ],
    )
    _sqlite_db(
        home / ".smriti/smriti.db",
        [
            "CREATE TABLE memories(id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)",
            "INSERT INTO memories(text, created_at) VALUES ('smriti memory', '2026-05-11T03:00:00Z')",
        ],
    )
    _write(home / ".dharma/witness/2026-05-11.jsonl", '{"event": "witnessed", "timestamp": "2026-05-11T04:00:00Z"}\n')
    _write(home / ".dharma/knowledge/wiki/concept.md", "# Concept\n\nCurated note.\n")
    from dharma_swarm.chetana import manifest as manifest_mod

    wiki_root = home / ".dharma/knowledge/wiki"
    manifest_mod.write_manifest(
        [
            manifest_mod.manifest_entry_for_file(
                wiki_root / "concept.md", root=wiki_root, tier="gold"
            )
        ],
        manifest_file=wiki_root / "MANIFEST.jsonl",
        kernel_signature=_MANIFEST_KERNEL_SIG,
    )
    _write(home / ".codex/memories/mcp-memory.jsonl", '{"text": "codex memory", "timestamp": "2026-05-11T05:00:00Z"}\n')
    _write(home / ".dharma/conversation_log/2026-05-11.jsonl", '{"content": "private long transcript"}\n')
    return home, repo


def test_memory_kernel_lists_read_only_m1_adapters(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    adapter_ids = set(kernel.list_adapter_ids())

    assert {
        "home.memory_plane",
        "home.runtime_state",
        "home.smriti",
        "home.witness",
        "home.knowledge_wiki",
        "home.codex_memory",
        "home.conversation_log",
    } <= adapter_ids


def test_memory_kernel_iterates_normalized_atoms_with_authority_labels(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=(
                "home.memory_plane",
                "home.runtime_state",
                "home.smriti",
                "home.witness",
                "home.knowledge_wiki",
                "home.codex_memory",
                "home.conversation_log",
            ),
            limit_per_surface=10,
        )
    )
    atom_types = {atom.atom_type for atom in atoms}

    assert MemoryAtomType.EPISODE in atom_types
    assert MemoryAtomType.FACT in atom_types
    assert MemoryAtomType.RETRIEVAL_FEEDBACK in atom_types
    assert MemoryAtomType.WITNESS_EVENT in atom_types
    assert MemoryAtomType.KNOWLEDGE_CARD in atom_types
    assert MemoryAtomType.EXTERNAL_MEMORY in atom_types
    assert all(atom.surface_id for atom in atoms)
    assert all(atom.authority_level.value in {"low", "medium", "high", "none"} for atom in atoms)
    assert all(atom.canon_risk.value != "unknown" for atom in atoms)
    assert all(atom.surface_category for atom in atoms)
    assert all(atom.surface_role for atom in atoms)
    assert all(atom.memory_lane for atom in atoms)
    assert all(atom.scope for atom in atoms)
    assert all(atom.truth_state is not TruthState.CANONICAL for atom in atoms)
    assert all(atom.promotion_allowed is False for atom in atoms)
    assert all(atom.context_admissible is False for atom in atoms)
    assert json.dumps([atom.to_json() for atom in atoms])


def test_memory_kernel_facade_methods_filter_atom_types(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    facts = list(kernel.iter_memory_facts(limit_per_surface=10))
    chunks = list(kernel.iter_source_chunks(limit_per_surface=10))
    feedback = list(kernel.iter_retrieval_feedback(limit_per_surface=10))
    witness = list(kernel.iter_witness_events(limit_per_surface=10))
    external = list(kernel.iter_external_memory_atoms(limit_per_surface=10))

    assert {atom.atom_type for atom in facts} <= {MemoryAtomType.FACT, MemoryAtomType.EDGE}
    assert {atom.atom_type for atom in chunks} == {MemoryAtomType.SOURCE_CHUNK}
    assert {atom.atom_type for atom in feedback} == {MemoryAtomType.RETRIEVAL_FEEDBACK}
    assert {atom.atom_type for atom in witness} == {MemoryAtomType.WITNESS_EVENT}
    assert {atom.atom_type for atom in external} == {MemoryAtomType.EXTERNAL_MEMORY}


def test_conversation_log_adapter_is_metadata_only(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.conversation_log",),
            limit_per_surface=5,
        )
    )

    assert len(atoms) == 1
    assert atoms[0].atom_type is MemoryAtomType.METADATA
    assert atoms[0].content is None
    assert atoms[0].read_mode is ReadMode.METADATA_ONLY
    assert atoms[0].metadata["metadata_only"] is True


def test_jsonl_adapters_are_bounded(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    _write(
        home / ".dharma/witness/more.jsonl",
        "".join(json.dumps({"event": f"witness-{index}"}) + "\n" for index in range(5)),
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=2, max_lines_per_file=2),
        )
    )

    atoms = list(kernel.iter_witness_events())

    assert len(atoms) == 2


def test_codex_memory_reads_complete_tail_without_newline(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    _write(
        home / ".codex/memories/mcp-memory.jsonl",
        '{"text": "first", "timestamp": "2026-05-11T05:00:00Z"}\n'
        '{"text": "complete tail", "timestamp": "2026-05-11T05:01:00Z"}',
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                order_by=MemoryOrder.OLDEST,
                include_content=True,
            ),
        )
    )
    metadata = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.METADATA},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert [atom.content for atom in atoms] == ["first", "complete tail"]
    assert metadata == []


def test_jsonl_adapter_skips_live_tail_without_warning(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    _write(
        home / ".codex/memories/mcp-memory.jsonl",
        '{"text": "complete", "timestamp": "2026-05-11T05:00:00Z"}\n{"text": ',
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=MemoryQuery(limit_total=None, limit_per_surface=10, include_content=True),
        )
    )
    metadata = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.METADATA},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert [atom.content for atom in atoms] == ["complete"]
    assert metadata == []


def test_jsonl_adapter_reports_malformed_non_tail_line(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    _write(
        home / ".codex/memories/mcp-memory.jsonl",
        '{"text": "complete"}\n{"text": \n{"text": "after"}\n',
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.codex_memory",),
            atom_types={MemoryAtomType.EXTERNAL_MEMORY},
            query=MemoryQuery(limit_total=None, limit_per_surface=10, include_content=True),
        )
    )

    assert {atom.content for atom in atoms} == {"complete", '{"text":', "after"}
    malformed = next(atom for atom in atoms if atom.content == '{"text":')
    assert malformed.metadata["read_warnings"] == ("jsonl_parse_error",)


def test_memory_query_limits_total_across_surfaces(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            query=MemoryQuery(limit_total=3, limit_per_surface=10),
        )
    )

    assert len(atoms) == 3


def test_sqlite_limit_per_surface_applies_across_tables(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            query=MemoryQuery(limit_total=None, limit_per_surface=2),
        )
    )

    assert len(atoms) == 2


def test_atom_type_filtering_happens_before_surface_cap(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    facts = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.FACT},
            query=MemoryQuery(limit_total=None, limit_per_surface=1, include_content=True),
        )
    )
    chunks = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.SOURCE_CHUNK},
            query=MemoryQuery(limit_total=None, limit_per_surface=1, include_content=True),
        )
    )

    assert len(facts) == 1
    assert facts[0].atom_type is MemoryAtomType.FACT
    assert facts[0].content == "idea shard"
    assert len(chunks) == 1
    assert chunks[0].atom_type is MemoryAtomType.SOURCE_CHUNK
    assert chunks[0].content == "source chunk"


def test_query_suppresses_and_allows_content(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    hidden = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )
    included = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(limit_total=None, limit_per_surface=10, include_content=True),
        )
    )

    assert hidden
    assert all(atom.content is None for atom in hidden)
    assert all(atom.metadata["content_status"] == "omitted_by_query" for atom in hidden)
    assert {atom.content for atom in included} == {"turn one", "turn two"}


def test_metadata_payloads_are_gated_and_redacted(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    hidden = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.RUNTIME_EVENT},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )
    included = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.RUNTIME_EVENT},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                include_content=True,
                include_metadata_payloads=True,
            ),
        )
    )

    hidden_event = next(atom for atom in hidden if atom.metadata["table"] == "event_log")
    included_event = next(atom for atom in included if atom.metadata["table"] == "event_log")

    assert "row" not in hidden_event.metadata
    assert "row" in hidden_event.metadata["redacted_keys"]
    assert included_event.content == "runtime event"
    assert included_event.metadata["row"]["payload"] == "<redacted>"
    assert included_event.metadata["row"]["secret_token"] == "<redacted>"
    assert "super-secret" not in json.dumps(included_event.metadata, default=str)


def test_query_ordering_modes_are_deterministic(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    newest = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                order_by=MemoryOrder.NEWEST,
                include_content=True,
            ),
        )
    )
    oldest = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=10,
                order_by=MemoryOrder.OLDEST,
                include_content=True,
            ),
        )
    )
    stable = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert [atom.content for atom in newest] == ["turn two", "turn one"]
    assert [atom.content for atom in oldest] == ["turn one", "turn two"]
    assert [atom.atom_id for atom in stable] == sorted(atom.atom_id for atom in stable)


def test_query_cursor_returns_atoms_after_cursor(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    with sqlite3.connect(home / ".dharma/db/memory_plane.db") as conn:
        conn.execute(
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn three', '2026-05-11T01:10:00Z')"
        )
        conn.commit()
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    first_page = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=2,
                order_by=MemoryOrder.OLDEST,
                include_content=True,
            ),
        )
    )
    assert first_page
    second_page = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            atom_types={MemoryAtomType.EPISODE},
            query=MemoryQuery(
                limit_total=None,
                limit_per_surface=2,
                order_by=MemoryOrder.OLDEST,
                include_content=True,
                cursor=first_page[-1].atom_id,
            ),
        )
    )

    assert [atom.content for atom in first_page] == ["turn one", "turn two"]
    assert [atom.content for atom in second_page] == ["turn three"]


def test_empty_wal_snapshot_sidecar_does_not_warn(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    _write(home / ".dharma/db/memory_plane.db-wal", "")
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.memory_plane",),
            query=MemoryQuery(limit_total=None, limit_per_surface=1),
        )
    )

    assert atoms
    assert "snapshot_warnings" not in atoms[0].metadata


def test_sqlite_adapter_reads_live_wal_without_snapshot_warning(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    runtime_db = home / ".dharma/state/runtime.db"
    live_conn = sqlite3.connect(runtime_db)
    try:
        live_conn.execute("PRAGMA journal_mode=WAL")
        live_conn.execute("PRAGMA wal_autocheckpoint=0")
        live_conn.execute(
            "INSERT INTO memory_facts(fact, created_at) VALUES ('live wal fact', '2026-05-11T02:02:00Z')"
        )
        live_conn.commit()
        assert runtime_db.with_name(runtime_db.name + "-wal").stat().st_size > 0

        kernel = MemoryKernel(
            MemoryKernelConfig(
                census=CensusConfig(repo_root=repo, home=home),
                adapter=ReadOnlyAdapterConfig(default_limit=10),
            )
        )
        atoms = list(
            kernel.iter_memory_atoms(
                surface_ids=("home.runtime_state",),
                atom_types={MemoryAtomType.FACT},
                query=MemoryQuery(
                    limit_total=None,
                    limit_per_surface=10,
                    include_content=True,
                ),
            )
        )
    finally:
        live_conn.close()

    assert "live wal fact" in {atom.content for atom in atoms}
    live_atom = next(atom for atom in atoms if atom.content == "live wal fact")
    assert live_atom.read_mode is ReadMode.READ_ONLY
    assert "snapshot_warnings" not in live_atom.metadata


def test_sqlite_adapter_reports_live_wal_read_error(tmp_path: Path, monkeypatch) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    runtime_db = home / ".dharma/state/runtime.db"
    _write(runtime_db.with_name(runtime_db.name + "-wal"), "live wal frames")

    def fail_readonly(_path: Path) -> sqlite3.Connection:
        raise sqlite3.OperationalError("wal read blocked")

    monkeypatch.setattr(
        "dharma_swarm.memory_kernel.adapters.read_only._connect_sqlite_readonly",
        fail_readonly,
    )
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    atoms = list(
        kernel.iter_memory_atoms(
            surface_ids=("home.runtime_state",),
            atom_types={MemoryAtomType.METADATA},
            query=MemoryQuery(limit_total=None, limit_per_surface=10),
        )
    )

    assert len(atoms) == 1
    assert atoms[0].metadata["read_warnings"] == (
        "sqlite_probe_error",
        "sqlite_live_wal_read_error",
    )


def test_memory_kernel_preview_memory_pack_is_read_only_and_conservative(tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)
    kernel = MemoryKernel(
        MemoryKernelConfig(
            census=CensusConfig(repo_root=repo, home=home),
            adapter=ReadOnlyAdapterConfig(default_limit=10),
        )
    )

    pack = kernel.preview_memory_pack(
        surface_ids=("home.memory_plane",),
        budget=MemoryContextBudget(max_candidate_atoms=3, max_admitted_atoms=2),
    )

    assert pack.candidate_count == 3
    assert pack.admitted_count == 0
    assert "no_atoms_admitted_by_policy" in pack.warnings
    assert all("atom_not_context_admissible" in item.omission_reasons for item in pack.items)
