"""Shared Council invariants (spec §2, §6).

One verifier substrate, multiple profiles. These invariants hold for EVERY
profile and are the load-bearing moat against fitness corruption:

  * Quarantine untrusted / contaminated input before it can corroborate anything.
  * Require >=2 decorrelated EVALUATOR families AND >=2 decorrelated SOURCE
    families to reach a ``corroborated`` verdict (the decorrelated moat).
  * Replayable receipts: same inputs -> same verdict + same inputs hash.
  * No hidden action authority: Council receipts preserve
    ``dispatch_authority=False`` unless explicitly transformed by a LATER warrant
    layer (not built in this keystone).
  * Explicit verdicts only: corroborated / refuted / insufficient / quarantined.

CORRECTNESS-AUTHORITY SPLIT (Codex's G sharpening): for Arena v1's verifiable
tasks the deterministic scorer / test-oracle is the SOLE correctness authority.
The Council verifies *trace integrity, contamination boundaries, evidence
sufficiency, and the "this genome beat controls" promotion claim* — NEVER
correctness itself. There is deliberately no ``correct`` verdict in the
vocabulary, and no Council code path may assert task correctness.
"""

from __future__ import annotations

from typing import Literal

# The ONLY verdicts the Council may emit. Note the conspicuous absence of any
# "correct"/"incorrect" verdict: correctness is the scorer's authority, not the
# Council's (spec §2, §6 invariant 2).
Verdict = Literal["corroborated", "refuted", "insufficient", "quarantined"]

VALID_VERDICTS: frozenset[str] = frozenset(
    {"corroborated", "refuted", "insufficient", "quarantined"}
)

# Decorrelated-moat thresholds (spec §2 shared invariant).
MIN_EVALUATOR_FAMILIES = 2
MIN_SOURCE_FAMILIES = 2

# Council NEVER holds dispatch authority in this build.
DISPATCH_AUTHORITY = False


def meets_decorrelation(evaluator_families: set[str], source_families: set[str]) -> bool:
    """True iff the decorrelated-moat thresholds are met."""
    return (
        len(evaluator_families) >= MIN_EVALUATOR_FAMILIES
        and len(source_families) >= MIN_SOURCE_FAMILIES
    )


__all__ = [
    "DISPATCH_AUTHORITY",
    "MIN_EVALUATOR_FAMILIES",
    "MIN_SOURCE_FAMILIES",
    "VALID_VERDICTS",
    "Verdict",
    "meets_decorrelation",
]
