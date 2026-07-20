"""Focused tests for the headless canonical session lifecycle recorder."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dharma_swarm.operator_core.session_lifecycle import SessionLifecycleRecorder
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.tui.engine.events import (
    SessionEnd,
    SessionStart,
    TextComplete,
    ToolProgress,
    UsageReport,
    UserPrompt,
)


class RecordingSessionStore(SessionStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root=root)
        self.calls: list[tuple[str, str]] = []
        self.finalize_calls = 0

    def create_session(self, **kwargs: object) -> str:
        self.calls.append(("create", str(kwargs.get("session_id") or "generated")))
        return super().create_session(**kwargs)  # type: ignore[arg-type]

    def append_event(self, session_id: str, event, *, strip_raw: bool = True) -> None:
        self.calls.append(("append", event.type))
        super().append_event(session_id, event, strip_raw=strip_raw)

    def finalize_session(self, session_id: str, **kwargs: object) -> None:
        self.finalize_calls += 1
        self.calls.append(("finalize", str(kwargs["status"])))
        super().finalize_session(session_id, **kwargs)  # type: ignore[arg-type]


def _begin(
    tmp_path: Path,
    *,
    parent_session_id: str | None = None,
) -> tuple[RecordingSessionStore, SessionLifecycleRecorder]:
    store = RecordingSessionStore(tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-turn-1",
        provider_id="claude",
        model_id="provisional-model",
        cwd="/repo",
        prompt="Keep this exact operator prompt.\nAnd its newline.",
        parent_session_id=parent_session_id,
    )
    return store, recorder


def test_begin_creates_before_recording_typed_operator_prompt(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path, parent_session_id="dgc-parent-1")

    assert recorder.session_id == "dgc-turn-1"
    assert store.calls[:2] == [("create", "dgc-turn-1"), ("append", "user_prompt")]
    transcript = store.load_transcript(recorder.session_id)
    assert len(transcript) == 1
    assert isinstance(transcript[0], UserPrompt)
    assert transcript[0].provider_id == ""
    assert transcript[0].content == "Keep this exact operator prompt.\nAnd its newline."
    meta = store.load_meta(recorder.session_id)
    assert meta["parent_session_id"] == "dgc-parent-1"
    assert meta["provider_session_id"] is None


def test_session_start_binds_native_id_and_actual_winning_route(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path, parent_session_id="dgc-parent-1")

    accepted = recorder.record(
        SessionStart(
            session_id="provider-native-id-must-not-be-canonical",
            provider_id="openrouter",
            model="winning/model",
            provider_session_id="provider-native-resume-77",
        )
    )

    assert isinstance(accepted, SessionStart)
    assert accepted.session_id == recorder.session_id
    assert recorder.provider_id == "openrouter"
    assert recorder.model_id == "winning/model"
    assert recorder.provider_session_id == "provider-native-resume-77"
    meta = store.load_meta(recorder.session_id)
    assert meta["provider_id"] == "openrouter"
    assert meta["model_id"] == "winning/model"
    assert meta["provider_session_id"] == "provider-native-resume-77"
    assert meta["parent_session_id"] == "dgc-parent-1"


def test_completed_turn_accumulates_usage_and_finalizes_once(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)
    recorder.record(
        SessionStart(
            provider_id="claude",
            model="actual-model",
            provider_session_id="native-1",
        )
    )
    recorder.record(
        UsageReport(
            provider_id="claude",
            input_tokens=10,
            output_tokens=4,
            cache_read_tokens=3,
            thinking_tokens=2,
            total_cost_usd=0.02,
        )
    )
    recorder.record(
        UsageReport(
            provider_id="claude",
            input_tokens=7,
            output_tokens=6,
            cache_write_tokens=5,
            total_cost_usd=0.03,
        )
    )
    recorder.record(TextComplete(provider_id="claude", role="assistant", content="part one"))
    recorder.record(TextComplete(provider_id="claude", role="assistant", content="part two"))

    accepted_end = recorder.record(SessionEnd(provider_id="claude", success=True))
    duplicate_end = recorder.record(SessionEnd(provider_id="claude", success=False))

    assert isinstance(accepted_end, SessionEnd)
    assert duplicate_end is None
    assert recorder.status == "completed"
    assert recorder.is_finalized
    assert recorder.usage.input_tokens == 17
    assert recorder.usage.output_tokens == 10
    assert recorder.usage.cache_read_tokens == 3
    assert recorder.usage.cache_write_tokens == 5
    assert recorder.usage.thinking_tokens == 2
    assert recorder.usage.total_cost_usd == pytest.approx(0.05)
    assert store.finalize_calls == 1

    meta = store.load_meta(recorder.session_id)
    assert meta["status"] == "completed"
    assert meta["total_turns"] == 1
    assert meta["total_input_tokens"] == 17
    assert meta["total_output_tokens"] == 10
    assert meta["total_cost_usd"] == pytest.approx(0.05)
    assert sum(isinstance(event, SessionEnd) for event in store.load_transcript(recorder.session_id)) == 1
    replay_ok, issues = store.verify_session_replay(recorder.session_id)
    assert replay_ok, issues


def test_bind_route_supports_buffered_fallback_before_projection(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)

    assert recorder.bind_route(provider_id="openrouter", model_id="fallback/model")
    assert not recorder.bind_route(provider_id="openrouter", model_id="fallback/model")
    recorder.record(
        SessionStart(
            provider_id="openrouter",
            model="fallback/model",
            provider_session_id="fallback-native",
        )
    )
    recorder.record(SessionEnd(provider_id="openrouter", success=True))

    assert store.load_meta(recorder.session_id)["provider_id"] == "openrouter"
    assert store.load_meta(recorder.session_id)["model_id"] == "fallback/model"


def test_bind_route_stays_coherent_when_snapshot_append_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, recorder = _begin(tmp_path)

    def fail_snapshot(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "_append_session_snapshot", fail_snapshot)

    with caplog.at_level("WARNING"):
        assert recorder.bind_route(provider_id="openrouter", model_id="fallback/model")

    meta = store.load_meta(recorder.session_id)
    assert (recorder.provider_id, recorder.model_id) == (
        meta["provider_id"],
        meta["model_id"],
    )
    assert store._last_snapshot_failure == (
        recorder.session_id,
        "route_rebound",
        "OSError",
    )
    assert "session route rebound snapshot failed" in caplog.text


def test_exception_before_provider_start_records_honest_failed_terminal(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)

    terminal = recorder.fail(RuntimeError("provider exploded"))
    duplicate = recorder.fail("late duplicate")

    assert isinstance(terminal, SessionEnd)
    assert terminal.session_id == recorder.session_id
    assert terminal.success is False
    assert terminal.error_code == "runner_exception"
    assert terminal.error_message == "RuntimeError: provider exploded"
    assert duplicate is None
    assert recorder.status == "failed"
    assert store.finalize_calls == 1
    transcript = store.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == ["user_prompt", "session_end"]
    assert store.load_meta(recorder.session_id)["status"] == "failed"


def test_cancel_wins_race_and_suppresses_late_provider_terminal(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)
    recorder.record(SessionStart(provider_id="claude", model="actual-model"))

    cancelled = recorder.cancel()
    late_provider_end = recorder.record(SessionEnd(provider_id="claude", success=True))
    duplicate_cancel = recorder.cancel()

    assert isinstance(cancelled, SessionEnd)
    assert cancelled.error_code == "cancelled"
    assert late_provider_end is None
    assert duplicate_cancel is None
    assert recorder.status == "cancelled"
    assert store.finalize_calls == 1
    transcript = store.load_transcript(recorder.session_id)
    assert sum(isinstance(event, SessionEnd) for event in transcript) == 1
    assert store.load_meta(recorder.session_id)["status"] == "cancelled"


def test_record_normalizes_event_session_and_rejects_second_prompt(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)

    accepted = recorder.record(
        ToolProgress(
            session_id="provider-leaked-id",
            provider_id="claude",
            tool_call_id="tool-1",
            tool_name="shell",
            elapsed_seconds=1.5,
        )
    )

    assert isinstance(accepted, ToolProgress)
    assert accepted.session_id == recorder.session_id
    assert accepted.tool_call_id == "tool-1"
    with pytest.raises(ValueError, match="single canonical user prompt"):
        recorder.record(UserPrompt(content="duplicate"))


def test_restart_recovers_previous_bridge_turn_once_as_failed(tmp_path: Path) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-orphaned-turn",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="this turn will be interrupted",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    recorder.record(
        SessionStart(
            provider_id="claude",
            model="claude-test",
            provider_session_id="native-orphan",
        )
    )

    reopened = SessionStore(root=tmp_path)
    recovered = reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    )

    assert recovered == ["dgc-orphaned-turn"]
    meta = reopened.load_meta(recorder.session_id)
    assert meta["status"] == "failed"
    assert meta["runtime_owner_id"] == "terminal-bridge:previous"
    assert meta["runtime_owner_pid"] == os.getpid()
    terminal_events = [
        event
        for event in reopened.load_transcript(recorder.session_id)
        if isinstance(event, SessionEnd)
    ]
    assert len(terminal_events) == 1
    assert terminal_events[0].success is False
    assert terminal_events[0].error_code == "bridge_interrupted"
    assert reopened.verify_session_replay(recorder.session_id) == (True, [])

    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == []
    assert sum(
        isinstance(event, SessionEnd)
        for event in reopened.load_transcript(recorder.session_id)
    ) == 1


def test_restart_recovers_old_ownerless_empty_row_after_grace(tmp_path: Path) -> None:
    store = SessionStore(root=tmp_path)
    session_id = store.create_session(
        session_id="legacy-empty-running",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
    )

    recovered = store.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
        legacy_owner_grace_seconds=0,
    )

    assert recovered == [session_id]
    assert store.load_meta(session_id)["status"] == "failed"
    [terminal] = store.load_transcript(session_id)
    assert isinstance(terminal, SessionEnd)
    assert terminal.success is False
    assert terminal.error_code == "bridge_interrupted"
    assert store.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
        legacy_owner_grace_seconds=0,
    ) == []


def test_restart_repairs_metadata_after_real_terminal_without_duplicate(
    tmp_path: Path,
) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-terminal-before-metadata-crash",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="provider will finish before metadata is written",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    store.append_event(
        recorder.session_id,
        SessionStart(
            session_id=recorder.session_id,
            provider_id="claude",
            model="claude-test",
        ),
    )
    store.append_event(
        recorder.session_id,
        SessionEnd(
            session_id=recorder.session_id,
            provider_id="claude",
            success=True,
        ),
    )
    assert store.load_meta(recorder.session_id)["status"] == "running"

    assert store.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == [recorder.session_id]

    assert store.load_meta(recorder.session_id)["status"] == "completed"
    assert sum(
        isinstance(event, SessionEnd)
        for event in store.load_transcript(recorder.session_id)
    ) == 1
    assert store.verify_session_replay(recorder.session_id) == (True, [])


def test_restart_leaves_turn_owned_by_other_live_process_running(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from dharma_swarm.operator_core import session_store as session_store_module

    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-live-elsewhere",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="still running elsewhere",
        runtime_owner_id="terminal-bridge:other-live",
        runtime_owner_pid=os.getpid() + 1000,
    )
    monkeypatch.setattr(session_store_module, "_pid_is_alive", lambda _pid: True)

    assert store.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == []
    assert store.load_meta(recorder.session_id)["status"] == "running"
    assert [event.type for event in store.load_transcript(recorder.session_id)] == [
        "user_prompt"
    ]
