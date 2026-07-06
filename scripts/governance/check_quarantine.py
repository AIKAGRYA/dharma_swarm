#!/usr/bin/env python3
"""Quarantine-list gate for the nightly full-suite lane.

tests/QUARANTINE.txt holds flaky tests deselected from the nightly run
(one pytest test-id per line). Quarantine is meant to be temporary, so
every entry must carry a tracking issue and an absolute expiry date, and
the list has a hard cap. This gate keeps the file from becoming a
graveyard:

    - entry without an ``issue:`` reference        -> FAIL
    - entry without an ``expiry:YYYY-MM-DD`` date  -> FAIL
    - entry whose expiry date has passed           -> FAIL
    - more than MAX_ENTRIES (15) entries           -> FAIL

Entry format (comment is required):

    tests/test_foo.py::test_bar  # quarantined 2026-07-04 issue:#123 owner:name expiry:2026-07-18

Usage:
    python3 scripts/governance/check_quarantine.py
    python3 scripts/governance/check_quarantine.py --emit-deselect
    python3 scripts/governance/check_quarantine.py --file <path> --today 2026-07-04

--emit-deselect validates the file and, on success, prints one
``--deselect=<test-id>`` argument per entry (nothing when empty) so the
nightly workflow consumes the same parse this gate enforces.

Exit codes:
    0   list valid (possibly empty)
    1   at least one violation
    2   environment error (file unreadable)

Policy source: dive_test_depth.md section 4b (flake policy mechanics).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_FILE = REPO_ROOT / "tests" / "QUARANTINE.txt"
MAX_ENTRIES = 15

ISSUE_RE = re.compile(r"issue:(\S+)")
EXPIRY_RE = re.compile(r"expiry:(\S+)")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_entries(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return (test_ids, violations) for the given file lines."""
    test_ids: list[str] = []
    violations: list[str] = []

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        entry, sep, comment = stripped.partition("#")
        test_id = entry.strip()
        if not test_id:
            continue

        where = f"line {lineno}: {test_id}"

        if "::" not in test_id:
            violations.append(
                f"{where} — not a pytest test id (expected path::test form)"
            )

        if not sep:
            violations.append(
                f"{where} — missing trailing comment with issue: and expiry:"
            )
            test_ids.append(test_id)
            continue

        if not ISSUE_RE.search(comment):
            violations.append(f"{where} — missing issue:<ref> in comment")

        expiry_match = EXPIRY_RE.search(comment)
        if not expiry_match:
            violations.append(f"{where} — missing expiry:YYYY-MM-DD in comment")
        else:
            expiry_raw = expiry_match.group(1)
            if not DATE_RE.match(expiry_raw):
                violations.append(
                    f"{where} — expiry must be an absolute YYYY-MM-DD date, "
                    f"got {expiry_raw!r}"
                )
            else:
                expiry_date = _dt.date.fromisoformat(expiry_raw)
                if expiry_date < _today():
                    violations.append(
                        f"{where} — EXPIRED {expiry_raw}: fix the test or "
                        "re-quarantine with a new issue-justified expiry"
                    )

        test_ids.append(test_id)

    if len(test_ids) > MAX_ENTRIES:
        violations.append(
            f"quarantine cap exceeded: {len(test_ids)} entries > "
            f"{MAX_ENTRIES} cap — a growing quarantine is a system signal, "
            "fix flakes before adding more"
        )

    return test_ids, violations


_TODAY_OVERRIDE: _dt.date | None = None


def _today() -> _dt.date:
    if _TODAY_OVERRIDE is not None:
        return _TODAY_OVERRIDE
    return _dt.datetime.now(_dt.timezone.utc).date()


def main(argv: list[str] | None = None) -> int:
    global _TODAY_OVERRIDE

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help=f"quarantine list path (default: {DEFAULT_FILE})",
    )
    parser.add_argument(
        "--today",
        help="override today's date (YYYY-MM-DD, UTC) — for testing",
    )
    parser.add_argument(
        "--emit-deselect",
        action="store_true",
        help="on success, print one --deselect=<id> per entry to stdout",
    )
    args = parser.parse_args(argv)

    if args.today:
        _TODAY_OVERRIDE = _dt.date.fromisoformat(args.today)

    try:
        lines = args.file.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"check_quarantine: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    test_ids, violations = parse_entries(lines)

    if violations:
        print(f"check_quarantine: FAIL — {args.file}", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1

    if args.emit_deselect:
        for test_id in test_ids:
            print(f"--deselect={test_id}")
    else:
        print(
            f"check_quarantine: OK — {len(test_ids)} quarantined "
            f"(cap {MAX_ENTRIES})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
