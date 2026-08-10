"""Bounded local client process used to drive the container runtime."""
from __future__ import annotations

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Sequence

from .pr_suite_execution_paths import redact_secret_text


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limit_exceeded: bool = False
    duration_seconds: float = 0.0
    profile_sha256: str = ""

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.output_limit_exceeded

    def to_receipt(self, *, max_output_chars: int = 4000) -> dict[str, Any]:
        return {
            "argv": [redact_secret_text(arg) for arg in self.argv],
            "cwd": self.cwd,
            "returncode": self.returncode,
            "passed": self.passed,
            "timed_out": self.timed_out,
            "output_limit_exceeded": self.output_limit_exceeded,
            "duration_seconds": round(self.duration_seconds, 4),
            "execution_profile_sha256": self.profile_sha256,
            "stdout_tail": redact_secret_text(self.stdout[-max_output_chars:]),
            "stderr_tail": redact_secret_text(self.stderr[-max_output_chars:]),
        }


def _clean_host_env() -> dict[str, str]:
    return {
        "DOCKER_CONFIG": "/nonexistent",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.defpath,
        "TZ": "UTC",
    }


def _kill_process_group(proc: subprocess.Popen[bytes]) -> None:
    pgid = proc.pid
    try:
        os.killpg(pgid, signal.SIGTERM)
        if proc.poll() is None:
            proc.wait(timeout=0.25)
    except (ProcessLookupError, subprocess.TimeoutExpired, ChildProcessError):
        pass
    # The runtime client can exit before one of its descendants. Always send
    # the hard-stop to the original group, even when the group leader is gone.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if proc.poll() is None:
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass


def _bounded_run(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    output_limit_bytes: int,
    stdin: bytes | None = None,
) -> tuple[int, bytes, bytes, bool, bool, float]:
    started = time.monotonic()
    proc = subprocess.Popen(  # noqa: S603 - explicit container runtime argv.
        list(argv),
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_clean_host_env(),
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    buffers: dict[int, bytearray] = {}
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
            buffers[stream.fileno()] = bytearray()
    input_offset = 0
    if stdin is not None and proc.stdin is not None:
        if stdin:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE)
        else:
            proc.stdin.close()
    timed_out = False
    exceeded = False
    total = 0
    deadline = started + max(0.001, timeout_seconds)
    try:
        while selector.get_map() or proc.poll() is None:
            if time.monotonic() >= deadline:
                timed_out = True
                _kill_process_group(proc)
            for key, _ in selector.select(timeout=0.02):
                if proc.stdin is not None and key.fileobj is proc.stdin:
                    try:
                        written = os.write(
                            key.fd,
                            stdin[input_offset : input_offset + 65536]
                            if stdin is not None
                            else b"",
                        )
                    except (BrokenPipeError, OSError):
                        selector.unregister(key.fileobj)
                        proc.stdin.close()
                        continue
                    input_offset += written
                    if stdin is None or input_offset >= len(stdin):
                        selector.unregister(key.fileobj)
                        proc.stdin.close()
                    continue
                try:
                    chunk = os.read(key.fd, 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = max(0, output_limit_bytes - total)
                buffers[key.fd].extend(chunk[:remaining])
                total += len(chunk)
                if total > output_limit_bytes:
                    exceeded = True
                    _kill_process_group(proc)
            if (timed_out or exceeded) and proc.poll() is not None and not selector.get_map():
                break
        if proc.poll() is None:
            _kill_process_group(proc)
    except BaseException:
        _kill_process_group(proc)
        raise
    finally:
        if proc.stdin is not None and not proc.stdin.closed:
            proc.stdin.close()
        selector.close()
    returncode = 124 if timed_out else 125 if exceeded else int(proc.returncode or 0)
    stdout = bytes(buffers.get(proc.stdout.fileno(), b"")) if proc.stdout is not None else b""
    stderr = bytes(buffers.get(proc.stderr.fileno(), b"")) if proc.stderr is not None else b""
    return returncode, stdout, stderr, timed_out, exceeded, time.monotonic() - started


__all__ = ["CommandResult"]
