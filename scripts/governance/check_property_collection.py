#!/usr/bin/env python3
"""Property-test collection gate (TV-01 / F2).

Every file under ``tests/properties`` guards its Hypothesis import with
``pytest.importorskip("hypothesis", ...)``. If Hypothesis is not installed, all
those modules SKIP at collection time and the suite stays green while the entire
property-based test layer silently vanishes — exactly the "green from
uncollected illusion" slop class.

This gate is fail-closed: whenever the properties directory is non-empty it
asserts BOTH

1. ``import hypothesis`` succeeds in the test interpreter, and
2. ``pytest --collect-only`` on that directory collects > 0 items.

If the directory is empty (or absent) there is nothing to protect and the gate
passes. The moment property tests exist, they must actually be collectable —
they may not quietly disappear behind a guarded import.

Usage:
    python3 scripts/governance/check_property_collection.py
    python3 scripts/governance/check_property_collection.py --properties-dir DIR
    python3 scripts/governance/check_property_collection.py --json

Exit codes:
    0   properties dir empty, OR hypothesis imports and collection > 0
    1   non-empty properties dir but hypothesis missing or 0 items collected
    2   environment error
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_PROPERTIES_REL = "tests/properties"
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")


def repo_root() -> Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
    return Path(out)


def count_test_modules(properties_dir: Path) -> int:
    if not properties_dir.is_dir():
        return 0
    return sum(
        1
        for p in properties_dir.rglob("test_*.py")
        if p.is_file()
    )


def hypothesis_importable() -> bool:
    return importlib.util.find_spec("hypothesis") is not None


def collected_item_count(properties_dir: Path, root: Path) -> int:
    """Run pytest --collect-only against the dir and parse the collected count.

    A module-level ``importorskip`` on a missing dependency makes the module
    skip at collection time and contribute zero collected items, which is the
    precise failure signature this gate exists to catch.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            str(properties_dir),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    matches = _COLLECTED_RE.findall(out)
    if not matches:
        return 0
    return max(int(m) for m in matches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument(
        "--properties-dir",
        default=None,
        help="Override the properties directory (default: tests/properties).",
    )
    args = parser.parse_args(argv)

    try:
        root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"property-collection: environment error: {exc}", file=sys.stderr)
        return 2

    properties_dir = (
        Path(args.properties_dir).resolve()
        if args.properties_dir
        else root / DEFAULT_PROPERTIES_REL
    )

    module_count = count_test_modules(properties_dir)
    if module_count == 0:
        msg = (
            f"property-collection: OK — no property test modules under "
            f"{properties_dir}; nothing to protect."
        )
        if args.json:
            print(json.dumps({
                "properties_dir": str(properties_dir),
                "module_count": 0,
                "hypothesis_importable": hypothesis_importable(),
                "collected": 0,
                "status": "ok_empty",
            }, indent=2, sort_keys=True))
        else:
            print(msg)
        return 0

    hyp_ok = hypothesis_importable()
    collected = collected_item_count(properties_dir, root)
    failed = (not hyp_ok) or collected <= 0

    if args.json:
        print(json.dumps({
            "properties_dir": str(properties_dir),
            "module_count": module_count,
            "hypothesis_importable": hyp_ok,
            "collected": collected,
            "status": "fail" if failed else "ok",
        }, indent=2, sort_keys=True))
        return 1 if failed else 0

    if not failed:
        print(
            f"property-collection: OK — {module_count} property module(s), "
            f"hypothesis importable, {collected} item(s) collected."
        )
        return 0

    print(
        f"::error::property-collection — {module_count} property test module(s) "
        f"exist under {properties_dir} but they are not being exercised:"
    )
    if not hyp_ok:
        print(
            "  hypothesis is NOT importable — every property module guarded by "
            "importorskip('hypothesis') silently skips. Install the 'dev' extra "
            "(pip install -e '.[dev]') so property tests run."
        )
    if collected <= 0:
        print(
            f"  pytest --collect-only collected {collected} item(s) from a "
            f"non-empty properties dir — property tests are vanishing from "
            f"collection (a guarded import or skip is hiding them)."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
