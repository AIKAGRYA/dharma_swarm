#!/usr/bin/env python3
"""CLI wrapper for read-only inquiry chewing through the TelicSeam."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.inquiry_substrate_chew import (  # noqa: E402
    DEFAULT_INLET_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEED_PATH,
    DEFAULT_WITNESS_PATH,
    ChewConfig,
    ProviderType,
    run_chew,
)


def _provider_type(value: str) -> ProviderType:
    try:
        return ProviderType(value)
    except ValueError as exc:
        valid = ", ".join(provider.value for provider in ProviderType)
        raise argparse.ArgumentTypeError(
            f"unknown provider {value!r}; valid providers: {valid}"
        ) from exc


def parse_args(argv: list[str] | None = None) -> ChewConfig:
    parser = argparse.ArgumentParser(
        description="Run an inquiry seed through TelicSeam + provider metabolism.",
    )
    parser.add_argument("seed_path", nargs="?", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--inlet", type=Path, default=DEFAULT_INLET_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--witness-jsonl", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--ontology-path", type=Path)
    parser.add_argument("--provider", type=_provider_type)
    parser.add_argument("--model")
    parser.add_argument("--prompt-class", default="seed_chew")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-seed-chars", type=int, default=24_000)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--block-on-review", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        help="Reasoning effort hint for reasoning models (currently gpt-5*). "
        "If unset, gpt-5 defaults to 'low' to preserve visible-content budget.",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe the resolved provider's /models endpoint before calling complete. "
        "Catches network/region/account 403s before paying for a full request.",
    )
    parser.add_argument(
        "--probe-timeout-seconds",
        type=float,
        default=5.0,
        help="Probe HTTP timeout in seconds (default 5).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="For target-blind label packets, label N examples per run.",
    )
    parser.add_argument(
        "--chunk-index",
        type=int,
        default=1,
        help="1-based chunk index when --chunk-size is set.",
    )
    args = parser.parse_args(argv)
    return ChewConfig(
        seed_path=args.seed_path,
        inlet_path=args.inlet,
        output_dir=args.output_dir,
        witness_path=args.witness_jsonl,
        ontology_path=args.ontology_path,
        provider_type=args.provider,
        model=args.model,
        prompt_class=args.prompt_class,
        max_tokens=args.max_tokens,
        max_seed_chars=args.max_seed_chars,
        timeout_seconds=args.timeout_seconds,
        block_on_review=args.block_on_review,
        dry_run=args.dry_run,
        reasoning_effort=args.reasoning_effort,
        probe=args.probe,
        probe_timeout_seconds=args.probe_timeout_seconds,
        chunk_size=args.chunk_size,
        chunk_index=args.chunk_index,
    )


async def async_main(argv: list[str] | None = None) -> int:
    result = await run_chew(parse_args(argv))
    print(json.dumps(result.to_json(), indent=2, sort_keys=True))
    return 0 if result.success or result.blocked else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
