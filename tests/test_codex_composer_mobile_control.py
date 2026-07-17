from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/runtime/codex_composer_mobile_control.py"
SPEC = importlib.util.spec_from_file_location("codex_composer_mobile_control", MODULE_PATH)
assert SPEC and SPEC.loader
control = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = control
SPEC.loader.exec_module(control)


def _config(tmp_path: Path) -> control.ControlConfig:
    return control.ControlConfig(
        instance_id="agni",
        card_sha256="a" * 64,
        memory_sha256="b" * 64,
        state_dir=tmp_path,
        freshness_seconds=90,
        cooldown_seconds=300,
        verify_timeout_seconds=10,
    )


def _heartbeat(*, observed_at: str, **overrides) -> dict:
    payload = {
        "agent_uid": "codex_composer",
        "instance_id": "agni",
        "card_sha256": "a" * 64,
        "memory_sha256": "b" * 64,
        "status": "online",
        "observed_at": observed_at,
        "boot_id": "c" * 32,
        "sequence": 12,
        "seat": {
            "ready": True,
            "state": "ready",
            "tmux_session": "codex_composer",
        },
    }
    payload.update(overrides)
    return payload


def _snapshot(*, healthy: bool, active: bool = True) -> control.HealthSnapshot:
    return control.HealthSnapshot(
        healthy=healthy,
        reasons=() if healthy else ("heartbeat_stale",),
        service_active=active,
        service_enabled=True,
        status="online" if healthy else "degraded",
        observed_at="2026-07-18T00:00:00+00:00",
        heartbeat_age_seconds=1 if healthy else 100,
        boot_id="c" * 32,
        sequence=12,
        seat_state="ready" if healthy else "tmux_present_unverified",
    )


def test_evaluate_health_requires_fresh_coherent_identity(tmp_path: Path) -> None:
    config = _config(tmp_path)
    observed = datetime(2026, 7, 18, tzinfo=timezone.utc)
    snapshot = control.evaluate_health(
        config,
        _heartbeat(observed_at=observed.isoformat()),
        service_active=True,
        service_enabled=True,
        now_epoch=observed.timestamp() + 20,
    )

    assert snapshot.healthy
    assert snapshot.reasons == ()
    assert snapshot.sequence == 12

    stale = control.evaluate_health(
        config,
        _heartbeat(observed_at=observed.isoformat(), card_sha256="d" * 64),
        service_active=False,
        service_enabled=True,
        now_epoch=observed.timestamp() + 200,
    )

    assert not stale.healthy
    assert set(stale.reasons) == {
        "service_inactive",
        "heartbeat_stale",
        "card_digest_mismatch",
    }


def test_load_config_reads_data_without_sourcing_shell(tmp_path: Path) -> None:
    path = tmp_path / "replica.env"
    path.write_text(
        "\n".join(
            (
                "CODEX_COMPOSER_INSTANCE_ID=agni",
                f"CODEX_COMPOSER_CARD_SHA256={'a' * 64}",
                f"CODEX_COMPOSER_MEMORY_SHA256={'b' * 64}",
                "CODEX_COMPOSER_STATE_DIR=/var/lib/dharma-codex-composer",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)

    config = control.load_config(path, required_uid=os.getuid())

    assert config.instance_id == "agni"
    assert config.state_dir == Path("/var/lib/dharma-codex-composer")


def test_control_inputs_reject_symlinks_and_non_private_modes(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("secret", encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(OSError):
        control._read_regular_bytes(link, required_uid=os.getuid())

    target.chmod(0o640)
    with pytest.raises(control.ControlConfigurationError, match="root-private"):
        control._read_regular_bytes(target, required_uid=os.getuid())


def test_probe_uses_only_the_literal_systemd_unit(tmp_path: Path) -> None:
    config = _config(tmp_path)
    observed = datetime.now(timezone.utc)
    config.heartbeat_file.write_text(
        json.dumps(_heartbeat(observed_at=observed.isoformat())), encoding="utf-8"
    )
    config.heartbeat_file.chmod(0o600)
    calls: list[list[str]] = []

    def runner(args: list[str], *, timeout: float):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    snapshot = control.probe_health(
        config,
        now_epoch=observed.timestamp() + 1,
        runner=runner,
        required_uid=os.getuid(),
    )

    assert snapshot.healthy
    assert calls == [
        [control.SYSTEMCTL, "is-active", "--quiet", control.UNIT],
        [control.SYSTEMCTL, "is-enabled", "--quiet", control.UNIT],
    ]


def test_reconcile_is_noop_when_healthy(tmp_path: Path) -> None:
    config = _config(tmp_path)
    calls: list[list[str]] = []

    def runner(args: list[str], *, timeout: float):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    payload, exit_code = control.run_reconcile(
        config,
        probe=lambda _: _snapshot(healthy=True),
        runner=runner,
    )

    assert exit_code == 0
    assert payload["result"] == "healthy_noop"
    assert payload["action"] == "none"
    assert calls == []


def test_reconcile_starts_only_literal_unit_and_verifies(tmp_path: Path) -> None:
    config = _config(tmp_path)
    observations = iter(
        (
            _snapshot(healthy=False, active=False),
            _snapshot(healthy=False, active=False),
            _snapshot(healthy=True, active=True),
        )
    )
    calls: list[list[str]] = []
    ticks = iter((1000.0, 1000.0, 1001.0, 1002.0))

    def runner(args: list[str], *, timeout: float):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    payload, exit_code = control.run_reconcile(
        config,
        probe=lambda _: next(observations),
        runner=runner,
        sleeper=lambda _: None,
        clock=lambda: next(ticks),
    )

    assert exit_code == 0
    assert payload["result"] == "reconciled_verified"
    assert payload["action"] == "start"
    assert calls == [
        [control.SYSTEMCTL, "reset-failed", control.UNIT],
        [control.SYSTEMCTL, "start", control.UNIT],
    ]
    assert len(payload["receipt_sha256"]) == 64


def test_reconcile_cooldown_never_invokes_systemd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(control, "_cooldown_remaining", lambda *_: 120.0)

    payload, exit_code = control.run_reconcile(
        config,
        probe=lambda _: _snapshot(healthy=False),
        runner=lambda args, timeout: calls.append(args),
        clock=lambda: 1000.0,
    )

    assert exit_code == 3
    assert payload["result"] == "cooldown"
    assert calls == []


def test_cooldown_state_is_instance_bound_and_finite(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.cooldown_file.write_text(
        json.dumps(
            {"instance_id": "rushabdev", "reconcile_started_epoch": 1000.0}
        ),
        encoding="utf-8",
    )
    config.cooldown_file.chmod(0o600)

    with pytest.raises(control.ControlConfigurationError, match="invalid cooldown state"):
        control._cooldown_remaining(config, 1001.0, required_uid=os.getuid())

    config.cooldown_file.write_text(
        '{"instance_id":"agni","reconcile_started_epoch":NaN}',
        encoding="utf-8",
    )
    with pytest.raises(control.ControlConfigurationError, match="invalid cooldown state"):
        control._cooldown_remaining(config, 1001.0, required_uid=os.getuid())


def test_cli_grammar_rejects_shell_or_arbitrary_arguments() -> None:
    with pytest.raises(SystemExit):
        control._parser().parse_args(["restart", "other.service"])
    with pytest.raises(SystemExit):
        control._parser().parse_args(["status", "; id"])

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "os.system" not in source
    assert "eval(" not in source


def test_ssh_gate_requires_exact_operation_target_and_fresh_ttl(tmp_path: Path) -> None:
    config = _config(tmp_path)
    command = "cc-mobile-v1 reconcile gha-12345-1-agni 1752796800 1752797100"

    assert control.validate_ssh_original_command(
        config,
        "reconcile",
        environ={"SSH_ORIGINAL_COMMAND": command},
        now_epoch=1752796810,
    ) == ("reconcile", "gha-12345-1-agni")

    bad = (
        "cc-mobile-v1 reconcile gha-12345-1-rushabdev "
        "1752796800 1752797100"
    )
    with pytest.raises(control.ControlConfigurationError, match="wrong instance"):
        control.validate_ssh_original_command(
            config,
            "reconcile",
            environ={"SSH_ORIGINAL_COMMAND": bad},
            now_epoch=1752796810,
        )
    with pytest.raises(control.ControlConfigurationError, match="stale"):
        control.validate_ssh_original_command(
            config,
            "reconcile",
            environ={"SSH_ORIGINAL_COMMAND": command},
            now_epoch=1752797200,
        )
    with pytest.raises(control.ControlConfigurationError):
        control.validate_ssh_original_command(
            config,
            "status",
            environ={"SSH_ORIGINAL_COMMAND": "cc-mobile-v1 status x;id 1752796800 1752797100"},
            now_epoch=1752796810,
        )


def test_deployment_contract_has_watchdog_and_exact_sudoers() -> None:
    unit = (ROOT / "deploy/systemd/dharma-codex-composer-replica.service").read_text(
        encoding="utf-8"
    )
    sudoers = (ROOT / "deploy/systemd/codex-composer-mobile-control.sudoers").read_text(
        encoding="utf-8"
    )

    assert "WatchdogSec=" in unit
    assert "NotifyAccess=main" in unit
    assert " ALL" not in sudoers.replace(" ALL=(root)", "")
    assert "codex_composer_mobile_control.py" not in sudoers
    assert "/usr/local/sbin/codex-composer-mobile-control ssh-gate status" in sudoers
    assert "/usr/local/sbin/codex-composer-mobile-control ssh-gate reconcile" in sudoers
    assert 'env_keep += "SSH_ORIGINAL_COMMAND"' in sudoers
    assert "*" not in sudoers


def _workflow() -> tuple[dict, str]:
    path = ROOT / ".github/workflows/codex-composer-mobile-ops.yml"
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded, text


def _run_embedded_receipt_validator(
    tmp_path: Path,
    payload: dict,
    *,
    operation: str,
    request_id: str,
    transport_exit: int,
) -> dict:
    loaded, _ = _workflow()
    run = loaded["jobs"]["status_agni"]["steps"][0]["run"]
    assert run.count("<<'PY'") == 1
    validator = run.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    raw = tmp_path / "remote.json"
    result = tmp_path / "result.json"
    raw.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-",
            str(raw),
            str(result),
            "agni",
            operation,
            request_id,
            str(transport_exit),
        ],
        input=validator,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    return json.loads(result.read_text(encoding="utf-8"))


def test_workflow_is_pinned_to_numeric_actors_hosts_and_forced_ssh() -> None:
    loaded, text = _workflow()
    jobs = loaded["jobs"]

    assert "concurrency" not in loaded
    assert "sender.get(\"id\")" in text
    assert "CODEX_COMPOSER_MOBILE_OPS_ISSUE_NUMBER" in text
    assert "CODEX_COMPOSER_MOBILE_OPS_ACTOR_IDS" in text
    assert "GITHUB_EVENT_PATH" in text
    assert "ssh-keyscan" not in text
    assert "StrictHostKeyChecking=yes" in text
    assert "ControlMaster=no" in text
    assert "ControlPath=none" in text
    assert "IdentityAgent=none" in text
    assert "IdentitiesOnly=yes" in text
    assert "ClearAllForwardings=yes" in text
    assert "cc-mobile-v1 ${remote_operation}" in text
    assert "claimed_digest != computed_digest" in text
    assert not re.search(r"secrets\.[A-Za-z0-9_]*(PASSWORD|TOKEN)", text)

    for instance in ("agni", "rushabdev", "meghadharma"):
        repair = jobs[f"repair_{instance}"]
        assert repair["environment"]["name"] == f"codex-composer-repair-{instance}"
        assert repair["concurrency"] == {
            "group": f"codex-composer-repair-{instance}",
            "cancel-in-progress": False,
        }
        run = repair["steps"][0]
        assert run["env"]["REMOTE_OPERATION"] == "reconcile"
        assert (
            run["env"]["SSH_PRIVATE_KEY"]
            == "${{ secrets.CODEX_COMPOSER_REPAIR_SSH_KEY }}"
        )


def test_workflow_accepts_bound_helper_receipt_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    request_id = "gha-123456789-1-agni"
    snapshot = _snapshot(healthy=True)
    payload = control._result_payload(
        config,
        operation="status",
        result="healthy_noop",
        action="none",
        snapshot=snapshot,
        request_id=request_id,
    )

    accepted = _run_embedded_receipt_validator(
        tmp_path,
        payload,
        operation="status",
        request_id=request_id,
        transport_exit=0,
    )
    assert accepted["accepted_remote_receipt"] is True
    assert accepted["ok"] is True
    assert accepted["remote"]["request_id"] == request_id

    payload["health"]["seat_state"] = "tampered"
    rejected = _run_embedded_receipt_validator(
        tmp_path,
        payload,
        operation="status",
        request_id=request_id,
        transport_exit=0,
    )
    assert rejected["accepted_remote_receipt"] is False
    assert rejected["detail_code"] == "invalid_remote_receipt"


def test_workflow_preserves_a_valid_unreadable_heartbeat_receipt(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    request_id = "gha-987654321-1-agni"
    snapshot = control.HealthSnapshot(
        healthy=False,
        reasons=("heartbeat_unreadable",),
        service_active=True,
        service_enabled=True,
    )
    payload = control._result_payload(
        config,
        operation="status",
        result="reported_unhealthy",
        action="none",
        snapshot=snapshot,
        request_id=request_id,
    )

    observed = _run_embedded_receipt_validator(
        tmp_path,
        payload,
        operation="status",
        request_id=request_id,
        transport_exit=3,
    )

    assert observed["accepted_remote_receipt"] is True
    assert observed["ok"] is False
    assert observed["detail_code"] == "remote_reported_unhealthy"
    assert observed["remote"]["health"]["observed_at"] == ""
