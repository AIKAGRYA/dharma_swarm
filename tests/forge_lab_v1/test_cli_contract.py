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
    assert payload["result"]["implementation_status"] == "cli_skeleton"


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


def test_repo_launcher_defaults_to_the_canonical_environment() -> None:
    launcher = (REPO_ROOT / "scripts" / "forge_lab" / "rsi").read_text(encoding="utf-8")

    assert 'base="/root/rsi-lab/current"' in launcher
    assert 'base="${HOME}/.dharma/rsi-lab/current"' in launcher
    assert 'repo="${RSI_LAB_REPO:-${base}/repo}"' in launcher
    assert 'python="${RSI_LAB_PYTHON:-${base}/.venv/bin/python}"' in launcher
    assert 'pydeps="${RSI_LAB_PYDEPS:-${base}/pydeps}"' in launcher
    assert "export PYTHONDONTWRITEBYTECODE=1" in launcher

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
        "signal",
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


def test_newrun_signal_preset_uses_broad_fixed_panel_shape() -> None:
    result = _invoke(MODULE_COMMAND, "newrun", "--json", "--preset", "signal")

    assert result.returncode == 0, result.stderr
    selected = json.loads(result.stdout)["selected"]
    assert selected["solver_model"] == "deepseek-v4-pro:cloud"
    assert selected["verifier_model"] == "minimax-m3:cloud"
    assert selected["mutator_model"] == "kimi-k2.7-code:cloud"
    assert selected["generations"] == 1
    assert selected["children"] == 2
    assert selected["tasks"] == 5
    assert selected["budget_tokens"] == 100_000
    assert selected["max_experiment_tokens"] == 500_000
    assert "--generations 1 --children 2 --tasks 5" in selected["command"]



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
        ("campaign", "plan", "--profile", "explore-open"),
        ("campaign", "run", "--manifest", "sha256:" + "0" * 64),
        ("campaign", "list"),
        ("campaign", "status"),
        ("campaign", "progress"),
        ("campaign", "events", "campaign-1"),
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
        ("reconcile",),
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


def _newrun_recommend_env(
    *,
    archive: Path,
    provider_root: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _pythonpath(env)
    env["RSI_LAB_REPO"] = str(REPO_ROOT)
    env["RSI_LAB_PYTHON"] = sys.executable
    env["RSI_LAB_PYDEPS"] = str(PYDEPS_ROOT)
    env["RSILAB_EVOLUTION_ARCHIVE_ROOT"] = str(archive)
    env["RSI_LAB_PROVIDER_SELFTEST_ROOT"] = str(provider_root)
    env["RSI_LAB_PROVIDER_SELFTEST_NOW"] = "2026-07-26T00:00:00Z"
    return env


def _write_provider_receipt(
    root: Path,
    *,
    checked_at: str,
    rows: list[dict[str, object]],
    suffix: str,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{checked_at.replace(':', '').replace('-', '')}__{suffix}__provider_selftest.json").write_text(
        json.dumps(
            {
                "schema": "rsi_lab.provider_selftest.v1",
                "live": True,
                "checked_at": checked_at,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def _provider_row(model_id: str, *, is_callable: bool) -> dict[str, object]:
    return {
        "model_id": model_id,
        "live": True,
        "callable": is_callable,
        "outcome": "callable" if is_callable else "unavailable",
        "stage": "complete" if is_callable else "call",
    }


def test_newrun_recommend_fails_closed_without_exact_provider_health(tmp_path: Path) -> None:
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
    env = _newrun_recommend_env(
        archive=archive,
        provider_root=tmp_path / "missing-provider-receipts",
    )

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
    assert payload["recommendation"]["selected_preset"] is None
    assert payload["recommendation"]["selected"] is None
    assert payload["selected"] is None
    assert any(
        "no preset has explicit callable evidence" in reason
        for reason in payload["recommendation"]["reasons"]
    )


def test_newrun_explicit_preset_remains_allowed_when_recommendation_fails(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            *MODULE_COMMAND,
            "newrun",
            "--recommend",
            "--preset",
            "fast",
            "--json",
        ],
        cwd=REPO_ROOT,
        env=_newrun_recommend_env(
            archive=tmp_path / "archive",
            provider_root=tmp_path / "provider",
        ),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"]["selected_preset"] is None
    assert payload["selected"]["name"] == "fast"


def test_newrun_recommend_execute_fails_when_nothing_is_selected(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [*MODULE_COMMAND, "newrun", "--recommend", "--execute"],
        cwd=REPO_ROOT,
        env=_newrun_recommend_env(
            archive=tmp_path / "archive",
            provider_root=tmp_path / "provider",
        ),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 2
    assert "nothing was executed" in result.stderr


def test_newrun_recommend_selects_signal_from_exact_routes_across_receipts(tmp_path: Path) -> None:
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
                "stats": {
                    "seed_pass_rate": 0.0,
                    "best_pass_rate": 1.0,
                    "same_panel_comparable": True,
                    "executed_phenotype_changes": 1,
                    "unique_task_ids": 5,
                    "seed_panel_saturated": False,
                    "observed_best_delta": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    provider_root = tmp_path / "provider"
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-25T14:26:45Z",
        suffix="solver",
        rows=[_provider_row("deepseek-v4-pro:cloud", is_callable=True)],
    )
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-25T14:32:27Z",
        suffix="verifier",
        rows=[_provider_row("minimax-m3:cloud", is_callable=True)],
    )
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-25T14:32:36Z",
        suffix="mutator",
        rows=[_provider_row("kimi-k2.7-code:cloud", is_callable=True)],
    )
    env = _newrun_recommend_env(
        archive=archive,
        provider_root=provider_root,
    )

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
    assert payload["recommendation"]["selected_preset"] == "signal"
    assert payload["selected"]["name"] == "signal"
    status = payload["recommendation"]["provider_selftest"]["preset_route_status"]
    assert status["signal"]["callable"] is True
    assert status["fast"]["callable"] is False


def test_newrun_recommend_latest_exact_route_failure_shadows_success(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive"
    provider_root = tmp_path / "provider"
    trio = [
        "deepseek-v4-pro:cloud",
        "minimax-m3:cloud",
        "kimi-k2.7-code:cloud",
    ]
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-25T14:32:36Z",
        suffix="trio-green",
        rows=[_provider_row(model, is_callable=True) for model in trio],
    )
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-25T14:39:03Z",
        suffix="mutator-red",
        rows=[_provider_row("kimi-k2.7-code:cloud", is_callable=False)],
    )

    result = subprocess.run(
        [*MODULE_COMMAND, "newrun", "--recommend", "--json"],
        cwd=REPO_ROOT,
        env=_newrun_recommend_env(
            archive=archive,
            provider_root=provider_root,
        ),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"]["selected_preset"] is None
    assert payload["selected"] is None
    routes = payload["recommendation"]["provider_selftest"]["routes"]
    assert routes["kimi-k2.7-code:cloud"]["callable"] is False
    assert "kimi-k2.7-code:cloud" in payload["recommendation"]["reasons"][-1]


def test_newrun_recommend_rejects_stale_exact_route_receipts(tmp_path: Path) -> None:
    provider_root = tmp_path / "provider"
    trio = [
        "deepseek-v4-pro:cloud",
        "minimax-m3:cloud",
        "kimi-k2.7-code:cloud",
    ]
    _write_provider_receipt(
        provider_root,
        checked_at="2026-07-24T00:00:00Z",
        suffix="stale-trio",
        rows=[_provider_row(model, is_callable=True) for model in trio],
    )

    result = subprocess.run(
        [*MODULE_COMMAND, "newrun", "--recommend", "--json"],
        cwd=REPO_ROOT,
        env=_newrun_recommend_env(
            archive=tmp_path / "archive",
            provider_root=provider_root,
        ),
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["recommendation"]["selected_preset"] is None
    assert payload["selected"] is None
    assert payload["recommendation"]["provider_selftest"]["routes"] == {}


def test_archive_movement_requires_comparable_executed_unsaturated_delta() -> None:
    from dharma_swarm.forge_lab.newrun_recommend import _has_archive_movement

    def run(stats: dict[str, object]) -> dict[str, object]:
        return {"closeout": {"stats": stats}}

    legacy = {
        "seed_pass_rate": 0.0,
        "best_pass_rate": 1.0,
    }
    comparable = {
        "descriptive_movement_eligible": True,
        "evidence_level": "L0_LegacyConfigurationSignal",
        "research_interpretation": "configuration_search_signal",
        "paired_lift_claim_eligible": False,
        "authority_granted": False,
        "same_panel_comparable": True,
        "executed_phenotype_changes": 1,
        "unique_task_ids": 5,
        "seed_panel_saturated": False,
        "observed_best_delta": 0.25,
    }

    assert _has_archive_movement(run(legacy)) is False
    assert _has_archive_movement(
        run({**comparable, "executed_phenotype_changes": 0})
    ) is False
    assert _has_archive_movement(
        run(
            {
                **comparable,
                "seed_pass_rate": 0.0,
                "best_pass_rate": 1.0,
                "unique_task_ids": 1,
            }
        )
    ) is False
    assert _has_archive_movement(
        run({**comparable, "seed_panel_saturated": True})
    ) is False
    assert _has_archive_movement(
        run({**comparable, "observed_best_delta": 0.0})
    ) is False
    assert _has_archive_movement(run(comparable)) is True
