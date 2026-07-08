"""Execution-safe chat tool backends.

This module keeps subprocess/sandbox policy out of ``api.chat_tools`` so the
chat tool registry remains small and auditable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.models import SandboxResult

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path.home() / "dharma_swarm"
ALLOWED_ROOTS = [
    PROJECT_ROOT,
    dharma_state_dir(),
]


class SecurityVulnerabilityException(BaseException):
    """Hard security abort that bypasses ordinary tool error handling."""


class ShellExecutionBackend(Protocol):
    """Isolated command execution backend."""

    name: str

    async def execute(self, command: str, timeout: float) -> SandboxResult:
        """Run a shell command in an isolated backend."""


def _path_allowed(path_str: str) -> bool:
    try:
        resolved = Path(path_str).resolve()
        return any(resolved == root or root in resolved.parents for root in ALLOWED_ROOTS)
    except (ValueError, OSError):
        return False


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _iter_grep_files(search_path: Path, file_glob: str):
    if search_path.is_file():
        if not file_glob or search_path.match(file_glob):
            yield search_path
        return

    if not search_path.is_dir():
        return

    pattern = file_glob or "*"
    for candidate in search_path.rglob(pattern):
        if candidate.is_file() and _path_allowed(str(candidate)):
            yield candidate


def _grep_files_sync(
    *,
    pattern: str,
    search_path: Path,
    file_glob: str,
    max_results: int,
) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"ERROR: invalid regex pattern: {exc}"

    matches: list[str] = []
    for file_path in sorted(_iter_grep_files(search_path, file_glob)):
        try:
            with file_path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, start=1):
                    if regex.search(line):
                        line_text = line.rstrip("\n\r")[:500]
                        matches.append(f"{file_path}:{line_no}:{line_text}")
                        if len(matches) >= max_results:
                            return "\n".join(matches)[:6000]
        except OSError:
            continue

    if not matches:
        return f"No matches for pattern '{pattern}'"
    return "\n".join(matches)[:6000]


async def exec_grep(args: dict) -> str:
    pattern = args["pattern"]
    search_path = _resolve_path(args.get("path", str(PROJECT_ROOT)))
    file_glob = args.get("glob", "")
    max_results = min(50, int(args.get("max_results", 30)))

    if not _path_allowed(str(search_path)):
        return f"ERROR: Path {search_path} is outside allowed scope"

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                _grep_files_sync,
                pattern=pattern,
                search_path=search_path,
                file_glob=file_glob,
                max_results=max_results,
            ),
            timeout=15,
        )
    except asyncio.TimeoutError:
        return "ERROR: Search timed out"
    except Exception as exc:
        return f"ERROR: {exc}"


_DANGEROUS_PATTERNS = [
    re.compile(
        r"\brm\s+-[A-Za-z]*[rf][A-Za-z]*"
        r"(?:\s+-[A-Za-z]*[rf][A-Za-z]*){0,3}"
        r"(?:\s+--[A-Za-z0-9-]+){0,3}\s+/(?:\s|$)"
    ),
    re.compile(
        r"\brm\s+-[A-Za-z]*[rf][A-Za-z]*"
        r"(?:\s+-[A-Za-z]*[rf][A-Za-z]*){0,3}"
        r"(?:\s+--[A-Za-z0-9-]+){0,3}\s+~(?:\s|/|$)"
    ),
    re.compile(r"mkfs\b"),
    re.compile(r"dd\s+.*if\s*="),
    re.compile(r">\s*/dev/"),
    re.compile(r"chmod\s+.*777\s+/"),
    re.compile(r"curl\s+.*\|\s*(?:ba)?sh"),
    re.compile(r"wget\s+.*\|\s*(?:ba)?sh"),
    re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\}"),
    re.compile(r">\s*/etc/"),
    re.compile(r"sudo\s"),
]

_SHELL_GATE_TIMEOUT_SECONDS = float(
    os.getenv("DHARMA_SHELL_GATE_TIMEOUT_SECONDS", "2.0")
)
_MAX_SHELL_TIMEOUT_SECONDS = 60.0


def _redacted_command_preview(command: str) -> str:
    preview = re.sub(r"[\r\n\t]+", " ", command).strip()[:120]
    return re.sub(
        r"(?i)(api[_-]?key|token|secret|password)=\S+",
        r"\1=<redacted>",
        preview,
    )


def _quarantine_shell_execution(
    reason: str,
    command: str,
    detail: dict[str, object] | None = None,
) -> None:
    """Persist a non-sensitive shell security receipt before aborting."""
    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "command_preview": _redacted_command_preview(command),
        "detail": detail or {},
    }
    try:
        quarantine_dir = dharma_state_dir() / "quarantine" / "shell_exec"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        name = (
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_"
            f"{receipt['command_sha256'][:12]}.json"
        )
        (quarantine_dir / name).write_text(
            json.dumps(receipt, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to write shell execution quarantine receipt")


async def _evaluate_shell_gate(command: str):
    from dharma_swarm.telos_gates import check_action

    return await asyncio.wait_for(
        asyncio.to_thread(
            check_action,
            action=f"shell_exec: {command[:200]}",
            content=command,
        ),
        timeout=_SHELL_GATE_TIMEOUT_SECONDS,
    )


async def _require_shell_gate_allow(command: str) -> None:
    from dharma_swarm.models import GateCheckResult, GateDecision

    try:
        gate = await _evaluate_shell_gate(command)
    except asyncio.TimeoutError as exc:
        _quarantine_shell_execution(
            "telos_gate_timeout",
            command,
            {"timeout_seconds": _SHELL_GATE_TIMEOUT_SECONDS},
        )
        raise SecurityVulnerabilityException(
            f"Telos gate timed out after {_SHELL_GATE_TIMEOUT_SECONDS}s"
        ) from exc
    except Exception as exc:
        _quarantine_shell_execution(
            "telos_gate_error",
            command,
            {"error_type": type(exc).__name__},
        )
        raise SecurityVulnerabilityException(
            f"Telos gate failed closed: {type(exc).__name__}"
        ) from exc

    if not isinstance(gate, GateCheckResult):
        _quarantine_shell_execution(
            "telos_gate_malformed",
            command,
            {"gate_type": type(gate).__name__},
        )
        raise SecurityVulnerabilityException(
            f"Telos gate returned malformed result: {type(gate).__name__}"
        )

    if gate.decision is not GateDecision.ALLOW:
        reason = getattr(gate, "reason", "missing explicit allow")
        _quarantine_shell_execution(
            "telos_gate_denied_or_malformed",
            command,
            {"decision": str(gate.decision), "reason": str(reason)[:500]},
        )
        raise SecurityVulnerabilityException(
            f"Telos gate did not explicitly allow command: {reason}"
        )


def _reject_dangerous_shell_pattern(command: str) -> None:
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            _quarantine_shell_execution(
                "dangerous_shell_pattern",
                command,
                {"pattern": pattern.pattern},
            )
            raise SecurityVulnerabilityException(
                "Command rejected by dangerous shell pattern"
            )


class _DockerShellExecutionBackend:
    name = "docker"

    async def execute(self, command: str, timeout: float) -> SandboxResult:
        from dharma_swarm.docker_sandbox import (
            ContainerConfig,
            DockerSandbox,
            NetworkMode,
        )

        network_value = os.getenv("DHARMA_SHELL_SANDBOX_NETWORK", "none").lower()
        try:
            network_mode = NetworkMode(network_value)
        except ValueError as exc:
            raise SecurityVulnerabilityException(
                f"Invalid DHARMA_SHELL_SANDBOX_NETWORK={network_value!r}"
            ) from exc

        sandbox = DockerSandbox(
            ContainerConfig(
                image=os.getenv("DHARMA_SHELL_SANDBOX_IMAGE", "python:3.11-slim"),
                memory_limit=os.getenv("DHARMA_SHELL_SANDBOX_MEMORY", "1g"),
                cpu_limit=float(os.getenv("DHARMA_SHELL_SANDBOX_CPUS", "1.0")),
                network_mode=network_mode,
                timeout=timeout,
                workdir="/workspace",
                volumes={str(PROJECT_ROOT): "/workspace"},
            )
        )
        try:
            return await sandbox.execute(command, timeout=timeout)
        finally:
            await sandbox.cleanup()


class _HostShellExecutionBackend:
    name = "host"

    async def execute(self, command: str, timeout: float) -> SandboxResult:
        from dharma_swarm.sandbox import LocalSandbox

        sandbox = LocalSandbox(workdir=PROJECT_ROOT)
        try:
            return await sandbox.execute(command, timeout=timeout)
        finally:
            await sandbox.cleanup()


def _shell_backend_from_env() -> ShellExecutionBackend:
    backend = os.getenv("DHARMA_SHELL_EXEC_BACKEND", "docker").lower()
    if backend in {"docker", "container"}:
        return _DockerShellExecutionBackend()
    if backend == "host":
        if os.getenv("DHARMA_ALLOW_HOST_SHELL_EXEC") == "1":
            logger.critical("Host shell execution explicitly enabled by environment")
            return _HostShellExecutionBackend()
        raise SecurityVulnerabilityException(
            "Host shell backend requested without DHARMA_ALLOW_HOST_SHELL_EXEC=1"
        )
    raise SecurityVulnerabilityException(f"Unknown shell execution backend: {backend}")


def _format_sandbox_result(result: SandboxResult, timeout: float) -> str:
    if result.timed_out:
        return f"ERROR: Command timed out after {timeout}s"

    out = result.stdout[:8000]
    err = result.stderr[:2000]
    formatted = f"exit_code: {result.exit_code}\n"
    if out:
        formatted += f"stdout:\n{out}\n"
    if err:
        formatted += f"stderr:\n{err}\n"
    return formatted


async def exec_shell(args: dict) -> str:
    command = str(args["command"])
    timeout = min(_MAX_SHELL_TIMEOUT_SECONDS, float(args.get("timeout", 30)))

    await _require_shell_gate_allow(command)
    _reject_dangerous_shell_pattern(command)

    try:
        backend = _shell_backend_from_env()
    except SecurityVulnerabilityException as exc:
        _quarantine_shell_execution(
            "shell_backend_config_denied",
            command,
            {"error": str(exc)},
        )
        raise

    logger.info(
        "shell_exec via %s: sha256=%s preview=%s",
        backend.name,
        hashlib.sha256(command.encode("utf-8")).hexdigest()[:12],
        _redacted_command_preview(command),
    )

    try:
        result = await backend.execute(command, timeout)
    except SecurityVulnerabilityException:
        raise
    except Exception as exc:
        _quarantine_shell_execution(
            "shell_backend_failure",
            command,
            {"backend": backend.name, "error_type": type(exc).__name__},
        )
        raise SecurityVulnerabilityException(
            f"Shell backend {backend.name!r} failed closed: {type(exc).__name__}"
        ) from exc

    return _format_sandbox_result(result, timeout)
