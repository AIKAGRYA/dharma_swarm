"""Tests for session-scoped JSONL ledgers."""

import hashlib
import json
import sqlite3

import pytest

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


def test_new_nested_session_fsyncs_base_directory(tmp_path, monkeypatch):
    base_dir = tmp_path / "nested" / "ledgers"
    synced = []

    def record_fsync(path):
        assert path.is_dir()
        synced.append(path)

    monkeypatch.setattr(
        "dharma_swarm.session_ledger._fsync_directory",
        record_fsync,
    )
    kwargs = {
        "base_dir": base_dir,
        "session_id": "sess_nested",
        "runtime_db_path": tmp_path / "runtime.db",
    }
    SessionLedger(**kwargs)

    assert synced == [tmp_path, tmp_path / "nested", base_dir]
    assert (base_dir / "sess_nested").is_dir()
    synced.clear()
    SessionLedger(**kwargs)
    assert synced == []


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


def test_constructor_drains_every_backlog_page_before_new_attempt(
    tmp_path,
    monkeypatch,
):
    runtime_db = tmp_path / "runtime.db"
    session_id = "sess-paged-backlog"
    session_dir = tmp_path / session_id
    episode_path = session_dir / "episode_ledger.jsonl"
    episode_id = f"ep_{hashlib.sha256(session_id.encode()).hexdigest()[:16]}"
    destination_id = (
        "dst_"
        + hashlib.sha256(
            str(episode_path.resolve(strict=False)).encode()
        ).hexdigest()[:32]
    )
    store = RuntimeStateStore(runtime_db)
    for index in range(5):
        store.enqueue_episode_event_sync(
            delivery_key=f"backlog:{index}",
            destination_id=destination_id,
            episode_id=episode_id,
            attempt_id=f"at-backlog-{index}",
            event_type="attempt_started",
            payload={"index": index},
        )

    original_list = RuntimeStateStore.list_pending_episode_events_sync
    page_calls = 0

    def two_at_a_time(store_self, **kwargs):
        nonlocal page_calls
        page_calls += 1
        return original_list(store_self, limit=2, **kwargs)

    monkeypatch.setattr(
        RuntimeStateStore,
        "list_pending_episode_events_sync",
        two_at_a_time,
    )
    ledger = SessionLedger(
        base_dir=tmp_path,
        session_id=session_id,
        runtime_db_path=runtime_db,
    )

    events = _read_episode_events(episode_path)
    assert page_calls >= 5
    assert any(
        event.event_type == "attempt_started"
        and event.attempt_id == ledger.attempt_id
        for event in events
    )
    assert store.list_pending_episode_events_sync(
        episode_id=episode_id,
        destination_id=destination_id,
    ) == []


@pytest.mark.parametrize("failed_event_type", ["episode_opened", "attempt_started"])
def test_constructor_aborts_when_required_lifecycle_staging_fails(
    tmp_path,
    monkeypatch,
    failed_event_type,
):
    original_enqueue = RuntimeStateStore.enqueue_episode_event_sync

    def fail_selected(store_self, **kwargs):
        if kwargs["event_type"] == failed_event_type:
            raise sqlite3.OperationalError("transient lifecycle staging failure")
        return original_enqueue(store_self, **kwargs)

    monkeypatch.setattr(
        RuntimeStateStore,
        "enqueue_episode_event_sync",
        fail_selected,
    )
    with pytest.raises(
        RuntimeError,
        match=f"failed to stage required {failed_event_type} delivery",
    ):
        SessionLedger(
            base_dir=tmp_path,
            session_id=f"sess-stage-{failed_event_type}",
            runtime_db_path=tmp_path / f"{failed_event_type}.db",
        )


def test_same_session_in_new_destination_receives_stable_open(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    first = SessionLedger(
        base_dir=tmp_path / "first",
        session_id="sess-destination-move",
        runtime_db_path=runtime_db,
    )
    second = SessionLedger(
        base_dir=tmp_path / "second",
        session_id="sess-destination-move",
        runtime_db_path=runtime_db,
    )

    second_events = _read_episode_events(second.episode_path)
    assert first.episode_destination_id != second.episode_destination_id
    assert second_events[0].event_type == "episode_opened"
    assert second_events[1].event_type == "attempt_started"
    assert (
        RuntimeStateStore(runtime_db)
        .get_episode_outbox_sync(
            f"episode:{second.episode_id}:opened",
            destination_id=second.episode_destination_id,
        )
        .acked_at
        is not None
    )


def test_deleted_destination_requeues_stable_open_before_new_attempt(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess-destination-recreated",
        "runtime_db_path": runtime_db,
    }
    first = SessionLedger(**kwargs)
    first.episode_path.unlink()
    second = SessionLedger(**kwargs)

    recreated = _read_episode_events(second.episode_path)
    assert second.episode_destination_id == first.episode_destination_id
    assert [event.event_type for event in recreated] == [
        "episode_opened",
        "attempt_started",
        "attempt_started",
    ]
    assert [event.attempt_id for event in recreated[1:]] == [
        first.attempt_id,
        second.attempt_id,
    ]


def test_recreated_destination_durably_opens_before_later_backlog_ack(
    tmp_path,
    monkeypatch,
):
    runtime_db = tmp_path / "runtime.db"
    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess-open-before-backlog",
        "runtime_db_path": runtime_db,
    }
    first = SessionLedger(**kwargs)
    backlog_key = "session-event:sevt-crash-gap:observation"
    store = RuntimeStateStore(runtime_db)
    store.enqueue_episode_event_sync(
        delivery_key=backlog_key,
        destination_id=first.episode_destination_id,
        episode_id=first.episode_id,
        attempt_id=first.attempt_id,
        event_type="observation_recorded",
        payload={"session_event_id": "sevt-crash-gap"},
    )
    first.episode_path.unlink()
    original_ack = RuntimeStateStore.ack_episode_event_sync
    acked_keys = []

    class SimulatedCrash(BaseException):
        pass

    def crash_after_backlog_ack(store_self, delivery_key, **ack):
        result = original_ack(store_self, delivery_key, **ack)
        acked_keys.append(delivery_key)
        if delivery_key == backlog_key:
            raise SimulatedCrash
        return result

    monkeypatch.setattr(
        RuntimeStateStore,
        "ack_episode_event_sync",
        crash_after_backlog_ack,
    )
    with pytest.raises(SimulatedCrash):
        SessionLedger(**kwargs)

    opened_key = f"episode:{first.episode_id}:opened"
    first_attempt_key = f"attempt:{first.attempt_id}:started"
    recreated = _read_episode_events(first.episode_path)
    assert [event.event_type for event in recreated] == [
        "episode_opened",
        "attempt_started",
        "observation_recorded",
    ]
    assert recreated[1].attempt_id == first.attempt_id
    assert recreated[2].attempt_id == first.attempt_id
    assert acked_keys == [opened_key, first_attempt_key, backlog_key]
    assert store.get_episode_outbox_sync(
        opened_key,
        destination_id=first.episode_destination_id,
    ).acked_at is not None
    assert store.get_episode_outbox_sync(
        first_attempt_key,
        destination_id=first.episode_destination_id,
    ).acked_at is not None
    assert store.get_episode_outbox_sync(
        backlog_key,
        destination_id=first.episode_destination_id,
    ).acked_at is not None


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
    assert not hasattr(second, "_episode_sequence")
    assert second._episode_writer.rehydration_passes == 1


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

    def boom(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(ledger._episode_writer, "append_delivery", boom)
    ledger.task_event("dispatch_assigned", task_id="t1")

    assert ledger.episode_ledger_failures == 1
    assert (tmp_path / "sess_fl" / "task_ledger.jsonl").exists()


def test_episode_append_failure_replays_durable_observation_on_restart(
    tmp_path,
    monkeypatch,
):
    runtime_db = tmp_path / "runtime.db"
    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess_replay",
        "runtime_db_path": runtime_db,
    }
    first = SessionLedger(**kwargs)

    def fail_append(**_kwargs):
        raise OSError("transient episode append failure")

    monkeypatch.setattr(first._episode_writer, "append_delivery", fail_append)
    first.task_event("dispatch_assigned", task_id="t-replay")
    task_row = json.loads(
        (tmp_path / "sess_replay" / "task_ledger.jsonl").read_text().strip()
    )
    delivery_key = f"session-event:{task_row['event_id']}:observation"
    store = RuntimeStateStore(runtime_db)

    assert len(store.search_session_events_sync("dispatch_assigned")) == 1
    assert [
        item.delivery_key
        for item in store.list_pending_episode_events_sync(
            episode_id=first.episode_id
        )
    ] == [delivery_key]

    SessionLedger(**kwargs)
    events = _read_episode_events(
        tmp_path / "sess_replay" / "episode_ledger.jsonl"
    )
    observations = [
        event
        for event in events
        if event.payload.get("session_event_id") == task_row["event_id"]
    ]
    delivered = store.get_episode_outbox_sync(delivery_key)

    assert len(observations) == 1
    assert delivered is not None
    assert delivered.acked_at is not None
    assert delivered.episode_event_id == observations[0].event_id


def test_crash_before_outbox_ack_replays_without_duplicate_file_event(
    tmp_path,
    monkeypatch,
):
    runtime_db = tmp_path / "runtime.db"
    kwargs = {
        "base_dir": tmp_path,
        "session_id": "sess_crash_ack",
        "runtime_db_path": runtime_db,
    }
    first = SessionLedger(**kwargs)

    def fail_ack(*_args, **_kwargs):
        raise RuntimeError("simulated crash before ack")

    monkeypatch.setattr(first._runtime_state, "ack_episode_event_sync", fail_ack)
    first.progress_event("task_started", task_id="t-crash")
    progress_row = json.loads(
        (tmp_path / "sess_crash_ack" / "progress_ledger.jsonl").read_text().strip()
    )
    delivery_key = f"session-event:{progress_row['event_id']}:observation"
    episode_path = tmp_path / "sess_crash_ack" / "episode_ledger.jsonl"
    before = [
        event
        for event in _read_episode_events(episode_path)
        if event.payload.get("session_event_id") == progress_row["event_id"]
    ]

    assert len(before) == 1
    assert RuntimeStateStore(runtime_db).get_episode_outbox_sync(
        delivery_key
    ).acked_at is None

    SessionLedger(**kwargs)
    after = [
        event
        for event in _read_episode_events(episode_path)
        if event.payload.get("session_event_id") == progress_row["event_id"]
    ]
    delivered = RuntimeStateStore(runtime_db).get_episode_outbox_sync(delivery_key)

    assert len(after) == 1
    assert after[0].event_id == before[0].event_id
    assert delivered is not None
    assert delivered.acked_at is not None
    assert delivered.episode_event_id == before[0].event_id


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
