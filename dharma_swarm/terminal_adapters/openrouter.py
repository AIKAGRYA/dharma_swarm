"""OpenRouter provider adapter (httpx async streaming -> canonical events)."""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any, AsyncIterator

import httpx

from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType

from .base import Capability, CompletionRequest, ModelProfile, ProviderAdapter, ProviderConfig
from dharma_swarm.terminal_engine.events import (
    ErrorEvent,
    SessionEnd,
    SessionStart,
    TextComplete,
    UsageReport,
)

OPENROUTER_CAPABILITIES = (
    Capability.SYSTEM_PROMPT
    | Capability.COST_TRACKING
    | Capability.CANCEL
)

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(ProviderAdapter):
    """ProviderAdapter implementation for OpenRouter (OpenAI-compatible chat completions)."""

    provider_id = "openrouter"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider_id=self.provider_id,
            base_url=_DEFAULT_BASE_URL,
            default_model=DEFAULT_MODELS.get(ProviderType.OPENROUTER, "xiaomi/mimo-v2-pro"),
        )
        self._cancelled = False
        self._response: httpx.Response | None = None

        # All OpenRouter models the swarm knows about. The adapter handles any
        # model ID — this list controls what appears in the terminal handshake.
        # Sources: agent_registry.MODEL_PRICING, free_fleet._TIER_RULES,
        # cross_pollination.py, provider_smoke.py, ginko_agents.py
        _OR_MODELS: dict[str, str] = {
            # Paid
            "xiaomi/mimo-v2-pro": "MiMo V2 Pro",
            "openai/gpt-5-codex": "GPT-5 Codex",
            "google/gemini-2.5-pro": "Gemini 2.5 Pro",
            "moonshotai/kimi-k2.5": "Kimi K2.5",
            "deepseek/deepseek-chat-v3-0324": "DeepSeek V3",
            "deepseek/deepseek-r1": "DeepSeek R1",
            # Free — Nemotron
            "nvidia/nemotron-3-super-120b-a12b:free": "Nemotron 3 Super 120B [FREE]",
            "nvidia/llama-3.1-nemotron-70b-instruct:free": "Nemotron 70B [FREE]",
            "nvidia/nemotron-nano-9b-v2:free": "Nemotron Nano 9B [FREE]",
            # Free — GLM
            "z-ai/glm-5": "GLM-5",
            "z-ai/glm-4.5-air:free": "GLM-4.5 Air [FREE]",
            "zhipuai/glm-5-plus": "GLM-5 Plus",
            # Free — Meta / Qwen / other
            "meta-llama/llama-3.3-70b-instruct:free": "Llama 3.3 70B [FREE]",
            "qwen/qwen3-coder:free": "Qwen3 Coder [FREE]",
            "qwen/qwen3-235b-a22b": "Qwen3 235B",
            "google/gemma-3-27b-it:free": "Gemma 3 27B [FREE]",
            "nousresearch/hermes-3-llama-3.1-405b:free": "Hermes 3 405B [FREE]",
        }
        self._profiles: dict[str, ModelProfile] = {
            model_id: ModelProfile(
                provider_id=self.provider_id,
                model_id=model_id,
                display_name=display_name,
                capabilities=OPENROUTER_CAPABILITIES,
            )
            for model_id, display_name in _OR_MODELS.items()
        }

    async def list_models(self) -> list[ModelProfile]:
        return list(self._profiles.values())

    def get_profile(self, model_id: str | None = None) -> ModelProfile:
        model = model_id or self._config.default_model or DEFAULT_MODELS.get(
            ProviderType.OPENROUTER, "xiaomi/mimo-v2-pro"
        )
        if model in self._profiles:
            return self._profiles[model]
        return ModelProfile(
            provider_id=self.provider_id,
            model_id=model,
            display_name=model,
            capabilities=OPENROUTER_CAPABILITIES,
        )

    async def stream(
        self,
        request: CompletionRequest,
        session_id: str,
    ) -> AsyncIterator[SessionStart | TextComplete | UsageReport | ErrorEvent | SessionEnd]:
        profile = self.get_profile(request.model)
        model = request.model or profile.model_id
        self._cancelled = False

        yield SessionStart(
            provider_id=self.provider_id,
            session_id=session_id,
            model=model,
            capabilities=[c.name.lower() for c in Capability if profile.capabilities & c],
            tools_available=[],
            system_info={"base_url": self._config.base_url or _DEFAULT_BASE_URL},
        )

        api_key = (
            self._config.api_key
            or request.provider_options.get("openrouter_api_key")
            or os.environ.get("OPENROUTER_API_KEY")
        )
        if not api_key:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="missing_api_key",
                message="OPENROUTER_API_KEY not set",
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="missing_api_key",
                error_message="OPENROUTER_API_KEY not set",
            )
            return

        base_url = (self._config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        url = f"{base_url}/chat/completions"

        messages = list(request.messages or [])
        if request.system_prompt:
            messages = [{"role": "system", "content": request.system_prompt}, *messages]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = int(request.max_tokens)
        if request.temperature is not None:
            payload["temperature"] = float(request.temperature)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/dharma-swarm",
            "X-Title": "dharma_swarm",
        }

        timeout_sec = float(request.provider_options.get("timeout_sec", 120))
        collected_text: list[str] = []
        usage_data: dict[str, Any] = {}
        cost: float | None = None

        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as resp:
                    self._response = resp
                    if resp.status_code >= 400:
                        error_body = ""
                        async for chunk in resp.aiter_text():
                            error_body += chunk
                            if len(error_body) > 1000:
                                break
                        code = "rate_limited" if resp.status_code == 429 else f"http_{resp.status_code}"
                        msg = error_body.strip()[:1000] or f"HTTP {resp.status_code}"
                        yield ErrorEvent(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            code=code,
                            message=msg,
                            retryable=resp.status_code in {408, 409, 429, 500, 502, 503, 504},
                        )
                        yield SessionEnd(
                            provider_id=self.provider_id,
                            session_id=session_id,
                            success=False,
                            error_code=code,
                            error_message=msg,
                        )
                        return

                    async for line in resp.aiter_lines():
                        if self._cancelled:
                            break

                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith(":"):
                            continue
                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = _parse_json(data_str)
                        except Exception:
                            continue

                        if not isinstance(data, dict):
                            continue

                        chunk_usage = data.get("usage")
                        if isinstance(chunk_usage, dict):
                            usage_data = chunk_usage

                        chunk_cost = _extract_cost(data)
                        if chunk_cost is not None:
                            cost = chunk_cost

                        content_piece = _extract_delta_content(data)
                        if content_piece:
                            collected_text.append(content_piece)

                    self._response = None

            if self._cancelled:
                yield SessionEnd(
                    provider_id=self.provider_id,
                    session_id=session_id,
                    success=False,
                    error_code="cancelled",
                    error_message="request cancelled",
                )
                return

            full_text = "".join(collected_text)
            yield TextComplete(
                provider_id=self.provider_id,
                session_id=session_id,
                content=full_text,
                role="assistant",
            )
            yield UsageReport(
                provider_id=self.provider_id,
                session_id=session_id,
                input_tokens=int(usage_data.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage_data.get("completion_tokens", 0) or 0),
                total_cost_usd=cost or 0.0,
                model_breakdown=usage_data if isinstance(usage_data, dict) else {},
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
                message="OpenRouter request timed out",
                retryable=True,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="timeout",
                error_message="OpenRouter request timed out",
            )
        except Exception as exc:
            yield ErrorEvent(
                provider_id=self.provider_id,
                session_id=session_id,
                code="openrouter_error",
                message=str(exc),
                retryable=False,
            )
            yield SessionEnd(
                provider_id=self.provider_id,
                session_id=session_id,
                success=False,
                error_code="openrouter_error",
                error_message=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True
        resp = self._response
        if resp is not None:
            with contextlib.suppress(Exception):
                await resp.aclose()
        await asyncio.sleep(0)

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.cancel()


def _parse_json(s: str) -> Any:
    import json
    return json.loads(s)


def _extract_delta_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta", {})
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    return ""


def _extract_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message", {})
    if isinstance(msg, dict):
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str):
                        chunks.append(txt)
            if chunks:
                return "\n".join(chunks)
        reasoning = msg.get("reasoning", "")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning
        details = msg.get("reasoning_details", [])
        if isinstance(details, list):
            chunks = []
            for item in details:
                if isinstance(item, dict):
                    txt = item.get("text")
                    if isinstance(txt, str) and txt.strip():
                        chunks.append(txt)
            if chunks:
                return "\n".join(chunks)
    return ""


def _extract_cost(data: Any) -> float | None:
    if not isinstance(data, dict):
        return None
    usage = data.get("usage", {})
    if isinstance(usage, dict):
        for key in ("total_cost", "cost"):
            if key in usage:
                try:
                    return float(usage[key])
                except Exception:
                    pass
    return None
