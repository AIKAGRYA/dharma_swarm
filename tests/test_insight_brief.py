from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from dharma_swarm.cron_job_runtime import CronJobRunStatus
from dharma_swarm.cron_runner import execute_cron_job
from dharma_swarm.insight_brief import InsightBriefBuilder, WITA
from dharma_swarm.models import GateCheckResult, GateDecision, GateResult
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.ontology_action_gateway import (
    OntologyActionGateway,
    OntologyGatewayError,
)
from dharma_swarm.ontology_runtime import (
    get_shared_registry,
    persist_shared_registry,
    reset_shared_registry,
)


class RecordingGatekeeper:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def check(self, **kwargs):
        self.calls.append(kwargs)
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
def gatekeeper() -> RecordingGatekeeper:
    return RecordingGatekeeper()


@pytest.fixture()
def gateway(registry: OntologyRegistry, gatekeeper: RecordingGatekeeper) -> OntologyActionGateway:
    return OntologyActionGateway(registry=registry, gatekeeper=gatekeeper)


def _now() -> datetime:
    return datetime(2026, 5, 8, 4, 30, tzinfo=WITA)


def _outcome(
    registry: OntologyRegistry,
    task_id: str = "task-1",
    *,
    success: bool = True,
    summary: str = "Verified substrate-backed result",
):
    obj, errors = registry.create_object(
        "Outcome",
        {
            "proposal_id": f"proposal-{task_id}",
            "task_id": task_id,
            "agent_id": "agent-alpha",
            "success": success,
            "result_summary": summary if success else "",
            "error": "" if success else summary,
            "duration_ms": 12.0,
            "fitness_score": 0.9,
        },
        created_by="test",
    )
    assert obj is not None, errors
    return obj


def test_brief_creates_typed_objects(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    _outcome(registry)
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    brief = builder.compose(builder.propose())

    assert brief.type_name == "KnowledgeArtifact"
    assert registry.get_objects_by_type("WitnessLog")
    assert registry.get_links(source_id=brief.id, link_name="derived_from")
    assert registry.get_links(source_id=brief.id, link_name="cites_witness")


def test_brief_fails_without_outcomes(
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    with pytest.raises(OntologyGatewayError, match="at least one Outcome"):
        builder.compose(builder.propose())


def test_propose_demotes_provider_plumbing_failures(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    noisy = _outcome(
        registry,
        "task-provider-error",
        success=False,
        summary="All providers failed in chain ['codex'] :: codex:provider_error",
    )
    signal = _outcome(
        registry,
        "task-real-signal",
        success=True,
        summary="## Synthesis of Disagreement\nVerified useful result with cited evidence.",
    )
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now, max_outcomes=1)

    assert builder.propose() == [signal]
    assert noisy not in builder.propose()


def test_failures_render_under_breakages(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    failure = _outcome(
        registry,
        "task-breakage",
        success=False,
        summary="Telos block: AHIMSA violation",
    )
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    brief = builder.compose([failure])
    content = str(brief.properties["content"])

    assert "## Breakages" in content
    assert "## Signals" not in content
    assert "Telos block" in content


def test_brief_citations_resolve(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    outcome = _outcome(registry)
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    brief = builder.compose([outcome])

    content = str(brief.properties["content"])
    citations = re.findall(
        r"ontology://KnowledgeArtifact/([0-9a-f]+)#cites/Outcome/([0-9a-f]+)",
        content,
    )
    assert citations == [(brief.id, outcome.id)]
    for artifact_id, outcome_id in citations:
        assert registry.get_object(artifact_id) is not None
        assert registry.get_object(outcome_id) is not None


def test_publish_action_passes_gates(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    gatekeeper: RecordingGatekeeper,
    tmp_path,
) -> None:
    outcome = _outcome(registry)
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)
    brief = builder.compose([outcome])
    path = builder.publish(brief)

    assert path.exists()
    assert gatekeeper.calls
    history = registry.action_history(brief.id, "Publish")
    assert history
    assert set(history[0].gate_results) == {
        "BHED_GNAN",
        "STEELMAN",
        "DOGMA_DRIFT",
        "CONSENT",
    }


def test_brief_bypass_attempt_fails(
    registry: OntologyRegistry,
    gateway: OntologyActionGateway,
    tmp_path,
) -> None:
    raw, errors = registry.create_object(
        "KnowledgeArtifact",
        {
            "title": "Bypass Brief",
            "artifact_type": "note",
            "domain": "dharma_swarm",
            "content": "uncited summary",
        },
        created_by="test",
    )
    assert raw is not None, errors
    builder = InsightBriefBuilder(gateway, output_dir=tmp_path, now_fn=_now)

    with pytest.raises(OntologyGatewayError, match="composed"):
        builder.publish(raw)


def test_cron_handler_publishes_canonical_insight_brief(
    registry: OntologyRegistry,
    tmp_path,
) -> None:
    _outcome(registry)
    db_path = tmp_path / "ontology.db"
    persist_shared_registry(registry, db_path)
    reset_shared_registry()

    try:
        result = execute_cron_job({
            "id": "ontology_insight_brief",
            "name": "Ontology-Native Insight Brief",
            "handler": "insight_brief",
            "ontology_path": str(db_path),
            "output_dir": str(tmp_path),
        })

        assert result.status == CronJobRunStatus.COMPLETED
        assert result.error == ""
        assert result.output.startswith("Insight brief published: ")
        published = Path(result.output.split(": ", 1)[1])
        assert published.exists()

        persisted = get_shared_registry(db_path, force_reload=True)
        artifacts = persisted.get_objects_by_type("KnowledgeArtifact")
        witnesses = persisted.get_objects_by_type("WitnessLog")
        assert artifacts
        assert witnesses
    finally:
        reset_shared_registry()
