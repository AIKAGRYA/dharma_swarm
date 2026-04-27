"""chetana.governance — gate check + axiom signing for atom promotion.

This is the L4 governance overlay's PYTHON entry point. Every chetana.promote
call must pass through gate_check_atom() before the atom enters the trusted
substrates (wiki, memory graph). Failure modes:

    BLOCK — Tier A or B gate fired; atom rejected, never written
    WARN  — Tier C gate fired; atom written with review_status='staged'
    ALLOW — no gate fired; atom written with review_status='approved'
            (if auto_promote=True) or 'staged' (default)

The gates themselves are dharma_swarm.telos_gates.TelosGatekeeper. The kernel
identity is dharma_swarm.dharma_kernel.KernelGuard. chetana governance does
NOT re-implement either; it ROUTES through them and records the decision into
provenance frontmatter.

Council finding (2026-04-27): the underlying gates currently use substring
matching, not semantic evaluation. This module honors that limitation — it does
NOT add a separate semantic layer. When the council's Phase 6b semantic gates
land, this module benefits without changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .provenance import (
    AtomProvenance,
    GateCheckRecord,
    GateResult,
    ReviewStatus,
    compute_axiom_signature,
    now_iso,
)

logger = logging.getLogger(__name__)

WITNESS_DIR = Path.home() / ".dharma" / "witness" / "chetana"


@dataclass
class GovernanceCheck:
    """Result of a chetana governance pass over an atom."""

    result: GateResult
    record: GateCheckRecord
    axiom_signature: str
    kernel_signature: str
    can_promote: bool  # False on BLOCK; True on WARN (with review) or ALLOW

    def to_provenance(
        self, *, promoted_by: str, review_status: ReviewStatus, reviewer: str | None = None
    ) -> AtomProvenance:
        return AtomProvenance(
            promoted_by=promoted_by,
            promoted_at=now_iso(),
            gate_check=self.record,
            axiom_signature=self.axiom_signature,
            review_status=review_status,
            reviewer=reviewer,
        )


def gate_check_atom(
    *,
    atom_content: str,
    atom_title: str,
    requested_action: str = "promote_atom",
    metadata: dict[str, Any] | None = None,
) -> GovernanceCheck:
    """Run an atom's content through the dharma_swarm telos gates.

    Imports TelosGatekeeper + KernelGuard lazily so chetana can be installed
    and unit-tested without the full dharma_swarm runtime present.
    """
    metadata = metadata or {}

    # Try to use the real gatekeeper. Fall back to PERMISSIVE-WITH-WITNESS
    # if dharma_swarm internals aren't importable in the current env (e.g.
    # the package is checked out but not pip install -e .'d, or this is a
    # standalone import test).
    try:
        from dharma_swarm.telos_gates import TelosGatekeeper  # type: ignore
        from dharma_swarm.dharma_kernel import KernelGuard  # type: ignore
    except ImportError as e:
        logger.warning(
            "chetana.governance: dharma_swarm not importable (%s); running in PERMISSIVE mode. "
            "Install dharma_swarm (pip install -e .) for real governance.",
            e,
        )
        return _permissive_check(atom_content, requested_action)

    kernel = KernelGuard()
    kernel_sig = "0" * 64
    try:
        loaded = kernel.load()
        if hasattr(loaded, "__await__"):
            # KernelGuard.load() in dharma_swarm is async; run it to completion.
            import asyncio as _aio

            try:
                _aio.get_event_loop().run_until_complete(loaded)
            except RuntimeError:
                _aio.run(loaded)
        kernel_sig = getattr(getattr(kernel, "kernel", None), "signature", None) or kernel_sig  # type: ignore[arg-type]
    except Exception as e:
        logger.warning("KernelGuard.load() failed (%s); using zero-signature.", e)

    gatekeeper = TelosGatekeeper()
    full_action_text = f"{requested_action}: {atom_title}\n\n{atom_content}"
    try:
        gate_result = gatekeeper.check_action(full_action_text)
    except Exception as e:
        logger.warning("TelosGatekeeper.check_action() failed (%s); permissive fallback.", e)
        return _permissive_check(atom_content, requested_action, kernel_sig=kernel_sig)

    # Translate dharma_swarm GateCheckResult → chetana GateCheckRecord.
    # The dharma_swarm result has fields like .decision (ALLOW/WARN/BLOCK),
    # .triggered_gates, .reasons. Be defensive.
    decision = _coerce_decision(getattr(gate_result, "decision", None))
    triggered = list(getattr(gate_result, "triggered_gates", []) or [])
    reasons = getattr(gate_result, "reasons", None)
    rationale = (
        "; ".join(reasons) if isinstance(reasons, (list, tuple)) else (reasons or None)
    )

    if decision == "BLOCK":
        gates_blocked = triggered
        gates_warned: list[str] = []
        gates_passed: list[str] = []
        can_promote = False
    elif decision == "WARN":
        gates_blocked = []
        gates_warned = triggered
        gates_passed = []
        can_promote = True
    else:
        gates_blocked = []
        gates_warned = []
        gates_passed = ["all_gates_clear"]
        can_promote = True

    record = GateCheckRecord(
        result=decision,
        gates_passed=gates_passed,
        gates_warned=gates_warned,
        gates_blocked=gates_blocked,
        rationale=rationale,
        checked_at=now_iso(),
    )
    sig = compute_axiom_signature(atom_content, kernel_sig)

    _write_witness(record, atom_title, sig, kernel_sig)

    return GovernanceCheck(
        result=decision,
        record=record,
        axiom_signature=sig,
        kernel_signature=kernel_sig,
        can_promote=can_promote,
    )


def _permissive_check(
    atom_content: str, requested_action: str, kernel_sig: str | None = None
) -> GovernanceCheck:
    """Fallback when dharma_swarm internals aren't available."""
    kernel_sig = kernel_sig or ("0" * 64)
    record = GateCheckRecord(
        result="WARN",
        gates_passed=[],
        gates_warned=["chetana_permissive_mode"],
        gates_blocked=[],
        rationale=(
            "dharma_swarm.telos_gates not importable; chetana ran in permissive mode. "
            "All atoms are written with review_status='staged' for human review."
        ),
        checked_at=now_iso(),
    )
    sig = compute_axiom_signature(atom_content, kernel_sig)
    return GovernanceCheck(
        result="WARN",
        record=record,
        axiom_signature=sig,
        kernel_signature=kernel_sig,
        can_promote=True,
    )


def _coerce_decision(raw: Any) -> GateResult:
    if raw is None:
        return "ALLOW"
    s = str(raw).upper()
    s = s.split(".")[-1]  # GateDecision.BLOCK -> BLOCK
    if s in ("ALLOW", "PASS", "OK"):
        return "ALLOW"
    if s in ("WARN", "WARNING", "REVIEW", "ADVISORY"):
        return "WARN"
    if s in ("BLOCK", "DENY", "REJECT", "FAIL"):
        return "BLOCK"
    return "WARN"  # conservative default


def _write_witness(
    record: GateCheckRecord, atom_title: str, sig: str, kernel_sig: str
) -> None:
    try:
        WITNESS_DIR.mkdir(parents=True, exist_ok=True)
        path = WITNESS_DIR / f"{record.checked_at.replace(':', '-')}.jsonl"
        line = (
            f'{{"checked_at": "{record.checked_at}", "atom_title": '
            f'{atom_title!r}, "result": "{record.result}", "axiom_signature": '
            f'"{sig}", "kernel_signature": "{kernel_sig}"}}\n'
        )
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:  # pragma: no cover
        logger.warning("chetana witness write failed: %s", e)
