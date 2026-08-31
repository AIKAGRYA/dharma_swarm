from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TUI_PATH = REPO_ROOT / "scripts" / "forge_lab" / "rsilab_tui.py"


def _load_tui():
    spec = importlib.util.spec_from_file_location("rsilab_tui", TUI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tui = _load_tui()


def _daily(*, digest=None, rc=1, modality="InconclusiveInfrastructure", halt=True, terminal=False, closeout=None):
    return {
        "ok": False,
        "result": {
            "ready_for_next_run": False,
            "last_cycle_healthy": False,
            "checks": {
                "halt": {"absent": halt, "path": "/root/rsi-lab/state/.dharma/forge_lab/HALT"},
                "admission": {"ready": True},
                "scheduler": {
                    "ready": False,
                    "units": {"rsi-lab-explore.timer": {"installed_digest": None}},
                },
                "models": {
                    "role_bindings": [
                        {"role": "mutator", "provider": "zhipu", "model_id": "glm-5.2"},
                        {"role": "solver", "provider": "ollama", "model_id": "deepseek-v4-pro:cloud"},
                        {"role": "verifier", "provider": "zhipu", "model_id": "glm-5.2"},
                    ]
                },
                "last_unattended": {
                    "attempt": {
                        "run_id": "unattended-test",
                        "child_result_digest": digest,
                        "epistemic_modality": modality,
                        "returncode": rc,
                        "wall_seconds": 128,
                        "closeout_state": closeout,
                    },
                    "readiness": {"terminal_success": terminal},
                },
            },
        },
    }


def test_silent_death_is_reject() -> None:
    view = tui.summarize_daily(_daily())
    assert view.verdict == "REJECT"
    assert view.silent_death is True
    assert view.digest is None
    assert "silent death" in view.why


def test_typed_negative_closeout_is_valid() -> None:
    view = tui.summarize_daily(
        _daily(
            digest="sha256:" + "a" * 64,
            rc=0,
            modality="EXPLORE_ONLY",
            terminal=True,
            closeout="measured_negative",
        )
    )
    assert view.verdict == "VALID"
    assert view.silent_death is False
    assert view.digest.startswith("sha256:")


def test_n50_is_refused() -> None:
    assert tui.refuse_scale(["run", "n50"]) is not None
    assert tui.refuse_scale(["--generations", "50"]) is not None
    assert tui.refuse_scale(["run", "1"]) is None
    rc = tui.main(["run", "n50"])
    assert rc == 3


def test_selectable_routes_drop_blocked() -> None:
    payload = {
        "ok": True,
        "result": {
            "routes": [
                {"provider": "zhipu", "model_id": "glm-5.2", "runtime_selectable": True, "runtime_blocker": None},
                {"provider": "x", "model_id": "nope", "runtime_selectable": False, "runtime_blocker": None},
                {"provider": "y", "model_id": "blocked", "runtime_selectable": True, "runtime_blocker": "missing"},
            ]
        },
    }
    routes = tui.selectable_routes(payload)
    assert [row["model_id"] for row in routes] == ["glm-5.2"]


class FakeTransport:
    def __init__(self, daily):
        self.daily = daily
        self.commands: list[str] = []

    def json(self, remote_command: str, *, timeout: int = 45):
        self.commands.append(remote_command)
        if "daily status" in remote_command:
            return self.daily
        raise AssertionError(remote_command)

    def stream(self, remote_command: str, *, timeout: int) -> int:
        self.commands.append(remote_command)
        return 7

    def raw(self, remote_command: str, *, timeout: int = 30):
        self.commands.append(remote_command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_run_refuses_when_halt_present() -> None:
    transport = FakeTransport(_daily(halt=False))
    with pytest.raises(tui.MenuError) as exc:
        tui.cmd_run(transport, yes=True)
    assert exc.value.code == "HALT_PRESENT"


def test_run_streams_explore_and_prints_reject(capsys) -> None:
    transport = FakeTransport(_daily())
    rc = tui.cmd_run(transport, yes=True)
    assert rc == 1
    assert any("rsi-unattended-explore --timeout-seconds 2700" in cmd for cmd in transport.commands)
    out = capsys.readouterr().out
    assert "REJECT" in out
    assert "n50" in out.lower()


def test_parse_cli_json_skips_preamble() -> None:
    payload = tui.parse_cli_json("HALT=ABSENT\n{\"ok\": true, \"result\": {\"x\": 1}}")
    assert payload["ok"] is True
    assert payload["result"]["x"] == 1
