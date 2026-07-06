"""Hash-chain adapter for dispatch EvidenceReceipts.

Rung 0 of the DharmaGraph receipt-unification plan: every dispatch
EvidenceReceipt can be projected into the existing VerifiedMachineReceipt
chain, without adding a new truth store.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.spine.receipt import (
    EvidenceReceipt,
    VerifiedMachineReceipt,
    append_machine_receipt,
)

DISPATCH_CHAIN_SCHEMA_VERSION = "dispatch_evidence_machine_projection.v1"


def dispatch_machine_receipt(
    receipt: EvidenceReceipt,
    *,
    side_effect_key: str = "",
    operation_hash: str = "",
) -> VerifiedMachineReceipt:
    """Project a dispatch EvidenceReceipt into the machine receipt chain."""
    side_effect_key = side_effect_key or str(
        receipt.attributes.get("side_effect_key", "")
    )
    receipt_hash = _stable_hash_uri(receipt.to_dict())
    operation_hash = operation_hash or _operation_hash(receipt)
    return VerifiedMachineReceipt(
        claim_id=receipt.claim_id or receipt.task_id or str(receipt.receipt_id),
        command=receipt.operation or "invoke_agent",
        actor=receipt.agent_id,
        model=receipt.model,
        exit_code=0 if receipt.status == "ok" else 1,
        stdout_stderr_hash=receipt_hash,
        started_at=_timestamp(receipt.started_at),
        finished_at=_timestamp(receipt.finished_at)
        if receipt.finished_at is not None
        else "",
        generated_by="dharma_swarm.graph.durable_invoker",
        verified_by="dispatch_evidence_receipt_chain",
        artifact_hashes={
            "evidence_receipt": receipt_hash,
            "operation": _sha256_uri(operation_hash),
        },
        attributes={
            "schema_version": DISPATCH_CHAIN_SCHEMA_VERSION,
            "source_receipt_type": "EvidenceReceipt",
            "source_receipt_id": str(receipt.receipt_id),
            "trace_id": receipt.trace_id,
            "task_id": receipt.task_id,
            "agent_id": receipt.agent_id,
            "status": receipt.status,
            "error_source": receipt.error_source,
            "provider": receipt.provider,
            "model": receipt.model,
            "receipt_hash": receipt_hash,
            "side_effect_key_hash": (
                _stable_hash_uri(side_effect_key) if side_effect_key else ""
            ),
        },
    )


def append_dispatch_receipt_to_machine_chain(
    receipt: EvidenceReceipt,
    *,
    path: Path | None = None,
    side_effect_key: str = "",
    operation_hash: str = "",
) -> VerifiedMachineReceipt:
    """Append a dispatch receipt projection to the existing machine chain."""
    return append_machine_receipt(
        dispatch_machine_receipt(
            receipt,
            side_effect_key=side_effect_key,
            operation_hash=operation_hash,
        ),
        path=path,
    )


def _operation_hash(receipt: EvidenceReceipt) -> str:
    return hashlib.sha256(
        f"{receipt.operation}:{receipt.task_id}:{receipt.agent_id}".encode("utf-8")
    ).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _stable_hash_uri(payload: object) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _sha256_uri(value: str) -> str:
    clean = value.strip()
    if clean.startswith("sha256:"):
        return clean
    return f"sha256:{clean}"


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
