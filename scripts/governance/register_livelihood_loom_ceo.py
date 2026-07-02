#!/usr/bin/env python3
"""Register livelihood_loom_ceo through the Stage-1 external-worker desk."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (  # noqa: E402
    build_external_worker_registration,
    register_livelihood_loom_ceo_sync,
)


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--dharma-home", default=str(Path.home() / ".dharma"))
    parser.add_argument("--agents-dir", default="")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write registration, living dock, A2A card, telemetry, and AgentRegistry identity",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the worker registration packet without writing; default behavior",
    )
    parser.add_argument(
        "--no-onboarding",
        action="store_true",
        help="write only external_agents registration.json plus AgentRegistry identity",
    )
    args = parser.parse_args(argv)

    home = Path(args.dharma_home).expanduser()
    repo = Path(args.repo_root).expanduser()
    agents_dir = Path(args.agents_dir).expanduser() if args.agents_dir else None
    worker = build_external_worker_registration(dharma_home=home, repo_root=repo)

    if not args.write:
        payload = worker.model_dump()
        payload["dry_run"] = True
        payload["would_write"] = {
            "external_registration": str(home / "external_agents" / worker.agent_uid / "registration.json"),
            "living_agent": str(home / "agents" / worker.agent_uid / "living_agent.json"),
            "a2a_card": str(home / "a2a" / "cards" / f"{worker.callsign}.json"),
            "last_onboarding_receipt": str(home / "agents" / worker.agent_uid / "last_receipt.json"),
            "agent_registry_identity": str((agents_dir or home / "ginko" / "agents") / worker.agent_uid / "identity.json"),
        }
        print(_json(payload), end="")
        return 0

    result = register_livelihood_loom_ceo_sync(
        dharma_home=home,
        repo_root=repo,
        agents_dir=agents_dir,
        write_canonical_onboarding=not args.no_onboarding,
    )
    print(_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
