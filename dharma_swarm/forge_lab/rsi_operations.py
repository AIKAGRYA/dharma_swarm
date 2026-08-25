"""Implemented RSI CLI operations kept separate from parser registration."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from dharma_swarm.forge_lab.campaign_control import (
    CampaignError,
    campaign_events,
    campaign_progress,
    campaign_status,
    list_campaigns,
    plan_campaign,
    run_campaign,
)
from dharma_swarm.forge_lab.operator_views import (
    doctor,
    inspect_archive,
    list_alerts,
    list_workers,
    reconcile,
)
from dharma_swarm.forge_lab.version import CLI_RESULT_SCHEMA

OPERATION_FAILURE_EXIT = 8


def _emit(command: str, result: dict[str, Any], *, as_json: bool, ok: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": ok,
                    "command": command,
                    "result": result,
                },
                sort_keys=True,
            )
        )
        return
    print(f"rsi {command}: {'READY' if ok else 'NOT READY'}")
    print(json.dumps(result, indent=2, sort_keys=True))


def _error(command: str, code: str, message: str, *, as_json: bool) -> int:
    if as_json:
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
    return OPERATION_FAILURE_EXIT


def _campaign(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    command = args._command_path
    if command == "campaign plan":
        return plan_campaign(args.profile), True
    if command == "campaign run":
        return run_campaign(args.manifest, args.request_id), True
    if command == "campaign list":
        return list_campaigns(args.state), True
    if command == "campaign status":
        return campaign_status(args.campaign), True
    if command == "campaign progress":
        return campaign_progress(args.campaign), True
    if command == "campaign events":
        if args.follow:
            raise CampaignError(
                "FOLLOW_NOT_IMPLEMENTED",
                "follow mode requires the persistent supervisor; use the finite read surface",
            )
        return campaign_events(args.campaign, args.after), True
    raise CampaignError(
        "MUTATION_NOT_IMPLEMENTED",
        f"{command} is not implemented; it remains fail-closed until the "
        "fenced live campaign controller exists",
    )


def dispatch(args: argparse.Namespace) -> int | None:
    """Run one implemented non-sync operation, or return ``None``."""

    command = args._command_path
    try:
        if command == "doctor":
            result = doctor()
            ok = bool(result.get("ok"))
        elif command.startswith("campaign "):
            result, ok = _campaign(args)
        elif command == "reconcile":
            if args.apply:
                return _error(
                    command,
                    "APPLY_NOT_IMPLEMENTED",
                    "reconciliation is read-only until fenced repair actions exist",
                    as_json=args.json,
                )
            result = reconcile()
            ok = bool(result.get("ok"))
        elif command == "worker list":
            result, ok = list_workers(), True
        elif command == "alerts list":
            result, ok = list_alerts(), True
        elif command == "archive inspect":
            result, ok = inspect_archive(args.candidate), True
        else:
            return None
    except CampaignError as exc:
        return _error(command, exc.code, str(exc), as_json=args.json)
    except ValueError as exc:
        return _error(command, "INVALID_ARGUMENT", str(exc), as_json=args.json)

    _emit(command, result, as_json=args.json, ok=ok)
    return 0 if ok else OPERATION_FAILURE_EXIT


__all__ = ["OPERATION_FAILURE_EXIT", "dispatch"]
