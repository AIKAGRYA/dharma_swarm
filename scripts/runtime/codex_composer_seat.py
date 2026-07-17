#!/usr/bin/env python3
"""Launch and verify the unprivileged Codex Composer tmux seat."""
from __future__ import annotations

import hashlib
import json
import pwd
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

AGENT_UID = "codex_composer"


class SeatConfig(Protocol):
    instance_id: str
    nats_password: str
    card_path: Path
    card_sha256: str
    memory_path: Path
    memory_sha256: str
    workspace: Path
    codex_bin: str
    seat_user: str
    tmux_session: str


class IntegrityView(Protocol):
    card_sha256: str
    memory_sha256: str


class SeatConfigurationError(RuntimeError):
    """The host cannot prove a safely isolated Codex seat."""


@dataclass(frozen=True, slots=True)
class SeatStatus:
    ready: bool
    state: str
    tmux_session: str
    seat_user: str = ""
    pane_command: str = ""
    codex_version: str = ""
    contract_sha256: str = ""
    workspace: str = ""
    detail: str = ""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str
    ).encode()


def _run(
    args: list[str],
    *,
    timeout: float = 15.0,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _codex_path(config: SeatConfig) -> str:
    candidate = shutil.which(config.codex_bin)
    if candidate is None:
        raise SeatConfigurationError("Codex CLI is not installed")
    return candidate


def _seat_env(config: SeatConfig) -> dict[str, str]:
    try:
        account = pwd.getpwnam(config.seat_user)
    except KeyError as exc:
        raise SeatConfigurationError("dedicated Codex seat user is missing") from exc
    return {
        "HOME": account.pw_dir,
        "USER": config.seat_user,
        "LOGNAME": config.seat_user,
        "LANG": "C.UTF-8",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "TERM": "xterm-256color",
    }


def _seat_command(config: SeatConfig, args: list[str]) -> list[str]:
    runuser = shutil.which("runuser")
    if runuser is None:
        raise SeatConfigurationError("runuser is required for seat isolation")
    return [runuser, "-u", config.seat_user, "--", *args]


def _run_as_seat(
    config: SeatConfig,
    args: list[str],
    *,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    return _run(_seat_command(config, args), timeout=timeout, env=_seat_env(config))


def seat_prompt(config: SeatConfig) -> str:
    return (
        f"You are the official persistent {AGENT_UID} replica on {config.instance_id}. "
        f"Read {config.card_path} and {config.memory_path} before making claims. "
        "Verify their configured hashes through the host supervisor. Operate read-only by "
        "default. Replica presence is not an ExecutionLease: do not consume NATS tasks, "
        "write source, approve, merge, expose secrets, or mutate protected state without a "
        "separate valid operator-issued lease. Stay available for operator attachment and "
        "begin with a terse identity, authority, evidence, and next-safe-action status."
    )


def codex_tmux_command(config: SeatConfig, codex_path: str) -> list[str]:
    codex = [
        codex_path,
        "-C",
        str(config.workspace),
        "-s",
        "read-only",
        "-a",
        "on-request",
        "--no-alt-screen",
        seat_prompt(config),
    ]
    return [
        "tmux",
        "new-session",
        "-d",
        "-s",
        config.tmux_session,
        "-c",
        str(config.workspace),
        shlex.join(codex),
    ]


def seat_contract_sha256(
    config: SeatConfig,
    integrity: IntegrityView,
    codex_path: str,
) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "agent_uid": AGENT_UID,
                "seat_user": config.seat_user,
                "tmux_session": config.tmux_session,
                "workspace": str(config.workspace.resolve()),
                "codex_path": codex_path,
                "card_sha256": integrity.card_sha256,
                "memory_sha256": integrity.memory_sha256,
                "sandbox": "read-only",
                "approval_policy": "on-request",
                "prompt": seat_prompt(config),
            }
        )
    ).hexdigest()


def _failure(
    config: SeatConfig,
    state: str,
    *,
    version: str = "",
    detail: str = "",
) -> SeatStatus:
    return SeatStatus(
        False,
        state,
        config.tmux_session,
        seat_user=config.seat_user,
        codex_version=version,
        detail=detail,
    )


def ensure_seat(config: SeatConfig, integrity: IntegrityView) -> SeatStatus:
    if not config.workspace.is_dir():
        return _failure(config, "workspace_missing")
    try:
        codex_path = _codex_path(config)
        _seat_env(config)
    except SeatConfigurationError as exc:
        return _failure(config, "seat_prerequisite_missing", detail=str(exc))

    marker = seat_contract_sha256(config, integrity, codex_path)
    version_result = _run_as_seat(config, [codex_path, "--version"], timeout=10)
    version = (version_result.stdout or version_result.stderr).strip().splitlines()[0]
    present = _run_as_seat(
        config, ["tmux", "has-session", "-t", config.tmux_session], timeout=5
    )
    if present.returncode != 0:
        login = _run_as_seat(config, [codex_path, "login", "status"], timeout=15)
        if login.returncode != 0 or "Logged in" not in (login.stdout + login.stderr):
            return _failure(config, "codex_not_authenticated", version=version)
        launched = _run_as_seat(
            config, codex_tmux_command(config, codex_path), timeout=15
        )
        if launched.returncode != 0:
            detail = (launched.stderr or launched.stdout).strip()[:300]
            return _failure(config, "tmux_launch_failed", version=version, detail=detail)
        marked = _run_as_seat(
            config,
            ["tmux", "set-option", "-t", config.tmux_session, "@dharma_contract", marker],
            timeout=5,
        )
        if marked.returncode != 0:
            return _failure(config, "tmux_marker_failed", version=version)

    pane = _run_as_seat(
        config,
        [
            "tmux",
            "display-message",
            "-p",
            "-t",
            config.tmux_session,
            "#{pane_current_command}\t#{pane_current_path}",
        ],
        timeout=5,
    )
    observed_marker = _run_as_seat(
        config,
        ["tmux", "show-option", "-qv", "-t", config.tmux_session, "@dharma_contract"],
        timeout=5,
    )
    command, _, workspace = pane.stdout.strip().partition("\t")
    try:
        workspace_matches = Path(workspace).resolve() == config.workspace.resolve()
    except OSError:
        workspace_matches = False
    ready = (
        version_result.returncode == 0
        and pane.returncode == 0
        and observed_marker.stdout.strip() == marker
        and command in {"codex", "node"}
        and workspace_matches
    )
    # A Codex process can exit while its contract-marked tmux session remains.
    # Recreate only a session carrying this exact current contract marker.  An
    # unmarked or stale/mismatched marker may belong to an operator and is
    # deliberately left untouched.
    if (
        not ready
        and present.returncode == 0
        and version_result.returncode == 0
        and observed_marker.stdout.strip() == marker
    ):
        login = _run_as_seat(config, [codex_path, "login", "status"], timeout=15)
        if login.returncode != 0 or "Logged in" not in (login.stdout + login.stderr):
            return _failure(config, "codex_not_authenticated", version=version)
        killed = _run_as_seat(
            config,
            ["tmux", "kill-session", "-t", config.tmux_session],
            timeout=5,
        )
        if killed.returncode != 0:
            return _failure(config, "tmux_recreate_failed", version=version)
        launched = _run_as_seat(
            config, codex_tmux_command(config, codex_path), timeout=15
        )
        if launched.returncode != 0:
            detail = (launched.stderr or launched.stdout).strip()[:300]
            return _failure(config, "tmux_launch_failed", version=version, detail=detail)
        marked = _run_as_seat(
            config,
            ["tmux", "set-option", "-t", config.tmux_session, "@dharma_contract", marker],
            timeout=5,
        )
        if marked.returncode != 0:
            return _failure(config, "tmux_marker_failed", version=version)
        pane = _run_as_seat(
            config,
            [
                "tmux",
                "display-message",
                "-p",
                "-t",
                config.tmux_session,
                "#{pane_current_command}\t#{pane_current_path}",
            ],
            timeout=5,
        )
        observed_marker = _run_as_seat(
            config,
            ["tmux", "show-option", "-qv", "-t", config.tmux_session, "@dharma_contract"],
            timeout=5,
        )
        command, _, workspace = pane.stdout.strip().partition("\t")
        try:
            workspace_matches = Path(workspace).resolve() == config.workspace.resolve()
        except OSError:
            workspace_matches = False
        ready = (
            pane.returncode == 0
            and observed_marker.stdout.strip() == marker
            and command in {"codex", "node"}
            and workspace_matches
        )
    return SeatStatus(
        ready,
        "ready" if ready else "tmux_present_unverified",
        config.tmux_session,
        seat_user=config.seat_user,
        pane_command=command,
        codex_version=version,
        contract_sha256=observed_marker.stdout.strip(),
        workspace=workspace,
    )


def seat_environment_contains_secret(config: SeatConfig) -> bool:
    """Test helper: prove the generated seat environment excludes the NATS secret."""
    environment = _seat_env(config)
    return any(config.nats_password in value for value in environment.values())
