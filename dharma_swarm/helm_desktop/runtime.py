"""Desktop process adapters. The terminal launcher retains all session ownership."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

from .config import DesktopConfig, DesktopError
from .storage import read_json, state_path, write_json

Runner = Callable[..., subprocess.CompletedProcess[str]]


def run(argv: list[str], *, env: dict[str, str], timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, env=env, timeout=timeout, capture_output=True, text=True, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 124, stdout="", stderr=str(exc))


def tmux(config: DesktopConfig, *args: str, runner: Runner = run) -> subprocess.CompletedProcess[str]:
    return runner(["tmux", "-L", config.socket, "-f", "/dev/null", *args], env=config.environment())


def observe(config: DesktopConfig) -> dict[str, Any]:
    """Only read one bounded projection file; never contact a model, socket or database."""
    try:
        from dharma_swarm.terminal_bridge_desktop_status import read_status

        result = read_status(state_path(config.state_dir, "status.json"))
    except ValueError as exc:
        result = {"availability": "invalid", "reason": str(exc), "snapshot": None}
    except (ImportError, OSError) as exc:
        result = {"availability": "unavailable", "reason": str(exc), "snapshot": None}
    snapshot = result.get("snapshot")
    if isinstance(snapshot, dict) and (
        snapshot.get("repo_root") != str(config.repo_root) or snapshot.get("seat") != config.seat()
    ):
        result = {"availability": "invalid", "reason": "snapshot belongs to another repository or seat",
                  "snapshot": None}
    return {**result, "schema": "dharma.helm.desktop_observation.v1", "authority": "observation_only",
            "repo_root": str(config.repo_root), "state_dir": str(config.state_dir),
            "status_file": str(config.status_path), "seat": config.seat()}


def doctor(config: DesktopConfig) -> dict[str, Any]:
    from .profiles import load_profile

    checks: dict[str, Any] = {}
    checks["interpreter"] = {"available": sys.version_info >= (3, 11), "path": sys.executable,
                             "version": sys.version.split()[0], "required_for_start": True}
    for name in ("python3", "bun", "tmux", "wezterm", "nvim", "open", "aerospace"):
        found = shutil.which(name)
        checks[name] = {"available": found is not None, "path": found,
                        "required_for_start": name in {"bun", "tmux"}}
    checks["terminal_dependencies"] = {
        "available": (config.repo_root / "terminal/node_modules").is_dir(), "required_for_start": True}
    try:
        profile = load_profile(config)
        checks["profile"] = {"available": True, "name": profile["name"]}
    except DesktopError as exc:
        checks["profile"] = {"available": False, "reason": str(exc)}
    return {"schema": "dharma.helm.desktop_doctor.v1", "authority": "observation_only",
            "ready_to_start": all(c["available"] for c in checks.values() if c.get("required_for_start")),
            "checks": checks, "status": observe(config)}


def start(config: DesktopConfig, *, runner: Runner = run) -> dict[str, Any]:
    if sys.version_info < (3, 11):
        raise DesktopError("Helm requires Python 3.11 or newer; run this CLI with the repository virtual environment")
    for relative in ("terminal", "status.json", "last_start.json"):
        state_path(config.state_dir, relative)
    existing = tmux(config, "has-session", "-t", f"={config.session}", runner=runner).returncode == 0
    if existing:
        observed = observe(config)
        snapshot = observed.get("snapshot") or {}
        if observed["availability"] != "fresh" or snapshot.get("phase") == "closed":
            raise DesktopError("private seat already exists without a fresh matching owner; inspect it before restarting")
    # The existing launcher checks the exact pane and live bridge descendant. It
    # removes only an unhealthy session that this invocation itself created.
    environment = {**config.environment(), "DHARMA_PYTHON": sys.executable}
    result = runner(["bash", str(config.repo_root / "scripts/start_terminal_tui_tmux.sh")],
                    env=environment, timeout=30.0)
    if result.returncode:
        raise DesktopError(f"Helm launcher failed ({result.returncode}): {(result.stderr or result.stdout).strip()[-2000:]}")
    deadline = time.monotonic() + 3.0
    observed = observe(config)
    while (observed["availability"] != "fresh" or (observed.get("snapshot") or {}).get("phase") == "closed") and time.monotonic() < deadline:
        time.sleep(0.025)
        observed = observe(config)
    ready = observed["availability"] == "fresh" and (observed.get("snapshot") or {}).get("phase") != "closed"
    report = {"action": "start", "outcome": ("already_running" if existing else "started") if ready else "partial",
              "seat": config.seat(), "executor_verified_by": "scripts/start_terminal_tui_tmux.sh",
              "repo_root": str(config.repo_root), "observed_at": time.time(), "desktop_ready": ready,
              "owner": (observed.get("snapshot") or {}).get("owner"), "status": observed}
    if not ready:
        report["detail"] = "executor was verified, but no fresh matching desktop status arrived within 3 seconds; seat preserved"
    write_json(config.state_dir, "last_start.json", report)
    return report


def wezterm_panes(config: DesktopConfig, *, runner: Runner = run) -> list[dict[str, Any]] | None:
    result = runner(["wezterm", "cli", "--no-auto-start", "list", "--format", "json"], env=config.environment())
    if result.returncode:
        return None
    try:
        value = json.loads(result.stdout)
    except ValueError as exc:
        raise DesktopError("WezTerm returned invalid pane data") from exc
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise DesktopError("WezTerm pane data must be a list of objects")
    return value


def activate_pane(config: DesktopConfig, pane_id: int, *, runner: Runner = run) -> dict[str, Any]:
    result = runner(["wezterm", "cli", "--no-auto-start", "activate-pane", "--pane-id", str(pane_id)],
                    env=config.environment())
    if result.returncode:
        raise DesktopError("could not activate the existing WezTerm pane")
    foreground = runner(["open", "-a", "WezTerm"], env=config.environment())
    if foreground.returncode:
        raise DesktopError("pane selected, but macOS could not bring WezTerm to the foreground")
    return {"outcome": "focused", "pane_id": pane_id}


def attach_argv(config: DesktopConfig) -> list[str]:
    return ["/usr/bin/env", "-u", "TMUX", "TMUX_TMPDIR=/tmp", "tmux", "-L", config.socket,
            "-f", "/dev/null", "attach-session", "-t", f"={config.session}"]


def focus(config: DesktopConfig, *, runner: Runner = run) -> dict[str, Any]:
    if tmux(config, "has-session", "-t", f"={config.session}", runner=runner).returncode:
        raise DesktopError("Helm is not running on the private desktop seat; use `start` explicitly")
    observed = observe(config)
    if observed["availability"] == "invalid":
        raise DesktopError(str(observed["reason"]))
    clients = tmux(config, "list-clients", "-t", f"={config.session}", "-F", "#{client_tty}", runner=runner)
    if clients.returncode:
        raise DesktopError("could not inspect clients on the exact private Helm seat")
    ttys = set(clients.stdout.splitlines())
    panes = wezterm_panes(config, runner=runner)
    for pane in panes or []:
        if pane.get("tty_name") in ttys and type(pane.get("pane_id")) is int:
            return {"action": "focus", "seat": config.seat(), **activate_pane(config, pane["pane_id"], runner=runner)}
    pending = read_json(config.state_dir, "focus_pending.json")
    if pending and isinstance(pending.get("at"), (int, float)) and 0 <= time.time() - pending["at"] < 10:
        return {"action": "focus", "outcome": "attachment_pending", "seat": config.seat(),
                "detail": "attachment was just requested; awaiting a matching tmux client"}
    if ttys:
        # An attached client outside WezTerm is real work. Do not duplicate it.
        return {"action": "focus", "outcome": "attached_elsewhere", "seat": config.seat(),
                "detail": "the existing seat is attached in another terminal", "attach_argv": attach_argv(config)}
    if panes is None:
        # `open --args` submits a bounded GUI launch without waiting for the app
        # lifetime. This starts an attach client only; the bridge already exists.
        argv = ["open", "-a", "WezTerm", "--args", "start", "--workspace", "Helm",
                "--cwd", str(config.repo_root), "--", *attach_argv(config)]
        result = runner(argv, env=config.environment())
        if result.returncode:
            raise DesktopError("macOS could not request a WezTerm attachment")
        outcome: dict[str, Any] = {"outcome": "attachment_requested"}
    else:
        result = runner(["wezterm", "cli", "--no-auto-start", "spawn", "--new-window", "--workspace", "Helm",
                         "--cwd", str(config.repo_root), "--", *attach_argv(config)], env=config.environment())
        if result.returncode or not result.stdout.strip().isdigit():
            raise DesktopError("WezTerm could not create an attach-only pane")
        outcome = {"outcome": "attachment_requested", "pane_id": int(result.stdout.strip())}
        runner(["open", "-a", "WezTerm"], env=config.environment())
    write_json(config.state_dir, "focus_pending.json", {"at": time.time(), "seat": config.seat(), **outcome})
    return {"action": "focus", "seat": config.seat(), **outcome}
