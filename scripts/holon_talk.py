#!/usr/bin/env python3
"""Compatibility CLI for the package-owned sovereign-holon talk runtime.

    python3 scripts/holon_talk.py opus_composer "who are you?"
    python3 scripts/holon_talk.py opus_composer --mode declared-first "who are you?"
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
    _looks_like_provider_failure,
    _normalize_routing_mode,
    _resolve_declared_provider,
    _resolve_free_provider,
    _resolve_provider,
    _stream_request,
    talk,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Talk to a registered sovereign holon.")
    parser.add_argument("agent", nargs="?", default="opus_composer")
    parser.add_argument("message", nargs="*")
    parser.add_argument("--mode", choices=ROUTING_MODE_CHOICES, default="free-first")
    parser.add_argument("--max-tokens", type=int, default=400)
    args = parser.parse_args(argv)
    message = " ".join(args.message) or "In two sentences, who are you and what is your telos?"
    return asyncio.run(
        talk(
            args.agent,
            message,
            routing_mode=args.mode,
            max_tokens=args.max_tokens,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ROUTING_MODE_CHOICES",
    "_looks_like_provider_failure",
    "_normalize_routing_mode",
    "_resolve_declared_provider",
    "_resolve_free_provider",
    "_resolve_provider",
    "_stream_request",
    "main",
    "talk",
]
