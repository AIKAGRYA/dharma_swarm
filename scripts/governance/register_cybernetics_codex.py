#!/usr/bin/env python3
"""Register cybernetics_codex through the Stage-1 external-worker desk."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.cybernetics_codex_registration import (  # noqa: E402
    build_external_worker_registration,
)
from dharma_swarm.daemon_config import dharma_state_dir  # noqa: E402
from dharma_swarm.external_agent_registration import register_external_worker  # noqa: E402


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n"


async def _write_registration(args: argparse.Namespace) -> dict[str, object]:
    dharma_home = Path(args.dharma_home).expanduser()
    worker = build_external_worker_registration(
        dharma_home=dharma_home,
        repo_root=Path(args.repo_root),
    )
    return await register_external_worker(
        worker,
        dharma_home=dharma_home,
        write_canonical_onboarding=not args.no_onboarding,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dharma-home", default=str(dharma_state_dir()))
    parser.add_argument(
        "--write",
        action="store_true",
        help="write registration, living dock, A2A card, telemetry, and onboarding receipt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the worker registration packet without writing; default behavior",
    )
    parser.add_argument(
        "--no-onboarding",
        action="store_true",
        help="write only external_agents registration.json, not canonical onboarding surfaces",
    )
    args = parser.parse_args(argv)

    dharma_home = Path(args.dharma_home).expanduser()
    worker = build_external_worker_registration(
        dharma_home=dharma_home,
        repo_root=Path(args.repo_root),
    )

    if not args.write:
        payload = worker.model_dump()
        payload["dry_run"] = True
        payload["would_write"] = {
            "external_registration": str(
                dharma_home / "external_agents" / worker.agent_uid / "registration.json"
            ),
            "living_agent": str(
                dharma_home / "agents" / worker.agent_uid / "living_agent.json"
            ),
            "a2a_card": str(dharma_home / "a2a" / "cards" / f"{worker.callsign}.json"),
            "last_onboarding_receipt": str(
                dharma_home / "agents" / worker.agent_uid / "last_receipt.json"
            ),
        }
        print(_json(payload), end="")
        return 0

    result = asyncio.run(_write_registration(args))
    print(_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
