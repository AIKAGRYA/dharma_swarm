from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.field_knowledge_base import ALL_FIELD_ENTRIES


REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_DIR = REPO_ROOT / "references" / "research" / "agentic_autonomy_2026-03-27"
MANIFEST_PATH = BUNDLE_DIR / "sources.json"


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        pytest.skip(f"optional agentic autonomy source bundle is absent: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_agentic_autonomy_manifest_has_at_least_20_sources() -> None:
    data = _load_manifest()
    assert len(data["sources"]) >= 20


def test_agentic_autonomy_local_paths_exist() -> None:
    data = _load_manifest()
    for source in data["sources"]:
        local_path = source.get("local_path")
        assert local_path, f"missing local_path for {source['id']}"
        assert (REPO_ROOT / local_path).exists(), f"missing local artifact for {source['id']}: {local_path}"


def test_field_knowledge_base_contains_new_agentic_entries() -> None:
    ids = {entry["id"] for entry in ALL_FIELD_ENTRIES}
    expected = {
        "meta-rea-2026",
        "minimax-m27",
        "ouroboros-identity-loop",
        "cashclaw-hyrve",
        "hyrve-agent-marketplace",
        "langchain-deepagents",
        "plugmem",
        "mempo",
    }
    assert expected.issubset(ids)
