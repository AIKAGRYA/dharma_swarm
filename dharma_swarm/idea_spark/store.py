"""Receipt construction + append-only persistence for the ingest lifecycle.

No network. All writes are atomic (tmp + ``os.replace``) and immutable by id:
re-writing an ``OperatorInputReceipt`` with the same id but different content
raises, mirroring the MemoryKernel append-only contract. Source receipts never
mutate trusted memory (spec section 4).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import (
    candidates_path,
    input_receipt_path,
    input_receipts_dir,
    lifecycle_receipt_path,
)
from .schemas import (
    RAW_CONTENT_RIGHTS,
    IdeaSparkCandidate,
    OperatorInputLifecycleReceipt,
    OperatorInputReceipt,
    RedactionPolicy,
    SourceKind,
    SourceRights,
    content_hash,
    derive_correlation_id,
    derive_input_id,
    utc_now_iso,
)

# Source kinds that are public web surfaces: default to a non-raw redaction
# policy unless the operator explicitly supplies an owned artifact.
_PUBLIC_WEB_KINDS = frozenset({"youtube_transcript", "url"})


def default_redaction_for(
    source_kind: str,
    source_rights: str,
) -> RedactionPolicy:
    """Pick a privacy-safe default redaction policy for the input."""
    if source_rights in RAW_CONTENT_RIGHTS:
        return "none"
    if source_rights == "link_only":
        return "link_only"
    if source_kind in _PUBLIC_WEB_KINDS:
        return "summary_only"
    if source_rights == "public_excerpt":
        return "summary_only"
    return "link_only"


def build_operator_input_receipt(
    *,
    source_kind: SourceKind,
    source_ref: str,
    content: str,
    source_rights: SourceRights,
    captured_by: str,
    captured_at: str | None = None,
    correlation_id: str | None = None,
    raw_storage_ref: str = "",
    redaction_policy: RedactionPolicy | None = None,
) -> OperatorInputReceipt:
    """Build an immutable source receipt with source-rights enforcement.

    ``content`` is the supplied content or allowed extract; only its hash is
    embedded. Raw content is retained (via ``raw_storage_ref``) only when
    ``source_rights`` permits it; otherwise ``raw_storage_ref`` is cleared.
    """
    digest = content_hash(content)
    input_id = derive_input_id(source_kind, source_ref, digest)
    corr = correlation_id or derive_correlation_id(source_ref, digest)
    policy = redaction_policy or default_redaction_for(source_kind, source_rights)

    # Enforce: do not retain raw content references for non-ownable rights.
    if source_rights not in RAW_CONTENT_RIGHTS:
        raw_storage_ref = ""

    return OperatorInputReceipt(
        input_id=input_id,
        correlation_id=corr,
        source_kind=source_kind,
        source_ref=source_ref,
        source_rights=source_rights,
        content_hash=digest,
        captured_at=captured_at or utc_now_iso(),
        captured_by=captured_by,
        raw_storage_ref=raw_storage_ref,
        redaction_policy=policy,
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_input_receipt(
    receipt: OperatorInputReceipt,
    state_root: Path | None = None,
) -> Path:
    """Persist a source receipt immutably; conflicting re-writes raise."""
    path = input_receipt_path(receipt.input_id, state_root)
    payload = receipt.to_json_dict()
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            # captured_at is a volatile wall-clock field; re-ingesting identical
            # content at a later time is an idempotent no-op (keep the original
            # receipt), not a content conflict. Compare the content-bearing subset.
            existing_cmp = {k: v for k, v in existing.items() if k != "captured_at"}
            payload_cmp = {k: v for k, v in payload.items() if k != "captured_at"}
            if existing_cmp != payload_cmp:
                raise ValueError(
                    f"conflicting immutable operator input receipt: {receipt.input_id}"
                )
        return path
    _write_json_atomic(path, payload)
    return path


def read_input_receipt(
    input_id: str,
    state_root: Path | None = None,
) -> OperatorInputReceipt | None:
    path = input_receipt_path(input_id, state_root)
    if not path.exists():
        return None
    return OperatorInputReceipt.model_validate_json(path.read_text(encoding="utf-8"))


def load_input_receipts(state_root: Path | None = None) -> list[OperatorInputReceipt]:
    directory = input_receipts_dir(state_root)
    if not directory.exists():
        return []
    receipts: list[OperatorInputReceipt] = []
    for path in sorted(directory.glob("*.json")):
        try:
            receipts.append(
                OperatorInputReceipt.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            )
        except (OSError, ValueError):
            continue
    return receipts


def append_candidate(
    candidate: IdeaSparkCandidate,
    state_root: Path | None = None,
) -> Path:
    """Append a candidate to the append-only, latest-wins candidates log."""
    path = candidates_path(state_root, ensure=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(candidate.to_json_dict(), sort_keys=True) + "\n")
    return path


def load_candidates(state_root: Path | None = None) -> list[IdeaSparkCandidate]:
    """Load candidates deduped by ``candidate_id`` (latest occurrence wins)."""
    path = candidates_path(state_root)
    if not path.exists():
        return []
    latest: dict[str, IdeaSparkCandidate] = {}
    order: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            candidate = IdeaSparkCandidate.model_validate_json(line)
        except ValueError:
            continue
        if candidate.candidate_id not in latest:
            order.append(candidate.candidate_id)
        latest[candidate.candidate_id] = candidate
    return [latest[cid] for cid in order]


def load_candidate(
    candidate_id: str,
    state_root: Path | None = None,
) -> IdeaSparkCandidate | None:
    for candidate in load_candidates(state_root):
        if candidate.candidate_id == candidate_id:
            return candidate
    return None


def load_lifecycle_receipt(
    correlation_id: str,
    state_root: Path | None = None,
) -> OperatorInputLifecycleReceipt | None:
    path = lifecycle_receipt_path(correlation_id, state_root)
    if not path.exists():
        return None
    return OperatorInputLifecycleReceipt.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def write_lifecycle_receipt(
    receipt: OperatorInputLifecycleReceipt,
    state_root: Path | None = None,
) -> Path:
    path = lifecycle_receipt_path(receipt.correlation_id, state_root)
    _write_json_atomic(path, receipt.to_json_dict())
    return path


_LIFECYCLE_MERGE_LIST_FIELDS = frozenset({"blockers", "evidence_paths"})


def update_lifecycle_receipt(
    correlation_id: str,
    state_root: Path | None = None,
    *,
    status: str | None = None,
    created_at: str | None = None,
    **fields: Any,
) -> OperatorInputLifecycleReceipt:
    """Load-or-create the lifecycle receipt, apply non-empty fields, persist.

    String fields are overwritten only when a non-empty value is supplied; list
    fields (``blockers``, ``evidence_paths``) are unioned to stay append-only.
    Pass ``created_at`` to make the receipt timestamps deterministic.
    """
    stamp = created_at or utc_now_iso()
    existing = load_lifecycle_receipt(correlation_id, state_root)
    base = (
        existing.model_dump()
        if existing is not None
        else {"correlation_id": correlation_id, "created_at": stamp}
    )
    for key, value in fields.items():
        if key in _LIFECYCLE_MERGE_LIST_FIELDS and value:
            merged = list(base.get(key) or [])
            for item in value:
                if item not in merged:
                    merged.append(item)
            base[key] = merged
        elif value not in (None, "", [], {}):
            base[key] = value
    if status:
        base["status"] = status
    base["updated_at"] = stamp
    receipt = OperatorInputLifecycleReceipt.model_validate(base)
    write_lifecycle_receipt(receipt, state_root)
    return receipt
