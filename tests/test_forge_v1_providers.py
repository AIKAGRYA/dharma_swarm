"""Tests for the Forge v1 live-model adapter (providers.py).

Two layers:
- OFFLINE (always run): the prompt-build / patch-parse plumbing via
  FakeCompletion, plus the token-usage helper across both naming conventions.
  No network, no spend.
- LIVE (gated): a single real frontier-model call, skipped unless FORGE_LIVE=1
  so CI / offline never spends money.
"""
import os

import pytest

from dharma_swarm.forge_v1.fixtures import ADD_TASK
from dharma_swarm.forge_v1.harness import verify
from dharma_swarm.forge_v1.providers import (
    FakeCompletion,
    LiveModel,
    PoolCompletion,
    _provider_for_model,
    _usage_tokens,
)
from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import RuntimeProviderConfig


# --- OFFLINE: prompt -> completion -> parse -> Candidate plumbing ---
def test_livemodel_parses_fenced_patch_from_completion():
    """A fenced python block in the completion is parsed into the patch."""
    fixed = "def add(a, b):\n    return a + b\n"
    fake = FakeCompletion([f"Here is the fix:\n```python\n{fixed}```\n"])
    cand = LiveModel(fake).propose(ADD_TASK, 0)

    assert set(cand.patch) == {"solution.py"}
    assert cand.patch["solution.py"] == fixed
    assert cand.tokens > 0  # FakeCompletion charges len-based tokens
    # The parsed patch is correct, so the gold-test verifier passes offline.
    assert verify(ADD_TASK, cand.patch) is True


def test_livemodel_falls_back_to_raw_text_when_no_fence():
    """No code fence -> the whole response is used as the patch body."""
    fake = FakeCompletion(["def add(a, b):\n    return a + b\n"])
    cand = LiveModel(fake).propose(ADD_TASK, 0)
    assert cand.patch["solution.py"].startswith("def add")


def test_livemodel_prompt_includes_buggy_source_and_filename():
    captured = {}

    class _Spy:
        def complete(self, prompt):
            captured["prompt"] = prompt
            return "```python\nx\n```", 7

    LiveModel(_Spy()).propose(ADD_TASK, 0)
    assert "solution.py" in captured["prompt"]
    assert "return a - b" in captured["prompt"]  # the buggy source is shown


# --- OFFLINE: token-usage accounting across provider conventions ---
def test_usage_tokens_openai_convention():
    assert _usage_tokens({"prompt_tokens": 100, "completion_tokens": 40}) == 140


def test_usage_tokens_anthropic_convention():
    assert _usage_tokens({"input_tokens": 12, "output_tokens": 8}) == 20


def test_usage_tokens_total_only_fallback():
    assert _usage_tokens({"total_tokens": 55}) == 55


def test_usage_tokens_empty():
    assert _usage_tokens({}) == 0


def test_pool_completion_routes_k3_to_kimi_code_provider(monkeypatch):
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

    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.resolve_runtime_provider_config",
        fake_resolve,
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.create_runtime_provider",
        fake_create,
    )

    resolved_provider, wire_model = _provider_for_model("k3")

    assert resolved_provider is provider
    assert captured["provider_type"] == ProviderType.KIMI_CODE
    assert captured["model"] == "k3"
    assert captured["timeout_seconds"] == 240
    assert wire_model == "k3"


def test_pool_completion_routes_glm_52_to_zhipu_provider(monkeypatch):
    captured = {}
    provider = object()

    def fake_resolve(provider_type, *, model=None, timeout_seconds=None):
        captured["provider_type"] = provider_type
        captured["model"] = model
        return RuntimeProviderConfig(
            provider=provider_type,
            default_model=model,
            timeout_seconds=timeout_seconds,
            available=True,
        )

    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.resolve_runtime_provider_config",
        fake_resolve,
    )
    monkeypatch.setattr(
        "dharma_swarm.runtime_provider.create_runtime_provider",
        lambda config: provider,
    )

    resolved_provider, wire_model = _provider_for_model("glm-5.2")

    assert resolved_provider is provider
    assert captured["provider_type"] == ProviderType.ZHIPU
    assert captured["model"] == "glm-5.2"
    assert wire_model == "glm-5.2"


# --- LIVE: gated single real call (skipped unless FORGE_LIVE=1) ---
@pytest.mark.skipif(
    os.environ.get("FORGE_LIVE") != "1",
    reason="live model call costs money; set FORGE_LIVE=1 to run",
)
def test_pool_completion_live_call_produces_verified_patch():
    model_id = os.environ.get("FORGE_LIVE_MODEL", "gpt-5")
    cand = LiveModel(PoolCompletion(model_id)).propose(ADD_TASK, 0)
    assert cand.tokens > 0
    assert verify(ADD_TASK, cand.patch) is True
