from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dharma_swarm.model_council_e2e import (
    MODEL_COUNCIL_SCHEMA_VERSION,
    build_model_council_receipt,
    select_council_agents,
)
from dharma_swarm.model_status import (
    ModelStatus,
    ModelStatusProjection,
    ModelVerification,
    RouteStatus,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.runtime_provider import RuntimeProviderConfig


def _model(
    model_id: str,
    provider: ProviderType,
    route_model: str,
    rank: int,
) -> ModelStatus:
    route = RouteStatus(
        provider=provider.value,
        model_id=route_model,
        route=f"{provider.value}:{route_model}",
        status="live_routable",
        reason=None,
    )
    return ModelStatus(
        id=model_id,
        rank=rank,
        provider=provider.value,
        display_name=model_id,
        ui_label=model_id,
        custom_label=None,
        short_name=None,
        tier="strong",
        lane="floor",
        below_floor=False,
        max_context=128_000,
        strengths=["reasoning"],
        available=True,
        status="live_routable",
        unavailable_reason=None,
        available_routes=[route.route],
        routes=[route.route],
        route_statuses=[route],
        notes=None,
        docs_url="https://docs.example.invalid",
        provider_url="https://docs.example.invalid",
        verification=ModelVerification(status="unverified"),
    )


def _projection() -> ModelStatusProjection:
    return ModelStatusProjection(
        schema_version="test.schema",
        generated_at="2026-06-18T00:00:00Z",
        oracle_state="fresh",
        live_providers=[
            ProviderType.OPENAI.value,
            ProviderType.OLLAMA.value,
            ProviderType.NVIDIA_NIM.value,
        ],
        models=[
            _model("one", ProviderType.OPENAI, "route-one", 1),
            _model("two", ProviderType.OLLAMA, "route-two", 2),
            _model("three", ProviderType.NVIDIA_NIM, "route-three", 3),
        ],
    )


def test_select_council_agents_prefers_three_providers() -> None:
    agents, skipped, projection_data = select_council_agents(_projection())

    assert skipped == []
    assert projection_data["oracle_state"] == "fresh"
    assert [agent.stage for agent in agents] == ["draft", "critique", "synthesis"]
    assert {agent.route.provider for agent in agents} == {
        ProviderType.OPENAI,
        ProviderType.OLLAMA,
        ProviderType.NVIDIA_NIM,
    }


def test_model_council_dry_run_does_not_construct_provider() -> None:
    def resolver(*_args, **_kwargs) -> RuntimeProviderConfig:
        raise AssertionError("resolver should not run during dry-run")

    payload = build_model_council_receipt(
        projection=_projection(),
        live_calls_enabled=False,
        resolver=resolver,
    )

    assert payload["schema_version"] == MODEL_COUNCIL_SCHEMA_VERSION
    assert payload["status"] == "planned"
    assert payload["counts"]["planned_agents"] == 3
    assert payload["counts"]["unique_planned_providers"] == 3
    assert payload["counts"]["live_calls_attempted"] == 0
    assert payload["transcript"] == []


def test_model_council_live_path_uses_a2a_and_runtime_factory() -> None:
    resolver_calls: list[tuple[ProviderType, str | None]] = []

    def resolver(provider: ProviderType, **kwargs) -> RuntimeProviderConfig:
        resolver_calls.append((provider, kwargs.get("model")))
        return RuntimeProviderConfig(
            provider=provider,
            default_model=kwargs.get("model"),
            available=True,
            source="test",
        )

    class FakeProvider:
        async def complete(self, request: LLMRequest) -> LLMResponse:
            content = f"{request.model} completed {request.messages[0]['content'][:30]}"
            return LLMResponse(
                content=content,
                model=request.model,
                provider="fake",
                usage={"total_tokens": 3},
            )

    payload = build_model_council_receipt(
        projection=_projection(),
        live_calls_enabled=True,
        resolver=resolver,
        provider_factory=lambda _config: FakeProvider(),
    )

    assert payload["status"] == "passed"
    assert payload["counts"]["live_calls_attempted"] == 3
    assert payload["counts"]["completed_stages"] == 3
    assert payload["a2a"]["a2a_path"] == "local_in_process"
    assert payload["a2a"]["a2a_server_tasks"] == {"completed": 3}
    assert [row["a2a_task"]["status"] for row in payload["transcript"]] == [
        "completed",
        "completed",
        "completed",
    ]
    assert resolver_calls == [
        (ProviderType.OPENAI, "route-one"),
        (ProviderType.OLLAMA, "route-two"),
        (ProviderType.NVIDIA_NIM, "route-three"),
    ]
    assert payload["final_artifact"]["status"] == "available"


def test_model_council_live_cli_requires_env_gate(monkeypatch) -> None:
    monkeypatch.delenv("DHARMA_LIVE_MODEL_E2E", raising=False)
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("DHARMA_LIVE_MODEL_E2E", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify/model_council_e2e.py",
            "--live",
            "--no-refresh",
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 2
    assert "DHARMA_LIVE_MODEL_E2E=1" in result.stdout
