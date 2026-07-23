"""Repo-owned RSI CLI skeleton.

Only version reporting is implemented in Packet A. Every operational command is
registered so callers can discover the target surface, but dispatch fails closed
before importing legacy experiment or live-provider code.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from dharma_swarm.forge_lab.version import (
    CLI_RESULT_SCHEMA,
    PACKAGE_VERSION,
    forge_identity,
    source_commit,
)


NOT_IMPLEMENTED_EXIT = 3
DRIFT_EXIT = 4
SYNC_FAILURE_EXIT = 5
PROVIDER_FAILURE_EXIT = 6


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit a versioned JSON result")


def _leaf(
    subparsers: Any,
    name: str,
    *,
    command_path: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.set_defaults(_command_path=command_path)
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Build the complete v0.1 command tree without importing runtime code."""

    parser = argparse.ArgumentParser(prog="rsi", description="Forge Lab RSI control plane")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PACKAGE_VERSION} source={source_commit()}",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    version = _leaf(
        commands,
        "version",
        command_path="version",
        help_text="report package and source identity",
    )
    _json_flag(version)

    newrun = _leaf(
        commands,
        "newrun",
        command_path="newrun",
        help_text="show or launch bleeding-edge Forge Lab EXPLORE runs",
    )
    from dharma_swarm.forge_lab.newrun import add_newrun_arguments

    add_newrun_arguments(newrun)
    _json_flag(newrun)

    doctor = _leaf(
        commands,
        "doctor",
        command_path="doctor",
        help_text="inspect control-plane readiness without side effects",
    )
    _json_flag(doctor)

    provider = commands.add_parser("provider", help="inspect provider routes")
    provider_commands = provider.add_subparsers(dest="provider_command", required=True)
    provider_selftest = _leaf(
        provider_commands,
        "selftest",
        command_path="provider selftest",
        help_text="test provider readiness",
    )
    provider_selftest.add_argument("--profile", required=True)
    provider_selftest.add_argument("--live", action="store_true")
    provider_selftest.add_argument("--require-independent-routes", type=int)
    provider_selftest.add_argument("--model", help="current model id to include for current/newrun profiles")
    provider_selftest.add_argument("--timeout-s", type=int, default=20, help="per-route live probe timeout")
    _json_flag(provider_selftest)

    taskpack = commands.add_parser("taskpack", help="manage evaluation taskpacks")
    taskpack_commands = taskpack.add_subparsers(dest="taskpack_command", required=True)
    taskpack_build = _leaf(
        taskpack_commands,
        "build",
        command_path="taskpack build",
        help_text="build a content-addressed taskpack",
    )
    taskpack_build.add_argument("--profile", required=True)
    _json_flag(taskpack_build)

    campaign = commands.add_parser("campaign", help="manage governed RSI campaigns")
    campaign_commands = campaign.add_subparsers(dest="campaign_command", required=True)

    campaign_plan = _leaf(
        campaign_commands,
        "plan",
        command_path="campaign plan",
        help_text="materialize a campaign manifest",
    )
    campaign_plan.add_argument("--profile", required=True, choices=("explore-open",))
    _json_flag(campaign_plan)

    campaign_run = _leaf(
        campaign_commands,
        "run",
        command_path="campaign run",
        help_text="run a stored campaign manifest",
    )
    campaign_run.add_argument("--manifest", required=True)
    campaign_run.add_argument("--request-id")
    _json_flag(campaign_run)

    campaign_list = _leaf(
        campaign_commands,
        "list",
        command_path="campaign list",
        help_text="list campaigns",
    )
    campaign_list.add_argument("--state")
    _json_flag(campaign_list)

    campaign_status = _leaf(
        campaign_commands,
        "status",
        command_path="campaign status",
        help_text="show campaign state",
    )
    campaign_status.add_argument("campaign", nargs="?")
    _json_flag(campaign_status)

    campaign_progress = _leaf(
        campaign_commands,
        "progress",
        command_path="campaign progress",
        help_text="show durable campaign progress",
    )
    campaign_progress.add_argument("campaign", nargs="?")
    _json_flag(campaign_progress)

    campaign_events = _leaf(
        campaign_commands,
        "events",
        command_path="campaign events",
        help_text="read the authoritative campaign event sequence",
    )
    campaign_events.add_argument("campaign")
    campaign_events.add_argument("--after", type=int)
    campaign_events.add_argument("--follow", action="store_true")
    _json_flag(campaign_events)

    for name in ("pause", "resume", "stop"):
        lifecycle = _leaf(
            campaign_commands,
            name,
            command_path=f"campaign {name}",
            help_text=f"{name} a campaign",
        )
        lifecycle.add_argument("campaign")
        lifecycle.add_argument("--request-id")
        _json_flag(lifecycle)

    campaign_fork = _leaf(
        campaign_commands,
        "fork",
        command_path="campaign fork",
        help_text="create a provenance-linked campaign fork",
    )
    campaign_fork.add_argument("campaign")
    campaign_fork.add_argument("--runner")
    _json_flag(campaign_fork)

    campaign_fuse_ack = _leaf(
        campaign_commands,
        "fuse-ack",
        command_path="campaign fuse-ack",
        help_text="acknowledge a campaign fuse trip",
    )
    campaign_fuse_ack.add_argument("campaign")
    campaign_fuse_ack.add_argument("--trip", required=True)
    campaign_fuse_ack.add_argument("--reason", required=True)
    campaign_fuse_ack.add_argument("--rearm", action="store_true")
    _json_flag(campaign_fuse_ack)

    reconcile = _leaf(
        commands,
        "reconcile",
        command_path="reconcile",
        help_text="report control-plane drift",
    )
    reconcile.add_argument("--apply", action="store_true")
    _json_flag(reconcile)

    backup = commands.add_parser("backup", help="manage control-plane snapshots")
    backup_commands = backup.add_subparsers(dest="backup_command", required=True)
    backup_create = _leaf(
        backup_commands,
        "create",
        command_path="backup create",
        help_text="create a snapshot",
    )
    _json_flag(backup_create)
    backup_verify = _leaf(
        backup_commands,
        "verify",
        command_path="backup verify",
        help_text="verify a stored snapshot",
    )
    backup_verify.add_argument("--snapshot", required=True)
    _json_flag(backup_verify)
    backup_restore = _leaf(
        backup_commands,
        "restore",
        command_path="backup restore",
        help_text="restore a snapshot into an isolated target",
    )
    backup_restore.add_argument("--snapshot", required=True)
    backup_restore.add_argument("--target", required=True)
    backup_restore.add_argument("--apply", action="store_true")
    _json_flag(backup_restore)

    worker = commands.add_parser("worker", help="manage enrolled workers")
    worker_commands = worker.add_subparsers(dest="worker_command", required=True)
    worker_list = _leaf(
        worker_commands,
        "list",
        command_path="worker list",
        help_text="list enrolled workers",
    )
    _json_flag(worker_list)
    for name in ("enroll", "revoke"):
        worker_mutation = _leaf(
            worker_commands,
            name,
            command_path=f"worker {name}",
            help_text=f"{name} a worker",
        )
        worker_mutation.add_argument("worker")
        worker_mutation.add_argument("--request-id")
        _json_flag(worker_mutation)

    alerts = commands.add_parser("alerts", help="inspect and acknowledge durable alerts")
    alerts_commands = alerts.add_subparsers(dest="alerts_command", required=True)
    alerts_list = _leaf(
        alerts_commands,
        "list",
        command_path="alerts list",
        help_text="list durable alerts",
    )
    _json_flag(alerts_list)
    alerts_ack = _leaf(
        alerts_commands,
        "ack",
        command_path="alerts ack",
        help_text="acknowledge an alert",
    )
    alerts_ack.add_argument("alert")
    alerts_ack.add_argument("--reason", required=True)
    alerts_ack.add_argument("--request-id")
    _json_flag(alerts_ack)

    archive = commands.add_parser("archive", help="inspect the immutable archive")
    archive_commands = archive.add_subparsers(dest="archive_command", required=True)
    archive_inspect = _leaf(
        archive_commands,
        "inspect",
        command_path="archive inspect",
        help_text="inspect an archived candidate",
    )
    archive_inspect.add_argument("candidate", nargs="?")
    _json_flag(archive_inspect)

    sync = commands.add_parser(
        "sync", help="verify and converge immutable RSI Lab code releases"
    )
    sync_commands = sync.add_subparsers(dest="sync_command", required=True)

    sync_status = _leaf(
        sync_commands,
        "status",
        command_path="sync status",
        help_text="compare GitHub, Mac, and Meghadharma code identity",
    )
    sync_status.add_argument("--remote", default="meghadharma")
    _json_flag(sync_status)

    sync_plan = _leaf(
        sync_commands,
        "plan",
        command_path="sync plan",
        help_text="pin the canonical GitHub ref in a content-addressed manifest",
    )
    _json_flag(sync_plan)

    sync_apply = _leaf(
        sync_commands,
        "apply",
        command_path="sync apply",
        help_text="prepare, verify, and atomically activate a stored manifest",
    )
    sync_apply.add_argument("--manifest", required=True)
    sync_apply.add_argument("--request-id", required=True)
    sync_apply.add_argument("--remote", default="meghadharma")
    _json_flag(sync_apply)

    sync_converge = _leaf(
        sync_commands,
        "converge",
        command_path="sync converge",
        help_text="plan and apply the current canonical ref in one explicit operation",
    )
    sync_converge.add_argument("--request-id", required=True)
    sync_converge.add_argument("--remote", default="meghadharma")
    _json_flag(sync_converge)

    sync_rollback = _leaf(
        sync_commands,
        "rollback",
        command_path="sync rollback",
        help_text="atomically reactivate a previously verified full-SHA release",
    )
    sync_rollback.add_argument("--release", required=True)
    sync_rollback.add_argument("--request-id", required=True)
    sync_rollback.add_argument("--remote", default="meghadharma")
    _json_flag(sync_rollback)

    return parser


def _emit_version(as_json: bool) -> int:
    identity = forge_identity()
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": True,
                    "command": "version",
                    "result": identity,
                },
                sort_keys=True,
            )
        )
        return 0

    for field in (
        "package",
        "package_version",
        "source_commit",
        "source_tree_state",
        "canonical_checkout",
        "implementation_status",
    ):
        print(f"{field}: {identity[field]}")
    return 0


def _fail_not_implemented(command_path: str, as_json: bool) -> int:
    message = f"rsi {command_path} is registered but not implemented"
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": False,
                    "command": command_path,
                    "error": {"code": "NOT_IMPLEMENTED", "message": message},
                },
                sort_keys=True,
            )
        )
    print(message, file=sys.stderr)
    return NOT_IMPLEMENTED_EXIT


def _normalize_operator_argv(argv: list[str] | None) -> list[str] | None:
    """Accept operator shorthand such as ``RSILAB - NEWRUN``.

    The canonical command remains ``rsi newrun``.  The shorthand exists because
    the operator asked for a memorable one-command entrypoint and may type it
    in uppercase with a visual dash separator.
    """

    if argv is None:
        argv = sys.argv[1:]
    else:
        argv = list(argv)
    if len(argv) >= 2 and argv[0] == "-" and argv[1].lower().replace("-", "") == "newrun":
        return ["newrun", *argv[2:]]
    if argv and argv[0].lower().replace("-", "") == "newrun":
        return ["newrun", *argv[1:]]
    return argv

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_operator_argv(argv))
    command_path = args._command_path
    if command_path == "version":
        return _emit_version(args.json)
    if command_path == "newrun":
        from dharma_swarm.forge_lab.newrun import run_newrun

        return run_newrun(args)
    if command_path.startswith("provider "):
        from dharma_swarm.forge_lab.rsi_provider_cli import dispatch_provider

        return dispatch_provider(args)
    if command_path.startswith("sync "):
        from dharma_swarm.forge_lab.rsi_sync_cli import dispatch_sync

        return dispatch_sync(args)
    return _fail_not_implemented(command_path, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
