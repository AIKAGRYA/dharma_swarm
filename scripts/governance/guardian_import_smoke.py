#!/usr/bin/env python3
"""Guardian import-smoke gate (fail-closed, AI-N1).

Imports each critical module and FAILS (exit 2) if any critical module cannot
be imported -- unless the failure is a *named, declared optional dependency*
being absent.

The optional-dependency allowance is an allowlist by top-level module NAME,
sourced from the repository's own dependency manifest
(``scripts/governance/import_provenance_allowlist.txt``). It is never a
substring match on the exception text. A substring match on ``No module
named`` forgives ``No module named 'dharma_swarm.world_actions'`` -- i.e. the
critical module itself is gone -- and lets a dead critical module report a
green import-smoke. That green-on-nothing outcome is the exact failure this
gate exists to catch (invariant AI-N1: absence is never green).

``dharma_swarm`` is never in the manifest allowlist, so a missing critical
module or a missing first-party submodule always fails closed.

Usage::

    python3 scripts/governance/guardian_import_smoke.py
    python3 scripts/governance/guardian_import_smoke.py --module pkg.a --module pkg.b
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from fail_closed import NakedGreenError, emit_verdict  # noqa: E402

GATE = "guardian-import-smoke"

ALLOWLIST_PATH = _HERE / "import_provenance_allowlist.txt"

# The critical first-party modules whose import must never silently break.
CRITICAL_MODULES = (
    "dharma_swarm.world_actions",
    "dharma_swarm.dgm_loop",
    "dharma_swarm.archaeology_ingestion",
    "dharma_swarm.guardian_crew",
    "dharma_swarm.gnani_lodestone",
    "dharma_swarm.swarm_health_api",
)


def load_optional_allowlist(path: Path | None = None) -> frozenset[str]:
    """Load the declared third-party top-level roots from the manifest.

    These are the names whose absence at runtime is an optional-dependency
    condition rather than a broken critical module. Comment and blank lines
    are ignored.
    """

    path = path or ALLOWLIST_PATH
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.add(stripped)
    return frozenset(names)


def is_optional_absence(exc: BaseException, allowlist: frozenset[str]) -> bool:
    """True only if ``exc`` is a named, allowlisted optional dependency absence.

    Matched by the top-level root of ``ModuleNotFoundError.name`` against the
    allowlist -- never by a substring of the message. Any other import error
    (a missing first-party submodule, a broken C extension, a circular import,
    a syntax error surfaced at import) is treated as a real failure.
    """

    if not isinstance(exc, ModuleNotFoundError):
        return False
    missing = getattr(exc, "name", None)
    if not missing:
        return False
    root = missing.split(".", 1)[0]
    return root in allowlist


def run_smoke(
    modules: tuple[str, ...] | list[str],
    *,
    allowlist: frozenset[str] | None = None,
) -> int:
    """Import each module; return 0 only if every one is OK or an optional skip.

    Returns 2 on any real import failure, and 2 on a naked-green verdict
    (nothing measured), per AI-N1.
    """

    if allowlist is None:
        allowlist = load_optional_allowlist()

    measured = 0
    failures: list[str] = []
    for module in modules:
        try:
            importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 -- any import error is in scope
            if is_optional_absence(exc, allowlist):
                measured += 1
                print(f"SKIP (optional dep absent): {module} -- {exc}")
                continue
            failures.append(f"{module}: {exc!r}")
            print(f"FAIL: {module} -- {exc!r}")
            continue
        measured += 1
        print(f"OK: {module}")

    green = not failures
    try:
        emit_verdict(gate=GATE, green=green, items_measured=measured)
    except NakedGreenError as exc:
        print(f"FAIL: {exc}")
        return 2

    if failures:
        print(f"{GATE}: {len(failures)} critical module(s) failed to import")
        return 2
    print(f"{GATE}: OK ({measured} module(s) measured, 0 failures)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        action="append",
        dest="modules",
        help="Override the critical module list (repeatable). Defaults to the "
        "built-in CRITICAL_MODULES.",
    )
    args = parser.parse_args(argv)
    modules = tuple(args.modules) if args.modules else CRITICAL_MODULES
    return run_smoke(modules)


if __name__ == "__main__":
    raise SystemExit(main())
