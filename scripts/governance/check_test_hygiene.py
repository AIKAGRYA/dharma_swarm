"""Test hygiene gate (Rules 3 + 5).

Semgrep auto-excludes the `tests/` directory and we couldn't override
that without invasive CLI changes. These two rules are implemented as
a small Python script instead.

Rule 3 — `dharma.test-no-default-state`:
    Tests must not call `RuntimeStateStore` without a non-None db_path. That
    falls through to the canonical `~/.dharma/state/runtime.db` — the
    operator's REAL DB. Tests must pass a tmp DB:

        store = RuntimeStateStore(db_path=tmp_path / "test.db")

Rule 5 — `dharma.tests-no-dgc-subprocess`:
    Tests must not invoke the `dgc` CLI as a subprocess unless they
    explicitly pass `--state-dir` to redirect mutations away from the
    operator's live state.

Usage:
    python3 scripts/governance/check_test_hygiene.py
    python3 scripts/governance/check_test_hygiene.py --warn-only
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Rule 5: subprocess invocation with "dgc" as the command.
RULE_5_DGC_INVOKE = re.compile(
    r"""
    (?:subprocess\.(?:run|Popen|call|check_call|check_output)\s*\(
      [^)]*?
      ["']dgc["']
      [^)]*?
    \))
    """,
    re.VERBOSE | re.DOTALL,
)
RULE_5_STATE_DIR = re.compile(r"--state[-_]dir")

# Files that may legitimately call RuntimeStateStore without an explicit db_path.
RULE_3_ALLOWLIST: set[str] = set()
RULE_5_ALLOWLIST: set[str] = set()


def _is_runtime_state_store_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == "RuntimeStateStore"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "RuntimeStateStore"
    return False


def _is_none_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _runtime_store_missing_db_path(node: ast.Call) -> bool:
    if not _is_runtime_state_store_call(node):
        return False
    if node.args:
        return _is_none_literal(node.args[0])
    for keyword in node.keywords:
        if keyword.arg == "db_path":
            return _is_none_literal(keyword.value)
    return True


def scan_rule_3(text: str, path: Path) -> list[tuple[int, str]]:
    """Return list of (line_no, line_text) for Rule 3 matches in this file."""
    findings: list[tuple[int, str]] = []
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _runtime_store_missing_db_path(node):
            line_no = getattr(node, "lineno", 1)
            line_text = lines[line_no - 1].rstrip() if 1 <= line_no <= len(lines) else ""
            findings.append((line_no, line_text))
    return findings


def scan_rule_5(text: str, path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for m in RULE_5_DGC_INVOKE.finditer(text):
        # Check if this invocation includes --state-dir.
        if RULE_5_STATE_DIR.search(m.group(0)):
            continue
        # Compute line number.
        line_no = text[: m.start()].count("\n") + 1
        line_text = text.splitlines()[line_no - 1].rstrip()
        findings.append((line_no, line_text))
    return findings


def find_test_files() -> list[Path]:
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        return []
    return sorted(p for p in tests_dir.rglob("*.py") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warn-only", action="store_true",
                        help="Exit 0 even on findings; for advisory mode.")
    args = parser.parse_args()

    rule_3_errs: list[str] = []
    rule_5_errs: list[str] = []

    for path in find_test_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(REPO_ROOT))

        for line_no, line_text in scan_rule_3(text, path):
            if rel in RULE_3_ALLOWLIST:
                continue
            entry = f"  {rel}:{line_no}  {line_text.strip()}"
            rule_3_errs.append(entry)

        for line_no, line_text in scan_rule_5(text, path):
            if rel in RULE_5_ALLOWLIST:
                continue
            rule_5_errs.append(f"  {rel}:{line_no}  {line_text.strip()}")

    print("Test hygiene gate results")
    print("-" * 60)

    if rule_3_errs:
        print()
        print("Rule 3 (test-no-default-state) — FAIL:")
        for e in rule_3_errs:
            print(e)

    if rule_5_errs:
        print()
        print("Rule 5 (tests-no-dgc-subprocess) — FAIL:")
        for e in rule_5_errs:
            print(e)

    if not (rule_3_errs or rule_5_errs):
        print()
        print("No findings.")

    print()
    if args.warn_only:
        return 0
    if rule_3_errs or rule_5_errs:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
