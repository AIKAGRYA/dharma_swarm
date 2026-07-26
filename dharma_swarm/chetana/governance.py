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

import asyncio
import inspect
import json
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

    # Try to use the real gatekeeper. Chetana is a trust-writing surface, so
    # governance degradation is fail-closed: no real gates, no trusted write.
    try:
        from dharma_swarm.telos_gates import TelosGatekeeper  # type: ignore
        from dharma_swarm.dharma_kernel import KernelGuard  # type: ignore
    except ImportError as e:
        logger.warning(
            "chetana.governance: dharma_swarm not importable (%s); blocking trusted write. "
            "Install dharma_swarm (pip install -e .) for real governance.",
            e,
        )
        return _fail_closed_check(
            atom_content=atom_content,
            atom_title=atom_title,
            requested_action=requested_action,
            reason=f"dharma_swarm governance imports unavailable: {type(e).__name__}: {e}",
        )

    kernel = KernelGuard()
    kernel_sig_placeholder = "0" * 64
    kernel_sig = kernel_sig_placeholder
    kernel_sig_degraded_reason: str | None = None
    try:
        loaded = kernel.load()
        if inspect.isawaitable(loaded):
            loaded = _run_sync_awaitable(loaded)
        resolved = (
            getattr(loaded, "signature", None)
            or getattr(getattr(kernel, "_kernel", None), "signature", None)
        )
        if resolved:
            kernel_sig = resolved
        else:
            reason = (
                "KernelGuard.load() returned but neither loaded.signature nor "
                "kernel._kernel.signature was available; blocking trusted write."
            )
            logger.warning("chetana.governance: %s", reason)
            return _fail_closed_check(
                atom_content=atom_content,
                atom_title=atom_title,
                requested_action=requested_action,
                reason=reason,
                kernel_sig=kernel_sig,
            )
    except Exception as e:
        reason = (
            f"KernelGuard.load() raised {type(e).__name__}: {e}; "
            "blocking trusted write."
        )
        logger.warning("chetana.governance: %s", reason)
        return _fail_closed_check(
            atom_content=atom_content,
            atom_title=atom_title,
            requested_action=requested_action,
            reason=reason,
            kernel_sig=kernel_sig,
        )

    gatekeeper = TelosGatekeeper()
    action_line = f"{requested_action}: {atom_title}"
    try:
        gate_result = gatekeeper.check(action=action_line, content=atom_content)
    except Exception as e:
        reason = f"TelosGatekeeper.check() raised {type(e).__name__}: {e}; blocking trusted write."
        logger.warning("chetana.governance: %s", reason)
        return _fail_closed_check(
            atom_content=atom_content,
            atom_title=atom_title,
            requested_action=requested_action,
            reason=reason,
            kernel_sig=kernel_sig,
        )

    # Translate dharma_swarm GateCheckResult → chetana GateCheckRecord.
    # Real shape (verified 2026-04-27 against installed dharma_swarm):
    #   decision: GateDecision enum (ALLOW | BLOCK | REVIEW)
    #   gate: str — the single gate that fired (or "" on ALLOW)
    #   gate_results: list of per-gate detail records
    #   reason: str — human-readable rationale
    #   timestamp: str
    decision = _coerce_decision(getattr(gate_result, "decision", None))
    primary_gate = getattr(gate_result, "gate", "") or ""
    triggered = [primary_gate] if primary_gate else []
    rationale = getattr(gate_result, "reason", None) or None
    if kernel_sig_degraded_reason:
        prefix = "[zero-signature] "
        rationale = prefix + (rationale or "no gate rationale") + (
            f" — degradation: {kernel_sig_degraded_reason}"
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


def _fail_closed_check(
    *,
    atom_content: str,
    atom_title: str,
    requested_action: str,
    reason: str,
    kernel_sig: str | None = None,
) -> GovernanceCheck:
    """Return a BLOCK result when the real governance path is unavailable."""
    kernel_sig = kernel_sig or ("0" * 64)
    record = GateCheckRecord(
        result="BLOCK",
        gates_passed=[],
        gates_warned=[],
        gates_blocked=["chetana_governance_unavailable"],
        rationale=f"{requested_action}: {reason}",
        checked_at=now_iso(),
    )
    sig = compute_axiom_signature(atom_content, kernel_sig)
    _write_witness(record, atom_title, sig, kernel_sig)
    return GovernanceCheck(
        result="BLOCK",
        record=record,
        axiom_signature=sig,
        kernel_signature=kernel_sig,
        can_promote=False,
    )


def _coerce_decision(raw: Any) -> GateResult:
    """Map any of {Enum, str, value} to chetana's GateResult literal.

    Handles GateDecision.ALLOW / .BLOCK / .REVIEW (the dharma_swarm enum), plus
    string variants. REVIEW maps to WARN (chetana's middle tier). Anything
    unrecognized fails closed to BLOCK — chetana writes trust, so an unknown
    gate verdict must never promote. That includes None: a GateCheckResult
    whose ``decision`` attribute is missing (interface drift) must not read
    as ALLOW.
    """
    if raw is None:
        return "BLOCK"
    # Try the enum's .value first ('allow' | 'block' | 'review')
    val = getattr(raw, "value", None)
    if isinstance(val, str):
        s = val.upper()
    else:
        s = str(raw).split(".")[-1].upper()
    if s in ("ALLOW", "PASS", "OK"):
        return "ALLOW"
    if s in ("WARN", "WARNING", "REVIEW", "ADVISORY"):
        return "WARN"
    if s in ("BLOCK", "DENY", "REJECT", "FAIL"):
        return "BLOCK"
    return "BLOCK"  # unknown verdict → fail closed


def current_kernel_signature() -> str:
    """Load the current kernel signature via a plain file read (event-loop safe).

    Returns the 64-zero placeholder when the kernel is unavailable or fails
    integrity — callers treat placeholder-signed material as zero-sig.
    """
    placeholder = "0" * 64
    try:
        from dharma_swarm.dharma_kernel import DharmaKernel, KernelGuard  # type: ignore

        kernel_path = KernelGuard().path
        text = kernel_path.read_text(encoding="utf-8")
        kernel = DharmaKernel.model_validate_json(text)
        if kernel.verify_integrity() and kernel.signature:
            return kernel.signature
    except (ImportError, OSError, ValueError) as exc:
        # Kernel missing/unreadable/invalid (pydantic ValidationError is a
        # ValueError): fall back to the zero-sig placeholder. Anything else
        # propagates — an unexpected failure should fail the approval loudly,
        # not silently downgrade it to placeholder-signed material.
        logger.debug("chetana kernel signature unavailable, using placeholder: %s", exc)
    return placeholder


def _run_sync_awaitable(awaitable: Any) -> Any:
    """Resolve an awaitable from this sync API when no event loop is active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    close = getattr(awaitable, "close", None)
    if callable(close):
        close()
    raise RuntimeError("cannot synchronously load kernel while an event loop is running")


def _write_witness(
    record: GateCheckRecord, atom_title: str, sig: str, kernel_sig: str
) -> None:
    try:
        WITNESS_DIR.mkdir(parents=True, exist_ok=True)
        path = WITNESS_DIR / f"{record.checked_at.replace(':', '-')}.jsonl"
        payload = {
            "checked_at": record.checked_at,
            "atom_title": atom_title,
            "result": record.result,
            "axiom_signature": sig,
            "kernel_signature": kernel_sig,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception as e:  # pragma: no cover
        logger.warning("chetana witness write failed: %s", e)
