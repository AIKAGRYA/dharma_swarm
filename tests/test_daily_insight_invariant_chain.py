from __future__ import annotations

import re
from datetime import datetime

import pytest

from dharma_swarm.insight_brief import InsightBriefBuilder, WITA
from dharma_swarm.lineage import LineageGraph
from dharma_swarm.models import (
    GateCheckResult,
    GateDecision,
    GateResult,
    Task,
    TaskPriority,
)
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.ontology_action_gateway import OntologyActionGateway
from dharma_swarm.telic_seam import TelicSeam


class AllowGatekeeper:
    def check(self, **kwargs):
        return GateCheckResult(
            decision=GateDecision.ALLOW,
            reason="ok",
            gate_results={
                "BHED_GNAN": (GateResult.PASS, ""),
                "STEELMAN": (GateResult.PASS, ""),
                "DOGMA_DRIFT": (GateResult.PASS, ""),
                "CONSENT": (GateResult.PASS, ""),
            },
        )


@pytest.fixture()
def registry() -> OntologyRegistry:
    return OntologyRegistry.create_dharma_registry()


@pytest.fixture()
def lineage(tmp_path) -> LineageGraph:
    return LineageGraph(db_path=tmp_path / "lineage.db")


@pytest.fixture()
def gateway(registry: OntologyRegistry) -> OntologyActionGateway:
    return OntologyActionGateway(registry=registry, gatekeeper=AllowGatekeeper())


@pytest.fixture()
def sample_task() -> Task:
    return Task(
        title="Prove daily insight invariant",
        description="Runtime evidence should survive the telic seam into the daily brief.",
        priority=TaskPriority.HIGH,
        metadata={"task_type": "invariant_chain"},
    )


def _now() -> datetime:
    return datetime(2026, 5, 8, 4, 30, tzinfo=WITA)


def _gate_allow() -> GateCheckResult:
    return GateCheckResult(
        decision=GateDecision.ALLOW,
        reason="All gates passed",
        gate_results={
            "AHIMSA": (GateResult.PASS, ""),
            "SATYA": (GateResult.PASS, ""),
        },
    )


def _record_value_chain(
    seam: TelicSeam,
    task: Task,
    outcome_id: str,
) -> tuple[str, str]:
    value_event_id = seam.record_value_event(
        outcome_id,
        task,
        "agent_alpha",
        result_text="Verified daily insight invariant chain with ontology citations.",
        success=True,
        duration_ms=1000.0,
        cell_id="daily_insight_cell",
    )
    assert value_event_id is not None
    value_event = seam.registry.get_object(value_event_id)
    assert value_event is not None

    contribution_id = seam.record_contribution(
        value_event_id,
        "agent_alpha",
        composite_value=value_event.properties["composite_value"],
        cell_id="daily_insight_cell",
        task_type=value_event.properties["task_type"],
    )
    assert contribution_id is not None
    core_four_metric_ids = seam.record_core_four_metrics(
        value_event_id,
        evidence_summary="Core Four dimensions derived from invariant outcome telemetry.",
    )
    assert len(core_four_metric_ids) == 4
    return value_event_id, contribution_id


def test_telic_seam_recovers_proposal_for_outcome_across_instances(
    registry: OntologyRegistry,
    lineage: LineageGraph,
    sample_task: Task,
) -> None:
    orchestrator_seam = TelicSeam(registry=registry, lineage=lineage)
    proposal_id = orchestrator_seam.record_dispatch(sample_task, "agent_alpha")
    assert proposal_id is not None
    gate_id = orchestrator_seam.record_gate_decision(proposal_id, _gate_allow())
    assert gate_id is not None

    runner_seam = TelicSeam(registry=registry, lineage=lineage)
    outcome_id = runner_seam.record_outcome(
        sample_task,
        "agent_alpha",
        success=True,
        result_summary="Verified daily insight invariant chain.",
        duration_ms=1000.0,
        fitness_score=0.9,
    )
    assert outcome_id is not None

    outcome = registry.get_object(outcome_id)
    assert outcome is not None
    assert outcome.properties["proposal_id"] == proposal_id
    assert registry.get_links(
        source_id=proposal_id,
        target_id=outcome_id,
        link_name="has_outcome",
    )


def test_daily_insight_brief_uses_telic_outcome_and_cites_full_chain(
    registry: OntologyRegistry,
    lineage: LineageGraph,
    gateway: OntologyActionGateway,
    sample_task: Task,
    tmp_path,
) -> None:
    seam = TelicSeam(registry=registry, lineage=lineage)
    proposal_id = seam.record_dispatch(sample_task, "agent_alpha")
    assert proposal_id is not None
    gate_id = seam.record_gate_decision(proposal_id, _gate_allow())
    assert gate_id is not None
    outcome_id = seam.record_outcome(
        sample_task,
        "agent_alpha",
        success=True,
        result_summary="Verified daily insight invariant chain with ontology citations.",
        duration_ms=1000.0,
        fitness_score=0.9,
    )
    assert outcome_id is not None
    value_event_id, contribution_id = _record_value_chain(seam, sample_task, outcome_id)

    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    proposed = builder.propose()
    assert [obj.id for obj in proposed] == [outcome_id]

    brief = builder.compose(proposed)
    assert brief.type_name == "KnowledgeArtifact"
    witnesses = registry.get_objects_by_type("WitnessLog")
    assert len(witnesses) == 1

    assert registry.get_links(
        source_id=proposal_id,
        target_id=gate_id,
        link_name="has_gate_decision",
    )
    assert registry.get_links(
        source_id=proposal_id,
        target_id=outcome_id,
        link_name="has_outcome",
    )
    assert registry.get_links(
        source_id=outcome_id,
        target_id=value_event_id,
        link_name="has_value_event",
    )
    assert registry.get_links(
        source_id=value_event_id,
        target_id=contribution_id,
        link_name="has_contribution",
    )
    core_four_metrics = seam.query_core_four_metrics(value_event_id=value_event_id)
    assert [m.properties["dimension"] for m in core_four_metrics] == [
        "speed", "effectiveness", "quality", "impact",
    ]
    for metric in core_four_metrics:
        assert registry.get_links(
            source_id=value_event_id,
            target_id=metric.id,
            link_name="has_core_four_metric",
        )
        assert registry.get_links(
            source_id=metric.id,
            target_id=outcome_id,
            link_name="measures_outcome",
        )
    assert registry.get_links(
        source_id=brief.id,
        target_id=outcome_id,
        link_name="derived_from",
    )
    assert registry.get_links(
        source_id=brief.id,
        target_id=witnesses[0].id,
        link_name="cites_witness",
    )

    content = str(brief.properties["content"])
    citations = re.findall(
        r"ontology://KnowledgeArtifact/([0-9a-f]+)#cites/Outcome/([0-9a-f]+)",
        content,
    )
    assert citations == [(brief.id, outcome_id)]
    assert "Verified daily insight invariant chain" in content
    assert seam.lifecycle_integrity_report()["is_clean"] is True


def test_lifecycle_integrity_report_flags_outcome_without_proposal_id(
    registry: OntologyRegistry,
    lineage: LineageGraph,
    sample_task: Task,
) -> None:
    seam = TelicSeam(registry=registry, lineage=lineage)
    outcome_id = seam.record_outcome(
        sample_task,
        "agent_alpha",
        success=True,
        result_summary="Runtime outcome without dispatch linkage.",
    )
    assert outcome_id is not None

    report = seam.lifecycle_integrity_report()

    assert report["is_clean"] is False
    assert outcome_id in report["orphan_outcomes"]
