"""Anti-metaphor discipline check — every U-invariant with a Sanskrit or
philosophical name must have (a) measure, (b) threshold, (c) citation.

Phase 0: warning-only (all kernel/manifest.yaml invariants already comply).
Phase 1+: becomes blocking; PRs introducing named-only gates fail CI.
"""
from __future__ import annotations

from telos_kernel.manifest import load_manifest


def test_every_invariant_has_measure_threshold_citation():
    m = load_manifest()
    offenders = []
    for inv in m.invariants:
        if not inv.measure.strip():
            offenders.append(f"{inv.id}: missing measure")
        if not inv.threshold:
            offenders.append(f"{inv.id}: missing threshold")
        if not inv.citations:
            offenders.append(f"{inv.id}: missing citations")
    assert not offenders, (
        "Anti-metaphor discipline violated. Every U-invariant must have a "
        "measure, threshold, and citation:\n  " + "\n  ".join(offenders)
    )
