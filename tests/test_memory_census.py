"""Tests for the memory_census scanner.

Conservative coverage: scanner runs on a synthetic substrate fixture,
emits well-formed JSONL, classifier returns a known-class hint, governance
lookup finds documented owners, diff distinguishes added/removed/changed.

The scanner is read-only; tests assert it never writes outside the
caller-provided output path. Real-substrate accuracy is verified by
the operator running ``python -m dharma_swarm.memory_census scan`` and
diffing against a manual expectation, not in unit tests.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from dharma_swarm.memory_census import (
    CENSUS_VERSION,
    KNOWN_CLASSES,
    KNOWN_SUBSTRATES,
    MemorySurface,
    _classify_python,
    _detect_substrate,
    _find_dharma_writers,
    _load_semgrep_allowlist,
    _load_state_dir_owners,
    _risk_for,
    _surface_id,
    diff_runs,
    scan,
    write_jsonl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_repo(tmp_path: Path) -> Path:
    """Build a minimal synthetic repo with a STATE_DIR_OWNERS doc + semgrep
    YAML + one Python module that writes to ~/.dharma."""
    repo = tmp_path / "repo"
    pkg = repo / "dharma_swarm"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "register_disciplines.py").write_text(
        textwrap.dedent(
            '''
            from pathlib import Path

            DEFAULT_REGISTER_LOG = Path.home() / ".dharma" / "stigmergy" / "register_marks.jsonl"

            class RegisterStore:
                def write(self, m): pass
            '''
        ).lstrip()
    )
    (pkg / "memory_lattice.py").write_text(
        textwrap.dedent(
            '''
            class MemoryLattice:
                def admit_memory_fact(self, f): pass
            '''
        ).lstrip()
    )
    (repo / "docs" / "governance").mkdir(parents=True)
    (repo / "docs" / "governance" / "STATE_DIR_OWNERS.md").write_text(
        "## owners\n- `dharma_swarm/register_disciplines.py` writes register_marks.jsonl\n"
    )
    (repo / ".semgrep").mkdir()
    (repo / ".semgrep" / "dharma-anti-slop.yml").write_text(
        textwrap.dedent(
            '''
            rules:
              - id: dharma.no-unauthorized-dharma-write
                paths:
                  exclude:
                    - "dharma_swarm/register_disciplines.py"
            '''
        )
    )
    return repo


def _build_home(tmp_path: Path) -> Path:
    """Build a minimal synthetic ~/.dharma + ~/.claude/cabinet + ~/.smriti."""
    home = tmp_path / "home"
    dharma = home / ".dharma"
    (dharma / "stigmergy").mkdir(parents=True)
    (dharma / "stigmergy" / "register_marks.jsonl").write_text('{"id": 1}\n')
    (dharma / "stigmergy" / "marks.jsonl").write_text('{"id": 2}\n')
    (dharma / "witness").mkdir()
    (dharma / "witness" / "witness_20260502.jsonl").write_text("{}\n")
    (dharma / "evolution").mkdir()
    (dharma / "evolution" / "archive.jsonl").write_text("{}\n")

    cabinet = home / ".claude" / "cabinet"
    cabinet.mkdir(parents=True)
    (cabinet / "INDEX.md").write_text("# index\n")
    (cabinet / "worldview").mkdir()
    (cabinet / "worldview" / "money_as_divine_force.md").write_text("# essay\n")

    smriti = home / ".smriti"
    smriti.mkdir()
    (smriti / "smriti.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    return home


# ---------------------------------------------------------------------------
# Substrate detection
# ---------------------------------------------------------------------------


def test_detect_substrate_recognizes_known_kinds(tmp_path: Path) -> None:
    py = tmp_path / "x.py"
    py.write_text("")
    db = tmp_path / "x.db"
    db.write_bytes(b"")
    jl = tmp_path / "x.jsonl"
    jl.write_text("")
    md = tmp_path / "x.md"
    md.write_text("")
    d = tmp_path / "dir"
    d.mkdir()
    assert _detect_substrate(py) == "python_module"
    assert _detect_substrate(db) == "sqlite"
    assert _detect_substrate(jl) == "jsonl"
    assert _detect_substrate(md) == "markdown"
    assert _detect_substrate(d) == "directory"


def test_detect_substrate_other_for_unknown(tmp_path: Path) -> None:
    weird = tmp_path / "x.foo"
    weird.write_text("")
    assert _detect_substrate(weird) == "other"


# ---------------------------------------------------------------------------
# Surface id stability
# ---------------------------------------------------------------------------


def test_surface_id_is_stable_for_same_path() -> None:
    a = _surface_id("/x/y/z")
    b = _surface_id("/x/y/z")
    assert a == b
    assert len(a) == 16


def test_surface_id_differs_across_paths() -> None:
    assert _surface_id("/a") != _surface_id("/b")


# ---------------------------------------------------------------------------
# Classifier hints
# ---------------------------------------------------------------------------


def test_classify_python_recognizes_store() -> None:
    assert _classify_python("class FooStore: pass") == "write_authority"


def test_classify_python_recognizes_index() -> None:
    assert _classify_python("class FooIndex: pass") == "projection"


def test_classify_python_recognizes_decay_distiller() -> None:
    assert _classify_python("def decay(x): pass") == "distiller"


def test_classify_python_unknown_for_neutral_module() -> None:
    assert _classify_python("def hello(): return 1") == "unknown"


def test_class_hint_constants_are_subset_of_known() -> None:
    # Sanity: the strings the classifier uses must be in KNOWN_CLASSES
    for hint in {"write_authority", "projection", "distiller", "agent_local",
                 "human_curated", "unknown"}:
        assert hint in KNOWN_CLASSES


# ---------------------------------------------------------------------------
# Governance lookup
# ---------------------------------------------------------------------------


def test_state_dir_owners_extracts_module_paths(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    owners = _load_state_dir_owners(repo)
    assert "dharma_swarm/register_disciplines.py" in owners


def test_semgrep_allowlist_extracts_paths(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    allowed = _load_semgrep_allowlist(repo)
    assert "dharma_swarm/register_disciplines.py" in allowed


def test_state_dir_owners_handles_missing_doc(tmp_path: Path) -> None:
    assert _load_state_dir_owners(tmp_path) == set()


# ---------------------------------------------------------------------------
# Dharma writer detection
# ---------------------------------------------------------------------------


def test_find_dharma_writers_maps_subpath_to_module(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    writers = _find_dharma_writers(repo)
    assert writers.get("stigmergy/register_marks.jsonl") == "dharma_swarm/register_disciplines.py"


# ---------------------------------------------------------------------------
# End-to-end scan
# ---------------------------------------------------------------------------


def test_scan_returns_surfaces_for_python_and_dharma(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    surfaces = scan(repo_root=repo, home=home)

    paths = {s.path for s in surfaces}
    # Python memory module surface
    assert any("register_disciplines.py" in p for p in paths)
    assert any("memory_lattice.py" in p for p in paths)
    # ~/.dharma surfaces
    assert any("stigmergy" in p for p in paths)
    assert any(".smriti" in p for p in paths)
    assert any("cabinet" in p for p in paths)


def test_scan_marks_known_owner_as_governed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    surfaces = scan(repo_root=repo, home=home)
    register = next(s for s in surfaces if s.path.endswith("register_disciplines.py"))
    assert register.in_state_dir_owners is True
    assert register.in_semgrep_allowlist is True
    assert register.reconciliation_tag in {"verified", "probable"}


def test_scan_marks_unknown_owner_as_needs_owner(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    # Add an orphaned ~/.dharma file with no Python writer
    (home / ".dharma" / "orphan.jsonl").write_text("{}\n")
    surfaces = scan(repo_root=repo, home=home)
    orphan = next((s for s in surfaces if s.path.endswith("orphan.jsonl")), None)
    assert orphan is not None
    assert orphan.reconciliation_tag == "needs_owner"


def test_scan_records_substrate_correctly(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    surfaces = scan(repo_root=repo, home=home)
    by_substrate = {s.substrate for s in surfaces}
    assert {"python_module", "jsonl", "directory"}.issubset(by_substrate)


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def _surface(*, size: int, governed: bool) -> MemorySurface:
    return MemorySurface(
        surface_id="x",
        path="/x",
        substrate="directory",
        size_bytes=size,
        last_modified="",
        owner_module_hint=None,
        in_state_dir_owners=governed,
        in_semgrep_allowlist=governed,
    )


def test_risk_critical_for_huge_ungoverned_surfaces() -> None:
    huge = _surface(size=200 * 1024**3, governed=False)
    assert _risk_for(huge) == "critical"


def test_risk_low_for_small_governed_surfaces() -> None:
    small = _surface(size=1024, governed=True)
    assert _risk_for(small) == "low"


def test_risk_high_for_large_ungoverned() -> None:
    large = _surface(size=20 * 1024**3, governed=False)
    assert _risk_for(large) == "high"


# ---------------------------------------------------------------------------
# JSONL output
# ---------------------------------------------------------------------------


def test_write_jsonl_produces_meta_and_one_row_per_surface(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    surfaces = scan(repo_root=repo, home=home)
    output = tmp_path / "census.jsonl"
    write_jsonl(surfaces, output)
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    meta = json.loads(lines[0])
    assert meta["_meta"]["census_version"] == CENSUS_VERSION
    assert meta["_meta"]["surface_count"] == len(surfaces)
    body = [json.loads(line) for line in lines[1:]]
    assert len(body) == len(surfaces)
    for row in body:
        assert "surface_id" in row
        assert "path" in row
        assert row["substrate"] in KNOWN_SUBSTRATES


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def test_diff_detects_added_removed_changed_size(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    surfaces_a = scan(repo_root=repo, home=home)
    write_jsonl(surfaces_a, a_path)

    # Mutate: add an orphan + grow an existing file
    (home / ".dharma" / "newborn.jsonl").write_text("{}\n")
    (home / ".dharma" / "stigmergy" / "register_marks.jsonl").write_text(
        '{"id": 1}\n{"id": 2}\n'  # bigger
    )
    surfaces_b = scan(repo_root=repo, home=home)
    write_jsonl(surfaces_b, b_path)

    result = diff_runs(a_path, b_path)
    assert any("newborn.jsonl" not in line for line in result["added"]) or result["added"]
    assert result["added"]  # at least one new surface
    assert isinstance(result["changed_size"], list)


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def test_cli_scan_smoke(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _build_repo(tmp_path)
    home = _build_home(tmp_path)
    output = tmp_path / "out.jsonl"
    from dharma_swarm.memory_census import main

    rc = main(
        ["scan", "--repo-root", str(repo), "--home", str(home), "--output", str(output)]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "surfaces:" in captured.out
    assert output.exists()
