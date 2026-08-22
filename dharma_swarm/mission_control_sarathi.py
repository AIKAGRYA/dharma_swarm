"""Typed, fail-closed Sarathi proposal adapter for Mission Control.
Proposals and admissions are evidence, not dispatch authority.  This adapter
does not use legacy mailbox/wake paths or Mission Control execution lifecycle.
"""
from __future__ import annotations
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any
from dharma_swarm.holon_system.sarathi.plan import (
    VALID_CHANNELS,
    PlannedDelegation,
    plan_dedup_key,
)
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    clean_identifier,
    stable_id,
)
from dharma_swarm.mission_control_dispatch import GovernanceAdmission
from dharma_swarm.models import TaskStatus
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)
from dharma_swarm.operator_core.reversibility_gate import (
    ActionClass,
    GateDecision,
    classify_action,
)
SARATHI_SCHEMA_VERSION = "dharma.mission_control.sarathi.v1"
SARATHI_METADATA_KEY = "mission_control_sarathi"
MAX_DEPENDENCIES = 128
MAX_METADATA_BYTES = 65_536
MAX_PROVENANCE_BYTES = 32_768
_VALID_CHANNELS = frozenset(VALID_CHANNELS)
_RISK_TIERS = {"safe": "Q1", "low": "Q1", "medium": "Q2", "high": "Q3", "critical": "Q4"}
_KIND_TO_WORK_KIND = {"build": WorkKind.CODE_WRITE, "experiment": WorkKind.LONG_RUNNING,
                      "publication": WorkKind.CODE_WRITE, "merge": WorkKind.PROMOTION}
_KIND_RANK = {kind: rank for rank, kind in enumerate((WorkKind.READ_ONLY, WorkKind.A2A_CLAIM, WorkKind.LONG_RUNNING, WorkKind.CODE_WRITE, WorkKind.SELF_EVOLUTION, WorkKind.PROMOTION))}
_HARD_DENY_CLASSES = frozenset({ActionClass.IRREVERSIBLE, ActionClass.OPERATOR_ONLY})
AdmissionEvaluator = Callable[[GovernedWorkRequest], GovernedWorkAdmission]
class SarathiMissionError(MissionControlError):
    """Raised when proposal identity or governance binding fails closed."""
@dataclass(frozen=True, slots=True)
class MissionProposal:
    """Proposal-only claim formed from one complete PlannedDelegation."""
    schema_version: str
    proposal_id: str
    proposal_digest: str
    admission_request_id: str
    mission_id: str
    plan_key: str
    action: str
    recipient: str
    channel: str
    summary: str
    body: str
    dependency_labels: tuple[str, ...]
    metadata: dict[str, Any]
    gate_input: str
    gate_risk: str
    gate_action_class: str
    work_kind: WorkKind
    risk_tier: str
    requires_execution_lease: bool
    proposal_only: bool = True
    confers_dispatch_authority: bool = False
    proves_executor_liveness: bool = False
@dataclass(frozen=True, slots=True)
class AcceptedMissionTask:
    """Canonical TaskBoard acceptance; still not a dispatch authorization."""
    schema_version: str
    proposal_id: str
    proposal_digest: str
    mission_id: str
    plan_key: str
    task_id: str
    status: TaskStatus
    assigned_to: str
    admission: GovernanceAdmission
    dependency_task_ids: tuple[str, ...]
    confers_dispatch_authority: bool = False
    proves_executor_liveness: bool = False
def _canonical_json(value: Any, label: str) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise SarathiMissionError(f"{label} must be JSON-serializable") from exc
def _digest(value: Any, label: str) -> str:
    return hashlib.sha256(_canonical_json(value, label).encode("utf-8")).hexdigest()
def _json_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        raise SarathiMissionError("metadata must be a mapping")
    def check_keys(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if not isinstance(key, str):
                    raise SarathiMissionError("metadata keys must be strings")
                check_keys(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                check_keys(nested)
    check_keys(metadata)
    encoded = _canonical_json(dict(metadata), "metadata")
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise SarathiMissionError("metadata exceeds the bounded proposal limit")
    return json.loads(encoded)
def _required_text(value: Any, label: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str):
        raise SarathiMissionError(f"{label} must be a string")
    if not value.strip():
        raise SarathiMissionError(f"{label} is required")
    if identifier:
        try:
            return clean_identifier(value, label)
        except MissionControlError as exc:
            raise SarathiMissionError(str(exc)) from exc
    return value
def _dependency_labels(values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise SarathiMissionError("depends_on must be a tuple of dependency labels")
    if len(values) > MAX_DEPENDENCIES:
        raise SarathiMissionError("too many proposal dependencies")
    labels: list[str] = []
    for value in values:
        label = _required_text(value, "dependency label")
        if label != label.strip():
            raise SarathiMissionError(
                "dependency labels must not contain surrounding whitespace"
            )
        labels.append(label)
    if len(set(labels)) != len(labels):
        raise SarathiMissionError("dependency labels must be unique")
    return tuple(labels)
def _validated_delegation(value: PlannedDelegation) -> PlannedDelegation:
    if type(value) is not PlannedDelegation:
        raise SarathiMissionError("delegation must be a PlannedDelegation")
    channel = _required_text(value.channel, "channel")
    if channel not in _VALID_CHANNELS:
        raise SarathiMissionError(f"invalid Sarathi channel: {channel!r}")
    return PlannedDelegation(
        action=_required_text(value.action, "action"),
        recipient=_required_text(value.recipient, "recipient", identifier=True),
        channel=channel,
        summary=_required_text(value.summary, "summary"),
        body=_required_text(value.body, "body"),
        depends_on=_dependency_labels(value.depends_on),
        metadata=_json_metadata(value.metadata),
    )
def _gate_payload(delegation: PlannedDelegation) -> dict[str, Any]:
    return {
        "action": delegation.action,
        "recipient": delegation.recipient,
        "channel": delegation.channel,
        "summary": delegation.summary,
        "body": delegation.body,
        "depends_on": list(delegation.depends_on),
        "metadata": dict(delegation.metadata),
    }
def _classify(payload: Mapping[str, Any]) -> tuple[str, GateDecision]:
    gate_input = _canonical_json(dict(payload), "proposal payload")
    return gate_input, classify_action(gate_input, operator_reachable=False)
def _work_kind(metadata: Mapping[str, Any], gate: GateDecision) -> WorkKind:
    kind = str(metadata.get("sarathi_kind") or "").strip().lower()
    declared = _KIND_TO_WORK_KIND.get(kind, WorkKind.LONG_RUNNING)
    if kind == "review" and gate.action_class is ActionClass.REVERSIBLE_SAFE:
        declared = WorkKind.READ_ONLY
    complete_text = gate.action.lower()
    if any(term in complete_text for term in ("self evolution", "self_evolution")):
        return max((declared, WorkKind.SELF_EVOLUTION), key=_KIND_RANK.__getitem__)
    if "promotion" in complete_text or "merge" in complete_text:
        return max((declared, WorkKind.PROMOTION), key=_KIND_RANK.__getitem__)
    return declared
def _proposal_payload(proposal: MissionProposal) -> dict[str, Any]:
    payload = asdict(proposal)
    payload.pop("proposal_digest")
    payload["work_kind"] = proposal.work_kind.value
    return payload
def _request_metadata(proposal: MissionProposal) -> dict[str, str]:
    return {
        "schema_version": SARATHI_SCHEMA_VERSION, "mission_id": proposal.mission_id,
        "proposal_id": proposal.proposal_id, "plan_key": proposal.plan_key,
        "proposal_digest": proposal.proposal_digest,
        "channel": proposal.channel, "recipient": proposal.recipient,
    }
def _request_digest(request: GovernedWorkRequest) -> str:
    return _digest(request.model_dump(mode="json"), "governed work request")
class SarathiMissionAdapter:
    """Translate proposals into pending canonical tasks after fresh admission."""

    def __init__(
        self,
        mission_control: MissionControl,
        *,
        admission_evaluator: AdmissionEvaluator = evaluate_governed_work_admission,
    ) -> None:
        if not callable(admission_evaluator):
            raise TypeError("admission_evaluator must be callable")
        self._mission_control = mission_control
        self._admission_evaluator = admission_evaluator

    def propose(
        self, mission_id: str, delegation: PlannedDelegation
    ) -> MissionProposal:
        """Form a deterministic proposal without writing owner state."""
        mission_id = _required_text(mission_id, "mission_id", identifier=True)
        delegation = _validated_delegation(delegation)
        plan_key = plan_dedup_key(delegation)
        proposal_id = stable_id("sarathi_proposal", mission_id, plan_key)
        gate_input, gate = _classify(_gate_payload(delegation))
        risk_tier = _RISK_TIERS[gate.risk.value]
        work_kind = _work_kind(delegation.metadata, gate)
        admission_request_id = stable_id(
            "sarathi_admission", proposal_id, plan_key
        )
        unsigned = MissionProposal(
            schema_version=SARATHI_SCHEMA_VERSION,
            proposal_id=proposal_id,
            proposal_digest="",
            admission_request_id=admission_request_id,
            mission_id=mission_id,
            plan_key=plan_key,
            action=delegation.action,
            recipient=delegation.recipient,
            channel=delegation.channel,
            summary=delegation.summary,
            body=delegation.body,
            dependency_labels=delegation.depends_on,
            metadata=dict(delegation.metadata),
            gate_input=gate_input,
            gate_risk=gate.risk.value,
            gate_action_class=gate.action_class.value,
            work_kind=work_kind,
            risk_tier=risk_tier,
            requires_execution_lease=gate.requires_execution_lease,
        )
        return replace(
            unsigned,
            proposal_digest=_digest(_proposal_payload(unsigned), "proposal"),
        )

    def admit(
        self,
        proposal: MissionProposal,
        governed_request: GovernedWorkRequest,
    ) -> GovernanceAdmission:
        """Evaluate a bound request; the returned value is not authorization."""
        gate = self._validate_proposal(proposal)
        self._require_not_hard_denied(gate)
        self._require_request_binding(proposal, governed_request)
        request_digest = _request_digest(governed_request)
        try:
            evaluated = self._admission_evaluator(governed_request)
        except MissionControlError:
            raise
        except Exception as exc:
            raise SarathiMissionError("governance admission evaluation failed") from exc
        if _request_digest(governed_request) != request_digest:
            raise SarathiMissionError("governed work request changed during evaluation")
        if type(evaluated) is not GovernedWorkAdmission:
            raise SarathiMissionError(
                "admission evaluator returned a foreign evidence type"
            )
        if evaluated.request_id != proposal.admission_request_id:
            raise SarathiMissionError("admission evaluator changed the request identity")
        if evaluated.decision != "allow":
            raise SarathiMissionError(
                f"governance admission did not allow acceptance: {evaluated.decision}"
            )
        return GovernanceAdmission(
            subject_id=proposal.proposal_id,
            subject_digest=proposal.proposal_digest,
            principal=proposal.recipient,
            request_digest=request_digest,
            reasons=tuple(evaluated.reasons),
            required_receipts=tuple(evaluated.required_receipts),
            reduced_authority=_json_metadata(evaluated.reduced_authority),
        )

    async def accept(
        self,
        proposal: MissionProposal,
        governed_request: GovernedWorkRequest,
        admission: GovernanceAdmission,
        dependency_task_ids: Mapping[str, str],
    ) -> AcceptedMissionTask:
        """Create one pending task after re-evaluating every admission binding."""
        if type(proposal) is not MissionProposal:
            raise SarathiMissionError("MissionProposal evidence is required")
        proposal = replace(proposal, metadata=_json_metadata(proposal.metadata))
        gate = self._validate_proposal(proposal)
        if proposal.channel == "merge_intent":
            raise SarathiMissionError(
                "merge_intent is proposal-only and requires a Merge Master adapter"
            )
        self._require_not_hard_denied(gate)
        if type(admission) is not GovernanceAdmission:
            raise SarathiMissionError("GovernanceAdmission evidence is required")
        fresh = self.admit(proposal, governed_request)
        fresh = replace(fresh, reduced_authority=_json_metadata(fresh.reduced_authority))
        if fresh != admission:
            raise SarathiMissionError("governance admission is stale or mismatched")
        if fresh.decision != "allow":
            raise SarathiMissionError(
                f"governance admission did not allow acceptance: {fresh.decision}"
            )

        dependency_ids, mapping = self._validate_dependency_mapping(proposal, dependency_task_ids)
        mission = await self._mission_control.get_mission(proposal.mission_id)
        if mission is None:
            raise SarathiMissionError(f"mission {proposal.mission_id!r} was not found")
        refreshed = self.admit(proposal, governed_request)
        refreshed = replace(refreshed, reduced_authority=_json_metadata(refreshed.reduced_authority))
        if refreshed != fresh:
            raise SarathiMissionError("governance admission changed before task creation")
        metadata = self._task_metadata(proposal, refreshed, mapping)
        task = await self._mission_control.create_task(
            proposal.mission_id,
            title=proposal.summary,
            description=proposal.body,
            created_by="sarathi",
            depends_on=list(dependency_ids),
            idempotency_key=f"sarathi:{proposal.plan_key}",
            metadata=metadata,
        )
        if (
            task.mission_id != proposal.mission_id
            or task.status is not TaskStatus.PENDING
            or task.assigned_to
        ):
            raise SarathiMissionError(
                "Mission Control returned a foreign or already-executing task"
            )
        return AcceptedMissionTask(
            schema_version=SARATHI_SCHEMA_VERSION,
            proposal_id=proposal.proposal_id,
            proposal_digest=proposal.proposal_digest,
            mission_id=proposal.mission_id,
            plan_key=proposal.plan_key,
            task_id=task.task_id,
            status=task.status,
            assigned_to=task.assigned_to,
            admission=fresh,
            dependency_task_ids=dependency_ids,
        )

    def _validate_proposal(self, proposal: MissionProposal) -> GateDecision:
        if type(proposal) is not MissionProposal:
            raise SarathiMissionError("MissionProposal evidence is required")
        if proposal.schema_version != SARATHI_SCHEMA_VERSION:
            raise SarathiMissionError("proposal has a foreign schema")
        mission_id = _required_text(proposal.mission_id, "mission_id", identifier=True)
        delegation = _validated_delegation(
            PlannedDelegation(
                action=proposal.action,
                recipient=proposal.recipient,
                channel=proposal.channel,
                summary=proposal.summary,
                body=proposal.body,
                depends_on=proposal.dependency_labels,
                metadata=proposal.metadata,
            )
        )
        expected_plan_key = plan_dedup_key(delegation)
        if proposal.plan_key != expected_plan_key:
            raise SarathiMissionError("proposal plan identity does not match its content")
        expected_id = stable_id("sarathi_proposal", mission_id, expected_plan_key)
        expected_request_id = stable_id(
            "sarathi_admission", expected_id, expected_plan_key
        )
        if proposal.proposal_id != expected_id:
            raise SarathiMissionError("proposal identity does not match its mission")
        if proposal.admission_request_id != expected_request_id:
            raise SarathiMissionError("proposal admission request identity is invalid")
        gate_input, gate = _classify(_gate_payload(delegation))
        expected_kind = _work_kind(delegation.metadata, gate)
        expected_risk_tier = _RISK_TIERS[gate.risk.value]
        if (
            proposal.gate_input != gate_input
            or proposal.gate_risk != gate.risk.value
            or proposal.gate_action_class != gate.action_class.value
            or proposal.work_kind is not expected_kind
            or proposal.risk_tier != expected_risk_tier
            or proposal.requires_execution_lease != gate.requires_execution_lease
            or not proposal.proposal_only
            or proposal.confers_dispatch_authority
            or proposal.proves_executor_liveness
        ):
            raise SarathiMissionError("proposal gate or authority claims were altered")
        expected_digest = _digest(_proposal_payload(proposal), "proposal")
        if proposal.proposal_digest != expected_digest:
            raise SarathiMissionError("proposal digest does not match its content")
        return gate

    @staticmethod
    def _require_not_hard_denied(gate: GateDecision) -> None:
        if gate.never_auto_hit or gate.action_class in _HARD_DENY_CLASSES:
            raise SarathiMissionError(
                "proposal is hard-denied by the deterministic reversibility gate"
            )

    @staticmethod
    def _require_request_binding(
        proposal: MissionProposal, request: GovernedWorkRequest
    ) -> None:
        if type(request) is not GovernedWorkRequest:
            raise SarathiMissionError("GovernedWorkRequest evidence is required")
        expected = GovernedWorkRequest(request_id=proposal.admission_request_id, agent_uid=proposal.recipient, work_kind=proposal.work_kind, intent=proposal.gate_input, risk_tier=proposal.risk_tier, context_quorum_ok=False, metadata=_request_metadata(proposal))
        if request != expected:
            raise SarathiMissionError(
                "governed work request is not canonically bound to the proposal"
            )

    @staticmethod
    def _validate_dependency_mapping(
        proposal: MissionProposal, dependency_task_ids: Mapping[str, str]
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        if not isinstance(dependency_task_ids, Mapping):
            raise SarathiMissionError("dependency mapping must be a mapping")
        mapping = dict(dependency_task_ids)
        if any(not isinstance(key, str) for key in mapping):
            raise SarathiMissionError("dependency mapping keys must be strings")
        expected = set(proposal.dependency_labels)
        actual = set(mapping)
        if actual != expected:
            raise SarathiMissionError(
                "dependency mapping must be exact and complete; "
                f"missing={sorted(expected - actual)!r}; "
                f"extra={sorted(actual - expected)!r}"
            )
        canonical: dict[str, str] = {}
        for label in proposal.dependency_labels:
            raw_task_id = mapping[label]
            if not isinstance(raw_task_id, str):
                raise SarathiMissionError("canonical dependency IDs must be strings")
            try:
                task_id = clean_identifier(raw_task_id, "canonical dependency task ID")
            except MissionControlError as exc:
                raise SarathiMissionError(str(exc)) from exc
            canonical[label] = task_id
        dependency_ids = tuple(canonical[label] for label in proposal.dependency_labels)
        if len(set(dependency_ids)) != len(dependency_ids):
            raise SarathiMissionError(
                "dependency labels must map to distinct canonical task IDs"
            )
        return dependency_ids, canonical

    @staticmethod
    def _task_metadata(
        proposal: MissionProposal,
        admission: GovernanceAdmission,
        dependency_mapping: Mapping[str, str],
    ) -> dict[str, Any]:
        provenance = {
            "schema_version": SARATHI_SCHEMA_VERSION, "claim": "AcceptedMissionTask",
            "claim_ceiling": "accepted_mission_task", "proposal_id": proposal.proposal_id,
            "proposal_digest": proposal.proposal_digest,
            "plan_key": proposal.plan_key,
            "proposal_metadata_digest": _digest(
                proposal.metadata, "proposal metadata"
            ),
            "recipient_attribution": proposal.recipient, "planned_channel": proposal.channel,
            "work_kind": proposal.work_kind.value, "risk_tier": proposal.risk_tier,
            "dependency_task_ids": dict(dependency_mapping),
            "governance": {
                "subject_id": admission.subject_id, "subject_digest": admission.subject_digest,
                "principal": admission.principal, "decision": admission.decision,
                "request_digest": admission.request_digest,
                "reasons": list(admission.reasons),
                "required_receipts": list(admission.required_receipts),
                "reduced_authority_digest": _digest(
                    admission.reduced_authority, "reduced authority"
                ),
            },
            "confers_dispatch_authority": False, "proves_executor_liveness": False,
        }
        encoded = _canonical_json(provenance, "Sarathi task provenance")
        if len(encoded.encode("utf-8")) > MAX_PROVENANCE_BYTES:
            raise SarathiMissionError("Sarathi task provenance exceeds its bound")
        return {SARATHI_METADATA_KEY: json.loads(encoded)}

__all__ = ["SARATHI_SCHEMA_VERSION", "SARATHI_METADATA_KEY", "AcceptedMissionTask",
           "MissionProposal", "SarathiMissionAdapter", "SarathiMissionError"]
