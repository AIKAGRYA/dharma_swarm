from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
import subprocess
from pathlib import Path

from dharma_swarm.forge_lab import daily_status as daily
from dharma_swarm.forge_lab import unattended_explore as unattended


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


def test_last_attempt_resolves_exact_referenced_prior_admission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    forge_root = tmp_path / "state" / ".dharma" / "forge_lab"
    receipts = forge_root / "unattended_explore" / "receipts.jsonl"
    monkeypatch.setattr(daily, "forge_state_root", lambda: forge_root)
    admitted = unattended.append_chain(
        receipts,
        {"kind": "run_admitted", "run_id": "run-a"},
        schema=daily.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    unattended.append_chain(
        receipts,
        {"kind": "run_admitted", "run_id": "run-b"},
        schema=daily.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )
    closeout = unattended.append_chain(
        receipts,
        {
            "kind": "run_closeout",
            "run_id": "run-a",
            "admission_receipt_digest": admitted["receipt_digest"],
        },
        schema=daily.RECEIPT_SCHEMA,
        digest_field="receipt_digest",
    )

    projection = daily._last_unattended_attempt()

    assert projection["valid_chain"] is True
    assert projection["attempt"] == closeout
    assert projection["admission"] == admitted


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
    forge_root = tmp_path / "state" / ".dharma" / "forge_lab"
    run_id = "unattended-fixture"
    run_dir = forge_root / "unattended_explore" / "runs" / run_id
    run_dir.mkdir(parents=True)
    scratch_root = (
        tmp_path
        / "state"
        / ".dharma"
        / "evolution_worktrees"
        / "unattended"
        / run_id
    )
    marker_digest = "sha256:" + "c" * 64
    root_identity = {"device": 1, "inode": 2}

    def scratch_proof(operation: str, inventory):
        proof = {
            "schema": "rsi_lab.unattended_scratch_proof.v1",
            "operation": operation,
            "ok": True,
            "scratch_root": str(scratch_root),
            "run_id": run_id,
            "root_identity": root_identity,
            "marker_digest": marker_digest,
            "inventory": inventory,
            "code": None,
            "message": None,
        }
        proof["proof_digest"] = daily.content_digest(proof)
        return proof

    attestation = scratch_proof("attest", None)
    experiment_id = "experiment-fixture"
    child = {
        "schema": "rsi_lab.unattended_child_result.v1",
        "run_id": run_id,
        "experiment_id": experiment_id,
        "closeout_state": "inconclusive_low_power",
        "logical_provider_calls_used": 5,
        "logical_provider_call_limit": 5,
        "logical_provider_calls_by_role": {
            "candidate_generation": 2,
            "mutation": 1,
            "candidate_solver": 1,
            "candidate_verifier": 1,
        },
        "expected_provider_calls_by_role": {
            "candidate_generation": 2,
            "mutation": 1,
            "candidate_solver": 1,
            "candidate_verifier": 1,
        },
        "execution_shape_ok": True,
        "scratch_cleanup_ok": True,
        "scratch_custody_attestation": attestation,
        "experiment_closeout": {
            "schema": "forge_lab.closeout.v0",
            "experiment_id": experiment_id,
            "closeout_state": "inconclusive_low_power",
            "scratch_worktree": {
                "path": str(scratch_root / experiment_id / "repo"),
                "state": "removed",
                "removed": True,
            },
            "stats": {
                "counters": {"graded": 2, "paired_controls": 1, "blocked": 0}
            },
        },
        "epistemic_modality": "EXPLORE_ONLY",
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
        "admission_receipt_digest": "sha256:" + "e" * 64,
        "reservation_digest": "sha256:" + "f" * 64,
        "at": "2026-08-27T04:00:00Z",
        "returncode": 0,
        "timed_out": False,
        "halted": False,
        "child_result": str(child_path),
        "child_result_digest": daily.content_digest(child),
        "log": str(log_path),
        "log_digest": daily._sha256(log_path),
        "experiment_id": experiment_id,
        "explore_closeout_state": "inconclusive_low_power",
        "logical_provider_calls_used": 5,
        "scratch_custody": {
            "create": scratch_proof("create", None),
            "cleanup": scratch_proof(
                "cleanup",
                {
                    "entries": 1,
                    "directories": 0,
                    "regular_files": 1,
                    "symlinks": 0,
                    "bytes": 1,
                    "inventory_digest": "sha256:" + "d" * 64,
                    "run_id": run_id,
                },
            ),
        },
        "scratch_cleanup_ok": True,
        "epistemic_modality": "EXPLORE_ONLY",
        "positive_rsi_claim": False,
    }
    spec = {
        "schema": "rsi_lab.unattended_explore.v1",
        "run_id": run_id,
        "source_commit": "a" * 40,
        "state_root": str(tmp_path / "state"),
        "scratch_root": str(scratch_root),
        "result_path": str(child_path),
        "model_profile_digest": "sha256:" + "1" * 64,
        "role_bindings": {"solver": {"model_id": "model-a"}},
        "task_id": "task-fixture",
        "task_context_binding_digest": "sha256:" + "2" * 64,
        "shape": {"generations": 1, "children": 1, "tasks": 1},
        "limits": {"logical_provider_call_slots": 5},
        "reservation_digest": closeout["reservation_digest"],
        "positive_rsi_claim": False,
    }
    spec["spec_digest"] = daily.content_digest(spec)
    spec_path = run_dir / "child_spec.json"
    spec_path.write_text(json.dumps(spec) + "\n", encoding="utf-8")
    admission = {
        "kind": "run_admitted",
        "receipt_digest": closeout["admission_receipt_digest"],
        "run_id": run_id,
        "source_commit": spec["source_commit"],
        "model_profile_digest": spec["model_profile_digest"],
        "role_bindings": spec["role_bindings"],
        "task_id": spec["task_id"],
        "task_context_binding_digest": spec["task_context_binding_digest"],
        "shape": spec["shape"],
        "limits": spec["limits"],
        "spec": str(spec_path),
        "spec_digest": spec["spec_digest"],
        "reservation_digest": spec["reservation_digest"],
        "scratch_custody_create": closeout["scratch_custody"]["create"],
        "positive_rsi_claim": False,
    }
    projection = {"valid_chain": True, "attempt": closeout}
    scheduler = {"systemd": {"LastTriggerUSec": "Thu 2026-08-27 03:35:00 UTC"}}

    unanchored, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )

    assert unanchored is False
    assert details["admission_authority_valid"] is False

    projection["admission"] = admission
    ready, details = daily._last_attempt_ready(
        projection,
        scheduler,
        now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
        forge_root=forge_root,
    )
    assert ready is True
    assert details["terminal_success"] is True

    for field, mismatched in (
        ("receipt_digest", "sha256:" + "9" * 64),
        ("reservation_digest", "sha256:" + "8" * 64),
        ("scratch_custody_create", {"substituted": True}),
    ):
        projection["admission"] = {**admission, field: mismatched}
        substituted, substituted_details = daily._last_attempt_ready(
            projection,
            scheduler,
            now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
            forge_root=forge_root,
        )
        assert substituted is False
        assert substituted_details["admission_authority_valid"] is False
    projection["admission"] = admission

    for field, mismatched in (
        ("experiment_id", "different-experiment"),
        ("explore_closeout_state", "measured_negative"),
        ("logical_provider_calls_used", 4),
    ):
        projection["attempt"] = {**closeout, field: mismatched}
        mismatched_ready, mismatched_details = daily._last_attempt_ready(
            projection,
            scheduler,
            now=datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
            forge_root=forge_root,
        )
        assert mismatched_ready is False
        assert mismatched_details["attempt_child_binding_valid"] is False

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
