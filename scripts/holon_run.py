#!/usr/bin/env python3
"""Compatibility CLI for the package-owned sovereign-holon run runtime.

    python3 scripts/holon_run.py opus_composer 2
    python3 scripts/holon_run.py opus_composer 2 --mode declared-first
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.terminal_commands._holons import (  # noqa: E402
    ROUTING_MODE_CHOICES,
    SELF_TASK,
    _looks_like_provider_failure,
    _make_free_runner,
    _resolve_free_provider,
    _resolve_provider,
    run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run governed cycles for a registered sovereign holon."
    )
    parser.add_argument("agent", nargs="?", default="opus_composer")
    parser.add_argument("cycles", nargs="?", type=int, default=2)
    parser.add_argument("--mode", choices=ROUTING_MODE_CHOICES, default="free-first")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.agent, args.cycles, routing_mode=args.mode))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ROUTING_MODE_CHOICES",
    "SELF_TASK",
    "_looks_like_provider_failure",
    "_make_free_runner",
    "_resolve_free_provider",
    "_resolve_provider",
    "main",
    "run",
]
