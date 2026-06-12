"""Read-only BoardStore projection for SemanticReceipt artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dharma_swarm.board.models import (
    AcceptanceCriterion,
    Card,
    CardId,
    CardStatus,
    ObjectiveId,
    ReceiptRef,
    RenderHints,
    Version,
)
from dharma_swarm.operator_core.runtime_truth import sha256_file, stable_payload_hash
from dharma_swarm.operator_core.semantic_receipt import SemanticReceiptValidationError, validate_semantic_receipt


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _identifier(value: Any) -> str:
    chars: list[str] = []
    for char in str(value or ""):
        if char.isalnum() or char in {"-", "_"}:
            chars.append(char)
        else:
            chars.append("_")
    return "".join(chars).strip("_") or stable_payload_hash(value)[:18].replace(":", "_")


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def _model_identity(receipt: dict[str, Any]) -> dict[str, Any]:
    model_identity = receipt.get("model_identity")
    return model_identity if isinstance(model_identity, dict) else {}


def _card_status(receipt: dict[str, Any]) -> CardStatus:
    failure_type = str(receipt.get("failure_type") or "").strip()
    if failure_type:
        return "blocked"
    verdict = str(receipt.get("verdict") or "").strip()
    if verdict in {"failed", "blocked"}:
        return "blocked"
    if verdict in {"pass", "approve"}:
        return "review"
    return "review"


def _receipt_refs(path: Path, receipt: dict[str, Any], created_at: str) -> list[ReceiptRef]:
    receipt_id = str(receipt.get("receipt_id") or path.stem)
    return [
        ReceiptRef(
            receipt_id=f"semantic_receipt:{receipt_id}",
            kind="semantic_receipt",
            store="external",
            uri=str(path),
            checksum=sha256_file(path),
            created_at=created_at,
            summary=str(receipt.get("summary") or receipt.get("failure_reason") or ""),
        )
    ]


def _criteria(receipt: dict[str, Any], receipt_path: Path) -> list[AcceptanceCriterion]:
    criteria = [
        AcceptanceCriterion(
            id="semantic_receipt_validates",
            text="SemanticReceipt artifact passes executable v1 validation or records validation failure explicitly",
            kind="test",
            verifier="dharma_swarm.operator_core.semantic_receipt.validate_semantic_receipt",
            evidence_ref=str(receipt_path),
        ),
        AcceptanceCriterion(
            id="semantic_claim_model_authored",
            text="semantic_reply_claim is true only for model-authored validated artifacts",
            kind="receipt",
            verifier="scripts/runtime/model_critic_runner.py",
            evidence_ref=str(receipt_path),
        ),
    ]
    if receipt.get("failure_type"):
        criteria.append(
            AcceptanceCriterion(
                id="provider_failure_typed",
                text="Provider or validation failure is recorded with failure_type and failure_reason",
                kind="receipt",
                verifier=str(receipt.get("failure_type") or ""),
                evidence_ref=str(receipt_path),
            )
        )
    return criteria


def _body(receipt: dict[str, Any]) -> str:
    model_identity = _model_identity(receipt)
    lines = [
        f"receipt_id: {receipt.get('receipt_id') or ''}",
        f"verdict: {receipt.get('verdict') or ''}",
        f"provider: {model_identity.get('provider') or ''}",
        f"model: {model_identity.get('model') or ''}",
        f"confidence: {receipt.get('confidence')}",
        f"capability_match: {receipt.get('capability_match')}",
        f"authored_by_model: {bool(receipt.get('authored_by_model'))}",
        f"semantic_reply_claim: {bool(receipt.get('semantic_reply_claim'))}",
        f"peer_model_processed_claim: {bool(receipt.get('peer_model_processed_claim'))}",
        f"failure_type: {receipt.get('failure_type') or ''}",
        f"failure_reason: {receipt.get('failure_reason') or ''}",
        f"missing_context: {', '.join(receipt.get('missing_context') or [])}",
        f"explicit_disagreement: {receipt.get('explicit_disagreement') or ''}",
        f"review_target: {receipt.get('review_target') or ''}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _weight(status: CardStatus, receipt: dict[str, Any]) -> float:
    if status == "blocked":
        return 0.95
    confidence = receipt.get("confidence")
    if isinstance(confidence, int | float):
        return max(0.25, min(0.9, 1.0 - float(confidence) / 2.0))
    return 0.75


def semantic_receipt_to_card(receipt: dict[str, Any], *, receipt_path: Path) -> Card:
    """Project one SemanticReceipt artifact into a BoardStore Card."""
    path = receipt_path.expanduser().resolve()
    try:
        validated = validate_semantic_receipt(receipt)
        validation_error = ""
    except SemanticReceiptValidationError as exc:
        validated = dict(receipt)
        validation_error = "; ".join(exc.errors)
        validated.setdefault("failure_type", "schema_validation_failed")
        validated.setdefault("failure_reason", validation_error)
        validated.setdefault("verdict", "failed")
        validated.setdefault("semantic_reply_claim", False)
        validated.setdefault("peer_model_processed_claim", False)

    receipt_id = str(validated.get("receipt_id") or path.stem)
    created_at = str(validated.get("created_at") or _mtime_iso(path))
    model_identity = _model_identity(validated)
    provider = str(model_identity.get("provider") or "unknown")
    model = str(model_identity.get("model") or "unknown")
    status = _card_status(validated)
    title_verdict = str(validated.get("verdict") or "unknown")
    body = _body(validated)
    if validation_error:
        body = f"{body}\nvalidation_error: {validation_error}"

    return Card(
        id=CardId(f"semr_{_identifier(receipt_id)}"),
        parent_objective=ObjectiveId("semantic_receipts"),
        title=f"SemanticReceipt {provider}/{model}: {title_verdict}",
        body=body,
        status=status,
        assignee_kind="daemon",
        capability_required=["semantic_receipt", "model_critic", "agentops"],
        acceptance_criteria=_criteria(validated, path),
        receipt_refs=_receipt_refs(path, validated, created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"semantic_receipt:{stable_payload_hash({'receipt_id': receipt_id, 'path': str(path)})}",
        arjuna_weight=_weight(status, validated),
        created_by=str(validated.get("agent_uid") or "codex_composer"),
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="semantic_receipts",
            thread_hint=str(validated.get("review_target") or ""),
            map_node_kind="semantic_receipt",
        ),
    )


class SemanticReceiptBoardAdapter:
    """Read-only adapter over SemanticReceipt JSON artifacts."""

    def __init__(self, receipt_root: Path | str) -> None:
        self.receipt_root = Path(receipt_root).expanduser().resolve()

    def receipt_paths(self) -> list[Path]:
        if not self.receipt_root.exists():
            return []
        return sorted(self.receipt_root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)

    def list_cards(self, *, model: str = "", verdict: str = "", limit: int = 0) -> list[Card]:
        cards: list[Card] = []
        for path in self.receipt_paths():
            receipt = _read_json(path)
            model_identity = _model_identity(receipt)
            if model and model not in {str(model_identity.get("model") or ""), path.stem}:
                continue
            if verdict and str(receipt.get("verdict") or "") != verdict:
                continue
            cards.append(semantic_receipt_to_card(receipt, receipt_path=path))
            if limit > 0 and len(cards) >= limit:
                break
        return cards


def load_semantic_receipt_cards(
    receipt_root: Path | str,
    *,
    model: str = "",
    verdict: str = "",
    limit: int = 0,
) -> list[Card]:
    """Convenience projection for APIs and dashboards."""
    return SemanticReceiptBoardAdapter(receipt_root).list_cards(model=model, verdict=verdict, limit=limit)
