"""Durable workflow plan contracts for VentureCell missions.

This module does not import Temporal directly. It gives Dharma Swarm a stable
contract that a Temporal worker can later consume, while tests can already
enforce side-effect/idempotency/approval rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class WorkflowActivitySpec:
    name: str
    activity_type: str
    requires_approval: bool = False
    requires_idempotency_key: bool = True
    side_effecting: bool = False

    def validate(self) -> None:
        if not self.name:
            raise ValueError("activity name is required")
        if self.side_effecting and not self.requires_approval:
            raise ValueError("side-effecting workflow activities require approval")
        if self.side_effecting and not self.requires_idempotency_key:
            raise ValueError("side-effecting workflow activities require idempotency")


@dataclass(frozen=True)
class DurableWorkflowSpec:
    workflow_name: str
    mission_id: str
    trace_id: str
    activities: tuple[WorkflowActivitySpec, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not self.workflow_name:
            raise ValueError("workflow_name is required")
        if not self.mission_id:
            raise ValueError("mission_id is required")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        for activity in self.activities:
            activity.validate()

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["activities"] = [asdict(activity) for activity in self.activities]
        return payload


def livelihood_pilot_workflow_spec(*, mission_id: str, trace_id: str) -> DurableWorkflowSpec:
    spec = DurableWorkflowSpec(
        workflow_name="LivelihoodPilotWorkflow",
        mission_id=mission_id,
        trace_id=trace_id,
        activities=(
            WorkflowActivitySpec("import_candidates", "ingestion", side_effecting=False),
            WorkflowActivitySpec("enrich_candidates", "analysis", side_effecting=False),
            WorkflowActivitySpec("risk_score_candidates", "analysis", side_effecting=False),
            WorkflowActivitySpec("draft_enablement_packets", "drafting", side_effecting=False),
            WorkflowActivitySpec(
                "queue_human_approved_actions",
                "external_action_queue",
                requires_approval=True,
                side_effecting=True,
            ),
            WorkflowActivitySpec("record_outcome_receipt", "receipt", side_effecting=False),
        ),
    )
    spec.validate()
    return spec
