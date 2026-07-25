from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/governance/orientation_graph.py"
spec = importlib.util.spec_from_file_location("orientation_graph_truth_graph", SCRIPT)
og = importlib.util.module_from_spec(spec)
sys.modules["orientation_graph_truth_graph"] = og
spec.loader.exec_module(og)


def test_truth_graph_repo_context_writes_json_and_markdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(og, "REPO_CONTEXT_DIR", tmp_path)
    monkeypatch.setattr(og, "REPO_CONTEXT_JSON", tmp_path / "repo_context.json")
    monkeypatch.setattr(og, "REPO_CONTEXT_MD", tmp_path / "repo_context.md")

    packet = og.build_packet()
    first_hash = packet.context_hash
    json_path, md_path = og.write_repo_context(packet)
    first_bytes = json_path.read_bytes()
    og.write_repo_context(packet)

    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["context_hash"] == first_hash
    assert "lanes" in payload
    repo_context_path = og._normalize_context_path(str(og.REPO_ROOT))
    assert any(
        lane["path"] == repo_context_path and lane["head"] == "CURRENT_CHECKOUT"
        for lane in payload["lanes"]
    )
    assert "agents" in payload
    assert all("age_hours" not in agent for agent in payload["agents"])
    assert "a2a_bus" in payload
    assert "body" in payload
    assert json_path.read_bytes() == first_bytes
