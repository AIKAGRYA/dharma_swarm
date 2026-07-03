"""Nagini soundness — sound static verifier for a Python subset.

Runs `nagini` on the kernel core modules. Skips if `nagini` is not installed
(local dev ergonomics); CI installs it via `.github/workflows/kernel-nagini.yml`.

References:
  * marcoeilers/nagini: https://github.com/marcoeilers/nagini
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

KERNEL_ROOT = Path(__file__).resolve().parents[1]

# Modules Phase 0 asks Nagini to check. `checker.py` is a stub; the others
# are the core signing/serialization path.
TARGETS = [
    KERNEL_ROOT / "merkle_log.py",
    KERNEL_ROOT / "receipt.py",
    KERNEL_ROOT / "manifest.py",
    KERNEL_ROOT / "checker.py",
]


@pytest.mark.skipif(shutil.which("nagini") is None, reason="nagini not installed")
@pytest.mark.parametrize("target", TARGETS, ids=lambda p: p.name)
def test_nagini_passes(target):
    result = subprocess.run(
        ["nagini", "--select", "unsound-verification", str(target)],
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, (
        f"Nagini failed on {target.name}:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
