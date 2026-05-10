from __future__ import annotations

import json

import pytest

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.providers import ModelRouter
from dharma_swarm.routing_contract import complete_routed
from dharma_swarm.telemetry_plane import TelemetryPlaneStore


class _DummyProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="ok",
            model=request.model,
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        )

    async def stream(self, request: LLMRequest):
        yield "ok"


@pytest.mark.asyncio
async def test_complete_routed_success_uses_model_router_and_returns_contract(
    tmp_path,
) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {ProviderType.OPENAI: _DummyProvider()},
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    result = await complete_routed(
        request=LLMRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "say ok"}],
        ),
        action_name="contract_success",
        context={
            "session_id": "sess-contract",
            "task_id": "task-contract-success",
        },
        caller="tests.routing_contract",
        task_type="test",
        router=router,
        available_provider_types=[ProviderType.OPENAI],
        audit_log_path=tmp_path / "routing_contract_audit.jsonl",
    )

    assert result.outcome == "success"
    assert result.resident_handoff is False
    assert result.decision is not None
    assert result.decision.selected_provider == ProviderType.OPENAI
    assert result.response is not None
    assert result.response.content == "ok"
    assert result.task_signature

    routes = await telemetry.list_routing_decisions(
        task_id="task-contract-success",
        limit=10,
    )
    assert len(routes) == 1
    assert routes[0].selected_provider == "openai"


@pytest.mark.asyncio
async def test_complete_routed_no_provider_records_resident_handoff(
    tmp_path,
) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    audit_log = tmp_path / "routing_contract_audit.jsonl"
    router = ModelRouter({}, telemetry=telemetry, routing_audit_path=audit_log)

    result = await complete_routed(
        request=LLMRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "keep watch"}],
        ),
        action_name="contract_no_provider",
        context={
            "session_id": "sess-no-provider",
            "task_id": "task-no-provider",
        },
        caller="tests.routing_contract",
        task_type="pulse",
        router=router,
        available_provider_types=[],
        audit_log_path=audit_log,
        raise_on_failure=False,
    )

    assert result.outcome == "no_route"
    assert result.resident_handoff is True
    assert result.response is None
    assert result.decision is None
    assert "No available providers" in result.error

    routes = await telemetry.list_routing_decisions(
        task_id="task-no-provider",
        limit=10,
    )
    assert len(routes) == 1
    assert routes[0].route_path == "resident_degraded_handoff"
    assert routes[0].selected_provider == ""
    assert routes[0].requires_human is True
    assert routes[0].metadata["resident_fallback"] is True
    assert routes[0].metadata["caller"] == "tests.routing_contract"

    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-no-provider",
        limit=10,
    )
    assert any(
        item.outcome_kind == "resident_degraded_handoff"
        and item.subject_id == "resident_control_plane"
        and item.status == "queued"
        for item in outcomes
    )

    audit_rows = [
        json.loads(line) for line in audit_log.read_text().splitlines()
    ]
    assert audit_rows[0]["row_kind"] == "resident_handoff"
    assert audit_rows[0]["outcome"] == "no_route"
    assert audit_rows[0]["metadata"]["resident_fallback"] is True

    stigmergy_rows = [
        json.loads(line)
        for line in (tmp_path / "_stigmergy_isolated" / "marks.jsonl")
        .read_text()
        .splitlines()
    ]
    assert stigmergy_rows[0]["agent"] == "resident_control_plane"
    assert stigmergy_rows[0]["channel"] == "action_queue"


@pytest.mark.asyncio
async def test_complete_routed_raise_on_failure_still_records_handoff(
    tmp_path,
) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    audit_log = tmp_path / "routing_contract_audit.jsonl"
    router = ModelRouter({}, telemetry=telemetry, routing_audit_path=audit_log)

    with pytest.raises(RuntimeError, match="No available providers"):
        await complete_routed(
            request=LLMRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": "keep watch"}],
            ),
            action_name="contract_raise_no_provider",
            context={
                "session_id": "sess-raise",
                "task_id": "task-raise",
            },
            caller="tests.routing_contract",
            task_type="pulse",
            router=router,
            available_provider_types=[],
            audit_log_path=audit_log,
            raise_on_failure=True,
        )

    routes = await telemetry.list_routing_decisions(task_id="task-raise", limit=10)
    assert len(routes) == 1
    assert routes[0].route_path == "resident_degraded_handoff"
