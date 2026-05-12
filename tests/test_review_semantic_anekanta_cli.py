from __future__ import annotations

import json
from pathlib import Path

from scripts.review_semantic_anekanta import main


def test_review_semantic_anekanta_cli_writes_existing_result_shape(
    tmp_path: Path,
    capsys,
) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text(
        "dharma_swarm/telos_gates.py routes WITNESS and ANEKANTA before "
        "provider execution, records GateDecisionRecord objects, and then "
        "writes Outcome and ValueEvent records through TelicSeam.",
        encoding="utf-8",
    )
    output = tmp_path / "review.json"

    code = main([str(artifact), "--output", str(output)])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert output.exists()
    assert payload["gate_result"] == "PASS"
    assert set(payload["grounded_frames"]) == {"mechanistic", "systems"}
    assert payload["reviewer"] == "semantic_anekanta_v0"


def test_review_semantic_anekanta_cli_can_fail_on_fail(
    tmp_path: Path,
    capsys,
) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text(
        "A robust architecture must integrate mechanism, witness, and "
        "feedback into a holistic optimization substrate.",
        encoding="utf-8",
    )

    code = main([str(artifact), "--fail-on-fail"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_result"] == "FAIL"
    assert payload["label"] == "padded"
