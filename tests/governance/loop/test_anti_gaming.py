"""Tests for scripts/governance/loop/anti_gaming.py — the §8 anti-gaming checklist.

Covers the six checklist items that run on a fix diff:
  no_new_skips, no_new_xfails, no_weakened_assertions, no_deleted_tests,
  no_widened_budgets, fix_addresses_root_cause.

A violation REJECTS the fix (non-zero exit, archived with evidence), not merely
flagged (VAL-REMEDIATE-007, VAL-REMEDIATE-012, VAL-REMEDIATE-013).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = sys.executable
ANTI_GAMING_CLI = REPO_ROOT / "scripts" / "governance" / "loop" / "anti_gaming.py"

CHECKLIST_ITEMS = [
    "no_new_skips",
    "no_new_xfails",
    "no_weakened_assertions",
    "no_deleted_tests",
    "no_widened_budgets",
    "fix_addresses_root_cause",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_check(diff_text: str, finding: dict | None = None):
    """Call run_anti_gaming_check directly and return the result."""
    from scripts.governance.loop.anti_gaming import run_anti_gaming_check

    return run_anti_gaming_check(diff_text, finding=finding)


def _run_cli(diff_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [VENV_PYTHON, str(ANTI_GAMING_CLI), str(diff_path)],
        capture_output=True,
        text=True,
        env=env,
    )


def _clean_diff() -> str:
    """A diff that adds a new source file — should pass all checklist items."""
    return textwrap.dedent("""\
        diff --git a/scripts/governance/loop/new_helper.py b/scripts/governance/loop/new_helper.py
        new file mode 100644
        index 0000000..1111111
        --- /dev/null
        +++ b/scripts/governance/loop/new_helper.py
        @@ -0,0 +1,3 @@
        +def helper():
        +    return 42
        +
        """)


# ---------------------------------------------------------------------------
# All items present
# ---------------------------------------------------------------------------


def test_checklist_has_all_six_items():
    """VAL-REMEDIATE-013: the checklist includes fix_addresses_root_cause and all items."""
    result = _run_check(_clean_diff())
    names = [item.name for item in result.items]
    for expected in CHECKLIST_ITEMS:
        assert expected in names, f"checklist missing item: {expected}"


def test_clean_diff_passes_all():
    """A diff with no gaming patterns passes every checklist item."""
    result = _run_check(_clean_diff())
    assert result.passed, f"clean diff should pass: {result.to_dict()}"
    for item in result.items:
        assert item.passed, f"{item.name} should pass on clean diff: {item.detail}"


# ---------------------------------------------------------------------------
# no_new_skips
# ---------------------------------------------------------------------------


def test_new_skip_fails():
    """Adding pytest.skip or @pytest.mark.skip fails no_new_skips."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,4 @@
         def test_a():
        +    pytest.skip("not ready")
             assert True
        """)
    result = _run_check(diff)
    assert not result.passed
    skip_item = next(i for i in result.items if i.name == "no_new_skips")
    assert not skip_item.passed


def test_new_skipif_fails():
    """Adding @pytest.mark.skipif fails no_new_skips."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,5 @@
        +@pytest.mark.skipif(True, reason="flaky")
         def test_a():
             assert True
        """)
    result = _run_check(diff)
    skip_item = next(i for i in result.items if i.name == "no_new_skips")
    assert not skip_item.passed


def test_module_level_pytestmark_skip_fails():
    """Adding pytestmark = pytest.mark.skip(...) fails no_new_skips."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,2 +1,3 @@
         import pytest
        +pytestmark = pytest.mark.skip(reason="not now")
         def test_a():
        """)
    result = _run_check(diff)
    skip_item = next(i for i in result.items if i.name == "no_new_skips")
    assert not skip_item.passed


# ---------------------------------------------------------------------------
# no_new_xfails
# ---------------------------------------------------------------------------


def test_new_xfail_fails():
    """Adding @pytest.mark.xfail fails no_new_xfails."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,4 @@
        +@pytest.mark.xfail(reason="known issue")
         def test_a():
             assert True
        """)
    result = _run_check(diff)
    xfail_item = next(i for i in result.items if i.name == "no_new_xfails")
    assert not xfail_item.passed


# ---------------------------------------------------------------------------
# no_weakened_assertions
# ---------------------------------------------------------------------------


def test_removed_assert_fails():
    """Removing an assert line without replacement fails no_weakened_assertions."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,2 @@
         def test_a():
        -    assert result == 42
             pass
        """)
    result = _run_check(diff)
    weak_item = next(i for i in result.items if i.name == "no_weakened_assertions")
    assert not weak_item.passed


def test_replaced_assert_passes():
    """Replacing an assert with an equal-or-stronger assert passes."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,3 @@
         def test_a():
        -    assert result == 42
        +    assert result == 42 and result > 0
             pass
        """)
    result = _run_check(diff)
    weak_item = next(i for i in result.items if i.name == "no_weakened_assertions")
    assert weak_item.passed, f"replaced assert should pass: {weak_item.detail}"


def test_replaced_specific_assert_with_assert_true_fails():
    """Replacing a specific assertion with assert True is a weakened assertion."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,3 @@
         def test_a():
        -    assert result == 42
        +    assert True
             pass
        """)
    result = _run_check(diff)
    weak_item = next(i for i in result.items if i.name == "no_weakened_assertions")
    assert not weak_item.passed


# ---------------------------------------------------------------------------
# no_deleted_tests
# ---------------------------------------------------------------------------


def test_deleted_test_fails():
    """Removing a def test_ line fails no_deleted_tests."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +0,0 @@
        -def test_a():
        -    assert True
        -
        """)
    result = _run_check(diff)
    del_item = next(i for i in result.items if i.name == "no_deleted_tests")
    assert not del_item.passed


def test_renamed_test_passes():
    """Renaming a test (remove old def + add new def) passes no_deleted_tests."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,3 @@
        -def test_old_name():
        +def test_new_name():
             assert True
        """)
    result = _run_check(diff)
    del_item = next(i for i in result.items if i.name == "no_deleted_tests")
    assert del_item.passed, f"renamed test should pass: {del_item.detail}"


# ---------------------------------------------------------------------------
# no_widened_budgets
# ---------------------------------------------------------------------------


def test_widened_budget_fails():
    """Increasing a budget/threshold number fails no_widened_budgets."""
    diff = textwrap.dedent("""\
        diff --git a/config.yaml b/config.yaml
        --- a/config.yaml
        +++ b/config.yaml
        @@ -1,2 +1,2 @@
        -max_fixes_per_run: 5
        +max_fixes_per_run: 50
         """)
    result = _run_check(diff)
    budget_item = next(i for i in result.items if i.name == "no_widened_budgets")
    assert not budget_item.passed


def test_unchanged_budget_passes():
    """A diff that doesn't touch budgets passes no_widened_budgets."""
    diff = textwrap.dedent("""\
        diff --git a/scripts/foo.py b/scripts/foo.py
        --- a/scripts/foo.py
        +++ b/scripts/foo.py
        @@ -1,1 +1,2 @@
         x = 1
        +y = 2
        """)
    result = _run_check(diff)
    budget_item = next(i for i in result.items if i.name == "no_widened_budgets")
    assert budget_item.passed


# ---------------------------------------------------------------------------
# fix_addresses_root_cause
# ---------------------------------------------------------------------------


def test_empty_diff_fails_root_cause():
    """An empty diff fails fix_addresses_root_cause (no fix = no root cause addressed)."""
    result = _run_check("")
    rc_item = next(i for i in result.items if i.name == "fix_addresses_root_cause")
    assert not rc_item.passed


def test_diff_touches_finding_files_passes():
    """A diff that touches a file named in the finding's files[] passes fix_addresses_root_cause."""
    diff = textwrap.dedent("""\
        diff --git a/scripts/governance/loop/warrant.py b/scripts/governance/loop/warrant.py
        --- a/scripts/governance/loop/warrant.py
        +++ b/scripts/governance/loop/warrant.py
        @@ -1,1 +1,2 @@
         x = 1
        +y = 2
        """)
    finding = {"files": ["scripts/governance/loop/warrant.py"]}
    result = _run_check(diff, finding=finding)
    rc_item = next(i for i in result.items if i.name == "fix_addresses_root_cause")
    assert rc_item.passed


def test_diff_does_not_touch_finding_files_fails():
    """A diff that doesn't touch any file in the finding's files[] fails fix_addresses_root_cause."""
    diff = textwrap.dedent("""\
        diff --git a/scripts/governance/loop/other.py b/scripts/governance/loop/other.py
        --- a/scripts/governance/loop/other.py
        +++ b/scripts/governance/loop/other.py
        @@ -1,1 +1,2 @@
         x = 1
        +y = 2
        """)
    finding = {"files": ["scripts/governance/loop/warrant.py"]}
    result = _run_check(diff, finding=finding)
    rc_item = next(i for i in result.items if i.name == "fix_addresses_root_cause")
    assert not rc_item.passed


def test_no_finding_files_nonempty_diff_passes():
    """A non-empty diff with a finding that has no files[] passes fix_addresses_root_cause."""
    diff = _clean_diff()
    finding = {"files": []}
    result = _run_check(diff, finding=finding)
    rc_item = next(i for i in result.items if i.name == "fix_addresses_root_cause")
    assert rc_item.passed


# ---------------------------------------------------------------------------
# Result API
# ---------------------------------------------------------------------------


def test_result_to_dict():
    """to_dict returns {item_name: 'pass'|'fail'} for all items."""
    result = _run_check(_clean_diff())
    d = result.to_dict()
    assert isinstance(d, dict)
    assert len(d) == len(CHECKLIST_ITEMS)
    for name in CHECKLIST_ITEMS:
        assert name in d
        assert d[name] in ("pass", "fail")


def test_result_failures():
    """failures() returns only the failed items."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,4 @@
        +    pytest.skip("not ready")
         def test_a():
             assert True
        """)
    result = _run_check(diff)
    failures = result.failures()
    assert len(failures) >= 1
    assert all(not f.passed for f in failures)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_clean_diff_exit_zero(tmp_path):
    """CLI on a clean diff file exits 0."""
    diff_path = tmp_path / "clean.diff"
    diff_path.write_text(_clean_diff())
    proc = _run_cli(diff_path)
    assert proc.returncode == 0, f"clean diff should exit 0: {proc.stdout!r} {proc.stderr!r}"


def test_cli_gamed_diff_exit_nonzero(tmp_path):
    """CLI on a gamed diff (new skip) exits non-zero (REJECT, not merely flagged)."""
    diff = textwrap.dedent("""\
        diff --git a/tests/test_foo.py b/tests/test_foo.py
        --- a/tests/test_foo.py
        +++ b/tests/test_foo.py
        @@ -1,3 +1,4 @@
        +    pytest.skip("not ready")
         def test_a():
             assert True
        """)
    diff_path = tmp_path / "gamed.diff"
    diff_path.write_text(diff)
    proc = _run_cli(diff_path)
    assert proc.returncode != 0, f"gamed diff should exit non-zero: {proc.stdout!r}"
    output = proc.stdout + proc.stderr
    assert "no_new_skips" in output or "fail" in output.lower()


def test_cli_output_has_checklist_json(tmp_path):
    """CLI outputs JSON with all checklist items and pass/fail values."""
    diff_path = tmp_path / "clean.diff"
    diff_path.write_text(_clean_diff())
    proc = _run_cli(diff_path)
    data = json.loads(proc.stdout.strip())
    for name in CHECKLIST_ITEMS:
        assert name in data
        assert data[name] in ("pass", "fail")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
