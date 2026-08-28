#!/usr/bin/env python3
"""Pin GitNexus CLI + MCP wiring on the operator host.

This is host-side repair, not session status. ``make onboard`` remains
read-only and never calls this module. Missing Node is optional unless
``--require-node`` is set.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.onboarding.gitnexus_status import (  # noqa: E402
    PINNED_VERSION,
    classify_mcp_pin,
    collect_gitnexus_status,
)

_GROK_STANZA = (
    "[mcp_servers.gitnexus]\n"
    'command = "gitnexus"\n'
    'args = ["mcp"]\n'
    "enabled = true\n"
)


def _run(cmd: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _current_version() -> str:
    status = collect_gitnexus_status(repo_root=REPO_ROOT)
    return str(status.get("cli_version") or "")


def _ensure_cli(*, optional: bool) -> int:
    if _current_version() == PINNED_VERSION:
        print(f"gitnexus-ensure: CLI already {PINNED_VERSION}")
        return 0
    npm = _which("npm")
    if not npm:
        message = "gitnexus-ensure: npm not on PATH; cannot pin gitnexus"
        if optional:
            print(message)
            return 0
        print(message, file=sys.stderr)
        return 4
    print(f"gitnexus-ensure: installing gitnexus@{PINNED_VERSION}")
    try:
        proc = _run([npm, "install", "-g", f"gitnexus@{PINNED_VERSION}"], timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"gitnexus-ensure: npm install failed: {exc}", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(proc.stderr or proc.stdout, file=sys.stderr)
        return proc.returncode
    print(f"gitnexus-ensure: CLI now {PINNED_VERSION}")
    return 0


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


def _upsert_toml_section(path: Path, header: str, stanza: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "[mcp_servers.gitnexus]" in existing:
        command = ""
        args: list[str] = []
        in_section = False
        for raw in existing.splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                in_section = line[1:-1].strip() == header
                continue
            if not in_section or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "command":
                command = value.strip().strip('"').strip("'")
            if key.strip() == "args":
                inner = value.strip()
                if inner.startswith("[") and inner.endswith("]"):
                    args = [
                        part.strip().strip('"').strip("'")
                        for part in inner[1:-1].split(",")
                        if part.strip()
                    ]
        if classify_mcp_pin(command, args) in {"global_binary", "npx_pinned"}:
            return False
        lines = existing.splitlines(keepends=True)
        kept: list[str] = []
        skipping = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                skipping = stripped[1:-1].strip() == header
            if skipping:
                continue
            kept.append(line)
        existing = "".join(kept).rstrip() + "\n\n"
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing and not existing.endswith("\n\n"):
        existing += "\n"
    path.write_text(existing + stanza, encoding="utf-8")
    return True


def _upsert_json_server(path: Path, home: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"gitnexus-ensure: skip unreadable {path}")
        return False
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        payload["mcpServers"] = servers
    current = servers.get("gitnexus") if isinstance(servers.get("gitnexus"), dict) else {}
    command = str(current.get("command") or "")
    args = [str(item) for item in current.get("args", [])] if isinstance(
        current.get("args"), list
    ) else []
    if classify_mcp_pin(command, args) in {"global_binary", "npx_pinned"}:
        return False
    binary = home / ".npm-global" / "bin" / "gitnexus"
    command_value = str(binary) if binary.is_file() else "gitnexus"
    servers["gitnexus"] = {
        "type": "stdio",
        "command": command_value,
        "args": ["mcp"],
        "env": {},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _ensure_mcp(*, home: Path, repo_root: Path) -> None:
    if _upsert_toml_section(
        home / ".grok" / "config.toml", "mcp_servers.gitnexus", _GROK_STANZA
    ):
        print("gitnexus-ensure: wrote ~/.grok/config.toml gitnexus stanza")
    if _upsert_toml_section(
        repo_root / ".grok" / "config.toml", "mcp_servers.gitnexus", _GROK_STANZA
    ):
        print("gitnexus-ensure: wrote repo .grok/config.toml gitnexus stanza")
    if _upsert_json_server(home / ".claude.json", home):
        print("gitnexus-ensure: updated ~/.claude.json gitnexus MCP")
    if _upsert_json_server(repo_root / ".mcp.json", home):
        print("gitnexus-ensure: updated repo .mcp.json gitnexus MCP")


def _print_status(*, home: Path | None, repo_root: Path) -> int:
    payload = collect_gitnexus_status(home=home, repo_root=repo_root)
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="print the local GitNexus observation JSON and exit",
    )
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="pin CLI + MCP wiring (default when --status is omitted)",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="missing npm/node is not a failure",
    )
    parser.add_argument(
        "--require-node",
        action="store_true",
        help="exit 4 when npm is missing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = Path.home()
    if args.status:
        return _print_status(home=home, repo_root=REPO_ROOT)
    optional = bool(args.optional) and not bool(args.require_node)
    result = _ensure_cli(optional=optional)
    if result != 0:
        return result
    _ensure_mcp(home=home, repo_root=REPO_ROOT)
    return _print_status(home=home, repo_root=REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
