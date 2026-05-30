"""The TelosProof advisory gate.

``telosproof_gate`` runs the conservative body extraction + the 8 protected-body
invariants over a unified diff and returns a
:class:`~dharma_swarm.models.GateCheckResult`:

* ``decision = BLOCK`` if any invariant is violated, else ``ALLOW``.
* ``proof_obligation`` carries the aggregate (first) violation, or a satisfied
  obligation when the patch is clean.
* ``reason`` summarises the outcome and lists the violated rule predicates.

ADVISORY BY DEFAULT — NOT WIRED INTO THE APPLY PATH
---------------------------------------------------
This module is *advisory*. Whether enforcement is "live" is read from the
``DHARMA_PROOF_ENFORCE`` environment variable (default ``"0"`` = advisory),
mirroring ``DHARMA_EVOLUTION_SHADOW`` in ``dgm_loop.py``. The module-level flag
``PROOF_ENFORCE`` exposes the parsed value.

WHAT THIS GATE IS — AND CRUCIALLY, WHAT IT IS NOT (read before trusting it)
--------------------------------------------------------------------------
This is a *regex/heuristic* advisory layer over a diff. Its positive checks
(invariants 2-7's named-marker vocabularies, and invariant 8's metadata
credential) are **INCOMPLETE BY CONSTRUCTION**: they enumerate a closed set of
markers, and any rename or synonym the proposer chooses can step outside that
set. Do NOT mistake this layer's ALLOW for a proof of safety.

* **Invariant (8) ``preserves_replay_rollback_metadata`` is SELF-SATISFIABLE
  and is NOT an adversarial defense.** The same untrusted proposer that writes
  the diff also supplies the ``replay_command`` / ``rollback_plan`` substrings
  (or metadata). It can self-credential (8) and pass it while doing something
  dangerous elsewhere. (8) only answers "did an *honest* author remember to
  attach replay/rollback notes?" — an integrity-of-honest-proposer check. It is
  worthless against an adversary acting in bad faith.

* **The real adversarial defense in v0 is the STRUCTURAL DENY-BY-DEFAULT
  BACKSTOP** (``ChangeSummary.net_removes_from_safety_surface`` →
  ``invariants.STRUCTURAL_BACKSTOP_PREDICATE``): any diff that net-removes lines
  from a safety-surface file (dgm_loop / diff_applier / telos_gates /
  dharma_kernel / telosproof, or a path naming approval/consent/witness/receipt/
  rollback/ledger) is forced to **REVIEW regardless of vocabulary**. That
  catches the synonym/rename bypass enumeration cannot. It is a coarse net, not
  a proof.

* **The actual proof lives in v1, not here.** Sound adversarial defense requires
  a Lean primitive-vocabulary (an allow-list, deny-by-default over a fixed set
  of safe primitives), not this regex layer. Until that lands, advisory output
  must NEVER be mistaken for proof — false-positives are acceptable, but an
  ALLOW from this layer is "no enumerated red flag found", not "safe".

IMPORTANT: even when ``DHARMA_PROOF_ENFORCE=1``, NOTHING in this v0 package
calls into ``diff_applier.apply`` / ``apply_and_test`` or ``dgm_loop``. The flag
only changes the ``severity`` field on the emitted obligation and is intended as
the future wiring switch. The integration point is *documented* below as a
commented (not executed) example. Turning advisory into enforcing is a
deliberate, operator-reviewed step — it is not done here.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dharma_swarm.models import (
    GateCheckResult,
    GateDecision,
    GateResult,
    ProofObligation,
)
from dharma_swarm.telosproof.change_summary import extract_change_summary
from dharma_swarm.telosproof.invariants import (
    GATE_NAME,
    STRUCTURAL_BACKSTOP_PREDICATE,
    check_invariants,
)


def _enforce_enabled() -> bool:
    """Read DHARMA_PROOF_ENFORCE (default 0 = advisory).

    Mirrors the DHARMA_EVOLUTION_SHADOW convention: a string "0"/"false"/""
    means OFF. Any other non-empty value means enforcement is requested.
    """
    raw = os.environ.get("DHARMA_PROOF_ENFORCE", "0").strip().lower()
    return raw not in ("", "0", "false", "no", "off")


# Module-level snapshot of the flag at import time. ADVISORY when False.
# Re-evaluated per-call inside telosproof_gate so tests can monkeypatch env.
PROOF_ENFORCE: bool = _enforce_enabled()


def telosproof_gate(
    diff_text: str,
    metadata: Optional[dict[str, Any]] = None,
) -> GateCheckResult:
    """Advisory proof-carrying-telos check over a self-modification *body*.

    Args:
        diff_text: A unified diff describing the proposed self-modification.
        metadata: Optional out-of-band context (e.g. ``replay_command`` /
            ``rollback_plan`` positive evidence). Passed straight through to
            ``extract_change_summary``.

    Returns:
        A :class:`GateCheckResult`. ``decision`` is ``BLOCK`` when any
        protected-body invariant is violated, else ``ALLOW``. The result is
        ADVISORY — no apply path consumes it in v0.
    """
    enforcing = _enforce_enabled()
    severity = "enforcing" if enforcing else "advisory"

    summary = extract_change_summary(diff_text, metadata)
    violations = check_invariants(summary)

    # Per-rule gate_results map (each violated invariant -> FAIL).
    gate_results: dict[str, tuple[GateResult, str]] = {}
    for v in violations:
        gate_results[v.predicate] = (GateResult.FAIL, "; ".join(v.evidence_required))

    if violations:
        # Aggregate / first violation becomes the carried obligation. We also
        # fold every violated predicate into evidence_required so the single
        # carried obligation reflects the full failure set.
        first = violations[0]
        aggregate = ProofObligation(
            gate_name=GATE_NAME,
            obligation_type=first.obligation_type,
            predicate=first.predicate,
            satisfied=False,
            evidence_required=[
                f"{v.predicate}: {'; '.join(v.evidence_required)}" for v in violations
            ],
            severity=severity,
        )
        violated_names = ", ".join(v.predicate for v in violations)

        # Decision mapping:
        #   * any HARD invariant violated -> BLOCK.
        #   * ONLY the structural deny-by-default backstop fired -> REVIEW.
        # The backstop (net-removal from a safety surface) is intentionally a
        # softer signal: it forces human eyes on rename/synonym edits that the
        # closed positive-marker vocabulary cannot classify, without asserting
        # the edit is definitely dangerous. It must NEVER collapse to ALLOW.
        non_backstop = [
            v for v in violations if v.predicate != STRUCTURAL_BACKSTOP_PREDICATE
        ]
        if non_backstop:
            decision = GateDecision.BLOCK
            verb = "BLOCK"
        else:
            decision = GateDecision.REVIEW
            verb = "REVIEW"

        reason = (
            f"TelosProof {verb} ({'enforcing' if enforcing else 'advisory'}): "
            f"{len(violations)} protected-body invariant(s) violated: {violated_names}"
        )
        return GateCheckResult(
            decision=decision,
            reason=reason,
            gate=GATE_NAME,
            gate_results=gate_results,
            proof_obligation=aggregate,
        )

    # Clean patch: ALLOW with a satisfied obligation recording what was proven.
    satisfied = ProofObligation(
        gate_name=GATE_NAME,
        obligation_type="safety_contract",
        predicate="all_protected_body_invariants_hold",
        satisfied=True,
        evidence_required=[],
        severity=severity,
    )
    return GateCheckResult(
        decision=GateDecision.ALLOW,
        reason=(
            f"TelosProof ALLOW ({'enforcing' if enforcing else 'advisory'}): "
            "all 8 protected-body invariants hold."
        ),
        gate=GATE_NAME,
        gate_results={},
        proof_obligation=satisfied,
    )


# ===========================================================================
# DOCUMENTED INTEGRATION POINT (COMMENTED — NOT EXECUTED IN v0)
# ===========================================================================
#
# TelosProof is advisory in v0 and is deliberately NOT wired into the live
# apply path. When the operator decides to promote it from advisory to
# enforcing, the gate would sit immediately BEFORE the patch is written —
# either in `diff_applier.DiffApplier.apply_and_test` (around line 273, just
# before the `apply_result = await self.apply(diff_text)` call at line 294) or
# in `dgm_loop.DGMLoop.run_one_generation` right after the existing protected-
# target check at line 351. The shape would be:
#
#     from dharma_swarm.telosproof import telosproof_gate, PROOF_ENFORCE
#     from dharma_swarm.models import GateDecision
#
#     # inside apply_and_test, BEFORE `await self.apply(diff_text)`:
#     proof = telosproof_gate(diff_text, metadata=patch_metadata)
#     if PROOF_ENFORCE and proof.decision is GateDecision.BLOCK:
#         return ApplyTestResult(
#             applied=False,
#             tests_passed=False,
#             error=proof.reason,
#             # proof.proof_obligation carries the violated invariant(s)
#         )
#     # advisory mode: emit `proof` to the witness log and continue.
#
# Until that operator-reviewed wiring lands, this package only ever *returns* a
# GateCheckResult; it never blocks, mutates, or rolls back anything.
# ===========================================================================
