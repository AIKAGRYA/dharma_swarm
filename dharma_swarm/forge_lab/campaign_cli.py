"""Argument and result adapter for governed campaign commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

from dharma_swarm.forge_lab.version import CLI_RESULT_SCHEMA


LeafFactory = Callable[..., argparse.ArgumentParser]
JsonFlag = Callable[[argparse.ArgumentParser], None]
CAMPAIGN_FAILURE_EXIT = 7
RECONCILIATION_DRIFT_EXIT = 4


def add_campaign_commands(
    commands: Any,
    *,
    leaf: LeafFactory,
    json_flag: JsonFlag,
) -> None:
    """Register campaign and reconciliation commands on the root parser."""

    campaign = commands.add_parser("campaign", help="manage governed RSI campaigns")
    subcommands = campaign.add_subparsers(dest="campaign_command", required=True)

    plan = leaf(
        subcommands,
        "plan",
        command_path="campaign plan",
        help_text="materialize a campaign manifest",
    )
    plan.add_argument(
        "--profile",
        required=True,
        choices=("explore-open", "forge-lab-n30-to-1000-v1"),
    )
    json_flag(plan)

    run = leaf(
        subcommands,
        "run",
        command_path="campaign run",
        help_text="run a stored campaign manifest",
    )
    run.add_argument("--manifest", required=True)
    run.add_argument("--request-id")
    run.add_argument("--operator-envelope")
    run.add_argument("--identity-receipt")
    run.add_argument("--provider-receipt")
    run.add_argument(
        "--host",
        default="meghadharma",
        choices=("meghadharma",),
        help="authoritative campaign host (v1 is pinned to Meghadharma)",
    )
    json_flag(run)

    listing = leaf(
        subcommands,
        "list",
        command_path="campaign list",
        help_text="list campaigns",
    )
    listing.add_argument("--state")
    json_flag(listing)

    status = leaf(
        subcommands,
        "status",
        command_path="campaign status",
        help_text="show campaign state",
    )
    status.add_argument("campaign", nargs="?")
    json_flag(status)

    progress = leaf(
        subcommands,
        "progress",
        command_path="campaign progress",
        help_text="show durable campaign progress",
    )
    progress.add_argument("campaign", nargs="?")
    json_flag(progress)

    events = leaf(
        subcommands,
        "events",
        command_path="campaign events",
        help_text="read the authoritative campaign event sequence",
    )
    events.add_argument("campaign")
    events.add_argument("--after", type=int)
    events.add_argument("--follow", action="store_true")
    json_flag(events)

    for name in ("pause", "resume", "stop"):
        lifecycle = leaf(
            subcommands,
            name,
            command_path=f"campaign {name}",
            help_text=f"{name} a campaign",
        )
        lifecycle.add_argument("campaign")
        lifecycle.add_argument("--request-id")
        json_flag(lifecycle)

    fork = leaf(
        subcommands,
        "fork",
        command_path="campaign fork",
        help_text="create a provenance-linked campaign fork",
    )
    fork.add_argument("campaign")
    fork.add_argument("--runner")
    json_flag(fork)

    fuse_ack = leaf(
        subcommands,
        "fuse-ack",
        command_path="campaign fuse-ack",
        help_text="acknowledge a campaign fuse trip",
    )
    fuse_ack.add_argument("campaign")
    fuse_ack.add_argument("--trip", required=True)
    fuse_ack.add_argument("--reason", required=True)
    fuse_ack.add_argument("--rearm", action="store_true")
    json_flag(fuse_ack)

    reconcile = leaf(
        commands,
        "reconcile",
        command_path="reconcile",
        help_text="report control-plane drift",
    )
    reconcile.add_argument("--apply", action="store_true")
    reconcile.add_argument("--report")
    reconcile.add_argument("--request-id")
    json_flag(reconcile)


def _emit(
    command: str,
    result: Any,
    *,
    as_json: bool,
    ok: bool = True,
    error_code: str | None = None,
) -> None:
    if as_json:
        payload: dict[str, Any] = {
            "schema": CLI_RESULT_SCHEMA,
            "ok": ok,
            "command": command,
            "result": result,
        }
        if error_code:
            payload["error"] = {
                "code": error_code,
                "message": f"rsi {command} failed [{error_code}]",
            }
        print(json.dumps(payload, sort_keys=True))
        return
    if isinstance(result, dict):
        for key in (
            "campaign_name",
            "campaign",
            "manifest_digest",
            "state",
            "disposition",
            "receipt_path",
            "report_digest",
        ):
            if key in result:
                print(f"{key}: {result[key]}")
    elif isinstance(result, list):
        for item in result:
            campaign = item.get("campaign") if isinstance(item, dict) else None
            state = item.get("state") if isinstance(item, dict) else None
            print(f"{campaign or item}: {state or ''}".rstrip())


def _failure(command: str, exc: Exception, *, as_json: bool) -> int:
    code = getattr(exc, "code", "CAMPAIGN_CONTROL_FAILURE")
    result = getattr(exc, "result", None)
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": False,
                    "command": command,
                    "error": {"code": code, "message": str(exc)},
                    "result": result,
                },
                sort_keys=True,
            )
        )
    print(f"rsi {command} failed [{code}]: {exc}", file=sys.stderr)
    return CAMPAIGN_FAILURE_EXIT


def dispatch(args: argparse.Namespace) -> int:
    """Dispatch only governed, non-legacy campaign operations."""

    from dharma_swarm.forge_lab import campaign_control as control
    from dharma_swarm.forge_lab.campaign_actions import lifecycle_action
    from dharma_swarm.forge_lab.campaign_contract import resolve_state_root
    from dharma_swarm.forge_lab.campaign_reconcile import (
        ReconciliationError,
        reconcile_state,
    )

    command = args._command_path
    try:
        if command == "campaign plan":
            result = control.plan_campaign(args.profile)
        elif command == "campaign run":
            result = control.run_campaign(
                args.manifest,
                request_id=args.request_id,
                expected_host=args.host,
                envelope_path=args.operator_envelope,
                identity_receipt_path=args.identity_receipt,
                provider_receipt_path=args.provider_receipt,
            )
            _emit(
                command,
                result,
                as_json=args.json,
                ok=False,
                error_code="CAMPAIGN_BLOCKED",
            )
            print(
                f"rsi {command} blocked; receipt: {result['receipt_path']}",
                file=sys.stderr,
            )
            return CAMPAIGN_FAILURE_EXIT
        elif command == "campaign list":
            result = control.list_campaigns(state=args.state)
            if not result:
                raise control.CampaignControlError(
                    "NO_CAMPAIGNS", "no campaigns matched"
                )
        elif command == "campaign status":
            result = control.campaign_status(args.campaign)
        elif command == "campaign progress":
            result = control.campaign_progress(args.campaign)
        elif command == "campaign events":
            if args.follow:
                raise control.CampaignControlError(
                    "FOLLOW_NOT_IMPLEMENTED",
                    "minimum controller supports committed event snapshots only",
                )
            result = control.campaign_events(args.campaign, after=args.after or 0)
        elif command in {
            "campaign pause",
            "campaign resume",
            "campaign stop",
        }:
            result = lifecycle_action(
                command.rsplit(" ", 1)[1],
                args.campaign,
                request_id=args.request_id,
            )
        elif command == "reconcile":
            state = resolve_state_root()
            report = None
            digest = None
            if args.report:
                report = json.loads(Path(args.report).read_text(encoding="utf-8"))
                digest = report.get("report_digest")
            result = reconcile_state(
                state,
                apply=args.apply,
                report=report,
                report_digest=digest,
                request_id=args.request_id,
            )
            _emit(command, result, as_json=args.json)
            return (
                RECONCILIATION_DRIFT_EXIT
                if not args.apply and result["summary"]["status"] != "clean"
                else 0
            )
        else:
            raise control.CampaignControlError(
                "NOT_IMPLEMENTED",
                f"rsi {command} is registered but not implemented "
                "in the minimum safe lifecycle",
            )
    except (OSError, json.JSONDecodeError, ReconciliationError) as exc:
        return _failure(command, exc, as_json=args.json)
    except Exception as exc:
        return _failure(command, exc, as_json=args.json)
    _emit(command, result, as_json=args.json)
    return 0
