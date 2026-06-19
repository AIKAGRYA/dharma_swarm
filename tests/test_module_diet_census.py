from __future__ import annotations

from pathlib import Path

from scripts.governance.module_diet_census import build_census


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_module_diet_census_classifies_imported_and_dead_modules(tmp_path: Path) -> None:
    write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml", "")
    write(tmp_path / "pyproject.toml", "")
    write(tmp_path / "dharma_swarm" / "__init__.py", "")
    write(tmp_path / "dharma_swarm" / "live.py", "VALUE = 1\n")
    write(tmp_path / "dharma_swarm" / "dead.py", "VALUE = 2\n")
    write(tmp_path / "api" / "uses_live.py", "from dharma_swarm import live\n")
    write(tmp_path / "tests" / "test_live.py", "from dharma_swarm.live import VALUE\n")

    result = build_census(tmp_path)
    by_module = {row.module: row for row in result.rows}

    assert by_module["dharma_swarm.live"].imported_by_count == 2
    assert by_module["dharma_swarm.live"].classification == "LIVE_CANDIDATE"
    assert by_module["dharma_swarm.dead"].classification == "DEAD_CANDIDATE"
    assert by_module["dharma_swarm.dead"].proof_required


def test_module_diet_census_marks_duplicate_seam_review(tmp_path: Path) -> None:
    write(tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml", "")
    write(tmp_path / "pyproject.toml", "")
    write(tmp_path / "dharma_swarm" / "__init__.py", "")
    write(tmp_path / "dharma_swarm" / "example_bridge.py", "VALUE = 1\n")

    result = build_census(tmp_path)
    row = {item.module: item for item in result.rows}["dharma_swarm.example_bridge"]

    assert row.classification == "DUPLICATE_REVIEW"
    assert row.duplicate_families == ["bridge"]
    assert result.summary["duplicate_family_counts"] == {"bridge": 1}


def test_module_diet_census_honors_manifest_mentions(tmp_path: Path) -> None:
    write(
        tmp_path / "ACTIVE_SURFACE_MANIFEST.yaml",
        "owner_module: dharma_swarm/manifest_owned.py\n",
    )
    write(tmp_path / "pyproject.toml", "")
    write(tmp_path / "dharma_swarm" / "__init__.py", "")
    write(tmp_path / "dharma_swarm" / "manifest_owned.py", "VALUE = 1\n")

    result = build_census(tmp_path)
    row = {item.module: item for item in result.rows}["dharma_swarm.manifest_owned"]

    assert row.manifest_mentioned is True
    assert row.classification == "LIVE"
