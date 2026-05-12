"""Tests for the durable fleet state store."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.fleet.state import (
    FleetStateStore,
    FleetTaskEventType,
    FleetTaskPriority,
    FleetTaskStatus,
)


@pytest.fixture
def store(tmp_path):
    fleet_store = FleetStateStore(tmp_path / "fleet.db")
    fleet_store.init_db()
    return fleet_store


def test_schema_initializes_idempotently(tmp_path):
    db_path = tmp_path / "nested" / "fleet.db"
    store = FleetStateStore(db_path)

    store.init_db()
    store.init_db()

    with sqlite3.connect(db_path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        journal_mode = db.execute("PRAGMA journal_mode").fetchone()[0]

    assert {
        "fleet_tasks",
        "fleet_task_events",
        "fleet_task_artifacts",
    }.issubset(tables)
    assert journal_mode == "wal"


def test_create_task_persists_json_payload_and_capabilities(store):
    task = store.create_task(
        title="Run fleet dry run",
        kind="dry_run",
        description="Exercise the future control plane store.",
        payload={"repo": "dharma_swarm", "steps": ["inspect", "report"]},
        required_capabilities=["codex", "pytest"],
        priority="high",
        requested_by="operator",
        correlation_id="corr-1",
        trace_id="trace-1",
        metadata={"source": "test"},
    )

    loaded = store.get_task(task.task_id)

    assert loaded is not None
    assert loaded.title == "Run fleet dry run"
    assert loaded.kind == "dry_run"
    assert loaded.payload["steps"] == ["inspect", "report"]
    assert loaded.required_capabilities == ["codex", "pytest"]
    assert loaded.priority == FleetTaskPriority.HIGH
    assert loaded.status == FleetTaskStatus.QUEUED
    assert loaded.metadata == {"source": "test"}
    assert loaded.correlation_id == "corr-1"
    assert loaded.trace_id == "trace-1"

    events = store.list_events(task.task_id)
    assert len(events) == 1
    assert events[0].event_type == FleetTaskEventType.CREATED
    assert events[0].status == FleetTaskStatus.QUEUED


def test_idempotency_key_returns_existing_task(store):
    first = store.create_task(
        title="First title",
        idempotency_key="fleet-idem-1",
        payload={"value": 1},
    )
    second = store.create_task(
        title="Second title",
        idempotency_key="fleet-idem-1",
        payload={"value": 2},
    )

    assert second.task_id == first.task_id
    assert second.title == "First title"
    assert second.payload == {"value": 1}
    assert len(store.list_tasks()) == 1


def test_list_tasks_filters_by_status_and_assignment(store):
    first = store.create_task(
        title="first",
        assigned_node_id="node-a",
        assigned_worker_id="worker-a",
    )
    second = store.create_task(title="second", assigned_node_id="node-b")
    store.update_task_status(first.task_id, FleetTaskStatus.RUNNING)

    running = store.list_tasks(status=FleetTaskStatus.RUNNING)
    node_b = store.list_tasks(assigned_node_id="node-b")
    worker_a = store.list_tasks(assigned_worker_id="worker-a")

    assert [task.task_id for task in running] == [first.task_id]
    assert [task.task_id for task in node_b] == [second.task_id]
    assert [task.task_id for task in worker_a] == [first.task_id]


def test_update_task_status_updates_timestamps_and_appends_event(store):
    created_at = datetime(2026, 5, 11, 1, 0, tzinfo=timezone.utc)
    running_at = created_at + timedelta(minutes=5)
    failed_at = running_at + timedelta(minutes=3)
    task = store.create_task(title="status me", now=created_at)

    running = store.update_task_status(
        task.task_id,
        "running",
        message="worker started",
        node_id="node-1",
        worker_id="worker-1",
        now=running_at,
    )
    failed = store.update_task_status(
        task.task_id,
        FleetTaskStatus.FAILED,
        failed_reason="adapter exited non-zero",
        payload={"exit_code": 2},
        now=failed_at,
    )

    assert running.status == FleetTaskStatus.RUNNING
    assert running.started_at == running_at
    assert failed.status == FleetTaskStatus.FAILED
    assert failed.completed_at == failed_at
    assert failed.failed_reason == "adapter exited non-zero"
    assert failed.updated_at == failed_at

    events = store.list_events(task.task_id)
    assert [event.event_type for event in events] == [
        FleetTaskEventType.CREATED,
        FleetTaskEventType.STATUS_CHANGED,
        FleetTaskEventType.STATUS_CHANGED,
    ]
    assert events[1].message == "worker started"
    assert events[1].node_id == "node-1"
    assert events[1].worker_id == "worker-1"
    assert events[2].payload["exit_code"] == 2
    assert events[2].payload["old_status"] == "running"
    assert events[2].payload["new_status"] == "failed"


def test_append_event_preserves_order_and_filters_by_task(store):
    task = store.create_task(title="ordered events")
    first_at = datetime(2026, 5, 11, 2, 0, tzinfo=timezone.utc)
    second_at = first_at + timedelta(seconds=1)

    first = store.append_event(
        task_id=task.task_id,
        message="first",
        payload={"n": 1},
        severity="debug",
        created_at=first_at,
    )
    second = store.append_event(
        task_id=task.task_id,
        message="second",
        payload={"n": 2},
        severity="warning",
        created_at=second_at,
    )

    events = store.list_events(
        task.task_id,
        event_type=FleetTaskEventType.EVENT,
    )

    assert [event.event_id for event in events] == [first.event_id, second.event_id]
    assert [event.payload["n"] for event in events] == [1, 2]
    assert events[0].severity == "debug"
    assert events[1].severity == "warning"


def test_record_artifact_links_to_task_and_round_trips_metadata(store):
    task = store.create_task(title="artifact task")

    artifact = store.record_artifact(
        task_id=task.task_id,
        node_id="node-1",
        worker_id="worker-1",
        name="report",
        kind="markdown",
        uri="file:///tmp/report.md",
        sha256="abc123",
        size_bytes=128,
        metadata={"content_type": "text/markdown"},
    )

    artifacts = store.list_artifacts(task.task_id)

    assert [item.artifact_id for item in artifacts] == [artifact.artifact_id]
    assert artifacts[0].task_id == task.task_id
    assert artifacts[0].node_id == "node-1"
    assert artifacts[0].worker_id == "worker-1"
    assert artifacts[0].metadata["content_type"] == "text/markdown"


def test_lease_fields_can_be_set_and_cleared(store):
    task = store.create_task(title="lease task", metadata={"keep": "me"})
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    leased = store.set_task_lease(
        task.task_id,
        lease_owner="node-1:worker-1",
        lease_expires_at=expires_at,
    )
    cleared = store.clear_task_lease(task.task_id)

    assert leased.lease_owner == "node-1:worker-1"
    assert leased.lease_expires_at == expires_at
    assert leased.metadata == {"keep": "me"}
    assert cleared.lease_owner is None
    assert cleared.lease_expires_at is None
    assert cleared.metadata == {"keep": "me"}

    lease_events = [
        event.event_type
        for event in store.list_events(task.task_id)
        if event.event_type in {
            FleetTaskEventType.LEASE_SET,
            FleetTaskEventType.LEASE_CLEARED,
        }
    ]
    assert lease_events == [
        FleetTaskEventType.LEASE_SET,
        FleetTaskEventType.LEASE_CLEARED,
    ]


def test_invalid_status_priority_approval_and_severity_are_rejected(store):
    task = store.create_task(title="validation task")

    with pytest.raises(ValueError, match="Invalid fleet task status"):
        store.update_task_status(task.task_id, "teleported")

    with pytest.raises(ValueError, match="Invalid fleet task priority"):
        store.create_task(title="bad priority", priority="impossible")

    with pytest.raises(ValueError, match="Invalid fleet approval status"):
        store.create_task(title="bad approval", approval_status="maybe")

    with pytest.raises(ValueError, match="Invalid fleet event severity"):
        store.append_event(task_id=task.task_id, severity="loud")


def test_missing_task_references_raise_key_error(store):
    with pytest.raises(KeyError, match="not found"):
        store.append_event(task_id="missing")

    with pytest.raises(KeyError, match="not found"):
        store.record_artifact(
            task_id="missing",
            name="report",
            kind="markdown",
            uri="file:///tmp/report.md",
        )

    with pytest.raises(KeyError, match="not found"):
        store.update_task_status("missing", FleetTaskStatus.RUNNING)
