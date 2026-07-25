"""Moonshot/Kimi Open Platform provider shim.

This stays outside providers.py because that module is already above the
project's line-budget ceiling. Moonshot reuses the Kimi Code OpenAI-compatible
request/stream behavior but has its own key, default model, and provider family.
"""

from __future__ import annotations

import os

from dharma_swarm.api_keys import MOONSHOT_API_KEY_ENV
from dharma_swarm.base_provider import ProviderCapabilities
from dharma_swarm.model_hierarchy import default_model as canonical_default_model
from dharma_swarm.models import ProviderType
from dharma_swarm.providers import KimiCodeProvider


class MoonshotProvider(KimiCodeProvider):
    """Kimi Open Platform / Moonshot global OpenAI-compatible provider."""

    capabilities = ProviderCapabilities(
        supports_streaming=True,
        supports_tools=True,
        supports_thinking=True,
        supports_system_prompt=True,
        max_context_tokens=256_000,
        provider_family="moonshot",
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        self._api_key = api_key or os.environ.get(MOONSHOT_API_KEY_ENV)
        self._base_url = (base_url or "https://api.moonshot.ai/v1").rstrip("/")
        self._default_model = default_model or canonical_default_model(ProviderType.MOONSHOT)
        self._timeout = float(timeout)
        self._client = None
