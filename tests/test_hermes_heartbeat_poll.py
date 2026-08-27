"""Tests for scripts/hermes_heartbeat_poll.py."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import hermes_heartbeat_poll as hermes

from dharma_swarm.operator_core import a2a_task_lifecycle as lifecycle


def _canonical_queue(root: Path) -> Path:
    queue = root / "a2a_bus" / "tasks" / "queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    return queue


def test_poll_queue_claims_through_canonical_protocol(
    monkeypatch, tmp_path: Path
) -> None:
    """Matching tasks are claimed via claim_task — not a local rewrite.

    The claim result must carry the canonical claim fields (claimed_via,
    return_address, inbox mirror) proving the mutation went through
    a2a_task_lifecycle.claim_task, and the queue line must be rewritten in
    the canonical writer's shape.
    """
    queue_file = _canonical_queue(tmp_path)
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
        json.dumps(claimable) + "\n" + json.dumps(unsupported) + "\n",
        encoding="utf-8",
    )

    claimed = hermes.poll_queue(dry_run=False, queue_file=queue_file)

    assert [task["id"] for task in claimed] == ["task-1"]
    assert claimed[0]["claimed_by"] == hermes.HERMES_AGENT_ID
    assert claimed[0]["status"] == "claimed"
    # Canonical mutation artifacts a local rewrite would never produce.
    assert claimed[0]["claimed_via"] == (
        "dharma_swarm.operator_core.a2a_task_lifecycle"
    )
    assert claimed[0]["return_address"]["resume_ref"] == "a2a_task:task-1"
    assert Path(claimed[0]["inbox_path"]).exists()

    lines = queue_file.read_text(encoding="utf-8").splitlines()
    rewritten_claimable = json.loads(lines[0])
    assert rewritten_claimable["claimed_by"] == hermes.HERMES_AGENT_ID
    assert rewritten_claimable["status"] == "claimed"
    assert json.loads(lines[1]) == unsupported


def test_poll_queue_preserves_malformed_lines_via_canonical_writer(
    monkeypatch, tmp_path: Path
) -> None:
    """Malformed lines survive the canonical claim rewrite untouched."""
    queue_file = _canonical_queue(tmp_path)
    claimable = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
        "description": "claim me",
    }
    queue_file.write_text(
        "\n".join(["{malformed-json", json.dumps(claimable)]) + "\n",
        encoding="utf-8",
    )

    claimed = hermes.poll_queue(dry_run=False, queue_file=queue_file)

    assert [task["id"] for task in claimed] == ["task-1"]
    lines = queue_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "{malformed-json"
    assert json.loads(lines[1])["status"] == "claimed"


def test_poll_queue_does_not_claim_task_without_capability_or_type(
    monkeypatch, tmp_path: Path
) -> None:
    queue_file = _canonical_queue(tmp_path)
    task = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "description": "untyped task",
    }
    queue_file.write_text(json.dumps(task) + "\n", encoding="utf-8")

    assert hermes.poll_queue(dry_run=False, queue_file=queue_file) == []
    assert json.loads(queue_file.read_text(encoding="utf-8")) == task


def test_poll_queue_skips_task_when_canonical_claim_rejects_it(
    monkeypatch, tmp_path: Path
) -> None:
    """A claim rejected by the canonical writer is skipped, never forced.

    Simulates the race where another agent claims or closes the task between
    Hermes' scan and the canonical claim: the lifecycle error must surface as
    a skip (no reported claim, no queue mutation by Hermes).
    """
    queue_file = _canonical_queue(tmp_path)
    task = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
    }
    queue_file.write_text(json.dumps(task) + "\n", encoding="utf-8")

    def refused_claim(*_args: object, **_kwargs: object) -> dict:
        raise lifecycle.A2ATaskLifecycleError("task task-1 is already claimed by other")

    monkeypatch.setattr(hermes, "claim_task", refused_claim)

    assert hermes.poll_queue(dry_run=False, queue_file=queue_file) == []
    assert json.loads(queue_file.read_text(encoding="utf-8")) == task


def test_poll_queue_dry_run_never_mutates(monkeypatch, tmp_path: Path) -> None:
    queue_file = _canonical_queue(tmp_path)
    task = {
        "id": "task-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
    }
    queue_file.write_text(json.dumps(task) + "\n", encoding="utf-8")

    def must_not_claim(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("dry-run must not claim")

    monkeypatch.setattr(hermes, "claim_task", must_not_claim)

    claimed = hermes.poll_queue(dry_run=True, queue_file=queue_file)

    assert [task["id"] for task in claimed] == ["task-1"]
    assert json.loads(queue_file.read_text(encoding="utf-8")) == task


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
    pointed at ``tmp_path`` so the queue path is computed exactly as it would
    be in a live cron invocation.
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


def test_hermes_polls_state_dir_preferred_root(monkeypatch, tmp_path: Path) -> None:
    """DHARMA_STATE_DIR wins over DHARMA_HOME for the queue surface.

    The canonical resolver (default_state_root) prefers DHARMA_STATE_DIR;
    producers enqueue there, so Hermes must poll there too. Passing DHARMA_HOME
    explicitly would bypass the canonical precedence and poll the wrong root.
    """
    state_dir = tmp_path / "state-pref"
    home_dir = tmp_path / "home-legacy"
    monkeypatch.setenv("DHARMA_HOME", str(home_dir))
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))
    hermes_reloaded = importlib.reload(hermes)
    monkeypatch.setattr(hermes_reloaded, "HERMES_STATE_FILE", tmp_path / "hermes_state.json")

    task = {
        "id": "task-statedir-1",
        "status": "pending",
        "claimed_by": None,
        "capability": "heartbeat",
        "description": "enqueued under DHARMA_STATE_DIR by a canonical producer",
    }
    _write_canonical_task(lifecycle.queue_path(state_dir), task)
    # A decoy task under the legacy home root must never be claimed.
    _write_canonical_task(lifecycle.queue_path(home_dir), {**task, "id": "task-decoy"})

    claimed = hermes_reloaded.poll_queue(dry_run=False)

    assert [t["id"] for t in claimed] == ["task-statedir-1"]

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
        "description": "legacy surface",
    }
    legacy_queue.write_text(json.dumps(legacy_task) + "\n", encoding="utf-8")

    assert hermes_reloaded.poll_queue(dry_run=False) == []
    assert json.loads(legacy_queue.read_text(encoding="utf-8")) == legacy_task

    importlib.reload(hermes)


def test_cron_invocation_runs_without_installed_package(tmp_path: Path) -> None:
    """The exact cron command must work from a direct checkout.

    ``python3 scripts/hermes_heartbeat_poll.py`` from the repository root puts
    ``scripts/`` (not the repo root) on sys.path, so the package import must
    bootstrap the repo root itself or the cron job dies with
    ModuleNotFoundError.
    """
    repo_root = Path(__file__).resolve().parent.parent
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(tmp_path),
        "DHARMA_HOME": str(tmp_path / ".dharma"),
    }
    result = subprocess.run(
        [sys.executable, "scripts/hermes_heartbeat_poll.py", "--dry-run"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["tasks_claimed"] == 0
