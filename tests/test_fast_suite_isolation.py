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
- every active ``command_passes`` criterion that runs a test file budgets at
  least that file's largest declared ``pytest.mark.timeout`` override, so an
  outer governance timeout cannot contradict the test contract it evaluates;
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
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_TRACK = REPO_ROOT / "docs" / "governance" / "ACTIVE_TRACK.yaml"
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


def _file_timeout_contract(
    relative_path: str,
) -> tuple[int | float | None, list[int]]:
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    overrides: list[int | float] = []
    unresolved_lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if _mark_chain(node.func) != "pytest.mark.timeout":
            continue
        timeout = _timeout_override([node])
        if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
            overrides.append(timeout)
        else:
            unresolved_lines.append(node.lineno)
    return max(overrides, default=None), sorted(unresolved_lines)


def _criterion_test_files(command: object) -> list[str]:
    if not isinstance(command, list):
        return []
    files: set[str] = set()
    for part in command:
        if not isinstance(part, str):
            continue
        relative = part.split("::", 1)[0]
        if relative.startswith("tests/") and relative.endswith(".py"):
            files.add(relative)
    return sorted(files)


def _criterion_timeout_violations(portfolio: dict[str, object]) -> list[str]:
    violations: list[str] = []
    for track in portfolio.get("active_tracks", []):
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("id", "<missing-track-id>"))
        for group in ("prerequisites", "completion_criteria", "ship_vetoes"):
            criteria = track.get(group, [])
            if not isinstance(criteria, list):
                continue
            for criterion in criteria:
                if not isinstance(criterion, dict):
                    continue
                if criterion.get("kind") != "command_passes":
                    continue
                criterion_id = str(criterion.get("id", "<missing-criterion-id>"))
                budget = int(criterion.get("timeout_s", 120))
                for relative_path in _criterion_test_files(criterion.get("command")):
                    declared, unresolved_lines = _file_timeout_contract(relative_path)
                    if unresolved_lines:
                        lines = ",".join(str(line) for line in unresolved_lines)
                        violations.append(
                            f"{track_id}::{criterion_id} cannot compare "
                            f"{relative_path} pytest.mark.timeout at line(s) {lines}; "
                            "use a numeric literal"
                        )
                    if declared is not None and budget < declared:
                        violations.append(
                            f"{track_id}::{criterion_id} timeout_s={budget} < "
                            f"{relative_path} max pytest.mark.timeout={declared}"
                        )
    return sorted(violations)


# ── outer criterion budgets must cover inner pytest contracts ───────


class TestTrackCriterionTimeoutBudgets:
    def test_command_criteria_cover_declared_test_timeouts(self):
        portfolio = yaml.safe_load(ACTIVE_TRACK.read_text(encoding="utf-8"))
        violations = _criterion_timeout_violations(portfolio)
        assert not violations, (
            "an outer command_passes budget is below a pytest timeout declared "
            "by one of its test files; the governance runner can time out valid "
            "work and misreport it as a regression:\n" + "\n".join(violations)
        )

    def test_guard_names_real_underbudget_mutation(self):
        mutated = {
            "active_tracks": [
                {
                    "id": "synthetic-timeout-track",
                    "completion_criteria": [
                        {
                            "id": "synthetic-verifier-contracts-pass",
                            "kind": "command_passes",
                            "timeout_s": 900,
                            "command": [
                                "python3",
                                "-m",
                                "pytest",
                                "tests/test_verifier_selfcheck_contract.py",
                                "-q",
                            ],
                        }
                    ],
                }
            ]
        }
        verifier = mutated["active_tracks"][0]["completion_criteria"][0]
        verifier.pop("timeout_s", None)

        violations = _criterion_timeout_violations(mutated)
        expected = (
            "synthetic-timeout-track::"
            "synthetic-verifier-contracts-pass timeout_s=120 < "
            "tests/test_verifier_selfcheck_contract.py max pytest.mark.timeout=900"
        )
        assert expected in violations, violations

    def test_guard_fails_closed_on_dynamic_timeout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        test_file = tmp_path / "tests" / "test_dynamic_timeout.py"
        test_file.parent.mkdir()
        test_file.write_text(
            "import pytest\n\n"
            "@pytest.mark.timeout(LONG_TIMEOUT)\n"
            "def test_dynamic_timeout():\n"
            "    pass\n",
            encoding="utf-8",
        )
        monkeypatch.setitem(globals(), "REPO_ROOT", tmp_path)
        portfolio = {
            "active_tracks": [
                {
                    "id": "synthetic-track",
                    "completion_criteria": [
                        {
                            "id": "dynamic-timeout",
                            "kind": "command_passes",
                            "command": [
                                "python3",
                                "-m",
                                "pytest",
                                "tests/test_dynamic_timeout.py",
                            ],
                        }
                    ],
                }
            ]
        }

        violations = _criterion_timeout_violations(portfolio)
        assert violations == [
            "synthetic-track::dynamic-timeout cannot compare "
            "tests/test_dynamic_timeout.py pytest.mark.timeout at line(s) 3; "
            "use a numeric literal"
        ]


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
    ("tests/test_model_key_routing_guard.py", "test_model_literals_do_not_escape_canonical_registries"),
    ("tests/test_pr_ci_safe_rebase_mutations.py", "test_matrix_reports_all_nineteen_killed"),
    ("tests/test_make_onboarding_contract.py", "test_make_report_root_rejects_hypothesis_cache_symlink"),
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
