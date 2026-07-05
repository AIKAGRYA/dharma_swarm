"""Fail-closed conformance sweep (invariant AI-N1).

AI-N1: a green verdict requires evidence; absence is never green. Each gate
under test is fed EMPTY or ABSENT input and must go NON-GREEN (non-zero exit /
raised verdict). This is the second-order check that keeps the checks honest --
a gate that greens on nothing is worse than no gate, because false-green is
slop training data for an autonomous system.

Targeted gates:
  * guardian-import-smoke (scripts/governance/guardian_import_smoke.py) -- the
    known no-op: the pre-fix inline rule in .github/workflows/tests.yml forgives
    any exception whose text contains "No module named", so a dead critical
    module reports a green import-smoke. The fix allowlists optional deps by
    NAME (from the dependency manifest), never by substring.
  * coherence-delta validate (scripts/governance/check_pr_coherence_delta.py)
    -- a required branch-protection context; an empty PR body/comment set must
    fail, not pass.
  * the AI-N1 primitive itself (scripts/governance/fail_closed.py).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GOV = REPO_ROOT / "scripts" / "governance"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, GOV / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guardian = _load("_conf_guardian_import_smoke", "guardian_import_smoke.py")
fail_closed = _load("_conf_fail_closed", "fail_closed.py")


def _run_gate(rel_script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GOV / rel_script), *args],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": ""},
        capture_output=True,
        text=True,
    )


# --------------------------------------------------------------------------- #
# AI-N1 primitive
# --------------------------------------------------------------------------- #
def test_ai_n1_raises_on_green_with_zero_measurements():
    with pytest.raises(fail_closed.NakedGreenError):
        fail_closed.emit_verdict(gate="unit", green=True, items_measured=0)


def test_ai_n1_allows_green_with_evidence():
    fail_closed.emit_verdict(gate="unit", green=True, items_measured=1)


def test_ai_n1_allows_nongreen_with_zero_measurements():
    # A gate that found nothing and is failing closed is behaving correctly.
    fail_closed.emit_verdict(gate="unit", green=False, items_measured=0)


# --------------------------------------------------------------------------- #
# guardian-import-smoke: absence is never green
# --------------------------------------------------------------------------- #
def test_guardian_empty_module_set_is_not_green():
    # No modules to import => measured nothing => must NOT be green (AI-N1).
    assert guardian.run_smoke([]) != 0


def test_guardian_absent_critical_module_is_not_green():
    # A missing first-party module is the exact case the substring rule
    # forgave. Named allowlisting fails it closed.
    assert guardian.run_smoke(["dharma_swarm.__conformance_absent__"]) != 0


def test_guardian_named_allowlist_forgives_optional_not_critical():
    allowlist = guardian.load_optional_allowlist()

    optional = ModuleNotFoundError("No module named 'torch'")
    optional.name = "torch"
    assert guardian.is_optional_absence(optional, allowlist) is True

    # The regression the fix removes: a substring match on "No module named"
    # would forgive this too; a NAME allowlist must not.
    critical = ModuleNotFoundError("No module named 'dharma_swarm.world_actions'")
    critical.name = "dharma_swarm.world_actions"
    assert guardian.is_optional_absence(critical, allowlist) is False


def test_guardian_non_modulenotfound_is_never_optional():
    allowlist = guardian.load_optional_allowlist()
    # A broken C extension / circular import surfaces as ImportError, not a
    # clean ModuleNotFoundError -- it must fail closed.
    assert guardian.is_optional_absence(ImportError("bad extension"), allowlist) is False


def test_guardian_cli_absent_module_exits_nonzero():
    result = _run_gate(
        "guardian_import_smoke.py", "--module", "dharma_swarm.__conformance_absent__"
    )
    assert result.returncode != 0, result.stdout + result.stderr


def test_guardian_green_on_real_input():
    # No regression: the actual critical modules import in this environment.
    assert guardian.run_smoke(list(guardian.CRITICAL_MODULES)) == 0


# --------------------------------------------------------------------------- #
# coherence-delta validate: empty body/comments must fail
# --------------------------------------------------------------------------- #
def test_coherence_delta_empty_body_is_not_green(tmp_path: Path):
    comments = tmp_path / "comments.json"
    comments.write_text("[]", encoding="utf-8")
    result = _run_gate(
        "check_pr_coherence_delta.py",
        "--body",
        "",
        "--comments-file",
        str(comments),
    )
    assert result.returncode != 0, result.stdout + result.stderr


def test_coherence_delta_absent_comments_file_is_not_green():
    result = _run_gate(
        "check_pr_coherence_delta.py",
        "--body",
        "",
        "--comments-file",
        "/nonexistent/conformance/comments.json",
    )
    assert result.returncode != 0, result.stdout + result.stderr
