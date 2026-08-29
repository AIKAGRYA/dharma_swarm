"""Implemented RSI CLI operations kept separate from parser registration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
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
        elif command == "taskpack build":
            from dharma_swarm.forge_lab.taskpack import build_taskpack

            result = build_taskpack(
                profile=args.profile,
                source_manifest=Path(args.source_manifest) if args.source_manifest else None,
                instance_ids=args.instances,
                root=Path(args.taskpack_root) if args.taskpack_root else None,
            )
            ok = True
        elif command == "taskpack import":
            from dharma_swarm.forge_lab.taskpack import import_taskpack

            result = import_taskpack(
                args.taskpack,
                request_id=args.request_id,
                apply=args.apply,
                db_path=Path(args.taskbed_db) if args.taskbed_db else None,
                root=Path(args.taskpack_root) if args.taskpack_root else None,
            )
            ok = bool(result.get("ok"))
        elif command == "safety status":
            from dharma_swarm.forge_lab.safety_control import halt_status
            from dharma_swarm.forge_lab.state_io import forge_state_root

            result, ok = halt_status(forge_state_root()), True
        elif command == "safety halt":
            from dharma_swarm.forge_lab.safety_control import latch_halt
            from dharma_swarm.forge_lab.state_io import forge_state_root, now_utc

            result = latch_halt(
                forge_state_root(),
                at=now_utc(),
                code=args.code,
                reason=args.reason,
                source="operator_cli",
                operator_id=args.operator_id,
                request_id=args.request_id,
            )
            ok = True
        elif command == "safety resume":
            from dharma_swarm.forge_lab.safety_control import resume_halt
            from dharma_swarm.forge_lab.state_io import forge_state_root, now_utc

            result = resume_halt(
                forge_state_root(),
                at=now_utc(),
                operator_id=args.operator_id,
                request_id=args.request_id,
                reason=args.reason,
                expected_halt_digest=args.expected_halt_digest,
                signature_path=Path(args.signature),
            )
            ok = True
        elif command.startswith("campaign "):
            result, ok = _campaign(args)
        elif command == "reconcile":
            if args.apply:
                if not args.request_id:
                    return _error(
                        command,
                        "REQUEST_ID_REQUIRED",
                        "--request-id is required for receipted reconciliation",
                        as_json=args.json,
                    )
                from dharma_swarm.forge_lab.unattended_reconcile import reconcile_abandoned_runs

                result = reconcile_abandoned_runs(request_id=args.request_id)
                ok = True
            else:
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
    except Exception as exc:
        from dharma_swarm.forge_lab.taskpack import TaskpackError
        from dharma_swarm.forge_lab.unattended_receipts import UnattendedError

        if isinstance(exc, (TaskpackError, UnattendedError)):
            return _error(command, exc.code, str(exc), as_json=args.json)
        raise

    _emit(command, result, as_json=args.json, ok=ok)
    return 0 if ok else OPERATION_FAILURE_EXIT


__all__ = ["OPERATION_FAILURE_EXIT", "dispatch"]
