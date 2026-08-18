"""Tests for external-target ingestion and tree digesting."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.foundry.target_ingest import (
    TargetSpec,
    compute_tree_digest,
    ingest,
)


def _make_source(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    (src / "kernels").mkdir(parents=True)
    (src / "kernels" / "attn.py").write_text("def k():\n    return 1\n")
    (src / "README.md").write_text("hello")
    return src


def test_tree_digest_deterministic(tmp_path):
    src = _make_source(tmp_path)
    assert compute_tree_digest(src) == compute_tree_digest(src)


def test_tree_digest_changes_on_edit(tmp_path):
    src = _make_source(tmp_path)
    before = compute_tree_digest(src)
    (src / "kernels" / "attn.py").write_text("def k():\n    return 2\n")
    assert compute_tree_digest(src) != before


def test_tree_digest_scoped_to_evolve_paths(tmp_path):
    src = _make_source(tmp_path)
    scoped_before = compute_tree_digest(src, ["kernels/"])
    (src / "README.md").write_text("changed outside scope")
    # Editing a file outside the evolve scope must not change the scoped digest.
    assert compute_tree_digest(src, ["kernels/"]) == scoped_before


def test_ingest_local_source_writes_manifest(tmp_path):
    src = _make_source(tmp_path)
    dest = tmp_path / "targets"
    spec = TargetSpec(
        id="demo",
        name="Demo",
        url="https://example.invalid/demo",
        sha="abc123",
        evolve_paths=["kernels/"],
        oracle_cmd=["python", "-m", "pytest"],
        license="Apache-2.0",
        ai_policy="native",
    )
    pinned = ingest(spec, dest_root=dest, local_source=src)

    assert Path(pinned.root).exists()
    assert pinned.tree_digest.startswith("sha256:")
    manifest = json.loads((dest / "demo.pin.json").read_text())
    assert manifest["spec"]["id"] == "demo"
    assert manifest["tree_digest"] == pinned.tree_digest
    assert manifest["resolved_sha"] == "abc123"
