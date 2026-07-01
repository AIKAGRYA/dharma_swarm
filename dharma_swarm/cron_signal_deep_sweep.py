"""Cron handler for the signal_deep_sweep job.

Extracted from cron_runner.py (Rule 10 module-line-budget decomposition,
2026-07-01) to keep cron_runner.py under the enforced 1000-line ceiling.
Follows the same "cron-adjacent logic lives in its own small module,
cron_runner.py just dispatches to it" pattern already used by
cron_job_runtime.py and cron_portable_context.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dharma_swarm.cron_job_runtime import CronJobExecutionResult, CronJobRunStatus
from dharma_swarm.daemon_config import dharma_state_dir


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def run_signal_deep_sweep_job(job: dict[str, Any]) -> CronJobExecutionResult:
    """Run the capped, automated deep sweep (separate, lower-cadence cousin
    of world_scout -- widens to DefaultBeats() and runs a bounded LLM
    verification+synthesis pass through invoke_agent(), not just cheap API
    fetches). Disabled by default: see signal_deep_sweep's cron_jobs.json
    entry -- spending real LLM budget automatically is a bigger decision
    than free API scraping and should be turned on deliberately.
    """
    fetch_enabled = _as_bool(job.get("fetch"), False) or _as_bool(
        os.environ.get("DHARMA_SIGNAL_DEEP_SWEEP_FETCH"),
        False,
    )
    if not fetch_enabled:
        return CronJobExecutionResult(
            status=CronJobRunStatus.WAITING_EXTERNAL,
            output=(
                "signal_deep_sweep fetch disabled; set job.fetch=true or "
                "DHARMA_SIGNAL_DEEP_SWEEP_FETCH=1 to run the capped deep sweep"
            ),
            metadata={"fetch_enabled": False},
        )

    try:
        from dharma_swarm.knowledge_ops.deep_sweep import (
            DEFAULT_MAX_VERIFICATIONS,
            run_deep_sweep,
        )

        state_dir = job.get("state_dir") or None
        state_path = Path(str(state_dir)).expanduser() if state_dir else dharma_state_dir()
        max_verifications = _as_int(job.get("max_verifications"), DEFAULT_MAX_VERIFICATIONS)
        result = asyncio.run(
            run_deep_sweep(
                state_path,
                max_verifications=max_verifications,
                scout_timeout_s=_as_int(job.get("scout_timeout_sec"), 300),
                verification_timeout_s=_as_int(job.get("verification_timeout_sec"), 300),
                synthesis_timeout_s=_as_int(job.get("synthesis_timeout_sec"), 300),
            )
        )
        output = (
            "signal_deep_sweep: "
            f"movements={result['movements_count']} "
            f"newly_seen={result['newly_seen_count']} "
            f"verifications={result['verifications_count']} "
            f"(cap={max_verifications}) "
            f"likely_fabricated={result['likely_fabricated_count']} "
            f"digest={result['digest_path']}"
        )
        errors = [
            e
            for e in (result.get("scout_error"), result.get("verification_error"), result.get("synthesis_error"))
            if e
        ]
        if errors:
            output = f"{output} errors={errors}"
        return CronJobExecutionResult(
            status=CronJobRunStatus.COMPLETED,
            output=output,
            error="; ".join(errors)[:500] if errors else "",
            metadata={
                "fetch_enabled": True,
                "max_verifications": max_verifications,
                **{k: v for k, v in result.items() if k not in ("cycle_dir",)},
            },
        )
    except Exception as e:  # noqa: BLE001
        return CronJobExecutionResult(
            status=CronJobRunStatus.FAILED,
            output=str(e),
            error=str(e),
        )


__all__ = ["run_signal_deep_sweep_job"]
