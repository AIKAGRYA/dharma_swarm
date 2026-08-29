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

    taskpack = commands.add_parser("taskpack", help="manage evaluation taskpacks")
    taskpack_commands = taskpack.add_subparsers(dest="taskpack_command", required=True)
    taskpack_build = leaf(
        taskpack_commands,
        "build",
        command_path="taskpack build",
        help_text="build a content-addressed taskpack",
    )
    taskpack_build.add_argument("--profile", required=True)
    taskpack_build.add_argument("--source-manifest")
    taskpack_build.add_argument("--instance", action="append", dest="instances")
    taskpack_build.add_argument("--taskpack-root")
    json_flag(taskpack_build)
    taskpack_import = leaf(
        taskpack_commands,
        "import",
        command_path="taskpack import",
        help_text="admit a sealed official taskpack through the canonical taskbed API",
    )
    taskpack_import.add_argument("--taskpack", required=True)
    taskpack_import.add_argument("--request-id", required=True)
    taskpack_import.add_argument("--taskbed-db")
    taskpack_import.add_argument("--taskpack-root")
    taskpack_import.add_argument("--apply", action="store_true")
    json_flag(taskpack_import)

    safety = commands.add_parser("safety", help="inspect and operate the durable HALT latch")
    safety_commands = safety.add_subparsers(dest="safety_command", required=True)
    safety_status = leaf(
        safety_commands,
        "status",
        command_path="safety status",
        help_text="inspect the durable HALT latch and receipt chain",
    )
    json_flag(safety_status)
    safety_halt = leaf(
        safety_commands,
        "halt",
        command_path="safety halt",
        help_text="latch an operator-requested durable safety stop",
    )
    safety_halt.add_argument("--operator-id", required=True)
    safety_halt.add_argument("--request-id", required=True)
    safety_halt.add_argument("--reason", required=True)
    safety_halt.add_argument("--code", default="OPERATOR_HALT")
    json_flag(safety_halt)
    safety_resume = leaf(
        safety_commands,
        "resume",
        command_path="safety resume",
        help_text="resume only the exact HALT digest under explicit operator authority",
    )
    safety_resume.add_argument("--operator-id", required=True)
    safety_resume.add_argument("--request-id", required=True)
    safety_resume.add_argument("--reason", required=True)
    safety_resume.add_argument("--expected-halt-digest", required=True)
    safety_resume.add_argument(
        "--signature",
        required=True,
        help="OpenSSH signature over the canonical resume-authority statement",
    )
    json_flag(safety_resume)

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
    reconcile.add_argument("--apply", action="store_true")
    reconcile.add_argument("--request-id")
    json_flag(reconcile)

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
