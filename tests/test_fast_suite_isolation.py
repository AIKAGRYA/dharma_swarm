"""WP-0D fast-suite determinism contract (TIT-002).

`make test-fast` repeatedly stalled mid-suite on tests that passed alone in
under a second — suite-order / leaked-resource / global-state coupling, not
defects in the stalled tests. Commit 280fc25 (PR #1092) and merge a4e2f7c
(PR #1099, commit f3fb230) killed the identified suite-context timeout
modes. These tests pin those protections so a revert cannot land silently:

- ``test-fast`` declares a blanket per-test timeout and it is never raised
  (the WP-0D spec forbids "raising the global fast timeout without
  root-cause evidence" — repo-scale tests get per-test overrides instead);
- ``test-fast`` excludes ``slow``/``docker``/``network`` markers with the
  same expression ``make test`` and the required CI suite use, so the fast
  suite never collects tests every other automated gate excludes;
- the known repo-scale tests carry ``pytest.mark.timeout`` overrides above
  the blanket fast budget instead of a ``slow`` marker — a ``slow`` marker
  would silently drop them from every automated gate (``make test``,
  ``make test-fast``, and .github/workflows/tests.yml all filter
  ``-m "not slow ..."``);
- AgentConfig-driven state resolution never falls back to this checkout's
  ambient repo-root ``.dharma/`` (its shared ontology.db grows across test
  runs until writes cross the fast budget — the autouse
  ``_isolate_agent_state_dir`` guard in tests/conftest.py suppresses
  exactly that path while leaving the fallback intact elsewhere).

Subprocess/process-group timeout containment (the other WP-0D fix family,
dharma_swarm/sandbox.py ``kill_process_group`` + ``start_new_session``) is
behaviorally covered by tests/test_sandbox.py and
tests/test_subprocess_cancellation.py and deliberately not duplicated here.

Authority: docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0D).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
TESTS_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(
    encoding="utf-8"
)

# The heavy-marker set every automated suite gate must exclude.
EXCLUDED_MARKERS = ("slow", "docker", "network")


# ── helpers ─────────────────────────────────────────────────────────


def _recipe(target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n)*)", MAKEFILE, re.MULTILINE
    )
    assert match is not None, f"Makefile target {target!r} not found"
    return match.group(0)


def _marker_expression(text: str) -> str | None:
    match = re.search(r'-m\s+"([^"]+)"', text)
    return match.group(1) if match else None


def _blanket_timeout(text: str) -> int | None:
    match = re.search(r"--timeout=(\d+)", text)
    return int(match.group(1)) if match else None


def _fast_budget() -> int:
    budget = _blanket_timeout(_recipe("test-fast"))
    assert budget is not None, (
        "test-fast must declare a blanket per-test --timeout: without it a "
        "single leaked-state hang stalls the whole suite instead of failing "
        "one test (WP-0D determinism)"
    )
    return budget


def _ci_suite_budget() -> int:
    """Per-test --timeout of the full-suite pytest run in tests.yml."""
    anchor = TESTS_WORKFLOW.index("-m pytest tests/ ")
    window = TESTS_WORKFLOW[anchor : anchor + 400]
    budget = _blanket_timeout(window)
    assert budget is not None, (
        "the required CI suite run must declare a per-test --timeout so "
        "suite-context hangs fail one test instead of the 6h job limit"
    )
    return budget


def _mark_chain(node: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _function_decorators(relative_path: str, func_name: str) -> list[ast.expr]:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    matches = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == func_name
    ]
    assert len(matches) == 1, (
        f"{relative_path} must define exactly one {func_name!r} "
        f"(found {len(matches)}); if it moved or was renamed, update the "
        "WP-0D override registry in this file with it"
    )
    return matches[0].decorator_list


def _timeout_override(decorators: list[ast.expr]) -> int | float | None:
    for dec in decorators:
        if not isinstance(dec, ast.Call):
            continue
        if _mark_chain(dec.func) != "pytest.mark.timeout":
            continue
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                return arg.value
        for keyword in dec.keywords:
            if keyword.arg == "timeout" and isinstance(keyword.value, ast.Constant):
                return keyword.value.value
    return None


def _is_marked_slow(decorators: list[ast.expr]) -> bool:
    for dec in decorators:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if _mark_chain(target) == "pytest.mark.slow":
            return True
    return False


# ── the fast-suite invocation contract (Makefile + CI parity) ───────


class TestFastSuiteInvocation:
    def test_declares_bounded_per_test_timeout(self):
        assert _fast_budget() <= 10, (
            "the blanket fast per-test budget was raised above 10s — the "
            "WP-0D spec forbids raising the global fast timeout without "
            "root-cause evidence; give the genuinely repo-scale test its own "
            "pytest.mark.timeout override and register it in this file instead"
        )

    def test_excludes_heavy_markers(self):
        expression = _marker_expression(_recipe("test-fast"))
        assert expression is not None, (
            "test-fast lost its -m marker filter (added by WP-0D commit "
            "280fc25): without it the fast suite collects slow/docker/network "
            "tests that every other gate excludes, and each one is a "
            "guaranteed blanket-budget timeout"
        )
        for marker in EXCLUDED_MARKERS:
            assert f"not {marker}" in expression, (
                f"test-fast must exclude -m {marker!r} like make test does"
            )

    def test_marker_filter_matches_make_test(self):
        assert _marker_expression(_recipe("test-fast")) == _marker_expression(
            _recipe("test")
        ), (
            "test-fast and test must collect the same marker set (WP-0D "
            "commit 280fc25 aligned them); a divergence means the fast suite "
            "proves determinism for a different suite than the standard gate runs"
        )

    def test_ci_suite_uses_same_marker_filter(self):
        expression = _marker_expression(_recipe("test-fast"))
        assert expression is not None
        assert f'-m "{expression}"' in TESTS_WORKFLOW, (
            "the required CI suite (.github/workflows/tests.yml) must filter "
            "the same marker expression as test-fast — the per-test override "
            "policy below relies on `slow` being excluded everywhere alike"
        )

    def test_ci_suite_budget_not_below_fast_budget(self):
        assert _ci_suite_budget() >= _fast_budget(), (
            "CI runs the suite under 2-core contention; a CI per-test budget "
            "below the local fast budget would reintroduce CI-only "
            "suite-context timeouts (the #1099 failure mode, inverted)"
        )


# ── per-test overrides for repo-scale tests ─────────────────────────
#
# Each of these does real whole-repo work (AST/quality sweep, product
# score, X-Ray, memory-writer discovery scan, SwarmManager boot, sealed
# external-entry packet bootstrap), so its wall time scales with repo size
# and crosses the blanket fast budget under full-suite load even though
# nothing regressed. WP-0D's ratified fix (commit 280fc25; f3fb230 for the
# packet test) is a per-test pytest.mark.timeout override — NOT a `slow`
# marker, which every automated gate filters out.

REPO_SCALE_OVERRIDES = (
    ("tests/conformance/test_repo_ratchet_holds.py", "test_repo_quality_ratchet_has_no_regressions"),
    ("tests/test_cascade.py", "test_product_score_real_project"),
    ("tests/test_e2e_boot.py", "test_full_lifecycle_boot"),
    ("tests/test_e2e_boot.py", "test_custom_task_dispatch"),
    ("tests/test_memory_writer_sentinel.py", "test_writer_sentinel_cli_reports_discovery_summary"),
    ("tests/test_memory_writer_sentinel.py", "test_writer_sentinel_cli_action_required_gate_passes_for_triaged_repo"),
    ("tests/test_memory_writer_sentinel.py", "test_writer_sentinel_cli_ci_profile_runs_discovery_and_gates"),
    ("tests/test_memory_writer_sentinel.py", "test_writer_sentinel_cli_writes_markdown_report"),
    ("tests/test_xray.py", "test_on_dharma_swarm"),
    ("tests/test_agent_work_packet.py", "test_external_entry_packet_bootstrap_and_digest_binding"),
)


class TestRepoScaleTimeoutOverrides:
    @pytest.mark.parametrize(
        ("relative_path", "func_name"),
        REPO_SCALE_OVERRIDES,
        ids=[f"{path}::{name}" for path, name in REPO_SCALE_OVERRIDES],
    )
    def test_override_present_and_above_fast_budget(
        self, relative_path: str, func_name: str
    ):
        decorators = _function_decorators(relative_path, func_name)
        override = _timeout_override(decorators)
        assert override is not None, (
            f"{relative_path}::{func_name} lost its pytest.mark.timeout "
            "override (WP-0D): under full-suite load it exceeds the blanket "
            "fast budget while passing alone, so make test-fast becomes "
            "nondeterministic again"
        )
        assert override > _fast_budget(), (
            f"{relative_path}::{func_name} declares timeout({override}) "
            "which does not exceed the blanket fast budget — the override "
            "would no longer buy any headroom"
        )
        assert not _is_marked_slow(decorators), (
            f"{relative_path}::{func_name} was marked `slow` — the WP-0D "
            "spec forbids marking a failing test slow merely because it "
            "appears late in the suite, and every automated gate filters "
            "-m 'not slow', so the marker silently drops it from all of them"
        )

    def test_ci_contention_override_exceeds_ci_budget(self):
        """PR #1099: the external-entry packet test (~15s solo) timed out on
        four CI suite runs under the workflow's own per-test budget while
        passing alone every time. Its marker must stay above that CI budget
        or the override stops overriding where the failures happened."""
        decorators = _function_decorators(
            "tests/test_agent_work_packet.py",
            "test_external_entry_packet_bootstrap_and_digest_binding",
        )
        override = _timeout_override(decorators)
        assert override is not None
        assert override > _ci_suite_budget(), (
            f"timeout({override}) no longer exceeds the CI suite's per-test "
            "budget — under 2-core CI contention the test will time out again "
            "(the exact #1099 failure mode)"
        )


# ── ambient checkout state must never leak into tests ───────────────


class TestAgentStateIsolation:
    """agent_runner._resolve_config_state_dir falls back to ``cwd/.dharma``
    when an AgentConfig carries no explicit state dir. Resolved against the
    real checkout root, that is shared, ambient, cross-test-run state whose
    ontology.db grows with every unisolated run until writes against it
    cross the blanket fast budget (the WP-0D suite-context timeout). The
    autouse ``_isolate_agent_state_dir`` fixture in tests/conftest.py must
    keep suppressing exactly that resolution — and only that one."""

    def test_repo_root_dharma_fallback_is_suppressed(self, monkeypatch):
        import dharma_swarm.agent_runner as agent_runner
        from dharma_swarm.models import AgentConfig, AgentRole

        repo_dharma = REPO_ROOT / ".dharma"
        created = False
        if not repo_dharma.exists():
            # Gitignored (.gitignore lists `.dharma/`); created empty and
            # removed below so the checkout is left exactly as found.
            repo_dharma.mkdir()
            created = True
        try:
            monkeypatch.chdir(REPO_ROOT)
            resolved = agent_runner._resolve_config_state_dir(
                AgentConfig(name="wp0d-isolation-probe", role=AgentRole.CODER)
            )
            assert resolved is None, (
                f"resolved ambient checkout state {resolved} — the autouse "
                "_isolate_agent_state_dir guard in tests/conftest.py is gone "
                "or no longer wraps agent_runner._resolve_config_state_dir, "
                "so unisolated AgentConfig tests will accumulate shared "
                "ontology.db state across runs again (WP-0D)"
            )
        finally:
            if created:
                repo_dharma.rmdir()

    def test_isolated_cwd_fallback_still_resolves(self, monkeypatch, tmp_path):
        """The guard suppresses only the literal repo-root path: a test that
        deliberately exercises the CWD fallback against an isolated tmp dir
        must still see real resolver behavior. This also proves the test
        above fails for the right reason — same code path, only the cwd
        differs."""
        import dharma_swarm.agent_runner as agent_runner
        from dharma_swarm.models import AgentConfig, AgentRole

        (tmp_path / ".dharma").mkdir()
        monkeypatch.chdir(tmp_path)
        resolved = agent_runner._resolve_config_state_dir(
            AgentConfig(name="wp0d-isolation-probe", role=AgentRole.CODER)
        )
        assert resolved is not None, (
            "the CWD fallback stopped resolving an isolated .dharma — the "
            "conftest guard must wrap the resolver, not disable the fallback"
        )
        assert resolved.resolve() == (tmp_path / ".dharma").resolve()
