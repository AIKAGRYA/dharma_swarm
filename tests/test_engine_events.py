"""Tests for dharma_swarm/engine/events.py — canonical event schema."""

from __future__ import annotations

from datetime import datetime, timezone

from dharma_swarm.engine.events import CanonicalEvent, EventType


class TestEventType:
    def test_all_values_are_strings(self) -> None:
        for member in EventType:
            assert isinstance(member.value, str)

    def test_session_lifecycle_events(self) -> None:
        assert EventType.SESSION_START.value == "session_start"
        assert EventType.SESSION_END.value == "session_end"

    def test_task_events(self) -> None:
        assert EventType.TASK_ASSIGNED.value == "task_assigned"
        assert EventType.TASK_COMPLETED.value == "task_completed"
        assert EventType.TASK_FAILED.value == "task_failed"

    def test_artifact_events(self) -> None:
        assert EventType.ARTIFACT_CREATED.value == "artifact_created"
        assert EventType.ARTIFACT_VERIFIED.value == "artifact_verified"

    def test_inter_loop_signals(self) -> None:
        assert EventType.FITNESS_IMPROVED.value == "fitness_improved"
        assert EventType.ANOMALY_DETECTED.value == "anomaly_detected"
        assert EventType.CASCADE_EIGENFORM_DISTANCE.value == "cascade_eigenform_distance"


class TestCanonicalEvent:
    def test_create_minimal(self) -> None:
        event = CanonicalEvent(event_type=EventType.TASK_ASSIGNED)
        assert event.event_type == EventType.TASK_ASSIGNED
        assert event.event_id != ""
        assert isinstance(event.timestamp, datetime)

    def test_create_full(self) -> None:
        event = CanonicalEvent(
            event_type=EventType.ARTIFACT_CREATED,
            source_agent="devin",
            target_agent="mike",
            session_id="sess-001",
            artifact_id="art-001",
            payload={"file": "test.py"},
            metadata={"priority": "high"},
        )
        assert event.source_agent == "devin"
        assert event.target_agent == "mike"
        assert event.artifact_id == "art-001"
        assert event.payload["file"] == "test.py"

    def test_to_dict(self) -> None:
        event = CanonicalEvent(
            event_type=EventType.TASK_COMPLETED,
            source_agent="agent-1",
            session_id="s-123",
        )
        d = event.to_dict()
        assert d["event_type"] == "task_completed"
        assert d["source_agent"] == "agent-1"
        assert d["session_id"] == "s-123"
        assert "timestamp" in d
        assert "event_id" in d

    def test_from_dict(self) -> None:
        data = {
            "event_type": "artifact_verified",
            "timestamp": "2026-06-02T10:00:00+00:00",
            "event_id": "abc123",
            "source_agent": "reviewer",
            "target_agent": "builder",
            "session_id": "s-456",
            "artifact_id": "art-789",
            "payload": {"status": "approved"},
            "metadata": {"ci_run": 42},
        }
        event = CanonicalEvent.from_dict(data)
        assert event.event_type == EventType.ARTIFACT_VERIFIED
        assert event.event_id == "abc123"
        assert event.source_agent == "reviewer"
        assert event.artifact_id == "art-789"
        assert event.payload["status"] == "approved"

    def test_roundtrip(self) -> None:
        original = CanonicalEvent(
            event_type=EventType.EVAL_COMPLETED,
            source_agent="grader",
            payload={"score": 0.95},
        )
        d = original.to_dict()
        restored = CanonicalEvent.from_dict(d)
        assert restored.event_type == original.event_type
        assert restored.source_agent == original.source_agent
        assert restored.payload == original.payload
        assert restored.event_id == original.event_id

    def test_from_dict_missing_fields(self) -> None:
        data = {"event_type": "session_start"}
        event = CanonicalEvent.from_dict(data)
        assert event.event_type == EventType.SESSION_START
        assert event.source_agent == ""
        assert event.artifact_id is None

    def test_timestamp_is_utc(self) -> None:
        event = CanonicalEvent(event_type=EventType.SESSION_START)
        assert event.timestamp.tzinfo == timezone.utc
