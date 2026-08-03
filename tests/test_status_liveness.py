"""loop_liveness.json must never say "running" for a dead owner.

Negative control for the 2026-07-25..08-01 outage: `dgc status` printed
"20 running" from a 7-day-old liveness file whose owning pid (67078) was
long dead.
"""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.terminal_commands._status_helpers import _loop_liveness_summary


def _write_liveness(path: Path, *, pid: int, running: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pid": pid,
                "running": [f"loop_{i}" for i in range(running)],
                "abandoned": [],
                "restart_counts": {},
            }
        ),
        encoding="utf-8",
    )


def test_loop_liveness_summary_marks_dead_owner(monkeypatch, tmp_path: Path) -> None:
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    _write_liveness(liveness_path, pid=67078, running=20)

    monkeypatch.setattr(
        "dharma_swarm.terminal_commands._status_helpers._pid_alive",
        lambda pid: False,
    )

    summary = _loop_liveness_summary(liveness_path)

    assert summary is not None
    assert summary["pid"] == 67078
    assert summary["pid_alive"] is False
    assert summary["running"] == 20


def test_loop_liveness_summary_confirms_live_owner(monkeypatch, tmp_path: Path) -> None:
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    _write_liveness(liveness_path, pid=4242, running=19)

    monkeypatch.setattr(
        "dharma_swarm.terminal_commands._status_helpers._pid_alive",
        lambda pid: pid == 4242,
    )

    summary = _loop_liveness_summary(liveness_path)

    assert summary is not None
    assert summary["pid_alive"] is True


def test_loop_liveness_summary_absent_file(tmp_path: Path) -> None:
    assert _loop_liveness_summary(tmp_path / "ops" / "loop_liveness.json") is None


def test_status_render_refuses_dead_running_claim(monkeypatch, capsys) -> None:
    """cmd_status must print DEAD, not "20 running", for a dead owner."""
    from dharma_swarm.terminal_commands import status as status_module

    data = {
        "pulse": {"last": None, "count": 0, "source": None},
        "gates_today": 0,
        "loop_liveness": {
            "running": 20,
            "abandoned": [],
            "hot_restarts": {},
            "age_min": 10000,
            "pid": 67078,
            "pid_alive": False,
        },
    }
    monkeypatch.setattr(status_module, "_build_status_data", lambda: data)

    status_module.cmd_status(as_json=False)

    out = capsys.readouterr().out
    assert "Daemon loops: DEAD" in out
    assert "do not trust it" in out
    assert "67078" in out
