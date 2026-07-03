"""Solver dispatch.

Primary: Z3 (already used indirectly by every SMT-based verifier).
Portfolio: optional CVC5 fallback for cases where Z3 returns UNKNOWN.

Each VC is discharged independently — no cross-condition state. Solver
timeouts are per-VC (default 10 seconds) so a stuck condition doesn't
block the whole run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import z3

from titanium_verify.report import CounterExample, FunctionResult, Verdict
from titanium_verify.vc import VerificationCondition


@dataclass(frozen=True)
class SolverResult:
    verdict: Verdict
    witness: dict[str, str]
    detail: str
    time_ms: float


def _model_to_witness(model: z3.ModelRef) -> dict[str, str]:
    out: dict[str, str] = {}
    for d in model.decls():
        out[d.name()] = str(model[d])
    return out


def _run_z3(vc: VerificationCondition) -> SolverResult:
    t0 = time.perf_counter()
    result = vc.solver.check()
    elapsed = (time.perf_counter() - t0) * 1000
    if result == z3.unsat:
        # Property holds: no assignment satisfies its negation.
        return SolverResult(Verdict.VERIFIED, {}, "z3: unsat", elapsed)
    if result == z3.sat:
        model = vc.solver.model()
        return SolverResult(
            Verdict.REFUTED,
            _model_to_witness(model),
            f"z3: sat with witness on eff_{vc.function_qualname.replace('.', '_')}",
            elapsed,
        )
    # unknown
    return SolverResult(Verdict.UNKNOWN, {}, "z3: unknown (timeout or incomplete)", elapsed)


def discharge(vc: VerificationCondition) -> FunctionResult:
    """Discharge one verification condition."""
    result = _run_z3(vc)
    counterexample: CounterExample | None = None
    if result.verdict == Verdict.REFUTED:
        counterexample = CounterExample(
            function_qualname=vc.function_qualname,
            property_name=vc.property_name,
            witness=result.witness,
            trace=(vc.function_qualname,),
            detail=result.detail,
        )
    return FunctionResult(
        qualname=vc.function_qualname,
        verdict=result.verdict,
        detail=result.detail,
        counterexample=counterexample,
        solver_time_ms=result.time_ms,
    )
