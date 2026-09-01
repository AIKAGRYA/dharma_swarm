"""Focused tests for the headless canonical session lifecycle recorder."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import subprocess
from threading import Barrier

import pytest

from dharma_swarm.operator_core import build_session_detail
from dharma_swarm.operator_core.session_lifecycle import SessionLifecycleRecorder
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.tui.engine.events import (
    ContextReceipt,
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


class ContendedRecoverySessionStore(SessionStore):
    """Rendezvous independent stores immediately before recovery locking."""

    def __init__(self, root: Path, barrier: Barrier) -> None:
        super().__init__(root=root)
        self._barrier = barrier
        self.recovery_lock_attempted = False

    @contextmanager
    def session_recovery_lock(self, session_id: str):
        self.recovery_lock_attempted = True
        self._barrier.wait(timeout=5)
        with super().session_recovery_lock(session_id):
            yield


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
    assert meta["git_branch"] == ""


def test_begin_records_the_linked_worktree_branch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    linked = tmp_path / "linked"
    repo.mkdir()
    (repo / "tracked.txt").write_text("stable\n", encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "tracked.txt"],
        [
            "git",
            "-c",
            "user.name=Helm Test",
            "-c",
            "user.email=helm@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
    ):
        subprocess.run(command, cwd=repo, check=True)
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "codex/helm-test", str(linked)],
        cwd=repo,
        check=True,
    )

    store = RecordingSessionStore(tmp_path / "sessions")
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-linked-worktree",
        provider_id="claude",
        model_id="claude-sonnet-5",
        cwd=str(linked),
        prompt="Observe the branch without changing it.",
    )

    meta = store.load_meta(recorder.session_id)
    assert meta["git_branch"] == "codex/helm-test"


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


def test_context_receipt_is_typed_durable_and_session_owned(tmp_path: Path) -> None:
    store, recorder = _begin(tmp_path)

    accepted = recorder.record(
        ContextReceipt(
            session_id="provider-must-not-own-this-id",
            provider_id="fallback",
            model_id="winner-model",
            source_epoch="sha256:epoch",
            context_digest="",
            disposition="not_attached_fallback",
            authority="NONE",
            lane_outcome="completed",
        )
    )

    assert isinstance(accepted, ContextReceipt)
    assert accepted.session_id == recorder.session_id
    [persisted] = [
        event
        for event in store.load_transcript(recorder.session_id)
        if isinstance(event, ContextReceipt)
    ]
    assert persisted == accepted
    detail = build_session_detail(store, recorder.session_id)
    assert "context_receipt" in detail["compaction_preview"]["protected_event_types"]
    receipt_envelope = next(
        event
        for event in detail["recent_events"]
        if event["event_type"] == "context_receipt"
    )
    assert receipt_envelope["source"] == "runtime"


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


def test_restart_recovers_staged_context_boundary_before_interrupted_terminal(
    tmp_path: Path,
) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-orphaned-context-boundary",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="this provider boundary will be interrupted",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    staged = recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="fallback",
            model_id="fallback-model",
            source_epoch="sha256:epoch",
            context_digest="sha256:digest",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )
    assert staged.session_id == recorder.session_id
    assert "pending_context_receipt" in store.load_meta(recorder.session_id)

    reopened = SessionStore(root=tmp_path)
    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == [recorder.session_id]

    transcript = reopened.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    [receipt] = [event for event in transcript if isinstance(event, ContextReceipt)]
    assert receipt.provider_id == "fallback"
    assert receipt.model_id == "fallback-model"
    assert receipt.disposition == "offered_unconfirmed"
    assert receipt.lane_outcome == "interrupted"
    assert receipt.boundary_timestamp == 123.0
    assert receipt.timestamp == receipt.boundary_timestamp
    assert receipt.outcome_timestamp > receipt.boundary_timestamp
    meta = reopened.load_meta(recorder.session_id)
    assert meta["status"] == "failed"
    assert meta["provider_id"] == "fallback"
    assert meta["model_id"] == "fallback-model"
    assert "pending_context_receipt" not in meta
    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == []
    assert sum(
        isinstance(event, ContextReceipt)
        for event in reopened.load_transcript(recorder.session_id)
    ) == 1


def test_concurrent_recovery_serializes_one_interrupted_receipt_and_terminal(
    tmp_path: Path,
) -> None:
    seed = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        seed,
        session_id="dgc-concurrent-orphan-recovery",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="recover this context boundary exactly once",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )

    barrier = Barrier(2)
    contenders = [
        ContendedRecoverySessionStore(tmp_path, barrier),
        ContendedRecoverySessionStore(tmp_path, barrier),
    ]

    def recover(index: int) -> list[str]:
        return contenders[index].recover_orphaned_sessions(
            cwd="/repo",
            active_owner_id=f"terminal-bridge:replacement-{index}",
            active_owner_pid=os.getpid(),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recover, range(2)))

    assert all(store.recovery_lock_attempted for store in contenders)
    assert sorted(len(result) for result in results) == [0, 1]
    transcript = seed.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    assert sum(isinstance(event, ContextReceipt) for event in transcript) == 1
    assert sum(isinstance(event, SessionEnd) for event in transcript) == 1
    assert seed.load_meta(recorder.session_id)["status"] == "failed"


def test_unexpected_terminal_seals_staged_context_before_session_end(
    tmp_path: Path,
) -> None:
    store, recorder = _begin(tmp_path)
    recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )

    terminal = recorder.fail("unexpected bridge failure")

    assert isinstance(terminal, SessionEnd)
    transcript = store.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    [receipt] = [event for event in transcript if isinstance(event, ContextReceipt)]
    assert receipt.lane_outcome == "interrupted"
    assert receipt.timestamp == receipt.boundary_timestamp
    assert receipt.outcome_timestamp >= receipt.boundary_timestamp
    assert "pending_context_receipt" not in store.load_meta(recorder.session_id)


def test_restart_clears_staging_after_final_receipt_without_duplicate(
    tmp_path: Path,
) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-receipt-before-clear-crash",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="receipt append wins before staged metadata cleanup",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    staged = recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )
    store.append_event(
        recorder.session_id,
        replace(staged, outcome_timestamp=456.0, lane_outcome="failed"),
    )
    assert "pending_context_receipt" in store.load_meta(recorder.session_id)

    reopened = SessionStore(root=tmp_path)
    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == [recorder.session_id]

    transcript = reopened.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    assert sum(isinstance(event, ContextReceipt) for event in transcript) == 1
    assert "pending_context_receipt" not in reopened.load_meta(recorder.session_id)


def test_context_receipt_write_then_touch_error_stays_single_and_accepted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, recorder = _begin(tmp_path)
    staged = recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )
    original_touch = store._touch_session
    failed_once = False

    def fail_after_first_transcript_write(session_id: str) -> None:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("simulated post-append metadata failure")
        original_touch(session_id)

    monkeypatch.setattr(store, "_touch_session", fail_after_first_transcript_write)
    accepted = recorder.record(
        replace(
            staged,
            outcome_timestamp=456.0,
            lane_outcome="failed",
        )
    )
    terminal = recorder.fail("provider failed")

    assert isinstance(accepted, ContextReceipt)
    assert isinstance(terminal, SessionEnd)
    transcript = store.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    assert sum(isinstance(event, ContextReceipt) for event in transcript) == 1
    assert recorder.take_auto_context_receipt_for_emission() is None


def test_restart_discovers_staged_session_when_index_is_truncated(
    tmp_path: Path,
) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-index-truncated-context",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="recover from derived index loss",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )
    (tmp_path / "index.json").write_text('{"schema_version":', encoding="utf-8")

    reopened = SessionStore(root=tmp_path)
    assert [
        entry["session_id"] for entry in reopened.list_sessions()
    ] == [recorder.session_id]
    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == [recorder.session_id]
    transcript = reopened.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    assert "pending_context_receipt" not in reopened.load_meta(recorder.session_id)


def test_restart_separates_partial_transcript_tail_before_recovered_receipt(
    tmp_path: Path,
) -> None:
    store = SessionStore(root=tmp_path)
    recorder = SessionLifecycleRecorder.begin(
        store,
        session_id="dgc-partial-context-tail",
        provider_id="claude",
        model_id="claude-test",
        cwd="/repo",
        prompt="recover a partial context receipt write",
        runtime_owner_id="terminal-bridge:previous",
        runtime_owner_pid=os.getpid(),
    )
    recorder.stage_context_receipt(
        ContextReceipt(
            timestamp=123.0,
            boundary_timestamp=123.0,
            provider_id="claude",
            model_id="claude-test",
            disposition="offered_unconfirmed",
            authority="NONE",
            lane_outcome="pending",
        )
    )
    transcript_path = tmp_path / recorder.session_id / "transcript.jsonl"
    with open(transcript_path, "ab") as handle:
        handle.write(b'{"type":"context_receipt"')

    reopened = SessionStore(root=tmp_path)
    assert reopened.recover_orphaned_sessions(
        cwd="/repo",
        active_owner_id="terminal-bridge:replacement",
        active_owner_pid=os.getpid(),
    ) == [recorder.session_id]

    transcript = reopened.load_transcript(recorder.session_id)
    assert [event.type for event in transcript] == [
        "user_prompt",
        "context_receipt",
        "session_end",
    ]
    raw_lines = transcript_path.read_bytes().splitlines()
    assert raw_lines[1] == b'{"type":"context_receipt"'
    assert len(raw_lines) == 4
    assert "pending_context_receipt" not in reopened.load_meta(recorder.session_id)


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
