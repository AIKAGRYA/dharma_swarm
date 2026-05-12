from __future__ import annotations

import json

import pytest

from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.provider_policy import ProviderRouteRequest
from dharma_swarm.providers import ModelRouter
from dharma_swarm.telemetry_plane import TelemetryPlaneStore


class _DummyProvider:
    def __init__(
        self,
        content: str,
        *,
        prompt_tokens: int = 120,
        completion_tokens: int = 40,
    ) -> None:
        self.content = content
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    async def complete(self, request: LLMRequest) -> LLMResponse:
        total_tokens = self.prompt_tokens + self.completion_tokens
        return LLMResponse(
            content=self.content,
            model=request.model,
            usage={
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": total_tokens,
            },
        )

    async def stream(self, request: LLMRequest):
        yield self.content


class _FailingProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("synthetic upstream failure")

    async def stream(self, request: LLMRequest):
        yield ""


def _route_by_caller(routes, caller: str):
    return next(route for route in routes if route.caller == caller)


@pytest.mark.asyncio
async def test_model_router_success_writes_telemetry_records(tmp_path) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {ProviderType.OPENAI: _DummyProvider("ok")},
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    decision, response = await router.complete_for_task(
        ProviderRouteRequest(
            action_name="summarize_notes",
            risk_score=0.12,
            uncertainty=0.14,
            novelty=0.12,
            urgency=0.4,
            expected_impact=0.2,
            estimated_latency_ms=200,
            estimated_tokens=300,
            context={
                "session_id": "sess-telemetry",
                "task_id": "task-success",
                "run_id": "run-success",
            },
        ),
        LLMRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Summarize these notes"}],
        ),
        available_provider_types=[ProviderType.OPENAI],
    )

    routes = await telemetry.list_routing_decisions(task_id="task-success", limit=10)
    attempts = await telemetry.list_provider_attempts(decision_id=routes[0].decision_id)
    policies = await telemetry.list_policy_decisions(
        task_id="task-success",
        policy_name="provider_policy",
        limit=10,
    )
    economic = await telemetry.list_economic_events(
        event_kind="cost",
        session_id="sess-telemetry",
        limit=10,
    )
    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-telemetry",
        limit=20,
    )

    assert decision.selected_provider == ProviderType.OPENAI
    assert response.content == "ok"
    assert len(routes) == 1
    assert routes[0].selected_provider == "openai"
    assert routes[0].caller == "providers.ModelRouter.complete_for_task"
    assert routes[0].task_signature
    assert routes[0].task_type == "unknown"
    assert routes[0].decision_class == "pinned"
    assert routes[0].selected_tier == "paid"
    assert routes[0].n_attempts == 1
    assert routes[0].outcome == "success"
    assert routes[0].metadata["result"] == "success"
    assert len(attempts) == 1
    assert attempts[0].provider == "openai"
    assert attempts[0].success is True
    assert attempts[0].usage["total_tokens"] == 160
    assert len(policies) == 1
    assert policies[0].decision == "approved"
    assert len(economic) == 1
    assert economic[0].counterparty == "openai"
    assert economic[0].amount > 0.0
    assert any(
        item.outcome_kind == "provider_attempt"
        and item.subject_id == "openai"
        and item.status == "succeeded"
        for item in outcomes
    )
    assert any(
        item.outcome_kind == "provider_completion"
        and item.subject_id == "openai"
        and item.status == "observed"
        and item.value == 1.0
        for item in outcomes
    )
    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "routing_decisions.jsonl").read_text().splitlines()
    ]
    assert [row["row_kind"] for row in audit_rows] == ["decision", "attempt"]
    assert audit_rows[0]["caller"] == "providers.ModelRouter.complete_for_task"


@pytest.mark.asyncio
async def test_model_router_fallback_success_marks_fallback_in_telemetry(tmp_path) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {
            ProviderType.OPENROUTER_FREE: _FailingProvider(),
            ProviderType.ANTHROPIC: _DummyProvider("frontier"),
        },
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    decision, response = await router.complete_for_task(
        ProviderRouteRequest(
            action_name="triage_notes",
            risk_score=0.10,
            uncertainty=0.12,
            novelty=0.10,
            urgency=0.3,
            expected_impact=0.2,
            estimated_latency_ms=200,
            estimated_tokens=300,
            preferred_low_cost=True,
            context={
                "session_id": "sess-fallback",
                "task_id": "task-fallback",
                "run_id": "run-fallback",
            },
        ),
        LLMRequest(
            model="ignored",
            messages=[{"role": "user", "content": "Summarize these notes"}],
        ),
        available_provider_types=[
            ProviderType.OPENROUTER_FREE,
            ProviderType.ANTHROPIC,
        ],
    )

    routes = await telemetry.list_routing_decisions(task_id="task-fallback", limit=10)
    attempts = await telemetry.list_provider_attempts(decision_id=routes[0].decision_id)
    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-fallback",
        limit=20,
    )

    assert decision.selected_provider == ProviderType.ANTHROPIC
    assert response.content == "frontier"
    assert len(routes) == 1
    assert routes[0].selected_provider == "anthropic"
    assert routes[0].caller == "providers.ModelRouter.complete_for_task"
    assert routes[0].decision_class == "fallback"
    assert routes[0].widened_from == "openrouter_free"
    assert routes[0].n_attempts == len(attempts)
    assert routes[0].metadata["fallback_selected"] is True
    assert routes[0].metadata["initial_selected_provider"] == "openrouter_free"
    assert any(attempt.provider == "openrouter_free" and not attempt.success for attempt in attempts)
    assert any(attempt.provider == "anthropic" and attempt.success for attempt in attempts)
    assert any(
        item.outcome_kind == "provider_attempt"
        and item.subject_id == "openrouter_free"
        and item.status == "failed"
        for item in outcomes
    )
    assert any(
        item.outcome_kind == "provider_attempt"
        and item.subject_id == "anthropic"
        and item.status == "succeeded"
        for item in outcomes
    )
    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "routing_decisions.jsonl").read_text().splitlines()
    ]
    assert all(row["row_kind"] in {"decision", "attempt"} for row in audit_rows)
    assert audit_rows[0]["decision_class"] == "fallback"


@pytest.mark.asyncio
async def test_model_router_total_failure_writes_failed_completion_telemetry(tmp_path) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {ProviderType.OPENAI: _FailingProvider()},
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    with pytest.raises(RuntimeError, match="All providers failed"):
        await router.complete_for_task(
            ProviderRouteRequest(
                action_name="deploy_hotfix",
                risk_score=0.12,
                uncertainty=0.14,
                novelty=0.15,
                urgency=0.6,
                expected_impact=0.4,
                context={
                    "session_id": "sess-failure",
                    "task_id": "task-failure",
                    "run_id": "run-failure",
                },
            ),
            LLMRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Deploy the hotfix"}],
            ),
            available_provider_types=[ProviderType.OPENAI],
        )

    routes = await telemetry.list_routing_decisions(task_id="task-failure", limit=10)
    completion_route = _route_by_caller(
        routes,
        "providers.ModelRouter.complete_for_task",
    )
    resident_route = _route_by_caller(
        routes,
        "providers.ModelRouter.resident_degraded_handoff",
    )
    attempts = await telemetry.list_provider_attempts(decision_id=completion_route.decision_id)
    resident_attempts = await telemetry.list_provider_attempts(
        decision_id=resident_route.decision_id,
    )
    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-failure",
        limit=20,
    )
    economic = await telemetry.list_economic_events(
        event_kind="cost",
        session_id="sess-failure",
        limit=10,
    )

    assert len(routes) == 2
    assert completion_route.selected_provider == "openai"
    assert completion_route.decision_class == "pinned"
    assert completion_route.outcome == "all_failed"
    assert completion_route.n_attempts == len(attempts)
    assert completion_route.metadata["result"] == "failed"
    assert resident_route.selected_provider == ""
    assert resident_route.selected_model_hint == "resident-control-plane"
    assert resident_route.decision_class == "no_route"
    assert resident_route.outcome == "all_failed"
    assert resident_route.requires_human is True
    assert resident_route.metadata["resident_fallback"] is True
    assert resident_route.metadata["handoff_reason"] == "all_providers_failed"
    assert resident_attempts
    assert all(not attempt.success for attempt in resident_attempts)
    assert attempts
    assert all(not attempt.success for attempt in attempts)
    assert attempts[0].provider == "openai"
    assert economic == []
    assert any(
        item.outcome_kind == "provider_completion"
        and item.subject_id == "openai"
        and item.status == "failed"
        and item.value == 0.0
        for item in outcomes
    )
    assert any(
        item.outcome_kind == "resident_degraded_handoff"
        and item.subject_id == "resident_control_plane"
        and item.status == "queued"
        for item in outcomes
    )
    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "routing_decisions.jsonl").read_text().splitlines()
    ]
    decision_rows = [row for row in audit_rows if row["row_kind"] == "decision"]
    assert {row["caller"] for row in decision_rows} == {
        "providers.ModelRouter.complete_for_task",
        "providers.ModelRouter.resident_degraded_handoff",
    }
    assert any(row["outcome"] == "all_failed" for row in decision_rows)

    stigmergy_rows = [
        json.loads(line)
        for line in (tmp_path / "_stigmergy_isolated" / "marks.jsonl")
        .read_text()
        .splitlines()
    ]
    assert any(
        row["agent"] == "resident_control_plane"
        and row["channel"] == "action_queue"
        and "resident handoff queued" in row["observation"]
        for row in stigmergy_rows
    )


@pytest.mark.asyncio
async def test_model_router_no_available_provider_records_resident_handoff(
    tmp_path,
) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {},
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    with pytest.raises(RuntimeError, match="No available providers"):
        await router.complete_for_task(
            ProviderRouteRequest(
                action_name="heartbeat",
                risk_score=0.1,
                uncertainty=0.1,
                novelty=0.1,
                urgency=0.9,
                expected_impact=0.6,
                context={
                    "session_id": "sess-no-provider",
                    "task_id": "task-no-provider",
                    "run_id": "run-no-provider",
                    "task_type": "pulse",
                },
            ),
            LLMRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": "keep watch"}],
            ),
            available_provider_types=[],
        )

    routes = await telemetry.list_routing_decisions(task_id="task-no-provider", limit=10)
    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-no-provider",
        limit=10,
    )

    assert len(routes) == 1
    assert routes[0].caller == "providers.ModelRouter.resident_degraded_handoff"
    assert routes[0].selected_provider == ""
    assert routes[0].decision_class == "no_route"
    assert routes[0].outcome == "no_route"
    assert routes[0].task_type == "pulse"
    assert routes[0].requires_human is True
    assert routes[0].metadata["resident_fallback"] is True
    assert routes[0].metadata["handoff_reason"] == (
        "no_available_providers_after_routing_filter"
    )
    assert routes[0].n_attempts == 0
    assert any(
        item.outcome_kind == "resident_degraded_handoff"
        and item.subject_id == "resident_control_plane"
        and item.status == "queued"
        for item in outcomes
    )

    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "routing_decisions.jsonl").read_text().splitlines()
    ]
    assert audit_rows == [
        row
        for row in audit_rows
        if row["caller"] == "providers.ModelRouter.resident_degraded_handoff"
    ]
    assert audit_rows[0]["outcome"] == "no_route"

    stigmergy_rows = [
        json.loads(line)
        for line in (tmp_path / "_stigmergy_isolated" / "marks.jsonl")
        .read_text()
        .splitlines()
    ]
    assert stigmergy_rows[0]["agent"] == "resident_control_plane"
    assert stigmergy_rows[0]["channel"] == "action_queue"


@pytest.mark.asyncio
async def test_model_router_resident_handoff_survives_without_telemetry(
    tmp_path,
) -> None:
    router = ModelRouter(
        {},
        telemetry_enabled=False,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    with pytest.raises(RuntimeError, match="No available providers"):
        await router.complete_for_task(
            ProviderRouteRequest(
                action_name="resident_watch",
                risk_score=0.1,
                uncertainty=0.1,
                novelty=0.1,
                urgency=0.8,
                expected_impact=0.5,
                context={
                    "session_id": "sess-audit-only",
                    "task_id": "task-audit-only",
                    "task_type": "pulse",
                },
            ),
            LLMRequest(
                model="gpt-4o",
                messages=[{"role": "user", "content": "keep watch"}],
            ),
            available_provider_types=[],
        )

    audit_rows = [
        json.loads(line)
        for line in (tmp_path / "routing_decisions.jsonl").read_text().splitlines()
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0]["row_kind"] == "decision"
    assert audit_rows[0]["caller"] == "providers.ModelRouter.resident_degraded_handoff"
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
async def test_model_router_witness_failure_does_not_break_completion(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    telemetry = TelemetryPlaneStore(tmp_path / "runtime.db")
    router = ModelRouter(
        {ProviderType.OPENAI: _DummyProvider("ok")},
        telemetry=telemetry,
        routing_audit_path=tmp_path / "routing_decisions.jsonl",
    )

    async def raising_emit(**kwargs: object) -> None:
        raise RuntimeError("witness layer unavailable")

    monkeypatch.setattr(
        "dharma_swarm.route_witness.emit_routing_decision",
        raising_emit,
    )

    decision, response = await router.complete_for_task(
        ProviderRouteRequest(
            action_name="summarize_notes",
            risk_score=0.12,
            uncertainty=0.14,
            novelty=0.12,
            urgency=0.4,
            expected_impact=0.2,
            context={
                "session_id": "sess-witness-failure",
                "task_id": "task-witness-failure",
            },
        ),
        LLMRequest(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Summarize these notes"}],
        ),
        available_provider_types=[ProviderType.OPENAI],
    )

    assert decision.selected_provider == ProviderType.OPENAI
    assert response.content == "ok"
    assert await telemetry.list_routing_decisions(task_id="task-witness-failure") == []
    outcomes = await telemetry.list_external_outcomes(
        session_id="sess-witness-failure",
        limit=20,
    )
    assert any(
        item.outcome_kind == "provider_completion"
        and item.subject_id == "openai"
        and item.status == "observed"
        for item in outcomes
    )
