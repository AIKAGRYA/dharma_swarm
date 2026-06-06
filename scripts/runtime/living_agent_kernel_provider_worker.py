#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dharma_swarm.operator_core.living_agent_kernel_provider_worker import execute_provider_worker_cycle


def main() -> int:
    parser = argparse.ArgumentParser(description="Run promoted provider-backed LivingAgentKernel worker cycles.")
    parser.add_argument("--store-dir", type=Path, default=None)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--agent-uid", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--allowed-source", action="append", default=[])
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--heartbeat-max-age-seconds", type=int, default=120)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--now", default=None)
    parser.add_argument("--fixture-response", default=None)
    parser.add_argument("--live-provider", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.2)
    args = parser.parse_args()

    results = asyncio.run(_run_cycles(args))
    print(json.dumps({"cycles": results}, sort_keys=True))
    return 0


async def _run_cycles(args: argparse.Namespace) -> list[dict]:
    results: list[dict] = []
    for _ in range(max(1, int(args.cycles))):
        result = await execute_provider_worker_cycle(
            store_dir=args.store_dir,
            workspace_root=args.workspace_root,
            worker_id=args.worker_id,
            agent_uid=args.agent_uid,
            provider=args.provider,
            model=args.model,
            allowed_sources=args.allowed_source,
            lease_seconds=args.lease_seconds,
            heartbeat_max_age_seconds=args.heartbeat_max_age_seconds,
            now=args.now,
            fixture_response=args.fixture_response,
            live_provider=args.live_provider,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        results.append(result.model_dump(mode="json"))
    return results


if __name__ == "__main__":
    raise SystemExit(main())
