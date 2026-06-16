"""Tests for Semantic Commons PKM projection and retrieval scoping."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts/governance/agent_admission_projection.py"
PROJECTION_PATH = REPO_ROOT / "docs/ontology/pkm_projection.yaml"
RETRIEVAL_SCOPE_PATH = REPO_ROOT / "docs/ontology/retrieval_scope.yaml"

spec = importlib.util.spec_from_file_location("agent_admission_projection", SCRIPT_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules["agent_admission_projection"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_projection_config_is_read_only_and_path_scoped() -> None:
    payload = _load(PROJECTION_PATH)
    policy = payload["projection_policy"]

    assert policy["generated"] is True
    assert policy["canon"] is False
    assert policy["read_only_notes"] is True
    assert policy["mcp_access"] == "read_only"
    assert policy["command_execution"] == "disabled"
    assert "/Users/dhyana/.dharma/knowledge/wiki/semantic-commons" in policy["mcp_path_scopes"]


def test_generated_object_notes_have_required_projection_properties(tmp_path: Path) -> None:
    files, manifest = mod.build_projection(
        tmp_path / "semantic-commons",
        generated_at="2026-06-16T00:00:00+00:00",
    )
    object_notes = {path: body for path, body in files.items() if path.startswith("objects/")}

    assert manifest["object_count"] >= 12
    assert object_notes
    assert "bases/semantic-commons.base" in files
    sample = next(body for path, body in object_notes.items() if "session-orientation" in path)
    frontmatter = yaml.safe_load(sample.split("---", 2)[1])
    required = set(_load(PROJECTION_PATH)["required_note_properties"])

    assert required <= set(frontmatter)
    assert frontmatter["generated"] is True
    assert frontmatter["canon"] is False
    assert frontmatter["canonical_object_id"] == "semobj.session_orientation"
    assert frontmatter["projection_of"].startswith("docs/ontology/semantic_objects.yaml#")
    assert frontmatter["orientation_layers"][:3] == ["L0", "L1", "L2"]


def test_base_dashboard_contains_required_views() -> None:
    files, _manifest = mod.build_projection(
        Path("/tmp/semantic-commons"),
        generated_at="2026-06-16T00:00:00+00:00",
    )
    base = files["bases/semantic-commons.base"]

    for view in _load(PROJECTION_PATH)["base_views"]:
        assert view["name"] in base


def test_retrieval_scope_is_structural_first() -> None:
    payload = _load(RETRIEVAL_SCOPE_PATH)
    order = payload["retrieval_order"]

    assert payload["structural_scope_first"] is True
    assert order[0]["id"] == "orientation_route"
    assert order[0]["lane"] == "structural"
    assert {"L0", "L1"} <= set(order[0]["allowed_layers"])
    assert order[1]["id"] == "exact_match"
    assert [item["id"] for item in order] == [
        "orientation_route",
        "exact_match",
        "lexical_bm25_fts",
        "vector_search",
        "graph_expansion",
        "fusion",
    ]


def test_retrieval_results_expose_required_evidence_fields() -> None:
    payload = _load(RETRIEVAL_SCOPE_PATH)

    assert {
        "canonical_target",
        "authority_level",
        "lifecycle_state",
        "source_path",
        "projection_canon_status",
        "retrieval_lane",
        "timestamp",
        "freshness_marker",
        "selection_reason",
    } <= set(payload["result_required_fields"])
    assert payload["projection_rules"]["generated_notes_can_claim_canon"] is False
    assert payload["projection_rules"]["l4_never_first"] is True
