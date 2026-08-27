"""Bounded argv subprocess capture used by the Foundry isolation boundary."""

from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class BoundedProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False
    blocked: bool = False
    blocked_reason: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False


def run_bounded_argv(
    argv: Sequence[str],
    *,
    cwd: str | None,
    timeout_s: float,
    output_limit_bytes: int,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> BoundedProcessResult:
    """Execute an already-validated argv and retain at most N bytes per stream.

    The production path drains stdout and stderr continuously, discarding bytes
    beyond the cap so an untrusted child cannot force unbounded host memory.
    ``runner`` remains injectable for deterministic tests; injected output is
    capped before it crosses this module's result boundary.
    """
    if runner is subprocess.run:
        return _run_streaming(
            argv,
            cwd=cwd,
            timeout_s=timeout_s,
            output_limit_bytes=output_limit_bytes,
        )
    return _run_injected(
        argv,
        cwd=cwd,
        timeout_s=timeout_s,
        output_limit_bytes=output_limit_bytes,
        runner=runner,
    )


def _run_injected(
    argv, *, cwd, timeout_s, output_limit_bytes, runner
) -> BoundedProcessResult:
    start = time.monotonic()
    try:
        process = runner(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _bounded_text(exc.stdout, output_limit_bytes)
        stderr, stderr_truncated = _bounded_text(exc.stderr, output_limit_bytes)
        return BoundedProcessResult(
            -1,
            stdout,
            stderr or "timeout",
            time.monotonic() - start,
            timed_out=True,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError) as exc:
        return BoundedProcessResult(
            -1,
            "",
            "",
            time.monotonic() - start,
            blocked=True,
            blocked_reason=f"process invocation failed: {type(exc).__name__}",
        )

    returncode = getattr(process, "returncode", None)
    if type(returncode) is not int:
        return BoundedProcessResult(
            -1,
            "",
            "",
            time.monotonic() - start,
            blocked=True,
            blocked_reason="process runner returned a malformed exit code",
        )
    stdout, stdout_truncated = _bounded_text(
        getattr(process, "stdout", ""), output_limit_bytes
    )
    stderr, stderr_truncated = _bounded_text(
        getattr(process, "stderr", ""), output_limit_bytes
    )
    return BoundedProcessResult(
        returncode,
        stdout,
        stderr,
        time.monotonic() - start,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )


def _run_streaming(
    argv, *, cwd, timeout_s, output_limit_bytes
) -> BoundedProcessResult:
    start = time.monotonic()
    try:
        process = subprocess.Popen(  # noqa: S603 - caller validates argv
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
        return BoundedProcessResult(
            -1,
            "",
            "",
            time.monotonic() - start,
            blocked=True,
            blocked_reason=f"process invocation failed: {type(exc).__name__}",
        )

    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    truncated = {"stdout": False, "stderr": False}
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    assert process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = start + timeout_s
    timed_out = False
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(timeout=min(remaining, 0.1)):
                _drain_one(
                    selector,
                    key.fileobj,
                    key.data,
                    buffers,
                    truncated,
                    output_limit_bytes,
                )
        if not timed_out:
            try:
                process.wait(timeout=max(deadline - time.monotonic(), 0.0))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out:
            _kill_process_group(process)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
            _drain_after_exit(selector, buffers, truncated, output_limit_bytes)
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    stdout = bytes(buffers["stdout"]).decode("utf-8", errors="replace")
    stderr = bytes(buffers["stderr"]).decode("utf-8", errors="replace")
    return BoundedProcessResult(
        -1 if timed_out else process.returncode,
        stdout,
        stderr or ("timeout" if timed_out else ""),
        time.monotonic() - start,
        timed_out=timed_out,
        stdout_truncated=truncated["stdout"],
        stderr_truncated=truncated["stderr"],
    )


def _drain_one(selector, stream, name, buffers, truncated, limit) -> None:
    try:
        chunk = os.read(stream.fileno(), 64 * 1024)
    except OSError:
        chunk = b""
    if not chunk:
        try:
            selector.unregister(stream)
        except (KeyError, ValueError):
            return
        return
    remaining = max(0, limit - len(buffers[name]))
    buffers[name].extend(chunk[:remaining])
    if len(chunk) > remaining:
        truncated[name] = True


def _drain_after_exit(selector, buffers, truncated, limit) -> None:
    deadline = time.monotonic() + 1.0
    while selector.get_map() and time.monotonic() < deadline:
        for key, _ in selector.select(timeout=0.05):
            _drain_one(selector, key.fileobj, key.data, buffers, truncated, limit)


def _kill_process_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        try:
            process.kill()
        except ProcessLookupError:
            return


def _bounded_text(value: object, limit: int) -> tuple[str, bool]:
    if value is None:
        return "", False
    encoded = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return encoded[:limit].decode("utf-8", errors="replace"), len(encoded) > limit
