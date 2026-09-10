"""Exercise diagnostic-window closure against modeled process boundaries."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.helm_desktop import cli, runtime
from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError


@pytest.fixture
def config(tmp_path: Path) -> DesktopConfig:
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\n")
    return DesktopConfig(repo, tmp_path / "private state",
                         socket="CODEX_MANAGED_helm_close_test", session="helm_close_test")


class Attachments:
    """Detach changes only the requested client; every subprocess is intercepted."""

    def __init__(self, config: DesktopConfig) -> None:
        self.config = config
        self.clients = {"/dev/ttysHelm", "/dev/ttysManual"}
        self.panes: object = [{"pane_id": 91, "tty_name": "/dev/ttysHelm"}]
        self.calls: list[list[str]] = []
        self.session_exists = True
        self.inspections = 0
        self.failed_inspection: int | None = None
        self.detach_fails = False
        self.detach_stalls = False
        self.wezterm_fails = False

    def __call__(self, argv: list[str], *, env: dict[str, str], timeout: float = 5) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        assert env.get("TMUX") is None
        assert env.get("TMUX_TMPDIR") == "/tmp"
        code, output = 0, ""
        if argv[0] == "wezterm":
            assert argv == ["wezterm", "cli", "--no-auto-start", "list", "--format", "json"]
            code, output = int(self.wezterm_fails), json.dumps(self.panes)
        else:
            assert argv[:5] == ["tmux", "-L", self.config.socket, "-f", "/dev/null"]
            command = argv[5]
            if command == "has-session":
                assert argv[6:] == ["-t", f"={self.config.session}"]
                code = int(not self.session_exists)
            elif command == "list-clients":
                assert argv[6:] == ["-t", f"={self.config.session}", "-F", "#{client_tty}"]
                self.inspections += 1
                code = int(self.inspections == self.failed_inspection)
                output = "\n".join(sorted(self.clients))
            else:
                assert command == "detach-client"
                assert argv[6] == "-t" and len(argv) == 8
                code = int(self.detach_fails)
                if not code and not self.detach_stalls:
                    self.clients.discard(argv[7])
        return subprocess.CompletedProcess(argv, code, output, "injected process failure" if code else "")

    @property
    def detached(self) -> list[str]:
        return [argv[-1] for argv in self.calls if "detach-client" in argv]


def test_close_detaches_only_exact_private_seat_wezterm_clients(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TMUX", "operator-default-context")
    processes = Attachments(config)
    processes.clients.add("/dev/ttysHelmTwo")
    processes.panes = [
        {"pane_id": 91, "tty_name": "/dev/ttysHelm"},
        {"pane_id": 92, "tty_name": "/dev/ttysHelmTwo"},
        {"pane_id": 93, "tty_name": "/dev/ttysOtherProject"},
        {"pane_id": 94, "tty_name": "/dev/ttysHelm-extra"},
        {"pane_id": 91, "tty_name": "/dev/ttysHelm"},
    ]

    result = runtime.close(config, runner=processes)

    assert result["outcome"] == "closed"
    assert result["attachments_closed"] == 2
    assert result["session_preserved"] is True
    assert result["seat"] == config.seat()
    assert processes.detached == ["/dev/ttysHelm", "/dev/ttysHelmTwo"]
    assert processes.clients == {"/dev/ttysManual"}
    assert processes.session_exists
    assert not config.state_dir.exists()
    again = runtime.close(config, runner=processes)
    assert again["outcome"] == "attached_elsewhere"
    assert again["attachments_closed"] == 0
    assert again["attached_ttys"] == ["/dev/ttysManual"]
    assert processes.detached == ["/dev/ttysHelm", "/dev/ttysHelmTwo"]


def test_close_preserves_manual_clients_and_unrelated_wezterm_panes(config: DesktopConfig) -> None:
    processes = Attachments(config)
    processes.panes = [{"pane_id": 91, "tty_name": "/dev/ttysOtherProject"}]
    before = processes.clients.copy()

    result = runtime.close(config, runner=processes)

    assert result["outcome"] == "attached_elsewhere"
    assert result["attachments_closed"] == 0
    assert result["session_preserved"] is True
    assert result["attached_ttys"] == sorted(before)
    assert result["attach_argv"] == runtime.attach_argv(config)
    assert processes.clients == before
    assert processes.detached == []


def test_close_missing_seat_is_idempotent_and_does_not_launch_a_terminal(config: DesktopConfig) -> None:
    processes = Attachments(config)
    processes.session_exists = False

    first = runtime.close(config, runner=processes)
    second = runtime.close(config, runner=processes)

    assert first == second
    assert first["outcome"] == "already_closed"
    assert len(processes.calls) == 2
    assert all("has-session" in argv for argv in processes.calls)
    assert not config.state_dir.exists()


def test_close_seat_without_clients_does_not_require_wezterm(config: DesktopConfig) -> None:
    processes = Attachments(config)
    processes.clients.clear()
    processes.wezterm_fails = True

    result = runtime.close(config, runner=processes)

    assert result["outcome"] == "already_closed"
    assert processes.detached == []
    assert all(argv[0] == "tmux" for argv in processes.calls)


@pytest.mark.parametrize("failure, message", [
    ("inspection", "inspect"),
    ("detach", "could not be closed"),
    ("still_attached", "remains attached"),
    ("verification", "verif"),
    ("wezterm", "inspect|WezTerm"),
])
def test_close_propagates_inspection_detachment_and_verification_failures(
    config: DesktopConfig, failure: str, message: str,
) -> None:
    processes = Attachments(config)
    processes.failed_inspection = {"inspection": 1, "verification": 2}.get(failure)
    processes.detach_fails = failure == "detach"
    processes.detach_stalls = failure == "still_attached"
    processes.wezterm_fails = failure == "wezterm"

    with pytest.raises(DesktopError, match=message):
        runtime.close(config, runner=processes)

    assert "/dev/ttysManual" in processes.clients
    assert processes.session_exists
    if failure in {"inspection", "wezterm"}:
        assert processes.detached == []


def test_close_rejects_malformed_wezterm_inventory_before_detaching(config: DesktopConfig) -> None:
    processes = Attachments(config)
    processes.panes = {"pane_id": 91, "tty_name": "/dev/ttysHelm"}

    with pytest.raises(DesktopError, match="pane data"):
        runtime.close(config, runner=processes)

    assert processes.detached == []
    assert processes.clients == {"/dev/ttysHelm", "/dev/ttysManual"}


def test_close_cli_reports_failed_verification_instead_of_success(
    config: DesktopConfig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    processes = Attachments(config)
    processes.failed_inspection = 2
    close = runtime.close
    monkeypatch.setattr(runtime, "close", lambda selected: close(selected, runner=processes))

    code = cli.main(["--repo-root", str(config.repo_root), "--state-dir", str(config.state_dir),
                     "--socket", config.socket, "--session", config.session, "--json", "close"])

    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["ok"] is False
    assert report["action"] == "close"
    assert "verif" in report["error"]
    assert processes.clients == {"/dev/ttysManual"}


def test_cli_close_signals_failure_when_only_another_terminal_holds_the_seat(
    config: DesktopConfig, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    processes = Attachments(config)
    processes.panes = [{"pane_id": 91, "tty_name": "/dev/ttysOtherProject"}]
    close = runtime.close
    monkeypatch.setattr(runtime, "close", lambda selected: close(selected, runner=processes))

    code = cli.main(["--repo-root", str(config.repo_root), "--state-dir", str(config.state_dir),
                     "--socket", config.socket, "--session", config.session, "--json", "close"])

    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["ok"] is False
    assert report["outcome"] == "attached_elsewhere"
    assert report["detail"]
    assert processes.detached == []
