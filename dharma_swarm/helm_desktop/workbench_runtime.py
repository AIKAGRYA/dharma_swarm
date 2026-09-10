"""A dedicated terminal window for an OpenCode-owned Helm coding session.

Closing the window detaches its private tmux client. OpenCode owns conversation
history and tool execution; the older Helm bridge remains a separate observer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any

from .config import DesktopConfig, DesktopError
from .runtime import run
from .storage import read_json, state_path, write_bytes, write_json


def seat(config: DesktopConfig) -> dict[str, str]:
    suffix = hashlib.sha256(str(config.state_dir).encode()).hexdigest()[:10]
    return {"tmux_socket": f"CODEX_MANAGED_helm_workbench_{suffix}", "tmux_session": "helm_workbench"}


def _env(config: DesktopConfig) -> dict[str, str]:
    env = dict(os.environ)
    for key in ("TMUX", "WEZTERM_PANE", "WEZTERM_UNIX_SOCKET"):
        env.pop(key, None)
    env.update({"TMUX_TMPDIR": "/tmp", "PYTHONPATH": str(config.repo_root), "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def _tmux(config: DesktopConfig, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["tmux", "-L", seat(config)["tmux_socket"], "-f", "/dev/null", *args], env=_env(config))


def _identity(config: DesktopConfig) -> dict[str, str]:
    return {"repo_root": str(config.repo_root), "state_dir": str(config.state_dir), **seat(config)}


def _public_configuration(value: object) -> dict[str, Any]:
    keys = {"argv", "config_path", "tui_config_path", "model", "enabled_providers",
            "api_access", "api_access_semantics", "resume_scope", "subscription_auth", "model_semantics"}
    if not isinstance(value, dict) or set(value) != keys:
        raise DesktopError("the workbench launch record has an invalid public configuration")
    if (type(value["api_access"]) is not bool
            or any(not isinstance(value[name], str) for name in keys - {"api_access", "argv", "enabled_providers"})
            or any(not isinstance(value[name], list) or any(not isinstance(item, str) for item in value[name])
                   for name in ("argv", "enabled_providers"))):
        raise DesktopError("the workbench launch record has malformed public fields")
    return dict(value)


def _session_exists(config: DesktopConfig) -> bool:
    return _tmux(config, "has-session", "-t", "=helm_workbench").returncode == 0


def _verify_session(config: DesktopConfig) -> bool:
    if not _session_exists(config):
        return False
    # Option commands parse their target differently from has-session/list-panes.
    # The exact session was verified above; use its full name for option lookup.
    marker = _tmux(config, "show-options", "-qv", "-t", "helm_workbench", "@helm_workbench_state")
    if marker.returncode or marker.stdout.strip() != str(config.state_dir):
        raise DesktopError("the private workbench session has another owner; it was preserved")
    pane = _tmux(config, "list-panes", "-t", "=helm_workbench", "-F", "#{pane_dead} #{pane_current_path}")
    if pane.returncode or not any(line == f"0 {config.repo_root}" for line in pane.stdout.splitlines()):
        raise DesktopError("the workbench executor is unavailable or belongs to another directory")
    return True


def _window(config: DesktopConfig) -> tuple[dict[str, Any], dict[str, str]] | None:
    record = read_json(config.state_dir, "workbench/window.json")
    if not record or record.get("identity") != _identity(config):
        return None
    sock, tty, pane = record.get("wezterm_socket"), record.get("tty"), record.get("pane_id")
    if not isinstance(sock, str) or not sock.startswith("/") or not isinstance(tty, str) or type(pane) is not int:
        return None
    clients = _tmux(config, "list-clients", "-t", "=helm_workbench", "-F", "#{client_tty}")
    if clients.returncode or tty not in clients.stdout.splitlines():
        return None
    env = {**_env(config), "WEZTERM_UNIX_SOCKET": sock}
    result = run(["wezterm", "cli", "--no-auto-start", "list", "--format", "json"], env=env)
    if result.returncode:
        raise DesktopError("the workbench client is attached but its window could not be inspected")
    try:
        panes = json.loads(result.stdout) if result.returncode == 0 else []
    except ValueError:
        return None
    if not isinstance(panes, list) or not any(
        isinstance(item, dict) and item.get("pane_id") == pane and item.get("tty_name") == tty
        for item in panes
    ):
        return None
    return record, env


def _wezterm_config(config: DesktopConfig) -> Path:
    # Omarchy's Tokyo Night palette; use opaque surfaces and native Mac controls.
    source = """local wezterm = require 'wezterm'
local config = wezterm.config_builder()
config.color_scheme = 'Tokyo Night'
config.font_size = 14
config.initial_cols = 120
config.initial_rows = 36
config.window_background_opacity = 1
config.macos_window_background_blur = 0
config.window_decorations = 'TITLE | RESIZE'
config.window_close_confirmation = 'NeverPrompt'
config.exit_behavior = 'Close'
config.hide_tab_bar_if_only_one_tab = true
config.window_padding = { left = 18, right = 18, top = 12, bottom = 12 }
config.default_cursor_style = 'BlinkingBar'
config.keys = {
  {key='w', mods='CMD', action=wezterm.action.CloseCurrentTab{confirm=false}},
  {key='p', mods='CMD', action=wezterm.action.SendKey{key='p', mods='CTRL'}},
}
wezterm.on('format-window-title', function() return 'Helm — OpenCode Workbench' end)
return config
"""
    write_bytes(config.state_dir, "workbench/wezterm.lua", source.encode())
    return state_path(config.state_dir, "workbench/wezterm.lua")


def _internal_argv(config: DesktopConfig, operation: str) -> list[str]:
    return [sys.executable, "-m", __name__, operation, "--repo-root", str(config.repo_root),
            "--state-dir", str(config.state_dir)]


def open_workbench(config: DesktopConfig, *, model: str | None = None,
                   api_access: bool | None = None) -> dict[str, Any]:
    from .workbench_config import prepare_workbench

    for binary in ("opencode", "tmux", "wezterm", "open"):
        if not shutil.which(binary):
            raise DesktopError(f"{binary} is required to open the workbench")
    settings = read_json(config.state_dir, "workbench/settings.json") or {}
    if settings and settings.get("identity") != _identity(config):
        raise DesktopError("workbench settings belong to another workspace")
    selected_model = model if model is not None else settings.get("model")
    selected_api = api_access if api_access is not None else settings.get("api_access", False)
    live = _verify_session(config)
    if live and (model is not None or api_access is not None) and (
        selected_model != settings.get("model") or selected_api != settings.get("api_access", False)
    ):
        raise DesktopError("workbench is already running; change models with F4, or quit OpenCode before changing launch settings")
    if live:
        launch = read_json(config.state_dir, "workbench/launch.json") or {}
        if launch.get("identity") != _identity(config) or not isinstance(launch.get("configuration"), dict):
            raise DesktopError("the live workbench has no matching launch record; its configuration was preserved")
        configuration = _public_configuration(launch["configuration"])
    else:
        prepared = prepare_workbench(config, model=selected_model, api_access=selected_api)
        configuration = _public_configuration(prepared.public_report())
    if not live:
        write_json(config.state_dir, "workbench/settings.json", {
            "model": selected_model, "api_access": selected_api, "identity": _identity(config)})
        result = _tmux(config, "new-session", "-d", "-s", "helm_workbench", "-x", "120", "-y", "36",
                       "-c", str(config.repo_root), shlex.join(_internal_argv(config, "run")))
        if result.returncode:
            raise DesktopError("could not start the private coding session")
        marker = _tmux(config, "set-option", "-t", "helm_workbench", "@helm_workbench_state", str(config.state_dir))
        chrome = _tmux(config, "set-option", "-t", "helm_workbench", "status", "off")
        if marker.returncode or chrome.returncode:
            _tmux(config, "kill-session", "-t", "=helm_workbench")
            raise DesktopError("the newly created workbench could not establish its ownership")
        write_json(config.state_dir, "workbench/launch.json", {
            "identity": _identity(config), "configuration": configuration})
    current = _window(config)
    if current:
        record, env = current
        focused = run(["wezterm", "cli", "--no-auto-start", "activate-pane", "--pane-id", str(record["pane_id"])], env=env)
        if focused.returncode:
            raise DesktopError("could not focus the workbench window")
        return {**configuration, "action": "workbench.open", "outcome": "focused", "seat": seat(config),
                "gui_pid": record.get("gui_pid")}
    profile = _wezterm_config(config)
    log = state_path(config.state_dir, "workbench/window.log")
    with log.open("ab") as stream:
        os.chmod(log, 0o600)
        # LaunchServices registers and activates a normal Mac application. Direct
        # wezterm-gui execution can strand a second instance on another Space.
        gui = subprocess.Popen(["open", "-n", "-a", "WezTerm", "--args", "--config-file", str(profile), "start", "--always-new-process",
                                "--cwd", str(config.repo_root), "--", *_internal_argv(config, "attach")],
                               env=_env(config), cwd=config.repo_root, stdin=subprocess.DEVNULL,
                               stdout=stream, stderr=stream, start_new_session=True)
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        current = _window(config)
        if current:
            break
        if gui.poll() not in (None, 0):
            raise DesktopError(f"the workbench window did not open; inspect {log}")
        time.sleep(0.1)
    opened = current is not None and _verify_session(config)
    report = {**configuration, "action": "workbench.open", "outcome": "opened" if opened else "partial",
              "seat": seat(config), "gui_pid": current[0].get("gui_pid") if current else None,
              "launcher_pid": gui.pid, "window_verified": opened,
              "detail": "Coding workspace is open." if opened else
                  f"The window did not attach within 6 seconds. The coding session was preserved; inspect {log}."}
    write_json(config.state_dir, "workbench/last_open.json", report)
    return report


def close_workbench(config: DesktopConfig) -> dict[str, Any]:
    if not _verify_session(config):
        return {"action": "workbench.close", "outcome": "already_closed", "seat": seat(config)}
    current = _window(config)
    if current is None:
        attached = _tmux(config, "list-clients", "-t", "=helm_workbench", "-F", "#{client_tty}")
        if attached.returncode:
            raise DesktopError("could not inspect the private workbench attachments")
        ttys = sorted(tty for tty in attached.stdout.splitlines() if tty)
        if not ttys:
            return {"action": "workbench.close", "outcome": "already_closed", "seat": seat(config)}
        # The window this invocation owns is unverified, but a client is still
        # attached elsewhere. Report it rather than claiming the window is gone.
        return {"action": "workbench.close", "outcome": "attached_elsewhere", "seat": seat(config),
                "session_preserved": True, "attached_ttys": ttys,
                "detail": "the coding session is attached in another window; close it there"}
    record, _ = current
    result = _tmux(config, "detach-client", "-t", record["tty"])
    if result.returncode:
        raise DesktopError("the workbench attachment could not be closed")
    clients = _tmux(config, "list-clients", "-t", "=helm_workbench", "-F", "#{client_tty}")
    if clients.returncode:
        raise DesktopError("workbench close was requested but its completion could not be verified")
    if record["tty"] in clients.stdout.splitlines():
        raise DesktopError("workbench close was requested but the client remains attached")
    return {"action": "workbench.close", "outcome": "closed", "session_preserved": True, "seat": seat(config)}


def status(config: DesktopConfig) -> dict[str, Any]:
    live = _verify_session(config)
    return {"action": "workbench.status", "session_running": live,
            "window_attached": _window(config) is not None if live else False,
            "seat": seat(config), "authority": "observation_only"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("run", "attach"))
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    config = DesktopConfig(Path(args.repo_root), Path(args.state_dir))
    if args.operation == "attach":
        if not _verify_session(config):
            raise DesktopError("the owned workbench session is no longer running")
        sock = os.environ.get("WEZTERM_UNIX_SOCKET", "")
        pane = os.environ.get("WEZTERM_PANE", "")
        if not sock or not pane.isdigit() or not os.isatty(0):
            raise DesktopError("workbench attachment requires its own WezTerm window")
        write_json(config.state_dir, "workbench/window.json", {
            "identity": _identity(config), "wezterm_socket": sock,
            "pane_id": int(pane), "tty": os.ttyname(0), "gui_pid": os.getppid()})
        argv = ["tmux", "-L", seat(config)["tmux_socket"], "-f", "/dev/null", "attach-session", "-t", "=helm_workbench"]
        os.execvpe("tmux", argv, _env(config))
    from .workbench_config import prepare_workbench

    settings = read_json(config.state_dir, "workbench/settings.json") or {}
    if settings.get("identity") != _identity(config):
        raise DesktopError("workbench settings belong to another workspace")
    prepared = prepare_workbench(config, model=settings.get("model"), api_access=settings.get("api_access", False))
    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
    # reason=argv is a fixed internal tuple (resolved executable, repo root, validated model id)
    # passed as a list without a shell; the environment is a filtered allowlist built in
    # prepare_workbench, so no caller-controlled string reaches a command interpreter.
    return subprocess.call(prepared.argv, env=prepared.environment, cwd=config.repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
