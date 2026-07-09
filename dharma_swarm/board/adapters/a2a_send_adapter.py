"""Read-only BoardStore projection for A2A contact receipts.

A2A send, inbox-bridge, domain-reply, and reply-capture receipts remain the
contact-evidence truth. This adapter projects receipt JSON into BoardStore Card
objects so operator surfaces can see peer contact attempts without upgrading
publish/fallback/delivery evidence into fake semantic collaboration.
"""

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

ACK_TIER_NO_CONTACT = "NO_CONTACT"
ACK_TIER_PUBLISH_ACCEPTED = "PUBLISH_ACCEPTED"
ACK_TIER_CORE_FLUSH_ONLY = "CORE_FLUSH_ONLY"
ACK_TIER_HANDLER_ACKED = "HANDLER_ACKED"
ACK_TIER_DOMAIN_RECEIPTED = "DOMAIN_RECEIPTED"


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


def _contact_tier(receipt: dict[str, Any]) -> str:
    tier = str(receipt.get("contact_evidence_tier") or receipt.get("ack_tier") or "").strip()
    if tier:
        return tier
    status = str(receipt.get("status") or "").strip()
    if status.endswith("_CONSUMED") or status.endswith("_REPLIED"):
        return ACK_TIER_HANDLER_ACKED
    if status == "PUBLISH_ACKED":
        return ACK_TIER_PUBLISH_ACCEPTED
    return ACK_TIER_NO_CONTACT


def _card_status(receipt: dict[str, Any]) -> CardStatus:
    tier = _contact_tier(receipt)
    status = str(receipt.get("status") or "").strip()
    if tier == ACK_TIER_HANDLER_ACKED:
        return "review"
    if tier in {ACK_TIER_PUBLISH_ACCEPTED, ACK_TIER_CORE_FLUSH_ONLY}:
        return "review"
    if status in {"NATS_SECRETS_MISSING", "NATS_CLIENT_MISSING", "PUBLISH_FAILED"}:
        return "blocked"
    return "blocked"


def _agent_kind(target: str) -> str:
    raw = target.lower()
    if "devin" in raw:
        return "devin"
    if "cursor" in raw:
        return "cursor"
    if "fable" in raw or "claude" in raw or "opus" in raw:
        return "claude_code"
    if "hermes" in raw or "daemon" in raw:
        return "daemon"
    if "codex" in raw:
        return "codex"
    return "unknown"


def _receipt_refs(path: Path, receipt: dict[str, Any], created_at: str) -> list[ReceiptRef]:
    packet_id = str(receipt.get("packet_id") or path.stem)
    return [
        ReceiptRef(
            receipt_id=f"a2a_send_receipt:{packet_id}",
            kind="a2a_send_receipt",
            store="external",
            uri=str(path),
            checksum=sha256_file(path),
            created_at=created_at,
            summary=str(receipt.get("operator_contact_note") or receipt.get("status") or ""),
        )
    ]


def _bridge_receipt_refs(path: Path, receipt: dict[str, Any], created_at: str) -> list[ReceiptRef]:
    packet_id = str(receipt.get("packet_id") or path.stem)
    return [
        ReceiptRef(
            receipt_id=f"a2a_inbox_bridge_receipt:{packet_id}",
            kind="a2a_inbox_bridge_receipt",
            store="external",
            uri=str(path),
            checksum=sha256_file(path),
            created_at=created_at,
            summary=str(receipt.get("operator_contact_note") or receipt.get("status") or ""),
        )
    ]


def _reply_receipt_refs(path: Path, receipt: dict[str, Any], created_at: str) -> list[ReceiptRef]:
    packet_id = str(receipt.get("packet_id") or path.stem)
    return [
        ReceiptRef(
            receipt_id=f"a2a_reply_capture_receipt:{packet_id}",
            kind="a2a_reply_capture_receipt",
            store="external",
            uri=str(path),
            checksum=sha256_file(path),
            created_at=created_at,
            summary=str(receipt.get("operator_contact_note") or receipt.get("status") or ""),
        )
    ]


def _domain_reply_receipt_refs(path: Path, receipt: dict[str, Any], created_at: str) -> list[ReceiptRef]:
    packet_id = str(receipt.get("packet_id") or path.stem)
    return [
        ReceiptRef(
            receipt_id=f"a2a_domain_reply_publish_receipt:{packet_id}",
            kind="a2a_domain_reply_publish_receipt",
            store="external",
            uri=str(path),
            checksum=sha256_file(path),
            created_at=created_at,
            summary=str(receipt.get("operator_contact_note") or receipt.get("status") or ""),
        )
    ]


def _criteria(receipt: dict[str, Any], receipt_path: Path) -> list[AcceptanceCriterion]:
    target = str(receipt.get("to") or "")
    file_path = str(receipt.get("file") or "")
    return [
        AcceptanceCriterion(
            id="contact_evidence_tier_recorded",
            text="A2A send receipt records an explicit contact evidence tier",
            kind="receipt",
            verifier="scripts/runtime/a2a_send.py",
            evidence_ref=str(receipt_path),
        ),
        AcceptanceCriterion(
            id="handler_or_domain_receipt_required",
            text="Live collaboration requires handler ack or domain receipt",
            kind="external",
            verifier=(
                f"python3 scripts/runtime/a2a_send.py --to {target} --file {file_path} --wait 10"
                if target and file_path
                else "scripts/runtime/a2a_send.py"
            ),
            evidence_ref=str(receipt.get("ack_subject") or ""),
        ),
    ]


def _bridge_criteria(receipt: dict[str, Any], receipt_path: Path) -> list[AcceptanceCriterion]:
    return [
        AcceptanceCriterion(
            id="delivery_handler_ack_recorded",
            text="A2A inbox bridge receipt records delivery-handler ack evidence",
            kind="receipt",
            verifier="scripts/runtime/a2a_inbox_bridge.py",
            evidence_ref=str(receipt_path),
        ),
        AcceptanceCriterion(
            id="semantic_reply_or_domain_receipt_required",
            text="Semantic collaboration still requires a reply_subject payload or domain receipt",
            kind="external",
            verifier="scripts/runtime/a2a_inbox_bridge.py plus target agent semantic handler",
            evidence_ref=str(receipt.get("ack_subject") or ""),
        ),
    ]


def _reply_criteria(receipt: dict[str, Any], receipt_path: Path) -> list[AcceptanceCriterion]:
    return [
        AcceptanceCriterion(
            id="reply_capture_receipt_recorded",
            text="A2A reply capture receipt records whether the reply subject produced a payload",
            kind="receipt",
            verifier="scripts/runtime/a2a_reply_capture.py",
            evidence_ref=str(receipt_path),
        ),
        AcceptanceCriterion(
            id="typed_domain_receipt_required",
            text="Semantic collaboration requires a typed domain receipt or agent-authored reply",
            kind="external",
            verifier="scripts/runtime/a2a_reply_capture.py",
            evidence_ref=str(receipt.get("reply_subject") or ""),
        ),
    ]


def _domain_reply_criteria(receipt: dict[str, Any], receipt_path: Path) -> list[AcceptanceCriterion]:
    return [
        AcceptanceCriterion(
            id="target_owned_reply_artifact_validated",
            text="Domain reply worker validates a target-owned reply artifact before publishing",
            kind="receipt",
            verifier="scripts/runtime/a2a_domain_reply_worker.py",
            evidence_ref=str(receipt_path),
        ),
        AcceptanceCriterion(
            id="reply_capture_must_record_domain_receipt",
            text="Semantic closure requires reply capture to read the typed domain receipt from the stream",
            kind="external",
            verifier="scripts/runtime/a2a_reply_capture.py",
            evidence_ref=str(receipt.get("reply_subject") or ""),
        ),
    ]


def _body(receipt: dict[str, Any]) -> str:
    lines = [
        f"to: {receipt.get('to') or ''}",
        f"subject: {receipt.get('subject') or ''}",
        f"packet_id: {receipt.get('packet_id') or ''}",
        f"status: {receipt.get('status') or ''}",
        f"contact_evidence_tier: {_contact_tier(receipt)}",
        f"collaboration_claim: {receipt.get('collaboration_claim') or 'none'}",
        f"live_contact_claim: {bool(receipt.get('live_contact_claim'))}",
        f"file: {receipt.get('file') or ''}",
        f"error: {receipt.get('error') or ''}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _bridge_body(receipt: dict[str, Any]) -> str:
    lines = [
        "kind: inbox_bridge",
        f"agent_uid: {receipt.get('agent_uid') or ''}",
        f"subject: {receipt.get('subject') or ''}",
        f"consumer: {receipt.get('consumer') or ''}",
        f"packet_id: {receipt.get('packet_id') or ''}",
        f"status: {receipt.get('status') or ''}",
        f"contact_evidence_tier: {_contact_tier(receipt)}",
        f"collaboration_claim: {receipt.get('collaboration_claim') or 'none'}",
        f"semantic_reply_claim: {bool(receipt.get('semantic_reply_claim'))}",
        f"peer_model_processed_claim: {bool(receipt.get('peer_model_processed_claim'))}",
        f"delivery_path: {receipt.get('delivery_path') or ''}",
        f"ack_subject: {receipt.get('ack_subject') or ''}",
        f"error: {receipt.get('error') or ''}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _reply_body(receipt: dict[str, Any]) -> str:
    lines = [
        "kind: reply_capture",
        f"to: {receipt.get('to') or ''}",
        f"target_uid: {receipt.get('target_uid') or ''}",
        f"packet_id: {receipt.get('packet_id') or ''}",
        f"status: {receipt.get('status') or ''}",
        f"contact_evidence_tier: {_contact_tier(receipt)}",
        f"reply_evidence_tier: {receipt.get('reply_evidence_tier') or ''}",
        f"semantic_reply_claim: {bool(receipt.get('semantic_reply_claim'))}",
        f"domain_receipt_claim: {bool(receipt.get('domain_receipt_claim'))}",
        f"reply_schema: {receipt.get('reply_schema') or ''}",
        f"reply_subject: {receipt.get('reply_subject') or ''}",
        f"send_receipt_path: {receipt.get('send_receipt_path') or ''}",
        f"error: {receipt.get('error') or ''}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _domain_reply_body(receipt: dict[str, Any]) -> str:
    lines = [
        "kind: domain_reply_publish",
        f"agent_uid: {receipt.get('agent_uid') or ''}",
        f"packet_id: {receipt.get('packet_id') or ''}",
        f"status: {receipt.get('status') or ''}",
        f"contact_evidence_tier: {_contact_tier(receipt)}",
        f"reply_evidence_tier: {receipt.get('reply_evidence_tier') or ''}",
        f"semantic_reply_claim: {bool(receipt.get('semantic_reply_claim'))}",
        f"domain_receipt_claim: {bool(receipt.get('domain_receipt_claim'))}",
        f"target_owned_artifact_claim: {bool(receipt.get('target_owned_artifact_claim'))}",
        f"reply_subject: {receipt.get('reply_subject') or ''}",
        f"send_receipt_path: {receipt.get('send_receipt_path') or ''}",
        f"reply_artifact_path: {receipt.get('reply_artifact_path') or ''}",
        f"error: {receipt.get('error') or ''}",
    ]
    return "\n".join(line for line in lines if not line.endswith(": "))


def _weight(status: CardStatus, receipt: dict[str, Any]) -> float:
    if status == "blocked":
        return 0.95
    if status == "review":
        return 0.85
    if bool(receipt.get("live_contact_claim")):
        return 0.25
    return 0.75


def a2a_send_receipt_to_card(receipt: dict[str, Any], *, receipt_path: Path) -> Card:
    """Project one A2A send receipt into a BoardStore Card."""
    path = receipt_path.expanduser().resolve()
    target = str(receipt.get("to") or path.stem)
    packet_id = str(receipt.get("packet_id") or path.stem)
    status = _card_status(receipt)
    created_at = str(receipt.get("timestamp") or _mtime_iso(path))
    tier = _contact_tier(receipt)

    return Card(
        id=CardId(f"a2a_{_identifier(target)}_{_identifier(packet_id)}"),
        parent_objective=ObjectiveId("a2a_peer_contact"),
        title=f"A2A {target}: {tier}",
        body=_body(receipt),
        status=status,
        assignee_kind=_agent_kind(target),  # type: ignore[arg-type]
        capability_required=["a2a", "nats", "peer_contact"],
        acceptance_criteria=_criteria(receipt, path),
        receipt_refs=_receipt_refs(path, receipt, created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"a2a_send:{stable_payload_hash({'to': target, 'packet_id': packet_id, 'path': str(path)})}",
        arjuna_weight=_weight(status, receipt),
        created_by=str(receipt.get("from") or "codex_composer"),
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="a2a",
            thread_hint=str(receipt.get("subject") or ""),
            map_node_kind="a2a_send_receipt",
        ),
    )


def a2a_inbox_bridge_receipt_to_card(receipt: dict[str, Any], *, receipt_path: Path) -> Card:
    """Project one A2A inbox bridge receipt into a BoardStore Card."""
    path = receipt_path.expanduser().resolve()
    target = str(receipt.get("agent_uid") or path.stem)
    packet_id = str(receipt.get("packet_id") or path.stem)
    status_value = str(receipt.get("status") or "")
    status: CardStatus = "review" if status_value == "DELIVERED_AND_ACKED" else "blocked"
    if status_value == "NO_MESSAGES":
        status = "review"
    created_at = str(receipt.get("timestamp") or _mtime_iso(path))
    tier = _contact_tier(receipt)

    return Card(
        id=CardId(f"a2a_bridge_{_identifier(target)}_{_identifier(packet_id)}"),
        parent_objective=ObjectiveId("a2a_peer_contact"),
        title=f"A2A bridge {target}: {tier}",
        body=_bridge_body(receipt),
        status=status,
        assignee_kind=_agent_kind(target),  # type: ignore[arg-type]
        capability_required=["a2a", "nats", "inbox_bridge"],
        acceptance_criteria=_bridge_criteria(receipt, path),
        receipt_refs=_bridge_receipt_refs(path, receipt, created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"a2a_bridge:{stable_payload_hash({'agent_uid': target, 'packet_id': packet_id, 'path': str(path)})}",
        arjuna_weight=_weight(status, receipt),
        created_by="codex_composer",
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="a2a",
            thread_hint=str(receipt.get("subject") or ""),
            map_node_kind="a2a_inbox_bridge_receipt",
        ),
    )


def a2a_domain_reply_receipt_to_card(receipt: dict[str, Any], *, receipt_path: Path) -> Card:
    """Project one A2A domain-reply publish receipt into a BoardStore Card."""
    path = receipt_path.expanduser().resolve()
    target = str(receipt.get("agent_uid") or receipt.get("to") or receipt.get("target_uid") or path.stem)
    packet_id = str(receipt.get("packet_id") or path.stem)
    status_value = str(receipt.get("status") or "")
    status: CardStatus = "review" if status_value == "DOMAIN_REPLY_PUBLISHED" else "blocked"
    created_at = str(receipt.get("timestamp") or _mtime_iso(path))
    reply_tier = str(receipt.get("reply_evidence_tier") or status_value or "unknown")

    return Card(
        id=CardId(f"a2a_domain_reply_{_identifier(target)}_{_identifier(packet_id)}"),
        parent_objective=ObjectiveId("a2a_peer_contact"),
        title=f"A2A domain reply {target}: {reply_tier}",
        body=_domain_reply_body(receipt),
        status=status,
        assignee_kind=_agent_kind(target),  # type: ignore[arg-type]
        capability_required=["a2a", "nats", "domain_reply"],
        acceptance_criteria=_domain_reply_criteria(receipt, path),
        receipt_refs=_domain_reply_receipt_refs(path, receipt, created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"a2a_domain_reply:{stable_payload_hash({'target': target, 'packet_id': packet_id, 'path': str(path)})}",
        arjuna_weight=_weight(status, receipt),
        created_by="codex_composer",
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="a2a",
            thread_hint=str(receipt.get("reply_subject") or ""),
            map_node_kind="a2a_domain_reply_publish_receipt",
        ),
    )


def a2a_reply_capture_receipt_to_card(receipt: dict[str, Any], *, receipt_path: Path) -> Card:
    """Project one A2A reply capture receipt into a BoardStore Card."""
    path = receipt_path.expanduser().resolve()
    target = str(receipt.get("to") or receipt.get("target_uid") or path.stem)
    packet_id = str(receipt.get("packet_id") or path.stem)
    status_value = str(receipt.get("status") or "")
    if status_value == "DOMAIN_RECEIPTED":
        status: CardStatus = "review"
    elif status_value in {"REPLY_CAPTURE_FAILED", "NATS_CLIENT_MISSING"}:
        status = "blocked"
    else:
        status = "review"
    created_at = str(receipt.get("timestamp") or _mtime_iso(path))
    reply_tier = str(receipt.get("reply_evidence_tier") or status_value or "unknown")

    return Card(
        id=CardId(f"a2a_reply_{_identifier(target)}_{_identifier(packet_id)}"),
        parent_objective=ObjectiveId("a2a_peer_contact"),
        title=f"A2A reply {target}: {reply_tier}",
        body=_reply_body(receipt),
        status=status,
        assignee_kind=_agent_kind(target),  # type: ignore[arg-type]
        capability_required=["a2a", "nats", "reply_capture"],
        acceptance_criteria=_reply_criteria(receipt, path),
        receipt_refs=_reply_receipt_refs(path, receipt, created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"a2a_reply:{stable_payload_hash({'target': target, 'packet_id': packet_id, 'path': str(path)})}",
        arjuna_weight=_weight(status, receipt),
        created_by="codex_composer",
        created_at=created_at,
        updated_at=created_at,
        last_transitioned_at=created_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="a2a",
            thread_hint=str(receipt.get("reply_subject") or ""),
            map_node_kind="a2a_reply_capture_receipt",
        ),
    )


class A2ASendBoardAdapter:
    """Read-only adapter over A2A send, bridge, domain-reply, and reply receipt JSON files."""

    def __init__(
        self,
        receipt_root: Path | str,
        *,
        bridge_receipt_root: Path | str | None = None,
        domain_reply_receipt_root: Path | str | None = None,
        reply_receipt_root: Path | str | None = None,
    ) -> None:
        self.receipt_root = Path(receipt_root).expanduser().resolve()
        self.bridge_receipt_root = (
            Path(bridge_receipt_root).expanduser().resolve()
            if bridge_receipt_root is not None
            else None
        )
        self.domain_reply_receipt_root = (
            Path(domain_reply_receipt_root).expanduser().resolve()
            if domain_reply_receipt_root is not None
            else None
        )
        self.reply_receipt_root = (
            Path(reply_receipt_root).expanduser().resolve()
            if reply_receipt_root is not None
            else None
        )

    def receipt_paths(self) -> list[Path]:
        if not self.receipt_root.exists():
            return []
        return sorted(path for path in self.receipt_root.glob("*.json") if path.is_file())

    def bridge_receipt_paths(self) -> list[Path]:
        if self.bridge_receipt_root is None or not self.bridge_receipt_root.exists():
            return []
        return sorted(path for path in self.bridge_receipt_root.glob("*.json") if path.is_file())

    def reply_receipt_paths(self) -> list[Path]:
        if self.reply_receipt_root is None or not self.reply_receipt_root.exists():
            return []
        return sorted(path for path in self.reply_receipt_root.glob("*.json") if path.is_file())

    def domain_reply_receipt_paths(self) -> list[Path]:
        if self.domain_reply_receipt_root is None or not self.domain_reply_receipt_root.exists():
            return []
        return sorted(path for path in self.domain_reply_receipt_root.glob("*.json") if path.is_file())

    def _matches_target(self, path: Path, receipt: dict[str, Any], target: str) -> bool:
        if not target:
            return True
        return (
            target in path.stem
            or receipt.get("to") == target
            or receipt.get("target_uid") == target
            or receipt.get("agent_uid") == target
        )

    def list_cards(self, *, target: str = "", limit: int = 0) -> list[Card]:
        items: list[tuple[Path, str]] = [
            *[(path, "send") for path in self.receipt_paths()],
            *[(path, "bridge") for path in self.bridge_receipt_paths()],
            *[(path, "domain_reply") for path in self.domain_reply_receipt_paths()],
            *[(path, "reply") for path in self.reply_receipt_paths()],
        ]
        # Newest first; on mtime ties, replies/domain replies/bridge receipts
        # precede send receipts (the send is the least informative card of a
        # tied pair) — mtime-only sorting made this ordering nondeterministic.
        kind_priority = {"reply": 0, "domain_reply": 1, "bridge": 2, "send": 3}
        items.sort(key=lambda item: (-item[0].stat().st_mtime, kind_priority[item[1]]))
        cards: list[Card] = []
        for path, kind in items:
            receipt = _read_json(path)
            if not self._matches_target(path, receipt, target):
                continue
            if kind == "bridge":
                cards.append(a2a_inbox_bridge_receipt_to_card(receipt, receipt_path=path))
            elif kind == "domain_reply":
                cards.append(a2a_domain_reply_receipt_to_card(receipt, receipt_path=path))
            elif kind == "reply":
                cards.append(a2a_reply_capture_receipt_to_card(receipt, receipt_path=path))
            else:
                cards.append(a2a_send_receipt_to_card(receipt, receipt_path=path))
            if limit > 0 and len(cards) >= limit:
                break
        return cards


def load_a2a_send_cards(
    receipt_root: Path | str,
    *,
    bridge_receipt_root: Path | str | None = None,
    domain_reply_receipt_root: Path | str | None = None,
    reply_receipt_root: Path | str | None = None,
    target: str = "",
    limit: int = 0,
) -> list[Card]:
    """Convenience projection for APIs and dashboards."""
    return A2ASendBoardAdapter(
        receipt_root,
        bridge_receipt_root=bridge_receipt_root,
        domain_reply_receipt_root=domain_reply_receipt_root,
        reply_receipt_root=reply_receipt_root,
    ).list_cards(target=target, limit=limit)
