from __future__ import annotations

import json

from dharma_swarm.holon_system.sarathi import gateway


def test_gateway_snapshot_is_read_only_and_honest() -> None:
    snapshot = gateway.gateway_snapshot()

    assert snapshot["schema_version"] == "dharma.sarathi.gateway_snapshot.v1"
    assert snapshot["mode"] == "read_only_snapshot"
    assert snapshot["may_execute_unattended"] is False
    assert snapshot["sarathi_alive"] is False
    assert "alive" in snapshot["alive_verdict"]
    assert snapshot["load_holon"]["ok"] is True
    assert "runtime_surfaces" in snapshot


def test_write_operator_brief_writes_json_and_markdown(tmp_path) -> None:
    result = gateway.write_operator_brief(outbox=tmp_path)

    json_path = tmp_path / result["json_path"].split("/")[-1]
    markdown_path = tmp_path / result["markdown_path"].split("/")[-1]
    assert json_path.exists()
    assert markdown_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "dharma.sarathi.gateway_snapshot.v1"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Sarathi remote readiness brief" in markdown
    assert "does not claim Sarathi is alive" in markdown
