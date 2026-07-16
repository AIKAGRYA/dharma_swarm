#!/usr/bin/env python3
"""Compatibility entrypoint for dharma_swarm session status.

This file is a thin compatibility shim: it parses the public status flags
and delegates to the compact onboarding engine in
`dharma_swarm/operator_core/onboarding/cli.py`. Truthful typed exit codes are
the default; `--strict` is retained as a compatibility no-op. The legacy
v1-only `_receipt_payload` and the canonical
`_parse_broken_register` helpers remain exposed for tests and other
consumers that share the canonical parser.

The process exit is always the rendered receipt's true exit code.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BROKEN_REGISTER = REPO_ROOT / "docs/state/BROKEN_REGISTER.md"


def _load_broken_register_parser() -> Any:
    """Load the canonical broken-register parser without importing dharma_swarm.

    This keeps `python -I -S scripts/governance/agent_onboard.py --help` working
    and guarantees the canonical parser is shared by every consumer.
    """
    path = REPO_ROOT / "dharma_swarm/operator_core/onboarding/broken_register.py"
    spec = importlib.util.spec_from_file_location(
        "_dharma_broken_register_onboard", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load broken_register.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_broken_register


parse_broken_register = _load_broken_register_parser()


def _parse_broken_register() -> dict[str, Any]:
    """Return summary counts and top open BR items."""
    result = parse_broken_register(BROKEN_REGISTER)
    if not result.present:
        return {"present": False}
    top_open = [
        {
            "id": entry.id,
            "heading": entry.heading,
            "status_word": entry.status,
            "status": entry.raw_status,
        }
        for entry in result.open_entries[:3]
    ]
    return {
        "present": True,
        "total": result.total,
        "open_count": result.open_count,
        "closed_count": result.closed_count,
        "unknown_count": result.unknown_count,
        "top_open": top_open,
        "diagnostics": [
            {
                "code": diagnostic.code,
                "message": diagnostic.message,
                "br_id": diagnostic.br_id,
                "line": diagnostic.line,
            }
            for diagnostic in result.diagnostics
        ],
    }


def _receipt_payload(
    repo_state: dict[str, Any],
    lanes: dict[str, Any],
    rows: list[dict[str, Any]],
    prs: list[dict[str, Any]],
    evidence: dict[str, Any] | None,
    track: dict[str, Any],
) -> dict[str, Any]:
    """v1-only receipt payload kept for contract tests.

    D3 (external-reader inventory) is still pending, so the on-disk writer
    remains v1. This helper must not introduce v2 string constants.
    """
    return {
        "schema": "dharma_swarm.onboard_receipt.v1",
        "observed_at": "2026-01-01T00:00:00Z",
        "authority": "projection_only",
        "repo": dict(repo_state),
        "work_lanes": dict(lanes),
        "portfolio": dict(track),
        "next_items": list(rows),
        "swarm_bulletins": [],
        "broken_register": dict(evidence or {}),
        "open_prs": list(prs),
        "runtime_truth_packets": [],
    }


def _build_parser() -> argparse.ArgumentParser:
    """Mirror the compact CLI flags so --help is safe under `python -I -S`.

    Any unknown arguments are forwarded to the compact engine, which emits
    a typed usage-error condition and exit code 2.
    """
    parser = argparse.ArgumentParser(
        prog="onboard",
        description="Print read-only repository session status.",
        add_help=True,
    )
    parser.add_argument("--json", action="store_true", help="deterministic machine output")
    parser.add_argument("--deep", action="store_true", help="detailed view, same verdict")
    parser.add_argument("--net", action="store_true", help="opt-in non-admission PR context")
    parser.add_argument("--no-net", action="store_true", help="no-op alias; default is network-off")
    parser.add_argument("--require-live", action="store_true", help="required host gaps exit 4")
    parser.add_argument("--fast", action="store_true", help="deprecated alias of the compact default")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="deprecated compatibility no-op; truthful exits are always enabled",
    )
    return parser


def _bootstrap_namespace(name: str, path: Path) -> None:
    """Register a package path without executing its ``__init__.py``."""
    namespace = types.ModuleType(name)
    namespace.__path__ = [str(path)]
    namespace.__package__ = name
    namespace.__spec__ = None  # type: ignore[assignment]
    sys.modules[name] = namespace


def _install_pre311_stdlib_compat() -> list[tuple[Any, str]]:
    """Install only the 3.11 stdlib names used by status dependencies."""
    import datetime as datetime_module
    import enum as enum_module

    installed: list[tuple[Any, str]] = []
    if not hasattr(enum_module, "StrEnum"):
        class StrEnum(str, enum_module.Enum):
            def __str__(self) -> str:
                return str(self.value)

        setattr(enum_module, "StrEnum", StrEnum)
        installed.append((enum_module, "StrEnum"))
    if not hasattr(datetime_module, "UTC"):
        setattr(datetime_module, "UTC", datetime_module.timezone.utc)
        installed.append((datetime_module, "UTC"))
    return installed


def _load_cli_module() -> Any:
    """Load the compact onboarding engine, falling back to a namespace bootstrap.

    Supported interpreters prefer the normal package import.  In minimal or
    pre-3.11 environments (including the macOS system Python), namespace
    packages bypass eager runtime initializers so session status can render
    without importing the full runtime dependency graph.
    """
    # The runtime package requires Python 3.11+, but this public compatibility
    # status command must also run on the macOS system Python. On older interpreters,
    # skip the package initializer entirely: it can fail while evaluating
    # runtime-only type annotations before the ImportError fallback is reached.
    if sys.version_info >= (3, 11):
        try:
            import dharma_swarm.operator_core.onboarding.cli as cli

            return cli
        except (ImportError, ModuleNotFoundError):
            pass

    # Drop any partial initialization from the failed normal import.
    for name in list(sys.modules.keys()):
        if name == "dharma_swarm" or name.startswith("dharma_swarm."):
            del sys.modules[name]

    # Bootstrap every package on the compact status command's import path. In addition
    # to the top-level runtime initializer, onboarding/__init__.py and
    # memory_kernel/__init__.py eagerly import Python-3.11-only runtime code.
    _bootstrap_namespace("dharma_swarm", REPO_ROOT / "dharma_swarm")
    _bootstrap_namespace(
        "dharma_swarm.operator_core",
        REPO_ROOT / "dharma_swarm/operator_core",
    )
    _bootstrap_namespace(
        "dharma_swarm.operator_core.onboarding",
        REPO_ROOT / "dharma_swarm/operator_core/onboarding",
    )
    _bootstrap_namespace(
        "dharma_swarm.memory_kernel",
        REPO_ROOT / "dharma_swarm/memory_kernel",
    )

    installed_compat = _install_pre311_stdlib_compat()
    try:
        import dharma_swarm.operator_core.onboarding.cli as cli
    finally:
        for module, name in reversed(installed_compat):
            delattr(module, name)

    return cli


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    # Handle --help before importing any non-stdlib package.  parse_known_args
    # is used so unknown flags (e.g. a usage-error test) pass through to the
    # compact engine.
    parser.parse_known_args(argv)

    cli = _load_cli_module()
    return cli.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
