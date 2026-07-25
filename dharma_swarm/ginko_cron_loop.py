"""Ginko cron loop — container entrypoint for the compose ``cron`` service.

Replaces the docker-compose inline ``python3 -c`` script: YAML double-quoted
scalars fold newlines into spaces, which collapsed the multi-line body
(``while True:`` + ``try:``) onto one line — a SyntaxError, so the cron
container crash-looped on every fresh deploy (found live on the VPS,
2026-07-03). Same behavior, now as an importable, testable module:
run one full ginko cycle every ``INTERVAL_SECONDS``, log outcomes, never
let a failed cycle kill the loop.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ginko-cron")

INTERVAL_SECONDS = 21_600  # 6 hours, matching the prior inline script


async def run_cycle() -> dict[str, Any]:
    from dharma_swarm.ginko_orchestrator import action_full_cycle

    result = await action_full_cycle()
    logger.info(
        "Cycle complete: %s",
        {
            key: "OK"
            if not isinstance(value, dict) or "error" not in value
            else value["error"]
            for key, value in result.items()
            if key != "total_duration_ms"
        },
    )
    return result


def main(
    *,
    max_cycles: int | None = None,
    interval_seconds: float = INTERVAL_SECONDS,
    sleep: Any = time.sleep,
) -> int:
    """Run cycles forever (or ``max_cycles`` for tests). Returns failure count."""
    cycles = 0
    consecutive_failures = 0
    while max_cycles is None or cycles < max_cycles:
        cycles += 1
        try:
            asyncio.run(run_cycle())
            consecutive_failures = 0
        except Exception as exc:
            consecutive_failures += 1
            logger.error(
                "Cycle failed (%d consecutive): %s", consecutive_failures, exc
            )
        sleep(interval_seconds)
    return consecutive_failures


if __name__ == "__main__":  # pragma: no cover - container entrypoint
    raise SystemExit(main())
