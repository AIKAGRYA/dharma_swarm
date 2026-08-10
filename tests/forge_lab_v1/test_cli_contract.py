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
    assert payload["result"]["implementation_status"] == (
        "minimum_safe_blocked_controller"
    )


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
    env["RSI_LAB_PYDEPS"] = str(base / "pydeps")

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
        "run",
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
        "sync",
    }
    assert set(_subcommands(root["provider"])) == {"selftest"}
    assert set(_subcommands(root["taskpack"])) == {"build"}
    assert set(_subcommands(root["campaign"])) == {
        "plan",
        "prepare",
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
    assert set(_subcommands(root["sync"])) == {
        "status",
        "plan",
        "apply",
        "converge",
        "rollback",
    }


def test_paired_plan_cli_collects_exact_limits_atomically() -> None:
    from dharma_swarm.forge_lab import campaign_control
    from dharma_swarm.forge_lab.campaign_cli import _plan_limits
    from dharma_swarm.forge_lab.rsi_cli import build_parser

    args = build_parser().parse_args(
        [
            "campaign",
            "plan",
            "--profile",
            "forge-lab-paired-frozen-v1",
            "--total-tokens",
            "1000000",
            "--total-usd-micros",
            "25000000",
            "--total-requests",
            "120",
            "--deadline-utc",
            "2099-01-01T00:00:00Z",
            "--host-caps-json",
            '{"host":"meghadharma","max_parallel_requests":3}',
        ]
    )

    assert _plan_limits(args, campaign_control) == {
        "total_tokens": 1_000_000,
        "total_usd_micros": 25_000_000,
        "total_requests": 120,
        "deadline_utc": "2099-01-01T00:00:00Z",
        "host_caps": {"host": "meghadharma", "max_parallel_requests": 3},
    }


def test_repo_launcher_defaults_to_the_canonical_environment() -> None:
    launcher = (REPO_ROOT / "scripts" / "forge_lab" / "rsi").read_text(encoding="utf-8")

    assert 'base="/root/rsi-lab/current"' in launcher
    assert 'base="${HOME}/.dharma/rsi-lab/current"' in launcher
    assert 'repo="${RSI_LAB_REPO:-${base}/repo}"' in launcher
    assert 'python="${RSI_LAB_PYTHON:-${base}/.venv/bin/python}"' in launcher
    assert 'pydeps="${RSI_LAB_PYDEPS:-${base}/pydeps}"' in launcher
    assert "export PYTHONDONTWRITEBYTECODE=1" in launcher
    assert 'export RSI_LAB_STATE="${RSI_LAB_STATE:-${base}/state}"' in launcher

    rsilab = (REPO_ROOT / "scripts" / "forge_lab" / "RSILAB").read_text(encoding="utf-8")
    assert 'exec "${script_dir}/rsi" "$@"' in rsilab



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
    assert current["command"] == (
        "rsi campaign plan --profile forge-lab-paired-frozen-v1"
    )


def test_newrun_diverse_preset_uses_exact_routeable_cloud_ids() -> None:
    result = _invoke(MODULE_COMMAND, "newrun", "--json", "--preset", "diverse")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    selected = payload["selected"]
    assert selected["solver_model"] == "deepseek-v4-pro:cloud"
    assert selected["verifier_model"] == "minimax-m3:cloud"
    assert selected["mutator_model"] == "kimi-k2.7-code:cloud"
    assert selected["command"] == (
        "rsi campaign plan --profile forge-lab-paired-frozen-v1"
    )



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
    assert selected["command"] == (
        "rsi campaign plan --profile forge-lab-paired-frozen-v1"
    )



def test_provider_selftest_config_json_is_implemented() -> None:
    result = _invoke(MODULE_COMMAND, "provider", "selftest", "--profile", "offline", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "forge_lab.cli_result.v1"
    assert payload["command"] == "provider selftest"
    assert payload["result"]["schema"] == "rsi_lab.provider_selftest.v1"
    assert payload["result"]["live"] is False


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
    assert payload["result"]["failures"] == ["live_probe_required_for_independent_routes"]


@pytest.mark.parametrize(
    "args",
    [
        ("doctor",),
        ("taskpack", "build", "--profile", "offline"),
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
        ("worker", "list"),
        ("worker", "enroll", "worker-1"),
        ("worker", "revoke", "worker-1"),
        ("alerts", "list"),
        ("alerts", "ack", "alert-1", "--reason", "test"),
        ("archive", "inspect"),
    ],
)


def test_registered_operations_fail_closed_until_implemented(
    args: tuple[str, ...],
) -> None:
    result = _invoke(MODULE_COMMAND, *args)

    assert result.returncode != 0
    assert result.stdout == ""
    assert "not implemented" in result.stderr.lower()


def test_json_operation_failure_uses_versioned_envelope() -> None:
    result = _invoke(MODULE_COMMAND, "doctor", "--json")

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload == {
        "schema": "forge_lab.cli_result.v1",
        "ok": False,
        "command": "doctor",
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": "rsi doctor is registered but not implemented",
        },
    }
    assert "not implemented" in result.stderr.lower()


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
    assert "not implemented" in result.stderr.lower()
    assert "traceback" not in result.stderr.lower()


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
    assert "manifest-bound provider attestation" in payload["recommendation"]["reasons"][0]


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
    assert payload["recommendation"]["selected_preset"] == "fast"
    assert payload["selected"]["name"] == "fast"
    assert "manifest-bound provider attestation" in payload["recommendation"]["reasons"][0]
