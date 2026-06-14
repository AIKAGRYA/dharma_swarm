#!/usr/bin/env python3
"""Read-only preflight gate for repo-native ds-goal longruns."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.ds_goal_wrapper_contract import (
    wrapper_longrun_preflight_gate,
)


DEFAULT_WRAPPER = Path.home() / ".dharma" / "bin" / "ds-goal"


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _print(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, default=_json_default, sort_keys=True))
        return
    print("DS-GOAL LONGRUN PREFLIGHT")
    print(f"status: {payload['status']}")
    print(f"passed: {payload['passed']}")
    print(f"reason: {payload['reason']}")
    print(f"default_target: {payload['default_target_repo']}")
    print(f"audited_checkout: {payload['audited_checkout']}")
    if payload.get("repo_pin"):
        print(f"repo_pin: {payload['repo_pin']} ({payload['repo_pin_source']})")
    if payload.get("safe_current_checkout_invocation"):
        print(f"safe_invocation: {payload['safe_current_checkout_invocation']}")
    if payload.get("operator_convergence_required"):
        print("operator_convergence_required: true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail before starting a ds-goal longrun when the installed wrapper is unpinned and split-brain.",
    )
    parser.add_argument("--wrapper", type=Path, default=DEFAULT_WRAPPER)
    parser.add_argument("--audited-repo", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--repo-pin",
        type=Path,
        default=None,
        help="Explicit repo pin to evaluate. Defaults to DHARMA_SWARM_REPO when set.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def _repo_pin_from_args(args: argparse.Namespace) -> tuple[Path | None, str]:
    if args.repo_pin is not None:
        return args.repo_pin.expanduser(), "argument"
    env_pin = str(os.environ.get("DHARMA_SWARM_REPO") or "").strip()
    if env_pin:
        return Path(env_pin).expanduser(), "DHARMA_SWARM_REPO"
    return None, "none"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_pin, repo_pin_source = _repo_pin_from_args(args)
    payload = wrapper_longrun_preflight_gate(
        home=Path.home(),
        audited_repo=args.audited_repo.expanduser(),
        wrapper=args.wrapper.expanduser(),
        repo_pin=repo_pin,
        repo_pin_source=repo_pin_source,
    )
    _print(payload, as_json=args.json)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
