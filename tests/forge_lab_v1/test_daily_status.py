from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
from pathlib import Path

from dharma_swarm.forge_lab import daily_status as daily


def _systemctl(command, **_kwargs) -> subprocess.CompletedProcess[str]:
    if daily.TIMER_UNIT in command:
        stdout = (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "UnitFileState=enabled\n"
            f"FragmentPath={command_root / daily.TIMER_UNIT}\n"
            "DropInPaths=\n"
            "TimersCalendar={ OnCalendar=*-*-* 03:35:00 UTC ; next_elapse=... }\n"
            "NextElapseUSecRealtime=Fri 2026-08-28 03:35:00 UTC\n"
            "LastTriggerUSec=Thu 2026-08-27 03:35:00 UTC\n"
        )
    else:
        stdout = (
            "LoadState=loaded\n"
            "ActiveState=inactive\n"
            f"FragmentPath={command_root / daily.SERVICE_UNIT}\n"
            "DropInPaths=\n"
            "ExecStart={ path=/root/rsi-lab/bin/rsi-unattended-explore ; "
            "argv[]=/root/rsi-lab/bin/rsi-unattended-explore --timeout-seconds 2700 ; }\n"
            "Result=success\n"
            "ExecMainCode=1\n"
            "ExecMainStatus=0\n"
        )
    return subprocess.CompletedProcess(
        args=["systemctl"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )


command_root = Path("/unused")


def test_scheduler_status_requires_exact_enabled_persistent_unit_bytes(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[2]
    unit_root = tmp_path / "systemd"
    unit_root.mkdir()
    for name in (daily.TIMER_UNIT, daily.SERVICE_UNIT):
        shutil.copyfile(repo / "scripts" / "forge_lab" / "systemd" / name, unit_root / name)

    global command_root
    command_root = unit_root.resolve()
    status = daily.scheduler_status(repo_root=repo, unit_root=unit_root, runner=_systemctl)

    assert status["ready"] is True
    assert status["calendar"] == "*-*-* 03:35:00 UTC"
    assert status["persistent"] is True
    assert all(row["bytes_match"] for row in status["units"].values())

    (unit_root / daily.TIMER_UNIT).write_text("[Timer]\nOnCalendar=hourly\n")
    drifted = daily.scheduler_status(repo_root=repo, unit_root=unit_root, runner=_systemctl)
    assert drifted["ready"] is False


def test_scheduler_status_rejects_dropins_and_failed_service(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    unit_root = tmp_path / "systemd"
    unit_root.mkdir()
    for name in (daily.TIMER_UNIT, daily.SERVICE_UNIT):
        shutil.copyfile(repo / "scripts" / "forge_lab" / "systemd" / name, unit_root / name)

    def overridden(command, **_kwargs):
        global command_root
        command_root = unit_root.resolve()
        result = _systemctl(command)
        if daily.TIMER_UNIT in command:
            result.stdout = result.stdout.replace("DropInPaths=\n", "DropInPaths=/tmp/x.conf\n")
        else:
            result.stdout = result.stdout.replace("Result=success", "Result=exit-code")
            result.stdout = result.stdout.replace("ExecMainStatus=0", "ExecMainStatus=1")
        return result

    status = daily.scheduler_status(repo_root=repo, unit_root=unit_root, runner=overridden)

    assert status["ready"] is False
    assert status["effective_timer_ok"] is False
    assert status["effective_service_ok"] is False

    def no_next(command, **_kwargs):
        global command_root
        command_root = unit_root.resolve()
        result = _systemctl(command)
        if daily.TIMER_UNIT in command:
            result.stdout = result.stdout.replace(
                "NextElapseUSecRealtime=Fri 2026-08-28 03:35:00 UTC",
                "NextElapseUSecRealtime=n/a",
            )
        return result

    no_trigger = daily.scheduler_status(
        repo_root=repo, unit_root=unit_root, runner=no_next
    )
    assert no_trigger["ready"] is False


def test_scheduler_status_fails_closed_when_systemd_is_unavailable(tmp_path: Path) -> None:
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("systemctl")

    status = daily.scheduler_status(unit_root=tmp_path, runner=missing)

    assert status["ready"] is False
    assert status["error"] == "FileNotFoundError"


def test_latest_attempt_must_be_fresh_success_and_cover_last_trigger(tmp_path: Path) -> None:
    forge_root = tmp_path / "forge_lab"
    run_id = "unattended-fixture"
    run_dir = forge_root / "unattended_explore" / "runs" / run_id
    run_dir.mkdir(parents=True)
    child = {
        "schema": "rsi_lab.unattended_child_result.v1",
        "run_id": run_id,
        "experiment_id": "experiment-fixture",
        "closeout_state": "inconclusive_low_power",
        "logical_provider_calls_used": 5,
        "logical_provider_call_limit": 5,
        "execution_shape_ok": True,
        "positive_rsi_claim": False,
    }
    child["result_digest"] = daily.content_digest(child)
    child_path = run_dir / "child_result.json"
    child_path.write_text(json.dumps(child) + "\n", encoding="utf-8")
    log_path = run_dir / "child.log"
    log_path.write_text("bounded child fixture\n", encoding="utf-8")
    closeout = {
        "kind": "run_closeout",
        "run_id": run_id,
        "at": "2026-08-27T04:00:00Z",
        "returncode": 0,
        "timed_out": False,
        "halted": False,
        "child_result": str(child_path),
        "child_result_digest": daily.content_digest(child),
        "log": str(log_path),
        "log_digest": daily._sha256(log_path),
        "explore_closeout_state": "inconclusive_low_power",
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
    }
    projection = {"valid_chain": True, "attempt": closeout}
    scheduler = {"systemd": {"LastTriggerUSec": "Thu 2026-08-27 03:35:00 UTC"}}

    ready, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )

    assert ready is True
    assert details["terminal_success"] is True

    projection["attempt"] = {
        "kind": "admission_refusal",
        "at": "2026-08-27T04:30:00Z",
        "positive_rsi_claim": False,
    }
    refused, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )
    assert refused is False
    assert details["terminal_success"] is False

    projection["attempt"] = closeout
    stale, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )
    assert stale is False
    assert details["fresh"] is False

    child_path.unlink()
    missing, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )
    assert missing is False
    assert details["child_artifact_valid"] is False
