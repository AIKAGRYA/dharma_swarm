"""Bounded, non-admission Sourcegraph observation for session status.

Local filesystem and process-environment checks only. This collector never
calls Sourcegraph over the network, never runs ``src search``, never prints
token values, and never claims that ``dharma_swarm`` is indexed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

SCHEMA = "dharma_swarm.onboard_sourcegraph.v1"
SPEC_PATH = "docs/ops/CODEX_TOOLBELT_ONBOARDING.md"
PROBE_SCOPE = "local_cli_and_env_only"
DEFAULT_PUBLIC_ENDPOINT = "https://sourcegraph.com"
CANONICAL_CLI_DISPLAY = "~/.local/bin/src"
_CANONICAL_CLI_RELATIVE = Path(".local") / "bin" / "src"
_ENV_FILE_RELATIVE = Path(".dharma") / "sourcegraph.env"
_CONFIG_RELATIVE_PATHS = (
    Path(".config") / "sourcegraph" / "config.json",
    Path(".sourcegraph") / "config.json",
)
_ENV_FILE_KEYS = ("SRC_ENDPOINT", "SRC_ACCESS_TOKEN")


def _home(home: Path | None) -> Path:
    return home if home is not None else Path.home()


def _cli_path(home: Path) -> Path | None:
    canonical = home / _CANONICAL_CLI_RELATIVE
    if os.access(canonical, os.X_OK):
        return canonical
    which = shutil_which("src")
    if which:
        return Path(which)
    return None


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def _display_path(path: Path, home: Path) -> str:
    try:
        return "~/" + path.resolve().relative_to(home.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _endpoint_kind(raw: str) -> str:
    if not raw.strip():
        return "unset"
    host = urlparse(raw.strip()).netloc.lower()
    if not host:
        host = raw.strip().lower()
    if host in {"sourcegraph.com", "www.sourcegraph.com"}:
        return "public_dotcom"
    if host == "sourcegraph.app" or host.endswith(".sourcegraph.app"):
        return "workspace"
    if "sourcegraph" in host:
        return "self_hosted"
    return "other"


def _endpoint_host(raw: str) -> str:
    if not raw.strip():
        return ""
    parsed = urlparse(raw.strip())
    return parsed.netloc.lower()


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return parsed
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in _ENV_FILE_KEYS:
            parsed[key] = value.strip().strip("'").strip('"')
    return parsed


def _keychain_present(endpoint: str) -> bool:
    host = endpoint.strip().rstrip("/")
    if not host:
        return False
    service = f"Sourcegraph CLI <{host}>"
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", service],
            capture_output=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _config_rows(home: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in _CONFIG_RELATIVE_PATHS:
        target = home / relative
        rows.append({
            "path": "~/" + relative.as_posix(),
            "exists": target.is_file(),
        })
    return rows


def _search_scope(
    *,
    endpoint_kind: str,
    token_present: bool,
    config_present: bool,
    cli_present: bool,
    keychain_present: bool,
) -> str:
    if endpoint_kind == "workspace" and (
        token_present or config_present or keychain_present
    ):
        return "workspace_capable"
    if endpoint_kind in {"self_hosted", "other"} and (token_present or config_present):
        return "instance_capable"
    if endpoint_kind == "public_dotcom" or (endpoint_kind == "unset" and cli_present):
        return "public_only"
    return "unconfigured"


def collect_sourcegraph_status(
    *,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a typed projection that carries no admission or index authority."""

    state_home = _home(home)
    file_env = _parse_env_file(state_home / _ENV_FILE_RELATIVE)
    overlay: Mapping[str, str] = os.environ if environ is None else environ
    env = dict(file_env)
    for key in _ENV_FILE_KEYS:
        value = str(overlay.get(key, "") or "")
        if value:
            env[key] = value
    cli = _cli_path(state_home)
    endpoint = str(env.get("SRC_ENDPOINT", "") or "")
    token_present = bool(str(env.get("SRC_ACCESS_TOKEN", "") or "").strip())
    keychain_present = _keychain_present(endpoint)
    config_rows = _config_rows(state_home)
    config_present = any(row["exists"] for row in config_rows)
    kind = _endpoint_kind(endpoint)
    return {
        "schema": SCHEMA,
        "authority": "local_observation_only",
        "spec_path": SPEC_PATH,
        "probe_scope": PROBE_SCOPE,
        "src_cli_present": cli is not None,
        "src_cli_path": _display_path(cli, state_home) if cli is not None else "",
        "endpoint_set": bool(endpoint.strip()),
        "endpoint_kind": kind,
        "endpoint_host": _endpoint_host(endpoint),
        "token_present": token_present,
        "keychain_present": keychain_present,
        "env_file_present": (state_home / _ENV_FILE_RELATIVE).is_file(),
        "config_files": config_rows,
        "config_file_present": config_present,
        "search_scope": _search_scope(
            endpoint_kind=kind,
            token_present=token_present,
            config_present=config_present,
            cli_present=cli is not None,
            keychain_present=keychain_present,
        ),
        "default_public_endpoint": DEFAULT_PUBLIC_ENDPOINT,
        "canonical_cli_path": CANONICAL_CLI_DISPLAY,
        "live_search_claimed": False,
        "repo_index_claimed": False,
    }


__all__ = [
    "CANONICAL_CLI_DISPLAY",
    "DEFAULT_PUBLIC_ENDPOINT",
    "PROBE_SCOPE",
    "SCHEMA",
    "SPEC_PATH",
    "collect_sourcegraph_status",
]
