"""Default-off Darwin pre-apply observer for a separate ``vh`` process.

Admits only a well-formed child-reported CLEAN result. Does not inspect a
proposal diff, authenticate a binary, or prove the Rust engine. ``demo`` is
engine-liveness calibration only.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import signal
import stat
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

SCHEMA = "dharma.vibe_halt_observer.v1"
SCOPE = "engine_liveness_calibration"
DEFAULT_WORKLOAD = "demo"
DEFAULT_SEED = 0xD1CE
DEFAULT_SEED_TOKEN = "0xD1CE"
DEFAULT_UNIVERSES = 8
DEFAULT_TIMEOUT_SECONDS = 30
MAX_STREAM_BYTES = 1024 * 1024
MAX_TAIL_BYTES = 4096
MAX_UNIVERSES = 1_048_576
WORKLOAD_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
_HEADER_RE = re.compile(
    r"^vibe-halt: workload=(?P<workload>\S+) seed=(?P<seed>0x[0-9a-fA-F]+) "
    r"universes=(?P<universes>\d+) palette=\S+ divergence-check=(?P<div>true|false) "
    r"schedule=\S+ tape=\S+ fault-plan-schema=\S+$"
)
_VERDICT_CLEAN = "  verdict: CLEAN"
_VERDICT_FINDINGS = "  verdict: FINDINGS (see above)"
_VERDICT_UNCHECKED_RE = re.compile(r"^  verdict: UNCHECKED \(.*\)$")
_NULL_PROCESS = {
    "exit_code": None, "duration_ms": None, "timed_out": None, "output_limited": None,
    "stdout_sha256": None, "stderr_sha256": None, "stdout_tail": None, "stderr_tail": None,
}
_NULL_BINARY = {"resolved_path": None, "sha256": None}


class ObserverMode(str, Enum):
    OFF = "off"
    OBSERVE = "observe"
    REQUIRE = "require"
    INVALID = "invalid"


class ReportedOutcome(str, Enum):
    CLEAN = "clean"
    FINDINGS = "findings"
    UNCHECKED = "unchecked"
    ERROR = "error"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class ObserverPolicy:
    mode: ObserverMode


@dataclass(frozen=True, slots=True)
class ObserverSettings:
    bin_explicit: str | None
    workload: str
    universes: int
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ObserverObservation:
    mode: str
    reported_outcome: ReportedOutcome
    blocks_apply: bool
    ran: bool
    reason: str
    request: Mapping[str, Any]
    process: Mapping[str, Any]
    binary: Mapping[str, Any]

    def to_receipt(self, *, proposal_id: str, cycle_id: str | None) -> dict[str, Any]:
        return {
            "schema": SCHEMA, "proposal_id": proposal_id, "cycle_id": cycle_id,
            "mode": self.mode, "scope": SCOPE, "calibration_only": True, "diff_bound": False,
            "ran": self.ran, "reported_outcome": self.reported_outcome.value,
            "blocks_apply": self.blocks_apply, "reason": self.reason,
            "request": dict(self.request), "process": dict(self.process), "binary": dict(self.binary),
        }


def _default_request() -> dict[str, Any]:
    return {"workload": DEFAULT_WORKLOAD, "seed": DEFAULT_SEED_TOKEN, "universes": DEFAULT_UNIVERSES}


def _observation(
    mode: ObserverMode,
    outcome: ReportedOutcome,
    *,
    ran: bool,
    reason: str,
    request: Mapping[str, Any] | None = None,
    process: Mapping[str, Any] | None = None,
    binary: Mapping[str, Any] | None = None,
) -> ObserverObservation:
    return ObserverObservation(
        mode=mode.value, reported_outcome=outcome, blocks_apply=_blocks_apply(mode, outcome),
        ran=ran, reason=reason,
        request=dict(request) if request is not None else _default_request(),
        process=dict(process) if process is not None else dict(_NULL_PROCESS),
        binary=dict(binary) if binary is not None else dict(_NULL_BINARY),
    )


def _read_policy() -> ObserverPolicy:
    raw = os.environ.get("DHARMA_VH_OBSERVER")
    if raw is None or raw.strip() == "":
        return ObserverPolicy(mode=ObserverMode.OFF)
    token = raw.strip().lower()
    mapping = {item.value: item for item in (ObserverMode.OFF, ObserverMode.OBSERVE, ObserverMode.REQUIRE)}
    return ObserverPolicy(mode=mapping.get(token, ObserverMode.INVALID))


def _read_optional_text(name: str) -> str | None:
    return None if name not in os.environ else os.environ[name].strip()


def _bounded_int(raw: str | None, default: int, lo: int, hi: int, err: str):
    if raw is None:
        return default, None
    try:
        value = int(raw, 10)
    except ValueError:
        return None, err
    if value < lo or value > hi:
        return None, err
    return value, None


def _read_settings() -> tuple[ObserverSettings | None, str | None]:
    raw_bin = _read_optional_text("DHARMA_VH_BIN")
    if raw_bin == "":
        return None, "invalid_bin"
    raw_workload = _read_optional_text("DHARMA_VH_WORKLOAD")
    if raw_workload is None:
        workload = DEFAULT_WORKLOAD
    elif not WORKLOAD_RE.fullmatch(raw_workload):
        return None, "invalid_workload"
    else:
        workload = raw_workload
    universes, err = _bounded_int(
        _read_optional_text("DHARMA_VH_UNIVERSES"), DEFAULT_UNIVERSES, 1, MAX_UNIVERSES, "invalid_universes"
    )
    if err is not None:
        return None, err
    timeout_seconds, err = _bounded_int(
        _read_optional_text("DHARMA_VH_TIMEOUT_SECONDS"), DEFAULT_TIMEOUT_SECONDS, 1, 300, "invalid_timeout"
    )
    if err is not None:
        return None, err
    return ObserverSettings(raw_bin, workload, universes, timeout_seconds), None


def _regular_executable(path: str) -> bool:
    try:
        st = os.stat(path, follow_symlinks=True)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and os.access(path, os.X_OK)


def _resolve_binary(explicit: str | None) -> tuple[str | None, str | None]:
    if explicit is not None:
        if not os.path.isabs(explicit) or not _regular_executable(explicit):
            return None, "invalid_bin"
        return os.path.abspath(explicit), None
    located = shutil.which("vh")
    if located is None:
        return None, "missing_binary"
    resolved = os.path.abspath(located)
    if not _regular_executable(resolved):
        return None, "missing_binary"
    return resolved, None


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tail_text(payload: bytes) -> str:
    return payload[-MAX_TAIL_BYTES:].decode("utf-8", errors="replace")


def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    if proc.pid is None:
        return
    killpg, sigkill = getattr(os, "killpg", None), getattr(signal, "SIGKILL", None)
    try:
        if killpg is not None and sigkill is not None:
            killpg(proc.pid, sigkill)
            return
    except (AttributeError, ProcessLookupError, PermissionError, OSError):
        pass
    try:
        proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        return


async def _await_reap(awaitable: Any) -> Any:
    task = asyncio.ensure_future(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
            continue
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


async def _terminate_and_reap(proc: asyncio.subprocess.Process) -> None:
    _kill_process_group(proc)
    try:
        await _await_reap(proc.wait())
    except (ProcessLookupError, ChildProcessError, OSError):
        return


async def _cancel_tasks(*tasks: asyncio.Task[Any]) -> None:
    pending = [task for task in tasks if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


async def _stop_child(proc: asyncio.subprocess.Process, *tasks: asyncio.Task[Any]) -> None:
    await _terminate_and_reap(proc)
    await _cancel_tasks(*tasks)


async def _read_capped_stream(stream: asyncio.StreamReader) -> bytes:
    buf = bytearray()
    while True:
        remaining_plus = MAX_STREAM_BYTES + 1 - len(buf)
        if remaining_plus <= 0:
            return bytes(buf)
        chunk = await stream.read(min(65536, remaining_plus))
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)
        if len(buf) > MAX_STREAM_BYTES:
            return bytes(buf)


def _is_verdict_line(line: str) -> bool:
    return (
        line == _VERDICT_CLEAN
        or line == _VERDICT_FINDINGS
        or _VERDICT_UNCHECKED_RE.fullmatch(line) is not None
    )


def _parse_vh_run(
    stdout: str,
    stderr: str,
    exit_code: int,
    *,
    workload: str,
    universes: int,
    seed: int = DEFAULT_SEED,
) -> tuple[ReportedOutcome, str]:
    if exit_code < 0:
        return ReportedOutcome.ERROR, "signal_termination"
    stdout_lines, stderr_lines = stdout.splitlines(), stderr.splitlines()
    if any(_is_verdict_line(line) for line in stderr_lines):
        return ReportedOutcome.ERROR, "stderr_verdict"
    headers = [line for line in stdout_lines if line.startswith("vibe-halt:")]
    if len(headers) != 1:
        return ReportedOutcome.ERROR, "duplicate_header" if len(headers) > 1 else "malformed_header"
    match = _HEADER_RE.fullmatch(headers[0])
    if match is None:
        return ReportedOutcome.ERROR, "malformed_header"
    try:
        header_seed, header_universes = int(match.group("seed"), 16), int(match.group("universes"), 10)
    except ValueError:
        return ReportedOutcome.ERROR, "malformed_header"
    if (
        match.group("workload") != workload or header_seed != seed
        or header_universes != universes or match.group("div") != "true"
    ):
        return ReportedOutcome.ERROR, "header_mismatch"
    verdicts = [line for line in stdout_lines if _is_verdict_line(line)]
    if not verdicts:
        return ReportedOutcome.ERROR, "stderr_verdict" if any("verdict:" in line for line in stderr_lines) else "missing_verdict"
    if len(verdicts) > 1:
        return ReportedOutcome.ERROR, "contradictory_verdict" if len(set(verdicts)) > 1 else "duplicate_verdict"
    verdict = verdicts[0]
    expected = {_VERDICT_CLEAN: (0, ReportedOutcome.CLEAN, "clean"), _VERDICT_FINDINGS: (1, ReportedOutcome.FINDINGS, "findings")}
    if verdict in expected:
        want_exit, outcome, reason = expected[verdict]
        return (outcome, reason) if exit_code == want_exit else (ReportedOutcome.ERROR, "exit_mismatch")
    if _VERDICT_UNCHECKED_RE.fullmatch(verdict) is None:
        return ReportedOutcome.ERROR, "malformed_verdict"
    return (ReportedOutcome.UNCHECKED, "unchecked") if exit_code == 3 else (ReportedOutcome.ERROR, "exit_mismatch")


def _blocks_apply(mode: ObserverMode, outcome: ReportedOutcome) -> bool:
    if mode is ObserverMode.INVALID:
        return True
    if mode is ObserverMode.OFF:
        return False
    return outcome is ReportedOutcome.FINDINGS or (
        mode is ObserverMode.REQUIRE and outcome is not ReportedOutcome.CLEAN
    )


def _process_record(
    *,
    stdout: bytes,
    stderr: bytes,
    exit_code: int | None,
    duration_ms: int,
    timed_out: bool,
    output_limited: bool,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code, "duration_ms": duration_ms, "timed_out": timed_out,
        "output_limited": output_limited, "stdout_sha256": _sha256_bytes(stdout),
        "stderr_sha256": _sha256_bytes(stderr), "stdout_tail": _tail_text(stdout),
        "stderr_tail": _tail_text(stderr),
    }


def _task_bytes(task: asyncio.Task[bytes] | None) -> bytes:
    if task is None or not task.done() or task.cancelled() or task.exception() is not None:
        return b""
    return task.result()


async def _execute_vh(
    resolved: str,
    settings: ObserverSettings,
) -> tuple[bytes, bytes, int | None, int, bool, bool, str | None]:
    argv = [resolved, "run", "--workload", settings.workload, "--seed", DEFAULT_SEED_TOKEN, "--universes", str(settings.universes)]
    tmp = tempfile.TemporaryDirectory(prefix="dharma-vh-obs-")
    stdout = b""
    stderr = b""
    timed_out = False
    output_limited = False
    reason: str | None = None
    exit_code: int | None = None
    started = time.monotonic()
    proc: asyncio.subprocess.Process | None = None
    out_task: asyncio.Task[bytes] | None = None
    err_task: asyncio.Task[bytes] | None = None
    try:
        child_env = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "TMPDIR": tmp.name}
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmp.name,
                env=child_env,
                start_new_session=True,
            )
        except OSError:
            return b"", b"", None, int((time.monotonic() - started) * 1000), False, False, "spawn_failure"
        assert proc.stdout is not None and proc.stderr is not None
        out_task = asyncio.create_task(_read_capped_stream(proc.stdout))
        err_task = asyncio.create_task(_read_capped_stream(proc.stderr))
        deadline = started + settings.timeout_seconds
        pending: set[asyncio.Task[bytes]] = {out_task, err_task}
        try:
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out, reason = True, "timeout"
                    break
                done, pending = await asyncio.wait(
                    pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
                )
                if not done:
                    timed_out, reason = True, "timeout"
                    break
                for task in done:
                    if len(task.result()) > MAX_STREAM_BYTES:
                        output_limited, reason, pending = True, "output_overflow", set()
                        break
            if reason in {"timeout", "output_overflow"}:
                await _stop_child(proc, out_task, err_task)
            else:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=max(0.01, deadline - time.monotonic()))
                except TimeoutError:
                    timed_out, reason = True, "timeout"
                    await _stop_child(proc, out_task, err_task)
        except asyncio.CancelledError:
            await _stop_child(proc, out_task, err_task)
            raise
        stdout, stderr = _task_bytes(out_task), _task_bytes(err_task)
        if len(stdout) > MAX_STREAM_BYTES or len(stderr) > MAX_STREAM_BYTES:
            output_limited, reason = True, "output_overflow"
        exit_code = proc.returncode
        if reason is None and exit_code is None:
            reason, timed_out = "timeout", True
    finally:
        try:
            tmp.cleanup()
        except OSError:
            pass
    return stdout, stderr, exit_code, int((time.monotonic() - started) * 1000), timed_out, output_limited, reason


async def run_observer() -> ObserverObservation | None:
    """Return None only when policy resolves to off."""
    policy = _read_policy()
    if policy.mode is ObserverMode.OFF:
        return None
    if policy.mode is ObserverMode.INVALID:
        return _observation(policy.mode, ReportedOutcome.ERROR, ran=False, reason="invalid_policy")
    settings, settings_error = _read_settings()
    if settings is None:
        return _observation(policy.mode, ReportedOutcome.ERROR, ran=False, reason=settings_error or "invalid_settings")
    request = {"workload": settings.workload, "seed": DEFAULT_SEED_TOKEN, "universes": settings.universes}

    def _done(outcome: ReportedOutcome, reason: str, *, ran: bool, process=None, binary=None):
        return _observation(
            policy.mode, outcome, ran=ran, reason=reason, request=request, process=process, binary=binary
        )

    resolved, binary_error = _resolve_binary(settings.bin_explicit)
    if binary_error == "missing_binary":
        return _done(ReportedOutcome.MISSING, "missing_binary", ran=False)
    if binary_error is not None or resolved is None:
        return _done(ReportedOutcome.ERROR, binary_error or "invalid_bin", ran=False)
    binary = {"resolved_path": resolved, "sha256": _sha256_file(resolved)}
    stdout, stderr, exit_code, duration_ms, timed_out, output_limited, exec_reason = await _execute_vh(
        resolved, settings
    )
    process = _process_record(
        stdout=stdout, stderr=stderr, exit_code=exit_code, duration_ms=duration_ms,
        timed_out=timed_out, output_limited=output_limited,
    )
    if exec_reason == "spawn_failure":
        return _done(ReportedOutcome.ERROR, "spawn_failure", ran=False, process=process, binary=binary)
    if exec_reason is not None:
        return _done(ReportedOutcome.ERROR, exec_reason, ran=True, process=process, binary=binary)
    if exit_code is None or exit_code < 0:
        return _done(ReportedOutcome.ERROR, "signal_termination", ran=True, process=process, binary=binary)
    try:
        stdout_text, stderr_text = stdout.decode("utf-8"), stderr.decode("utf-8")
    except UnicodeDecodeError:
        return _done(ReportedOutcome.ERROR, "utf8_error", ran=True, process=process, binary=binary)
    outcome, reason = _parse_vh_run(
        stdout_text, stderr_text, exit_code, workload=settings.workload, universes=settings.universes
    )
    return _done(outcome, reason, ran=True, process=process, binary=binary)
