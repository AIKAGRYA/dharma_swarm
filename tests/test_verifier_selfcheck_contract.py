"""WP-0B verifier-truth contract (TIT-001).

`make verifier-selfcheck` printed "ALL GATES FUNCTIONAL" while executing only
syntax, F821, collection, and onboarding — no behavioral gate. These tests pin
the repaired contract:

- the recipe runs a bounded behavioral sentinel (`VERIFIER_SENTINEL`,
  overridable) with real assertions, not `--collect-only`;
- a failing sentinel makes the whole target exit nonzero (meta-test);
- a passing sentinel yields the narrowed banner that enumerates exactly what
  ran, and the overbroad "ALL GATES FUNCTIONAL" phrase is gone;
- the recipe resolves the test runner through `$(VENV_PYTHON)` so a
  bootstrapped `.venv` is preferred.

Authority: docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0B).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

NARROWED_BANNER = (
    "verifier-selfcheck: OK (syntax, F821, collection, onboarding, behavioral sentinel)"
)


@pytest.fixture(autouse=True)
def _no_bytecode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The target spawns Python subprocesses; keep the repo bytecode-free."""
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")


def _recipe(target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n)*)", MAKEFILE, re.MULTILINE
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group(0)


# ── Structural contract (fast) ──────────────────────────────────────


class TestRecipeStructure:
    def test_recipe_runs_behavioral_sentinel(self):
        recipe = _recipe("verifier-selfcheck")
        assert "$(VERIFIER_SENTINEL)" in recipe, (
            "verifier-selfcheck must execute the behavioral sentinel "
            "(TIT-001: success output and executed evidence must be equivalent)"
        )
        sentinel_lines = [
            line for line in recipe.splitlines() if "$(VERIFIER_SENTINEL)" in line
        ]
        assert any("-m pytest" in line for line in sentinel_lines)
        assert not any("--collect-only" in line for line in sentinel_lines), (
            "collection of the sentinel is not execution of the sentinel"
        )

    def test_sentinel_default_is_a_real_behavioral_suite(self):
        match = re.search(r"^VERIFIER_SENTINEL \?= (.+)$", MAKEFILE, re.MULTILINE)
        assert match is not None, "VERIFIER_SENTINEL must be overridable (?=)"
        default = match.group(1).strip()
        assert (REPO_ROOT / default).is_file(), default
        assert "def test_" in (REPO_ROOT / default).read_text(encoding="utf-8")

    def test_overbroad_banner_is_gone(self):
        recipe = _recipe("verifier-selfcheck")
        assert "ALL GATES FUNCTIONAL" not in recipe, (
            "the banner may not claim more than the gates that executed"
        )
        assert NARROWED_BANNER in recipe

    def test_recipe_uses_venv_python(self):
        recipe = _recipe("verifier-selfcheck")
        assert "$(VENV_PYTHON)" in recipe, (
            "the sentinel and collection steps must prefer the bootstrapped .venv"
        )

    def test_sentinel_failure_propagates_in_recipe_text(self):
        recipe = _recipe("verifier-selfcheck")
        sentinel_block = recipe[recipe.index("$(VERIFIER_SENTINEL)"):]
        assert "exit 1" in sentinel_block, (
            "a failing sentinel must fail the target, not be swallowed"
        )


# ── Behavioral meta-tests (bounded, full target runs) ───────────────
#
# verifier-selfcheck's onboarding step requires a clean worktree, so the
# target runs inside an isolated committed snapshot of the implementation
# under test (the pattern established by test_make_onboarding_contract.py).
# One snapshot is shared by both meta-tests.


def _snapshot_checkout(destination: Path) -> None:
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(destination)],
        check=True, timeout=120,
    )
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT, capture_output=True, check=True, timeout=60,
    ).stdout
    for raw_relative in listed.split(b"\0"):
        if not raw_relative:
            continue
        relative = os.fsdecode(raw_relative)
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
    subprocess.run(["git", "-C", str(destination), "add", "-A"], check=True, timeout=60)
    subprocess.run(
        ["git", "-C", str(destination),
         "-c", "user.name=WP-0B Contract Test",
         "-c", "user.email=wp0b-test@example.invalid",
         "commit", "--quiet", "--allow-empty", "-m", "snapshot under test"],
        check=True, timeout=60,
    )


@pytest.fixture(scope="module")
def clean_checkout(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("wp0b-selfcheck") / "checkout"
    _snapshot_checkout(destination)
    return destination


def _make_selfcheck_in(checkout: Path, sentinel: Path, timeout: int = 540) -> subprocess.CompletedProcess[str]:
    # Pin the tool identity to this test's own interpreter so the meta-run
    # does not depend on the caller's PATH providing bare `ruff`/`python3`
    # (the AgentOps gate environment is deliberately minimal). The recipe's
    # own $(VENV_PYTHON)/.venv preference is pinned structurally above.
    return subprocess.run(
        [
            "make", "-s", "verifier-selfcheck",
            f"VERIFIER_SENTINEL={sentinel}",
            f"VENV_PYTHON={sys.executable}",
            f"PYTHON={sys.executable}",
            f"RUFF={sys.executable} -m ruff",
        ],
        cwd=checkout, capture_output=True, text=True, timeout=timeout,
    )


@pytest.mark.timeout(900)
def test_failing_sentinel_fails_the_target(clean_checkout: Path, tmp_path: Path):
    failing = tmp_path / "test_failing_sentinel.py"
    failing.write_text(
        "def test_sentinel_must_fail():\n    assert False, 'deliberate sentinel failure'\n",
        encoding="utf-8",
    )
    result = _make_selfcheck_in(clean_checkout, failing)
    assert result.returncode != 0, (
        "verifier-selfcheck exited zero with a failing behavioral sentinel:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "BEHAVIORAL SENTINEL FAILED" in result.stdout + result.stderr
    assert NARROWED_BANNER not in result.stdout


@pytest.mark.timeout(900)
def test_passing_sentinel_yields_narrowed_banner(clean_checkout: Path, tmp_path: Path):
    passing = tmp_path / "test_passing_sentinel.py"
    passing.write_text(
        "def test_sentinel_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    result = _make_selfcheck_in(clean_checkout, passing)
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert NARROWED_BANNER in result.stdout
    assert "ALL GATES FUNCTIONAL" not in result.stdout
