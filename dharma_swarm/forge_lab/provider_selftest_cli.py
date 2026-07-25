"""CLI adapter for configuration-only provider self-tests."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from dharma_swarm.forge_lab.version import CLI_RESULT_SCHEMA


PROVIDER_FAILURE_EXIT = 6
GOVERNED_AUTHORITY_REQUIRED_EXIT = 7


def _emit(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": bool(result.get("ok")),
                    "command": "provider selftest",
                    "result": result,
                },
                sort_keys=True,
            )
        )
        return
    print(f"provider selftest: {'PASS' if result.get('ok') else 'FAIL'}")
    print(f"profile: {result.get('profile')} live={result.get('live')}")
    print(
        "independent routes: "
        f"{result.get('independent_route_count')}/"
        f"{result.get('require_independent_routes')}"
    )
    if result.get("receipt"):
        print(f"receipt: {result['receipt']}")
    for failure in result.get("failures", []):
        print(f"failure: {failure}")
    for row in result.get("rows", []):
        model = row.get("requested_model") or row.get("model_id")
        provider = row.get("provider") or "unresolved"
        stage = row.get("stage") or "unknown"
        error = row.get("error_type") or ""
        print(
            f"row: model={model} provider={provider} "
            f"callable={bool(row.get('callable'))} stage={stage} {error}".rstrip()
        )


def dispatch(args: argparse.Namespace) -> int:
    """Deny live probes before importing any provider-facing module."""

    command = args._command_path
    if args.live:
        code = "GOVERNED_PROBE_AUTHORITY_REQUIRED"
        message = (
            "live provider probes require a manifest-bound signed authority, "
            "fenced reservation, and governed broker; none is implemented"
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "schema": CLI_RESULT_SCHEMA,
                        "ok": False,
                        "command": command,
                        "error": {"code": code, "message": message},
                    },
                    sort_keys=True,
                )
            )
        print(f"rsi {command} failed [{code}]: {message}", file=sys.stderr)
        return GOVERNED_AUTHORITY_REQUIRED_EXIT
    try:
        from dharma_swarm.forge_lab.provider_selftest import run_provider_selftest

        result = run_provider_selftest(
            profile=args.profile,
            live=False,
            require_independent_routes=args.require_independent_routes,
            current_model=args.model,
            timeout_s=args.timeout_s,
        )
    except ValueError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "schema": CLI_RESULT_SCHEMA,
                        "ok": False,
                        "command": command,
                        "error": {
                            "code": "INVALID_PROFILE",
                            "message": str(exc),
                        },
                    },
                    sort_keys=True,
                )
            )
        print(f"rsi {command} failed [INVALID_PROFILE]: {exc}", file=sys.stderr)
        return PROVIDER_FAILURE_EXIT
    _emit(result, as_json=args.json)
    return 0 if result.get("ok") else PROVIDER_FAILURE_EXIT
