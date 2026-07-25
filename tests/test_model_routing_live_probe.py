from __future__ import annotations

from dataclasses import replace

import pytest

from dharma_swarm.model_routing_live_probe import (
    LIVE_PROBE_SCHEMA_VERSION,
    build_live_probe_matrix,
    build_probe_plan,
    classify_live_failure,
    normalize_failure_class,
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
    *,
    status: str,
    unavailable_reason: str | None,
    route_status: RouteStatus,
) -> ModelStatus:
    return ModelStatus(
        id="probe-model",
        rank=1,
        provider=route_status.provider,
        display_name="Probe Model",
        ui_label="Probe Model",
        custom_label=None,
        short_name=None,
        tier="strong",
        lane="floor",
        below_floor=False,
        max_context=128_000,
        strengths=["reasoning"],
        available=status == "live_routable",
        status=status,
        unavailable_reason=unavailable_reason,
        available_routes=[route_status.route] if status == "live_routable" else [],
        routes=[route_status.route],
        route_statuses=[route_status],
        notes=None,
        docs_url="https://docs.example.invalid",
        provider_url="https://docs.example.invalid",
        verification=ModelVerification(status="unverified"),
    )


def _projection(model: ModelStatus) -> ModelStatusProjection:
    return ModelStatusProjection(
        schema_version="test.schema",
        generated_at="2026-06-18T00:00:00Z",
        oracle_state="fresh",
        live_providers=[model.provider],
        models=[model],
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("OPENAI_API_KEY not set", "key_missing"),
        ("HTTP error 429: too many requests", "rate_limited"),
        ("insufficient_quota for this key", "quota"),
        ("Credit balance is too low", "quota"),
        ("HTTP error 404: model not found", "model_missing"),
        ("HTTP error 400 invalid_request unsupported model", "unsupported_route"),
        ("all connection attempts failed", "provider_dead"),
        (TimeoutError(), "timeout"),
        ("the JSON schema did not match", "schema_failure"),
    ],
)
def test_classify_live_failure_uses_contract_classes(error, expected: str) -> None:
    assert classify_live_failure(error) == expected


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("key_status_unknown", "key_missing"),
        ("quota_exhausted", "quota"),
        ("rate_limited", "rate_limited"),
        ("unknown_model", "model_missing"),
        ("unreachable", "provider_dead"),
        ("unsupported_route", "unsupported_route"),
    ],
)
def test_normalize_failure_class_maps_existing_reasons(reason: str, expected: str) -> None:
    assert normalize_failure_class(reason) == expected


def test_build_probe_plan_selects_first_live_route() -> None:
    route = RouteStatus(
        provider=ProviderType.OPENAI.value,
        model_id="route-model",
        route="openai:route-model",
        status="live_routable",
        reason=None,
    )
    specs, skipped, projection = build_probe_plan(_projection(_model(status="live_routable", unavailable_reason=None, route_status=route)))

    assert skipped == []
    assert projection["oracle_state"] == "fresh"
    assert len(specs) == 1
    assert specs[0].provider == ProviderType.OPENAI
    assert specs[0].model_id == "route-model"


def test_build_probe_plan_selects_all_live_routes_for_model() -> None:
    model = _model(
        status="live_routable",
        unavailable_reason=None,
        route_status=RouteStatus(
            provider=ProviderType.CODEX.value,
            model_id="codex-model",
            route="codex:codex-model",
            status="live_routable",
            reason=None,
        ),
    )
    model = replace(
        model,
        route_statuses=[
            model.route_statuses[0],
            RouteStatus(
                provider=ProviderType.OPENAI.value,
                model_id="openai-model",
                route="openai:openai-model",
                status="live_routable",
                reason=None,
            ),
        ],
        available_routes=["codex:codex-model", "openai:openai-model"],
        routes=["codex:codex-model", "openai:openai-model"],
    )

    specs, skipped, _projection_data = build_probe_plan(_projection(model))

    assert skipped == []
    assert [(spec.provider, spec.model_id) for spec in specs] == [
        (ProviderType.CODEX, "codex-model"),
        (ProviderType.OPENAI, "openai-model"),
    ]


def test_build_probe_plan_records_unavailable_reason() -> None:
    route = RouteStatus(
        provider=ProviderType.OPENAI.value,
        model_id="route-model",
        route="openai:route-model",
        status="unavailable",
        reason="quota",
    )
    specs, skipped, _projection_data = build_probe_plan(
        _projection(_model(status="unavailable", unavailable_reason="quota", route_status=route))
    )

    assert specs == []
    assert skipped[0]["failure_class"] == "quota"


@pytest.mark.asyncio
async def test_live_probe_matrix_uses_runtime_resolver_and_provider_factory() -> None:
    route = RouteStatus(
        provider=ProviderType.OPENAI.value,
        model_id="route-model",
        route="openai:route-model",
        status="live_routable",
        reason=None,
    )
    projection = _projection(_model(status="live_routable", unavailable_reason=None, route_status=route))
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
            if "minified JSON" in request.messages[0]["content"]:
                content = '{"ok":true,"token":"MODEL_PROBE"}'
            else:
                content = "PONG"
            return LLMResponse(
                content=content,
                model=request.model,
                provider="fake",
                usage={"total_tokens": 1},
            )

    payload = await build_live_probe_matrix(
        projection=projection,
        live_calls_enabled=True,
        profile="standard",
        resolver=resolver,
        provider_factory=lambda _config: FakeProvider(),
    )

    assert payload["schema_version"] == LIVE_PROBE_SCHEMA_VERSION
    assert payload["status"] == "passed"
    assert payload["counts"]["live_calls_attempted"] == 2
    assert payload["counts"]["failed"] == 0
    assert resolver_calls == [(ProviderType.OPENAI, "route-model")]
    assert {result["probe"] for result in payload["results"]} == {"pong_exact", "json_schema"}


@pytest.mark.asyncio
async def test_dry_run_matrix_does_not_construct_provider() -> None:
    route = RouteStatus(
        provider=ProviderType.OPENAI.value,
        model_id="route-model",
        route="openai:route-model",
        status="live_routable",
        reason=None,
    )

    def resolver(*_args, **_kwargs) -> RuntimeProviderConfig:
        raise AssertionError("resolver should not run in dry-run mode")

    payload = await build_live_probe_matrix(
        projection=_projection(_model(status="live_routable", unavailable_reason=None, route_status=route)),
        live_calls_enabled=False,
        resolver=resolver,
    )

    assert payload["status"] == "planned"
    assert payload["counts"]["live_calls_attempted"] == 0
    assert payload["planned"][0]["route"] == "openai:route-model"
