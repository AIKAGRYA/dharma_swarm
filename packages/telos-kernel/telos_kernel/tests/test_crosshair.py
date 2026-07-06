"""Crosshair SMT-guided counterexample search on icontract-decorated functions.

Crosshair searches for inputs that violate declared contracts. This adds an
adversarial verifier on top of Nagini (sound-verifier) and Hypothesis
(property-based random).

Skips if `crosshair` is not installed (local dev). CI enables via
`.github/workflows/kernel-crosshair.yml`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

KERNEL_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    "telos_kernel.capabilities.add_first_party_caveat",
    "telos_kernel.checker.verify_certificate",
    "telos_kernel.manifest.Manifest.verify_quorum",
]


@pytest.mark.skipif(shutil.which("crosshair") is None, reason="crosshair not installed")
@pytest.mark.parametrize("target", TARGETS)
def test_crosshair_check(target):
    result = subprocess.run(
        ["crosshair", "check", target, "--per_condition_timeout=8"],
        capture_output=True, text=True, timeout=300,
    )
    # crosshair returns 0 when no counterexample found in the budget.
    # Non-zero indicates a counterexample or an internal error; both block merge.
    assert result.returncode == 0, (
        f"Crosshair found a counterexample or error in {target}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
