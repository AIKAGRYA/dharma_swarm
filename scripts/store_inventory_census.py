#!/usr/bin/env python3
"""Store-inventory census — one legible, ratcheting map of every persistence
store name referenced in non-test source.

Why this exists
---------------
The repository's felt incoherence is *proliferation*: many subsystems each
opened their own SQLite database, JSONL ledger, or append log with no shared
schema or spine. You cannot collapse stores you cannot see. This census makes
the full set visible in one committed artifact and gates it with a ratchet so
the count can only go DOWN — every new store is a deliberate, reviewable edit,
and every consolidation shows up as a falling number.

Method (honest limits)
----------------------
This is a LEXICAL census, not a live-writer trace. It scans tracked ``*.py``
files under the non-test source roots for SQLite name literals
(``*.db`` / ``*.sqlite`` / ``*.sqlite3``) and ``*.jsonl`` literals **inside
string quotes** (so an attribute access like ``args.db`` is never matched), and
for ``class *Ledger`` declarations (including a class literally named
``Ledger``). Exclusion is by FILE only (test trees + test-named modules via
``_is_source``) — never by store NAME, so a production store named e.g.
``lattice_test.db`` is still counted. It deliberately does NOT resolve
path-builder variables (most live DBs open via a resolver function, e.g.
``root / "state" / "runtime.db"``), so a name that only ever appears as a
resolver output is counted once by its literal. The committed artifact records
only sorted NAMES and counts — never line numbers — so it changes when a store
is added or removed, not when unrelated code moves.

Usage
-----
    python3 scripts/store_inventory_census.py            # print JSON to stdout
    python3 scripts/store_inventory_census.py --write    # write the artifact
    python3 scripts/store_inventory_census.py --check     # exit 1 if stale
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = REPO_ROOT / "reports" / "governance" / "store_inventory_census.json"
_GENERATOR_REL = "scripts/store_inventory_census.py"

# Non-test source roots. A store literal only counts if it is referenced from
# source that ships and runs — test fixtures (tests/**) are excluded so the
# ratchet tracks production proliferation, not test scaffolding.
SOURCE_ROOTS = ("dharma_swarm/", "api/", "scripts/", "tools/")

# Directory segments that mark a test tree. A file under any of these is
# excluded so test fixtures never count as production stores.
_EXCLUDED_DIR_SEGMENTS = ("tests", "test")

# Store names are matched ONLY inside string literals, so an attribute access
# such as ``args.db`` in CLI code is never mistaken for a database. Both common
# SQLite suffixes count (.db / .sqlite / .sqlite3). Exclusion is by FILE (see
# _is_source) — never by store NAME, so a production store named e.g.
# ``lattice_test.db`` is still counted.
_DB_RE = re.compile(r"""['"]([^'"\s]*?[A-Za-z0-9_]\.(?:db|sqlite|sqlite3))['"]""")
_JSONL_RE = re.compile(r"""['"]([^'"\s]*?[A-Za-z0-9_]\.jsonl)['"]""")
# ``\w*Ledger`` matches a class literally named ``Ledger`` (zero leading
# characters) as well as ``SessionLedger`` etc.
_LEDGER_CLASS_RE = re.compile(r"^\s*class\s+(\w*Ledger)\b", re.MULTILINE)


def _git_tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def _is_source(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    # The census must never scan ITSELF: this generator necessarily contains
    # store-name literals as regexes, docstrings, and examples, which would be
    # counted as real stores (self-referential contamination).
    if path == _GENERATOR_REL:
        return False
    if not any(path.startswith(root) for root in SOURCE_ROOTS):
        return False
    segments = path.split("/")
    # Exclude anything under a tests/ directory tree ...
    if any(seg in _EXCLUDED_DIR_SEGMENTS for seg in segments):
        return False
    # ... AND test modules identified by filename, which live alongside source
    # (e.g. scripts/mirror_test.py, self_optimization/test_swarm_jikoku.py).
    # Segment-only matching missed these, leaking fixture store names such as
    # mirror_test.db / swarm_test.jsonl into the production count.
    base = segments[-1]
    if base == "conftest.py" or base.startswith("test_") or base.endswith("_test.py"):
        return False
    return True


def build_inventory() -> dict:
    """Return the deterministic store inventory as a plain dict."""
    db_names: set[str] = set()
    jsonl_names: set[str] = set()
    ledger_modules: set[str] = set()
    ledger_classes: set[str] = set()

    for rel in _git_tracked():
        if not _is_source(rel):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        # Normalize to the BASENAME: two literals that differ only by path
        # prefix (``state/runtime.db`` vs ``DHARMA_STATE_DIR/runtime.db``)
        # name the same logical store and must count once. Exclusion is by
        # FILE only (a store referenced from non-test source is real, whatever
        # it is named), so no name-based filtering happens here.
        for match in _DB_RE.findall(text):
            db_names.add(match.rsplit("/", 1)[-1])
        for match in _JSONL_RE.findall(text):
            jsonl_names.add(match.rsplit("/", 1)[-1])
        if rel.endswith("_ledger.py"):
            ledger_modules.add(rel)
        for cls in _LEDGER_CLASS_RE.findall(text):
            ledger_classes.add(cls)

    databases = sorted(db_names)
    jsonl_targets = sorted(jsonl_names)
    modules = sorted(ledger_modules)
    classes = sorted(ledger_classes)
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "scripts/store_inventory_census.py",
        "method": "lexical name-literal scan of non-test *.py; not a live-writer trace",
        "source_roots": list(SOURCE_ROOTS),
        "summary": {
            "distinct_db_names": len(databases),
            "distinct_jsonl_names": len(jsonl_targets),
            "ledger_modules": len(modules),
            "ledger_classes": len(classes),
        },
        "databases": databases,
        "jsonl_targets": jsonl_targets,
        "ledger_modules": modules,
        "ledger_classes": classes,
    }


def render_inventory() -> str:
    """Deterministic JSON text (sorted keys, trailing newline)."""
    return json.dumps(build_inventory(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the artifact")
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the committed artifact is stale"
    )
    args = parser.parse_args(argv)

    rendered = render_inventory()
    if args.write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {ARTIFACT_PATH.relative_to(REPO_ROOT)}")
        return 0
    if args.check:
        if not ARTIFACT_PATH.is_file():
            print("store_inventory_census.json missing; run --write", file=sys.stderr)
            return 1
        if ARTIFACT_PATH.read_text(encoding="utf-8") != rendered:
            print("store_inventory_census.json is stale; run --write", file=sys.stderr)
            return 1
        print("store inventory census is current")
        return 0
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
