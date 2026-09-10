"""Workbench process boundaries, plus one disposable real tmux ownership check."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError
from dharma_swarm.helm_desktop import workbench_config, workbench_runtime as runtime
from dharma_swarm.helm_desktop.storage import write_json

OWN_TTY = "/dev/ttys076"
OTHER_TTY = "/dev/ttys019"
OWN_SOCKET = "/tmp/helm-window.sock"
OTHER_SOCKET = "/tmp/operator-window.sock"
OWN_GUI_PID = 54321
SECRET = "fixture-environment-value-never-for-reports"


class Boundary:
    """Fake tmux and WezTerm at the actual argv/environment boundary."""

    def __init__(self, config: DesktopConfig) -> None:
        self.config = config
        self.prepared = workbench_config.PreparedWorkbench(
            argv=("/fixture/bin/opencode", str(config.repo_root), "--continue", "--model", "test/model"),
            environment={"API_KEY": SECRET},
            config_path=str(config.state_dir / "workbench/opencode.json"),
            tui_config_path=str(config.state_dir / "workbench/tui.json"),
            model="test/model", enabled_providers=("test",), api_access=False,
        )
        self.live = True
        self.marker = str(config.state_dir)
        self.panes = f"0 {config.repo_root}\n"
        self.clients = [OWN_TTY, OTHER_TTY]
        self.gui_panes: dict[str, Any] = {
            OWN_SOCKET: [{"pane_id": 76, "tty_name": OWN_TTY}],
            OTHER_SOCKET: [{"pane_id": 19, "tty_name": OTHER_TTY}],
        }
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.prepares: list[dict[str, Any]] = []
        self.gui_calls: list[tuple[list[str], dict[str, Any]]] = []
        self.marker_failure = False
        self.fail_after_detach = False
        self.detached = False
        self.created = False

    def run(self, argv: list[str], *, env: dict[str, str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((argv, dict(env)))
        code, output = 0, ""
        if argv[0] == "tmux":
            assert argv[1:5] == ["-L", runtime.seat(self.config)["tmux_socket"], "-f", "/dev/null"]
            assert "TMUX" not in env
            operation = argv[5]
            if operation == "has-session":
                code = 0 if self.live else 1
            elif operation == "show-options":
                assert argv[argv.index("-t") + 1] == "helm_workbench"
                output = self.marker + "\n"
            elif operation == "list-panes":
                output = self.panes
            elif operation == "list-clients":
                code = 1 if self.detached and self.fail_after_detach else 0
                output = "\n".join(self.clients) + "\n"
            elif operation == "detach-client":
                assert argv[-2:] == ["-t", OWN_TTY]
                self.clients.remove(OWN_TTY)
                self.detached = True
            elif operation == "new-session":
                self.live = True
                self.marker = ""
                self.created = True
            elif operation == "kill-session":
                assert self.created, "cleanup must not kill a pre-existing session"
                assert argv[-2:] == ["-t", "=helm_workbench"]
                self.live = False
            elif operation == "set-option":
                assert argv[argv.index("-t") + 1] == "helm_workbench"
                if "@helm_workbench_state" in argv:
                    code = 1 if self.marker_failure else 0
                    if not code:
                        self.marker = argv[-1]
            else:
                pytest.fail(f"unexpected tmux operation: {operation}")
        elif argv[:4] == ["wezterm", "cli", "--no-auto-start", "list"]:
            output = json.dumps(self.gui_panes.get(env.get("WEZTERM_UNIX_SOCKET", ""), []))
        elif argv[:4] == ["wezterm", "cli", "--no-auto-start", "activate-pane"]:
            assert argv[-1] == "76"
            assert env["WEZTERM_UNIX_SOCKET"] == OWN_SOCKET
        elif argv == ["open", "-a", "WezTerm"]:
            pass
        else:
            pytest.fail(f"unexpected process: {argv}")
        return subprocess.CompletedProcess(argv, code, output, "")

    def prepare(self, _: DesktopConfig, **kwargs: Any) -> workbench_config.PreparedWorkbench:
        self.prepares.append(kwargs)
        return self.prepared

    def record_window(self, **overrides: Any) -> None:
        write_json(self.config.state_dir, "workbench/window.json", {
            "identity": runtime._identity(self.config), "wezterm_socket": OWN_SOCKET,
            "pane_id": 76, "tty": OWN_TTY, "gui_pid": OWN_GUI_PID, **overrides,
        })

    def record_settings(self, **overrides: Any) -> None:
        write_json(self.config.state_dir, "workbench/settings.json", {
            "identity": runtime._identity(self.config), "model": "test/model", "api_access": False,
            **overrides,
        })

    def record_launch(self, **overrides: Any) -> None:
        write_json(self.config.state_dir, "workbench/launch.json", {
            "identity": runtime._identity(self.config),
            "configuration": self.prepared.public_report(), **overrides,
        })

    def spawn_window(self, argv: list[str], **kwargs: Any) -> Any:
        self.gui_calls.append((argv, kwargs))
        self.record_window()
        if OWN_TTY not in self.clients:
            self.clients.append(OWN_TTY)
        return SimpleNamespace(pid=12345, poll=lambda: None)


@pytest.fixture
def boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Boundary:
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\n")
    result = Boundary(DesktopConfig(repo, tmp_path / "desktop state"))
    monkeypatch.setattr(runtime, "run", result.run)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: f"/fixture/bin/{name}")
    monkeypatch.setattr(workbench_config, "prepare_workbench", result.prepare)
    monkeypatch.setenv("TMUX", "operator-owned-default-session")
    monkeypatch.setenv("WEZTERM_PANE", "19")
    monkeypatch.setenv("WEZTERM_UNIX_SOCKET", OTHER_SOCKET)
    monkeypatch.setenv("FIXTURE_API_KEY", SECRET)
    def no_window(*_: Any, **__: Any) -> Any:
        pytest.fail("this operation must not launch a GUI")
    monkeypatch.setattr(runtime.subprocess, "Popen", no_window)
    return result


def assert_no_destructive_calls(boundary: Boundary) -> None:
    assert not any(
        token in {"kill-server", "kill-session", "kill-pane", "kill-window", "detach-client"}
        for argv, _ in boundary.calls for token in argv
    )


def test_private_seat_is_stable_and_separate_per_state_directory(boundary: Boundary) -> None:
    first = runtime.seat(boundary.config)
    other = DesktopConfig(boundary.config.repo_root, boundary.config.state_dir.parent / "second state")
    assert first == runtime.seat(boundary.config)
    assert first["tmux_socket"].startswith("CODEX_MANAGED_helm_workbench_")
    assert first["tmux_socket"] != runtime.seat(other)["tmux_socket"]
    assert first["tmux_session"] == "helm_workbench"


def test_missing_session_status_is_observation_only_and_does_not_write(boundary: Boundary) -> None:
    boundary.live = False
    result = runtime.status(boundary.config)
    assert result["session_running"] is False
    assert result["window_attached"] is False
    assert SECRET not in json.dumps(result)
    assert not boundary.config.state_dir.exists()
    assert_no_destructive_calls(boundary)


@pytest.mark.parametrize("operation", [runtime.open_workbench, runtime.close_workbench, runtime.status])
def test_wrong_session_owner_is_preserved(boundary: Boundary, operation: Any) -> None:
    boundary.marker = "/another/owner"
    with pytest.raises(DesktopError):
        operation(boundary.config)
    assert not boundary.prepares
    assert not boundary.config.state_dir.exists()
    assert_no_destructive_calls(boundary)


@pytest.mark.parametrize("pane_state", ["1 {repo}\n", "0 /another/checkout\n", ""])
def test_dead_or_different_checkout_is_not_reported_running(boundary: Boundary, pane_state: str) -> None:
    boundary.panes = pane_state.format(repo=boundary.config.repo_root)
    with pytest.raises(DesktopError):
        runtime.status(boundary.config)
    assert_no_destructive_calls(boundary)


def test_close_detaches_only_verified_tty_and_preserves_other_clients(boundary: Boundary) -> None:
    boundary.record_window()
    result = runtime.close_workbench(boundary.config)
    assert result["outcome"] == "closed"
    assert result["session_preserved"] is True
    assert boundary.clients == [OTHER_TTY]
    assert boundary.live is True
    detach = [argv for argv, _ in boundary.calls if "detach-client" in argv]
    assert len(detach) == 1
    assert detach[0][-2:] == ["-t", OWN_TTY]
    assert not any(token.startswith("kill-") for argv, _ in boundary.calls for token in argv)
    wezterm_calls = [(argv, env) for argv, env in boundary.calls if argv[0] == "wezterm"]
    assert all(env["WEZTERM_UNIX_SOCKET"] == OWN_SOCKET for _, env in wezterm_calls)
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize("mismatch", ["identity", "socket", "pane", "tty", "client", "wezterm_tty"])
def test_close_does_not_touch_mismatched_or_operator_pane(boundary: Boundary, mismatch: str) -> None:
    overrides = {
        "identity": {"identity": {"repo_root": "/other"}},
        "socket": {"wezterm_socket": OTHER_SOCKET},
        "pane": {"pane_id": 19},
        "tty": {"tty": OTHER_TTY},
    }.get(mismatch, {})
    if mismatch == "client":
        boundary.clients = [OTHER_TTY]
    elif mismatch == "wezterm_tty":
        boundary.gui_panes[OWN_SOCKET] = [{"pane_id": 76, "tty_name": OTHER_TTY}]
    boundary.record_window(**overrides)
    before = list(boundary.clients)
    result = runtime.close_workbench(boundary.config)
    assert result["outcome"] == "already_closed"
    assert boundary.clients == before
    assert_no_destructive_calls(boundary)


def test_close_does_not_claim_success_when_followup_probe_fails(boundary: Boundary) -> None:
    boundary.record_window()
    boundary.fail_after_detach = True
    with pytest.raises(DesktopError):
        runtime.close_workbench(boundary.config)


@pytest.mark.parametrize("settings", [{"model": "another/model"}, {"api_access": True}])
def test_explicit_launch_settings_cannot_retarget_existing_run(boundary: Boundary, settings: dict[str, Any]) -> None:
    boundary.record_settings()
    boundary.record_window()
    with pytest.raises(DesktopError):
        runtime.open_workbench(boundary.config, **settings)
    assert not boundary.prepares
    assert_no_destructive_calls(boundary)


def test_focusing_existing_run_does_not_reprepare_or_rewrite_its_configuration(boundary: Boundary) -> None:
    boundary.record_settings()
    boundary.record_launch()
    boundary.record_window()
    result = runtime.open_workbench(boundary.config)
    assert result["outcome"] == "focused"
    assert not boundary.prepares
    assert not boundary.gui_calls
    assert SECRET not in json.dumps(result)
    assert_no_destructive_calls(boundary)


def test_external_settings_edits_cannot_retarget_a_live_session(boundary: Boundary) -> None:
    boundary.record_settings(model="externally/changed", api_access=True)
    boundary.record_launch()
    boundary.record_window()
    result = runtime.open_workbench(boundary.config)
    assert result["outcome"] == "focused"
    assert result["model"] == "test/model"
    assert not boundary.prepares


@pytest.mark.parametrize("foreign", [False, True])
def test_missing_or_foreign_launch_record_cannot_reprepare_live_session(
    boundary: Boundary, foreign: bool,
) -> None:
    boundary.record_settings()
    boundary.record_window()
    if foreign:
        boundary.record_launch(identity={"repo_root": "/other"})
    with pytest.raises(DesktopError):
        runtime.open_workbench(boundary.config)
    assert not boundary.prepares
    assert_no_destructive_calls(boundary)


def test_launch_receipt_cannot_forge_observations_or_leak_environment(boundary: Boundary) -> None:
    boundary.record_settings()
    boundary.record_window()
    boundary.record_launch(configuration={
        **boundary.prepared.public_report(), "outcome": "forged", "seat": {"tmux_socket": "default"},
        "window_verified": True, "environment": {"API_KEY": SECRET},
    })
    try:
        result = runtime.open_workbench(boundary.config)
    except DesktopError:
        return  # Rejecting malformed stored configuration is also safe.
    assert result["outcome"] == "focused"
    assert result["seat"] == runtime.seat(boundary.config)
    assert SECRET not in json.dumps(result)
    assert "environment" not in result


def test_foreign_settings_do_not_select_model_or_api_access(boundary: Boundary) -> None:
    boundary.live = False
    boundary.record_settings(identity={"repo_root": "/other"}, model="foreign/paid", api_access=True)
    with pytest.raises(DesktopError):
        runtime.open_workbench(boundary.config)
    assert not boundary.prepares
    assert not any("new-session" in argv for argv, _ in boundary.calls)


def test_failed_owner_marker_stops_before_launching_window(boundary: Boundary) -> None:
    boundary.live = False
    boundary.marker_failure = True
    with pytest.raises(DesktopError):
        runtime.open_workbench(boundary.config)
    assert not boundary.gui_calls
    killed = [argv for argv, _ in boundary.calls if "kill-session" in argv]
    assert killed and all(argv[-2:] == ["-t", "=helm_workbench"] for argv in killed)
    assert not boundary.live


def test_new_window_uses_private_process_and_reports_verified_attachment_only(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary.live = False
    boundary.clients = [OTHER_TTY]
    monkeypatch.setattr(runtime.subprocess, "Popen", boundary.spawn_window)
    result = runtime.open_workbench(boundary.config, model="test/model", api_access=False)
    assert result["outcome"] == "opened"
    assert result["window_verified"] is True
    assert result["gui_pid"] == OWN_GUI_PID
    assert len(boundary.gui_calls) == 1
    argv, kwargs = boundary.gui_calls[0]
    assert argv[:6] == ["open", "-n", "-a", "WezTerm", "--args", "--config-file"]
    assert "--always-new-process" in argv
    assert kwargs["cwd"] == boundary.config.repo_root
    assert not {"TMUX", "WEZTERM_PANE", "WEZTERM_UNIX_SOCKET"} & set(kwargs["env"])
    assert OTHER_TTY in boundary.clients
    assert SECRET not in json.dumps(result)
    report = boundary.config.state_dir / "workbench/last_open.json"
    assert SECRET not in report.read_text()
    assert report.stat().st_mode & 0o777 == 0o600
    assert_no_destructive_calls(boundary)


def test_successful_launch_helper_can_exit_before_window_attaches(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary.live = False
    boundary.clients = [OTHER_TTY]
    clock = [0.0]
    polls: list[int] = []
    def poll() -> int:
        polls.append(0)
        return 0
    def spawn(argv: list[str], **kwargs: Any) -> Any:
        boundary.gui_calls.append((argv, kwargs))
        return SimpleNamespace(pid=12345, poll=poll)
    def attached_after_wait(seconds: float) -> None:
        clock[0] += seconds
        boundary.record_window()
        boundary.clients.append(OWN_TTY)
    monkeypatch.setattr(runtime.subprocess, "Popen", spawn)
    monkeypatch.setattr(runtime, "time", SimpleNamespace(
        monotonic=lambda: clock[0], sleep=attached_after_wait,
    ))
    result = runtime.open_workbench(boundary.config)
    assert polls, "the helper must have exited before attachment became visible"
    assert result["outcome"] == "opened"
    assert result["window_verified"] is True
    assert result["gui_pid"] == OWN_GUI_PID
    assert result["gui_pid"] != 12345
    assert OTHER_TTY in boundary.clients


def test_successful_launch_helper_alone_does_not_prove_gui_opened(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary.live = False
    boundary.clients = [OTHER_TTY]
    clock = [0.0]
    def advance(_: float) -> None:
        clock[0] += 1
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_, **__: SimpleNamespace(pid=12345, poll=lambda: 0))
    monkeypatch.setattr(runtime, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=advance))
    result = runtime.open_workbench(boundary.config)
    assert result["outcome"] == "partial"
    assert result["window_verified"] is False
    assert result["gui_pid"] is None
    assert boundary.live is True
    assert_no_destructive_calls(boundary)


def test_failed_launch_helper_is_reported_without_touching_other_windows(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary.live = False
    boundary.clients = [OTHER_TTY]
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_, **__: SimpleNamespace(pid=12345, poll=lambda: 7))
    with pytest.raises(DesktopError):
        runtime.open_workbench(boundary.config)
    assert boundary.clients == [OTHER_TTY]
    assert boundary.live is True
    assert_no_destructive_calls(boundary)


def attach_environment(boundary: Boundary, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["workbench", "attach", "--repo-root", str(boundary.config.repo_root),
                                     "--state-dir", str(boundary.config.state_dir)])
    monkeypatch.setenv("WEZTERM_UNIX_SOCKET", OWN_SOCKET)
    monkeypatch.setenv("WEZTERM_PANE", "76")
    monkeypatch.setattr(runtime.os, "isatty", lambda _: True)
    monkeypatch.setattr(runtime.os, "ttyname", lambda _: OWN_TTY)
    monkeypatch.setattr(runtime.os, "getppid", lambda: OWN_GUI_PID)


def test_attach_rechecks_owner_before_recording_window_or_exec(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary.marker = "/another/owner"
    attach_environment(boundary, monkeypatch)
    def forbidden(*_: Any) -> None:
        pytest.fail("must not attach to an unowned session")
    monkeypatch.setattr(runtime.os, "execvpe", forbidden)
    with pytest.raises(DesktopError):
        runtime.main()
    assert not (boundary.config.state_dir / "workbench/window.json").exists()


def test_attach_execs_exact_private_session_and_records_actual_window(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch,
) -> None:
    attach_environment(boundary, monkeypatch)
    captured: list[tuple[str, list[str], dict[str, str]]] = []
    class Attached(Exception):
        pass
    def execvpe(binary: str, argv: list[str], env: dict[str, str]) -> None:
        captured.append((binary, argv, env))
        raise Attached()
    monkeypatch.setattr(runtime.os, "execvpe", execvpe)
    with pytest.raises(Attached):
        runtime.main()
    binary, argv, env = captured[0]
    assert binary == "tmux"
    assert argv[1:5] == ["-L", runtime.seat(boundary.config)["tmux_socket"], "-f", "/dev/null"]
    assert argv[-2:] == ["-t", "=helm_workbench"]
    assert not {"TMUX", "WEZTERM_PANE", "WEZTERM_UNIX_SOCKET"} & set(env)
    record = json.loads((boundary.config.state_dir / "workbench/window.json").read_text())
    assert record["tty"] == OWN_TTY
    assert record["pane_id"] == 76
    assert record["wezterm_socket"] == OWN_SOCKET
    assert record["gui_pid"] == OWN_GUI_PID
    assert SECRET not in json.dumps(record)


@pytest.mark.parametrize("foreign", [False, True])
def test_internal_run_checks_settings_identity_and_propagates_child_exit(
    boundary: Boundary, monkeypatch: pytest.MonkeyPatch, foreign: bool,
) -> None:
    boundary.record_settings(**({"identity": {"repo_root": "/other"}} if foreign else {}))
    monkeypatch.setattr(sys, "argv", ["workbench", "run", "--repo-root", str(boundary.config.repo_root),
                                     "--state-dir", str(boundary.config.state_dir)])
    child_calls: list[tuple[list[str], dict[str, Any]]] = []
    def child(argv: list[str], **kwargs: Any) -> int:
        child_calls.append((argv, kwargs))
        return 23
    monkeypatch.setattr(runtime.subprocess, "call", child)
    if foreign:
        with pytest.raises(DesktopError):
            runtime.main()
        assert not boundary.prepares
        assert not child_calls
    else:
        assert runtime.main() == 23
        assert child_calls == [(boundary.prepared.argv, {
            "env": boundary.prepared.environment, "cwd": boundary.config.repo_root,
        })]


@pytest.mark.skipif(shutil.which("tmux") is None, reason="real tmux is not installed")
def test_real_tmux_option_targets_and_exact_session_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    record_testsuite_property: Callable[[str, object], None],
) -> None:
    """Exercise production option commands; no OpenCode or graphical process runs."""
    repo = tmp_path / "source tree"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts/start_terminal_tui_tmux.sh").write_text("#!/bin/sh\n")
    config = DesktopConfig(repo, tmp_path / f"private-{uuid.uuid4().hex}")
    identity = runtime.seat(config)
    socket = identity["tmux_socket"]
    record_testsuite_property("tmux_socket", socket)
    record_testsuite_property("tmux_session", identity["tmux_session"])
    record_testsuite_property("decoy_session", "helm_workbench_extra")
    real_run = runtime.run
    real_which = shutil.which
    created = False

    def runner(argv: list[str], *, env: dict[str, str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal created
        if argv[0] == "tmux":
            assert argv[1:5] == ["-L", socket, "-f", "/dev/null"]
            result = real_run(argv, env=env, **kwargs)
            if argv[5] == "new-session" and result.returncode == 0:
                created = True
            return result
        assert argv == ["open", "-a", "WezTerm"] or argv == [
            "wezterm", "cli", "--no-auto-start", "activate-pane", "--pane-id", "76",
        ]
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(runtime, "run", runner)
    monkeypatch.setattr(runtime.shutil, "which", lambda name: real_which(name) if name == "tmux" else f"/fixture/{name}")
    prepared = Boundary(config).prepared
    monkeypatch.setattr(workbench_config, "prepare_workbench", lambda *_, **__: prepared)
    monkeypatch.setattr(runtime, "_internal_argv", lambda *_: ["/bin/sleep", "30"])
    monkeypatch.setattr(runtime, "_window", lambda _: ({"pane_id": 76}, runtime._env(config)))

    # A UUID-derived state directory gives this run a separate socket. Preserve
    # any pre-existing server anyway rather than assuming the name is unowned.
    if runtime._tmux(config, "list-sessions").returncode == 0:
        pytest.skip("the disposable socket is unexpectedly already owned")
    try:
        decoy = runtime._tmux(config, "new-session", "-d", "-s", "helm_workbench_extra",
                              "-c", str(config.repo_root), "/bin/sleep", "30")
        assert decoy.returncode == 0, decoy.stderr
        assert runtime._verify_session(config) is False
        result = runtime.open_workbench(config, model="test/model", api_access=False)
        assert result["outcome"] == "focused"
        assert runtime._verify_session(config) is True
        record_testsuite_property("executor_verified_on_exact_socket", True)
        option = runtime._tmux(config, "show-options", "-qv", "-t", "helm_workbench", "status")
        assert option.returncode == 0 and option.stdout.strip() == "off"
        stopped = runtime._tmux(config, "kill-session", "-t", "=helm_workbench")
        assert stopped.returncode == 0, stopped.stderr
        assert runtime._tmux(config, "has-session", "-t", "=helm_workbench_extra").returncode == 0
        assert runtime._verify_session(config) is False
    finally:
        if created:
            cleaned = runtime._tmux(config, "kill-server")
            record_testsuite_property("cleanup_exit_code", cleaned.returncode)
            assert cleaned.returncode == 0, cleaned.stderr
            assert runtime._tmux(config, "list-sessions").returncode != 0
            record_testsuite_property("private_server_removed", True)
