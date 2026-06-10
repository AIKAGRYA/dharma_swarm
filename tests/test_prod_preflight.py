"""Tests for the production preflight gate planner/report."""

from __future__ import annotations

from pathlib import Path

from scripts.prod_preflight import GateResult, PreflightGate, build_gate_plan, build_report


def test_prod_preflight_default_plan_contains_release_candidate_gates() -> None:
    names = [gate.name for gate in build_gate_plan(quick=False, include_security=False)]

    assert names == [
        "memory_kernel_readiness",
        "operator_prod_smoke",
        "docops_integrity",
        "test_hygiene",
        "module_budget",
        "diff_check",
        "focused_recursive_operator_tests",
        "control_surface_tests",
    ]


def test_prod_preflight_quick_plan_skips_control_surface_shard() -> None:
    names = [gate.name for gate in build_gate_plan(quick=True, include_security=False)]

    assert "control_surface_tests" not in names


def test_prod_preflight_security_gates_are_explicit_opt_in() -> None:
    names = [gate.name for gate in build_gate_plan(quick=True, include_security=True)]

    assert names[-2:] == ["semgrep_strict", "gitleaks"]


def test_prod_preflight_report_fails_on_required_gate_failure() -> None:
    gate = PreflightGate("docops_integrity", ("make", "docops-integrity"))
    result = GateResult(
        gate=gate,
        returncode=1,
        elapsed_seconds=0.1,
        stdout_tail="FAIL",
        stderr_tail="",
    )

    report = build_report(
        repo_root=Path("."),
        gates=(gate,),
        results=(result,),
        quick=True,
        include_security=False,
    )

    assert report["ok"] is False
    assert report["failed_required_gates"] == ["docops_integrity"]
