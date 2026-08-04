"""loop_liveness.json must never say "running" for a dead owner.

Negative control for the 2026-07-25..08-01 outage: `dgc status` printed
"20 running" from a 7-day-old liveness file whose owning pid (67078) was
long dead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.runtime_artifacts import loop_liveness_summary as _loop_liveness_summary
from dharma_swarm.terminal_commands import _status_helpers


def test_status_helpers_resolves_the_canonical_summary() -> None:
    """`dgc status` must keep reaching the same function after the move.

    The helper lives in runtime_artifacts (next to dgc_health_snapshot_summary,
    the other artifact-plus-pid-probe reader); _status_helpers imports it. If
    that wiring breaks, the status lane silently loses the pid probe, so pin it.
    """
    assert _status_helpers._loop_liveness_summary is _loop_liveness_summary


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


def test_loop_liveness_summary_marks_dead_owner(tmp_path: Path) -> None:
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    _write_liveness(liveness_path, pid=67078, running=20)

    summary = _loop_liveness_summary(liveness_path, pid_alive=lambda pid: False)

    assert summary is not None
    assert summary["pid"] == 67078
    assert summary["pid_alive"] is False
    assert summary["running"] == 20


def test_loop_liveness_summary_confirms_live_owner(tmp_path: Path) -> None:
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    _write_liveness(liveness_path, pid=4242, running=19)

    summary = _loop_liveness_summary(liveness_path, pid_alive=lambda pid: pid == 4242)

    assert summary is not None
    assert summary["pid_alive"] is True


def test_loop_liveness_summary_marks_recycled_owner_dead(
    monkeypatch, tmp_path: Path
) -> None:
    """A pid recycled onto an unrelated process is not an owner."""
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    _write_liveness(liveness_path, pid=67078, running=20)

    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_alive", lambda pid: True
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_process_identity.pid_command",
        lambda pid, timeout=5.0: "/Applications/Safari.app/Contents/MacOS/Safari",
    )

    summary = _loop_liveness_summary(liveness_path)

    assert summary is not None
    assert summary["pid_alive"] is False


@pytest.mark.parametrize("raw_pid", [None, "67078", 67078.0, True])
def test_loop_liveness_summary_cannot_verify_non_integer_owner(
    tmp_path: Path, raw_pid: object
) -> None:
    """Missing/null/string/float/bool pids are unverifiable, never alive."""
    liveness_path = tmp_path / "ops" / "loop_liveness.json"
    liveness_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "running": ["loop_a", "loop_b"],
        "abandoned": [],
        "restart_counts": {},
    }
    if raw_pid is not None:
        payload["pid"] = raw_pid
    liveness_path.write_text(json.dumps(payload), encoding="utf-8")

    summary = _loop_liveness_summary(liveness_path)

    assert summary is not None
    assert summary["pid_alive"] is None


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


def test_status_render_refuses_unverifiable_running_claim(monkeypatch, capsys) -> None:
    """pid_alive=None means the owner was never verified — not "running"."""
    from dharma_swarm.terminal_commands import status as status_module

    data = {
        "pulse": {"last": None, "count": 0, "source": None},
        "gates_today": 0,
        "loop_liveness": {
            "running": 20,
            "abandoned": [],
            "hot_restarts": {},
            "age_min": 10000,
            "pid": None,
            "pid_alive": None,
        },
    }
    monkeypatch.setattr(status_module, "_build_status_data", lambda: data)

    status_module.cmd_status(as_json=False)

    out = capsys.readouterr().out
    assert "Daemon loops: UNVERIFIED" in out
    assert "do not trust it" in out
    assert "Daemon loops: 20 running" not in out
