"""One explicit action vocabulary for scripts, native UI and AI tool adapters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import DesktopConfig, DesktopError, SESSION, SOCKET


def _common(parser: argparse.ArgumentParser) -> None:
    for flag, help_text in (("--state-dir", "isolated runtime/config directory (default: ~/.dharma/helm_desktop)"),
                            ("--repo-root", "checkout containing the existing Helm launcher"),
                            ("--profile", "installed profile name or absolute JSON profile path"),
                            ("--socket", "explicit CODEX_MANAGED_<name> socket"),
                            ("--session", "exact private tmux session name")):
        parser.add_argument(flag, default=argparse.SUPPRESS, help=help_text)
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, dest="as_json",
                        help="emit one machine-readable JSON object")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Helm Desktop: observe, focus and configure the existing Helm owner.")
    _common(root)
    commands = root.add_subparsers(dest="command", required=True)
    for name, help_text in (("status", "read the owner status file; no subprocesses"),
                            ("doctor", "read-only dependency and profile checks"),
                            ("start", "explicitly start or verify the private Helm seat"),
                            ("focus", "focus/attach an existing seat; never start the bridge"),
                            ("close", "close the verified diagnostic window; preserve its session"),
                            ("catalog", "print supported typed actions for automation")):
        _common(commands.add_parser(name, help=help_text))
    workbench = commands.add_parser("workbench", help="OpenCode coding workspace with Dharma context")
    _common(workbench)
    workbench_commands = workbench.add_subparsers(dest="operation", required=True)
    workbench_open = workbench_commands.add_parser("open", help="open or focus the dedicated coding window")
    _common(workbench_open)
    workbench_open.add_argument("--model", help="initial provider/model; use F4 for later switches")
    workbench_open.add_argument("--api-access", action=argparse.BooleanOptionalAction, default=None,
                                help="make existing metered API accounts available in this workspace")
    _common(workbench_commands.add_parser("close", help="close the window and retain the coding session"))
    _common(workbench_commands.add_parser("status", help="inspect the exact coding session and window"))
    workspace = commands.add_parser("workspace", help="preview/open typed project resources")
    _common(workspace)
    workspace_commands = workspace.add_subparsers(dest="operation", required=True)
    _common(workspace_commands.add_parser("preview"))
    workspace_open = workspace_commands.add_parser("open")
    _common(workspace_open)
    workspace_open.add_argument("--reopen", action="store_true", help="repeat prior browser or untracked editor requests")
    install = commands.add_parser("install", help="preview/apply isolated profile and launch wrappers")
    _common(install)
    install_commands = install.add_subparsers(dest="operation", required=True)
    _common(install_commands.add_parser("preview"))
    install_apply = install_commands.add_parser("apply")
    _common(install_apply)
    install_apply.add_argument("--apply", action="store_true", required=True, help="write the previewed isolated artifacts")
    for name in ("restore", "uninstall"):
        restore = commands.add_parser(name, help="preview restoration; preserve later user edits")
        _common(restore)
        restore.add_argument("--apply", action="store_true", help="apply compare-before-restore changes")
    return root


def catalog() -> dict[str, Any]:
    rows = [
        ("status", ["status"], "observation_only", False, "read one status snapshot"),
        ("doctor", ["doctor"], "observation_only", False, "inspect local prerequisites"),
        ("focus", ["focus"], "desktop_navigation", True, "focus or attach the existing exact private seat"),
        ("close", ["close"], "desktop_navigation", True, "detach only the verified diagnostic window"),
        ("workbench.open", ["workbench", "open"], "explicit_session_start", True, "open the isolated OpenCode coding workspace"),
        ("workbench.close", ["workbench", "close"], "desktop_navigation", True, "close its window and preserve its coding session"),
        ("workbench.status", ["workbench", "status"], "observation_only", False, "inspect the private coding seat"),
        ("start", ["start"], "explicit_session_start", True, "invoke the existing owner launcher and verify its executor"),
        ("workspace.preview", ["workspace", "preview"], "observation_only", False, "show validated resource intents"),
        ("workspace.open", ["workspace", "open"], "desktop_navigation", True, "apply typed app/resource intents"),
        ("install.preview", ["install", "preview"], "observation_only", False, "show isolated generated files"),
        ("install.apply", ["install", "apply", "--apply"], "explicit_config_write", True, "write only isolated generated files"),
        ("restore", ["restore", "--apply"], "explicit_config_write", True, "restore only files still matching installed hashes"),
    ]
    return {"schema": "dharma.helm.desktop_actions.v1", "authority": "descriptive_only",
            "grants_execution_authority": False,
            "actions": [{"id": action, "argv": argv, "capability": capability, "mutates": mutates,
                         "description": description, "arbitrary_shell": False}
                        for action, argv, capability, mutates, description in rows]}


def execute(args: argparse.Namespace, config: DesktopConfig) -> dict[str, Any]:
    from . import install, runtime, workspace
    from .storage import operation_lock

    if args.command == "status":
        return runtime.observe(config)
    if args.command == "doctor":
        return runtime.doctor(config)
    if args.command == "catalog":
        return catalog()
    if args.command == "workbench" and args.operation == "status":
        from .workbench_runtime import status
        return status(config)
    if args.command == "workspace" and args.operation == "preview":
        return workspace.preview(config)
    if args.command == "install" and args.operation == "preview":
        return install.preview(config)
    if args.command in {"restore", "uninstall"} and not args.apply:
        return install.restore(config)
    with operation_lock(config.state_dir):
        if args.command == "start":
            return runtime.start(config)
        if args.command == "focus":
            return runtime.focus(config)
        if args.command == "close":
            return runtime.close(config)
        if args.command == "workbench":
            from .workbench_runtime import close_workbench, open_workbench
            if args.operation == "close":
                return close_workbench(config)
            return open_workbench(config, model=args.model, api_access=args.api_access)
        if args.command == "workspace":
            return workspace.open_workspace(config, reopen=args.reopen)
        if args.command == "install":
            return install.apply(config)
        return install.restore(config, apply_changes=True)


def _human(result: dict[str, Any]) -> str:
    if "availability" in result:
        snapshot = result.get("snapshot") or {}
        return f"Helm: {result['availability']} · {snapshot.get('phase', result.get('reason', 'unknown'))}\n{result['status_file']}"
    if result.get("action") == "install.preview":
        rows = [f"{item['action']}: {item['path']}" for item in result["files"]]
        rows.append("Review generated content with --json. Apply with: install apply --apply")
        return "\n".join(rows)
    return json.dumps(result, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    options = vars(args)
    try:
        config = DesktopConfig(
            repo_root=Path(options.get("repo_root", Path(__file__).resolve().parents[2])),
            state_dir=Path(options.get("state_dir", Path.home() / ".dharma/helm_desktop")),
            profile=options.get("profile", "research"), socket=options.get("socket", SOCKET),
            session=options.get("session", SESSION))
        result = execute(args, config)
        unclosed = (result.get("action") in {"close", "workbench.close"}
                    and result.get("outcome") == "attached_elsewhere")
        failed = (result.get("outcome") == "partial" or unclosed
                  or result.get("ready") is False or result.get("ready_to_start") is False)
        result = {"ok": not failed, **result}
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")) if options.get("as_json") else _human(result))
        return 1 if failed else 0
    except (DesktopError, OSError) as exc:
        result = {"ok": False, "action": args.command, "error": str(exc)}
        if options.get("as_json"):
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        else:
            print(f"Helm Desktop: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
