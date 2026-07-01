from __future__ import annotations

import pytest

from dharma_swarm.forge_v1 import providers as forge_providers
from dharma_swarm.forge_v1.forge_v2 import runner
from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import RuntimeProviderConfig


@pytest.mark.parametrize(
    ("model_id", "expected_provider"),
    [
        ("glm-5.2", ProviderType.ZHIPU),
        ("kimi-for-coding", ProviderType.KIMI_CODE),
    ],
)
def test_pool_completion_routes_direct_frontier_lanes(monkeypatch, model_id, expected_provider):
    captured = {}
    provider = object()

    def fake_resolve(provider_type, *, model=None, timeout_seconds=None):
        captured["provider_type"] = provider_type
        captured["model"] = model
        captured["timeout_seconds"] = timeout_seconds
        return RuntimeProviderConfig(
            provider=provider_type,
            default_model=model,
            timeout_seconds=timeout_seconds,
            available=True,
        )

    def fake_create(config):
        captured["config"] = config
        return provider

    monkeypatch.setenv("FORGE_MODEL_CALL_TIMEOUT_S", "17")
    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.resolve_runtime_provider_config",
        fake_resolve,
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.create_runtime_provider",
        fake_create,
    )

    resolved_provider, wire_model = forge_providers._provider_for_model(model_id)

    assert resolved_provider is provider
    assert captured["provider_type"] == expected_provider
    assert captured["model"] == model_id
    assert captured["timeout_seconds"] == 17
    assert wire_model == model_id


def test_forge_v2_prefix_routes_glm_to_zhipu_not_stale_zai() -> None:
    assert runner._prefix_provider("glm-5.2") == ProviderType.ZHIPU
    assert runner._prefix_provider("kimi-for-coding") == ProviderType.KIMI_CODE
