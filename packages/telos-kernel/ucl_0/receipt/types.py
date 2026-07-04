"""Frozen UCL-0 P0 receipt records.

DERIVED_MODALITY:
    modality is derived from evidence records and is never serialized as a
    receipt seed field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_RFC3339Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


@dataclass(frozen=True)
class EvidenceRecord:
    method: bytes
    trust_base: bytes
    independence_class: bytes
    body: bytes


@dataclass(frozen=True)
class ValidityRecord:
    issued_at: str
    ttl_seconds: int


@dataclass(frozen=True)
class Receipt:
    claim: bytes
    evidence: list[EvidenceRecord]
    predecessors: list[bytes]
    validity: ValidityRecord


def validity_holds(validity: ValidityRecord) -> bool:
    return bool(_RFC3339Z.match(validity.issued_at)) and validity.ttl_seconds > 0


def is_well_formed(receipt: Receipt) -> bool:
    if not isinstance(receipt.claim, bytes):
        return False
    if not isinstance(receipt.evidence, list):
        return False
    if not isinstance(receipt.predecessors, list):
        return False
    if not isinstance(receipt.validity, ValidityRecord):
        return False
    if not validity_holds(receipt.validity):
        return False
    for predecessor in receipt.predecessors:
        if not isinstance(predecessor, bytes) or not len(predecessor) == 32:
            return False
    for evidence in receipt.evidence:
        if not isinstance(evidence, EvidenceRecord):
            return False
        if not isinstance(evidence.method, bytes):
            return False
        if not isinstance(evidence.trust_base, bytes):
            return False
        if not isinstance(evidence.independence_class, bytes):
            return False
        if not isinstance(evidence.body, bytes):
            return False
    return True


def parse_receipt(value: dict[str, Any]) -> Receipt:
    allowed = {"claim", "evidence", "predecessors", "validity"}
    if not set(value) == allowed:
        raise ValueError("UCL-0 receipts have exactly four seed fields")
    claim = _bytes_from_hex(value["claim"], "claim")
    evidence = [_parse_evidence(item) for item in _list(value["evidence"], "evidence")]
    predecessors = [
        _bytes_from_hex(item, "predecessor")
        for item in _list(value["predecessors"], "predecessors")
    ]
    validity_value = value["validity"]
    if not isinstance(validity_value, dict):
        raise ValueError("validity must be an object")
    validity = ValidityRecord(
        issued_at=_string(validity_value.get("issued_at"), "issued_at"),
        ttl_seconds=_int(validity_value.get("ttl_seconds"), "ttl_seconds"),
    )
    receipt = Receipt(claim, evidence, predecessors, validity)
    if not is_well_formed(receipt):
        raise ValueError("receipt is not well formed")
    return receipt


def _parse_evidence(value: Any) -> EvidenceRecord:
    if not isinstance(value, dict):
        raise ValueError("evidence item must be an object")
    allowed = {"method", "trust_base", "independence_class", "body"}
    if not set(value) == allowed:
        raise ValueError("evidence has exactly four fields")
    return EvidenceRecord(
        method=_bytes_from_hex(value["method"], "method"),
        trust_base=_bytes_from_hex(value["trust_base"], "trust_base"),
        independence_class=_bytes_from_hex(value["independence_class"], "independence_class"),
        body=_bytes_from_hex(value["body"], "body"),
    )


def _bytes_from_hex(value: Any, label: str) -> bytes:
    text = _string(value, label)
    try:
        return bytes.fromhex(text)
    except ValueError as error:
        raise ValueError(f"{label} must be hex bytes") from error


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    return value


def _int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value
