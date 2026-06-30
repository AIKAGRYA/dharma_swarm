#!/usr/bin/env python3
"""Spec §8 anti-gaming checklist for fix diffs.

Deterministic checks on a fix diff to prevent reward hacking. The classic
failure of an auto-fixer is making the auditor happy by deleting the failing
test, adding a skip/xfail, or weakening an assertion. This module runs those
checks against the fix diff itself (not the original code).

A violation REJECTS the fix (non-zero exit, archived with evidence) — not
merely flagged (spec §8, VAL-REMEDIATE-012).

Checklist items:
  - no_new_skips: no new pytest skip markers introduced by the fix
  - no_new_xfails: no new pytest.xfail markers introduced by the fix
  - no_weakened_assertions: no assertions weakened or removed
  - no_deleted_tests: no test functions deleted
  - no_widened_budgets: no grandfather budgets/thresholds widened
  - fix_addresses_root_cause: fix targets root cause, not symptom

Usage:
    python3 scripts/governance/loop/anti_gaming.py <diff_file>

Exit codes:
    0   all checklist items pass
    1   at least one checklist item failed (REJECT the fix)
    2   hard error (diff file unreadable)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKIP_PATTERNS: tuple[str, ...] = (
    r"pytest\.skip",
    r"pytestmark\s*=\s*pytest\.mark\.skip\b",
    r"pytest\.mark\.skip\b",
    r"@pytest\.mark\.skip\b",
    r"@pytest\.mark\.skipif",
    r"unittest\.skip",
    r"\.skipTest\b",
)

XFAIL_PATTERNS: tuple[str, ...] = (
    r"pytestmark\s*=\s*pytest\.mark\.xfail\b",
    r"pytest\.mark\.xfail",
    r"pytest\.xfail",
    r"@unittest\.expectedFailure",
    r"expected_failure",
)

TEST_DEF_RE = re.compile(r"^\s*def\s+test_\w+")
ASSERT_RE = re.compile(r"\bassert\b")
BUDGET_KEY_RE = re.compile(
    r"(budget|threshold|max_\w+|grandfather|allowlist_\w+|tolerance)\s*[:=]\s*(\d+)",
    re.IGNORECASE,
)


@dataclass
class ChecklistItem:
    """A single anti-gaming checklist item with a pass/fail verdict."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class AntiGamingResult:
    """The full anti-gaming checklist result for a fix diff."""

    items: list[ChecklistItem] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.items)

    def to_dict(self) -> dict[str, str]:
        return {item.name: ("pass" if item.passed else "fail") for item in self.items}

    def failures(self) -> list[ChecklistItem]:
        return [item for item in self.items if not item.passed]


# ---------------------------------------------------------------------------
# Diff line extraction
# ---------------------------------------------------------------------------


def _extract_added_lines(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            lines.append(line[1:])
    return lines


def _extract_removed_lines(diff: str) -> list[str]:
    lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            lines.append(line[1:])
    return lines


def _extract_changed_files(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
        elif line.startswith("+++ /dev/null"):
            if line.startswith("--- a/"):
                files.append(line[6:])
    return files


# ---------------------------------------------------------------------------
# Individual checklist items
# ---------------------------------------------------------------------------


def _check_no_new_skips(added: list[str]) -> ChecklistItem:
    for line in added:
        for pattern in SKIP_PATTERNS:
            if re.search(pattern, line):
                return ChecklistItem(
                    "no_new_skips",
                    False,
                    f"new skip introduced: {line.strip()!r}",
                )
    return ChecklistItem("no_new_skips", True)


def _check_no_new_xfails(added: list[str]) -> ChecklistItem:
    for line in added:
        for pattern in XFAIL_PATTERNS:
            if re.search(pattern, line):
                return ChecklistItem(
                    "no_new_xfails",
                    False,
                    f"new xfail introduced: {line.strip()!r}",
                )
    return ChecklistItem("no_new_xfails", True)


def _check_no_weakened_assertions(added: list[str], removed: list[str]) -> ChecklistItem:
    removed_assert_lines = [line for line in removed if ASSERT_RE.search(line)]
    added_assert_lines = [line for line in added if ASSERT_RE.search(line)]
    removed_asserts = len(removed_assert_lines)
    added_asserts = len(added_assert_lines)
    if removed_asserts > added_asserts:
        return ChecklistItem(
            "no_weakened_assertions",
            False,
            f"assertions weakened: removed {removed_asserts} assert lines, added {added_asserts}",
        )
    if removed_assert_lines and added_assert_lines:
        trivial = [line for line in added_assert_lines if _is_trivial_assert(line)]
        if trivial:
            return ChecklistItem(
                "no_weakened_assertions",
                False,
                f"assertions weakened: replaced specific assertion with trivial assertion {trivial[0].strip()!r}",
            )
    return ChecklistItem("no_weakened_assertions", True)


def _is_trivial_assert(line: str) -> bool:
    text = line.strip()
    return bool(re.fullmatch(r"assert\s+(True|1|not\s+False)(\s*(,|#).*)?", text))


def _check_no_deleted_tests(removed: list[str], added: list[str]) -> ChecklistItem:
    removed_tests = sum(1 for line in removed if TEST_DEF_RE.match(line))
    added_tests = sum(1 for line in added if TEST_DEF_RE.match(line))
    if removed_tests > added_tests:
        return ChecklistItem(
            "no_deleted_tests",
            False,
            f"tests deleted: removed {removed_tests} test definitions, added {added_tests}",
        )
    return ChecklistItem("no_deleted_tests", True)


def _check_no_widened_budgets(added: list[str], removed: list[str]) -> ChecklistItem:
    removed_budgets: dict[str, int] = {}
    for line in removed:
        match = BUDGET_KEY_RE.search(line)
        if match:
            removed_budgets[match.group(1).lower()] = int(match.group(2))

    for line in added:
        match = BUDGET_KEY_RE.search(line)
        if match:
            key = match.group(1).lower()
            new_val = int(match.group(2))
            old_val = removed_budgets.get(key)
            if old_val is not None and new_val > old_val:
                return ChecklistItem(
                    "no_widened_budgets",
                    False,
                    f"budget widened: {key} {old_val} -> {new_val}",
                )
    return ChecklistItem("no_widened_budgets", True)


def _check_fix_addresses_root_cause(
    diff_text: str,
    finding: dict | None = None,
) -> ChecklistItem:
    changed_files = _extract_changed_files(diff_text)
    if not changed_files:
        return ChecklistItem(
            "fix_addresses_root_cause",
            False,
            "empty diff — no fix applied",
        )

    if finding:
        finding_files = finding.get("files", [])
        if finding_files:
            touched = any(
                cf == ff or ff in cf or cf in ff
                for cf in changed_files
                for ff in finding_files
            )
            if not touched:
                return ChecklistItem(
                    "fix_addresses_root_cause",
                    False,
                    f"fix touches {changed_files} but finding names {finding_files}",
                )

    return ChecklistItem("fix_addresses_root_cause", True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_anti_gaming_check(
    diff_text: str,
    finding: dict | None = None,
) -> AntiGamingResult:
    """Run the full §8 anti-gaming checklist on a fix diff.

    Returns an AntiGamingResult with one ChecklistItem per checklist entry.
    ``result.passed`` is True only if every item passed. A failure means the
    fix should be REJECTED (not merely flagged).
    """
    added = _extract_added_lines(diff_text)
    removed = _extract_removed_lines(diff_text)

    items = [
        _check_no_new_skips(added),
        _check_no_new_xfails(added),
        _check_no_weakened_assertions(added, removed),
        _check_no_deleted_tests(removed, added),
        _check_no_widened_budgets(added, removed),
        _check_fix_addresses_root_cause(diff_text, finding),
    ]
    return AntiGamingResult(items=items)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the §8 anti-gaming checklist on a fix diff. A violation REJECTS the fix.",
    )
    parser.add_argument("diff_file", help="path to a unified diff file to check")
    args = parser.parse_args(argv)

    diff_path = Path(args.diff_file)
    if not diff_path.is_file():
        return _emit_error(f"diff file not found: {diff_path}")

    try:
        diff_text = diff_path.read_text()
    except OSError as exc:
        return _emit_error(f"cannot read diff file: {exc}")

    result = run_anti_gaming_check(diff_text)
    json.dump(result.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if not result.passed:
        for failure in result.failures():
            sys.stderr.write(f"REJECT: {failure.name} — {failure.detail}\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
