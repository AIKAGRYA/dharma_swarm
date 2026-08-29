#!/usr/bin/env python3
"""Run the versioned status probe and receipt any non-healthy verdict."""

from __future__ import annotations

import os
import fcntl
import hashlib
import json
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

Runner = Callable[..., subprocess.CompletedProcess]


def _terminate_process(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass


def _bounded_process(
    command: list[str], *, timeout_s: float, max_output_bytes: int
) -> tuple[subprocess.CompletedProcess, bool, bool]:
    """Self-contained stdlib probe; imports no mutable checkout code."""
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        start_new_session=True,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    limited = threading.Event()
    lock = threading.Lock()

    def drain(name: str, pipe) -> None:
        nonlocal total
        while True:
            chunk = pipe.read(65_536)
            if not chunk:
                return
            with lock:
                remaining = max(0, max_output_bytes - total)
                if remaining:
                    retained = chunk[:remaining]
                    buffers[name].extend(retained)
                    total += len(retained)
                if len(chunk) > remaining:
                    limited.set()
                    _terminate_process(proc)

    threads = [
        threading.Thread(target=drain, args=(name, pipe), daemon=True)
        for name, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr))
    ]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process(proc)
        proc.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)
    return (
        subprocess.CompletedProcess(
            command,
            proc.returncode if proc.returncode is not None else -1,
            buffers["stdout"].decode("utf-8", errors="replace"),
            buffers["stderr"].decode("utf-8", errors="replace"),
        ),
        timed_out,
        limited.is_set(),
    )


def _fingerprint(stdout: str, category: str, exit_code: int) -> str:
    try:
        payload = json.loads(stdout)
        basis = {
            "verdict": payload.get("verdict"),
            "problems": payload.get("problems", []),
            "warnings": payload.get("warnings", []),
        }
    except (ValueError, TypeError, AttributeError):
        basis = {"category": category, "exit_code": exit_code}
    return "sha256:" + hashlib.sha256(json.dumps(
        basis, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def run_status_job(
    *,
    repo_root: Path,
    state_root: Path,
    python: Path,
    expected_sha: str,
    verifier: Path = Path("/usr/local/bin/sublimation-foundry-verify-deployment.py"),
    manifest: Path = Path("/etc/dharma-foundry/deployment.json"),
    runner: Runner = subprocess.run,
) -> int:
    state_root = Path(state_root)
    if not state_root.is_absolute() or not state_root.is_dir() or state_root.is_symlink():
        return 4
    previous_umask = os.umask(0o077)
    try:
        with (state_root / ".status-job.lock").open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            verify_command = [
                str(python), "-B", str(verifier), "verify",
                "--repo", str(repo_root),
                "--expected-sha", expected_sha,
                "--manifest", str(manifest),
            ]
            status_command = [
                str(python), str(repo_root / "scripts/foundry/foundry_status.py"),
                "--repo-root", str(repo_root), "--state-root", str(state_root),
                "--expected-sha", expected_sha, "--compact",
            ]
            category = "progress_health"
            try:
                if runner is subprocess.run:
                    verification, timed_out, output_limited = _bounded_process(
                        verify_command,
                        timeout_s=30,
                        max_output_bytes=65_536,
                    )
                    if timed_out:
                        category = "deployment_verify_timeout"
                        status = subprocess.CompletedProcess(
                            verify_command, 4, "", "timeout"
                        )
                    elif output_limited:
                        category = "deployment_verify_output_limit"
                        status = subprocess.CompletedProcess(
                            verify_command, 4, "", "output_limit_exceeded"
                        )
                    elif verification.returncode != 0:
                        category = "deployment_integrity"
                        status = verification
                    else:
                        status, timed_out, output_limited = _bounded_process(
                            status_command,
                            timeout_s=120,
                            max_output_bytes=262_144,
                        )
                else:
                    verification = runner(
                        verify_command, timeout=30, check=False
                    )
                    if verification.returncode != 0:
                        category = "deployment_integrity"
                        status = verification
                    else:
                        status = runner(status_command, timeout=120, check=False)
                        timed_out = False
                        output_limited = False
                if category == "progress_health" and runner is subprocess.run:
                    # ``timed_out``/``output_limited`` now describe the status
                    # probe because a successful verifier reached this branch.
                    if timed_out:
                        category = "status_timeout"
                        status = subprocess.CompletedProcess(
                            status_command, 4, "", "timeout"
                        )
                    elif output_limited:
                        category = "status_output_limit"
                        status = subprocess.CompletedProcess(
                            status_command, 4, status.stdout,
                            "output_limit_exceeded",
                        )
            except subprocess.TimeoutExpired:
                category = (
                    "deployment_verify_timeout"
                    if "verification" not in locals() else "status_timeout"
                )
                status = subprocess.CompletedProcess(
                    verify_command if category.startswith("deployment") else status_command,
                    4,
                    "",
                    "timeout",
                )
            except OSError:
                category = (
                    "deployment_verify_launch_failure"
                    if "verification" not in locals() else "status_launch_failure"
                )
                status = subprocess.CompletedProcess(
                    verify_command if category.startswith("deployment") else status_command,
                    4,
                    "",
                    "launch_failure",
                )
            stdout_value = getattr(status, "stdout", "") or ""
            stdout = (
                stdout_value.decode("utf-8", errors="replace")
                if isinstance(stdout_value, bytes)
                else str(stdout_value)
            )
            if stdout:
                print(stdout.rstrip())
            if status.returncode == 0:
                return 0
            fingerprint = _fingerprint(stdout, category, status.returncode)
            alert_command = [
                str(python), "-B", "/usr/local/bin/sublimation-foundry-alert.py",
                "--state-root", str(state_root),
                "--unit", "sublimation-foundry-status.cron",
                "--category", category,
                "--exit-code", str(status.returncode),
                "--fingerprint", fingerprint,
            ]
            try:
                alert = runner(alert_command, timeout=30, check=False)
            except (OSError, subprocess.SubprocessError):
                return 4
            return status.returncode if alert.returncode == 0 else 4
    finally:
        os.umask(previous_umask)


def main() -> int:
    repo = Path(os.environ.get("FOUNDRY_REPO_ROOT", ""))
    state = Path(os.environ.get("FOUNDRY_STATE_ROOT", ""))
    python = Path(os.environ.get("FOUNDRY_PYTHON", sys.executable))
    expected_sha = os.environ.get("FOUNDRY_EXPECTED_SHA", "")
    verifier = Path(os.environ.get("FOUNDRY_VERIFY_DEPLOYMENT", ""))
    manifest = Path(os.environ.get("FOUNDRY_DEPLOYMENT_MANIFEST", ""))
    if not all(path.is_absolute() for path in (repo, state, python, verifier, manifest)):
        print("Foundry status job requires absolute versioned environment paths", file=sys.stderr)
        return 4
    return run_status_job(
        repo_root=repo,
        state_root=state,
        python=python,
        expected_sha=expected_sha,
        verifier=verifier,
        manifest=manifest,
    )


if __name__ == "__main__":
    raise SystemExit(main())
