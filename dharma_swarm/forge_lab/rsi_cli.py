"""Repo-owned RSI control plane.

The governed minimum implements content-addressed campaign planning, fail-closed
preflight, durable query/control receipts, reconciliation, and code sync. Other
registered surfaces still refuse before importing legacy live experiment code.
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

    from dharma_swarm.forge_lab.campaign_cli import add_campaign_commands

    add_campaign_commands(commands, leaf=_leaf, json_flag=_json_flag)

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


def _emit_sync_payload(
    command_path: str,
    result: dict[str, Any],
    *,
    as_json: bool,
    ok: bool = True,
) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "schema": CLI_RESULT_SCHEMA,
                    "ok": ok,
                    "command": command_path,
                    "result": result,
                },
                sort_keys=True,
            )
        )
        return
    if command_path == "sync status":
        print(f"status: {'IN_SYNC' if result['in_sync'] else 'DRIFT'}")
        print(f"github: {result['canonical'].get('commit') or 'unavailable'}")
        for node in ("mac", "meghadharma"):
            identity = result.get(node, {}).get("identity") or {}
            print(
                f"{node}: {identity.get('commit') or 'unavailable'} "
                f"clean={identity.get('repo_clean', False)}"
            )
        for failure in result.get("failures", []):
            print(f"failure: {failure}")
        return
    if command_path == "sync plan":
        print(f"commit: {result['plan']['commit']}")
        print(f"plan: {result['plan']['plan_digest']}")
        print(f"path: {result['path']}")
        return
    print(f"commit: {result['commit']}")
    if result.get("plan_digest"):
        print(f"plan: {result['plan_digest']}")
    if result.get("receipt"):
        print(f"receipt: {result['receipt']}")



def _dispatch_sync(args: argparse.Namespace) -> int:
    from dharma_swarm.forge_lab import sync_orchestrator as sync_control

    command_path = args._command_path
    try:
        if command_path == "sync status":
            result = sync_control.sync_status(remote=args.remote)
            _emit_sync_payload(
                command_path, result, as_json=args.json, ok=result["in_sync"]
            )
            return 0 if result["in_sync"] else DRIFT_EXIT
        if command_path == "sync plan":
            plan, path = sync_control.create_plan()
            result = {"plan": plan, "path": str(path)}
        elif command_path == "sync apply":
            plan, _ = sync_control.load_plan(args.manifest)
            result = sync_control.apply_plan(
                plan, request_id=args.request_id, remote=args.remote
            )
        elif command_path == "sync converge":
            result = sync_control.converge(
                request_id=args.request_id, remote=args.remote
            )
        elif command_path == "sync rollback":
            result = sync_control.rollback(
                args.release, request_id=args.request_id, remote=args.remote
            )
        else:  # pragma: no cover - parser owns the command set
            raise sync_control.SyncError("UNKNOWN_SYNC_COMMAND", command_path)
        _emit_sync_payload(command_path, result, as_json=args.json)
        return 0
    except sync_control.SyncError as exc:
        message = str(exc)
        if args.json:
            print(
                json.dumps(
                    {
                        "schema": CLI_RESULT_SCHEMA,
                        "ok": False,
                        "command": command_path,
                        "error": {"code": exc.code, "message": message},
                    },
                    sort_keys=True,
                )
            )
        print(f"rsi {command_path} failed [{exc.code}]: {message}", file=sys.stderr)
        return SYNC_FAILURE_EXIT



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
        from dharma_swarm.forge_lab.provider_selftest_cli import dispatch

        return dispatch(args)
    if command_path.startswith("campaign ") or command_path == "reconcile":
        from dharma_swarm.forge_lab.campaign_cli import dispatch
        return dispatch(args)
    if command_path.startswith("sync "):
        return _dispatch_sync(args)
    return _fail_not_implemented(command_path, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
