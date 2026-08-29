"""Fail-closed process isolation for evaluating untrusted Foundry candidates.

An argv invocation in a digest-pinned Docker image can produce a bounded
observation of requested hardening flags. It cannot produce promotion authority:
the runner and all of its test hooks live in the caller process, and structural
facts remain publicly constructible until an external attestor owns this seam.

This boundary attests the exact isolation options passed to Docker and the
observed process outcome. It does not attest Docker daemon integrity, image
provenance beyond the pinned content digest, or independent process custody.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

from dharma_swarm.foundry.runner_process import run_bounded_argv

_PINNED_IMAGE_RE = re.compile(r"[a-z0-9][a-z0-9._:/-]*@sha256:[0-9a-f]{64}")
_RESOURCE_SIZE_RE = re.compile(r"[1-9][0-9]*(?:b|k|m|g)")
_NON_ROOT_USER_RE = re.compile(r"([1-9][0-9]*):([1-9][0-9]*)")
_MAX_CAPTURE_BYTES = 1024 * 1024
_MAX_ARGV_ITEMS = 4096
_MAX_ARGV_BYTES = 256 * 1024


class IsolationLevel(str, Enum):
    DOCKER_NONET = "docker_nonet"
    LOCAL_RESTRICTED = "local_restricted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class IsolationPolicy:
    network_disabled: bool = True
    timeout_s: float = 120.0
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    pids_limit: int = 128
    tmpfs_limit: str = "64m"
    run_as_user: str = "65534:65534"
    output_limit_bytes: int = 64 * 1024
    allow_degraded: bool = False
    docker_image: str = ""
    docker_executable: str = ""


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
    network_disabled: bool = False
    readonly_rootfs: bool = False
    cap_drop_all: bool = False
    no_new_privileges: bool = False
    pids_limited: bool = False
    memory_limited: bool = False
    memory_swap_limited: bool = False
    tmpfs_limited: bool = False
    non_root_user: bool = False
    workdir_readonly: bool = False

    @property
    def promotion_allowed(self) -> bool:
        """This caller-constructible observation can never authorize promotion."""
        return False

    def to_dict(self) -> dict[str, Any]:
        """Return the exact fact/digest shape validated by the evaluator."""
        body = {
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
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return {
            **body,
            "digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
            "promotion_allowed": self.promotion_allowed,
        }


def docker_available(
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    *,
    docker_executable: str | None = None,
) -> bool:
    """Return whether Docker is reachable through a bounded absolute-path probe."""
    executable = docker_executable or resolve_docker_executable()
    if not executable:
        return False
    outcome = run_bounded_argv(
        [executable, "info", "--format", "{{.ServerVersion}}"],
        cwd=None,
        timeout_s=5.0,
        output_limit_bytes=4096,
        runner=runner,
    )
    return (
        not outcome.blocked
        and not outcome.timed_out
        and not outcome.stdout_truncated
        and not outcome.stderr_truncated
        and outcome.exit_code == 0
    )


def resolve_docker_executable() -> str:
    """Resolve Docker only from fixed system locations, never ambient ``PATH``."""

    candidates = (
        "/opt/homebrew/bin/docker",
        "/usr/local/bin/docker",
        "/usr/bin/docker",
        "/Applications/Docker.app/Contents/Resources/bin/docker",
    )
    for raw in candidates:
        try:
            path = Path(raw).resolve(strict=True)
            metadata = path.stat()
        except OSError:
            continue
        if (
            path.is_file()
            and stat.S_ISREG(metadata.st_mode)
            and os.access(path, os.X_OK)
        ):
            return str(path)
    return ""


def run_isolated(
    cmd: Sequence[str] | str,
    workdir: str,
    policy: IsolationPolicy | None = None,
    *,
    docker_ok: bool | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> RunResult:
    """Run an argv under the strongest admitted isolation.

    String commands are intentionally rejected. This function never invokes a
    shell, so shell metacharacters inside an argument remain ordinary bytes.
    """
    policy = policy or IsolationPolicy()
    argv, argv_error = _validated_argv(cmd)
    if argv_error:
        return _blocked(argv_error)

    common_error = _validate_common_policy(policy)
    if common_error:
        return _blocked(common_error)

    normalized_workdir, workdir_error = _validated_workdir(workdir)
    if workdir_error:
        return _blocked(workdir_error)

    if docker_ok is None:
        docker_ok = docker_available(
            runner,
            docker_executable=policy.docker_executable or None,
        )
    if type(docker_ok) is not bool:
        return _blocked("docker availability must be an exact boolean")

    if docker_ok and policy.network_disabled:
        docker_error = _validate_docker_policy(policy, normalized_workdir)
        if docker_error:
            return _blocked(docker_error)
        return _run_docker(argv, normalized_workdir, policy, runner)

    if policy.allow_degraded:
        return _run_local(argv, normalized_workdir, policy, runner)

    return _blocked(
        "strong isolation unavailable or disabled and degraded runs disallowed"
    )


def _validated_argv(cmd: Sequence[str] | str) -> tuple[list[str], str]:
    if isinstance(cmd, (str, bytes, bytearray)):
        return [], "string commands are forbidden; provide an argv sequence"
    try:
        argv = list(cmd)
    except (TypeError, ValueError):
        return [], "command must be a finite argv sequence"
    if not argv:
        return [], "command argv must not be empty"
    if len(argv) > _MAX_ARGV_ITEMS:
        return [], "command argv exceeds the item limit"
    if any(type(argument) is not str for argument in argv):
        return [], "every command argument must be an exact string"
    if not argv[0]:
        return [], "command executable must not be empty"
    if any("\x00" in argument for argument in argv):
        return [], "command arguments must not contain NUL bytes"
    try:
        argv_bytes = sum(len(argument.encode("utf-8")) for argument in argv)
    except UnicodeError:
        return [], "command arguments must be valid UTF-8 text"
    if argv_bytes > _MAX_ARGV_BYTES:
        return [], "command argv exceeds the byte limit"
    return argv, ""


def _validate_common_policy(policy: IsolationPolicy) -> str:
    if type(policy.network_disabled) is not bool:
        return "network_disabled must be an exact boolean"
    if type(policy.allow_degraded) is not bool:
        return "allow_degraded must be an exact boolean"
    if (
        type(policy.timeout_s) not in (int, float)
        or not math.isfinite(float(policy.timeout_s))
        or policy.timeout_s <= 0
    ):
        return "timeout_s must be a finite positive number"
    if (
        type(policy.output_limit_bytes) is not int
        or not 0 < policy.output_limit_bytes <= _MAX_CAPTURE_BYTES
    ):
        return f"output_limit_bytes must be between 1 and {_MAX_CAPTURE_BYTES}"
    return ""


def _validated_workdir(workdir: str) -> tuple[str, str]:
    if not isinstance(workdir, (str, os.PathLike)):
        return "", "workdir must be a path string"
    try:
        path = Path(workdir).resolve(strict=True)
    except (OSError, RuntimeError):
        return "", "workdir must resolve to an existing directory"
    if not path.is_dir():
        return "", "workdir must resolve to an existing directory"
    return str(path), ""


def _validate_docker_policy(policy: IsolationPolicy, workdir: str) -> str:
    if (
        type(policy.docker_image) is not str
        or _PINNED_IMAGE_RE.fullmatch(policy.docker_image) is None
    ):
        return "docker image must be pinned by an exact sha256 digest"
    if type(policy.docker_executable) is not str or not policy.docker_executable:
        return "docker_executable must be an absolute resolved executable"
    try:
        executable = Path(policy.docker_executable)
        resolved = executable.resolve(strict=True)
        metadata = resolved.stat()
    except (OSError, RuntimeError):
        return "docker_executable must be an absolute resolved executable"
    if (
        not executable.is_absolute()
        or str(resolved) != policy.docker_executable
        or not stat.S_ISREG(metadata.st_mode)
        or not os.access(resolved, os.X_OK)
    ):
        return "docker_executable must be an absolute resolved executable"
    if "," in workdir:
        return "workdir containing a comma cannot be encoded as a safe Docker mount"
    if (
        type(policy.memory_limit) is not str
        or _RESOURCE_SIZE_RE.fullmatch(policy.memory_limit) is None
    ):
        return "memory_limit must be a positive Docker byte value"
    if (
        type(policy.tmpfs_limit) is not str
        or _RESOURCE_SIZE_RE.fullmatch(policy.tmpfs_limit) is None
    ):
        return "tmpfs_limit must be a positive Docker byte value"
    if (
        type(policy.cpu_limit) not in (int, float)
        or not math.isfinite(float(policy.cpu_limit))
        or policy.cpu_limit <= 0
    ):
        return "cpu_limit must be a finite positive number"
    if type(policy.pids_limit) is not int or not 0 < policy.pids_limit <= 4096:
        return "pids_limit must be an integer between 1 and 4096"
    if (
        type(policy.run_as_user) is not str
        or _NON_ROOT_USER_RE.fullmatch(policy.run_as_user) is None
    ):
        return "run_as_user must contain non-root numeric uid:gid values"
    return ""


def _run_docker(argv, workdir, policy, runner) -> RunResult:
    docker_cmd = [
        policy.docker_executable,
        "run",
        "--rm",
        "--pull=never",
        "--init",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        f"--pids-limit={policy.pids_limit}",
        f"--memory={policy.memory_limit}",
        f"--memory-swap={policy.memory_limit}",
        f"--cpus={policy.cpu_limit}",
        f"--tmpfs=/tmp:rw,noexec,nosuid,nodev,size={policy.tmpfs_limit},mode=1777",
        f"--user={policy.run_as_user}",
        f"--mount=type=bind,src={workdir},dst=/work,readonly",
        "--workdir=/work",
        "--env=HOME=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=PYTHONPYCACHEPREFIX=/tmp/python-pycache",
        f"--entrypoint={argv[0]}",
        policy.docker_image,
        *argv[1:],
    ]
    facts = {
        "network_disabled": True,
        "readonly_rootfs": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "pids_limited": True,
        "memory_limited": True,
        "memory_swap_limited": True,
        "tmpfs_limited": True,
        "non_root_user": True,
        "workdir_readonly": True,
    }
    details = {
        "docker_executable": policy.docker_executable,
        "docker_image": policy.docker_image,
        "docker_image_digest": policy.docker_image.rsplit("@", 1)[1],
    }
    return _invoke(
        docker_cmd,
        None,
        policy,
        runner,
        IsolationLevel.DOCKER_NONET,
        facts=facts,
        details=details,
    )


def _run_local(argv, workdir, policy, runner) -> RunResult:
    return _invoke(
        argv,
        workdir,
        policy,
        runner,
        IsolationLevel.LOCAL_RESTRICTED,
        details={"degraded_reason": "local execution has no isolation jail"},
    )


def _invoke(cmd, cwd, policy, runner, level, *, facts=None, details=None) -> RunResult:
    facts = facts or {}
    details = details or {}
    outcome = run_bounded_argv(
        cmd,
        cwd=cwd,
        timeout_s=policy.timeout_s,
        output_limit_bytes=policy.output_limit_bytes,
        runner=runner,
    )
    output_incomplete = outcome.stdout_truncated or outcome.stderr_truncated
    result_details = {
        **details,
        "output_limit_bytes": str(policy.output_limit_bytes),
        "stdout_truncated": str(outcome.stdout_truncated).lower(),
        "stderr_truncated": str(outcome.stderr_truncated).lower(),
    }
    blocked_reason = outcome.blocked_reason
    if output_incomplete and not blocked_reason:
        blocked_reason = "process output exceeded the bounded capture limit"
    return RunResult(
        exit_code=outcome.exit_code,
        stdout=outcome.stdout,
        stderr=outcome.stderr,
        duration_s=round(outcome.duration_s, 4),
        isolation_level=level.value,
        timed_out=outcome.timed_out,
        blocked=outcome.blocked or output_incomplete,
        blocked_reason=blocked_reason,
        details=result_details,
        **facts,
    )


def _blocked(reason: str) -> RunResult:
    return RunResult(
        exit_code=-1,
        stdout="",
        stderr="",
        duration_s=0.0,
        isolation_level=IsolationLevel.BLOCKED.value,
        blocked=True,
        blocked_reason=reason,
    )


def promotion_allowed(result: RunResult) -> bool:
    """Compatibility helper delegating to the concrete proof predicate."""
    return type(result) is RunResult and result.promotion_allowed
