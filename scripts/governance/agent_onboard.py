#!/usr/bin/env python3
"""agent_onboard.py — the single door any human or agent uses to land in
 the current operating reality of dharma_swarm.

This file is a thin compatibility shim: it parses the public door flags
and delegates to the compact onboarding engine in
`dharma_swarm/operator_core/onboarding/cli.py`.  Strict verdicts and exit
codes are still opt-in (`--strict` or `DHARMA_ONBOARD_STRICT=1`) until
WP-O5.  The legacy v1-only `_receipt_payload` and the canonical
`_parse_broken_register` helpers remain exposed for tests and other
consumers that share the canonical parser.

Exit code:
 - 0 for the default (legacy pre-WP-O5) door, except usage errors (2).
 - The receipt's true exit code when `--strict` / `DHARMA_ONBOARD_STRICT=1`.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

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
        description="Print the current operating reality of dharma_swarm.",
        add_help=True,
    )
    parser.add_argument("--json", action="store_true", help="deterministic machine output")
    parser.add_argument("--deep", action="store_true", help="detailed view, same verdict")
    parser.add_argument("--net", action="store_true", help="opt-in non-admission PR context")
    parser.add_argument("--no-net", action="store_true", help="no-op alias; default is network-off")
    parser.add_argument("--require-live", action="store_true", help="required host gaps exit 4")
    parser.add_argument("--packet", help="Session Entry Packet path to validate and bind")
    parser.add_argument("--fast", action="store_true", help="deprecated alias of the compact default")
    parser.add_argument("--strict", action="store_true", help="strict verdict exits (pre-WP-O5 opt-in)")
    return parser


def _load_cli_module() -> Any:
    """Load the compact onboarding engine, falling back to a namespace bootstrap.

    The compact engine and the onboarding subsystem are stdlib + PyYAML; only
    the top-level ``dharma_swarm/__init__.py`` imports ``pydantic``.  In minimal
    environments (e.g. CI's ``Onboarding admission parity`` job) we bootstrap
    ``dharma_swarm`` as a namespace package so the door can render without
    installing optional runtime dependencies.
    """
    try:
        import dharma_swarm.operator_core.onboarding.cli as cli

        return cli
    except (ImportError, ModuleNotFoundError):
        pass

    # Drop any partial initialization from the failed normal import.
    for name in list(sys.modules.keys()):
        if name == "dharma_swarm" or name.startswith("dharma_swarm."):
            del sys.modules[name]

    # Bootstrap dharma_swarm as a namespace package so __init__.py (which
    # requires pydantic) is not executed; the onboarding modules are loaded from
    # disk through their own __init__.py files.
    namespace = types.ModuleType("dharma_swarm")
    namespace.__path__ = [str(REPO_ROOT / "dharma_swarm")]
    namespace.__package__ = "dharma_swarm"
    namespace.__spec__ = None  # type: ignore[assignment]
    sys.modules["dharma_swarm"] = namespace

    import dharma_swarm.operator_core.onboarding.cli as cli

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
