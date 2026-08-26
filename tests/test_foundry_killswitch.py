"""Tests for foundry kill-switch wiring."""

from __future__ import annotations

import json

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
