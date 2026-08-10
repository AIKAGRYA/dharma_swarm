"""Admission boundaries for governed campaigns and legacy preview surfaces."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
import sys

import pytest

from dharma_swarm.forge_lab import newrun, provider_selftest
from dharma_swarm.forge_lab.rsi_cli import build_parser


def _newrun_args(*arguments: str):
    return build_parser().parse_args(["newrun", *arguments])


def _clear_state_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "RSI_LAB_PROVIDER_SELFTEST_ROOT",
        "RSI_LAB_STATE",
        "RSI_LAB_BASE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_newrun_preview_points_only_to_governed_campaign(capsys) -> None:
    args = _newrun_args("--preset", "fast", "--json")

    assert newrun.run_newrun(args) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["selected"]["command"] == (
        "rsi campaign plan --profile forge-lab-paired-frozen-v1"
    )
    assert payload["safety_boundary"]["newrun_execute_supported"] is False
    assert payload["safety_boundary"]["signed_operator_envelope_required"] is True
    assert "dharma_swarm.forge_lab.cli" not in json.dumps(payload)


def test_newrun_human_menu_does_not_suggest_legacy_execution(capsys) -> None:
    args = _newrun_args("--preset", "fast")

    assert newrun.run_newrun(args) == 0
    output = capsys.readouterr().out

    assert "governed campaign preview" in output
    assert "rsi campaign plan --profile forge-lab-paired-frozen-v1" in output
    assert "dharma_swarm.forge_lab.cli" not in output
    assert "newrun --preset fast --execute" not in output


def test_newrun_execute_rejects_budget_authority_without_legacy_import(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    for key in (
        "FORGE_ALLOW_LIVE",
        "RSI_LAB_APPROVED",
        "RSI_LAB_SPEND_AUTHORIZED",
        "RSI_LAB_BUDGET_TOKENS",
        "RSI_LAB_BUDGET_USD",
    ):
        monkeypatch.setenv(key, "999999999")

    attempted_imports: list[str] = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.forge_lab.cli":
            attempted_imports.append(name)
            raise AssertionError("legacy live launcher import reached")
        return real_import(name, *args, **kwargs)

    def forbidden_forge_args(*_args, **_kwargs):
        raise AssertionError("legacy live arguments were constructed")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(newrun.NewRunPreset, "forge_args", forbidden_forge_args)
    args = _newrun_args(
        "--preset",
        "fast",
        "--execute",
        "--json",
        "--budget-tokens",
        "999999999",
        "--budget-usd",
        "999999999",
        "--max-experiment-tokens",
        "999999999",
    )

    assert newrun.run_newrun(args) == newrun.GOVERNED_CAMPAIGN_REQUIRED_EXIT
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "GOVERNED_CAMPAIGN_REQUIRED"
    assert payload["result"]["governed_entrypoint"] == (
        "rsi campaign plan --profile forge-lab-paired-frozen-v1"
    )
    assert "GOVERNED_CAMPAIGN_REQUIRED" in captured.err
    assert attempted_imports == []


def test_newrun_execute_without_preset_is_still_machine_denied(capsys) -> None:
    args = _newrun_args("--execute", "--json")

    assert newrun.run_newrun(args) == newrun.GOVERNED_CAMPAIGN_REQUIRED_EXIT
    payload = json.loads(capsys.readouterr().out)

    assert payload["error"]["code"] == "GOVERNED_CAMPAIGN_REQUIRED"
    assert payload["result"]["selected_preset"] is None


def test_direct_legacy_cli_is_retired_before_experiment_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "dharma_swarm.forge_lab.experiment", None)
    from dharma_swarm.forge_lab import cli

    result = cli.main(
        [
            "run",
            "--solver-model",
            "moonshot:kimi-k2.7-code",
            "--mutator-model",
            "moonshot:kimi-k2.7-code",
        ]
    )

    assert result == 7


def test_provider_receipt_root_has_no_home_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_state_environment(monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path / "decoy-home"))

    with pytest.raises(ValueError, match="canonical state is unbound"):
        provider_selftest._receipt_root()


def test_provider_receipt_root_resolves_explicit_state_and_base(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit"
    state = tmp_path / "canonical-state"
    base = tmp_path / "canonical-release"

    monkeypatch.setenv("RSI_LAB_PROVIDER_SELFTEST_ROOT", str(explicit))
    monkeypatch.setenv("RSI_LAB_STATE", str(state))
    monkeypatch.setenv("RSI_LAB_BASE", str(base))
    assert provider_selftest._receipt_root() == explicit

    monkeypatch.delenv("RSI_LAB_PROVIDER_SELFTEST_ROOT")
    assert provider_selftest._receipt_root() == (
        state / ".dharma" / "forge_lab" / "provider_selftests"
    )

    monkeypatch.delenv("RSI_LAB_STATE")
    assert provider_selftest._receipt_root() == (
        base / "state" / ".dharma" / "forge_lab" / "provider_selftests"
    )


def test_live_provider_probe_validates_canonical_root_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_state_environment(monkeypatch)
    monkeypatch.setattr(
        provider_selftest,
        "profile_model_ids",
        lambda profile, current_model=None: ["moonshot:kimi-k2.7-code"],
    )
    calls: list[str] = []

    def forbidden_live_row(model_id: str, *, timeout_s: int):
        calls.append(model_id)
        raise AssertionError("provider call reached without canonical state")

    monkeypatch.setattr(provider_selftest, "_live_row", forbidden_live_row)

    with pytest.raises(ValueError, match="signed probe authority"):
        provider_selftest.run_provider_selftest(
            profile="frontier",
            live=True,
            require_independent_routes=1,
        )
    assert calls == []


def test_cli_live_provider_probe_is_denied_before_provider_import(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    attempted_imports: list[str] = []
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "dharma_swarm.forge_lab.provider_selftest":
            attempted_imports.append(name)
            raise AssertionError("provider selftest import reached")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    from dharma_swarm.forge_lab.rsi_cli import main

    assert (
        main(
            [
                "provider",
                "selftest",
                "--profile",
                "frontier",
                "--live",
                "--json",
            ]
        )
        == 7
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "GOVERNED_PROBE_AUTHORITY_REQUIRED"
    assert attempted_imports == []
