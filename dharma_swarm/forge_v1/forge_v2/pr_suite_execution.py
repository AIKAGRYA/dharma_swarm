"""Fail-closed execution boundary for untrusted PR-suite repositories.

This compatibility facade keeps the original public API and the container
executor's monkeypatch seams stable. Profile/trust, path/materialization, and
bounded process concerns live in focused sibling modules.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol, Sequence

from .pr_suite_execution_paths import (
    atomic_write_json,
    atomic_write_text,
    materialize_text,
    redact_secret_text,
    safe_materialization_path,
    validated_target_path,
)
from .pr_suite_execution_process import (
    CommandResult,
    _bounded_run,
    _clean_host_env as _clean_host_env,
    _kill_process_group as _kill_process_group,
)
from .pr_suite_execution_profile import (
    DEFAULT_TEST_COMMAND as DEFAULT_TEST_COMMAND,
    PROFILE_ENV,
    PROFILE_SCHEMA,
    VALIDATOR_ATTESTATION_SCHEMA,
    VALIDATOR_PRIVATE_KEY_SCHEMA as VALIDATOR_PRIVATE_KEY_SCHEMA,
    VALIDATOR_SIGNING_KEY_ENV,
    VALIDATOR_TRUST_ROOT_ENV,
    VALIDATOR_TRUST_ROOT_SCHEMA as VALIDATOR_TRUST_ROOT_SCHEMA,
    ExecutionBoundaryError,
    ExecutionProfile,
    IsolationUnavailable,
    ProfileTampered,
    UnsafeTargetPath,
    _USER_RE,
    load_execution_profile,
    load_validator_trust_root,
    resolve_validator_signer,
    sign_validator_receipt,
    verify_validator_receipt_signature as _verify_validator_receipt_signature,
)


_SAFE_ENV = {
    "HOME": "/tmp",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "TMPDIR": "/tmp",
}


class CommandExecutor(Protocol):
    profile: ExecutionProfile
    workspace_root: Path

    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        stdin: str | None = None,
    ) -> CommandResult: ...

    def test_argv(self, *, cwd: Path, targets: Sequence[str]) -> list[str]: ...

    def setup_argv(self, *, cwd: Path) -> list[str] | None: ...


ExecutorFactory = Callable[..., CommandExecutor]


def resolve_execution_profile(
    profile: ExecutionProfile | Path | str | None,
) -> ExecutionProfile:
    """Resolve through facade globals so established monkeypatch seams remain live."""

    if isinstance(profile, ExecutionProfile):
        return profile
    configured = profile or os.environ.get(PROFILE_ENV, "").strip()
    if not configured:
        raise IsolationUnavailable("explicit PR-suite execution profile required")
    return load_execution_profile(configured)


def verify_validator_receipt_signature(
    receipt: dict[str, Any],
    *,
    trusted_public_keys: dict[str, bytes | str] | None = None,
) -> dict[str, Any]:
    """Verify through the facade trust-root seam used by validators and tests."""

    trusted = trusted_public_keys or load_validator_trust_root()
    return _verify_validator_receipt_signature(
        receipt,
        trusted_public_keys=trusted,
    )


def normalized_template_tokens(template: str, *, python: str) -> tuple[str, ...]:
    text = str(template or "").strip()
    if not text:
        return ()
    tokens = list(shlex.split(text))
    if tokens and tokens[0] == python:
        tokens[0] = "{python}"
    return tuple(tokens)


def require_command_contract(
    profile: ExecutionProfile,
    *,
    test_command_template: str,
    setup_command_template: str,
    python: str,
) -> None:
    if normalized_template_tokens(test_command_template, python=python) != profile.test_command:
        raise ProfileTampered("test command differs from digest-bound execution profile")
    if normalized_template_tokens(setup_command_template, python=python) != profile.setup_command:
        raise ProfileTampered("setup command differs from digest-bound execution profile")


class ContainerExecutor:
    """Synchronous Docker/Podman executor with a single monotonic deadline."""

    def __init__(
        self,
        profile: ExecutionProfile,
        *,
        workspace_root: Path,
        source_roots: Sequence[Path] = (),
        total_timeout_seconds: int,
        probe_backend: bool = True,
    ) -> None:
        if not 1 <= int(total_timeout_seconds) <= 86_400:
            raise ValueError("total_timeout_seconds outside safe bounds")
        self.profile = profile
        self.workspace_root = workspace_root.expanduser().resolve(strict=False)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        match = _USER_RE.fullmatch(profile.user)
        assert match is not None  # ExecutionProfile already validated this.
        uid, gid = int(match.group("uid")), int(match.group("gid"))
        if os.geteuid() == 0:
            try:
                os.chown(self.workspace_root, uid, gid)
                os.chmod(self.workspace_root, 0o700)
            except OSError:
                # Some rootless/user-namespace hosts map only uid 0. The
                # workspace is a random per-run child; make only that child
                # writable so the explicitly non-root container can operate.
                os.chmod(self.workspace_root, 0o777)
        elif self.workspace_root.stat().st_uid != uid or uid != os.geteuid():
            raise IsolationUnavailable(
                "workspace is not owned by the configured unprivileged uid"
            )
        self.source_roots = tuple(
            path.expanduser().resolve(strict=True) for path in source_roots
        )
        self._deadline = time.monotonic() + int(total_timeout_seconds)
        runtime = Path(profile.runtime)
        if not runtime.is_file() or not os.access(runtime, os.X_OK):
            raise IsolationUnavailable(f"container runtime unavailable: {runtime}")
        runtime_stat = runtime.lstat()
        if (
            runtime.is_symlink()
            or runtime_stat.st_mode & 0o022
            or runtime_stat.st_uid not in {0, os.geteuid()}
        ):
            raise IsolationUnavailable("container runtime is not a trusted executable")
        if probe_backend:
            probes = (
                [profile.runtime, "info"],
                [profile.runtime, "image", "inspect", profile.image],
            )
            for probe in probes:
                rc, _, _, timed_out, exceeded, _ = _bounded_run(
                    probe,
                    timeout_seconds=5,
                    output_limit_bytes=16 * 1024,
                )
                if rc != 0 or timed_out or exceeded:
                    raise IsolationUnavailable(
                        f"container backend/image unavailable: {profile.backend}"
                    )

    @property
    def profile_sha256(self) -> str:
        return self.profile.sha256

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def _map_path(self, raw: Path | str) -> str:
        path = Path(raw).expanduser().resolve(strict=False)
        try:
            relative = path.relative_to(self.workspace_root)
            return str(PurePosixPath("/workspace", *relative.parts))
        except ValueError:
            pass
        for index, source in enumerate(self.source_roots):
            try:
                relative = path.relative_to(source)
                return str(PurePosixPath(f"/input{index}", *relative.parts))
            except ValueError:
                continue
        raise ExecutionBoundaryError(f"path is outside declared executor mounts: {path}")

    def _translate_argv(self, argv: Sequence[str]) -> list[str]:
        roots = (self.workspace_root, *self.source_roots)
        translated: list[str] = []
        for token in argv:
            replacement = str(token)
            for root in roots:
                root_text = str(root)
                if replacement == root_text or replacement.startswith(root_text + os.sep):
                    replacement = self._map_path(replacement)
                    break
            translated.append(replacement)
        return translated

    def _render(
        self,
        tokens: Sequence[str],
        *,
        cwd: Path,
        targets: Sequence[str],
    ) -> list[str]:
        safe_targets = [
            validated_target_path(target, cwd)
            + str(target)[len(str(target).split("::", 1)[0]) :]
            for target in targets
        ]
        rendered: list[str] = []
        checkout = self._map_path(cwd)
        for token in tokens:
            if token == "{targets}":
                rendered.extend(safe_targets)
                continue
            rendered.append(
                token.format(
                    python=self.profile.python,
                    checkout=checkout,
                    target=safe_targets[0] if safe_targets else "",
                    targets=" ".join(safe_targets),
                )
            )
        return rendered

    def test_argv(self, *, cwd: Path, targets: Sequence[str]) -> list[str]:
        if not targets:
            raise ValueError("no PR-suite test targets supplied")
        return self._render(self.profile.test_command, cwd=cwd, targets=targets)

    def setup_argv(self, *, cwd: Path) -> list[str] | None:
        if not self.profile.setup_command:
            return None
        return self._render(self.profile.setup_command, cwd=cwd, targets=())

    def container_command(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        cidfile: Path,
        interactive: bool,
    ) -> list[str]:
        mounts = [(self.workspace_root, "/workspace", "rw")]
        for index, source in enumerate(self.source_roots):
            source_text = str(source)
            if any(
                str(token) == source_text or str(token).startswith(source_text + os.sep)
                for token in argv
            ):
                # The source mirror is needed only by the clone command. Test
                # and setup containers never receive this additional mount.
                mounts.append((source, f"/input{index}", "readonly"))
        for source, _, _ in mounts:
            if "," in str(source) or "\x00" in str(source):
                raise ExecutionBoundaryError(
                    "container mount path contains an unsupported character"
                )
        command = [
            self.profile.runtime,
            "run",
            "--rm",
            f"--pull={self.profile.pull_policy}",
            "--read-only",
            f"--network={self.profile.network_mode}",
            f"--cap-drop={self.profile.cap_drop[0]}",
            "--security-opt=no-new-privileges:true",
            "--ipc=none",
            "--init",
            "--user",
            self.profile.user,
            "--pids-limit",
            str(self.profile.pids_limit),
            "--memory",
            str(self.profile.memory_bytes),
            "--memory-swap",
            str(self.profile.memory_bytes),
            "--cpus",
            str(self.profile.cpu_count),
            "--ulimit",
            f"nofile={self.profile.nofile_limit}:{self.profile.nofile_limit}",
            "--ulimit",
            f"fsize={self.profile.file_size_bytes}:{self.profile.file_size_bytes}",
            "--ulimit",
            "core=0:0",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={self.profile.tmpfs_bytes},mode=1777",
            "--cidfile",
            str(cidfile),
            "--workdir",
            self._map_path(cwd),
        ]
        if interactive:
            command.append("-i")
        for key, value in sorted(_SAFE_ENV.items()):
            command.extend(["--env", f"{key}={value}"])
        for source, destination, mode in mounts:
            mount = f"type=bind,src={source},dst={destination}"
            if mode == "readonly":
                mount += ",readonly"
            command.extend(["--mount", mount])
        command.append(self.profile.image)
        command.extend(self._translate_argv(argv))
        return command

    def _remove_container(self, cidfile: Path) -> None:
        try:
            container_id = cidfile.read_text(encoding="utf-8").strip()
        except OSError:
            return
        if not re.fullmatch(r"[0-9a-fA-F]{12,64}", container_id):
            return
        _bounded_run(
            [self.profile.runtime, "rm", "--force", container_id],
            timeout_seconds=5,
            output_limit_bytes=16 * 1024,
        )

    def run(
        self,
        argv: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
        stdin: str | None = None,
    ) -> CommandResult:
        remaining = self.remaining_seconds()
        if remaining <= 0:
            return CommandResult(
                list(argv),
                str(cwd),
                124,
                "",
                "global execution deadline exhausted",
                True,
                profile_sha256=self.profile.sha256,
            )
        raw_stdin = stdin.encode("utf-8") if stdin is not None else None
        if raw_stdin is not None and len(raw_stdin) > self.profile.stdin_limit_bytes:
            raise ExecutionBoundaryError("command stdin exceeds profile limit")
        cid_dir = Path(tempfile.mkdtemp(prefix="forge-pr-suite-cid-"))
        cidfile = cid_dir / f"{uuid.uuid4().hex}.cid"
        try:
            outer = self.container_command(
                argv,
                cwd=cwd,
                cidfile=cidfile,
                interactive=raw_stdin is not None,
            )
            try:
                rc, stdout, stderr, timed_out, exceeded, duration = _bounded_run(
                    outer,
                    timeout_seconds=min(max(1, int(timeout_seconds)), remaining),
                    output_limit_bytes=self.profile.output_limit_bytes,
                    stdin=raw_stdin,
                )
            except BaseException:
                self._remove_container(cidfile)
                raise
            if timed_out or exceeded:
                self._remove_container(cidfile)
            return CommandResult(
                argv=list(argv),
                cwd=str(cwd),
                returncode=rc,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                timed_out=timed_out,
                output_limit_exceeded=exceeded,
                duration_seconds=duration,
                profile_sha256=self.profile.sha256,
            )
        finally:
            shutil.rmtree(cid_dir, ignore_errors=True)


def build_executor(
    *,
    profile: ExecutionProfile | Path | str | None,
    workspace_root: Path,
    source_roots: Sequence[Path] = (),
    total_timeout_seconds: int,
) -> CommandExecutor:
    resolved = resolve_execution_profile(profile)
    return ContainerExecutor(
        resolved,
        workspace_root=workspace_root,
        source_roots=source_roots,
        total_timeout_seconds=total_timeout_seconds,
    )


__all__ = [
    "CommandExecutor",
    "CommandResult",
    "ContainerExecutor",
    "ExecutionBoundaryError",
    "ExecutionProfile",
    "ExecutorFactory",
    "IsolationUnavailable",
    "PROFILE_ENV",
    "PROFILE_SCHEMA",
    "VALIDATOR_ATTESTATION_SCHEMA",
    "VALIDATOR_SIGNING_KEY_ENV",
    "VALIDATOR_TRUST_ROOT_ENV",
    "ProfileTampered",
    "UnsafeTargetPath",
    "atomic_write_json",
    "atomic_write_text",
    "build_executor",
    "load_execution_profile",
    "load_validator_trust_root",
    "normalized_template_tokens",
    "require_command_contract",
    "redact_secret_text",
    "resolve_execution_profile",
    "resolve_validator_signer",
    "safe_materialization_path",
    "materialize_text",
    "sign_validator_receipt",
    "validated_target_path",
    "verify_validator_receipt_signature",
]
