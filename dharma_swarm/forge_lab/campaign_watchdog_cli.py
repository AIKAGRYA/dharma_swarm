"""Credential-free process launcher and CLI for the campaign watchdog."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from dharma_swarm.forge_lab.campaign_watchdog import (
    EXIT_INVALID,
    WatchdogConfig,
    WatchdogError,
    run_watchdog,
)


def _config_values(config: WatchdogConfig) -> dict[str, Any]:
    return {
        "state-root": config.state_root,
        "campaign-id": config.campaign_id,
        "manifest-digest": config.manifest_digest,
        "fence": config.fence,
        "deadline": config.deadline,
        "heartbeat-timeout-s": config.heartbeat_timeout_s,
        "poll-interval-s": config.poll_interval_s,
    }


def spawn_watchdog_process(config: WatchdogConfig) -> subprocess.Popen[bytes]:
    """Start a detached worker without inheriting provider credentials."""

    package_root = str(Path(__file__).resolve().parents[2])
    pythonpath = os.pathsep.join(
        item for item in (package_root, os.environ.get("PYTHONPATH", "")) if item
    )
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": pythonpath,
        "PYTHONNOUSERSITE": "1",
    }
    command = [
        sys.executable,
        "-m",
        "dharma_swarm.forge_lab.campaign_watchdog",
    ]
    for name, value in _config_values(config).items():
        command.extend((f"--{name}", str(value)))
    return subprocess.Popen(
        command,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge Lab external closure-only watchdog")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--manifest-digest", required=True)
    parser.add_argument("--fence", type=int, required=True)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--heartbeat-timeout-s", type=float, required=True)
    parser.add_argument("--poll-interval-s", type=float, default=0.25)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        fields = WatchdogConfig.__dataclass_fields__
        config = WatchdogConfig(**{field: getattr(args, field) for field in fields})
        code, decision = run_watchdog(config, once=args.once)
    except WatchdogError as exc:
        code = EXIT_INVALID
        decision = {
            "schema": "forge_lab.watchdog_decision.v1",
            "status": "invalid",
            "reason": exc.code,
            "message": str(exc),
        }
    print(json.dumps(decision, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
