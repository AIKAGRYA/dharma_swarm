"""Mutation matrix: seven executable bypass mutants must be killed by tests.

Each mutant keeps safety diagnostic strings but disables the executable check
(`if False and ...`). Isolated temp trees run targeted behavioral pytest and
must fail with a real assertion — not collection/import/syntax. Unmutated
helper must pass the same targets.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "scripts" / "governance" / "pr_ci_safe_rebase.py"
BEHAVIORAL = REPO_ROOT / "tests" / "test_pr_ci_safe_rebase.py"
PYTEST = [sys.executable, "-m", "pytest", "-q", "--tb=line"]

FALSE_KILL = re.compile(
    r"ModuleNotFoundError|SyntaxError|ERROR collecting|ImportError|"
    r"No such file or directory|cannot import|FileNotFoundError",
    re.I,
)


@dataclass(frozen=True)
class Mutant:
    name: str
    old: str
    new: str
    targets: tuple[str, ...]


# Exact production snippets (with indent). Mutants retain diagnostic strings.
MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        name="previous_filename_detection_bypass",
        old=(
            '        prev = entry.get("previous_filename")\n'
            "        if isinstance(prev, str) and is_protected_path(prev):\n"
            "            hits.append(prev)\n"
        ),
        new=(
            '        prev = entry.get("previous_filename")\n'
            "        if False and isinstance(prev, str) and is_protected_path(prev):\n"
            "            hits.append(prev)\n"
        ),
        targets=(
            "tests/test_pr_ci_safe_rebase.py::test_rename_away_previous_filename_packet_skips",
            "tests/test_pr_ci_safe_rebase.py::test_page_two_rename_away_previous_filename_packet_skips",
        ),
    ),
    Mutant(
        name="count_mismatch_rejection_bypass",
        old=(
            "    if len(collected) != changed_files:\n"
            "        raise Skip(\n"
            '            f"changed_files count mismatch: metadata={changed_files} "\n'
            '            f"enumerated={len(collected)}"\n'
            "        )\n"
        ),
        new=(
            "    if False and len(collected) != changed_files:\n"
            "        raise Skip(\n"
            '            f"changed_files count mismatch: metadata={changed_files} "\n'
            '            f"enumerated={len(collected)}"\n'
            "        )\n"
        ),
        targets=("tests/test_pr_ci_safe_rebase.py::test_changed_files_count_mismatch_skips",),
    ),
    Mutant(
        name="nonempty_sentinel_rejection_bypass",
        old=(
            "    payload = _fetch_files_page(runner, repo, pr, page)\n"
            "    if payload:\n"
            '        raise Skip(f"nonempty sentinel files page {page}")\n'
        ),
        new=(
            "    payload = _fetch_files_page(runner, repo, pr, page)\n"
            "    if False and payload:\n"
            '        raise Skip(f"nonempty sentinel files page {page}")\n'
        ),
        targets=(
            "tests/test_pr_ci_safe_rebase.py::test_full_final_page_nonempty_sentinel_skips",
            "tests/test_pr_ci_safe_rebase.py::test_zero_changed_files_nonempty_page1_skips",
        ),
    ),
    Mutant(
        name="partial_non_final_page_rejection_bypass",
        old=(
            "        if page < pages_needed and len(payload) != FILES_PER_PAGE:\n"
            '            raise Skip(f"partial non-final files page {page}")\n'
        ),
        new=(
            "        if False and page < pages_needed and len(payload) != FILES_PER_PAGE:\n"
            '            raise Skip(f"partial non-final files page {page}")\n'
        ),
        targets=("tests/test_pr_ci_safe_rebase.py::test_partial_non_final_files_page_skips",),
    ),
    Mutant(
        name="duplicate_filename_rejection_bypass",
        old=(
            "            if filename in seen_names:\n"
            '                raise Skip(f"duplicate filename in files enumeration: {filename!r}")\n'
        ),
        new=(
            "            if False and filename in seen_names:\n"
            '                raise Skip(f"duplicate filename in files enumeration: {filename!r}")\n'
        ),
        targets=("tests/test_pr_ci_safe_rebase.py::test_duplicate_filename_skips",),
    ),
    Mutant(
        name="files_api_return_code_check_bypass",
        old=(
            "    if result.returncode != 0:\n"
            "        raise Skip(\n"
            '            f"files page {page} API failed: "\n'
            "            f\"{result.stderr.strip() or result.returncode}\"\n"
            "        )\n"
        ),
        new=(
            "    if False and result.returncode != 0:\n"
            "        raise Skip(\n"
            '            f"files page {page} API failed: "\n'
            "            f\"{result.stderr.strip() or result.returncode}\"\n"
            "        )\n"
        ),
        targets=("tests/test_pr_ci_safe_rebase.py::test_files_api_nonzero_skips_exact",),
    ),
    Mutant(
        name="files_page_array_shape_check_bypass",
        old=(
            "    if not isinstance(payload, list):\n"
            '        raise Skip(f"files page {page} is not a JSON array")\n'
        ),
        new=(
            "    if False and not isinstance(payload, list):\n"
            '        raise Skip(f"files page {page} is not a JSON array")\n'
        ),
        targets=("tests/test_pr_ci_safe_rebase.py::test_malformed_json_and_entry_shape_skips",),
    ),
)


def _apply_mutant(source: str, mutant: Mutant) -> str:
    if source.count(mutant.old) != 1:
        raise AssertionError(
            f"mutant {mutant.name}: expected 1 site, found {source.count(mutant.old)}"
        )
    out = source.replace(mutant.old, mutant.new, 1)
    if out == source or mutant.new not in out:
        raise AssertionError(f"mutant {mutant.name}: replacement failed")
    return out


def _write_tree(tmp: Path, helper_src: str) -> Path:
    scripts = tmp / "scripts" / "governance"
    tests = tmp / "tests"
    scripts.mkdir(parents=True)
    tests.mkdir(parents=True)
    (scripts / "pr_ci_safe_rebase.py").write_text(helper_src, encoding="utf-8")
    (scripts / "__init__.py").write_text("", encoding="utf-8")
    (tmp / "scripts" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(BEHAVIORAL, tests / "test_pr_ci_safe_rebase.py")
    (tests / "__init__.py").write_text("", encoding="utf-8")
    return tmp


def _run_targets(tree: Path, targets: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*PYTEST, *targets],
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _assert_real_kill(name: str, proc: subprocess.CompletedProcess[str]) -> None:
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode != 0, (
        f"mutant {name} SURVIVED: expected targeted tests to fail\n{combined}"
    )
    assert not FALSE_KILL.search(combined), (
        f"mutant {name} false kill (collection/import/syntax):\n{combined}"
    )
    assert re.search(r"FAILED|AssertionError|assert ", combined), (
        f"mutant {name}: failure output lacks assertion/test identity:\n{combined}"
    )
    assert "test_pr_ci_safe_rebase.py" in combined or "FAILED" in combined, combined


def test_production_snippets_exist_exactly_once() -> None:
    src = HELPER.read_text(encoding="utf-8")
    for m in MUTANTS:
        assert src.count(m.old) == 1, f"{m.name}: site count {src.count(m.old)}"
        assert m.old != m.new
        assert "False and" in m.new


def test_unmutated_helper_passes_targeted_behavioral_tests(tmp_path: Path) -> None:
    src = HELPER.read_text(encoding="utf-8")
    tree = _write_tree(tmp_path / "clean", src)
    targets = tuple(dict.fromkeys(t for m in MUTANTS for t in m.targets))
    proc = _run_targets(tree, targets)
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, f"clean helper failed targeted tests:\n{combined}"


@pytest.mark.parametrize("mutant", MUTANTS, ids=[m.name for m in MUTANTS])
def test_mutant_is_killed_by_targeted_behavioral_tests(
    mutant: Mutant, tmp_path: Path
) -> None:
    src = HELPER.read_text(encoding="utf-8")
    mutated = _apply_mutant(src, mutant)
    tree = _write_tree(tmp_path / mutant.name, mutated)
    proc = _run_targets(tree, mutant.targets)
    _assert_real_kill(mutant.name, proc)


def test_matrix_reports_all_seven_killed(tmp_path: Path) -> None:
    """Aggregate proof: all seven killed; no self-certifying string-only check."""
    src = HELPER.read_text(encoding="utf-8")
    killed: list[str] = []
    for mutant in MUTANTS:
        mutated = _apply_mutant(src, mutant)
        tree = _write_tree(tmp_path / f"agg_{mutant.name}", mutated)
        proc = _run_targets(tree, mutant.targets)
        _assert_real_kill(mutant.name, proc)
        killed.append(mutant.name)
    assert len(killed) == 7
    assert killed == [m.name for m in MUTANTS]
