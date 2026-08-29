"""Parser registration for the non-sync RSI operator command groups."""

from __future__ import annotations

from typing import Any, Callable

ParserFactory = Callable[..., Any]
JsonFlag = Callable[[Any], None]


def add_operator_commands(
    commands: Any,
    *,
    leaf: ParserFactory,
    json_flag: JsonFlag,
) -> None:
    def role_arguments(parser: Any) -> None:
        for role in ("mutator", "solver", "verifier"):
            parser.add_argument(f"--{role}-provider", required=True)
            parser.add_argument(f"--{role}-model", required=True)

    provider = commands.add_parser("provider", help="inspect provider routes")
    provider_commands = provider.add_subparsers(dest="provider_command", required=True)
    provider_selftest = leaf(
        provider_commands,
        "selftest",
        command_path="provider selftest",
        help_text="test provider readiness",
    )
    provider_selftest.add_argument("--profile", required=True)
    provider_selftest.add_argument("--live", action="store_true")
    provider_selftest.add_argument("--require-independent-routes", type=int)
    provider_selftest.add_argument(
        "--model", help="current model id to include for current/newrun profiles"
    )
    provider_selftest.add_argument(
        "--timeout-s", type=int, default=20, help="per-route live probe timeout"
    )
    provider_selftest.add_argument(
        "--max-probes", type=int, default=4, help="hard cap on live route probes"
    )
    provider_selftest.add_argument(
        "--min-refresh-interval-s",
        type=int,
        default=0,
        help="reuse a compatible receipt within this interval instead of spending again",
    )
    json_flag(provider_selftest)

    provider_models = provider_commands.add_parser(
        "models", help="plan and activate exact model-role routes"
    )
    provider_model_commands = provider_models.add_subparsers(
        dest="provider_model_command", required=True
    )
    provider_models_list = leaf(
        provider_model_commands,
        "list",
        command_path="provider models list",
        help_text="list source-supported exact routes without loading keys",
    )
    json_flag(provider_models_list)
    provider_models_status = leaf(
        provider_model_commands,
        "status",
        command_path="provider models status",
        help_text="show the active role profile",
    )
    json_flag(provider_models_status)
    provider_models_plan = leaf(
        provider_model_commands,
        "plan",
        command_path="provider models plan",
        help_text="dry-run an exact mutator/solver/verifier profile",
    )
    role_arguments(provider_models_plan)
    provider_models_plan.add_argument("--expected-current-digest")
    json_flag(provider_models_plan)
    provider_models_apply = leaf(
        provider_model_commands,
        "apply",
        command_path="provider models apply",
        help_text="activate a digest-bound role profile",
    )
    role_arguments(provider_models_apply)
    provider_models_apply.add_argument("--plan-digest", required=True)
    provider_models_apply.add_argument("--request-id", required=True)
    provider_models_apply.add_argument("--expected-current-digest")
    json_flag(provider_models_apply)
    provider_models_rollback = leaf(
        provider_model_commands,
        "rollback",
        command_path="provider models rollback",
        help_text="reactivate an ancestor profile as a new generation",
    )
    provider_models_rollback.add_argument("--request-id", required=True)
    provider_models_rollback.add_argument("--expected-current-digest", required=True)
    provider_models_rollback.add_argument("--target-profile-digest")
    json_flag(provider_models_rollback)

    provider_credential = provider_commands.add_parser(
        "credential", help="hand a provider key to the existing host-only store"
    )
    credential_commands = provider_credential.add_subparsers(
        dest="provider_credential_command", required=True
    )
    credential_status = leaf(
        credential_commands,
        "status",
        command_path="provider credential status",
        help_text="show credential names and presence only",
    )
    credential_status.add_argument("--provider")
    json_flag(credential_status)
    credential_plan = leaf(
        credential_commands,
        "plan",
        command_path="provider credential plan",
        help_text="plan a hidden-input credential handoff",
    )
    credential_plan.add_argument("--provider", required=True)
    json_flag(credential_plan)
    credential_apply = leaf(
        credential_commands,
        "apply",
        command_path="provider credential apply",
        help_text="apply a key from a hidden prompt or stdin, never argv",
    )
    credential_apply.add_argument("--provider", required=True)
    credential_apply.add_argument("--plan-digest", required=True)
    credential_apply.add_argument("--request-id", required=True)
    credential_apply.add_argument(
        "--stdin",
        action="store_true",
        help="read exactly one credential line from stdin instead of prompting",
    )
    json_flag(credential_apply)

    taskpack = commands.add_parser("taskpack", help="manage evaluation taskpacks")
    taskpack_commands = taskpack.add_subparsers(dest="taskpack_command", required=True)
    taskpack_build = leaf(
        taskpack_commands,
        "build",
        command_path="taskpack build",
        help_text="build a content-addressed taskpack",
    )
    taskpack_build.add_argument("--profile", required=True)
    json_flag(taskpack_build)
    taskpack_status = leaf(
        taskpack_commands,
        "status",
        command_path="taskpack status",
        help_text="inspect the anchored taskbed without mutation",
    )
    json_flag(taskpack_status)
    for name in ("plan", "apply"):
        taskpack_action = leaf(
            taskpack_commands,
            name,
            command_path=f"taskpack {name}",
            help_text=f"{name} a content-addressed governed taskpack",
        )
        taskpack_action.add_argument("--manifest", required=True)
        taskpack_action.add_argument("--manifest-digest", required=True)
        taskpack_action.add_argument("--model-cutoff", required=True)
        taskpack_action.add_argument(
            "--mode",
            choices=("governed_fresh", "search_only_public_swebench"),
            default="governed_fresh",
        )
        if name == "apply":
            taskpack_action.add_argument("--plan-digest", required=True)
            taskpack_action.add_argument("--request-id", required=True)
            taskpack_action.add_argument("--timeout-seconds", type=int, default=90)
        json_flag(taskpack_action)

    campaign = commands.add_parser("campaign", help="manage governed RSI campaigns")
    campaign_commands = campaign.add_subparsers(dest="campaign_command", required=True)
    campaign_plan = leaf(
        campaign_commands,
        "plan",
        command_path="campaign plan",
        help_text="materialize a campaign manifest",
    )
    campaign_plan.add_argument(
        "--profile",
        required=True,
        choices=("pilot-five-offline", "explore-open"),
    )
    json_flag(campaign_plan)

    campaign_run = leaf(
        campaign_commands,
        "run",
        command_path="campaign run",
        help_text="run a stored campaign manifest",
    )
    campaign_run.add_argument("--manifest", required=True)
    campaign_run.add_argument("--request-id", required=True)
    json_flag(campaign_run)

    campaign_list = leaf(
        campaign_commands,
        "list",
        command_path="campaign list",
        help_text="list campaigns",
    )
    campaign_list.add_argument("--state")
    json_flag(campaign_list)

    campaign_status = leaf(
        campaign_commands,
        "status",
        command_path="campaign status",
        help_text="show campaign state",
    )
    campaign_status.add_argument("campaign", nargs="?")
    json_flag(campaign_status)

    campaign_progress = leaf(
        campaign_commands,
        "progress",
        command_path="campaign progress",
        help_text="show durable campaign progress",
    )
    campaign_progress.add_argument("campaign", nargs="?")
    json_flag(campaign_progress)

    campaign_events = leaf(
        campaign_commands,
        "events",
        command_path="campaign events",
        help_text="read the authoritative campaign event sequence",
    )
    campaign_events.add_argument("campaign")
    campaign_events.add_argument("--after", type=int)
    campaign_events.add_argument("--follow", action="store_true")
    json_flag(campaign_events)

    for name in ("pause", "resume", "stop"):
        lifecycle = leaf(
            campaign_commands,
            name,
            command_path=f"campaign {name}",
            help_text=f"{name} a campaign",
        )
        lifecycle.add_argument("campaign")
        lifecycle.add_argument("--request-id")
        json_flag(lifecycle)

    campaign_fork = leaf(
        campaign_commands,
        "fork",
        command_path="campaign fork",
        help_text="create a provenance-linked campaign fork",
    )
    campaign_fork.add_argument("campaign")
    campaign_fork.add_argument("--runner")
    json_flag(campaign_fork)

    campaign_fuse_ack = leaf(
        campaign_commands,
        "fuse-ack",
        command_path="campaign fuse-ack",
        help_text="acknowledge a campaign fuse trip",
    )
    campaign_fuse_ack.add_argument("campaign")
    campaign_fuse_ack.add_argument("--trip", required=True)
    campaign_fuse_ack.add_argument("--reason", required=True)
    campaign_fuse_ack.add_argument("--rearm", action="store_true")
    json_flag(campaign_fuse_ack)

    reconcile = leaf(
        commands,
        "reconcile",
        command_path="reconcile",
        help_text="report control-plane drift",
    )
    reconcile_mode = reconcile.add_mutually_exclusive_group()
    reconcile_mode.add_argument("--plan", action="store_true")
    reconcile_mode.add_argument("--apply", action="store_true")
    reconcile.add_argument("--plan-digest")
    reconcile.add_argument("--request-id")
    reconcile.add_argument("--campaign")
    json_flag(reconcile)

    daily = commands.add_parser("daily", help="inspect the bounded daily lane")
    daily_commands = daily.add_subparsers(dest="daily_command", required=True)
    daily_status = leaf(
        daily_commands,
        "status",
        command_path="daily status",
        help_text="show one read-only daily readiness projection",
    )
    json_flag(daily_status)

    backup = commands.add_parser("backup", help="manage control-plane snapshots")
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    backup_create = leaf(
        backup_commands,
        "create",
        command_path="backup create",
        help_text="create a snapshot",
    )
    json_flag(backup_create)
    backup_verify = leaf(
        backup_commands,
        "verify",
        command_path="backup verify",
        help_text="verify a stored snapshot",
    )
    backup_verify.add_argument("--snapshot", required=True)
    json_flag(backup_verify)
    backup_restore = leaf(
        backup_commands,
        "restore",
        command_path="backup restore",
        help_text="restore a snapshot into an isolated target",
    )
    backup_restore.add_argument("--snapshot", required=True)
    backup_restore.add_argument("--target", required=True)
    backup_restore.add_argument("--apply", action="store_true")
    json_flag(backup_restore)

    worker = commands.add_parser("worker", help="manage enrolled workers")
    worker_commands = worker.add_subparsers(dest="worker_command", required=True)
    worker_list = leaf(
        worker_commands,
        "list",
        command_path="worker list",
        help_text="list enrolled workers",
    )
    json_flag(worker_list)
    for name in ("enroll", "revoke"):
        mutation = leaf(
            worker_commands,
            name,
            command_path=f"worker {name}",
            help_text=f"{name} a worker",
        )
        mutation.add_argument("worker")
        mutation.add_argument("--request-id")
        json_flag(mutation)

    alerts = commands.add_parser("alerts", help="inspect and acknowledge durable alerts")
    alerts_commands = alerts.add_subparsers(dest="alerts_command", required=True)
    alerts_list = leaf(
        alerts_commands,
        "list",
        command_path="alerts list",
        help_text="list durable alerts",
    )
    json_flag(alerts_list)
    alerts_ack = leaf(
        alerts_commands,
        "ack",
        command_path="alerts ack",
        help_text="acknowledge an alert",
    )
    alerts_ack.add_argument("alert")
    alerts_ack.add_argument("--reason", required=True)
    alerts_ack.add_argument("--request-id")
    json_flag(alerts_ack)

    archive = commands.add_parser("archive", help="inspect the immutable archive")
    archive_commands = archive.add_subparsers(dest="archive_command", required=True)
    archive_inspect = leaf(
        archive_commands,
        "inspect",
        command_path="archive inspect",
        help_text="inspect an archived candidate",
    )
    archive_inspect.add_argument("candidate", nargs="?")
    json_flag(archive_inspect)


__all__ = ["add_operator_commands"]
