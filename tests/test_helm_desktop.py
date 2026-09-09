"""Behavioral checks at the actual desktop CLI and process boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError
from dharma_swarm.helm_desktop import profiles, runtime, workspace

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/helm_desktop.py"


@pytest.fixture
def config(tmp_path: Path) -> DesktopConfig:
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\nexit 0\n")
    (repo / "notes.md").write_text("Research notes\n")
    return DesktopConfig(repo, tmp_path / "private state")


def invoke(config: DesktopConfig, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CLI), "--repo-root", str(config.repo_root),
                           "--state-dir", str(config.state_dir), "--json", *args],
                          env=env, capture_output=True, text=True, timeout=10)


@pytest.mark.parametrize("args", [("status",), ("doctor",), ("catalog",), ("workspace", "preview"),
                                  ("install", "preview"), ("restore",)])
def test_observation_cli_creates_nothing(config: DesktopConfig, args: tuple[str, ...]) -> None:
    result = invoke(config, *args)
    assert result.returncode == (1 if args == ("doctor",) else 0), result.stderr + result.stdout
    assert isinstance(json.loads(result.stdout), dict)
    assert not config.state_dir.exists()


def test_global_options_work_after_subcommands(config: DesktopConfig) -> None:
    result = subprocess.run([sys.executable, str(CLI), "workspace", "preview", "--profile", "research",
                             "--repo-root", str(config.repo_root), "--state-dir", str(config.state_dir), "--json"],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["profile"]["project_root"] == str(config.repo_root)


def test_invalid_socket_never_reaches_process_execution(config: DesktopConfig) -> None:
    result = invoke(config, "focus", "--socket", "default")
    assert result.returncode == 1
    assert "CODEX_MANAGED" in json.loads(result.stdout)["error"]
    assert not config.state_dir.exists()


def test_install_requires_explicit_apply(config: DesktopConfig) -> None:
    result = invoke(config, "install", "apply")
    assert result.returncode == 2
    assert not config.state_dir.exists()


@pytest.fixture
def fake_apps(tmp_path: Path) -> tuple[dict[str, str], Path]:
    directory, log = tmp_path / "fake-bin", tmp_path / "processes.jsonl"
    directory.mkdir()
    code = f"""#!{sys.executable}
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ['HELM_TEST_LOG'], 'a') as stream:
    stream.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name == 'tmux':
    if 'has-session' in sys.argv:
        sys.exit(int(os.environ.get('HELM_TEST_SESSION_MISSING', '0')))
    if 'list-clients' in sys.argv:
        print('/dev/ttysHELM')
elif name == 'wezterm' and 'list' in sys.argv:
    print(json.dumps([{{'pane_id': 91, 'tab_id': 92, 'tty_name': '/dev/ttysHELM'}}]))
"""
    for name in ("tmux", "wezterm", "open"):
        path = directory / name
        path.write_text(code)
        path.chmod(0o700)
    return {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}", "HELM_TEST_LOG": str(log),
            "TMUX": "operator-owned-default-context"}, log


def test_focus_cli_targets_existing_exact_private_seat(config: DesktopConfig, fake_apps: tuple[dict[str, str], Path]) -> None:
    env, log = fake_apps
    result = invoke(config, "focus", env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["outcome"] == "focused"
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    tmux_calls = [call for call in calls if call[0] == "tmux"]
    assert all(call[1:5] == ["-L", config.socket, "-f", "/dev/null"] for call in tmux_calls)
    assert all(f"={config.session}" in call for call in tmux_calls)
    assert ["wezterm", "cli", "--no-auto-start", "activate-pane", "--pane-id", "91"] in calls
    assert not any("new-session" in call or "bash" in call for call in calls)


def test_focus_missing_session_does_not_start_bridge(config: DesktopConfig, fake_apps: tuple[dict[str, str], Path]) -> None:
    env, log = fake_apps
    result = invoke(config, "focus", env={**env, "HELM_TEST_SESSION_MISSING": "1"})
    assert result.returncode == 1
    assert "use `start` explicitly" in json.loads(result.stdout)["error"]
    assert len(log.read_text().splitlines()) == 1


def test_start_reuses_existing_launcher_and_passes_mirror_environment(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def runner(argv: list[str], *, env: dict[str, str], timeout: float = 5) -> subprocess.CompletedProcess[str]:
        calls.append((argv, env))
        return subprocess.CompletedProcess(argv, 1 if "has-session" in argv else 0, "verified", "")

    monkeypatch.setattr(runtime, "observe", lambda _: {"availability": "fresh", "snapshot": {"phase": "idle"}})
    result = runtime.start(config, runner=runner)
    assert result["outcome"] == "started"
    assert calls[1][0] == ["bash", str(config.repo_root / "scripts/start_terminal_tui_tmux.sh")]
    env = calls[1][1]
    assert "TMUX" not in env
    assert env["DHARMA_HELM_DESKTOP_STATUS_FILE"] == str(config.state_dir / "status.json")
    assert env["DHARMA_HELM_DESKTOP_TMUX_SOCKET"] == config.socket
    assert env["DHARMA_TERMINAL_TMUX_SESSION"] == config.session


def test_start_refuses_existing_unobserved_seat(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(runtime, "observe", lambda _: {"availability": "stale", "snapshot": {"phase": "idle"}})
    with pytest.raises(DesktopError, match="private seat already exists"):
        runtime.start(config, runner=runner)
    assert len(calls) == 1


def test_start_waits_for_matching_owner_before_reporting_ready(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    observations = iter([{"availability": "unavailable", "snapshot": None},
                         {"availability": "fresh", "snapshot": {"phase": "idle", "owner": {"id": "real-owner"}}}])
    monkeypatch.setattr(runtime, "observe", lambda _: next(observations))
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1 if "has-session" in argv else 0, "", "")

    result = runtime.start(config, runner=runner)
    assert result["desktop_ready"]
    assert result["owner"] == {"id": "real-owner"}


def test_start_missing_mirror_reports_partial_and_preserves_executor(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter([0.0, 4.0])
    calls: list[list[str]] = []
    monkeypatch.setattr(runtime.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runtime, "observe", lambda _: {"availability": "unavailable", "snapshot": None})

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1 if "has-session" in argv else 0, "", "")

    result = runtime.start(config, runner=runner)
    assert result["outcome"] == "partial"
    assert not result["desktop_ready"]
    assert not any("kill-session" in call for call in calls)


def save_profile(config: DesktopConfig, resources: list[dict[str, str]]) -> None:
    path = config.state_dir / "profiles/research.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": profiles.SCHEMA, "name": "research", "label": "Research",
                                "project_root": str(config.repo_root), "resources": resources}))


@pytest.mark.parametrize("resource", [
    {"id": "bad", "app": "terminal", "kind": "helm", "shell": "touch /tmp/pwned"},
    {"id": "bad", "app": "editor", "kind": "path", "path": "../outside"},
    {"id": "bad", "app": "browser", "kind": "url", "url": "file:///etc/passwd"},
    {"id": "bad", "app": "browser", "kind": "url", "url": "https://secret:credential@example.com"},
    {"id": "bad", "app": "browser", "kind": "url", "url": "https://[bad-ipv6"},
])
def test_profiles_reject_untyped_or_escaping_actions(config: DesktopConfig, resource: dict[str, str]) -> None:
    save_profile(config, [resource])
    with pytest.raises(DesktopError):
        profiles.load_profile(config)


def test_editor_path_cannot_escape_via_symlink(config: DesktopConfig, tmp_path: Path) -> None:
    (tmp_path / "private.txt").write_text("not project context")
    (config.repo_root / "escape").symlink_to(tmp_path / "private.txt")
    save_profile(config, [{"id": "bad", "app": "editor", "kind": "path", "path": "escape"}])
    with pytest.raises(DesktopError, match="symlink"):
        profiles.load_profile(config)


def test_browser_open_once_is_receipt_backed_and_no_shell(config: DesktopConfig) -> None:
    url = "https://example.com/$(touch${IFS}/tmp/should-not-exist)"
    save_profile(config, [{"id": "paper", "app": "browser", "kind": "url", "url": url}])
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    first = workspace.open_workspace(config, runner=runner)
    second = workspace.open_workspace(config, runner=runner)
    assert first["resources"][0]["outcome"] == "launch_requested"
    assert second["resources"][0]["outcome"] == "already_requested"
    assert calls == [["open", url]]
    workspace.open_workspace(config, runner=runner, reopen=True)
    assert calls == [["open", url], ["open", url]]


def test_workspace_reports_partial_failures(config: DesktopConfig) -> None:
    save_profile(config, [{"id": "one", "app": "browser", "kind": "url", "url": "https://one.example"},
                          {"id": "two", "app": "browser", "kind": "url", "url": "https://two.example"}])

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1 if "one.example" in argv[-1] else 0, "", "")

    result = workspace.open_workspace(config, runner=runner)
    assert result["outcome"] == "partial"
    assert [item["outcome"] for item in result["resources"]] == ["failed", "launch_requested"]


def test_editor_reuses_observed_resource_tab(config: DesktopConfig) -> None:
    save_profile(config, [{"id": "notes", "app": "editor", "kind": "path", "path": "notes.md"}])
    panes: list[dict[str, object]] = []
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        output = ""
        if "list" in argv:
            output = json.dumps(panes)
        elif "spawn" in argv:
            panes.append({"pane_id": 9, "tab_id": 7, "tab_title": ""})
            output = "9\n"
        elif "set-tab-title" in argv:
            panes[0]["tab_title"] = argv[-1]
        return subprocess.CompletedProcess(argv, 0, output, "")

    first = workspace.open_workspace(config, runner=runner)
    second = workspace.open_workspace(config, runner=runner)
    assert first["resources"][0]["outcome"] == "opened"
    assert second["resources"][0]["outcome"] == "focused"
    assert sum("spawn" in call for call in calls) == 1
    panes.clear()
    workspace.open_workspace(config, runner=runner)
    assert sum("spawn" in call for call in calls) == 2


def test_focus_pending_attachment_does_not_duplicate_panes(config: DesktopConfig) -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        output = "[]" if "list" in argv else "4\n" if "spawn" in argv else ""
        return subprocess.CompletedProcess(argv, 0, output, "")

    assert runtime.focus(config, runner=runner)["outcome"] == "attachment_requested"
    assert runtime.focus(config, runner=runner)["outcome"] == "attachment_pending"
    assert sum("spawn" in call for call in calls) == 1


def test_status_never_promotes_wrong_repository_observation(config: DesktopConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    import dharma_swarm.terminal_bridge_desktop_status as status

    monkeypatch.setattr(status, "read_status", lambda _: {"availability": "fresh", "reason": None,
                        "snapshot": {"repo_root": "/other/tree", "seat": config.seat(), "phase": "running"}})
    result = runtime.observe(config)
    assert result["availability"] == "invalid"
    assert result["snapshot"] is None
