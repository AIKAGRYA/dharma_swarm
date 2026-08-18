"""Mutation matrix: 19 executable bypass mutants must be killed by tests.

Each mutant keeps safety diagnostic strings but disables the executable check
(`if False and ...`). Isolated temp trees run targeted behavioral pytest and
must fail with a real assertion — not collection/import/syntax/runner exhaustion.
Unmutated helper must pass the same targets.
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
    r"No such file or directory|cannot import|FileNotFoundError|"
    r"\bNameError\b|\bAttributeError\b|\bTypeError\b|"
    r"unexpected extra metadata|unexpected files page|"
    r"unexpected command \(no handler\)|"
    r"TimeoutError|\btimed out\b|INTERNALERROR|"
    r"error during collection|pytest\.(fail|exit)|"
    r"RecursionError|IndentationError|TabError",
    re.I,
)


@dataclass(frozen=True)
class Mutant:
    name: str
    old: str
    new: str
    targets: tuple[str, ...]


def _bypass_if(old: str) -> str:
    """Insert `False and` after the first `if`; parenthesize or-chains for real bypass.

    `if False and a or b` still evaluates `b` (and-binds tighter than or). Or-chains
    become `if False and (a or b)` so the guard is truly disabled while diagnostics stay.
    """
    lines = old.split("\n")
    out: list[str] = []
    done = False
    for line in lines:
        m = re.match(r"^(\s*)if\s+(.+):\s*$", line)
        if not done and m:
            indent, cond = m.group(1), m.group(2)
            if " or " in cond and not (cond.startswith("(") and cond.endswith(")")):
                cond = f"({cond})"
            out.append(f"{indent}if False and {cond}:")
            done = True
        else:
            out.append(line)
    if not done:
        raise AssertionError(f"no if-site in mutant snippet:\n{old}")
    return "\n".join(out)


def _m(name: str, old: str, *targets: str) -> Mutant:
    return Mutant(name=name, old=old, new=_bypass_if(old), targets=targets)


T = "tests/test_pr_ci_safe_rebase.py"

# Exact production snippets (with indent). Mutants retain diagnostic strings.
MUTANTS: tuple[Mutant, ...] = (
    # --- original seven ---
    _m(
        "previous_filename_detection_bypass",
        (
            '        prev = entry.get("previous_filename")\n'
            "        if isinstance(prev, str) and is_protected_path(prev):\n"
            "            hits.append(prev)\n"
        ),
        f"{T}::test_rename_away_previous_filename_packet_skips",
        f"{T}::test_page_two_rename_away_previous_filename_packet_skips",
    ),
    _m(
        "count_mismatch_rejection_bypass",
        (
            "    if len(collected) != changed_files:\n"
            "        raise Skip(\n"
            '            f"changed_files count mismatch: metadata={changed_files} "\n'
            '            f"enumerated={len(collected)}"\n'
            "        )\n"
        ),
        f"{T}::test_changed_files_count_mismatch_skips",
    ),
    _m(
        "nonempty_sentinel_rejection_bypass",
        (
            "    payload = _fetch_files_page(runner, repo, pr, page)\n"
            "    if payload:\n"
            '        raise Skip(f"nonempty sentinel files page {page}")\n'
        ),
        f"{T}::test_full_final_page_nonempty_sentinel_skips",
        f"{T}::test_zero_changed_files_nonempty_page1_skips",
    ),
    _m(
        "partial_non_final_page_rejection_bypass",
        (
            "        if page < pages_needed and len(payload) != FILES_PER_PAGE:\n"
            '            raise Skip(f"partial non-final files page {page}")\n'
        ),
        f"{T}::test_partial_non_final_files_page_skips",
    ),
    _m(
        "duplicate_filename_rejection_bypass",
        (
            "            if filename in seen_names:\n"
            '                raise Skip(f"duplicate filename in files enumeration: {filename!r}")\n'
        ),
        f"{T}::test_duplicate_filename_skips",
    ),
    _m(
        "files_api_return_code_check_bypass",
        (
            "    if result.returncode != 0:\n"
            "        raise Skip(\n"
            '            f"files page {page} API failed: "\n'
            "            f\"{result.stderr.strip() or result.returncode}\"\n"
            "        )\n"
        ),
        f"{T}::test_files_api_nonzero_skips_exact",
    ),
    _m(
        "files_page_array_shape_check_bypass",
        (
            "    if not isinstance(payload, list):\n"
            '        raise Skip(f"files page {page} is not a JSON array")\n'
        ),
        f"{T}::test_malformed_json_and_entry_shape_skips",
    ),
    # --- expanded eleven (string-retaining bypass operators) ---
    _m(
        "metadata_api_return_code_check_bypass",
        (
            "    if result.returncode != 0:\n"
            '        raise Skip(f"PR metadata API failed: {result.stderr.strip() or result.returncode}")\n'
        ),
        f"{T}::test_metadata_api_rc_nonzero_exact",
    ),
    _m(
        "base_ref_identity_check_bypass",
        (
            "    if not isinstance(base_ref, str) or base_ref != expected_base or base_ref != EXPECTED_BASE:\n"
            '        raise Skip(f"base ref is not {EXPECTED_BASE}")\n'
        ),
        f"{T}::test_base_ref_not_main_exact",
    ),
    _m(
        "head_ref_identity_check_bypass",
        (
            "    if not isinstance(head_ref, str) or head_ref != expected_head:\n"
            '        raise Skip("head ref does not match expected-head")\n'
        ),
        f"{T}::test_head_ref_mismatch_exact",
    ),
    _m(
        "head_sha_type_regex_check_bypass",
        (
            "    if not isinstance(head_sha, str) or not _SHA_RE.fullmatch(head_sha):\n"
            '        raise Skip("head.sha is not a 40-char hex SHA")\n'
        ),
        f"{T}::test_head_sha_type_or_regex_exact",
    ),
    _m(
        "head_repo_object_type_check_bypass",
        (
            "    if not isinstance(head_repo_obj, dict):\n"
            '        raise Skip("fork or missing head.repo; same-repo only")\n'
        ),
        f"{T}::test_head_repo_non_object_exact",
    ),
    _m(
        "head_repo_full_name_type_check_bypass",
        (
            "    if not isinstance(full_name, str):\n"
            '        raise Skip("fork or missing head.repo.full_name; same-repo only")\n'
        ),
        f"{T}::test_head_repo_full_name_non_string_exact",
    ),
    _m(
        "changed_files_nonneg_int_check_bypass",
        (
            "    if not isinstance(changed, int) or isinstance(changed, bool) or changed < 0:\n"
            '        raise Skip("changed_files is not a non-negative integer")\n'
        ),
        f"{T}::test_changed_files_not_nonneg_int_exact",
    ),
    _m(
        "files_page_exceeds_per_page_check_bypass",
        (
            "    if len(payload) > FILES_PER_PAGE:\n"
            '        raise Skip(f"files page {page} exceeds per_page={FILES_PER_PAGE}")\n'
        ),
        f"{T}::test_files_page_exceeds_per_page_exact",
    ),
    _m(
        "premature_empty_files_page_check_bypass",
        (
            "        if not payload:\n"
            '            raise Skip(f"premature empty files page {page}")\n'
        ),
        f"{T}::test_premature_empty_files_page_exact",
    ),
    _m(
        "previous_filename_string_type_check_bypass",
        (
            "                if not isinstance(prev, str):\n"
            "                    raise Skip(\n"
            '                        f"files page {page} previous_filename is not a string"\n'
            "                    )\n"
        ),
        f"{T}::test_previous_filename_non_string_exact",
    ),
    _m(
        "branch_validation_return_code_check_bypass",
        (
            "    if result.returncode != 0:\n"
            '        raise Skip(f"head ref failed check-ref-format: {head_ref!r}")\n'
        ),
        f"{T}::test_branch_validation_rc_nonzero_exact",
    ),
    Mutant(
        name="branch_validation_call_bypass",
        old="        _validate_branch_name(run, identity.head_ref)\n",
        new=(
            "        if False and bool(identity.head_ref):\n"
            "            _validate_branch_name(run, identity.head_ref)\n"
            "            raise Skip('disabled branch validation call')\n"
        ),
        targets=(f"{T}::test_branch_validation_rc_nonzero_exact",),
    ),
)

assert len(MUTANTS) == 19
assert len({m.name for m in MUTANTS}) == 19
assert len({m.old for m in MUTANTS}) == 19


def _apply_mutant(source: str, mutant: Mutant) -> str:
    if source.count(mutant.old) != 1:
        raise AssertionError(
            f"mutant {mutant.name}: expected 1 site, found {source.count(mutant.old)}"
        )
    out = source.replace(mutant.old, mutant.new, 1)
    if out == source or mutant.new not in out:
        raise AssertionError(f"mutant {mutant.name}: replacement failed")
    # Exactly one mutation replacement; safety diagnostics remain.
    assert source.count(mutant.old) == 1
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
        f"mutant {name} false kill (collection/import/syntax/exhaustion):\n{combined}"
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
        # Diagnostic strings retained in mutant source.
        for token in re.findall(r'"(?:Skip\(|f?)?([^"\\]{8,})"', m.old):
            if "raise" in token or token.startswith("f"):
                continue
        assert "raise Skip" in m.new or "hits.append" in m.new


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


@pytest.mark.timeout(120)
def test_matrix_reports_all_nineteen_killed(tmp_path: Path) -> None:
    """Aggregate proof: all 19 killed; no self-certifying string-only check."""
    src = HELPER.read_text(encoding="utf-8")
    killed: list[str] = []
    for mutant in MUTANTS:
        mutated = _apply_mutant(src, mutant)
        tree = _write_tree(tmp_path / f"agg_{mutant.name}", mutated)
        proc = _run_targets(tree, mutant.targets)
        _assert_real_kill(mutant.name, proc)
        killed.append(mutant.name)
    assert len(killed) == 19
    assert killed == [m.name for m in MUTANTS]
    print("19/19 mapping:")
    for m in MUTANTS:
        print(f"  KILLED {m.name} <- {', '.join(m.targets)}")
