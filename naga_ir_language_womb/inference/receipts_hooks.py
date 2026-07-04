"""NAGA-IR-shaped receipt emission helpers for NAGA-IR Language Womb.

This module is intentionally stdlib-only. PR #3's shared
``scripts/governance/naga_receipt_emit.py`` is not present on this branch, so
the womb starts with a local predecessor that follows the wire shape and marks
receipts as unsigned bootstrap records. These records are not canonical for
cross-fragment transfer until a signer/verifier layer is wired.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

NAGA_RECEIPT_SCHEMA_VERSION = "dharma.naga_receipt.v1"
WOMB_TRUST_BASE_ID = "naga_ir_language_womb.trust_base.v1"
WOMB_FRAGMENT_ID = "naga_ir_language_womb.fragment.v1"
WOMB_RECEIPT_MESH_ID = "naga_ir_language_womb.receipt_mesh.v1"
DEFAULT_TTL_DAYS = 7

_RECEIPT_CLASS_RE = re.compile(r"^naga_ir_language_womb\.[a-z0-9_]+\.v[0-9]+$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReceiptWriteRecord:
    schema_version: str
    receipt_path: Path
    receipt_hash: str
    receipt_id: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_uri(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_json(value: Any) -> str:
    return sha256_uri(canonical_json_bytes(value))


def validate_modality(modality: str, *, proof_checked: bool = False, ensemble_agreement: bool = False) -> str:
    if modality == "Proven_by" and not proof_checked:
        raise ValueError("Proven_by requires proof_checked=True")
    if modality == "Tested_by" and not ensemble_agreement and not proof_checked:
        raise ValueError("Tested_by requires ensemble_agreement=True or proof_checked=True")
    if modality not in {"Proven_by", "Tested_by", "Witnessed_by", "Attested_by", "Assumed"}:
        raise ValueError(f"unsupported modality: {modality}")
    return modality


def default_receipts_root(repo_root: Path) -> Path:
    return repo_root / "naga_ir_language_womb" / "receipts"


def dated_receipt_dir(receipts_root: Path, issued_at: str) -> Path:
    year, month, day = issued_at[:4], issued_at[5:7], issued_at[8:10]
    return receipts_root / year / month / day


def _receipt_file_stem(receipt_class: str, receipt_hash: str) -> str:
    compact_class = receipt_class.replace("naga_ir_language_womb.", "").replace(".", "_")
    return f"{compact_class}_{receipt_hash.removeprefix('sha256:')[:16]}"


def emit_womb_receipt(
    *,
    repo_root: Path,
    receipt_class: str,
    subject: dict[str, Any],
    claim: dict[str, Any],
    evidence: list[dict[str, Any]],
    causal_origin: dict[str, Any],
    prev_receipt_hash: str | None = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    receipts_root: Path | None = None,
) -> ReceiptWriteRecord:
    if not _RECEIPT_CLASS_RE.match(receipt_class):
        raise ValueError(f"invalid womb receipt class: {receipt_class}")
    if prev_receipt_hash is not None and not _HASH_RE.match(prev_receipt_hash):
        raise ValueError("prev_receipt_hash must be null or sha256:<64 hex>")
    if not evidence:
        raise ValueError("receipt evidence must not be empty")

    issued_at = utc_now()
    expires_at = (
        datetime.fromisoformat(issued_at.removesuffix("Z") + "+00:00") + timedelta(days=ttl_days)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    fragment_version = f"git:{_git_commit_hint(repo_root)}"
    subject_id = _subject_id(subject)
    claim_hash = hash_json(claim)
    authority_key = hash_json(
        {
            "subject_id": subject_id,
            "claim_hash": claim_hash,
            "trust_base_id": WOMB_TRUST_BASE_ID,
            "fragment_id": WOMB_FRAGMENT_ID,
            "fragment_version": fragment_version,
        }
    )
    receipt_id = f"{receipt_class}:{claim_hash.removeprefix('sha256:')[:16]}"

    normalized_evidence = []
    for item in evidence:
        modality = validate_modality(str(item.get("modality", "")))
        normalized_evidence.append(
            {
                "modality": modality,
                "method": item.get("method", "naga_ir_language_womb.bootstrap"),
                "result": item.get("result", "pass"),
                "trust_base_id": item.get("trust_base_id", WOMB_TRUST_BASE_ID),
                "fragment_id": item.get("fragment_id", WOMB_FRAGMENT_ID),
                "issued_at": item.get("issued_at", issued_at),
                "ttl_expires_at": item.get("ttl_expires_at", expires_at),
                "body": item.get("body", {}),
            }
        )

    receipt = {
        "schema_version": NAGA_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "receipt_class": receipt_class,
        "subject": subject,
        "claim": claim,
        "claim_hash": claim_hash,
        "evidence": normalized_evidence,
        "authority": {
            "trust_base_id": WOMB_TRUST_BASE_ID,
            "fragment_id": WOMB_FRAGMENT_ID,
            "fragment_version": fragment_version,
            "authority_scope": "canonical_within_womb_fragment",
            "transfer_rule": "recheck_or_coercion_receipt_required",
        },
        "causal_origin": causal_origin,
        "epistemic_origin": {
            "trust_base_id": WOMB_TRUST_BASE_ID,
            "checker": "naga_ir_language_womb.local_receipt_hook",
            "canonicality": "noncanonical_unsigned_bootstrap",
        },
        "ttl": {
            "issued_at": issued_at,
            "expires_at": expires_at,
        },
        "challenge_base": {
            "mesh_id": WOMB_RECEIPT_MESH_ID,
            "authority_key": authority_key,
            "evidence_horizon": f"P{ttl_days}D",
            "horizon_start": issued_at,
            "horizon_end": expires_at,
            "snapshot_observed_at": issued_at,
            "base_snapshot_hash": hash_json({"mesh_id": WOMB_RECEIPT_MESH_ID, "status": "seed_empty"}),
        },
        "challenge_state": {
            "authoritative": False,
            "observed_at": issued_at,
            "unresolved_count": 0,
            "challenge_receipt_ids": [],
        },
        "clock": {
            "observed_at": issued_at,
            "clock_uncertainty_ms": 1000,
            "max_clock_skew_ms": 5000,
        },
        "prev_receipt_hash": prev_receipt_hash,
        "signatures": [],
    }
    receipt_hash = hash_json(receipt)
    root = receipts_root or default_receipts_root(repo_root)
    out_dir = dated_receipt_dir(root, issued_at)
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = out_dir / f"{_receipt_file_stem(receipt_class, receipt_hash)}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return ReceiptWriteRecord(
        schema_version="naga_ir_language_womb.receipt_write_record.v1",
        receipt_path=receipt_path,
        receipt_hash=receipt_hash,
        receipt_id=receipt_id,
    )


def _subject_id(subject: dict[str, Any]) -> str:
    content_hash = subject.get("content_hash")
    if isinstance(content_hash, str) and _HASH_RE.match(content_hash):
        return content_hash
    return hash_json(subject)


def _git_commit_hint(repo_root: Path) -> str:
    head = repo_root / ".git"
    if head.is_file():
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            git_dir = (repo_root / text.split(":", 1)[1].strip()).resolve()
            return _read_git_head(git_dir)
    if head.is_dir():
        return _read_git_head(head)
    return "unknown"


def _read_git_head(git_dir: Path) -> str:
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        return "unknown"
    head_text = head_path.read_text(encoding="utf-8").strip()
    if head_text.startswith("ref:"):
        ref_path = git_dir / head_text.split(":", 1)[1].strip()
        if ref_path.is_file():
            return ref_path.read_text(encoding="utf-8").strip()[:12]
        return "unknown"
    return head_text[:12]
