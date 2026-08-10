from __future__ import annotations

from types import SimpleNamespace

import pytest

from dharma_swarm.forge_v1.providers import PoolCompletion


class _Provider:
    def __init__(self, *, usage: dict[str, int] | None = None) -> None:
        self.calls = 0
        self.request = None
        self.usage = usage or {"input_tokens": 10, "output_tokens": 20}

    async def complete(self, request):
        self.calls += 1
        self.request = request
        return SimpleNamespace(content="{}", usage=self.usage)

    async def close(self) -> None:
        return None


def _completion(provider: _Provider) -> PoolCompletion:
    completion = object.__new__(PoolCompletion)
    completion.model_id = "test-model"
    completion._wire_model = "test-model"
    completion._provider = provider
    return completion


def test_mutation_prompt_that_cannot_fit_is_refused_before_provider_call() -> None:
    provider = _Provider()

    with pytest.raises(RuntimeError, match="cannot fit"):
        _completion(provider).complete("x" * 100, max_total_tokens=600)

    assert provider.calls == 0


def test_mutation_completion_carries_remaining_hard_output_ceiling() -> None:
    provider = _Provider()

    text, tokens = _completion(provider).complete("x" * 10, max_total_tokens=600)

    assert text == "{}"
    assert tokens == 30
    assert provider.request.max_tokens == 78


def test_provider_usage_above_total_ceiling_fails_closed() -> None:
    provider = _Provider(usage={"input_tokens": 500, "output_tokens": 101})

    with pytest.raises(RuntimeError, match="usage exceeded"):
        _completion(provider).complete("x" * 10, max_total_tokens=600)
