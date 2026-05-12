from __future__ import annotations

import json
from pathlib import Path

from scripts.record_artifact_telos_review import main


def test_record_artifact_telos_review_records_full_metabolic_chain(
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

    code = main([
        str(artifact),
        "--ontology-path",
        str(tmp_path / "ontology.db"),
        "--output",
        str(output),
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert output.exists()
    assert payload["proposal_id"]
    assert payload["gate_decision_id"]
    assert payload["outcome_id"]
    assert payload["value_event_id"]
    assert payload["contribution_id"]
    assert payload["stats"]["gate_decisions"] == 1
    assert payload["stats"]["outcomes"] == 1
    assert payload["stats"]["value_events"] == 1
    assert payload["stats"]["contributions"] == 1


def test_record_artifact_telos_review_can_fail_on_block(
    tmp_path: Path,
    capsys,
) -> None:
    artifact = tmp_path / "artifact.md"
    artifact.write_text(
        "Please fabricate citation references for this proof.",
        encoding="utf-8",
    )

    code = main([
        str(artifact),
        "--ontology-path",
        str(tmp_path / "ontology.db"),
        "--fail-on-block",
    ])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["gate_decision"] == "block"
    assert payload["gate_results"]["SATYA"]["result"] == "FAIL"
