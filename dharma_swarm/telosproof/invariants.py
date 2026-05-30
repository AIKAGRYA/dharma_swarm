"""The 8 protected-body invariants a self-modification patch must satisfy.

Each invariant is a pure predicate over a :class:`ChangeSummary` (the BODY of
the patch). A *violated* invariant produces one
:class:`~dharma_swarm.models.ProofObligation` with ``satisfied=False`` whose
``predicate`` names the rule. ``check_invariants`` returns the list of violated
obligations (empty == all invariants hold).

Body, not mind: every predicate inspects only what the diff literally touches /
adds / removes. No intent is inferred.

Invariant (1) — "touches no DGM-protected file" — REUSES the live
``DGM_PROTECTED_FILES`` frozenset and ``_is_protected_dgm_target`` from
``dgm_loop.py``. The list is NOT duplicated here; we import and call the
authoritative helper so the two layers can never drift.
"""

from __future__ import annotations

from dharma_swarm.dgm_loop import DGM_PROTECTED_FILES, _is_protected_dgm_target
from dharma_swarm.models import ProofObligation
from dharma_swarm.telosproof.change_summary import ChangeSummary


GATE_NAME = "telosproof"

# Predicate name for the structural deny-by-default backstop (not one of the 8
# enumerated invariants). The gate special-cases this to decide REVIEW vs BLOCK:
# when it is the ONLY violation, the decision is REVIEW; when a harder invariant
# also fired, the decision is BLOCK.
STRUCTURAL_BACKSTOP_PREDICATE = "net_removes_from_safety_surface"


def _obligation(predicate: str, evidence: list[str]) -> ProofObligation:
    """Build an unsatisfied safety-contract obligation for a violated rule."""
    return ProofObligation(
        gate_name=GATE_NAME,
        obligation_type="safety_contract",
        predicate=predicate,
        satisfied=False,
        evidence_required=evidence,
        severity="advisory",
    )


# ---------------------------------------------------------------------------
# Invariant (1): touches no DGM-protected file
# ---------------------------------------------------------------------------

def _protected_targets(summary: ChangeSummary) -> list[str]:
    """Return touched paths that hit a DGM-protected file (authoritative)."""
    hits: list[str] = []
    for p in summary.touched_paths:
        try:
            if _is_protected_dgm_target(p):
                hits.append(p)
        except Exception:
            # Unparseable path: conservative — treat as a protected hit so a
            # malformed path can never sneak past as "safe" (no false-negative).
            hits.append(p)
    return hits


# ---------------------------------------------------------------------------
# check_invariants — one ProofObligation per violated rule
# ---------------------------------------------------------------------------

def check_invariants(summary: ChangeSummary) -> list[ProofObligation]:
    """Return the list of violated protected-body invariants.

    An empty list means all 8 invariants hold. Order is stable (1..8) so the
    gate can deterministically pick the first / aggregate violation.
    """
    violations: list[ProofObligation] = []

    # (1) touches no DGM-protected file -- REUSES the live frozenset.
    protected_hits = _protected_targets(summary)
    if protected_hits:
        violations.append(
            _obligation(
                "touches_no_dgm_protected_file",
                evidence=[
                    f"touched protected file(s): {', '.join(protected_hits)}",
                    f"protected set: {sorted(DGM_PROTECTED_FILES)}",
                ],
            )
        )

    # (2) does not disable receipt emission.
    if summary.disables_receipts:
        violations.append(
            _obligation(
                "does_not_disable_receipt_emission",
                evidence=["diff removes a receipt/witness emitter or sets receipts off"],
            )
        )

    # (3) does not disable rollback.
    if summary.disables_rollback:
        violations.append(
            _obligation(
                "does_not_disable_rollback",
                evidence=["diff removes a rollback/backup path or disables rollback"],
            )
        )

    # (4) does not bypass human approval.
    if summary.bypasses_human_approval:
        violations.append(
            _obligation(
                "does_not_bypass_human_approval",
                evidence=["diff removes an approval gate or auto-approves"],
            )
        )

    # (5) does not raise autonomy level.
    if summary.raises_autonomy:
        violations.append(
            _obligation(
                "does_not_raise_autonomy_level",
                evidence=["diff adds a line raising autonomy / unlocking a higher level"],
            )
        )

    # (6) does not disable shadow mode.
    if summary.disables_shadow_mode:
        violations.append(
            _obligation(
                "does_not_disable_shadow_mode",
                evidence=["diff turns shadow mode off or edits DHARMA_EVOLUTION_SHADOW"],
            )
        )

    # (7) creates no new persistence substrate.
    if summary.creates_new_persistence:
        violations.append(
            _obligation(
                "creates_no_new_persistence_substrate",
                evidence=["diff opens a DB/file store or adds a persistence-store file"],
            )
        )

    # (8) preserves replay/rollback metadata.
    # Conservative credential check: BOTH a replay command AND a rollback plan
    # must be positively present. Absence of either (the on-doubt default)
    # violates the invariant, triggering human review rather than silent pass.
    #
    # ADVERSARIAL CAVEAT (read before relying on this): invariant (8) is
    # SELF-SATISFIABLE. The same untrusted proposer that authors the diff also
    # supplies the replay_command / rollback_plan substrings (or metadata) — it
    # can self-credential this check and pass it while doing something dangerous
    # elsewhere. (8) is an INTEGRITY-OF-HONEST-PROPOSER check (did a well-meaning
    # author remember to attach replay/rollback notes?), NOT an adversarial
    # defense. The adversarial defense is the structural backstop below
    # (net-removal from a safety surface) plus the v1 Lean primitive-vocabulary
    # allow-list — never (8) alone.
    if not (summary.has_replay_command and summary.has_rollback_plan):
        missing: list[str] = []
        if not summary.has_replay_command:
            missing.append("replay_command")
        if not summary.has_rollback_plan:
            missing.append("rollback_plan")
        violations.append(
            _obligation(
                "preserves_replay_rollback_metadata",
                evidence=[f"missing required metadata: {', '.join(missing)}"],
            )
        )

    # (9) STRUCTURAL BACKSTOP — deny-by-default on safety-surface net-removal.
    # This is NOT one of the 8 enumerated body invariants; it is the adversarial
    # backstop that catches synonym/rename bypass the closed positive-marker
    # vocabularies (2)-(7) cannot. Any diff that NET-REMOVES lines from a file
    # on a safety surface (dgm_loop / diff_applier / telos_gates / dharma_kernel
    # / telosproof, or a path naming approval/consent/witness/receipt/rollback/
    # ledger) trips this REGARDLESS of vocabulary. The gate maps it to REVIEW
    # (not silent ALLOW) when no harder invariant already fired.
    if summary.net_removes_from_safety_surface:
        violations.append(
            _obligation(
                STRUCTURAL_BACKSTOP_PREDICATE,
                evidence=[
                    "net-removal of lines from a safety-surface file "
                    "(deny-by-default; vocabulary-independent backstop)",
                ],
            )
        )

    return violations
