"""Observe-only receipt overlays for Telos gate checks.

The legacy Telos gatekeeper remains the enforcing authority. This module
attaches formal-gate and optional Titanium Merkle receipt metadata to the same
``GateCheckResult`` object without changing its decision.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.models import GateCheckResult, GateDecision


def enrich_gate_result_with_formal_receipts(
    result: GateCheckResult,
    *,
    action: str,
    content: str = "",
    tool_name: str = "",
    formal_context: Any | None = None,
    receipt_log: Any | None = None,
) -> GateCheckResult:
    """Attach formal/Titanium receipt metadata without changing enforcement.

    ``receipt_log`` is explicit capability injection. Without it, this function
    never creates ambient Merkle authority and only records the local formal
    SHA-256 report.
    """
    metadata = dict(result.metadata or {})
    try:
        from dharma_swarm.telos_formal import evaluate_formal_gates
        from dharma_swarm.telos_formal_models import ActionContext

        if formal_context is None:
            context = ActionContext(action=action)
        elif isinstance(formal_context, dict):
            context = ActionContext(**formal_context)
        else:
            context = formal_context

        report = evaluate_formal_gates(context)
        canonical_payload = report._canonical_payload()
        formal_meta: dict[str, Any] = {
            "status": "ok",
            "mode": "observe_only",
            "decision": report.decision.value,
            "receipt_sha256": report.receipt_sha256,
            "tool_name": tool_name,
            "content_sha256": _sha256_text(content),
            "canonical_payload": canonical_payload,
        }

        if receipt_log is not None:
            formal_meta["titanium"] = _append_titanium_receipt(
                report=report,
                canonical_payload=canonical_payload,
                receipt_log=receipt_log,
            )

        metadata["formal_telos"] = formal_meta
    except Exception as exc:
        metadata["formal_telos"] = {
            "status": "error",
            "mode": "observe_only",
            "error_type": type(exc).__name__,
        }

    result.metadata = metadata
    return result


def _append_titanium_receipt(
    *,
    report: Any,
    canonical_payload: dict[str, Any],
    receipt_log: Any,
) -> dict[str, Any]:
    try:
        from telos_kernel import check
        from telos_kernel.receipt import Tier, Verdict
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
        }

    verdict = {
        GateDecision.ALLOW: Verdict.ALLOW,
        GateDecision.REVIEW: Verdict.REVIEW,
        GateDecision.BLOCK: Verdict.BLOCK,
    }.get(report.decision, Verdict.REVIEW)

    try:
        leaf = check(
            gate="U5_tool_check_report",
            tier=Tier.C,
            measure=canonical_payload,
            threshold={"observe_only": True},
            verdict=verdict,
            log=receipt_log,
        )
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
        }

    head_hash = receipt_log.head_hash() if hasattr(receipt_log, "head_hash") else ""
    return {
        "status": "ok",
        "gate": leaf.gate,
        "proposal_id": leaf.proposal_id,
        "verdict": leaf.verdict.value,
        "merkle_head": head_hash,
    }


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
