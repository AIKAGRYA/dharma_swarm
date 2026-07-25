"""Top-level verifier orchestration.

Given a package root and a property name, this module:
    1. Parses every .py file under the package into typed IR (frontend.py).
    2. Runs effect analysis (effects.py).
    3. Generates one SMT VC per function (vc.py).
    4. Dispatches each VC to Z3 (solvers.py).
    5. Aggregates results into a Report (report.py).

The final Report is the machine-readable artifact CI blocks on.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from titanium_verify.effects import analyze_effects
from titanium_verify.frontend import Function, Module, parse_package
from titanium_verify.report import (
    CounterExample,
    FunctionResult,
    Report,
    Verdict,
)
from titanium_verify.solvers import discharge
from titanium_verify.vc import generate_purity_vcs


def _aggregate_verdict(per_function: Iterable[FunctionResult]) -> Verdict:
    fns = list(per_function)
    if not fns:
        return Verdict.UNKNOWN
    if any(f.verdict == Verdict.REFUTED for f in fns):
        return Verdict.REFUTED
    if any(f.verdict == Verdict.REJECTED for f in fns):
        return Verdict.REJECTED
    if any(f.verdict == Verdict.UNKNOWN for f in fns):
        return Verdict.UNKNOWN
    return Verdict.VERIFIED


def _rejected_results(modules: Iterable[Module]) -> list[FunctionResult]:
    """Surface every REJECTED function as an explicit FunctionResult."""
    out: list[FunctionResult] = []
    for m in modules:
        for f in m.functions:
            if f.is_rejected:
                out.append(FunctionResult(
                    qualname=f.qualname,
                    verdict=Verdict.REJECTED,
                    detail=f"frontend rejected: {f.rejected_reason}",
                ))
    return out


def verify_package(
    pkg_root: Path,
    dotted_prefix: str,
    property_name: str = "purity",
) -> Report:
    """Verify `property_name` over every function in the package.

    Returns a `Report`. If `report.is_success` is True, the property is
    proved for every non-rejected function in the core.
    """
    t0 = time.perf_counter()
    modules = parse_package(pkg_root, dotted_prefix)
    if property_name != "purity":
        return Report(
            package=dotted_prefix,
            property_name=property_name,
            verdict=Verdict.REJECTED,
            functions_checked=0,
            functions_verified=0,
            per_function=(),
            counterexamples=(),
            total_time_ms=(time.perf_counter() - t0) * 1000,
            tool_version="0.1.0",
        )
    analysis = analyze_effects(modules)
    vcs = generate_purity_vcs(modules, analysis)
    per_function_results = _rejected_results(modules)
    for vc in vcs:
        per_function_results.append(discharge(vc))
    verified = sum(1 for f in per_function_results if f.verdict == Verdict.VERIFIED)
    counterexamples = tuple(
        f.counterexample for f in per_function_results if f.counterexample is not None
    )
    return Report(
        package=dotted_prefix,
        property_name=property_name,
        verdict=_aggregate_verdict(per_function_results),
        functions_checked=len(per_function_results),
        functions_verified=verified,
        counterexamples=counterexamples,
        per_function=tuple(per_function_results),
        total_time_ms=(time.perf_counter() - t0) * 1000,
        tool_version="0.1.0",
    )
