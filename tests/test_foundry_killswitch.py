"""Tests for foundry kill-switch wiring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.foundry import killswitch
from dharma_swarm.holon_killswitch import request_kill


def test_not_stopped_by_default(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    assert killswitch.is_stopped(agents_root=agents, state_root=state) is False
    killswitch.check(agents_root=agents, state_root=state)  # no raise


def test_stop_file_stops(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    state.mkdir()
    (state / "STOP").write_text("operator halt")
    assert killswitch.is_stopped(agents_root=agents, state_root=state)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(agents_root=agents, state_root=state)


def test_holon_kill_stops(tmp_path):
    agents = tmp_path / "agents"
    state = tmp_path / "state"
    request_kill(killswitch.FOUNDRY_HOLON, reason="guardian tripped", agents_root=agents)
    assert killswitch.is_stopped(agents_root=agents, state_root=state)
    reason = killswitch.stop_reason(agents_root=agents, state_root=state)
    assert "guardian tripped" in reason


def test_terminal_kill_is_persistent_and_first_cause_wins(tmp_path):
    path = killswitch.persist_terminal_kill(
        tmp_path,
        category="replication_failure",
        reason="seed replay mismatch",
        evidence={"target_id": "t"},
    )
    first = path.read_bytes()
    killswitch.persist_terminal_kill(
        tmp_path,
        category="later_failure",
        reason="must not overwrite",
    )
    assert path.read_bytes() == first
    assert killswitch.has_terminal_kill(tmp_path)
    assert killswitch.is_stopped(state_root=tmp_path)
    payload = json.loads(path.read_text())
    assert payload["category"] == "replication_failure"
    assert "seed replay mismatch" in killswitch.stop_reason(state_root=tmp_path)


def test_terminal_kill_falls_back_when_evidence_is_unserializable(tmp_path):
    path = killswitch.persist_terminal_kill(
        tmp_path,
        category="invalid_evidence",
        reason="diagnostics must not veto the stop",
        evidence={"bad": object()},
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["category"] == "invalid_evidence"
    assert payload["reason"] == "diagnostics must not veto the stop"
    assert payload["evidence"] == {}
    assert payload["evidence_serialization_error"] == "TypeError"
    assert killswitch.is_stopped(state_root=tmp_path)

    killswitch.persist_terminal_kill(
        tmp_path,
        category="later_cause",
        reason="must not replace fallback first cause",
    )
    assert path.read_bytes() == (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def test_terminal_kill_fsyncs_file_and_parent_directory(tmp_path, monkeypatch):
    fsync_calls: list[int] = []
    monkeypatch.setattr(killswitch.os, "fsync", fsync_calls.append)
    killswitch.persist_terminal_kill(
        tmp_path,
        category="durability_check",
        reason="sync marker and directory entry",
    )
    assert len(fsync_calls) == 2


def test_dangling_terminal_kill_symlink_fails_closed_and_is_recoverable(tmp_path):
    marker = killswitch.terminal_kill_file(tmp_path)
    marker.symlink_to(tmp_path / "missing-terminal-kill-target")

    assert not marker.exists()
    assert killswitch.has_terminal_kill(tmp_path)
    assert killswitch.is_stopped(state_root=tmp_path)
    assert "corrupt_kill_marker" in killswitch.stop_reason(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)

    # Persistence never follows or silently clobbers a corrupt directory entry.
    killswitch.persist_terminal_kill(
        tmp_path,
        category="later_failure",
        reason="must remain stopped",
    )
    assert marker.is_symlink()
    assert killswitch.is_stopped(state_root=tmp_path)

    # An operator can remove the visibly corrupt sentinel and record a valid cause.
    marker.unlink()
    killswitch.persist_terminal_kill(
        tmp_path,
        category="operator_recovered",
        reason="valid terminal marker restored",
    )
    assert killswitch.read_terminal_kill(tmp_path)["category"] == "operator_recovered"


def test_non_regular_terminal_kill_marker_fails_closed(tmp_path):
    killswitch.terminal_kill_file(tmp_path).mkdir()
    assert killswitch.has_terminal_kill(tmp_path)
    assert killswitch.is_stopped(state_root=tmp_path)
    assert "not a regular file" in killswitch.stop_reason(state_root=tmp_path)


@pytest.mark.parametrize("contents", ["not json", "[]"])
def test_corrupt_terminal_marker_fails_closed(tmp_path, contents):
    tmp_path.mkdir(exist_ok=True)
    killswitch.terminal_kill_file(tmp_path).write_text(contents, encoding="utf-8")
    assert killswitch.is_stopped(state_root=tmp_path)
    assert "corrupt_kill_marker" in killswitch.stop_reason(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)


@pytest.mark.parametrize("name", ["QUARANTINE.json", "QUARANTINE"])
def test_evidence_quarantine_stops_until_operator_review(tmp_path, name):
    marker = tmp_path / name
    marker.write_text("quarantined", encoding="utf-8")
    assert killswitch.is_stopped(state_root=tmp_path)
    assert str(marker) in killswitch.stop_reason(state_root=tmp_path)


@pytest.mark.parametrize("name", ["QUARANTINE.json", "QUARANTINE"])
def test_dangling_quarantine_marker_still_stops(tmp_path, name):
    marker = tmp_path / name
    marker.symlink_to(tmp_path / "missing-quarantine-evidence")
    assert not marker.exists()
    assert killswitch.is_stopped(state_root=tmp_path)
    assert str(marker) in killswitch.stop_reason(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)


def test_non_regular_quarantine_marker_still_stops(tmp_path):
    marker = tmp_path / "QUARANTINE.json"
    marker.mkdir()
    assert killswitch.is_stopped(state_root=tmp_path)
    assert str(marker) in killswitch.stop_reason(state_root=tmp_path)


def test_uninspectable_quarantine_marker_fails_closed(tmp_path, monkeypatch):
    marker = tmp_path / "QUARANTINE.json"
    original_lstat = Path.lstat

    def guarded_lstat(path):
        if path == marker:
            raise PermissionError("simulated unreadable quarantine marker")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", guarded_lstat)
    assert killswitch.is_stopped(state_root=tmp_path)
    assert str(marker) in killswitch.stop_reason(state_root=tmp_path)
    with pytest.raises(killswitch.FoundryStopped):
        killswitch.check(state_root=tmp_path)
