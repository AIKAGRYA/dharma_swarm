"""Consent guards for Livelihood Loom."""

from __future__ import annotations

from dharma_swarm.venture_cell.livelihood_loom.ontology import ConsentLevel, ConsentReceipt


class ConsentViolation(PermissionError):
    """Raised when a Livelihood Loom action exceeds consent."""


def require_contact_consent(receipt: ConsentReceipt) -> None:
    if receipt.level != ConsentLevel.DIRECT_CONTACT_APPROVED:
        raise ConsentViolation("direct contact requires DIRECT_CONTACT_APPROVED consent")


def require_publish_consent(receipt: ConsentReceipt) -> None:
    if receipt.level != ConsentLevel.PUBLISH_APPROVED:
        raise ConsentViolation("publication requires PUBLISH_APPROVED consent")


def is_blocked(receipt: ConsentReceipt) -> bool:
    return receipt.level in {ConsentLevel.OPT_OUT, ConsentLevel.BLOCKED}
