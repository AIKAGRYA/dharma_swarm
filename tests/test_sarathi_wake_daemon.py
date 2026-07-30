"""Standing wake-loop runtime wrapper (PR-S5): dial-gated, kill-honoring, thin.

The daemon binds the merged organs into a governed loop so the dial drives
real work — but it never claims liveness (Gate-10), honors the safety envelope
of the organs it composes, carries budget across restarts, dedups against all
of its own tasks, retains per-run evidence, and exits nonzero on error cycles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "runtime"))

import sarathi_wake_daemon as daemon  # noqa: E402


def _run(tmp_path: Path, cycles: int = 2, backlog: str = "", extra=None) -> tuple[int, dict]:
    argv = [
        "--cycles", str(cycles),
        "--state-root", str(tmp_path),
        "--agents-root", str(tmp_path / "agents"),  # isolate kill/persistence
        "--json",
    ]
    if backlog:
        argv += ["--backlog", backlog]
    argv += extra or []
    code = daemon.main(argv)
    report = json.loads((tmp_path / "sarathi" / "wake_daemon_report.json").read_text())
    return code, report


def test_propose_default_runs_but_dispatches_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DGC_SARATHI_AUTONOMY", raising=False)
    code, report = _run(tmp_path, cycles=2)
    assert code == 0
    assert report["autonomy_level"] == "propose"
    assert report["wake_loop_active"] is False
    assert report["statuses"] == ["ran", "ran"]
    tasks_dir = tmp_path / "sarathi" / "mailbox" / "tasks"
    assert not tasks_dir.exists() or not list(tasks_dir.glob("*.json"))
    briefs = list((tmp_path / "sarathi" / "briefs").rglob("brief_cycle_*.md"))
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
    tasks = list((tmp_path / "sarathi" / "mailbox" / "tasks").glob("*.json"))
    assert len(tasks) == 1


def test_kill_switch_halts_the_loop(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "propose")
    from dharma_swarm import holon_killswitch

    holon_killswitch.request_kill("sarathi", agents_root=tmp_path / "agents")
    code, report = _run(tmp_path, cycles=5)
    assert code == 0  # governed halt is healthy
    assert report["statuses"] == ["halted:kill"]
    assert report["cycles_run"] == 1


def test_monotonic_run_ids_retain_evidence(tmp_path, monkeypatch) -> None:
    """Codex/Greptile P1: a scheduler re-invoking the daemon must not overwrite
    the prior run's brief; each run gets its own retained directory + report."""
    monkeypatch.delenv("DGC_SARATHI_AUTONOMY", raising=False)
    _run(tmp_path, cycles=1)
    _run(tmp_path, cycles=1)
    run_dirs = sorted((tmp_path / "sarathi" / "briefs").glob("run_*"))
    assert [p.name for p in run_dirs] == ["run_0001", "run_0002"]
    reports = sorted((tmp_path / "sarathi").glob("wake_daemon_report_run_*.json"))
    assert len(reports) == 2


def test_run_id_reservation_is_atomic_against_collision(tmp_path) -> None:
    """Greptile P1: a pre-existing run dir must not be reused — reserve_run
    reserves the next free id via atomic mkdir, so concurrent daemons can never
    select the same id and overwrite evidence."""
    sarathi_root = tmp_path / "sarathi"
    (sarathi_root / "briefs" / "run_0001").mkdir(parents=True)  # taken
    run_id, run_dir = daemon.reserve_run(sarathi_root)
    assert run_id == 2 and run_dir.name == "run_0002"
    # A second reservation skips the one just reserved.
    run_id2, run_dir2 = daemon.reserve_run(sarathi_root)
    assert run_id2 == 3 and run_dir2 != run_dir


def test_budget_cap_carried_and_enforced(tmp_path, monkeypatch) -> None:
    """Codex/Greptile P1: a real cumulative spend snapshot (not hardcoded 0)
    reaches the guard, so the cap halts."""
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "propose")
    code, report = _run(
        tmp_path, cycles=3, extra=["--spent-usd", "0.10", "--cap-usd", "0.10"]
    )
    assert code == 0  # budget halt is governed
    assert report["statuses"] == ["halted:budget"]
    assert report["spent_usd"] == 0.10
    # The ledger persists across restarts.
    assert (tmp_path / "sarathi" / "spent_usd").exists()


def test_dedup_suppresses_completed_backlog_item(tmp_path, monkeypatch) -> None:
    """Codex/Greptile P1: a responded task's summary must still suppress
    re-planning the same backlog item."""
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "dispatch")
    from dharma_swarm.roaming_mailbox import RoamingMailbox

    mailbox = RoamingMailbox(queue_root=tmp_path / "sarathi" / "mailbox")
    task = mailbox.enqueue_task(
        recipient="hermes-m5", sender="sarathi",
        summary="extend the chamber gym battery", body="x",
    )
    mailbox.claim_task(task.task_id, claimed_by="hermes-m5")
    mailbox.respond_to_task(
        task_id=task.task_id, responder="hermes-m5", summary="ok", body="ok"
    )
    backlog = tmp_path / "backlog.json"
    backlog.write_text(
        json.dumps([{"kind": "build", "summary": "extend the chamber gym battery",
                     "body": "add one scenario"}])
    )
    code, report = _run(tmp_path, cycles=1, backlog=str(backlog))
    assert code == 0
    # No NEW task for the already-completed summary — only the original exists.
    tasks = list((tmp_path / "sarathi" / "mailbox" / "tasks").glob("*.json"))
    assert len(tasks) == 1


def test_error_cycle_exits_nonzero(tmp_path, monkeypatch) -> None:
    """Codex P2: an error/unverified cycle must produce a nonzero exit so a
    service manager alerts; governed kill/budget halts stay 0."""
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "propose")

    async def _boom(*args, **kwargs):
        return {"status": "halted:error", "error": "boot pack failed"}

    monkeypatch.setattr(daemon, "holon_wake_cycle", _boom)
    code, report = _run(tmp_path, cycles=1)
    assert code == 1
    assert report["had_error"] is True
    assert report["statuses"] == ["halted:error"]


def test_closeback_records_bind_into_the_report(tmp_path, monkeypatch) -> None:
    """Codex P2: cycles bind durable closeback linkage. It is folded into the
    per-run report (a JSON artifact already emitted, rewritten per cycle) rather
    than a separate ``closeback_ledger.jsonl`` — the dedicated store raised the
    store-inventory census ratchet and tripped the memory-writer sentinel for a
    non-memory operational append (CI on PR #1170)."""
    monkeypatch.setenv("DGC_SARATHI_AUTONOMY", "dispatch")
    backlog = tmp_path / "backlog.json"
    backlog.write_text(
        json.dumps([{"kind": "build", "summary": "one build", "body": "b"}])
    )
    code, report = _run(tmp_path, cycles=1, backlog=str(backlog))
    assert code == 0
    assert report["closeback"] and report["closeback"][0]["outcomes"]
    # No separate ledger store is introduced (census/sentinel stay clean).
    assert not (tmp_path / "sarathi" / "closeback_ledger.jsonl").exists()


def test_concurrent_daemon_halts_budget_contended(tmp_path) -> None:
    """Greptile P1 security on PR #1170: while one daemon holds the advisory
    budget flock, a second sharing ``--state-root`` must NOT read the same spend
    snapshot and double-authorize. It halts ``budget-contended`` (exit 0,
    governed) and dispatches nothing."""
    import fcntl
    import os

    sarathi_root = tmp_path / "sarathi"
    sarathi_root.mkdir(parents=True)
    held = os.open(str(sarathi_root / "spend.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(held, fcntl.LOCK_EX)
    try:
        code, report = _run(tmp_path, cycles=3)
        assert code == 0  # a governed halt is healthy
        assert report["statuses"] == ["halted:budget-contended"]
        assert report["cycles_run"] == 0
        # Nothing dispatched: no per-cycle brief for the contended run.
        briefs = list((tmp_path / "sarathi" / "briefs").rglob("brief_cycle_*.md"))
        assert briefs == []
    finally:
        fcntl.flock(held, fcntl.LOCK_UN)
        os.close(held)
