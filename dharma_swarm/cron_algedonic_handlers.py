"""Cron handlers for algedonic signal maintenance jobs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dharma_swarm.cron_job_runtime import CronJobExecutionResult, CronJobRunStatus


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def run_algedonic_triage(job: dict[str, Any]) -> CronJobExecutionResult:
    """Drain algedonic pain signals into the triage cursor and alert flag."""

    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "algedonic_triage.py"
    if not script.exists():
        error = f"missing script: {script}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )

    env = os.environ.copy()
    state_dir = str(job.get("state_dir") or "").strip()
    if state_dir:
        env["DHARMA_STATE_DIR"] = str(Path(state_dir).expanduser())

    timeout = _as_int(job.get("timeout_sec"), 60)
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root),
            env=env,
        )
    except subprocess.TimeoutExpired:
        error = f"algedonic_triage timed out after {timeout}s"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output="",
            error=error,
        )

    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=output or err or f"algedonic_triage exited {proc.returncode}",
            error=err or output[:500],
        )
    return CronJobExecutionResult(
        status=CronJobRunStatus.COMPLETED,
        output=output or "algedonic_triage: no new signals",
        error="",
    )


def run_provider_starvation_alert(job: dict[str, Any]) -> CronJobExecutionResult:
    """Emit algedonic P0 signal when provider-chain failures dominate."""

    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "runtime" / "provider_starvation_alert.py"
    if not script.exists():
        error = f"missing script: {script}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=error,
            error=error,
        )

    args = [sys.executable, str(script)]
    state_dir = str(job.get("state_dir") or "").strip()
    if state_dir:
        args.extend(["--state-dir", state_dir])
    since_date = str(job.get("since_date") or "").strip()
    if since_date:
        args.extend(["--since-date", since_date])
    if job.get("threshold") is not None:
        args.extend(["--threshold", str(job.get("threshold"))])
    if job.get("min_count") is not None:
        args.extend(["--min-count", str(job.get("min_count"))])

    timeout = _as_int(job.get("timeout_sec"), 30)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(repo_root),
        )
    except subprocess.TimeoutExpired:
        error = f"provider_starvation_alert timed out after {timeout}s"
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output="",
            error=error,
        )

    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=output or err or f"provider_starvation_alert exited {proc.returncode}",
            error=err or output[:500],
        )
    return CronJobExecutionResult(
        status=CronJobRunStatus.COMPLETED,
        output=output or "provider_starvation_alert: no output",
        error="",
    )
