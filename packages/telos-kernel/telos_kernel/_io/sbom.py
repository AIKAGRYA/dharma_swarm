"""SBOM digest \u2014 filesystem walk over kernel modules.

The boot receipt includes a SHA-256 digest of the kernel's own bytes.
This walk is impure (reads sys.executable, walks Path.rglob) and lives
in the rim; the core `boot()` calls this via the import edge that
`test_no_effects_in_core.py` allows only for boot bookkeeping.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from telos_kernel.effects import Effect, effect


@effect(Effect.FS_READ)
def compute_sbom_digest() -> str:
    """Return a SHA-256 hex digest binding the current interpreter and the
    hashes of every core kernel .py file. Rim files (this subpackage) are
    excluded so rim churn does not invalidate boot receipts.
    """
    tcb_root = Path(__file__).resolve().parents[1]  # telos_kernel/
    parts = [
        f"python_version={sys.version_info[:3]}",
        f"executable_hash={hashlib.sha256(sys.executable.encode('utf-8')).hexdigest()}",
    ]
    for p in sorted(tcb_root.rglob("*.py")):
        # Exclude rim: rim churn is not part of the TCB integrity claim.
        if "/_io/" in str(p) or "\\_io\\" in str(p):
            continue
        # Exclude tests.
        if "/tests/" in str(p) or "\\tests\\" in str(p):
            continue
        with open(p, "rb") as f:
            parts.append(
                f"{p.relative_to(tcb_root)}={hashlib.sha256(f.read()).hexdigest()}"
            )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
