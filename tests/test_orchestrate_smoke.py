"""Smoke tests for orchestrate imports and basic instantiation (no event loop)."""
import tempfile
from pathlib import Path


def test_swarm_manager_import():
    from dharma_swarm.swarm import SwarmManager
    assert SwarmManager is not None


def test_daemon_config_import():
    from dharma_swarm.swarm import DaemonConfig
    assert DaemonConfig is not None


def test_daemon_config_quiet_hours_has_static_floor_by_default():
    from dharma_swarm.swarm import DaemonConfig
    cfg = DaemonConfig()
    assert cfg.quiet_hours == [2, 3, 4, 5]


def test_swarm_manager_instantiates_with_temp_dir():
    from dharma_swarm.swarm import SwarmManager
    with tempfile.TemporaryDirectory() as tmp:
        manager = SwarmManager(state_dir=tmp)
        assert manager is not None


def test_orchestrator_import():
    from dharma_swarm.orchestrator import Orchestrator
    assert Orchestrator is not None


def test_task_board_import():
    from dharma_swarm.task_board import TaskBoard
    assert TaskBoard is not None
