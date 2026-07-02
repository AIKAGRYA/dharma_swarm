from __future__ import annotations

import json

from dharma_swarm.venture_cell.livelihood_loom.cli import main


def test_livelihood_cli_status_json(capsys):
    assert main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cell_id"] == "livelihood_loom"
    assert payload["overall_status"].endswith("provider_blocked")
    gates = {gate["name"]: gate["status"] for gate in payload["gates"]}
    assert gates["provider_proof"] == "red"


def test_livelihood_cli_status_text(capsys):
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "livelihood_loom:" in out
    assert "provider_blocked" in out
    assert "provider_proof: red" in out
