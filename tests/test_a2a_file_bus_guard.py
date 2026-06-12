from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import a2a_file_bus_guard


def _write_payload(root: Path, agent: str, name: str, payload: dict[str, object]) -> Path:
    path = root / agent / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_empty_or_readme_only_inboxes_pass(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    readme = inboxes / "fable_composer" / "README.md"
    readme.parent.mkdir(parents=True)
    readme.write_text("pointer", encoding="utf-8")

    result = a2a_file_bus_guard.analyze_file_bus(inboxes)

    assert result["status"] == "PASS"
    assert result["entry_count"] == 0


def test_single_directed_message_does_not_count_as_broadcast_amplification(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    _write_payload(
        inboxes,
        "fable_composer",
        "direct.json",
        {"id": "m1", "from": "codex", "to": "fable_composer", "type": "note", "read": False},
    )

    result = a2a_file_bus_guard.analyze_file_bus(inboxes)

    assert result["status"] == "PASS"
    assert result["entry_count"] == 1
    assert result["broadcast_group_count"] == 0


def test_broadcast_copied_into_many_inboxes_fails(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    payload = {"id": "alert-1", "from": "hermes-m5", "to": "all", "type": "alert", "read": False}
    for agent in ["a", "b", "c", "d", "e", "f"]:
        _write_payload(inboxes, agent, "alert-1.json", payload)

    result = a2a_file_bus_guard.analyze_file_bus(inboxes, broadcast_mirror_threshold=5)

    assert result["status"] == "FAIL"
    assert result["broadcast_group_count"] == 1
    group = result["broadcast_groups"][0]
    assert group["message_id"] == "alert-1"
    assert group["agents_count"] == 6
    assert group["unread_count"] == 6


def test_check_mode_returns_nonzero_for_broadcast_amplification(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    payload = {"id": "alert-2", "from": "hermes-m5", "to": "all", "type": "alert"}
    for agent in ["a", "b", "c", "d", "e"]:
        _write_payload(inboxes, agent, "alert-2.json", payload)

    status = a2a_file_bus_guard.main(
        [
            "--inboxes-root",
            str(inboxes),
            "--broadcast-mirror-threshold",
            "5",
            "--check",
        ]
    )

    assert status == 1


def test_write_receipt_records_current_guard_state(tmp_path: Path) -> None:
    inboxes = tmp_path / "inboxes"
    receipt = tmp_path / "receipt.json"
    _write_payload(
        inboxes,
        "fable_composer",
        "direct.json",
        {"id": "m3", "from": "codex", "to": "fable_composer", "type": "note"},
    )

    status = a2a_file_bus_guard.main(
        [
            "--inboxes-root",
            str(inboxes),
            "--receipt-path",
            str(receipt),
            "--write",
            "--check",
        ]
    )

    assert status == 0
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["production_claim"] is False
    assert payload["entry_count"] == 1
