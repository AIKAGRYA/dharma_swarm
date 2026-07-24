"""Tests for session-scoped JSONL ledgers."""

import hashlib
import json

from dharma_swarm.episode_ledger import EpisodeEvent, project_episode
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.session_ledger import SessionLedger


def test_session_ledger_writes_task_and_progress(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path,
        session_id="sess_a",
        runtime_db_path=runtime_db,
    )

    ledger.task_event("dispatch_assigned", task_id="t1", agent_id="a1")
    ledger.progress_event("task_started", task_id="t1", agent_id="a1")

    task_path = tmp_path / "sess_a" / "task_ledger.jsonl"
    progress_path = tmp_path / "sess_a" / "progress_ledger.jsonl"
    assert task_path.exists()
    assert progress_path.exists()

    task_row = json.loads(task_path.read_text().strip())
    progress_row = json.loads(progress_path.read_text().strip())
    assert task_row["event"] == "dispatch_assigned"
    assert progress_row["event"] == "task_started"
    assert task_row["session_id"] == "sess_a"
    assert progress_row["session_id"] == "sess_a"


def test_session_ledger_uses_env_dir_and_session(tmp_path, monkeypatch):
    monkeypatch.setenv("DGC_LEDGER_DIR", str(tmp_path))
    monkeypatch.setenv("DGC_SESSION_ID", "sess_env")
    ledger = SessionLedger(runtime_db_path=tmp_path / "runtime.db")
    ledger.task_event("dispatch_blocked", task_id="t2", reason="blocked")

    task_path = tmp_path / "sess_env" / "task_ledger.jsonl"
    assert task_path.exists()


def test_session_ledger_produces_validated_episode_events(tmp_path):
    """B1 producer slice: the session ledger emits Episode Ledger events —
    episode_opened at init, observation_recorded per task/progress event —
    all validating through EpisodeEvent.from_dict (versioned schema)."""
    ledger = SessionLedger(
        base_dir=tmp_path, session_id="sess_ep", runtime_db_path=tmp_path / "runtime.db"
    )
    ledger.task_event("dispatch_assigned", task_id="t1", agent_id="a1")
    ledger.progress_event("task_started", task_id="t1", agent_id="a1")

    episode_path = tmp_path / "sess_ep" / "episode_ledger.jsonl"
    assert episode_path.exists(), "producer wrote no episode ledger"
    events = [
        EpisodeEvent.from_dict(json.loads(line))
        for line in episode_path.read_text().splitlines()
    ]
    state = project_episode(events)
    assert [e.event_type for e in state.events][0] == "episode_opened"
    assert len(state.observations) == 2
    kinds = [e.payload["ledger_kind"] for e in state.observations]
    assert kinds == ["task", "progress"]
    assert all(e.payload["session_event_id"] for e in state.observations)


def test_session_ledger_episode_id_is_stable_and_opened_dedupes(tmp_path):
    """Same session -> same episode_id (derived from session_id, not random),
    and a restart re-emitting episode_opened dedups instead of duplicating."""
    kwargs = dict(
        base_dir=tmp_path, session_id="sess_st", runtime_db_path=tmp_path / "runtime.db"
    )
    first = SessionLedger(**kwargs)
    second = SessionLedger(**kwargs)
    expected = f"ep_{hashlib.sha256(b'sess_st').hexdigest()[:16]}"
    assert first.episode_id == expected
    assert second.episode_id == expected

    episode_path = tmp_path / "sess_st" / "episode_ledger.jsonl"
    opened = [
        json.loads(line)
        for line in episode_path.read_text().splitlines()
        if json.loads(line)["event_type"] == "episode_opened"
    ]
    assert len(opened) == 1, "restart duplicated episode_opened"


def test_session_ledger_counts_episode_persistence_failures(tmp_path, monkeypatch):
    """Episode persistence failures never break orchestration but are COUNTED,
    not swallowed — the unversioned ledger's silent-except pattern ends here."""
    ledger = SessionLedger(
        base_dir=tmp_path, session_id="sess_fl", runtime_db_path=tmp_path / "runtime.db"
    )
    assert ledger.episode_ledger_failures == 0

    def boom(_event):
        raise OSError("disk full")

    monkeypatch.setattr(ledger._episode_writer, "append", boom)
    ledger.task_event("dispatch_assigned", task_id="t1")
    assert ledger.episode_ledger_failures == 1
    task_path = tmp_path / "sess_fl" / "task_ledger.jsonl"
    assert task_path.exists(), "episode failure broke the task ledger write"


def test_session_ledger_updates_runtime_search_index(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    ledger = SessionLedger(base_dir=tmp_path, session_id="sess_idx", runtime_db_path=runtime_db)

    ledger.progress_event(
        "task_failed",
        task_id="t9",
        agent_id="worker-loop",
        failure_signature="provider_timeout",
        summary="provider timeout on fallback lane",
    )

    hits = RuntimeStateStore(runtime_db).search_session_events_sync("provider timeout")

    assert len(hits) == 1
    assert hits[0].session_id == "sess_idx"
    assert hits[0].ledger_kind == "progress"
    assert hits[0].event_name == "task_failed"
