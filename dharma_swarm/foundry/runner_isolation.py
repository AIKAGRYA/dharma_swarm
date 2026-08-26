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

import shlex
import subprocess
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence


class IsolationLevel(str, Enum):
    DOCKER_NONET = "docker_nonet"      # strongest: container, no network
    LOCAL_RESTRICTED = "local_restricted"  # degraded: local subprocess, no jail
    BLOCKED = "blocked"                # no acceptable isolation available


class StrongIsolationUnavailable(RuntimeError):
    """Unattended execution cannot safely run model-generated target code."""


UNATTENDED_UID_GID = "65534:65534"


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
    readonly_rootfs: bool = True
    cap_drop_all: bool = True
    no_new_privileges: bool = True
    pids_limit: int = 256
    tmpfs_size: str = "512m"
    run_as_user: str = ""


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


@dataclass(frozen=True)
class IsolationProof:
    """Non-coercible evidence describing the isolation that actually ran."""

    isolation_level: str
    network_disabled: bool
    blocked: bool
    timed_out: bool
    exit_code: int
    readonly_rootfs: bool
    cap_drop_all: bool
    no_new_privileges: bool
    pids_limited: bool
    memory_limited: bool
    memory_swap_limited: bool
    tmpfs_limited: bool
    non_root_user: bool
    workdir_readonly: bool
    digest: str

    @classmethod
    def from_result(cls, result: RunResult, policy: IsolationPolicy) -> "IsolationProof":
        body = {
            "isolation_level": result.isolation_level,
            "network_disabled": result.details.get("network_disabled") == "true",
            "blocked": bool(result.blocked),
            "timed_out": bool(result.timed_out),
            "exit_code": int(result.exit_code),
            "readonly_rootfs": result.details.get("readonly_rootfs") == "true",
            "cap_drop_all": result.details.get("cap_drop_all") == "true",
            "no_new_privileges": result.details.get("no_new_privileges") == "true",
            "pids_limited": result.details.get("pids_limited") == "true",
            "memory_limited": result.details.get("memory_limited") == "true",
            "memory_swap_limited": result.details.get("memory_swap_limited") == "true",
            "tmpfs_limited": result.details.get("tmpfs_limited") == "true",
            "non_root_user": result.details.get("non_root_user") == "true",
            "workdir_readonly": result.details.get("workdir_readonly") == "true",
        }
        digest = "sha256:" + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(**body, digest=digest)

    @property
    def promotion_allowed(self) -> bool:
        return (
            not self.blocked
            and not self.timed_out
            and self.network_disabled
            and self.readonly_rootfs
            and self.cap_drop_all
            and self.no_new_privileges
            and self.pids_limited
            and self.memory_limited
            and self.memory_swap_limited
            and self.tmpfs_limited
            and self.non_root_user
            and self.workdir_readonly
            and self.exit_code == 0
            and self.isolation_level == IsolationLevel.DOCKER_NONET.value
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "isolation_level": self.isolation_level,
            "network_disabled": self.network_disabled,
            "blocked": self.blocked,
            "timed_out": self.timed_out,
            "exit_code": self.exit_code,
            "readonly_rootfs": self.readonly_rootfs,
            "cap_drop_all": self.cap_drop_all,
            "no_new_privileges": self.no_new_privileges,
            "pids_limited": self.pids_limited,
            "memory_limited": self.memory_limited,
            "memory_swap_limited": self.memory_swap_limited,
            "tmpfs_limited": self.tmpfs_limited,
            "non_root_user": self.non_root_user,
            "workdir_readonly": self.workdir_readonly,
            "digest": self.digest,
            "promotion_allowed": self.promotion_allowed,
        }


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
    """Render a command for ``bash -c`` INSIDE the container.

    Lists must be re-quoted with shlex — a naive space-join destroys nested
    quoting (e.g. ``["bash", "-c", "cd x && python -c \"...\""]`` would run
    ``cd`` bare and the payload from the wrong directory).
    """
    if isinstance(cmd, str):
        return cmd
    return shlex.join(cmd)


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
        "--memory-swap", policy.memory_limit,
        f"--cpus={policy.cpu_limit}",
        "--pids-limit", str(policy.pids_limit),
        "-v", mount,
        "-w", "/work",
    ]
    if policy.readonly_rootfs:
        docker_cmd.append("--read-only")
    if policy.cap_drop_all:
        docker_cmd += ["--cap-drop", "ALL"]
    if policy.no_new_privileges:
        docker_cmd += ["--security-opt", "no-new-privileges:true"]
    if policy.run_as_user:
        docker_cmd += ["--user", policy.run_as_user]
    # Writable scratch is bounded and separated from the host tree.
    docker_cmd += [
        "--tmpfs", f"/tmp:rw,nosuid,nodev,size={policy.tmpfs_size}",
        "-e", "TMPDIR=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
    ]
    docker_cmd += [policy.docker_image, "bash", "-c", _as_bash(cmd)]
    user_parts = policy.run_as_user.split(":", maxsplit=1)
    non_root_user = bool(user_parts[0]) and all(
        part not in {"0", "root"} for part in user_parts
    )
    details = {
        "network_disabled": str(policy.network_disabled).lower(),
        "readonly_rootfs": str(policy.readonly_rootfs).lower(),
        "cap_drop_all": str(policy.cap_drop_all).lower(),
        "no_new_privileges": str(policy.no_new_privileges).lower(),
        "pids_limited": str(policy.pids_limit > 0).lower(),
        "memory_limited": str(bool(policy.memory_limit)).lower(),
        "memory_swap_limited": str(bool(policy.memory_limit)).lower(),
        "tmpfs_limited": str(bool(policy.tmpfs_size)).lower(),
        # Merely passing --user is not proof: --user 0:0 is still root.
        "non_root_user": str(non_root_user).lower(),
        "workdir_readonly": str(policy.readonly_workdir).lower(),
    }
    return _invoke(
        docker_cmd, None, policy, runner, IsolationLevel.DOCKER_NONET, details=details
    )


def _run_local(cmd, workdir, policy, runner) -> RunResult:
    local_cmd = ["bash", "-c", _as_bash(cmd)] if isinstance(cmd, str) else list(cmd)
    return _invoke(local_cmd, workdir, policy, runner, IsolationLevel.LOCAL_RESTRICTED)


def _invoke(cmd, cwd, policy, runner, level, *, details=None) -> RunResult:
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
            isolation_level=level.value, timed_out=True, details=details or {},
        )
    return RunResult(
        exit_code=getattr(proc, "returncode", 0) or 0,
        stdout=getattr(proc, "stdout", "") or "",
        stderr=getattr(proc, "stderr", "") or "",
        duration_s=round(time.monotonic() - start, 4),
        isolation_level=level.value,
        details=details or {},
    )


def promotion_allowed(
    result: RunResult,
    policy: IsolationPolicy | None = None,
) -> bool:
    """Only a strongly-isolated, clean, on-time run may feed ring 2/3.

    A degraded (local) run can inform exploration but can never confirm an
    improvement — that is the isolation-as-gating-prerequisite rule.
    """
    effective = policy or IsolationPolicy()
    return IsolationProof.from_result(result, effective).promotion_allowed
