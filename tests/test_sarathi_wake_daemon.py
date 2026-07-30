"""Standing wake-loop runtime wrapper (PR-S5): dial-gated, kill-honoring, thin.

The daemon binds the merged organs into a governed loop so the dial drives
real work — but it never claims liveness (Gate-10) and honors the safety
envelope of the organs it composes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import sarathi_wake_daemon as daemon  # noqa: E402


def _run(tmp_path: Path, cycles: int = 2, backlog: str = "") -> tuple[int, dict]:
    argv = ["--cycles", str(cycles), "--state-root", str(tmp_path), "--json"]
    if backlog:
        argv += ["--backlog", backlog]
    code = daemon.main(argv)
    report = json.loads(
        (tmp_path / "sarathi" / "wake_daemon_report.json").read_text()
    )
    return code, report


def test_propose_default_runs_but_dispatches_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DGC_SARATHI_AUTONOMY", raising=False)
    code, report = _run(tmp_path, cycles=2)
    assert code == 0
    assert report["autonomy_level"] == "propose"
    assert report["wake_loop_active"] is False  # never claimed here
    assert report["statuses"] == ["ran", "ran"]
    # Propose holds dispatch: the shared mailbox stays empty.
    mailbox_dir = tmp_path / "sarathi" / "mailbox" / "tasks"
    assert not mailbox_dir.exists() or not list(mailbox_dir.glob("*.json"))
    briefs = sorted((tmp_path / "sarathi" / "briefs").glob("brief_cycle_*.md"))
    assert len(briefs) == 2


def test_invalid_dial_fails_closed_to_shadow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "fulll")  # typo -> shadow
    code, report = _run(tmp_path, cycles=1)
    assert code == 0
    assert report["autonomy_level"] == "shadow"


def test_dispatch_dial_enqueues_leased_work(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "dispatch")
    backlog = tmp_path / "backlog.json"
    backlog.write_text(
        json.dumps(
            [{"kind": "build", "summary": "extend the chamber gym battery",
              "body": "add one scenario"}]
        )
    )
    code, report = _run(tmp_path, cycles=1, backlog=str(backlog))
    assert code == 0
    assert report["autonomy_level"] == "dispatch"
    # A leased build reaches the mailbox as a real task at dispatch level.
    tasks = list((tmp_path / "sarathi" / "mailbox" / "tasks").glob("*.json"))
    assert len(tasks) == 1


def test_kill_switch_halts_the_loop(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "propose")
    from dharma_swarm import holon_killswitch

    holon_killswitch.request_kill("sarathi", agents_root=tmp_path / "agents")
    code, report = _run(tmp_path, cycles=5)
    assert code == 0
    # The kill-check runs before work every cycle; the loop stops immediately.
    assert report["statuses"] == ["halted:kill"]
    assert report["cycles_run"] == 1
