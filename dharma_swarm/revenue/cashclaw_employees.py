"""CashClaw employee-cell receipts.

The employee cell is audit instrumentation, not a new control plane. It lets
CashClaw Autopilot show which internal employee roles reviewed a packet before
the packet reaches human approval.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.revenue.action_gateway import CashClawActionGateway
from dharma_swarm.revenue.action_gateway_models import (
    ActionCategory,
    CashClawActionDecision,
    CashClawActionRequest,
    CashClawExecutionReceipt,
    canonical_hash,
    utc_now_iso,
)


CASHCLAW_EMPLOYEE_ROLES: tuple[dict[str, str], ...] = (
    {
        "role": "opportunity_scanner",
        "category": ActionCategory.OBSERVE.value,
        "intent": "Read the available opportunity signal and classify source quality.",
    },
    {
        "role": "buyer_scout",
        "category": ActionCategory.ANALYZE.value,
        "intent": "Estimate buyer pain, channel access, and demand proof.",
    },
    {
        "role": "budget_skeptic",
        "category": ActionCategory.ANALYZE.value,
        "intent": "Check budget clarity, pricing realism, and margin fit.",
    },
    {
        "role": "deliverable_builder",
        "category": ActionCategory.DRAFT_INTERNAL.value,
        "intent": "Draft the internal deliverable scope and acceptance criteria.",
    },
    {
        "role": "risk_welfare_gate",
        "category": ActionCategory.ANALYZE.value,
        "intent": "Inspect risk flags, welfare constraints, and prohibited action paths.",
    },
    {
        "role": "approval_clerk",
        "category": ActionCategory.REQUEST_HUMAN_APPROVAL.value,
        "intent": "Request human review only if the gauntlet passed.",
    },
)


class CashClawEmployeeReceipt(BaseModel):
    """One employee-role receipt for one CashClaw packet."""

    schema_version: str = "cashclaw_employee_receipt.v1"
    receipt_id: str
    cycle_id: str
    action_id: str
    opportunity_id: str = ""
    employee_uid: str
    employee_role: str
    intent: str
    category: ActionCategory
    verdict: str = ""
    gateway_decision: str = ""
    gateway_decision_id: str = ""
    gateway_reasons: list[str] = Field(default_factory=list)
    gateway_required_receipts: list[str] = Field(default_factory=list)
    execution_receipt_id: str = ""
    side_effects_performed: bool = False
    artifact_refs: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    next_human_decision: str = ""
    payload_hash: str = ""
    receipt_hash: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


class CashClawEmployeeReceiptBundle(BaseModel):
    """Receipt bundle for the six-role CashClaw employee cell."""

    schema_version: str = "cashclaw_employee_receipt_bundle.v1"
    bundle_id: str
    cycle_id: str
    action_id: str
    opportunity_id: str = ""
    agent_uid: str
    roles_completed: list[str] = Field(default_factory=list)
    employee_receipts: list[CashClawEmployeeReceipt] = Field(default_factory=list)
    gateway_decisions: list[CashClawActionDecision] = Field(default_factory=list)
    execution_receipts: list[CashClawExecutionReceipt] = Field(default_factory=list)
    decision_counts: dict[str, int] = Field(default_factory=dict)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    receipt_chain_hash: str = ""
    final_gateway_decision: str = ""
    final_gateway_decision_id: str = ""
    final_gateway_reasons: list[str] = Field(default_factory=list)
    final_gateway_required_receipts: list[str] = Field(default_factory=list)
    final_employee_receipt_id: str = ""
    final_execution_receipt_id: str = ""
    side_effects_performed: bool = False
    bundle_hash: str = ""
    created_at: str = Field(default_factory=utc_now_iso)


def build_employee_receipt_bundle(
    packet: Any,
    *,
    cycle_id: str,
    agent_uid: str = "cashclaw_autopilot",
    gateway: CashClawActionGateway | None = None,
) -> CashClawEmployeeReceiptBundle:
    """Build six employee receipts and gateway decisions for a packet."""

    gateway = gateway or CashClawActionGateway()
    payload = _packet_payload(packet)
    evidence_refs = _evidence_refs(packet)
    decisions: list[CashClawActionDecision] = []
    execution_receipts: list[CashClawExecutionReceipt] = []
    employee_receipts: list[CashClawEmployeeReceipt] = []

    for role_spec in CASHCLAW_EMPLOYEE_ROLES:
        role = role_spec["role"]
        category = ActionCategory(role_spec["category"])
        request = _role_request(
            packet,
            role=role,
            category=category,
            intent=role_spec["intent"],
            agent_uid=agent_uid,
            payload=payload,
            evidence_refs=evidence_refs,
        )
        decision = gateway.evaluate(request)
        execution_receipt = gateway.execution_receipt(
            request,
            decision,
            applied=False,
            external_side_effect=False,
            result_ref=str(_artifact_dir(packet)),
        )
        decisions.append(decision)
        execution_receipts.append(execution_receipt)
        receipt = CashClawEmployeeReceipt(
            receipt_id=f"caemp_{canonical_hash([request.action_id, role, decision.decision_id])[-24:]}",
            cycle_id=cycle_id,
            action_id=str(getattr(packet, "action_id", "")),
            opportunity_id=str(getattr(packet, "opportunity_id", "")),
            employee_uid=f"{agent_uid}:{role}",
            employee_role=role,
            intent=role_spec["intent"],
            category=category,
            verdict=str(getattr(packet, "verdict", "")),
            gateway_decision=decision.decision,
            gateway_decision_id=decision.decision_id,
            gateway_reasons=list(decision.reasons),
            gateway_required_receipts=list(decision.required_receipts),
            execution_receipt_id=execution_receipt.receipt_id,
            side_effects_performed=False,
            artifact_refs=evidence_refs,
            risk_flags=list(getattr(packet, "risk_flags", []) or []),
            next_human_decision=_next_human_decision(role, decision),
            payload_hash=request.payload_hash,
        )
        receipt.receipt_hash = _model_content_hash(receipt, exclude={"receipt_hash"})
        employee_receipts.append(receipt)

    final_index = _final_decision_index(decisions)
    final_decision = decisions[final_index]
    final_employee_receipt = employee_receipts[final_index]
    final_execution_receipt = execution_receipts[final_index]
    counts = {
        "allow": sum(1 for decision in decisions if decision.decision == "allow"),
        "review": sum(1 for decision in decisions if decision.decision == "review"),
        "block": sum(1 for decision in decisions if decision.decision == "block"),
    }
    artifact_hashes = _artifact_hashes(evidence_refs)
    receipt_chain_hash = canonical_hash(
        {
            "employee_receipt_hashes": [receipt.receipt_hash for receipt in employee_receipts],
            "gateway_decision_ids": [decision.decision_id for decision in decisions],
            "execution_receipt_ids": [receipt.receipt_id for receipt in execution_receipts],
            "artifact_hashes": artifact_hashes,
        }
    )
    bundle = CashClawEmployeeReceiptBundle(
        bundle_id=f"caempbundle_{canonical_hash([cycle_id, getattr(packet, 'action_id', ''), counts])[-24:]}",
        cycle_id=cycle_id,
        action_id=str(getattr(packet, "action_id", "")),
        opportunity_id=str(getattr(packet, "opportunity_id", "")),
        agent_uid=agent_uid,
        roles_completed=[role["role"] for role in CASHCLAW_EMPLOYEE_ROLES],
        employee_receipts=employee_receipts,
        gateway_decisions=decisions,
        execution_receipts=execution_receipts,
        decision_counts=counts,
        artifact_hashes=artifact_hashes,
        receipt_chain_hash=receipt_chain_hash,
        final_gateway_decision=final_decision.decision,
        final_gateway_decision_id=final_decision.decision_id,
        final_gateway_reasons=list(final_decision.reasons),
        final_gateway_required_receipts=list(final_decision.required_receipts),
        final_employee_receipt_id=final_employee_receipt.receipt_id,
        final_execution_receipt_id=final_execution_receipt.receipt_id,
        side_effects_performed=False,
    )
    bundle.bundle_hash = _model_content_hash(bundle, exclude={"bundle_hash"})
    return bundle


def write_employee_receipt_bundle(path: Path, bundle: CashClawEmployeeReceiptBundle) -> None:
    """Write a six-role employee receipt bundle as JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"employee receipt bundle already exists: {path}")
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_employee_receipt_bundle(path: Path, *, allowed_root: Path | None = None) -> list[str]:
    """Return integrity issues for a persisted employee receipt bundle."""

    issues: list[str] = []
    if allowed_root is not None and not _is_under(path, allowed_root):
        issues.append("bundle_path_outside_allowed_root")
    payload = json.loads(path.read_text(encoding="utf-8"))
    bundle = CashClawEmployeeReceiptBundle(**payload)
    for idx, receipt in enumerate(bundle.employee_receipts):
        expected = _model_content_hash(receipt, exclude={"receipt_hash"})
        if receipt.receipt_hash != expected:
            issues.append(f"employee_receipt_hash_mismatch:{idx}:{receipt.employee_role}")
    expected_artifacts: dict[str, str] = {}
    for artifact_ref in {ref for receipt in bundle.employee_receipts for ref in receipt.artifact_refs}:
        artifact_path = Path(artifact_ref)
        if allowed_root is not None and not _is_under(artifact_path, allowed_root):
            issues.append(f"artifact_outside_allowed_root:{artifact_ref}")
            continue
        if not artifact_path.exists():
            issues.append(f"artifact_missing:{artifact_ref}")
            continue
        expected_artifacts[artifact_ref] = _file_sha256(artifact_path)
    if bundle.artifact_hashes != expected_artifacts:
        issues.append("artifact_hashes_mismatch")
    expected_chain = canonical_hash(
        {
            "employee_receipt_hashes": [receipt.receipt_hash for receipt in bundle.employee_receipts],
            "gateway_decision_ids": [decision.decision_id for decision in bundle.gateway_decisions],
            "execution_receipt_ids": [receipt.receipt_id for receipt in bundle.execution_receipts],
            "artifact_hashes": bundle.artifact_hashes,
        }
    )
    if bundle.receipt_chain_hash != expected_chain:
        issues.append("receipt_chain_hash_mismatch")
    expected_bundle = _model_content_hash(bundle, exclude={"bundle_hash"})
    if bundle.bundle_hash != expected_bundle:
        issues.append("bundle_hash_mismatch")
    return issues


def _role_request(
    packet: Any,
    *,
    role: str,
    category: ActionCategory,
    intent: str,
    agent_uid: str,
    payload: dict[str, Any],
    evidence_refs: list[str],
) -> CashClawActionRequest:
    action_id = str(getattr(packet, "action_id", ""))
    request_action_id = action_id if role == "approval_clerk" else f"{action_id}:{role}"
    request_payload = {
        **payload,
        "employee_role": role,
        "intent": intent,
        "risk_flags_observed": list(getattr(packet, "risk_flags", []) or []),
    }
    return CashClawActionRequest(
        action_id=request_action_id,
        agent_uid=agent_uid,
        employee_role=role,
        category=category,
        intent=intent,
        payload=request_payload,
        evidence_refs=evidence_refs,
        risk_flags=list(getattr(packet, "risk_flags", []) or []) if role == "approval_clerk" else [],
        revenue_refs={
            "opportunity_id": str(getattr(packet, "opportunity_id", "")),
            "source": str(getattr(packet, "source", "")),
        },
        gauntlet_refs={
            "decision": str(getattr(packet, "gauntlet_decision", "")),
            "score": str(getattr(packet, "gauntlet_score", "")),
            "artifact_dir": str(getattr(packet, "artifact_dir", "")),
        },
        no_external_side_effects=True,
    )


def _packet_payload(packet: Any) -> dict[str, Any]:
    return {
        "action_id": getattr(packet, "action_id", ""),
        "opportunity_id": getattr(packet, "opportunity_id", ""),
        "rank": getattr(packet, "rank", 0),
        "score": getattr(packet, "score", 0),
        "verdict": getattr(packet, "verdict", ""),
        "gauntlet_decision": getattr(packet, "gauntlet_decision", ""),
        "gauntlet_score": getattr(packet, "gauntlet_score", 0),
        "approval_packet_ready": getattr(packet, "approval_packet_ready", False),
        "source": getattr(packet, "source", ""),
        "source_url": getattr(packet, "source_url", ""),
        "buyer_name": getattr(packet, "buyer_name", ""),
        "org": getattr(packet, "org", ""),
        "title": getattr(packet, "title", ""),
        "service_fit": getattr(packet, "service_fit", ""),
        "proposed_price_usd": getattr(packet, "proposed_price_usd", 0.0),
        "proposed_deliverable": getattr(packet, "proposed_deliverable", ""),
        "first_action": getattr(packet, "first_action", ""),
        "status": getattr(packet, "status", ""),
        "no_external_side_effects": getattr(packet, "no_external_side_effects", True),
    }


def _evidence_refs(packet: Any) -> list[str]:
    artifact_dir = _artifact_dir(packet)
    refs = [str(artifact_dir / name) for name in ("human_packet.md", "gate_evidence.json", "evaluation.json")]
    existing = [ref for ref in refs if Path(ref).exists()]
    return existing or [str(artifact_dir)]


def _artifact_dir(packet: Any) -> Path:
    return Path(str(getattr(packet, "artifact_dir", "") or "."))


def _next_human_decision(role: str, decision: CashClawActionDecision) -> str:
    if role != "approval_clerk":
        return ""
    if decision.decision == "review":
        return "operator_approves_or_rejects_external_action_packet"
    if decision.decision == "block":
        return "repair_hold_or_kill_packet_before_approval"
    return ""


def _final_decision_index(decisions: list[CashClawActionDecision]) -> int:
    for idx, decision in enumerate(decisions):
        if decision.decision == "block":
            return idx
    for idx, decision in enumerate(decisions):
        if decision.decision == "review":
            return idx
    return len(decisions) - 1


def _artifact_hashes(artifact_refs: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for artifact_ref in artifact_refs:
        path = Path(artifact_ref)
        if path.exists():
            hashes[artifact_ref] = _file_sha256(path)
    return hashes


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _model_content_hash(model: BaseModel, *, exclude: set[str]) -> str:
    return canonical_hash(model.model_dump(mode="json", exclude=exclude))


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
