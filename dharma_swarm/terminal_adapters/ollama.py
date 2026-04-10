"""Ollama Cloud adapter — OpenAI-compatible chat completions via ollama.com."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any, AsyncIterator

import httpx

from dharma_swarm.ollama_config import OLLAMA_CLOUD_BASE_URL, resolve_ollama_base_url
from dharma_swarm.power_model_catalog import OLLAMA_CLOUD_POWER_MODELS
from .base import Capability, CompletionRequest, ModelProfile, ProviderAdapter, ProviderConfig
from dharma_swarm.terminal_engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    TextDelta,
    UsageReport,
)

OLLAMA_CAPABILITIES = (
    Capability.SYSTEM_PROMPT
    | Capability.COST_TRACKING
    | Capability.CANCEL
    | Capability.STREAMING
)

_CLOUD_MODELS: dict[str, str] = dict(OLLAMA_CLOUD_POWER_MODELS)


def _wire_model(model: str) -> str:
    stripped = (model or "").strip()
    if stripped.lower().endswith(":cloud"):
        return stripped[:-6]
    return stripped


class OllamaAdapter(ProviderAdapter):
    """Provider adapter for Ollama Cloud (ollama.com) chat completions."""

    provider_id = "ollama"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_id=self.provider_id,
            base_url=OLLAMA_CLOUD_BASE_URL,
            default_model="glm-5:cloud",
        )
        self._cancelled = False
        self._profiles = {
            model_id: ModelProfile(
                provider_id=self.provider_id,
                model_id=model_id,
                display_name=display_name,
                capabilities=OLLAMA_CAPABILITIES,
            )
            for model_id, display_name in _CLOUD_MODELS.items()
        }

    async def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        model = model_id or self._config.default_model or "glm-5:cloud"
        return self._profiles.get(model, next(iter(self._profiles.values())))

    async def stream(
        self, request: CompletionRequest, session_id: str
    ) -> AsyncIterator[SessionStart | TextDelta | TextComplete | UsageReport | ErrorEvent | SessionEnd]:
        profile = self.get_profile(request.model)
        model = request.model or profile.model_id
        wire_model = _wire_model(model)
        self._cancelled = False

        yield SessionStart(
            provider_id=self.provider_id,
            session_id=session_id,
            model=model,
            capabilities=[c.name.lower() for c in Capability if profile.capabilities & c],
            tools_available=[],
            system_info={"base_url": self._config.base_url or OLLAMA_CLOUD_BASE_URL},
        )

        api_key = (
            self._config.api_key
            or request.provider_options.get("ollama_api_key")
            or os.environ.get("OLLAMA_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        if not api_key:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="missing_api_key",
                message="OLLAMA_API_KEY (or OPENROUTER_API_KEY) not set",
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="missing_api_key",
                error_message="OLLAMA_API_KEY not set",
            )
            return

        base_url = resolve_ollama_base_url(
            base_url=self._config.base_url,
            api_key=api_key,
        ).rstrip("/")
        url = f"{base_url}/api/chat"

        messages = request.messages or []
        if request.system_prompt:
            messages = [{"role": "system", "content": request.system_prompt}] + messages

        payload = {"model": wire_model, "messages": messages, "stream": True}
        if request.max_tokens:
            payload["options"] = {"num_predict": int(request.max_tokens)}

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        timeout = float(request.provider_options.get("timeout_sec", 120))
        collected: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        error_text = ""
                        async for chunk in resp.aiter_text():
                            error_text += chunk
                            if len(error_text) > 500:
                                break
                        yield ErrorEvent(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            code=f"http_{resp.status_code}",
                            message=f"Ollama API error ({resp.status_code}): {error_text}",
                            retryable=resp.status_code >= 500,
                        )
                        yield SessionEnd(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            success=False,
                            error_code=f"http_{resp.status_code}",
                            error_message=error_text[:500],
                        )
                        return

                    async for line in resp.aiter_lines():
                        if self._cancelled:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue
                        msg = chunk.get("message", {})
                        if isinstance(msg, dict):
                            piece = msg.get("content", "")
                            if piece:
                                collected.append(piece)
                                yield TextDelta(
                                    provider_id=self.provider_id,
                                    session_id=session_id,
                                    content=piece,
                                    content_index=0,
                                    role="assistant",
                                )
                        if chunk.get("done"):
                            break

            if self._cancelled:
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="cancelled",
                    error_message="request cancelled",
                )
                return

            full_text = "".join(collected)
            if full_text:
                yield TextComplete(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    content=full_text,
                    content_index=0,
                    role="assistant",
                )

            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=True,
            )

        except httpx.TimeoutException:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="timeout",
                message="Ollama Cloud request timed out",
                retryable=True,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="timeout",
                error_message="request timed out",
            )
        except Exception as exc:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="request_error",
                message=str(exc),
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="request_error",
                error_message=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True

    async def close(self) -> None:
        pass
