"""Tests for foundry kill-switch wiring."""

from __future__ import annotations

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
