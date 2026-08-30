#!/usr/bin/env python3
"""Run the fixed read-only SSH preflight for one remote holon."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dharma_swarm.holon_system.transport.ssh_preflight import (  # noqa: E402
    RemoteHolonPreflightError,
    invalid_input_result,
    run_remote_holon_preflight,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ssh_alias", help="Configured SSH alias; IPs and user@host are rejected.")
    parser.add_argument("holon_name", help="Canonical holon identity name to check.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="SSH connect timeout in seconds (1-15; default: 5).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_remote_holon_preflight(
            args.ssh_alias,
            args.holon_name,
            connect_timeout=args.timeout,
        )
    except RemoteHolonPreflightError as exc:
        result = invalid_input_result(exc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
