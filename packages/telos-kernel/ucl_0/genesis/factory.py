"""Genesis receipt construction.

P0 genesis is unsigned by default and mandatorily forkable. An optional
threshold signature body can be carried as ordinary evidence, but no special
root privilege is created.
"""

from __future__ import annotations

import logging

from ucl_0.receipt.types import EvidenceRecord, Receipt, ValidityRecord

LOGGER = logging.getLogger(__name__)
DEFAULT_ISSUED_AT = "2026-07-05T00:00:00Z"
DEFAULT_TTL_SECONDS = 31_536_000


def make_genesis(
    claim: bytes,
    threshold_signature: bytes | None = None,
    validity: ValidityRecord | None = None,
) -> Receipt:
    LOGGER.warning("genesis is mandatorily forkable per L7")
    evidence: list[EvidenceRecord] = []
    if threshold_signature is not None:
        evidence.append(
            EvidenceRecord(
                method=b"threshold_signature",
                trust_base=b"threshold_signature",
                independence_class=b"genesis_endorsement",
                body=threshold_signature,
            )
        )
    return Receipt(
        claim=claim,
        evidence=evidence,
        predecessors=[],
        validity=validity or ValidityRecord(
            issued_at=DEFAULT_ISSUED_AT,
            ttl_seconds=DEFAULT_TTL_SECONDS,
        ),
    )
