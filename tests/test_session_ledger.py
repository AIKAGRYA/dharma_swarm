"""Tests for session-scoped JSONL ledgers."""

import hashlib
import json

from dharma_swarm.episode_ledger import EpisodeEvent, project_episode
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.session_ledger import SessionLedger


def _read_episode_events(path):
    events = []
    for line in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        try:
            events.append(EpisodeEvent.from_dict(record))
        except (TypeError, ValueError):
            continue
    return events


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
    """The producer emits an episode, one attempt, then observations."""

    ledger = SessionLedger(
        base_dir=tmp_path, session_id="sess_ep", runtime_db_path=tmp_path / "runtime.db"
    )
    ledger.task_event("dispatch_assigned", task_id="t1", agent_id="a1")
    ledger.progress_event("task_started", task_id="t1", agent_id="a1")

    episode_path = tmp_path / "sess_ep" / "episode_ledger.jsonl"
    assert episode_path.exists(), "producer wrote no episode ledger"
    events = _read_episode_events(episode_path)
    state = project_episode(events)

    assert [event.event_type for event in state.events] == [
        "episode_opened",
        "attempt_started",
        "observation_recorded",
        "observation_recorded",
    ]
    assert state.events[0].attempt_id == ""
    assert state.events[1].attempt_id == ledger.attempt_id
    assert all(event.attempt_id == ledger.attempt_id for event in state.observations)
    assert [event.payload["ledger_kind"] for event in state.observations] == [
        "task",
        "progress",
    ]
    assert all(event.payload["session_event_id"] for event in state.observations)


def test_session_ledger_episode_is_stable_but_attempts_are_distinct(tmp_path):
    """Restarts reuse the episode, dedupe its open, and mint new attempts."""

    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess_st",
        "runtime_db_path": tmp_path / "runtime.db",
    }
    first = SessionLedger(**kwargs)
    second = SessionLedger(**kwargs)
    expected = f"ep_{hashlib.sha256(b'sess_st').hexdigest()[:16]}"

    assert first.episode_id == expected
    assert second.episode_id == expected
    assert first.attempt_id != second.attempt_id

    events = _read_episode_events(tmp_path / "sess_st" / "episode_ledger.jsonl")
    opened = [event for event in events if event.event_type == "episode_opened"]
    attempts = [event for event in events if event.event_type == "attempt_started"]

    assert len(opened) == 1, "restart duplicated episode_opened"
    assert opened[0].attempt_id == ""
    assert [event.attempt_id for event in attempts] == [
        first.attempt_id,
        second.attempt_id,
    ]


def test_session_ledger_sequence_uses_highest_valid_event_not_line_count(tmp_path):
    """Corrupt physical lines cannot become the next sequence authority."""

    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess_seq",
        "runtime_db_path": tmp_path / "runtime.db",
    }
    first = SessionLedger(**kwargs)
    first.task_event("dispatch_assigned", task_id="t1")

    episode_path = tmp_path / "sess_seq" / "episode_ledger.jsonl"
    with open(episode_path, "a", encoding="utf-8") as stream:
        stream.write("not-json\n")
        stream.write("null\n")

    second = SessionLedger(**kwargs)
    second.task_event("task_started", task_id="t2")

    events = _read_episode_events(episode_path)
    second_attempt = next(
        event
        for event in events
        if event.event_type == "attempt_started"
        and event.attempt_id == second.attempt_id
    )
    second_observation = next(
        event
        for event in events
        if event.event_type == "observation_recorded"
        and event.attempt_id == second.attempt_id
    )

    assert second_attempt.sequence == 3
    assert second_observation.sequence == 4


def test_session_ledger_survives_torn_utf8_tail(tmp_path):
    """A torn multi-byte UTF-8 write at the end of the episode file must not
    disable the producer: decoding happens per line, so the torn tail is
    skipped like any corrupt line and new events still persist."""

    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess_torn",
        "runtime_db_path": tmp_path / "runtime.db",
    }
    first = SessionLedger(**kwargs)
    first.task_event("dispatch_assigned", task_id="t1")

    episode_path = tmp_path / "sess_torn" / "episode_ledger.jsonl"
    with open(episode_path, "ab") as stream:
        stream.write(b'{"note": "caf\xc3')  # torn mid-codepoint, no newline

    second = SessionLedger(**kwargs)
    assert second._episode_writer is not None, "torn UTF-8 disabled the producer"
    second.task_event("task_started", task_id="t2")

    events = _read_episode_events(episode_path)
    assert any(
        event.event_type == "observation_recorded"
        and event.attempt_id == second.attempt_id
        for event in events
    ), "no observation persisted after torn-tail restart"


def test_session_ledger_counts_episode_persistence_failures(tmp_path, monkeypatch):
    """A real append failure is counted without breaking the task ledger."""

    ledger = SessionLedger(
        base_dir=tmp_path, session_id="sess_fl", runtime_db_path=tmp_path / "runtime.db"
    )
    assert ledger.episode_ledger_failures == 0

    def boom(_event):
        raise OSError("disk full")

    monkeypatch.setattr(ledger._episode_writer, "append", boom)
    ledger.task_event("dispatch_assigned", task_id="t1")

    assert ledger.episode_ledger_failures == 1
    assert (tmp_path / "sess_fl" / "task_ledger.jsonl").exists()


def test_session_ledger_counts_writer_setup_failure_once(tmp_path, monkeypatch):
    """One writer-construction failure is not recounted for every lost event."""

    def fail_writer(_path):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("dharma_swarm.session_ledger.EpisodeLedgerWriter", fail_writer)
    ledger = SessionLedger(
        base_dir=tmp_path,
        session_id="sess_setup_failure",
        runtime_db_path=tmp_path / "runtime.db",
    )

    assert ledger.episode_ledger_failures == 1
    assert ledger._episode_writer is None

    ledger.task_event("dispatch_assigned", task_id="t1")
    assert ledger.episode_ledger_failures == 1


def test_session_ledger_updates_runtime_search_index(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path,
        session_id="sess_idx",
        runtime_db_path=runtime_db,
    )

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
