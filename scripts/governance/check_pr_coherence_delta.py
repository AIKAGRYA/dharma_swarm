#!/usr/bin/env python3
"""Validate the PR-body Coherence Delta fields.

This checker is intentionally small and stdlib-only so it can run early in CI.
It validates that a pull request body contains the four merge-boundary fields
defined in docs/governance/COHERENCE_DELTA.md and that each field has a
substantive answer.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_FIELDS = (
    "Organ touched",
    "Declared-vs-actual gap closed",
    "Proof that re-reads the map",
    "New drift introduced",
)

PLACEHOLDER_VALUES = {
    "",
    "n/a",
    "na",
    "none yet",
    "tbd",
    "todo",
    "unknown",
    "fill in",
    "placeholder",
}


@dataclass(frozen=True)
class FieldResult:
    name: str
    value: str
    ok: bool
    reason: str = ""


def _read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if args.body is not None:
        return args.body
    env_body = os.environ.get("PR_BODY")
    if env_body is not None:
        return env_body
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _field_pattern(field: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?{re.escape(field)}(?:\*\*)?\s*:\s*(.*)$"
    )


def extract_field(body: str, field: str) -> str | None:
    """Extract a single Coherence Delta field from a Markdown PR body."""

    match = _field_pattern(field).search(body)
    if not match:
        return None

    first_line = match.group(1).strip()
    tail: list[str] = []
    lines = body[match.end() :].splitlines()
    stop_re = re.compile(
        r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:"
        + "|".join(re.escape(name) for name in REQUIRED_FIELDS)
        + r")(?:\*\*)?\s*:"
    )
    for line in lines:
        stripped = line.strip()
        if stop_re.match(line):
            break
        if stripped.startswith("#"):
            break
        if stripped:
            tail.append(stripped)
    value = "\n".join(part for part in [first_line, *tail] if part).strip()
    return value


def validate_field(body: str, field: str) -> FieldResult:
    value = extract_field(body, field)
    if value is None:
        return FieldResult(field, "", False, "missing field")
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    normalized = normalized.strip("`*_-. ")
    if normalized.startswith("unknown") and len(normalized.split()) < 3:
        return FieldResult(field, value, False, "UNKNOWN requires a reason")
    if normalized in PLACEHOLDER_VALUES:
        return FieldResult(field, value, False, "placeholder value")
    if "<!--" in value and "-->" in value:
        return FieldResult(field, value, False, "comment placeholder left in value")
    return FieldResult(field, value, True)


def validate_body(body: str) -> list[FieldResult]:
    return [validate_field(body, field) for field in REQUIRED_FIELDS]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", help="Path to a file containing the PR body")
    parser.add_argument("--body", help="PR body text")
    args = parser.parse_args(argv)

    body = _read_body(args)
    results = validate_body(body)
    failed = [result for result in results if not result.ok]

    if failed:
        print("Coherence Delta check failed:")
        for result in failed:
            print(f"- {result.name}: {result.reason}")
        print()
        print("Every PR body must answer:")
        for field in REQUIRED_FIELDS:
            print(f"- {field}:")
        return 1

    print("Coherence Delta check passed:")
    for result in results:
        preview = result.value.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        print(f"- {result.name}: {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
