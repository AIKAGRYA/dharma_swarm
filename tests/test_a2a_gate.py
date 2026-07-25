from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.a2a.task_receipt import (
    RECEIPT_SCHEMA,
    bounce_payload,
    read_receipted_inbox,
    validate_or_quarantine_file,
    validate_task_receipt,
)


def _valid_receipt() -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "claim": "A claim with evidence.",
        "evidence": [{"kind": "command", "value": "pytest tests/test_a2a_gate.py"}],
        "verdict": "verified",
        "next_action": "Continue.",
        "files_changed": [],
    }


def test_a2a_gate_accepts_receipt_shape() -> None:
    result = validate_task_receipt(_valid_receipt())
    assert result.valid
    assert result.errors == []


def test_a2a_gate_rejects_unstructured_essay() -> None:
    result = validate_task_receipt({"body": "long confident essay"})
    assert not result.valid
    assert "schema must be dharma_a2a_task_receipt.v1" in result.errors
    assert bounce_payload(result.errors)["message"] == "receipt or it didn't happen."


def test_a2a_gate_quarantines_invalid_file(tmp_path: Path) -> None:
    inbox_file = tmp_path / "essay.json"
    quarantine = tmp_path / "quarantine"
    inbox_file.write_text(json.dumps({"body": "essay"}) + "\n", encoding="utf-8")

    result = validate_or_quarantine_file(inbox_file, quarantine_dir=quarantine)

    assert not result.valid
    records = list(quarantine.glob("*.quarantine.json"))
    assert len(records) == 1
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    assert payload["bounce"]["message"] == "receipt or it didn't happen."


def test_a2a_gate_receipt_only_inbox_returns_receipts_and_quarantines_essays(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    quarantine = tmp_path / "quarantine"
    inbox.mkdir()
    inbox.joinpath("essay.json").write_text(json.dumps({"body": "essay"}) + "\n", encoding="utf-8")
    inbox.joinpath("receipt.json").write_text(json.dumps(_valid_receipt()) + "\n", encoding="utf-8")

    receipts = read_receipted_inbox(inbox, quarantine_dir=quarantine)

    assert [item.path.name for item in receipts] == ["receipt.json"]
    assert receipts[0].payload["schema"] == RECEIPT_SCHEMA
    assert len(list(quarantine.glob("*.quarantine.json"))) == 1
