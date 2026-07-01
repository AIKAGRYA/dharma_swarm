"""Sequential alpha-spending receipt for Forge promotion evidence.

This module records whether an analysis sequence stayed within a frozen alpha
budget.  It is deliberately non-authoritative: passing here only gives a payload
that can be signed as ``sequential_alpha_spending``.  Promotion still requires
``verify_promotion`` with trusted signed receipts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.sequential_alpha_spending_receipt.v1"
RECEIPT_NAME = "sequential_alpha_spending"
DEFAULT_ALPHA_TOTAL = 0.05


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _row_id(row: Mapping[str, Any], fallback: int) -> str:
    return str(row.get("look_id") or row.get("analysis_id") or f"look-{fallback}")


def evaluate_alpha_spending(
    looks: Iterable[Mapping[str, Any]],
    *,
    alpha_total: float = DEFAULT_ALPHA_TOTAL,
    require_confirm_final_only: bool = True,
) -> dict[str, Any]:
    """Build a fail-closed receipt for a sequential analysis log.

    Expected row shape is intentionally minimal:

    - ``look_index``: 1-based sequence number.
    - ``alpha_spent`` or ``alpha``: alpha budget consumed at that look.
    - optional ``p_value`` and ``decision``.
    - optional ``split`` and ``final``.

    A success stop must clear that look's alpha boundary, the cumulative spend
    must not exceed ``alpha_total``, and CONFIRM analyses may not be adaptively
    replanned or used for non-final peeking.
    """
    rows = [dict(row) for row in looks]
    blockers: list[str] = []
    normalized: list[dict[str, Any]] = []
    cumulative = 0.0
    seen_ids: set[str] = set()

    if not rows:
        blockers.append("missing_alpha_spending_rows")

    for offset, row in enumerate(rows, start=1):
        look_index = _safe_int(row.get("look_index") or row.get("index"), offset)
        look_id = _row_id(row, offset)
        alpha_spent = _safe_float(
            row.get("alpha_spent") or row.get("alpha") or row.get("alpha_budget")
        )
        p_value = _safe_float(row.get("p_value"), 1.0)
        decision = str(row.get("decision") or "").strip()
        split = str(row.get("split") or "").strip()
        final = bool(row.get("final"))
        cumulative = round(cumulative + alpha_spent, 12)

        if look_id in seen_ids:
            blockers.append(f"duplicate_look_id:{look_id}")
        seen_ids.add(look_id)
        if look_index != offset:
            blockers.append("non_sequential_look_index")
        if alpha_spent <= 0:
            blockers.append(f"non_positive_alpha_spent:{look_id}")
        if p_value < 0 or p_value > 1:
            blockers.append(f"p_value_out_of_range:{look_id}")
        if decision == "stop_for_success" and p_value > alpha_spent:
            blockers.append(f"success_stop_misses_boundary:{look_id}")
        if require_confirm_final_only and split == "confirm" and not final:
            blockers.append(f"confirm_non_final_peek:{look_id}")
        if split == "confirm" and bool(row.get("adaptive_replanned")):
            blockers.append(f"confirm_adaptive_replanned:{look_id}")

        normalized.append(
            {
                "look_index": look_index,
                "look_id": look_id,
                "split": split,
                "alpha_spent": alpha_spent,
                "cumulative_alpha_spent": cumulative,
                "p_value": p_value,
                "decision": decision,
                "final": final,
            }
        )

    if cumulative - alpha_total > 1e-12:
        blockers.append("alpha_budget_exceeded")

    payload = {
        "alpha_total": alpha_total,
        "cumulative_alpha_spent": cumulative,
        "looks": normalized,
        "require_confirm_final_only": require_confirm_final_only,
    }
    receipt = {
        "schema": SCHEMA_VERSION,
        "name": RECEIPT_NAME,
        "decision": "pass" if not blockers else "refused",
        "promotion_gate_satisfied": not blockers,
        "payload": payload,
        "blockers": sorted(set(blockers)),
    }
    receipt["payload_sha256"] = canonical_sha256(receipt)
    return receipt


__all__ = [
    "DEFAULT_ALPHA_TOTAL",
    "RECEIPT_NAME",
    "SCHEMA_VERSION",
    "evaluate_alpha_spending",
]
