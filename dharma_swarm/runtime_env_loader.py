"""The ONE runtime env loader — unification seam for provider credentials.

Before 2026-07-03 this host-family had FOUR loaders with two conflicting
precedence semantics: ``api_keys.bootstrap_runtime_env()`` (Python,
never-overwrite/first-wins), ``scripts/load_runtime_env.sh`` (shell,
``set -a`` last-wins, plus a keychain step and its own narrower alias
table), inline launchd plist snippets, and ``~/.zshrc``. Same files, four
readers, order-dependent results — the root cause of weeks of "which keys
do we have?" confusion across seats.

This module makes ``bootstrap_runtime_env()`` the single loader:

- the macOS-keychain fallback step moved here from the shell script and is
  invoked by the Python bootstrap on every process (darwin only, missing
  keys only) — no longer dependent on which loader ran first;
- the split-key-store guard warns loudly when a project ``.env`` carries
  secret-shaped vars while the canonical vault ``~/.dharma/agent_keys.env``
  exists on the same host (the observed failure: launchd snippets doing
  ``set -a; source .env`` shadowed the vault's real OPENAI key with a
  broken placeholder);
- ``emit_shell_exports()`` lets shell callers delegate:
  ``eval "$(python3 -m dharma_swarm.runtime_env_loader emit-exports)"``
  so shell processes get exactly the Python loader's files, precedence,
  aliases, and keychain step — one semantic everywhere.

Doctrine: provider secrets live in ONE store per host — the dkeys vault
(``~/.dharma/agent_keys.env``) on operator machines, ``.env`` next to
docker-compose on vault-less hosts (VPS). The project ``.env`` on a vault
host is configuration, never credentials.
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable

from dharma_swarm.api_keys import (
    ANTHROPIC_API_KEY_ENV,
    GROQ_API_KEY_ENV,
    KIMI_API_KEY_ENV,
    OLLAMA_API_KEY_ENV,
    OPENAI_API_KEY_ENV,
    OPENROUTER_API_KEY_ENV,
    bootstrap_runtime_env,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# (env var, keychain account or None for current user, keychain service).
# Ported verbatim from the retired shell keychain step so behavior is
# preserved; the OpenRouter row with the literal "openrouter" account is the
# shell script's legacy second lookup.
KEYCHAIN_FALLBACKS: tuple[tuple[str, str | None, str], ...] = (
    (ANTHROPIC_API_KEY_ENV, None, "anthropic-api-key"),
    (OPENAI_API_KEY_ENV, None, "openai-api-key"),
    (OPENROUTER_API_KEY_ENV, None, "openrouter-api-key"),
    (OLLAMA_API_KEY_ENV, None, "ollama-api-key"),
    (KIMI_API_KEY_ENV, None, "kimi-api-key"),
    (GROQ_API_KEY_ENV, None, "groq-api-key"),
    ("NIM_API_KEY", None, "nim-api-key"),
    (OPENROUTER_API_KEY_ENV, "openrouter", "openrouter-api-key"),
)

_SECRET_SUFFIXES = (
    "_API_KEY",
    "_AUTH_TOKEN",
    "_TOKEN",
    "_SECRET_KEY",
    "_SECRET_ACCESS_KEY",
)

_SPLIT_STORE_WARNED = False


def _keychain_lookup(account: str, service: str) -> str:
    proc = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def load_keychain_fallbacks(
    env: dict[str, str] | None = None,
    *,
    platform: str | None = None,
    lookup: Callable[[str, str], str] | None = None,
) -> int:
    """Fill MISSING canonical keys from the macOS keychain. Never raises.

    No-op off darwin and for keys already present — with the vault loaded
    this normally touches nothing (verified 2026-07-03: the keychain holds
    no provider keys on the live seat; the step exists for parity with the
    retired shell loader, not because it currently fires).
    """
    target = env if env is not None else os.environ
    plat = platform if platform is not None else sys.platform
    if plat != "darwin":
        return 0
    resolver = lookup or _keychain_lookup
    try:
        import getpass

        user = getpass.getuser()
    except Exception:
        user = ""
    loaded = 0
    for env_name, account, service in KEYCHAIN_FALLBACKS:
        if target.get(env_name, "").strip():
            continue
        try:
            value = resolver(account or user, service)
        except Exception:
            continue
        if value:
            target[env_name] = value
            loaded += 1
    return loaded


def detect_project_env_secret_names(project_env: Path) -> list[str]:
    """Names (never values) of secret-shaped assignments in a project .env."""
    try:
        lines = project_env.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    names: list[str] = []
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        if raw.startswith("export "):
            raw = raw[len("export "):].strip()
        name, value = raw.split("=", 1)
        name = name.strip()
        if not value.split("#", 1)[0].strip():
            continue
        if any(name.endswith(suffix) for suffix in _SECRET_SUFFIXES):
            names.append(name)
    return names


def warn_on_split_key_stores(
    project_env: Path | None = None,
    vault: Path | None = None,
    *,
    force: bool = False,
) -> list[str]:
    """Warn (once per process) when project .env and the vault both hold keys.

    The loader never reads the project .env; the danger is out-of-band
    ``set -a; source .env`` snippets (launchd plists) shadowing vault keys.
    Returns the offending names so callers/tests can assert on them.
    """
    global _SPLIT_STORE_WARNED
    if _SPLIT_STORE_WARNED and not force:
        return []
    project = project_env if project_env is not None else _REPO_ROOT / ".env"
    vault_path = (
        vault if vault is not None else Path.home() / ".dharma" / "agent_keys.env"
    )
    if not (project.is_file() and vault_path.is_file()):
        return []
    names = detect_project_env_secret_names(project)
    if names:
        _SPLIT_STORE_WARNED = True
        logger.warning(
            "SPLIT KEY STORES: %s carries secret-shaped vars %s while the "
            "canonical vault %s exists. The runtime loader never reads the "
            "project .env — but any `set -a; source .env` snippet (launchd "
            "plists) will SHADOW vault keys with these values. Keep provider "
            "secrets only in the vault on this host; project .env is for "
            "non-secret flags.",
            project,
            ", ".join(sorted(names)),
            vault_path,
        )
    return names


# Failures of the never-fatal hook steps, kept diagnosable (inspect from a
# REPL / dgc doctor) instead of vanishing into debug logs.
LAST_HOOK_ERRORS: list[str] = []


def post_file_bootstrap_hook() -> None:
    """Steps the canonical bootstrap runs after loading env files.

    Called (late-imported) from api_keys.bootstrap_runtime_env(); must never
    raise — a broken keychain or unreadable .env cannot be allowed to take
    down provider resolution. Failures are recorded in LAST_HOOK_ERRORS.
    """
    try:
        load_keychain_fallbacks()
    except Exception as exc:  # pragma: no cover - defensive
        LAST_HOOK_ERRORS.append(f"keychain: {exc!r}")
        logger.debug("keychain fallback step failed", exc_info=True)
    try:
        warn_on_split_key_stores()
    except Exception as exc:  # pragma: no cover - defensive
        LAST_HOOK_ERRORS.append(f"split-store-guard: {exc!r}")
        logger.debug("split-key-store guard failed", exc_info=True)


def emit_shell_exports(env_paths: Iterable[Path] | None = None) -> str:
    """Run the canonical bootstrap and render newly-set vars as export lines.

    Shell wrapper contract:
    ``eval "$(python3 -m dharma_swarm.runtime_env_loader emit-exports)"``.
    Only vars the bootstrap actually set/changed are emitted (plus the
    loaded marker), values shell-quoted.
    """
    before = dict(os.environ)
    bootstrap_runtime_env(env_paths=env_paths, force=True)
    lines: list[str] = []
    for name in sorted(os.environ):
        value = os.environ[name]
        if before.get(name) == value:
            continue
        lines.append(f"export {name}={shlex.quote(value)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "emit-exports"
    if command == "emit-exports":
        output = emit_shell_exports()
        if output:
            print(output)
        return 0
    print(
        "usage: python3 -m dharma_swarm.runtime_env_loader emit-exports",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised via shell wrapper
    raise SystemExit(main())
