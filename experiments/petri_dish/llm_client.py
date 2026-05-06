"""Thin async LLM client for OpenRouter.

Uses the canonical runtime provider factory so experiment code does not
instantiate provider SDK clients directly.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dharma_swarm.models import LLMRequest, ProviderType
from dharma_swarm.runtime_provider import (
    create_runtime_provider,
    resolve_runtime_provider_config,
)

logger = logging.getLogger(__name__)


class PetriDishLLM:
    """Minimal async OpenRouter client for the petri dish experiment."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._base_url = base_url
        self._total_calls = 0
        self._total_tokens = 0

    def _get_provider(self) -> Any:
        if not self._api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        config = resolve_runtime_provider_config(
            ProviderType.OPENROUTER,
            api_key=self._api_key,
            base_url=self._base_url,
        )
        return create_runtime_provider(config)

    async def complete(
        self,
        system: str,
        user_message: str,
        *,
        model: str = "meta-llama/llama-3.3-70b-instruct:free",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        messages: list[dict[str, str]] | None = None,
    ) -> str:
        """Single completion call. Returns content string.

        If `messages` is provided, it is used as the conversation history
        (system prompt is still prepended). Otherwise, a single user message
        is constructed from `user_message`.
        """
        provider = self._get_provider()

        msg_list: list[dict[str, str]] = [{"role": "system", "content": system}]
        if messages:
            msg_list.extend(messages)
        else:
            msg_list.append({"role": "user", "content": user_message})

        try:
            resp = await provider.complete(
                LLMRequest(
                    model=model,
                    messages=msg_list,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            self._total_calls += 1
            usage = resp.usage or {}
            self._total_tokens += int(usage.get("total_tokens", 0) or 0)
            return resp.content or ""
        except Exception as e:
            logger.error("LLM call failed (model=%s): %s", model, e)
            raise

    @property
    def stats(self) -> dict[str, int]:
        return {"total_calls": self._total_calls, "total_tokens": self._total_tokens}
