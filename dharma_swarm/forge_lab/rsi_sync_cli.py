"""Sync subcommand dispatch for the RSI CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from dharma_swarm.forge_lab.version import CLI_RESULT_SCHEMA

SYNC_FAILURE_EXIT = 5


def emit_sync_payload(command_path: str, result: dict[str, Any], *, as_json: bool, ok: bool = True) -> None:
    if as_json:
        print(json.dumps({"schema": CLI_RESULT_SCHEMA, "ok": ok, "command": command_path, "result": result}, sort_keys=True))
        return
    if command_path == "sync status":
        print(f"status: {'IN_SYNC' if result['in_sync'] else 'DRIFT'}")
        print(f"github: {result['canonical'].get('commit') or 'unavailable'}")
        for node in ("mac", "meghadharma"):
            identity = result.get(node, {}).get("identity") or {}
            print(f"{node}: {identity.get('commit') or 'unavailable'} clean={identity.get('repo_clean', False)}")
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


def dispatch_sync(args: argparse.Namespace) -> int:
    from dharma_swarm.forge_lab import sync_orchestrator as sync_control

    command_path = args._command_path
    try:
        if command_path == "sync status":
            result = sync_control.sync_status(remote=args.remote)
            emit_sync_payload(command_path, result, as_json=args.json, ok=result["in_sync"])
            return 0 if result["in_sync"] else 4
        if command_path == "sync plan":
            plan, path = sync_control.create_plan()
            result = {"plan": plan, "path": str(path)}
        elif command_path == "sync apply":
            plan, _ = sync_control.load_plan(args.manifest)
            result = sync_control.apply_plan(plan, request_id=args.request_id, remote=args.remote)
        elif command_path == "sync converge":
            result = sync_control.converge(request_id=args.request_id, remote=args.remote)
        elif command_path == "sync rollback":
            result = sync_control.rollback(args.release, request_id=args.request_id, remote=args.remote)
        else:  # pragma: no cover - parser owns the command set
            raise sync_control.SyncError("UNKNOWN_SYNC_COMMAND", command_path)
        emit_sync_payload(command_path, result, as_json=args.json)
        return 0
    except sync_control.SyncError as exc:
        message = str(exc)
        if args.json:
            print(json.dumps({"schema": CLI_RESULT_SCHEMA, "ok": False, "command": command_path, "error": {"code": exc.code, "message": message}}, sort_keys=True))
        print(f"rsi {command_path} failed [{exc.code}]: {message}", file=sys.stderr)
        return SYNC_FAILURE_EXIT
