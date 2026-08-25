from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.lab_supervisor.cli import main


def _write_config(tmp_path: Path, *, dry_run: bool = False) -> Path:
    lab_root = tmp_path / "lab"
    lab_root.mkdir()
    evidence = lab_root / "evidence.json"
    evidence.write_text('{"status":"ok"}', encoding="utf-8")
    config = {
        "schema": "dharma.lab_supervisor.config.v1",
        "policy": {
            "dry_run": dry_run,
            "min_free_disk_bytes": 1,
            "max_load_per_cpu": 100,
        },
        "labs": [
            {
                "name": "rsi-lab",
                "kind": "rsi_lab",
                "state_root": str(lab_root),
                "evidence_paths": [str(evidence)],
                "halt_paths": [str(lab_root / "HALT")],
                "max_stale_seconds": 3600,
                "bounded_trial": {
                    "argv": ["/usr/bin/true", "trial"],
                    "feature_argv": ["/usr/bin/true", "--help"],
                },
                "trial_interval_seconds": 0,
            }
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_validate_config_emits_feature_availability(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path)
    assert main(["validate-config", "--config", str(config)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "dharma.lab_supervisor.features.v1"
    assert payload["ready"] is True
    assert payload["failures"] == []
    assert payload["labs"]["rsi-lab"]["commands"]["bounded_trial"] == {
        "command_sha256": payload["labs"]["rsi-lab"]["commands"]["bounded_trial"]["command_sha256"],
        "declared": True,
        "executable_available": True,
        "feature_command_sha256": payload["labs"]["rsi-lab"]["commands"]["bounded_trial"]["feature_command_sha256"],
        "feature_verified": True,
        "reason": "",
    }


def test_validate_config_fails_closed_on_declared_feature_failure(
    tmp_path: Path, capsys
) -> None:
    config = _write_config(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["labs"][0]["bounded_trial"]["feature_argv"] = ["/usr/bin/false"]
    config.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate-config", "--config", str(config)]) == 4
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is False
    assert report["failures"] == ["rsi-lab:bounded_trial:feature_probe_failed"]


def test_tick_is_safe_dry_run_without_second_action_key(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, dry_run=False)
    state_root = tmp_path / "supervisor"
    assert main(["tick", "--config", str(config), "--state-root", str(state_root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["assessments"][0]["actions"][-1]["status"] == "dry_run"
    assert payload["receipt_hash"].startswith("sha256:")

    assert main(["status", "--config", str(config), "--state-root", str(state_root)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["schema"] == "dharma.lab_supervisor.status.v1"
    assert status["receipt_chain"]["valid"] is True
    assert status["receipt_chain"]["count"] == 1


def test_tick_exit_distinguishes_lab_halt_from_internal_chain_failure(
    tmp_path: Path, capsys
) -> None:
    config = _write_config(tmp_path)
    raw = json.loads(config.read_text(encoding="utf-8"))
    Path(raw["labs"][0]["halt_paths"][0]).write_text("halt", encoding="utf-8")
    state_root = tmp_path / "supervisor"
    argv = ["tick", "--config", str(config), "--state-root", str(state_root)]
    assert main(argv) == 0
    governed = json.loads(capsys.readouterr().out)
    assert governed["state"] == "Halted"
    assert governed["internal_failure"] is False

    receipts = state_root / "receipts.jsonl"
    row = json.loads(receipts.read_text(encoding="utf-8"))
    row["dry_run"] = not row["dry_run"]
    receipts.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert main(argv) == 4
    internal = json.loads(capsys.readouterr().out)
    assert internal["state"] == "Blocked"
    assert internal["internal_failure"] is True
    assert "receipt_chain_invalid" in internal["notes"]


def test_repo_entrypoint_help_is_feature_detectable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/runtime/lab_supervisor.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "validate-config" in completed.stdout
    assert "tick" in completed.stdout
    assert "status" in completed.stdout


def test_anomaly_schema_has_literal_false_authority_fields(capsys) -> None:
    assert main(["anomaly-schema"]) == 0
    payload = json.loads(capsys.readouterr().out)
    effects = payload["properties"]["forbidden_effects"]["properties"]
    assert effects == {
        "clear_kill": {"const": False},
        "deploy": {"const": False},
        "expand_budget": {"const": False},
        "merge": {"const": False},
    }


def test_systemd_template_is_timer_bounded_and_default_safe() -> None:
    service = Path("docs/ops/LAB_SUPERVISOR.service").read_text(encoding="utf-8")
    timer = Path("docs/ops/LAB_SUPERVISOR.timer").read_text(encoding="utf-8")
    installer = Path("scripts/runtime/install_lab_supervisor.sh").read_text(encoding="utf-8")
    assert "Type=oneshot" in service
    assert "--allow-actions" not in next(
        line for line in service.splitlines() if line.startswith("ExecStart=")
    )
    assert "OnUnitActiveSec=5min" in timer
    assert "Persistent=true" in timer
    assert "--expected-sha" in installer
    assert "never enables or starts" in installer
    for directive in (
        "CapabilityBoundingSet=",
        "PrivateDevices=true",
        "ProtectKernelTunables=true",
        "ProtectKernelModules=true",
        "ProtectControlGroups=true",
        "RestrictAddressFamilies=AF_UNIX",
    ):
        assert directive in service
