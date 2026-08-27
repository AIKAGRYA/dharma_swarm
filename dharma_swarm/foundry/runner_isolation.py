"""Runner isolation — the gating prerequisite for scoring untrusted diffs.

External candidates are untrusted code. Benchmarking them in-process would let a
malicious or reward-hacking diff read the evaluator, forge logs, or reach the
network. This module runs the target's oracle command under the strongest
available isolation and, crucially, refuses to let a WEAKLY-isolated run feed
promotion (ring 2/3): if Docker with ``--network none`` is not available, the
run is marked degraded and :func:`promotion_allowed` returns False. Exploration
may proceed degraded; promotion may not.

The chamber/Titanium tracks still owe a full seccomp-class jail; until then a
degraded run can EXPLORE but never CONFIRM. Sync + stdlib only (shells to the
Docker CLI) so it stays importable and testable without the heavy stack.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence


class IsolationLevel(str, Enum):
    DOCKER_NONET = "docker_nonet"      # strongest: container, no network
    LOCAL_RESTRICTED = "local_restricted"  # degraded: local subprocess, no jail
    BLOCKED = "blocked"                # no acceptable isolation available


@dataclass(frozen=True)
class IsolationPolicy:
    network_disabled: bool = True
    timeout_s: float = 120.0
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    allow_degraded: bool = True  # explore degraded; promotion still blocked below
    docker_image: str = "python:3.11-slim"
    # Read-only workdir: mounts /work as :ro with a writable tmpfs at /tmp, so
    # the running candidate cannot rewrite tests/oracle files mid-run. Suites
    # that must write inside their tree can't run under this; the evaluator
    # falls back to rw + post-run tamper digest (detection instead of
    # prevention) and records which mode actually ran.
    readonly_workdir: bool = False


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    isolation_level: str
    timed_out: bool = False
    blocked: bool = False
    blocked_reason: str = ""
    details: dict[str, str] = field(default_factory=dict)


def docker_available(runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> bool:
    """True if a Docker daemon is reachable (sync ``docker info`` probe)."""
    try:
        proc = runner(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return getattr(proc, "returncode", 1) == 0
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return False


def _as_bash(cmd: Sequence[str] | str) -> str:
    if isinstance(cmd, str):
        return cmd
    return " ".join(cmd)


def run_isolated(
    cmd: Sequence[str] | str,
    workdir: str,
    policy: IsolationPolicy | None = None,
    *,
    docker_ok: bool | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> RunResult:
    """Run ``cmd`` in ``workdir`` under the strongest available isolation."""
    policy = policy or IsolationPolicy()
    if docker_ok is None:
        docker_ok = docker_available(runner)

    if policy.network_disabled and docker_ok:
        return _run_docker(cmd, workdir, policy, runner)
    if policy.allow_degraded:
        return _run_local(cmd, workdir, policy, runner)
    return RunResult(
        exit_code=-1, stdout="", stderr="", duration_s=0.0,
        isolation_level=IsolationLevel.BLOCKED.value,
        blocked=True,
        blocked_reason="strong isolation (docker --network none) unavailable and degraded runs disallowed",
    )


def _run_docker(cmd, workdir, policy, runner) -> RunResult:
    mount = f"{workdir}:/work:ro" if policy.readonly_workdir else f"{workdir}:/work"
    docker_cmd = [
        "docker", "run", "--rm",
        "--network", "none" if policy.network_disabled else "bridge",
        "--memory", policy.memory_limit,
        f"--cpus={policy.cpu_limit}",
        "-v", mount,
        "-w", "/work",
    ]
    if policy.readonly_workdir:
        # Writable scratch lives only inside the container, never on the host tree.
        docker_cmd += ["--tmpfs", "/tmp:rw,size=512m", "-e", "TMPDIR=/tmp",
                       "-e", "PYTHONDONTWRITEBYTECODE=1"]
    docker_cmd += [policy.docker_image, "bash", "-c", _as_bash(cmd)]
    return _invoke(docker_cmd, None, policy, runner, IsolationLevel.DOCKER_NONET)


def _run_local(cmd, workdir, policy, runner) -> RunResult:
    local_cmd = ["bash", "-c", _as_bash(cmd)] if isinstance(cmd, str) else list(cmd)
    return _invoke(local_cmd, workdir, policy, runner, IsolationLevel.LOCAL_RESTRICTED)


def _invoke(cmd, cwd, policy, runner, level) -> RunResult:
    import time

    start = time.monotonic()
    try:
        proc = runner(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=policy.timeout_s
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            exit_code=-1, stdout="", stderr="timeout",
            duration_s=round(time.monotonic() - start, 4),
            isolation_level=level.value, timed_out=True,
        )
    return RunResult(
        exit_code=getattr(proc, "returncode", 0) or 0,
        stdout=getattr(proc, "stdout", "") or "",
        stderr=getattr(proc, "stderr", "") or "",
        duration_s=round(time.monotonic() - start, 4),
        isolation_level=level.value,
    )


def promotion_allowed(result: RunResult) -> bool:
    """Only a strongly-isolated, clean, on-time run may feed ring 2/3.

    A degraded (local) run can inform exploration but can never confirm an
    improvement — that is the isolation-as-gating-prerequisite rule.
    """
    return (
        not result.blocked
        and not result.timed_out
        and result.isolation_level == IsolationLevel.DOCKER_NONET.value
    )
