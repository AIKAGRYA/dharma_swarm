"""End-to-end: titanium-verify must certify the real telos-kernel package.

This is the load-bearing test. If it passes, we have a mathematical proof
(modulo Z3's soundness) that every non-rim function in the TCB is pure.

If it fails, either:
    (a) A core module leaked an effect and needs to move to the rim, or
    (b) The verifier's frontend or effect analysis has a bug.

Either way, this is the check that runs in CI as the merge blocker.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from titanium_verify.report import Verdict
from titanium_verify.verifier import verify_package


# parents[0]=tests, [1]=titanium_verify, [2]=titanium-verify pkg,
# [3]=packages, [4]=repo root.
TELOS_KERNEL_ROOT = (
    Path(__file__).resolve().parents[3]
    / "telos-kernel" / "telos_kernel"
)


@pytest.mark.skipif(
    not TELOS_KERNEL_ROOT.exists(),
    reason=f"telos_kernel not found at {TELOS_KERNEL_ROOT}",
)
def test_titanium_verify_certifies_telos_kernel_purity():
    report = verify_package(
        TELOS_KERNEL_ROOT,
        dotted_prefix="telos_kernel",
        property_name="purity",
    )
    # Print detail on failure for easy debugging.
    if report.verdict != Verdict.VERIFIED:
        print(f"\ntitanium-verify report ({report.verdict.value}):")
        print(f"  functions_checked: {report.functions_checked}")
        print(f"  functions_verified: {report.functions_verified}")
        for f in report.per_function:
            if f.verdict != Verdict.VERIFIED:
                print(f"  - {f.qualname}: {f.verdict.value} — {f.detail}")
    assert report.verdict == Verdict.VERIFIED, (
        f"telos_kernel purity check FAILED with verdict={report.verdict.value}. "
        f"Counterexamples: {[c.function_qualname for c in report.counterexamples]}. "
        f"Rejected: {[f.qualname for f in report.per_function if f.verdict == Verdict.REJECTED]}."
    )


@pytest.mark.skipif(
    not TELOS_KERNEL_ROOT.exists(),
    reason=f"telos_kernel not found at {TELOS_KERNEL_ROOT}",
)
def test_titanium_verify_covers_all_core_functions():
    report = verify_package(
        TELOS_KERNEL_ROOT,
        dotted_prefix="telos_kernel",
        property_name="purity",
    )
    # Sanity floor: we should be checking at least a few dozen functions,
    # not zero. If this drops precipitously, something is wrong with the
    # frontend or path resolution.
    assert report.functions_checked >= 30, (
        f"only {report.functions_checked} functions checked — frontend may be "
        f"misconfigured. Report: {report}"
    )
