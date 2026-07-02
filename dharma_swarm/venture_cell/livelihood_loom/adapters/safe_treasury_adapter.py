"""Safe treasury request builder.

This adapter only drafts requests. Execution belongs behind
ExternalActionQueue approval and a human multisig.
"""

from __future__ import annotations


def build_safe_treasury_request(
    *,
    cell_id: str,
    token: str,
    amount: str,
    recipient_label: str,
    purpose: str,
    external_action_request_id: str,
) -> dict[str, str]:
    if not external_action_request_id:
        raise ValueError("treasury request requires external_action_request_id")
    return {
        "schema": "livelihood_loom.safe_treasury_request.v1",
        "cell_id": cell_id,
        "token": token,
        "amount": amount,
        "recipient_label": recipient_label,
        "purpose": purpose,
        "external_action_request_id": external_action_request_id,
        "execution_mode": "draft_only_human_multisig_required",
    }
