"""Idempotent runtime receipts for standalone Holon."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA_VERSION = "holon.runtime_receipt.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_digest(data: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    kind: str
    subject: str
    status: str
    side_effect_key: str
    payload: dict[str, Any]
    created_at: str = field(default_factory=utc_now)
    schema_version: str = RECEIPT_SCHEMA_VERSION
    artifact_refs: list[str] = field(default_factory=list)
    verifier_refs: list[str] = field(default_factory=list)
    digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        digest = data.pop("digest", "")
        data["digest"] = digest or stable_digest(data)
        return data


def build_receipt(
    *,
    kind: str,
    subject: str,
    status: str,
    side_effect_key: str,
    payload: dict[str, Any],
    artifact_refs: list[str] | None = None,
    verifier_refs: list[str] | None = None,
) -> EvidenceReceipt:
    base = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": kind,
        "subject": subject,
        "status": status,
        "side_effect_key": side_effect_key,
        "payload": payload,
        "artifact_refs": artifact_refs or [],
        "verifier_refs": verifier_refs or [],
    }
    receipt_id = "hrcpt_" + hashlib.sha256(
        stable_json({"kind": kind, "subject": subject, "side_effect_key": side_effect_key}).encode("utf-8")
    ).hexdigest()[:24]
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        kind=kind,
        subject=subject,
        status=status,
        side_effect_key=side_effect_key,
        payload=payload,
        artifact_refs=list(artifact_refs or []),
        verifier_refs=list(verifier_refs or []),
        digest=stable_digest({**base, "receipt_id": receipt_id}),
    )
    return receipt


def receipt_dir(agents_root: Path, holon_name: str) -> Path:
    return agents_root / holon_name / "receipts"


def write_receipt(receipt: EvidenceReceipt, *, agents_root: Path, holon_name: str) -> dict[str, str]:
    directory = receipt_dir(agents_root, holon_name)
    directory.mkdir(parents=True, exist_ok=True)
    payload = receipt.to_dict()
    path = directory / f"{receipt.receipt_id}.json"
    if not path.exists():
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        index = directory / "receipts.jsonl"
        with index.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return {"receipt_id": receipt.receipt_id, "path": str(path), "digest": payload["digest"]}
