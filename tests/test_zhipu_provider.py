"""Stage 3: z.ai / Zhipu wired as a first-party GLM provider (not via OpenRouter).

Track: provider-routing-consolidation-2026-06. Locks the full wiring chain:
enum -> key env -> default model -> resolution -> factory -> intelligence rank.
"""
from __future__ import annotations

import pytest

from dharma_swarm.api_keys import ZHIPU_API_KEY_ENV, PROVIDER_API_KEY_ENV_KEYS
from dharma_swarm.model_defaults import default_for_provider
from dharma_swarm.model_hierarchy import (
    CANONICAL_SEED_ORDER,
    MODEL_INTELLIGENCE,
    intelligence_order,
)
from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import (
    create_runtime_provider,
    resolve_runtime_provider_config,
)


def test_zhipu_is_a_provider_type() -> None:
    assert ProviderType.ZHIPU.value == "zhipu"
    assert ProviderType.ZHIPU in CANONICAL_SEED_ORDER


def test_zhipu_key_env_registered() -> None:
    assert ZHIPU_API_KEY_ENV == "ZHIPU_API_KEY"
    assert PROVIDER_API_KEY_ENV_KEYS["zhipu"] == ZHIPU_API_KEY_ENV


def test_zhipu_default_model_is_glm() -> None:
    assert default_for_provider(ProviderType.ZHIPU) == "glm-5.2"


def test_zhipu_has_intelligence_score() -> None:
    # GLM-4.6 ranks among the strong frontier (above Google, below cloud GLM-5).
    assert MODEL_INTELLIGENCE[ProviderType.ZHIPU] == 67


def test_zhipu_resolves_to_first_party_endpoint() -> None:
    cfg = resolve_runtime_provider_config(
        ProviderType.ZHIPU, api_key="sk-zhipu-test"
    )
    assert cfg.available is True
    assert cfg.default_model == "glm-5.2"
    # First-party z.ai endpoint — NOT openrouter.ai
    assert cfg.base_url == "https://api.z.ai/api/coding/paas/v4"
    assert "z.ai" in (cfg.base_url or "")
    assert "openrouter" not in (cfg.base_url or "")


def test_zhipu_unavailable_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Deterministic: clear every alias the resolver would fall back to, so the
    # assertion can't be flaked by a GLM/z.ai key present in the CI environment.
    for var in ("ZHIPU_API_KEY", "GLM_API_KEY", "ZAI_API_KEY", "ZHIPUAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    cfg = resolve_runtime_provider_config(ProviderType.ZHIPU, api_key=None)
    assert cfg.available is False


def test_zhipu_factory_builds_zhipu_provider() -> None:
    cfg = resolve_runtime_provider_config(ProviderType.ZHIPU, api_key="sk-zhipu-test")
    provider = create_runtime_provider(cfg)
    assert type(provider).__name__ == "ZhipuProvider"


def test_zhipu_ranks_by_power_above_cheaper_frontier() -> None:
    order = intelligence_order(CANONICAL_SEED_ORDER, respect_cost_tiers=False)
    # Power-first: Zhipu (67) outranks Google AI (65) and OpenRouter (59).
    assert order.index(ProviderType.ZHIPU) < order.index(ProviderType.GOOGLE_AI)
    assert order.index(ProviderType.ZHIPU) < order.index(ProviderType.OPENROUTER)
