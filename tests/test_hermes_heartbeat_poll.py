"""Tests for scripts/hermes_heartbeat_poll.py."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import hermes_heartbeat_poll as hermes

from dharma_swarm.operator_core import a2a_task_lifecycle as lifecycle


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


def _write_canonical_task(queue: Path, task: dict) -> None:
    """Append one task to the canonical a2a_bus/tasks/queue.jsonl surface."""
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(task) + "\n")


def test_hermes_polls_canonical_lifecycle_queue(monkeypatch, tmp_path: Path) -> None:
    """A task written to the canonical lifecycle queue must be seen + claimed.

    The canonical writer (dharma_swarm.operator_core.a2a_task_lifecycle) owns
    ``<root>/a2a_bus/tasks/queue.jsonl``. Hermes must poll THAT file, not the
    legacy root ``<root>/a2a_bus/queue.jsonl``. Reload the module with the env
    pointed at ``tmp_path`` so QUEUE_FILE is computed exactly as it would be in
    a live cron invocation.
    """
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path))
    monkeypatch.delenv("DHARMA_STATE_DIR", raising=False)
    hermes_reloaded = importlib.reload(hermes)
    monkeypatch.setattr(hermes_reloaded, "HERMES_STATE_FILE", tmp_path / "hermes_state.json")

    canonical_queue = lifecycle.queue_path(tmp_path)
    task = {
        "id": "task-canonical-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
        "description": "written via canonical a2a_bus/tasks/queue.jsonl",
    }
    _write_canonical_task(canonical_queue, task)

    claimed = hermes_reloaded.poll_queue(dry_run=False)

    assert [t["id"] for t in claimed] == ["task-canonical-1"]
    persisted = json.loads(canonical_queue.read_text(encoding="utf-8").splitlines()[0])
    assert persisted["claimed_by"] == hermes_reloaded.HERMES_AGENT_ID
    assert persisted["status"] == "claimed"

    # Restore module state (env already restored by monkeypatch).
    importlib.reload(hermes)


def test_hermes_ignores_legacy_root_queue(monkeypatch, tmp_path: Path) -> None:
    """Negative control: a task at the OLD root path is NOT treated as canonical.

    Guards against an over-broad fix that reads both the legacy
    ``<root>/a2a_bus/queue.jsonl`` and the canonical
    ``<root>/a2a_bus/tasks/queue.jsonl``. The legacy task must be left
    untouched and never claimed.
    """
    monkeypatch.setenv("DHARMA_HOME", str(tmp_path))
    monkeypatch.delenv("DHARMA_STATE_DIR", raising=False)
    hermes_reloaded = importlib.reload(hermes)
    monkeypatch.setattr(hermes_reloaded, "HERMES_STATE_FILE", tmp_path / "hermes_state.json")

    legacy_queue = tmp_path / "a2a_bus" / "queue.jsonl"
    legacy_queue.parent.mkdir(parents=True, exist_ok=True)
    legacy_task = {
        "id": "task-legacy-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
        "description": "written to the legacy root path",
    }
    legacy_queue.write_text(json.dumps(legacy_task) + "\n", encoding="utf-8")

    claimed = hermes_reloaded.poll_queue(dry_run=False)

    assert claimed == []
    persisted = json.loads(legacy_queue.read_text(encoding="utf-8"))
    assert persisted["claimed_by"] is None
    assert persisted["status"] == "pending"

    # Restore module state (env already restored by monkeypatch).
    importlib.reload(hermes)
