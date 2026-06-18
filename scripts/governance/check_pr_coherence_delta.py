#!/usr/bin/env python3
"""Validate the PR-body Coherence Delta fields.

This checker is intentionally small and stdlib-only so it can run early in CI.
It validates that a pull request body contains the four merge-boundary fields
defined in docs/governance/COHERENCE_DELTA.md and that each field has a
substantive answer.
"""

from __future__ import annotations

import argparse
import json
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

# Accepted label variants per canonical field. The gate cares that each
# question is answered, not that the label is typed verbatim.
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "Organ touched": (
        "Organ touched",
        "Organs touched",
        "Organ(s) touched",
    ),
    "Declared-vs-actual gap closed": (
        "Declared-vs-actual gap closed",
        "Declared vs actual gap closed",
        "Declared-vs-actual gap",
        "Gap closed",
    ),
    "Proof that re-reads the map": (
        "Proof that re-reads the map",
        "Proof that rereads the map",
        "Proof",
    ),
    "New drift introduced": (
        "New drift introduced",
        "Drift introduced",
        "New drift",
    ),
}

_ALL_LABELS = tuple(
    label for aliases in FIELD_ALIASES.values() for label in aliases
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


def _label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*:\s*(.*)$"
    )


_STOP_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:"
    + "|".join(re.escape(label) for label in _ALL_LABELS)
    + r")(?:\*\*)?\s*:"
)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_html_comments(text: str) -> str:
    """Drop HTML comments before parsing fields.

    Review bots edit the PR description and inject ``<!-- ... -->`` blocks
    (e.g. Greptile's ``<!-- greptile_comment -->``). Without this, the last
    field's value greedily sweeps those comments in and the gate rejects an
    otherwise-valid block. Substance is preserved: a field whose only content
    was a leftover template hint comment becomes empty and still fails.
    """

    return _HTML_COMMENT_RE.sub("", text)


def extract_field(body: str, field: str) -> str | None:
    """Extract a single Coherence Delta field from a Markdown PR body.

    Accepts any registered label alias for the field.
    """

    body = _strip_html_comments(body)
    match = None
    for label in FIELD_ALIASES.get(field, (field,)):
        match = _label_pattern(label).search(body)
        if match:
            break
    if not match:
        return None

    first_line = match.group(1).strip()
    tail: list[str] = []
    lines = body[match.end() :].splitlines()
    for line in lines:
        stripped = line.strip()
        if _STOP_RE.match(line):
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
    return FieldResult(field, value, True)


def validate_body(body: str) -> list[FieldResult]:
    return [validate_field(body, field) for field in REQUIRED_FIELDS]


def _load_comments(comments_file: str | None) -> list[str]:
    if not comments_file:
        return []
    path = Path(comments_file)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    bodies: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                text = item.get("body")
            else:
                text = item
            if isinstance(text, str) and text.strip():
                bodies.append(text)
    return bodies


def validate_sources(body: str, comments: list[str]) -> tuple[list[FieldResult], str]:
    """Validate the PR body first; fall back to PR comments (latest first).

    A comment containing all four substantive fields satisfies the gate, so
    agents that cannot edit the PR description can still answer the merge
    boundary questions in-thread.
    """

    body_results = validate_body(body)
    if all(result.ok for result in body_results):
        return body_results, "PR body"
    for index, comment in enumerate(reversed(comments)):
        comment_results = validate_body(comment)
        if all(result.ok for result in comment_results):
            return comment_results, f"PR comment #{len(comments) - index}"
    return body_results, "PR body"


_FAIL_TEMPLATE = """
To pass, add this block to the PR body — or, if you cannot edit the body,
post it as a PR comment (the gate accepts either):

## Coherence Delta
- Organ touched: <module(s)/file(s) + architectural layer>
- Declared-vs-actual gap closed: <BR-NNN / MM-NN id + evidence, or 'none — why'>
- Proof that re-reads the map: <what map/check you re-read or ran>
- New drift introduced: <named drift, or 'none'>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body-file", help="Path to a file containing the PR body")
    parser.add_argument("--body", help="PR body text")
    parser.add_argument(
        "--comments-file",
        help="Path to a JSON file of PR comments (list of objects with 'body')",
    )
    args = parser.parse_args(argv)

    body = _read_body(args)
    comments = _load_comments(args.comments_file)
    results, source = validate_sources(body, comments)
    failed = [result for result in results if not result.ok]

    if failed:
        print("Coherence Delta check failed (no valid block in body or comments):")
        for result in failed:
            print(f"- {result.name}: {result.reason}")
        print(_FAIL_TEMPLATE)
        return 1

    print(f"Coherence Delta check passed (source: {source}):")
    for result in results:
        preview = result.value.replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        print(f"- {result.name}: {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
