"""Bounded, non-admission GitNexus observation for session status.

Local filesystem, config, and ``gitnexus --version`` only. This collector
never opens LadybugDB, never talks MCP, never runs ``analyze``, and never
claims a live handshake.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "dharma_swarm.onboard_gitnexus.v1"
SPEC_PATH = "docs/ops/AGENT_ONBOARDING.md"
PROBE_SCOPE = "local_cli_mcp_and_index_meta_only"
PINNED_VERSION = "1.6.9"
CANONICAL_CLI_DISPLAY = "~/.npm-global/bin/gitnexus"
_CANONICAL_CLI_RELATIVE = Path(".npm-global") / "bin" / "gitnexus"
_REGISTRY_RELATIVE = Path(".gitnexus") / "registry.json"
_INDEX_META_RELATIVE = Path(".gitnexus") / "meta.json"
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def _home(home: Path | None) -> Path:
    return home if home is not None else Path.home()


def _repo_root(repo_root: Path | None) -> Path:
    return repo_root if repo_root is not None else _DEFAULT_REPO_ROOT


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def _display_path(path: Path, home: Path) -> str:
    try:
        return "~/" + path.resolve().relative_to(home.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _cli_path(home: Path) -> Path | None:
    canonical = home / _CANONICAL_CLI_RELATIVE
    if os.access(canonical, os.X_OK):
        return canonical
    which = shutil_which("gitnexus")
    if which:
        return Path(which)
    return None


def _read_package_version(cli: Path) -> str:
    candidates = (
        cli.parent.parent / "lib" / "node_modules" / "gitnexus" / "package.json",
        Path("/usr/local/lib/node_modules/gitnexus/package.json"),
    )
    for package in candidates:
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        version = str(payload.get("version") or "").strip()
        if version:
            return version
    return ""


def read_cli_version(cli: Path | None) -> str:
    """Prefer package.json; fall back to a bounded ``--version`` call."""
    if cli is None:
        return ""
    packaged = _read_package_version(cli)
    if packaged:
        return packaged
    try:
        proc = subprocess.run(
            [str(cli), "--version"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or proc.stderr or "").strip().splitlines()[0].strip()


def classify_mcp_pin(command: str, args: list[str]) -> str:
    joined = " ".join([command, *args]).strip()
    if not command and not args:
        return "missing"
    if "gitnexus@1.4." in joined or "gitnexus@1.5." in joined or "gitnexus@1.3." in joined:
        return "npx_stale"
    if f"gitnexus@{PINNED_VERSION}" in joined:
        return "npx_pinned"
    if "gitnexus@latest" in joined or "gitnexus@rc" in joined:
        return "npx_unpinned"
    if Path(command).name == "gitnexus" and "mcp" in args:
        return "global_binary"
    if "gitnexus" in joined and "mcp" in args:
        return "other"
    return "missing"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _toml_section(text: str, header: str) -> dict[str, str]:
    """Tiny TOML table reader for the GitNexus MCP stanza only."""
    collected: dict[str, str] = {}
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_section = line[1:-1].strip() == header
            continue
        if not in_section or "=" not in line:
            continue
        key, value = line.split("=", 1)
        collected[key.strip()] = value.strip().strip('"').strip("'")
    return collected


def _toml_args(raw: str) -> list[str]:
    if not raw.startswith("["):
        return []
    inner = raw.strip()[1:-1]
    return [part.strip().strip('"').strip("'") for part in inner.split(",") if part.strip()]


def _mcp_source(path: Path, display: str, *, kind: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": display,
        "exists": path.is_file(),
        "pin_kind": "missing",
    }
    if not path.is_file():
        return row
    if kind == "json":
        payload = _load_json_object(path)
        server = payload.get("mcpServers", {})
        if not isinstance(server, dict):
            return row
        entry = server.get("gitnexus", {})
        if not isinstance(entry, dict):
            return row
        command = str(entry.get("command") or "")
        args = [str(item) for item in entry.get("args", [])] if isinstance(
            entry.get("args"), list
        ) else []
        row["pin_kind"] = classify_mcp_pin(command, args)
        return row
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return row
    section = _toml_section(text, "mcp_servers.gitnexus")
    command = section.get("command", "")
    args = _toml_args(section.get("args", ""))
    row["pin_kind"] = classify_mcp_pin(command, args)
    return row


def _ready_pin(kind: str) -> bool:
    return kind in {"global_binary", "npx_pinned"}


def _git_head(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _index_projection(repo_root: Path, head: str) -> dict[str, Any]:
    meta_path = repo_root / _INDEX_META_RELATIVE
    empty = {
        "index_present": False,
        "index_commit": "",
        "index_matches_head": False,
        "index_schema_version": 0,
        "index_node_count": 0,
    }
    if not meta_path.is_file():
        return empty
    payload = _load_json_object(meta_path)
    commit = str(payload.get("lastCommit") or "")
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    nodes = stats.get("nodes", 0)
    try:
        node_count = int(nodes)
    except (TypeError, ValueError):
        node_count = 0
    schema = payload.get("schemaVersion", 0)
    try:
        schema_version = int(schema)
    except (TypeError, ValueError):
        schema_version = 0
    matches = bool(head) and bool(commit) and (
        head.startswith(commit) or commit.startswith(head)
    )
    return {
        "index_present": True,
        "index_commit": commit[:12],
        "index_matches_head": matches,
        "index_schema_version": schema_version,
        "index_node_count": node_count,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _registry_lists_repo(home: Path, repo_root: Path) -> bool:
    raw = _load_json(home / _REGISTRY_RELATIVE)
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict) and isinstance(raw.get("repos"), list):
        rows = raw["repos"]
    else:
        return False
    try:
        wanted = repo_root.resolve()
    except OSError:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path:
            continue
        try:
            if Path(path).resolve() == wanted:
                return True
        except OSError:
            continue
    return False


def collect_gitnexus_status(
    *,
    home: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return a typed projection that carries no admission or handshake authority."""

    state_home = _home(home)
    root = _repo_root(repo_root)
    cli = _cli_path(state_home)
    version = read_cli_version(cli)
    mcp_sources = [
        _mcp_source(
            state_home / ".grok" / "config.toml",
            "~/.grok/config.toml",
            kind="toml",
        ),
        _mcp_source(
            root / ".grok" / "config.toml",
            ".grok/config.toml",
            kind="toml",
        ),
        _mcp_source(
            state_home / ".claude.json",
            "~/.claude.json",
            kind="json",
        ),
        _mcp_source(root / ".mcp.json", ".mcp.json", kind="json"),
    ]
    wired = any(_ready_pin(str(row["pin_kind"])) for row in mcp_sources)
    head = _git_head(root)
    index = _index_projection(root, head)
    return {
        "schema": SCHEMA,
        "authority": "local_observation_only",
        "spec_path": SPEC_PATH,
        "probe_scope": PROBE_SCOPE,
        "pinned_version": PINNED_VERSION,
        "cli_present": cli is not None,
        "cli_path": _display_path(cli, state_home) if cli is not None else "",
        "cli_version": version,
        "version_matches_pin": version == PINNED_VERSION,
        "mcp_wired": wired,
        "mcp_sources": mcp_sources,
        "canonical_cli_path": CANONICAL_CLI_DISPLAY,
        "checkout_head": head[:12],
        "registry_lists_checkout": _registry_lists_repo(state_home, root),
        "live_mcp_claimed": False,
        "analyze_claimed": False,
        **index,
    }


__all__ = [
    "CANONICAL_CLI_DISPLAY",
    "PINNED_VERSION",
    "PROBE_SCOPE",
    "SCHEMA",
    "SPEC_PATH",
    "classify_mcp_pin",
    "collect_gitnexus_status",
    "read_cli_version",
]
