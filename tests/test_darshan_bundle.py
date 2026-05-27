from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from dharma_swarm.venture_cell.darshan.bundle import (
    REQUIRED_BUNDLE_FILES,
    create_bundle,
    refresh_manifest,
    validate_bundle,
)
from dharma_swarm.venture_cell.darshan.conductor import run_once


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def test_create_bundle_writes_required_files_under_venture_cell_path(fake_home: Path) -> None:
    bundle_path = create_bundle(
        title="After the Feed",
        bundle_date=date(2026, 5, 26),
    )

    expected = (
        fake_home
        / ".dharma"
        / "artifacts"
        / "venture_cell"
        / "DARSHAN"
        / "2026-05-26"
        / "after-the-feed"
    )
    assert bundle_path == expected
    assert sorted(p.name for p in bundle_path.iterdir()) == sorted(REQUIRED_BUNDLE_FILES)

    result = validate_bundle(bundle_path)
    assert result.valid is True
    assert result.errors == []
    assert result.manifest is not None
    assert result.manifest.season == "After the Feed"


def test_validate_bundle_fails_when_required_file_missing(fake_home: Path) -> None:
    bundle_path = create_bundle(title="Missing Ledger")
    (bundle_path / "claim_ledger.json").unlink()

    result = validate_bundle(bundle_path)

    assert result.valid is False
    assert "missing required file: claim_ledger.json" in result.errors


def test_validate_bundle_fails_on_malformed_source_pack(fake_home: Path) -> None:
    bundle_path = create_bundle(title="Malformed Source Pack")
    (bundle_path / "source_pack.json").write_text("{}", encoding="utf-8")

    result = validate_bundle(bundle_path)

    assert result.valid is False
    assert any("source_pack.json invalid" in err for err in result.errors)


def test_validate_bundle_warns_when_manifest_hash_changes(fake_home: Path) -> None:
    bundle_path = create_bundle(title="Editable Article")
    article = bundle_path / "article.md"
    article.write_text(article.read_text(encoding="utf-8") + "\nNew paragraph.\n", encoding="utf-8")

    result = validate_bundle(bundle_path)

    assert result.valid is True
    assert "content hash changed since manifest write: article.md" in result.warnings


def test_refresh_manifest_clears_hash_warnings(fake_home: Path) -> None:
    bundle_path = create_bundle(title="Refreshable Article")
    article = bundle_path / "article.md"
    article.write_text(article.read_text(encoding="utf-8") + "\nNew paragraph.\n", encoding="utf-8")

    refresh_manifest(bundle_path)
    result = validate_bundle(bundle_path)

    assert result.valid is True
    assert result.warnings == []


def test_run_once_creates_valid_manual_transaction(fake_home: Path) -> None:
    result = run_once(title="The Thing They Are Competing For")

    assert result.valid is True
    assert result.manifest is not None
    assert result.manifest.slug == "the-thing-they-are-competing-for"
    assert json.loads((result.bundle_path / "decision_delta.json").read_text(encoding="utf-8"))[
        "affected_cells"
    ] == ["DARSHAN"]
