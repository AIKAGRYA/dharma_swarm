from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.context_packet_router import (
    INDEX_PATH,
    load_index,
    main,
    packet_by_id,
    route_packets,
)


def test_context_packet_index_exists() -> None:
    assert INDEX_PATH.exists()


def test_routes_sab_topic_to_sab_packet() -> None:
    matches = route_packets("SAB First Spark flywheel witness receipt", top=1)
    assert matches
    assert matches[0].packet_id == "ctx.sab-flywheel"


def test_routes_runtime_provider_path_to_model_packet() -> None:
    matches = route_packets(
        "fix provider fallback",
        paths=("dharma_swarm/runtime_provider.py",),
        top=1,
    )
    assert matches
    assert matches[0].packet_id == "ctx.model-provider-routing"


def test_exact_packet_lookup_returns_file() -> None:
    packet = packet_by_id("ctx.memory-semantic-commons")
    assert packet is not None
    assert packet["file"] == "packets/03_memory_semantic_commons.md"


def test_packet_index_v11_packets_expose_anchor_fields() -> None:
    data = load_index()
    assert data["schema_version"] == "context-packet-index-v1.1"
    for packet in data["packets"]:
        assert packet["vision_anchors"]
        assert packet["current_reality_anchors"]
        assert packet["dense_docs"]
        assert packet["future_agent_review_hooks"]


def test_anchor_file_refs_exist_for_all_packets() -> None:
    data = load_index()
    repo_root = INDEX_PATH.parents[2]
    for packet in data["packets"]:
        for field in ("vision_anchors", "current_reality_anchors", "dense_docs"):
            for item in packet[field]:
                if item["type"] == "file":
                    assert (repo_root / item["ref"]).exists(), (
                        packet["id"],
                        field,
                        item["ref"],
                    )


def test_packet_by_id_returns_anchor_metadata() -> None:
    packet = packet_by_id("ctx.command-plane-governance")
    assert packet is not None
    assert any(
        anchor["ref"] == "docs/governance/SOVEREIGN_MANIFEST.md"
        for anchor in packet["vision_anchors"]
    )
    assert any(
        anchor["ref"] == "docs/governance/ACTIVE_TRACK.yaml"
        for anchor in packet["current_reality_anchors"]
    )
    assert packet["future_agent_review_hooks"]


def test_route_packets_json_hydrate_includes_anchor_fields(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "fix provider fallback",
            "--path",
            "dharma_swarm/runtime_provider.py",
            "--top",
            "1",
            "--json",
            "--hydrate",
        ]
    )
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["packet_id"] == "ctx.model-provider-routing"
    assert out[0]["vision_anchors"]
    assert out[0]["current_reality_anchors"]
    assert out[0]["dense_docs"]
    assert out[0]["future_agent_review_hooks"]


def test_show_anchors_prints_compact_anchor_sections(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--id", "ctx.model-provider-routing", "--show-anchors"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Vision anchors:" in out
    assert "Current reality anchors:" in out
    assert "Dense docs:" in out
    assert "Future-agent review hooks:" in out


def test_load_index_rejects_packet_missing_current_reality_anchors(tmp_path: Path) -> None:
    data = load_index()
    del data["packets"][0]["current_reality_anchors"]
    bad = tmp_path / "bad_index.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="current_reality_anchors"):
        load_index(bad)


def test_v2_packet_markdown_contains_anchor_headings() -> None:
    data = load_index()
    for packet in data["packets"]:
        content = (INDEX_PATH.parent / packet["file"]).read_text(encoding="utf-8")
        assert "## Vision Anchors" in content
        assert "## Current Reality Anchors" in content
        assert "## Dense Docs" in content
        assert "## Work-Lane Anchors" in content
        assert "## Evidence Boundary" in content
        assert "## Future-Agent Review Hooks" in content


def test_packet_handoff_shapes_include_common_claim_and_next_fields() -> None:
    data = load_index()
    for packet in data["packets"]:
        content = (INDEX_PATH.parent / packet["file"]).read_text(encoding="utf-8")
        assert '"claims_with_citations"' in content
        assert '"claims_not_made"' in content
        assert '"next_packet"' in content
        assert '"residual_risk"' in content
        assert '"next_step"' in content
