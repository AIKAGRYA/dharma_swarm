from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from dharma_swarm.holon_system.transport import ssh_preflight


SSH_CONFIG = "host agni\nhostname 157.245.193.15\nuser root\nport 22\n"
PROBE_OUTPUT = """probe_version\t1
remote_user\troot
platform_system\tLinux
platform_machine\tx86_64
repo_tag\thome_dharma_swarm
repo_present\t1
venv_present\t1
package_present\t1
bootstrap_present\t1
identity_present\t1
active_prompt_present\t1
key_store_present\t1
key_store_mode\t600
"""


def _completed(
    argv: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, stderr)


def test_success_uses_resolved_alias_and_fixed_hardened_probe(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        if argv[:2] == ["ssh", "-G"]:
            return _completed(argv, stdout=SSH_CONFIG)
        return _completed(argv, stdout=PROBE_OUTPUT)

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight(
        "agni",
        "codex_remote",
        connect_timeout=5,
    )

    assert calls[0][0] == ["ssh", "-G", "--", "agni"]
    probe_argv, probe_kwargs = calls[1]
    for option in (
        "BatchMode=yes",
        "IdentitiesOnly=yes",
        "StrictHostKeyChecking=yes",
        "ForwardAgent=no",
        "ClearAllForwardings=yes",
        "PermitLocalCommand=no",
        "ControlMaster=no",
        "ControlPath=none",
        "ProxyCommand=none",
        "ProxyJump=none",
        "UpdateHostKeys=no",
        "ConnectTimeout=5",
    ):
        assert option in probe_argv
    assert probe_argv[-6:] == ["--", "agni", "sh", "-s", "--", "codex_remote"]
    assert probe_kwargs["input"] is ssh_preflight.REMOTE_PROBE
    assert probe_kwargs["timeout"] == 10
    assert [call[0][0] for call in calls] == ["ssh", "ssh"]
    assert '[ ! -L "$key_store_path" ]' in ssh_preflight.REMOTE_PROBE

    assert result["ok"] is True
    assert result["readiness"] == {
        "materialization_ready": True,
        "identity_ready": True,
        "activation_ready": False,
        "provider_readiness_inferred": False,
        "key_store_required_for_materialization": False,
    }
    assert result["ssh"]["authentication_observed"] is True
    assert result["observations"]["user"] == "root"
    assert result["observations"]["platform"] == {
        "system": "Linux",
        "machine": "x86_64",
    }
    assert result["observations"]["runtime_candidate"] == {
        "repository_present": True,
        "repository_location": "home_dharma_swarm",
        "venv_python_present": True,
        "package_source_present": True,
        "bootstrap_module_present": True,
    }
    assert result["observations"]["key_store"] == {
        "present": True,
        "mode": "0600",
        "safe_mode": True,
        "content_read": False,
    }
    assert result["authority"]["authorization_granted"] is False
    assert result["authority"]["mutation_authority"] is False
    assert "not authorization" in result["authority"]["claim"]
    assert result["operation_contract"] == {
        "mode": "fixed_read_only_probe",
        "remote_writes_requested": False,
        "deploy_requested": False,
        "sync_requested": False,
        "bootstrap_requested": False,
        "secret_values_read": False,
    }
    assert "157.245.193.15" not in json.dumps(result)


@pytest.mark.parametrize(
    "alias",
    [
        "root@agni",
        "157.245.193.15",
        "010.000.000.001",
        "2001:db8::1",
        "-oProxyCommand=id",
        "agni;id",
        "agni space",
        "agni\nother",
        "../agni",
    ],
)
def test_rejects_non_alias_destinations_before_subprocess(monkeypatch, alias: str) -> None:
    def forbidden_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("subprocess must not run for a rejected destination")

    monkeypatch.setattr(ssh_preflight.subprocess, "run", forbidden_run)

    with pytest.raises(ssh_preflight.RemoteHolonPreflightError) as exc:
        ssh_preflight.run_remote_holon_preflight(alias, "codex_remote")

    assert exc.value.code == "invalid_ssh_alias"


def test_rejects_unsafe_holon_name_before_subprocess(monkeypatch) -> None:
    def forbidden_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("subprocess must not run for a rejected holon name")

    monkeypatch.setattr(ssh_preflight.subprocess, "run", forbidden_run)

    with pytest.raises(ssh_preflight.RemoteHolonPreflightError) as exc:
        ssh_preflight.run_remote_holon_preflight("agni", "../../agent_keys.env")

    assert exc.value.code == "invalid_holon_name"


def test_ssh_config_failure_is_structured_and_does_not_echo_stderr(monkeypatch) -> None:
    sensitive_stderr = "configuration detail that must not be reflected"

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return _completed(argv, returncode=255, stderr=sensitive_stderr)

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight("agni", "codex_remote")

    assert result["ok"] is False
    assert result["error"]["code"] == "ssh_config_failed"
    assert result["authority"]["authentication_observed"] is False
    assert sensitive_stderr not in json.dumps(result)


def test_default_only_ssh_hostname_is_not_accepted_as_configured_alias(monkeypatch) -> None:
    calls = 0

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return _completed(
            argv,
            stdout="host arbitrary.example\nhostname arbitrary.example\nuser root\nport 22\n",
        )

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight(
        "arbitrary.example",
        "codex_remote",
    )

    assert calls == 1
    assert result["ok"] is False
    assert result["error"]["code"] == "ssh_config_invalid"
    assert result["ssh"]["authentication_observed"] is False


def test_authentication_failure_is_not_promoted_to_authority(monkeypatch) -> None:
    calls = 0
    sensitive_stderr = "Permission denied with local connection details"

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(argv, stdout=SSH_CONFIG)
        return _completed(argv, returncode=255, stderr=sensitive_stderr)

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight("agni", "codex_remote")

    assert result["error"]["code"] == "ssh_authentication_failed"
    assert result["ssh"]["config_resolved"] is True
    assert result["ssh"]["authentication_observed"] is False
    assert result["authority"]["authorization_granted"] is False
    assert sensitive_stderr not in json.dumps(result)


def test_arbitrary_remote_output_is_rejected_without_reflection(monkeypatch) -> None:
    calls = 0
    untrusted_output = "secret_value\tshould-never-be-returned\n"

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(argv, stdout=SSH_CONFIG)
        return _completed(argv, stdout=untrusted_output)

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight("agni", "codex_remote")

    assert result["error"]["code"] == "remote_probe_output_invalid"
    assert result["ssh"]["authentication_observed"] is True
    assert untrusted_output.strip() not in json.dumps(result)


def test_key_store_mode_is_metadata_and_does_not_gate_materialization(monkeypatch) -> None:
    calls = 0
    unsafe_probe = PROBE_OUTPUT.replace("key_store_mode\t600", "key_store_mode\t644")

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _completed(argv, stdout=SSH_CONFIG)
        return _completed(argv, stdout=unsafe_probe)

    monkeypatch.setattr(ssh_preflight.subprocess, "run", fake_run)

    result = ssh_preflight.run_remote_holon_preflight("agni", "codex_remote")

    assert result["ok"] is True
    assert result["readiness"]["materialization_ready"] is True
    assert result["readiness"]["identity_ready"] is True
    assert result["readiness"]["activation_ready"] is False
    assert result["readiness"]["key_store_required_for_materialization"] is False
    assert result["observations"]["key_store"] == {
        "present": True,
        "mode": "0644",
        "safe_mode": False,
        "content_read": False,
    }


def test_script_help_is_available_without_running_ssh() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "scripts/remote_holon_preflight.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    help_text = result.stdout.lower()
    assert "configured ssh alias" in help_text
    assert "fixed read-only ssh preflight" in help_text
