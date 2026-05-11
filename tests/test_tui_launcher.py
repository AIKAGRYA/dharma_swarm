"""Tests for dharma_swarm.tui.tui_launcher — TUI launch with fallback chain."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from dharma_swarm.tui.tui_launcher import launch_tui


# ---------------------------------------------------------------------------
# launch_tui fallback behaviour
# ---------------------------------------------------------------------------


def test_launch_tui_new_tui_success():
    """When the new TUI's run() works, launch_tui should call it and return."""
    fake_run = MagicMock()

    with patch.dict(sys.modules, {"dharma_swarm.tui": MagicMock(run=fake_run)}):
        launch_tui()

    fake_run.assert_called_once()


def test_launch_tui_falls_back_to_legacy():
    """When the new TUI raises, launch_tui should try tui_legacy.DGCApp."""
    mock_app_instance = MagicMock()
    mock_dgc_app = MagicMock(return_value=mock_app_instance)
    fake_legacy = MagicMock(DGCApp=mock_dgc_app)

    def bad_run():
        raise RuntimeError("new TUI broken")

    fake_tui = MagicMock(run=bad_run)

    with patch.dict(
        sys.modules,
        {
            "dharma_swarm.tui": fake_tui,
            "dharma_swarm.tui_legacy": fake_legacy,
        },
    ):
        launch_tui()

    mock_app_instance.run.assert_called_once()


def test_launch_tui_exits_when_all_fail():
    """When both new and legacy TUI fail, launch_tui should sys.exit(1)."""

    def bad_run():
        raise RuntimeError("new TUI broken")

    fake_tui = MagicMock(run=bad_run)

    with patch.dict(
        sys.modules,
        {
            "dharma_swarm.tui": fake_tui,
            "dharma_swarm.tui_legacy": None,
        },
    ):
        with pytest.raises(SystemExit) as exc_info:
            launch_tui()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Module-level import sanity
# ---------------------------------------------------------------------------


def test_tui_launcher_importable():
    """tui_launcher module should be importable without side effects."""
    from dharma_swarm.tui import tui_launcher

    assert hasattr(tui_launcher, "launch_tui")
    assert callable(tui_launcher.launch_tui)
