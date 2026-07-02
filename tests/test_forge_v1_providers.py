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


def test_forge_v2_high_slot_defaults_are_recent_frontier() -> None:
    assert runner.FORGE_HIGH_SLOT_MIN_RELEASE_DATE == "2026-04-01"
    assert runner.DEFAULT_FORGE_HIGH_SLOT_PROBE_TIMEOUT_S == 20
    assert runner._high_slot_probe_timeout_s(240) == 20
    assert runner.DEFAULT_FORGE_GENERATOR_MODEL == "glm-5.2"
    assert runner.DEFAULT_FORGE_VERIFIER_MODEL == "kimi-k2.7-code:cloud"
    assert "moonshotai/kimi-k2.6" not in runner.FORGE_HIGH_SLOT_MODEL_IDS
    assert "deepseek-v4-pro:cloud" in runner.FORGE_HIGH_SLOT_MODEL_IDS
    assert "minimax-m3:cloud" in runner.FORGE_HIGH_SLOT_MODEL_IDS


def test_forge_v2_high_slot_pair_skips_legacy_pin_for_recent_fallback(monkeypatch) -> None:
    live = {"deepseek-v4-pro:cloud", "minimax-m3:cloud"}

    def fake_probe(slot, timeout_s=40):
        return slot.model_id in live

    monkeypatch.setattr(runner, "_probe", fake_probe)

    gen, ver, callable_slots, rows = runner._resolve_high_slot_pair(
        "glm-5.2",
        "moonshotai/kimi-k2.6",
        timeout_s=1,
    )

    assert gen.model_id == "deepseek-v4-pro:cloud"
    assert ver.model_id == "minimax-m3:cloud"
    assert [slot.model_id for slot in callable_slots] == [
        "deepseek-v4-pro:cloud",
        "minimax-m3:cloud",
    ]
    legacy_row = next(row for row in rows if row["model_id"] == "moonshotai/kimi-k2.6")
    assert legacy_row["callable"] is False
    assert legacy_row["error"] == "below_recent_high_slot_floor"


def test_forge_v2_probe_uses_single_shot_provider_call(monkeypatch) -> None:
    class Response:
        content = "OK"

    class Provider:
        async def complete(self, request):
            assert request.max_tokens == 256
            return Response()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("probe must not use canonical _call retry path")

    monkeypatch.setattr(runner, "_provider_for_slot", lambda *_args, **_kwargs: (Provider(), "glm-5.2"))
    monkeypatch.setattr(runner, "_call", fail_if_called)

    assert runner._probe(runner._SimpleSlot("glm-5.2", ProviderType.ZHIPU), timeout_s=1) is True
