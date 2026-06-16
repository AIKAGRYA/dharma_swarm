"""Read-only BoardStore projection for AgentOps work packets.

AgentOps JSON packets remain the domain truth. This adapter projects those
packets into BoardStore Card objects so operator surfaces can show delegated
work alongside ds-goal and other board-backed lanes without creating a second
kanban store.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

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

_CARD_STATUSES = set(get_args(CardStatus))


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


def _title(packet: dict[str, Any]) -> str:
    title = str(packet.get("title") or "").strip()
    if title:
        return title
    packet_id = str(packet.get("id") or "").strip()
    if packet_id:
        return packet_id.replace("-", " ")
    intent = str(packet.get("intent") or "").strip()
    return intent.split(".", 1)[0].strip() or "AgentOps work packet"


def _has_runtime_truth_refs(packet: dict[str, Any]) -> bool:
    for key in (
        "runtime_truth_ref",
        "runtime_truth_refs",
        "runtime_receipt_ref",
        "runtime_receipt_refs",
        "receipt_ref",
        "receipt_refs",
        "run_id",
        "trace_id",
        "correlation_id",
        "identity_invariant_digest",
    ):
        value = packet.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and any(item for item in value):
            return True
    return False


def _status(packet: dict[str, Any]) -> CardStatus:
    raw = str(packet.get("status") or "").strip().lower()
    has_runtime_refs = _has_runtime_truth_refs(packet)
    if raw == "done":
        return "done" if has_runtime_refs else "review"
    if raw in _CARD_STATUSES:
        return raw  # type: ignore[return-value]
    if packet.get("completed_at") or packet.get("closed_at"):
        return "done" if has_runtime_refs else "review"
    if packet.get("blocked_reason"):
        return "blocked"
    if packet.get("claimed_by") or packet.get("assignee"):
        return "claimed"
    return "planned"


def _agent_kind(packet: dict[str, Any]) -> str:
    haystack = " ".join(
        str(packet.get(key) or "")
        for key in ("id", "branch", "worktree", "intent", "claimed_by", "assignee")
    ).lower()
    if "codex" in haystack:
        return "codex"
    if "devin" in haystack:
        return "devin"
    if "cursor" in haystack:
        return "cursor"
    if "fable" in haystack or "claude" in haystack or "opus" in haystack:
        return "claude_code"
    if "hermes" in haystack or "daemon" in haystack:
        return "daemon"
    return "unknown"


def _criteria(packet: dict[str, Any]) -> list[AcceptanceCriterion]:
    criteria: list[AcceptanceCriterion] = []
    gates = packet.get("gates")
    if isinstance(gates, list):
        for idx, gate in enumerate(gates):
            if not isinstance(gate, dict):
                continue
            name = str(gate.get("name") or f"gate-{idx + 1}")
            command = str(gate.get("command") or "")
            criteria.append(
                AcceptanceCriterion(
                    id=f"gate_{_identifier(name)}",
                    text=f"Gate '{name}' exits 0",
                    kind="test",
                    verifier=command,
                )
            )

    approval = packet.get("approval") if isinstance(packet.get("approval"), dict) else {}
    for key, label in (
        ("before_commit", "Operator approval before commit"),
        ("before_merge", "Operator approval before merge"),
    ):
        if approval.get(key):
            criteria.append(
                AcceptanceCriterion(
                    id=f"approval_{key}",
                    text=label,
                    kind="manual",
                    verifier="operator approval",
                )
            )
    return criteria


def _resolve_artifact_path(uri: str, *, packet_path: Path) -> Path:
    raw = Path(uri).expanduser()
    if raw.is_absolute():
        return raw
    for base in (packet_path.parent, *packet_path.parents):
        candidate = base / raw
        if candidate.exists():
            return candidate
    return packet_path.parent / raw


def _artifact_receipt_refs(packet: dict[str, Any], *, packet_path: Path, created_at: str) -> list[ReceiptRef]:
    refs: list[ReceiptRef] = []
    artifacts = packet.get("output_artifacts")
    if not isinstance(artifacts, list):
        return refs
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            continue
        uri = str(artifact.get("uri") or artifact.get("path") or "").strip()
        if not uri:
            continue
        resolved = _resolve_artifact_path(uri, packet_path=packet_path)
        kind = str(artifact.get("kind") or "agentops_output_artifact")
        summary = str(artifact.get("summary") or kind)
        checksum = sha256_file(resolved) if resolved.is_file() else ""
        refs.append(
            ReceiptRef(
                receipt_id=f"{kind}:{stable_payload_hash({'uri': uri, 'index': index})[-16:]}",
                kind=kind,
                store="external",
                uri=uri,
                checksum=checksum,
                created_at=str(artifact.get("created_at") or created_at),
                summary=summary,
            )
        )
    return refs


def _receipt_refs(packet: dict[str, Any], *, packet_path: Path, created_at: str) -> list[ReceiptRef]:
    refs = [
        ReceiptRef(
            receipt_id=f"agentops_work_packet:{stable_payload_hash(str(packet_path))[-16:]}",
            kind="agentops_work_packet",
            store="external",
            uri=str(packet_path),
            checksum=sha256_file(packet_path),
            created_at=created_at,
            summary="AgentOps work packet JSON",
        )
    ]
    refs.extend(_artifact_receipt_refs(packet, packet_path=packet_path, created_at=created_at))
    return refs


def _body(packet: dict[str, Any]) -> str:
    lines = [
        f"id: {packet.get('id') or ''}",
        f"status: {packet.get('status') or ''}",
        f"claimed_by: {packet.get('claimed_by') or packet.get('assignee') or ''}",
        f"branch: {packet.get('branch') or ''}",
        f"worktree: {packet.get('worktree') or ''}",
        f"base_ref: {packet.get('base_ref') or ''}",
        f"intent: {packet.get('intent') or ''}",
    ]
    artifacts = packet.get("output_artifacts")
    if isinstance(artifacts, list) and artifacts:
        lines.append("output_artifacts:")
        for artifact in artifacts:
            if isinstance(artifact, dict):
                lines.append(f"- {artifact.get('kind') or 'artifact'}: {artifact.get('uri') or artifact.get('path') or ''}")
    return "\n".join(line for line in lines if not line.endswith(": "))


def _weight(status: CardStatus, packet: dict[str, Any]) -> float:
    if status in {"blocked", "failed"}:
        return 0.95
    if status in {"claimed", "running", "review"}:
        return 0.85
    if status == "done":
        return 0.25
    gates = packet.get("gates")
    return 0.8 if isinstance(gates, list) and gates else 0.7


def work_packet_to_card(packet: dict[str, Any], *, packet_path: Path) -> Card:
    """Project one AgentOps work packet into a BoardStore Card."""
    packet_root = packet_path.expanduser().resolve()
    packet_id = str(packet.get("id") or packet_root.stem)
    status = _status(packet)
    created_at = str(packet.get("created_at") or _mtime_iso(packet_root))
    updated_at = str(packet.get("updated_at") or created_at)
    branch = str(packet.get("branch") or "")
    worktree = str(packet.get("worktree") or "")

    return Card(
        id=CardId(f"agop_{_identifier(packet_id)}"),
        parent_objective=ObjectiveId("agentops_work_packets"),
        title=_title(packet),
        body=_body(packet),
        status=status,
        assignee_kind=_agent_kind(packet),  # type: ignore[arg-type]
        capability_required=["agentops", "work_packet"],
        acceptance_criteria=_criteria(packet),
        receipt_refs=_receipt_refs(packet, packet_path=packet_root, created_at=created_at),
        cost_ceiling_usd=Decimal("0.00"),
        version=Version(1),
        idempotency_key=f"agentops:{stable_payload_hash({'id': packet_id, 'path': str(packet_root)})}",
        arjuna_weight=_weight(status, packet),
        created_by=str(packet.get("created_by") or "agentops"),
        created_at=created_at,
        updated_at=updated_at,
        last_transitioned_at=updated_at,
        source_surface="operator_bridge",
        render_hints=RenderHints(
            column_hint=status,
            lane_hint="agentops",
            thread_hint=worktree or branch,
            map_node_kind="agentops_work_packet",
        ),
    )


class AgentOpsBoardAdapter:
    """Read-only adapter over AgentOps work-packet JSON files."""

    def __init__(self, work_packet_root: Path | str) -> None:
        self.work_packet_root = Path(work_packet_root).expanduser().resolve()

    def packet_paths(self) -> list[Path]:
        if not self.work_packet_root.exists():
            return []
        return sorted(path for path in self.work_packet_root.glob("*.json") if path.is_file())

    def list_cards(self, *, packet_id: str = "", limit: int = 0) -> list[Card]:
        cards: list[Card] = []
        paths = self.packet_paths()
        if packet_id:
            paths = [path for path in paths if path.stem == packet_id or _read_json(path).get("id") == packet_id]
        for path in paths:
            cards.append(work_packet_to_card(_read_json(path), packet_path=path))
            if limit > 0 and len(cards) >= limit:
                break
        return cards


def load_agentops_cards(
    work_packet_root: Path | str,
    *,
    packet_id: str = "",
    limit: int = 0,
) -> list[Card]:
    """Convenience projection for APIs and dashboards."""
    return AgentOpsBoardAdapter(work_packet_root).list_cards(packet_id=packet_id, limit=limit)
