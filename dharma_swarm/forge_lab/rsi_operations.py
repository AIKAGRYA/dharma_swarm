"""Implemented RSI CLI operations kept separate from parser registration."""

from __future__ import annotations

import argparse
import getpass
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
from dharma_swarm.forge_lab.credential_handoff import CredentialHandoffError
from dharma_swarm.forge_lab.model_onboarding import ModelOnboardingError
from dharma_swarm.forge_lab.operator_views import (
    doctor,
    inspect_archive,
    list_alerts,
    list_workers,
)
from dharma_swarm.forge_lab.reconciliation import ReconciliationError
from dharma_swarm.forge_lab.reconciliation_view import (
    composite_reconciliation_status,
)
from dharma_swarm.forge_lab.taskpack_ops import TaskpackError
from dharma_swarm.forge_lab.version import CLI_RESULT_SCHEMA

OPERATION_FAILURE_EXIT = 8


def _emit(command: str, result: dict[str, Any], *, as_json: bool, ok: bool) -> None:
    # Every producer routed through _emit returns value-free receipts/status
    # dicts (credential_handoff records secret_value_recorded: False; provider
    # rows carry env-var NAMES, never values). No secret reaches this sink.
    if as_json:
        print(
            json.dumps(  # codeql[py/clear-text-logging-sensitive-data]
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
    print(json.dumps(result, indent=2, sort_keys=True))  # codeql[py/clear-text-logging-sensitive-data]


def _error(
    command: str,
    code: str,
    message: str,
    *,
    as_json: bool,
    details: dict[str, Any] | None = None,
) -> int:
    if as_json:
        error: dict[str, Any] = {"code": code, "message": message}
        if details:
            error["details"] = details
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": False,
                    "command": command,
                    "error": error,
                },
                sort_keys=True,
            )
        )
    print(f"rsi {command} failed [{code}]: {message}", file=sys.stderr)
    if details and details.get("receipt_path"):
        print(f"evidence: {details['receipt_path']}", file=sys.stderr)
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


def _role_bindings(args: argparse.Namespace) -> list[dict[str, str]]:
    return [
        {
            "role": role,
            "provider": str(getattr(args, f"{role}_provider")),
            "model_id": str(getattr(args, f"{role}_model")),
        }
        for role in ("mutator", "solver", "verifier")
    ]


def _provider(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    command = args._command_path
    if command.startswith("provider models "):
        from dharma_swarm.forge_lab.model_onboarding import (
            activation_status,
            apply_activation,
            list_supported_routes,
            plan_activation,
            rollback_activation,
        )

        if command == "provider models list":
            return list_supported_routes(), True
        if command == "provider models status":
            result = activation_status()
            return result, bool(result.get("active"))
        if command == "provider models plan":
            result = plan_activation(
                _role_bindings(args),
                expected_current_digest=args.expected_current_digest,
            )
            return result, result.get("outcome") == "ready"
        if command == "provider models apply":
            plan = plan_activation(
                _role_bindings(args),
                expected_current_digest=args.expected_current_digest,
            )
            if plan["plan_digest"] != args.plan_digest:
                raise ModelOnboardingError(
                    "PLAN_DIGEST_MISMATCH",
                    "current canonical plan does not match --plan-digest",
                )
            return (
                apply_activation(
                    plan,
                    request_id=args.request_id,
                    expected_current_digest=args.expected_current_digest,
                ),
                True,
            )
        if command == "provider models rollback":
            return (
                rollback_activation(
                    request_id=args.request_id,
                    expected_current_digest=args.expected_current_digest,
                    target_profile_digest=args.target_profile_digest,
                ),
                True,
            )

    if command.startswith("provider credential "):
        from dharma_swarm.forge_lab.credential_handoff import (
            apply_credential,
            credential_status,
            plan_credential,
        )

        if command == "provider credential status":
            result = credential_status(args.provider)
            return result, bool(result.get("ok"))
        if command == "provider credential plan":
            return plan_credential(args.provider), True
        if command == "provider credential apply":
            plan = plan_credential(args.provider)
            if plan["plan_digest"] != args.plan_digest:
                raise CredentialHandoffError(
                    "PLAN_DIGEST_MISMATCH",
                    "current credential plan does not match --plan-digest",
                )
            if args.stdin:
                secret = sys.stdin.readline().rstrip("\r\n")
            else:
                secret = getpass.getpass(
                    f"{plan['credential_env']} for {plan['provider']} (input hidden): "
                )
            if not secret:
                raise CredentialHandoffError("SECRET_INPUT_EMPTY", "no credential was supplied")
            try:
                return (
                    apply_credential(
                        args.provider,
                        plan_digest=args.plan_digest,
                        request_id=args.request_id,
                        secret=secret,
                    ),
                    True,
                )
            finally:
                secret = ""
    raise ValueError(f"unknown provider operation: {command}")


def _taskpack(args: argparse.Namespace) -> tuple[dict[str, Any], bool] | None:
    from dharma_swarm.forge_lab.taskpack_ops import (
        apply_taskpack,
        plan_taskpack,
        taskpack_status,
    )

    command = args._command_path
    if command == "taskpack build":
        return None
    if command == "taskpack status":
        result = taskpack_status()
        return result, bool(result.get("ready"))
    plan = plan_taskpack(
        args.manifest,
        manifest_digest=args.manifest_digest,
        model_cutoff=args.model_cutoff,
        mode=args.mode,
    )
    if command == "taskpack plan":
        return plan, True
    if command == "taskpack apply":
        if plan["plan_digest"] != args.plan_digest:
            raise TaskpackError(
                "PLAN_DIGEST_MISMATCH",
                "current canonical plan does not match --plan-digest",
            )
        return (
            apply_taskpack(
                plan,
                plan_digest=args.plan_digest,
                request_id=args.request_id,
                timeout_seconds=args.timeout_seconds,
            ),
            True,
        )
    raise ValueError(f"unknown taskpack operation: {command}")


def dispatch(args: argparse.Namespace) -> int | None:
    """Run one implemented non-sync operation, or return ``None``."""

    command = args._command_path
    try:
        if command == "doctor":
            result = doctor()
            ok = bool(result.get("ok"))
        elif command.startswith("campaign "):
            result, ok = _campaign(args)
        elif command.startswith("provider "):
            result, ok = _provider(args)
        elif command.startswith("taskpack "):
            taskpack_result = _taskpack(args)
            if taskpack_result is None:
                return None
            result, ok = taskpack_result
        elif command == "reconcile":
            if args.plan:
                if args.plan_digest or args.request_id:
                    raise ReconciliationError(
                        "INVALID_MODE_ARGUMENTS",
                        "--plan does not accept --plan-digest or --request-id",
                    )
                from dharma_swarm.forge_lab.reconciliation import plan_reconciliation

                result = plan_reconciliation(campaign_id=args.campaign)
                ok = True
            elif args.apply:
                from dharma_swarm.forge_lab.reconciliation import apply_reconciliation

                if not args.plan_digest or not args.request_id:
                    raise ReconciliationError(
                        "APPLY_ARGUMENTS_REQUIRED",
                        "--apply requires --plan-digest and --request-id",
                    )
                result = apply_reconciliation(
                    plan_digest=args.plan_digest,
                    request_id=args.request_id,
                    campaign_id=args.campaign,
                )
                ok = True
            else:
                if args.plan_digest or args.request_id or args.campaign:
                    raise ReconciliationError(
                        "INVALID_MODE_ARGUMENTS",
                        "--plan-digest, --request-id, and --campaign require --plan or --apply",
                    )
                result = composite_reconciliation_status()
                ok = bool(result.get("ok"))
        elif command == "daily status":
            from dharma_swarm.forge_lab.daily_status import daily_status

            result = daily_status()
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
    except TaskpackError as exc:
        details = (
            {"receipt_path": str(exc.receipt_path)}
            if exc.receipt_path is not None
            else None
        )
        return _error(
            command,
            exc.code,
            str(exc),
            as_json=args.json,
            details=details,
        )
    except (
        CredentialHandoffError,
        ModelOnboardingError,
        ReconciliationError,
    ) as exc:
        return _error(command, exc.code, str(exc), as_json=args.json)
    except ValueError as exc:
        return _error(command, "INVALID_ARGUMENT", str(exc), as_json=args.json)

    _emit(command, result, as_json=args.json, ok=ok)
    return 0 if ok else OPERATION_FAILURE_EXIT


__all__ = ["OPERATION_FAILURE_EXIT", "dispatch"]
