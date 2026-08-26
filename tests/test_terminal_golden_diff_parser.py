"""Contract for Helm's Semgrep-safe golden-diff parameter expansion."""

from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIFF = REPO_ROOT / "terminal/scripts/golden_diff.sh"
PARSER_SAFE_EXPANSION = r"firstpath=${first%%\(*}"
UNESCAPED_EXPANSION = "firstpath=${first%%(*}"


def test_golden_diff_uses_parser_safe_literal_parenthesis() -> None:
    text = GOLDEN_DIFF.read_text(encoding="utf-8")

    assert text.count(PARSER_SAFE_EXPANSION) == 1
    assert UNESCAPED_EXPANSION not in text

    syntax = subprocess.run(
        ["bash", "-n", str(GOLDEN_DIFF)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_escaped_parameter_pattern_preserves_bash_results() -> None:
    probe = r"""
set -euo pipefail
for value in "$@"; do
  original=${value%%(*}
  parser_safe=${value%%\(*}
  [[ "$original" == "$parser_safe" ]] || exit 7
done
"""
    values = [
        "80x24/chat.txt(missing-from-fresh-capture)",
        "120x40/repo.txt",
        "a(b)c",
        "(",
    ]

    result = subprocess.run(
        ["bash", "-c", probe, "golden-diff-contract", *values],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
