"""Tests for scripts/hermes_heartbeat_poll.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import hermes_heartbeat_poll as hermes


def test_poll_queue_preserves_malformed_lines_when_claiming(
    monkeypatch, tmp_path: Path
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    claimable = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
        "description": "claim me",
    }
    unsupported = {
        "id": "task-2",
        "status": "pending",
        "claimed_by": None,
        "capability": "not-hermes",
    }
    queue_file.write_text(
        "\n".join(
            [
                "{malformed-json",
                json.dumps(claimable),
                "",
                json.dumps(unsupported),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(hermes, "QUEUE_FILE", queue_file)

    claimed = hermes.poll_queue(dry_run=False)

    assert [task["id"] for task in claimed] == ["task-1"]
    lines = queue_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "{malformed-json"
    assert lines[2] == ""
    rewritten_claimable = json.loads(lines[1])
    assert rewritten_claimable["claimed_by"] == hermes.HERMES_AGENT_ID
    assert rewritten_claimable["status"] == "claimed"
    assert json.loads(lines[3]) == unsupported


def test_poll_queue_uses_advisory_lock(monkeypatch, tmp_path: Path) -> None:
    queue_file = tmp_path / "queue.jsonl"
    queue_file.write_text("", encoding="utf-8")
    calls: list[int] = []

    def fake_flock(_fd: int, operation: int) -> None:
        calls.append(operation)

    monkeypatch.setattr(hermes, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(hermes.fcntl, "flock", fake_flock)

    assert hermes.poll_queue(dry_run=False) == []
    assert calls == [hermes.fcntl.LOCK_EX, hermes.fcntl.LOCK_UN]


def test_poll_queue_does_not_claim_task_without_capability_or_type(
    monkeypatch, tmp_path: Path
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    task = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "description": "untyped task",
    }
    queue_file.write_text(json.dumps(task) + "\n", encoding="utf-8")
    monkeypatch.setattr(hermes, "QUEUE_FILE", queue_file)

    assert hermes.poll_queue(dry_run=False) == []
    assert json.loads(queue_file.read_text(encoding="utf-8")) == task


def test_poll_queue_write_failure_does_not_report_claim(
    monkeypatch, tmp_path: Path
) -> None:
    queue_file = tmp_path / "queue.jsonl"
    task = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
    }
    queue_file.write_text(json.dumps(task) + "\n", encoding="utf-8")

    def fail_replace(_src: str, _dst: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(hermes, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(hermes.os, "replace", fail_replace)

    try:
        hermes.poll_queue(dry_run=False)
    except OSError as exc:
        assert "replace failed" in str(exc)
    else:
        raise AssertionError("poll_queue should fail when claim writeback fails")

    persisted = json.loads(queue_file.read_text(encoding="utf-8"))
    assert persisted["status"] == "pending"
    assert persisted["claimed_by"] is None
