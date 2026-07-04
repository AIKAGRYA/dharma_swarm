"""Receipt identity for UCL-0 P0.

The identity rule is SHA-256 over RFC 8785 JCS bytes of the receipt projection
with transport identity and signature slots absent, as required by
[RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785).
"""

from __future__ import annotations

import hashlib
from typing import Any

from ucl_0.receipt.jcs import canonicalize
from ucl_0.receipt.types import EvidenceRecord, Receipt, ValidityRecord


def receipt_to_json(receipt: Receipt) -> dict[str, Any]:
    return {
        "claim": receipt.claim.hex(),
        "evidence": [_evidence_to_json(item) for item in receipt.evidence],
        "predecessors": [item.hex() for item in receipt.predecessors],
        "validity": _validity_to_json(receipt.validity),
    }


def canonical_receipt_bytes(receipt: Receipt) -> bytes:
    return canonicalize(receipt_to_json(receipt))


def receipt_id(receipt: Receipt) -> bytes:
    return hashlib.sha256(canonical_receipt_bytes(receipt)).digest()


def receipt_id_uri(receipt: Receipt) -> str:
    return "sha256:" + receipt_id(receipt).hex()


def _evidence_to_json(evidence: EvidenceRecord) -> dict[str, str]:
    return {
        "body": evidence.body.hex(),
        "independence_class": evidence.independence_class.hex(),
        "method": evidence.method.hex(),
        "trust_base": evidence.trust_base.hex(),
    }


def _validity_to_json(validity: ValidityRecord) -> dict[str, int | str]:
    return {
        "issued_at": validity.issued_at,
        "ttl_seconds": validity.ttl_seconds,
    }
