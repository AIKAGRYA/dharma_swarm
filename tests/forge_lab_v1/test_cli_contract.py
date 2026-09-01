"""Packet A contract tests for the repo-owned RSI command surface."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYDEPS_ROOT = REPO_ROOT.parent / "pydeps"
MODULE_COMMAND = (sys.executable, "-m", "dharma_swarm.forge_lab")
SCRIPT_COMMAND = (str(REPO_ROOT / "scripts" / "forge_lab" / "rsi"),)


def _pythonpath(env: dict[str, str]) -> str:
    entries = [str(REPO_ROOT)]
    if PYDEPS_ROOT.is_dir():
        entries.append(str(PYDEPS_ROOT))
    if env.get("PYTHONPATH"):
        entries.append(env["PYTHONPATH"])
    return os.pathsep.join(entries)


def _invoke(command: tuple[str, ...], *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    env["RSI_LAB_REPO"] = str(REPO_ROOT)
    env["RSI_LAB_PYTHON"] = sys.executable
    env["RSI_LAB_PYDEPS"] = str(PYDEPS_ROOT)
    env["RSI_LAB_DEV_SOURCE"] = "1"
    return subprocess.run(
        [*command, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    action = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return action.choices


def test_package_and_cli_report_packet_a_version() -> None:
    from dharma_swarm.forge_lab import __version__

    assert __version__ == "0.1.0-dev"

    short = _invoke(MODULE_COMMAND, "--version")
    assert short.returncode == 0, short.stderr
    assert short.stdout.startswith("rsi 0.1.0-dev source=")
    assert len(short.stdout.strip().rsplit("=", 1)[1]) == 40

    human = _invoke(MODULE_COMMAND, "version")
    assert human.returncode == 0, human.stderr
    assert "package_version: 0.1.0-dev" in human.stdout
    assert "source_commit:" in human.stdout
    assert "canonical_checkout:" in human.stdout

    machine = _invoke(MODULE_COMMAND, "version", "--json")
    assert machine.returncode == 0, machine.stderr
    payload = json.loads(machine.stdout)
    assert payload["schema"] == "forge_lab.cli_result.v1"
    assert payload["ok"] is True
    assert payload["command"] == "version"
    assert payload["result"]["package_version"] == "0.1.0-dev"
    assert payload["result"]["source_commit"]
    assert payload["result"]["canonical_checkout"] == str(REPO_ROOT)
    assert payload["result"]["source_checkout"] == str(REPO_ROOT)
    assert payload["result"]["source_tree_state"] in {"clean", "dirty", "unknown"}
    assert payload["result"]["implementation_status"] == "bounded_operator_control"


def test_default_checkout_selection_survives_inaccessible_remote_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from dharma_swarm.forge_lab.version import _default_lab_base

    remote = tmp_path / "megha-current"
    remote.mkdir()
    assert _default_lab_base(Path("/root"), remote) == remote

    def inaccessible(_path: Path) -> bool:
        raise PermissionError("cross-host path is inaccessible")

    monkeypatch.setattr(Path, "is_dir", inaccessible)
    assert _default_lab_base(Path("/home/runner"), remote) == Path(
        "/home/runner/.dharma/rsi-lab/current"
    )


def test_launcher_exports_custom_base_as_reported_identity(tmp_path: Path) -> None:
    base = tmp_path / "current"
    base.mkdir()
    (base / "repo").symlink_to(REPO_ROOT, target_is_directory=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    env["RSI_LAB_BASE"] = str(base)
    env["RSI_LAB_REPO"] = ""
    env["RSI_LAB_PYTHON"] = sys.executable
    # The release verifier intentionally keeps third-party packages outside the
    # immutable repo. Point the nested launcher at the verifier's actual
    # dependency root instead of a host-local virtualenv assumption.
    env["RSI_LAB_PYDEPS"] = str(Path(pytest.__file__).resolve().parent.parent)
    env["RSI_LAB_DEV_SOURCE"] = "1"

    result = subprocess.run(
        [*SCRIPT_COMMAND, "version", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"]["canonical_checkout"] == str(base / "repo")


def test_launcher_cannot_be_shadowed_by_the_callers_working_directory(
    tmp_path: Path,
) -> None:
    shadow = tmp_path / "shadow"
    rogue = shadow / "dharma_swarm" / "forge_lab"
    rogue.mkdir(parents=True)
    (shadow / "dharma_swarm" / "__init__.py").write_text("", encoding="utf-8")
    (rogue / "__init__.py").write_text("", encoding="utf-8")
    (rogue / "__main__.py").write_text(
        'print("{\\"rogue\\": true}")\n', encoding="utf-8"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(shadow)
    env["RSI_LAB_BASE"] = str(REPO_ROOT.parent)
    env["RSI_LAB_REPO"] = str(REPO_ROOT)
    env["RSI_LAB_PYTHON"] = sys.executable
    env["RSI_LAB_PYDEPS"] = str(REPO_ROOT.parent / "pydeps")
    env["RSI_LAB_DEV_SOURCE"] = "1"

    result = subprocess.run(
        [*SCRIPT_COMMAND, "version", "--json"],
        cwd=shadow,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload.get("rogue") is not True
    assert payload["schema"] == "forge_lab.cli_result.v1"
    assert payload["result"]["source_checkout"] == str(REPO_ROOT)


def test_module_and_repo_script_share_the_same_version_identity() -> None:
    module_result = _invoke(MODULE_COMMAND, "version", "--json")
    script_result = _invoke(SCRIPT_COMMAND, "version", "--json")

    assert module_result.returncode == script_result.returncode == 0
    assert json.loads(module_result.stdout) == json.loads(script_result.stdout)


def test_packet_a_registers_the_target_operator_command_tree() -> None:
    from dharma_swarm.forge_lab.rsi_cli import build_parser

    root = _subcommands(build_parser())
    assert set(root) == {
        "version",
        "newrun",
        "doctor",
        "provider",
        "taskpack",
        "campaign",
        "reconcile",
        "backup",
        "worker",
        "alerts",
        "archive",
        "daily",
        "sync",
    }
    provider = _subcommands(root["provider"])
    assert set(provider) == {"selftest", "models", "credential"}
    assert set(_subcommands(provider["models"])) == {
        "list",
        "status",
        "plan",
        "apply",
        "rollback",
    }
    assert set(_subcommands(provider["credential"])) == {"status", "plan", "apply"}
    assert set(_subcommands(root["taskpack"])) == {"build", "status", "plan", "apply"}
    assert set(_subcommands(root["campaign"])) == {
        "plan",
        "run",
        "list",
        "status",
        "progress",
        "events",
        "pause",
        "resume",
        "stop",
        "fork",
        "fuse-ack",
    }
    assert set(_subcommands(root["backup"])) == {"create", "verify", "restore"}
    assert set(_subcommands(root["worker"])) == {"list", "enroll", "revoke"}
    assert set(_subcommands(root["alerts"])) == {"list", "ack"}
    assert set(_subcommands(root["archive"])) == {"inspect"}
    assert set(_subcommands(root["daily"])) == {"status"}
    assert set(_subcommands(root["sync"])) == {
        "status",
        "plan",
        "apply",
        "converge",
        "rollback",
    }


def test_repo_launcher_defaults_to_the_canonical_environment() -> None:
    launcher = (REPO_ROOT / "scripts" / "forge_lab" / "rsi").read_text(encoding="utf-8")

    assert 'base="/root/rsi-lab/current"' in launcher
    assert 'base="${HOME}/.dharma/rsi-lab/current"' in launcher
    assert 'base="$(cd -- "${logical_base}" && pwd -P)"' in launcher
    assert 'repo="${base}/repo"' in launcher
    assert 'python="${base}/.venv/bin/python"' in launcher
    assert 'pydeps="${base}/pydeps"' in launcher
    assert 'state="${base}/state"' in launcher
    assert 'export RSI_LAB_PYDEPS="${pydeps}"' in launcher
    assert 'export RSI_LAB_SWEBENCH_PYDEPS="${swebench_pydeps}"' in launcher
    assert 'export RSI_LAB_REQUIRE_SWEBENCH_PYDEPS="${swebench_required}"' in launcher
    assert 'export DOCKER_CONTEXT="${docker_context}"' in launcher
    assert 'export FORGE_DOCKER_CONTEXT="${docker_context}"' in launcher
    assert 'export DOCKER_HOST="${docker_host}"' in launcher
    assert 'export RSI_LAB_STATE="${state}"' in launcher
    assert 'export DHARMA_HOME="${state}/.dharma"' in launcher
    assert (
        'export RSI_LAB_PROVIDER_SELFTEST_ROOT="${state}/.dharma/forge_lab/provider_selftests"'
        in launcher
    )
    assert 'export RSI_LAB_GRADER_MODE="${grader_mode}"' in launcher
    assert (
        'export PYTHONPATH="${repo}:${pydeps}${swebench_pydeps:+:${swebench_pydeps}}"'
        in launcher
    )
    assert "export PYTHONDONTWRITEBYTECODE=1" in launcher

    rsilab = (REPO_ROOT / "scripts" / "forge_lab" / "RSILAB").read_text(encoding="utf-8")
    assert 'exec "${script_dir}/rsi" "$@"' in rsilab

    env_script = (REPO_ROOT / "scripts" / "forge_lab" / "rsi-env").read_text(
        encoding="utf-8"
    )
    assert 'export RSI_LAB_REPO="${RSI_LAB_BASE}/repo"' in env_script
    assert 'export RSI_LAB_STATE="${RSI_LAB_BASE}/state"' in env_script
    assert 'export DHARMA_HOME="${RSI_LAB_STATE}/.dharma"' in env_script
    assert (
        'export RSI_LAB_PROVIDER_SELFTEST_ROOT="${RSI_LAB_STATE}/.dharma/forge_lab/provider_selftests"'
        in env_script
    )
    assert 'export RSI_LAB_GRADER_MODE="official-swebench-docker"' in env_script
    assert 'export RSI_LAB_SWEBENCH_PYDEPS=""' in env_script
    assert 'export RSI_LAB_REQUIRE_SWEBENCH_PYDEPS="1"' in env_script
    assert 'export DOCKER_CONTEXT="default"' in env_script
    assert 'export FORGE_DOCKER_CONTEXT="default"' in env_script
    assert 'export DOCKER_HOST="unix:///var/run/docker.sock"' in env_script
    assert (
        'export PYTHONPATH="${RSI_LAB_REPO}:${RSI_LAB_PYDEPS}'
        '${RSI_LAB_SWEBENCH_PYDEPS:+:${RSI_LAB_SWEBENCH_PYDEPS}}"'
        in env_script
    )


def test_installed_launcher_symlink_terminates_without_self_recursion(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    release = home / ".dharma" / "rsi-lab" / "releases" / ("a" * 40)
    release.mkdir(parents=True)
    (release / "repo").symlink_to(REPO_ROOT, target_is_directory=True)
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / ".venv" / "bin" / "python").symlink_to(sys.executable)
    (release / "pydeps").mkdir()
    (release / "state").mkdir()
    (home / ".dharma" / "rsi-lab" / "current").symlink_to(
        release, target_is_directory=True
    )
    launcher_dir = home / ".dharma" / "bin"
    launcher_dir.mkdir(parents=True)
    installed = launcher_dir / "rsi"
    installed.symlink_to(REPO_ROOT / "scripts" / "forge_lab" / "rsi")
    env = os.environ.copy()
    env["HOME"] = str(home)
    for key in tuple(env):
        if key.startswith("RSI_LAB_") or key in {"DHARMA_HOME", "PYTHONPATH"}:
            env.pop(key)

    result = subprocess.run(
        [str(installed), "version", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["command"] == "version"
    assert payload["result"]["source_commit"]


def test_production_launcher_ignores_inherited_source_state_and_pythonpath(
    tmp_path: Path,
) -> None:
    release = tmp_path / "releases" / ("a" * 40)
    logical = tmp_path / "current"
    (release / "repo" / "dharma_swarm" / "forge_lab").mkdir(parents=True)
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / "pydeps").mkdir()
    (release / "state").mkdir()
    logical.symlink_to(release, target_is_directory=True)
    fake_python = release / ".venv" / "bin" / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s|%s|%s|%s|%s|%s\\n' \"$RSI_LAB_STATE\" \"$DHARMA_HOME\" "
        "\"$PYTHONPATH\" \"$RSI_LAB_REPO\" \"$RSI_LAB_PROVIDER_SELFTEST_ROOT\" "
        "\"$RSI_LAB_PYDEPS\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env.pop("RSI_LAB_DEV_SOURCE", None)
    env.update(
        {
            "RSI_LAB_BASE": str(logical),
            "RSI_LAB_REPO": str(tmp_path / "rogue-repo"),
            "RSI_LAB_STATE": str(tmp_path / "rogue-state"),
            "DHARMA_HOME": str(tmp_path / "rogue-home"),
            "PYTHONPATH": str(tmp_path / "rogue-pythonpath"),
        }
    )

    result = subprocess.run(
        [*SCRIPT_COMMAND, "version", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "|".join(
        (
            str(release / "state"),
            str(release / "state" / ".dharma"),
            f"{release / 'repo'}:{release / 'pydeps'}",
            str(release / "repo"),
            str(release / "state" / ".dharma" / "forge_lab" / "provider_selftests"),
            str(release / "pydeps"),
        )
    )



def test_newrun_menu_projects_bleeding_edge_options_without_live_imports() -> None:
    result = _invoke(MODULE_COMMAND, "newrun", "--json", "--model", "glm-5.2")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "rsi_lab.newrun_options.v1"
    assert payload["ok"] is True
    assert payload["current_model"] == "glm-5.2"
    assert {preset["name"] for preset in payload["presets"]} == {
        "fast",
        "current",
        "diverse",
        "soak",
    }
    current = next(preset for preset in payload["presets"] if preset["name"] == "current")
    assert current["solver_model"] == "glm-5.2"
    assert current["mutator_model"] == "glm-5.2"
    assert current["verifier_model"] == "kimi-code"
    assert current["command"].startswith("python -m dharma_swarm.forge_lab.cli run --mode shadow")


def test_newrun_diverse_preset_uses_exact_routeable_cloud_ids() -> None:
    result = _invoke(MODULE_COMMAND, "newrun", "--json", "--preset", "diverse")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    selected = payload["selected"]
    assert selected["solver_model"] == "deepseek-v4-pro:cloud"
    assert selected["verifier_model"] == "minimax-m3:cloud"
    assert selected["mutator_model"] == "kimi-k2.7-code:cloud"
    assert "--solver-model deepseek-v4-pro:cloud" in selected["command"]
    assert "--verifier-model minimax-m3:cloud" in selected["command"]
    assert "--mutator-model kimi-k2.7-code:cloud" in selected["command"]



def test_newrun_accepts_operator_shorthand_dash_newrun() -> None:
    result = _invoke(MODULE_COMMAND, "-", "NEWRUN", "--json", "--preset", "fast")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["selected"]["name"] == "fast"


def test_newrun_selected_preset_can_be_overridden_without_execute() -> None:
    result = _invoke(
        MODULE_COMMAND,
        "newrun",
        "--json",
        "--preset",
        "fast",
        "--solver-model",
        "qwen3-coder:480b-cloud",
        "--generations",
        "2",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    selected = payload["selected"]
    assert selected["name"] == "fast"
    assert selected["solver_model"] == "qwen3-coder:480b-cloud"
    assert selected["generations"] == 2
    assert "--solver-model qwen3-coder:480b-cloud" in selected["command"]



def test_provider_selftest_config_json_is_implemented() -> None:
    result = _invoke(MODULE_COMMAND, "provider", "selftest", "--profile", "offline", "--json")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == "forge_lab.cli_result.v1"
    assert payload["command"] == "provider selftest"
    assert payload["result"]["schema"] == "rsi_lab.provider_selftest.v2"
    assert payload["result"]["live"] is False
    assert payload["result"]["callable_count"] == 0
    assert "config_only_no_callable_route_attestation" in payload["result"]["failures"]


def test_provider_selftest_route_requirement_fails_closed_without_live() -> None:
    result = _invoke(
        MODULE_COMMAND,
        "provider",
        "selftest",
        "--profile",
        "offline",
        "--require-independent-routes",
        "2",
        "--json",
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "live_probe_required_for_independent_routes" in payload["result"]["failures"]


def test_provider_selftest_invalid_bounds_are_not_mistyped_as_profile_errors() -> None:
    result = _invoke(
        MODULE_COMMAND,
        "provider",
        "selftest",
        "--profile",
        "staged",
        "--timeout-s",
        "0",
        "--json",
    )

    assert result.returncode != 0
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_ARGUMENT"


def test_taskpack_cli_error_preserves_terminal_evidence_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dharma_swarm.forge_lab import rsi_operations
    from dharma_swarm.forge_lab.taskpack_ops import TaskpackError

    receipt = tmp_path / "failed-action.json"

    def fail(_args: argparse.Namespace):
        raise TaskpackError("IMPORTER_FAILED", "bounded failure", receipt_path=receipt)

    monkeypatch.setattr(rsi_operations, "_taskpack", fail)
    result = rsi_operations.dispatch(
        argparse.Namespace(_command_path="taskpack status", json=True)
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == rsi_operations.OPERATION_FAILURE_EXIT
    assert payload["error"]["details"]["receipt_path"] == str(receipt)
    assert f"evidence: {receipt}" in captured.err


def test_provider_model_plan_is_exact_credential_free_and_ready() -> None:
    result = _invoke(
        MODULE_COMMAND,
        "provider",
        "models",
        "plan",
        "--mutator-provider",
        "zhipu",
        "--mutator-model",
        "glm-5.2",
        "--solver-provider",
        "ollama",
        "--solver-model",
        "deepseek-v4-pro:cloud",
        "--verifier-provider",
        "zhipu",
        "--verifier-model",
        "glm-5.2",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"]["outcome"] == "ready"
    assert payload["result"]["staged_models"] == [
        "glm-5.2",
        "deepseek-v4-pro:cloud",
    ]
    assert payload["result"]["claim_boundary"]["credentials_loaded"] is False
    assert payload["result"]["claim_boundary"]["promotion_authority"] is False


def test_provider_credential_plan_names_existing_store_but_never_takes_value() -> None:
    result = _invoke(
        MODULE_COMMAND,
        "provider",
        "credential",
        "plan",
        "--provider",
        "ollama",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    plan = payload["result"]
    assert plan["credential_env"] == "OLLAMA_API_KEY"
    assert plan["input_channel"] == "hidden_prompt_or_stdin_only"
    assert plan["secret_values_recorded"] is False
    assert plan["secret_digests_recorded"] is False


@pytest.mark.parametrize(
    "args",
    [
        ("taskpack", "build", "--profile", "offline"),
        ("campaign", "pause", "campaign-1"),
        ("campaign", "resume", "campaign-1"),
        ("campaign", "stop", "campaign-1"),
        ("campaign", "fork", "campaign-1"),
        (
            "campaign",
            "fuse-ack",
            "campaign-1",
            "--trip",
            "sha256:" + "1" * 64,
            "--reason",
            "test",
        ),
        ("backup", "create"),
        ("backup", "verify", "--snapshot", "sha256:" + "2" * 64),
        (
            "backup",
            "restore",
            "--snapshot",
            "sha256:" + "3" * 64,
            "--target",
            "/tmp/forge-restore-test",
        ),
        ("worker", "enroll", "worker-1"),
        ("worker", "revoke", "worker-1"),
        ("alerts", "ack", "alert-1", "--reason", "test"),
    ],
)


def test_registered_operations_fail_closed_until_implemented(
    args: tuple[str, ...],
) -> None:
    result = _invoke(MODULE_COMMAND, *args)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "not implemented" in result.stderr.lower()


def test_doctor_json_is_truthful_and_versioned() -> None:
    result = _invoke(MODULE_COMMAND, "doctor", "--json")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["schema"] == "forge_lab.cli_result.v1"
    assert payload["ok"] is False
    assert payload["command"] == "doctor"
    assert payload["result"]["schema"] == "rsi_lab.doctor.v1"
    assert set(payload["result"]["checks"]) == {
        "source",
        "state_anchor",
        "providers",
        "grader",
        "taskbed",
        "legacy_controls",
    }


def test_campaign_cli_plan_run_and_read_surfaces_are_real(tmp_path: Path) -> None:
    state = tmp_path / "state"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": _pythonpath(env),
            "RSI_LAB_REPO": str(REPO_ROOT),
            "RSI_LAB_BASE": str(REPO_ROOT.parent),
            "RSI_LAB_STATE": str(state),
            "DHARMA_HOME": str(state / ".dharma"),
            "RSI_LAB_DEV_SOURCE": "1",
        }
    )

    def invoke(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*MODULE_COMMAND, *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )

    planned = invoke("campaign", "plan", "--profile", "pilot-five-offline", "--json")
    assert planned.returncode == 0, planned.stderr
    digest = json.loads(planned.stdout)["result"]["manifest_digest"]
    ran = invoke(
        "campaign",
        "run",
        "--manifest",
        digest,
        "--request-id",
        "cli-five-run-pilot",
        "--json",
    )
    assert ran.returncode == 0, ran.stderr
    campaign_id = json.loads(ran.stdout)["result"]["campaign_id"]

    listed = invoke("campaign", "list", "--json")
    status = invoke("campaign", "status", campaign_id, "--json")
    progress = invoke("campaign", "progress", campaign_id, "--json")
    events = invoke("campaign", "events", campaign_id, "--after", "10", "--json")
    assert all(result.returncode == 0 for result in (listed, status, progress, events))
    assert json.loads(listed.stdout)["result"]["count"] == 1
    assert json.loads(status.stdout)["result"]["campaign"]["state"] == "COMPLETED"
    assert json.loads(progress.stdout)["result"]["completed"] == 5
    assert json.loads(events.stdout)["result"]["count"] == 2


def test_minimum_read_only_cli_views_are_implemented(tmp_path: Path) -> None:
    state = tmp_path / "state"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": _pythonpath(env),
            "RSI_LAB_REPO": str(REPO_ROOT),
            "RSI_LAB_BASE": str(REPO_ROOT.parent),
            "RSI_LAB_STATE": str(state),
            "DHARMA_HOME": str(state / ".dharma"),
            "RSI_LAB_DEV_SOURCE": "1",
            "RSI_LAB_CRONTAB_TEXT": "",
        }
    )
    for args in (
        ("worker", "list", "--json"),
        ("alerts", "list", "--json"),
        ("archive", "inspect", "--json"),
    ):
        result = subprocess.run(
            [*MODULE_COMMAND, *args],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["result"]["read_only"] is True

    reconcile = subprocess.run(
        [*MODULE_COMMAND, "reconcile", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    assert reconcile.returncode != 0
    report = json.loads(reconcile.stdout)["result"]
    assert report["read_only"] is True
    assert report["findings"]


def test_reconcile_rejects_mutation_arguments_outside_explicit_apply() -> None:
    ignored_apply = _invoke(
        MODULE_COMMAND,
        "reconcile",
        "--request-id",
        "must-not-be-ignored",
        "--plan-digest",
        "sha256:" + "0" * 64,
        "--json",
    )
    polluted_plan = _invoke(
        MODULE_COMMAND,
        "reconcile",
        "--plan",
        "--request-id",
        "must-not-be-ignored",
        "--json",
    )

    assert ignored_apply.returncode != 0
    assert polluted_plan.returncode != 0
    assert json.loads(ignored_apply.stdout)["error"]["code"] == "INVALID_MODE_ARGUMENTS"
    assert json.loads(polluted_plan.stdout)["error"]["code"] == "INVALID_MODE_ARGUMENTS"


def test_new_cli_never_imports_legacy_or_live_experiment_modules() -> None:
    probe = """
import sys
sys.modules['dharma_swarm.forge_lab.cli'] = None
sys.modules['dharma_swarm.forge_lab.experiment'] = None
from dharma_swarm.forge_lab import rsi_cli
raise SystemExit(rsi_cli.main(['doctor']))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert "not ready" in result.stdout.lower()
    assert "traceback" not in result.stderr.lower()


def test_newrun_execute_refuses_dirty_nonrelease_source_before_live_imports(
    tmp_path: Path,
) -> None:
    source = tmp_path / "nonrelease-source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "rsi-test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "RSI Test"],
        check=True,
    )
    marker = source / "marker.txt"
    marker.write_text("committed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "marker.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "-q", "-m", "fixture"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "remote",
            "add",
            "origin",
            "https://github.com/AIKAGRYA/dharma_swarm.git",
        ],
        check=True,
    )
    marker.write_text("dirty\n", encoding="utf-8")

    result = _invoke(
        MODULE_COMMAND,
        "newrun",
        "--preset",
        "fast",
        "--source-repo",
        str(source),
        "--execute",
        "--json",
    )

    assert result.returncode == 7
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NONCANONICAL_EXECUTION_SOURCE"


def test_newrun_recommend_selects_fast_without_provider_health(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "agent_evolution"
    run_dir = archive / "exp_fast_latest"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp_fast_latest",
                "config": {
                    "solver_model": "kimi-code",
                    "verifier_model": "glm-5.2",
                    "mutator_model": "gemini-2.5-flash",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "closeout.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp_fast_latest",
                "closeout_state": "inconclusive_low_power",
                "stats": {"seed_pass_rate": 0.0, "best_pass_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    env["RSI_LAB_REPO"] = str(REPO_ROOT)
    env["RSI_LAB_PYTHON"] = sys.executable
    env["RSI_LAB_PYDEPS"] = str(PYDEPS_ROOT)
    env["RSILAB_EVOLUTION_ARCHIVE_ROOT"] = str(archive)
    env["RSI_LAB_PROVIDER_SELFTEST_ROOT"] = str(tmp_path / "missing-provider-receipts")

    result = subprocess.run(
        [*MODULE_COMMAND, "newrun", "--recommend", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"]["selected_preset"] == "fast"
    assert payload["selected"]["name"] == "fast"
    assert "provider health" in payload["recommendation"]["reasons"][0]


def test_newrun_recommend_selects_soak_after_provider_health_and_fast_movement(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "agent_evolution"
    run_dir = archive / "exp_fast_latest"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp_fast_latest",
                "config": {
                    "solver_model": "kimi-code",
                    "verifier_model": "glm-5.2",
                    "mutator_model": "gemini-2.5-flash",
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "closeout.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp_fast_latest",
                "closeout_state": "inconclusive_low_power",
                "stats": {"seed_pass_rate": 0.0, "best_pass_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )
    provider_root = tmp_path / "provider"
    provider_root.mkdir()
    (provider_root / "20260723T000000Z__frontier__provider_selftest.json").write_text(
        json.dumps({"ok": True, "independent_route_count": 2, "receipt": "test"}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    env["RSI_LAB_REPO"] = str(REPO_ROOT)
    env["RSI_LAB_PYTHON"] = sys.executable
    env["RSI_LAB_PYDEPS"] = str(PYDEPS_ROOT)
    env["RSILAB_EVOLUTION_ARCHIVE_ROOT"] = str(archive)
    env["RSI_LAB_PROVIDER_SELFTEST_ROOT"] = str(provider_root)

    result = subprocess.run(
        [*MODULE_COMMAND, "newrun", "--recommend", "--json"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"]["selected_preset"] == "soak"
    assert payload["selected"]["name"] == "soak"
