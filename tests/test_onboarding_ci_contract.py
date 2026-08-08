"""CI/local parity for the read-only onboarding status command.

The required workflow context runs plain ``make onboard`` with strict-default
semantics, then a focused onboarding test set. Work-packet admission remains a
separate explicit preflight and is not coupled to the status workflow.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOW = REPO_ROOT / ".github/workflows/active-track.yml"
CI_TRUTH_CONTRACT = REPO_ROOT / "docs/governance/CI_TRUTH_CONTRACT.json"
FOCUSED_ONBOARDING_TESTS = (
    "tests/test_agent_onboard.py",
    "tests/test_onboarding_cli.py",
    "tests/test_onboarding_readiness.py",
    "tests/test_onboarding_ci_contract.py",
)
FOCUSED_ONBOARDING_COMMAND = (
    "python3 -m pytest -q " + " ".join(FOCUSED_ONBOARDING_TESTS)
)

def _job_block(name: str) -> str:
    """Raw job text with comment-only lines REMOVED.

    Every assertion in this file is a substring test over this string, so
    comments were load-bearing in the worst way: an `in` assertion could be
    satisfied by prose alone, and a `not in` assertion could be broken by prose
    alone. Caught on PR #1287, where a comment block explaining why `always()`
    had been REPLACED kept `assert "always()" in compat` green after the real
    condition became `!cancelled()` — a guard reporting on its own explanation.
    That is precisely the CLAUDE.md rule "never add prose to satisfy a gate",
    committed accidentally.

    Inline comments are left alone: the only ones present are action SHA pins
    (`uses: ...@sha # v4`), no assertion depends on them, and stripping `#`
    mid-line would corrupt any legitimate `#` inside a shell step.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow job {name!r} not found in active-track.yml"
    return "\n".join(
        line for line in match.group(0).splitlines()
        if not line.lstrip().startswith("#")
    )


def _job_block_with_comments(name: str) -> str:
    """Raw job text, comments included.

    Exactly one caller wants this: the test that asserts a specific warning
    comment leads the steps list. Every other assertion in this file must go
    through _job_block(), which strips comments, so that no gate here can be
    satisfied — or broken — by prose.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow job {name!r} not found in active-track.yml"
    return match.group(0)


def _job_condition(name: str) -> str:
    """The parsed `if:` value — structure, never text. Immune to comments."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return " ".join(str(doc["jobs"][name].get("if", "")).split())


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        assert key not in result, f"duplicate CI truth contract key: {key}"
        result[key] = value
    return result


def _assert_workflow_onboarding_contract(job: str) -> None:
    pr_head = "github.event.pull_request.head.sha"
    group_head = "github.event.merge_group.head_sha"

    assert "name: Onboarding session status" in job
    assert f"ref: ${{{{ {pr_head} || {group_head} }}}}" in job
    assert "github.sha" not in job
    assert re.search(
        r"- name: Run session status \(same command as local\)\n"
        r"\s+env:\n"
        r"\s+DHARMA_OPS_DIR: \$\{\{ runner\.temp \}\}/"
        r"dharma-agentops/onboarding\n",
        job,
    )
    assert job.count("make onboard") == 1
    assert "python3 -m pytest -q \\" in job
    for relative in FOCUSED_ONBOARDING_TESTS:
        assert job.count(relative) == 1
    for removed in (
        "scripts/governance/run_agent_work_packet.py",
        "--ci-event",
        "EVENT_BASE",
        "EVENT_HEAD",
        "EVENT_NAME",
        "actions/upload-artifact",
        "onboarding-admission-evidence",
        "if: always()",
    ):
        assert removed not in job
    assert job.count("set -euo pipefail") == 4
    assert "continue-on-error" not in job
    assert "|| true" not in job


def test_ci_and_local_status_command_equivalence() -> None:
    """The required context runs the exact strict-default local command."""
    job = _job_block("onboarding-status")
    _assert_workflow_onboarding_contract(job)

    contract = json.loads(
        CI_TRUTH_CONTRACT.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_json_object,
    )
    required = [
        check
        for check in contract["required"]
        if "Onboarding admission parity" in check.get("names", [])
    ]
    assert len(required) == 1
    assert required[0] == {
        "id": "onboarding_session_status",
        "names": ["Onboarding admission parity"],
        "owner": "onboarding",
        "local_command": f"make onboard && {FOCUSED_ONBOARDING_COMMAND}",
        "failure_category": "session_status",
        "autofix": "manual",
    }
    assert all(
        "Onboarding admission parity" not in check.get("names", [])
        for check in contract["advisory"]
    )


def test_legacy_required_context_fails_closed_on_session_status() -> None:
    """The phase-1 bridge cannot mask a failed or cancelled real status job.

    The condition is read from the parsed YAML, not from the job text. It was
    `always() &&` until 2026-08-07; it is now `!cancelled() &&`, which still
    overrides the implicit needs-success gate (so a FAILED session-status runs
    the bridge and blocks) but CANCELS rather than SKIPS when the run is
    cancelled. Skipping would be worse than the bug it fixed: a SKIPPED
    required check counts as a pass in branch protection and in
    scripts/runtime/pr_merge_control.py:53, and an operator-initiated cancel
    has no successor run. See tests/test_admission_parity_bridge.py."""

    compat = _job_block("onboarding-admission-parity-compat")
    condition = _job_condition("onboarding-admission-parity-compat")
    assert "name: Onboarding admission parity" in compat
    assert "needs: onboarding-status" in compat
    assert "!cancelled()" in condition, (
        "the bridge must run even when session-status failed, or a failure "
        f"would skip it and a skipped required check passes; got: {condition}"
    )
    assert "always()" not in condition, (
        "always() runs the bridge after a cancellation and reports that "
        f"indeterminate state as a hard failure; got: {condition}"
    )
    assert "SESSION_STATUS_RESULT: ${{ needs.onboarding-status.result }}" in compat
    assert 'test "${SESSION_STATUS_RESULT}" = "success"' in compat
    assert "continue-on-error" not in compat
    assert "|| true" not in compat


def test_ci_status_has_no_weakening_flags() -> None:
    job = _job_block("onboarding-status")
    assert "continue-on-error" not in job
    assert "|| true" not in job
    assert "--no-strict" not in job
    assert "DHARMA_ONBOARD_STRICT" not in job
    assert not re.search(r"\bmake onboard\s+--strict\b", job)
    assert "timeout-minutes: 30" in job
    assert 'python-version: "3.12.13"' in job
    assert (
        'install_source="${RUNNER_TEMP}/dharma-agentops-bootstrap/package-source"'
        in job
    )
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert 'python3 -m pip install "${install_source}[dev]"' in job
    assert 'python3 -m pip install ".[dev]"' not in job
    assert 'python3 -m pip install -e ".[dev]"' not in job
    assert "python3 -m pip install pyyaml" not in job
    for externalized in (
        "'PYTHONDONTWRITEBYTECODE=1'",
        '"PYTHONPYCACHEPREFIX=${bootstrap}/pycache"',
        "'PYTEST_ADDOPTS=-p no:cacheprovider'",
        '"XDG_CACHE_HOME=${bootstrap}/xdg"',
        '"RUFF_CACHE_DIR=${bootstrap}/ruff"',
        '"PIP_CACHE_DIR=${bootstrap}/pip"',
    ):
        assert externalized in job

    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = project["project"]["dependencies"]
    development = project["project"]["optional-dependencies"]["dev"]
    assert any(item.startswith("pydantic>=2") for item in runtime)
    assert any(item.startswith("pyyaml>=") for item in runtime)
    for dependency in ("pytest", "pytest-timeout", "ruff"):
        assert any(
            item == dependency or item.startswith((f"{dependency}>=", f"{dependency}=="))
            for item in development
        )
    for relative in (
        "tests/test_make_onboarding_contract.py",
        "tests/test_onboarding_ci_contract.py",
        "tests/test_agent_work_packet.py",
        "tests/test_orientation_graph.py",
    ):
        assert (REPO_ROOT / relative).is_file()


def test_active_track_gate_installs_full_dev_environment_before_evaluation() -> None:
    """The blocking checker must execute criteria, not compare an empty env."""
    job = _job_block("active-track-governance")
    install = 'python3 -m pip install "${install_source}[dev]"'
    evaluate = "python3 scripts/governance/check_track_status.py"

    assert (
        'install_source="${RUNNER_TEMP}/dharma-active-track-bootstrap/package-source"'
        in job
    )
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert install in job
    assert "python3 -m pip install pyyaml" not in job
    assert 'python3 -m pip install ".[dev]"' not in job
    assert 'python3 -m pip install -e ".[dev]"' not in job
    for externalized in (
        "'PYTHONDONTWRITEBYTECODE=1'",
        '"PYTHONPYCACHEPREFIX=${bootstrap}/pycache"',
        "'PYTEST_ADDOPTS=-p no:cacheprovider'",
        '"XDG_CACHE_HOME=${bootstrap}/xdg"',
        '"RUFF_CACHE_DIR=${bootstrap}/ruff"',
        '"PIP_CACHE_DIR=${bootstrap}/pip"',
        '"HYPOTHESIS_STORAGE_DIRECTORY=${bootstrap}/hypothesis"',
    ):
        assert externalized in job
    assert not re.search(r"^\s+continue-on-error:", job, re.MULTILINE)
    assert job.index(install) < job.index(evaluate)


def test_macos_compatibility_job_is_advisory_and_executable() -> None:
    job = _job_block("onboarding-macos-compatibility")
    assert "runs-on: macos-14" in job
    assert "python-version: \"3.12\"" in job
    assert "python-version: \"3.12.13\"" not in job
    assert 'git archive --format=tar HEAD | tar -xf - -C "${install_source}"' in job
    assert 'python3 -m pip install "${install_source}[dev]"' in job
    assert "pip install 'pytest>=7.0'" not in job
    reproducer = "/usr/bin/make onboarding-macos-compatibility"
    assert job.count(reproducer) == 1
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "onboarding-macos-compatibility:\n\t@set -eu;" in makefile
    for command in (
        "/usr/bin/make -n onboard",
        "/usr/bin/make -n orient",
        "/usr/bin/make -n help",
    ):
        assert command in makefile
    for proof in (
        "test_darwin_negative_confinement_executes_and_denies_outside_write",
        "test_darwin_account_temp_root_native_and_prepares_report_root",
        "test_darwin_account_temp_root_uses_getconf_with_scrubbed_environment",
        "test_darwin_report_anchor_rejects_environment_minted_temp_root",
        "test_private_report_anchor_enforces_owner_mode_and_symlink_boundaries",
    ):
        assert proof in makefile

    contract = json.loads(
        CI_TRUTH_CONTRACT.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_json_object,
    )
    advisory = next(
        check
        for check in contract["advisory"]
        if "Onboarding macOS 3.81 compatibility" in check.get("names", [])
    )
    assert advisory["local_command"] == reproducer


def test_ci_runner_context_is_resolved_only_after_job_assignment() -> None:
    """GitHub does not expose ``runner`` while evaluating job-level ``env``.

    A forbidden context there invalidates the entire workflow before any job
    exists, so the external cache roots must be exported from a runner step.
    """
    job = _job_block("onboarding-status")
    job_header, steps = job.split("    steps:\n", maxsplit=1)
    assert "${{ runner." not in job_header
    # The leading-comment assertion is the one place a comment IS the subject,
    # so it reads the unstripped text on purpose.
    _, raw_steps = _job_block_with_comments("onboarding-status").split(
        "    steps:\n", maxsplit=1
    )
    assert raw_steps.startswith(
        "      # `runner` is unavailable while GitHub evaluates job-level `env`."
    )
    assert "- name: Confine tool state outside checkout" in steps
    assert 'bootstrap="${RUNNER_TEMP}/dharma-agentops-bootstrap"' in steps
    assert '>> "${GITHUB_ENV}"' in steps


def test_verifier_selfcheck_propagates_onboard_failure() -> None:
    """O4-B6: root validation orders the sequential, fail-closed verifier."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^agent-build-preflight:(.*)$", makefile, re.MULTILINE)
    assert match
    prerequisites = match.group(1).split()
    assert prerequisites == ["agentops-report-root-check"]

    recipe_match = re.search(
        r"^agent-build-preflight:.*\n((?:\t.*\n|ifdef .*\n|endif\n)*)",
        makefile,
        re.MULTILINE,
    )
    assert recipe_match
    recipe = recipe_match.group(0)
    assert recipe.count("$(MAKE) -s verifier-selfcheck") == 1
    assert recipe.count("$(MAKE) -s hygiene-check") == 1
    assert recipe.count("MAKEOVERRIDES=") == 2
    assert "AGENTOPS_RECURSIVE_OVERRIDES" not in recipe
    assert recipe.index("verifier-selfcheck") < recipe.index("hygiene-check")
    assert "$(MAKE) -s onboard" not in recipe
    assert "|| true" not in recipe
